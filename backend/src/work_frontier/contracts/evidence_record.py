"""Pydantic models for Work Frontier evidence records.

Models match the JSON Schema at contracts/evidence-record.schema.json exactly.
Schema version: 1.0.0
"""

from datetime import datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

JsonValue = str | int | float | bool | None | dict[str, object] | list[object]


class Invocation(BaseModel):
    """Invocation envelope for harness execution details."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    command: str = Field(
        min_length=1, description="Full command invoked by the harness"
    )
    exit_code: int = Field(description="Process exit code")
    working_directory: str | None = Field(
        default=None, description="Working directory where command was executed"
    )
    start_time: datetime = Field(
        description="ISO 8601 timestamp when execution started"
    )
    end_time: datetime = Field(
        description="ISO 8601 timestamp when execution completed"
    )
    duration_seconds: float = Field(ge=0, description="Execution duration in seconds")


class Tool(BaseModel):
    """Tool driver information."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Tool name (e.g., pytest, mypy, ruff)")
    version: str = Field(min_length=1, description="Tool version string")
    commit_sha: str = Field(
        pattern=r"^[a-f0-9]{40}$",
        description="Git commit SHA (40-character hex) of the tested codebase",
    )


class Artifact(BaseModel):
    """File or resource examined or produced during execution."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, description="File path relative to repository root")
    hashes: dict[str, str] | None = Field(
        default=None,
        description="Content hashes keyed by algorithm name (e.g., sha256)",
    )


class Result(BaseModel):
    """Individual test result or finding."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1, description="Result type identifier")
    passed: bool = Field(description="Whether this specific result passed")
    detail: str | None = Field(
        default=None, description="Human-readable detail about the result"
    )


class EvidenceRecord(BaseModel):
    """Canonical evidence record for verification harness execution.

    Inspired by SARIF v2.1.0 patterns (invocation envelope, tool.driver,
    artifact.hashes, propertyBag). The property_bag field is an extension
    point for harness-specific data without requiring schema migration.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = Field(
        description="Schema version for forward compatibility"
    )
    harness_id: str = Field(
        pattern=r"^WF-HAR-[A-Z]+-\d{2}$",
        description="Harness identifier: WF-HAR-{CATEGORY}-{NN}",
    )
    status: Literal["pass", "fail", "skip"] = Field(
        description="Overall harness execution status"
    )
    invocation: Invocation
    tool: Tool
    artifacts: list[Artifact] = Field(
        default_factory=list,
        description="Files or resources examined or produced during execution",
    )
    results: list[Result] = Field(
        default_factory=list, description="Individual test results or findings"
    )
    property_bag: dict[str, JsonValue] | None = Field(
        default=None,
        description=("Extension point for harness-specific data."),
    )
