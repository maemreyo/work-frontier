#!/usr/bin/env python3
"""Verify index.md health-signal claims against a fresh module-doc rollup."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rollup import (  # noqa: E402
    DEPENDS_HEADING_RE,
    USED_BY_HEADING_RE,
    extract_coverage,
    extract_refs,
    find_cycles,
)

SECTION_HEADING_RE = re.compile(r"^##\s*Codebase health signals", re.IGNORECASE)
ANY_H2_RE = re.compile(r"^##\s")
MOST_CONNECTED_ROW_RE = re.compile(r"^\s*\d+\.\s*`([^`]+)`")
BOLD_LABEL_RE = re.compile(r"^\*\*([^*]+):\*\*\s*(.*)$")
NONE_FOUND_RE = re.compile(r"\bnone found\b", re.IGNORECASE)
TRACE_FULL_OF_RE = re.compile(r"(\d+)\s+of\s+(\d+)\s+modules\s+were\s+traced\s+in\s+full", re.IGNORECASE)
BACKTICK_RE = re.compile(r"`([^`]+)`")
SLUG_RE = re.compile(r"^[A-Za-z0-9_-]+$")
CHAIN_RE = re.compile(r"([A-Za-z0-9_-]+(?:\s*->\s*[A-Za-z0-9_-]+)+)")


def canonical_cycle(path):
    nodes = list(path)
    if len(nodes) > 1 and nodes[0] == nodes[-1]:
        nodes = nodes[:-1]
    if not nodes:
        return tuple()
    rotations = [tuple(nodes[index:] + nodes[:index]) for index in range(len(nodes))]
    return min(rotations)


def parse_slug_list(rest):
    if rest is None:
        return None
    if NONE_FOUND_RE.search(rest):
        return []
    values = [value.strip() for value in BACKTICK_RE.findall(rest) if SLUG_RE.fullmatch(value.strip())]
    return sorted(set(values)) if values else None


def parse_cycle_list(rest):
    if rest is None:
        return None
    if NONE_FOUND_RE.search(rest):
        return []
    plain = rest.replace("`", "")
    cycles = []
    for match in CHAIN_RE.finditer(plain):
        nodes = [part.strip() for part in match.group(1).split("->")]
        if len(nodes) >= 2:
            cycles.append(canonical_cycle(nodes))
    return sorted(set(cycles)) if cycles else None


def parse_index_health_signals(text):
    in_section = False
    ranking, orphans_line, cycles_line, trace_line = [], None, None, None
    for line in text.splitlines():
        if SECTION_HEADING_RE.match(line):
            in_section = True
            continue
        if in_section and ANY_H2_RE.match(line):
            break
        if not in_section:
            continue
        match = MOST_CONNECTED_ROW_RE.match(line)
        if match:
            ranking.append(match.group(1))
            continue
        match = BOLD_LABEL_RE.match(line.strip())
        if not match:
            continue
        label, rest = match.group(1).strip().lower(), match.group(2).strip()
        if label.startswith("possible dead code") or label.startswith("orphan"):
            orphans_line = rest
        elif label.startswith("dependency cycles"):
            cycles_line = rest
        elif label.startswith("trace coverage"):
            trace_line = rest
    trace_claim = None
    if trace_line is not None:
        match = TRACE_FULL_OF_RE.search(trace_line)
        if match:
            trace_claim = {"full_claimed": int(match.group(1)), "total_claimed": int(match.group(2))}
    return {
        "most_connected_order": ranking,
        "orphans_line": orphans_line,
        "orphan_modules": parse_slug_list(orphans_line),
        "cycles_line": cycles_line,
        "cycles": parse_cycle_list(cycles_line),
        "trace_coverage_line": trace_line,
        "trace_coverage_claim": trace_claim,
    }


def compute_actual(modules_dir, top_n):
    depends_on, used_by, coverage = {}, {}, {}
    for path in sorted(modules_dir.glob("*.md")):
        text = path.read_text(errors="ignore")
        depends_on[path.stem] = extract_refs(text, DEPENDS_HEADING_RE)
        used_by[path.stem] = extract_refs(text, USED_BY_HEADING_RE)
        coverage[path.stem] = extract_coverage(text)[0]
    all_slugs = sorted(set(depends_on) | set(used_by))
    degree = {slug: len(depends_on.get(slug, ())) + len(used_by.get(slug, ())) for slug in all_slugs}
    most_connected = sorted(all_slugs, key=lambda slug: (-degree[slug], slug))[:top_n]
    orphans = sorted(slug for slug in all_slugs if not depends_on.get(slug) and not used_by.get(slug))
    graph = {slug: depends_on.get(slug, set()) & set(all_slugs) for slug in all_slugs}
    cycles = sorted(set(canonical_cycle(path) for path in find_cycles(graph)))
    counts = {"full": 0, "sampled": 0, "listed": 0, "unstated": 0}
    for status in coverage.values():
        counts[status] = counts.get(status, 0) + 1
    return {
        "most_connected_order": most_connected,
        "orphan_candidates": orphans,
        "cycles": [list(cycle) + [cycle[0]] for cycle in cycles if cycle],
        "canonical_cycles": [list(cycle) for cycle in cycles],
        "coverage_counts": counts,
        "modules_found": len(all_slugs),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root")
    args = parser.parse_args()
    root = Path(args.output_root).resolve()
    index_path, modules_dir = root / "index.md", root / "modules"
    if not index_path.is_file() or not modules_dir.is_dir():
        missing = index_path if not index_path.is_file() else modules_dir
        print(json.dumps({"error": "not found: %s" % missing}, indent=2))
        sys.exit(2)

    claimed = parse_index_health_signals(index_path.read_text(errors="ignore"))
    actual = compute_actual(modules_dir, max(len(claimed["most_connected_order"]), 5))
    findings = []

    ranking = claimed["most_connected_order"]
    if not ranking:
        findings.append({"signal": "most_connected", "issue": "unparsed -- no numbered rows found"})
    elif ranking != actual["most_connected_order"][:len(ranking)]:
        findings.append({"signal": "most_connected", "index_md_claims": ranking, "rollup_actual": actual["most_connected_order"][:len(ranking)]})

    if claimed["orphan_modules"] is None:
        findings.append({"signal": "orphan_candidates", "issue": "unparsed -- list modules in backticks or write 'none found'"})
    elif claimed["orphan_modules"] != actual["orphan_candidates"]:
        findings.append({"signal": "orphan_candidates", "index_md_claims": claimed["orphan_modules"], "rollup_actual": actual["orphan_candidates"]})

    actual_cycles = sorted(tuple(item) for item in actual["canonical_cycles"])
    claimed_cycles = None if claimed["cycles"] is None else sorted(tuple(item) for item in claimed["cycles"])
    if claimed_cycles is None:
        findings.append({"signal": "cycles", "issue": "unparsed -- use A -> B -> A chains or write 'none found'"})
    elif claimed_cycles != actual_cycles:
        findings.append({"signal": "cycles", "index_md_claims": [list(item) for item in claimed_cycles], "rollup_actual": [list(item) for item in actual_cycles]})

    claim = claimed["trace_coverage_claim"]
    if claim is None:
        findings.append({"signal": "trace_coverage", "issue": "unparsed -- expected '<X> of <Y> modules were traced in full'"})
    else:
        actual_full, actual_total = actual["coverage_counts"]["full"], actual["modules_found"]
        if claim["full_claimed"] != actual_full or claim["total_claimed"] != actual_total:
            findings.append({"signal": "trace_coverage", "index_md_claims": claim, "rollup_actual": {"full": actual_full, "total": actual_total, "counts": actual["coverage_counts"]}})

    print(json.dumps({
        "output_root": str(root),
        "index_md_claims": claimed,
        "rollup_actual": actual,
        "findings": findings,
        "note": "Non-empty orphan/cycle claims are compared exactly, not only none-vs-some.",
    }, indent=2))
    if findings:
        sys.exit(1)


if __name__ == "__main__":
    main()
