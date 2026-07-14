"""Stable setup use cases shared by CLI, HTTP, and headless automation."""

from __future__ import annotations

import hashlib
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from work_frontier.application.ports.setup import (
        ConfigurationStore,
        JournalSession,
        SetupActionRunner,
        SetupJournal,
        SystemProbe,
    )
from work_frontier.application.setup.detection import detect_environment
from work_frontier.application.setup.execution import execute_plan
from work_frontier.application.setup.planning import build_setup_plan
from work_frontier.application.setup.readiness import derive_capability_reports
from work_frontier.contracts.setup import (
    ActionResult,
    ActionState,
    CheckState,
    DetectionCheck,
    DetectionSnapshot,
    SetupEnvelope,
    SetupPlan,
    SetupProfile,
)


class SetupService:
    """Coordinate detection, review, apply, resume, and readiness."""

    config_store: ConfigurationStore
    _journal: SetupJournal
    _probe: SystemProbe
    _runner: SetupActionRunner

    def __init__(
        self,
        *,
        config_store: ConfigurationStore,
        journal: SetupJournal,
        probe: SystemProbe,
        runner: SetupActionRunner,
    ) -> None:
        """Bind explicit persistence, probe, and action-runner ports."""
        self.config_store = config_store
        self._journal = journal
        self._probe = probe
        self._runner = runner
        self._snapshots: dict[str, DetectionSnapshot] = {}
        self._plans: dict[str, SetupPlan] = {}
        self._desired: dict[str, dict[str, str | int | bool]] = {}

    def detect(self, profile: SetupProfile) -> DetectionSnapshot:
        """Detect current state without side effects."""
        config, revision = self.config_store.read()
        snapshot = detect_environment(profile, revision, self._probe)
        if profile is SetupProfile.PRODUCTION:
            retained = tuple(
                check
                for check in snapshot.checks
                if not _production_config_owned_check(check.check_id)
            )
            snapshot = snapshot.model_copy(
                update={
                    "checks": tuple(
                        sorted(
                            (*retained, *_production_configuration_checks(config)),
                            key=lambda check: check.check_id,
                        )
                    )
                }
            )
            snapshot = snapshot.model_copy(
                update={"snapshot_id": _rehash_snapshot(snapshot)}
            )
        self._snapshots[snapshot.snapshot_id] = snapshot
        return snapshot

    def plan(
        self,
        *,
        profile: SetupProfile,
        desired: dict[str, str | int | bool],
        expected_snapshot_id: str,
    ) -> SetupPlan:
        """Build a plan only from a known current snapshot."""
        snapshot = self._snapshots.get(expected_snapshot_id)
        if snapshot is None:
            raise KeyError(expected_snapshot_id)
        current, revision = self.config_store.read()
        if revision != snapshot.config_revision:
            message = "configuration changed after detection"
            raise RuntimeError(message)
        plan = build_setup_plan(
            profile=profile,
            desired=desired,
            current=current,
            snapshot=snapshot,
        )
        self._plans[plan.plan_id] = plan
        self._desired[plan.plan_id] = dict(desired)
        return plan

    def apply_reviewed_plan(self, plan: SetupPlan) -> SetupEnvelope:
        """Revalidate and apply a serialized secret-free plan in a fresh process."""
        snapshot = self.detect(plan.profile)
        _current, revision = self.config_store.read()
        plan.assert_current(snapshot, revision)
        desired = _desired_from_plan(plan)
        self._plans[plan.plan_id] = plan
        self._desired[plan.plan_id] = desired
        return self.apply(plan.plan_id)

    def apply(self, plan_id: str) -> SetupEnvelope:
        """Apply a reviewed plan and persist config only after full verification."""
        plan = self._plans[plan_id]
        snapshot = self._snapshots[plan.detection_snapshot_id]
        _current, revision = self.config_store.read()
        session_id = secrets.token_hex(12)
        self._journal.save_plan(plan)
        results = execute_plan(
            session_id=session_id,
            plan=plan,
            current_snapshot=snapshot,
            current_config_revision=revision,
            journal=self._journal,
            runner=self._runner,
        )
        if results and all(result.state is ActionState.VERIFIED for result in results):
            document, current_revision = self.config_store.read()
            document.update(self._desired[plan_id])
            document["profile"] = plan.profile.value
            _ = self.config_store.compare_and_swap(current_revision, document)
        latest = self.detect(plan.profile)
        capabilities = derive_capability_reports(plan.profile, latest.checks, results)
        return SetupEnvelope(
            session_id=session_id,
            detection=latest,
            plan=plan,
            capabilities=capabilities,
            results=results,
        )

    def resume(self, session_id: str) -> SetupEnvelope:
        """Resume an interrupted setup session from its durable reviewed plan."""
        session = self._journal.load_session(session_id)
        plan = self._journal.load_plan(session.plan_id)
        snapshot = self.detect(plan.profile)
        _current, revision = self.config_store.read()
        plan.assert_current(snapshot, revision)
        self._plans[plan.plan_id] = plan
        self._desired[plan.plan_id] = _desired_from_plan(plan)
        results = execute_plan(
            session_id=session_id,
            plan=plan,
            current_snapshot=snapshot,
            current_config_revision=revision,
            journal=self._journal,
            runner=self._runner,
        )
        if results and all(result.state is ActionState.VERIFIED for result in results):
            document, current_revision = self.config_store.read()
            document.update(self._desired[plan.plan_id])
            document["profile"] = plan.profile.value
            _ = self.config_store.compare_and_swap(current_revision, document)
        latest = self.detect(plan.profile)
        return SetupEnvelope(
            session_id=session_id,
            detection=latest,
            plan=plan,
            capabilities=derive_capability_reports(
                plan.profile, latest.checks, results
            ),
            results=results,
        )

    def status(self, profile: SetupProfile) -> SetupEnvelope:
        """Return current setup status and durable execution facts."""
        detection = self.detect(profile)
        session_id = self._journal.latest_session_id()
        plan: SetupPlan | None = None
        results: tuple[ActionResult, ...] = ()
        if session_id is not None:
            session = self._journal.load_session(session_id)
            candidate = self._journal.load_plan(session.plan_id)
            if candidate.profile is profile:
                plan = candidate
                results = _results_from_session(session)
        return SetupEnvelope(
            session_id=session_id,
            detection=detection,
            plan=plan,
            capabilities=derive_capability_reports(profile, detection.checks, results),
            results=results,
        )


