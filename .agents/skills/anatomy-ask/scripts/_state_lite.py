"""Standalone anatomy hash/diff implementation used by satellite skills.

This file deliberately mirrors anatomy/scripts/_common.py + state.py without
importing another skill's install path. Keep its file-selection semantics in
sync with the canonical implementation; regression tests compare both copies.
Python 3.8+, stdlib only.
"""
import fnmatch
import hashlib
import os
from pathlib import Path

IGNORE_DIR_NAMES = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".env", "dist", "build", "target", ".next", ".nuxt", "out", "coverage",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".idea", ".vscode",
    ".gradle", "obj", "Pods", "DerivedData", ".terraform", ".serverless",
    "egg-info", ".eggs", ".cache", ".parcel-cache", "site-packages",
    "bower_components", ".dart_tool",
}
IGNORE_FILE_SUFFIXES = {".pyc", ".pyo", ".so", ".o", ".class", ".min.js", ".min.css"}
DEFAULT_OUTPUT_PATHS = ("docs/anatomy", "docs/system-trace")


def is_ignored_dir(name):
    return name in IGNORE_DIR_NAMES or (
        name.startswith(".") and name not in {".", "..", ".github", ".circleci"}
    )


class GitIgnoreRule(object):
    def __init__(self, pattern, negated, directory_only, anchored):
        self.pattern = pattern
        self.negated = negated
        self.directory_only = directory_only
        self.anchored = anchored

    def _matches_candidate(self, rel):
        if self.anchored:
            return fnmatch.fnmatchcase(rel, self.pattern)
        if "/" in self.pattern:
            return fnmatch.fnmatchcase(rel, self.pattern) or fnmatch.fnmatchcase(rel, "**/" + self.pattern)
        return any(fnmatch.fnmatchcase(part, self.pattern) for part in rel.split("/"))

    def matches(self, rel_path, is_dir):
        rel = rel_path.replace("\\", "/").lstrip("/")
        if not rel:
            return False
        candidates = [rel]
        if not is_dir:
            parts = rel.split("/")
            candidates.extend("/".join(parts[:i]) for i in range(1, len(parts)))
        for candidate in candidates:
            if self.directory_only and candidate == rel and not is_dir:
                continue
            if self._matches_candidate(candidate):
                return True
        return False


class GitIgnoreMatcher(object):
    def __init__(self, repo_root):
        self.repo_root = Path(repo_root).resolve()
        self.rules = self._load(self.repo_root / ".gitignore")

    @staticmethod
    def _load(path):
        try:
            lines = path.read_text(errors="ignore").splitlines()
        except OSError:
            return []
        rules = []
        for raw in lines:
            line = raw.rstrip()
            if not line:
                continue
            if line.startswith(r"\#"):
                line = line[1:]
            elif line.startswith("#"):
                continue
            negated = False
            if line.startswith(r"\!"):
                line = line[1:]
            elif line.startswith("!"):
                negated = True
                line = line[1:]
            anchored = line.startswith("/")
            if anchored:
                line = line[1:]
            directory_only = line.endswith("/")
            if directory_only:
                line = line[:-1]
            if line:
                rules.append(GitIgnoreRule(line, negated, directory_only, anchored))
        return rules

    def ignored(self, path, is_dir=None):
        try:
            rel = Path(path).resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return False
        if is_dir is None:
            is_dir = Path(path).is_dir()
        ignored = False
        for rule in self.rules:
            if rule.matches(rel, is_dir):
                ignored = not rule.negated
        return ignored


