"""Verify ALLOW_MATRIX covers all 36 layer pairs and is behaviorally enforced."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest
from scripts.check_import_boundaries import ALLOW_MATRIX, validate

LAYERS: tuple[str, ...] = (
    "domain",
    "platform",
    "application",
    "adapters",
    "interfaces",
    "contracts",
)

PORTS_EXCEPTION_SOURCES: frozenset[str] = frozenset({"platform", "adapters"})


def test_matrix_is_complete() -> None:
    """Every layer must have entries for all 6 targets."""
    for source in LAYERS:
        assert source in ALLOW_MATRIX, f"Missing source layer: {source}"
        for target in LAYERS:
            assert target in ALLOW_MATRIX[source], f"Missing edge: {source} -> {target}"


@pytest.mark.parametrize(("source", "target"), [(s, t) for s in LAYERS for t in LAYERS])
def test_all_36_pairs_have_bool_verdict(source: str, target: str) -> None:
    """Each of 36 layer pairs has an explicit allow/deny decision."""
    verdict = ALLOW_MATRIX[source][target]
    assert isinstance(verdict, bool), (
        f"Edge {source}->{target} must be bool, got {type(verdict)}"
    )


@pytest.mark.parametrize(("source", "target"), [(s, t) for s in LAYERS for t in LAYERS])
def test_all_36_pairs_enforced_by_source_injection(
    source: str, target: str, tmp_path: Path
) -> None:
    """Inject a real import for every matrix cell and assert checker verdict."""
    pkg = tmp_path / "work_frontier"
    source_dir = pkg / source
    source_dir.mkdir(parents=True)
    module_path = source_dir / "probe.py"
    _ = module_path.write_text(
        f"from work_frontier.{target} import probe\n",
        encoding="utf-8",
    )

    violations = validate(tmp_path)
    matrix_allowed = ALLOW_MATRIX[source][target]
    has_violation = any(
        v.path == module_path and v.rule != "unknown-source-layer" for v in violations
    )

    if matrix_allowed:
        assert not has_violation, (
            f"Expected allow {source}->{target}, got {[v.rule for v in violations]}"
        )
    else:
        assert has_violation, (
            f"Expected deny {source}->{target}, got no matrix violation"
        )


@pytest.mark.parametrize("source", sorted(PORTS_EXCEPTION_SOURCES))
def test_ports_exception_allows_application_ports(source: str, tmp_path: Path) -> None:
    """Platform/adapters may import application.ports despite matrix deny."""
    pkg = tmp_path / "work_frontier"
    source_dir = pkg / source
    source_dir.mkdir(parents=True)
    module_path = source_dir / "probe.py"
    _ = module_path.write_text(
        "from work_frontier.application.ports import repository\n",
        encoding="utf-8",
    )

    violations = validate(tmp_path)
    assert not any(v.path == module_path for v in violations)