def _desired_from_plan(plan: SetupPlan) -> dict[str, str | int | bool]:
    desired = {
        key: value
        for action in plan.actions
        for key, value in action.parameters.items()
        if isinstance(value, (str, int, bool))
    }
    for action in plan.actions:
        if action.kind == "github_reference":
            repository = action.parameters.get("repository")
            if isinstance(repository, str):
                desired["github_repository"] = repository
        if action.kind == "prepare_release":
            desired["prepare_release"] = True
        if action.kind == "prepare_cutover":
            desired["prepare_cutover"] = True
    return desired


def _production_config_owned_check(check_id: str) -> bool:
    return check_id == "tool.docker_compose" or check_id.startswith(
        ("github.", "services.", "release.", "cutover.")
    )


def _production_configuration_checks(
    config: dict[str, str | int | bool],
) -> tuple[DetectionCheck, ...]:
    return (
        _config_check(
            "github.app",
            "GitHub App machine identity",
            config,
            (
                "github_repository",
                "github_app_id",
                "github_installation_id",
                "github_app_credential_reference",
                "github_webhook_reference",
            ),
        ),
        _config_check(
            "services.database_external",
            "External PostgreSQL",
            config,
            ("database_endpoint", "database_credential_reference"),
        ),
        _config_check(
            "services.object_store_external",
            "External object storage",
            config,
            ("object_storage_endpoint", "object_storage_credential_reference"),
        ),
        _config_check(
            "release.signing",
            "Release signing",
            config,
            ("release_signing_key_reference", "release_key_id"),
        ),
        _config_check(
            "release.sandbox",
            "Release sandbox",
            config,
            ("release_sandbox_repository",),
        ),
        _config_check(
            "release.soak",
            "Release soak policy",
            config,
            ("soak_duration_seconds",),
        ),
        _config_check(
            "cutover.approval",
            "Cutover approval",
            config,
            ("cutover_approval_id",),
        ),
        _config_check(
            "cutover.source",
            "Cutover exact source revision",
            config,
            ("cutover_source_revision",),
        ),
        _config_check(
            "cutover.repository",
            "Cutover reference repository",
            config,
            ("cutover_repository",),
        ),
    )


def _config_check(
    check_id: str,
    label: str,
    config: dict[str, str | int | bool],
    required: tuple[str, ...],
) -> DetectionCheck:
    missing = tuple(name for name in required if config.get(name) in (None, ""))
    return DetectionCheck(
        check_id=check_id,
        state=CheckState.NEEDS_INPUT if missing else CheckState.REPAIRABLE,
        summary=(
            f"{label} needs configuration"
            if missing
            else f"{label} is configured but not yet verified"
        ),
        impact=f"{label} must be configured for production readiness",
        remediation=(f"Provide: {', '.join(missing)}",) if missing else (),
        evidence={"configured": not missing},
    )


def _results_from_session(
    session: JournalSession,
) -> tuple[ActionResult, ...]:
    return tuple(
        ActionResult(
            action_id=action_id,
            state=action.state,
            message=f"Durable setup action state: {action.state.value}",
            redacted_evidence=dict(action.payload),
        )
        for action_id, action in sorted(session.actions.items())
    )


def _rehash_snapshot(snapshot: DetectionSnapshot) -> str:
    canonical = snapshot.model_dump_json(
        exclude={"snapshot_id"},
        by_alias=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
