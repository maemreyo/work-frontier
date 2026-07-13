#!/usr/bin/env python3
"""Certify the exact committed revision for completed plan items P0 through 9."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
PLAN: Final = ROOT / ".omo" / "plans" / "full-product-implementation.md"
ITEMS: Final = ("P0", "1", "2", "3", "4", "5", "6", "7", "8", "9")
HARNESS_IDS: Final = (
    "WF-HAR-DOMAIN-02",
    "WF-HAR-DOMAIN-05",
    "WF-HAR-DOMAIN-03",
    "WF-HAR-PROPERTY-02",
    "WF-HAR-META-05",
    "WF-HAR-DOMAIN-04",
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
    """Run foundation and Wave 1 harnesses against one clean commit."""
    status = _capture("git", "status", "--porcelain", "--untracked-files=all")
    if status:
        msg = "working tree must be clean before certification:\n" + status
        raise SystemExit(msg)

    plan = PLAN.read_text(encoding="utf-8")
    missing = [item for item in ITEMS if f"- [x] {item}." not in plan]
    if missing:
        msg = f"plan items are not marked complete: {missing}"
        raise SystemExit(msg)

    subject_sha = _capture("git", "rev-parse", "HEAD")
    _ = _run("make", "check")
    _ = _run("make", "infra-up")
    try:
        _ = _run("make", "recertify-foundation")
        for harness_id in HARNESS_IDS:
            _ = _run("make", "harness", f"ID={harness_id}")
    finally:
        _ = subprocess.run(
            ["make", "infra-down"],
            cwd=ROOT,
            check=False,
            text=True,
        )

    post_status = _capture(
        "git",
        "status",
        "--porcelain",
        "--untracked-files=all",
    )
    if post_status:
        msg = "certification changed tracked source files:\n" + post_status
        raise SystemExit(msg)

    print(f"plan P0-9 certified against exact subject {subject_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
