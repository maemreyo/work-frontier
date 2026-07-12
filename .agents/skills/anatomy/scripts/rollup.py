#!/usr/bin/env python3
"""
rollup.py -- aggregates signals already sitting in modules/*.md into the
"whole system" numbers index.md's "Codebase health signals" section wants,
for the end of Phase 5 of the anatomy skill's tracing workflow.

Usage:
    python3 rollup.py <output_root> [--top-n 10]

<output_root> is docs/anatomy/ (or wherever the run wrote its output) -- the
folder containing modules/*.md. Run this after modules/*.md are written
(same point as verify_diagram.py) and fold its output into index.md; don't
hand-count any of this by eye, it's exactly the kind of bookkeeping a script
should do over data Claude already produced during Phase 4.

Prints JSON with four things, all derived purely from "Depends on"/"Used by"
sections and the per-module footer line already written into modules/*.md
-- nothing here re-reads the source code or re-verifies anything:

  - most_connected: modules ranked by (depends_on + used_by) edge count.
    High-fan-in/fan-out modules are usually either genuinely central
    (worth flagging to a new reader as "understand this one first") or a
    sign a module boundary was drawn in the wrong place -- either way,
    worth a human glance, not just a number.
  - orphan_candidates: modules with zero confirmed "Depends on" AND zero
    "Used by". Could be dead code, a truly standalone utility/entry point,
    or a boundary drawn wrong (see module-detection.md's "when still
    unsure") -- this script can't tell which, it just surfaces the
    candidates for a human/Claude judgment call.
  - cycles: modules that participate in a dependency cycle (A depends on
    B depends on ... depends on A), detected on the "Depends on" graph
    only. A cycle isn't automatically a bug -- some are intentional
    (bidirectional event pub/sub, a shared registry pattern) -- but it's
    always worth a second look and worth being visible in index.md rather
    than silently buried across N separate module docs.
  - trace_coverage: rolls up each module doc's footer ("Files examined in
    depth: ...") into full / sampled / unstated, so a reader of index.md
    can see at a glance which modules got exhaustive treatment versus a
    sample, without opening every module doc to check. "unstated" entries
    are a lint signal -- tracing-methodology.md requires every module to
    say plainly what it covered; an unstated one means that line got
    dropped and is worth fixing before calling Phase 5 done.

This is purely a rollup over existing output, same spirit as
verify_diagram.py: cheap, mechanical, and it catches things an eyeballed
pass across N module docs will often miss simply from volume.
"""
import argparse
import json
import re
import sys
from pathlib import Path

