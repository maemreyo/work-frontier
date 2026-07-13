#!/usr/bin/env python3
"""Certify one clean committed revision for completed plan items P0 through 27."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
PLAN: Final = ROOT / ".omo" / "plans" / "full-product-implementation.md"
ITEMS: Final = ("P0", *(str(number) for number in range(1, 28)))
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
    "WF-HAR-SEC-09",
    "WF-HAR-SEC-13",
    "WF-HAR-PROPERTY-04",
    "WF-HAR-META-04",
    "WF-HAR-GITHUB-SANDBOX-01",
    "WF-HAR-539-REPLAY-01",
    "WF-HAR-CONTRACT-01",
    "WF-HAR-CONTRACT-04",
    "WF-HAR-INTEG-04",
    "WF-HAR-PRODUCT-01",
    "WF-HAR-PRODUCT-02",
    "WF-HAR-PRODUCT-03",
    "WF-HAR-PRODUCT-04",
    "WF-HAR-PRODUCT-05",
    "WF-HAR-PRODUCT-06",
    "WF-HAR-OPS-01",
)
PLATFORM_ENV: Final = {
    "DATABASE_URL": (
        "postgresql+psycopg://work_frontier:work_frontier@localhost:54329/work_frontier"
    ),
    "MINIO_ENDPOINT_URL": "http://localhost:9002",
    "MINIO_ROOT_USER": "work-frontier",
    "MINIO_ROOT_PASSWORD": "work-frontier-minio",
}
_SANDBOX_ENV: Final = (
    "WF_GITHUB_SANDBOX_REPOSITORY",
    "WF_GITHUB_SANDBOX_TOKEN",
)


def _run(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(PLATFORM_ENV)
    result = subprocess.run(
        list(args),
        cwd=ROOT,
        check=False,
        capture_output=capture,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def _capture(*args: str) -> str:
    return _run(*args, capture=True).stdout.strip()


def main() -> int:
    """Run all release-blocking harnesses through the Builder workspace."""
    status = _capture("git", "status", "--porcelain", "--untracked-files=all")
    if status:
        msg = "working tree must be clean before certification:\n" + status
        raise SystemExit(msg)
    missing_env = [name for name in _SANDBOX_ENV if not os.environ.get(name)]
    if missing_env:
        msg = "GitHub sandbox environment is required: " + ", ".join(missing_env)
        raise SystemExit(msg)
    plan = PLAN.read_text(encoding="utf-8")
    missing_items = [item for item in ITEMS if f"- [x] {item}." not in plan]
    if missing_items:
        msg = f"plan items are not marked complete: {missing_items}"
        raise SystemExit(msg)

    subject_sha = _capture("git", "rev-parse", "HEAD")
    _ = _run("make", "check")
    _ = _run("make", "infra-up")
    try:
        _ = _run("make", "migration-smoke")
        _ = _run("make", "storage-smoke")
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
    post_status = _capture("git", "status", "--porcelain", "--untracked-files=all")
    if post_status:
        msg = "certification changed tracked source files:\n" + post_status
        raise SystemExit(msg)
    print(f"plan P0-27 certified against exact subject {subject_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
