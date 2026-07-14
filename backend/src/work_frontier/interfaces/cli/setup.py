"""One-command interactive setup and headless configuration CLI."""

from __future__ import annotations

import json
import secrets
import socket
import sys
import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from collections.abc import Callable

    from work_frontier.application.setup.service import SetupService
    from work_frontier.interfaces.api.setup_app import SecretWriter
from work_frontier.contracts.setup import CapabilityReport, SetupPlan, SetupProfile
from work_frontier.interfaces.api.setup_app import create_setup_app

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
setup_app = typer.Typer(invoke_without_command=True, no_args_is_help=False)
config_app = typer.Typer(no_args_is_help=True)
app.add_typer(setup_app, name="setup")
app.add_typer(config_app, name="config")


@dataclass(slots=True)
class _SetupComposition:
    setup_service_factory: Callable[[], SetupService] | None = None
    secret_store_factory: Callable[[], SecretWriter | None] | None = None


_composition = _SetupComposition()


def configure(
    *,
    setup_service_factory: Callable[[], SetupService],
    secret_store_factory: Callable[[], SecretWriter | None],
) -> None:
    """Inject composition-owned setup dependencies for this CLI interface."""
    _composition.setup_service_factory = setup_service_factory
    _composition.secret_store_factory = secret_store_factory


@setup_app.callback(invoke_without_command=True)
def setup_callback(
    context: typer.Context,
    no_open: Annotated[bool, typer.Option("--no-open")] = False,
    detach: Annotated[bool, typer.Option("--detach")] = False,
) -> None:
    """Start the loopback Setup Center when no setup subcommand is supplied."""
    if context.invoked_subcommand is not None:
        return
    service = build_default_setup_service()
    recovery_url = launch_setup_server(service, no_open=no_open, detach=detach)
    typer.echo("Work Frontier Setup Center is ready")
    typer.echo(f"Recovery URL: {recovery_url}")


@setup_app.command("status")
def setup_status(
    json_output: Annotated[bool, typer.Option("--json")] = False,
    profile: Annotated[
        SetupProfile, typer.Option("--profile")
    ] = SetupProfile.DEVELOPMENT,
) -> None:
    """Show independent setup capability readiness."""
    envelope = build_default_setup_service().status(profile)
    if json_output:
        typer.echo(envelope.model_dump_json(indent=2))
        return
    _render_status_table(envelope.capabilities)


@setup_app.command("repair")
def setup_repair() -> None:
    """Open the persistent setup experience for repair."""
    recovery_url = launch_setup_server(
        build_default_setup_service(),
        no_open=False,
        detach=False,
    )
    typer.echo(f"Recovery URL: {recovery_url}")


@setup_app.command("plan")
def setup_plan(
    repository: Annotated[str, typer.Option("--repository")],
    profile: Annotated[
        SetupProfile, typer.Option("--profile")
    ] = SetupProfile.DEVELOPMENT,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Create a secret-free setup plan."""
    service = build_default_setup_service()
    detection = service.detect(profile)
    plan = service.plan(
        profile=profile,
        desired={"github_repository": repository},
        expected_snapshot_id=detection.snapshot_id,
    )
    typer.echo(plan.model_dump_json(indent=2) if json_output else _render_plan(plan))


@setup_app.command("apply")
def setup_apply(
    plan: Annotated[
        Path, typer.Option("--plan", exists=True, dir_okay=False, readable=True)
    ],
    non_interactive: Annotated[bool, typer.Option("--non-interactive")] = False,
) -> None:
    """Revalidate and apply a serialized reviewed plan."""
    if not non_interactive:
        message = "headless plan apply requires --non-interactive"
        raise typer.BadParameter(message)
    reviewed = SetupPlan.model_validate_json(plan.read_text(encoding="utf-8"))
    envelope = build_default_setup_service().apply_reviewed_plan(reviewed)
    typer.echo(envelope.model_dump_json(indent=2))


@config_app.command("show")
def config_show(
    redacted: Annotated[bool, typer.Option("--redacted")] = True,
) -> None:
    """Show normal configuration; only redacted output is supported."""
    if not redacted:
        message = "configuration output is always redacted"
        raise typer.BadParameter(message)
    service = build_default_setup_service()
    document, revision = service.config_store.read()
    typer.echo(
        json.dumps({"revision": revision, "config": document}, indent=2, sort_keys=True)
    )


def build_default_setup_service() -> SetupService:
    """Build the default local setup composition."""
    if _composition.setup_service_factory is None:
        message = "setup CLI has not been composed"
        raise RuntimeError(message)
    return _composition.setup_service_factory()


def launch_setup_server(
    service: SetupService,
    *,
    no_open: bool,
    detach: bool,
) -> str:
    """Start setup on an ephemeral loopback port and optionally open a browser."""
    bootstrap_token = secrets.token_urlsafe(32)
    if _composition.secret_store_factory is None:
        message = "setup CLI has not been composed"
        raise RuntimeError(message)
    secret_store = _composition.secret_store_factory()
    static_directory = Path(__file__).resolve().parents[1] / "setup_static"
    setup_api = create_setup_app(
        service,
        bootstrap_token=bootstrap_token,
        secret_store=secret_store,
        static_directory=static_directory,
    )
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = int(listener.getsockname()[1])
    server = uvicorn.Server(
        uvicorn.Config(setup_api, log_level="warning", lifespan="off")
    )
    thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [listener]},
        daemon=detach,
        name="work-frontier-setup",
    )
    thread.start()
    recovery_url = f"http://127.0.0.1:{port}/setup.html"
    if not no_open:
        _ = webbrowser.open(f"{recovery_url}#{bootstrap_token}")
    if not detach:
        try:
            thread.join()
        except KeyboardInterrupt:
            server.should_exit = True
            thread.join(timeout=5)
    return recovery_url


def _render_status_table(capabilities: tuple[CapabilityReport, ...]) -> None:
    """Render capability readiness as a compact human-readable table."""
    labels = {
        "local_runtime": "Local runtime",
        "github_integration": "GitHub integration",
        "release_certification": "Release certification",
        "production_cutover": "Production cutover",
    }
    table = Table(title="Setup readiness", show_lines=False)
    table.add_column("Capability")
    table.add_column("State")
    table.add_column("Reason")
    for report in capabilities:
        capability = report.capability.value
        table.add_row(labels[capability], report.state.value, report.reason)
    Console(file=sys.stdout, force_terminal=False, color_system=None).print(table)


def _render_plan(plan: SetupPlan) -> str:
    lines = [f"Plan {plan.plan_id[:12]} ({plan.profile.value})"]
    for action in plan.actions:
        reversible = (
            "reversible" if action.reversible else "manual recovery if interrupted"
        )
        lines.append(f"- {action.title} [{action.risk}; {reversible}]")
    return "\n".join(lines)


def main() -> None:
    """Run the Work Frontier setup CLI."""
    app()


_ = setup_callback, setup_status, setup_repair, setup_plan, setup_apply, config_show
