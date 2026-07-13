import pytest

from work_frontier.interfaces.api.errors import ControlPlaneError
from work_frontier.interfaces.api.models import ClaimBody
from work_frontier.interfaces.api.services import InMemoryControlPlane


def test_stale_decision_rejects_claim_without_mutation() -> None:
    service = InMemoryControlPlane.seeded()
    context = service.validate_session(
        token=next(iter(service.sessions)),
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        actor_hint=None,
    )
    with pytest.raises(ControlPlaneError) as raised:
        _ = service.claim(context, "item-1", ClaimBody(decision_id="stale"))
    assert raised.value.code == "stale_decision"
    assert service.leases == {}
