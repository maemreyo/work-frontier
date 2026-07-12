#!/usr/bin/env python3
"""Check anatomy docs for content drift and source-input drift.

Two modes (select with --mode):

  check   (default) — read-only.  Fails when anatomy output is stale
          relative to source code *or* when the anatomy output files
          themselves have diverged from the last-known content digest.

   update  — computes fresh content_digest, source_input_digest,
           generator_version, and source_inputs then writes them
           into _manifest.json.  Never runs automatically; only invoked
           explicitly by the developer who regenerated docs.

Exit codes:
  0 — no drift
  1 — drift detected (check mode only)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

# Use git ls-files to get all tracked source files for the source-input
# digest, excluding anatomy docs and generated/derived artifacts.
# This replaces the previously manually-maintained glob list which missed
# modules like platform/, frontend/, workflows/, migrations, etc.
_SOURCE_EXCLUDE_PREFIXES: tuple[str, ...] = (
    "docs/anatomy/",
    ".omo/evidence/",
)

_HEX64: re.Pattern[str] = re.compile(r"^[a-f0-9]{64}$")


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


def _git_ls_files(repo_root: Path) -> list[str]:
    """Return all tracked file paths (repo-root-relative) via git ls-files."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _get_source_input_files(repo_root: Path) -> list[str]:
    """Return sorted list of tracked source file paths for the source-input digest.

    Excludes anatomy/evidence paths from the result.
    """
    files: list[str] = []
    for rel_path in sorted(_git_ls_files(repo_root)):
        if any(rel_path.startswith(prefix) for prefix in _SOURCE_EXCLUDE_PREFIXES):
            continue
        full_path = repo_root / rel_path
        if not full_path.is_file():
            continue
        files.append(rel_path)
    return files


def _compute_source_input_digest(repo_root: Path) -> str | None:
    """Hash all tracked source files via git ls-files, excluding docs/evidence.

    Using git ls-files avoids the manually-maintained glob list that
    previously missed platform/, frontend/, workflows/, migrations, etc.
    """
    h = hashlib.blake2b(digest_size=32)
    found_any = False
    for rel_path in _get_source_input_files(repo_root):
        found_any = True
        full_path = repo_root / rel_path
        h.update(rel_path.encode("utf-8"))
        h.update(b"\x00")
        h.update(_hash_file_blake2b(full_path).encode("utf-8"))
        h.update(b"\x00")
    if not found_any:
        return None
    return h.hexdigest()


def _is_valid_64hex(value: object) -> bool:
    """Return True if value is a 64-char lowercase hex string."""
    return isinstance(value, str) and bool(_HEX64.match(value))


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

    # Require BOTH digests to exist and be valid 64-char hex.
    # A missing or malformed digest is a hard failure; neither the
    # content check nor the source check can be silently skipped.
    content_valid = _is_valid_64hex(stored_content)
    source_valid = _is_valid_64hex(stored_source)

    if not content_valid or not source_valid:
        if not content_valid:
            print(
                f"ERROR: content_digest is missing or malformed "
                f"(got {stored_content!r}); run with --mode update.",
                file=sys.stderr,
            )
        if not source_valid:
            print(
                f"ERROR: source_input_digest is missing or malformed "
                f"(got {stored_source!r}); run with --mode update.",
                file=sys.stderr,
            )
        return 1

    stored_generator_version = manifest.get("generator_version")
    if not stored_generator_version:
        print(
            "ERROR: generator_version is missing from _manifest.json — "
            "anatomy docs were generated by an untracked version.\n"
            "  Regenerate with --mode update --generator-version <version>.",
            file=sys.stderr,
        )
        return 1

    failures: list[str] = []

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
        f"anatomy checks OK (generator_version={stored_generator_version}, "
        "content=computed, source=computed)"
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

    manifest["generator_version"] = args.generator_version

    manifest["content_digest"] = current_content

    current_source = _compute_source_input_digest(repo_root)
    if current_source is not None:
        manifest["source_input_digest"] = current_source

    manifest["source_inputs"] = _get_source_input_files(repo_root)

    # Remove the stale source_commit field — it was previously
    # hard-coded and never updated automatically, creating provenance
    # contradictions.  The content_digest and source_input_digest
    # already pin the exact state without a separate commit field.
    _ = manifest.pop("source_commit", None)

    _ = manifest_path.write_text(f"{json.dumps(manifest, indent=2)}\n")
    print(
        f"updated _manifest.json: generator_version={args.generator_version}, "
        f"content_digest={current_content}, "
        f"source_input_digest={current_source}, "
        f"source_inputs={len(manifest['source_inputs'])} files, "
        f"source_commit removed"
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
    _ = parser.add_argument(
        "--generator-version",
        type=str,
        default=None,
        help="Version of the anatomy generator (required for --mode update)",
    )
    args = parser.parse_args()

    if args.mode == "update":
        if args.generator_version is None:
            print(
                "ERROR: --generator-version is required when --mode=update.",
                file=sys.stderr,
            )
            return 1
        return _cmd_update(args)
    return _cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
