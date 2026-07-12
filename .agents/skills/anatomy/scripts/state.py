#!/usr/bin/env python3
"""Manifest hashing/diff helpers for anatomy incremental updates.

Existing commands remain compatible. `hash-modules` now accepts a custom
output root/exclusions and can optionally emit the file-selection policy used
for the hashes.

Usage:
    python3 state.py hash-modules <repo_root> <modules.json> \
        [--output-root PATH] [--exclude PATH ...] [--with-policy]
    python3 state.py diff <old_manifest.json> <fresh_hashes.json>
    python3 state.py write <manifest_path> <data.json>
    python3 state.py git-commit <repo_root>
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    AnatomyInputError,
    load_module_map_dict,
    normalize_excludes,
    path_is_within,
    scan_policy_metadata,
    sha256_file,
    sha256_text,
    walk_source_files,
)


def _read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except OSError as exc:
        raise AnatomyInputError("could not read %s: %s" % (path, exc))
    except json.JSONDecodeError as exc:
        raise AnatomyInputError("invalid JSON in %s: %s" % (path, exc))


def hash_module(repo_root, module_rel_path, exclude_paths=None):
    """Hash one module or return an error-bearing record.

    Unknown file state is never converted into a stable pseudo-hash. A module
    containing an unreadable file receives an `error`, and `state.py diff`
    refuses to classify the run as clean.
    """
    repo = Path(repo_root).resolve()
    module_path = (repo / module_rel_path).resolve()
    if not path_is_within(module_path, repo):
        return {"error": "module path escapes repository root: %s" % module_rel_path}
    if not module_path.exists():
        return {"error": "path not found: %s" % module_rel_path}

    excluded = normalize_excludes(repo, exclude_paths)
    file_hashes = []
    errors = []

    if module_path.is_file():
        if any(path_is_within(module_path, item) for item in excluded):
            return {"error": "module path is excluded by scan policy: %s" % module_rel_path}
        try:
            digest = sha256_file(module_path)
            file_hashes.append("%s:%s" % (Path(module_rel_path).as_posix(), digest))
        except OSError as exc:
            errors.append({"path": Path(module_rel_path).as_posix(), "error": str(exc)})
    else:
        for abs_path, _rel_to_module in walk_source_files(
            module_path,
            gitignore_root=repo,
            exclude_paths=excluded,
        ):
            try:
                rel = abs_path.relative_to(repo).as_posix()
                file_hashes.append("%s:%s" % (rel, sha256_file(abs_path)))
            except (OSError, ValueError) as exc:
                try:
                    rendered = abs_path.relative_to(repo).as_posix()
                except ValueError:
                    rendered = str(abs_path)
                errors.append({"path": rendered, "error": str(exc)})
        file_hashes.sort()

    if errors:
        return {
            "error": "one or more files could not be hashed",
            "file_count": len(file_hashes),
            "file_errors": errors,
        }
    return {
        "hash": sha256_text("\n".join(file_hashes)),
        "file_count": len(file_hashes),
    }


def hash_modules(repo_root, modules, output_root=None, excludes=None):
    repo = Path(repo_root).resolve()
    effective_excludes = normalize_excludes(repo, excludes, output_root)
    return {
        slug: hash_module(repo, rel_path, exclude_paths=effective_excludes)
        for slug, rel_path in sorted(modules.items())
    }


def unwrap_fresh_hashes(payload):
    """Accept the legacy flat shape and the policy-bearing v2 shape."""
    if not isinstance(payload, dict):
        raise AnatomyInputError("fresh hashes JSON must be an object")
    if "modules" in payload and isinstance(payload.get("modules"), dict):
        return payload["modules"], payload.get("scan_policy")
    return payload, None


def canonical_scan_policy(policy):
    if not isinstance(policy, dict):
        return policy
    normalized = dict(policy)
    excludes = normalized.get("excludes")
    if isinstance(excludes, list):
        normalized["excludes"] = sorted(set(str(item) for item in excludes))
    return normalized


def compute_diff(old_manifest, fresh_payload):
    fresh, fresh_policy = unwrap_fresh_hashes(fresh_payload)
    old_modules = old_manifest.get("modules", {}) if isinstance(old_manifest, dict) else {}
    if not isinstance(old_modules, dict):
        raise AnatomyInputError("old manifest's 'modules' field must be an object")

    errors = {
        slug: info
        for slug, info in fresh.items()
        if not isinstance(info, dict) or info.get("error")
    }
    unchanged, changed, added = [], [], []
    for slug, info in sorted(fresh.items()):
        if slug in errors:
            continue
        if slug not in old_modules:
            added.append(slug)
        elif old_modules[slug].get("hash") != info.get("hash"):
            changed.append(slug)
        else:
            unchanged.append(slug)

    # A path-not-found record still represents a currently declared slug. It
    # is an error, not a removal; otherwise a typo in modules.json would make
    # a live module appear safely removed.
    removed = sorted(slug for slug in old_modules if slug not in fresh)
    total = len(unchanged) + len(changed) + len(added) + len(removed)
    ratio = (len(changed) + len(added) + len(removed)) / total if total else 0.0

    old_policy = old_manifest.get("scan_policy") if isinstance(old_manifest, dict) else None
    policy_changed = bool(
        fresh_policy is not None and old_policy is not None
        and canonical_scan_policy(fresh_policy) != canonical_scan_policy(old_policy)
    )
    policy_migrated = bool(fresh_policy is not None and old_policy is None)
    return {
        "unchanged": unchanged,
        "changed": changed,
        "added": added,
        "removed": removed,
        "errors": errors,
        "change_ratio": round(ratio, 3),
        "scan_policy_changed": policy_changed,
        "scan_policy_migrated": policy_migrated,
        "recommendation": (
            "hashing failed for one or more modules -- do not use this diff"
            if errors
            else "scan policy changed -- review exclusions before trusting unchanged classifications"
            if policy_changed
            else "scan policy metadata added -- verify exclusions once before carrying the manifest forward"
            if policy_migrated
            else "more than ~60% of modules differ -- consider a full re-trace"
            if ratio >= 0.6
            else "incremental update looks safe"
        ),
    }


def cmd_hash_modules(args):
    repo = Path(args.repo_root).resolve()
    modules = load_module_map_dict(args.modules_json, repo)
    hashes = hash_modules(repo, modules, args.output_root, args.exclude)
    if args.with_policy:
        payload = {
            "version": 2,
            "scan_policy": scan_policy_metadata(repo, args.exclude, args.output_root),
            "modules": hashes,
        }
    else:
        payload = hashes
    print(json.dumps(payload, indent=2))
    if any(info.get("error") for info in hashes.values()):
        sys.exit(2)


def cmd_diff(args):
    result = compute_diff(_read_json(args.old_manifest), _read_json(args.fresh_hashes))
    print(json.dumps(result, indent=2))
    if result["errors"]:
        sys.exit(2)


def cmd_write(args):
    data = _read_json(args.data_json)
    if not isinstance(data, dict):
        raise AnatomyInputError("manifest data must be a JSON object")
    data["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    target = Path(args.manifest_path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(json.dumps(data, indent=2) + "\n")
        temporary.replace(target)
    except OSError as exc:
        raise AnatomyInputError("could not write %s: %s" % (target, exc))
    print(json.dumps({"written": str(target)}))


def cmd_git_commit(args):
    repo = Path(args.repo_root).resolve()
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        commit = proc.stdout.strip() if proc.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        commit = None
    print(json.dumps({"commit": commit}))


def build_parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    hash_parser = sub.add_parser("hash-modules")
    hash_parser.add_argument("repo_root")
    hash_parser.add_argument("modules_json")
    hash_parser.add_argument(
        "--output-root",
        default=None,
        help="actual anatomy output root; excluded from scans even when a module maps to '.'",
    )
    hash_parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="additional path to exclude (repeatable; relative paths are resolved from repo_root)",
    )
    hash_parser.add_argument(
        "--with-policy",
        action="store_true",
        help="emit {version, scan_policy, modules}; default preserves the legacy flat JSON shape",
    )
    hash_parser.set_defaults(func=cmd_hash_modules)

    diff_parser = sub.add_parser("diff")
    diff_parser.add_argument("old_manifest")
    diff_parser.add_argument("fresh_hashes")
    diff_parser.set_defaults(func=cmd_diff)

    write_parser = sub.add_parser("write")
    write_parser.add_argument("manifest_path")
    write_parser.add_argument("data_json")
    write_parser.set_defaults(func=cmd_write)

    git_parser = sub.add_parser("git-commit")
    git_parser.add_argument("repo_root")
    git_parser.set_defaults(func=cmd_git_commit)
    return parser


def main():
    try:
        args = build_parser().parse_args()
        args.func(args)
    except AnatomyInputError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(2)


if __name__ == "__main__":
    main()
