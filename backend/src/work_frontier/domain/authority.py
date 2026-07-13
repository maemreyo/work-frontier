"""Deterministic authority precedence, freshness, conflict, and attention semantics."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum, StrEnum

from work_frontier.domain.errors import DomainErrorCode, DomainInvariantError

AuthorityValue = str | int | float | bool | None | tuple[str, ...]


class SourceLevel(IntEnum):
    """Six-level source precedence; larger values win."""

    INFERENCE = 1
    PARSED_MARKDOWN = 2
    STRUCTURED_METADATA = 3
    NATIVE_TRACKER = 4
    CONFIGURED_POLICY = 5
    HUMAN_OVERRIDE = 6


class AuthorityStatus(StrEnum):
    """Canonical trust states."""

    AUTHORITATIVE = "authoritative"
    PROVISIONAL = "provisional"
    STALE = "stale"
    CONFLICTED = "conflicted"
    UNAVAILABLE = "unavailable"


class ConflictResolution(StrEnum):
    """Conflict resolution lifecycle."""

    PENDING = "pending"
    AUTO_RESOLVED = "auto_resolved"
    WAIVED = "waived"


class AttentionSeverity(StrEnum):
    """Severity for deterministic attention bases."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True, order=True)
class SourceRevision:
    """Revision identity for one source input."""

    source_id: str
    revision: str

    def __post_init__(self) -> None:
        """Validate non-empty source and revision identities."""
        if not self.source_id.strip() or not self.revision.strip():
            raise DomainInvariantError(
                DomainErrorCode.INVALID_PROVENANCE,
                "source_revision",
                "source_id and revision are required",
            )


