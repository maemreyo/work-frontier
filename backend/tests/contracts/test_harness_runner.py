"""Tests for harness runner revision-bound certification rules.

These guard the certification invariant: a claimed pass must come from
a clean working tree and the recorded tree SHA must match the source
tree that produced the evidence. The runner is fail-closed on dirty
trees, tree-mismatch, and prior-revision (stale) evidence.

The tests run the production ``recertify_foundation`` function against
fresh git clones of the repository so the working tree under inspection
is genuinely the one shipped at HEAD, not a working copy that contains
the test's own source edits.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from work_frontier.contracts.harness_runner import (
    CertificationError,
    recertify_foundation,
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


def test_recertify_foundation_fails_on_tracked_drift() -> None:
    clone = _make_clean_clone()
    try:
        _ = (clone / "README.md").write_text("mutated tracked content\n")
        with pytest.raises(CertificationError, match="working tree is dirty"):
            _ = recertify_foundation(repo_root=clone, require_clean_tree=True)
    finally:
        shutil.rmtree(clone, ignore_errors=True)


def test_recertify_foundation_fails_on_untracked_source() -> None:
    clone = _make_clean_clone()
    try:
        (clone / "scripts" / "stray_untracked.py").parent.mkdir(
            parents=True, exist_ok=True
        )
        _ = (clone / "scripts" / "stray_untracked.py").write_text("print(1)\n")
        with pytest.raises(CertificationError, match="working tree is dirty"):
            _ = recertify_foundation(repo_root=clone, require_clean_tree=True)
    finally:
        shutil.rmtree(clone, ignore_errors=True)


def test_recertify_foundation_fails_on_untracked_under_contracts() -> None:
    clone = _make_clean_clone()
    try:
        (clone / "contracts" / "stray.json").parent.mkdir(parents=True, exist_ok=True)
        _ = (clone / "contracts" / "stray.json").write_text("{}\n")
        with pytest.raises(CertificationError, match="working tree is dirty"):
            _ = recertify_foundation(repo_root=clone, require_clean_tree=True)
    finally:
        shutil.rmtree(clone, ignore_errors=True)


def test_recertify_foundation_records_subject_tree_sha_on_clean_tree() -> None:
    """When the tree is clean, the report's subject_tree_sha equals
    ``git write-tree`` and the working_tree_clean flag is True.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        # Use a minimal closure with a single passing harness command so the
        # test does not depend on uv/pnpm being installed in CI. The point
        # is to exercise the runner's tree-SHA + working_tree_clean logic,
        # not the harness commands themselves. The registry file lives
        # outside the clone so writing it does not dirty the working tree.
        import json as _json

        minimal_registry = {
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
        _ = registry_path.write_text(_json.dumps(minimal_registry))

        sys.path.insert(0, str(clone / "backend" / "src"))
        for mod in [
            "work_frontier.contracts.harness_runner",
            "work_frontier.contracts.evidence_writer",
        ]:
            if mod in sys.modules:
                del sys.modules[mod]
        from work_frontier.contracts import harness_runner as hr
        from work_frontier.contracts.evidence_writer import get_git_tree_sha

        expected_tree = get_git_tree_sha(clone)
        report = hr.recertify_foundation(
            repo_root=clone,
            registry_path=registry_path,
            require_clean_tree=True,
        )
        assert report["subject_tree_sha"] == expected_tree
        assert report["working_tree_clean"] is True
        for record in report["records"]:
            assert record["subject_tree_sha"] == expected_tree
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        with contextlib.suppress(NameError, AttributeError):
            registry_path.unlink(missing_ok=True)
        with contextlib.suppress(ValueError, NameError):
            sys.path.remove(str(clone / "backend" / "src"))


def test_recertify_foundation_reports_dirty_flag_when_clean_check_disabled() -> None:
    """With ``require_clean_tree=False`` the runner records a tree SHA that
    reflects the on-disk state, not HEAD. This is for the rare case where
    the caller already knows the working tree is intentionally dirty and
    wants the evidence to attest that state explicitly.
    """
    clone = _make_clean_clone()
    registry_path = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        import json as _json

        minimal_registry = {
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
        _ = registry_path.write_text(_json.dumps(minimal_registry))

        _ = (clone / "README.md").write_text("intentional mutation\n")

        sys.path.insert(0, str(clone / "backend" / "src"))
        for mod in [
            "work_frontier.contracts.harness_runner",
            "work_frontier.contracts.evidence_writer",
        ]:
            if mod in sys.modules:
                del sys.modules[mod]
        from work_frontier.contracts import harness_runner as hr

        report = hr.recertify_foundation(
            repo_root=clone,
            registry_path=registry_path,
            require_clean_tree=False,
        )
        # Evidence can still certify the surface pass/fail of the registry
        # harnesses, but the report's working_tree_clean flag must be False
        # so downstream consumers know not to claim a clean revision.
        assert report["working_tree_clean"] is False
        assert report["subject_tree_sha"] is not None
    finally:
        shutil.rmtree(clone, ignore_errors=True)
        with contextlib.suppress(NameError, AttributeError):
            registry_path.unlink(missing_ok=True)
        with contextlib.suppress(ValueError, NameError):
            sys.path.remove(str(clone / "backend" / "src"))
