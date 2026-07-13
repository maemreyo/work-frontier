"""Immutable core domain entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TypeVar

from work_frontier.domain.authority import SourceObservation
from work_frontier.domain.errors import DomainErrorCode, DomainInvariantError
from work_frontier.domain.identifiers import (
    ActorId,
    DecisionId,
    ExternalBlockerId,
    ProgramId,
    ResourceRef,
    TenantId,
    WorkItemId,
    WorkspaceId,
    Ulid,
)


class ActorKind(StrEnum):
    """Supported claimant/author kinds."""

    HUMAN = "human"
    AGENT = "agent"
    AUTOMATION = "automation"
    SYSTEM = "system"


class WorkType(StrEnum):
    """Canonical WorkItem types."""

    FEATURE = "feature"
    BUGFIX = "bugfix"
    MAINTENANCE = "maintenance"
    INVESTIGATION = "investigation"
    DECISION = "decision"


class Lifecycle(StrEnum):
    """Canonical normalized lifecycle states."""

    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ProgramStatus(StrEnum):
    """Program rollup states."""

    ACTIVE = "active"
    STALLED = "stalled"
    COMPLETE = "complete"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class Actor:
    """Workspace-scoped immutable actor identity."""

    actor_id: ActorId
    tenant_id: TenantId
    workspace_id: WorkspaceId
    kind: ActorKind
    display_name: str

    def __post_init__(self) -> None:
        _require_text(self.display_name, "display_name", max_length=200)


@dataclass(frozen=True, slots=True)
class ExternalBlocker:
    """Blocker originating outside a Program's scope."""

    blocker_id: ExternalBlockerId
    description: str
    source: str
    affected_members: tuple[WorkItemId, ...]
    created_at: datetime
    resolved: bool = False

    def __post_init__(self) -> None:
        _require_text(self.description, "description")
        _require_text(self.source, "source")
        _require_aware(self.created_at, "created_at")
        object.__setattr__(
            self,
            "affected_members",
            _canonical_ids(self.affected_members, "affected_members"),
        )


@dataclass(frozen=True, slots=True)
class WorkItem:
    """Base unit of work; derived fields are decision-bound caches only."""

    item_id: WorkItemId
    tenant_id: TenantId
    workspace_id: WorkspaceId
    title: str
    work_type: WorkType
    lifecycle: Lifecycle
    created_at: datetime
    updated_at: datetime
    created_by: ActorId
    description: str | None = None
    tracker_ids: tuple[tuple[str, str], ...] = ()
    program_ids: tuple[ProgramId, ...] = ()
    labels: tuple[str, ...] = ()
    completion_policy_id: str | None = None
    derived_from_decision_id: DecisionId | None = None
    readiness: bool | None = None
    ranking_position: int | None = None
    fan_out: int | None = None
    primary_owner: ActorId | None = None
    participants: tuple[ActorId, ...] = ()
    source_authorities: tuple[SourceObservation, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.title, "title", max_length=500)
        _require_aware(self.created_at, "created_at")
        _require_aware(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_TIMESTAMP,
                "updated_at",
                "must not precede created_at",
            )
        if self.ranking_position is not None and self.ranking_position < 1:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_ENTITY,
                "ranking_position",
                "must be at least one",
            )
        if self.fan_out is not None and self.fan_out < 0:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_ENTITY,
                "fan_out",
                "must be non-negative",
            )
        if (
            any(
                value is not None
                for value in (self.readiness, self.ranking_position, self.fan_out)
            )
            and self.derived_from_decision_id is None
        ):
            raise DomainInvariantError(
                DomainErrorCode.DERIVED_WITHOUT_DECISION,
                "derived_from_decision_id",
                "required whenever a derived cache is exposed",
            )

        tracker_ids = tuple(sorted(self.tracker_ids))
        tracker_names = tuple(name for name, _ in tracker_ids)
        if any(not name.strip() or not value.strip() for name, value in tracker_ids):
            raise DomainInvariantError(
                DomainErrorCode.INVALID_ENTITY,
                "tracker_ids",
                "tracker names and values are required",
            )
        if len(tracker_names) != len(set(tracker_names)):
            raise DomainInvariantError(
                DomainErrorCode.INVALID_ENTITY,
                "tracker_ids",
                "tracker names must be unique",
            )
        object.__setattr__(self, "tracker_ids", tracker_ids)
        object.__setattr__(
            self, "program_ids", _canonical_ids(self.program_ids, "program_ids")
        )
        object.__setattr__(self, "labels", _canonical_text(self.labels, "labels"))
        object.__setattr__(
            self, "participants", _canonical_ids(self.participants, "participants")
        )
        if self.primary_owner is not None and self.primary_owner in self.participants:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_ENTITY,
                "participants",
                "primary owner must not be duplicated as a participant",
            )


