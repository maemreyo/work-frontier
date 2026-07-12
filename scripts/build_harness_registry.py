#!/usr/bin/env python3
"""Build or check the machine-readable harness registry from the catalog.

Catalog is the sole semantic source of truth. This builder only:
- parses catalog entries
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

# Import runtime constants and validation from the shared module so we
# don't maintain a separate copy of artifact-mode rules.
from work_frontier.contracts.harness_registry import (  # noqa: E402
    RUNNER_EVIDENCE_EXPECTED_PATTERN,
    RUNNER_EVIDENCE_HARNESSES,
    VALID_ARTIFACT_MODES,
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


def _clean_cell(value: str) -> str:
    value = value.strip()
    value = value.strip("`")
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
        status = "implemented" if harness_id in FOUNDATION_CLOSURE else "specified"
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
                "status": status,
            }
        )
    return harnesses


def _validate_artifact_modes(harnesses: list[dict[str, object]]) -> None:
    """Validate artifact_mode values and runner_evidence path contracts.

    Uses shared constants from harness_registry.py to avoid duplication.
    """
    for h in harnesses:
        h_id = str(h["id"])
        mode = h.get("artifact_mode", "declared_file")
        if mode not in VALID_ARTIFACT_MODES:
            msg = (
                f"invalid artifact_mode {mode!r} for {h_id}; "
                f"valid values: {sorted(VALID_ARTIFACT_MODES)}"
            )
            raise ValueError(msg)
        if mode == "runner_evidence":
            if h_id not in RUNNER_EVIDENCE_HARNESSES:
                msg = f"{h_id}: runner_evidence mode not allowed for this harness"
                raise ValueError(msg)
            declared = str(h.get("artifact", ""))
            if not RUNNER_EVIDENCE_EXPECTED_PATTERN.match(declared):
                msg = (
                    f"{h_id}: runner_evidence artifact {declared!r} does not "
                    f"match expected pattern .omo/evidence/static/<HARNESS_ID>.json"
                )
                raise ValueError(msg)
            expected_path = f".omo/evidence/static/{h_id}.json"
            if declared != expected_path:
                msg = (
                    f"{h_id}: runner_evidence artifact {declared!r} "
                    f"does not match expected path {expected_path!r}"
                )
                raise ValueError(msg)


def build_registry(harnesses: list[dict[str, object]]) -> dict[str, object]:
    by_id = {str(item["id"]): item for item in harnesses}
    for harness_id in FOUNDATION_CLOSURE:
        if harness_id not in by_id:
            msg = f"foundation closure harness missing from catalog: {harness_id}"
            raise ValueError(msg)

    _validate_artifact_modes(harnesses)

    standard_blockers = [
        str(item["id"])
        for item in harnesses
        if item.get("blocks_release") and item.get("applicability") == "standard"
    ]
    return {
        "schema_version": "1.0.0",
        "source": "docs/quality/harness-catalog.md",
        "harness_count": len(harnesses),
        "catalog_harness_count": len(harnesses),
        "standard_blocker_count": len(standard_blockers),
        "standard_blockers": standard_blockers,
        "foundation_closure": list(FOUNDATION_CLOSURE),
        "harnesses": harnesses,
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
