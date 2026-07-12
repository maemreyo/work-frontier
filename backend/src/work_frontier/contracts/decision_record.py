"""Canonical DecisionRecord transport contract."""

import json
from typing import ClassVar, Final

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

DECISION_RECORD_SCHEMA_NAME: Final = "DecisionRecordContract"
DECISION_RECORD_SCHEMA_VERSION: Final = "1.0.0"


class DecisionRecordContract(BaseModel):
    """Immutable cross-language DecisionRecord reproducibility envelope."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        title=DECISION_RECORD_SCHEMA_NAME,
    )

    schema_version: str = Field(default=DECISION_RECORD_SCHEMA_VERSION, min_length=1)
    decision_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    program_id: str | None = Field(min_length=1)
    item_id: str = Field(min_length=1)
    computed_at: AwareDatetime
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    normalized_snapshot_id: str = Field(min_length=1)
    normalized_snapshot_hash: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    source_revision_set: dict[str, str] = Field(min_length=1)
    graph_revision: str = Field(min_length=1)
    policy_bundle_id: str = Field(min_length=1)
    policy_bundle_hash: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    ranking_pipeline_hash: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    engine_version: str = Field(min_length=1)
    normalization_profile_version: str = Field(min_length=1)
    ready: bool
    ranking_position: int = Field(ge=1)

    def canonical_json(self) -> str:
        """Return deterministic JSON with sorted keys for hashing."""
        data = self.model_dump(mode="json")
        return json.dumps(
            data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
