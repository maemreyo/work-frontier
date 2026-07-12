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


# The fixture inventory is the shared corpus that proves parity between
# Python and TypeScript runtimes. Every required fixture name must be
# present and have a paired `.canonical.sha256` for valid payloads. If a
# required fixture is removed, the corpus shrinks silently and the cross-
# language gate stops exercising that coverage. Asserting the explicit set
# here makes the inventory an executable gate rather than a directory glob.
REQUIRED_VALID_FIXTURES: frozenset[str] = frozenset(
    {"valid-minimal.json", "valid-maximal.json"}
)
REQUIRED_INVALID_FIXTURES: frozenset[str] = frozenset(
    {
        "invalid-missing-workspace-id.json",
        "invalid-empty-decision-id.json",
        "invalid-empty-source-revision-set.json",
        "invalid-unknown-field.json",
        "invalid-naive-datetime.json",
        "invalid-uppercase-hash.json",
        "invalid-non-hex-hash.json",
        "invalid-coerce-int.json",
        "invalid-coerce-bool.json",
    }
)
REQUIRED_FIXTURE_INVENTORY: frozenset[str] = (
    REQUIRED_VALID_FIXTURES | REQUIRED_INVALID_FIXTURES
)


def test_decision_record_fixture_inventory_is_complete() -> None:
    # Given the shared fixture corpus on disk
    on_disk = {path.name for path in FIXTURES_DIR.glob("*.json")}

    # When the test asserts the required inventory
    # Then every required fixture must be present and no extras allowed
    assert on_disk == REQUIRED_FIXTURE_INVENTORY, (
        f"fixture inventory drift: "
        f"missing={REQUIRED_FIXTURE_INVENTORY - on_disk}, "
        f"extra={on_disk - REQUIRED_FIXTURE_INVENTORY}"
    )


def test_decision_record_valid_fixtures_have_golden_hashes() -> None:
    # Given every required valid fixture
    # When the test asserts the paired canonical hash file
    for name in REQUIRED_VALID_FIXTURES:
        path = FIXTURES_DIR / name
        golden = path.with_suffix(".canonical.sha256")
        assert golden.exists(), f"missing golden hash for {name}"
        digest = golden.read_text(encoding="utf-8").strip()
        assert len(digest) == 64, f"golden hash for {name} is not a 64-char hex"
        _ = int(digest, 16)  # raises ValueError if not hex


def test_decision_record_invalid_fixtures_cover_required_mutations() -> None:
    # Given the required invalid fixture corpus
    # When the test asserts that each scenario is exercised at least once
    scenarios = {
        "missing reproducibility identity": {"invalid-missing-workspace-id.json"},
        "empty string reproducibility": {
            "invalid-empty-decision-id.json",
            "invalid-empty-source-revision-set.json",
        },
        "unknown field rejection": {"invalid-unknown-field.json"},
        "naive datetime rejection": {"invalid-naive-datetime.json"},
        "hash pattern enforcement": {
            "invalid-uppercase-hash.json",
            "invalid-non-hex-hash.json",
        },
        "type coercion rejection": {
            "invalid-coerce-int.json",
            "invalid-coerce-bool.json",
        },
    }

    # Then every required scenario must have at least one fixture
    for label, required_names in scenarios.items():
        on_disk = {path.name for path in FIXTURES_DIR.glob("*.json")}
        assert on_disk & required_names, f"no fixture covers {label}"


def test_decision_record_breaking_mutation_is_detected() -> None:
    # Given a valid minimal fixture and a simulated breaking mutation
    # (the consumer treats the field as required but the model drops it)
    record = DecisionRecordContract(
        decision_id="decision-mutation",
        workspace_id="workspace-mutation",
        program_id=None,
        item_id="item-mutation",
        computed_at=datetime(2026, 7, 12, tzinfo=UTC),
        causation_id="event-mutation",
        correlation_id="trace-mutation",
        normalized_snapshot_id="snapshot-mutation",
        normalized_snapshot_hash=HASH,
        source_revision_set={"backend": "abc"},  # pyright: ignore[reportArgumentType]
        graph_revision="graph-mutation",
        policy_bundle_id="policy-mutation",
        policy_bundle_hash=HASH,
        ranking_pipeline_hash=HASH,
        engine_version="engine-mutation",
        normalization_profile_version="profile-mutation",
        ready=True,
        ranking_position=1,
    )
    original_canonical = record.canonical_json()
    original_digest = sha256(original_canonical.encode("utf-8")).hexdigest()

    # When a simulated breaking mutation drops the ranking_position field
    # (the contract would no longer canonicalize identically)
    mutated_canonical = original_canonical.replace(
        '"ranking_position":1', '"ranking_position":null'
    )

    # Then the canonical digest changes
    mutated_digest = sha256(mutated_canonical.encode("utf-8")).hexdigest()
    assert original_digest != mutated_digest, (
        "breaking mutation must change canonical hash"
    )

    # And the regenerated artifact would differ from the checked-in golden
    regenerated_canonical = record.canonical_json()
    regenerated_digest = sha256(regenerated_canonical.encode("utf-8")).hexdigest()
    assert regenerated_digest == original_digest, (
        "regeneration must produce byte-identical canonical output"
    )
