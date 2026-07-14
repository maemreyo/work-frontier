from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from work_frontier.adapters.github.setup import (
    GhCliSetupAdapter,
    GitHubAppSetupVerifier,
)

if TYPE_CHECKING:
    from work_frontier.contracts.setup import SecretReference


@dataclass
class FakeProcess:
    output: tuple[int, str, str]
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def run(
        self, command: tuple[str, ...], *, timeout: int = 10
    ) -> tuple[int, str, str]:
        del timeout
        self.calls.append(command)
        return self.output


def test_gh_cli_identity_returns_reference_without_token() -> None:
    process = FakeProcess(
        (
            0,
            json.dumps(
                {"hosts": {"github.com": [{"login": "octocat", "active": True}]}}
            ),
            "",
        )
    )
    adapter = GhCliSetupAdapter(process)
    identity = adapter.inspect_identity()
    assert identity.login == "octocat"
    assert identity.credential_reference.uri == "gh-cli://github.com/octocat"
    assert "token" not in identity.model_dump_json().casefold()


class FakeSecretResolver:
    value: str

    def __init__(self, value: str) -> None:
        self.value = value

    def resolve(self, reference: SecretReference) -> str:
        assert reference.uri.startswith(("keyring://", "env://"))
        return self.value


def test_github_app_verifier_exchanges_token_and_returns_redacted_evidence() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    requests: list[httpx.Request] = []
    credential_value = "installation-" + "credential"

    def transport(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/access_tokens"):
            return httpx.Response(
                201,
                json={
                    "token": credential_value,
                    "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                    "permissions": {
                        "issues": "write",
                        "metadata": "read",
                        "pull_requests": "read",
                    },
                },
            )
        return httpx.Response(200, json={"full_name": "acme/managed"})

    verifier = GitHubAppSetupVerifier(
        client=httpx.Client(
            transport=httpx.MockTransport(transport),
            base_url="https://api.github.com",
        ),
        secrets=FakeSecretResolver(private_pem),
        clock=lambda: datetime.now(UTC),
    )
    evidence = verifier.verify(
        {
            "github_repository": "acme/managed",
            "github_app_id": 12345,
            "github_installation_id": 67890,
            "github_app_credential_reference": (
                "keyring://work-frontier/installations/production/github-app-key"
            ),
            "github_webhook_reference": (
                "keyring://work-frontier/installations/production/webhook"
            ),
        }
    )

    assert evidence["repository"] == "acme/managed"
    assert evidence["installation_id"] == "67890"
    assert credential_value not in json.dumps(evidence)
    assert requests[0].headers["authorization"].startswith("Bearer ")
    assert requests[1].headers["authorization"] == f"Bearer {credential_value}"
