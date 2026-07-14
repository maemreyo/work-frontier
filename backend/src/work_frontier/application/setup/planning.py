"""Secret-free deterministic Detect → Plan conversion."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from work_frontier.contracts.setup import (
    DetectionSnapshot,
    SetupAction,
    SetupPlan,
    SetupProfile,
    StaleSetupPlanError,
)

_REVERSIBLE = True
_IRREVERSIBLE = False


class SetupPlanningInputError(ValueError):
    """Signal missing profile-specific desired configuration."""


def build_setup_plan(
    *,
    profile: SetupProfile,
    desired: dict[str, str | int | bool],
    current: dict[str, str | int | bool],
    snapshot: DetectionSnapshot,
) -> SetupPlan:
    """Build a deterministic plan from desired and detected state."""
    del current
    actions = [_config_action(profile)]
    repository = desired.get("github_repository")
    if isinstance(repository, str) and repository:
        actions.append(
            _action(
                "github.reference",
                "Reference GitHub identity",
                "Use the selected GitHub sandbox or installation",
                "low",
                _REVERSIBLE,
                ("config.write",),
                "github_reference",
                {"repository": repository},
            )
        )
    predecessor = actions[-1].action_id
    if profile is SetupProfile.DEVELOPMENT:
        actions.extend(_development_actions(predecessor))
    else:
        actions.extend(_production_actions(desired, predecessor))
    return _build_plan(profile, desired, snapshot, actions)


def assert_plan_current(
    plan: SetupPlan,
    snapshot: DetectionSnapshot,
    config_revision: str,
) -> None:
    """Reject a stale reviewed plan before any side effect."""
    if (
        plan.detection_snapshot_id != snapshot.snapshot_id
        or plan.config_revision != config_revision
    ):
        message = "setup plan is stale; detect and review again"
        raise StaleSetupPlanError(message)


def _config_action(profile: SetupProfile) -> SetupAction:
    return _action(
        "config.write",
        "Write configuration",
        "Persist selected non-secret configuration",
        "low",
        _REVERSIBLE,
        (),
        "write_config",
        {"profile": profile.value},
    )


def _development_actions(predecessor: str) -> tuple[SetupAction, ...]:
    return (
        _action(
            "services.local.start",
            "Start local data services",
            "Provide PostgreSQL and object storage",
            "medium",
            _REVERSIBLE,
            (predecessor,),
            "docker_compose_up",
            {"profile": "development"},
        ),
        _action(
            "database.migrate",
            "Apply database migrations",
            "Bring the local schema to the supported revision",
            "medium",
            _IRREVERSIBLE,
            ("services.local.start",),
            "database_migrate",
            {},
        ),
        _action(
            "storage.verify",
            "Verify object storage",
            "Confirm evidence object lifecycle",
            "low",
            _IRREVERSIBLE,
            ("database.migrate",),
            "storage_verify",
            {},
        ),
        _action(
            "checks.fast",
            "Run fast verification",
            "Confirm the runtime is safe to enter",
            "low",
            _IRREVERSIBLE,
            ("storage.verify",),
            "run_fast_checks",
            {},
        ),
    )


def _production_actions(
    desired: dict[str, str | int | bool],
    predecessor: str,
) -> tuple[SetupAction, ...]:
    github_parameters = _required_parameters(
        desired,
        (
            "github_repository",
            "github_app_id",
            "github_installation_id",
            "github_app_credential_reference",
            "github_webhook_reference",
        ),
        section="GitHub App",
    )
    service_parameters = _required_parameters(
        desired,
        (
            "database_endpoint",
            "database_credential_reference",
            "object_storage_endpoint",
            "object_storage_credential_reference",
        ),
        section="external data services",
    )
    actions: list[SetupAction] = [
        _action(
            "github.app.verify",
            "Verify GitHub App installation",
            "Validate machine identity and repository permissions",
            "high",
            _IRREVERSIBLE,
            (predecessor,),
            "github_app_verify",
            github_parameters,
        ),
        _action(
            "services.external.verify",
            "Verify external data services",
            "Confirm TLS, authentication, and service capabilities",
            "high",
            _IRREVERSIBLE,
            ("github.app.verify",),
            "verify_external_services",
            service_parameters,
        ),
    ]
    last = "services.external.verify"
    if desired.get("prepare_release") is True:
        release_parameters = _required_parameters(
            desired,
            (
                "release_signing_key_reference",
                "release_key_id",
                "release_sandbox_repository",
                "soak_duration_seconds",
            ),
            section="release certification",
        )
        actions.append(
            _action(
                "release.prepare",
                "Prepare Standard release certification",
                "Validate signing, sandbox, and real soak inputs",
                "high",
                _IRREVERSIBLE,
                (last,),
                "prepare_release",
                release_parameters,
            )
        )
        last = "release.prepare"
    if desired.get("prepare_cutover") is True:
        cutover_parameters = _required_parameters(
            desired,
            (
                "cutover_approval_id",
                "cutover_source_revision",
                "cutover_repository",
            ),
            section="production cutover",
        )
        actions.append(
            _action(
                "cutover.prepare",
                "Prepare controlled production cutover",
                "Validate approval, exact source revision, and target repository",
                "high",
                _IRREVERSIBLE,
                (last,),
                "prepare_cutover",
                cutover_parameters,
            )
        )
        last = "cutover.prepare"
    actions.append(
        _action(
            "checks.fast",
            "Run fast verification",
            "Confirm configured production dependencies",
            "low",
            _IRREVERSIBLE,
            (last,),
            "run_fast_checks",
            {},
        )
    )
    return tuple(actions)


def _required_parameters(
    desired: dict[str, str | int | bool],
    names: tuple[str, ...],
    *,
    section: str,
) -> dict[str, str | int | bool | None]:
    missing = [name for name in names if desired.get(name) in (None, "")]
    if missing:
        message = f"{section} requires: {', '.join(missing)}"
        raise SetupPlanningInputError(message)
    return {name: desired[name] for name in names}


def _build_plan(
    profile: SetupProfile,
    desired: dict[str, str | int | bool],
    snapshot: DetectionSnapshot,
    actions: list[SetupAction],
) -> SetupPlan:
    canonical = json.dumps(
        {
            "profile": profile.value,
            "snapshot": snapshot.snapshot_id,
            "config_revision": snapshot.config_revision,
            "desired": desired,
            "actions": [action.model_dump(mode="json") for action in actions],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return SetupPlan(
        plan_id=hashlib.sha256(canonical.encode()).hexdigest(),
        profile=profile,
        detection_snapshot_id=snapshot.snapshot_id,
        config_revision=snapshot.config_revision,
        actions=tuple(actions),
    )


def _action(  # noqa: PLR0913 - action contracts are intentionally explicit
    action_id: str,
    title: str,
    reason: str,
    risk: Literal["low", "medium", "high"],
    reversible: bool,
    depends_on: tuple[str, ...],
    kind: str,
    parameters: dict[str, str | int | bool | None],
) -> SetupAction:
    return SetupAction(
        action_id=action_id,
        title=title,
        reason=reason,
        risk=risk,
        reversible=reversible,
        depends_on=depends_on,
        kind=kind,
        parameters=parameters,
    )
