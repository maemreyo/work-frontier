"""Shared helpers for the anatomy skill's scripts.

No third-party dependencies: this module runs anywhere Python 3.8+ runs.
Every scanner and hasher must use the same file-selection contract so an
incremental manifest cannot disagree with inventory/import scans merely because
those commands walked different files.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple, Union

# Directories that are unambiguously generated/dependency/VCS state. `bin` is
# intentionally absent: many repositories keep first-party CLI source there.
IGNORE_DIR_NAMES = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".env", "dist", "build", "target", ".next", ".nuxt", "out",
    "coverage", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    ".idea", ".vscode", ".gradle", "obj", "Pods", "DerivedData",
    ".terraform", ".serverless", "egg-info", ".eggs", ".cache", ".parcel-cache",
    "site-packages", "bower_components", ".dart_tool",
}

# These names can contain either first-party code or vendored/generated code.
# Walk them, but surface them to the inventory for a human decision.
AMBIGUOUS_DIR_NAMES = {"packages", "vendor", "third_party", "external", "bin"}

IGNORE_FILE_SUFFIXES = {".pyc", ".pyo", ".so", ".o", ".class", ".min.js", ".min.css"}
DEFAULT_OUTPUT_PATHS = ("docs/anatomy", "docs/system-trace")

LANGUAGE_BY_EXT = {
    ".py": "Python", ".pyi": "Python",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".go": "Go", ".rs": "Rust",
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".rb": "Ruby", ".php": "PHP", ".cs": "C#",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++",
    ".c": "C", ".h": "C/C++ header", ".swift": "Swift", ".m": "Objective-C",
    ".scala": "Scala", ".ex": "Elixir", ".exs": "Elixir", ".dart": "Dart",
    ".sql": "SQL", ".sh": "Shell", ".bash": "Shell", ".vue": "Vue",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS",
}

MANIFEST_FILENAMES = {
    "package.json", "pnpm-workspace.yaml", "lerna.json", "nx.json", "turbo.json",
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile", "poetry.lock",
    "go.mod", "go.work", "Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts",
    "settings.gradle", "composer.json", "Gemfile", "mix.exs", "Dockerfile",
    "docker-compose.yml", "docker-compose.yaml", "Makefile", ".env.example",
}


class AnatomyInputError(ValueError):
    """Raised when input would make a scan or module map ambiguous/unsafe."""


@dataclass(frozen=True)
class GitIgnoreRule:
    pattern: str
    negated: bool
    directory_only: bool
    anchored: bool

    def matches(self, rel_path: str, *, is_dir: bool) -> bool:
        rel = rel_path.replace("\\", "/").lstrip("/")
        if not rel:
            return False

        candidates = [rel]
        if not is_dir:
            # A directory rule also applies to every descendant of that dir.
            parts = rel.split("/")
            candidates.extend("/".join(parts[:i]) for i in range(1, len(parts)))

        for candidate in candidates:
            if self.directory_only and candidate == rel and not is_dir:
                continue
            if self._matches_candidate(candidate):
                return True
        return False

    def _matches_candidate(self, rel: str) -> bool:
        if self.anchored:
            return fnmatch.fnmatchcase(rel, self.pattern)
        if "/" in self.pattern:
            # Git treats slash-containing unanchored patterns relative to any
            # directory below the .gitignore root.
            return fnmatch.fnmatchcase(rel, self.pattern) or fnmatch.fnmatchcase(rel, f"**/{self.pattern}")
        return any(fnmatch.fnmatchcase(part, self.pattern) for part in rel.split("/"))


class GitIgnoreMatcher:
    """Deterministic stdlib-only subset of .gitignore semantics.

    Supports ordered rules, comments, escaped leading `#`/`!`, negation,
    root-anchored patterns, trailing-slash directory rules, and fnmatch
    wildcards including `**`. It intentionally does not claim perfect Git
    parity, but unlike the previous reader it does not discard every pattern
    containing `/` or every ordinary trailing-slash rule.
    """

    def __init__(self, repo_root: Union[Path, str]):
        self.repo_root = Path(repo_root).resolve()
        self.rules = self._load(self.repo_root / ".gitignore")

    @staticmethod
    def _load(path: Path) -> List[GitIgnoreRule]:
        try:
            lines = path.read_text(errors="ignore").splitlines()
        except OSError:
            return []

        rules: List[GitIgnoreRule] = []
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

    def ignored(self, path: Path, *, is_dir: Optional[bool] = None) -> bool:
        try:
            rel = path.resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return False
        if is_dir is None:
            is_dir = path.is_dir()
        ignored = False
        for rule in self.rules:
            if rule.matches(rel, is_dir=is_dir):
                ignored = not rule.negated
        return ignored


def is_ignored_dir(name: str) -> bool:
    return name in IGNORE_DIR_NAMES or (
        name.startswith(".") and name not in {".", "..", ".github", ".circleci"}
    )


def _dedupe_paths(paths: Iterable[Path]) -> List[Path]:
    result: List[Path] = []
    seen: Set[str] = set()
    for raw in paths:
        resolved = Path(raw).resolve()
        key = os.path.normcase(str(resolved))
        if key not in seen:
            seen.add(key)
            result.append(resolved)
    return result


def normalize_excludes(
    repo_root: Union[Path, str],
    excludes: Optional[Sequence[Union[Path, str]]] = None,
    output_root: Optional[Union[Path, str]] = None,
) -> List[Path]:
    """Return absolute exclusion roots.

    The two historical output locations are always excluded. A custom output
    root must be supplied by callers through `output_root`; additional
    repeatable paths can be supplied through `excludes`.
    """
    repo = Path(repo_root).resolve()
    paths: List[Path] = [repo / rel for rel in DEFAULT_OUTPUT_PATHS]
    for raw in [output_root, *(excludes or ())]:
        if raw is None:
            continue
        path = Path(raw)
        if not path.is_absolute():
            path = repo / path
        paths.append(path)
    return _dedupe_paths(paths)


def scan_policy_metadata(
    repo_root: Union[Path, str],
    excludes: Optional[Sequence[Union[Path, str]]] = None,
    output_root: Optional[Union[Path, str]] = None,
) -> dict:
    repo = Path(repo_root).resolve()
    normalized = normalize_excludes(repo, excludes, output_root)
    rendered = []
    for path in normalized:
        try:
            rendered.append(path.relative_to(repo).as_posix())
        except ValueError:
            rendered.append(str(path))
    return {
        "version": 1,
        "gitignore_root": ".",
        # Policy comparison is semantic: CLI ordering of equivalent excludes
        # must not manufacture a stale-state signal.
        "excludes": sorted(set(rendered)),
        "unreadable_file_policy": "error",
    }


def path_is_within(path: Union[Path, str], parent: Union[Path, str]) -> bool:
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def is_ignored_path(
    path: Union[Path, str],
    *,
    repo_root: Union[Path, str],
    exclude_paths: Optional[Sequence[Union[Path, str]]] = None,
    matcher: Optional[GitIgnoreMatcher] = None,
    is_dir: Optional[bool] = None,
) -> bool:
    candidate = Path(path).resolve()
    if any(path_is_within(candidate, excluded) for excluded in (exclude_paths or ())):
        return True
    if is_dir is None:
        is_dir = candidate.is_dir()
    if is_dir and is_ignored_dir(candidate.name):
        return True
    active_matcher = matcher if matcher is not None else GitIgnoreMatcher(repo_root)
    return active_matcher.ignored(candidate, is_dir=is_dir)


def walk_source_files(
    scan_root: Union[Path, str],
    *,
    gitignore_root: Optional[Union[Path, str]] = None,
    exclude_paths: Optional[Sequence[Union[Path, str]]] = None,
) -> Iterator[Tuple[Path, Path]]:
    """Yield `(absolute_path, path_relative_to_scan_root)` for source files.

    `gitignore_root` is deliberately separate from `scan_root`: hashing a
    module at `src/api` must still respect the repository-root `.gitignore`.
    Existing one-argument callers retain their old behavior.
    """
    scan = Path(scan_root).resolve()
    repo = Path(gitignore_root).resolve() if gitignore_root else scan
    excludes = _dedupe_paths(Path(p) for p in (exclude_paths or ()))
    matcher = GitIgnoreMatcher(repo)

    if any(path_is_within(scan, excluded) for excluded in excludes):
        return

    for dirpath, dirnames, filenames in os.walk(scan):
        current = Path(dirpath)
        kept: List[str] = []
        for dirname in sorted(dirnames):
            candidate = current / dirname
            if is_ignored_path(
                candidate,
                repo_root=repo,
                exclude_paths=excludes,
                matcher=matcher,
                is_dir=True,
            ):
                continue
            kept.append(dirname)
        dirnames[:] = kept

        for filename in sorted(filenames):
            if any(filename.endswith(suffix) for suffix in IGNORE_FILE_SUFFIXES):
                continue
            candidate = current / filename
            if not path_is_within(candidate, repo):
                continue
            if is_ignored_path(
                candidate,
                repo_root=repo,
                exclude_paths=excludes,
                matcher=matcher,
                is_dir=False,
            ):
                continue
            try:
                rel = candidate.relative_to(scan)
            except ValueError:
                continue
            yield candidate, rel


def detect_language(path: Path):
    return LANGUAGE_BY_EXT.get(path.suffix.lower())


def sha256_file(path: Path) -> str:
    """Hash a file or raise OSError when its state is unknown."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def slugify(name: str) -> str:
    """Return a filename/Mermaid-safe ASCII slug.

    Use `stable_slug_map` when deriving multiple slugs so collisions are
    detected and disambiguated deterministically.
    """
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower().strip()).strip("-")
    if slug:
        return slug
    return "module-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]