def path_is_within(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def _dedupe_paths(paths):
    out, seen = [], set()
    for raw in paths:
        path = Path(raw).resolve()
        key = os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def normalize_excludes(repo_root, output_root=None, excludes=None, scan_policy=None):
    repo = Path(repo_root).resolve()
    paths = [repo / rel for rel in DEFAULT_OUTPUT_PATHS]
    policy_excludes = []
    if isinstance(scan_policy, dict):
        policy_excludes = scan_policy.get("excludes", []) or []
    for raw in list(policy_excludes) + list(excludes or []) + [output_root]:
        if raw is None:
            continue
        path = Path(raw)
        if not path.is_absolute():
            path = repo / path
        paths.append(path)
    return _dedupe_paths(paths)


def walk_source_files(scan_root, gitignore_root=None, exclude_paths=None):
    scan = Path(scan_root).resolve()
    repo = Path(gitignore_root).resolve() if gitignore_root else scan
    excluded = _dedupe_paths(exclude_paths or [])
    matcher = GitIgnoreMatcher(repo)
    if any(path_is_within(scan, item) for item in excluded):
        return
    for dirpath, dirnames, filenames in os.walk(scan):
        current = Path(dirpath)
        kept = []
        for dirname in sorted(dirnames):
            candidate = current / dirname
            if is_ignored_dir(dirname):
                continue
            if any(path_is_within(candidate, item) for item in excluded):
                continue
            if matcher.ignored(candidate, is_dir=True):
                continue
            kept.append(dirname)
        dirnames[:] = kept
        for filename in sorted(filenames):
            if any(filename.endswith(suffix) for suffix in IGNORE_FILE_SUFFIXES):
                continue
            candidate = current / filename
            if not path_is_within(candidate, repo):
                continue
            if any(path_is_within(candidate, item) for item in excluded):
                continue
            if matcher.ignored(candidate, is_dir=False):
                continue
            yield candidate, candidate.relative_to(scan)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def hash_module(repo_root, module_rel_path, exclude_paths=None):
    repo = Path(repo_root).resolve()
    module_path = (repo / module_rel_path).resolve()
    if not path_is_within(module_path, repo):
        return {"error": "module path escapes repository root: %s" % module_rel_path}
    if not module_path.exists():
        return {"error": "path not found: %s" % module_rel_path}

    file_hashes, errors = [], []
    if module_path.is_file():
        if any(path_is_within(module_path, item) for item in (exclude_paths or [])):
            return {"error": "module path is excluded by scan policy: %s" % module_rel_path}
        try:
            file_hashes.append("%s:%s" % (Path(module_rel_path).as_posix(), sha256_file(module_path)))
        except OSError as exc:
            errors.append({"path": Path(module_rel_path).as_posix(), "error": str(exc)})
    else:
        for abs_path, _rel in walk_source_files(
            module_path,
            gitignore_root=repo,
            exclude_paths=exclude_paths,
        ):
            try:
                rel = abs_path.relative_to(repo).as_posix()
                file_hashes.append("%s:%s" % (rel, sha256_file(abs_path)))
            except (OSError, ValueError) as exc:
                errors.append({"path": str(abs_path), "error": str(exc)})
        file_hashes.sort()
    if errors:
        return {
            "error": "one or more files could not be hashed",
            "file_count": len(file_hashes),
            "file_errors": errors,
        }
    return {"hash": sha256_text("\n".join(file_hashes)), "file_count": len(file_hashes)}


def hash_modules(repo_root, modules_map, output_root=None, excludes=None, scan_policy=None):
    effective = normalize_excludes(repo_root, output_root, excludes, scan_policy)
    return {
        slug: hash_module(repo_root, rel_path, effective)
        for slug, rel_path in sorted(modules_map.items())
    }


def diff_hashes(old_modules, fresh_hashes):
    unchanged, changed, added = [], [], []
    errors = {}
    missing_paths = []
    for slug, info in sorted(fresh_hashes.items()):
        if isinstance(info, dict) and str(info.get("error", "")).startswith("path not found:"):
            missing_paths.append(slug)
            continue
        if not isinstance(info, dict) or info.get("error"):
            errors[slug] = info
            continue
        if slug not in old_modules:
            added.append(slug)
        elif old_modules[slug].get("hash") != info.get("hash"):
            changed.append(slug)
        else:
            unchanged.append(slug)
    removed = sorted(set(slug for slug in old_modules if slug not in fresh_hashes) | set(missing_paths))
    total = len(unchanged) + len(changed) + len(added) + len(removed)
    ratio = (len(changed) + len(added) + len(removed)) / total if total else 0.0
    return {
        "unchanged": unchanged,
        "changed": changed,
        "added": added,
        "removed": removed,
        "errors": errors,
        "change_ratio": round(ratio, 3),
    }
