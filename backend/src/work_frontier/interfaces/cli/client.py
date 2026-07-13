"""HTTP-only CLI client contract and implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

import httpx


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """Transport-neutral control-plane response."""

    status_code: int
    payload: dict[str, object]


class ControlPlaneApi(Protocol):
    """Minimal API client consumed by Typer commands."""

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> ApiResponse:
        """Send one control-plane request."""
        ...


@dataclass(slots=True)
class HttpControlPlaneApi:
    """HTTPX implementation that never logs or renders bearer credentials."""

    base_url: str
    token: str
    tenant_id: str
    workspace_id: str
    timeout_seconds: float = 10.0

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> ApiResponse:
        """Send a scoped JSON request and return decoded public data."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Tenant-ID": self.tenant_id,
            "X-Workspace-ID": self.workspace_id,
        }
        response = httpx.request(
            method,
            f"{self.base_url.rstrip('/')}{path}",
            headers=headers,
            json=payload,
            timeout=self.timeout_seconds,
        )
        decoded = response.json()
        if not isinstance(decoded, dict):
            msg = "control-plane response must be a JSON object"
            raise TypeError(msg)
        return ApiResponse(response.status_code, cast("dict[str, object]", decoded))
