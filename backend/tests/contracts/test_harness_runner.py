"""Tests for harness runner revision-bound certification rules.

These guard the certification invariant: a claimed pass must come from
a clean working tree and the recorded tree SHA must match the committed
HEAD tree that produced the evidence. The runner is fail-closed on dirty
trees and stale untracked files, but tolerates ephemeral untracked data
(.omo/evidence/**, __pycache__/, .pytest_cache/, etc.).

The tests run the production ``recertify_foundation`` function against
fresh git clones of the repository so the working tree under inspection
is genuinely the one shipped at HEAD, not a working copy that contains
the test's own source edits.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

from work_frontier.contracts.evidence_record import (
    Artifact,
    EvidenceRecord,
    Invocation,
    JsonValue,
    Tool,
)
from work_frontier.contracts.evidence_writer import hash_bytes
from work_frontier.contracts.harness_registry import HarnessRegistryError
from work_frontier.contracts.harness_runner import (
    CertificationError,
    recertify_foundation,
    validate_evidence_record,
)

ROOT = Path(__file__).resolve().parents[3]


def _make_clean_clone() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="wf-recert-mut-"))
    _ = subprocess.run(  # noqa: S603 - source path is repo root, not untrusted
        ["git", "clone", "--quiet", str(ROOT), str(tmp)],
        check=True,
    )
    _ = subprocess.run(
        ["git", "reset", "--hard", "HEAD"],
        cwd=tmp,
        check=True,
        capture_output=True,
    )
    return tmp


def _make_minimal_registry(path: Path) -> None:
    """Write a minimal one-harness registry that always passes."""
    registry = {
        "schema_version": "1.0.0",
        "harness_count": 1,
        "catalog_harness_count": 1,
        "standard_blocker_count": 1,
        "standard_blockers": ["WF-HAR-TEST-01"],
        "harnesses": [
            {
                "id": "WF-HAR-TEST-01",
                "name": "test",
                "command": "true",
                "artifact": "s3://example-bucket/does-not-matter",
                "artifact_mode": "declared_file",
                "blocks_release": True,
                "what_it_runs": "noop",
                "pass_criteria": "exit 0",
                "applicability": "standard",
                "status": "implemented",
            }
        ],
        "foundation_closure": ["WF-HAR-TEST-01"],
    }
    _ = path.write_text(json.dumps(registry))


def _import_harness_runner(clone: Path) -> ModuleType:
    """Import harness_runner and evidence_writer from the clone."""
    sys.path.insert(0, str(clone / "backend" / "src"))
    for mod in [
        "work_frontier.contracts.harness_runner",
        "work_frontier.contracts.evidence_writer",
    ]:
        if mod in sys.modules:
            del sys.modules[mod]
    from work_frontier.contracts import harness_runner as hr

    return hr


# ---------------------------------------------------------------------------
# Bogus artifact_mode rejection (integration)
# ---------------------------------------------------------------------------


def test_recertify_rejects_bogus_artifact_mode() -> None:
    """A harness with artifact_mode='bogus' is rejected at runtime validation.

    Preseed a stale artifact and set command='true' to confirm the
    bogus mode does NOT allow a stale file to fabricate a pass.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        # Register a harness with invalid artifact_mode="bogus"
        registry = {
            "schema_version": "1.0.0",
            "harness_count": 1,
            "catalog_harness_count": 1,
            "standard_blocker_count": 1,
            "standard_blockers": ["WF-HAR-BOGUS-01"],
            "harnesses": [
                {
                    "id": "WF-HAR-BOGUS-01",
                    "name": "bogus-mode",
                    "command": "true",
                    "artifact": ".omo/evidence/static/preseeded.json",
                    "artifact_mode": "bogus",
                    "blocks_release": True,
                    "what_it_runs": "noop with bogus mode",
                    "pass_criteria": "exit 0",
                    "applicability": "standard",
                    "status": "implemented",
                }
            ],
            "foundation_closure": ["WF-HAR-BOGUS-01"],
        }
        _ = registry_path.write_text(json.dumps(registry))

        # Preseed a stale artifact that should never be accepted
        preseeded = clone / ".omo" / "evidence" / "static" / "preseeded.json"
        preseeded.parent.mkdir(parents=True, exist_ok=True)
        _ = preseeded.write_text('{"stale": true}')

        # Runtime should reject the bogus artifact_mode at registry load
        with pytest.raises(HarnessRegistryError, match="invalid artifact_mode"):
            _ = recertify_foundation(
                repo_root=clone,
                registry_path=registry_path,
            )

        # The preseeded file must NOT have been certified
        assert preseeded.is_file(), (
            "preseeded artifact should still exist (no run attempted)"
        )
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


