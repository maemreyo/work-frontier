#!/usr/bin/env python3
"""Run one Wave-3 harness mode and emit its declared machine-readable receipt."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
_MODE_TESTS: Final = {
    "decision-atomicity": (
        "backend/tests/application/test_decision_cycles.py",
        "backend/tests/integration/test_decision_cycle_postgres.py",
    ),
    "authorization": (
        "backend/tests/security/test_authorization_identity.py",
        "backend/tests/platform_layer/test_wave3_schema.py",
    ),
    "credential-exposure": (
        "backend/tests/security/test_authorization_identity.py",
        "backend/tests/platform_layer/test_wave3_schema.py",
    ),
    "adapters": (
        "backend/tests/adapters/test_reference_and_connections.py",
        "backend/tests/adapters/test_github_adapter.py",
    ),
    "convergence": ("backend/tests/property/test_projection_convergence.py",),
    "parity": ("backend/tests/metamorphic/test_projection_parity.py",),
    "539-replay": (
        "backend/tests/adapters/test_reference_and_connections.py",
        "backend/tests/adapters/test_github_adapter.py",
        "backend/tests/application/test_ingestion.py",
        "backend/tests/crosscut/test_539_replay.py",
    ),
    "github-sandbox": ("backend/tests/crosscut/test_github_sandbox.py",),
    "ingestion": ("backend/tests/application/test_ingestion.py",),
}


def _artifact_path() -> Path:
    value = os.environ.get("WF_HARNESS_ARTIFACT")
    if value is None:
        return ROOT / ".omo" / "evidence" / "wave3-harness.json"
    return Path(value)


def _required_environment(mode: str) -> None:
    if mode != "github-sandbox":
        return
    missing = [
        name
        for name in (
            "WF_GITHUB_SANDBOX_REPOSITORY",
            "WF_GITHUB_SANDBOX_TOKEN",
        )
        if not os.environ.get(name)
    ]
    if missing:
        msg = f"GitHub sandbox harness requires environment: {', '.join(missing)}"
        raise SystemExit(msg)


def _platform_durability_probe() -> subprocess.CompletedProcess[str] | None:
    if "DATABASE_URL" not in os.environ:
        msg = "decision-atomicity harness requires DATABASE_URL"
        raise SystemExit(msg)
    probe_artifact = _artifact_path().with_suffix(".platform-durability.json")
    env = {**os.environ, "WF_HARNESS_ARTIFACT": str(probe_artifact)}
    return subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/run_platform_harness.py",
            "--mode",
            "durability",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def main() -> int:
    """Execute one configured pytest slice and write a structured receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--mode", choices=tuple(_MODE_TESTS), required=True)
    args = parser.parse_args()
    _required_environment(args.mode)
    preflight = (
        _platform_durability_probe() if args.mode == "decision-atomicity" else None
    )
    command = ["uv", "run", "pytest", "-q", *_MODE_TESTS[args.mode]]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    artifact = _artifact_path()
    artifact.parent.mkdir(parents=True, exist_ok=True)
    preflight_returncode = 0 if preflight is None else preflight.returncode
    exit_code = completed.returncode or preflight_returncode
    receipt = {
        "command": command,
        "exit_code": exit_code,
        "mode": args.mode,
        "passed": exit_code == 0,
        "platform_preflight_stderr": (
            "" if preflight is None else preflight.stderr[-4000:]
        ),
        "platform_preflight_stdout": (
            "" if preflight is None else preflight.stdout[-4000:]
        ),
        "stderr": completed.stderr[-4000:],
        "stdout": completed.stdout[-4000:],
    }
    _ = artifact.write_text(
        f"{json.dumps(receipt, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    print(json.dumps({"artifact": str(artifact), **receipt}, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
