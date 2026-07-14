from __future__ import annotations

import pytest
from pydantic import ValidationError

from work_frontier.contracts.setup import (
    ActionState,
    CapabilityName,
    CheckState,
    DetectionCheck,
    SecretReference,
    SetupAction,
    SetupPlan,
    SetupProfile,
)


def test_secret_reference_accepts_supported_schemes_and_rejects_plaintext() -> None:
    assert (
        SecretReference(uri="keyring://work-frontier/local/token").scheme == "keyring"
    )
    assert SecretReference(uri="env://WF_DATABASE_PASSWORD").scheme == "env"
    assert SecretReference(uri="gh-cli://github.com/octocat").scheme == "gh-cli"
    with pytest.raises(ValidationError):
        _ = SecretReference(uri="plain-text-secret")


def test_setup_plan_requires_dependency_order_and_rejects_secret_fields() -> None:
    first = SetupAction(
        action_id="config.write",
        title="Write configuration",
        reason="Persist non-secret selections",
        risk="low",
        reversible=True,
        depends_on=(),
        kind="write_config",
        parameters={"profile": "development"},
    )
    second = SetupAction(
        action_id="services.start",
        title="Start local services",
        reason="Provide data services",
        risk="medium",
        reversible=True,
        depends_on=("config.write",),
        kind="docker_compose_up",
        parameters={"profile": "development"},
    )
    plan = SetupPlan(
        plan_id="plan-001",
        profile=SetupProfile.DEVELOPMENT,
        detection_snapshot_id="snapshot-001",
        config_revision="config-001",
        actions=(first, second),
    )
    assert plan.actions[1].depends_on == ("config.write",)

    with pytest.raises(ValidationError, match="dependency order"):
        _ = SetupPlan(
            plan_id="bad-order",
            profile=SetupProfile.DEVELOPMENT,
            detection_snapshot_id="snapshot-001",
            config_revision="config-001",
            actions=(second, first),
        )

    with pytest.raises(ValidationError, match="secret-bearing"):
        _ = SetupAction(
            action_id="bad",
            title="Bad",
            reason="Bad",
            risk="high",
            reversible=False,
            depends_on=(),
            kind="write_config",
            parameters={"password": "leak"},
        )


def test_contract_enums_preserve_required_states() -> None:
    assert ActionState.MANUAL_RECOVERY_REQUIRED == "manual_recovery_required"
    assert CheckState.NOT_REQUIRED == "not_required"
    assert CapabilityName.PRODUCTION_CUTOVER == "production_cutover"


def test_detection_check_rejects_secret_evidence_keys() -> None:
    with pytest.raises(ValidationError, match="secret-bearing"):
        _ = DetectionCheck(
            check_id="github.auth",
            state=CheckState.READY,
            summary="Authenticated",
            impact="GitHub is available",
            evidence={"token": "secret"},
        )
