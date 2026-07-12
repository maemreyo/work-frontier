"""Verify ALLOW_MATRIX covers all 25 layer pairs explicitly."""

from __future__ import annotations

import pytest
from scripts.check_import_boundaries import ALLOW_MATRIX

LAYERS: tuple[str, ...] = ("domain", "platform", "application", "adapters", "interfaces")


def test_matrix_is_complete() -> None:
    """Every layer must have entries for all 5 targets."""
    for source in LAYERS:
        assert source in ALLOW_MATRIX, f"Missing source layer: {source}"
        for target in LAYERS:
            assert target in ALLOW_MATRIX[source], f"Missing edge: {source} -> {target}"


@pytest.mark.parametrize("source,target", [(s, t) for s in LAYERS for t in LAYERS])
def test_all_25_pairs_have_bool_verdict(source: str, target: str) -> None:
    """Each of 25 layer pairs has an explicit allow/deny decision."""
    verdict = ALLOW_MATRIX[source][target]
    assert isinstance(verdict, bool), f"Edge {source}->{target} must be bool, got {type(verdict)}"
