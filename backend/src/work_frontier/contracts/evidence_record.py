"""Pydantic models for Work Frontier evidence records.

Models match the JSON Schema at contracts/generated/evidence-record.schema.json exactly.
Schema version: 1.0.0
"""

import re
from datetime import datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

JsonValue = str | int | float | bool | None | dict[str, object] | list[object]

_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class Invocation(BaseModel):
    """Invocation envelope for harness execution details."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    command: str = Field(
        min_length=1, description="Full command invoked by the harness"
    )
    exit_code: int = Field(description="Process exit code")
    working_directory: str = Field(
        description="Working directory (repo-relative) where command was executed"
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


class ArtifactHashes(BaseModel):
    """Typed content hashes with required canonical SHA-256.

    The ``sha256`` field is required and must be a lowercase 64-char hex
    string. Additional hash algorithms may be stored as extra fields for
    interoperability (e.g. md5 for legacy tools), but ``sha256`` is the
    authoritative content identity for certification.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    sha256: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="Lowercase SHA-256 hex digest (required, canonical)",
    )


class Artifact(BaseModel):
    """File or resource examined or produced during execution."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, description="File path relative to repository root")
    hashes: ArtifactHashes = Field(
        description="Content hashes with required canonical sha256",
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
        pattern=r"^WF-HAR-[A-Z0-9]+(?:-[A-Z0-9]+)*$",
        description="Harness identifier matching the authoritative registry",
    )
    status: Literal["pass", "fail", "skip", "not_applicable"] = Field(
        description="Overall harness execution status"
    )
    run_id: str = Field(
        min_length=1,
        description="Unique run identifier for this evidence generation",
    )
    subject_sha: str = Field(
        pattern=r"^[a-f0-9]{40}$",
        description="Git commit SHA of the code being tested",
    )
    subject_tree_sha: str = Field(
        pattern=r"^[a-f0-9]{40}$",
        description=(
            "Git tree SHA of the committed HEAD^{tree}. Required for "
            "revision-bound certification; every record in a closure must "
            "match the report's subject_tree_sha."
        ),
    )
    invocation: Invocation
    tool: Tool
    applicability: Literal["standard", "large", "tenant"] = Field(
        description="Harness applicability scope; required, no default",
    )
    applicability_reason: str | None = Field(
        default=None,
        description=(
            "Reason for the applicability value. Required when status is "
            "'not_applicable'; optional otherwise."
        ),
    )
    environment: dict[str, str] = Field(
        description="Environment fingerprint (OS, runtime versions, etc.)",
    )
    artifacts: list[Artifact] = Field(
        default_factory=list,
        description="Files or resources examined or produced during execution",
    )
    results: list[Result] = Field(
        default_factory=list, description="Individual test results or findings"
    )
    stdout_artifact: Artifact = Field(description="Captured stdout artifact")
    stderr_artifact: Artifact = Field(description="Captured stderr artifact")
    property_bag: dict[str, JsonValue] | None = Field(
        default=None,
        description=("Extension point for harness-specific data."),
    )

    @field_validator("environment")
    @classmethod
    def environment_must_be_non_empty(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate environment is non-empty and includes 'os' key."""
        msg = "environment must be non-empty and include 'os' key"
        if not v or "os" not in v:
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_applicability_reason(self) -> "EvidenceRecord":
        """Validate applicability_reason is present when status is not_applicable."""
        if self.status == "not_applicable" and (
            not self.applicability_reason or not self.applicability_reason.strip()
        ):
            msg = "applicability_reason is required when status is 'not_applicable'"
            raise ValueError(msg)
        return self
