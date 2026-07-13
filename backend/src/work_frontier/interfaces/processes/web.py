"""Independent web process construction."""

from __future__ import annotations

from typing import TYPE_CHECKING

from work_frontier.interfaces.api.app import create_app
from work_frontier.interfaces.api.services import InMemoryControlPlane

if TYPE_CHECKING:
    from fastapi import FastAPI


def build_web_process() -> FastAPI:
    """Build the default self-hosted web process without starting a server."""
    return create_app(InMemoryControlPlane.seeded())
