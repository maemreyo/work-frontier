from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from work_frontier.contracts.setup import (
    CheckState,
    DetectionCheck,
    SetupEnvelope,
    SetupPlan,
    SetupProfile,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
from work_frontier.interfaces.cli.setup import app

runner = CliRunner()


class FakeService:
    def status(self, profile: SetupProfile) -> SetupEnvelope:
        from work_frontier.application.setup.readiness import derive_capability_reports
        from work_frontier.contracts.setup import DetectionSnapshot, SetupEnvelope

        checks = (
            DetectionCheck(
                check_id="tool.uv",
                state=CheckState.READY,
                summary="uv ready",
                impact="runtime",
            ),
        )
        detection = DetectionSnapshot(
            snapshot_id="snapshot",
            profile=profile,
            config_revision="revision",
            checks=checks,
        )
        return SetupEnvelope(
            detection=detection,
            capabilities=derive_capability_reports(profile, checks, ()),
        )


def test_status_json_is_machine_readable_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def build_service() -> FakeService:
        return FakeService()

    monkeypatch.setattr(
        "work_frontier.interfaces.cli.setup.build_default_setup_service",
        build_service,
    )
    result = runner.invoke(app, ["setup", "status", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "capabilities" in payload
    assert "password" not in result.stdout.casefold()


def test_setup_bootstrap_prints_recovery_url_without_fragment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def build_service() -> FakeService:
        return FakeService()

    monkeypatch.setattr(
        "work_frontier.interfaces.cli.setup.build_default_setup_service",
        build_service,
    )

    def fake_launch(_service: object, *, no_open: bool, detach: bool) -> str:
        assert detach
        assert not no_open
        return "http://127.0.0.1:43123/setup.html"

    monkeypatch.setattr(
        "work_frontier.interfaces.cli.setup.launch_setup_server",
        fake_launch,
    )
    result = runner.invoke(app, ["setup", "--detach"])
    assert result.exit_code == 0
    assert "http://127.0.0.1:43123/setup.html" in result.stdout
    assert "#" not in result.stdout


def test_headless_apply_reads_reviewed_plan_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class ApplyService(FakeService):
        applied: SetupPlan | None = None

        def apply_reviewed_plan(self, plan: SetupPlan) -> SetupEnvelope:
            self.applied = plan
            return self.status(plan.profile).model_copy(update={"plan": plan})

    service = ApplyService()

    def build_service() -> ApplyService:
        return service

    monkeypatch.setattr(
        "work_frontier.interfaces.cli.setup.build_default_setup_service",
        build_service,
    )
    plan_path = tmp_path / "plan.json"
    _ = plan_path.write_text(
        SetupPlan(
            plan_id="plan-1",
            profile=SetupProfile.DEVELOPMENT,
            detection_snapshot_id="snapshot",
            config_revision="revision",
            actions=(),
        ).model_dump_json()
    )

    result = runner.invoke(
        app,
        ["setup", "apply", "--plan", str(plan_path), "--non-interactive"],
    )

    assert result.exit_code == 0
    assert service.applied is not None
    assert '"plan_id": "plan-1"' in result.stdout


def test_status_human_output_uses_readable_capability_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def build_service() -> FakeService:
        return FakeService()

    monkeypatch.setattr(
        "work_frontier.interfaces.cli.setup.build_default_setup_service",
        build_service,
    )
    result = runner.invoke(app, ["setup", "status"])
    assert result.exit_code == 0
    assert "Setup readiness" in result.stdout
    assert "Local runtime" in result.stdout
