"""Public identity, session, and credential-encryption contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from work_frontier.domain.authorization import ResourceScope


class IdentityError(ValueError):
    """Signal invalid identity/session/credential input without leaking secrets."""


@dataclass(frozen=True, slots=True)
class ExternalIdentity:
    """OIDC/OAuth identity returned by a trusted identity provider port."""

    provider: str
    subject: str
    email: str | None
    display_name: str | None

    def __post_init__(self) -> None:
        """Reject blank provider and subject identity."""
        if not self.provider.strip() or not self.subject.strip():
            msg = "external identity provider and subject are required"
            raise IdentityError(msg)


class IdentityProvider(Protocol):
    """OIDC/OAuth provider port; tokens remain provider-specific."""

    def exchange_code(self, authorization_code: str, redirect_uri: str) -> str:
        """Exchange a short-lived authorization code for an opaque provider token."""
        ...

    def resolve_identity(self, provider_token: str) -> ExternalIdentity:
        """Resolve one trusted external identity."""
        ...


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """Opaque revocable session bound to one active workspace scope."""

    session_id: str
    actor_id: str
    token_hash: str
    scope: ResourceScope
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    role_revision: int

    def __post_init__(self) -> None:
        """Validate session identity, time bounds, and role revision."""
        if not self.session_id.strip() or not self.actor_id.strip():
            msg = "session_id and actor_id are required"
            raise IdentityError(msg)
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            msg = "session timestamps must be timezone-aware"
            raise IdentityError(msg)
        if self.expires_at <= self.issued_at:
            msg = "session expiry must follow issuance"
            raise IdentityError(msg)
        if self.role_revision < 1:
            msg = "session role revision must be positive"
            raise IdentityError(msg)


class SessionStore(Protocol):
    """Persistence port for opaque sessions."""

    def put(self, session: SessionRecord) -> None:
        """Persist one session."""
        ...

    def get(self, session_id: str) -> SessionRecord | None:
        """Return one session by opaque identity."""
        ...

    def revoke(self, session_id: str, revoked_at: datetime) -> None:
        """Revoke one session immediately."""
        ...


@dataclass(frozen=True, slots=True)
class LocalIdentityRecord:
    """Self-hosted local identity with verifier and encrypted MFA reference."""

    actor_id: str
    username: str
    password_salt_b64: str
    password_verifier_b64: str
    mfa_credential_id: str | None
    role_revision: int
    enabled: bool = True

    def __post_init__(self) -> None:
        """Reject blank identity/verifier fields and invalid role revisions."""
        required = (
            self.actor_id,
            self.username,
            self.password_salt_b64,
            self.password_verifier_b64,
        )
        if any(not value.strip() for value in required) or self.role_revision < 1:
            msg = "local identity, password verifier, and role revision are required"
            raise IdentityError(msg)


@dataclass(frozen=True, slots=True)
class EncryptedCredential:
    """Workspace-scoped envelope-encrypted connection credential."""

    credential_id: str
    key_id: str
    nonce_b64: str
    ciphertext_b64: str
    associated_data_b64: str
    fingerprint: str

    def masked(self) -> str:
        """Return a stable non-secret display fingerprint."""
        return f"credential:{self.fingerprint[:8]}…"


class CredentialCipher(Protocol):
    """Envelope-encryption port implemented by hosted or self-hosted key systems."""

    def encrypt(
        self,
        *,
        credential_id: str,
        workspace_id: str,
        plaintext: bytes,
    ) -> EncryptedCredential:
        """Encrypt one workspace-scoped credential."""
        ...

    def decrypt(
        self,
        *,
        workspace_id: str,
        credential: EncryptedCredential,
    ) -> bytes:
        """Decrypt one credential only within its associated workspace scope."""
        ...

    def rotate(
        self,
        *,
        workspace_id: str,
        credential: EncryptedCredential,
    ) -> EncryptedCredential:
        """Re-encrypt one credential under the active key."""
        ...
