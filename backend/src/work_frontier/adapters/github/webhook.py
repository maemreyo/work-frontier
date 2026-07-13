"""GitHub webhook HMAC boundary and durable-receipt contract."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import TYPE_CHECKING

from work_frontier.application.ports.connections import AdapterError, AdapterErrorKind

if TYPE_CHECKING:
    from collections.abc import Callable

_HASH_LENGTH = 64


@dataclass(frozen=True, slots=True)
class WebhookReceipt:
    """Verified metadata safe to persist before acknowledging a delivery."""

    delivery_id: str
    event_name: str
    repository: str
    installation_id: str
    payload_hash: str
    raw_payload: bytes

    def __post_init__(self) -> None:
        """Reject blank delivery/scope identities and invalid payload hashes."""
        required = (
            self.delivery_id,
            self.event_name,
            self.repository,
            self.installation_id,
            self.payload_hash,
        )
        if any(not value.strip() for value in required):
            msg = "verified webhook delivery metadata is required"
            raise ValueError(msg)
        if len(self.payload_hash) != _HASH_LENGTH:
            msg = "webhook payload hash must be SHA-256"
            raise ValueError(msg)


def verify_webhook_signature(secret: bytes, payload: bytes, signature: str) -> bool:
    """Verify one `X-Hub-Signature-256` value in constant time."""
    if not secret or not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


@dataclass(frozen=True, slots=True)
class WebhookRequest:
    """Untrusted GitHub webhook boundary inputs."""

    payload: bytes
    signature: str
    delivery_id: str
    event_name: str
    repository: str
    installation_id: str


def accept_webhook(
    request: WebhookRequest,
    *,
    secret: bytes,
    persist_verified: Callable[[WebhookReceipt], None],
) -> WebhookReceipt:
    """Verify before invoking the durable inbox persistence boundary."""
    if not verify_webhook_signature(secret, request.payload, request.signature):
        msg = "invalid GitHub webhook signature"
        raise AdapterError(AdapterErrorKind.UNAUTHORIZED, msg)
    receipt = WebhookReceipt(
        delivery_id=request.delivery_id,
        event_name=request.event_name,
        repository=request.repository,
        installation_id=request.installation_id,
        payload_hash=hashlib.sha256(request.payload).hexdigest(),
        raw_payload=request.payload,
    )
    persist_verified(receipt)
    return receipt
