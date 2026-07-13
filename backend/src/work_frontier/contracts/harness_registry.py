"""Authoritative harness registry loading and fail-closed validation."""

from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, cast

HARNESS_ID_PATTERN: Final = re.compile(r"^WF-HAR-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
APPLICABILITY: Final = frozenset({"standard", "large", "tenant"})
RELEASE_STAGES: Final = frozenset({"pre_ga", "ga"})
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
VALID_ARTIFACT_MODES: Final = frozenset({"declared_file", "runner_evidence"})
RUNNER_EVIDENCE_HARNESSES: Final = frozenset({"WF-HAR-STATIC-01", "WF-HAR-STATIC-04"})
RUNNER_EVIDENCE_EXPECTED_PATTERN: Final = re.compile(
    r"^\.omo/evidence/static/WF-HAR-[A-Z0-9]+(?:-[A-Z0-9]+)*\.json$"
)
REMOTE_ARTIFACT_PREFIXES: Final = ("s3://", "http://", "https://")


class ArtifactMode(StrEnum):
    """Valid artifact modes."""

    DECLARED_FILE = "declared_file"
    RUNNER_EVIDENCE = "runner_evidence"


class Applicability(StrEnum):
    """Workload applicability scope."""

    STANDARD = "standard"
    LARGE = "large"
    TENANT = "tenant"


class ReleaseStage(StrEnum):
    """Release stage dimension, independent of workload scope."""

    PRE_GA = "pre_ga"
    GA = "ga"


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


def _validate_declared_artifact_path(harness_id: str, path: str) -> None:
    if path.startswith(REMOTE_ARTIFACT_PREFIXES):
        msg = f"{harness_id}: remote artifact {path!r} is not allowed"
        raise HarnessRegistryError(msg)
    if path.startswith(("\\\\", "//")):
        msg = f"{harness_id}: UNC artifact path {path!r} is not allowed"
        raise HarnessRegistryError(msg)
    if path.startswith("/"):
        msg = f"{harness_id}: absolute artifact path {path!r} is not allowed"
        raise HarnessRegistryError(msg)
    if "\\" in path:
        msg = (
            f"{harness_id}: Windows-style artifact path {path!r} is not allowed; "
            "use POSIX relative notation"
        )
        raise HarnessRegistryError(msg)
    if ".." in path.split("/"):
        msg = f"{harness_id}: artifact path {path!r} contains traversal"
        raise HarnessRegistryError(msg)
    if len(path) >= 2 and path[1] == ":":
        msg = f"{harness_id}: Windows-style artifact path {path!r} is not allowed"
        raise HarnessRegistryError(msg)


def _validate_prerequisites(
    prereqs: list[str], harness_id: str, all_ids: set[str]
) -> None:
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


def _validate_prerequisite_cycles(harnesses: list[dict[str, Any]]) -> None:
    by_id = {str(harness["id"]): harness for harness in harnesses}
    in_degree: dict[str, int] = dict.fromkeys(by_id, 0)
    adjacency: dict[str, list[str]] = {harness_id: [] for harness_id in by_id}
    for harness_id, harness in by_id.items():
        for prereq_id in cast("list[str]", harness.get("prerequisites", [])):
            adjacency[prereq_id].append(harness_id)
            in_degree[harness_id] += 1

    queue = [harness_id for harness_id, degree in in_degree.items() if degree == 0]
    sorted_count = 0
    while queue:
        node = queue.pop()
        sorted_count += 1
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    if sorted_count != len(by_id):
        cyclic = sorted(
            harness_id for harness_id, degree in in_degree.items() if degree
        )
        msg = f"prerequisite graph contains a cycle involving: {cyclic}"
        raise HarnessRegistryError(msg)


def _validate_harness_entry(harness_entry: dict[str, Any], seen: set[str]) -> str:
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

    if not str(harness_entry["command"]).strip():
        msg = f"{harness_id}: command is required"
        raise HarnessRegistryError(msg)
    declared_artifact = str(harness_entry["artifact"])
    if not declared_artifact.strip():
        msg = f"{harness_id}: artifact is required"
        raise HarnessRegistryError(msg)
    _validate_declared_artifact_path(harness_id, declared_artifact)

    applicability = str(harness_entry["applicability"])
    if applicability not in APPLICABILITY:
        msg = f"{harness_id}: invalid applicability {applicability!r}"
        raise HarnessRegistryError(msg)
    artifact_mode = str(harness_entry["artifact_mode"])
    if artifact_mode not in VALID_ARTIFACT_MODES:
        msg = f"{harness_id}: invalid artifact_mode {artifact_mode!r}"
        raise HarnessRegistryError(msg)
    if artifact_mode == ArtifactMode.RUNNER_EVIDENCE:
        if harness_id not in RUNNER_EVIDENCE_HARNESSES:
            msg = f"{harness_id}: runner_evidence mode not allowed for this harness"
            raise HarnessRegistryError(msg)
        if RUNNER_EVIDENCE_EXPECTED_PATTERN.match(declared_artifact) is None:
            msg = f"{harness_id}: runner_evidence artifact does not match expected pattern"
            raise HarnessRegistryError(msg)
        expected = f".omo/evidence/static/{harness_id}.json"
        if declared_artifact != expected:
            msg = (
                f"{harness_id}: runner_evidence artifact {declared_artifact!r} "
                f"does not match expected path {expected!r}"
            )
            raise HarnessRegistryError(msg)

    status = str(harness_entry["status"])
    if status not in STATUS:
        msg = f"{harness_id}: invalid status {status!r}"
        raise HarnessRegistryError(msg)
    if not isinstance(harness_entry["blocks_release"], bool):
        msg = f"{harness_id}: blocks_release must be bool"
        raise HarnessRegistryError(msg)
    return harness_id


def _validate_registry_counts(
    data: dict[str, Any], harnesses: list[dict[str, Any]]
) -> None:
    if data.get("harness_count") != len(harnesses):
        raise HarnessRegistryError("harness_count does not match harnesses length")
    if data.get("catalog_harness_count") != len(harnesses):
        raise HarnessRegistryError("catalog_harness_count must equal harness_count")
    standard_blockers = [
        str(entry["id"])
        for entry in harnesses
        if entry.get("blocks_release") and entry.get("applicability") == "standard"
    ]
    if data.get("standard_blocker_count") != len(standard_blockers):
        raise HarnessRegistryError(
            "standard_blocker_count does not match computed blockers"
        )
    if data.get("standard_blockers") != standard_blockers:
        raise HarnessRegistryError(
            "standard_blockers list is inconsistent with harness entries"
        )


def _validate_foundation_closure(data: dict[str, Any], all_ids: set[str]) -> None:
    raw = data.get("foundation_closure")
    if not isinstance(raw, list) or not raw:
        raise HarnessRegistryError("foundation_closure missing from registry")
    closure = [str(item) for item in raw]
    if len(closure) != len(set(closure)):
        raise HarnessRegistryError("foundation_closure contains duplicates")
    by_id = {str(item["id"]): item for item in data["harnesses"]}
    for harness_id in closure:
        if harness_id not in all_ids:
            msg = f"foundation_closure references unknown harness {harness_id}"
            raise HarnessRegistryError(msg)
        if by_id[harness_id].get("status") != "implemented":
            msg = f"foundation_closure member is not implemented: {harness_id}"
            raise HarnessRegistryError(msg)


def validate_registry(data: dict[str, Any]) -> None:
    schema_version = data.get("schema_version")
    if schema_version not in {"1.0.0", "1.1.0", "1.2.0"}:
        raise HarnessRegistryError(
            "registry schema_version must be 1.0.0, 1.1.0, or 1.2.0"
        )
    raw = data.get("harnesses")
    if not isinstance(raw, list) or not raw:
        raise HarnessRegistryError("registry must contain a non-empty harnesses list")
    harnesses = cast("list[dict[str, Any]]", raw)

    seen: set[str] = set()
    for harness in harnesses:
        _ = _validate_harness_entry(harness, seen)

    for harness in harnesses:
        harness_id = str(harness["id"])
        prereqs_raw = harness.get("prerequisites")
        if schema_version != "1.0.0" and not isinstance(prereqs_raw, list):
            msg = f"{harness_id}: prerequisites must be an explicit array"
            raise HarnessRegistryError(msg)
        if prereqs_raw is not None:
            if not isinstance(prereqs_raw, list) or not all(
                isinstance(item, str) for item in prereqs_raw
            ):
                msg = f"{harness_id}: prerequisites must contain only strings"
                raise HarnessRegistryError(msg)
            _validate_prerequisites(cast("list[str]", prereqs_raw), harness_id, seen)

        release_stage = harness.get("release_stage")
        if schema_version == "1.2.0" and release_stage not in RELEASE_STAGES:
            msg = f"{harness_id}: release_stage must be 'pre_ga' or 'ga'"
            raise HarnessRegistryError(msg)
        if release_stage is not None and release_stage not in RELEASE_STAGES:
            msg = f"{harness_id}: invalid release_stage {release_stage!r}"
            raise HarnessRegistryError(msg)

    _validate_prerequisite_cycles(harnesses)
    _validate_registry_counts(data, harnesses)
    _validate_foundation_closure(data, seen)


def get_harness(registry: dict[str, Any], harness_id: str) -> dict[str, Any]:
    for item in registry["harnesses"]:
        if item["id"] == harness_id:
            return cast("dict[str, Any]", item)
    raise HarnessRegistryError(f"unknown harness id: {harness_id}")


def foundation_closure(registry: dict[str, Any]) -> list[str]:
    raw = registry.get("foundation_closure")
    if not isinstance(raw, list) or not raw:
        raise HarnessRegistryError("foundation_closure missing from registry")
    return [str(item) for item in raw]


def get_prerequisites(registry: dict[str, Any], harness_id: str) -> list[str]:
    harness = get_harness(registry, harness_id)
    raw = harness.get("prerequisites")
    if raw is None and registry.get("schema_version") == "1.0.0":
        return []
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise HarnessRegistryError(
            f"{harness_id}: prerequisites are missing or invalid"
        )
    return cast("list[str]", raw)


def get_release_stage(registry: dict[str, Any], harness_id: str) -> str:
    harness = get_harness(registry, harness_id)
    stage = harness.get("release_stage")
    if stage is None and registry.get("schema_version") in {"1.0.0", "1.1.0"}:
        return "pre_ga"
    if stage not in RELEASE_STAGES:
        raise HarnessRegistryError(f"{harness_id}: release_stage is missing or invalid")
    return str(stage)


def dependency_closure(registry: dict[str, Any], target_id: str) -> list[str]:
    """Return implemented target dependencies in deterministic topological order."""
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(harness_id: str) -> None:
        if harness_id in visited:
            return
        if harness_id in visiting:
            raise HarnessRegistryError(
                f"prerequisite graph contains a cycle at {harness_id}"
            )
        harness = get_harness(registry, harness_id)
        if harness.get("status") != "implemented":
            msg = (
                f"{harness_id}: status={harness.get('status')!r}; "
                "dependency closure requires implemented harnesses"
            )
            raise HarnessRegistryError(msg)
        visiting.add(harness_id)
        for prereq_id in get_prerequisites(registry, harness_id):
            visit(prereq_id)
        visiting.remove(harness_id)
        visited.add(harness_id)
        ordered.append(harness_id)

    visit(target_id)
    return ordered
