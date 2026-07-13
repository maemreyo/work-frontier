"""GitHub App JWT signing and memory-only installation-token refresh."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Protocol

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from work_frontier.application.ports.connections import (
    AdapterError,
    AdapterErrorKind,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class GitHubAppCredentials:
    """Non-persisted GitHub App machine-identity inputs."""

    app_id: str
    installation_id: str
    private_key_pem: bytes

    def __post_init__(self) -> None:
        """Reject blank identities and absent private-key bytes."""
        if not self.app_id.strip() or not self.installation_id.strip():
            msg = "GitHub App and installation identities are required"
            raise ValueError(msg)
        if not self.private_key_pem:
            msg = "GitHub App private key is required"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class InstallationToken:
    """Short-lived installation token retained only in process memory."""

    value: str
    expires_at: datetime
    permissions: tuple[str, ...]

    def __post_init__(self) -> None:
        """Reject blank tokens and naive expiration timestamps."""
        if not self.value.strip():
            msg = "installation token value is required"
            raise ValueError(msg)
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            msg = "installation token expiry must be timezone-aware"
            raise ValueError(msg)
        object.__setattr__(self, "permissions", tuple(sorted(set(self.permissions))))


class InstallationTokenProvider(Protocol):
    """Provider of short-lived installation tokens kept only in memory."""

    def token(self) -> InstallationToken:
        """Return one currently valid installation token."""
        ...


class InstallationTokenTransport(Protocol):
    """Minimal transport used to exchange an App JWT for an installation token."""

    def create_installation_token(
        self,
        *,
        installation_id: str,
        app_jwt: str,
    ) -> InstallationToken:
        """Return one scoped short-lived installation token."""
        ...


class GitHubAppTokenProvider:
    """Refresh installation tokens before expiry and never persist them."""

    _credentials: GitHubAppCredentials
    _transport: InstallationTokenTransport
    _clock: Callable[[], datetime]
    _cached: InstallationToken | None

    def __init__(
        self,
        credentials: GitHubAppCredentials,
        transport: InstallationTokenTransport,
        *,
        clock: Callable[[], datetime],
    ) -> None:
        """Bind explicit credentials, transport, and clock dependencies."""
        self._credentials = credentials
        self._transport = transport
        self._clock = clock
        self._cached = None

    def token(self) -> InstallationToken:
        """Return a valid installation token, refreshing five minutes early."""
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            msg = "GitHub token-provider clock must be timezone-aware"
            raise ValueError(msg)
        cached = self._cached
        if cached is not None and now + timedelta(minutes=5) < cached.expires_at:
            return cached
        app_jwt = build_app_jwt(self._credentials, issued_at=now)
        token = self._transport.create_installation_token(
            installation_id=self._credentials.installation_id,
            app_jwt=app_jwt,
        )
        required = {"issues:write", "metadata:read", "pull_requests:read"}
        if not required.issubset(set(token.permissions)):
            msg = "installation token lacks required GitHub App permissions"
            raise AdapterError(AdapterErrorKind.UNAUTHORIZED, msg)
        self._cached = token
        return token


def build_app_jwt(credentials: GitHubAppCredentials, *, issued_at: datetime) -> str:
    """Build a deterministic RS256 GitHub App JWT with a nine-minute lifetime."""
    if issued_at.tzinfo is None or issued_at.utcoffset() is None:
        msg = "GitHub App JWT issuance time must be timezone-aware"
        raise ValueError(msg)
    header = {"alg": "RS256", "typ": "JWT"}
    issued_epoch = int(issued_at.timestamp()) - 60
    payload = {
        "exp": issued_epoch + 9 * 60,
        "iat": issued_epoch,
        "iss": credentials.app_id,
    }
    signing_input = b".".join(
        (
            _base64url(_canonical_json(header)),
            _base64url(_canonical_json(payload)),
        )
    )
    key = serialization.load_pem_private_key(credentials.private_key_pem, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        msg = "GitHub App private key must be RSA"
        raise TypeError(msg)
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input.decode()}.{_base64url(signature).decode()}"


def _canonical_json(value: Mapping[str, str | int]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _base64url(value: bytes) -> bytes:
    return base64.urlsafe_b64encode(value).rstrip(b"=")
