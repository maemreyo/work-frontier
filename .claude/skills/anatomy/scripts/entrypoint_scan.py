#!/usr/bin/env python3
"""Create source-level entry-point hypotheses for route/CLI/queue/cron coverage."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    AnatomyInputError,
    load_module_map,
    normalize_excludes,
    resolve_module_for_path,
    walk_source_files,
)

ROUTES = [
    ("flask", re.compile(r"@\w*\.route\(\s*['\"]([^'\"]+)['\"]")),
    ("fastapi", re.compile(r"@\w+\.(get|post|put|delete|patch|head|options)\(\s*['\"]([^'\"]+)")),
    ("express", re.compile(r"\b(?:app|router)\.(get|post|put|delete|patch|all)\(\s*['\"]([^'\"]+)")),
    ("rails", re.compile(r"^\s*(get|post|put|patch|delete)\s+['\"]([^'\"]+)")),
    ("spring", re.compile(r"@(Get|Post|Put|Delete|Patch|Request)Mapping\(\s*(?:value\s*=\s*)?['\"]([^'\"]*)")),
    ("laravel", re.compile(r"Route::(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)")),
]
CLI = [
    ("click", re.compile(r"@\w+\.command\(\s*(?:name\s*=\s*)?['\"]([^'\"]+)")),
    ("argparse", re.compile(r"add_parser\(\s*['\"]([^'\"]+)")),
    ("commander", re.compile(r"\.command\(\s*['\"]([^'\" ]+)")),
    ("cobra", re.compile(r"Use:\s*['\"]([^'\" ]+)")),
]
QUEUE = [
    ("consume", re.compile(r"\.(?:subscribe|consume|on)\(\s*['\"]([^'\"]+)")),
    ("consume", re.compile(r"KafkaConsumer\(\s*['\"]([^'\"]+)")),
]
CRON = [
    ("node-cron", re.compile(r"cron\.schedule\(\s*['\"]([^'\"]+)")),
    ("decorator", re.compile(r"@(?:scheduled|cron)\(\s*['\"]([^'\"]+)")),
]


def owner(rel: Path, module_map):
    result = resolve_module_for_path(rel.parts, module_map) if module_map is not None else None
    return result or (rel.parts[0] if len(rel.parts) > 1 else "(root)")


def scan(rel: Path, text: str, module_map) -> List[dict]:
    findings = []
    module = owner(rel, module_map)
    for number, line in enumerate(text.splitlines(), start=1):
        for framework, regex in ROUTES:
            match = regex.search(line)
            if not match:
                continue
            if framework == "flask":
                path = match.group(1)
                methods_match = re.search(r"methods\s*=\s*\[([^]]+)\]", line)
                methods = re.findall(r"['\"]([A-Za-z]+)['\"]", methods_match.group(1) if methods_match else "") or ["ANY"]
            else:
                methods = [match.group(1).upper().replace("REQUEST", "ANY")]
                path = match.group(2)
            for method in methods:
                findings.append({"kind": "http_routes", "module": module, "method": method.upper(), "detail": path, "file": rel.as_posix(), "line": number, "framework": framework, "confidence": "hypothesis"})
        for framework, regex in CLI:
            match = regex.search(line)
            if match:
                findings.append({"kind": "cli_commands", "module": module, "detail": match.group(1), "file": rel.as_posix(), "line": number, "framework": framework, "confidence": "hypothesis"})
        for _direction, regex in QUEUE:
            match = regex.search(line)
            if match:
                findings.append({"kind": "queue_consumers", "module": module, "detail": match.group(1), "file": rel.as_posix(), "line": number, "framework": "queue", "confidence": "hypothesis"})
        for framework, regex in CRON:
            match = regex.search(line)
            if match:
                findings.append({"kind": "cron_jobs", "module": module, "detail": match.group(1), "file": rel.as_posix(), "line": number, "framework": framework, "confidence": "hypothesis"})
    return findings


def dedupe_findings(findings):
    """Remove duplicate regex hits while preserving stable source order."""
    result = []
    seen = set()
    for finding in findings:
        key = (
            finding.get("kind"), finding.get("module"), finding.get("method"),
            finding.get("detail"), finding.get("file"), finding.get("line"),
        )
        if key not in seen:
            seen.add(key)
            result.append(finding)
    return result


def write_atomically(path, text):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(text)
    temporary.replace(target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("--modules", required=True)
    parser.add_argument("--output-root", default="docs/anatomy")
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--write", help="write JSON to this path instead of stdout")
    args = parser.parse_args()
    repo = Path(args.repo_root).resolve()
    if not repo.is_dir():
        print(json.dumps({"error": "not a directory: %s" % repo}, indent=2))
        sys.exit(2)
    try:
        module_map = load_module_map(args.modules, repo)
        excludes = normalize_excludes(repo, args.exclude, args.output_root)
    except AnatomyInputError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(2)
    findings = []
    scan_errors = []
    for path, rel in walk_source_files(repo, gitignore_root=repo, exclude_paths=excludes):
        try:
            findings.extend(scan(rel, path.read_text(errors="ignore"), module_map))
        except OSError as exc:
            scan_errors.append({"file": rel.as_posix(), "error": str(exc)})
    findings = dedupe_findings(findings)
    payload = {
        "repo_root": str(repo),
        "hypotheses": findings,
        "scan_errors": scan_errors,
        "note": (
            "Every hypothesis must be reviewed against framework wiring/source before it becomes canonical. "
            "For a false positive, add disposition=false_positive and a review_note before running "
            "verify_entry_points.py --strict-source."
        ),
    }
    text = json.dumps(payload, indent=2) + "\n"
    if args.write:
        try:
            write_atomically(args.write, text)
        except OSError as exc:
            print(json.dumps({"error": "could not write %s: %s" % (args.write, exc)}, indent=2))
            sys.exit(2)
        print(json.dumps({"written": str(Path(args.write).resolve()), "hypotheses": len(findings)}))
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
