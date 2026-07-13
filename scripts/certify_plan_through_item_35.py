#!/usr/bin/env python3
"""Certify one clean implementation revision and close plan Items 28 through 35."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Final

from work_frontier.contracts.final_certification import (
    FinalCertificationInputError,
    validate_exact_certification_environment,
    validate_plan_ready_for_final_certification,
)

ROOT: Final = Path(__file__).resolve().parents[1]
PLAN: Final = ROOT / ".omo" / "plans" / "full-product-implementation.md"


def _run(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=ROOT,
        capture_output=capture,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def _capture(*args: str) -> str:
    return _run(*args, capture=True).stdout.strip()


def _close_items(subject_sha: str) -> None:
    content = PLAN.read_text(encoding="utf-8")
    for item in range(28, 36):
        marker = f"- [ ] {item}."
        if content.count(marker) != 1:
            msg = f"expected exactly one open Item {item} marker"
            raise SystemExit(msg)
        content = content.replace(marker, f"- [x] {item}.", 1)
    old_status = (
        "**Continuation status:** P0 through Todo 27 are implemented and verified; "
        "the next executable work is Todo 28, Coordinator proposal and dependency "
        "workflows. Todos 28-35 remain open until exact-revision GA certification; "
        "F1-F4 additionally require surfaced audit results and explicit user "
        "acceptance."
    )
    new_status = (
        "**Continuation status:** P0 through Todo 35 are implemented and exact-"
        "revision certified; F1-F4 remain open pending surfaced audit results and "
        "explicit user acceptance."
    )
    if old_status in content:
        content = content.replace(old_status, new_status, 1)
    notes = {
        28: (
            "Coordinator proposal/dependency journey and accessibility "
            "alternative passed."
        ),
        29: (
            "Executive/Operator role matrix, export authority, recovery, and "
            "redaction passed."
        ),
        30: "All four WCAG 2.2 AA harnesses passed on required viewports.",
        31: (
            "Copilot remained default-off and passed lifecycle-isolation and "
            "injection tests."
        ),
        32: "All 15 security harnesses passed with no high or critical finding.",
        33: (
            "Deployment, SLO, failure, DR, migration, and 72-hour soak evidence passed."
        ),
        34: "All 68 harness receipts were bound to one subject and Ed25519-signed.",
        35: (
            "Approved eight-phase #539 cutover reached one writer with "
            "rollback certified."
        ),
    }
    for item, note in notes.items():
        commit_prefix = "      Commit: Y | `"
        item_start = content.index(f"- [x] {item}.")
        next_start = content.find("\n- [", item_start + 1)
        if next_start < 0:
            next_start = len(content)
        section = content[item_start:next_start]
        commit_offset = section.find(commit_prefix)
        if commit_offset < 0:
            msg = f"Item {item} commit marker missing"
            raise SystemExit(msg)
        absolute = item_start + commit_offset
        line_end = content.find("\n", absolute)
        rendered = (
            f"      Completion verification: {note} Exact subject `{subject_sha}`."
        )
        if rendered not in section:
            content = (
                content[: line_end + 1] + rendered + "\n" + content[line_end + 1 :]
            )
    _ = PLAN.write_text(content, encoding="utf-8")


def main() -> int:
    """Run GA release/cutover gates and close only implementation todos."""
    status = _capture("git", "status", "--porcelain", "--untracked-files=all")
    if status:
        msg = "working tree must be clean before exact certification:\n" + status
        raise SystemExit(msg)
    try:
        validate_exact_certification_environment(os.environ)
    except FinalCertificationInputError as exc:
        raise SystemExit(str(exc)) from exc
    soak_seconds = int(os.environ.get("WF_SOAK_DURATION_SECONDS", "0"))
    if soak_seconds < 72 * 60 * 60:
        msg = "WF_SOAK_DURATION_SECONDS must be at least 259200 for GA"
        raise SystemExit(msg)

    plan = PLAN.read_text(encoding="utf-8")
    try:
        validate_plan_ready_for_final_certification(plan)
    except FinalCertificationInputError as exc:
        raise SystemExit(str(exc)) from exc

    subject_sha = _capture("git", "rev-parse", "HEAD")
    _ = _run("make", "check")
    _ = _run("make", "infra-up")
    try:
        _ = _run("make", "migration-smoke")
        _ = _run("make", "storage-smoke")
        _ = _run("uv", "run", "python", "scripts/run_release_certification.py")
        _ = _run("uv", "run", "python", "scripts/run_cutover_539.py")
    finally:
        _ = subprocess.run(
            ["make", "infra-down"],
            cwd=ROOT,
            check=False,
            text=True,
        )

    _close_items(subject_sha)
    _ = _run(
        "python3",
        "scripts/check_anatomy_drift.py",
        "docs/anatomy",
        "--repo-root",
        ".",
        "--mode",
        "update",
        "--generator-version",
        "anatomy-skill@1.0.0",
    )
    _ = _run("git", "diff", "--check")
    print(f"Items 28-35 certified against exact subject {subject_sha}")
    print("F1-F4 remain open until explicit review and approval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
