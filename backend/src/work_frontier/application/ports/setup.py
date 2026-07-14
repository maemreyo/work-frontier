"""Outbound ports used by setup application services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from types import MappingProxyType

    from work_frontier.contracts.setup import (
        ActionState,
        DetectionCheck,
        SetupAction,
        SetupPlan,
        SetupProfile,
    )

Scalar = str | int | bool | None
ConfigurationDocument = dict[str, str | int | bool]
RedactedPayload = dict[str, Scalar]


@dataclass(frozen=True, slots=True)
class JournalAction:
    """Latest durable state for one setup action."""

    state: ActionState
    payload: MappingProxyType[str, Scalar]


@dataclass(frozen=True, slots=True)
class JournalSession:
    """Reconstructed durable setup session."""

    session_id: str
    plan_id: str
    actions: MappingProxyType[str, JournalAction]


class ConfigurationStore(Protocol):
    """Versioned non-secret configuration persistence."""

    def read(self) -> tuple[ConfigurationDocument, str]:
        """Return the current configuration and its revision."""
        ...

    def compare_and_swap(
        self,
        expected_revision: str,
        document: ConfigurationDocument,
    ) -> str:
        """Atomically replace configuration at the expected revision."""
        ...


class SetupJournal(Protocol):
    """Transactional reviewed-plan and action-state journal."""

    def acquire_installation_lock(
        self,
        installation_id: str,
        session_id: str,
    ) -> None:
        """Acquire the installation-wide writer lock."""
        ...

    def release_installation_lock(
        self,
        installation_id: str,
        session_id: str,
    ) -> None:
        """Release a lock owned by the supplied session."""
        ...

    def save_plan(self, plan: SetupPlan) -> None:
        """Persist a reviewed secret-free plan."""
        ...

    def load_plan(self, plan_id: str) -> SetupPlan:
        """Load a reviewed plan by identifier."""
        ...

    def latest_session_id(self) -> str | None:
        """Return the most recently updated session identifier."""
        ...

    def create_session(self, session_id: str, plan_id: str) -> None:
        """Create a durable execution session idempotently."""
        ...

    def record_transition(
        self,
        session_id: str,
        action_id: str,
        state: ActionState,
        payload: RedactedPayload,
    ) -> None:
        """Append one redacted action transition."""
        ...

    def load_session(self, session_id: str) -> JournalSession:
        """Reconstruct the latest action states for a session."""
        ...


class SystemProbe(Protocol):
    """Read-only environment inspection."""

    def detect(self, profile: SetupProfile) -> tuple[DetectionCheck, ...]:
        """Return read-only facts for the selected profile."""
        ...


class SetupActionRunner(Protocol):
    """Controlled side-effect runner for reviewed setup actions."""

    def apply(self, action: SetupAction) -> RedactedPayload:
        """Apply one reviewed action."""
        ...

    def verify(self, action: SetupAction) -> RedactedPayload:
        """Verify one applied action."""
        ...

    def compensate(self, action: SetupAction) -> RedactedPayload:
        """Compensate one reversible action."""
        ...
