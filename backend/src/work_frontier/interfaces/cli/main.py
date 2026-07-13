"""Typer CLI with endpoint parity and no direct database access."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated, cast

import typer

if TYPE_CHECKING:
    from work_frontier.interfaces.cli.client import ApiResponse, ControlPlaneApi

_HTTP_ERROR_MIN = 400
_HTTP_CONFLICT = 409
_CONFLICT_EXIT = 4
_ERROR_EXIT = 2
_JsonOption = Annotated[bool, typer.Option("--json")]
_YesOption = Annotated[bool, typer.Option("--yes")]


def build_cli(api: ControlPlaneApi) -> typer.Typer:
    """Build a CLI bound only to the public control-plane API."""
    app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
    proposal_app = typer.Typer(no_args_is_help=True)
    connection_app = typer.Typer(no_args_is_help=True)
    writer_app = typer.Typer(no_args_is_help=True)
    app.add_typer(proposal_app, name="proposal")
    app.add_typer(connection_app, name="connection")
    app.add_typer(writer_app, name="writer")

    @app.command("frontier")
    def frontier(json_output: _JsonOption = False) -> None:
        _render(api.request("GET", "/frontier"), json_output=json_output)

    @app.command("item")
    def item(item_id: str, json_output: _JsonOption = False) -> None:
        _render(api.request("GET", f"/frontier/{item_id}"), json_output=json_output)

    @app.command("claim")
    def claim(
        item_id: str,
        decision_id: str,
        yes: _YesOption = False,
        json_output: _JsonOption = False,
    ) -> None:
        _confirm_mutation(yes, "Claim this WorkItem?")
        _render(
            api.request(
                "POST",
                f"/leases/{item_id}/claim",
                payload={"decision_id": decision_id},
            ),
            json_output=json_output,
        )

    @proposal_app.command("approve")
    def approve_proposal(
        proposal_id: str,
        yes: _YesOption = False,
        json_output: _JsonOption = False,
    ) -> None:
        _confirm_mutation(yes, "Approve and recompute this proposal?")
        _render(
            api.request("POST", f"/proposals/{proposal_id}/approve"),
            json_output=json_output,
        )

    @connection_app.command("list")
    def list_connections(json_output: _JsonOption = False) -> None:
        _render(api.request("GET", "/connections"), json_output=json_output)

    @app.command("sync")
    def sync(
        yes: _YesOption = False,
        json_output: _JsonOption = False,
    ) -> None:
        _confirm_mutation(yes, "Schedule a workspace sync?")
        _render(api.request("POST", "/sync"), json_output=json_output)

    @app.command("audit")
    def audit(json_output: _JsonOption = False) -> None:
        _render(api.request("GET", "/audit"), json_output=json_output)

    @writer_app.command("state")
    def writer_state(json_output: _JsonOption = False) -> None:
        _render(api.request("GET", "/writer-state"), json_output=json_output)

    @app.command("certify")
    def certify(json_output: _JsonOption = False) -> None:
        _render(api.request("GET", "/certification"), json_output=json_output)

    _ = (
        frontier,
        item,
        claim,
        approve_proposal,
        list_connections,
        sync,
        audit,
        writer_state,
        certify,
    )
    return app


def _confirm_mutation(yes: bool, prompt: str) -> None:
    if yes:
        return
    _ = typer.confirm(prompt, abort=True)


def _render(response: ApiResponse, *, json_output: bool) -> None:
    if response.status_code >= _HTTP_ERROR_MIN:
        error = response.payload.get("error")
        message = "control-plane request failed"
        if isinstance(error, dict):
            typed_error = cast("dict[str, object]", error)
            rendered = typed_error.get("message")
            if isinstance(rendered, str):
                message = rendered
        typer.echo(message)
        exit_code = (
            _CONFLICT_EXIT if response.status_code == _HTTP_CONFLICT else _ERROR_EXIT
        )
        raise typer.Exit(code=exit_code)
    if json_output:
        typer.echo(json.dumps(response.payload, sort_keys=True, indent=2))
        return
    typer.echo(_humanize(response.payload))


def _humanize(payload: dict[str, object]) -> str:
    items = payload.get("items")
    if isinstance(items, list):
        lines: list[str] = []
        typed_items = cast("list[object]", items)
        for item in typed_items:
            if isinstance(item, dict):
                typed_item = cast("dict[str, object]", item)
                item_id = typed_item.get("item_id", "unknown")
                ready = typed_item.get("ready", False)
                lines.append(f"{item_id}: {'ready' if ready else 'blocked'}")
        return "\n".join(lines) if lines else "No items"
    return json.dumps(payload, sort_keys=True)
