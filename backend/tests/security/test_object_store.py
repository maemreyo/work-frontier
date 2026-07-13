from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO

import pytest

from work_frontier.platform.object_store import ContentAddressedEvidenceStore


class MissingError(Exception):
    response: dict[str, object]

    def __init__(self) -> None:
        super().__init__("missing")
        self.response = {"ResponseMetadata": {"HTTPStatusCode": 404}}


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, dict[str, str]]] = {}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        key = (Bucket, Key)
        if key not in self.objects:
            raise MissingError
        content, metadata = self.objects[key]
        return {"Metadata": metadata, "ContentLength": len(content)}

    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        Metadata: Mapping[str, str],
        ContentType: str,
    ) -> dict[str, object]:
        key = (Bucket, Key)
        if key in self.objects:
            raise AssertionError("content-addressed key must not be overwritten")
        assert ContentType == "application/octet-stream"
        self.objects[key] = (Body, dict(Metadata))
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        content, _ = self.objects[(Bucket, Key)]
        return {"Body": BytesIO(content)}

    def delete_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        del self.objects[(Bucket, Key)]
        return {}


def test_content_address_roundtrip_and_idempotent_second_put() -> None:
    client = FakeS3()
    store = ContentAddressedEvidenceStore(client, "evidence")
    first = store.put(tenant_id="tenant", workspace_id="workspace", content=b"proof")
    second = store.put(tenant_id="tenant", workspace_id="workspace", content=b"proof")
    assert first == second
    assert store.get(first) == b"proof"
    assert first.key.startswith("tenant/workspace/sha256/")


def test_existing_object_with_wrong_hash_metadata_is_rejected() -> None:
    client = FakeS3()
    store = ContentAddressedEvidenceStore(client, "evidence")
    reference = store.put(
        tenant_id="tenant",
        workspace_id="workspace",
        content=b"proof",
    )
    key = (reference.bucket, reference.key)
    content, _ = client.objects[key]
    client.objects[key] = (content, {"sha256": "0" * 64})
    with pytest.raises(ValueError, match="metadata mismatch"):
        _ = store.put(tenant_id="tenant", workspace_id="workspace", content=b"proof")
