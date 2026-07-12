"""Canonical DecisionRecord transport contract."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import ClassVar, Final, cast, override

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
)
from pydantic_core import CoreSchema, core_schema

DECISION_RECORD_SCHEMA_NAME: Final = "DecisionRecordContract"
DECISION_RECORD_SCHEMA_VERSION: Final = "1.0.0"


class FrozenStringMap(Mapping[str, str]):
    """Immutable, canonically ordered string-to-string map."""

    __slots__: tuple[str, ...] = ("_data",)
    _data: dict[str, str]

    def __init__(self, data: Mapping[str, str]) -> None:
        if len(data) < 1:
            msg = "source_revision_set must not be empty"
            raise ValueError(msg)
        ordered: dict[str, str] = {}
        for key, value in data.items():
            ordered[key] = value
        object.__setattr__(self, "_data", dict(sorted(ordered.items())))

    @override
    def __getitem__(self, key: str) -> str:
        return self._data[key]

    @override
    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    @override
    def __len__(self) -> int:
        return len(self._data)

    @override
    def __repr__(self) -> str:
        return f"FrozenStringMap({self._data!r})"

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return self._data == cast("Mapping[str, str]", other)
        return NotImplemented

    @override
    def __hash__(self) -> int:
        return hash(tuple(self._data.items()))

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: type[object], _handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        dict_schema = core_schema.dict_schema(
            core_schema.str_schema(min_length=1),
            core_schema.str_schema(min_length=1),
            min_length=1,
        )
        as_instance = core_schema.is_instance_schema(cls)
        from_mapping = core_schema.no_info_after_validator_function(cls, dict_schema)
        return core_schema.json_or_python_schema(
            json_schema=from_mapping,
            python_schema=core_schema.union_schema([as_instance, from_mapping]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda value: dict(value),
                info_arg=False,
                return_schema=dict_schema,
            ),
        )


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
    source_revision_set: FrozenStringMap
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
