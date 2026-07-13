"""AES-GCM envelope-encryption adapter with explicit key references."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from work_frontier.application.ports.identity import (
    EncryptedCredential,
    IdentityError,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_NONCE_SIZE: Final = 12
_VALID_KEY_SIZES: Final = frozenset({16, 24, 32})


@dataclass(frozen=True, slots=True)
class EnvelopeKey:
    """One versioned AES key reference supplied by a key-management boundary."""

    key_id: str
    key_bytes: bytes

    def __post_init__(self) -> None:
        """Validate key identity and AES key length."""
        if not self.key_id.strip() or len(self.key_bytes) not in _VALID_KEY_SIZES:
            msg = "envelope key requires an identity and valid AES key length"
            raise ValueError(msg)


class AesGcmCredentialCipher:
    """Credential cipher with active-key rotation and workspace associated data."""

    _keys: dict[str, bytes]
    _active_key_id: str
    _nonce_source: Callable[[int], bytes]

    def __init__(
        self,
        keys: tuple[EnvelopeKey, ...],
        *,
        active_key_id: str,
        nonce_source: Callable[[int], bytes],
    ) -> None:
        """Build a cipher from an explicit key ring and nonce source."""
        self._keys = {item.key_id: item.key_bytes for item in keys}
        if len(self._keys) != len(keys) or active_key_id not in self._keys:
            msg = "key ring must contain unique keys and the active key"
            raise ValueError(msg)
        self._active_key_id = active_key_id
        self._nonce_source = nonce_source

    def encrypt(
        self,
        *,
        credential_id: str,
        workspace_id: str,
        plaintext: bytes,
    ) -> EncryptedCredential:
        """Encrypt one credential with workspace/credential associated data."""
        if not credential_id.strip() or not workspace_id.strip() or not plaintext:
            msg = "credential identity, workspace, and plaintext are required"
            raise IdentityError(msg)
        nonce = self._nonce_source(_NONCE_SIZE)
        if len(nonce) != _NONCE_SIZE:
            msg = "nonce source must return exactly twelve bytes"
            raise IdentityError(msg)
        associated_data = _associated_data(workspace_id, credential_id)
        ciphertext = AESGCM(self._keys[self._active_key_id]).encrypt(
            nonce,
            plaintext,
            associated_data,
        )
        return EncryptedCredential(
            credential_id=credential_id,
            key_id=self._active_key_id,
            nonce_b64=base64.b64encode(nonce).decode(),
            ciphertext_b64=base64.b64encode(ciphertext).decode(),
            associated_data_b64=base64.b64encode(associated_data).decode(),
            fingerprint=hashlib.sha256(plaintext).hexdigest(),
        )

    def decrypt(
        self,
        *,
        workspace_id: str,
        credential: EncryptedCredential,
    ) -> bytes:
        """Decrypt one credential and fail closed on scope/key/tag mismatch."""
        key = self._keys.get(credential.key_id)
        if key is None:
            msg = "credential encryption key is unavailable"
            raise IdentityError(msg)
        associated_data = _associated_data(workspace_id, credential.credential_id)
        encoded_associated_data = base64.b64decode(
            credential.associated_data_b64,
            validate=True,
        )
        if encoded_associated_data != associated_data:
            msg = "credential workspace scope does not match associated data"
            raise IdentityError(msg)
        try:
            return AESGCM(key).decrypt(
                base64.b64decode(credential.nonce_b64, validate=True),
                base64.b64decode(credential.ciphertext_b64, validate=True),
                associated_data,
            )
        except (InvalidTag, ValueError) as exc:
            msg = "credential authentication failed"
            raise IdentityError(msg) from exc

    def rotate(
        self,
        *,
        workspace_id: str,
        credential: EncryptedCredential,
    ) -> EncryptedCredential:
        """Decrypt and re-encrypt one credential under the active key."""
        plaintext = self.decrypt(workspace_id=workspace_id, credential=credential)
        return self.encrypt(
            credential_id=credential.credential_id,
            workspace_id=workspace_id,
            plaintext=plaintext,
        )


def _associated_data(workspace_id: str, credential_id: str) -> bytes:
    if not workspace_id.strip() or not credential_id.strip():
        msg = "credential associated-data identities are required"
        raise IdentityError(msg)
    return f"work-frontier:{workspace_id}:{credential_id}".encode()
