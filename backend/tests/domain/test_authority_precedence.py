from datetime import UTC, datetime, timedelta
from itertools import permutations

import pytest
from hypothesis import given, strategies as st

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
    tuple(FreshnessRule(level, timedelta(hours=1)) for level in SourceLevel)
)


def observation(level: SourceLevel, value: str, source_id: str | None = None):
    resolved_source = source_id or level.name.lower()
    return SourceObservation(
        field="priority",
        value=value,
        source_level=level,
        source_id=resolved_source,
        observed_at=NOW - timedelta(minutes=5),
        authority=AuthorityStatus.PROVISIONAL
        if level is SourceLevel.INFERENCE
        else AuthorityStatus.AUTHORITATIVE,
        revision=SourceRevision(resolved_source, "r1"),
        expires_at=NOW + timedelta(minutes=30)
        if level is SourceLevel.HUMAN_OVERRIDE
        else None,
    )


@pytest.mark.parametrize("higher", tuple(SourceLevel))
@pytest.mark.parametrize("lower", tuple(SourceLevel))
def test_every_precedence_pair_selects_the_higher_level(
    higher: SourceLevel, lower: SourceLevel
) -> None:
    expected = max(higher, lower)
    result = reconcile_authority(
        field="priority",
        observations=(observation(higher, higher.name), observation(lower, lower.name)),
        now=NOW,
        freshness=POLICY,
    )
    assert result.selected is not None
    assert result.selected.source_level is expected


def test_conflict_is_surfaced_while_precedence_selects_current_value() -> None:
    result = reconcile_authority(
        field="priority",
        observations=(
            observation(SourceLevel.NATIVE_TRACKER, "low", "github"),
            observation(SourceLevel.HUMAN_OVERRIDE, "critical", "user-1"),
        ),
        now=NOW,
        freshness=POLICY,
        safety_critical=True,
    )
    assert result.value == "critical"
    assert result.status is AuthorityStatus.CONFLICTED
    assert result.conflict is not None
    assert {value.value for value in result.conflict.values} == {"low", "critical"}
    assert result.blocks_readiness is True
    assert result.attention[0].deterministic_basis == "distinct_source_values > 1"


def test_ordering_is_invariant_for_every_permutation() -> None:
    inputs = (
        observation(SourceLevel.PARSED_MARKDOWN, "medium", "markdown"),
        observation(SourceLevel.NATIVE_TRACKER, "high", "github"),
        observation(SourceLevel.CONFIGURED_POLICY, "critical", "policy"),
    )
    results = {
        reconcile_authority(
            field="priority",
            observations=tuple(order),
            now=NOW,
            freshness=POLICY,
        )
        for order in permutations(inputs)
    }
    assert len(results) == 1


@given(
    st.permutations(
        (
            SourceLevel.PARSED_MARKDOWN,
            SourceLevel.NATIVE_TRACKER,
            SourceLevel.CONFIGURED_POLICY,
        )
    )
)
def test_hypothesis_permutations_preserve_selected_value(
    ordered_levels: list[SourceLevel],
) -> None:
    observations = tuple(
        observation(level, level.name, f"source-{index}")
        for index, level in enumerate(ordered_levels)
    )
    result = reconcile_authority(
        field="priority",
        observations=observations,
        now=NOW,
        freshness=POLICY,
    )
    assert result.selected is not None
    assert result.selected.source_level is SourceLevel.CONFIGURED_POLICY


def test_authoritative_inference_is_rejected() -> None:
    with pytest.raises(DomainInvariantError) as exc:
        _ = SourceObservation(
            field="ranking",
            value=1,
            source_level=SourceLevel.INFERENCE,
            source_id="engine",
            observed_at=NOW,
            authority=AuthorityStatus.AUTHORITATIVE,
            revision=SourceRevision("engine", "r1"),
        )
    assert exc.value.code is DomainErrorCode.AUTHORITATIVE_INFERENCE