@dataclass(frozen=True, slots=True)
class Program:
    """Immutable Program with typed multi-parent containment references."""

    program_id: ProgramId
    tenant_id: TenantId
    workspace_id: WorkspaceId
    name: str
    status: ProgramStatus
    member_ids: tuple[WorkItemId, ...]
    contained_by: tuple[ProgramId, ...]
    contains: tuple[ResourceRef, ...]
    created_at: datetime
    updated_at: datetime
    created_by: ActorId
    description: str | None = None
    external_blockers: tuple[ExternalBlocker, ...] = ()
    labels: tuple[str, ...] = ()
    primary_owner: ActorId | None = None
    participants: tuple[ActorId, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.name, "name", max_length=200)
        _require_aware(self.created_at, "created_at")
        _require_aware(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_TIMESTAMP,
                "updated_at",
                "must not precede created_at",
            )
        members = _canonical_ids(self.member_ids, "member_ids")
        parents = _canonical_ids(self.contained_by, "contained_by")
        children = tuple(
            sorted(self.contains, key=lambda item: (item.kind, str(item.resource_id)))
        )
        if len(children) != len(set(children)):
            raise DomainInvariantError(
                DomainErrorCode.INVALID_ENTITY,
                "contains",
                "contains entries must be unique",
            )
        if self.program_id in parents or any(
            child.resource_id == self.program_id for child in children
        ):
            raise DomainInvariantError(
                DomainErrorCode.INVALID_ENTITY,
                "contains",
                "a Program cannot contain or be contained by itself",
            )
        object.__setattr__(self, "member_ids", members)
        object.__setattr__(self, "contained_by", parents)
        object.__setattr__(self, "contains", children)
        object.__setattr__(self, "labels", _canonical_text(self.labels, "labels"))
        object.__setattr__(
            self, "participants", _canonical_ids(self.participants, "participants")
        )
        if not members:
            object.__setattr__(self, "status", ProgramStatus.ARCHIVED)


TUlid = TypeVar("TUlid", bound=Ulid)


def _canonical_ids(values: tuple[TUlid, ...], field: str) -> tuple[TUlid, ...]:
    ordered = tuple(sorted(values, key=str))
    if len(ordered) != len(set(ordered)):
        raise DomainInvariantError(
            DomainErrorCode.INVALID_ENTITY,
            field,
            "duplicate values are not allowed",
        )
    return ordered


def _canonical_text(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    if any(not value.strip() for value in values):
        raise DomainInvariantError(
            DomainErrorCode.INVALID_ENTITY,
            field,
            "blank values are not allowed",
        )
    ordered = tuple(sorted(values))
    if len(ordered) != len(set(ordered)):
        raise DomainInvariantError(
            DomainErrorCode.INVALID_ENTITY,
            field,
            "duplicate values are not allowed",
        )
    return ordered


def _require_text(value: str, field: str, *, max_length: int | None = None) -> None:
    if not value.strip():
        raise DomainInvariantError(
            DomainErrorCode.INVALID_ENTITY,
            field,
            "must not be blank",
        )
    if max_length is not None and len(value) > max_length:
        raise DomainInvariantError(
            DomainErrorCode.INVALID_ENTITY,
            field,
            f"must be at most {max_length} characters",
        )


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainInvariantError(
            DomainErrorCode.INVALID_TIMESTAMP,
            field,
            "timezone-aware datetime required",
        )
