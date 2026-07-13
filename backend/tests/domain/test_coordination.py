from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from work_frontier.domain.coordination import (
    AttentionState,
    ClaimError,
    ClaimRequest,
    LeaseMode,
    claim_item,
    force_override,
    heartbeat,
    open_attention,
    release,
    request_handoff,
    resolve_attention,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _request(actor: str = "builder-1") -> ClaimRequest:
    return ClaimRequest(
        lease_id="lease-1",
        item_id="item-1",
        actor=actor,
        mode=LeaseMode.EXCLUSIVE,
        decision_id="decision-1",
        expected_version=0,
        ttl=timedelta(minutes=10),
    )


def test_exclusive_claim_race_has_one_winner() -> None:
    first = claim_item(None, _request(), current_decision_id="decision-1", now=NOW)
    with pytest.raises(ClaimError, match="already claimed"):
        _ = claim_item(
            first, _request("builder-2"), current_decision_id="decision-1", now=NOW
        )


def test_stale_decision_cannot_support_claim() -> None:
    with pytest.raises(ClaimError, match="stale DecisionRecord"):
        _ = claim_item(None, _request(), current_decision_id="decision-2", now=NOW)


def test_heartbeat_handoff_release_and_forced_override_are_auditable() -> None:
    lease = claim_item(None, _request(), current_decision_id="decision-1", now=NOW)
    renewed = heartbeat(lease, actor="builder-1", now=NOW + timedelta(minutes=1))
    assert renewed.version == 2

    handoff = request_handoff(renewed, actor="coordinator-1", target="builder-2")
    assert handoff.handoff_to == "builder-2"

    overridden, event = force_override(
        handoff,
        actor="admin-1",
        new_owner="builder-3",
        reason="incident recovery requires explicit reassignment",
        now=NOW,
    )
    assert overridden.owner == "builder-3"
    assert event.event_type == "lease_forced_override"

    released = release(overridden, actor="builder-3", now=NOW)
    assert released.state.value == "released"


def test_attention_identity_and_resolution_are_deterministic() -> None:
    first = open_attention(
        item_id="item-1",
        category="stale_source",
        severity="warning",
        deterministic_basis="source=github;revision=old",
        opened_at=NOW,
    )
    second = open_attention(
        item_id="item-1",
        category="stale_source",
        severity="warning",
        deterministic_basis="source=github;revision=old",
        opened_at=NOW,
    )
    assert first.attention_id == second.attention_id
    resolved = resolve_attention(
        first, actor="operator-1", resolution="refetched", now=NOW
    )
    assert resolved.state is AttentionState.RESOLVED