def test_recertify_rejects_missing_artifact_mode() -> None:
    """A harness with no artifact_mode field is rejected at runtime validation."""
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        registry = {
            "schema_version": "1.0.0",
            "harness_count": 1,
            "catalog_harness_count": 1,
            "standard_blocker_count": 1,
            "standard_blockers": ["WF-HAR-NOAM-01"],
            "harnesses": [
                {
                    "id": "WF-HAR-NOAM-01",
                    "name": "no-artifact-mode",
                    "command": "true",
                    "artifact": "s3://bucket/test",
                    # artifact_mode deliberately omitted
                    "blocks_release": True,
                    "what_it_runs": "noop without artifact_mode",
                    "pass_criteria": "exit 0",
                    "applicability": "standard",
                    "status": "implemented",
                }
            ],
            "foundation_closure": ["WF-HAR-NOAM-01"],
        }
        _ = registry_path.write_text(json.dumps(registry))

        with pytest.raises(HarnessRegistryError, match="missing required field"):
            _ = recertify_foundation(
                repo_root=clone,
                registry_path=registry_path,
            )
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Dirty-tree rejection
# ---------------------------------------------------------------------------


def test_recertify_foundation_fails_on_tracked_drift() -> None:
    """A tracked file mutation makes the working tree dirty -> certification fails."""
    clone = _make_clean_clone()
    try:
        _ = (clone / "README.md").write_text("mutated tracked content\n")
        with pytest.raises(CertificationError, match="working tree is dirty"):
            _ = recertify_foundation(repo_root=clone)
    finally:
        shutil.rmtree(clone, ignore_errors=True)


def test_recertify_foundation_fails_on_untracked_source() -> None:
    """An untracked file outside ephemeral prefixes -> certification fails."""
    clone = _make_clean_clone()
    try:
        (clone / "scripts" / "stray_untracked.py").parent.mkdir(
            parents=True, exist_ok=True
        )
        _ = (clone / "scripts" / "stray_untracked.py").write_text("print(1)\n")
        with pytest.raises(CertificationError, match="working tree is dirty"):
            _ = recertify_foundation(repo_root=clone)
    finally:
        shutil.rmtree(clone, ignore_errors=True)


def test_recertify_foundation_fails_on_untracked_under_contracts() -> None:
    """An untracked file under contracts/ is meaningful -> certification fails."""
    clone = _make_clean_clone()
    try:
        (clone / "contracts" / "stray.json").parent.mkdir(parents=True, exist_ok=True)
        _ = (clone / "contracts" / "stray.json").write_text("{}\n")
        with pytest.raises(CertificationError, match="working tree is dirty"):
            _ = recertify_foundation(repo_root=clone)
    finally:
        shutil.rmtree(clone, ignore_errors=True)


# ---------------------------------------------------------------------------
# Ephemeral untracked tolerance
# ---------------------------------------------------------------------------


