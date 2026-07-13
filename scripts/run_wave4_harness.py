#!/usr/bin/env python3
"""Run Wave-4 control-plane harnesses and emit a structured receipt."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Final, TypedDict

ROOT: Final = Path(__file__).resolve().parents[1]
_COMMANDS: Final[dict[str, tuple[tuple[str, ...], ...]]] = {
    "schema-regression": (
        (
            "uv",
            "run",
            "pytest",
            "backend/tests/platform_layer/test_schema_registration.py",
            "-q",
        ),
    ),
    "cutover": (("uv", "run", "pytest", "backend/tests/domain/test_cutover.py", "-q"),),
    "proposals": (
        (
            "uv",
            "run",
            "pytest",
            "backend/tests/domain/test_proposals.py",
            "backend/tests/product/test_projection_update.py",
            "-q",
        ),
    ),
    "leases": (
        (
            "uv",
            "run",
            "pytest",
            "backend/tests/domain/test_coordination.py",
            "backend/tests/product/test_atomic_claim_race.py",
            "-q",
        ),
    ),
    "break-glass": (
        (
            "uv",
            "run",
            "pytest",
            "backend/tests/security/test_break_glass_retention.py",
            "-q",
        ),
    ),
    "api-contract": (
        ("uv", "run", "pytest", "backend/tests/contract/test_api_schema.py", "-q"),
    ),
    "process-contract": (
        ("uv", "run", "pytest", "backend/tests/contract/test_inter_service.py", "-q"),
    ),
    "web": (
        ("uv", "run", "pytest", "backend/tests/integration/test_web_server.py", "-q"),
    ),
    "cli": (("uv", "run", "pytest", "backend/tests/interfaces/test_cli.py", "-q"),),
    "stale-decision": (
        ("uv", "run", "pytest", "backend/tests/product/test_stale_decision.py", "-q"),
    ),
    "projection-update": (
        (
            "uv",
            "run",
            "pytest",
            "backend/tests/product/test_projection_update.py",
            "-q",
        ),
    ),
    "ui-shell": (
        (
            "pnpm",
            "--dir",
            "frontend",
            "exec",
            "vitest",
            "run",
            "tests/control-room/onboarding.test.ts",
        ),
        (
            "pnpm",
            "--dir",
            "frontend",
            "exec",
            "playwright",
            "test",
            "tests/product/control-room.spec.ts",
        ),
    ),
    "builder": (
        (
            "pnpm",
            "--dir",
            "frontend",
            "exec",
            "vitest",
            "run",
            "tests/control-room/builder.test.ts",
        ),
        (
            "pnpm",
            "--dir",
            "frontend",
            "exec",
            "playwright",
            "test",
            "tests/product/control-room.spec.ts",
            "--grep",
            "Builder",
        ),
    ),
    "smoke": (
        (
            "uv",
            "run",
            "pytest",
            "backend/tests/integration/test_web_server.py",
            "backend/tests/contract/test_inter_service.py",
            "-q",
        ),
    ),
}


class Execution(TypedDict):
    """One subprocess execution captured in a harness receipt."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str


_DEFAULT_ARTIFACTS: Final = {
    "schema-regression": ".omo/evidence/product/schema-registration.json",
    "cutover": ".omo/evidence/product/writer-cutover.json",
    "proposals": ".omo/evidence/product/proposals.json",
    "leases": ".omo/evidence/product/atomic-claim-race.json",
    "break-glass": ".omo/evidence/security/break-glass-retention.json",
    "api-contract": ".omo/evidence/contract/api-schema.json",
    "process-contract": ".omo/evidence/contract/inter-service.json",
    "web": ".omo/evidence/integration/web-server.json",
    "cli": ".omo/evidence/product/cli-parity.json",
    "stale-decision": ".omo/evidence/product/stale-decision.json",
    "projection-update": ".omo/evidence/product/projection-update.json",
    "ui-shell": ".omo/evidence/product/onboarding-recommendation.json",
    "builder": ".omo/evidence/product/builder-workspace.json",
    "smoke": ".omo/evidence/ops/smoke.json",
}


def _run(command: tuple[str, ...]) -> Execution:
    result = subprocess.run(
        list(command),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    return {
        "command": list(command),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--mode", required=True, choices=tuple(_COMMANDS))
    args = parser.parse_args()
    mode = str(args.mode)
    executions = tuple(_run(command) for command in _COMMANDS[mode])
    passed = all(execution["returncode"] == 0 for execution in executions)
    artifact = Path(os.environ.get("WF_HARNESS_ARTIFACT", _DEFAULT_ARTIFACTS[mode]))
    if not artifact.is_absolute():
        artifact = ROOT / artifact
    artifact.parent.mkdir(parents=True, exist_ok=True)
    _ = artifact.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "mode": mode,
                "passed": passed,
                "executions": executions,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    for execution in executions:
        print(str(execution["stdout"]), end="")
        print(str(execution["stderr"]), end="")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
