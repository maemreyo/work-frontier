"""Content-addressed immutable evidence objects over an S3-compatible port."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, cast


class ReadableBody(Protocol):
    """Streaming object body returned by an S3-compatible client."""

    def read(self) -> bytes: ...


class S3Client(Protocol):
    """Minimal boto3-compatible operations used by the evidence store."""

    def head_object(self, *, Bucket: str, Key: str) -> Mapping[str, object]: ...

    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        Metadata: Mapping[str, str],
        ContentType: str,
    ) -> Mapping[str, object]: ...

    def get_object(self, *, Bucket: str, Key: str) -> Mapping[str, object]: ...


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
        if not bucket.strip():
            raise ValueError("bucket is required")
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
            response = getattr(exc, "response", None)
            if not isinstance(response, Mapping):
                raise
            response_map = cast("Mapping[str, object]", response)
            metadata = response_map.get("ResponseMetadata")
            if (
                not isinstance(metadata, Mapping)
                or cast("Mapping[str, object]", metadata).get("HTTPStatusCode") != 404
            ):
                raise
        else:
            metadata_raw = head.get("Metadata", {})
            metadata = cast("Mapping[str, object]", metadata_raw)
            if metadata.get("sha256") != digest:
                raise ValueError("content-addressed object metadata mismatch")
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
            raise ValueError("evidence object hash mismatch")
        return content