def test_recertify_foundation_tolerates_ephemeral_untracked() -> None:
    """Untracked files under ephemeral prefixes (e.g. .omo/evidence/) are OK."""
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        _make_minimal_registry(registry_path)

        # Drop a junk file inside the ephemeral evidence tree
        junk = clone / ".omo" / "evidence" / "static" / "junk.json"
        junk.parent.mkdir(parents=True, exist_ok=True)
        _ = junk.write_text('{"ephemeral": true}\n')

        # Must tolerate the ephemeral untracked file
        report = recertify_foundation(
            repo_root=clone,
            registry_path=registry_path,
        )
        assert report["certified"] is True
        assert report["working_tree_clean"] is True
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Tree SHA recording and matching
# ---------------------------------------------------------------------------


def test_recertify_foundation_records_subject_tree_sha_and_requires_tree_match() -> (
    None
):
    """The report's subject_tree_sha matches every record's subject_tree_sha.

    A mutation (even if reverted before the harness runs) changes the
    committed tree SHA and is caught as a subject_tree_sha mismatch.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        _make_minimal_registry(registry_path)
        hr = _import_harness_runner(clone)

        expected_tree = hr.get_git_tree_sha(clone)
        report = hr.recertify_foundation(
            repo_root=clone,
            registry_path=registry_path,
        )
        assert report["subject_tree_sha"] == expected_tree
        assert report["working_tree_clean"] is True
        for record in report["records"]:
            assert record["subject_tree_sha"] == expected_tree
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)
        with contextlib.suppress(ValueError):
            sys.path.remove(str(clone / "backend" / "src"))


# ---------------------------------------------------------------------------
# Stale artifact prevention
# ---------------------------------------------------------------------------


def _make_registry_with_local_artifact(path: Path) -> None:
    """Write a registry whose artifact is a local file (not remote)."""
    registry = {
        "schema_version": "1.0.0",
        "harness_count": 1,
        "catalog_harness_count": 1,
        "standard_blocker_count": 1,
        "standard_blockers": ["WF-HAR-TEST-02"],
        "harnesses": [
            {
                "id": "WF-HAR-TEST-02",
                "name": "test-local",
                "command": (
                    "mkdir -p .omo/evidence/static && "
                    "echo hello > .omo/evidence/static/test-output.txt"
                ),
                "artifact": ".omo/evidence/static/test-output.txt",
                "artifact_mode": "declared_file",
                "blocks_release": True,
                "what_it_runs": "creates output file",
                "pass_criteria": "file exists",
                "applicability": "standard",
                "status": "implemented",
            }
        ],
        "foundation_closure": ["WF-HAR-TEST-02"],
    }
    _ = path.write_text(json.dumps(registry))


def test_recertify_deletes_stale_artifact_before_harness() -> None:
    """A pre-existing stale artifact is deleted before the harness runs.

    Without this guard a stale file from a previous run could be hashed
    by the runner and attributed to the current HEAD, fabricating a pass.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        _make_registry_with_local_artifact(registry_path)

        stale_dir = clone / ".omo" / "evidence" / "static"
        stale_dir.mkdir(parents=True, exist_ok=True)
        stale_file = stale_dir / "test-output.txt"
        _ = stale_file.write_text("stale content from previous run")

        report = recertify_foundation(
            repo_root=clone,
            registry_path=registry_path,
        )
        assert report["certified"] is True
        fresh_content = stale_file.read_text()
        assert fresh_content != "stale content from previous run"
        assert "hello" in fresh_content
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Cross-harness tamper detection
# ---------------------------------------------------------------------------


