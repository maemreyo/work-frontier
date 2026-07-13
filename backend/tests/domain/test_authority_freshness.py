from datetime import UTC, datetime, timedelta

import pytest

from work_frontier.domain.authority import (
    AuthorityStatus,
    FreshnessPolicy,
    FreshnessRule,
    SourceLevel,
    SourceObservation,
    SourceRevision,
    reconcile_authority,
)
from work_frontier.domain.errors import DomainErrorCode, DomainInvariantError

NOW = datetime(2026, 7, 13, 8, tzinfo=UTC)
POLICY = FreshnessPolicy(
    tuple(FreshnessRule(level, timedelta(minutes=30)) for level in SourceLevel)
)


def tracker_observation(
    *, observed_at: datetime, revision: str = "r1"
) -> SourceObservation:
    return SourceObservation(
        field="lifecycle",
        value="active",
        source_level=SourceLevel.NATIVE_TRACKER,
        source_id="github",
        observed_at=observed_at,
        authority=AuthorityStatus.AUTHORITATIVE,
        revision=SourceRevision("github", revision),
    )


def test_elapsed_ttl_downgrades_to_stale_and_emits_attention_basis() -> None:
    result = reconcile_authority(
        field="lifecycle",
        observations=(tracker_observation(observed_at=NOW - timedelta(hours=1)),),
        now=NOW,
        freshness=POLICY,
        safety_critical=True,
    )
    assert result.status is AuthorityStatus.STALE
    assert result.blocks_readiness is True
    assert result.attention[0].category == "authority_downgraded"
    assert "source_stale" in result.attention[0].deterministic_basis


def test_source_revision_mismatch_is_stale_even_inside_ttl() -> None:
    result = reconcile_authority(
        field="lifecycle",
        observations=(tracker_observation(observed_at=NOW, revision="r1"),),
        current_revisions=(SourceRevision("github", "r2"),),
        now=NOW,
        freshness=POLICY,
    )
    assert result.status is AuthorityStatus.STALE
    assert result.source_revisions == (SourceRevision("github", "r1"),)


def test_equal_values_do_not_create_a_conflict() -> None:
    tracker = tracker_observation(observed_at=NOW)
    metadata = SourceObservation(
        field="lifecycle",
        value="active",
        source_level=SourceLevel.STRUCTURED_METADATA,
        source_id="github-labels",
        observed_at=NOW,
        authority=AuthorityStatus.AUTHORITATIVE,
        revision=SourceRevision("github-labels", "r1"),
    )
    result = reconcile_authority(
        field="lifecycle",
        observations=(tracker, metadata),
        now=NOW,
        freshness=POLICY,
    )
    assert result.status is AuthorityStatus.AUTHORITATIVE
    assert result.conflict is None


def test_freshness_policy_requires_every_source_level() -> None:
    with pytest.raises(DomainInvariantError) as exc:
        _ = FreshnessPolicy(
            (FreshnessRule(SourceLevel.NATIVE_TRACKER, timedelta(minutes=10)),)
        )
    assert exc.value.code is DomainErrorCode.INVALID_FRESHNESS_POLICY


def test_human_override_requires_expiry() -> None:
    with pytest.raises(DomainInvariantError) as exc:
        _ = SourceObservation(
            field="priority",
            value="critical",
            source_level=SourceLevel.HUMAN_OVERRIDE,
            source_id="user-1",
            observed_at=NOW,
            authority=AuthorityStatus.AUTHORITATIVE,
            revision=SourceRevision("user-1", "r1"),
        )
    assert exc.value.code is DomainErrorCode.INVALID_PROVENANCE
