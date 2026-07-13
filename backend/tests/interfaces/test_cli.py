from __future__ import annotations

from typing import override

from typer.testing import CliRunner

from work_frontier.interfaces.cli.client import ApiResponse, ControlPlaneApi
from work_frontier.interfaces.cli.main import build_cli


class FakeApi(ControlPlaneApi):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    @override
    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> ApiResponse:
        del payload
        self.calls.append((method, path))
        if path.endswith("/approve"):
            return ApiResponse(
                409,
                {"error": {"code": "stale_decision", "message": "refresh required"}},
            )
        if path == "/frontier":
            return ApiResponse(200, {"items": [{"item_id": "item-1", "ready": True}]})
        return ApiResponse(200, {"ok": True})


def test_frontier_json_and_command_endpoint_parity() -> None:
    api = FakeApi()
    runner = CliRunner()
    result = runner.invoke(build_cli(api), ["frontier", "--json"])
    assert result.exit_code == 0
    assert '"item_id": "item-1"' in result.stdout
    assert api.calls == [("GET", "/frontier")]


def test_mutation_requires_confirmation_and_stale_error_is_nonzero() -> None:
    api = FakeApi()
    runner = CliRunner()
    declined = runner.invoke(build_cli(api), ["proposal", "approve", "proposal-1"])
    assert declined.exit_code != 0
    assert api.calls == []

    stale = runner.invoke(
        build_cli(api),
        ["proposal", "approve", "proposal-1", "--yes"],
    )
    assert stale.exit_code == 4
    assert "refresh required" in stale.stdout


def test_secret_bearing_configuration_is_never_rendered() -> None:
    api = FakeApi()
    runner = CliRunner()
    result = runner.invoke(build_cli(api), ["connection", "list", "--json"])
    assert result.exit_code == 0
    assert "token" not in result.stdout.lower()
