"""Canonical immutable audit chains, anchors, and governed segment purge proofs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from datetime import datetime

GENESIS_CHECKSUM: Final = "0" * 64


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Canonical event input before sequence and checksum assignment."""

    event_id: str
    event_type: str
    actor: str
    subject_id: str | None
    causation_id: str
    correlation_id: str
    created_at: datetime
    payload: tuple[tuple[str, object], ...]

    def __post_init__(self) -> None:
        """Validate immutable event identities and canonicalize payload keys."""
        required = (
            self.event_id,
            self.event_type,
            self.actor,
            self.causation_id,
            self.correlation_id,
        )
        if any(not value.strip() for value in required):
            msg = "audit event identities must not be blank"
            raise ValueError(msg)
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            msg = "audit event timestamp must be timezone-aware"
            raise ValueError(msg)
        ordered = tuple(sorted(self.payload))
        if len(ordered) != len({key for key, _ in ordered}):
            msg = "audit payload keys must be unique"
            raise ValueError(msg)
        object.__setattr__(self, "payload", ordered)


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """One immutable checksummed event in a workspace segment."""

    tenant_id: str
    workspace_id: str
    segment_id: str
    seq: int
    event: AuditEvent
    payload_hash: str
    previous_checksum: str
    checksum: str


@dataclass(frozen=True, slots=True)
class AuditSegment:
    """Workspace-scoped append-only audit segment."""

    tenant_id: str
    workspace_id: str
    segment_id: str
    entries: tuple[AuditEntry, ...]
    closed: bool
    final_checksum: str

    @classmethod
    def open(cls, tenant_id: str, workspace_id: str, segment_id: str) -> AuditSegment:
        """Create an empty open segment with the zero genesis hash."""
        if not tenant_id.strip() or not workspace_id.strip() or not segment_id.strip():
            msg = "audit segment scope and identity are required"
            raise ValueError(msg)
        return cls(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            segment_id=segment_id,
            entries=(),
            closed=False,
            final_checksum=GENESIS_CHECKSUM,
        )

    def close(self) -> AuditSegment:
        """Close the segment against further append operations."""
        if not self.entries:
            msg = "empty audit segments cannot be closed"
            raise ValueError(msg)
        return replace(self, closed=True)