def stable_slug_map(items: Iterable[Tuple[str, str]]) -> Dict[str, str]:
    """Build `{source_path: slug}` from `(display_name, source_path)` pairs.

    Slugs are assigned over the complete candidate set. Normalization
    collisions receive a deterministic path-derived suffix, and a final global
    uniqueness pass also covers the rarer case where that suffixed value equals
    another module's natural slug (or two path hashes share a prefix).
    """
    prepared = [(name, Path(path).as_posix()) for name, path in items]
    source_paths = [path for _name, path in prepared]
    if len(source_paths) != len(set(source_paths)):
        raise AnatomyInputError("stable_slug_map received the same source path more than once")

    rows = [(slugify(name), path) for name, path in prepared]
    base_counts: Dict[str, int] = {}
    for base, _path in rows:
        base_counts[base] = base_counts.get(base, 0) + 1

    result: Dict[str, str] = {}
    used: Set[str] = set()
    for base, path in sorted(rows, key=lambda item: (item[0], item[1])):
        digest = hashlib.sha1(path.encode("utf-8")).hexdigest()
        candidate = base if base_counts[base] == 1 else "%s-%s" % (base, digest[:8])
        width = 8
        counter = 2
        while candidate in used:
            if width < len(digest):
                width = min(width + 4, len(digest))
                candidate = "%s-%s" % (base, digest[:width])
            else:
                candidate = "%s-%s-%d" % (base, digest, counter)
                counter += 1
        used.add(candidate)
        result[path] = candidate
    return result


