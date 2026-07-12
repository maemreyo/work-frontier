#!/usr/bin/env python3
"""Pass/fail docs-staleness gate for an existing anatomy trace."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state_lite import diff_hashes, hash_modules  # noqa: E402

SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


def load_json(path):
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: %r" % key)
            result[key] = value
        return result
    try:
        return json.loads(Path(path).read_text(), object_pairs_hook=no_duplicates)
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def valid_trace_state(manifest, modules_map):
    if not isinstance(manifest, dict) or not isinstance(modules_map, dict) or not modules_map:
        return False
    old_modules = manifest.get("modules")
    if not isinstance(old_modules, dict):
        return False
    return all(
        isinstance(slug, str) and slug.strip() and isinstance(path, str) and path.strip()
        for slug, path in modules_map.items()
    )


def git_head(repo_root):
    try:
        proc = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10)
        return proc.stdout.strip() if proc.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def classify(diff, graph):
    findings = []
    for slug in diff["removed"]:
        findings.append({"module": slug, "status": "removed", "severity": "high", "reason": "the persisted module source path no longer exists; stale docs may remain"})
    for slug in diff["added"]:
        findings.append({"module": slug, "status": "added", "severity": "high", "reason": "source module has no prior manifest entry"})
    for slug, info in sorted(diff.get("errors", {}).items()):
        findings.append({"module": slug, "status": "unknown", "severity": "high", "reason": "hashing failed; freshness cannot be established", "detail": info})

    graph_unavailable = not isinstance(graph, dict)
    most_connected, orphans = {}, set()
    if not graph_unavailable:
        health = graph.get("health_signals", {})
        for rank, row in enumerate(health.get("most_connected", []), start=1):
            most_connected[row.get("module")] = {"rank": rank, "total_degree": row.get("total_degree")}
        orphans = set(health.get("orphan_candidates", []))
    for slug in diff["changed"]:
        if graph_unavailable:
            severity, reason = "medium", "source changed; _graph.json unavailable so centrality-based ranking is unavailable"
        elif slug in most_connected:
            item = most_connected[slug]
            severity, reason = "high", "source changed; module ranks #%s in most_connected (degree %s)" % (item["rank"], item["total_degree"])
        elif slug in orphans:
            severity, reason = "low", "source changed; prior graph classified the module as an orphan candidate"
        else:
            severity, reason = "medium", "source changed since the last trace"
        findings.append({"module": slug, "status": "changed", "severity": severity, "reason": reason})
    return findings, graph_unavailable


def format_text(result):
    lines = ["docs-staleness gate: %s" % result["status"].upper()]
    for finding in sorted(result["findings"], key=lambda item: (-SEVERITY_RANK[item["severity"]], item["module"])):
        lines.append("  [%-6s] %s (%s) -- %s" % (finding["severity"].upper(), finding["module"], finding["status"], finding["reason"]))
    if not result["findings"]:
        lines.append("  docs/anatomy is hash-consistent with source")
    lines.append("  change_ratio=%s fail_on=%s" % (result["change_ratio"], result["fail_on"]))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--fail-on", choices=["high", "medium", "low", "none"], default="high")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()

    output_root = Path(args.output_root).resolve()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd().resolve()
    manifest, modules_map = load_json(output_root / "_manifest.json"), load_json(output_root / "_modules.json")
    if not valid_trace_state(manifest, modules_map):
        print(json.dumps({"status": "error", "message": "missing, unreadable, invalid, or empty _manifest.json/_modules.json"}, indent=2))
        sys.exit(2)
    fresh = hash_modules(repo_root, modules_map, output_root=output_root, excludes=args.exclude, scan_policy=manifest.get("scan_policy"))
    diff = diff_hashes(manifest.get("modules", {}), fresh)
    graph = load_json(output_root / "_graph.json")
    findings, graph_unavailable = classify(diff, graph)
    fails = False if args.fail_on == "none" else any(SEVERITY_RANK[item["severity"]] >= SEVERITY_RANK[args.fail_on] for item in findings)
    hashing_unknown = bool(diff.get("errors"))
    result = {
        "status": "error" if hashing_unknown else ("fail" if fails else "pass"),
        "output_root": str(output_root),
        "repo_root": str(repo_root),
        "source_commit_at_last_trace": manifest.get("source_commit"),
        "current_commit": git_head(repo_root),
        "change_ratio": diff["change_ratio"],
        "unchanged_count": len(diff["unchanged"]),
        "findings": findings,
        "graph_unavailable": graph_unavailable,
        "fail_on": args.fail_on,
        "note": "Unreadable files are high-severity unknowns, never stable pseudo-hashes.",
    }
    print(format_text(result) if args.format == "text" else json.dumps(result, indent=2))
    if hashing_unknown:
        sys.exit(2)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
