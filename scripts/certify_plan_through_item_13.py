#!/usr/bin/env python3
"""Certify one clean committed revision for completed plan items P0 through 13."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
PLAN: Final = ROOT / ".omo" / "plans" / "full-product-implementation.md"
ITEMS: Final = (
    "P0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
)
HARNESS_IDS: Final = (
    "WF-HAR-DOMAIN-02",
    "WF-HAR-DOMAIN-05",
    "WF-HAR-DOMAIN-03",
    "WF-HAR-PROPERTY-02",
    "WF-HAR-META-05",
    "WF-HAR-DOMAIN-04",
    "WF-HAR-DOMAIN-01",
    "WF-HAR-PROPERTY-01",
    "WF-HAR-PROPERTY-03",
    "WF-HAR-PROPERTY-05",
    "WF-HAR-META-01",
    "WF-HAR-META-02",
    "WF-HAR-META-03",
    "WF-HAR-SEC-04",
    "WF-HAR-SEC-14",
    "WF-HAR-SEC-15",
    "WF-HAR-INTEG-03",
    "WF-HAR-INTEG-05",
    "WF-HAR-INTEG-06",
    "WF-HAR-OPS-03",
)
PLATFORM_ENV: Final = {
    "DATABASE_URL": (
        "postgresql+psycopg://work_frontier:work_frontier@localhost:54329/work_frontier"
    ),
    "MINIO_ENDPOINT_URL": "http://localhost:9002",
    "MINIO_ROOT_USER": "work-frontier",
    "MINIO_ROOT_PASSWORD": "work-frontier-minio",
}


def _run(
    *args: str,
    capture: bool = False,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        list(args),
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=capture,
        env=env,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def _capture(*args: str) -> str:
    return _run(*args, capture=True).stdout.strip()


def main() -> int:
    """Run static, infrastructure, and registry harnesses against one commit."""
    status = _capture("git", "status", "--porcelain", "--untracked-files=all")
    if status:
        raise SystemExit("working tree must be clean before certification:\n" + status)

    plan = PLAN.read_text(encoding="utf-8")
    missing = [item for item in ITEMS if f"- [x] {item}." not in plan]
    if missing:
        msg = f"plan items are not marked complete: {missing}"
        raise SystemExit(msg)

    subject_sha = _capture("git", "rev-parse", "HEAD")
    _ = _run("make", "check")
    _ = _run("make", "infra-up")
    try:
        _ = _run("make", "migration-smoke", extra_env=PLATFORM_ENV)
        _ = _run("make", "storage-smoke", extra_env=PLATFORM_ENV)
        _ = _run("make", "recertify-foundation", extra_env=PLATFORM_ENV)
        for harness_id in HARNESS_IDS:
            _ = _run(
                "make",
                "harness",
                f"ID={harness_id}",
                extra_env=PLATFORM_ENV,
            )
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
        raise SystemExit("certification changed tracked source files:\n" + post_status)

    print(f"plan P0-13 certified against exact subject {subject_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
