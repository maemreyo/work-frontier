from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override
from uuid import uuid4

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
from work_frontier.interfaces.api.setup_app import create_setup_app
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
                impact="runtime",
            ),
            DetectionCheck(
                check_id="github.identity",
                state=CheckState.NEEDS_INPUT,
                summary="GitHub required",
                impact="integration",
                remediation=("Connect GitHub",),
            ),
        )


class Runner:
    def apply(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        return {"operation": action.kind}

    def verify(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        return {"verified": bool(action.action_id)}

    def compensate(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        return {"compensated": bool(action.action_id)}


@dataclass
class SecretStore:
    values: dict[str, str]

    def store(self, *, namespace: str, name: str, value: str) -> SecretReference:
        self.values[f"{namespace}/{name}"] = value
        return SecretReference(uri=f"keyring://work-frontier/{namespace}/{name}")


def service(tmp_path: Path) -> SetupService:
    paths = SetupPaths.from_root(tmp_path)
    return SetupService(
        config_store=TomlConfigurationStore(paths),
        journal=SqliteSetupJournal(paths.journal_file),
        probe=Probe(),
        runner=Runner(),
    )


def _nonce() -> str:
    return f"test-{uuid4().hex}"


def test_bootstrap_token_is_single_use_and_session_is_cookie_bound(
    tmp_path: Path,
) -> None:
    token = _nonce()
    app = create_setup_app(
        service(tmp_path),
        bootstrap_token=token,
        secret_store=SecretStore({}),
    )
    client = TestClient(app)
    first = client.post("/api/setup/session/exchange", json={"token": token})
    second = client.post("/api/setup/session/exchange", json={"token": token})
    assert first.status_code == 204
    assert second.status_code == 401
    assert "wf_setup_session" in first.headers["set-cookie"]

    csrf = first.headers["x-setup-csrf"]
    detected = client.post(
        "/api/setup/detect",
        headers={"X-Setup-CSRF": csrf},
        json={"profile": "development"},
    )
    assert detected.status_code == 200
    assert detected.json()["profile"] == "development"


def test_setup_app_rejects_remote_forwarding(tmp_path: Path) -> None:
    token = _nonce()
    app = create_setup_app(service(tmp_path), bootstrap_token=token)
    response = TestClient(app).get(
        "/api/setup/status",
        headers={"Forwarded": "for=203.0.113.8;host=evil.example"},
    )
    assert response.status_code == 403


def test_secret_submission_returns_reference_only(tmp_path: Path) -> None:
    token = _nonce()
    store = SecretStore({})
    app = create_setup_app(
        service(tmp_path),
        bootstrap_token=token,
        secret_store=store,
    )
    client = TestClient(app)
    exchange = client.post("/api/setup/session/exchange", json={"token": token})
    response = client.post(
        "/api/setup/secrets",
        headers={"X-Setup-CSRF": exchange.headers["x-setup-csrf"]},
        json={"namespace": "release", "name": "signing-key", "value": "private-value"},
    )
    assert response.status_code == 201
    assert response.json() == {
        "reference": "keyring://work-frontier/release/signing-key"
    }
    assert "private-value" not in response.text


def test_packaged_assets_are_served_from_setup_only_app(tmp_path: Path) -> None:
    token = _nonce()
    static = tmp_path / "static"
    assets = static / "assets"
    _ = assets.mkdir(parents=True)
    _ = (static / "setup.html").write_text(
        '<script src="/assets/setup-center.js"></script>'
    )
    _ = (assets / "setup-center.js").write_text("export const ready = true")
    app = create_setup_app(
        service(tmp_path / "state"),
        bootstrap_token=token,
        static_directory=static,
    )
    client = TestClient(app)
    assert client.get("/setup.html").status_code == 200
    asset = client.get("/assets/setup-center.js")
    assert asset.status_code == 200
    assert "ready = true" in asset.text


def test_setup_app_rejects_non_loopback_host_header(tmp_path: Path) -> None:
    token = _nonce()
    app = create_setup_app(service(tmp_path), bootstrap_token=token)
    response = TestClient(app).get(
        "/setup.html",
        headers={"Host": "attacker.example"},
    )
    assert response.status_code == 403


class FailingRunner(Runner):
    @override
    def apply(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        if action.action_id == "database.migrate":
            message = "migration interrupted"
            raise RuntimeError(message)
        return super().apply(action)


def test_bootstrap_api_resumes_durable_session_after_process_restart(
    tmp_path: Path,
) -> None:
    token = _nonce()
    paths = SetupPaths.from_root(tmp_path)
    first = SetupService(
        config_store=TomlConfigurationStore(paths),
        journal=SqliteSetupJournal(paths.journal_file),
        probe=Probe(),
        runner=FailingRunner(),
    )
    detection = first.detect(SetupProfile.DEVELOPMENT)
    plan = first.plan(
        profile=SetupProfile.DEVELOPMENT,
        desired={"github_repository": "acme/sandbox"},
        expected_snapshot_id=detection.snapshot_id,
    )
    failed = first.apply(plan.plan_id)
    assert failed.session_id is not None

    second = SetupService(
        config_store=TomlConfigurationStore(paths),
        journal=SqliteSetupJournal(paths.journal_file),
        probe=Probe(),
        runner=Runner(),
    )
    app = create_setup_app(second, bootstrap_token=token)
    client = TestClient(app)
    exchange = client.post(
        "/api/setup/session/exchange",
        json={"token": token},
    )
    response = client.post(
        f"/api/setup/resume/{failed.session_id}",
        headers={"X-Setup-CSRF": exchange.headers["x-setup-csrf"]},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == failed.session_id
    assert all(item["state"] == "verified" for item in response.json()["results"])


def test_signing_key_generation_returns_only_public_material(tmp_path: Path) -> None:
    token = _nonce()
    store = SecretStore({})
    app = create_setup_app(
        service(tmp_path),
        bootstrap_token=token,
        secret_store=store,
    )
    client = TestClient(app)
    exchange = client.post(
        "/api/setup/session/exchange",
        json={"token": token},
    )
    response = client.post(
        "/api/setup/signing-key",
        headers={"X-Setup-CSRF": exchange.headers["x-setup-csrf"]},
        json={
            "namespace": "release",
            "name": "standard-signing-key",
            "key_id": "work-frontier-standard-2026-01",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["reference"] == (
        "keyring://work-frontier/release/standard-signing-key"
    )
    assert payload["key_id"] == "work-frontier-standard-2026-01"
    assert len(payload["fingerprint"]) == 64
    assert "public_key_b64" in payload
    stored = store.values["release/standard-signing-key"]
    assert stored not in response.text
