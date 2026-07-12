#!/usr/bin/env python3
"""Check anatomy docs for content drift using file-content hashes.

Computes a deterministic content digest over the anatomy output files
(excluding _manifest.json, which contains the digest itself) and compares
it against the value stored in _manifest.json.  This avoids the
self-reference problem of comparing ``source_commit`` to HEAD.

Exit codes:
  0 — no drift (or anatomy is absent / not yet generated)
  1 — drift detected
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def hash_file_blake2b(path: Path) -> str:
    """Return the BLAKE2b-256 hex digest of *path* contents."""
    h = hashlib.blake2b(digest_size=32)
    h.update(path.read_bytes())
    return h.hexdigest()


def compute_content_digest(anatomy_root: Path) -> str | None:
    """Return a deterministic digest of all non-manifest files under *anatomy_root*.

    Returns None when *anatomy_root* does not exist (anatomy not generated yet).
    """
    if not anatomy_root.is_dir():
        return None

    entries: list[tuple[str, str]] = []

    for entry in sorted(anatomy_root.rglob("*")):
        if not entry.is_file():
            continue
        rel = entry.relative_to(anatomy_root)
        # Exclude the manifest itself (it carries the digest) and any
        # hidden or lock files that are not meaningful content.
        if entry.name == "_manifest.json":
            continue
        if entry.name.startswith("."):
            continue
        entries.append((str(rel), hash_file_blake2b(entry)))

    h = hashlib.blake2b(digest_size=32)
    for rel_path, file_hash in entries:
        h.update(rel_path.encode("utf-8"))
        h.update(b"\x00")
        h.update(file_hash.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_anatomy_drift.py <anatomy_root>", file=sys.stderr)
        return 1

    root = Path(sys.argv[1])
    manifest_path = root / "_manifest.json"

    current_digest = compute_content_digest(root)
    if current_digest is None:
        print("anatomy not generated — skipping drift check")
        return 0

    if not manifest_path.is_file():
        print(f"ERROR: {manifest_path} not found", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_bytes())
    stored_digest = manifest.get("content_digest")

    if stored_digest is None:
        # First run: write the current digest into the manifest.
        manifest["content_digest"] = current_digest
        _ = manifest_path.write_text(f"{json.dumps(manifest, indent=2)}\n")
        print(f"initialized content_digest={current_digest}")
        return 0

    if stored_digest != current_digest:
        print(
            f"ERROR: anatomy content drift detected\n"
            f"  stored:   {stored_digest}\n"
            f"  current:  {current_digest}\n"
            f"  Regenerate anatomy docs or investigate the drift.",
            file=sys.stderr,
        )
        return 1

    print(f"anatomy content digest OK: {current_digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
