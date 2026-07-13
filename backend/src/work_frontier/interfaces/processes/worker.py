"""Independent worker process entrypoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from work_frontier.interfaces.api.services import ControlPlaneService


def run_worker_once(service: ControlPlaneService) -> str:
    """Execute one durable worker iteration through the application port."""
    return service.worker_once()
