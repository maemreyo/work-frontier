"""Execute registry harnesses and emit revision-bound evidence."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from work_frontier.contracts.evidence_record import (
    Artifact,
    ArtifactHashes,
    EvidenceRecord,
    JsonValue,
    Result,
)
from work_frontier.contracts.evidence_writer import (
    generate_run_id,
    get_git_commit_sha,
    get_git_tree_sha,
    get_tool_version,
    hash_file,
    is_working_tree_clean,
    write_evidence,
)
from work_frontier.contracts.harness_registry import (
    foundation_closure,
    get_harness,
    get_prerequisites,
    load_registry,
)


class CertificationError(ValueError):
    """Raised when evidence cannot certify a subject revision."""


# Minimum path parts for artifacts/<harness_id>/<filename>
_ARTIFACT_MIN_PARTS = 3


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


def run_harness(  # noqa: PLR0915 - harness lifecycle spans pre/post validation
    harness_id: str,
    *,
    repo_root: Path | None = None,
    registry_path: Path | None = None,
    evidence_root: Path | None = None,
    run_id: str | None = None,
) -> EvidenceRecord:
    """Run one harness by registry ID and write evidence under *evidence_root*.

    When *run_id* is provided, all evidence records produced by this
    harness share the same outer run identifier, binding them to a single
    certification run.  When *None*, a new run identifier is generated.
    """
    root = repo_root or Path.cwd()
    registry = load_registry(
        registry_path or (root / "contracts" / "harness-registry.json")
    )
    harness = get_harness(registry, harness_id)
    command = str(harness["command"])
    tool_name = tool_name_for_harness(harness_id)
    tool_version = get_tool_version(tool_name)

    # Resolve run_id early so it is consistently used for both the
    # evidence-root directory path and the evidence record.  When the
    # caller provides neither run_id nor evidence_root, the same
    # generated ID drives the directory name AND the record field,
    # preventing record.run_id from differing from the directory name.
    resolved_run_id = run_id or generate_run_id()

    if evidence_root is None:
        # Generate a unique run-scoped evidence root for standalone
        # invocations so concurrent calls do not collide on the same
        # global directory.
        evidence_root = root / ".omo" / "evidence" / "runs" / resolved_run_id
    evidence_root.mkdir(parents=True, exist_ok=True)

    # Resolve declared artifact to a run-scoped path so that concurrent
    # recertifications do not collide on the same global file.  The
    # artifact is written under evidence_root/artifacts/<harness_id>/.
    declared_artifact = str(harness["artifact"])
    artifact_mode = harness.get("artifact_mode", "declared_file")
    run_artifact_dir = evidence_root / "artifacts" / harness_id
    run_artifact_path = run_artifact_dir / Path(declared_artifact).name

    # Pre-harness: delete stale artifact from the run-scoped location
    # so a previous run's leftover cannot fabricate a fresh pass.
    if artifact_mode == "declared_file" and not _is_remote_artifact(declared_artifact):
        run_artifact_path.unlink(missing_ok=True)

    start_time = datetime.now(UTC)
    harness_env = {
        **os.environ,
        "WF_EVIDENCE_ROOT": str(evidence_root),
    }
    if artifact_mode == "declared_file" and not _is_remote_artifact(declared_artifact):
        run_artifact_dir.mkdir(parents=True, exist_ok=True)
        harness_env["WF_HARNESS_ARTIFACT"] = str(run_artifact_path)
    completed = subprocess.run(
        command,
        shell=True,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=harness_env,
    )
    end_time = datetime.now(UTC)

    status: Literal["pass", "fail", "skip", "not_applicable"]
    status = "pass" if completed.returncode == 0 else "fail"

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
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
        "registry.declared_artifact": declared_artifact,
    }

    artifacts: list[Artifact] = []
    evidence_filename = f"{harness_id}.json"
    if artifact_mode == "runner_evidence":
        property_bag["artifact.kind"] = "runner_evidence"
        # The evidence file itself IS the artifact. Store the actual
        # run-scoped path rather than the static registry path so
        # downstream consumers can locate it.
        ev_rel = str((evidence_root / evidence_filename).relative_to(root))
        property_bag["artifact.resolved_path"] = ev_rel
        property_bag["artifact.runner_evidence_path"] = ev_rel
    else:
        # Only the run-scoped path is authoritative.  The legacy global
        # fallback (root / declared_artifact) is eliminated to prevent
        # stale artifact fabrication: a harness with command=true must
        # not certify a pre-existing global artifact.
        artifact_source = run_artifact_path
        if artifact_source.is_file():
            try:
                artifact_rel = str(run_artifact_path.relative_to(root))
            except ValueError:
                artifact_rel = str(run_artifact_path)
            artifacts.append(
                Artifact(
                    path=artifact_rel,
                    hashes=ArtifactHashes(sha256=hash_file(run_artifact_path)),
                )
            )
            property_bag["artifact.kind"] = "local-file"
            property_bag["artifact.resolved_path"] = artifact_rel
        else:
            evidence_root_rel = evidence_root.relative_to(root)
            console_rel = f"{evidence_root_rel}/{harness_id}.console.log"
            console_content = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}\n"
            from work_frontier.contracts.evidence_writer import write_text_artifact

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
    # The harness's own evidence file is the certification record, not an
    # artifact to re-hash. Drop it from the artifact list so a re-validation
    # round-trip stays stable across runs and the validator does not see an
    # ever-shifting hash on the self-referential file.
    evidence_relpath = str(evidence_root / evidence_filename)
    try:
        evidence_rel = str((evidence_root / evidence_filename).relative_to(root))
    except ValueError:
        evidence_rel = evidence_relpath
    artifacts = [artifact for artifact in artifacts if artifact.path != evidence_rel]

    _ = write_evidence(
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
        output_filename=evidence_filename,
        repo_root=root,
        stdout=stdout,
        stderr=stderr,
        evidence_root=evidence_root,
        run_id=resolved_run_id,
        applicability=cast(
            "Literal['standard', 'large', 'tenant']",
            str(harness.get("applicability", "standard")),
        ),
    )

    evidence_path = evidence_root / evidence_filename
    return EvidenceRecord.model_validate_json(evidence_path.read_text(encoding="utf-8"))


def _validate_artifact(
    artifact: Artifact,
    root: Path,
    harness_id: str,
    *,
    label: str = "artifact",
) -> list[str]:
    """Return certification failures for one artifact (regular or stdout/stderr)."""
    failures: list[str] = []
    digest = artifact.hashes.sha256
    if not digest:
        failures.append(
            f"{harness_id}: {label} artifact {artifact.path} missing sha256"
        )
        return failures
    if _is_remote_artifact(artifact.path):
        failures.append(
            f"{harness_id}: {label} artifact {artifact.path} is remote and "
            "cannot be locally content-verified"
        )
        return failures

    candidate = (root / artifact.path).resolve()
    # Defense-in-depth: ensure the resolved path stays within the repo root.
    if not candidate.is_relative_to(root.resolve()):
        failures.append(
            f"{harness_id}: {label} artifact path escapes repo root: {artifact.path}"
        )
        return failures

    if not candidate.is_file():
        failures.append(
            f"{harness_id}: {label} artifact path does not exist: {artifact.path}"
        )
        return failures
    if hash_file(candidate) != digest:
        failures.append(f"{harness_id}: {label} artifact {artifact.path} hash mismatch")
    return failures


def validate_evidence_record(
    record: EvidenceRecord,
    *,
    registry: dict[str, Any],
    expected_subject_sha: str | None = None,
    expected_subject_tree_sha: str | None = None,
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

    if (
        expected_subject_tree_sha
        and record.subject_tree_sha != expected_subject_tree_sha
    ):
        failures.append(
            f"{record.harness_id}: subject_tree_sha {record.subject_tree_sha} "
            f"!= {expected_subject_tree_sha}"
        )

    if expected_subject_sha and record.tool.commit_sha != expected_subject_sha:
        failures.append(
            f"{record.harness_id}: tool.commit_sha {record.tool.commit_sha} "
            f"!= expected_subject_sha {expected_subject_sha}"
        )

    if record.tool.version in {"", "1.0.0", "unknown", "fabricated"}:
        failures.append(f"{record.harness_id}: fabricated or missing tool version")

    if record.invocation.working_directory.startswith("/"):
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
        failures.extend(
            _validate_artifact(artifact, root, record.harness_id, label="artifact")
        )

    # Validate stdout/stderr artifacts (hash integrity and existence).
    for label, art in (
        ("stdout", record.stdout_artifact),
        ("stderr", record.stderr_artifact),
    ):
        failures.extend(_validate_artifact(art, root, record.harness_id, label=label))

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

    # Applicability must match the registry declaration exactly.
    # A record that claims "standard" for a registry-declared "tenant"
    # harness is a contradiction that could bypass scope gating.
    registry_applicability = str(harness.get("applicability", "standard"))
    if record.applicability != registry_applicability:
        failures.append(
            f"{record.harness_id}: record.applicability={record.applicability!r} "
            f"does not match registry.applicability={registry_applicability!r}"
        )

    return failures


def recertify_foundation(  # noqa: PLR0915 - certification lifecycle spans 8 harnesses + post-closure
    *,
    repo_root: Path | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Run foundation closure harnesses; write supersession certification.

    The working tree must match HEAD and contain no source-of-truth
    untracked files. This guards against the previous failure mode where
    evidence was written from a dirty working tree but only
    ``git rev-parse HEAD`` was recorded, so the supersession report
    attributed results to a revision that did not contain the code that
    produced them.
    """
    root = repo_root or Path.cwd()
    registry = load_registry(
        registry_path or (root / "contracts" / "harness-registry.json")
    )
    subject_sha = get_git_commit_sha(root)
    closure = foundation_closure(registry)

    failures: list[str] = []
    working_tree_clean = is_working_tree_clean(root)
    if not working_tree_clean:
        failures.append(
            "working tree is dirty; cannot certify a revision-bound claim. "
            "Commit, stash, or remove untracked source files and re-run."
        )

    subject_tree_sha = get_git_tree_sha(root)
    run_id = generate_run_id()
    # Run-scoped evidence directory prevents stale-artifact fabrication:
    # each recertification starts with a clean directory.
    evidence_root = root / ".omo" / "evidence" / "runs" / subject_sha[:12] / run_id

    records: list[EvidenceRecord] = []
    initial_record_hashes: dict[str, str] = {}
    # Track which harnesses from the closure have passed evidence in this run.
    satisfied_prereqs: set[str] = set()
    if not failures:
        for harness_id in closure:
            harness = get_harness(registry, harness_id)
            if harness.get("status") != "implemented":
                failures.append(f"{harness_id}: not implemented; cannot recertify")
                continue

            # Check prerequisites before running.
            prereqs = get_prerequisites(registry, harness_id)
            unsatisfied = [p for p in prereqs if p not in satisfied_prereqs]
            if unsatisfied:
                failures.append(
                    f"{harness_id}: prerequisite(s) not satisfied "
                    f"in this run: {unsatisfied}"
                )
                continue

            record = run_harness(
                harness_id,
                repo_root=root,
                registry_path=registry_path,
                evidence_root=evidence_root,
                run_id=run_id,
            )
            records.append(record)
            failures.extend(
                validate_evidence_record(
                    record,
                    registry=registry,
                    expected_subject_sha=subject_sha,
                    expected_subject_tree_sha=subject_tree_sha,
                    require_blocking_pass=True,
                    repo_root=root,
                )
            )
            # Mark this harness as satisfied if it passed.
            if record.status == "pass":
                satisfied_prereqs.add(harness_id)

            # Capture the initial record hash immediately after writing, before
            # any subsequent harness can tamper with it.
            record_path = evidence_root / f"{harness_id}.json"
            if record_path.is_file():
                initial_record_hashes[harness_id] = hash_file(record_path)

    # TOCTOU guard: recheck commit identity, tree identity, and tree
    # cleanliness after full harness closure.  Harness execution must not
    # have mutated the source tree or changed the checked-out revision.
    if not failures:
        if not is_working_tree_clean(root):
            failures.append(
                "TOCTOU: working tree became dirty during harness execution"
            )
        try:
            post_commit_sha = get_git_commit_sha(root)
        except Exception:  # noqa: BLE001 - surface as certification failure
            failures.append("TOCTOU: could not compute commit SHA after closure")
            post_commit_sha = None
        if post_commit_sha is not None and post_commit_sha != subject_sha:
            failures.append(
                f"TOCTOU: commit SHA changed during harness execution "
                f"({subject_sha} -> {post_commit_sha})"
            )
        try:
            post_tree_sha = get_git_tree_sha(root)
        except Exception:  # noqa: BLE001 - surface as certification failure
            failures.append("TOCTOU: could not compute git tree SHA after closure")
            post_tree_sha = None
        if post_tree_sha is not None and post_tree_sha != subject_tree_sha:
            failures.append(
                f"TOCTOU: tree SHA changed during harness execution "
                f"({subject_tree_sha} -> {post_tree_sha})"
            )

    # Post-closure full revalidation: reload EVERY record from disk and
    # verify that declared artifacts still exist with matching hashes.
    # This catches cross-harness tampering where harness B overwrites or
    # deletes harness A's evidence record file after A was validated.
    #
    # Previously this loop validated the in-memory EvidenceRecord objects
    # rather than reloaded-from-disk records, meaning a tampered or deleted
    # evidence file would go undetected.
    disk_records: list[EvidenceRecord] = []
    if not failures:
        for expected_id in closure:
            record_path = evidence_root / f"{expected_id}.json"
            if not record_path.is_file():
                failures.append(
                    f"{expected_id}: evidence record file missing from disk"
                )
                continue

            # Tamper detection: check if the file hash changed since creation.
            expected_initial = initial_record_hashes.get(expected_id)
            current_hash = hash_file(record_path) if record_path.is_file() else ""
            if expected_initial is not None and current_hash != expected_initial:
                failures.append(
                    f"{expected_id}: evidence record content changed after "
                    f"creation (initial hash={expected_initial[:16]}..., "
                    f"current hash={current_hash[:16]}...)"
                )
                continue

            try:
                record = EvidenceRecord.model_validate_json(
                    record_path.read_text(encoding="utf-8")
                )
            except Exception as exc:  # noqa: BLE001 - surface as certification failure
                failures.append(
                    f"{expected_id}: evidence record file is invalid JSON: {exc}"
                )
                continue
            if record.harness_id != expected_id:
                failures.append(
                    f"{expected_id}: file contains record for {record.harness_id}"
                )
                continue
            if record.run_id != run_id:
                failures.append(
                    f"{expected_id}: record run_id {record.run_id!r} does not match "
                    f"certification run_id {run_id!r}"
                )
                continue
            disk_records.append(record)
            failures.extend(
                validate_evidence_record(
                    record,
                    registry=registry,
                    expected_subject_sha=subject_sha,
                    expected_subject_tree_sha=subject_tree_sha,
                    require_blocking_pass=True,
                    repo_root=root,
                )
            )

    # Build evidence manifest with SHA-256 of every file under the
    # evidence root (recursive).  This proves which exact record content
    # was certified and enables downstream tamper detection.  The manifest
    # covers what is actually on disk so that an extra, stale, or nested
    # evidence file cannot sneak in unnoticed.
    #
    # Expected files are:
    #   - <harness_id>.json          — evidence record for each closure member
    #   - <harness_id>.stdout.txt    — stdout sidecar
    #   - <harness_id>.stderr.txt    — stderr sidecar
    #   - artifacts/<harness_id>/*   — declared artifact copies
    # Any file outside these patterns is rejected as unexpected.
    evidence_manifest: dict[str, str] = {}
    disk_json_stems: set[str] = set()
    unexpected_files: list[str] = []
    for path in sorted(evidence_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(evidence_root)
        rel_str = str(rel)

        # Classify the file.
        is_expected = False
        # Evidence JSON for a closure member
        if rel.parent == Path() and rel.suffix == ".json":
            stem = path.stem
            if stem in closure:
                is_expected = True
                disk_json_stems.add(stem)
                evidence_manifest[rel_str] = hash_file(path)
                continue
        # Stdout/stderr sidecar for a closure member
        if rel.parent == Path() and rel_str.endswith((".stdout.txt", ".stderr.txt")):
            base_stem = path.stem.rsplit(".", 2)[0]  # removes .stdout or .stderr
            if base_stem in closure:
                is_expected = True
                evidence_manifest[rel_str] = hash_file(path)
                continue
        # Declared artifact under artifacts/<harness_id>/
        if rel.parts[:1] == ("artifacts",) and len(rel.parts) >= _ARTIFACT_MIN_PARTS:
            artifact_harness_id = rel.parts[1]
            if artifact_harness_id in closure:
                is_expected = True
                evidence_manifest[rel_str] = hash_file(path)
                continue

        if not is_expected:
            unexpected_files.append(rel_str)
            evidence_manifest[rel_str] = hash_file(path)

    # Reject both missing records AND extra/unexpected files on disk.
    if not failures:
        missing = set(closure) - disk_json_stems
        if missing:
            failures.append(f"evidence manifest missing records for: {sorted(missing)}")
        if unexpected_files:
            failures.append(
                f"evidence disk has unexpected files: {sorted(unexpected_files)}"
            )
    if not failures:
        disk_ids = [record.harness_id for record in disk_records]
        if disk_ids != closure:
            failures.append(
                f"evidence record IDs {disk_ids} do not match closure {closure}"
            )
        if len(disk_ids) != len(set(disk_ids)):
            failures.append("duplicate harness IDs in disk records")

    # For runner_evidence mode harnesses, include the evidence file path
    # to prove the record was actually written.
    property_bag_manifest: dict[str, JsonValue] = {
        "evidence_root": str(evidence_root.relative_to(root))
        if evidence_root.is_relative_to(root)
        else str(evidence_root),
    }

    certified = len(failures) == 0 and len(disk_records) == len(closure)
    report = {
        "schema_version": "1.0.0",
        "kind": "foundation_recertification",
        "subject_sha": subject_sha,
        "subject_tree_sha": subject_tree_sha,
        "working_tree_clean": working_tree_clean,
        "closure": closure,
        "run_id": run_id,
        "evidence_root": str(evidence_root.relative_to(root))
        if evidence_root.is_relative_to(root)
        else str(evidence_root),
        "evidence_manifest": evidence_manifest,
        "property_bag": property_bag_manifest,
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
            for record in (disk_records or records)
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
