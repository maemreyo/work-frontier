from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from work_frontier.contracts import DecisionRecordContract

HASH = "a" * 64


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
        source_revision_set={"github:issue:1": "revision-01"},
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
