#!/usr/bin/env python3
"""Build or check the registry from catalog and lifecycle metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
_BACKEND_SRC = ROOT / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from work_frontier.contracts.harness_registry import (  # noqa: E402
    RUNNER_EVIDENCE_HARNESSES,
    validate_registry,
)

CATALOG = ROOT / "docs" / "quality" / "harness-catalog.md"
LIFECYCLE = ROOT / "contracts" / "harness-lifecycle.json"
REGISTRY = ROOT / "contracts" / "harness-registry.json"
FIELD_RE = re.compile(r"\|\s*\*\*([^*]+)\*\*\s*\|\s*(.*?)\s*\|")
KNOWN_LAYER_ORDER: dict[str, int] = {
    "PREFLIGHT": 1,
    "STATIC": 1,
    "DOMAIN": 2,
    "PROPERTY": 3,
    "META": 4,
    "CONTRACT": 5,
    "INTEG": 6,
    "PRODUCT": 7,
    "OPS": 8,
}
_HAR_ID_LAYER_RE = re.compile(r"^WF-HAR-([A-Z0-9]+(?:-[A-Z0-9]+)*)-\d+")
_HAR_ID_SEQ_RE = re.compile(r"^WF-HAR-(?:[A-Z0-9]+(?:-[A-Z0-9]+)*)-(\d+)")


@dataclass(frozen=True, slots=True)
class HarnessLifecycleMetadata:
    """Canonical implementation, release-stage, closure, and dependency data."""

    foundation_closure: tuple[str, ...]
    implemented_harnesses: frozenset[str]
    deferred_harnesses: frozenset[str]
    pre_ga_harnesses: frozenset[str]
    prerequisites: dict[str, tuple[str, ...]]


def load_lifecycle_metadata(path: Path = LIFECYCLE) -> HarnessLifecycleMetadata:
    """Load and validate the hand-reviewed lifecycle metadata."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != "1.0.0":
        msg = "harness lifecycle schema_version must be 1.0.0"
        raise ValueError(msg)

    implemented = frozenset(str(item) for item in raw["implemented_harnesses"])
    deferred = frozenset(str(item) for item in raw["deferred_harnesses"])
    if implemented & deferred:
        msg = "implemented_harnesses and deferred_harnesses must not overlap"
        raise ValueError(msg)

    prerequisites = {
        str(harness_id): tuple(str(item) for item in values)
        for harness_id, values in cast(
            "dict[str, list[object]]", raw["prerequisites"]
        ).items()
    }
    if set(prerequisites) != set(implemented):
        msg = "prerequisites must contain exactly every implemented harness"
        raise ValueError(msg)

    closure = tuple(str(item) for item in raw["foundation_closure"])
    if not closure or len(closure) != len(set(closure)):
        msg = "foundation_closure must be non-empty and duplicate-free"
        raise ValueError(msg)
    if not set(closure) <= implemented:
        msg = "every foundation closure member must be implemented"
        raise ValueError(msg)

    pre_ga = frozenset(str(item) for item in raw["pre_ga_harnesses"])
    if not implemented <= pre_ga:
        msg = "every currently implemented harness must be available pre-GA"
        raise ValueError(msg)

    return HarnessLifecycleMetadata(
        foundation_closure=closure,
        implemented_harnesses=implemented,
        deferred_harnesses=deferred,
        pre_ga_harnesses=pre_ga,
        prerequisites=prerequisites,
    )


def _clean_cell(value: str) -> str:
    value = value.strip().strip("`")
    value = re.sub(r"`\s*\(.*$", "", value).strip()
    return value.rstrip("`").strip()


def _extract_layer_from_id(harness_id: str) -> str:
    match = _HAR_ID_LAYER_RE.match(harness_id)
    return match.group(1) if match else ""


def _extract_sequence_from_id(harness_id: str) -> int:
    match = _HAR_ID_SEQ_RE.search(harness_id)
    return int(match.group(1)) if match else 0


def _layer_number_for_harness(harness_id: str) -> int | None:
    return KNOWN_LAYER_ORDER.get(_extract_layer_from_id(harness_id))


def derive_prerequisites(
    harnesses: list[dict[str, object]],
    metadata: HarnessLifecycleMetadata | None = None,
) -> None:
    """Attach only explicit immediate dependencies; never transitive catalog order."""
    lifecycle = metadata or load_lifecycle_metadata()
    catalog_ids = {str(harness["id"]) for harness in harnesses}
    for harness in harnesses:
        harness_id = str(harness["id"])
        status = str(harness.get("status", "specified"))
        if status == "implemented":
            if harness_id not in lifecycle.prerequisites:
                msg = f"implemented harness lacks explicit prerequisites: {harness_id}"
                raise ValueError(msg)
            prereqs = lifecycle.prerequisites[harness_id]
            unknown = set(prereqs) - catalog_ids
            if unknown:
                msg = f"{harness_id}: unknown explicit prerequisites: {sorted(unknown)}"
                raise ValueError(msg)
            harness["prerequisites"] = list(prereqs)
        else:
            harness["prerequisites"] = []
        _ = harness.pop("_layer_order", None)
        _ = harness.pop("_sequence", None)


