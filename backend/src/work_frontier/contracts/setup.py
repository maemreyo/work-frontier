"""Canonical contracts for interactive setup and ongoing configuration repair."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal, Self

if TYPE_CHECKING:
    from collections.abc import Mapping

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

_SECRET_MARKERS = ("password", "token", "private_key", "private-key", "secret")


class StaleSetupPlanError(ValueError):
    """Signal a reviewed plan whose detection basis changed."""


class StrictModel(BaseModel):
    """Reject unknown fields and keep setup facts immutable."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class SetupProfile(StrEnum):
    """Supported onboarding profiles."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"


class CapabilityName(StrEnum):
    """Independent setup readiness capabilities."""

    LOCAL_RUNTIME = "local_runtime"
    GITHUB_INTEGRATION = "github_integration"
    RELEASE_CERTIFICATION = "release_certification"
    PRODUCTION_CUTOVER = "production_cutover"


class CheckState(StrEnum):
    """Typed detector and capability states."""

    READY = "ready"
    REPAIRABLE = "repairable"
    NEEDS_INPUT = "needs_input"
    BLOCKED = "blocked"
    NOT_REQUIRED = "not_required"


class ActionState(StrEnum):
    """Journaled setup action states."""

    PENDING = "pending"
    RUNNING = "running"
    APPLIED = "applied"
    VERIFIED = "verified"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    MANUAL_RECOVERY_REQUIRED = "manual_recovery_required"


class SecretReference(StrictModel):
    """Opaque reference to secret material owned by another provider."""

    uri: Annotated[str, Field(min_length=8, max_length=512)]

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, value: str) -> str:
        """Require an opaque supported-provider URI."""
        scheme, separator, remainder = value.partition("://")
        if separator != "://" or scheme not in {"keyring", "env", "gh-cli"}:
            message = "secret reference must use keyring://, env://, or gh-cli://"
            raise ValueError(message)
        if not remainder or any(character.isspace() for character in value):
            message = "secret reference must contain a non-empty opaque path"
            raise ValueError(message)
        return value

    @computed_field
    @property
    def scheme(self) -> str:
        """Return the reference provider scheme."""
        return self.uri.partition("://")[0]


class DetectionCheck(StrictModel):
    """One read-only environment fact with user-facing remediation."""

    check_id: Annotated[str, Field(min_length=1, max_length=128)]
    state: CheckState
    summary: Annotated[str, Field(min_length=1, max_length=512)]
    impact: Annotated[str, Field(min_length=1, max_length=1024)]
    remediation: tuple[str, ...] = ()
    evidence: dict[str, str | int | bool | None] = Field(default_factory=dict)

    @field_validator("evidence")
    @classmethod
    def reject_secret_evidence(
        cls,
        value: dict[str, str | int | bool | None],
    ) -> dict[str, str | int | bool | None]:
        """Reject secret-bearing detector evidence."""
        _reject_secret_mapping(value)
        return value


class DetectionSnapshot(StrictModel):
    """Canonical read-only detection snapshot."""

    snapshot_id: str
    profile: SetupProfile
    config_revision: str
    checks: tuple[DetectionCheck, ...]


class SetupAction(StrictModel):
    """One deterministic reviewed side effect."""

    action_id: Annotated[str, Field(min_length=1, max_length=128)]
    title: Annotated[str, Field(min_length=1, max_length=256)]
    reason: Annotated[str, Field(min_length=1, max_length=1024)]
    risk: Literal["low", "medium", "high"]
    reversible: bool
    depends_on: tuple[str, ...]
    kind: Annotated[str, Field(min_length=1, max_length=128)]
    parameters: dict[str, str | int | bool | None]

    @field_validator("parameters")
    @classmethod
    def reject_secret_parameters(
        cls,
        value: dict[str, str | int | bool | None],
    ) -> dict[str, str | int | bool | None]:
        """Reject secret-bearing action parameters."""
        _reject_secret_mapping(value)
        return value

    @model_validator(mode="after")
    def reject_self_dependency(self) -> Self:
        """Reject direct self-dependencies."""
        if self.action_id in self.depends_on:
            message = "action cannot depend on itself"
            raise ValueError(message)
        return self


class SetupPlan(StrictModel):
    """Secret-free, deterministic, dependency-ordered setup plan."""

    plan_id: str
    profile: SetupProfile
    detection_snapshot_id: str
    config_revision: str
    actions: tuple[SetupAction, ...]

    def assert_current(
        self,
        snapshot: DetectionSnapshot,
        config_revision: str,
    ) -> None:
        """Reject execution when the reviewed basis changed."""
        if (
            self.detection_snapshot_id != snapshot.snapshot_id
            or self.config_revision != config_revision
        ):
            message = "setup plan is stale; detect and review again"
            raise StaleSetupPlanError(message)

    @model_validator(mode="after")
    def validate_dependency_order(self) -> Self:
        """Require unique IDs in serialized dependency order."""
        action_ids = [action.action_id for action in self.actions]
        if len(action_ids) != len(set(action_ids)):
            message = "setup action IDs must be unique"
            raise ValueError(message)
        known: set[str] = set()
        for action in self.actions:
            if any(dependency not in known for dependency in action.depends_on):
                message = "actions must be serialized in dependency order"
                raise ValueError(message)
            known.add(action.action_id)
        return self


class ActionResult(StrictModel):
    """Redacted outcome for one setup action."""

    action_id: str
    state: ActionState
    message: str
    redacted_evidence: dict[str, str | int | bool | None] = Field(default_factory=dict)

    @field_validator("redacted_evidence")
    @classmethod
    def reject_secret_result_evidence(
        cls,
        value: dict[str, str | int | bool | None],
    ) -> dict[str, str | int | bool | None]:
        """Reject secret-bearing execution evidence."""
        _reject_secret_mapping(value)
        return value


class CapabilityReport(StrictModel):
    """Independent readiness report for one capability."""

    capability: CapabilityName
    state: CheckState
    reason: str
    impact: str
    next_actions: tuple[str, ...]
    supporting_check_ids: tuple[str, ...]


class SetupEnvelope(StrictModel):
    """Cross-language setup API envelope."""

    session_id: str | None = None
    detection: DetectionSnapshot | None = None
    plan: SetupPlan | None = None
    capabilities: tuple[CapabilityReport, ...] = ()
    results: tuple[ActionResult, ...] = ()


def _reject_secret_mapping(value: Mapping[str, object]) -> None:
    for key, item in value.items():
        normalized = key.casefold().replace("-", "_")
        if any(marker.replace("-", "_") in normalized for marker in _SECRET_MARKERS):
            if isinstance(item, str) and item.startswith(
                ("keyring://", "env://", "gh-cli://")
            ):
                continue
            message = f"secret-bearing field is forbidden: {key}"
            raise ValueError(message)
