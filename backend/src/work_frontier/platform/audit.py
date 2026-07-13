"""Canonical immutable audit chains, anchors, and governed segment purge proofs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Final

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
            raise ValueError("audit event identities must not be blank")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("audit event timestamp must be timezone-aware")
        ordered = tuple(sorted(self.payload))
        if len(ordered) != len({key for key, _ in ordered}):
            raise ValueError("audit payload keys must be unique")
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
            raise ValueError("audit segment scope and identity are required")
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
            raise ValueError("empty audit segments cannot be closed")
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
            raise ValueError("only closed segments with a signer can be anchored")
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
        raise ValueError("closed audit segments are immutable")
    if any(entry.event.event_id == event.event_id for entry in segment.entries):
        raise ValueError("event_id must be unique within a segment")
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


def verify_segment(
    segment: AuditSegment,
    *,
    anchor: SignedAnchor | None = None,
    require_external_anchor: bool = False,
) -> VerificationResult:
    """Verify payload, envelope, actor, timestamp, sequence, and anchor integrity."""
    previous = GENESIS_CHECKSUM
    event_ids: set[str] = set()
    for expected_seq, entry in enumerate(segment.entries, start=1):
        if entry.seq != expected_seq:
            return VerificationResult(False, "sequence_mismatch")
        if entry.event.event_id in event_ids:
            return VerificationResult(False, "duplicate_event_id")
        event_ids.add(entry.event.event_id)
        if entry.previous_checksum != previous:
            return VerificationResult(False, "previous_checksum_mismatch")
        payload_hash = _sha256(_canonical_json(dict(entry.event.payload)))
        if entry.payload_hash != payload_hash:
            return VerificationResult(False, "payload_hash_mismatch")
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
        checksum = _sha256(previous + _canonical_json(envelope) + payload_hash)
        if entry.checksum != checksum:
            return VerificationResult(False, "checksum_mismatch")
        previous = checksum
    if previous != segment.final_checksum:
        return VerificationResult(False, "final_checksum_mismatch")
    if require_external_anchor and (anchor is None or not anchor.verifies(segment)):
        return VerificationResult(False, "external_anchor_required")
    if anchor is not None and not anchor.verifies(segment):
        return VerificationResult(False, "invalid_external_anchor")
    return VerificationResult(True)


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
        raise ValueError("only closed audit segments can be purged")
    if purged_at.tzinfo is None or purged_at.utcoffset() is None:
        raise ValueError("purged_at must be timezone-aware")
    if not policy_id.strip() or not authorized_by.strip():
        raise ValueError("purge policy and actor are required")
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
