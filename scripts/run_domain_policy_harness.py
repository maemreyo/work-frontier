#!/usr/bin/env python3
"""Run the policy-gate harness and emit a domain-specific receipt."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
TEST_PATH: Final = "backend/tests/domain/test_policy_gates.py"
FALLBACK_ARTIFACT: Final = "evidence/domain/policy-gates.json"


def main() -> int:
    """Execute the policy matrix and write its authoritative receipt."""
    command = [sys.executable, "-m", "pytest", TEST_PATH, "-v"]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    _ = sys.stdout.write(completed.stdout)
    _ = sys.stderr.write(completed.stderr)

    configured_artifact = os.environ.get("WF_HARNESS_ARTIFACT")
    artifact_path = (
        Path(configured_artifact) if configured_artifact else ROOT / FALLBACK_ARTIFACT
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "1.0.0",
        "kind": "domain_policy_harness_receipt",
        "command": command,
        "test_path": TEST_PATH,
        "exit_code": completed.returncode,
        "passed": completed.returncode == 0,
    }
    temporary_path = artifact_path.with_suffix(f"{artifact_path.suffix}.tmp")
    _ = temporary_path.write_text(
        f"{json.dumps(receipt, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    _ = temporary_path.replace(artifact_path)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
