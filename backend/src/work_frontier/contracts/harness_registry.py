"""Authoritative harness registry loading and validation."""

from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, cast

HARNESS_ID_PATTERN: Final = re.compile(r"^WF-HAR-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
APPLICABILITY: Final = frozenset({"standard", "large", "tenant"})
STATUS: Final = frozenset({"specified", "implemented", "deferred"})
REQUIRED_FIELDS: Final = (
    "id",
    "name",
    "command",
    "artifact",
    "artifact_mode",
    "blocks_release",
    "what_it_runs",
    "pass_criteria",
    "applicability",
    "status",
)

# Valid artifact_mode values.
VALID_ARTIFACT_MODES: Final = frozenset({"declared_file", "runner_evidence"})

# Harnesses whose declared artifact is the evidence record itself.
RUNNER_EVIDENCE_HARNESSES: Final = frozenset({"WF-HAR-STATIC-01", "WF-HAR-STATIC-04"})

# Expected output path pattern for runner_evidence harnesses.
RUNNER_EVIDENCE_EXPECTED_PATTERN: Final = re.compile(
    r"^\.omo/evidence/static/WF-HAR-[A-Z0-9]+(?:-[A-Z0-9]+)*\.json$"
)
REMOTE_ARTIFACT_PREFIXES: Final = ("s3://", "http://", "https://")


class ArtifactMode(StrEnum):
    """Valid artifact_mode values for registry harness entries."""

    DECLARED_FILE = "declared_file"
    RUNNER_EVIDENCE = "runner_evidence"


class Applicability(StrEnum):
    """Harness applicability scope for certification gating."""

    STANDARD = "standard"
    LARGE = "large"
    TENANT = "tenant"


class HarnessRegistryError(ValueError):
    """Raised when the registry is invalid or a harness is unknown."""


def default_registry_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path.cwd()
    return root / "contracts" / "harness-registry.json"


def load_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or default_registry_path()
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    validate_registry(data)
    return data


_MIN_DRIVE_LETTER_LEN = 2


def _validate_declared_artifact_path(harness_id: str, path: str) -> None:
    """Validate declared artifact path.

    Rejects remote, absolute, traversal, Windows drive-letter, and UNC paths.
    """
    if path.startswith(REMOTE_ARTIFACT_PREFIXES):
        msg = (
            f"{harness_id}: remote artifact {path!r} is not allowed; "
            "a registry-declared certification artifact must be locally verifiable"
        )
        raise HarnessRegistryError(msg)

    # Reject UNC paths (\\server\share or //server/share).
    # Must be checked before absolute-path check because // starts with /.
    if path.startswith(("\\\\", "//")):
        msg = (
            f"{harness_id}: UNC artifact path {path!r} is not allowed; "
            "artifact paths must be repo-relative"
        )
        raise HarnessRegistryError(msg)

    # Reject absolute paths.
    if path.startswith("/"):
        msg = (
            f"{harness_id}: absolute artifact path {path!r} is not "
            "allowed; artifact paths must be repo-relative"
        )
        raise HarnessRegistryError(msg)

    # Reject path-traversal components.
    normalized = Path(path).as_posix()
    if ".." in normalized.split("/"):
        msg = (
            f"{harness_id}: artifact path {path!r} contains '..' "
            "traversal; artifact paths must be contained within the repo"
        )
        raise HarnessRegistryError(msg)

    # Reject Windows drive-letter paths (e.g. C:\foo).
    if len(path) >= _MIN_DRIVE_LETTER_LEN and path[1] == ":":
        msg = (
            f"{harness_id}: Windows-style artifact path {path!r} is "
            "not allowed; artifact paths must use POSIX relative notation"
        )
        raise HarnessRegistryError(msg)


def _validate_prerequisites(
    prereqs: list[str], harness_id: str, all_ids: set[str]
) -> None:
    """Validate a harness's prerequisite list.

    Rejects duplicates, self-references, and unknown IDs.  Also validates
    the graph is acyclic by running a topological-sort check against the
    full set of harness entries (deferred to a per-registry call).
    """
    if len(prereqs) != len(set(prereqs)):
        msg = f"{harness_id}: prerequisites contain duplicates: {prereqs}"
        raise HarnessRegistryError(msg)

    if harness_id in prereqs:
        msg = f"{harness_id}: prerequisite references itself"
        raise HarnessRegistryError(msg)

    for prereq_id in prereqs:
        if prereq_id not in all_ids:
            msg = f"{harness_id}: prerequisite {prereq_id!r} is not a known harness ID"
            raise HarnessRegistryError(msg)


def _validate_prerequisite_cycles(
    harnesses: list[dict[str, Any]],
) -> None:
    """Validate the prerequisite graph has no cycles (topological sort)."""
    # Build adjacency and in-degree maps for all harnesses.
    by_id: dict[str, dict[str, Any]] = {}
    for h in harnesses:
        hid = str(h["id"])
        by_id[hid] = h

    in_degree: dict[str, int] = dict.fromkeys(by_id, 0)
    adjacency: dict[str, list[str]] = {hid: [] for hid in by_id}

    for h in harnesses:
        hid = str(h["id"])
        prereqs_entry = h.get("prerequisites")
        if isinstance(prereqs_entry, list):
            prereqs_raw: list[object] = cast("list[object]", prereqs_entry)
            prereq_items: list[str] = [str(p) for p in prereqs_raw]
            for pid in prereq_items:
                if pid in by_id:
                    adjacency[pid].append(hid)
                    in_degree[hid] += 1

    # Kahn's algorithm.
    queue = [hid for hid, deg in in_degree.items() if deg == 0]
    sorted_count = 0
    while queue:
        node = queue.pop()
        sorted_count += 1
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if sorted_count != len(by_id):
        cyclic = [hid for hid, deg in in_degree.items() if deg > 0]
        msg = f"prerequisite graph contains a cycle involving: {sorted(cyclic)}"
        raise HarnessRegistryError(msg)


def _validate_harness_entry(
    harness_entry: dict[str, Any],
    seen: set[str],
) -> str:
    """Validate a single harness entry; return the normalized harness id."""
    for field in REQUIRED_FIELDS:
        if field not in harness_entry:
            msg = f"harness missing required field {field}"
            raise HarnessRegistryError(msg)
    harness_id = str(harness_entry["id"])
    if HARNESS_ID_PATTERN.fullmatch(harness_id) is None:
        msg = f"invalid harness id: {harness_id!r}"
        raise HarnessRegistryError(msg)
    if harness_id in seen:
        msg = f"duplicate harness id: {harness_id}"
        raise HarnessRegistryError(msg)
    seen.add(harness_id)
    if not str(harness_entry.get("command", "")).strip():
        msg = f"{harness_id}: command is required"
        raise HarnessRegistryError(msg)
    if not str(harness_entry.get("artifact", "")).strip():
        msg = f"{harness_id}: artifact is required"
        raise HarnessRegistryError(msg)
    declared_artifact = str(harness_entry["artifact"])
    _validate_declared_artifact_path(harness_id, declared_artifact)

    applicability = str(harness_entry.get("applicability", ""))
    if applicability not in APPLICABILITY:
        msg = f"{harness_id}: invalid applicability {applicability!r}"
        raise HarnessRegistryError(msg)

    artifact_mode = str(harness_entry.get("artifact_mode", ""))
    if artifact_mode not in VALID_ARTIFACT_MODES:
        msg = (
            f"{harness_id}: invalid artifact_mode {artifact_mode!r}; "
            f"valid values: {sorted(VALID_ARTIFACT_MODES)}"
        )
        raise HarnessRegistryError(msg)
    if artifact_mode == "runner_evidence":
        if harness_id not in RUNNER_EVIDENCE_HARNESSES:
            msg = f"{harness_id}: runner_evidence mode not allowed for this harness"
            raise HarnessRegistryError(msg)
        declared = str(harness_entry.get("artifact", ""))
        if not RUNNER_EVIDENCE_EXPECTED_PATTERN.match(declared):
            msg = (
                f"{harness_id}: runner_evidence artifact {declared!r} does not "
                f"match expected pattern .omo/evidence/static/<HARNESS_ID>.json"
            )
            raise HarnessRegistryError(msg)
        expected_path = f".omo/evidence/static/{harness_id}.json"
        if declared != expected_path:
            msg = (
                f"{harness_id}: runner_evidence artifact {declared!r} "
                f"does not match expected path {expected_path!r}"
            )
            raise HarnessRegistryError(msg)

    status = str(harness_entry.get("status", ""))
    if status not in STATUS:
        msg = f"{harness_id}: invalid status {status!r}"
        raise HarnessRegistryError(msg)
    if not isinstance(harness_entry.get("blocks_release"), bool):
        msg = f"{harness_id}: blocks_release must be bool"
        raise HarnessRegistryError(msg)
    return harness_id


def _validate_registry_counts(
    data: dict[str, Any], harnesses: list[dict[str, Any]]
) -> list[str]:
    """Validate top-level counts and the standard_blockers invariant."""
    if data.get("harness_count") != len(harnesses):
        msg = "harness_count does not match harnesses length"
        raise HarnessRegistryError(msg)
    if data.get("catalog_harness_count") != len(harnesses):
        msg = "catalog_harness_count must equal harness_count (catalog is sole source)"
        raise HarnessRegistryError(msg)

    standard_blockers: list[str] = [
        str(entry["id"])
        for entry in harnesses
        if entry.get("blocks_release") and entry.get("applicability") == "standard"
    ]
    if data.get("standard_blocker_count") != len(standard_blockers):
        msg = "standard_blocker_count does not match computed blockers"
        raise HarnessRegistryError(msg)

    declared = data.get("standard_blockers")
    if declared != standard_blockers:
        msg = "standard_blockers list is inconsistent with harness entries"
        raise HarnessRegistryError(msg)

    return standard_blockers


def _validate_foundation_closure(data: dict[str, Any], seen: set[str]) -> list[str]:
    """Validate the foundation_closure list references known harnesses."""
    closure_raw = data.get("foundation_closure")
    if not isinstance(closure_raw, list) or not closure_raw:
        msg = "foundation_closure missing from registry"
        raise HarnessRegistryError(msg)
    closure = [str(item) for item in cast("list[Any]", closure_raw)]
    if len(closure) != len(set(closure)):
        msg = "foundation_closure contains duplicates"
        raise HarnessRegistryError(msg)
    for harness_id in closure:
        if harness_id not in seen:
            msg = f"foundation_closure references unknown harness {harness_id}"
            raise HarnessRegistryError(msg)
    return closure


def validate_registry(data: dict[str, Any]) -> None:
    if data.get("schema_version") != "1.0.0":
        msg = "registry schema_version must be 1.0.0"
        raise HarnessRegistryError(msg)
    harnesses_raw = data.get("harnesses")
    if not isinstance(harnesses_raw, list) or not harnesses_raw:
        msg = "registry must contain a non-empty harnesses list"
        raise HarnessRegistryError(msg)
    harnesses = cast("list[dict[str, Any]]", harnesses_raw)

    seen: set[str] = set()
    all_ids: set[str] = set()
    for harness_entry in harnesses:
        hid = _validate_harness_entry(harness_entry, seen)
        all_ids.add(hid)

    # Validate prerequisites for every harness after all IDs are known.
    for harness_entry in harnesses:
        prereqs_entry = harness_entry.get("prerequisites")
        hid = str(harness_entry["id"])
        if isinstance(prereqs_entry, list):
            prereqs_raw: list[object] = cast("list[object]", prereqs_entry)
            prereqs: list[str] = [str(p) for p in prereqs_raw]
            _validate_prerequisites(prereqs, hid, all_ids)

    _validate_prerequisite_cycles(harnesses)
    _ = _validate_registry_counts(data, harnesses)
    _ = _validate_foundation_closure(data, seen)


def get_harness(registry: dict[str, Any], harness_id: str) -> dict[str, Any]:
    for item in registry["harnesses"]:
        if item["id"] == harness_id:
            return item
    msg = f"unknown harness id: {harness_id}"
    raise HarnessRegistryError(msg)


def foundation_closure(registry: dict[str, Any]) -> list[str]:
    closure_raw = registry.get("foundation_closure")
    if not isinstance(closure_raw, list) or not closure_raw:
        msg = "foundation_closure missing from registry"
        raise HarnessRegistryError(msg)
    closure = cast("list[Any]", closure_raw)
    return [str(item) for item in closure]


def get_prerequisites(registry: dict[str, Any], harness_id: str) -> list[str]:
    harness = get_harness(registry, harness_id)
    prereqs_entry = harness.get("prerequisites")
    if isinstance(prereqs_entry, list):
        prereqs_raw: list[object] = cast("list[object]", prereqs_entry)
        return [str(p) for p in prereqs_raw]
    return []
