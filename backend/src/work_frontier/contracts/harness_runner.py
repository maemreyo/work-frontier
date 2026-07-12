"""Execute registry harnesses and emit revision-bound evidence."""

from __future__ import annotations

import json
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from work_frontier.contracts.evidence_record import (
    Artifact,
    EvidenceRecord,
    JsonValue,
    Result,
)
from work_frontier.contracts.evidence_writer import (
    get_git_commit_sha,
    get_git_tree_sha,
    get_tool_version,
    hash_bytes,
    hash_file,
    is_working_tree_clean,
    write_evidence,
    write_text_artifact,
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
    if harness_id == "WF-HAR-STATIC-05":
        return "gitleaks"
    if harness_id.startswith("WF-HAR-STATIC"):
        return "python"
    if harness_id == "WF-HAR-CONTRACT-05":
        return "generate_contracts"
    if harness_id == "WF-HAR-INTEG-01":
        return "migration-smoke"
    if harness_id == "WF-HAR-INTEG-02":
        return "storage-smoke"
    return "python"


def _is_remote_artifact(path: str) -> bool:
    return path.startswith(("s3://", "http://", "https://"))


def run_harness(
    harness_id: str,
    *,
    repo_root: Path | None = None,
    registry_path: Path | None = None,
) -> EvidenceRecord:
    """Run one harness by registry ID and write evidence under .omo/evidence."""
    root = repo_root or Path.cwd()
    registry = load_registry(
        registry_path or (root / "contracts" / "harness-registry.json")
    )
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
    status = "pass" if completed.returncode == 0 else "fail"

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    declared_artifact = str(harness["artifact"])
    results = [
        Result(
            kind="harness_exit",
            passed=completed.returncode == 0,
            detail=f"exit_code={completed.returncode}",
        )
    ]

    property_bag: dict[str, JsonValue] = {
        "registry.harness_id": harness_id,
        "registry.blocks_release": bool(harness.get("blocks_release")),
        "registry.applicability": str(harness.get("applicability", "standard")),
        "registry.status": str(harness.get("status", "specified")),
        "registry.command": command,
        "registry.artifact": declared_artifact,
    }

    artifacts: list[Artifact] = []
    if _is_remote_artifact(declared_artifact):
        artifacts.append(
            Artifact(
                path=declared_artifact,
                hashes={"sha256": hash_bytes(declared_artifact.encode("utf-8"))},
            )
        )
        property_bag["artifact.kind"] = "remote"
    else:
        artifact_file = root / declared_artifact
        if artifact_file.is_file():
            artifacts.append(
                Artifact(
                    path=declared_artifact,
                    hashes={"sha256": hash_file(artifact_file)},
                )
            )
            property_bag["artifact.kind"] = "local-file"
        else:
            console_rel = f".omo/evidence/static/{harness_id}.console.log"
            console_content = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}\n"
            console_artifact = write_text_artifact(
                content=console_content,
                relative_path=console_rel,
                repo_root=root,
            )
            artifacts.append(console_artifact)
            property_bag["artifact.kind"] = "console-fallback"
            property_bag["artifact.declared_missing"] = declared_artifact
            if status == "pass":
                status = "fail"
                results.append(
                    Result(
                        kind="missing_declared_artifact",
                        passed=False,
                        detail=f"declared artifact missing: {declared_artifact}",
                    )
                )

    evidence_filename = f"{harness_id}.json"
    evidence_relpath = f".omo/evidence/static/{evidence_filename}"
    # The harness's own evidence file is the certification record, not an
    # artifact to re-hash. Drop it from the artifact list so a re-validation
    # round-trip stays stable across runs and the validator does not see an
    # ever-shifting hash on the self-referential file.
    artifacts = [
        artifact for artifact in artifacts if artifact.path != evidence_relpath
    ]

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
        artifacts=artifacts,
        results=results,
        property_bag=property_bag,
        output_filename=f"{harness_id}.json",
        repo_root=root,
        stdout=stdout,
        stderr=stderr,
    )

    return EvidenceRecord.model_validate_json(evidence_path.read_text(encoding="utf-8"))


