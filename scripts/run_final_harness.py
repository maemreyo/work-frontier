#!/usr/bin/env python3
"""Executable commands for final GA harnesses that were previously specified only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
ARTIFACT = Path(
    os.environ.get("WF_HARNESS_ARTIFACT", ".omo/evidence/final/final-harness.json")
)

COMMANDS: Final[dict[str, tuple[str, ...]]] = {
    "WF-HAR-STATIC-03": (
        "uv",
        "run",
        "python",
        "scripts/run_ops_harness.py",
        "--mode",
        "dead-code",
    ),
    "WF-HAR-CONTRACT-02": ("make", "migration-smoke"),
    "WF-HAR-CONTRACT-03": (
        "uv",
        "run",
        "pytest",
        "-q",
        "backend/tests/contract/test_event_schemas.py",
    ),
    "WF-HAR-OPS-02": (
        "uv",
        "run",
        "python",
        "scripts/run_ops_harness.py",
        "--mode",
        "load",
    ),
    "WF-HAR-OPS-02-L": (
        "uv",
        "run",
        "python",
        "scripts/run_ops_harness.py",
        "--mode",
        "large",
    ),
    "WF-HAR-OPS-02-T": (
        "uv",
        "run",
        "python",
        "scripts/run_ops_harness.py",
        "--mode",
        "tenant",
    ),
    "WF-HAR-OPS-04": (
        "uv",
        "run",
        "python",
        "scripts/run_ops_harness.py",
        "--mode",
        "soak",
    ),
    "WF-HAR-OPS-05": (
        "uv",
        "run",
        "python",
        "scripts/run_ops_harness.py",
        "--mode",
        "failure",
    ),
    "WF-HAR-OPS-06": (
        "uv",
        "run",
        "python",
        "scripts/run_ops_harness.py",
        "--mode",
        "dr",
    ),
    "WF-HAR-OPS-07": (
        "uv",
        "run",
        "python",
        "scripts/run_ops_harness.py",
        "--mode",
        "migration",
    ),
    "WF-HAR-SEC-01": (
        "uv",
        "run",
        "python",
        "scripts/run_security_harness.py",
        "--mode",
        "auth",
    ),
    "WF-HAR-SEC-02": (
        "uv",
        "run",
        "python",
        "scripts/run_security_harness.py",
        "--mode",
        "input",
    ),
    "WF-HAR-SEC-03": (
        "uv",
        "run",
        "python",
        "scripts/run_security_harness.py",
        "--mode",
        "ssrf",
    ),
    "WF-HAR-SEC-05": (
        "uv",
        "run",
        "python",
        "scripts/run_security_harness.py",
        "--mode",
        "csrf",
    ),
    "WF-HAR-SEC-06": (
        "uv",
        "run",
        "python",
        "scripts/run_security_harness.py",
        "--mode",
        "rate",
    ),
    "WF-HAR-SEC-07": (
        "uv",
        "run",
        "python",
        "scripts/run_security_harness.py",
        "--mode",
        "dependency",
    ),
    "WF-HAR-SEC-08": (
        "uv",
        "run",
        "python",
        "scripts/run_security_harness.py",
        "--mode",
        "tls",
    ),
    "WF-HAR-SEC-10": (
        "uv",
        "run",
        "python",
        "scripts/run_security_harness.py",
        "--mode",
        "safety",
    ),
    "WF-HAR-SEC-11": (
        "uv",
        "run",
        "python",
        "scripts/run_security_harness.py",
        "--mode",
        "override",
    ),
    "WF-HAR-SEC-12": (
        "uv",
        "run",
        "python",
        "scripts/run_security_harness.py",
        "--mode",
        "authority",
    ),
    "WF-HAR-A11Y-01": (
        "pnpm",
        "--dir",
        "frontend",
        "exec",
        "playwright",
        "test",
        "tests/accessibility/wcag-audit.spec.ts",
    ),
    "WF-HAR-A11Y-02": (
        "pnpm",
        "--dir",
        "frontend",
        "exec",
        "playwright",
        "test",
        "tests/accessibility/keyboard-nav.spec.ts",
    ),
    "WF-HAR-A11Y-03": (
        "pnpm",
        "--dir",
        "frontend",
        "exec",
        "playwright",
        "test",
        "tests/accessibility/focus-appearance.spec.ts",
    ),
    "WF-HAR-A11Y-04": (
        "pnpm",
        "--dir",
        "frontend",
        "exec",
        "playwright",
        "test",
        "tests/accessibility/drag-alternatives.spec.ts",
    ),
}


def main() -> int:
    """Run one final harness and always produce its declared artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--id", required=True)
    args = parser.parse_args()
    command = COMMANDS.get(args.id)
    if command is None:
        msg = f"unsupported final harness ID: {args.id}"
        raise SystemExit(msg)
    is_playwright = "playwright" in command
    test_results = ROOT / "frontend" / "test-results"
    if is_playwright:
        shutil.rmtree(test_results, ignore_errors=True)
    completed = subprocess.run(
        list(command),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    if completed.returncode != 0:
        raise SystemExit((completed.stdout or "") + (completed.stderr or ""))
    if not ARTIFACT.exists():
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        _ = ARTIFACT.write_text(
            json.dumps(
                {
                    "harness_id": args.id,
                    "status": "passed",
                    "command": list(command),
                    "stdout": (completed.stdout or "")[-4_000:],
                    "attachments": [
                        {
                            "path": str(path.relative_to(ROOT)),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        }
                        for path in sorted(test_results.rglob("*.png"))
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
