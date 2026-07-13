"""Strongly authenticated break-glass and governed retention policies."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta


class BreakGlassError(ValueError):
    """Signal an unsafe emergency-access or retention request."""


_MIN_REASON_LENGTH = 20
_MAX_DAILY_INVOCATIONS = 2

_FORBIDDEN_PERMISSIONS = frozenset(
    {
        "role.assign",
        "policy.configure",
        "connection.delete",
        "connection.configure",
    }
)


@dataclass(frozen=True, slots=True)
class BreakGlassRequest:
    """Explicit emergency request with strong reauthentication evidence."""

    actor: str
    permission: str
    reason: str
    reauthenticated: bool
    mfa_verified: bool
    confirmed: bool
    requested_at: datetime
    prior_invocations: tuple[datetime, ...]


@dataclass(frozen=True, slots=True)
class BreakGlassGrant:
    """Two-hour scoped emergency grant and mandatory review deadline."""

    grant_id: str
    actor: str
    permissions: tuple[str, ...]
    reason: str
    issued_at: datetime
    expires_at: datetime
    review_due_at: datetime


@dataclass(frozen=True, slots=True)
class RetentionSubject:
    """Personal data selected for governed anonymization."""

    subject_id: str
    email: str
    display_name: str
    metadata: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class RetentionProof:
    """PII-free immutable evidence of governed anonymization."""

    proof_id: str
    subject_fingerprint: str
    policy_id: str
    authorized_by: str
    anonymized_at: datetime
    removed_fields: tuple[str, ...]
    retained_metadata_keys: tuple[str, ...]

    def canonical_json(self) -> str:
        """Return stable proof JSON that intentionally excludes subject PII."""
        payload = {
            "anonymized_at": self.anonymized_at.isoformat(),
            "authorized_by": self.authorized_by,
            "policy_id": self.policy_id,
            "proof_id": self.proof_id,
            "removed_fields": list(self.removed_fields),
            "retained_metadata_keys": list(self.retained_metadata_keys),
            "subject_fingerprint": self.subject_fingerprint,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def authorize_break_glass(request: BreakGlassRequest) -> BreakGlassGrant:
    """Authorize only strongly authenticated, scoped, rate-limited emergencies."""
    _require_aware(request.requested_at, "requested_at")
    if not request.reauthenticated or not request.mfa_verified:
        msg = "strong reauthentication and MFA are required"
        raise BreakGlassError(msg)
    if len(request.reason.strip()) < _MIN_REASON_LENGTH:
        msg = "break-glass reason must contain at least 20 characters"
        raise BreakGlassError(msg)
    if not request.confirmed:
        msg = "explicit emergency confirmation is required"
        raise BreakGlassError(msg)
    if request.permission in _FORBIDDEN_PERMISSIONS:
        msg = "requested operation is forbidden during break-glass"
        raise BreakGlassError(msg)
    cutoff = request.requested_at - timedelta(hours=24)
    recent = tuple(value for value in request.prior_invocations if value >= cutoff)
    if len(recent) >= _MAX_DAILY_INVOCATIONS:
        msg = "break-glass is limited to two invocations per 24 hours"
        raise BreakGlassError(msg)
    identity = (
        f"{request.actor}|{request.permission}|{request.requested_at.isoformat()}"
    )
    return BreakGlassGrant(
        grant_id=hashlib.sha256(identity.encode()).hexdigest()[:32],
        actor=request.actor,
        permissions=("read:workspace", request.permission),
        reason=request.reason.strip(),
        issued_at=request.requested_at,
        expires_at=request.requested_at + timedelta(hours=2),
        review_due_at=request.requested_at + timedelta(hours=48),
    )


def anonymize_subject(
    subject: RetentionSubject,
    *,
    policy_id: str,
    authorized_by: str,
    anonymized_at: datetime,
) -> RetentionProof:
    """Remove direct PII and emit a non-reversible policy proof."""
    _require_aware(anonymized_at, "anonymized_at")
    fingerprint_payload = f"{subject.subject_id}|{subject.email}|{subject.display_name}"
    fingerprint = hashlib.sha256(fingerprint_payload.encode()).hexdigest()
    proof_payload = (
        f"{fingerprint}|{policy_id}|{authorized_by}|{anonymized_at.isoformat()}"
    )
    return RetentionProof(
        proof_id=hashlib.sha256(proof_payload.encode()).hexdigest()[:32],
        subject_fingerprint=fingerprint,
        policy_id=policy_id,
        authorized_by=authorized_by,
        anonymized_at=anonymized_at,
        removed_fields=("display_name", "email", "subject_id"),
        retained_metadata_keys=tuple(sorted(key for key, _ in subject.metadata)),
    )


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        msg = f"{field} must be timezone-aware"
        raise BreakGlassError(msg)