@dataclass(frozen=True, slots=True)
class SourceObservation:
    """One field value with authority and revision provenance."""

    field: str
    value: AuthorityValue
    source_level: SourceLevel
    source_id: str
    observed_at: datetime
    authority: AuthorityStatus
    revision: SourceRevision
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate timestamp, provenance, and source-authority invariants."""
        _require_aware(self.observed_at, "observed_at")
        if self.expires_at is not None:
            _require_aware(self.expires_at, "expires_at")
        if not self.field.strip() or not self.source_id.strip():
            raise DomainInvariantError(
                DomainErrorCode.INVALID_PROVENANCE,
                "field",
                "field and source_id are required",
            )
        if self.revision.source_id != self.source_id:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_PROVENANCE,
                "revision.source_id",
                "must match observation source_id",
            )
        if self.source_level is SourceLevel.HUMAN_OVERRIDE and self.expires_at is None:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_PROVENANCE,
                "expires_at",
                "human overrides must be time-bounded",
            )
        if (
            self.source_level is SourceLevel.INFERENCE
            and self.authority is AuthorityStatus.AUTHORITATIVE
        ):
            raise DomainInvariantError(
                DomainErrorCode.AUTHORITATIVE_INFERENCE,
                "authority",
                "inference cannot claim authoritative status",
            )


@dataclass(frozen=True, slots=True)
class FreshnessRule:
    """Configured maximum age for a source level."""

    source_level: SourceLevel
    max_age: timedelta

    def __post_init__(self) -> None:
        """Validate that the configured maximum age is positive."""
        if self.max_age <= timedelta(0):
            raise DomainInvariantError(
                DomainErrorCode.INVALID_FRESHNESS_POLICY,
                "max_age",
                "must be positive",
            )


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    """Complete configurable freshness policy for all source levels."""

    rules: tuple[FreshnessRule, ...]

    def __post_init__(self) -> None:
        """Require exactly one freshness rule for every source level."""
        levels = tuple(rule.source_level for rule in self.rules)
        if len(levels) != len(set(levels)) or set(levels) != set(SourceLevel):
            raise DomainInvariantError(
                DomainErrorCode.INVALID_FRESHNESS_POLICY,
                "rules",
                "exactly one rule is required for every source level",
            )

    def max_age_for(self, source_level: SourceLevel) -> timedelta:
        """Return configured maximum age for a source level."""
        for rule in self.rules:
            if rule.source_level is source_level:
                return rule.max_age
        msg = "FreshnessPolicy invariant was bypassed"
        raise AssertionError(msg)


@dataclass(frozen=True, slots=True)
class ConflictValue:
    """One surfaced value in a conflict."""

    value: AuthorityValue
    source_level: SourceLevel
    source_id: str
    revision: SourceRevision


@dataclass(frozen=True, slots=True)
class ConflictDetail:
    """All disagreeing values for one field."""

    field: str
    values: tuple[ConflictValue, ...]
    resolution: ConflictResolution = ConflictResolution.PENDING
    resolved_by: str | None = None
    resolved_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AttentionBasis:
    """Deterministic basis for a later AttentionItem emission."""

    category: str
    severity: AttentionSeverity
    field: str
    deterministic_basis: str


@dataclass(frozen=True, slots=True)
class AuthorityResolution:
    """Deterministic current value plus surfaced authority state."""

    field: str
    value: AuthorityValue
    status: AuthorityStatus
    selected: SourceObservation | None
    provenance: tuple[SourceObservation, ...]
    conflict: ConflictDetail | None
    source_revisions: tuple[SourceRevision, ...]
    attention: tuple[AttentionBasis, ...]
    blocks_readiness: bool


def reconcile_authority(  # noqa: PLR0913 - explicit domain inputs are auditable
    *,
    field: str,
    observations: tuple[SourceObservation, ...],
    now: datetime,
    freshness: FreshnessPolicy,
    current_revisions: tuple[SourceRevision, ...] = (),
    safety_critical: bool = False,
) -> AuthorityResolution:
    """Resolve one field deterministically while surfacing conflicts and staleness."""
    _require_aware(now, "now")
    if any(observation.field != field for observation in observations):
        raise DomainInvariantError(
            DomainErrorCode.INVALID_PROVENANCE,
            "field",
            "all observations must describe the requested field",
        )
    if not observations:
        unavailable_attention = (
            AttentionBasis(
                category="authority_downgraded",
                severity=AttentionSeverity.WARNING,
                field=field,
                deterministic_basis="no_source_observations",
            ),
        )
        return AuthorityResolution(
            field=field,
            value=None,
            status=AuthorityStatus.UNAVAILABLE,
            selected=None,
            provenance=(),
            conflict=None,
            source_revisions=(),
            attention=unavailable_attention,
            blocks_readiness=safety_critical,
        )

    current_by_source = {
        revision.source_id: revision.revision for revision in current_revisions
    }
    ordered = tuple(sorted(observations, key=_observation_sort_key))
    selected = ordered[0]
    stale = _is_stale(selected, now, freshness, current_by_source)
    distinct_values = {_canonical_value(item.value) for item in ordered}

    conflict: ConflictDetail | None = None
    attention_items: list[AttentionBasis] = []
    if len(distinct_values) > 1:
        conflict = ConflictDetail(
            field=field,
            values=tuple(
                ConflictValue(
                    value=item.value,
                    source_level=item.source_level,
                    source_id=item.source_id,
                    revision=item.revision,
                )
                for item in ordered
            ),
        )
        status = AuthorityStatus.CONFLICTED
        attention_items.append(
            AttentionBasis(
                category="authority_downgraded",
                severity=AttentionSeverity.WARNING,
                field=field,
                deterministic_basis="distinct_source_values > 1",
            )
        )
    elif stale:
        status = AuthorityStatus.STALE
        attention_items.append(
            AttentionBasis(
                category="authority_downgraded",
                severity=AttentionSeverity.WARNING,
                field=field,
                deterministic_basis=(
                    f"source_stale(source_id={selected.source_id},"
                    f"revision={selected.revision.revision})"
                ),
            )
        )
    elif selected.authority is AuthorityStatus.PROVISIONAL:
        status = AuthorityStatus.PROVISIONAL
    else:
        status = AuthorityStatus.AUTHORITATIVE

    revisions = tuple(sorted({item.revision for item in ordered}))
    blocks_readiness = safety_critical and status in {
        AuthorityStatus.STALE,
        AuthorityStatus.CONFLICTED,
        AuthorityStatus.UNAVAILABLE,
    }
    return AuthorityResolution(
        field=field,
        value=selected.value,
        status=status,
        selected=selected,
        provenance=ordered,
        conflict=conflict,
        source_revisions=revisions,
        attention=tuple(attention_items),
        blocks_readiness=blocks_readiness,
    )


def _observation_sort_key(
    observation: SourceObservation,
) -> tuple[int, str, str, str, str]:
    return (
        -int(observation.source_level),
        observation.source_id,
        observation.revision.revision,
        observation.observed_at.isoformat(),
        _canonical_value(observation.value),
    )


def _canonical_value(value: AuthorityValue) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _is_stale(
    observation: SourceObservation,
    now: datetime,
    freshness: FreshnessPolicy,
    current_by_source: dict[str, str],
) -> bool:
    if now - observation.observed_at > freshness.max_age_for(observation.source_level):
        return True
    if observation.expires_at is not None and now >= observation.expires_at:
        return True
    current_revision = current_by_source.get(observation.source_id)
    return (
        current_revision is not None
        and current_revision != observation.revision.revision
    )


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainInvariantError(
            DomainErrorCode.INVALID_TIMESTAMP,
            field,
            "timezone-aware datetime required",
        )
