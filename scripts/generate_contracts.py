"""Generate deterministic JSON Schema and Zod artifacts from Pydantic contracts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from work_frontier.contracts import DecisionRecordContract

CHECK_ARGUMENT: Final = "--check"
CONTRACT_DIRECTORY: Final = Path("contracts/generated")
JSON_SCHEMA_PATH: Final = CONTRACT_DIRECTORY / "decision-record.schema.json"
ZOD_PATH: Final = Path("frontend/src/contracts/decision-record.generated.ts")


def json_schema() -> str:
    """Return canonical serialized Pydantic JSON Schema."""
    schema = DecisionRecordContract.model_json_schema()
    return f"{json.dumps(schema, indent=2, sort_keys=True)}\n"


def zod_source() -> str:
    """Generate Zod source by calling x-to-zod script on Pydantic-derived schema."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as schema_tmp:
        _ = schema_tmp.write(json_schema())
        schema_path = Path(schema_tmp.name)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ts", delete=False) as zod_tmp:
        zod_path = Path(zod_tmp.name)

    try:
        _ = subprocess.run(
            [
                "node",
                "scripts/generate_zod_from_schema.mjs",
                str(schema_path),
                str(zod_path),
                "DecisionRecordSchema",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        content = zod_path.read_text(encoding="utf-8")
        return content.replace(str(schema_path), str(JSON_SCHEMA_PATH))
    finally:
        _ = schema_path.unlink(missing_ok=True)
        _ = zod_path.unlink(missing_ok=True)


def expected_artifacts() -> tuple[tuple[Path, str], ...]:
    """Return every generated artifact and its expected deterministic content."""
    return ((JSON_SCHEMA_PATH, json_schema()), (ZOD_PATH, zod_source()))


def artifacts_are_current() -> bool:
    """Return whether checked-in artifacts match the canonical contract model."""
    return all(
        path.exists() and path.read_text(encoding="utf-8") == content
        for path, content in expected_artifacts()
    )


def write_artifacts() -> None:
    """Write deterministic generated contract artifacts."""
    for path, content in expected_artifacts():
        _ = path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(content, encoding="utf-8")


def main(arguments: list[str]) -> int:
    """Generate artifacts or report whether checked-in artifacts drifted."""
    from work_frontier.contracts.evidence_record import Artifact, Result
    from work_frontier.contracts.evidence_writer import write_evidence

    start_time = datetime.now(UTC)
    repo_root = Path(__file__).parent.parent

    check_mode = len(arguments) == 1 and arguments[0] == CHECK_ARGUMENT

    if not check_mode and len(arguments) == 0:
        write_artifacts()
        exit_code = 0
        status = "pass"
        results = [
            Result(
                kind="json_schema_generated", passed=True, detail=str(JSON_SCHEMA_PATH)
            ),
            Result(kind="zod_generated", passed=True, detail=str(ZOD_PATH)),
        ]
    elif check_mode:
        is_current = artifacts_are_current()
        exit_code = 0 if is_current else 1
        status = "pass" if is_current else "fail"
        results = []
        for path, content in expected_artifacts():
            exists = path.exists()
            matches = exists and path.read_text(encoding="utf-8") == content
            if matches:
                label = "current"
            elif exists:
                label = "drift detected"
            else:
                label = "missing"
            results.append(
                Result(
                    kind="artifact_check",
                    passed=matches,
                    detail=f"{path}: {label}",
                )
            )
    else:
        print("usage: generate_contracts.py [--check]", file=sys.stderr)
        exit_code = 2
        status = "skip"
        results = []

    end_time = datetime.now(UTC)

    if exit_code != 2:
        artifacts = [Artifact(path=str(path)) for path, _ in expected_artifacts()]

        _ = write_evidence(
            harness_id="WF-HAR-STATIC-02",
            status=status,
            command=f"python {' '.join(['generate_contracts.py', *arguments])}",
            exit_code=exit_code,
            working_directory=str(repo_root),
            start_time=start_time,
            end_time=end_time,
            tool_name="generate_contracts",
            artifacts=artifacts,
            results=results,
            property_bag={
                "generate_contracts": {
                    "mode": "check" if check_mode else "generate",
                    "artifacts_current": exit_code == 0 if check_mode else None,
                }
            },
            output_filename="contracts.json",
            repo_root=repo_root,
        )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
