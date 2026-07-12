"""Tests for harness registry and runner certification rules."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from work_frontier.contracts.evidence_record import (
    Artifact,
    ArtifactHashes,
    EvidenceRecord,
    Invocation,
    Result,
    Tool,
)
from work_frontier.contracts.evidence_writer import get_tool_version
from work_frontier.contracts.harness_registry import (
    HarnessRegistryError,
    get_harness,
    load_registry,
    validate_registry,
)
from work_frontier.contracts.harness_runner import validate_evidence_record

ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / "contracts" / "harness-registry.json"


def test_registry_loads_and_matches_catalog_counts() -> None:
    registry = load_registry(REGISTRY_PATH)
    assert registry["schema_version"] == "1.0.0"
    assert registry["catalog_harness_count"] == registry["harness_count"] == 68
    assert "WF-HAR-PREFLIGHT-01" in registry["foundation_closure"]
    assert "WF-HAR-STATIC-01" in registry["foundation_closure"]
    assert "WF-HAR-STATIC-05" in registry["foundation_closure"]
    preflight = get_harness(registry, "WF-HAR-PREFLIGHT-01")
    assert preflight["status"] == "implemented"
    assert "validate.test.mjs" in preflight["command"]
    static05 = get_harness(registry, "WF-HAR-STATIC-05")
    assert "gitleaks" in static05["command"].lower()
    assert "validate.mjs" not in static05["command"]


def test_registry_rejects_invalid_artifact_mode() -> None:
    """Runtime validate_registry rejects harnesses with invalid artifact_mode."""
    registry = load_registry(REGISTRY_PATH)
    # Inject a harness with bogus artifact_mode
    bogus = dict(registry["harnesses"][0])
    bogus["id"] = "WF-HAR-TEST-BOGUS"
    bogus["artifact_mode"] = "bogus"
    registry["harnesses"] = [*registry["harnesses"], bogus]
    registry["harness_count"] = len(registry["harnesses"])
    with pytest.raises(HarnessRegistryError, match="invalid artifact_mode"):
        validate_registry(registry)


def test_registry_rejects_missing_artifact_mode() -> None:
    """Runtime validate_registry rejects harnesses missing artifact_mode."""
    registry = load_registry(REGISTRY_PATH)
    entry = dict(registry["harnesses"][0])
    entry["id"] = "WF-HAR-TEST-NOAM"
    entry.pop("artifact_mode", None)
    entry["artifact"] = "s3://bucket/test"
    registry["harnesses"] = [*registry["harnesses"], entry]
    registry["harness_count"] = len(registry["harnesses"])
    err_match = "missing required field artifact_mode"
    with pytest.raises(HarnessRegistryError, match=err_match):
        validate_registry(registry)


def test_registry_rejects_duplicate_ids() -> None:
    registry = load_registry(REGISTRY_PATH)
    registry["harnesses"] = [
        *registry["harnesses"],
        dict(registry["harnesses"][0]),
    ]
    registry["harness_count"] = len(registry["harnesses"])
    with pytest.raises(HarnessRegistryError, match="duplicate"):
        validate_registry(registry)


def test_get_tool_version_does_not_fabricate() -> None:
    version = get_tool_version("python")
    assert version
    assert version != "1.0.0"
    with pytest.raises(LookupError):
        _ = get_tool_version("definitely-not-a-real-tool-xyz")


def test_validate_evidence_rejects_fabricated_version_and_stale_subject() -> None:
    registry = load_registry(REGISTRY_PATH)
    record = EvidenceRecord(
        schema_version="1.0.0",
        harness_id="WF-HAR-STATIC-02",
        status="pass",
        run_id="run-test",
        subject_sha="a" * 40,
        subject_tree_sha="a" * 40,
        invocation=Invocation(
            command="true",
            exit_code=0,
            working_directory=".",
            start_time=datetime(2026, 7, 12, tzinfo=UTC),
            end_time=datetime(2026, 7, 12, 0, 0, 1, tzinfo=UTC),
            duration_seconds=1.0,
        ),
        tool=Tool(name="python", version="1.0.0", commit_sha="a" * 40),
        applicability="standard",
        environment={"os": "test"},
        artifacts=[Artifact(path="x", hashes=ArtifactHashes(sha256="b" * 64))],
        results=[Result(kind="test", passed=True)],
        stdout_artifact=Artifact(
            path="stdout.txt", hashes=ArtifactHashes(sha256="c" * 64)
        ),
        stderr_artifact=Artifact(
            path="stderr.txt", hashes=ArtifactHashes(sha256="d" * 64)
        ),
        property_bag={"registry.harness_id": "WF-HAR-STATIC-02"},
    )
    failures = validate_evidence_record(
        record,
        registry=registry,
        expected_subject_sha="c" * 40,
        require_blocking_pass=True,
        repo_root=ROOT,
    )
    assert any("subject_sha" in item for item in failures)
    assert any("tool version" in item for item in failures)
    assert any(
        "stdout artifact" in item or "stderr artifact" in item for item in failures
    )


def test_registry_file_is_valid_json_with_foundation_closure() -> None:
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert data["harness_count"] == data["catalog_harness_count"] == 68
    assert "WF-HAR-PREFLIGHT-01" in data["foundation_closure"]
    assert "WF-HAR-STATIC-05" in data["foundation_closure"]
    assert all(harness["command"].strip() for harness in data["harnesses"])
    assert all(harness["artifact"].strip() for harness in data["harnesses"])


def _minimal_harness(**overrides: object) -> dict[str, object]:
    """Build a minimal valid harness dict with overrides."""
    base: dict[str, object] = {
        "id": "WF-HAR-TEST-01",
        "name": "test",
        "command": "true",
        "artifact": "s3://bucket/test",
        "blocks_release": False,
        "what_it_runs": "test",
        "pass_criteria": "exit 0",
        "applicability": "standard",
        "artifact_mode": "declared_file",
        "status": "implemented",
    }
    base.update(overrides)
    return base


def _minimal_registry(*harnesses: dict[str, object]) -> dict[str, object]:
    """Build a minimal valid registry dict around the given harnesses."""
    harness_list = list(harnesses) if harnesses else [_minimal_harness()]
    return {
        "schema_version": "1.0.0",
        "harness_count": len(harness_list),
        "catalog_harness_count": len(harness_list),
        "standard_blocker_count": 0,
        "standard_blockers": [],
        "foundation_closure": [str(h["id"]) for h in harness_list],
        "harnesses": harness_list,
    }


def test_build_rejects_invalid_artifact_mode_value() -> None:
    """Invalid artifact_mode values are rejected at build time."""
    harness = _minimal_harness(artifact_mode="bogus_mode")
    registry = _minimal_registry(harness)
    with pytest.raises(HarnessRegistryError, match="invalid artifact_mode"):
        validate_registry(registry)


def test_build_rejects_runner_evidence_on_unapproved_harness() -> None:
    """runner_evidence mode is only allowed for whitelisted harnesses."""
    harness = _minimal_harness(
        id="WF-HAR-STATIC-02",
        artifact_mode="runner_evidence",
        artifact=".omo/evidence/static/WF-HAR-STATIC-02.json",
    )
    registry = _minimal_registry(harness)
    with pytest.raises(HarnessRegistryError, match="runner_evidence mode not allowed"):
        validate_registry(registry)


def test_build_rejects_wrong_runner_evidence_artifact_path() -> None:
    """runner_evidence harness must declare artifact path matching its ID."""
    harness = _minimal_harness(
        id="WF-HAR-STATIC-01",
        artifact_mode="runner_evidence",
        artifact=".omo/evidence/static/wrong-path.json",
    )
    registry = _minimal_registry(harness)
    with pytest.raises(HarnessRegistryError, match="does not match expected"):
        validate_registry(registry)


def test_build_rejects_runner_evidence_artifact_mismatch() -> None:
    """runner_evidence harness must declare exact correct path, not just pattern."""
    harness = _minimal_harness(
        id="WF-HAR-STATIC-01",
        artifact_mode="runner_evidence",
        artifact=".omo/evidence/static/WF-HAR-STATIC-02.json",
    )
    registry = _minimal_registry(harness)
    with pytest.raises(HarnessRegistryError, match="does not match expected"):
        validate_registry(registry)