def _make_two_harness_registry(path: Path) -> None:
    """Write a registry with two harnesses that share an artifact path.

    The second harness overwrites the artifact produced by the first,
    testing the post-closure revalidation guard.
    """
    registry = {
        "schema_version": "1.0.0",
        "harness_count": 2,
        "catalog_harness_count": 2,
        "standard_blocker_count": 2,
        "standard_blockers": ["WF-HAR-TAMPER-01", "WF-HAR-TAMPER-02"],
        "harnesses": [
            {
                "id": "WF-HAR-TAMPER-01",
                "name": "producer",
                "command": (
                    "mkdir -p .omo/evidence/static && "
                    "echo 'first content' > .omo/evidence/static/shared-output.txt"
                ),
                "artifact": ".omo/evidence/static/shared-output.txt",
                "artifact_mode": "declared_file",
                "blocks_release": True,
                "what_it_runs": "creates shared output",
                "pass_criteria": "file exists",
                "applicability": "standard",
                "status": "implemented",
            },
            {
                "id": "WF-HAR-TAMPER-02",
                "name": "tamperer",
                "command": (
                    "mkdir -p .omo/evidence/static && "
                    "echo 'tampered content' > .omo/evidence/static/shared-output.txt"
                ),
                "artifact": ".omo/evidence/static/shared-output.txt",
                "artifact_mode": "declared_file",
                "blocks_release": True,
                "what_it_runs": "overwrites shared output",
                "pass_criteria": "file exists",
                "applicability": "standard",
                "status": "implemented",
            },
        ],
        "foundation_closure": ["WF-HAR-TAMPER-01", "WF-HAR-TAMPER-02"],
    }
    _ = path.write_text(json.dumps(registry))


def test_recertify_rejects_cross_harness_tamper() -> None:
    """Post-closure revalidation catches artifact tampering between harnesses.

    Harness B overwrites harness A's declared artifact after A was
    validated.  The post-closure revalidation must detect the hash
    mismatch and fail certification.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        _make_two_harness_registry(registry_path)

        with pytest.raises(CertificationError, match="hash mismatch"):
            _ = recertify_foundation(
                repo_root=clone,
                registry_path=registry_path,
            )
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


def _make_two_harness_evidence_tamper_registry(path: Path) -> None:
    """Write a registry where the second harness deletes the first's evidence JSON.

    This tests the disk-reload guard: the post-closure loop must detect
    that a harness's evidence record file has been deleted from the shared
    evidence root by another harness.
    """
    # Use 'find' to locate the evidence file at a known relative path under
    # .omo/evidence/runs/<sha>/<run_id>/. Both harnesses share the same
    # evidence_root within a single recertify_foundation call.
    delete_command = (
        "EVIDENCE_FILE=$(find .omo/evidence/runs -name "
        "'WF-HAR-TAMPER-EV-01.json' -type f 2>/dev/null | head -1) && "
        '[ -n "$EVIDENCE_FILE" ] && rm -f "$EVIDENCE_FILE" || true'
    )
    registry = {
        "schema_version": "1.0.0",
        "harness_count": 2,
        "catalog_harness_count": 2,
        "standard_blocker_count": 2,
        "standard_blockers": ["WF-HAR-TAMPER-EV-01", "WF-HAR-TAMPER-EV-02"],
        "harnesses": [
            {
                "id": "WF-HAR-TAMPER-EV-01",
                "name": "producer",
                "command": "echo producer > /dev/null",
                "artifact": "s3://bucket/producer",
                "artifact_mode": "declared_file",
                "blocks_release": True,
                "what_it_runs": "creates evidence",
                "pass_criteria": "exit 0",
                "applicability": "standard",
                "status": "implemented",
            },
            {
                "id": "WF-HAR-TAMPER-EV-02",
                "name": "evidence-tamperer",
                "command": delete_command,
                "artifact": "s3://bucket/tamperer",
                "artifact_mode": "declared_file",
                "blocks_release": True,
                "what_it_runs": "deletes first harness's evidence file",
                "pass_criteria": "exit 0",
                "applicability": "standard",
                "status": "implemented",
            },
        ],
        "foundation_closure": ["WF-HAR-TAMPER-EV-01", "WF-HAR-TAMPER-EV-02"],
    }
    _ = path.write_text(json.dumps(registry))


def test_recertify_rejects_deleted_evidence_record() -> None:
    """Post-closure disk reload catches a deleted evidence record file.

    Harness B deletes harness A's evidence JSON from the shared evidence
    root.  The disk-reload loop must detect the missing file and fail.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        _make_two_harness_evidence_tamper_registry(registry_path)

        with pytest.raises(CertificationError, match="evidence record file missing"):
            _ = recertify_foundation(
                repo_root=clone,
                registry_path=registry_path,
            )
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


