"""Independent setup capability readiness derivation."""

from __future__ import annotations

from work_frontier.contracts.setup import (
    ActionResult,
    ActionState,
    CapabilityName,
    CapabilityReport,
    CheckState,
    DetectionCheck,
    SetupProfile,
)

_ORDER = {
    CheckState.NOT_REQUIRED: 0,
    CheckState.READY: 1,
    CheckState.REPAIRABLE: 2,
    CheckState.NEEDS_INPUT: 3,
    CheckState.BLOCKED: 4,
}
_CAPABILITIES = (
    CapabilityName.LOCAL_RUNTIME,
    CapabilityName.GITHUB_INTEGRATION,
    CapabilityName.RELEASE_CERTIFICATION,
    CapabilityName.PRODUCTION_CUTOVER,
)
_REQUIRED_ACTIONS: dict[SetupProfile, dict[CapabilityName, frozenset[str]]] = {
    SetupProfile.DEVELOPMENT: {
        CapabilityName.LOCAL_RUNTIME: frozenset(
            {
                "services.local.start",
                "database.migrate",
                "storage.verify",
                "checks.fast",
            }
        ),
        CapabilityName.GITHUB_INTEGRATION: frozenset({"github.reference"}),
        CapabilityName.RELEASE_CERTIFICATION: frozenset(),
        CapabilityName.PRODUCTION_CUTOVER: frozenset(),
    },
    SetupProfile.PRODUCTION: {
        CapabilityName.LOCAL_RUNTIME: frozenset(
            {"services.external.verify", "checks.fast"}
        ),
        CapabilityName.GITHUB_INTEGRATION: frozenset({"github.app.verify"}),
        CapabilityName.RELEASE_CERTIFICATION: frozenset({"release.prepare"}),
        CapabilityName.PRODUCTION_CUTOVER: frozenset({"cutover.prepare"}),
    },
}
_FAILURE_STATES = frozenset({ActionState.FAILED, ActionState.MANUAL_RECOVERY_REQUIRED})


def derive_capability_reports(
    profile: SetupProfile,
    checks: tuple[DetectionCheck, ...],
    results: tuple[ActionResult, ...],
) -> tuple[CapabilityReport, ...]:
    """Return all capability states without collapsing them into one flag."""
    by_action = {result.action_id: result for result in results}
    reports: list[CapabilityReport] = []
    for capability in _CAPABILITIES:
        owned = tuple(check for check in checks if _owns(capability, check.check_id))
        if profile is SetupProfile.DEVELOPMENT and capability in {
            CapabilityName.RELEASE_CERTIFICATION,
            CapabilityName.PRODUCTION_CUTOVER,
        }:
            state = CheckState.NOT_REQUIRED
        elif not owned:
            state = CheckState.NEEDS_INPUT
        else:
            state = max((check.state for check in owned), key=_ORDER.__getitem__)
            state = _apply_execution_state(profile, capability, state, by_action)
        blocking = tuple(
            check for check in owned if _ORDER[check.state] > _ORDER[CheckState.READY]
        )
        reports.append(
            CapabilityReport(
                capability=capability,
                state=state,
                reason=_reason(state),
                impact=_impact(capability),
                next_actions=tuple(
                    remediation
                    for check in blocking
                    for remediation in check.remediation
                ),
                supporting_check_ids=tuple(check.check_id for check in owned),
            )
        )
    return tuple(reports)


def _apply_execution_state(
    profile: SetupProfile,
    capability: CapabilityName,
    detected_state: CheckState,
    results: dict[str, ActionResult],
) -> CheckState:
    required = _REQUIRED_ACTIONS[profile][capability]
    if not required:
        return detected_state
    relevant = tuple(
        results[action_id] for action_id in required if action_id in results
    )
    if any(result.state in _FAILURE_STATES for result in relevant):
        return CheckState.BLOCKED
    if (
        detected_state in {CheckState.READY, CheckState.REPAIRABLE}
        and required
        and all(
            action_id in results and results[action_id].state is ActionState.VERIFIED
            for action_id in required
        )
    ):
        return CheckState.READY
    return detected_state


def _reason(state: CheckState) -> str:
    return {
        CheckState.READY: "All required checks and setup actions are verified",
        CheckState.REPAIRABLE: (
            "Configuration exists but requires verified setup actions"
        ),
        CheckState.NEEDS_INPUT: "Capability requires additional configuration",
        CheckState.BLOCKED: "A blocking setup action or check failed",
        CheckState.NOT_REQUIRED: "Capability is not required for the selected profile",
    }[state]


def _owns(capability: CapabilityName, check_id: str) -> bool:
    if capability is CapabilityName.LOCAL_RUNTIME:
        return check_id.startswith(
            ("tool.", "services.", "config.", "migration.", "legacy.")
        )
    if capability is CapabilityName.GITHUB_INTEGRATION:
        return check_id.startswith("github.")
    if capability is CapabilityName.RELEASE_CERTIFICATION:
        return check_id.startswith("release.")
    return check_id.startswith("cutover.")


def _impact(capability: CapabilityName) -> str:
    return {
        CapabilityName.LOCAL_RUNTIME: "Controls whether Work Frontier can run locally",
        CapabilityName.GITHUB_INTEGRATION: "Controls repository synchronization",
        CapabilityName.RELEASE_CERTIFICATION: "Controls Standard release certification",
        CapabilityName.PRODUCTION_CUTOVER: "Controls approved writer activation",
    }[capability]
