"""Content-addressed immutable evidence objects over an S3-compatible port."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, cast

_HTTP_NOT_FOUND = 404


class ReadableBody(Protocol):
    """Streaming object body returned by an S3-compatible client."""

    def read(self) -> bytes:
        """Read the complete object body."""
        ...


class S3Client(Protocol):
    """Minimal boto3-compatible operations used by the evidence store."""

    def head_object(self, **kwargs: object) -> Mapping[str, object]:
        """Return metadata for one object or raise a provider error."""
        ...

    def put_object(self, **kwargs: object) -> Mapping[str, object]:
        """Store one object with immutable integrity metadata."""
        ...

    def get_object(self, **kwargs: object) -> Mapping[str, object]:
        """Return one object body and metadata."""
        ...


@dataclass(frozen=True, slots=True)
class EvidenceObjectRef:
    """Immutable content-addressed object identity."""

    bucket: str
    key: str
    sha256: str
    size: int


class ContentAddressedEvidenceStore:
    """Store evidence by hash and reject any attempted content overwrite."""

    _client: S3Client
    _bucket: str

    def __init__(self, client: S3Client, bucket: str) -> None:
        """Bind the store to one S3-compatible client and bucket."""
        if not bucket.strip():
            msg = "bucket is required"
            raise ValueError(msg)
        self._client = client
        self._bucket = bucket

    def put(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        content: bytes,
    ) -> EvidenceObjectRef:
        """Put bytes once under a tenant/workspace/hash namespace."""
        digest = hashlib.sha256(content).hexdigest()
        key = f"{tenant_id}/{workspace_id}/sha256/{digest}"
        try:
            head = self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            if not _is_not_found(exc):
                raise
        else:
            metadata_raw = head.get("Metadata", {})
            metadata = cast("Mapping[str, object]", metadata_raw)
            if metadata.get("sha256") != digest:
                msg = "content-addressed object metadata mismatch"
                raise ValueError(msg)
            return EvidenceObjectRef(self._bucket, key, digest, len(content))

        _ = self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content,
            Metadata={"sha256": digest},
            ContentType="application/octet-stream",
        )
        return EvidenceObjectRef(self._bucket, key, digest, len(content))

    def get(self, reference: EvidenceObjectRef) -> bytes:
        """Retrieve bytes and verify their content hash before returning."""
        response = self._client.get_object(
            Bucket=reference.bucket,
            Key=reference.key,
        )
        body = cast("ReadableBody", response["Body"])
        content = body.read()
        if hashlib.sha256(content).hexdigest() != reference.sha256:
            msg = "evidence object hash mismatch"
            raise ValueError(msg)
        return content


def _is_not_found(exc: Exception) -> bool:
    """Return whether an S3-compatible provider exception represents HTTP 404."""
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return False
    response_map = cast("Mapping[str, object]", response)
    metadata = response_map.get("ResponseMetadata")
    return (
        isinstance(metadata, Mapping)
        and cast("Mapping[str, object]", metadata).get("HTTPStatusCode")
        == _HTTP_NOT_FOUND
    )
