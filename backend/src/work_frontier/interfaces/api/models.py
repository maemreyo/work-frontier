"""Typed FastAPI request and response models for the control plane."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Strict API model with unknown fields rejected."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", strict=True)


class ErrorBody(StrictModel):
    """Non-leaking typed error payload."""

    code: str
    message: str


class ErrorEnvelope(StrictModel):
    """Top-level error response."""

    error: ErrorBody


class FrontierItem(StrictModel):
    """Current authoritative projection for one WorkItem."""

    item_id: str
    decision_id: str
    decision_type: str
    title: str
    ready: bool
    ranking_position: int | None
    authority: str
    freshness: str
    why: tuple[str, ...]
    blocked_by: tuple[str, ...]


class FrontierPage(StrictModel):
    """Cursor-paginated current frontier response."""

    items: tuple[FrontierItem, ...]
    next_cursor: str | None


class ClaimBody(StrictModel):
    """Claim request anchored to the visible DecisionRecord."""

    decision_id: str = Field(min_length=1, max_length=128)
    divergence_reason: str | None = Field(default=None, max_length=500)


class LeaseResponse(StrictModel):
    """Claim result returned to Builder clients."""

    lease_id: str
    item_id: str
    owner: str
    decision_id: str
    version: int


class ProposalBody(StrictModel):
    """Immutable proposed change request."""

    item_id: str = Field(min_length=1, max_length=128)
    base_decision_id: str = Field(min_length=1, max_length=128)
    expected_source_revision: str = Field(min_length=1, max_length=256)
    field: str = Field(min_length=1, max_length=128)
    new_value: str = Field(min_length=1, max_length=1000)


class ProposalResponse(StrictModel):
    """Proposal identity and current disposition."""

    proposal_id: str
    state: str
    item_id: str
    base_decision_id: str


class ApprovalResponse(StrictModel):
    """Accepted proposal result with new derivation identity."""

    proposal_id: str
    state: str
    new_decision_id: str
    derived_from_decision_id: str


class WriterStateResponse(StrictModel):
    """Exclusive writer state exposed to operators."""

    mode: str
    active_writer: str
    version: int


class SyncResponse(StrictModel):
    """Durable sync scheduling response."""

    job_id: str
    state: str


class AttentionResponse(StrictModel):
    """Current AttentionItem projection."""

    attention_id: str
    item_id: str | None
    category: str
    severity: str
    state: str
    deterministic_basis: str


class HealthResponse(StrictModel):
    """Process health response."""

    status: str
    process: str
