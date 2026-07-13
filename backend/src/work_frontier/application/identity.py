"""Identity ports, opaque sessions, local credentials, MFA, and credential service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

from work_frontier.application.ports.identity import IdentityError, SessionStore

if TYPE_CHECKING:
    from datetime import datetime

    from work_frontier.domain.authorization import ResourceScope

_MIN_SESSION_TOKEN_LENGTH = 32
_MIN_PASSWORD_LENGTH = 12
_MIN_SALT_LENGTH = 16
_TOTP_DIGITS = 6


@dataclass(frozen=True, slots=True)
class SessionPrincipal:
    """Validated request principal resolved from an opaque session token."""

    actor_id: str
    scope: ResourceScope
    role_revision: int


def hash_session_token(token: str) -> str:
    """Hash an opaque session token for storage and constant-time validation."""
    if len(token) < _MIN_SESSION_TOKEN_LENGTH:
        msg = "opaque session token must contain at least thirty-two characters"
        raise IdentityError(msg)
    return hashlib.sha256(token.encode()).hexdigest()


def validate_session(
    store: SessionStore,
    *,
    session_id: str,
    token: str,
    now: datetime,
    current_role_revision: int,
) -> SessionPrincipal:
    """Validate revocation, expiry, token hash, and next-request role freshness."""
    session = store.get(session_id)
    if session is None:
        msg = "session is invalid"
        raise IdentityError(msg)
    if now.tzinfo is None or now.utcoffset() is None:
        msg = "session validation time must be timezone-aware"
        raise IdentityError(msg)
    if session.revoked_at is not None or now >= session.expires_at:
        msg = "session is invalid"
        raise IdentityError(msg)
    candidate_hash = hash_session_token(token)
    if not hmac.compare_digest(candidate_hash, session.token_hash):
        msg = "session is invalid"
        raise IdentityError(msg)
    if current_role_revision != session.role_revision:
        msg = "session role grants changed; re-authentication is required"
        raise IdentityError(msg)
    return SessionPrincipal(session.actor_id, session.scope, session.role_revision)


@dataclass(frozen=True, slots=True)
class PasswordRecord:
    """Scrypt password verifier for the self-hosted local identity path."""

    salt_b64: str
    verifier_b64: str
    n: int = 2**14
    r: int = 8
    p: int = 1


def derive_password_record(password: str, salt: bytes) -> PasswordRecord:
    """Derive a local password verifier without storing plaintext."""
    if len(password) < _MIN_PASSWORD_LENGTH:
        msg = "local passwords must contain at least twelve characters"
        raise IdentityError(msg)
    if len(salt) < _MIN_SALT_LENGTH:
        msg = "password salt must contain at least sixteen bytes"
        raise IdentityError(msg)
    verifier = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return PasswordRecord(
        salt_b64=base64.b64encode(salt).decode(),
        verifier_b64=base64.b64encode(verifier).decode(),
    )


def verify_password(password: str, record: PasswordRecord) -> bool:
    """Verify a local password using constant-time comparison."""
    salt = base64.b64decode(record.salt_b64, validate=True)
    expected = base64.b64decode(record.verifier_b64, validate=True)
    candidate = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=record.n,
        r=record.r,
        p=record.p,
        dklen=len(expected),
    )
    return hmac.compare_digest(candidate, expected)


def verify_totp(
    secret_b32: str,
    code: str,
    *,
    unix_time: int,
    period_seconds: int = 30,
    allowed_drift_steps: int = 1,
) -> bool:
    """Verify a six-digit RFC-6238-style TOTP code with bounded drift."""
    if len(code) != _TOTP_DIGITS or not code.isdecimal():
        return False
    if period_seconds < 1 or allowed_drift_steps < 0:
        msg = "TOTP period must be positive and drift must not be negative"
        raise IdentityError(msg)
    try:
        secret = base64.b32decode(secret_b32.upper(), casefold=True)
    except ValueError:
        return False
    counter = unix_time // period_seconds
    for offset in range(-allowed_drift_steps, allowed_drift_steps + 1):
        payload = struct.pack(">Q", counter + offset)
        digest = hmac.new(secret, payload, hashlib.sha1).digest()
        index = digest[-1] & 0x0F
        binary = int.from_bytes(digest[index : index + 4]) & 0x7FFFFFFF
        expected = f"{binary % 1_000_000:06d}"
        if hmac.compare_digest(expected, code):
            return True
    return False
