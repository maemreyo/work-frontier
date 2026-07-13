"""PostgreSQL durable inbox, queue, outbox, and scheduler fencing operations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from work_frontier.platform.persistence.scope import WorkspaceScope

CLAIM_SQL: Final = text(
    """
    WITH candidate AS (
      SELECT tenant_id, workspace_id, job_id
      FROM job_queue
      WHERE state IN ('pending', 'retry_scheduled')
        AND next_attempt_at <= :now
      ORDER BY attempts ASC, next_attempt_at ASC, created_at ASC, job_id ASC
      FOR UPDATE SKIP LOCKED
      LIMIT 1
    )
    UPDATE job_queue AS jobs
    SET state = 'claimed',
        lease_owner = :worker_id,
        lease_expires_at = :lease_expires_at,
        heartbeat_at = :now,
        claimed_at = COALESCE(claimed_at, :now),
        attempt_history = attempt_history || CAST(:history AS jsonb)
    FROM candidate
    WHERE jobs.tenant_id = candidate.tenant_id
      AND jobs.workspace_id = candidate.workspace_id
      AND jobs.job_id = candidate.job_id
    RETURNING jobs.*
    """
)


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    """Minimal immutable claimed-job identity returned to a worker."""

    job_id: str
    tenant_id: str
    workspace_id: str
    lease_owner: str
    lease_expires_at: datetime
    attempts: int


async def persist_inbox_before_ack(
    session: AsyncSession,
    scope: WorkspaceScope,
    *,
    delivery_id: str,
    payload_hash: str,
    payload_json: str,
) -> bool:
    """Durably deduplicate a webhook before the caller acknowledges delivery."""
    result = await session.execute(
        text(
            """
            INSERT INTO webhook_inbox
              (tenant_id, workspace_id, delivery_id, payload_hash, state, payload)
            VALUES
              (:tenant_id, :workspace_id, :delivery_id, :payload_hash,
               'received', CAST(:payload AS jsonb))
            ON CONFLICT (tenant_id, workspace_id, delivery_id) DO NOTHING
            RETURNING 1
            """
        ),
        {
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "delivery_id": delivery_id,
            "payload_hash": payload_hash,
            "payload": payload_json,
        },
    )
    return result.scalar_one_or_none() is not None


async def enqueue_job(
    session: AsyncSession,
    scope: WorkspaceScope,
    *,
    job_id: str,
    job_type: str,
    idempotency_key: str,
    payload_json: str,
    max_attempts: int,
    now: datetime,
) -> bool:
    """Insert one workspace-scoped job exactly once by idempotency key."""
    result = await session.execute(
        text(
            """
            INSERT INTO job_queue
              (tenant_id, workspace_id, job_id, job_type, state,
               idempotency_key, payload, attempts, max_attempts,
               next_attempt_at, attempt_history, created_at)
            VALUES
              (:tenant_id, :workspace_id, :job_id, :job_type, 'pending',
               :idempotency_key, CAST(:payload AS jsonb), 0, :max_attempts,
               :now, '[]'::jsonb, :now)
            ON CONFLICT (tenant_id, workspace_id, idempotency_key) DO NOTHING
            RETURNING 1
            """
        ),
        {
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "job_id": job_id,
            "job_type": job_type,
            "idempotency_key": idempotency_key,
            "payload": payload_json,
            "max_attempts": max_attempts,
            "now": now,
        },
    )
    return result.scalar_one_or_none() is not None


async def claim_next_job(
    session: AsyncSession,
    *,
    worker_id: str,
    now: datetime,
    lease_duration: timedelta,
) -> ClaimedJob | None:
    """Claim one eligible row using FOR UPDATE SKIP LOCKED and owner fencing."""
    row = (
        (
            await session.execute(
                CLAIM_SQL,
                {
                    "worker_id": worker_id,
                    "now": now,
                    "lease_expires_at": now + lease_duration,
                    "history": f'["claimed:{worker_id}:{now.isoformat()}"]',
                },
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return ClaimedJob(
        job_id=str(row["job_id"]),
        tenant_id=str(row["tenant_id"]),
        workspace_id=str(row["workspace_id"]),
        lease_owner=str(row["lease_owner"]),
        lease_expires_at=row["lease_expires_at"],
        attempts=int(row["attempts"]),
    )


async def heartbeat_job(
    session: AsyncSession,
    *,
    job_id: str,
    worker_id: str,
    now: datetime,
    lease_duration: timedelta,
) -> bool:
    """Extend a lease only while its current owner still holds it."""
    result = await session.execute(
        text(
            """
            UPDATE job_queue
            SET heartbeat_at = :now, lease_expires_at = :lease_expires_at
            WHERE job_id = :job_id AND state = 'claimed'
              AND lease_owner = :worker_id AND lease_expires_at >= :now
            RETURNING 1
            """
        ),
        {
            "job_id": job_id,
            "worker_id": worker_id,
            "now": now,
            "lease_expires_at": now + lease_duration,
        },
    )
    return result.scalar_one_or_none() is not None


async def complete_job(
    session: AsyncSession,
    *,
    job_id: str,
    worker_id: str,
    now: datetime,
    result_json: str,
) -> bool:
    """Complete through a lease-owner compare-and-swap; stale workers lose."""
    result = await session.execute(
        text(
            """
            UPDATE job_queue
            SET state = 'completed', result = CAST(:result AS jsonb),
                completed_at = :now, lease_owner = NULL,
                lease_expires_at = NULL, heartbeat_at = NULL
            WHERE job_id = :job_id AND state = 'claimed'
              AND lease_owner = :worker_id AND lease_expires_at >= :now
            RETURNING 1
            """
        ),
        {
            "job_id": job_id,
            "worker_id": worker_id,
            "now": now,
            "result": result_json,
        },
    )
    return result.scalar_one_or_none() is not None


def retry_delay_seconds(idempotency_key: str, attempt: int) -> int:
    """Return bounded deterministic exponential backoff plus stable jitter."""
    if attempt < 1:
        raise ValueError("attempt must be positive")
    base = min(3_600, 5 * (2 ** (attempt - 1)))
    jitter = int.from_bytes(
        hashlib.sha256(f"{idempotency_key}:{attempt}".encode()).digest()[:4],
        "big",
    ) % (max(1, base // 4) + 1)
    return min(3_600, base + jitter)


async def acquire_scheduler_fence(
    session: AsyncSession,
    scope: WorkspaceScope,
    *,
    schedule_key: str,
    owner: str,
    now: datetime,
    lease_duration: timedelta,
) -> bool:
    """Acquire or renew one scheduler key while rejecting overlapping owners."""
    result = await session.execute(
        text(
            """
            INSERT INTO scheduler_leases
              (tenant_id, workspace_id, schedule_key, lease_owner,
               lease_expires_at, version)
            VALUES
              (:tenant_id, :workspace_id, :schedule_key, :owner,
               :lease_expires_at, 1)
            ON CONFLICT (tenant_id, workspace_id, schedule_key)
            DO UPDATE SET
              lease_owner = EXCLUDED.lease_owner,
              lease_expires_at = EXCLUDED.lease_expires_at,
              version = scheduler_leases.version + 1
            WHERE scheduler_leases.lease_owner = EXCLUDED.lease_owner
               OR scheduler_leases.lease_expires_at < :now
            RETURNING 1
            """
        ),
        {
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "schedule_key": schedule_key,
            "owner": owner,
            "lease_expires_at": now + lease_duration,
            "now": now,
        },
    )
    return result.scalar_one_or_none() is not None
