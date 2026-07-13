"""Typed connection port shared by deterministic and production adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Final, Protocol, runtime_checkable

_MAX_COVERAGE_PERCENT: Final = 100


class CertificationLevel(IntEnum):
    """Connection certification level from experimental to production-ready."""

    EXPERIMENTAL = 0
    DETERMINISTIC = 1
    RESILIENT = 2
    CERTIFIED = 3


class AdapterErrorKind(StrEnum):
    """Typed adapter failures exposed to application orchestration."""

    MALFORMED_RESPONSE = "malformed_response"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UNAUTHORIZED = "unauthorized"
    UNAVAILABLE = "unavailable"


class AdapterError(RuntimeError):
    """Connection failure with stable kind and retry metadata."""

    kind: AdapterErrorKind
    retry_after_seconds: int | None

    def __init__(
        self,
        kind: AdapterErrorKind,
        detail: str,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        """Build one typed adapter failure."""
        super().__init__(detail)
        self.kind = kind
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class ConnectionCapabilities:
    """Capabilities declared by one adapter implementation."""

    read_items: bool
    read_revisions: bool
    receive_webhooks: bool
    write_projections: bool


@dataclass(frozen=True, slots=True)
class CertificationMetadata:
    """Auditable certification metadata for one adapter."""

    level: CertificationLevel
    certified_at: str | None
    certifier: str | None
    test_coverage_percent: int
    last_audit: str | None

    def __post_init__(self) -> None:
        """Validate bounded coverage and level-specific metadata."""
        if not 0 <= self.test_coverage_percent <= _MAX_COVERAGE_PERCENT:
            msg = "test coverage must be between zero and one hundred"
            raise ValueError(msg)
        if self.level >= CertificationLevel.DETERMINISTIC and not self.certifier:
            msg = "deterministic adapters require a certifier"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SourceItem:
    """Canonical source item returned by connection adapters."""

    source_id: str
    item_id: str
    revision: str
    title: str
    body: str
    state: str
    labels: tuple[str, ...]
    updated_at: str
    raw: tuple[tuple[str, str | int | bool | None], ...]
    policy_blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Canonicalize labels/raw fields and reject blank source identity."""
        required = (
            self.source_id,
            self.item_id,
            self.revision,
            self.title,
            self.state,
            self.updated_at,
        )
        if any(not value.strip() for value in required):
            msg = "source item identity, revision, title, state, and time are required"
            raise ValueError(msg)
        object.__setattr__(self, "labels", tuple(sorted(set(self.labels))))
        object.__setattr__(self, "raw", tuple(sorted(self.raw)))
        object.__setattr__(
            self,
            "policy_blockers",
            tuple(sorted(set(self.policy_blockers))),
        )


@dataclass(frozen=True, slots=True)
class SourcePage:
    """One deterministic page of source items."""

    items: tuple[SourceItem, ...]
    next_cursor: str | None
    source_revision: str

    def __post_init__(self) -> None:
        """Require a source revision and deterministic item ordering."""
        if not self.source_revision.strip():
            msg = "page source revision is required"
            raise ValueError(msg)
        ordered = tuple(sorted(self.items, key=lambda item: item.item_id))
        if len({item.item_id for item in ordered}) != len(ordered):
            msg = "page item IDs must be unique"
            raise ValueError(msg)
        object.__setattr__(self, "items", ordered)


@dataclass(frozen=True, slots=True)
class ProjectionWriteGuard:
    """Proof required before an adapter may perform an external projection write."""

    writer_lease_id: str
    approval_token: str
    expected_source_revision: str

    def __post_init__(self) -> None:
        """Reject absent lease, approval, or source fence."""
        if any(
            not value.strip()
            for value in (
                self.writer_lease_id,
                self.approval_token,
                self.expected_source_revision,
            )
        ):
            msg = "projection writes require lease, approval, and source revision"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ProjectionMutation:
    """Idempotent external projection mutation."""

    item_id: str
    fingerprint: str
    body: str
    labels: tuple[str, ...]

    def __post_init__(self) -> None:
        """Canonicalize labels and reject blank identity/fingerprint."""
        if not self.item_id.strip() or not self.fingerprint.strip():
            msg = "projection item identity and fingerprint are required"
            raise ValueError(msg)
        object.__setattr__(self, "labels", tuple(sorted(set(self.labels))))


@runtime_checkable
class ConnectionAdapter(Protocol):
    """Isolated source adapter contract consumed by application use cases."""

    @property
    def capabilities(self) -> ConnectionCapabilities:
        """Return declared adapter capabilities."""
        ...

    @property
    def certification(self) -> CertificationMetadata:
        """Return auditable certification metadata."""
        ...

    def list_items(self, *, cursor: str | None, page_size: int) -> SourcePage:
        """Return one deterministic page of authoritative items."""
        ...

    def get_item(self, item_id: str) -> SourceItem:
        """Return one authoritative item by provider identity."""
        ...

    def current_revision(self) -> str:
        """Return the adapter-wide source revision identity."""
        ...

    def publish_projection(
        self,
        mutation: ProjectionMutation,
        guard: ProjectionWriteGuard,
    ) -> str:
        """Publish one guarded idempotent projection and return provider revision."""
        ...
