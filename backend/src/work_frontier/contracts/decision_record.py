"""Canonical DecisionRecord transport contract."""

from datetime import datetime
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field

DECISION_RECORD_SCHEMA_NAME: Final = "DecisionRecordContract"


class DecisionRecordContract(BaseModel):
    """Immutable cross-language DecisionRecord reproducibility envelope."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        title=DECISION_RECORD_SCHEMA_NAME,
    )

    decision_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    program_id: str | None
    item_id: str = Field(min_length=1)
    computed_at: datetime
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    normalized_snapshot_id: str = Field(min_length=1)
    normalized_snapshot_hash: str = Field(min_length=64, max_length=64)
    source_revision_set: dict[str, str] = Field(min_length=1)
    graph_revision: str = Field(min_length=1)
    policy_bundle_id: str = Field(min_length=1)
    policy_bundle_hash: str = Field(min_length=64, max_length=64)
    ranking_pipeline_hash: str = Field(min_length=64, max_length=64)
    engine_version: str = Field(min_length=1)
    normalization_profile_version: str = Field(min_length=1)
    ready: bool
    ranking_position: int = Field(ge=1)
