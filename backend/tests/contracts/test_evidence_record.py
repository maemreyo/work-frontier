"""Tests for evidence record Pydantic models.

Tests validate that the Pydantic models match the JSON Schema exactly
and handle all required validation cases.
"""

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from work_frontier.contracts.evidence_record import EvidenceRecord

# Path to fixtures directory
FIXTURES_DIR = (
    Path(__file__).parent.parent.parent.parent / "contracts" / "fixtures" / "evidence"
)


def test_valid_minimal_fixture_validates() -> None:
    """Test that valid-minimal.json validates correctly."""
    # Given: a minimal valid fixture
    fixture_path = FIXTURES_DIR / "valid-minimal.json"
    with fixture_path.open() as f:
        data = cast("dict[str, object]", json.load(f))

    # When: validating via Pydantic
    record = EvidenceRecord.model_validate(data)

    # Then: all required fields are present and correct
    assert record.schema_version == "1.0.0"
    assert record.harness_id == "WF-HAR-PREFLIGHT-01"
    assert record.status == "pass"
    assert record.invocation.command == "pytest tests/unit"
    assert record.invocation.exit_code == 0
    assert record.tool.name == "pytest"
    assert record.tool.version == "8.2.0"
    assert record.tool.commit_sha == "a1b2c3d4e5f6789012345678901234567890abcd"
    assert record.environment["os"] == "linux-x86_64"
    assert record.artifacts == []
    assert record.results == []
    assert record.property_bag is None


def test_valid_full_fixture_validates() -> None:
    """Test that valid-full.json validates correctly."""
    # Given: a full valid fixture with all optional fields
    fixture_path = FIXTURES_DIR / "valid-full.json"
    with fixture_path.open() as f:
        data = cast("dict[str, object]", json.load(f))

    # When: validating via Pydantic
    record = EvidenceRecord.model_validate(data)

    # Then: all fields including optional ones are present and correct
    assert record.schema_version == "1.0.0"
    assert record.harness_id == "WF-HAR-CONTRACT-03"
    assert record.status == "fail"
    assert record.invocation.command == "mypy backend/app --strict"
    assert record.invocation.exit_code == 1
    assert record.invocation.working_directory == "."
    assert record.tool.name == "mypy"
    assert len(record.artifacts) == 1
    assert record.artifacts[0].path == "backend/app/models/user.py"
    assert record.artifacts[0].hashes is not None
    expected_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert record.artifacts[0].hashes["sha256"] == expected_sha
    assert len(record.results) == 2
    assert record.results[0].kind == "type_error"
    assert record.results[0].passed is False
    assert record.property_bag is not None
    assert record.property_bag["contract.service_name"] == "backend"


def test_roundtrip_minimal_preserves_data() -> None:
    """Test that fixture → Pydantic → dict → Pydantic → dict is stable."""
    # Given: a minimal fixture loaded once
    fixture_path = FIXTURES_DIR / "valid-minimal.json"
    with fixture_path.open() as f:
        original_data = cast("dict[str, object]", json.load(f))

    # When: roundtripping through Pydantic twice
    record1 = EvidenceRecord.model_validate(original_data)
    dict1 = record1.model_dump(mode="json")
    record2 = EvidenceRecord.model_validate(dict1)
    dict2 = record2.model_dump(mode="json")

    # Then: the two dict representations should be identical
    assert dict1 == dict2


def test_roundtrip_full_preserves_data() -> None:
    """Test that full fixture roundtrip preserves all data."""
    # Given: a full fixture with optional fields
    fixture_path = FIXTURES_DIR / "valid-full.json"
    with fixture_path.open() as f:
        original_data = cast("dict[str, object]", json.load(f))

    # When: roundtripping through Pydantic twice
    record1 = EvidenceRecord.model_validate(original_data)
    dict1 = record1.model_dump(mode="json")
    record2 = EvidenceRecord.model_validate(dict1)
    dict2 = record2.model_dump(mode="json")

    # Then: the two dict representations should be identical
    assert dict1 == dict2


