#!/usr/bin/env python3
"""Build a bounded structural inventory using the shared file-selection rules."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    AMBIGUOUS_DIR_NAMES,
    MANIFEST_FILENAMES,
    detect_language,
    normalize_excludes,
    walk_source_files,
)

CI_KEYWORDS = {
    "test": re.compile(r"\btest\w*\b", re.I),
    "build": re.compile(r"\bbuild\w*\b", re.I),
    "lint": re.compile(r"\blint\w*\b", re.I),
    "deploy": re.compile(r"\bdeploy\w*\b", re.I),
}


def bucket_command(text: str) -> List[str]:
    return sorted(name for name, regex in CI_KEYWORDS.items() if regex.search(text))


def parse_manifest(path: Path) -> dict:
    fields = {}
    try:
        if path.name == "package.json":
            data = json.loads(path.read_text(errors="ignore"))
            fields = {
                "name": data.get("name"),
                "workspaces": data.get("workspaces"),
                "dependencies_sample": list((data.get("dependencies") or {}).keys())[:15],
                "scripts": list((data.get("scripts") or {}).keys()),
            }
        elif path.name == "pyproject.toml":
            try:
                import tomllib
                data = tomllib.loads(path.read_text(errors="ignore"))
                project = data.get("project", {})
                poetry = data.get("tool", {}).get("poetry", {})
                fields = {
                    "name": project.get("name") or poetry.get("name"),
                    "dependencies_sample": (project.get("dependencies") or [])[:15],
                }
            except Exception as exc:
                fields = {"note": "read directly; TOML parser unavailable/unparsable", "parse_error": str(exc)}
        elif path.name == "go.mod":
            for line in path.read_text(errors="ignore").splitlines():
                if line.startswith("module "):
                    fields["module"] = line.split(maxsplit=1)[1].strip()
                    break
        elif path.name == "Cargo.toml":
            try:
                import tomllib
                data = tomllib.loads(path.read_text(errors="ignore"))
                fields = {
                    "name": data.get("package", {}).get("name"),
                    "workspace_members": data.get("workspace", {}).get("members"),
                }
            except Exception as exc:
                fields = {"note": "read directly", "parse_error": str(exc)}
        elif path.name in {"docker-compose.yml", "docker-compose.yaml"}:
            try:
                import yaml
                data = yaml.safe_load(path.read_text(errors="ignore")) or {}
                services = {}
                for name, service in (data.get("services") or {}).items():
                    if not isinstance(service, dict):
                        continue
                    depends_on = service.get("depends_on") or []
                    if isinstance(depends_on, dict):
                        depends_on = list(depends_on)
                    services[name] = {
                        "image": service.get("image"),
                        "build": bool(service.get("build")),
                        "ports": service.get("ports") or [],
                        "depends_on": depends_on,
                    }
                fields["services"] = services
            except Exception as exc:
                fields = {"note": "read compose file directly", "parse_error": str(exc)}
        elif path.name == "composer.json":
            data = json.loads(path.read_text(errors="ignore"))
            fields["name"] = data.get("name")
        elif path.name in {"pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"}:
            fields["note"] = "JVM build file; read directly for modules and commands"
    except Exception as exc:
        fields["parse_error"] = str(exc)
    return fields


def extract_run_commands_regex(text: str) -> List[dict]:
    """Fallback parser that also captures YAML block scalars (`run: |`)."""
    lines = text.splitlines()
    commands = []
    current_name = None
    index = 0
    while index < len(lines):
        line = lines[index]
        name_match = re.match(r"^\s*(?:-\s*)?name:\s*(.+)$", line)
        if name_match:
            current_name = name_match.group(1).strip().strip("'\"")
        run_match = re.match(r"^(\s*)(?:-\s*)?(run|command):\s*(.*)$", line)
        if not run_match:
            index += 1
            continue
        indent, _key, value = run_match.groups()
        value = value.strip()
        if value in {"|", ">", "|-", ">-", "|+", ">+"} or not value:
            block = []
            base_indent = len(indent)
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if candidate.strip() and len(candidate) - len(candidate.lstrip()) <= base_indent:
                    break
                block.append(candidate.strip())
                index += 1
            command = "\n".join(part for part in block if part).strip()
        else:
            command = value.strip("'\"")
            index += 1
        if command:
            commands.append({
                "job": None,
                "step": current_name,
                "command": command,
                "keywords": bucket_command(f"{current_name or ''} {command}"),
            })
    return commands


def extract_run_commands_yaml(data) -> List[dict]:
    commands = []

    def walk(node, job_name=None):
        if isinstance(node, dict):
            jobs = node.get("jobs")
            if isinstance(jobs, dict):
                for name, body in jobs.items():
                    walk(body, name)
            steps = node.get("steps")
            if isinstance(steps, list):
                for step in steps:
                    if not isinstance(step, dict):
                        continue
                    run = step.get("run")
                    name = step.get("name")
                    if isinstance(run, str):
                        commands.append({
                            "job": job_name,
                            "step": name,
                            "command": run.strip(),
                            "keywords": bucket_command(f"{name or ''} {run}"),
                        })
                    elif isinstance(run, dict) and isinstance(run.get("command"), str):
                        command = run["command"].strip()
                        commands.append({
                            "job": job_name,
                            "step": run.get("name") or name,
                            "command": command,
                            "keywords": bucket_command(f"{run.get('name') or name or ''} {command}"),
                        })
            for value in node.values():
                if value is not jobs and value is not steps:
                    walk(value, job_name)
        elif isinstance(node, list):
            for item in node:
                walk(item, job_name)

    walk(data)
    # Deduplicate generic recursion hits.
    unique = []
    seen = set()
    for item in commands:
        key = (item.get("job"), item.get("step"), item["command"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def parse_ci_file(path: Path) -> dict:
    text = path.read_text(errors="ignore")
    try:
        import yaml
        data = yaml.safe_load(text)
        commands = extract_run_commands_yaml(data)
        method = "yaml"
        if not commands:
            commands = extract_run_commands_regex(text)
            method = "regex_fallback"
    except ImportError:
        commands = extract_run_commands_regex(text)
        method = "regex_no_pyyaml"
    except Exception:
        commands = extract_run_commands_regex(text)
        method = "regex_after_yaml_error"
    return {"parse_method": method, "run_commands": commands}


def parse_ci(repo_root: Path) -> dict:
    workflows = []
    gh = repo_root / ".github" / "workflows"
    if gh.is_dir():
        for path in sorted(list(gh.glob("*.yml")) + list(gh.glob("*.yaml"))):
            workflows.append({"provider": "github_actions", "path": path.relative_to(repo_root).as_posix(), **parse_ci_file(path)})
    for name in ("config.yml", "config.yaml"):
        path = repo_root / ".circleci" / name
        if path.is_file():
            workflows.append({"provider": "circleci", "path": path.relative_to(repo_root).as_posix(), **parse_ci_file(path)})
            break
    return {
        "found": bool(workflows),
        "workflows": workflows,
        "note": "CI commands are evidence to verify, not proof that every local command is current.",
    }


# Backward-compatible private names used by older tests/tools.
_bucket_command = bucket_command
_extract_run_commands_via_regex = extract_run_commands_regex
_extract_run_commands_via_yaml = extract_run_commands_yaml
parse_ci_workflow_file = parse_ci_file
parse_ci_config = parse_ci


def build_tree(repo_root: Path, files: List[Tuple[Path, Path]], max_depth: int) -> dict:
    counts = {(): 0}
    for _abs_path, rel in files:
        counts[()] += 1
        parts = rel.parts[:-1]
        for depth in range(1, min(len(parts), max_depth) + 1):
            key = tuple(parts[:depth])
            counts[key] = counts.get(key, 0) + 1

    def node(prefix):
        children_keys = sorted(
            key for key in counts
            if len(key) == len(prefix) + 1 and key[: len(prefix)] == prefix
        )
        result = {"name": prefix[-1] if prefix else repo_root.name, "file_count": counts.get(prefix, 0)}
        if children_keys:
            result["children"] = [node(key) for key in children_keys]
        return result

    return node(())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--top-n-largest", type=int, default=15)
    parser.add_argument("--output-root", default="docs/anatomy")
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if not repo_root.is_dir():
        print(json.dumps({"error": f"not a directory: {repo_root}"}))
        sys.exit(1)
    excludes = normalize_excludes(repo_root, args.exclude, args.output_root)
    files = list(walk_source_files(repo_root, gitignore_root=repo_root, exclude_paths=excludes))

    languages = {}
    manifests = []
    ambiguous = set()
    line_counts = []
    for abs_path, rel_path in files:
        for part in rel_path.parts[:-1]:
            if part in AMBIGUOUS_DIR_NAMES:
                ambiguous.add(part)
        language = detect_language(abs_path)
        if language:
            languages[language] = languages.get(language, 0) + 1
            try:
                line_counts.append((rel_path.as_posix(), sum(1 for _ in abs_path.open(errors="ignore"))))
            except OSError:
                pass
        if abs_path.name in MANIFEST_FILENAMES:
            manifests.append({"path": rel_path.as_posix(), "type": abs_path.name, "fields": parse_manifest(abs_path)})

    top_counts = {}
    root_files = []
    for _abs_path, rel in files:
        if len(rel.parts) == 1:
            root_files.append(rel.name)
        else:
            top_counts[rel.parts[0]] = top_counts.get(rel.parts[0], 0) + 1
    top_level = [
        {"name": name, "type": "dir", "file_count": count}
        for name, count in sorted(top_counts.items())
    ] + [{"name": name, "type": "file"} for name in sorted(root_files)]

    line_counts.sort(key=lambda item: (-item[1], item[0]))
    print(json.dumps({
        "repo_root": str(repo_root),
        "excluded_paths": [str(path) for path in excludes],
        "total_files_scanned": len(files),
        "languages": dict(sorted(languages.items(), key=lambda item: (-item[1], item[0]))),
        "manifests": manifests,
        "ci_config": parse_ci(repo_root),
        "top_level": top_level,
        "ambiguous_dirs_found": sorted(ambiguous),
        "largest_files_by_line_count": [
            {"path": path, "lines": count}
            for path, count in line_counts[: args.top_n_largest]
        ],
        "directory_tree": build_tree(repo_root, files, args.max_depth),
    }, indent=2))


if __name__ == "__main__":
    main()
