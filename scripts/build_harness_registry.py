#!/usr/bin/env python3
"""Build or check the machine-readable harness registry from the catalog.

Catalog is the sole semantic source of truth. This builder only:
- parses catalog entries grouped by section/layer
- derives prerequisites from catalog layout (layers execute bottom-up;
  within each layer, sequence determines order)
- marks foundation-closure IDs as implemented when their catalog command is local
- does not rewrite harness meaning, name, or artifact semantics
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BACKEND_SRC = ROOT / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

# Import runtime validation and constants from the shared module.
from work_frontier.contracts.harness_registry import (  # noqa: E402
    RUNNER_EVIDENCE_HARNESSES,
    validate_registry,
)

CATALOG = ROOT / "docs" / "quality" / "harness-catalog.md"
REGISTRY = ROOT / "contracts" / "harness-registry.json"

# Foundation dependency closure for Todo 5 recertification of Todos 1-4 / P0.
FOUNDATION_CLOSURE: tuple[str, ...] = (
    "WF-HAR-PREFLIGHT-01",
    "WF-HAR-STATIC-01",
    "WF-HAR-STATIC-02",
    "WF-HAR-STATIC-04",
    "WF-HAR-STATIC-05",
    "WF-HAR-CONTRACT-05",
    "WF-HAR-INTEG-01",
    "WF-HAR-INTEG-02",
)

FIELD_RE = re.compile(r"\|\s*\*\*([^*]+)\*\*\s*\|\s*(.*?)\s*\|")

# Section names whose harnesses live outside the numbered layer sequence.
# Cross-cutting harnesses have no layer/sequence semantics in the catalog,
# so they receive no derived prerequisites (conservative decision).
CROSS_CUTTING_SECTION = "Cross-Cutting Harnesses"

# Known numbered-layer prefixes.  PREFLIGHT lives in the Layer 1 (Static)
# section of the catalog.
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

# Layer-extraction pattern from a harness ID: WF-HAR-{LAYER}-{SEQ}-{NAME}
# For IDs with an extra trailing qualifier like -L or -T the layer is
# still the third segment.
_HAR_ID_LAYER_RE = re.compile(r"^WF-HAR-([A-Z0-9]+(?:-[A-Z0-9]+)*)-\d+")

# Sequence extraction from a harness ID: the first numeric segment after
# WF-HAR-{LAYER}-
_HAR_ID_SEQ_RE = re.compile(r"^WF-HAR-(?:[A-Z0-9]+(?:-[A-Z0-9]+)*)-(\d+)")


def _clean_cell(value: str) -> str:
    value = value.strip()
    value = value.strip("`")
    value = re.sub(r"`\s*\(.*$", "", value).strip()
    value = value.rstrip("`").strip()
    return value


def _extract_layer_from_id(harness_id: str) -> str:
    """Extract the LAYER component from a WF-HAR-{LAYER}-{SEQ}-{NAME} id."""
    m = _HAR_ID_LAYER_RE.match(harness_id)
    if m:
        return m.group(1)
    return ""


def _extract_sequence_from_id(harness_id: str) -> int:
    """Extract the numeric SEQUENCE from a WF-HAR-{LAYER}-{SEQ}-{NAME} id."""
    m = _HAR_ID_SEQ_RE.search(harness_id)
    if m:
        return int(m.group(1))
    return 0


def _section_title(line: str) -> str:
    """Return the plain-text section title stripped of markdown and layer prefix."""
    # "## Layer 1: Static (WF-HAR-STATIC)" -> "Layer 1: Static"
    # "## Cross-Cutting Harnesses" -> "Cross-Cutting Harnesses"
    title = line.lstrip("#").strip()
    return title


def _layer_number_for_harness(harness_id: str) -> int | None:
    """Return the numeric layer order for a harness based on catalog placement.

    Returns None if no unambiguous layer can be established.  Cross-cutting
    harnesses receive None because the catalog provides no layer/sequence
    semantics for them — a conservative decision that yields no derived
    prerequisites.
    """
    # Check if this harness's layer prefix is a known numbered-layer prefix.
    id_layer = _extract_layer_from_id(harness_id)
    if id_layer in KNOWN_LAYER_ORDER:
        return KNOWN_LAYER_ORDER[id_layer]

    # Cross-cutting harnesses are outside the numbered layer sequence and
    # receive no derived prerequisites.  Returns None so derive_prerequisites
    # skips them.
    return None


def _harness_sort_key(
    harness: dict[str, object],
) -> tuple[int, int]:
    layer_val = harness.get("_layer_order", 99)
    seq_val = harness.get("_sequence", 0)
    if not isinstance(layer_val, int):
        layer_val = 99
    if not isinstance(seq_val, int):
        seq_val = 0
    return (layer_val, seq_val)  # type: ignore[return-value]


def derive_prerequisites(
    harnesses: list[dict[str, object]],
) -> None:
    """Derive prerequisites for each harness from catalog layer ordering.

    Prerequisites are all harnesses that must have been run before this one:
    - All harnesses from lower-numbered layers in the catalog.
    - Within the same layer, all harnesses that appear earlier in catalog
      order (stable sort by layer, then sequence, then catalog position).
    - When a harness has no unambiguous layer assignment (e.g. cross-cutting
      harnesses outside the numbered-layer sequence), it gets no derived
      prerequisites (conservative).

    Mutates *harnesses* in place by adding a ``prerequisites`` list.
    """
    # Sort harnesses by (layer, sequence); stable sort preserves catalog
    # order within equal (layer, sequence) groups.
    sorted_harnesses = sorted(harnesses, key=_harness_sort_key)
    for i, harness in enumerate(sorted_harnesses):
        layer = harness.get("_layer_order")
        prereqs: list[str] = []
        if layer is not None:
            for j in range(i):
                candidate = sorted_harnesses[j]
                clayer = candidate.get("_layer_order")
                if clayer is not None and candidate.get("status") == "implemented":
                    prereqs.append(str(candidate["id"]))
        harness["prerequisites"] = prereqs

    # Strip internal metadata before returning.
    for h in harnesses:
        _ = h.pop("_layer_order", None)
        _ = h.pop("_sequence", None)


def parse_catalog(text: str) -> list[dict[str, object]]:
    """Parse the catalog Markdown into a list of harness dicts.

    Each result includes internal ``_layer_order`` and ``_sequence`` keys
    used for prerequisite derivation; these are stripped before final output.
    """
    # Split the document into sections at ## headings.
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_section = ""
    current_lines: list[str] = []
    for line in lines:
        if line.startswith("## ") and not line.startswith("### "):
            if current_section:
                sections.append((current_section, current_lines))
            current_section = _section_title(line)
            current_lines = []
        else:
            current_lines.append(line)
    if current_section:
        sections.append((current_section, current_lines))

    # Process each section using the existing ###-based harness parser.
    all_harnesses: list[dict[str, object]] = []
    for _, section_lines in sections:
        section_text = "\n".join(section_lines)
        parts = re.split(r"^### (WF-HAR-[^\n]+)\n", section_text, flags=re.MULTILINE)
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
            blocks = fields.get("Blocks release", "").lower().startswith("yes")
            applicability = "standard"
            if harness_id.endswith("-L"):
                applicability = "large"
            elif harness_id.endswith("-T"):
                applicability = "tenant"
            status = "implemented" if harness_id in FOUNDATION_CLOSURE else "specified"

            # Derive layer metadata from harness ID.
            layer_order = _layer_number_for_harness(harness_id)

            entry: dict[str, object] = {
                "id": harness_id,
                "name": name,
                "command": fields.get("Command", ""),
                "artifact": fields.get("Artifact", ""),
                "blocks_release": blocks,
                "what_it_runs": fields.get("What it runs", ""),
                "pass_criteria": fields.get("Pass criteria", ""),
                "applicability": applicability,
                "status": status,
                "_layer_order": layer_order,
                "_sequence": _extract_sequence_from_id(harness_id),
            }
            all_harnesses.append(entry)

    return all_harnesses


def build_registry(harnesses: list[dict[str, object]]) -> dict[str, object]:
    by_id = {str(item["id"]): item for item in harnesses}
    for harness_id in FOUNDATION_CLOSURE:
        if harness_id not in by_id:
            msg = f"foundation closure harness missing from catalog: {harness_id}"
            raise ValueError(msg)

    # Derive prerequisites from catalog layer ordering before building.
    derive_prerequisites(harnesses)

    standard_blockers = [
        str(item["id"])
        for item in harnesses
        if item.get("blocks_release") and item.get("applicability") == "standard"
    ]
    registry: dict[str, object] = {
        "schema_version": "1.0.0",
        "source": "docs/quality/harness-catalog.md",
        "harness_count": len(harnesses),
        "catalog_harness_count": len(harnesses),
        "standard_blocker_count": len(standard_blockers),
        "standard_blockers": standard_blockers,
        "foundation_closure": list(FOUNDATION_CLOSURE),
        "harnesses": harnesses,
    }
    validate_registry(registry)
    return registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if committed registry differs from catalog-derived output",
    )
    args = parser.parse_args()

    harnesses = parse_catalog(CATALOG.read_text(encoding="utf-8"))
    for h in harnesses:
        h_id = str(h["id"])
        if h_id in RUNNER_EVIDENCE_HARNESSES:
            h["artifact_mode"] = "runner_evidence"
        else:
            h["artifact_mode"] = "declared_file"
    registry = build_registry(harnesses)
    rendered = f"{json.dumps(registry, indent=2, sort_keys=False)}\n"

    if args.check:
        if not REGISTRY.exists():
            print(f"missing registry: {REGISTRY}", file=sys.stderr)
            return 1
        existing = REGISTRY.read_text(encoding="utf-8")
        if existing != rendered:
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
