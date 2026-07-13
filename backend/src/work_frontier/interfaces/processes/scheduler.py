"""Independent scheduler process entrypoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from work_frontier.interfaces.api.services import ControlPlaneService


def run_scheduler_once(service: ControlPlaneService) -> str:
    """Execute one fenced scheduler iteration through the application port."""
    return service.scheduler_once()
