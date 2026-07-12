#!/usr/bin/env python3
"""Lightweight freshness check for anatomy-ask."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state_lite import diff_hashes, hash_modules  # noqa: E402


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--module", default=None)
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()

    output_root = Path(args.output_root).resolve()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd().resolve()
    manifest_path = output_root / "_manifest.json"
    modules_path = output_root / "_modules.json"
    if not manifest_path.is_file() or not modules_path.is_file():
        missing = manifest_path if not manifest_path.is_file() else modules_path
        print(json.dumps({"status": "error", "message": "required trace state not found: %s" % missing}, indent=2))
        sys.exit(2)

    manifest, modules_map = load_json(manifest_path), load_json(modules_path)
    if not valid_trace_state(manifest, modules_map):
        print(json.dumps({"status": "error", "message": "_manifest.json or _modules.json is invalid or empty"}, indent=2))
        sys.exit(2)

    fresh = hash_modules(
        repo_root,
        modules_map,
        output_root=output_root,
        excludes=args.exclude,
        scan_policy=manifest.get("scan_policy"),
    )
    diff = diff_hashes(manifest.get("modules", {}), fresh)
    result = {
        "status": "error" if diff["errors"] else "ok",
        "output_root": str(output_root),
        "generated_at": manifest.get("generated_at"),
        "source_commit_at_last_trace": manifest.get("source_commit"),
        **diff,
    }
    if diff["errors"]:
        result["message"] = "freshness is unknown because one or more module files could not be hashed"

    if args.module:
        slug = args.module
        if slug in diff["unchanged"]:
            module_status, caveat = "unchanged", ""
        elif slug in diff["changed"]:
            module_status = "changed"
            caveat = "`%s` changed since the last anatomy trace; its doc may be stale." % slug
        elif slug in diff["added"]:
            module_status = "added"
            caveat = "`%s` exists in source but has no prior traced manifest entry." % slug
        elif slug in diff["removed"]:
            module_status = "removed"
            caveat = "`%s` remains in the trace state but its source path no longer exists." % slug
        elif slug in diff["errors"]:
            module_status = "unknown"
            caveat = "`%s` could not be hashed; do not claim its documentation is current." % slug
        else:
            module_status = "not_found"
            caveat = "`%s` is not a known module slug in this trace." % slug
        if diff["change_ratio"] > 0 and module_status == "unchanged":
            caveat = "Other modules changed since the trace, but `%s` itself did not." % slug
        result.update({"module": slug, "module_status": module_status, "caveat": caveat})

    print(json.dumps(result, indent=2))
    if diff["errors"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
