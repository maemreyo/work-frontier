"""Tests for evidence record Pydantic models.

Tests validate that the Pydantic models match the JSON Schema exactly
and handle all required validation cases.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from work_frontier.contracts.evidence_record import (
    Artifact,
    ArtifactHashes,
    EvidenceRecord,
    Invocation,
)

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


@pytest.mark.parametrize(
    "working_directory",
    ["/absolute/path", "build/../outside"],
)
def test_invocation_rejects_non_portable_working_directory(
    working_directory: str,
) -> None:
    with pytest.raises(ValidationError, match="working_directory"):
        _ = Invocation(
            command="true",
            exit_code=0,
            working_directory=working_directory,
            start_time=datetime(2026, 7, 12, 10, 0, 0, tzinfo=UTC),
            end_time=datetime(2026, 7, 12, 10, 0, 1, tzinfo=UTC),
            duration_seconds=1.0,
        )


def test_artifact_rejects_absolute_path() -> None:
    """Test that artifact with absolute path raises ValidationError."""
    # Given/When/Then
    with pytest.raises(ValidationError, match="pattern"):
        _ = Artifact(path="/etc/passwd", hashes=ArtifactHashes(sha256="ab" * 32))


def test_artifact_rejects_traversal_path() -> None:
    """Test that artifact with traversal path raises ValidationError."""
    # Given/When/Then
    with pytest.raises(ValidationError, match="artifact path"):
        _ = Artifact(
            path="../outside/file.txt", hashes=ArtifactHashes(sha256="ab" * 32)
        )


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
    assert record.artifacts[0].hashes.sha256 == expected_sha
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
            "end_time": "2026-07-12T03:20:15.5Z",
            "duration_seconds": 15.5,
        },
        "tool": {
            "name": "pytest",
            "version": "8.2.0",
            "commit_sha": "a1b2c3d4e5f6789012345678901234567890abcd",
        },
        "applicability": "standard",
        "applicability_reason": "Standard foundation closure fixture",
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


# ---------------------------------------------------------------------------
# Fixture-inventory gate (shared cross-language corpus)
# ---------------------------------------------------------------------------

# The fixture inventory is the shared corpus that proves parity between
# Python and TypeScript runtimes. Every required fixture name must be
# present. For valid fixtures, a paired .canonical.sha256 golden hash
# attests deterministic serialization. If a required fixture is removed,
# the corpus shrinks silently and the cross-language gate stops exercising
# that coverage. Asserting the explicit set here makes the inventory an
# executable gate rather than a directory glob.
REQUIRED_VALID_FIXTURES: frozenset[str] = frozenset(
    {"valid-minimal.json", "valid-full.json", "valid-maximal.json"}
)
REQUIRED_INVALID_FIXTURES: frozenset[str] = frozenset(
    {
        "invalid-absolute-working-directory.json",
        "invalid-traversal-working-directory.json",
        "invalid-absolute-artifact-path.json",
        "invalid-traversal-artifact-path.json",
        "invalid-missing-environment-os.json",
        "invalid-pass-with-failing-result.json",
        "invalid-fail-zero-without-failing-result.json",
        "invalid-duration-mismatch.json",
        "invalid-not-applicable-short-reason.json",
    }
)
REQUIRED_FIXTURE_INVENTORY: frozenset[str] = (
    REQUIRED_VALID_FIXTURES | REQUIRED_INVALID_FIXTURES
)


def test_evidence_record_fixture_inventory_is_complete() -> None:
    """Assert the fixture corpus matches the required inventory exactly."""
    # Given the shared fixture corpus on disk
    on_disk = {path.name for path in FIXTURES_DIR.glob("*.json")}

    # When the test asserts the required inventory
    # Then every required fixture must be present and no extras allowed
    assert on_disk == REQUIRED_FIXTURE_INVENTORY, (
        f"fixture inventory drift: "
        f"missing={REQUIRED_FIXTURE_INVENTORY - on_disk}, "
        f"extra={on_disk - REQUIRED_FIXTURE_INVENTORY}"
    )


def test_evidence_record_valid_fixtures_have_golden_hashes() -> None:
    """Assert every valid fixture has a paired golden canonical hash."""
    # Given every required valid fixture
    # When the test asserts the paired canonical hash file
    for name in REQUIRED_VALID_FIXTURES:
        path = FIXTURES_DIR / name
        golden = path.with_suffix(".canonical.sha256")
        assert golden.exists(), f"missing golden hash for {name}"
        digest = golden.read_text(encoding="utf-8").strip()
        assert len(digest) == 64, f"golden hash for {name} is not a 64-char hex"
        _ = int(digest, 16)  # raises ValueError if not hex


def test_evidence_record_invalid_fixtures_cover_required_mutations() -> None:
    """Assert each mutation scenario is exercised by at least one fixture."""
    scenarios = {
        "absolute working directory": {"invalid-absolute-working-directory.json"},
        "traversal working directory": {"invalid-traversal-working-directory.json"},
        "absolute artifact path": {"invalid-absolute-artifact-path.json"},
        "traversal artifact path": {"invalid-traversal-artifact-path.json"},
        "missing environment.os": {"invalid-missing-environment-os.json"},
        "pass with failing result": {"invalid-pass-with-failing-result.json"},
        "fail with exit_code=0 and no failing result": {
            "invalid-fail-zero-without-failing-result.json"
        },
        "duration mismatch with timestamps": {"invalid-duration-mismatch.json"},
        "not_applicable with short reason": {
            "invalid-not-applicable-short-reason.json"
        },
    }

    # Then every required scenario must have at least one fixture
    for label, required_names in scenarios.items():
        on_disk = {path.name for path in FIXTURES_DIR.glob("*.json")}
        assert on_disk & required_names, f"no fixture covers {label}"


# ---------------------------------------------------------------------------
# Cross-language fixture consistency (shared corpus)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_file",
    sorted(FIXTURES_DIR.glob("valid-*.json")),
    ids=lambda p: p.name,
)
def test_evidence_record_valid_fixtures_cross_language_consistency(
    fixture_file: Path,
) -> None:
    """Valid fixtures must match their golden canonical hashes."""
    # Given a valid fixture
    json_str = fixture_file.read_text()

    # When validated by Pydantic
    record = EvidenceRecord.model_validate_json(json_str)

    # Then the canonical digest matches the golden hash
    dumped = record.model_dump(mode="json")
    canonical = json.dumps(dumped, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    golden_path = fixture_file.with_suffix(".canonical.sha256")
    assert golden_path.exists(), f"missing golden hash for {fixture_file.name}"
    assert digest == golden_path.read_text(encoding="utf-8").strip(), (
        f"canonical hash mismatch for {fixture_file.name}"
    )


@pytest.mark.parametrize(
    "fixture_file",
    sorted(FIXTURES_DIR.glob("invalid-*.json")),
    ids=lambda p: p.name,
)
def test_evidence_record_invalid_fixtures_rejected_by_pydantic(
    fixture_file: Path,
) -> None:
    """Invalid fixtures must be rejected by the Pydantic contract."""
    # Given an invalid fixture
    json_str = fixture_file.read_text()

    # When validated by Pydantic, it MUST raise ValidationError
    with pytest.raises(ValidationError):
        _ = EvidenceRecord.model_validate_json(json_str)


# ---------------------------------------------------------------------------
# Semantic validation tests — rules that JSON Schema cannot express
# ---------------------------------------------------------------------------
# The following validations involve arithmetic (duration_seconds vs
# start_time/end_time) or cross-field semantic constraints (status vs
# results).  JSON Schema 2020-12 cannot express these; they are implemented
# as Pydantic model_validators and tested below.  The frontend Zod schema
# accepts these values at the schema level but the application MUST enforce
# them at the business-logic layer.


def test_duration_mismatch_raises_validation_error() -> None:
    """duration_seconds must match end_time - start_time (arithmetic rule)."""
    # Given: a valid invocation where duration_seconds does not match
    # end_time - start_time (should be 75.0, not 99.0)
    with pytest.raises(ValidationError, match="duration_seconds"):
        _ = Invocation(
            command="true",
            exit_code=0,
            working_directory=".",
            start_time=datetime(2026, 7, 12, 10, 0, 0, tzinfo=UTC),
            end_time=datetime(2026, 7, 12, 10, 1, 15, tzinfo=UTC),
            duration_seconds=99.0,  # should be 75.0
        )


def test_duration_mismatch_in_evidence_record_raises_validation_error() -> None:
    """EvidenceRecord must reject duration mismatch inside Invocation."""
    # Given: a record where invocation.duration_seconds is wrong
    data = _base_valid_data()
    inv_data = cast("dict[str, object]", data["invocation"])
    inv_data["duration_seconds"] = 999.9  # should be 15.2

    # When/Then
    with pytest.raises(ValidationError, match="duration_seconds"):
        _ = EvidenceRecord.model_validate(data)


def test_pass_status_with_failing_result_raises_validation_error() -> None:
    """status=pass with any result.passed=False must be rejected."""
    # Given: status='pass' but a result has passed=False
    data = _base_valid_data()
    data["results"] = [
        {"kind": "unit_test", "passed": False, "detail": "test_foo failed"}
    ]

    # When/Then
    with pytest.raises(ValidationError, match="status is 'pass'"):
        _ = EvidenceRecord.model_validate(data)


def test_fail_status_with_exit_code_zero_and_no_failing_results_raises_validation_error() -> (  # noqa: E501
    None
):
    """status=fail with exit_code=0 and no failing result must be rejected."""
    # Given: status='fail', exit_code=0, but all results have passed=True
    data = _base_valid_data()
    data["status"] = "fail"
    inv_data = cast("dict[str, object]", data["invocation"])
    inv_data["exit_code"] = 0
    data["results"] = [
        {"kind": "unit_test", "passed": True, "detail": "test_bar passed"}
    ]

    # When/Then
    with pytest.raises(ValidationError, match="status is 'fail'"):
        _ = EvidenceRecord.model_validate(data)


def test_fail_status_with_exit_code_nonzero_and_no_results_is_valid() -> None:
    """status=fail with non-zero exit_code and empty results is semantically valid.

    A harness may fail at the process level (non-zero exit) without
    having produced individual test results.  This is a valid state.
    """
    # Given: status='fail', exit_code=1, no results
    data = _base_valid_data()
    data["status"] = "fail"
    inv_data = cast("dict[str, object]", data["invocation"])
    inv_data["exit_code"] = 1
    data["results"] = []

    # When/Then
    _ = EvidenceRecord.model_validate(data)


@pytest.mark.parametrize(
    ("reason", "expected_valid"),
    [
        # status="pass" with any non-empty reason is valid
        ("Any reason works for non-not_applicable", True),
        # not_applicable with >=10 chars is valid
        ("Substantive reason that meets the ten char threshold", True),
        # not_applicable with <10 chars is invalid
        ("Too short", False),
        # not_applicable with exactly empty reason is invalid
        ("", False),
    ],
)
def test_applicability_reason_length_validation(
    reason: str, expected_valid: bool
) -> None:
    """not_applicable status requires >=10 char applicability_reason."""
    # Given: a record with the given status and reason
    data = _base_valid_data()
    data["status"] = "not_applicable"
    data["applicability_reason"] = reason

    # When/Then
    if expected_valid:
        _ = EvidenceRecord.model_validate(data)
    else:
        with pytest.raises(ValidationError, match="applicability_reason"):
            _ = EvidenceRecord.model_validate(data)
