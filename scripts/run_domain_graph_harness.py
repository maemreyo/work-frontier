#!/usr/bin/env python3
"""Run one graph harness and emit a domain-specific receipt."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
TEST_BY_MODE: Final = {
    "dependency": "backend/tests/domain/test_dependency_chains.py",
    "property": "backend/tests/property/test_dependency_acyclicity.py",
    "isolation": "backend/tests/metamorphic/test_invalid_component_isolation.py",
}
FALLBACK_ARTIFACT_BY_MODE: Final = {
    "dependency": "evidence/domain/dependency-chains.json",
    "property": "evidence/property/dependency-acyclicity.json",
    "isolation": "evidence/metamorphic/invalid-component-isolation.json",
}
EXTRA_ARGS_BY_MODE: Final = {
    "dependency": ("-v",),
    "property": ("--hypothesis-seed=0",),
    "isolation": (),
}


def main() -> int:
    """Execute pytest and always write the authoritative graph receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--mode", choices=tuple(TEST_BY_MODE), required=True)
    args = parser.parse_args()
    mode = str(args.mode)
    test_path = TEST_BY_MODE[mode]
    command = [
        sys.executable,
        "-m",
        "pytest",
        test_path,
        *EXTRA_ARGS_BY_MODE[mode],
    ]

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
        Path(configured_artifact)
        if configured_artifact
        else ROOT / FALLBACK_ARTIFACT_BY_MODE[mode]
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "1.0.0",
        "kind": "domain_graph_harness_receipt",
        "mode": mode,
        "command": command,
        "test_path": test_path,
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