DEPENDS_HEADING_RE = re.compile(r"^#{1,6}\s*Depends on", re.IGNORECASE)
USED_BY_HEADING_RE = re.compile(r"^#{1,6}\s*Used by", re.IGNORECASE)
ANY_HEADING_RE = re.compile(r"^#{1,6}\s")
MODULE_REF_RE = re.compile(r"\*\*`([^`]+)`\*\*")
FOOTER_RE = re.compile(r"Files examined in depth:\s*(.+?)\.?\s*$", re.IGNORECASE)
SAMPLED_RE = re.compile(r"sampled\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE)
ALL_N_RE = re.compile(r"\ball\s+(\d+)\s+files?\b", re.IGNORECASE)


def extract_refs(text, heading_re):
    refs = set()
    in_section = False
    for line in text.splitlines():
        if heading_re.match(line):
            in_section = True
            continue
        if in_section and ANY_HEADING_RE.match(line):
            in_section = False
            continue
        if in_section:
            refs.update(MODULE_REF_RE.findall(line))
    return refs


def extract_coverage(text):
    """Best-effort read of the standard module-doc footer line. Returns one
    of 'full', 'sampled', or 'unstated' plus the raw matched fragment (or
    None) for a human to double check if they want the exact wording."""
    m = FOOTER_RE.search(text)
    if not m:
        return "unstated", None
    # The footer line is wrapped in underscore-italics per
    # output-templates.md's template (`_Traced from source ... files._`), so
    # the lazy match above typically swallows the sentence's closing period
    # *and* the italics-closing "_" before it can find a "$" to anchor on.
    # Strip trailing italics-marker characters (some projects' own docs use
    # *asterisk* italics instead -- strip either) and any stray punctuation
    # left over either side of them, in whichever order they show up.
    fragment = m.group(1).strip()
    fragment = fragment.rstrip("*_")
    fragment = fragment.rstrip(".")
    fragment = fragment.rstrip("*_")
    fragment = fragment.strip()
    if ALL_N_RE.search(fragment):
        return "full", fragment
    if SAMPLED_RE.search(fragment):
        return "sampled", fragment
    # A literal comma-separated file list (neither "all N files" nor
    # "sampled M of N") -- treat as stated-but-ambiguous rather than
    # unstated, since something was written; note it plainly instead of
    # guessing which bucket it belongs in.
    return "listed", fragment


def find_cycles(graph, cap=25):
    """DFS-based cycle detection over the 'Depends on' adjacency. Reports up
    to `cap` distinct cycles (as slug lists, first node repeated at the end)
    rather than exhaustively enumerating every cycle in a densely-connected
    graph, which can blow up combinatorially and isn't more useful past the
    first handful for a human to look at."""
    cycles = []
    visited = set()
    stack = []
    on_stack = set()

    def dfs(node):
        if len(cycles) >= cap:
            return
        visited.add(node)
        stack.append(node)
        on_stack.add(node)
        for nxt in sorted(graph.get(node, ())):
            if len(cycles) >= cap:
                break
            if nxt in on_stack:
                start = stack.index(nxt)
                cycles.append(stack[start:] + [nxt])
            elif nxt not in visited:
                dfs(nxt)
        stack.pop()
        on_stack.discard(node)

    for node in sorted(graph.keys()):
        if node not in visited and len(cycles) < cap:
            dfs(node)
    return cycles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("output_root", help="path to docs/anatomy/ (or wherever the trace was written)")
    ap.add_argument("--top-n", type=int, default=10, help="how many modules to list under most_connected")
    args = ap.parse_args()

    root = Path(args.output_root).resolve()
    modules_dir = root / "modules"
    if not modules_dir.is_dir():
        print(json.dumps({"error": f"not found: {modules_dir}"}))
        sys.exit(1)

    depends_on, used_by, coverage = {}, {}, {}
    for md in sorted(modules_dir.glob("*.md")):
        slug = md.stem
        text = md.read_text(errors="ignore")
        depends_on[slug] = extract_refs(text, DEPENDS_HEADING_RE)
        used_by[slug] = extract_refs(text, USED_BY_HEADING_RE)
        status, fragment = extract_coverage(text)
        coverage[slug] = {"status": status, "detail": fragment}

    all_slugs = sorted(set(depends_on) | set(used_by))

    degree = {
        slug: len(depends_on.get(slug, ())) + len(used_by.get(slug, ()))
        for slug in all_slugs
    }
    most_connected = sorted(
        (
            {"module": slug, "depends_on_count": len(depends_on.get(slug, ())),
             "used_by_count": len(used_by.get(slug, ())), "total_degree": degree[slug]}
            for slug in all_slugs
        ),
        key=lambda r: (-r["total_degree"], r["module"]),
    )[: args.top_n]

    orphan_candidates = sorted(
        slug for slug in all_slugs
        if not depends_on.get(slug) and not used_by.get(slug)
    )

    graph = {slug: depends_on.get(slug, set()) & set(all_slugs) for slug in all_slugs}
    raw_cycles = find_cycles(graph)
    cycles = [{"path": c, "length": len(c) - 1} for c in raw_cycles]

    coverage_counts = {"full": 0, "sampled": 0, "listed": 0, "unstated": 0}
    unstated = []
    sampled_detail = []
    for slug, info in coverage.items():
        coverage_counts[info["status"]] = coverage_counts.get(info["status"], 0) + 1
        if info["status"] == "unstated":
            unstated.append(slug)
        elif info["status"] == "sampled":
            sampled_detail.append({"module": slug, "detail": info["detail"]})

    result = {
        "output_root": str(root),
        "modules_found": len(coverage),
        "most_connected": most_connected,
        "orphan_candidates": orphan_candidates,
        "cycles": cycles,
        "trace_coverage": {
            "counts": coverage_counts,
            "sampled_modules": sorted(sampled_detail, key=lambda r: r["module"]),
            "unstated_modules": sorted(unstated),
        },
        "note": (
            "Purely a rollup of modules/*.md content -- orphan_candidates "
            "and cycles are candidates for a human/Claude judgment call, "
            "not automatic verdicts (see module-detection.md's 'when still "
            "unsure'). unstated_modules means that module's footer line "
            "doesn't match either the 'all N files' or 'sampled M of N' "
            "convention -- fix the footer line before calling Phase 5 done, "
            "per tracing-methodology.md's honesty-about-coverage rule."
        ),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()