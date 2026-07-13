"""Tests for harness registry and runner certification rules."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from work_frontier.contracts.evidence_record import (
    Artifact,
    ArtifactHashes,
    EvidenceRecord,
    Invocation,
    Result,
    Tool,
)
from work_frontier.contracts.evidence_writer import get_tool_version
from work_frontier.contracts.harness_registry import (
    HarnessRegistryError,
    get_harness,
    load_registry,
    validate_registry,
)
from work_frontier.contracts.harness_runner import validate_evidence_record

ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / "contracts" / "harness-registry.json"


def test_registry_loads_and_matches_catalog_counts() -> None:
    registry = load_registry(REGISTRY_PATH)
    assert registry["schema_version"] == "1.1.0"
    assert registry["catalog_harness_count"] == registry["harness_count"] == 68
    assert "WF-HAR-PREFLIGHT-01" in registry["foundation_closure"]
    assert "WF-HAR-STATIC-01" in registry["foundation_closure"]
    assert "WF-HAR-STATIC-05" in registry["foundation_closure"]
    preflight = get_harness(registry, "WF-HAR-PREFLIGHT-01")
    assert preflight["status"] == "implemented"
    assert "validate.test.mjs" in preflight["command"]
    static05 = get_harness(registry, "WF-HAR-STATIC-05")
    assert "gitleaks" in static05["command"].lower()
    assert "validate.mjs" not in static05["command"]


def test_registry_rejects_invalid_artifact_mode() -> None:
    """Runtime validate_registry rejects harnesses with invalid artifact_mode."""
    registry = load_registry(REGISTRY_PATH)
    # Inject a harness with bogus artifact_mode
    bogus = dict(registry["harnesses"][0])
    bogus["id"] = "WF-HAR-TEST-BOGUS"
    bogus["artifact_mode"] = "bogus"
    registry["harnesses"] = [*registry["harnesses"], bogus]
    registry["harness_count"] = len(registry["harnesses"])
    with pytest.raises(HarnessRegistryError, match="invalid artifact_mode"):
        validate_registry(registry)


def test_registry_rejects_missing_artifact_mode() -> None:
    """Runtime validate_registry rejects harnesses missing artifact_mode."""
    registry = load_registry(REGISTRY_PATH)
    entry = dict(registry["harnesses"][0])
    entry["id"] = "WF-HAR-TEST-NOAM"
    entry.pop("artifact_mode", None)
    entry["artifact"] = "s3://bucket/test"
    registry["harnesses"] = [*registry["harnesses"], entry]
    registry["harness_count"] = len(registry["harnesses"])
    err_match = "missing required field artifact_mode"
    with pytest.raises(HarnessRegistryError, match=err_match):
        validate_registry(registry)


def test_registry_rejects_duplicate_ids() -> None:
    registry = load_registry(REGISTRY_PATH)
    registry["harnesses"] = [
        *registry["harnesses"],
        dict(registry["harnesses"][0]),
    ]
    registry["harness_count"] = len(registry["harnesses"])
    with pytest.raises(HarnessRegistryError, match="duplicate"):
        validate_registry(registry)


def test_get_tool_version_does_not_fabricate() -> None:
    version = get_tool_version("python")
    assert version
    assert version != "1.0.0"
    with pytest.raises(LookupError):
        _ = get_tool_version("definitely-not-a-real-tool-xyz")


def test_validate_evidence_rejects_fabricated_version_and_stale_subject() -> None:
    registry = load_registry(REGISTRY_PATH)
    record = EvidenceRecord(
        schema_version="1.0.0",
        harness_id="WF-HAR-STATIC-02",
        status="pass",
        run_id="run-test",
        subject_sha="a" * 40,
        subject_tree_sha="a" * 40,
        invocation=Invocation(
            command="true",
            exit_code=0,
            working_directory=".",
            start_time=datetime(2026, 7, 12, tzinfo=UTC),
            end_time=datetime(2026, 7, 12, 0, 0, 1, tzinfo=UTC),
            duration_seconds=1.0,
        ),
        tool=Tool(name="python", version="1.0.0", commit_sha="a" * 40),
        applicability="standard",
        applicability_reason="Standard foundation closure test record",
        environment={"os": "test"},
        artifacts=[Artifact(path="x", hashes=ArtifactHashes(sha256="b" * 64))],
        results=[Result(kind="test", passed=True)],
        stdout_artifact=Artifact(
            path="stdout.txt", hashes=ArtifactHashes(sha256="c" * 64)
        ),
        stderr_artifact=Artifact(
            path="stderr.txt", hashes=ArtifactHashes(sha256="d" * 64)
        ),
        property_bag={"registry.harness_id": "WF-HAR-STATIC-02"},
    )
    failures = validate_evidence_record(
        record,
        registry=registry,
        expected_subject_sha="c" * 40,
        require_blocking_pass=True,
        repo_root=ROOT,
    )
    assert any("subject_sha" in item for item in failures)
    assert any("tool version" in item for item in failures)
    assert any(
        "stdout artifact" in item or "stderr artifact" in item for item in failures
    )


def test_registry_file_is_valid_json_with_foundation_closure() -> None:
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert data["harness_count"] == data["catalog_harness_count"] == 68
    assert "WF-HAR-PREFLIGHT-01" in data["foundation_closure"]
    assert "WF-HAR-STATIC-05" in data["foundation_closure"]
    assert all(harness["command"].strip() for harness in data["harnesses"])
    assert all(harness["artifact"].strip() for harness in data["harnesses"])


def _minimal_harness(**overrides: object) -> dict[str, object]:
    """Build a minimal valid harness dict with overrides."""
    base: dict[str, object] = {
        "id": "WF-HAR-TEST-01",
        "name": "test",
        "command": "true",
        "artifact": ".omo/evidence/static/test.json",
        "blocks_release": False,
        "what_it_runs": "test",
        "pass_criteria": "exit 0",
        "applicability": "standard",
        "artifact_mode": "declared_file",
        "status": "implemented",
        "prerequisites": [],
    }
    base.update(overrides)
    return base


def _minimal_registry(*harnesses: dict[str, object]) -> dict[str, object]:
    """Build a minimal valid registry dict around the given harnesses."""
    harness_list = list(harnesses) if harnesses else [_minimal_harness()]
    return {
        "schema_version": "1.0.0",
        "harness_count": len(harness_list),
        "catalog_harness_count": len(harness_list),
        "standard_blocker_count": 0,
        "standard_blockers": [],
        "foundation_closure": [str(h["id"]) for h in harness_list],
        "harnesses": harness_list,
    }


def test_build_rejects_invalid_artifact_mode_value() -> None:
    """Invalid artifact_mode values are rejected at build time."""
    harness = _minimal_harness(artifact_mode="bogus_mode")
    registry = _minimal_registry(harness)
    with pytest.raises(HarnessRegistryError, match="invalid artifact_mode"):
        validate_registry(registry)


def test_registry_rejects_remote_declared_artifact() -> None:
    harness = _minimal_harness(artifact="s3://bucket/unverified")
    registry = _minimal_registry(harness)

    with pytest.raises(HarnessRegistryError, match="remote artifact"):
        validate_registry(registry)


def test_build_rejects_runner_evidence_on_unapproved_harness() -> None:
    """runner_evidence mode is only allowed for whitelisted harnesses."""
    harness = _minimal_harness(
        id="WF-HAR-STATIC-02",
        artifact_mode="runner_evidence",
        artifact=".omo/evidence/static/WF-HAR-STATIC-02.json",
    )
    registry = _minimal_registry(harness)
    with pytest.raises(HarnessRegistryError, match="runner_evidence mode not allowed"):
        validate_registry(registry)


def test_build_rejects_wrong_runner_evidence_artifact_path() -> None:
    """runner_evidence harness must declare artifact path matching its ID."""
    harness = _minimal_harness(
        id="WF-HAR-STATIC-01",
        artifact_mode="runner_evidence",
        artifact=".omo/evidence/static/wrong-path.json",
    )
    registry = _minimal_registry(harness)
    with pytest.raises(HarnessRegistryError, match="does not match expected"):
        validate_registry(registry)


def test_build_rejects_runner_evidence_artifact_mismatch() -> None:
    """runner_evidence harness must declare exact correct path, not just pattern."""
    harness = _minimal_harness(
        id="WF-HAR-STATIC-01",
        artifact_mode="runner_evidence",
        artifact=".omo/evidence/static/WF-HAR-STATIC-02.json",
    )
    registry = _minimal_registry(harness)
    with pytest.raises(HarnessRegistryError, match="does not match expected"):
        validate_registry(registry)


# ---------------------------------------------------------------------------
# Declared artifact path validation — reject absolute/traversal/Windows/UNC
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("artifact_path", "match_substr"),
    [
        ("/etc/passwd", "absolute"),
        ("/tmp/artifact.json", "absolute"),  # noqa: S108 - test input string, not a file path
        ("../outside/repo", "traversal"),
        ("foo/../../bar", "traversal"),
        ("C:\\Windows\\system32", "(?i)windows"),
        ("D:\\artifacts\\test.json", "(?i)windows"),
        ("\\\\server\\share\\file", "UNC"),
        ("//unc/share/path", "UNC"),
    ],
)
def test_registry_rejects_absolute_traversal_windows_unc_artifact_path(
    artifact_path: str, match_substr: str
) -> None:
    """Registry validates declared artifact paths: absolute, traversal, Windows, UNC."""
    harness = _minimal_harness(artifact=artifact_path)
    registry = _minimal_registry(harness)
    with pytest.raises(HarnessRegistryError, match=match_substr):
        validate_registry(registry)


@pytest.mark.parametrize(
    "artifact_path",
    [
        ".omo/evidence/static/test.json",
        "relative/path/artifact.txt",
        "artifacts/output.bin",
    ],
)
def test_registry_accepts_valid_artifact_paths(artifact_path: str) -> None:
    """Valid relative artifact paths pass registry validation."""
    harness = _minimal_harness(artifact=artifact_path)
    registry = _minimal_registry(harness)
    # Should not raise
    _ = validate_registry(registry)


# ---------------------------------------------------------------------------
# Prerequisite validation
# ---------------------------------------------------------------------------


def test_registry_accepts_prerequisites_field() -> None:
    """A harness with valid prerequisites passes validation."""
    h1 = _minimal_harness(id="WF-HAR-PREREQ-A-01")
    h2 = _minimal_harness(id="WF-HAR-PREREQ-B-01", prerequisites=["WF-HAR-PREREQ-A-01"])
    registry = _minimal_registry(h1, h2)
    _ = validate_registry(registry)


def test_registry_rejects_unknown_prerequisite() -> None:
    """A harness that references an unknown harness ID as a prerequisite fails."""
    h1 = _minimal_harness(
        id="WF-HAR-PREREQ-UNK-01",
        prerequisites=["WF-HAR-NONEXISTENT-01"],
    )
    registry = _minimal_registry(h1)
    with pytest.raises(HarnessRegistryError, match="not a known harness"):
        validate_registry(registry)


def test_registry_rejects_self_prerequisite() -> None:
    """A harness that lists itself as a prerequisite fails."""
    h1 = _minimal_harness(
        id="WF-HAR-PREREQ-SELF-01",
        prerequisites=["WF-HAR-PREREQ-SELF-01"],
    )
    registry = _minimal_registry(h1)
    with pytest.raises(HarnessRegistryError, match="references itself"):
        validate_registry(registry)


def test_registry_rejects_duplicate_prerequisites() -> None:
    """Duplicate entries in a prerequisite list are rejected."""
    h1 = _minimal_harness(id="WF-HAR-PREREQ-DUP-A-01")
    h2 = _minimal_harness(
        id="WF-HAR-PREREQ-DUP-B-01",
        prerequisites=["WF-HAR-PREREQ-DUP-A-01", "WF-HAR-PREREQ-DUP-A-01"],
    )
    registry = _minimal_registry(h1, h2)
    with pytest.raises(HarnessRegistryError, match="duplicate"):
        validate_registry(registry)


def test_registry_rejects_prerequisite_cycle() -> None:
    """A circular prerequisite graph is rejected."""
    h1 = _minimal_harness(
        id="WF-HAR-PREREQ-CYCLE-A-01",
        prerequisites=["WF-HAR-PREREQ-CYCLE-B-01"],
    )
    h2 = _minimal_harness(
        id="WF-HAR-PREREQ-CYCLE-B-01",
        prerequisites=["WF-HAR-PREREQ-CYCLE-A-01"],
    )
    registry = _minimal_registry(h1, h2)
    with pytest.raises(HarnessRegistryError, match="cycle"):
        validate_registry(registry)


def test_registry_rejects_larger_prerequisite_cycle() -> None:
    """A three-harness circular graph is rejected."""
    h1 = _minimal_harness(id="WF-HAR-PREREQ-CYC3-A-01", prerequisites=[])
    h2 = _minimal_harness(
        id="WF-HAR-PREREQ-CYC3-B-01",
        prerequisites=["WF-HAR-PREREQ-CYC3-C-01"],
    )
    h3 = _minimal_harness(
        id="WF-HAR-PREREQ-CYC3-C-01",
        prerequisites=["WF-HAR-PREREQ-CYC3-A-01"],
    )
    # h2 depends on h3 which depends on h1, no cycle. But if we add
    # h1 -> h2, we get a cycle: h2 -> h3 -> h1 -> h2.
    h1["prerequisites"] = ["WF-HAR-PREREQ-CYC3-B-01"]
    registry = _minimal_registry(h1, h2, h3)
    with pytest.raises(HarnessRegistryError, match="cycle"):
        validate_registry(registry)


def test_registry_v11_rejects_missing_prerequisites() -> None:
    """Canonical registry entries cannot silently lose dependencies."""
    h1 = _minimal_harness(id="WF-HAR-PREREQ-NONE-01")
    _ = h1.pop("prerequisites")
    registry = _minimal_registry(h1)
    registry["schema_version"] = "1.1.0"
    with pytest.raises(HarnessRegistryError, match="explicit array"):
        validate_registry(registry)


# ---------------------------------------------------------------------------
# Prerequisite derivation tests (builder logic)
# ---------------------------------------------------------------------------


def test_derive_prerequisites_preflight() -> None:
    from scripts.build_harness_registry import derive_prerequisites

    prereqs_harnesses = [_derive_harness_entry("WF-HAR-PREFLIGHT-01", layer=1, seq=1)]
    derive_prerequisites(prereqs_harnesses)
    assert prereqs_harnesses[0].get("prerequisites") == []


def _derive_harness_entry(
    hid: str,
    layer: int | None = None,
    seq: int = 1,
) -> dict[str, object]:
    """Build a harness entry dict for derive_prerequisites tests."""
    entry: dict[str, object] = {
        "id": hid,
        "_sequence": seq,
        "status": "implemented",
    }
    if layer is not None:
        entry["_layer_order"] = layer
    return entry


def test_derive_prerequisites_static() -> None:
    from scripts.build_harness_registry import derive_prerequisites

    harnesses = [
        _derive_harness_entry("WF-HAR-PREFLIGHT-01", layer=1, seq=1),
        _derive_harness_entry("WF-HAR-STATIC-01", layer=1, seq=1),
        _derive_harness_entry("WF-HAR-STATIC-02", layer=1, seq=2),
        _derive_harness_entry("WF-HAR-STATIC-03", layer=1, seq=3),
    ]
    derive_prerequisites(harnesses)
    assert harnesses[0].get("prerequisites") == []
    assert harnesses[1].get("prerequisites") == ["WF-HAR-PREFLIGHT-01"]
    assert harnesses[2].get("prerequisites") == [
        "WF-HAR-PREFLIGHT-01",
        "WF-HAR-STATIC-01",
    ]
    assert harnesses[3].get("prerequisites") == [
        "WF-HAR-PREFLIGHT-01",
        "WF-HAR-STATIC-01",
        "WF-HAR-STATIC-02",
    ]


def test_derive_prerequisites_domain_depends_on_static() -> None:
    from scripts.build_harness_registry import derive_prerequisites

    harnesses = [
        _derive_harness_entry("WF-HAR-STATIC-01", layer=1, seq=1),
        _derive_harness_entry("WF-HAR-STATIC-02", layer=1, seq=2),
        _derive_harness_entry("WF-HAR-DOMAIN-01", layer=2, seq=1),
    ]
    derive_prerequisites(harnesses)
    prereqs_result = cast("list[str]", harnesses[2].get("prerequisites", []))
    assert prereqs_result == ["WF-HAR-STATIC-01", "WF-HAR-STATIC-02"]


def test_derive_prerequisites_without_layer_order() -> None:
    from scripts.build_harness_registry import derive_prerequisites

    harnesses = [
        _derive_harness_entry("WF-HAR-STATIC-01", layer=1, seq=1),
        _derive_harness_entry("WF-HAR-UNKNOWN-01", seq=1),
    ]
    derive_prerequisites(harnesses)
    assert cast("list[str]", harnesses[1].get("prerequisites", [])) == []


def test_derive_prerequisites_ordered_by_layer_then_sequence() -> None:
    from scripts.build_harness_registry import derive_prerequisites

    harnesses = [
        _derive_harness_entry("WF-HAR-STATIC-01", layer=1, seq=1),
        _derive_harness_entry("WF-HAR-DOMAIN-01", layer=2, seq=2),
        _derive_harness_entry("WF-HAR-DOMAIN-02", layer=2, seq=3),
        _derive_harness_entry("WF-HAR-STATIC-03", layer=1, seq=3),
    ]
    derive_prerequisites(harnesses)
    for h in harnesses:
        hid = str(h["id"])
        if hid == "WF-HAR-DOMAIN-02":
            prereqs = cast("list[str]", h.get("prerequisites", []))
            assert hid not in prereqs
            assert "WF-HAR-STATIC-01" in prereqs
            assert "WF-HAR-STATIC-03" in prereqs
            assert prereqs[-1] == "WF-HAR-DOMAIN-01"
            break


# ---------------------------------------------------------------------------
# Cross-cutting harnesses get layer None; OPS -L/-T retain layer 8
# (tested through the public parse_catalog API)
# ---------------------------------------------------------------------------


def test_cross_cutting_harnesses_layer_is_none() -> None:
    """Cross-cutting harnesses get _layer_order=None from parse_catalog."""
    from scripts.build_harness_registry import parse_catalog

    harnesses = parse_catalog(
        "## Cross-Cutting Harnesses\n"
        "\n"
        "### WF-HAR-SEC-01: Auth\n"
        "\n"
        "| **Command** | `true` |\n"
        "| **Artifact** | `a.json` |\n"
        "| **What it runs** | auth |\n"
        "| **Pass criteria** | exit 0 |\n"
        "| **Blocks release** | Yes |\n"
    )
    assert len(harnesses) == 1
    assert harnesses[0]["_layer_order"] is None


def test_ops_suffix_harnesses_layer_is_eight() -> None:
    """OPS -L/-T harnesses get _layer_order=8 from parse_catalog."""
    from scripts.build_harness_registry import parse_catalog

    harnesses = parse_catalog(
        "## Layer 8: Operational (WF-HAR-OPS)\n"
        "\n"
        "### WF-HAR-OPS-02-L: Large Load\n"
        "\n"
        "| **Command** | `true` |\n"
        "| **Artifact** | `a.json` |\n"
        "| **What it runs** | load |\n"
        "| **Pass criteria** | exit 0 |\n"
        "| **Blocks release** | Yes |\n"
        "\n"
        "### WF-HAR-OPS-02-T: Tenant Test\n"
        "\n"
        "| **Command** | `true` |\n"
        "| **Artifact** | `b.json` |\n"
        "| **What it runs** | tenant |\n"
        "| **Pass criteria** | exit 0 |\n"
        "| **Blocks release** | Yes |\n"
    )
    assert len(harnesses) == 2
    for h in harnesses:
        assert h["_layer_order"] == 8


def test_ops_suffix_harnesses_sequence_is_correct() -> None:
    """OPS -L/-T harnesses retain correct _sequence from parse_catalog."""
    from scripts.build_harness_registry import parse_catalog

    harnesses = parse_catalog(
        "## Layer 8: Operational (WF-HAR-OPS)\n"
        "\n"
        "### WF-HAR-OPS-01: Smoke\n"
        "\n"
        "| **Command** | `true` |\n"
        "| **Artifact** | `a.json` |\n"
        "| **What it runs** | smoke |\n"
        "| **Pass criteria** | exit 0 |\n"
        "| **Blocks release** | Yes |\n"
        "\n"
        "### WF-HAR-OPS-02-L: Large Load\n"
        "\n"
        "| **Command** | `true` |\n"
        "| **Artifact** | `b.json` |\n"
        "| **What it runs** | load |\n"
        "| **Pass criteria** | exit 0 |\n"
        "| **Blocks release** | Yes |\n"
        "\n"
        "### WF-HAR-OPS-02-T: Tenant Test\n"
        "\n"
        "| **Command** | `true` |\n"
        "| **Artifact** | `c.json` |\n"
        "| **What it runs** | tenant |\n"
        "| **Pass criteria** | exit 0 |\n"
        "| **Blocks release** | Yes |\n"
    )
    by_id = {str(h["id"]): h for h in harnesses}
    assert by_id["WF-HAR-OPS-01"]["_sequence"] == 1
    assert by_id["WF-HAR-OPS-02-L"]["_sequence"] == 2
    assert by_id["WF-HAR-OPS-02-T"]["_sequence"] == 2


# ---------------------------------------------------------------------------
# Cross-cutting harnesses get no derived prerequisites
# ---------------------------------------------------------------------------


def test_cross_cutting_harnesses_no_prerequisites() -> None:
    """Cross-cutting harnesses receive no derived prerequisites."""
    from scripts.build_harness_registry import derive_prerequisites

    harnesses = [
        _derive_harness_entry("WF-HAR-STATIC-01", layer=1, seq=1),
        _derive_harness_entry("WF-HAR-SEC-01", seq=1),
        _derive_harness_entry("WF-HAR-A11Y-01", seq=1),
    ]
    derive_prerequisites(harnesses)
    assert harnesses[0].get("prerequisites") == []
    assert harnesses[1].get("prerequisites") == []
    assert harnesses[2].get("prerequisites") == []


def test_ops_suffix_harnesses_retain_layer_order_in_prereqs() -> None:
    """OPS -L/-T suffix harnesses retain numbered layer order in derivation."""
    from scripts.build_harness_registry import derive_prerequisites

    harnesses = [
        _derive_harness_entry("WF-HAR-STATIC-01", layer=1, seq=1),
        _derive_harness_entry("WF-HAR-STATIC-02", layer=1, seq=2),
        _derive_harness_entry("WF-HAR-OPS-01", layer=8, seq=1),
        _derive_harness_entry("WF-HAR-OPS-02-L", layer=8, seq=2),
        _derive_harness_entry("WF-HAR-OPS-02-T", layer=8, seq=2),
    ]
    derive_prerequisites(harnesses)
    ops_l = cast("list[str]", harnesses[3].get("prerequisites", []))
    assert "WF-HAR-STATIC-01" in ops_l
    assert "WF-HAR-STATIC-02" in ops_l
    assert "WF-HAR-OPS-01" in ops_l
    assert "WF-HAR-OPS-02-L" not in ops_l

    ops_t = cast("list[str]", harnesses[4].get("prerequisites", []))
    # OPS-02-T is after OPS-02-L in input order (same layer/seq), so
    # stable sort preserves that: OPS-02-T has OPS-02-L as an extra prereq.
    assert ops_t[:-1] == ops_l
    assert ops_t[-1] == "WF-HAR-OPS-02-L"


# ---------------------------------------------------------------------------
# parse_catalog + derive_prerequisites end-to-end with numbered layers
# ---------------------------------------------------------------------------


def test_parse_catalog_and_derive_prerequisites_numbered_layers() -> None:
    """parse_catalog + derive_prerequisites: layers ordered by number,
    cross-cutting has none."""
    from scripts.build_harness_registry import derive_prerequisites, parse_catalog

    catalog = """## Layer 1: Static (WF-HAR-STATIC)

