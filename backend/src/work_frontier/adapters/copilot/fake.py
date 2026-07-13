"""Deterministic fake Copilot provider for tests and local development."""

from __future__ import annotations

from dataclasses import dataclass

from work_frontier.application.ports.copilot import (
    CopilotPrompt,
    CopilotPurpose,
    CopilotResult,
)


@dataclass(frozen=True, slots=True)
class DeterministicCopilot:
    """Return stable grounded output without network calls."""

    def complete(self, prompt: CopilotPrompt) -> CopilotResult:
        """Build deterministic output from purpose and citations."""
        refs = ", ".join(citation.decision_id for citation in prompt.citations)
        if prompt.purpose is CopilotPurpose.EXPLAIN_DECISION:
            return CopilotResult(
                text=f"Explanation grounded in decisions: {refs}.",
                citations=prompt.citations,
            )
        if prompt.purpose is CopilotPurpose.DRAFT_EVIDENCE_REQUEST:
            return CopilotResult(
                text=f"Draft evidence request grounded in: {refs}.",
                citations=prompt.citations,
                proposed_change_kind="evidence_request",
                proposed_change_payload=(("request", prompt.text),),
            )
        return CopilotResult(
            text=f"Draft dependency repair grounded in: {refs}.",
            citations=prompt.citations,
            proposed_change_kind="dependency_repair",
            proposed_change_payload=(("rationale", prompt.text),),
        )
