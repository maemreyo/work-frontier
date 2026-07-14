"""Fail-closed interpretation of declared harness applicability artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from pathlib import Path

_MIN_REASON_LENGTH = 10

HarnessStatus = Literal["pass", "fail", "not_applicable"]


@dataclass(frozen=True, slots=True)
class DeclaredHarnessOutcome:
    """Status override extracted from a freshly generated declared artifact."""

    status: HarnessStatus
    applicability_reason: str | None = None
    failure_detail: str | None = None


def resolve_declared_outcome(
    *,
    exit_code: int,
    artifact_path: Path,
) -> DeclaredHarnessOutcome:
    """Resolve command status and a truthful scoped not-applicable declaration."""
    if exit_code != 0:
        return DeclaredHarnessOutcome(status="fail")
    if not artifact_path.is_file():
        return DeclaredHarnessOutcome(status="pass")
    try:
        raw_payload: object = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return DeclaredHarnessOutcome(status="pass")
    if not isinstance(raw_payload, dict):
        return DeclaredHarnessOutcome(status="pass")
    payload = cast("dict[str, object]", raw_payload)
    if payload.get("status") != "not_applicable":
        return DeclaredHarnessOutcome(status="pass")
    reason = payload.get("applicability_reason")
    if not isinstance(reason, str) or len(reason.strip()) < _MIN_REASON_LENGTH:
        return DeclaredHarnessOutcome(
            status="fail",
            failure_detail=(
                "not_applicable artifact requires a substantive applicability_reason"
            ),
        )
    return DeclaredHarnessOutcome(
        status="not_applicable",
        applicability_reason=reason.strip(),
    )