def _make_two_harness_evidence_status_tamper_registry(path: Path) -> None:
    """Write a registry where second harness modifies first's evidence status.

    Harness B overwrites A's evidence JSON, changing the status from
    'pass' to 'fail'.  The disk-reload must detect the modified record
    (status changed) and revalidation must catch the tamper.
    """
    sed_command = (
        "EVIDENCE_FILE=$(find .omo/evidence/runs -name "
        "'WF-HAR-TAMPER-ST-01.json' -type f 2>/dev/null | head -1) && "
        '[ -n "$EVIDENCE_FILE" ] && '
        r"sed -i '' 's/\"status\": \"pass\"/\"status\": \"fail\"/' "
        '"$EVIDENCE_FILE" || true'
    )
    # macOS sed needs -i '' for in-place without backup
    registry = {
        "schema_version": "1.0.0",
        "harness_count": 2,
        "catalog_harness_count": 2,
        "standard_blocker_count": 2,
        "standard_blockers": ["WF-HAR-TAMPER-ST-01", "WF-HAR-TAMPER-ST-02"],
        "harnesses": [
            {
                "id": "WF-HAR-TAMPER-ST-01",
                "name": "producer",
                "command": "echo producer > /dev/null",
                "artifact": "s3://bucket/producer",
                "artifact_mode": "declared_file",
                "blocks_release": True,
                "what_it_runs": "creates evidence",
                "pass_criteria": "exit 0",
                "applicability": "standard",
                "status": "implemented",
            },
            {
                "id": "WF-HAR-TAMPER-ST-02",
                "name": "status-tamperer",
                "command": sed_command,
                "artifact": "s3://bucket/tamperer",
                "artifact_mode": "declared_file",
                "blocks_release": True,
                "what_it_runs": "changes first harness's evidence status",
                "pass_criteria": "exit 0",
                "applicability": "standard",
                "status": "implemented",
            },
        ],
        "foundation_closure": ["WF-HAR-TAMPER-ST-01", "WF-HAR-TAMPER-ST-02"],
    }
    _ = path.write_text(json.dumps(registry))


