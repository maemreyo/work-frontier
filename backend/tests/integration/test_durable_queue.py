from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from work_frontier.platform.queue import (
    DurableQueue,
    JobState,
    QueuePolicy,
    SchedulerFence,
    WorkspaceJob,
    retry_delay_seconds,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def job(job_id: str, tenant: str = "t1", workspace: str = "w1") -> WorkspaceJob:
    return WorkspaceJob.pending(
        tenant_id=tenant,
        workspace_id=workspace,
        job_id=job_id,
        job_type="sync",
        idempotency_key=f"key-{job_id}",
        payload=(("job", job_id),),
        max_attempts=3,
        now=NOW,
    )


def test_idempotent_enqueue_and_claim_ownership() -> None:
    queue = DurableQueue(policy=QueuePolicy())
    first = queue.enqueue(job("a"))
    second = queue.enqueue(job("a"))
    assert first == second
    claimed = queue.claim_next(worker_id="worker-1", now=NOW)
    assert claimed is not None
    assert claimed.state is JobState.CLAIMED
    assert claimed.lease_owner == "worker-1"
    assert queue.claim_next(worker_id="worker-2", now=NOW) is None


def test_lease_losing_worker_cannot_complete() -> None:
    queue = DurableQueue(policy=QueuePolicy(lease_duration=timedelta(seconds=5)))
    _ = queue.enqueue(job("a"))
    claimed = queue.claim_next(worker_id="worker-1", now=NOW)
    assert claimed is not None
    recovered = queue.recover_expired(now=NOW + timedelta(seconds=6))
    assert recovered
    claimed_again = queue.claim_next(
        worker_id="worker-2",
        now=NOW + timedelta(seconds=7),
    )
    assert claimed_again is not None
    with pytest.raises(ValueError):
        _ = queue.complete(
            job_id="a",
            worker_id="worker-1",
            now=NOW + timedelta(seconds=7),
            result=(("ok", True),),
        )


def test_retry_dead_letter_and_controlled_replay() -> None:
    queue = DurableQueue(policy=QueuePolicy(base_retry_seconds=2, max_retry_seconds=30))
    _ = queue.enqueue(job("a"))
    failed: WorkspaceJob | None = None
    for attempt in range(3):
        claimed = queue.claim_next(
            worker_id="worker",
            now=NOW + timedelta(seconds=100 * attempt),
        )
        assert claimed is not None
        failed = queue.fail(
            job_id="a",
            worker_id="worker",
            now=NOW + timedelta(seconds=100 * attempt),
            reason="poison",
            retryable=True,
        )
    assert failed is not None
    assert failed.state is JobState.DEAD_LETTER
    replay = queue.replay_dead_letter(
        job_id="a",
        replay_job_id="a-replay",
        authorized_by="admin",
        now=NOW + timedelta(seconds=400),
    )
    assert replay.replay_of == "a"
    assert replay.state is JobState.PENDING


def test_fair_claiming_rotates_tenants() -> None:
    queue = DurableQueue(policy=QueuePolicy())
    _ = queue.enqueue(job("a1", tenant="a", workspace="wa"))
    _ = queue.enqueue(job("a2", tenant="a", workspace="wa"))
    _ = queue.enqueue(job("b1", tenant="b", workspace="wb"))
    first = queue.claim_next(worker_id="w1", now=NOW)
    assert first is not None
    _ = queue.complete(first.job_id, "w1", NOW, (("ok", True),))
    second = queue.claim_next(worker_id="w2", now=NOW)
    assert second is not None
    assert first.tenant_id != second.tenant_id


def test_scheduler_fence_prevents_overlap() -> None:
    fence = SchedulerFence()
    assert fence.acquire("reconcile", "scheduler-1") is True
    assert fence.acquire("reconcile", "scheduler-2") is False
    fence.release("reconcile", "scheduler-1")
    assert fence.acquire("reconcile", "scheduler-2") is True


def test_retry_jitter_is_deterministic_and_bounded() -> None:
    policy = QueuePolicy(base_retry_seconds=2, max_retry_seconds=60)
    first = retry_delay_seconds("same-key", 3, policy)
    second = retry_delay_seconds("same-key", 3, policy)
    assert first == second
    assert 0 < first <= policy.max_retry_seconds
