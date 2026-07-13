from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from httpx import Response

from work_frontier.interfaces.api.app import create_app
from work_frontier.interfaces.api.services import InMemoryControlPlane


class _TestHttpClient(Protocol):
    def get(self, path: str, *, headers: dict[str, str] | None = None) -> Response:
        """Send a test GET request."""
        ...

    def post(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
    ) -> Response:
        """Send a test POST request."""
        ...


def _client() -> TestClient:
    service = InMemoryControlPlane.seeded()
    return TestClient(create_app(service))


def _get(
    client: TestClient, path: str, *, headers: dict[str, str] | None = None
) -> Response:
    return cast("_TestHttpClient", client).get(path, headers=headers)


def _post(
    client: TestClient,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, object] | None = None,
) -> Response:
    return cast("_TestHttpClient", client).post(path, headers=headers, json=payload)


def _json(response: Response) -> dict[str, object]:
    decoded = response.json()
    if not isinstance(decoded, dict):
        raise TypeError
    return cast("dict[str, object]", decoded)


def _error_code(response: Response) -> str:
    payload = _json(response)
    error = payload.get("error")
    if not isinstance(error, dict):
        raise TypeError
    typed_error = cast("dict[str, object]", error)
    code = typed_error.get("code")
    if not isinstance(code, str):
        raise TypeError
    return code


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer session-good",
        "X-Tenant-ID": "tenant-1",
        "X-Workspace-ID": "workspace-1",
    }


def test_health_and_openapi_are_public_but_control_plane_is_scoped() -> None:
    client = _client()
    assert _get(client, "/healthz").status_code == 200
    openapi = _json(_get(client, "/openapi.json")).get("openapi")
    assert isinstance(openapi, str)
    assert openapi.startswith("3.1")
    assert _get(client, "/frontier").status_code == 401
    assert _get(client, "/frontier", headers=_headers()).status_code == 200


def test_cross_scope_and_malformed_ids_return_non_leaking_errors() -> None:
    client = _client()
    wrong = {**_headers(), "X-Workspace-ID": "workspace-2"}
    assert _get(client, "/frontier/item-1", headers=wrong).status_code == 404
    response = _get(client, "/frontier/invalid id", headers=_headers())
    assert response.status_code == 422
    assert _error_code(response) == "invalid_request"


def test_claim_race_and_stale_proposal_have_typed_conflicts() -> None:
    client = _client()
    first = _post(
        client,
        "/leases/item-1/claim",
        headers=_headers(),
        payload={"decision_id": "decision-1"},
    )
    second = _post(
        client,
        "/leases/item-1/claim",
        headers=_headers(),
        payload={"decision_id": "decision-1"},
    )
    assert first.status_code == 201
    assert second.status_code == 409
    assert _error_code(second) == "lease_conflict"

    proposal = _post(
        client,
        "/proposals",
        headers=_headers(),
        payload={
            "item_id": "item-1",
            "base_decision_id": "decision-0",
            "expected_source_revision": "rev-1",
            "field": "dependency",
            "new_value": "item-2",
        },
    )
    assert proposal.status_code == 201
    approval = _post(
        client,
        f"/proposals/{_json(proposal)['proposal_id']}/approve",
        headers={**_headers(), "X-Actor-ID": "reviewer-1"},
    )
    assert approval.status_code == 409
    assert _error_code(approval) == "stale_decision"


def test_process_entrypoints_share_application_services() -> None:
    from work_frontier.interfaces.processes.scheduler import run_scheduler_once
    from work_frontier.interfaces.processes.worker import run_worker_once

    service = InMemoryControlPlane.seeded()
    assert run_worker_once(service) == "idle"
    assert run_scheduler_once(service) == "scheduled:0"
