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
            msg = "lease_duration must be positive"
            raise ValueError(msg)
        if self.base_retry_seconds < 1:
            msg = "base_retry_seconds must be positive"
            raise ValueError(msg)
        if self.max_retry_seconds < self.base_retry_seconds:
            msg = "max_retry_seconds must cover the base delay"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class JobSubmission:
    """Validated immutable input used to create one pending queue job."""

    tenant_id: str
    workspace_id: str
    job_id: str
    job_type: str
    idempotency_key: str
    payload: tuple[tuple[str, object], ...]
    max_attempts: int

    def __post_init__(self) -> None:
        """Validate scope, identity, retry policy, and payload ordering."""
        identities = (
            self.tenant_id,
            self.workspace_id,
            self.job_id,
            self.job_type,
            self.idempotency_key,
        )
        if any(not value.strip() for value in identities):
            msg = "job scope and identities are required"
            raise ValueError(msg)
        if self.max_attempts < 1:
            msg = "max_attempts must be positive"
            raise ValueError(msg)
        object.__setattr__(self, "payload", tuple(sorted(self.payload)))


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
    def pending(cls, submission: JobSubmission, now: datetime) -> WorkspaceJob:
        """Create one durable pending job from validated submission data."""
        if now.tzinfo is None or now.utcoffset() is None:
            msg = "job timestamps must be timezone-aware"
            raise ValueError(msg)
        return cls(
            tenant_id=submission.tenant_id,
            workspace_id=submission.workspace_id,
            job_id=submission.job_id,
            job_type=submission.job_type,
            idempotency_key=submission.idempotency_key,
            payload=submission.payload,
            state=JobState.PENDING,
            attempts=0,
            max_attempts=submission.max_attempts,
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
            msg = "job_id already exists"
            raise ValueError(msg)
        self._jobs[job.job_id] = job
        self._idempotency[key] = job.job_id
        return job

    def claim_next(self, *, worker_id: str, now: datetime) -> WorkspaceJob | None:
        """Claim one eligible job using tenant-fair deterministic ordering."""
        if not worker_id.strip():
            msg = "worker_id is required"
            raise ValueError(msg)
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
            msg = "failure reason is required"
            raise ValueError(msg)
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
            msg = "only dead-letter jobs can be replayed"
            raise ValueError(msg)
        if not authorized_by.strip():
            msg = "controlled replay requires an authorizing actor"
            raise ValueError(msg)
        replay = WorkspaceJob.pending(
            JobSubmission(
                tenant_id=original.tenant_id,
                workspace_id=original.workspace_id,
                job_id=replay_job_id,
                job_type=original.job_type,
                idempotency_key=(f"replay:{replay_job_id}:{original.idempotency_key}"),
                payload=original.payload,
                max_attempts=original.max_attempts,
            ),
            now,
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
            msg = "worker does not own a live job lease"
            raise ValueError(msg)
        return current


class SchedulerFence:
    """Reference exclusive scheduler ownership matching an advisory-lock contract."""

    def __init__(self) -> None:
        """Initialize an empty in-memory scheduler-fence registry."""
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
            msg = "scheduler does not own the fence"
            raise ValueError(msg)
        del self._owners[schedule_key]


def retry_delay_seconds(
    idempotency_key: str,
    attempt: int,
    policy: QueuePolicy,
) -> int:
    """Return deterministic bounded exponential backoff with hash-derived jitter."""
    if attempt < 1:
        msg = "attempt must be positive"
        raise ValueError(msg)
    exponential = min(
        policy.max_retry_seconds,
        policy.base_retry_seconds * (2 ** (attempt - 1)),
    )
    digest = hashlib.sha256(f"{idempotency_key}:{attempt}".encode()).digest()
    jitter_ceiling = max(1, exponential // 4)
    jitter = int.from_bytes(digest[:4], "big") % (jitter_ceiling + 1)
    return min(policy.max_retry_seconds, exponential + jitter)
