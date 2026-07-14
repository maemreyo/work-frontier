from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from work_frontier.contracts.setup import CheckState, SetupAction, SetupProfile
from work_frontier.platform.setup.local import (
    LocalSystemProbe,
    ProcessSetupActionRunner,
    UnsupportedSetupActionError,
)


@dataclass
class FakeProcess:
    outputs: dict[tuple[str, ...], tuple[int, str, str]] = field(default_factory=dict)
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def run(
        self, command: tuple[str, ...], *, timeout: int = 10
    ) -> tuple[int, str, str]:
        del timeout
        self.calls.append(command)
        return self.outputs.get(command, (127, "", "not found"))


def test_probe_reports_versions_github_and_legacy_env_without_values(
    tmp_path: Path,
) -> None:
    process = FakeProcess(
        outputs={
            ("git", "--version"): (0, "git version 2.50.0\n", ""),
            ("uv", "--version"): (0, "uv 0.10.0\n", ""),
            ("node", "--version"): (0, "v22.23.1\n", ""),
            ("pnpm", "--version"): (0, "10.20.0\n", ""),
            ("docker", "compose", "version", "--short"): (0, "2.40.0\n", ""),
            ("gh", "auth", "status", "--hostname", "github.com", "--json", "hosts"): (
                0,
                json.dumps(
                    {"hosts": {"github.com": [{"login": "octocat", "active": True}]}}
                ),
                "",
            ),
        }
    )
    probe = LocalSystemProbe(
        process=process,
        repository_root=tmp_path,
        environment={"WF_RELEASE_SIGNING_KEY_B64": "must-not-leak"},
        port_checker=lambda _port: False,
    )
    checks = probe.detect(SetupProfile.DEVELOPMENT)
    by_id = {check.check_id: check for check in checks}
    assert by_id["tool.uv"].state is CheckState.READY
    assert by_id["github.identity"].evidence == {"login": "octocat"}
    assert "must-not-leak" not in repr(checks)
    assert by_id["legacy.environment"].evidence == {
        "WF_RELEASE_SIGNING_KEY_B64_present": True
    }


def test_action_runner_uses_allowlisted_repository_commands(tmp_path: Path) -> None:
    process = FakeProcess(
        outputs={
            ("make", "infra-up"): (0, "started", ""),
            ("make", "migration-smoke"): (0, "migrated", ""),
        }
    )
    runner = ProcessSetupActionRunner(process=process, repository_root=tmp_path)
    action = SetupAction(
        action_id="services.local.start",
        title="Start",
        reason="Start services",
        risk="medium",
        reversible=True,
        depends_on=(),
        kind="docker_compose_up",
        parameters={},
    )
    assert runner.apply(action)["exit_code"] == 0
    assert process.calls == [("make", "infra-up")]
    with pytest.raises(UnsupportedSetupActionError):
        _ = runner.apply(action.model_copy(update={"kind": "shell"}))


def test_subprocess_port_turns_missing_tool_into_typed_probe_result(
    tmp_path: Path,
) -> None:
    from work_frontier.platform.setup.local import SubprocessPort

    exit_code, stdout, stderr = SubprocessPort(cwd=tmp_path).run(
        ("work-frontier-command-that-does-not-exist", "--version")
    )
    assert exit_code == 127
    assert stdout == ""
    assert "not found" in stderr
