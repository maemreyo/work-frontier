#!/usr/bin/env python3
"""Check anatomy docs for content drift and source-input drift.

Two modes (select with --mode):

  check   (default) — read-only.  Fails when anatomy output is stale
          relative to source code *or* when the anatomy output files
          themselves have diverged from the last-known content digest.

  update  — computes fresh content_digest and source_input_digest and
          writes them into _manifest.json.  Never runs automatically;
          only invoked explicitly by the developer who regenerated docs.

Exit codes:
  0 — no drift
  1 — drift detected (check mode only)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Source and config file patterns that affect anatomy output.  When any
# of these change the anatomy *should* be regenerated.
_SOURCE_INPUT_PATTERNS: tuple[str, ...] = (
    "backend/src/work_frontier/contracts/**/*.py",
    "backend/src/work_frontier/domain/**/*.py",
    "backend/src/work_frontier/application/**/*.py",
    "backend/src/work_frontier/adapters/**/*.py",
    "backend/src/work_frontier/interfaces/**/*.py",
    "scripts/**/*.py",
    "pyproject.toml",
    "AGENTS.md",
    "CLAUDE.md",
)


def _hash_file_blake2b(path: Path) -> str:
    h = hashlib.blake2b(digest_size=32)
    h.update(path.read_bytes())
    return h.hexdigest()


def _compute_content_digest(anatomy_root: Path) -> str | None:
    entries: list[tuple[str, str]] = []
    for entry in sorted(anatomy_root.rglob("*")):
        if not entry.is_file():
            continue
        if entry.name == "_manifest.json":
            continue
        if entry.name.startswith("."):
            continue
        rel = entry.relative_to(anatomy_root)
        entries.append((str(rel), _hash_file_blake2b(entry)))
    if not entries:
        return None
    h = hashlib.blake2b(digest_size=32)
    for rel_path, file_hash in entries:
        h.update(rel_path.encode("utf-8"))
        h.update(b"\x00")
        h.update(file_hash.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _compute_source_input_digest(repo_root: Path) -> str | None:
    h = hashlib.blake2b(digest_size=32)
    found_any = False
    for pattern in _SOURCE_INPUT_PATTERNS:
        for path in sorted(repo_root.glob(pattern)):
            if not path.is_file():
                continue
            found_any = True
            rel = path.relative_to(repo_root)
            h.update(str(rel).encode("utf-8"))
            h.update(b"\x00")
            h.update(_hash_file_blake2b(path).encode("utf-8"))
            h.update(b"\x00")
    if not found_any:
        return None
    return h.hexdigest()


def _cmd_check(args: argparse.Namespace) -> int:
    root = args.anatomy_root
    manifest_path = root / "_manifest.json"
    repo_root = args.repo_root

    if not root.is_dir():
        print(f"ERROR: anatomy root not found: {root}", file=sys.stderr)
        return 1

    if not manifest_path.is_file():
        print(f"ERROR: _manifest.json not found in {root}", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_bytes())
    stored_content = manifest.get("content_digest")
    stored_source = manifest.get("source_input_digest")

    if stored_content is None and stored_source is None:
        print(
            "ERROR: _manifest.json has no content_digest or "
            "source_input_digest. Run with --mode update first.",
            file=sys.stderr,
        )
        return 1

    failures: list[str] = []

    if stored_content is not None:
        current_content = _compute_content_digest(root)
        if current_content is None:
            failures.append("anatomy content directory is empty")
        elif current_content != stored_content:
            failures.append(
                f"anatomy content digest mismatch\n"
                f"  stored:   {stored_content}\n"
                f"  current:  {current_content}\n"
                f"  Regenerate anatomy docs."
            )

    if stored_source is not None:
        current_source = _compute_source_input_digest(repo_root)
        if current_source is None:
            failures.append("could not compute source input digest")
        elif current_source != stored_source:
            failures.append(
                f"anatomy source-input digest mismatch — source code has "
                f"changed since anatomy was last regenerated.\n"
                f"  stored:   {stored_source}\n"
                f"  current:  {current_source}\n"
                f"  Regenerate anatomy docs with the `anatomy` skill."
            )

    if failures:
        for msg in failures:
            print(f"ERROR: {msg}", file=sys.stderr)
        return 1

    print(
        f"anatomy checks OK (content={'computed' if stored_content else 'N/A'}, "
        f"source={'computed' if stored_source else 'N/A'})"
    )
    return 0


def _cmd_update(args: argparse.Namespace) -> int:
    root = args.anatomy_root
    manifest_path = root / "_manifest.json"
    repo_root = args.repo_root

    if not root.is_dir():
        print(f"ERROR: anatomy root not found: {root}", file=sys.stderr)
        return 1

    manifest: dict[str, object] = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_bytes())

    current_content = _compute_content_digest(root)
    if current_content is None:
        print("ERROR: anatomy content directory is empty", file=sys.stderr)
        return 1

    manifest["content_digest"] = current_content

    current_source = _compute_source_input_digest(repo_root)
    if current_source is not None:
        manifest["source_input_digest"] = current_source

    _ = manifest_path.write_text(f"{json.dumps(manifest, indent=2)}\n")
    print(
        f"updated _manifest.json: content_digest={current_content}, "
        f"source_input_digest={current_source}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "anatomy_root",
        type=Path,
        help="Path to the docs/anatomy directory",
    )
    _ = parser.add_argument(
        "--mode",
        choices=("check", "update"),
        default="check",
        help="'check' (default, read-only) or 'update' (writes manifest)",
    )
    _ = parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Path to repository root (default: CWD)",
    )
    args = parser.parse_args()

    if args.mode == "update":
        return _cmd_update(args)
    return _cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
