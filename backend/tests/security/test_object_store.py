from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, cast

import pytest

from work_frontier.platform.object_store import ContentAddressedEvidenceStore

if TYPE_CHECKING:
    from collections.abc import Mapping


class MissingError(Exception):
    response: dict[str, object]

    def __init__(self) -> None:
        super().__init__("missing")
        self.response = {"ResponseMetadata": {"HTTPStatusCode": 404}}


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, dict[str, str]]] = {}

    def head_object(self, **kwargs: object) -> dict[str, object]:
        bucket = cast("str", kwargs["Bucket"])
        object_key = cast("str", kwargs["Key"])
        key = (bucket, object_key)
        if key not in self.objects:
            raise MissingError
        content, metadata = self.objects[key]
        return {"Metadata": metadata, "ContentLength": len(content)}

    def put_object(self, **kwargs: object) -> dict[str, object]:
        bucket = cast("str", kwargs["Bucket"])
        object_key = cast("str", kwargs["Key"])
        body = cast("bytes", kwargs["Body"])
        metadata = cast("Mapping[str, str]", kwargs["Metadata"])
        content_type = cast("str", kwargs["ContentType"])
        key = (bucket, object_key)
        if key in self.objects:
            msg = "content-addressed key must not be overwritten"
            raise AssertionError(msg)
        assert content_type == "application/octet-stream"
        self.objects[key] = (body, dict(metadata))
        return {}

    def get_object(self, **kwargs: object) -> dict[str, object]:
        bucket = cast("str", kwargs["Bucket"])
        object_key = cast("str", kwargs["Key"])
        content, _ = self.objects[(bucket, object_key)]
        return {"Body": BytesIO(content)}

    def delete_object(self, **kwargs: object) -> dict[str, object]:
        bucket = cast("str", kwargs["Bucket"])
        object_key = cast("str", kwargs["Key"])
        del self.objects[(bucket, object_key)]
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
