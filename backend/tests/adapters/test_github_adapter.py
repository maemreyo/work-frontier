from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

from work_frontier.adapters.github.adapter import GitHubAdapter, GitHubResponse
from work_frontier.adapters.github.app import (
    GitHubAppCredentials,
    GitHubAppTokenProvider,
    InstallationToken,
    build_app_jwt,
)
from work_frontier.adapters.github.webhook import WebhookRequest, accept_webhook
from work_frontier.application.ports.connections import (
    AdapterError,
    AdapterErrorKind,
    ProjectionMutation,
    ProjectionWriteGuard,
)


class TokenTransport:
    permissions: tuple[str, ...]
    calls: int

    def __init__(self, permissions: tuple[str, ...]) -> None:
        self.permissions = permissions
        self.calls = 0

    def create_installation_token(
        self,
        *,
        installation_id: str,
        app_jwt: str,
    ) -> InstallationToken:
        self.calls += 1
        assert installation_id == "42"
        assert app_jwt.count(".") == 2
        return InstallationToken(
            value=f"token-{self.calls}",
            expires_at=datetime(2026, 7, 13, 1, tzinfo=UTC),
            permissions=self.permissions,
        )


class QueueTransport:
    responses: list[GitHubResponse | BaseException]
    requests: list[tuple[str, str]]

    def __init__(self, responses: list[GitHubResponse | BaseException]) -> None:
        self.responses = responses
        self.requests = []

    def request(
        self,
        *,
        method: str,
        path: str,
        headers: tuple[tuple[str, str], ...],
        json_body: dict[str, object] | None,
    ) -> GitHubResponse:
        del headers, json_body
        self.requests.append((method, path))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def credentials() -> GitHubAppCredentials:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    return GitHubAppCredentials("123", "42", pem)


def provider(transport: TokenTransport) -> GitHubAppTokenProvider:
    return GitHubAppTokenProvider(
        credentials(),
        transport,
        clock=lambda: datetime(2026, 7, 13, tzinfo=UTC),
    )


def issue(number: int, *, node: str = "node-1") -> dict[str, object]:
    return {
        "body": "body",
        "labels": [{"name": "ready"}],
        "node_id": node,
        "number": number,
        "state": "open",
        "title": f"Issue {number}",
        "updated_at": "2026-07-13T00:00:00+00:00",
    }


def test_app_jwt_and_installation_tokens_are_scoped_and_memory_only() -> None:
    creds = credentials()
    jwt = build_app_jwt(creds, issued_at=datetime(2026, 7, 13, tzinfo=UTC))
    header, payload, _ = jwt.split(".")

    def decode(value: str) -> dict[str, object]:
        return json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))

    assert decode(header)["alg"] == "RS256"
    assert decode(payload)["iss"] == "123"

    transport = TokenTransport(("issues:write", "metadata:read", "pull_requests:read"))
    token_provider = provider(transport)
    assert token_provider.token().value == "token-1"
    assert token_provider.token().value == "token-1"
    assert transport.calls == 1

    unauthorized = provider(TokenTransport(("metadata:read",)))
    with pytest.raises(AdapterError) as captured:
        _ = unauthorized.token()
    assert captured.value.kind is AdapterErrorKind.UNAUTHORIZED


def test_webhook_signature_is_rejected_before_durable_persistence() -> None:
    persisted: list[object] = []
    with pytest.raises(AdapterError) as captured:
        _ = accept_webhook(
            WebhookRequest(
                payload=b"{}",
                signature="sha256=invalid",
                delivery_id="delivery",
                event_name="issues.edited",
                repository="owner/repo",
                installation_id="42",
            ),
            secret=b"secret",
            persist_verified=persisted.append,
        )
    assert captured.value.kind is AdapterErrorKind.UNAUTHORIZED
    assert persisted == []


def test_github_adapter_paginates_refetches_and_fails_closed_on_rate_limit() -> None:
    token_transport = TokenTransport(
        ("issues:write", "metadata:read", "pull_requests:read")
    )
    transport = QueueTransport(
        [
            GitHubResponse(
                200,
                (("etag", "page-rev"), ("link", '<x?page=2>; rel="next"')),
                [issue(1)],
            ),
            GitHubResponse(200, (), issue(1)),
            GitHubResponse(429, (("retry-after", "12"),), {}),
        ]
    )
    adapter = GitHubAdapter(
        repository="owner/repo",
        token_provider=provider(token_transport),
        transport=transport,
    )
    page = adapter.list_items(cursor=None, page_size=10)
    assert page.next_cursor == "page:2"
    assert adapter.get_item("1").item_id == "1"
    with pytest.raises(AdapterError) as captured:
        _ = adapter.current_revision()
    assert captured.value.kind is AdapterErrorKind.RATE_LIMITED
    assert captured.value.retry_after_seconds == 12


def test_projection_write_requires_exact_refetched_revision() -> None:
    token_transport = TokenTransport(
        ("issues:write", "metadata:read", "pull_requests:read")
    )
    transport = QueueTransport([GitHubResponse(200, (), issue(1, node="current"))])
    adapter = GitHubAdapter(
        repository="owner/repo",
        token_provider=provider(token_transport),
        transport=transport,
    )
    with pytest.raises(AdapterError, match="stale"):
        _ = adapter.publish_projection(
            ProjectionMutation("1", "fingerprint", "body", ("managed",)),
            ProjectionWriteGuard("lease", "approval", "older"),
        )
