"""Deterministic fixture adapter with explicit fault injection."""

from __future__ import annotations

from dataclasses import dataclass

from work_frontier.adapters.connections.memory import InMemoryAdapter
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
class FixtureAdapter:
    """Level-1 adapter for frozen source fixtures and deterministic CI."""

    _delegate: InMemoryAdapter
    fault: AdapterErrorKind | None = None
    retry_after_seconds: int | None = None

    @classmethod
    def from_items(
        cls,
        items: tuple[SourceItem, ...],
        revision: str,
        *,
        fault: AdapterErrorKind | None = None,
        retry_after_seconds: int | None = None,
    ) -> FixtureAdapter:
        """Build a fixture adapter from canonical source values."""
        return cls(
            InMemoryAdapter(items=items, revision=revision),
            fault=fault,
            retry_after_seconds=retry_after_seconds,
        )

    @property
    def capabilities(self) -> ConnectionCapabilities:
        """Return deterministic fixture capabilities."""
        return ConnectionCapabilities(
            read_items=True,
            read_revisions=True,
            receive_webhooks=False,
            write_projections=False,
        )

    @property
    def certification(self) -> CertificationMetadata:
        """Return level-1 certification metadata."""
        return CertificationMetadata(
            level=CertificationLevel.DETERMINISTIC,
            certified_at="2026-07-13T00:00:00+00:00",
            certifier="work-frontier-fixture-suite",
            test_coverage_percent=100,
            last_audit="2026-07-13",
        )

    def _raise_fault(self) -> None:
        if self.fault is None:
            return
        msg = f"injected fixture adapter fault: {self.fault.value}"
        raise AdapterError(
            self.fault,
            msg,
            retry_after_seconds=self.retry_after_seconds,
        )

    def list_items(self, *, cursor: str | None, page_size: int) -> SourcePage:
        """Return one fixture page or the configured typed fault."""
        self._raise_fault()
        return self._delegate.list_items(cursor=cursor, page_size=page_size)

    def get_item(self, item_id: str) -> SourceItem:
        """Return one fixture item or the configured typed fault."""
        self._raise_fault()
        return self._delegate.get_item(item_id)

    def current_revision(self) -> str:
        """Return the fixture corpus revision."""
        self._raise_fault()
        return self._delegate.current_revision()

    def publish_projection(
        self,
        mutation: ProjectionMutation,
        guard: ProjectionWriteGuard,
    ) -> str:
        """Reject writes because fixture adapters are read-only."""
        del mutation, guard
        msg = "fixture adapters do not publish external projections"
        raise AdapterError(AdapterErrorKind.UNAUTHORIZED, msg)
