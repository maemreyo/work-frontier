"""GitHub setup adapters that preserve machine and human identity separation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    import httpx
from pydantic import BaseModel, ConfigDict

from work_frontier.adapters.github.app import GitHubAppCredentials, build_app_jwt
from work_frontier.contracts.setup import SecretReference


class ProcessPort(Protocol):
    """Process seam required by the GitHub CLI adapter."""

    def run(
        self,
        command: tuple[str, ...],
        *,
        timeout: int = 10,
    ) -> tuple[int, str, str]:
        """Run a bounded command and return exit code, stdout, and stderr."""
        ...


class GitHubIdentity(BaseModel):
    """Redacted GitHub identity discovered during setup."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    login: str
    hostname: str
    credential_reference: SecretReference
    identity_kind: str


class GitHubSetupError(RuntimeError):
    """Signal a typed GitHub setup failure."""


class GhCliSetupAdapter:
    """Reference an existing GitHub CLI session without copying its token."""

    def __init__(self, process: ProcessPort, *, hostname: str = "github.com") -> None:
        """Bind a process seam and GitHub hostname."""
        self._process: ProcessPort = process
        self._hostname: str = hostname

    def inspect_identity(self) -> GitHubIdentity:
        """Return the active GitHub CLI user as a credential reference."""
        command = (
            "gh",
            "auth",
            "status",
            "--hostname",
            self._hostname,
            "--json",
            "hosts",
        )
        exit_code, stdout, _stderr = self._process.run(command)
        if exit_code != 0:
            message = "GitHub CLI is not authenticated"
            raise GitHubSetupError(message)
        try:
            raw = json.loads(stdout)
            accounts = raw["hosts"][self._hostname]
            active = next(account for account in accounts if account.get("active"))
            login = str(active["login"])
        except (KeyError, StopIteration, TypeError, json.JSONDecodeError) as exc:
            message = "GitHub CLI identity response is invalid"
            raise GitHubSetupError(message) from exc
        return GitHubIdentity(
            login=login,
            hostname=self._hostname,
            credential_reference=SecretReference(
                uri=f"gh-cli://{self._hostname}/{login}"
            ),
            identity_kind="human_development",
        )

    def list_repositories(self, *, limit: int = 100) -> tuple[str, ...]:
        """List repositories visible to the active CLI identity."""
        command = (
            "gh",
            "repo",
            "list",
            "--limit",
            str(limit),
            "--json",
            "nameWithOwner",
        )
        exit_code, stdout, _stderr = self._process.run(command)
        if exit_code != 0:
            message = "GitHub repositories could not be listed"
            raise GitHubSetupError(message)
        raw = json.loads(stdout)
        return tuple(sorted(str(item["nameWithOwner"]) for item in raw))


class SecretResolver(Protocol):
    """Resolve an opaque secret reference inside an adapter boundary."""

    def resolve(self, reference: SecretReference) -> str:
        """Resolve a reference only inside the adapter boundary."""
        ...


class GitHubAppSetupVerifier:
    """Verify GitHub App token exchange and repository installation access."""

    def __init__(
        self,
        *,
        client: httpx.Client,
        secrets: SecretResolver,
        clock: Callable[[], datetime],
    ) -> None:
        """Bind the HTTP client, secret resolver, and timezone-aware clock."""
        self._client: httpx.Client = client
        self._secrets: SecretResolver = secrets
        self._clock: Callable[[], datetime] = clock

    def verify(
        self,
        parameters: dict[str, str | int | bool | None],
    ) -> dict[str, str | int | bool | None]:
        """Exchange one short-lived token and return only redacted evidence."""
        repository = _required_string(parameters, "github_repository")
        app_id = str(_required_value(parameters, "github_app_id"))
        installation_id = str(_required_value(parameters, "github_installation_id"))
        reference = SecretReference(
            uri=_required_string(parameters, "github_app_credential_reference")
        )
        private_key = self._secrets.resolve(reference).encode()
        credentials = GitHubAppCredentials(
            app_id=app_id,
            installation_id=installation_id,
            private_key_pem=private_key,
        )
        app_jwt = build_app_jwt(credentials, issued_at=self._clock())
        token_response = self._client.post(
            f"/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        _ = token_response.raise_for_status()
        payload = cast("dict[str, object]", token_response.json())
        token = str(payload.get("token", ""))
        if not token:
            message = "GitHub returned a blank installation token"
            raise GitHubSetupError(message)
        permissions_raw = payload.get("permissions", {})
        permissions = (
            cast("dict[str, str]", permissions_raw)
            if isinstance(permissions_raw, dict)
            else {}
        )
        required = {
            "issues": "write",
            "metadata": "read",
            "pull_requests": "read",
        }
        if any(permissions.get(name) != level for name, level in required.items()):
            message = "GitHub App installation lacks required repository permissions"
            raise GitHubSetupError(message)
        repository_response = self._client.get(
            f"/repos/{repository}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        _ = repository_response.raise_for_status()
        return {
            "repository": repository,
            "installation_id": installation_id,
            "token_expires_at": str(payload.get("expires_at", "")),
            "permissions_verified": True,
        }


def _required_value(
    parameters: dict[str, str | int | bool | None],
    name: str,
) -> str | int | bool:
    value = parameters.get(name)
    if value in (None, ""):
        message = f"missing GitHub setup field: {name}"
        raise GitHubSetupError(message)
    return value


def _required_string(
    parameters: dict[str, str | int | bool | None],
    name: str,
) -> str:
    value = _required_value(parameters, name)
    if not isinstance(value, str):
        message = f"GitHub setup field must be text: {name}"
        raise GitHubSetupError(message)
    return value