def _load_json_object_without_duplicate_keys(path: Path) -> object:
    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise AnatomyInputError(f"duplicate JSON key in {path}: {key!r}")
            out[key] = value
        return out

    return json.loads(path.read_text(), object_pairs_hook=hook)


def validate_module_map(data: object, repo_root: Optional[Union[Path, str]] = None) -> Dict[str, str]:
    if not isinstance(data, dict) or not data:
        raise AnatomyInputError("modules.json must be a non-empty JSON object of slug -> relative path")
    root = Path(repo_root).resolve() if repo_root else None
    result: Dict[str, str] = {}
    seen_paths: Dict[str, str] = {}
    for raw_slug, raw_path in data.items():
        if not isinstance(raw_slug, str) or not isinstance(raw_path, str):
            raise AnatomyInputError("every module slug and path must be a string")
        slug = raw_slug.strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug):
            raise AnatomyInputError(
                f"invalid module slug {raw_slug!r}; use slugify()/stable_slug_map() and ASCII lowercase letters, digits, '-' or '_'"
            )
        rel = Path(raw_path)
        if rel.is_absolute() or ".." in rel.parts:
            raise AnatomyInputError(f"module {slug!r} has unsafe path {raw_path!r}")
        normalized = rel.as_posix() or "."
        path_key = os.path.normcase(normalized)
        if path_key in seen_paths:
            raise AnatomyInputError(
                f"modules {seen_paths[path_key]!r} and {slug!r} map to the same path {normalized!r}"
            )
        if root is not None and not path_is_within(root / rel, root):
            raise AnatomyInputError(f"module {slug!r} escapes repository root")
        seen_paths[path_key] = slug
        result[slug] = normalized
    return result


def load_module_map_dict(modules_json_path, repo_root: Optional[Union[Path, str]] = None):
    """Load and validate the raw `{slug: relative_path}` mapping."""
    path = Path(modules_json_path)
    try:
        raw = _load_json_object_without_duplicate_keys(path)
    except OSError as exc:
        raise AnatomyInputError("could not read %s: %s" % (path, exc))
    except json.JSONDecodeError as exc:
        raise AnatomyInputError("invalid JSON in %s: %s" % (path, exc))
    return validate_module_map(raw, repo_root)


def load_module_map(modules_json_path, repo_root: Optional[Union[Path, str]] = None):
    """Load Phase-2 modules.json sorted longest-path-first for prefix matching."""
    if not modules_json_path:
        return None
    data = load_module_map_dict(modules_json_path, repo_root)
    entries = []
    for slug, rel in data.items():
        parts = tuple(part for part in Path(rel).parts if part != ".")
        entries.append((parts, slug))
    entries.sort(key=lambda entry: (-len(entry[0]), entry[1]))
    return entries


def resolve_module_for_path(rel_path_parts, module_map):
    if module_map is None:
        return None
    parts = tuple(rel_path_parts)
    for prefix_parts, slug in module_map:
        if parts[: len(prefix_parts)] == prefix_parts:
            return slug
    return None


def resolve_relative_import(source_rel_path, target: str):
    """Resolve JS/TS filesystem imports and Python package-relative imports.

    Returns a repo-relative hypothesis path, or None for bare/external imports
    and for imports that escape above the repository root.
    """
    source = Path(source_rel_path)
    suffix = source.suffix.lower()

    if suffix in {".py", ".pyi"} and target.startswith(".") and not target.startswith(("./", "../")):
        leading = len(target) - len(target.lstrip("."))
        remainder = target[leading:]
        base = source.parent
        for _ in range(leading - 1):
            if base == Path("."):
                return None
            base = base.parent
        if remainder:
            base = base.joinpath(*[part for part in remainder.split(".") if part])
        normalized = os.path.normpath(base.as_posix()).replace("\\", "/")
    else:
        if not target.startswith(("./", "../", ".\\", "..\\")):
            return None
        normalized = os.path.normpath((source.parent / target).as_posix()).replace("\\", "/")

    if normalized == ".." or normalized.startswith("../"):
        return None
    return normalized
