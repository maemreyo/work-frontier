#!/usr/bin/env python3
"""Export docs/anatomy output as a machine-readable `_graph.json` snapshot."""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import AnatomyInputError, load_module_map_dict  # noqa: E402
from rollup import find_cycles  # noqa: E402
from verify_entry_points import extract_entry_point_rows  # noqa: E402

DEPENDS_HEADING_RE = re.compile(r"^#{1,6}\s*Depends on", re.IGNORECASE)
USED_BY_HEADING_RE = re.compile(r"^#{1,6}\s*Used by", re.IGNORECASE)
ANY_HEADING_RE = re.compile(r"^#{1,6}\s")
INTERNAL_LINE_RE = re.compile(r"^\s*-\s+\*\*`([^`]+)`\*\*\s*(.*)$")
EXTERNAL_LINE_RE = re.compile(r"^\s*-\s+external:\s*`([^`]+)`\s*(.*)$")
LEADING_SEP_RE = re.compile(r"^\s*(?:--|[-\u2013\u2014:])\s*")
TRAILING_CITATION_RE = re.compile(r"\(`([^`]+)`\)\s*\.?\s*$")
UNCONFIRMED_RE = re.compile(r"(?<![A-Za-z0-9])unconfirmed(?![A-Za-z0-9])", re.IGNORECASE)
FOOTER_RE = re.compile(r"Files examined in depth:\s*(.+?)\.?\s*$", re.IGNORECASE)
SAMPLED_RE = re.compile(r"sampled\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE)
ALL_N_RE = re.compile(r"\ball\s+(\d+)\s+files?\b", re.IGNORECASE)


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def extract_edges(text, heading_re):
    edges, in_section = [], False
    for line in text.splitlines():
        if heading_re.match(line):
            in_section = True
            continue
        if in_section and ANY_HEADING_RE.match(line):
            break
        if not in_section:
            continue
        match, kind = INTERNAL_LINE_RE.match(line), "internal"
        if not match:
            match, kind = EXTERNAL_LINE_RE.match(line), "external"
        if not match:
            continue
        target, rest = match.group(1).strip(), match.group(2).strip()
        rest = LEADING_SEP_RE.sub("", rest, count=1)
        citation_match = TRAILING_CITATION_RE.search(rest)
        citation = citation_match.group(1) if citation_match else None
        detail = TRAILING_CITATION_RE.sub("", rest).strip().rstrip(".").strip()
        edges.append({
            "target": target,
            "kind": kind,
            "detail": detail,
            "citation": citation,
            "confirmed": not bool(UNCONFIRMED_RE.search(line)),
        })
    return edges


def extract_coverage(text):
    match = FOOTER_RE.search(text)
    if not match:
        return "unstated", None
    fragment = match.group(1).strip().rstrip("*_.").strip()
    if ALL_N_RE.search(fragment):
        return "full", fragment
    if SAMPLED_RE.search(fragment):
        return "sampled", fragment
    return "listed", fragment


def resolve_source_root(root, explicit):
    if explicit:
        return str(Path(explicit).resolve()), []
    manifest = read_json(root / "_manifest.json")
    if isinstance(manifest, dict) and manifest.get("source_root"):
        return str(manifest["source_root"]), []
    return None, ["source_root unavailable: pass --source-root or write it into _manifest.json"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root")
    parser.add_argument("--source-root", default=None, help="repository root represented by the trace")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--allow-empty-graph", action="store_true")
    parser.add_argument("--allow-module-set-mismatch", action="store_true")
    args = parser.parse_args()
    root = Path(args.output_root).resolve()
    modules_dir = root / "modules"
    if not modules_dir.is_dir():
        print(json.dumps({"error": "not found: %s" % modules_dir}, indent=2))
        sys.exit(2)

    module_map_path = root / "_modules.json"
    try:
        module_paths = load_module_map_dict(module_map_path)
    except AnatomyInputError as exc:
        if not args.allow_module_set_mismatch:
            print(json.dumps({"error": "required non-empty module map not found or invalid: %s" % exc}, indent=2))
            sys.exit(2)
        module_paths = {}
    doc_paths = sorted(modules_dir.glob("*.md"))
    doc_slugs = {path.stem for path in doc_paths}
    mapped_slugs = set(module_paths)
    if mapped_slugs and mapped_slugs != doc_slugs and not args.allow_module_set_mismatch:
        print(json.dumps({
            "error": "module set mismatch between _modules.json and modules/*.md",
            "missing_docs": sorted(mapped_slugs - doc_slugs),
            "extra_docs": sorted(doc_slugs - mapped_slugs),
        }, indent=2))
        sys.exit(1)

    modules = {}
    for path in doc_paths:
        text = path.read_text(errors="ignore")
        status, detail = extract_coverage(text)
        modules[path.stem] = {
            "path": module_paths.get(path.stem),
            "depends_on": extract_edges(text, DEPENDS_HEADING_RE),
            "used_by": extract_edges(text, USED_BY_HEADING_RE),
            "trace_coverage": {"status": status, "detail": detail},
        }

    total_edges = sum(len(value["depends_on"]) + len(value["used_by"]) for value in modules.values())
    if len(modules) > 1 and total_edges == 0 and not args.allow_empty_graph:
        print(json.dumps({
            "error": "parsed multiple module docs but found zero relationship edges; inspect bullet format or pass --allow-empty-graph after manual confirmation",
            "modules_found": len(modules),
        }, indent=2))
        sys.exit(1)

    entry_points = {"http_routes": [], "cli_commands": [], "queue_consumers": [], "cron_jobs": []}
    ep_path = root / "entry-points.md"
    if ep_path.is_file():
        for row in extract_entry_point_rows(ep_path.read_text(errors="ignore")):
            entry_points.setdefault(row["kind"], []).append({
                "module": row["module"],
                "detail": row["detail"],
                "method": row.get("method"),
                "raw": row["raw"],
            })

    all_slugs = sorted(modules)
    internal_depends = {
        slug: {edge["target"] for edge in value["depends_on"] if edge["kind"] == "internal"}
        for slug, value in modules.items()
    }
    internal_used_by = {
        slug: {edge["target"] for edge in value["used_by"] if edge["kind"] == "internal"}
        for slug, value in modules.items()
    }
    degree = {slug: len(internal_depends[slug]) + len(internal_used_by[slug]) for slug in all_slugs}
    most_connected = sorted((
        {
            "module": slug,
            "depends_on_count": len(internal_depends[slug]),
            "used_by_count": len(internal_used_by[slug]),
            "total_degree": degree[slug],
        }
        for slug in all_slugs
    ), key=lambda row: (-row["total_degree"], row["module"]))[:args.top_n]
    orphans = sorted(slug for slug in all_slugs if not internal_depends[slug] and not internal_used_by[slug])
    graph = {slug: internal_depends[slug] & set(all_slugs) for slug in all_slugs}
    cycles = [{"path": path, "length": len(path) - 1} for path in find_cycles(graph)]
    coverage = {"full": 0, "sampled": 0, "listed": 0, "unstated": 0}
    for value in modules.values():
        status = value["trace_coverage"]["status"]
        coverage[status] = coverage.get(status, 0) + 1

    source_root, warnings = resolve_source_root(root, args.source_root)
    result = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_root": source_root,
        "modules": modules,
        "entry_points": entry_points,
        "health_signals": {
            "most_connected": most_connected,
            "orphan_candidates": orphans,
            "cycles": cycles,
            "trace_coverage_counts": coverage,
        },
        "warnings": warnings,
    }
    if args.write:
        target = root / "_graph.json"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".tmp")
            temporary.write_text(json.dumps(result, indent=2) + "\n")
            temporary.replace(target)
        except OSError as exc:
            print(json.dumps({"error": "could not write %s: %s" % (target, exc)}, indent=2))
            sys.exit(2)
        print(json.dumps({"written": str(target), "modules_found": len(modules), "warnings": warnings}, indent=2))
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
