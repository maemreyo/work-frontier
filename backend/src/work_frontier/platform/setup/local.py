"""Read-only local probes and allowlisted process setup actions."""

from __future__ import annotations

import json
import socket
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

from work_frontier.contracts.setup import (
    CheckState,
    DetectionCheck,
    SetupAction,
    SetupProfile,
)


class ProcessPort(Protocol):
    """Small process boundary used by probes and actions."""

    def run(
        self,
        command: tuple[str, ...],
        *,
        timeout: int = 10,
    ) -> tuple[int, str, str]:
        """Run a bounded command without shell expansion."""
        ...


class SubprocessPort:
    """Safe subprocess implementation without shell expansion."""

    _cwd: Path | None

    def __init__(self, *, cwd: Path | None = None) -> None:
        """Bind an optional repository working directory."""
        self._cwd = cwd

    def run(
        self,
        command: tuple[str, ...],
        *,
        timeout: int = 10,
    ) -> tuple[int, str, str]:
        """Run an explicit argv tuple and capture text output."""
        try:
            completed = subprocess.run(  # noqa: S603 - explicit argv, no shell
                list(command),
                cwd=self._cwd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            return 127, "", f"{command[0]} not found"
        except subprocess.TimeoutExpired:
            return 124, "", f"{command[0]} timed out after {timeout} seconds"
        return completed.returncode, completed.stdout, completed.stderr


def _port_open(port: int) -> bool:
    with socket.socket() as connection:
        connection.settimeout(0.15)
        return connection.connect_ex(("127.0.0.1", port)) == 0


@dataclass(slots=True)
class LocalSystemProbe:
    """Detect supported local tools and services without mutations."""

    process: ProcessPort
    repository_root: Path
    environment: Mapping[str, str]
    port_checker: Callable[[int], bool] = _port_open

    def detect(self, profile: SetupProfile) -> tuple[DetectionCheck, ...]:
        """Return read-only setup checks."""
        checks = [
            self._tool("git", ("git", "--version")),
            self._tool("uv", ("uv", "--version")),
            self._tool("node", ("node", "--version"), required=False),
            self._tool("pnpm", ("pnpm", "--version"), required=False),
            self._tool(
                "docker_compose",
                ("docker", "compose", "version", "--short"),
                required=profile is SetupProfile.DEVELOPMENT,
            ),
            self._github_identity(),
            self._service("database", 54329),
            self._service("object_store", 9002),
            self._legacy_environment(),
        ]
        if profile is SetupProfile.PRODUCTION:
            checks.extend(
                (
                    _needs_input(
                        "release.signing",
                        "Release signing is not configured",
                        "Standard certification cannot start",
                        "Open Release Certification in Setup Center",
                    ),
                    _needs_input(
                        "cutover.approval",
                        "Cutover approval is not configured",
                        "The production writer cannot activate",
                        "Add an approved change reference",
                    ),
                )
            )
        return tuple(checks)

    def _tool(
        self,
        name: str,
        command: tuple[str, ...],
        *,
        required: bool = True,
    ) -> DetectionCheck:
        exit_code, stdout, _stderr = self.process.run(command)
        if exit_code == 0:
            return DetectionCheck(
                check_id=f"tool.{name}",
                state=CheckState.READY,
                summary=f"{name} is available",
                impact="The supported setup workflow can use this tool",
                evidence={"version": stdout.strip()[:128]},
            )
        state = CheckState.BLOCKED if required else CheckState.REPAIRABLE
        return DetectionCheck(
            check_id=f"tool.{name}",
            state=state,
            summary=f"{name} is unavailable",
            impact="A supported setup action cannot run",
            remediation=(f"Install the pinned {name} version",),
            evidence={"exit_code": exit_code},
        )

    def _github_identity(self) -> DetectionCheck:
        exit_code, stdout, _stderr = self.process.run(
            ("gh", "auth", "status", "--hostname", "github.com", "--json", "hosts")
        )
        if exit_code != 0:
            return _needs_input(
                "github.identity",
                "GitHub CLI is not authenticated",
                "A development sandbox cannot be selected",
                "Run GitHub CLI authentication from the guided action",
            )
        try:
            raw = json.loads(stdout)
            accounts = raw["hosts"]["github.com"]
            active = next(account for account in accounts if account.get("active"))
            login = str(active["login"])
        except (KeyError, StopIteration, TypeError, json.JSONDecodeError):
            return DetectionCheck(
                check_id="github.identity",
                state=CheckState.BLOCKED,
                summary="GitHub CLI returned an unreadable identity",
                impact="Repository permissions cannot be verified",
                remediation=("Re-authenticate GitHub CLI",),
                evidence={"exit_code": exit_code},
            )
        return DetectionCheck(
            check_id="github.identity",
            state=CheckState.READY,
            summary=f"GitHub CLI authenticated as {login}",
            impact="Sandbox repository access can be verified",
            evidence={"login": login},
        )

    def _service(self, name: str, port: int) -> DetectionCheck:
        ready = self.port_checker(port)
        return DetectionCheck(
            check_id=f"services.{name}",
            state=CheckState.READY if ready else CheckState.REPAIRABLE,
            summary=(
                f"{name.replace('_', ' ').title()} is "
                f"{'reachable' if ready else 'stopped'}"
            ),
            impact="Runtime data services must be reachable",
            remediation=() if ready else ("Start supported Compose services",),
            evidence={"port": port, "reachable": ready},
        )

    def _legacy_environment(self) -> DetectionCheck:
        names = (
            "WF_GITHUB_SANDBOX_REPOSITORY",
            "WF_GITHUB_SANDBOX_TOKEN",
            "WF_RELEASE_SIGNING_KEY_B64",
            "WF_CUTOVER_APPROVAL_ID",
        )
        evidence: dict[str, str | int | bool | None] = {
            f"{name}_present": name in self.environment
            for name in names
            if name in self.environment
        }
        return DetectionCheck(
            check_id="legacy.environment",
            state=CheckState.REPAIRABLE if evidence else CheckState.READY,
            summary=(
                "Legacy setup environment variables were detected"
                if evidence
                else "No legacy setup environment variables were detected"
            ),
            impact="Legacy shell state can make setup difficult to reproduce",
            remediation=(
                "Import values into secret references, then clear shell exports",
            )
            if evidence
            else (),
            evidence=evidence,
        )


class UnsupportedSetupActionError(ValueError):
    """Signal a setup action outside the allowlist."""


class SetupActionExecutionError(RuntimeError):
    """Signal a failed allowlisted command."""


@dataclass(slots=True)
class ProcessSetupActionRunner:
    """Map reviewed setup actions to repository-owned commands."""

    process: ProcessPort
    repository_root: Path

    _COMMANDS: ClassVar[dict[str, tuple[str, ...]]] = {
        "docker_compose_up": ("make", "infra-up"),
        "database_migrate": ("make", "migration-smoke"),
        "storage_verify": ("make", "storage-smoke"),
        "run_fast_checks": ("make", "check"),
        "verify_external_services": ("make", "test-ops"),
        "certify_standard": ("make", "certify-standard"),
    }

    def apply(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        """Apply one reviewed action."""
        if action.kind in {"write_config", "github_reference"}:
            return {"operation": action.kind, "exit_code": 0}
        command = self._COMMANDS.get(action.kind)
        if command is None:
            raise UnsupportedSetupActionError(action.kind)
        exit_code, _stdout, stderr = self.process.run(command, timeout=1800)
        if exit_code != 0:
            message = f"{action.kind} failed: {stderr.strip()[:256]}"
            raise SetupActionExecutionError(message)
        return {"operation": action.kind, "exit_code": exit_code}

    def verify(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        """Return verification metadata for a successfully applied action."""
        return {"verified": True, "operation": action.kind}

    def compensate(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        """Compensate only actions with an explicit safe inverse."""
        if action.kind == "docker_compose_up":
            exit_code, _stdout, stderr = self.process.run(
                ("make", "infra-down"), timeout=300
            )
            if exit_code != 0:
                raise SetupActionExecutionError(stderr.strip()[:256])
        return {"compensated": True, "operation": action.kind}


def _needs_input(
    check_id: str,
    summary: str,
    impact: str,
    remediation: str,
) -> DetectionCheck:
    return DetectionCheck(
        check_id=check_id,
        state=CheckState.NEEDS_INPUT,
        summary=summary,
        impact=impact,
        remediation=(remediation,),
    )
