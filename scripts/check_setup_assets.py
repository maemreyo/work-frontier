"""Check that packaged first-run setup assets match their source files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "backend/src/work_frontier/interfaces/setup_static"
SOURCES = {
    "setup.html": ROOT / "frontend/setup.html",
    "assets/setup-center-element.js": ROOT
    / "frontend/src/setup/setup-center-element.js",
    "assets/setup-api.js": ROOT / "frontend/src/setup/setup-api.js",
    "assets/setup-model.js": ROOT / "frontend/src/setup/setup-model.js",
    "assets/setup-center.css": ROOT / "frontend/src/setup/setup-center.css",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assets_are_current() -> bool:
    """Return whether every packaged asset and manifest digest is current."""
    manifest_path = DESTINATION / "manifest.json"
    if not manifest_path.is_file():
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative, source in SOURCES.items():
        target = DESTINATION / relative
        if not target.is_file() or target.read_bytes() != source.read_bytes():
            return False
        if manifest.get(relative) != _sha256(source):
            return False
    return set(manifest) == set(SOURCES)


def main() -> int:
    """Exit nonzero when packaged setup assets drift."""
    if assets_are_current():
        print("setup assets are current")
        return 0
    print("setup assets drifted; run node scripts/build_setup_assets.mjs")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
