"""Explicit allowlisted loader for trusted built-in connection adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from work_frontier.adapters.connections.file import FileAdapter

if TYPE_CHECKING:
    from pathlib import Path

    from work_frontier.application.ports.connections import ConnectionAdapter


class AdapterLoadError(ValueError):
    """Signal an unsupported or malformed adapter configuration."""


def load_builtin_adapter(kind: str, *, fixture_path: Path | None) -> ConnectionAdapter:
    """Load only trusted built-in adapters; arbitrary module loading is forbidden."""
    if kind == "file" and fixture_path is not None:
        return FileAdapter(fixture_path)
    msg = f"unsupported built-in adapter kind: {kind}"
    raise AdapterLoadError(msg)
