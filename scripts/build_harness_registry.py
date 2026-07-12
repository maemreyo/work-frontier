#!/usr/bin/env python3
"""Build or check the machine-readable harness registry from the catalog."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "quality" / "harness-catalog.md"
REGISTRY = ROOT / "contracts" / "harness-registry.json"

HEADER_RE = re.compile(r"^### (WF-HAR-\S+):\s*(.+)$", re.MULTILINE)
FIELD_RE = re.compile(r"\|\s*\*\*([^*]+)\*\*\s*\|\s*(.*?)\s*\|")


def _clean_cell(value: str) -> str:
    value = value.strip()
    value = value.strip("`")
    # Drop trailing markdown residue such as "` (intended)"
    value = re.sub(r"`\s*\(.*$", "", value).strip()
    value = value.rstrip("`").strip()
    return value


def parse_catalog(text: str) -> list[dict[str, object]]:
    parts = re.split(r"^### (WF-HAR-[^\n]+)\n", text, flags=re.MULTILINE)
    harnesses: list[dict[str, object]] = []
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
        harnesses.append(
            {
                "id": harness_id,
                "name": name,
                "command": fields.get("Command", ""),
                "artifact": fields.get("Artifact", ""),
                "blocks_release": blocks,
                "what_it_runs": fields.get("What it runs", ""),
                "pass_criteria": fields.get("Pass criteria", ""),
                "applicability": applicability,
                "status": "specified",
            }
        )
    return harnesses


def build_registry(harnesses: list[dict[str, object]]) -> dict[str, object]:
    # Foundation dependency closure currently executable without full product stack.
    foundation_closure = [
        "WF-HAR-STATIC-02",
        "WF-HAR-STATIC-04",
        "WF-HAR-CONTRACT-05",
        "WF-HAR-INTEG-01",
        "WF-HAR-INTEG-02",
    ]
    # Local foundation preflight is not in the catalog but is required by ADR-006.
    local = [
        {
            "id": "WF-HAR-PREFLIGHT-01",
            "name": "ADR-006 Foundation Contract Gate",
            "command": "node .omo/preflight/adr-006/validate.mjs",
            "artifact": ".omo/evidence/preflight-adr-006/validation.json",
            "blocks_release": True,
            "what_it_runs": "Contract-specific P0 mutation validators for WF-P0-01..07",
            "pass_criteria": (
                "All negative fixtures reject with expected failure IDs; "
                "no false positives"
            ),
            "applicability": "standard",
            "status": "implemented",
        }
    ]
    # Mark implemented foundation harnesses with concrete local commands where catalog
    # paths are aspirational.
    command_overrides = {
        "WF-HAR-STATIC-02": "uv run python scripts/check_import_boundaries.py",
        "WF-HAR-STATIC-04": (
            "uv run ruff check backend/src backend/tests scripts && "
            "uv run ruff format --check backend/src backend/tests scripts && "
            "pnpm --dir frontend run check"
        ),
        "WF-HAR-CONTRACT-05": "uv run python scripts/generate_contracts.py --check",
        "WF-HAR-INTEG-01": "make migration-smoke",
        "WF-HAR-INTEG-02": "make storage-smoke",
    }
    by_id = {str(item["id"]): item for item in harnesses}
    for harness_id, command in command_overrides.items():
        if harness_id in by_id:
            by_id[harness_id]["command"] = command
            by_id[harness_id]["status"] = "implemented"

    all_harnesses = local + list(by_id.values())
    standard_blockers = [
        str(item["id"])
        for item in all_harnesses
        if item.get("blocks_release") and item.get("applicability") == "standard"
    ]
    return {
        "schema_version": "1.0.0",
        "source": "docs/quality/harness-catalog.md",
        "harness_count": len(all_harnesses),
        "catalog_harness_count": len(harnesses),
        "standard_blocker_count": len(standard_blockers),
        "standard_blockers": standard_blockers,
        "foundation_closure": ["WF-HAR-PREFLIGHT-01", *foundation_closure],
        "harnesses": all_harnesses,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if committed registry differs from catalog-derived output",
    )
    args = parser.parse_args()

    harnesses = parse_catalog(CATALOG.read_text(encoding="utf-8"))
    registry = build_registry(harnesses)
    rendered = f"{json.dumps(registry, indent=2, sort_keys=False)}\n"

    if args.check:
        if not REGISTRY.exists():
            print(f"missing registry: {REGISTRY}", file=sys.stderr)
            return 1
        existing = REGISTRY.read_text(encoding="utf-8")
        if existing != rendered:
            stale_msg = (
                "harness registry is out of date; run scripts/build_harness_registry.py"
            )
            print(stale_msg, file=sys.stderr)
            return 1
        ok_msg = (
            f"registry ok: {registry['harness_count']} harnesses, "
            f"{registry['standard_blocker_count']} standard blockers"
        )
        print(ok_msg)
        return 0

    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    _ = REGISTRY.write_text(rendered, encoding="utf-8")
    print(f"wrote {REGISTRY} ({registry['harness_count']} harnesses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
