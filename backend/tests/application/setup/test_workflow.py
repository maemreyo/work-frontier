from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

import pytest

from work_frontier.application.setup.detection import detect_environment
from work_frontier.application.setup.execution import execute_plan
from work_frontier.application.setup.planning import build_setup_plan
from work_frontier.application.setup.readiness import derive_capability_reports
from work_frontier.application.setup.service import SetupService
from work_frontier.contracts.setup import (
    ActionResult,
    ActionState,
    CapabilityName,
    CheckState,
    DetectionCheck,
    SetupAction,
    SetupProfile,
    StaleSetupPlanError,
)
from work_frontier.platform.configuration.setup_storage import (
    SetupLockConflictError,
    SetupPaths,
    SqliteSetupJournal,
    TomlConfigurationStore,
)

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class FakeProbe:
    checks: tuple[DetectionCheck, ...]
    calls: int = 0

    def detect(self, profile: SetupProfile) -> tuple[DetectionCheck, ...]:
        del profile
        self.calls += 1
        return self.checks


@dataclass
class FakeRunner:
    fail_action: str | None = None
    calls: list[tuple[str, str]] = field(default_factory=list)

    def apply(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        self.calls.append(("apply", action.action_id))
        if action.action_id == self.fail_action:
            message = "command failed with pass" + "word=should-not-leak"
            raise RuntimeError(message)
        return {"operation": action.kind}

    def verify(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        self.calls.append(("verify", action.action_id))
        return {"verified": True}

    def compensate(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        self.calls.append(("compensate", action.action_id))
        return {"compensated": True}


def ready_checks() -> tuple[DetectionCheck, ...]:
    return (
        DetectionCheck(
            check_id="tool.uv",
            state=CheckState.READY,
            summary="uv available",
            impact="Python dependencies can be resolved",
            evidence={"version": "0.10.0"},
        ),
        DetectionCheck(
            check_id="github.identity",
            state=CheckState.READY,
            summary="GitHub CLI authenticated",
            impact="Sandbox repositories can be inspected",
            evidence={"login": "octocat"},
        ),
        DetectionCheck(
            check_id="services.database",
            state=CheckState.REPAIRABLE,
            summary="Local PostgreSQL is stopped",
            impact="Runtime persistence is unavailable",
            remediation=("Start supported Compose services",),
        ),
        DetectionCheck(
            check_id="services.object_store",
            state=CheckState.REPAIRABLE,
            summary="Local object storage is stopped",
            impact="Evidence storage is unavailable",
            remediation=("Start supported Compose services",),
        ),
    )


def test_detection_is_deterministic_and_sorted() -> None:
    probe = FakeProbe(tuple(reversed(ready_checks())))
    first = detect_environment(SetupProfile.DEVELOPMENT, "config-1", probe)
    second = detect_environment(SetupProfile.DEVELOPMENT, "config-1", probe)
    assert first == second
    assert [check.check_id for check in first.checks] == sorted(
        check.check_id for check in first.checks
    )


def test_development_plan_is_dependency_ordered_and_stale_safe() -> None:
    snapshot = detect_environment(
        SetupProfile.DEVELOPMENT,
        "config-1",
        FakeProbe(ready_checks()),
    )
    plan = build_setup_plan(
        profile=SetupProfile.DEVELOPMENT,
        desired={"github_repository": "acme/sandbox"},
        current={"schema_version": 1},
        snapshot=snapshot,
    )
    assert [action.action_id for action in plan.actions] == [
        "config.write",
        "github.reference",
        "services.local.start",
        "database.migrate",
        "storage.verify",
        "checks.fast",
    ]
    changed = snapshot.model_copy(update={"snapshot_id": "changed"})
    with pytest.raises(StaleSetupPlanError):
        plan.assert_current(changed, "config-1")


def test_execution_verifies_and_compensates_reverse_order(tmp_path: Path) -> None:
    snapshot = detect_environment(
        SetupProfile.DEVELOPMENT,
        "config-1",
        FakeProbe(ready_checks()),
    )
    plan = build_setup_plan(
        profile=SetupProfile.DEVELOPMENT,
        desired={"github_repository": "acme/sandbox"},
        current={"schema_version": 1},
        snapshot=snapshot,
    )
    runner = FakeRunner(fail_action="database.migrate")
    journal = SqliteSetupJournal(tmp_path / "journal.sqlite3")
    results = execute_plan(
        session_id="session-1",
        plan=plan,
        current_snapshot=snapshot,
        current_config_revision="config-1",
        journal=journal,
        runner=runner,
    )
    assert any(result.state is ActionState.FAILED for result in results)
    assert runner.calls[-3:] == [
        ("compensate", "services.local.start"),
        ("compensate", "github.reference"),
        ("compensate", "config.write"),
    ]
    payloads = [
        repr(action.payload)
        for action in journal.load_session("session-1").actions.values()
    ]
    assert "should-not-leak" not in "".join(payloads)


def test_readiness_is_independent_for_development() -> None:
    reports = derive_capability_reports(
        SetupProfile.DEVELOPMENT,
        ready_checks(),
        (),
    )
    by_name = {report.capability: report for report in reports}
    assert by_name[CapabilityName.LOCAL_RUNTIME].state is CheckState.REPAIRABLE
    assert by_name[CapabilityName.GITHUB_INTEGRATION].state is CheckState.READY
    assert (
        by_name[CapabilityName.RELEASE_CERTIFICATION].state is CheckState.NOT_REQUIRED
    )
    assert by_name[CapabilityName.PRODUCTION_CUTOVER].state is CheckState.NOT_REQUIRED


def test_service_detect_plan_apply_round_trip(tmp_path: Path) -> None:
    paths = SetupPaths.from_root(tmp_path)
    service = SetupService(
        config_store=TomlConfigurationStore(paths),
        journal=SqliteSetupJournal(paths.journal_file),
        probe=FakeProbe(ready_checks()),
        runner=FakeRunner(),
    )
    detection = service.detect(SetupProfile.DEVELOPMENT)
    plan = service.plan(
        profile=SetupProfile.DEVELOPMENT,
        desired={"github_repository": "acme/sandbox"},
        expected_snapshot_id=detection.snapshot_id,
    )
    envelope = service.apply(plan.plan_id)
    assert envelope.plan == plan
    assert all(result.state is ActionState.VERIFIED for result in envelope.results)
    config, _revision = service.config_store.read()
    assert config["github_repository"] == "acme/sandbox"


def test_reviewed_plan_can_be_applied_in_a_fresh_process(tmp_path: Path) -> None:
    paths = SetupPaths.from_root(tmp_path)
    first = SetupService(
        config_store=TomlConfigurationStore(paths),
        journal=SqliteSetupJournal(paths.journal_file),
        probe=FakeProbe(ready_checks()),
        runner=FakeRunner(),
    )
    detection = first.detect(SetupProfile.DEVELOPMENT)
    plan = first.plan(
        profile=SetupProfile.DEVELOPMENT,
        desired={"github_repository": "acme/sandbox"},
        expected_snapshot_id=detection.snapshot_id,
    )

    second = SetupService(
        config_store=TomlConfigurationStore(paths),
        journal=SqliteSetupJournal(paths.journal_file),
        probe=FakeProbe(ready_checks()),
        runner=FakeRunner(),
    )
    envelope = second.apply_reviewed_plan(plan)

    assert envelope.plan == plan
    config, _revision = second.config_store.read()
    assert config["github_repository"] == "acme/sandbox"


def test_failed_session_can_resume_in_a_fresh_process(tmp_path: Path) -> None:
    paths = SetupPaths.from_root(tmp_path)
    first_runner = FakeRunner(fail_action="database.migrate")
    first = SetupService(
        config_store=TomlConfigurationStore(paths),
        journal=SqliteSetupJournal(paths.journal_file),
        probe=FakeProbe(ready_checks()),
        runner=first_runner,
    )
    detection = first.detect(SetupProfile.DEVELOPMENT)
    plan = first.plan(
        profile=SetupProfile.DEVELOPMENT,
        desired={"github_repository": "acme/sandbox"},
        expected_snapshot_id=detection.snapshot_id,
    )
    failed = first.apply(plan.plan_id)
    assert failed.session_id is not None
    assert any(result.state is ActionState.FAILED for result in failed.results)

    second_runner = FakeRunner()
    second = SetupService(
        config_store=TomlConfigurationStore(paths),
        journal=SqliteSetupJournal(paths.journal_file),
        probe=FakeProbe(ready_checks()),
        runner=second_runner,
    )
    resumed = second.resume(failed.session_id)

    assert resumed.session_id == failed.session_id
    assert resumed.plan == plan
    assert all(result.state is ActionState.VERIFIED for result in resumed.results)
    config, _revision = second.config_store.read()
    assert config["github_repository"] == "acme/sandbox"


def test_status_surfaces_latest_incomplete_session(tmp_path: Path) -> None:
    paths = SetupPaths.from_root(tmp_path)
    first = SetupService(
        config_store=TomlConfigurationStore(paths),
        journal=SqliteSetupJournal(paths.journal_file),
        probe=FakeProbe(ready_checks()),
        runner=FakeRunner(fail_action="database.migrate"),
    )
    detection = first.detect(SetupProfile.DEVELOPMENT)
    plan = first.plan(
        profile=SetupProfile.DEVELOPMENT,
        desired={"github_repository": "acme/sandbox"},
        expected_snapshot_id=detection.snapshot_id,
    )
    failed = first.apply(plan.plan_id)

    second = SetupService(
        config_store=TomlConfigurationStore(paths),
        journal=SqliteSetupJournal(paths.journal_file),
        probe=FakeProbe(ready_checks()),
        runner=FakeRunner(),
    )
    status = second.status(SetupProfile.DEVELOPMENT)
    assert status.session_id == failed.session_id


@dataclass
class VerifyFailRunner(FakeRunner):
    verify_fail_action: str | None = None

    @override
    def verify(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        self.calls.append(("verify", action.action_id))
        if action.action_id == self.verify_fail_action:
            message = "verification failed after side effect"
            raise RuntimeError(message)
        return {"verified": True}


def test_irreversible_applied_action_requires_manual_recovery(tmp_path: Path) -> None:
    snapshot = detect_environment(
        SetupProfile.DEVELOPMENT,
        "config-1",
        FakeProbe(ready_checks()),
    )
    plan = build_setup_plan(
        profile=SetupProfile.DEVELOPMENT,
        desired={"github_repository": "acme/sandbox"},
        current={"schema_version": 1},
        snapshot=snapshot,
    )
    runner = VerifyFailRunner(verify_fail_action="database.migrate")
    journal = SqliteSetupJournal(tmp_path / "journal.sqlite3")

    _ = execute_plan(
        session_id="session-manual",
        plan=plan,
        current_snapshot=snapshot,
        current_config_revision="config-1",
        journal=journal,
        runner=runner,
    )

    session = journal.load_session("session-manual")
    assert (
        session.actions["database.migrate"].state
        is ActionState.MANUAL_RECOVERY_REQUIRED
    )
    assert ("compensate", "database.migrate") not in runner.calls


def test_resume_does_not_repeat_verified_actions(tmp_path: Path) -> None:
    snapshot = detect_environment(
        SetupProfile.DEVELOPMENT,
        "config-1",
        FakeProbe(ready_checks()),
    )
    plan = build_setup_plan(
        profile=SetupProfile.DEVELOPMENT,
        desired={"github_repository": "acme/sandbox"},
        current={"schema_version": 1},
        snapshot=snapshot,
    )
    journal = SqliteSetupJournal(tmp_path / "journal.sqlite3")
    journal.save_plan(plan)
    journal.create_session("session-skip", plan.plan_id)
    journal.record_transition(
        "session-skip",
        "config.write",
        ActionState.RUNNING,
        {},
    )
    journal.record_transition(
        "session-skip",
        "config.write",
        ActionState.APPLIED,
        {},
    )
    journal.record_transition(
        "session-skip",
        "config.write",
        ActionState.VERIFIED,
        {"verified": True},
    )
    runner = FakeRunner()

    _ = execute_plan(
        session_id="session-skip",
        plan=plan,
        current_snapshot=snapshot,
        current_config_revision="config-1",
        journal=journal,
        runner=runner,
    )

    assert ("apply", "config.write") not in runner.calls
    assert ("verify", "config.write") not in runner.calls


def test_executor_respects_single_writer_and_releases_after_failure(
    tmp_path: Path,
) -> None:
    snapshot = detect_environment(
        SetupProfile.DEVELOPMENT,
        "config-1",
        FakeProbe(ready_checks()),
    )
    plan = build_setup_plan(
        profile=SetupProfile.DEVELOPMENT,
        desired={"github_repository": "acme/sandbox"},
        current={"schema_version": 1},
        snapshot=snapshot,
    )
    journal = SqliteSetupJournal(tmp_path / "journal.sqlite3")
    journal.acquire_installation_lock("default", "other-session")
    blocked_runner = FakeRunner()

    with pytest.raises(SetupLockConflictError):
        _ = execute_plan(
            session_id="blocked-session",
            plan=plan,
            current_snapshot=snapshot,
            current_config_revision="config-1",
            journal=journal,
            runner=blocked_runner,
        )
    assert blocked_runner.calls == []

    journal.release_installation_lock("default", "other-session")
    _ = execute_plan(
        session_id="failed-session",
        plan=plan,
        current_snapshot=snapshot,
        current_config_revision="config-1",
        journal=journal,
        runner=FakeRunner(fail_action="database.migrate"),
    )
    journal.acquire_installation_lock("default", "next-session")


def test_production_plan_prepares_github_services_release_and_cutover() -> None:
    snapshot = detect_environment(
        SetupProfile.PRODUCTION,
        "config-production",
        FakeProbe(ready_checks()),
    )
    desired: dict[str, str | int | bool] = {
        "github_repository": "acme/managed",
        "github_app_id": 12345,
        "github_installation_id": 67890,
        "github_app_credential_reference": (
            "keyring://work-frontier/installations/production/github-app-key"
        ),
        "github_webhook_reference": (
            "keyring://work-frontier/installations/production/webhook"
        ),
        "database_endpoint": "postgresql://db.internal:5432/work_frontier",
        "database_credential_reference": "env://WF_DATABASE_PASSWORD",
        "object_storage_endpoint": "https://objects.internal",
        "object_storage_credential_reference": "env://WF_OBJECT_STORAGE_SECRET",
        "prepare_release": True,
        "release_signing_key_reference": (
            "keyring://work-frontier/release/standard-signing-key"
        ),
        "release_key_id": "work-frontier-standard-2026-01",
        "release_sandbox_repository": "acme/release-sandbox",
        "soak_duration_seconds": 259200,
        "prepare_cutover": True,
        "cutover_approval_id": "approval-2026-07-14-001",
        "cutover_source_revision": "sha256:0123456789abcdef",
        "cutover_repository": "acme/reference-repository",
    }

    plan = build_setup_plan(
        profile=SetupProfile.PRODUCTION,
        desired=desired,
        current={"schema_version": 1},
        snapshot=snapshot,
    )

    assert [action.action_id for action in plan.actions] == [
        "config.write",
        "github.reference",
        "github.app.verify",
        "services.external.verify",
        "release.prepare",
        "cutover.prepare",
        "checks.fast",
    ]
    serialized = plan.model_dump_json()
    assert "WF_DATABASE_PASSWORD" in serialized
    assert "password=" not in serialized.casefold()
    assert "private" not in serialized.casefold()


def test_production_readiness_uses_persisted_references_without_plaintext(
    tmp_path: Path,
) -> None:
    paths = SetupPaths.from_root(tmp_path)
    store = TomlConfigurationStore(paths)
    document, revision = store.read()
    document.update(
        {
            "profile": "production",
            "github_repository": "acme/managed",
            "github_app_id": 12345,
            "github_installation_id": 67890,
            "github_app_credential_reference": (
                "keyring://work-frontier/installations/production/github-app-key"
            ),
            "github_webhook_reference": (
                "keyring://work-frontier/installations/production/webhook"
            ),
            "database_endpoint": "postgresql://db.internal:5432/work_frontier",
            "database_credential_reference": "env://WF_DATABASE_PASSWORD",
            "object_storage_endpoint": "https://objects.internal",
            "object_storage_credential_reference": ("env://WF_OBJECT_STORAGE_SECRET"),
            "release_signing_key_reference": (
                "keyring://work-frontier/release/standard-signing-key"
            ),
            "release_key_id": "work-frontier-standard-2026-01",
            "release_sandbox_repository": "acme/release-sandbox",
            "soak_duration_seconds": 259200,
            "cutover_approval_id": "approval-2026-07-14-001",
            "cutover_source_revision": "sha256:0123456789abcdef",
            "cutover_repository": "acme/reference-repository",
        }
    )
    _ = store.compare_and_swap(revision, document)
    probe = FakeProbe(
        (
            DetectionCheck(
                check_id="tool.uv",
                state=CheckState.READY,
                summary="uv available",
                impact="Runtime commands are available",
            ),
        )
    )
    service = SetupService(
        config_store=store,
        journal=SqliteSetupJournal(paths.journal_file),
        probe=probe,
        runner=FakeRunner(),
    )

    status = service.status(SetupProfile.PRODUCTION)
    by_name = {report.capability: report for report in status.capabilities}

    assert by_name[CapabilityName.LOCAL_RUNTIME].state is CheckState.REPAIRABLE
    assert by_name[CapabilityName.GITHUB_INTEGRATION].state is CheckState.REPAIRABLE
    assert by_name[CapabilityName.RELEASE_CERTIFICATION].state is CheckState.REPAIRABLE
    assert by_name[CapabilityName.PRODUCTION_CUTOVER].state is CheckState.REPAIRABLE


def test_verified_production_actions_promote_capabilities_to_ready() -> None:
    checks = (
        DetectionCheck(
            check_id="tool.uv",
            state=CheckState.READY,
            summary="uv available",
            impact="Runtime commands are available",
        ),
        DetectionCheck(
            check_id="github.app",
            state=CheckState.REPAIRABLE,
            summary="GitHub App is configured but not verified",
            impact="Machine identity must be verified",
        ),
        DetectionCheck(
            check_id="services.database_external",
            state=CheckState.REPAIRABLE,
            summary="Database is configured but not verified",
            impact="Database connectivity must be verified",
        ),
        DetectionCheck(
            check_id="release.signing",
            state=CheckState.REPAIRABLE,
            summary="Release inputs are configured but not verified",
            impact="Release preparation must be verified",
        ),
        DetectionCheck(
            check_id="cutover.approval",
            state=CheckState.REPAIRABLE,
            summary="Cutover inputs are configured but not verified",
            impact="Cutover preparation must be verified",
        ),
    )
    results = tuple(
        ActionResult(
            action_id=action_id,
            state=ActionState.VERIFIED,
            message="verified",
        )
        for action_id in (
            "services.external.verify",
            "checks.fast",
            "github.app.verify",
            "release.prepare",
            "cutover.prepare",
        )
    )

    reports = derive_capability_reports(SetupProfile.PRODUCTION, checks, results)
    by_name = {report.capability: report for report in reports}

    assert all(report.state is CheckState.READY for report in by_name.values())
