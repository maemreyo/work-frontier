"""Composition root and stable bootstrap contract."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final

import httpx

from work_frontier.adapters.github.setup import GitHubAppSetupVerifier
from work_frontier.application.setup.service import SetupService

if TYPE_CHECKING:
    from work_frontier.contracts.setup import SetupAction
from work_frontier.platform.configuration.settings import SetupRuntimeSettings
from work_frontier.platform.configuration.setup_storage import (
    SetupPaths,
    SqliteSetupJournal,
    TomlConfigurationStore,
)
from work_frontier.platform.secrets.stores import CompositeSecretResolver
from work_frontier.platform.setup.local import (
    LocalSystemProbe,
    ProcessSetupActionRunner,
    SubprocessPort,
)

HELLO_CONTRACT: Final = "work-frontier"
_MIN_SOAK_SECONDS: Final = 259_200


def hello_contract() -> str:
    """Return the stable bootstrap contract identifier."""
    return HELLO_CONTRACT


@dataclass(slots=True)
class ComposedSetupActionRunner:
    """Dispatch setup actions across local process and GitHub adapters."""

    local: ProcessSetupActionRunner
    github_app: GitHubAppSetupVerifier

    def apply(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        """Apply one reviewed action through its owning adapter."""
        if action.kind == "github_app_verify":
            return self.github_app.verify(dict(action.parameters))
        if action.kind in {"prepare_release", "prepare_cutover"}:
            return _validate_preparation(action)
        return self.local.apply(action)

    def verify(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        """Return stable verification metadata after successful apply."""
        return self.local.verify(action)

    def compensate(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        """Delegate safe local compensation."""
        return self.local.compensate(action)


def build_setup_service(
    *,
    paths: SetupPaths | None = None,
    repository_root: Path | None = None,
) -> SetupService:
    """Wire concrete local setup adapters into the Application service."""
    settings = SetupRuntimeSettings()
    resolved_paths = paths or (
        SetupPaths.from_root(settings.state_root)
        if settings.state_root is not None
        else SetupPaths.for_user()
    )
    root = repository_root or Path.cwd()
    process = SubprocessPort(cwd=root)
    local_runner = ProcessSetupActionRunner(process=process, repository_root=root)
    secrets = CompositeSecretResolver(os.environ)
    github_verifier = GitHubAppSetupVerifier(
        client=httpx.Client(
            base_url=str(settings.github_api_url).rstrip("/"),
            timeout=httpx.Timeout(settings.github_timeout_seconds),
            follow_redirects=False,
        ),
        secrets=secrets,
        clock=lambda: datetime.now(UTC),
    )
    return SetupService(
        config_store=TomlConfigurationStore(resolved_paths),
        journal=SqliteSetupJournal(resolved_paths.journal_file),
        probe=LocalSystemProbe(
            process=process,
            repository_root=root,
            environment=os.environ,
        ),
        runner=ComposedSetupActionRunner(
            local=local_runner,
            github_app=github_verifier,
        ),
    )


def _validate_preparation(
    action: SetupAction,
) -> dict[str, str | int | bool | None]:
    if action.kind == "prepare_release":
        soak = action.parameters.get("soak_duration_seconds")
        if not isinstance(soak, int) or soak < _MIN_SOAK_SECONDS:
            message = (
                f"release soak duration must be at least {_MIN_SOAK_SECONDS} seconds"
            )
            raise ValueError(message)
    for name, value in action.parameters.items():
        if value in (None, ""):
            message = f"missing preparation input: {name}"
            raise ValueError(message)
    return {
        "operation": action.kind,
        "inputs_validated": True,
        "authoritative_gate_bypassed": False,
    }