def validate_evidence_record(
    record: EvidenceRecord,
    *,
    registry: dict[str, Any],
    expected_subject_sha: str | None = None,
    require_blocking_pass: bool = False,
    repo_root: Path | None = None,
) -> list[str]:
    """Return certification failures for one evidence record."""
    failures: list[str] = []
    root = repo_root or Path.cwd()
    try:
        harness = get_harness(registry, record.harness_id)
    except Exception as exc:  # noqa: BLE001 - surface as certification failure
        failures.append(str(exc))
        return failures

    if expected_subject_sha and record.subject_sha != expected_subject_sha:
        failures.append(
            f"{record.harness_id}: subject_sha {record.subject_sha} "
            f"!= {expected_subject_sha}"
        )

    if record.tool.version in {"", "1.0.0", "unknown", "fabricated"}:
        failures.append(f"{record.harness_id}: fabricated or missing tool version")

    if (
        record.invocation.working_directory
        and record.invocation.working_directory.startswith("/")
    ):
        failures.append(f"{record.harness_id}: working_directory must be repo-relative")

    if record.invocation.command != str(harness.get("command", "")):
        failures.append(f"{record.harness_id}: command does not match registry")

    expected_pass = record.invocation.exit_code == 0
    if record.status == "pass" and not expected_pass:
        failures.append(f"{record.harness_id}: status pass with nonzero exit_code")
    if record.status == "fail" and expected_pass and require_blocking_pass:
        failures.append(f"{record.harness_id}: status fail with zero exit_code")

    if record.invocation.end_time < record.invocation.start_time:
        failures.append(f"{record.harness_id}: end_time before start_time")

    bag = record.property_bag or {}
    declared_missing = bag.get("artifact.declared_missing")
    if declared_missing:
        failures.append(
            f"{record.harness_id}: declared artifact missing: {declared_missing}"
        )

    for artifact in record.artifacts:
        digest = None if artifact.hashes is None else artifact.hashes.get("sha256")
        if not digest:
            failures.append(
                f"{record.harness_id}: artifact {artifact.path} missing sha256"
            )
            continue
        if _is_remote_artifact(artifact.path):
            continue
        candidate = root / artifact.path
        if not candidate.is_file():
            failures.append(
                f"{record.harness_id}: artifact path does not exist: {artifact.path}"
            )
            continue
        if hash_file(candidate) != digest:
            failures.append(
                f"{record.harness_id}: artifact {artifact.path} hash mismatch"
            )

    has_registry_id = bool(bag.get("registry.harness_id"))
    if (
        record.stdout_artifact is None or record.stderr_artifact is None
    ) and has_registry_id:
        failures.append(f"{record.harness_id}: missing stdout/stderr artifacts")

    if (
        require_blocking_pass
        and harness.get("blocks_release")
        and record.status != "pass"
    ):
        failures.append(
            f"{record.harness_id}: blocking harness status is {record.status}, not pass"
        )

    if record.status == "not_applicable" and harness.get("blocks_release"):
        failures.append(
            f"{record.harness_id}: blocking harness cannot be not_applicable"
        )

    if record.status == "skip" and harness.get("blocks_release"):
        failures.append(f"{record.harness_id}: blocking harness cannot be skip")

    return failures


def recertify_foundation(
    *,
    repo_root: Path | None = None,
    registry_path: Path | None = None,
    require_clean_tree: bool = True,
) -> dict[str, Any]:
    """Run foundation closure harnesses; write supersession certification.

    When ``require_clean_tree`` is True (the default), the working tree must
    match HEAD and contain no source-of-truth untracked files. This guards
    against the previous failure mode where evidence was written from a
    dirty working tree but only ``git rev-parse HEAD`` was recorded, so the
    supersession report attributed results to a revision that did not
    contain the code that produced them.
    """
    root = repo_root or Path.cwd()
    registry = load_registry(
        registry_path or (root / "contracts" / "harness-registry.json")
    )
    subject_sha = get_git_commit_sha(root)
    closure = foundation_closure(registry)

    failures: list[str] = []
    working_tree_clean = is_working_tree_clean(root)
    if require_clean_tree and not working_tree_clean:
        failures.append(
            "working tree is dirty; cannot certify a revision-bound claim. "
            "Commit, stash, or remove untracked source files and re-run."
        )

    try:
        subject_tree_sha = get_git_tree_sha(root)
    except Exception as exc:  # noqa: BLE001 - surface as certification failure
        subject_tree_sha = None
        failures.append(f"could not compute git tree SHA: {exc}")

    records: list[EvidenceRecord] = []
    if not failures:
        for harness_id in closure:
            harness = get_harness(registry, harness_id)
            if harness.get("status") != "implemented":
                failures.append(f"{harness_id}: not implemented; cannot recertify")
                continue
            record = run_harness(
                harness_id, repo_root=root, registry_path=registry_path
            )
            records.append(record)
            failures.extend(
                validate_evidence_record(
                    record,
                    registry=registry,
                    expected_subject_sha=subject_sha,
                    require_blocking_pass=True,
                    repo_root=root,
                )
            )

    certified = len(failures) == 0 and len(records) == len(closure)
    report = {
        "schema_version": "1.0.0",
        "kind": "foundation_recertification",
        "subject_sha": subject_sha,
        "subject_tree_sha": subject_tree_sha,
        "working_tree_clean": working_tree_clean,
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
                "subject_tree_sha": record.subject_tree_sha,
            }
            for record in records
        ],
        "supersedes": (
            "prior local foundation claims for Todos 1-4 and P0 inventory-only reports"
        ),
    }

    out_dir = root / ".omo" / "evidence" / "task-5-full-product-implementation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "foundation-recertification.json"
    _ = out_path.write_text(f"{json.dumps(report, indent=2)}\n", encoding="utf-8")

    if not certified:
        raise CertificationError(
            "foundation recertification failed:\n" + "\n".join(failures)
        )
    return report


def parse_command_preview(command: str) -> list[str]:
    """Expose shlex split for tests without executing."""
    return shlex.split(command)