@dataclass(frozen=True, slots=True)
class SignedAnchor:
    """External signed-anchor proof for one complete segment checksum."""

    segment_id: str
    segment_checksum: str
    signer: str
    signature: str

    @classmethod
    def sign_for_test(cls, segment: AuditSegment, signer: str) -> SignedAnchor:
        """Create a deterministic test anchor; production uses a signing port."""
        if not segment.closed or not signer.strip():
            msg = "only closed segments with a signer can be anchored"
            raise ValueError(msg)
        signature = _sha256(f"{segment.segment_id}:{segment.final_checksum}:{signer}")
        return cls(segment.segment_id, segment.final_checksum, signer, signature)

    def verifies(self, segment: AuditSegment) -> bool:
        """Verify anchor identity, checksum, and deterministic signature."""
        expected = _sha256(f"{self.segment_id}:{self.segment_checksum}:{self.signer}")
        return (
            self.segment_id == segment.segment_id
            and self.segment_checksum == segment.final_checksum
            and self.signature == expected
        )


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Structured audit-chain verification outcome."""

    valid: bool
    failure: str | None = None


@dataclass(frozen=True, slots=True)
class DeletionProof:
    """Proof that a complete governed segment, not selected entries, was purged."""

    tenant_id: str
    workspace_id: str
    segment_id: str
    segment_checksum: str
    entry_count: int
    policy_id: str
    authorized_by: str
    purged_at: datetime
    anchor_signature: str
    proof_hash: str


def append_event(segment: AuditSegment, event: AuditEvent) -> AuditSegment:
    """Append one event and return a new immutable segment value."""
    if segment.closed:
        msg = "closed audit segments are immutable"
        raise ValueError(msg)
    if any(entry.event.event_id == event.event_id for entry in segment.entries):
        msg = "event_id must be unique within a segment"
        raise ValueError(msg)
    seq = len(segment.entries) + 1
    payload_hash = _sha256(_canonical_json(dict(event.payload)))
    previous_checksum = segment.final_checksum
    envelope = {
        "actor": event.actor,
        "causation_id": event.causation_id,
        "correlation_id": event.correlation_id,
        "created_at": event.created_at.isoformat(),
        "event_id": event.event_id,
        "event_type": event.event_type,
        "segment_id": segment.segment_id,
        "seq": seq,
        "subject_id": event.subject_id,
        "tenant_id": segment.tenant_id,
        "workspace_id": segment.workspace_id,
    }
    checksum = _sha256(previous_checksum + _canonical_json(envelope) + payload_hash)
    entry = AuditEntry(
        tenant_id=segment.tenant_id,
        workspace_id=segment.workspace_id,
        segment_id=segment.segment_id,
        seq=seq,
        event=event,
        payload_hash=payload_hash,
        previous_checksum=previous_checksum,
        checksum=checksum,
    )
    return replace(
        segment,
        entries=(*segment.entries, entry),
        final_checksum=checksum,
    )


def _entry_failure(
    segment: AuditSegment,
    entry: AuditEntry,
    expected_seq: int,
    previous_checksum: str,
    event_ids: set[str],
) -> tuple[str | None, str]:
    """Return the first integrity failure and expected checksum for one entry."""
    payload_hash = _sha256(_canonical_json(dict(entry.event.payload)))
    envelope = {
        "actor": entry.event.actor,
        "causation_id": entry.event.causation_id,
        "correlation_id": entry.event.correlation_id,
        "created_at": entry.event.created_at.isoformat(),
        "event_id": entry.event.event_id,
        "event_type": entry.event.event_type,
        "segment_id": segment.segment_id,
        "seq": entry.seq,
        "subject_id": entry.event.subject_id,
        "tenant_id": segment.tenant_id,
        "workspace_id": segment.workspace_id,
    }
    checksum = _sha256(previous_checksum + _canonical_json(envelope) + payload_hash)
    if entry.seq != expected_seq:
        return "sequence_mismatch", checksum
    if entry.event.event_id in event_ids:
        return "duplicate_event_id", checksum
    if entry.previous_checksum != previous_checksum:
        return "previous_checksum_mismatch", checksum
    if entry.payload_hash != payload_hash:
        return "payload_hash_mismatch", checksum
    if entry.checksum != checksum:
        return "checksum_mismatch", checksum
    return None, checksum


def verify_segment(
    segment: AuditSegment,
    *,
    anchor: SignedAnchor | None = None,
    require_external_anchor: bool = False,
) -> VerificationResult:
    """Verify payload, envelope, actor, timestamp, sequence, and anchor integrity."""
    previous = GENESIS_CHECKSUM
    event_ids: set[str] = set()
    failure: str | None = None
    for expected_seq, entry in enumerate(segment.entries, start=1):
        failure, checksum = _entry_failure(
            segment,
            entry,
            expected_seq,
            previous,
            event_ids,
        )
        if failure is not None:
            break
        event_ids.add(entry.event.event_id)
        previous = checksum

    anchor_valid = anchor is not None and anchor.verifies(segment)
    if failure is None and previous != segment.final_checksum:
        failure = "final_checksum_mismatch"
    elif failure is None and require_external_anchor and not anchor_valid:
        failure = "external_anchor_required"
    elif failure is None and anchor is not None and not anchor_valid:
        failure = "invalid_external_anchor"
    return VerificationResult(valid=failure is None, failure=failure)


def purge_segment(
    segment: AuditSegment,
    *,
    anchor: SignedAnchor | None,
    policy_id: str,
    authorized_by: str,
    purged_at: datetime,
) -> DeletionProof:
    """Authorize only whole, closed, externally anchored segment deletion."""
    if not segment.closed:
        msg = "only closed audit segments can be purged"
        raise ValueError(msg)
    if purged_at.tzinfo is None or purged_at.utcoffset() is None:
        msg = "purged_at must be timezone-aware"
        raise ValueError(msg)
    if not policy_id.strip() or not authorized_by.strip():
        msg = "purge policy and actor are required"
        raise ValueError(msg)
    verification = verify_segment(
        segment,
        anchor=anchor,
        require_external_anchor=True,
    )
    if not verification.valid or anchor is None:
        raise ValueError(verification.failure or "invalid audit segment")
    payload = {
        "anchor_signature": anchor.signature,
        "authorized_by": authorized_by,
        "entry_count": len(segment.entries),
        "policy_id": policy_id,
        "purged_at": purged_at.isoformat(),
        "segment_checksum": segment.final_checksum,
        "segment_id": segment.segment_id,
        "tenant_id": segment.tenant_id,
        "workspace_id": segment.workspace_id,
    }
    return DeletionProof(
        tenant_id=segment.tenant_id,
        workspace_id=segment.workspace_id,
        segment_id=segment.segment_id,
        segment_checksum=segment.final_checksum,
        entry_count=len(segment.entries),
        policy_id=policy_id,
        authorized_by=authorized_by,
        purged_at=purged_at,
        anchor_signature=anchor.signature,
        proof_hash=_sha256(_canonical_json(payload)),
    )
