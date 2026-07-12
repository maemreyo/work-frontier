#!/usr/bin/env python3
"""
graph_history.py -- maintains docs/anatomy/_graph_history/, an archive of
past _graph.json snapshots, so diff_health_signals.py always has a
previous snapshot to compare the current _graph.json against.

Why this file exists at all: anatomy's graph_export.py --write overwrites
_graph.json in place every run -- by the time anatomy-drift-watch is
invoked (after an anatomy run finishes), the "old" version is already
gone. Rather than changing anatomy's own Phase 5 to keep a backup before
writing (anatomy is meant to stay as-is -- see anatomy-drift-watch's
SKILL.md), this skill keeps its own rolling archive, decoupled from
anatomy's write timing: every time this script's `archive` subcommand
runs, it copies whatever _graph.json currently contains into
_graph_history/ before anything about it changes again on some future
run. As long as `latest` is called (to get the comparison point) BEFORE
`archive` (to record this run's result for next time), the two calls
bracket exactly the same "before vs after" comparison a pre-write copy
would have given, just shifted to run after the fact instead of before.

Subcommands:
  latest <output_root>
      Prints the path to the most recently archived snapshot in
      <output_root>/_graph_history/, or null if none exists yet (first
      run for this repo).

  archive <output_root> [--keep N]
      Copies <output_root>/_graph.json into
      <output_root>/_graph_history/<generated_at>.json (using the
      snapshot's own `generated_at` field, sanitized for a filename;
      falls back to a wall-clock timestamp if that field is missing).
      Prunes down to the N most recent snapshots afterward (default 30)
      so this doesn't grow the output folder unbounded. Prints what it
      did.
"""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SAFE_NAME_RE = re.compile(r"[^0-9A-Za-z_.-]")


def history_dir(output_root: Path) -> Path:
    return output_root / "_graph_history"


def sorted_snapshots(hdir: Path):
    """Sort by file mtime (creation/archive order), not by filename.
    Filenames are generated_at-derived and usually sort chronologically
    too, but a collision-suffix ("-2.json", appended when two archived
    snapshots share the same generated_at -- see cmd_archive) can sort
    lexicographically *before* its un-suffixed sibling ('-' < '.' in
    ASCII), which would silently misorder "latest" and mis-prune "archive"
    if filenames were trusted alone. mtime reflects actual archive order
    regardless of what the filename looks like."""
    return sorted(hdir.glob("*.json"), key=lambda p: p.stat().st_mtime)


def cmd_latest(args):
    hdir = history_dir(Path(args.output_root).resolve())
    if not hdir.is_dir():
        print(json.dumps({"latest": None, "reason": "no _graph_history/ directory yet -- first run"}))
        return
    snapshots = sorted_snapshots(hdir)
    if not snapshots:
        print(json.dumps({"latest": None, "reason": "_graph_history/ exists but is empty"}))
        return
    print(json.dumps({"latest": str(snapshots[-1])}, indent=2))


def cmd_archive(args):
    output_root = Path(args.output_root).resolve()
    graph_path = output_root / "_graph.json"
    if not graph_path.is_file():
        print(json.dumps({"error": f"no _graph.json found at {graph_path} -- nothing to archive"}, indent=2))
        sys.exit(2)

    try:
        graph = json.loads(graph_path.read_text())
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"_graph.json isn't valid JSON: {e}"}, indent=2))
        sys.exit(2)

    generated_at = graph.get("generated_at")
    if generated_at:
        base_name = SAFE_NAME_RE.sub("-", generated_at)
    else:
        base_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-no-timestamp"

    hdir = history_dir(output_root)
    hdir.mkdir(exist_ok=True)

    dest = hdir / f"{base_name}.json"
    suffix = 2
    while dest.exists():
        dest = hdir / f"{base_name}-{suffix}.json"
        suffix += 1

    shutil.copyfile(graph_path, dest)

    keep = args.keep
    snapshots = sorted_snapshots(hdir)
    pruned = []
    if len(snapshots) > keep:
        to_prune = snapshots[: len(snapshots) - keep]
        for p in to_prune:
            p.unlink()
            pruned.append(str(p))

    print(json.dumps({
        "archived": str(dest),
        "total_snapshots": len(snapshots) - len(pruned),
        "pruned": pruned,
    }, indent=2))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("latest")
    p1.add_argument("output_root")
    p1.set_defaults(func=cmd_latest)

    p2 = sub.add_parser("archive")
    p2.add_argument("output_root")
    p2.add_argument("--keep", type=int, default=30, help="max snapshots to retain (default 30)")
    p2.set_defaults(func=cmd_archive)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
