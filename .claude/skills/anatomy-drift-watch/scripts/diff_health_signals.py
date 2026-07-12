#!/usr/bin/env python3
"""
diff_health_signals.py -- compares the `health_signals` block of two
_graph.json snapshots (written by the anatomy skill's graph_export.py) and
reports structural drift: new dependency cycles, new orphan candidates,
and modules whose most_connected rank moved sharply.

Usage:
    python3 diff_health_signals.py <old_graph.json> <new_graph.json>
                                    [--rank-jump-threshold N] [--fail-on-drift]

Why this exists: graph_export.py / rollup.py only ever look at the
*current* state of the traced graph -- there's no concept of "compared to
last time" anywhere in the anatomy skill today. A module quietly becoming
the most-connected thing in the system, or a new dependency cycle
appearing, is exactly the kind of change worth a deliberate "we saw this,
here's why it's fine (or not)" record -- an ADR -- rather than sailing
through unnoticed inside a routine anatomy re-trace. This script is the
detector; anatomy-drift-watch's SKILL.md is the workflow that turns a
positive result into a nudge to write one.

Cycle comparison is by participant node set, not exact path: a cycle
A->B->C->A and a cycle reported as B->C->A->B are the same cycle with a
different DFS starting point, and find_cycles() in rollup.py/
graph_export.py doesn't guarantee a stable starting node across runs (it
depends on dict/set iteration built from whatever changed). Comparing
node sets avoids reporting every pre-existing cycle as "new" just because
its reported rotation happened to differ this run.

Rank comparison only covers modules that appear in at least one run's
most_connected top-N list (graph_export.py's --top-n, default 10) --
a module ranked #11 in both runs is invisible to this comparison, same
limitation graph_export.py itself documents for its own output. A module
that enters the top-N from outside it is reported as
`new_to_most_connected` (its true prior rank is unknown, not "just
outside the list"); a module that leaves the top-N entirely is reported
as `dropped_from_most_connected` for the same reason, without a "new
rank" figure since it isn't ranked at all in the fresher snapshot's
visible data.

Output is informational by default (exit 0 regardless of findings) --
pass --fail-on-drift to get a non-zero exit when drift_detected is true,
for a CI/scripted use rather than the human-in-the-loop ADR nudge this
skill is primarily built for.
"""
import argparse
import json
import sys
from pathlib import Path


def load_graph(path: Path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"error": f"couldn't read/parse {path}: {e}"}, indent=2))
        sys.exit(2)


def cycle_key(cycle):
    """A cycle's `path` is a list of slugs with the start node repeated at
    the end (see rollup.py/graph_export.py's find_cycles). The participant
    set, not the path/rotation, is what identifies "the same cycle" across
    two runs."""
    return frozenset(cycle["path"][:-1]) if cycle.get("path") else frozenset()


def diff_cycles(old_cycles, new_cycles):
    old_keys = {cycle_key(c): c for c in old_cycles}
    new_keys = {cycle_key(c): c for c in new_cycles}
    new_only = [new_keys[k] for k in new_keys if k not in old_keys]
    resolved = [old_keys[k] for k in old_keys if k not in new_keys]
    return new_only, resolved


def diff_orphans(old_orphans, new_orphans):
    old_set, new_set = set(old_orphans), set(new_orphans)
    return sorted(new_set - old_set), sorted(old_set - new_set)


def diff_ranks(old_most_connected, new_most_connected, threshold):
    old_rank = {row["module"]: i + 1 for i, row in enumerate(old_most_connected)}
    new_rank = {row["module"]: i + 1 for i, row in enumerate(new_most_connected)}
    old_degree = {row["module"]: row.get("total_degree") for row in old_most_connected}
    new_degree = {row["module"]: row.get("total_degree") for row in new_most_connected}

    rank_jumps = []
    new_to_top = []
    for module, nr in new_rank.items():
        if module not in old_rank:
            new_to_top.append({
                "module": module,
                "new_rank": nr,
                "new_degree": new_degree.get(module),
            })
            continue
        delta = old_rank[module] - nr  # positive = moved up (toward #1)
        if abs(delta) >= threshold:
            rank_jumps.append({
                "module": module,
                "old_rank": old_rank[module],
                "new_rank": nr,
                "old_degree": old_degree.get(module),
                "new_degree": new_degree.get(module),
                "delta_rank": delta,
            })

    dropped = [
        {"module": module, "old_rank": old_rank[module], "old_degree": old_degree.get(module)}
        for module in old_rank
        if module not in new_rank
    ]

    rank_jumps.sort(key=lambda r: -abs(r["delta_rank"]))
    return rank_jumps, new_to_top, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old_graph", help="path to a previously archived _graph.json snapshot")
    ap.add_argument("new_graph", help="path to the current _graph.json")
    ap.add_argument("--rank-jump-threshold", type=int, default=3,
                     help="minimum |old_rank - new_rank| to report as a rank jump (default 3)")
    ap.add_argument("--fail-on-drift", action="store_true",
                     help="exit 1 if drift_detected is true (default: always exit 0, informational)")
    args = ap.parse_args()

    old = load_graph(args.old_graph)
    new = load_graph(args.new_graph)

    old_hs = old.get("health_signals", {})
    new_hs = new.get("health_signals", {})

    new_cycles, resolved_cycles = diff_cycles(old_hs.get("cycles", []), new_hs.get("cycles", []))
    new_orphans, resolved_orphans = diff_orphans(
        old_hs.get("orphan_candidates", []), new_hs.get("orphan_candidates", [])
    )
    rank_jumps, new_to_top, dropped = diff_ranks(
        old_hs.get("most_connected", []), new_hs.get("most_connected", []), args.rank_jump_threshold
    )

    drift_detected = bool(new_cycles or rank_jumps or new_to_top)

    result = {
        "old_graph": str(Path(args.old_graph).resolve()),
        "new_graph": str(Path(args.new_graph).resolve()),
        "old_generated_at": old.get("generated_at"),
        "new_generated_at": new.get("generated_at"),
        "drift_detected": drift_detected,
        "new_cycles": new_cycles,
        "resolved_cycles": resolved_cycles,
        "new_orphans": new_orphans,
        "resolved_orphans": resolved_orphans,
        "rank_jumps": rank_jumps,
        "new_to_most_connected": new_to_top,
        "dropped_from_most_connected": dropped,
        "rank_jump_threshold": args.rank_jump_threshold,
        "note": (
            "Cycle/orphan comparisons cover the full graph; rank comparisons only cover "
            "modules visible in either run's most_connected top-N (graph_export.py's own "
            "--top-n limit) -- a module ranked just outside the list in both runs is "
            "invisible here, same limitation graph_export.py documents for itself. "
            "drift_detected is true if there's a new cycle, a new entrant to "
            "most_connected, or a rank jump at/above the threshold -- resolved_cycles/"
            "resolved_orphans/dropped_from_most_connected are reported for context but "
            "don't count as drift on their own."
        ),
    }

    print(json.dumps(result, indent=2))
    if args.fail_on_drift and drift_detected:
        sys.exit(1)


if __name__ == "__main__":
    main()
