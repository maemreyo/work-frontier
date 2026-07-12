"""Tests for harness registry and runner certification rules."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from work_frontier.contracts.evidence_record import (
    Artifact,
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
        artifacts=[Artifact(path="x", hashes={"sha256": "b" * 64})],
        results=[Result(kind="test", passed=True)],
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
