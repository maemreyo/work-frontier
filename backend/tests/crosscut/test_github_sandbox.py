from __future__ import annotations

import http.client
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import pytest

from work_frontier.adapters.github.adapter import (
    GitHubAdapter,
    GitHubResponse,
)
from work_frontier.adapters.github.app import InstallationToken
from work_frontier.application.ports.connections import (
    ProjectionMutation,
    ProjectionWriteGuard,
)

_API_ROOT: Final = "https://api.github.com"
_API_VERSION: Final = "2022-11-28"


@dataclass(slots=True)
class StaticTokenProvider:
    """Sandbox-only provider for a pre-scoped short-lived test token."""

    value: str

    def token(self) -> InstallationToken:
        """Return the sandbox token without persisting it."""
        return InstallationToken(
            value=self.value,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            permissions=("issues:write", "metadata:read", "pull_requests:read"),
        )


@dataclass(slots=True)
class UrllibGitHubTransport:
    """Small real-network transport used only by the isolated sandbox harness."""

    token: str

    def request(
        self,
        *,
        method: str,
        path: str,
        headers: tuple[tuple[str, str], ...],
        json_body: dict[str, object] | None,
    ) -> GitHubResponse:
        """Execute one authenticated GitHub sandbox request."""
        return _https_request(
            method,
            path,
            token=self.token,
            headers=dict(headers),
            payload=json_body,
        )


def _sandbox_environment() -> tuple[str, str]:
    repository = os.environ.get("WF_GITHUB_SANDBOX_REPOSITORY")
    token = os.environ.get("WF_GITHUB_SANDBOX_TOKEN")
    if not repository or not token:
        pytest.skip("GitHub sandbox credentials are not configured")
    return repository, token


def _https_request(
    method: str,
    path: str,
    *,
    token: str,
    headers: dict[str, str] | None = None,
    payload: dict[str, object] | None = None,
) -> GitHubResponse:
    request_headers = {
        "accept": "application/vnd.github+json",
        "authorization": f"Bearer {token}",
        "content-type": "application/json",
        "x-github-api-version": _API_VERSION,
        **(headers or {}),
    }
    body = None if payload is None else json.dumps(payload).encode()
    connection = http.client.HTTPSConnection("api.github.com", timeout=30)
    try:
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        raw = response.read().decode()
        parsed: object = json.loads(raw) if raw else {}
        return GitHubResponse(
            status_code=response.status,
            headers=tuple(response.getheaders()),
            body=parsed,
        )
    finally:
        connection.close()


def _direct_request(
    token: str,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    response = _https_request(method, path, token=token, payload=payload)
    if not isinstance(response.body, dict):
        msg = "GitHub sandbox response must be an object"
        raise TypeError(msg)
    typed_body = cast("dict[object, object]", response.body)
    return {str(key): value for key, value in typed_body.items()}


def test_github_level3_sandbox_roundtrip_and_rate_budget() -> None:
    repository, token = _sandbox_environment()
    created = _direct_request(
        token,
        "POST",
        f"/repos/{repository}/issues",
        {
            "body": "Work Frontier isolated Level-3 certification probe",
            "title": "work-frontier sandbox certification probe",
        },
    )
    number = created.get("number")
    node_id = created.get("node_id")
    if (
        isinstance(number, bool)
        or not isinstance(number, int)
        or not isinstance(node_id, str)
    ):
        msg = "GitHub sandbox issue creation returned malformed identity"
        raise TypeError(msg)
    try:
        transport = UrllibGitHubTransport(token)
        adapter = GitHubAdapter(
            repository=repository,
            token_provider=StaticTokenProvider(token),
            transport=transport,
        )
        fetched = adapter.get_item(str(number))
        assert fetched.revision == node_id
        approval_token = f"sandbox-approval-{number}"
        revision = adapter.publish_projection(
            ProjectionMutation(
                item_id=str(number),
                fingerprint=f"sandbox-{number}",
                body="Managed by Work Frontier sandbox certification",
                labels=(),
            ),
            ProjectionWriteGuard(
                writer_lease_id="sandbox-writer-lease",
                approval_token=approval_token,
                expected_source_revision=node_id,
            ),
        )
        assert revision
        page = adapter.list_items(cursor=None, page_size=1)
        assert page.items
        rate = _direct_request(token, "GET", "/rate_limit")
        assert "resources" in rate
    finally:
        _ = _direct_request(
            token,
            "PATCH",
            f"/repos/{repository}/issues/{number}",
            {"state": "closed"},
        )
