import pytest

from work_frontier.interfaces.api.errors import ControlPlaneError
from work_frontier.interfaces.api.models import ClaimBody
from work_frontier.interfaces.api.services import InMemoryControlPlane


def test_atomic_claim_race_has_exactly_one_winner() -> None:
    service = InMemoryControlPlane.seeded()
    context = service.validate_session(
        token=next(iter(service.sessions)),
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        actor_hint=None,
    )
    body = ClaimBody(decision_id="decision-1")
    winner = service.claim(context, "item-1", body)
    with pytest.raises(ControlPlaneError) as raised:
        _ = service.claim(context, "item-1", body)
    assert raised.value.code == "lease_conflict"
    assert service.leases["item-1"] == winner
