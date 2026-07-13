#!/usr/bin/env python3
"""Certify the exact revision and close plan checkboxes through Item 8."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
PLAN: Final = ROOT / ".omo" / "plans" / "full-product-implementation.md"
ITEMS: Final = ("P0", "1", "2", "3", "4", "5", "6", "7", "8")
HARNESS_IDS: Final = (
    "WF-HAR-DOMAIN-02",
    "WF-HAR-DOMAIN-05",
    "WF-HAR-DOMAIN-03",
    "WF-HAR-PROPERTY-02",
    "WF-HAR-META-05",
)


def _run(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=capture,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def _capture(*args: str) -> str:
    return _run(*args, capture=True).stdout.strip()


def main() -> int:
    """Run exact-revision gates, then record truthful plan completion."""
    status = _capture("git", "status", "--porcelain", "--untracked-files=all")
    if status:
        msg = "working tree must be clean before certification:\n" + status
        raise SystemExit(msg)
    subject_sha = _capture("git", "rev-parse", "HEAD")

    _ = _run("make", "check")
    _ = _run("make", "recertify-foundation")
    for harness_id in HARNESS_IDS:
        _ = _run("make", "harness", f"ID={harness_id}")

    post_status = _capture(
        "git",
        "status",
        "--porcelain",
        "--untracked-files=all",
    )
    if post_status:
        msg = (
            "certification changed tracked source files; refusing plan closure:\n"
            + post_status
        )
        raise SystemExit(msg)

    content = PLAN.read_text(encoding="utf-8")
    status_updates = {
        (
            "Current code is a useful implementation candidate, but P0 and "
            "Todos 1-4 remain open until Todo 5 can recertify them truthfully."
        ): (
            "P0 and Todos 1-5 are certified against the exact subject revision "
            "recorded under Item 8; Wave 1 may continue."
        ),
        (
            "**Continuation status:** blocked before Todo 6; next executable "
            "work is foundation repair followed by Todo 5 and recertification."
        ): (
            "**Continuation status:** foundation recertified and Wave 1 Items "
            "6-8 complete; next executable work is Items 9 and 10."
        ),
    }
    for old_status, new_status in status_updates.items():
        if old_status in content:
            content = content.replace(old_status, new_status, 1)
        elif new_status not in content:
            msg = f"plan status marker missing: {old_status}"
            raise SystemExit(msg)

    for item in ITEMS:
        open_marker = f"- [ ] {item}."
        closed_marker = f"- [x] {item}."
        if closed_marker in content:
            continue
        if content.count(open_marker) != 1:
            msg = f"expected one open plan marker for {item}"
            raise SystemExit(msg)
        content = content.replace(open_marker, closed_marker, 1)

    item_8_commit = (
        "      Commit: Y | `feat(graph): add typed cycle and traversal engine`"
    )
    certification_note = (
        "      Certification: exact subject `"
        + subject_sha
        + "` passed `make check`, foundation recertification, "
        + "WF-HAR-DOMAIN-02/03/05, WF-HAR-PROPERTY-02, and WF-HAR-META-05."
    )
    if certification_note not in content:
        if content.count(item_8_commit) != 1:
            msg = "Item 8 commit marker is missing or ambiguous"
            raise SystemExit(msg)
        content = content.replace(
            item_8_commit,
            item_8_commit + "\n" + certification_note,
            1,
        )
    _ = PLAN.write_text(content, encoding="utf-8")

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
    print(f"plan P0-8 closed against certified subject {subject_sha}")
    print("commit the plan and anatomy manifest as a documentation-only follow-up")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