### WF-HAR-STATIC-01: Type Checking

| **Command** | `true` |
| **Artifact** | `.omo/evidence/static/WF-HAR-STATIC-01.json` |
| **What it runs** | type checks |
| **Pass criteria** | exit 0 |
| **Blocks release** | Yes |

### WF-HAR-STATIC-02: Lint

| **Command** | `true` |
| **Artifact** | `.omo/evidence/static/WF-HAR-STATIC-02.json` |
| **What it runs** | lint |
| **Pass criteria** | exit 0 |
| **Blocks release** | Yes |

## Layer 8: Operational (WF-HAR-OPS)

### WF-HAR-OPS-01: Smoke

| **Command** | `true` |
| **Artifact** | `.omo/evidence/ops/smoke.json` |
| **What it runs** | smoke |
| **Pass criteria** | exit 0 |
| **Blocks release** | Yes |

### WF-HAR-OPS-02-L: Large Load

| **Command** | `true` |
| **Artifact** | `.omo/evidence/ops/large-load.json` |
| **What it runs** | load |
| **Pass criteria** | exit 0 |
| **Blocks release** | Yes |

## Cross-Cutting Harnesses

### WF-HAR-SEC-01: Auth Bypass

| **Command** | `true` |
| **Artifact** | `.omo/evidence/security/auth-bypass.json` |
| **What it runs** | auth |
| **Pass criteria** | exit 0 |
| **Blocks release** | Yes |

