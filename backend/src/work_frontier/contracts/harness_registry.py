"""Authoritative harness registry loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HARNESS_ID_PATTERN = r"^WF-HAR-[A-Z0-9]+(?:-[A-Z0-9]+)*$"


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


def validate_registry(data: dict[str, Any]) -> None:
    if data.get("schema_version") != "1.0.0":
        msg = "registry schema_version must be 1.0.0"
        raise HarnessRegistryError(msg)
    harnesses = data.get("harnesses")
    if not isinstance(harnesses, list) or not harnesses:
        msg = "registry must contain a non-empty harnesses list"
        raise HarnessRegistryError(msg)

    seen: set[str] = set()
    for item in harnesses:
        if not isinstance(item, dict):
            msg = "each harness must be an object"
            raise HarnessRegistryError(msg)
        harness_id = item.get("id")
        if not isinstance(harness_id, str) or not harness_id.startswith("WF-HAR-"):
            msg = f"invalid harness id: {harness_id!r}"
            raise HarnessRegistryError(msg)
        if harness_id in seen:
            msg = f"duplicate harness id: {harness_id}"
            raise HarnessRegistryError(msg)
        seen.add(harness_id)
        if not item.get("command"):
            msg = f"{harness_id}: command is required"
            raise HarnessRegistryError(msg)

    if data.get("harness_count") != len(harnesses):
        msg = "harness_count does not match harnesses length"
        raise HarnessRegistryError(msg)

    standard_blockers = [
        str(item["id"])
        for item in harnesses
        if item.get("blocks_release") and item.get("applicability") == "standard"
    ]
    if data.get("standard_blocker_count") != len(standard_blockers):
        msg = "standard_blocker_count does not match computed blockers"
        raise HarnessRegistryError(msg)

    declared = data.get("standard_blockers")
    if declared != standard_blockers:
        msg = "standard_blockers list is inconsistent with harness entries"
        raise HarnessRegistryError(msg)


def get_harness(registry: dict[str, Any], harness_id: str) -> dict[str, Any]:
    for item in registry["harnesses"]:
        if item["id"] == harness_id:
            return item
    msg = f"unknown harness id: {harness_id}"
    raise HarnessRegistryError(msg)


def foundation_closure(registry: dict[str, Any]) -> list[str]:
    closure = registry.get("foundation_closure")
    if not isinstance(closure, list) or not closure:
        msg = "foundation_closure missing from registry"
        raise HarnessRegistryError(msg)
    return [str(item) for item in closure]
