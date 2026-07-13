from work_frontier.interfaces.api.models import ProposalBody
from work_frontier.interfaces.api.services import InMemoryControlPlane


def test_approved_proposal_creates_new_derived_decision_projection() -> None:
    service = InMemoryControlPlane.seeded()
    proposer = service.validate_session(
        token=next(iter(service.sessions)),
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        actor_hint="builder-1",
    )
    proposal = service.create_proposal(
        proposer,
        ProposalBody(
            item_id="item-1",
            base_decision_id="decision-1",
            expected_source_revision="rev-1",
            field="dependency",
            new_value="item-2",
        ),
    )
    reviewer = service.validate_session(
        token=next(iter(service.sessions)),
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        actor_hint="reviewer-1",
    )
    approval = service.approve_proposal(reviewer, proposal.proposal_id)
    assert approval.derived_from_decision_id == "decision-1"
    assert service.items["item-1"].decision_id == approval.new_decision_id