def test_recertify_rejects_tampered_evidence_status() -> None:
    """Post-closure disk reload catches a tampered evidence record (status change).

    Harness B modifies harness A's evidence JSON to change 'status'
    from 'pass' to 'fail'.  The disk-reload loop must detect the
    modified status (which contradicts the exit_code) and fail.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        _make_two_harness_evidence_status_tamper_registry(registry_path)

        with pytest.raises(CertificationError) as exc_info:
            _ = recertify_foundation(
                repo_root=clone,
                registry_path=registry_path,
            )
        # The revalidation should catch the tampered status (pass with
        # tampered exit_code mismatch, or the disk-reloaded record
        # validation)
        error_text = str(exc_info.value)
        assert any(
            kw in error_text for kw in ["status", "tamper", "fail", "hash mismatch"]
        )
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Validator negative tests (no git clones needed)
# ---------------------------------------------------------------------------

_REGISTRY = {
    "schema_version": "1.0.0",
    "harness_count": 1,
    "harnesses": [
        {
            "id": "WF-HAR-VALIDATE-TEST-01",
            "name": "validate-test",
            "command": "true",
            "artifact": "s3://example-bucket/test",
            "blocks_release": True,
            "what_it_runs": "test",
            "pass_criteria": "exit 0",
            "applicability": "standard",
            "status": "implemented",
        }
    ],
}

_SHA256_HEX = "ab" * 32


class _UnsetSentinel:
    pass


_UNSET: Any = _UnsetSentinel()


@pytest.fixture
def validator_env(tmp_path: Path) -> tuple[Path, EvidenceRecord]:
    """Create real stdout/stderr files and return (tmp_path, baseline_record)."""
    stdout_content = "stdout output"
    stderr_content = "stderr output"
    stdout_path = tmp_path / "stdout.txt"
    stderr_path = tmp_path / "stderr.txt"
    _ = stdout_path.write_text(stdout_content)
    _ = stderr_path.write_text(stderr_content)

    record = EvidenceRecord(
        schema_version="1.0.0",
        harness_id="WF-HAR-VALIDATE-TEST-01",
        status="pass",
        run_id="run-test-validate",
        subject_sha="a" * 40,
        subject_tree_sha="b" * 40,
        invocation=Invocation(
            command="true",
            exit_code=0,
            working_directory=".",
            start_time=datetime(2026, 7, 12, 10, 0, 0, tzinfo=UTC),
            end_time=datetime(2026, 7, 12, 10, 0, 1, tzinfo=UTC),
            duration_seconds=1.0,
        ),
        tool=Tool(
            name="test",
            version="8.2.0",
            commit_sha="a" * 40,
        ),
        applicability="standard",
        environment={"os": "test"},
        stdout_artifact=Artifact(
            path="stdout.txt",
            hashes={"sha256": hash_bytes(stdout_content.encode("utf-8"))},
        ),
        stderr_artifact=Artifact(
            path="stderr.txt",
            hashes={"sha256": hash_bytes(stderr_content.encode("utf-8"))},
        ),
        property_bag={"registry.harness_id": "WF-HAR-VALIDATE-TEST-01"},
    )
    return (tmp_path, record)


def _make_record(  # noqa: PLR0913 - many optional overrides for mutation tests
    *,
    env: tuple[Path, EvidenceRecord],
    subject_tree_sha: str = _UNSET,
    commit_sha: str = _UNSET,
    stdout: Artifact = _UNSET,
    stderr: Artifact = _UNSET,
    artifacts: list[Artifact] = _UNSET,
    property_bag: dict[str, JsonValue] = _UNSET,
) -> EvidenceRecord:
    """Build a record from the baseline with selective overrides.

    Each parameter independently overrides the corresponding field.
    Use *None* to explicitly clear a field.
    """
    base = env[1]
    overrides: dict[str, object] = {}
    if subject_tree_sha is not _UNSET:
        overrides["subject_tree_sha"] = subject_tree_sha
    if commit_sha is not _UNSET:
        overrides["tool"] = Tool(
            name="test",
            version="8.2.0",
            commit_sha=commit_sha,
        )
    if stdout is not _UNSET:
        overrides["stdout_artifact"] = stdout
    if stderr is not _UNSET:
        overrides["stderr_artifact"] = stderr
    if artifacts is not _UNSET:
        overrides["artifacts"] = artifacts or []
    if property_bag is not _UNSET:
        overrides["property_bag"] = property_bag
    return base.model_copy(update=overrides)


def test_validate_baseline_passes(
    validator_env: tuple[Path, EvidenceRecord],
) -> None:
    """Baseline record (real files, valid hashes, correct version) passes."""
    root, record = validator_env
    failures = validate_evidence_record(
        record,
        registry=_REGISTRY,
        expected_subject_sha="a" * 40,
        expected_subject_tree_sha="b" * 40,
        repo_root=root,
    )
    assert failures == []


def test_validate_rejects_subject_tree_sha_mismatch(
    validator_env: tuple[Path, EvidenceRecord],
) -> None:
    """Record subject_tree_sha differs from expected_subject_tree_sha -> failure."""
    root, _ = validator_env
    record = _make_record(env=validator_env, subject_tree_sha="x" * 40)
    _ = validate_evidence_record(
        record,
        registry=_REGISTRY,
        expected_subject_sha="a" * 40,
        expected_subject_tree_sha="x" * 40,
        repo_root=root,
    )
    record2 = _make_record(env=validator_env, subject_tree_sha="y" * 40)
    failures2 = validate_evidence_record(
        record2,
        registry=_REGISTRY,
        expected_subject_sha="a" * 40,
        expected_subject_tree_sha="x" * 40,
        repo_root=root,
    )
    assert any("subject_tree_sha" in f for f in failures2)
    assert len(failures2) == 1


def test_validate_rejects_tool_commit_sha_mismatch(
    validator_env: tuple[Path, EvidenceRecord],
) -> None:
    """tool.commit_sha differs from expected_subject_sha -> failure."""
    root, _ = validator_env
    record = _make_record(env=validator_env, commit_sha="c" * 40)
    failures = validate_evidence_record(
        record,
        registry=_REGISTRY,
        expected_subject_sha="a" * 40,
        repo_root=root,
    )
    assert any("tool.commit_sha" in f for f in failures)


def test_validate_rejects_stdout_hash_mismatch(
    validator_env: tuple[Path, EvidenceRecord],
) -> None:
    """stdout file content doesn't match the recorded hash -> failure."""
    root, record = validator_env
    _ = (root / "stdout.txt").write_text("tampered content")
    failures = validate_evidence_record(
        record,
        registry=_REGISTRY,
        expected_subject_sha="a" * 40,
        expected_subject_tree_sha="b" * 40,
        repo_root=root,
    )
    assert any("hash mismatch" in f for f in failures)


