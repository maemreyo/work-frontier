"""Application-owned provider-neutral Copilot contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class CopilotPurpose(StrEnum):
    """Only non-authoritative Copilot purposes."""

    EXPLAIN_DECISION = "explain_decision"
    DRAFT_EVIDENCE_REQUEST = "draft_evidence_request"
    DRAFT_DEPENDENCY_REPAIR = "draft_dependency_repair"


@dataclass(frozen=True, slots=True, order=True)
class CopilotCitation:
    """Reference to existing authoritative product records."""

    decision_id: str
    evidence_id: str | None = None

    def __post_init__(self) -> None:
        """Reject blank references."""
        if not self.decision_id.strip():
            msg = "decision_id is required"
            raise ValueError(msg)
        if self.evidence_id is not None and not self.evidence_id.strip():
            msg = "evidence_id must be non-blank when present"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class CopilotPrompt:
    """Redacted request sent to a provider."""

    purpose: CopilotPurpose
    text: str
    citations: tuple[CopilotCitation, ...]
    max_output_tokens: int


@dataclass(frozen=True, slots=True)
class CopilotResult:
    """Grounded explanation or proposal draft returned by a provider."""

    text: str
    citations: tuple[CopilotCitation, ...]
    proposed_change_kind: str | None = None
    proposed_change_payload: tuple[tuple[str, str], ...] = ()


class CopilotProvider(Protocol):
    """Minimal provider boundary with no product mutation methods."""

    def complete(self, prompt: CopilotPrompt) -> CopilotResult:
        """Return one bounded provider response."""
        ...
