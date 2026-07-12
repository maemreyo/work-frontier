"""Execute registry harnesses and emit revision-bound evidence."""

from __future__ import annotations

import json
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from work_frontier.contracts.evidence_record import Artifact, EvidenceRecord, Result
from work_frontier.contracts.evidence_writer import (
    get_git_commit_sha,
    get_tool_version,
    hash_bytes,
    write_evidence,
)
from work_frontier.contracts.harness_registry import (
    foundation_closure,
    get_harness,
    load_registry,
)


class CertificationError(ValueError):
    """Raised when evidence cannot certify a subject revision."""


def tool_name_for_harness(harness_id: str) -> str:
    if harness_id.startswith("WF-HAR-PREFLIGHT"):
        return "preflight"
    if harness_id == "WF-HAR-STATIC-02":
        return "check_import_boundaries"
    if harness_id.startswith("WF-HAR-STATIC"):
        return "python"
    if harness_id == "WF-HAR-CONTRACT-05":
        return "generate_contracts"
    if harness_id == "WF-HAR-INTEG-01":
        return "migration-smoke"
    if harness_id == "WF-HAR-INTEG-02":
        return "storage-smoke"
    return "python"


def run_harness(
    harness_id: str,
    *,
    repo_root: Path | None = None,
    registry_path: Path | None = None,
) -> EvidenceRecord:
    """Run one harness by registry ID and write evidence under .omo/evidence."""
    root = repo_root or Path.cwd()
    registry = load_registry(registry_path or (root / "contracts" / "harness-registry.json"))
    harness = get_harness(registry, harness_id)
    command = str(harness["command"])
    tool_name = tool_name_for_harness(harness_id)
    tool_version = get_tool_version(tool_name)

    start_time = datetime.now(UTC)
    completed = subprocess.run(
        command,
        shell=True,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    end_time = datetime.now(UTC)

    status: Literal["pass", "fail", "skip", "not_applicable"]
    if completed.returncode == 0:
        status = "pass"
    else:
        status = "fail"

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    artifact_path = str(harness.get("artifact") or f".omo/evidence/static/{harness_id}.json")
    results = [
        Result(
            kind="harness_exit",
            passed=completed.returncode == 0,
            detail=f"exit_code={completed.returncode}",
        )
    ]

    property_bag: dict[str, object] = {
        "registry.harness_id": harness_id,
        "registry.blocks_release": bool(harness.get("blocks_release")),
        "registry.applicability": str(harness.get("applicability", "standard")),
        "registry.status": str(harness.get("status", "specified")),
    }

    evidence_path = write_evidence(
        harness_id=harness_id,
        status=status,
        command=command,
        exit_code=completed.returncode,
        working_directory=str(root),
        start_time=start_time,
        end_time=end_time,
        tool_name=tool_name,
        tool_version=tool_version,
        artifacts=[
            Artifact(
                path=artifact_path,
                hashes={"sha256": hash_bytes((stdout + stderr).encode("utf-8"))},
            )
        ],
        results=results,
        property_bag=property_bag,  # type: ignore[arg-type]
        output_filename=f"{harness_id}.json",
        repo_root=root,
        stdout=stdout,
        stderr=stderr,
    )

    record = EvidenceRecord.model_validate_json(evidence_path.read_text(encoding="utf-8"))
    return record


def validate_evidence_record(
    record: EvidenceRecord,
    *,
    registry: dict[str, Any],
    expected_subject_sha: str | None = None,
    require_blocking_pass: bool = False,
) -> list[str]:
    """Return certification failures for one evidence record."""
    failures: list[str] = []
    try:
        harness = get_harness(registry, record.harness_id)
    except Exception as exc:  # noqa: BLE001 - surface as certification failure
        failures.append(str(exc))
        return failures

    if expected_subject_sha and record.subject_sha != expected_subject_sha:
        failures.append(
            f"{record.harness_id}: subject_sha {record.subject_sha} != {expected_subject_sha}"
        )

    if record.tool.version in {"", "1.0.0", "unknown", "fabricated"}:
        failures.append(f"{record.harness_id}: fabricated or missing tool version")

    if record.invocation.working_directory and record.invocation.working_directory.startswith(
        "/"
    ):
        failures.append(f"{record.harness_id}: working_directory must be repo-relative")

    for artifact in record.artifacts:
        if artifact.hashes is None or not artifact.hashes.get("sha256"):
            failures.append(f"{record.harness_id}: artifact {artifact.path} missing sha256")

    if record.stdout_artifact is None or record.stderr_artifact is None:
        # Runner-produced records must include logs; legacy records may omit them.
        if record.property_bag and record.property_bag.get("registry.harness_id"):
            failures.append(f"{record.harness_id}: missing stdout/stderr artifacts")

    if require_blocking_pass and harness.get("blocks_release") and record.status != "pass":
        failures.append(
            f"{record.harness_id}: blocking harness status is {record.status}, not pass"
        )

    if record.status == "not_applicable" and harness.get("blocks_release"):
        failures.append(f"{record.harness_id}: blocking harness cannot be not_applicable")

    if record.status == "skip" and harness.get("blocks_release"):
        failures.append(f"{record.harness_id}: blocking harness cannot be skip")

    return failures


def recertify_foundation(
    *,
    repo_root: Path | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Run foundation closure harnesses and write a supersession certification record."""
    root = repo_root or Path.cwd()
    registry = load_registry(registry_path or (root / "contracts" / "harness-registry.json"))
    subject_sha = get_git_commit_sha(root)
    closure = foundation_closure(registry)

    records: list[EvidenceRecord] = []
    failures: list[str] = []
    for harness_id in closure:
        harness = get_harness(registry, harness_id)
        if harness.get("status") != "implemented":
            failures.append(f"{harness_id}: not implemented; cannot recertify")
            continue
        record = run_harness(harness_id, repo_root=root, registry_path=registry_path)
        records.append(record)
        failures.extend(
            validate_evidence_record(
                record,
                registry=registry,
                expected_subject_sha=subject_sha,
                require_blocking_pass=True,
            )
        )

    certified = len(failures) == 0 and len(records) == len(closure)
    report = {
        "schema_version": "1.0.0",
        "kind": "foundation_recertification",
        "subject_sha": subject_sha,
        "closure": closure,
        "certified": certified,
        "failures": failures,
        "records": [
            {
                "harness_id": record.harness_id,
                "status": record.status,
                "run_id": record.run_id,
                "tool_version": record.tool.version,
                "exit_code": record.invocation.exit_code,
            }
            for record in records
        ],
        "supersedes": "prior local foundation claims for Todos 1-4 and P0 inventory-only reports",
    }

    out_dir = root / ".omo" / "evidence" / "task-5-full-product-implementation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "foundation-recertification.json"
    out_path.write_text(f"{json.dumps(report, indent=2)}\n", encoding="utf-8")

    if not certified:
        raise CertificationError(
            "foundation recertification failed:\n" + "\n".join(failures)
        )
    return report


def parse_command_preview(command: str) -> list[str]:
    """Expose shlex split for tests without executing."""
    return shlex.split(command)
