from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from work_frontier.contracts import DecisionRecordContract

HASH = "a" * 64
FIXTURES_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "contracts"
    / "fixtures"
    / "decision-record"
)


def test_decision_record_round_trip_when_complete_envelope_is_supplied() -> None:
    # Given a complete canonical DecisionRecord envelope
    record = DecisionRecordContract(
        decision_id="decision-01",
        workspace_id="workspace-01",
        program_id=None,
        item_id="item-01",
        computed_at=datetime(2026, 7, 12, tzinfo=UTC),
        causation_id="event-01",
        correlation_id="trace-01",
        normalized_snapshot_id="snapshot-01",
        normalized_snapshot_hash=HASH,
        source_revision_set={"github:issue:1": "revision-01"},  # pyright: ignore[reportArgumentType]
        graph_revision="graph-01",
        policy_bundle_id="policy-01",
        policy_bundle_hash=HASH,
        ranking_pipeline_hash=HASH,
        engine_version="engine-01",
        normalization_profile_version="profile-01",
        ready=True,
        ranking_position=1,
    )

    # When it crosses the JSON transport boundary
    restored = DecisionRecordContract.model_validate_json(record.model_dump_json())

    # Then the immutable contract is unchanged
    assert restored == record


def test_decision_record_rejects_missing_workspace_when_validated() -> None:
    # Given a complete envelope with its mandatory workspace field removed
    payload = (
        '{"decision_id":"decision-01","program_id":null,"item_id":"item-01",'
        '"computed_at":"2026-07-12T00:00:00Z","causation_id":"event-01",'
        '"correlation_id":"trace-01","normalized_snapshot_id":"snapshot-01",'
        f'"normalized_snapshot_hash":"{HASH}",'
        '"source_revision_set":{"github:issue:1":"revision-01"},'
        '"graph_revision":"graph-01","policy_bundle_id":"policy-01",'
        f'"policy_bundle_hash":"{HASH}","ranking_pipeline_hash":"{HASH}",'
        '"engine_version":"engine-01","normalization_profile_version":"profile-01",'
        '"ready":true,"ranking_position":1}'
    )

    # When the transport boundary validates the altered JSON
    # Then the reproducibility envelope is rejected
    with pytest.raises(ValidationError):
        _ = DecisionRecordContract.model_validate_json(payload)


def test_decision_record_source_revision_set_is_immutable() -> None:
    # Given a validated DecisionRecord
    record = DecisionRecordContract(
        decision_id="decision-01",
        workspace_id="workspace-01",
        program_id=None,
        item_id="item-01",
        computed_at=datetime(2026, 7, 12, tzinfo=UTC),
        causation_id="event-01",
        correlation_id="trace-01",
        normalized_snapshot_id="snapshot-01",
        normalized_snapshot_hash=HASH,
        source_revision_set={"github:issue:1": "revision-01", "backend": "abc123"},  # pyright: ignore[reportArgumentType]
        graph_revision="graph-01",
        policy_bundle_id="policy-01",
        policy_bundle_hash=HASH,
        ranking_pipeline_hash=HASH,
        engine_version="engine-01",
        normalization_profile_version="profile-01",
        ready=True,
        ranking_position=1,
    )

    # Then nested source revisions cannot be mutated after construction
    with pytest.raises(TypeError):
        record.source_revision_set["backend"] = "changed"  # pyright: ignore[reportIndexIssue]

    # And field reassignment is blocked by the frozen model
    with pytest.raises(ValidationError):
        record.source_revision_set = {"backend": "changed"}  # pyright: ignore[reportAttributeAccessIssue]


def test_decision_record_canonical_json_is_deterministic() -> None:
    # Given two identical DecisionRecord instances created independently
    record1 = DecisionRecordContract(
        decision_id="decision-01",
        workspace_id="workspace-01",
        program_id=None,
        item_id="item-01",
        computed_at=datetime(2026, 7, 12, 0, 0, 0, tzinfo=UTC),
        causation_id="event-01",
        correlation_id="trace-01",
        normalized_snapshot_id="snapshot-01",
        normalized_snapshot_hash=HASH,
        source_revision_set={"github:issue:1": "revision-01", "backend": "abc123"},  # pyright: ignore[reportArgumentType]
        graph_revision="graph-01",
        policy_bundle_id="policy-01",
        policy_bundle_hash=HASH,
        ranking_pipeline_hash=HASH,
        engine_version="engine-01",
        normalization_profile_version="profile-01",
        ready=True,
        ranking_position=1,
    )

    record2 = DecisionRecordContract(
        decision_id="decision-01",
        workspace_id="workspace-01",
        program_id=None,
        item_id="item-01",
        computed_at=datetime(2026, 7, 12, 0, 0, 0, tzinfo=UTC),
        causation_id="event-01",
        correlation_id="trace-01",
        normalized_snapshot_id="snapshot-01",
        normalized_snapshot_hash=HASH,
        source_revision_set={"backend": "abc123", "github:issue:1": "revision-01"},  # pyright: ignore[reportArgumentType]
        graph_revision="graph-01",
        policy_bundle_id="policy-01",
        policy_bundle_hash=HASH,
        ranking_pipeline_hash=HASH,
        engine_version="engine-01",
        normalization_profile_version="profile-01",
        ready=True,
        ranking_position=1,
    )

    # When both are serialized to canonical JSON
    canonical1 = record1.canonical_json()
    canonical2 = record2.canonical_json()

    # Then the serialized bytes are identical despite different field ordering
    assert canonical1 == canonical2

    # And the content-addressable hash is reproducible
    hash1 = sha256(canonical1.encode("utf-8")).hexdigest()
    hash2 = sha256(canonical2.encode("utf-8")).hexdigest()
    assert hash1 == hash2

    # And the golden hash matches the expected value for this exact payload
    expected_hash = "8bc408ea15bd0cdd4140db700fa28a8c87772e43ddbd7417b283c412712acc3a"
    assert hash1 == expected_hash


@pytest.mark.parametrize(
    "fixture_file",
    sorted(FIXTURES_DIR.glob("*.json")),
    ids=lambda p: p.name,
)
def test_decision_record_fixtures_cross_language_consistency(
    fixture_file: Path,
) -> None:
    # Given a shared fixture with expected validity encoded in filename
    json_str = fixture_file.read_text()
    expected_valid = fixture_file.name.startswith("valid-")

    # When the Pydantic contract validates it
    if expected_valid:
        result = DecisionRecordContract.model_validate_json(json_str)
        assert result is not None
        digest = sha256(result.canonical_json().encode("utf-8")).hexdigest()
        golden_path = fixture_file.with_suffix(".canonical.sha256")
        assert golden_path.exists(), f"missing golden hash for {fixture_file.name}"
        assert digest == golden_path.read_text(encoding="utf-8").strip()
    else:
        with pytest.raises(ValidationError):
            _ = DecisionRecordContract.model_validate_json(json_str)
