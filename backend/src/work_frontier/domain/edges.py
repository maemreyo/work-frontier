"""Immutable typed graph edges and endpoint validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from work_frontier.domain.errors import DomainErrorCode, DomainInvariantError
from work_frontier.domain.identifiers import (
    EdgeId,
    ResourceKind,
    ResourceRef,
    TenantId,
    WorkspaceId,
)

if TYPE_CHECKING:
    from datetime import datetime


class EdgeType(StrEnum):
    """Canonical graph relationship types."""

    CONTAINS = "contains"
    BLOCKS = "blocks"
    REQUIRES_GATE = "requires_gate"
    RELATED_TO = "related_to"


class BlockSubtype(StrEnum):
    """Readiness semantics for blocks edges."""

    HARD = "hard"
    SOFT = "soft"


class EdgeOrigin(StrEnum):
    """Permitted edge origins."""

    TRACKER = "tracker"
    USER = "user"


@dataclass(frozen=True, slots=True)
class Edge:
    """Immutable typed edge with workspace provenance."""

    edge_id: EdgeId
    tenant_id: TenantId
    workspace_id: WorkspaceId
    edge_type: EdgeType
    source: ResourceRef
    target: ResourceRef
    created_at: datetime
    origin: EdgeOrigin
    provenance: str
    subtype: BlockSubtype | None = None

    def __post_init__(self) -> None:
        """Validate timestamp, endpoint, subtype, and provenance invariants."""
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_TIMESTAMP,
                "created_at",
                "timezone-aware datetime required",
            )
        if not self.provenance.strip():
            raise DomainInvariantError(
                DomainErrorCode.INVALID_EDGE,
                "provenance",
                "edge provenance is required",
            )
        if self.source == self.target:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_EDGE,
                "target",
                "self edges are not allowed",
            )

        if self.edge_type is EdgeType.CONTAINS:
            valid = (
                self.source.kind is ResourceKind.PROGRAM
                and self.target.kind in {ResourceKind.PROGRAM, ResourceKind.WORK_ITEM}
            ) or (
                self.source.kind is ResourceKind.WORK_ITEM
                and self.target.kind is ResourceKind.WORK_ITEM
            )
        elif self.edge_type is EdgeType.BLOCKS:
            valid = (
                self.source.kind is ResourceKind.WORK_ITEM
                and self.target.kind is ResourceKind.WORK_ITEM
            )
        elif self.edge_type is EdgeType.REQUIRES_GATE:
            valid = (
                self.source.kind is ResourceKind.GATE
                and self.target.kind is ResourceKind.WORK_ITEM
            )
        else:
            valid = self.source.kind in {
                ResourceKind.PROGRAM,
                ResourceKind.WORK_ITEM,
            } and self.target.kind in {
                ResourceKind.PROGRAM,
                ResourceKind.WORK_ITEM,
            }
        if not valid:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_EDGE,
                "endpoints",
                f"invalid {self.edge_type} endpoint combination",
            )

        if self.edge_type is EdgeType.BLOCKS and self.subtype is None:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_EDGE,
                "subtype",
                "blocks edges require hard or soft subtype",
            )
        if self.edge_type is not EdgeType.BLOCKS and self.subtype is not None:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_EDGE,
                "subtype",
                "only blocks edges accept a subtype",
            )