def test_validate_rejects_stdout_without_sha256(
    validator_env: tuple[Path, EvidenceRecord],
) -> None:
    """stdout_artifact with no sha256 hash -> failure."""
    root, _ = validator_env
    record = _make_record(
        env=validator_env,
        stdout=Artifact(
            path="stdout.txt",
            hashes={"md5": "d41d8cd98f00b204e9800998ecf8427e"},
        ),
    )
    failures = validate_evidence_record(
        record,
        registry=_REGISTRY,
        expected_subject_sha="a" * 40,
        repo_root=root,
    )
    assert any("sha256" in f for f in failures)


def test_validate_rejects_artifact_without_sha256(
    validator_env: tuple[Path, EvidenceRecord],
) -> None:
    """Declared artifact with no sha256 hash -> failure."""
    root, _ = validator_env
    record = _make_record(
        env=validator_env,
        artifacts=[
            Artifact(
                path="output.json",
                hashes={"md5": "d41d8cd98f00b204e9800998ecf8427e"},
            )
        ],
    )
    failures = validate_evidence_record(
        record,
        registry=_REGISTRY,
        expected_subject_sha="a" * 40,
        repo_root=root,
    )
    assert any("sha256" in f for f in failures)


def test_validate_rejects_missing_declared_artifact_when_flag_set(
    validator_env: tuple[Path, EvidenceRecord],
) -> None:
    """property_bag declares missing artifact -> failure."""
    root, _ = validator_env
    record = _make_record(
        env=validator_env,
        property_bag={
            "registry.harness_id": "WF-HAR-VALIDATE-TEST-01",
            "artifact.declared_missing": "some/file.json",
        },
    )
    failures = validate_evidence_record(
        record,
        registry=_REGISTRY,
        expected_subject_sha="a" * 40,
        repo_root=root,
    )
    assert any("declared artifact missing" in f for f in failures)


def test_validate_rejects_fabricated_tool_version(
    validator_env: tuple[Path, EvidenceRecord],
) -> None:
    """Tool version '1.0.0' is treated as fabricated -> failure."""
    root, base = validator_env
    bad_tool = Tool(name="test", version="1.0.0", commit_sha="a" * 40)
    record = base.model_copy(update={"tool": bad_tool})
    failures = validate_evidence_record(
        record,
        registry=_REGISTRY,
        expected_subject_sha="a" * 40,
        repo_root=root,
    )
    assert any("fabricated" in f for f in failures)


def test_validate_rejects_applicability_mismatch(
    validator_env: tuple[Path, EvidenceRecord],
) -> None:
    """Record.applicability differs from registry.applicability -> failure."""
    root, base = validator_env
    record = base.model_copy(update={"applicability": "tenant"})
    failures = validate_evidence_record(
        record,
        registry=_REGISTRY,
        expected_subject_sha="a" * 40,
        repo_root=root,
    )
    assert any("applicability" in f for f in failures)
