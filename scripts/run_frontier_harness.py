#!/usr/bin/env python3
"""Run one deterministic frontier-engine harness and emit a receipt."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
TESTS_BY_MODE: Final = {
    "determinism": ("backend/tests/domain/test_frontier_engine.py",),
    "stability": ("backend/tests/property/test_frontier_properties.py",),
    "monotonicity": ("backend/tests/property/test_frontier_properties.py",),
    "ordering": ("backend/tests/property/test_frontier_properties.py",),
    "replay": ("backend/tests/metamorphic/test_frontier_replay.py",),
    "frontier-monotonicity": ("backend/tests/property/test_frontier_properties.py",),
    "readiness-monotonicity": ("backend/tests/property/test_frontier_properties.py",),
}
FALLBACK_BY_MODE: Final = {
    "determinism": "evidence/domain/frontier-computation.json",
    "stability": "evidence/property/frontier-determinism.json",
    "monotonicity": "evidence/property/readiness-monotonicity.json",
    "ordering": "evidence/property/input-ordering.json",
    "replay": "evidence/metamorphic/frontier-replay.json",
    "frontier-monotonicity": "evidence/metamorphic/frontier-monotonicity.json",
    "readiness-monotonicity": "evidence/metamorphic/readiness-monotonicity.json",
}


def main() -> int:
    """Execute the selected suite and always emit an authoritative receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--mode", choices=tuple(TESTS_BY_MODE), required=True)
    args = parser.parse_args()
    mode = str(args.mode)
    command = [sys.executable, "-m", "pytest", *TESTS_BY_MODE[mode], "-v"]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    _ = sys.stdout.write(completed.stdout)
    _ = sys.stderr.write(completed.stderr)
    configured = os.environ.get("WF_HARNESS_ARTIFACT")
    artifact = Path(configured) if configured else ROOT / FALLBACK_BY_MODE[mode]
    artifact.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "1.0.0",
        "kind": "frontier_engine_harness_receipt",
        "mode": mode,
        "command": command,
        "test_paths": list(TESTS_BY_MODE[mode]),
        "exit_code": completed.returncode,
        "passed": completed.returncode == 0,
    }
    temporary = artifact.with_suffix(f"{artifact.suffix}.tmp")
    _ = temporary.write_text(
        f"{json.dumps(receipt, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    _ = temporary.replace(artifact)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