### WF-HAR-A11Y-01: WCAG

| **Command** | `true` |
| **Artifact** | `.omo/evidence/a11y/wcag.json` |
| **What it runs** | a11y |
| **Pass criteria** | exit 0 |
| **Blocks release** | Yes |
"""
    harnesses = parse_catalog(catalog)
    derive_prerequisites(harnesses)

    by_id = {str(h["id"]): h for h in harnesses}

    # STATIC-01 (first in layer 1) -> no prereqs
    assert by_id["WF-HAR-STATIC-01"].get("prerequisites") == []

    # STATIC-02 (second in layer 1) -> STATIC-01 prereq
    assert by_id["WF-HAR-STATIC-02"].get("prerequisites") == ["WF-HAR-STATIC-01"]

    # OPS-01 (layer 8) -> STATIC-01, STATIC-02 prereqs
    ops01_prereqs = cast("list[str]", by_id["WF-HAR-OPS-01"].get("prerequisites", []))
    assert ops01_prereqs == ["WF-HAR-STATIC-01", "WF-HAR-STATIC-02"]

    # OPS-02-L (layer 8, seq 2) -> STATIC-01, STATIC-02, OPS-01 prereqs
    ops_l_prereqs = cast("list[str]", by_id["WF-HAR-OPS-02-L"].get("prerequisites", []))
    assert ops_l_prereqs == [
        "WF-HAR-STATIC-01",
        "WF-HAR-STATIC-02",
        "WF-HAR-OPS-01",
    ]

    # Cross-cutting entries have no prereqs
    assert by_id["WF-HAR-SEC-01"].get("prerequisites") == []
    assert by_id["WF-HAR-A11Y-01"].get("prerequisites") == []
