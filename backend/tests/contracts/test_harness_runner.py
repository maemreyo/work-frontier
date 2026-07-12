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
from typing import TYPE_CHECKING

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


def _make_valid_record(
    *,
    tree_sha_and_commit_match: str = "",
    stdout: Artifact | None = None,
    stderr: Artifact | None = None,
    artifacts: list[Artifact] | None = None,
    property_bag: dict[str, JsonValue] | None = None,
) -> EvidenceRecord:
    """Build a valid EvidenceRecord with optional field overrides."""
    return EvidenceRecord(
        schema_version="1.0.0",
        harness_id="WF-HAR-VALIDATE-TEST-01",
        status="pass",
        run_id="run-test-validate",
        subject_sha="a" * 40,
        subject_tree_sha=tree_sha_and_commit_match or "b" * 40,
        invocation=Invocation(
            command="true",
            exit_code=0,
            start_time=datetime(2026, 7, 12, 10, 0, 0, tzinfo=UTC),
            end_time=datetime(2026, 7, 12, 10, 0, 1, tzinfo=UTC),
            duration_seconds=1.0,
        ),
        tool=Tool(
            name="test",
            version="1.0.0",
            commit_sha=tree_sha_and_commit_match or "a" * 40,
        ),
        environment={"os": "test"},
        stdout_artifact=stdout
        or Artifact(path="stdout.txt", hashes={"sha256": _SHA256_HEX}),
        stderr_artifact=stderr
        or Artifact(path="stderr.txt", hashes={"sha256": _SHA256_HEX}),
        artifacts=artifacts or [],
        property_bag=property_bag or {"registry.harness_id": "WF-HAR-VALIDATE-TEST-01"},
    )


def test_validate_rejects_subject_tree_sha_mismatch() -> None:
    """Record subject_tree_sha differs from expected_subject_tree_sha -> failure."""
    record = _make_valid_record()
    failures = validate_evidence_record(
        record,
        registry=_REGISTRY,
        expected_subject_sha="a" * 40,
        expected_subject_tree_sha="x" * 40,
    )
    assert any("subject_tree_sha" in f for f in failures)


def test_validate_rejects_tool_commit_sha_mismatch() -> None:
    """tool.commit_sha differs from expected_subject_sha -> failure."""
    record = _make_valid_record(tree_sha_and_commit_match="c" * 40)
    failures = validate_evidence_record(
        record,
        registry=_REGISTRY,
        expected_subject_sha="a" * 40,
    )
    assert any("tool.commit_sha" in f for f in failures)


def test_validate_rejects_missing_stdout_artifact() -> None:
    """stdout_artifact is None -> failure."""
    record = _make_valid_record(stdout=None)
    failures = validate_evidence_record(record, registry=_REGISTRY)
    assert any("stdout" in f and "artifact" in f for f in failures)


def test_validate_rejects_missing_stderr_artifact() -> None:
    """stderr_artifact is None -> failure."""
    record = _make_valid_record(stderr=None)
    failures = validate_evidence_record(record, registry=_REGISTRY)
    assert any("stderr" in f and "artifact" in f for f in failures)


def test_validate_rejects_stdout_without_sha256() -> None:
    """stdout_artifact with no sha256 hash -> failure."""
    record = _make_valid_record(
        stdout=Artifact(path="stdout.txt", hashes=None),
    )
    failures = validate_evidence_record(record, registry=_REGISTRY)
    assert any("sha256" in f for f in failures)


def test_validate_rejects_artifact_without_sha256() -> None:
    """Declared artifact with no sha256 hash -> failure."""
    record = _make_valid_record(
        artifacts=[Artifact(path="output.json", hashes=None)],
    )
    failures = validate_evidence_record(record, registry=_REGISTRY)
    assert any("sha256" in f for f in failures)


def test_validate_rejects_missing_declared_artifact_when_flag_set() -> None:
    """property_bag declares missing artifact -> failure even without on-disk check."""
    record = _make_valid_record(
        property_bag={
            "registry.harness_id": "WF-HAR-VALIDATE-TEST-01",
            "artifact.declared_missing": "some/file.json",
        },
    )
    failures = validate_evidence_record(record, registry=_REGISTRY)
    assert any("declared artifact missing" in f for f in failures)
