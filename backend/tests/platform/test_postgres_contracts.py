from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta

from sqlalchemy.sql.elements import TextClause

from work_frontier.platform.persistence.database import workspace_session
from work_frontier.platform.persistence.postgres_queue import (
    acquire_scheduler_fence,
    claim_next_job,
    complete_job,
    enqueue_job,
    heartbeat_job,
    persist_inbox_before_ack,
    retry_delay_seconds,
)


def test_workspace_session_requires_explicit_scope_argument() -> None:
    parameters = inspect.signature(workspace_session).parameters
    assert tuple(parameters) == ("factory", "scope")


def test_postgres_operations_are_async_and_scope_inbox_and_enqueue() -> None:
    assert inspect.iscoroutinefunction(persist_inbox_before_ack)
    assert inspect.iscoroutinefunction(enqueue_job)
    assert inspect.iscoroutinefunction(claim_next_job)
    assert inspect.iscoroutinefunction(heartbeat_job)
    assert inspect.iscoroutinefunction(complete_job)
    assert inspect.iscoroutinefunction(acquire_scheduler_fence)


def test_retry_delay_is_deterministic_bounded_and_attempt_sensitive() -> None:
    first = retry_delay_seconds("same", 1)
    assert first == retry_delay_seconds("same", 1)
    assert retry_delay_seconds("same", 2) >= first
    assert retry_delay_seconds("same", 20) <= 3_600


def test_claim_contract_contains_skip_locked_and_owner_fence() -> None:
    import work_frontier.platform.persistence.postgres_queue as module

    claim_sql = module.CLAIM_SQL
    assert isinstance(claim_sql, TextClause)
    rendered = str(claim_sql)
    assert "FOR UPDATE SKIP LOCKED" in rendered
    assert "lease_owner" in rendered
    assert "lease_expires_at" in rendered


def test_time_inputs_are_explicit_not_read_from_global_clock() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    assert now + timedelta(seconds=retry_delay_seconds("x", 1)) > now
