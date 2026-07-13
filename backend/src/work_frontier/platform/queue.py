"""Deterministic durable-queue state machine and ownership semantics."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum


class JobState(StrEnum):
    """Durable ingestion and worker lifecycle states."""

    RECEIVED = "received"
    VERIFIED = "verified"
    PERSISTED = "persisted"
    PENDING = "pending"
    CLAIMED = "claimed"
    REFETCHED = "refetched"
    NORMALIZED = "normalized"
    SOLVED = "solved"
    PROJECTED = "projected"
    COMPLETED = "completed"
    RETRY_SCHEDULED = "retry_scheduled"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True, slots=True)
class QueuePolicy:
    """Versionable lease and retry policy."""

    lease_duration: timedelta = timedelta(seconds=30)
    base_retry_seconds: int = 1
    max_retry_seconds: int = 300

    def __post_init__(self) -> None:
        """Require positive bounded queue policy values."""
        if self.lease_duration <= timedelta(0):
            raise ValueError("lease_duration must be positive")
        if self.base_retry_seconds < 1:
            raise ValueError("base_retry_seconds must be positive")
        if self.max_retry_seconds < self.base_retry_seconds:
            raise ValueError("max_retry_seconds must cover the base delay")


@dataclass(frozen=True, slots=True)
class WorkspaceJob:
    """Workspace-scoped immutable job snapshot with preserved attempt history."""

    tenant_id: str
    workspace_id: str
    job_id: str
    job_type: str
    idempotency_key: str
    payload: tuple[tuple[str, object], ...]
    state: JobState
    attempts: int
    max_attempts: int
    next_attempt_at: datetime
    created_at: datetime
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    heartbeat_at: datetime | None = None
    completed_at: datetime | None = None
    result: tuple[tuple[str, object], ...] | None = None
    dead_letter_reason: str | None = None
    replay_of: str | None = None
    attempt_history: tuple[str, ...] = ()

    @classmethod
    def pending(
        cls,
        *,
        tenant_id: str,
        workspace_id: str,
        job_id: str,
        job_type: str,
        idempotency_key: str,
        payload: tuple[tuple[str, object], ...],
        max_attempts: int,
        now: datetime,
    ) -> WorkspaceJob:
        """Create one durable pending job."""
        if any(
            not value.strip()
            for value in (tenant_id, workspace_id, job_id, job_type, idempotency_key)
        ):
            raise ValueError("job scope and identities are required")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("job timestamps must be timezone-aware")
        ordered_payload = tuple(sorted(payload))
        return cls(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            job_id=job_id,
            job_type=job_type,
            idempotency_key=idempotency_key,
            payload=ordered_payload,
            state=JobState.PENDING,
            attempts=0,
            max_attempts=max_attempts,
            next_attempt_at=now,
            created_at=now,
        )


class DurableQueue:
    """Reference state machine mirroring PostgreSQL CAS and fair-claim behavior."""

    _policy: QueuePolicy
    _jobs: dict[str, WorkspaceJob]
    _idempotency: dict[tuple[str, str, str], str]
    _tenant_last_claim: dict[str, int]
    _claim_counter: int

    def __init__(self, *, policy: QueuePolicy) -> None:
        """Initialize isolated queue state."""
        self._policy = policy
        self._jobs = {}
        self._idempotency = {}
        self._tenant_last_claim = {}
        self._claim_counter = 0

    def enqueue(self, job: WorkspaceJob) -> WorkspaceJob:
        """Deduplicate by tenant/workspace/idempotency key before accepting."""
        key = (job.tenant_id, job.workspace_id, job.idempotency_key)
        existing_id = self._idempotency.get(key)
        if existing_id is not None:
            return self._jobs[existing_id]
        if job.job_id in self._jobs:
            raise ValueError("job_id already exists")
        self._jobs[job.job_id] = job
        self._idempotency[key] = job.job_id
        return job

    def claim_next(self, *, worker_id: str, now: datetime) -> WorkspaceJob | None:
        """Claim one eligible job using tenant-fair deterministic ordering."""
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        eligible = [
            job
            for job in self._jobs.values()
            if job.state in {JobState.PENDING, JobState.RETRY_SCHEDULED}
            and job.next_attempt_at <= now
        ]
        if not eligible:
            return None
        eligible.sort(
            key=lambda job: (
                self._tenant_last_claim.get(job.tenant_id, -1),
                job.created_at,
                job.tenant_id,
                job.workspace_id,
                job.job_id,
            )
        )
        selected = eligible[0]
        self._claim_counter += 1
        self._tenant_last_claim[selected.tenant_id] = self._claim_counter
        claimed = replace(
            selected,
            state=JobState.CLAIMED,
            lease_owner=worker_id,
            lease_expires_at=now + self._policy.lease_duration,
            heartbeat_at=now,
            attempt_history=(
                *selected.attempt_history,
                f"claimed:{worker_id}:{now.isoformat()}",
            ),
        )
        self._jobs[selected.job_id] = claimed
        return claimed

    def heartbeat(self, job_id: str, worker_id: str, now: datetime) -> WorkspaceJob:
        """Extend a live lease only for its current owner."""
        current = self._owned_claim(job_id, worker_id, now)
        updated = replace(
            current,
            lease_expires_at=now + self._policy.lease_duration,
            heartbeat_at=now,
        )
        self._jobs[job_id] = updated
        return updated

    def complete(
        self,
        job_id: str,
        worker_id: str,
        now: datetime,
        result: tuple[tuple[str, object], ...],
    ) -> WorkspaceJob:
        """Complete only through lease-owner compare-and-swap semantics."""
        current = self._owned_claim(job_id, worker_id, now)
        updated = replace(
            current,
            state=JobState.COMPLETED,
            completed_at=now,
            result=tuple(sorted(result)),
            lease_owner=None,
            lease_expires_at=None,
            heartbeat_at=None,
            attempt_history=(
                *current.attempt_history,
                f"completed:{worker_id}:{now.isoformat()}",
            ),
        )
        self._jobs[job_id] = updated
        return updated

    def fail(
        self,
        *,
        job_id: str,
        worker_id: str,
        now: datetime,
        reason: str,
        retryable: bool,
    ) -> WorkspaceJob:
        """Schedule a bounded retry or quarantine an exhausted poison job."""
        if not reason.strip():
            raise ValueError("failure reason is required")
        current = self._owned_claim(job_id, worker_id, now)
        attempts = current.attempts + 1
        history = (
            *current.attempt_history,
            f"failed:{worker_id}:{reason}:{now.isoformat()}",
        )
        if not retryable or attempts >= current.max_attempts:
            updated = replace(
                current,
                state=JobState.DEAD_LETTER,
                attempts=attempts,
                dead_letter_reason=reason,
                lease_owner=None,
                lease_expires_at=None,
                heartbeat_at=None,
                attempt_history=history,
            )
        else:
            delay = retry_delay_seconds(current.idempotency_key, attempts, self._policy)
            updated = replace(
                current,
                state=JobState.RETRY_SCHEDULED,
                attempts=attempts,
                next_attempt_at=now + timedelta(seconds=delay),
                lease_owner=None,
                lease_expires_at=None,
                heartbeat_at=None,
                attempt_history=history,
            )
        self._jobs[job_id] = updated
        return updated

    def recover_expired(self, *, now: datetime) -> tuple[WorkspaceJob, ...]:
        """Reclaim expired leases without allowing stale owners to complete."""
        recovered: list[WorkspaceJob] = []
        for job in tuple(self._jobs.values()):
            if (
                job.state is JobState.CLAIMED
                and job.lease_expires_at is not None
                and job.lease_expires_at < now
            ):
                attempts = job.attempts + 1
                if attempts >= job.max_attempts:
                    updated = replace(
                        job,
                        state=JobState.DEAD_LETTER,
                        attempts=attempts,
                        dead_letter_reason="lease_expired",
                        lease_owner=None,
                        lease_expires_at=None,
                        heartbeat_at=None,
                    )
                else:
                    updated = replace(
                        job,
                        state=JobState.PENDING,
                        attempts=attempts,
                        next_attempt_at=now,
                        lease_owner=None,
                        lease_expires_at=None,
                        heartbeat_at=None,
                        attempt_history=(
                            *job.attempt_history,
                            f"lease_expired:{now.isoformat()}",
                        ),
                    )
                self._jobs[job.job_id] = updated
                recovered.append(updated)
        return tuple(sorted(recovered, key=lambda item: item.job_id))

    def replay_dead_letter(
        self,
        *,
        job_id: str,
        replay_job_id: str,
        authorized_by: str,
        now: datetime,
    ) -> WorkspaceJob:
        """Create an auditable new job from one quarantined original."""
        original = self._jobs[job_id]
        if original.state is not JobState.DEAD_LETTER:
            raise ValueError("only dead-letter jobs can be replayed")
        if not authorized_by.strip():
            raise ValueError("controlled replay requires an authorizing actor")
        replay = WorkspaceJob.pending(
            tenant_id=original.tenant_id,
            workspace_id=original.workspace_id,
            job_id=replay_job_id,
            job_type=original.job_type,
            idempotency_key=f"replay:{replay_job_id}:{original.idempotency_key}",
            payload=original.payload,
            max_attempts=original.max_attempts,
            now=now,
        )
        replay = replace(
            replay,
            replay_of=original.job_id,
            attempt_history=(f"replayed_by:{authorized_by}:{now.isoformat()}",),
        )
        return self.enqueue(replay)

    def get(self, job_id: str) -> WorkspaceJob:
        """Return one immutable job snapshot."""
        return self._jobs[job_id]

    def _owned_claim(self, job_id: str, worker_id: str, now: datetime) -> WorkspaceJob:
        current = self._jobs[job_id]
        if (
            current.state is not JobState.CLAIMED
            or current.lease_owner != worker_id
            or current.lease_expires_at is None
            or current.lease_expires_at < now
        ):
            raise ValueError("worker does not own a live job lease")
        return current


class SchedulerFence:
    """Reference exclusive scheduler ownership matching an advisory-lock contract."""

    def __init__(self) -> None:
        self._owners: dict[str, str] = {}

    def acquire(self, schedule_key: str, owner: str) -> bool:
        """Acquire only when no other scheduler owns the key."""
        current = self._owners.get(schedule_key)
        if current is not None and current != owner:
            return False
        self._owners[schedule_key] = owner
        return True

    def release(self, schedule_key: str, owner: str) -> None:
        """Release only the caller's own fence."""
        if self._owners.get(schedule_key) != owner:
            raise ValueError("scheduler does not own the fence")
        del self._owners[schedule_key]


def retry_delay_seconds(
    idempotency_key: str,
    attempt: int,
    policy: QueuePolicy,
) -> int:
    """Return deterministic bounded exponential backoff with hash-derived jitter."""
    if attempt < 1:
        raise ValueError("attempt must be positive")
    exponential = min(
        policy.max_retry_seconds,
        policy.base_retry_seconds * (2 ** (attempt - 1)),
    )
    digest = hashlib.sha256(f"{idempotency_key}:{attempt}".encode()).digest()
    jitter_ceiling = max(1, exponential // 4)
    jitter = int.from_bytes(digest[:4], "big") % (jitter_ceiling + 1)
    return min(policy.max_retry_seconds, exponential + jitter)
