"""Authoritative harness registry loading and validation."""

from __future__ import annotations

import json
import re
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
    "blocks_release",
    "what_it_runs",
    "pass_criteria",
    "applicability",
    "status",
)


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


def _validate_harness_entry(harness_entry: dict[str, Any], seen: set[str]) -> str:
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
    applicability = str(harness_entry.get("applicability", ""))
    if applicability not in APPLICABILITY:
        msg = f"{harness_id}: invalid applicability {applicability!r}"
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
    for harness_entry in harnesses:
        _ = _validate_harness_entry(harness_entry, seen)

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
