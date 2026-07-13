from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from work_frontier.domain.proposals import (
    Approval,
    FieldChange,
    ProposalError,
    ProposedChange,
    apply_approved_change,
    create_override,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _proposal() -> ProposedChange:
    return ProposedChange.create(
        proposal_id="proposal-1",
        item_id="item-1",
        proposer="builder-1",
        base_decision_id="decision-1",
        expected_source_revision="rev-1",
        changes=(FieldChange("dependency", "old", "new"),),
        created_at=NOW,
    )


def test_proposal_requires_independent_current_approval() -> None:
    proposal = _proposal()
    with pytest.raises(ProposalError, match="approval is required"):
        _ = apply_approved_change(
            proposal=proposal,
            approval=None,
            claimant="builder-1",
            current_decision_id="decision-1",
            current_source_revision="rev-1",
            applied_at=NOW,
        )

    self_approval = Approval(
        proposal_id="proposal-1",
        approver="builder-1",
        approved_at=NOW,
        base_decision_id="decision-1",
        source_revision="rev-1",
    )
    with pytest.raises(ProposalError, match="separation of duties"):
        _ = apply_approved_change(
            proposal=proposal,
            approval=self_approval,
            claimant="builder-1",
            current_decision_id="decision-1",
            current_source_revision="rev-1",
            applied_at=NOW,
        )


def test_stale_approval_is_rejected_without_mutation() -> None:
    approval = Approval("proposal-1", "reviewer-1", NOW, "decision-0", "rev-1")
    with pytest.raises(ProposalError, match="stale approval"):
        _ = apply_approved_change(
            proposal=_proposal(),
            approval=approval,
            claimant="builder-1",
            current_decision_id="decision-1",
            current_source_revision="rev-1",
            applied_at=NOW,
        )


def test_approved_change_creates_new_derived_decision() -> None:
    approval = Approval("proposal-1", "reviewer-1", NOW, "decision-1", "rev-1")
    result = apply_approved_change(
        proposal=_proposal(),
        approval=approval,
        claimant="builder-1",
        current_decision_id="decision-1",
        current_source_revision="rev-1",
        applied_at=NOW,
    )
    assert result.new_decision_id != "decision-1"
    assert result.derived_from_decision_id == "decision-1"
    assert result.disposition == "accepted"


def test_override_cannot_weaken_safety_or_completion() -> None:
    with pytest.raises(ProposalError, match="cannot weaken"):
        _ = create_override(
            override_id="override-1",
            actor="admin-1",
            item_id="item-1",
            reason="temporary operational exception",
            expires_at=NOW + timedelta(hours=1),
            safety_weakening=True,
            completion_weakening=False,
            created_at=NOW,
        )
