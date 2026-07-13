"""Pydantic models for Work Frontier evidence records.

Models match the JSON Schema at contracts/generated/evidence-record.schema.json exactly.
Schema version: 1.0.0
"""

import math
import re
from pathlib import PurePosixPath
from typing import ClassVar, Final, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic import JsonValue as PydanticJsonValue

JsonValue = str | int | float | bool | None | dict[str, object] | list[object]

_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")

EVIDENCE_SEMANTIC_RULES: Final[dict[str, PydanticJsonValue]] = {
    "version": "1.0.0",
    "posix_relative_paths": [
        "invocation.working_directory",
        "artifacts[].path",
        "stdout_artifact.path",
        "stderr_artifact.path",
    ],
    "required_object_keys": [
        {"path": "environment", "keys": ["os"], "min_properties": 1}
    ],
    "duration": {
        "start": "invocation.start_time",
        "end": "invocation.end_time",
        "seconds": "invocation.duration_seconds",
        "tolerance_seconds": 0.001,
    },
    "not_applicable_reason": {"status": "not_applicable", "min_length": 10},
    "defaults": {"artifacts": [], "results": [], "release_stage": "pre_ga"},
}


class Invocation(BaseModel):
    """Invocation envelope for harness execution details."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    command: str = Field(
        min_length=1, description="Full command invoked by the harness"
    )
    exit_code: int = Field(description="Process exit code")
    working_directory: str = Field(
        min_length=1,
        pattern=r"^[^/]",
        description=(
            "Working directory (repo-relative) where command was executed. "
            "Must be a POSIX relative path (no leading slash)."
        ),
    )
    start_time: AwareDatetime = Field(
        description="ISO 8601 timestamp when execution started (must be timezone-aware)"
    )
    end_time: AwareDatetime = Field(
        description=(
            "ISO 8601 timestamp when execution completed (must be timezone-aware)"
        )
    )
    duration_seconds: float = Field(ge=0, description="Execution duration in seconds")

    @field_validator("working_directory")
    @classmethod
    def working_directory_must_be_repo_relative(cls, v: str) -> str:
        """Ensure the invocation directory is portable certification metadata."""
        parsed = PurePosixPath(v)
        if "\\" in v:
            msg = "working_directory must use POSIX separators"
            raise ValueError(msg)
        if parsed.is_absolute() or ".." in parsed.parts:
            msg = "working_directory must be repo-relative and contained"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_duration(self) -> "Invocation":
        """Enforce duration_seconds consistency with start_time/end_time."""
        expected = (self.end_time - self.start_time).total_seconds()
        if not math.isclose(self.duration_seconds, expected, abs_tol=0.001):
            msg = (
                f"duration_seconds ({self.duration_seconds}) does not match "
                f"end_time - start_time ({expected})"
            )
            raise ValueError(msg)
        return self


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

    Only SHA-256 is authoritative for certification.  Additional
    standard algorithms may be added as typed optional fields; the
    model does not accept arbitrary extra keys.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    sha256: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="Lowercase SHA-256 hex digest (required, canonical)",
    )
    md5: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{32}$",
        description="Optional MD5 hex digest (lowercase 32-char hex, legacy interop)",
    )
    sha512: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{128}$",
        description="Optional SHA-512 hex digest (lowercase 128-char hex)",
    )


class Artifact(BaseModel):
    """File or resource examined or produced during execution."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    path: str = Field(
        min_length=1,
        pattern=r"^[^/]",
        description=(
            "File path relative to repository root. "
            "Must be a POSIX relative path (no leading slash)."
        ),
    )
    hashes: ArtifactHashes = Field(
        description="Content hashes with required canonical sha256",
    )

    @field_validator("path")
    @classmethod
    def path_must_be_repo_relative(cls, v: str) -> str:
        """Reject absolute paths and path-traversal patterns.

        All artifact paths must be repository-root-relative (POSIX-style)
        so that certification is portable across working-directory layouts.
        """
        parsed = PurePosixPath(v)
        if "\\" in v:
            msg = f"artifact path must use POSIX separators: {v}"
            raise ValueError(msg)
        if parsed.is_absolute():
            msg = f"artifact path must be repo-relative, got absolute path: {v}"
            raise ValueError(msg)
        if ".." in parsed.parts:
            msg = f"artifact path must not contain '..' traversal: {v}"
            raise ValueError(msg)
        return v


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

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "if": {
                "properties": {"status": {"const": "not_applicable"}},
                "required": ["status"],
            },
            "then": {
                "properties": {
                    "applicability_reason": {
                        "type": "string",
                        "minLength": 10,
                        "description": (
                            "Substantive explanation of why the harness is not "
                            "applicable (min 10 characters)"
                        ),
                    }
                }
            },
            "x-work-frontier-semantic-rules": EVIDENCE_SEMANTIC_RULES,
        },
    )

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
    release_stage: Literal["pre_ga", "ga"] = Field(
        default="pre_ga",
        description=(
            "Release-stage dimension independent of workload scope; pre_ga "
            "harnesses remain required at GA"
        ),
    )
    applicability_reason: str = Field(
        min_length=1,
        description=(
            "Reason for the applicability value. Required for EVERY record: "
            "foundation records use 'Included in Standard foundation closure "
            "defined by registry.foundation_closure'; large/tenant records "
            "document the envelope trigger; not_applicable records document "
            "the condition that makes the harness inapplicable."
        ),
    )
    environment: dict[str, str] = Field(
        description=(
            "Environment fingerprint (OS, runtime versions, etc.). "
            "Must include 'os' key."
        ),
        json_schema_extra={
            "required": ["os"],
            "properties": {
                "os": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Operating system identifier (e.g., "
                    "linux-x86_64, darwin-arm64)",
                }
            },
        },
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
        """Validate applicability_reason is present for EVERY record."""
        if not self.applicability_reason or not self.applicability_reason.strip():
            msg = (
                f"applicability_reason is required for every record; "
                f"got status={self.status!r}, reason={self.applicability_reason!r}"
            )
            raise ValueError(msg)
        if self.status == "not_applicable" and len(self.applicability_reason) < 10:  # noqa: PLR2004
            msg = (
                f"applicability_reason for not_applicable must be a "
                f"substantive explanation (got {len(self.applicability_reason)} chars)"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_status_contradictions(self) -> "EvidenceRecord":
        """Reject status/result contradictions.

        When status is 'pass' every result must have passed=True.
        When status is 'fail' and exit_code is 0, at least one result
        must have passed=False.
        """
        if self.status == "pass":
            for r in self.results:
                if not r.passed:
                    msg = f"status is 'pass' but result {r.kind!r} has passed=False"
                    raise ValueError(msg)
        if (
            self.status == "fail"
            and self.invocation.exit_code == 0
            and not any(not r.passed for r in self.results)
        ):
            msg = "status is 'fail' with exit_code=0 but no result has passed=False"
            raise ValueError(msg)
        return self
