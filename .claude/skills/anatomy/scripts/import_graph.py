#!/usr/bin/env python3
"""
import_graph.py -- heuristic cross-file reference extraction, for Phase 3 of
the anatomy skill's tracing workflow. See external_calls.py for the
complementary script that covers cross-service/network interactions this
one can't see (it only catches same-language import/require/use statements).

Usage:
    python3 import_graph.py <repo_root> [--group-by-top-level]
                            [--modules modules.json]
                            [--output-root PATH] [--exclude PATH ...]

THIS IS A HYPOTHESIS GENERATOR, NOT GROUND TRUTH. Every reported edge must be
opened and confirmed in source before it goes into a module doc or diagram.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    AnatomyInputError,
    load_module_map,
    normalize_excludes,
    resolve_module_for_path,
    resolve_relative_import,
    walk_source_files,
)

PATTERNS = {
    ".py": [re.compile(r"^\s*from\s+([\w\.]+)\s+import"), re.compile(r"^\s*import\s+([\w\.]+)")],
    ".js": [
        re.compile(r"from\s+['\"]([^'\"]+)['\"]"),
        re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)"),
        re.compile(r"import\(\s*['\"]([^'\"]+)['\"]\s*\)"),
    ],
    ".jsx": None, ".ts": None, ".tsx": None, ".mjs": None, ".cjs": None,
    ".go": [re.compile(r'^\s*"([^"]+)"')],
    ".rs": [re.compile(r"^\s*use\s+([\w:]+)")],
    ".java": [re.compile(r"^\s*import\s+(?:static\s+)?([\w\.]+)\s*;")],
    ".kt": [re.compile(r"^\s*import\s+([\w\.]+)")],
    ".rb": [re.compile(r"require(?:_relative)?\s+['\"]([^'\"]+)['\"]")],
    ".php": [re.compile(r"use\s+([\w\\]+)\s*;"), re.compile(r"(?:require|include)(?:_once)?\s*\(?\s*['\"]([^'\"]+)['\"]")],
    ".cs": [re.compile(r"^\s*using\s+([\w\.]+)\s*;")],
    ".swift": [re.compile(r"^\s*(?:@testable\s+)?import\s+([\w\.]+)")],
    ".dart": [re.compile(r"^\s*(?:import|export|part)\s+['\"]([^'\"]+)['\"]")],
    ".scala": [re.compile(r"^\s*import\s+([\w\.{}, ]+)")],
    ".ex": [re.compile(r"^\s*(?:alias|import|use|require)\s+([\w\.]+)")],
    ".c": [re.compile(r'^\s*#\s*include\s*["<]([^">]+)[">]')],
    ".h": [re.compile(r'^\s*#\s*include\s*["<]([^">]+)[">]')],
    ".cpp": None, ".cc": None, ".cxx": None, ".hpp": None,
}
for alias in (".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
    PATTERNS[alias] = PATTERNS[".js"]
for alias in (".cpp", ".cc", ".cxx", ".hpp"):
    PATTERNS[alias] = PATTERNS[".c"]
PATTERNS[".exs"] = PATTERNS[".ex"]


def extract_go_imports(text):
    targets, in_block = [], False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ("):
            in_block = True
            continue
        if in_block:
            if stripped == ")":
                in_block = False
                continue
            match = re.match(r'"([^"]+)"', stripped)
            if match:
                targets.append(match.group(1))
        elif stripped.startswith("import "):
            match = re.search(r'"([^"]+)"', stripped)
            if match:
                targets.append(match.group(1))
    return targets


def extract_imports(path):
    suffix = path.suffix.lower()
    if suffix not in PATTERNS:
        return []
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return []
    if suffix == ".go":
        return extract_go_imports(text)
    targets = []
    for line in text.splitlines():
        for pattern in PATTERNS[suffix]:
            match = pattern.search(line)
            if match:
                targets.append(match.group(1))
    return targets


def top_level_of(rel_path):
    return rel_path.parts[0] if len(rel_path.parts) > 1 else "(root)"


def resolve_target_to_top_level(target, all_top_levels):
    normalized = target.replace(".", "/").replace("\\", "/")
    for segment in [item for item in normalized.split("/") if item]:
        if segment in all_top_levels:
            return segment
    return None


def resolve_target_to_module(source_rel_path, target, module_map, all_slugs):
    resolved_path = resolve_relative_import(source_rel_path, target)
    if resolved_path is not None:
        return resolve_module_for_path(tuple(Path(resolved_path).parts), module_map)
    normalized = target.replace(".", "/").replace("\\", "/").replace(":", "/")
    for segment in [item for item in normalized.split("/") if item]:
        if segment in all_slugs:
            return segment
    return None


# Compatibility alias used by tests/tools written against the first reliability draft.
def resolve_target(source, target, module_map, all_slugs):
    return resolve_target_to_module(str(source), target, module_map, all_slugs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("--group-by-top-level", action="store_true")
    parser.add_argument("--modules", default=None, help="Phase 2 modules.json; groups by actual module boundary")
    parser.add_argument("--output-root", default="docs/anatomy", help="generated anatomy output to exclude from scanning")
    parser.add_argument("--exclude", action="append", default=[], help="additional path to exclude (repeatable)")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if not repo_root.is_dir():
        print(json.dumps({"error": "not a directory: %s" % repo_root}, indent=2))
        sys.exit(2)
    try:
        module_map = load_module_map(args.modules, repo_root)
        excludes = normalize_excludes(repo_root, args.exclude, args.output_root)
    except AnatomyInputError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(2)
    all_slugs = {slug for _parts, slug in module_map} if module_map else set()
    files = list(walk_source_files(repo_root, gitignore_root=repo_root, exclude_paths=excludes))
    top_levels_seen = {rel.parts[0] for _abs, rel in files if len(rel.parts) > 1}

    per_file = []
    for abs_path, rel_path in files:
        targets = extract_imports(abs_path)
        if targets:
            per_file.append({"file": str(rel_path), "imports": targets})
    result = {"repo_root": str(repo_root), "per_file": per_file}

    if args.group_by_top_level:
        edge_counts, unmapped_files = {}, set()
        for entry in per_file:
            rel_path = Path(entry["file"])
            if module_map is not None:
                source = resolve_module_for_path(rel_path.parts, module_map)
                if source is None:
                    unmapped_files.add(entry["file"])
                    continue
            else:
                source = top_level_of(rel_path)
            for target in entry["imports"]:
                destination = (
                    resolve_target_to_module(entry["file"], target, module_map, all_slugs)
                    if module_map is not None
                    else resolve_target_to_top_level(target, top_levels_seen)
                )
                if destination and destination != source:
                    key = (source, destination)
                    edge_counts[key] = edge_counts.get(key, 0) + 1
        result["top_level_edges"] = [
            {"from": source, "to": target, "count": count}
            for (source, target), count in sorted(edge_counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        if module_map is not None:
            result["note"] = "top_level_edges is a hypothesis grouped by --modules boundaries; verify call sites before documenting edges."
            if unmapped_files:
                result["unmapped_files"] = sorted(unmapped_files)
                result["note"] += " unmapped_files fell outside every declared module path."
        else:
            result["note"] = "top_level_edges uses first path segments; pass --modules when a wrapper such as src/ contains the real modules."
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
