#!/usr/bin/env python3
"""Cross-check system-diagram.md against modules/*.md.

Understands both confirmed Mermaid edges (`-->`, `==>`) and quick-scan
unconfirmed edges (`-.->`), including inline node shapes and
`:::unconfirmed` class suffixes.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SECTION_HEADING_RE = re.compile(r"^#{1,6}\s*Module dependency graph", re.IGNORECASE)
ANY_HEADING_RE = re.compile(r"^#{1,6}\s")
FENCE_START_RE = re.compile(r"^```\s*mermaid\s*$", re.IGNORECASE)
FENCE_END_RE = re.compile(r"^```\s*$")
NODE_RE = r"([A-Za-z0-9_-]+)(?:\s*(?:\[[^\n]*?\]|\(\([^\n]*?\)\)|\([^\n]*?\)|\{[^\n]*?\}))?(?:\s*:::[A-Za-z0-9_-]+)?"
EDGE_LINE_RE = re.compile(r"^\s*" + NODE_RE + r"\s*(-->|-\.->|==>)\s*" + NODE_RE)
DEPENDS_HEADING_RE = re.compile(r"^#{1,6}\s*Depends on", re.IGNORECASE)
USED_BY_HEADING_RE = re.compile(r"^#{1,6}\s*Used by", re.IGNORECASE)
MODULE_REF_RE = re.compile(r"\*\*`([^`]+)`\*\*")
UNCONFIRMED_RE = re.compile(r"(?<![A-Za-z0-9])unconfirmed(?![A-Za-z0-9])", re.IGNORECASE)


def extract_module_graph_edges(text):
    """Return `{(from, to): confirmed_bool}` for the module Mermaid block."""
    edges = {}
    in_section = False
    in_fence = False
    for line in text.splitlines():
        if SECTION_HEADING_RE.match(line):
            in_section, in_fence = True, False
            continue
        if in_section and ANY_HEADING_RE.match(line) and not SECTION_HEADING_RE.match(line):
            break
        if not in_section:
            continue
        stripped = line.strip()
        if FENCE_START_RE.match(stripped):
            in_fence = True
            continue
        if in_fence and FENCE_END_RE.match(stripped):
            in_fence = False
            continue
        if in_fence:
            match = EDGE_LINE_RE.match(line)
            if match:
                source, arrow, target = match.group(1), match.group(2), match.group(3)
                # If the same edge appears twice, the less-confident rendering
                # wins so a dotted duplicate cannot be hidden by a solid one.
                confirmed = arrow != "-.->"
                key = (source, target)
                edges[key] = edges.get(key, True) and confirmed
    return edges


def extract_refs(text, heading_re):
    """Return `{target: confirmed_bool}` from a module relationship section."""
    refs = {}
    in_section = False
    for line in text.splitlines():
        if heading_re.match(line):
            in_section = True
            continue
        if in_section and ANY_HEADING_RE.match(line):
            break
        if not in_section:
            continue
        for target in MODULE_REF_RE.findall(line):
            confirmed = not bool(UNCONFIRMED_RE.search(line))
            refs[target] = refs.get(target, True) and confirmed
    return refs


def records(items):
    return [{"from": source, "to": target} for source, target in sorted(items)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root", help="path to docs/anatomy/ (or custom output root)")
    args = parser.parse_args()
    root = Path(args.output_root).resolve()
    diagram_path = root / "system-diagram.md"
    modules_dir = root / "modules"
    if not diagram_path.is_file() or not modules_dir.is_dir():
        missing = diagram_path if not diagram_path.is_file() else modules_dir
        print(json.dumps({"error": "not found: %s" % missing}, indent=2))
        sys.exit(2)

    diagram = extract_module_graph_edges(diagram_path.read_text(errors="ignore"))
    depends, used_by = {}, {}
    for path in sorted(modules_dir.glob("*.md")):
        text = path.read_text(errors="ignore")
        depends[path.stem] = extract_refs(text, DEPENDS_HEADING_RE)
        used_by[path.stem] = extract_refs(text, USED_BY_HEADING_RE)

    depends_edges = {
        (source, target): confirmed
        for source, targets in depends.items()
        for target, confirmed in targets.items()
    }
    used_by_edges = {
        (source, target): confirmed
        for target, sources in used_by.items()
        for source, confirmed in sources.items()
    }
    diagram_set = set(diagram)
    depends_set = set(depends_edges)
    used_by_set = set(used_by_edges)

    confirmation_mismatches = []
    for edge in sorted(diagram_set & depends_set):
        if diagram[edge] != depends_edges[edge]:
            confirmation_mismatches.append({
                "from": edge[0],
                "to": edge[1],
                "module_doc_confirmed": depends_edges[edge],
                "diagram_confirmed": diagram[edge],
            })

    transpose_mismatches = []
    for edge in sorted(depends_set | used_by_set):
        if edge not in depends_edges or edge not in used_by_edges:
            transpose_mismatches.append({"from": edge[0], "to": edge[1], "reason": "edge missing on one side"})
        elif depends_edges[edge] != used_by_edges[edge]:
            transpose_mismatches.append({
                "from": edge[0], "to": edge[1],
                "reason": "confirmation marker differs",
                "depends_on_confirmed": depends_edges[edge],
                "used_by_confirmed": used_by_edges[edge],
            })

    result = {
        # Preserve the original keys for existing consumers.
        "output_root": str(root),
        "modules_found": sorted(depends),
        "diagram_edges_unconfirmed": records(diagram_set - (depends_set | used_by_set)),
        "depends_on_missing_from_diagram": records(depends_set - diagram_set),
        "depends_on_used_by_mismatch": transpose_mismatches,
        # New confidence-aware checks.
        "edge_confirmation_style_mismatch": confirmation_mismatches,
        "quick_scan_unconfirmed_edges": records(edge for edge, confirmed in diagram.items() if not confirmed),
        "counts": {
            "diagram_edges": len(diagram),
            "diagram_edges_unconfirmed": len(diagram_set - (depends_set | used_by_set)),
            "depends_on_missing_from_diagram": len(depends_set - diagram_set),
            "depends_on_used_by_mismatch": len(transpose_mismatches),
            "edge_confirmation_style_mismatch": len(confirmation_mismatches),
            "quick_scan_unconfirmed_edges": sum(1 for confirmed in diagram.values() if not confirmed),
        },
        "note": (
            "Agreement here is output-to-output consistency, not proof against source. "
            "Dotted quick-scan edges are accepted only when the matching Depends on bullet "
            "is explicitly marked unconfirmed."
        ),
    }
    print(json.dumps(result, indent=2))
    blocking = (
        result["diagram_edges_unconfirmed"]
        or result["depends_on_missing_from_diagram"]
        or result["depends_on_used_by_mismatch"]
        or result["edge_confirmation_style_mismatch"]
    )
    if blocking:
        sys.exit(1)


if __name__ == "__main__":
    main()
