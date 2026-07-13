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

from pydantic import ValidationError

from work_frontier.contracts.evidence_record import (
    Artifact,
    ArtifactHashes,
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
    """Write a minimal one-harness registry that always passes.

    The harness writes to $WF_HARNESS_ARTIFACT (the run-scoped path)
    rather than a hard-coded global location.
    """
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
                "command": (
                    'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
                    'echo test > "$WF_HARNESS_ARTIFACT"'
                ),
                "artifact": ".omo/evidence/static/test-output.txt",
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
                    "artifact": ".omo/evidence/static/test.json",
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
        assert {record["run_id"] for record in report["records"]} == {report["run_id"]}
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
    """Write a registry whose artifact is a local file (not remote).

    The harness writes to $WF_HARNESS_ARTIFACT (the run-scoped path).
    """
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
                    'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
                    'echo hello > "$WF_HARNESS_ARTIFACT"'
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


def test_recertify_ignores_stale_global_artifact() -> None:
    """A stale artifact at the legacy global path does not affect certification.

    The legacy global path fallback has been eliminated: harness artifacts
    must be produced at the run-scoped path ($WF_HARNESS_ARTIFACT), not
    at the old global location. A stale file at the old path is simply
    ignored.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        _make_registry_with_local_artifact(registry_path)

        # Preseed a stale artifact at the legacy global path
        stale_dir = clone / ".omo" / "evidence" / "static"
        stale_dir.mkdir(parents=True, exist_ok=True)
        stale_file = stale_dir / "test-output.txt"
        _ = stale_file.write_text("stale content from previous run")

        # Recert succeeds — the stale global artifact is ignored
        report = recertify_foundation(
            repo_root=clone,
            registry_path=registry_path,
        )
        assert report["certified"] is True

        # The stale file at the global path is left untouched
        assert stale_file.read_text() == "stale content from previous run"

        # The harness wrote its artifact to the run-scoped path
        ev_root = clone / report["evidence_root"]
        artifact_path = ev_root / "artifacts" / "WF-HAR-TEST-02" / "test-output.txt"
        assert artifact_path.is_file()
        fresh_content = artifact_path.read_text()
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
    testing the post-closure revalidation guard.  Both harnesses write
    to their own $WF_HARNESS_ARTIFACT (run-scoped).
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
                    'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
                    "echo 'first content' > \"$WF_HARNESS_ARTIFACT\""
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
                    'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
                    "echo 'tampered content' > \"$WF_HARNESS_ARTIFACT\""
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


def test_recertify_run_scoped_artifacts_prevent_cross_harness_tamper() -> None:
    """Run-scoped artifact paths prevent cross-harness tampering.

    Each harness gets its own artifact directory under
    evidence_root/artifacts/<harness_id>/, so even when two harnesses
    write to the same global path, their certified artifact copies
    are isolated and no hash collision occurs.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        _make_two_harness_registry(registry_path)

        report = recertify_foundation(
            repo_root=clone,
            registry_path=registry_path,
        )
        assert report["certified"] is True

        # Verify each harness has its own run-scoped artifact.
        evidence_root = clone / report["evidence_root"]
        h1_artifact = (
            evidence_root / "artifacts" / "WF-HAR-TAMPER-01" / "shared-output.txt"
        )
        h2_artifact = (
            evidence_root / "artifacts" / "WF-HAR-TAMPER-02" / "shared-output.txt"
        )
        assert h1_artifact.is_file()
        assert h2_artifact.is_file()
        assert h1_artifact.read_text() != h2_artifact.read_text()
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


def test_recertify_rejects_unexpected_evidence_record_on_disk() -> None:
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        registry = {
            "schema_version": "1.0.0",
            "harness_count": 1,
            "catalog_harness_count": 1,
            "standard_blocker_count": 1,
            "standard_blockers": ["WF-HAR-EXTRA-01"],
            "harnesses": [
                {
                    "id": "WF-HAR-EXTRA-01",
                    "name": "writes-extra-record",
                    "command": (
                        'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
                        'echo output > "$WF_HARNESS_ARTIFACT" && '
                        "echo '{}' > \"$WF_EVIDENCE_ROOT/WF-HAR-EXTRA-FAKE.json\""
                    ),
                    "artifact": ".omo/evidence/static/extra-output.txt",
                    "artifact_mode": "declared_file",
                    "blocks_release": True,
                    "what_it_runs": "writes a contradictory record",
                    "pass_criteria": "closure rejects extra JSON",
                    "applicability": "standard",
                    "status": "implemented",
                }
            ],
            "foundation_closure": ["WF-HAR-EXTRA-01"],
        }
        _ = registry_path.write_text(json.dumps(registry))

        with pytest.raises(CertificationError, match="unexpected"):
            _ = recertify_foundation(repo_root=clone, registry_path=registry_path)
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


def test_recertify_rejects_unreferenced_nested_artifact() -> None:
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        registry = {
            "schema_version": "1.0.0",
            "harness_count": 1,
            "catalog_harness_count": 1,
            "standard_blocker_count": 1,
            "standard_blockers": ["WF-HAR-NESTED-EXTRA-01"],
            "harnesses": [
                {
                    "id": "WF-HAR-NESTED-EXTRA-01",
                    "name": "writes-unreferenced-nested-file",
                    "command": (
                        'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
                        'echo output > "$WF_HARNESS_ARTIFACT" && '
                        'echo stale > "$(dirname "$WF_HARNESS_ARTIFACT")/'
                        'old-failure.json"'
                    ),
                    "artifact": ".omo/evidence/static/output.txt",
                    "artifact_mode": "declared_file",
                    "blocks_release": True,
                    "what_it_runs": "writes an unreferenced nested artifact",
                    "pass_criteria": "closure rejects every unreferenced file",
                    "applicability": "standard",
                    "status": "implemented",
                }
            ],
            "foundation_closure": ["WF-HAR-NESTED-EXTRA-01"],
        }
        _ = registry_path.write_text(json.dumps(registry))

        with pytest.raises(CertificationError, match="unexpected"):
            _ = recertify_foundation(repo_root=clone, registry_path=registry_path)
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
        'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
        'echo tamper > "$WF_HARNESS_ARTIFACT" && '
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
                "command": (
                    'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
                    'echo producer > "$WF_HARNESS_ARTIFACT"'
                ),
                "artifact": ".omo/evidence/static/producer.json",
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
                "artifact": ".omo/evidence/static/tamperer.json",
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
        'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
        'echo tamper > "$WF_HARNESS_ARTIFACT" && '
        'python -c "import json,pathlib; '
        "p=next(pathlib.Path('.').rglob('WF-HAR-TAMPER-ST-01.json')); "
        "d=json.loads(p.read_text()); "
        "d['status']='fail'; "
        'p.write_text(json.dumps(d))"'
    )
    # Portable Python one-liner replaces the file's JSON status
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
                "command": (
                    'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
                    'echo producer > "$WF_HARNESS_ARTIFACT"'
                ),
                "artifact": ".omo/evidence/static/producer.json",
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
                "artifact": ".omo/evidence/static/tamperer.json",
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

        with pytest.raises(
            CertificationError,
            match=r"evidence record content changed after creation",
        ):
            _ = recertify_foundation(
                repo_root=clone,
                registry_path=registry_path,
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
            "artifact": ".omo/evidence/static/test.json",
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
        applicability_reason="Standard foundation closure test record",
        environment={"os": "test"},
        stdout_artifact=Artifact(
            path="stdout.txt",
            hashes=ArtifactHashes(sha256=hash_bytes(stdout_content.encode("utf-8"))),
        ),
        stderr_artifact=Artifact(
            path="stderr.txt",
            hashes=ArtifactHashes(sha256=hash_bytes(stderr_content.encode("utf-8"))),
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


def test_validate_rejects_stdout_without_sha256() -> None:
    """Artifact without sha256 is rejected at the model level."""
    with pytest.raises(ValidationError, match="sha256"):
        _ = Artifact(
            path="stdout.txt",
            hashes={"md5": "d41d8cd98f00b204e9800998ecf8427e"},  # pyright: ignore[reportArgumentType]
        )


def test_validate_rejects_artifact_without_sha256() -> None:
    """Declared artifact without sha256 is rejected at the model level."""
    with pytest.raises(ValidationError, match="sha256"):
        _ = Artifact(
            path="output.json",
            hashes={"md5": "d41d8cd98f00b204e9800998ecf8427e"},  # pyright: ignore[reportArgumentType]
        )


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


# ---------------------------------------------------------------------------
# Stale global artifact fallback elimination — command=true must NOT certify
# a pre-existing artifact at the legacy global path.
# ---------------------------------------------------------------------------


def test_recertify_rejects_stale_global_artifact_with_command_true() -> None:
    """command=true with a stale global artifact must NOT fabricate a pass.

    Previously, when the run-scoped artifact was missing, the runner fell back
    to root/declared_artifact (the legacy global path). A stale global file
    combined with command=true would produce a false pass. This test proves
    the fallback is eliminated: the artifact must be produced under the
    run-scoped directory or the harness fails.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        registry = {
            "schema_version": "1.0.0",
            "harness_count": 1,
            "catalog_harness_count": 1,
            "standard_blocker_count": 1,
            "standard_blockers": ["WF-HAR-STALE-01"],
            "harnesses": [
                {
                    "id": "WF-HAR-STALE-01",
                    "name": "stale-global-fallback",
                    "command": "true",
                    "artifact": ".omo/evidence/static/stale-output.txt",
                    "artifact_mode": "declared_file",
                    "blocks_release": True,
                    "what_it_runs": "produces no artifact (true does nothing)",
                    "pass_criteria": "must produce artifact",
                    "applicability": "standard",
                    "status": "implemented",
                }
            ],
            "foundation_closure": ["WF-HAR-STALE-01"],
        }
        _ = registry_path.write_text(json.dumps(registry))

        # Preseed the GLOBAL artifact path (legacy location).
        # The run-scoped directory under evidence_root/artifacts/ does not
        # have this file. Command=true will NOT produce it.
        global_dir = clone / ".omo" / "evidence" / "static"
        global_dir.mkdir(parents=True, exist_ok=True)
        stale_file = global_dir / "stale-output.txt"
        _ = stale_file.write_text("stale global artifact")

        # The certification must fail because the harness command is
        # 'true' (produces no artifact) and the global fallback is gone.
        with pytest.raises(
            CertificationError, match=r"missing_declared_artifact|artifact missing|fail"
        ):
            _ = recertify_foundation(repo_root=clone, registry_path=registry_path)

        # The stale global artifact must still exist (unused)
        assert stale_file.is_file()
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Standalone run_harness invocations get unique run-scoped evidence roots
# ---------------------------------------------------------------------------


def test_standalone_run_harness_gets_unique_evidence_root() -> None:
    """Standalone run_harness without evidence_root must generate a
    unique run-scoped root.

    Two consecutive calls must produce evidence in different directories.
    Previously both calls would default to .omo/evidence/static.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        registry = {
            "schema_version": "1.0.0",
            "harness_count": 1,
            "catalog_harness_count": 1,
            "standard_blocker_count": 0,
            "standard_blockers": [],
            "harnesses": [
                {
                    "id": "WF-HAR-UNIQUE-01",
                    "name": "unique-root",
                    "command": (
                        'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
                        'echo hello > "$WF_HARNESS_ARTIFACT"'
                    ),
                    "artifact": "output.txt",
                    "artifact_mode": "declared_file",
                    "blocks_release": False,
                    "what_it_runs": "echo",
                    "pass_criteria": "exit 0",
                    "applicability": "standard",
                    "status": "implemented",
                }
            ],
            "foundation_closure": ["WF-HAR-UNIQUE-01"],
        }
        _ = registry_path.write_text(json.dumps(registry))

        hr = _import_harness_runner(clone)

        # First call — should use a run-scoped evidence root
        record1 = hr.run_harness(
            "WF-HAR-UNIQUE-01",
            repo_root=clone,
            registry_path=registry_path,
        )

        # Second call — must use a DIFFERENT evidence root
        record2 = hr.run_harness(
            "WF-HAR-UNIQUE-01",
            repo_root=clone,
            registry_path=registry_path,
        )

        # Run IDs must differ, proving different unique evidence roots
        assert record1.run_id != record2.run_id, "run IDs should differ"

        # The evidence root directory name MUST equal record.run_id, proving
        # the resolve-once invariant: when run_harness receives neither
        # run_id nor evidence_root, it resolves one ID and uses it for
        # both the directory path and the record field.
        ev_root1 = clone / ".omo" / "evidence" / "runs" / record1.run_id
        ev_root2 = clone / ".omo" / "evidence" / "runs" / record2.run_id
        assert ev_root1.is_dir(), f"evidence root {ev_root1} should exist"
        assert ev_root2.is_dir(), f"evidence root {ev_root2} should exist"
        assert ev_root1 != ev_root2
        assert ev_root1.name == record1.run_id
        assert ev_root2.name == record2.run_id
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Recursive manifest coverage — expected sidecars/artifacts must be covered;
# unexpected nested files must be rejected.
# ---------------------------------------------------------------------------


def test_recertify_rejects_unexpected_nested_file_in_evidence_root() -> None:
    """An unexpected nested file under the evidence root causes certification failure.

    The manifest must recursively scan the evidence root, and any file
    not matching expected evidence records, stdout/stderr sidecars, or
    declared artifacts triggers a rejection.  A harness that writes a
    subdirectory file is caught by the recursive scanner.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        registry = {
            "schema_version": "1.0.0",
            "harness_count": 1,
            "catalog_harness_count": 1,
            "standard_blocker_count": 1,
            "standard_blockers": ["WF-HAR-NESTED-01"],
            "harnesses": [
                {
                    "id": "WF-HAR-NESTED-01",
                    "name": "nested-writer",
                    "command": (
                        'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
                        'echo legit > "$WF_HARNESS_ARTIFACT" && '
                        'mkdir -p "$WF_EVIDENCE_ROOT/unexpected/deep" && '
                        'echo sneaky > "$WF_EVIDENCE_ROOT/unexpected/deep/sneaky.txt"'
                    ),
                    "artifact": "nested-output.txt",
                    "artifact_mode": "declared_file",
                    "blocks_release": True,
                    "what_it_runs": "writes artifact and an unexpected nested file",
                    "pass_criteria": "closure rejects nested file",
                    "applicability": "standard",
                    "status": "implemented",
                }
            ],
            "foundation_closure": ["WF-HAR-NESTED-01"],
        }
        _ = registry_path.write_text(json.dumps(registry))

        with pytest.raises(CertificationError, match="unexpected"):
            _ = recertify_foundation(
                repo_root=clone,
                registry_path=registry_path,
            )
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


def test_recertify_manifest_covers_sidecar_and_artifact_files() -> None:
    """The evidence manifest must record hashes for sidecar files and artifacts.

    The manifest uses recursive scanning and should include stdout/stderr
    sidecars and artifact files in addition to the evidence JSON record.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        _make_minimal_registry(registry_path)

        report = recertify_foundation(
            repo_root=clone,
            registry_path=registry_path,
        )
        assert report["certified"] is True

        # The manifest should contain entries for the evidence JSON record,
        # stdout/stderr sidecars, and the artifact copy.
        manifest = report.get("evidence_manifest", {})
        # Evidence JSON for the closure member
        assert "WF-HAR-TEST-01.json" in manifest, (
            "manifest must contain the harness evidence JSON"
        )
        # Stdout sidecar
        assert "WF-HAR-TEST-01.stdout.txt" in manifest, (
            "manifest must contain stdout sidecar"
        )
        # Stderr sidecar (empty but still written)
        assert "WF-HAR-TEST-01.stderr.txt" in manifest, (
            "manifest must contain stderr sidecar"
        )
        # Artifact under artifacts/<harness_id>/
        artifact_keys = [
            k for k in manifest if k.startswith("artifacts/WF-HAR-TEST-01/")
        ]
        assert artifact_keys, (
            "manifest must contain artifact under artifacts/<harness_id>/"
        )
        total_expected = 4  # evidence JSON + stdout + stderr + artifact
        assert len(manifest) == total_expected, (
            f"expected {total_expected} files in manifest, got {len(manifest)}: "
            f"{sorted(manifest)}"
        )

        # On a fresh clone, rerun and verify same number of entries
        clone2 = _make_clean_clone()
        _make_minimal_registry(registry_path)
        report2 = recertify_foundation(
            repo_root=clone2,
            registry_path=registry_path,
        )
        manifest2 = report2.get("evidence_manifest", {})
        assert len(manifest2) == total_expected
        shutil.rmtree(clone2, ignore_errors=True)
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Prerequisite enforcement in recertify_foundation
# ---------------------------------------------------------------------------


def _make_prereq_registry(path: Path, *, first_fails: bool = False) -> None:
    """Write a two-harness registry where the second depends on the first.

    When *first_fails* is True the first harness command exits nonzero.
    The second harness's declared artifact proves whether it executed.
    """
    first_command = (
        'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
        'echo first > "$WF_HARNESS_ARTIFACT"'
    )
    if first_fails:
        first_command = (
            'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
            'echo first > "$WF_HARNESS_ARTIFACT" && exit 1'
        )
    second_command = (
        'mkdir -p "$(dirname "$WF_HARNESS_ARTIFACT")" && '
        'echo second > "$WF_HARNESS_ARTIFACT"'
    )
    registry: dict[str, object] = {
        "schema_version": "1.0.0",
        "harness_count": 2,
        "catalog_harness_count": 2,
        "standard_blocker_count": 2,
        "standard_blockers": ["WF-HAR-PREREQ-A-01", "WF-HAR-PREREQ-B-01"],
        "harnesses": [
            {
                "id": "WF-HAR-PREREQ-A-01",
                "name": "prereq-a",
                "command": first_command,
                "artifact": "output-a.txt",
                "artifact_mode": "declared_file",
                "blocks_release": True,
                "what_it_runs": "first harness",
                "pass_criteria": "exit 0",
                "applicability": "standard",
                "status": "implemented",
                "prerequisites": [],
            },
            {
                "id": "WF-HAR-PREREQ-B-01",
                "name": "prereq-b",
                "command": second_command,
                "artifact": "output-b.txt",
                "artifact_mode": "declared_file",
                "blocks_release": True,
                "what_it_runs": "second harness",
                "pass_criteria": "exit 0",
                "applicability": "standard",
                "status": "implemented",
                "prerequisites": ["WF-HAR-PREREQ-A-01"],
            },
        ],
        "foundation_closure": ["WF-HAR-PREREQ-A-01", "WF-HAR-PREREQ-B-01"],
    }
    _ = path.write_text(json.dumps(registry))


def test_recertify_prerequisite_failure_prevents_dependent_execution() -> None:
    """When a prerequisite fails, the dependent harness is not executed.

    The dependent harness writes a sentinel file; its absence after
    recertification proves the command was skipped.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        _make_prereq_registry(registry_path, first_fails=True)

        with pytest.raises(CertificationError, match=r"prerequisite.*not satisfied"):
            _ = recertify_foundation(
                repo_root=clone,
                registry_path=registry_path,
            )

        # The dependent declared artifact must not exist when it is skipped.
        artifact_root = clone / ".omo" / "evidence" / "runs"
        matching = sorted(artifact_root.rglob("**/output-b.txt"))
        assert not matching, (
            f"dependent harness should not have executed, "
            f"but declared artifact found: {matching}"
        )

        # The first harness's evidence root should exist under runs/
        first_records = list(
            (clone / ".omo" / "evidence" / "runs").rglob("WF-HAR-PREREQ-A-01.json")
        )
        assert first_records, "first harness evidence should have been written"
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


def test_recertify_prerequisite_pass_allows_dependent_execution() -> None:
    """When the prerequisite passes, the dependent harness executes."""
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        _make_prereq_registry(registry_path, first_fails=False)

        report = recertify_foundation(
            repo_root=clone,
            registry_path=registry_path,
        )
        assert report["certified"] is True

        # The dependent declared artifact proves that the harness ran.
        artifact_root = clone / ".omo" / "evidence" / "runs"
        matching = sorted(artifact_root.rglob("**/output-b.txt"))
        assert matching, "dependent harness should have executed"
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)


def test_recertify_failure_surfaces_command_output_without_manifest_noise() -> None:
    """A failed command exposes diagnostics without secondary manifest errors."""
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        registry = {
            "schema_version": "1.0.0",
            "harness_count": 1,
            "catalog_harness_count": 1,
            "standard_blocker_count": 1,
            "standard_blockers": ["WF-HAR-DIAG-01"],
            "harnesses": [
                {
                    "id": "WF-HAR-DIAG-01",
                    "name": "diagnostic-failure",
                    "command": (
                        "printf 'TYPECHECK_MARKER\\n'; "
                        "printf 'TSC_MARKER\\n' >&2; "
                        "exit 1"
                    ),
                    "artifact": ".omo/evidence/static/diagnostic.txt",
                    "artifact_mode": "declared_file",
                    "blocks_release": True,
                    "what_it_runs": "a deterministic failing command",
                    "pass_criteria": "diagnostics are surfaced",
                    "applicability": "standard",
                    "status": "implemented",
                }
            ],
            "foundation_closure": ["WF-HAR-DIAG-01"],
        }
        _ = registry_path.write_text(json.dumps(registry), encoding="utf-8")

        with pytest.raises(CertificationError) as exc:
            _ = recertify_foundation(
                repo_root=clone,
                registry_path=registry_path,
            )

        message = str(exc.value)
        assert "TYPECHECK_MARKER" in message
        assert "TSC_MARKER" in message
        assert "evidence disk is missing referenced files" not in message
        assert "evidence disk has unexpected files" not in message
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        registry_path.unlink(missing_ok=True)
