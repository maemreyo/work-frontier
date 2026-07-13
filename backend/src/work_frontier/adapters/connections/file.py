"""Deterministic file adapter consuming a strict canonical JSON fixture."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

from work_frontier.adapters.connections.fixture import FixtureAdapter
from work_frontier.application.ports.connections import (
    AdapterError,
    AdapterErrorKind,
    CertificationMetadata,
    ConnectionCapabilities,
    ProjectionMutation,
    ProjectionWriteGuard,
    SourceItem,
    SourcePage,
)


class FileAdapter:
    """Level-1 adapter that reads a strict offline JSON document once."""

    _delegate: FixtureAdapter

    def __init__(self, path: Path) -> None:
        """Parse and retain one canonical file fixture."""
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            document = cast("dict[str, object]", raw)
            revision_raw = document["source_revision"]
            items_raw = document["items"]
            revision, items = _parse_document(revision_raw, items_raw)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            msg = f"malformed file adapter document: {path}"
            raise AdapterError(AdapterErrorKind.MALFORMED_RESPONSE, msg) from exc
        self._delegate = FixtureAdapter.from_items(items, revision)

    @property
    def capabilities(self) -> ConnectionCapabilities:
        """Return file-adapter capabilities."""
        return self._delegate.capabilities

    @property
    def certification(self) -> CertificationMetadata:
        """Return file-adapter certification metadata."""
        return self._delegate.certification

    def list_items(self, *, cursor: str | None, page_size: int) -> SourcePage:
        """Return one deterministic file page."""
        return self._delegate.list_items(cursor=cursor, page_size=page_size)

    def get_item(self, item_id: str) -> SourceItem:
        """Return one file-backed source item."""
        return self._delegate.get_item(item_id)

    def current_revision(self) -> str:
        """Return the file corpus revision."""
        return self._delegate.current_revision()

    def publish_projection(
        self,
        mutation: ProjectionMutation,
        guard: ProjectionWriteGuard,
    ) -> str:
        """Reject writes because file adapters are read-only."""
        return self._delegate.publish_projection(mutation, guard)


def _parse_document(
    revision: object,
    items: object,
) -> tuple[str, tuple[SourceItem, ...]]:
    if not isinstance(revision, str) or not isinstance(items, list):
        msg = "file adapter revision and items are malformed"
        raise TypeError(msg)
    typed_items = cast("list[object]", items)
    return revision, tuple(_parse_item(item) for item in typed_items)


def _parse_item(value: object) -> SourceItem:
    if not isinstance(value, dict):
        raise TypeError
    item = cast("dict[str, object]", value)
    labels_raw = item.get("labels", [])
    raw_raw = item.get("raw", {})
    policy_raw = item.get("policy_blockers", [])
    if (
        not isinstance(labels_raw, list)
        or not isinstance(raw_raw, dict)
        or not isinstance(policy_raw, list)
    ):
        raise TypeError
    labels = cast("list[object]", labels_raw)
    policy_blockers = cast("list[object]", policy_raw)
    if any(not isinstance(label, str) for label in labels) or any(
        not isinstance(blocker, str) for blocker in policy_blockers
    ):
        raise TypeError
    raw_pairs: list[tuple[str, str | int | bool | None]] = []
    raw_mapping = cast("dict[object, object]", raw_raw)
    for key, raw_value in raw_mapping.items():
        if not isinstance(key, str) or not isinstance(
            raw_value,
            str | int | bool | type(None),
        ):
            raise TypeError
        raw_pairs.append((key, raw_value))
    return SourceItem(
        source_id=_string(item, "source_id"),
        item_id=_string(item, "item_id"),
        revision=_string(item, "revision"),
        title=_string(item, "title"),
        body=_string(item, "body", allow_empty=True),
        state=_string(item, "state"),
        labels=tuple(cast("list[str]", labels)),
        updated_at=_string(item, "updated_at"),
        raw=tuple(raw_pairs),
        policy_blockers=tuple(cast("list[str]", policy_blockers)),
    )


def _string(value: dict[str, object], key: str, *, allow_empty: bool = False) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or (not allow_empty and not raw.strip()):
        raise TypeError
    return raw
