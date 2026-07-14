from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from fastapi.testclient import TestClient

from work_frontier.application.setup.service import SetupService
from work_frontier.contracts.setup import (
    CheckState,
    DetectionCheck,
    SecretReference,
    SetupAction,
    SetupProfile,
)
from work_frontier.interfaces.api.app import create_app
from work_frontier.interfaces.api.services import InMemoryControlPlane
from work_frontier.platform.configuration.setup_storage import (
    SetupPaths,
    SqliteSetupJournal,
    TomlConfigurationStore,
)


class Probe:
    def detect(self, profile: SetupProfile) -> tuple[DetectionCheck, ...]:
        del profile
        return (
            DetectionCheck(
                check_id="tool.uv",
                state=CheckState.READY,
                summary="uv ready",
                impact="runtime ready",
            ),
        )


class Runner:
    def apply(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        return {"operation": action.kind}

    def verify(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        return {"verified": bool(action.action_id)}

    def compensate(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        return {"compensated": bool(action.action_id)}


def setup_service(tmp_path: Path) -> SetupService:
    paths = SetupPaths.from_root(tmp_path)
    return SetupService(
        config_store=TomlConfigurationStore(paths),
        journal=SqliteSetupJournal(paths.journal_file),
        probe=Probe(),
        runner=Runner(),
    )


def headers(role: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer session-good",
        "X-Tenant-ID": "tenant-1",
        "X-Workspace-ID": "workspace-1",
        "X-Actor-ID": "operator-1",
        "X-Actor-Role": role,
    }


def test_operator_can_read_persistent_setup_status(tmp_path: Path) -> None:
    app = create_app(
        InMemoryControlPlane.seeded(), setup_service=setup_service(tmp_path)
    )
    response = TestClient(app).get("/setup/status", headers=headers("operator"))
    assert response.status_code == 200
    assert len(response.json()["capabilities"]) == 4


def test_viewer_cannot_apply_setup_plan(tmp_path: Path) -> None:
    app = create_app(
        InMemoryControlPlane.seeded(), setup_service=setup_service(tmp_path)
    )
    response = TestClient(app).post(
        "/setup/apply",
        headers=headers("viewer"),
        json={"plan_id": "missing"},
    )
    assert response.status_code == 403


@dataclass
class SecretStore:
    values: dict[str, str]

    def store(self, *, namespace: str, name: str, value: str) -> SecretReference:
        self.values[f"{namespace}/{name}"] = value
        return SecretReference(uri=f"keyring://work-frontier/{namespace}/{name}")


def test_operator_can_generate_signing_key_without_secret_echo(tmp_path: Path) -> None:
    store = SecretStore({})
    app = create_app(
        InMemoryControlPlane.seeded(),
        setup_service=setup_service(tmp_path),
        setup_secret_store=store,
    )
    response = TestClient(app).post(
        "/setup/signing-key",
        headers=headers("operator"),
        json={
            "namespace": "release",
            "name": "standard-signing-key",
            "key_id": "work-frontier-standard-2026-01",
        },
    )
    assert response.status_code == 201
    stored = store.values["release/standard-signing-key"]
    assert stored not in response.text
    assert len(response.json()["fingerprint"]) == 64
