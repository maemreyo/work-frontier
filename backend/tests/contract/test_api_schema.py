from __future__ import annotations

from typing import Protocol, cast

from fastapi.testclient import TestClient

from work_frontier.interfaces.api.app import create_app
from work_frontier.interfaces.api.services import InMemoryControlPlane


class _Response(Protocol):
    status_code: int

    def json(self) -> object:
        """Decode the response body."""
        ...


class _Client(Protocol):
    def get(self, path: str, *, headers: dict[str, str] | None = None) -> _Response:
        """Send a test GET request."""
        ...


def _client() -> _Client:
    return cast("_Client", TestClient(create_app(InMemoryControlPlane.seeded())))


def test_openapi_31_contract_and_security_are_complete() -> None:
    client = _client()
    response = client.get("/openapi.json")
    payload = response.json()
    assert isinstance(payload, dict)
    document = cast("dict[str, object]", payload)
    assert document.get("openapi") == "3.1.0"
    paths = document.get("paths")
    assert isinstance(paths, dict)
    typed_paths = cast("dict[str, object]", paths)
    assert {
        "/attention",
        "/frontier",
        "/frontier/{item_id}",
        "/healthz",
        "/leases/{item_id}/claim",
        "/proposals",
        "/proposals/{proposal_id}/approve",
        "/sync",
        "/writer-state",
    } <= set(typed_paths)


def test_one_thousand_malformed_identifiers_never_bypass_validation() -> None:
    client = _client()
    headers = {
        "Authorization": "Bearer session-good",
        "X-Tenant-ID": "tenant-1",
        "X-Workspace-ID": "workspace-1",
    }
    for index in range(1000):
        response = client.get(f"/frontier/invalid id {index}", headers=headers)
        assert response.status_code == 422
