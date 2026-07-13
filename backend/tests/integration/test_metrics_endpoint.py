from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi.responses import PlainTextResponse

from work_frontier.interfaces.api.app import create_app
from work_frontier.interfaces.api.services import InMemoryControlPlane

if TYPE_CHECKING:
    from fastapi.routing import APIRoute


def test_metrics_is_public_and_prometheus_parseable() -> None:
    app = create_app(InMemoryControlPlane.seeded())
    route = next(
        cast("APIRoute", item)
        for item in app.routes
        if getattr(item, "path", None) == "/metrics"
    )

    assert route.response_class is PlainTextResponse
    assert route.endpoint() == (
        "# HELP work_frontier_up Process health\n"
        "# TYPE work_frontier_up gauge\n"
        'work_frontier_up{process="web"} 1\n'
    )
