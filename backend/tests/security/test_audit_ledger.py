from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from work_frontier.platform.audit import (
    AuditEvent,
    AuditSegment,
    SignedAnchor,
    append_event,
    purge_segment,
    verify_segment,
)


def event(event_id: str, payload: tuple[tuple[str, object], ...]) -> AuditEvent:
    return AuditEvent(
        event_id=event_id,
        event_type="tested",
        actor="system:test",
        subject_id="item-1",
        causation_id="cause-1",
        correlation_id="corr-1",
        created_at=datetime(2026, 7, 13, tzinfo=UTC),
        payload=payload,
    )


def test_chain_detects_payload_actor_timestamp_and_order_tampering() -> None:
    segment = AuditSegment.open("tenant", "workspace", "segment-1")
    segment = append_event(segment, event("e1", (("value", 1),)))
    segment = append_event(segment, event("e2", (("value", 2),)))
    assert verify_segment(segment).valid is True

    first = segment.entries[0]
    tampered = replace(first, event=replace(first.event, actor="attacker"))
    result = verify_segment(replace(segment, entries=(tampered, *segment.entries[1:])))
    assert result.valid is False

    reordered = replace(segment, entries=tuple(reversed(segment.entries)))
    assert verify_segment(reordered).valid is False


def test_privileged_threat_profile_requires_external_anchor() -> None:
    segment = append_event(
        AuditSegment.open("tenant", "workspace", "segment-1"),
        event("e1", (("value", 1),)),
    ).close()
    assert verify_segment(segment, require_external_anchor=True).valid is False
    anchor = SignedAnchor.sign_for_test(segment, signer="test-root")
    assert (
        verify_segment(
            segment,
            anchor=anchor,
            require_external_anchor=True,
        ).valid
        is True
    )


def test_segment_purge_is_whole_segment_only_and_emits_deletion_proof() -> None:
    segment = append_event(
        AuditSegment.open("tenant", "workspace", "segment-1"),
        event("e1", (("value", 1),)),
    ).close()
    anchor = SignedAnchor.sign_for_test(segment, signer="test-root")
    proof = purge_segment(
        segment,
        anchor=anchor,
        policy_id="retention-365d",
        authorized_by="admin-1",
        purged_at=datetime(2027, 7, 14, tzinfo=UTC),
    )
    assert proof.segment_id == segment.segment_id
    assert proof.entry_count == 1
    assert proof.segment_checksum == segment.final_checksum


def test_open_or_unanchored_segment_cannot_be_purged() -> None:
    open_segment = append_event(
        AuditSegment.open("tenant", "workspace", "segment-1"),
        event("e1", (("value", 1),)),
    )
    with pytest.raises(ValueError, match="only closed audit segments"):
        _ = purge_segment(
            open_segment,
            anchor=None,
            policy_id="retention",
            authorized_by="admin",
            purged_at=datetime(2027, 7, 14, tzinfo=UTC),
        )

    closed_segment = open_segment.close()
    with pytest.raises(ValueError, match="external_anchor_required"):
        _ = purge_segment(
            closed_segment,
            anchor=None,
            policy_id="retention",
            authorized_by="admin",
            purged_at=datetime(2027, 7, 14, tzinfo=UTC),
        )
