"""Fast in-memory connection adapter for isolated unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from work_frontier.application.ports.connections import (
    AdapterError,
    AdapterErrorKind,
    CertificationLevel,
    CertificationMetadata,
    ConnectionCapabilities,
    ProjectionMutation,
    ProjectionWriteGuard,
    SourceItem,
    SourcePage,
)


@dataclass(slots=True)
class InMemoryAdapter:
    """Experimental deterministic adapter backed by immutable source values."""

    items: tuple[SourceItem, ...]
    revision: str
    published: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Canonicalize source order and reject duplicate item IDs."""
        self.items = tuple(sorted(self.items, key=lambda item: item.item_id))
        if len({item.item_id for item in self.items}) != len(self.items):
            msg = "in-memory adapter item IDs must be unique"
            raise ValueError(msg)
        if not self.revision.strip():
            msg = "in-memory adapter revision is required"
            raise ValueError(msg)

    @property
    def capabilities(self) -> ConnectionCapabilities:
        """Return in-memory capabilities."""
        return ConnectionCapabilities(
            read_items=True,
            read_revisions=True,
            receive_webhooks=False,
            write_projections=True,
        )

    @property
    def certification(self) -> CertificationMetadata:
        """Return experimental certification metadata."""
        return CertificationMetadata(
            level=CertificationLevel.EXPERIMENTAL,
            certified_at=None,
            certifier=None,
            test_coverage_percent=0,
            last_audit=None,
        )

    def list_items(self, *, cursor: str | None, page_size: int) -> SourcePage:
        """Return one stable page using integer cursors."""
        if page_size < 1:
            msg = "page_size must be positive"
            raise ValueError(msg)
        try:
            start = 0 if cursor is None else int(cursor)
        except ValueError as exc:
            msg = "cursor must be an integer offset"
            raise AdapterError(AdapterErrorKind.MALFORMED_RESPONSE, msg) from exc
        page_items = self.items[start : start + page_size]
        next_offset = start + len(page_items)
        next_cursor = str(next_offset) if next_offset < len(self.items) else None
        return SourcePage(page_items, next_cursor, self.revision)

    def get_item(self, item_id: str) -> SourceItem:
        """Return one source item or a typed not-found fault."""
        for item in self.items:
            if item.item_id == item_id:
                return item
        msg = f"source item not found: {item_id}"
        raise AdapterError(AdapterErrorKind.NOT_FOUND, msg)

    def current_revision(self) -> str:
        """Return the source revision."""
        return self.revision

    def publish_projection(
        self,
        mutation: ProjectionMutation,
        guard: ProjectionWriteGuard,
    ) -> str:
        """Record a guarded idempotent projection mutation."""
        if guard.expected_source_revision != self.revision:
            msg = "projection source revision is stale"
            raise AdapterError(AdapterErrorKind.MALFORMED_RESPONSE, msg)
        existing = self.published.get(mutation.item_id)
        if existing is not None and existing != mutation.fingerprint:
            msg = "projection fingerprint conflicts with an existing write"
            raise AdapterError(AdapterErrorKind.MALFORMED_RESPONSE, msg)
        self.published[mutation.item_id] = mutation.fingerprint
        return f"projection:{mutation.fingerprint}"
