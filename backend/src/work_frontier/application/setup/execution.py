"""Journaled setup execution, verification, compensation, and resume."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from work_frontier.application.ports.setup import SetupActionRunner, SetupJournal
from work_frontier.application.setup.planning import assert_plan_current
from work_frontier.contracts.setup import (
    ActionResult,
    ActionState,
    DetectionSnapshot,
    SetupAction,
    SetupPlan,
)

_SECRET_VALUE = re.compile(
    r"(?i)(password|token|private[_-]?key|secret)\s*[:=]\s*[^\s,;]+"
)
_INSTALLATION_ID = "default"


def execute_plan(  # noqa: PLR0913 - explicit exact-plan inputs are auditable
    *,
    session_id: str,
    plan: SetupPlan,
    current_snapshot: DetectionSnapshot,
    current_config_revision: str,
    journal: SetupJournal,
    runner: SetupActionRunner,
) -> tuple[ActionResult, ...]:
    """Execute or resume a reviewed plan without repeating verified actions."""
    assert_plan_current(plan, current_snapshot, current_config_revision)
    journal.save_plan(plan)
    journal.acquire_installation_lock(_INSTALLATION_ID, session_id)
    try:
        journal.create_session(session_id, plan.plan_id)
        return _execute_locked(
            session_id=session_id,
            plan=plan,
            journal=journal,
            runner=runner,
        )
    finally:
        journal.release_installation_lock(_INSTALLATION_ID, session_id)


def _execute_locked(
    *,
    session_id: str,
    plan: SetupPlan,
    journal: SetupJournal,
    runner: SetupActionRunner,
) -> tuple[ActionResult, ...]:
    existing = journal.load_session(session_id).actions
    results: list[ActionResult] = []
    applied: list[SetupAction] = []
    for action in plan.actions:
        previous = existing.get(action.action_id)
        if previous is not None and previous.state is ActionState.VERIFIED:
            results.append(
                ActionResult(
                    action_id=action.action_id,
                    state=ActionState.VERIFIED,
                    message="Already verified; skipped during resume",
                    redacted_evidence=dict(previous.payload),
                )
            )
            continue
        try:
            journal.record_transition(
                session_id,
                action.action_id,
                ActionState.RUNNING,
                {},
            )
            applied_evidence = _redact_mapping(runner.apply(action))
            journal.record_transition(
                session_id,
                action.action_id,
                ActionState.APPLIED,
                applied_evidence,
            )
            applied.append(action)
            verified_evidence = _redact_mapping(runner.verify(action))
            journal.record_transition(
                session_id,
                action.action_id,
                ActionState.VERIFIED,
                verified_evidence,
            )
            results.append(
                ActionResult(
                    action_id=action.action_id,
                    state=ActionState.VERIFIED,
                    message="Applied and verified",
                    redacted_evidence=verified_evidence,
                )
            )
        except Exception as exc:  # noqa: BLE001 - adapter boundary must journal failure
            failure: dict[str, str | int | bool | None] = {
                "error": _redact_text(str(exc))
            }
            journal.record_transition(
                session_id,
                action.action_id,
                ActionState.FAILED,
                failure,
            )
            results.append(
                ActionResult(
                    action_id=action.action_id,
                    state=ActionState.FAILED,
                    message="Setup action failed",
                    redacted_evidence=failure,
                )
            )
            manual_recovery = _compensate(session_id, journal, runner, applied)
            if manual_recovery:
                results = [
                    result.model_copy(
                        update={
                            "state": ActionState.MANUAL_RECOVERY_REQUIRED,
                            "message": "Applied side effect requires manual recovery",
                        }
                    )
                    if result.action_id in manual_recovery
                    else result
                    for result in results
                ]
            break
    return tuple(results)


def _compensate(
    session_id: str,
    journal: SetupJournal,
    runner: SetupActionRunner,
    actions: list[SetupAction],
) -> set[str]:
    manual_recovery: set[str] = set()
    for action in reversed(actions):
        if not action.reversible:
            journal.record_transition(
                session_id,
                action.action_id,
                ActionState.MANUAL_RECOVERY_REQUIRED,
                {"reason": "applied action has no automatic compensation"},
            )
            manual_recovery.add(action.action_id)
            continue
        journal.record_transition(
            session_id,
            action.action_id,
            ActionState.COMPENSATING,
            {},
        )
        try:
            evidence = _redact_mapping(runner.compensate(action))
            journal.record_transition(
                session_id,
                action.action_id,
                ActionState.COMPENSATED,
                evidence,
            )
        except Exception as exc:  # noqa: BLE001 - compensation must be journaled
            journal.record_transition(
                session_id,
                action.action_id,
                ActionState.MANUAL_RECOVERY_REQUIRED,
                {"error": _redact_text(str(exc))},
            )
            manual_recovery.add(action.action_id)
    return manual_recovery


def _redact_mapping(
    value: dict[str, str | int | bool | None],
) -> dict[str, str | int | bool | None]:
    redacted: dict[str, str | int | bool | None] = {}
    for key, item in value.items():
        if isinstance(item, str):
            redacted[key] = _redact_text(item)
        else:
            redacted[key] = item
    return redacted


def _redact_text(value: str) -> str:
    return _SECRET_VALUE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