def _base_valid_data() -> dict[str, object]:
    """Return minimally valid data dict (excluding the field under test)."""
    return {
        "schema_version": "1.0.0",
        "harness_id": "WF-HAR-PREFLIGHT-01",
        "status": "pass",
        "run_id": "run-test-001",
        "subject_sha": "a1b2c3d4e5f6789012345678901234567890abcd",
        "subject_tree_sha": "0123456789abcdef0123456789abcdef01234567",
        "invocation": {
            "command": "pytest tests/unit",
            "exit_code": 0,
            "working_directory": ".",
            "start_time": "2026-07-12T03:20:00Z",
            "end_time": "2026-07-12T03:20:15Z",
            "duration_seconds": 15.2,
        },
        "tool": {
            "name": "pytest",
            "version": "8.2.0",
            "commit_sha": "a1b2c3d4e5f6789012345678901234567890abcd",
        },
        "environment": {
            "os": "linux-x86_64",
            "python": "3.13.5",
        },
        "stdout_artifact": {
            "path": "stdout.txt",
            "hashes": {"sha256": "ab" * 32},
        },
        "stderr_artifact": {
            "path": "stderr.txt",
            "hashes": {"sha256": "ab" * 32},
        },
    }


def test_missing_required_field_raises_validation_error() -> None:
    """Test that missing required field raises ValidationError."""
    # Given: data missing the required 'status' field
    data = _base_valid_data()
    del data["status"]

    # When/Then: validation should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        _ = EvidenceRecord.model_validate(data)

    # And: the error should mention the missing field
    assert "status" in str(exc_info.value)


def test_invalid_harness_id_pattern_raises_validation_error() -> None:
    """Test that invalid harness_id pattern raises ValidationError."""
    # Given: data with invalid harness_id pattern (wrong prefix)
    data = _base_valid_data()
    data["harness_id"] = "INVALID-HARNESS-01"  # Invalid: wrong prefix

    # When/Then: validation should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        _ = EvidenceRecord.model_validate(data)

    # And: the error should mention harness_id pattern mismatch
    assert "harness_id" in str(exc_info.value)


def test_invalid_commit_sha_pattern_raises_validation_error() -> None:
    """Test that invalid commit_sha pattern raises ValidationError."""
    # Given: data with invalid commit_sha (not 40 hex chars)
    data = _base_valid_data()
    tool_data = cast("dict[str, object]", data["tool"])
    tool_data["commit_sha"] = "invalid-sha"

    # When/Then: validation should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        _ = EvidenceRecord.model_validate(data)

    # And: the error should mention commit_sha pattern mismatch
    assert "commit_sha" in str(exc_info.value)


def test_extra_field_in_evidence_record_raises_validation_error() -> None:
    """Test that extra fields are rejected due to extra='forbid'."""
    # Given: valid data with an extra unknown field
    fixture_path = FIXTURES_DIR / "valid-minimal.json"
    with fixture_path.open() as f:
        data = cast("dict[str, object]", json.load(f))
    data["unknown_field"] = "should_fail"

    # When/Then: validation should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        _ = EvidenceRecord.model_validate(data)

    # And: the error should mention extra fields not permitted
    error_msg = str(exc_info.value).lower()
    assert "extra" in error_msg or "unexpected" in error_msg


def test_negative_duration_raises_validation_error() -> None:
    """Test that negative duration_seconds raises ValidationError."""
    # Given: data with negative duration
    data = _base_valid_data()
    inv_data = cast("dict[str, object]", data["invocation"])
    inv_data["duration_seconds"] = -5.0

    # When/Then: validation should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        _ = EvidenceRecord.model_validate(data)

    # And: the error should mention duration constraint
    assert "duration_seconds" in str(exc_info.value)
