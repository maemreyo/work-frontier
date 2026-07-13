from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from work_frontier.contracts.harness_applicability import resolve_declared_outcome


def test_scoped_not_applicable_requires_substantive_reason(tmp_path: Path) -> None:
    artifact = tmp_path / "capacity.json"
    _ = artifact.write_text(
        json.dumps(
            {
                "status": "not_applicable",
                "applicability_reason": (
                    "Large envelope support was not declared for this Standard release"
                ),
            }
        ),
        encoding="utf-8",
    )

    outcome = resolve_declared_outcome(exit_code=0, artifact_path=artifact)

    assert outcome.status == "not_applicable"
    assert outcome.applicability_reason is not None
    assert outcome.failure_detail is None


def test_not_applicable_without_reason_fails_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "capacity.json"
    _ = artifact.write_text('{"status":"not_applicable"}', encoding="utf-8")

    outcome = resolve_declared_outcome(exit_code=0, artifact_path=artifact)

    assert outcome.status == "fail"
    assert outcome.failure_detail is not None


def test_nonzero_exit_cannot_be_overridden_by_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "capacity.json"
    _ = artifact.write_text(
        json.dumps(
            {
                "status": "not_applicable",
                "applicability_reason": "A sufficiently long but irrelevant reason",
            }
        ),
        encoding="utf-8",
    )

    outcome = resolve_declared_outcome(exit_code=9, artifact_path=artifact)

    assert outcome.status == "fail"