def parse_catalog(  # noqa: PLR0912 - parser validates independent dimensions
    text: str,
    metadata: HarnessLifecycleMetadata | None = None,
) -> list[dict[str, object]]:
    """Parse canonical catalog entries and join lifecycle metadata."""
    lifecycle = metadata or load_lifecycle_metadata()
    lines = text.splitlines()
    sections: list[list[str]] = []
    current_lines: list[str] = []
    for line in lines:
        if line.startswith("## ") and not line.startswith("### "):
            if current_lines:
                sections.append(current_lines)
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append(current_lines)

    harnesses: list[dict[str, object]] = []
    for section_lines in sections:
        parts = re.split(
            r"^### (WF-HAR-[^\n]+)\n",
            "\n".join(section_lines),
            flags=re.MULTILINE,
        )
        for index in range(1, len(parts), 2):
            title = parts[index].strip()
            body = parts[index + 1]
            match = re.match(r"^(WF-HAR-\S+):\s*(.+)$", title)
            if match is None:
                msg = f"unparseable harness header: {title}"
                raise ValueError(msg)
            harness_id, name = match.group(1), match.group(2).strip()
            fields = {
                key.strip(): _clean_cell(value) for key, value in FIELD_RE.findall(body)
            }
            if harness_id in lifecycle.implemented_harnesses:
                status = "implemented"
            elif harness_id in lifecycle.deferred_harnesses:
                status = "deferred"
            else:
                status = "specified"

            applicability = "standard"
            if harness_id.endswith("-L"):
                applicability = "large"
            elif harness_id.endswith("-T"):
                applicability = "tenant"

            harnesses.append(
                {
                    "id": harness_id,
                    "name": name,
                    "command": fields.get("Command", ""),
                    "artifact": fields.get("Artifact", ""),
                    "blocks_release": fields.get("Blocks release", "")
                    .lower()
                    .startswith("yes"),
                    "what_it_runs": fields.get("What it runs", ""),
                    "pass_criteria": fields.get("Pass criteria", ""),
                    "applicability": applicability,
                    "release_stage": "pre_ga"
                    if harness_id in lifecycle.pre_ga_harnesses
                    else "ga",
                    "status": status,
                    "_layer_order": _layer_number_for_harness(harness_id),
                    "_sequence": _extract_sequence_from_id(harness_id),
                }
            )
    return harnesses


def _validate_metadata_against_catalog(
    harnesses: list[dict[str, object]], metadata: HarnessLifecycleMetadata
) -> None:
    catalog_ids = {str(item["id"]) for item in harnesses}
    referenced = (
        set(metadata.implemented_harnesses)
        | set(metadata.deferred_harnesses)
        | set(metadata.pre_ga_harnesses)
        | set(metadata.foundation_closure)
        | set(metadata.prerequisites)
        | {
            prereq
            for prerequisites in metadata.prerequisites.values()
            for prereq in prerequisites
        }
    )
    unknown = referenced - catalog_ids
    if unknown:
        msg = (
            "lifecycle metadata references unknown catalog harnesses: "
            f"{sorted(unknown)}"
        )
        raise ValueError(msg)


def build_registry(
    harnesses: list[dict[str, object]],
    metadata: HarnessLifecycleMetadata | None = None,
) -> dict[str, object]:
    """Build and validate the compiled authoritative registry."""
    lifecycle = metadata or load_lifecycle_metadata()
    _validate_metadata_against_catalog(harnesses, lifecycle)
    derive_prerequisites(harnesses, lifecycle)

    standard_blockers = [
        str(item["id"])
        for item in harnesses
        if item.get("blocks_release") and item.get("applicability") == "standard"
    ]
    registry: dict[str, object] = {
        "schema_version": "1.2.0",
        "source": "docs/quality/harness-catalog.md",
        "lifecycle_source": "contracts/harness-lifecycle.json",
        "harness_count": len(harnesses),
        "catalog_harness_count": len(harnesses),
        "standard_blocker_count": len(standard_blockers),
        "standard_blockers": standard_blockers,
        "foundation_closure": list(lifecycle.foundation_closure),
        "harnesses": harnesses,
    }
    validate_registry(registry)
    return registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if committed registry differs from its canonical sources",
    )
    args = parser.parse_args()

    metadata = load_lifecycle_metadata()
    harnesses = parse_catalog(CATALOG.read_text(encoding="utf-8"), metadata)
    for harness in harnesses:
        harness["artifact_mode"] = (
            "runner_evidence"
            if str(harness["id"]) in RUNNER_EVIDENCE_HARNESSES
            else "declared_file"
        )
    registry = build_registry(harnesses, metadata)
    rendered = f"{json.dumps(registry, indent=2, sort_keys=False)}\n"

    if args.check:
        if not REGISTRY.exists() or REGISTRY.read_text(encoding="utf-8") != rendered:
            print(
                "harness registry is out of date; "
                "run scripts/build_harness_registry.py",
                file=sys.stderr,
            )
            return 1
        print(
            f"registry ok: {registry['harness_count']} harnesses, "
            f"{registry['standard_blocker_count']} standard blockers"
        )
        return 0

    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    _ = REGISTRY.write_text(rendered, encoding="utf-8")
    print(f"wrote {REGISTRY} ({registry['harness_count']} harnesses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
