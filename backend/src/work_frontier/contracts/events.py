"""Versioned inter-process event envelopes with strict payload contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class EventType(StrEnum):
    """Published event types shared by web, worker, and scheduler."""

    SYNC_REQUESTED = "sync.requested"
    SOURCE_REVISION_OBSERVED = "source.revision_observed"
    DECISION_CYCLE_COMMITTED = "decision.cycle_committed"
    PROJECTION_WRITE_REQUESTED = "projection.write_requested"


class EventPayload(BaseModel):
    """Strict JSON-like payload for one event."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    resource_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class EventEnvelope(BaseModel):
    """Canonical message exchanged across runnable processes."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"]
    event_id: str = Field(min_length=1)
    event_type: EventType
    tenant_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    payload: EventPayload
