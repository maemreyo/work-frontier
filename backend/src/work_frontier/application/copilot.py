"""Default-off bounded Copilot orchestration with grounded citations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from work_frontier.application.ports.copilot import (
    CopilotCitation,
    CopilotPrompt,
    CopilotProvider,
    CopilotPurpose,
    CopilotResult,
)

_SECRET_PATTERN = re.compile(
    r"(?i)(authorization\s*:|bearer\s+[a-z0-9._-]+|password\s*=|token\s*=|"
    r"private[_ -]?key|client[_ -]?secret)"
)
_INJECTION_PATTERNS = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "developer message",
    "change readiness",
    "change ranking",
    "rank this",
    "waive safety",
    "mark authoritative",
    "approve this",
)
_ALLOWED_CHANGE_KINDS = frozenset({"dependency_repair", "evidence_request"})


class CopilotMode(StrEnum):
    """Runtime Copilot states."""

    DISABLED = "disabled"
    ENABLED = "enabled"


class CopilotError(ValueError):
    """Signal a fail-closed Copilot governance violation."""


@dataclass(frozen=True, slots=True)
class CopilotPolicy:
    """Purpose and budget controls."""

    max_input_characters: int = 8_000
    max_output_tokens: int = 800
    request_budget: int = 100
    failure_threshold: int = 3


@dataclass(slots=True)
class CopilotService:
    """Provider-neutral service that cannot mutate product truth."""

    mode: CopilotMode
    provider: CopilotProvider | None
    policy: CopilotPolicy = CopilotPolicy()
    requests_used: int = 0
    consecutive_failures: int = 0

    def run(
        self,
        *,
        purpose: CopilotPurpose,
        text: str,
        allowed_citations: tuple[CopilotCitation, ...],
    ) -> CopilotResult:
        """Run one redacted and grounded Copilot request."""
        if self.mode is CopilotMode.DISABLED or self.provider is None:
            msg = "Copilot is disabled"
            raise CopilotError(msg)
        if self.consecutive_failures >= self.policy.failure_threshold:
            msg = "Copilot circuit is open"
            raise CopilotError(msg)
        if self.requests_used >= self.policy.request_budget:
            msg = "Copilot request budget exhausted"
            raise CopilotError(msg)
        normalized = text.strip()
        if not normalized or len(normalized) > self.policy.max_input_characters:
            msg = "Copilot input is blank or exceeds the purpose limit"
            raise CopilotError(msg)
        if _SECRET_PATTERN.search(normalized):
            msg = "Copilot input contains credential-like material"
            raise CopilotError(msg)
        lowered = normalized.casefold()
        if any(pattern in lowered for pattern in _INJECTION_PATTERNS):
            msg = "Copilot input crosses the prompt-injection or authority boundary"
            raise CopilotError(msg)
        canonical_allowed = tuple(sorted(set(allowed_citations)))
        if not canonical_allowed:
            msg = "Copilot requires at least one authoritative citation"
            raise CopilotError(msg)

        self.requests_used += 1
        prompt = CopilotPrompt(
            purpose=purpose,
            text=normalized,
            citations=canonical_allowed,
            max_output_tokens=self.policy.max_output_tokens,
        )
        try:
            result = self.provider.complete(prompt)
            validated = _validate_result(result, purpose, canonical_allowed)
        except Exception as exc:
            self.consecutive_failures += 1
            if isinstance(exc, CopilotError):
                raise
            msg = "Copilot provider failed"
            raise CopilotError(msg) from exc
        self.consecutive_failures = 0
        return validated


def _validate_result(
    result: CopilotResult,
    purpose: CopilotPurpose,
    allowed: tuple[CopilotCitation, ...],
) -> CopilotResult:
    if not result.text.strip():
        msg = "Copilot output must not be blank"
        raise CopilotError(msg)
    citations = tuple(sorted(set(result.citations)))
    if not citations or any(citation not in allowed for citation in citations):
        msg = "Copilot output contains missing or unknown citations"
        raise CopilotError(msg)
    if purpose is CopilotPurpose.EXPLAIN_DECISION:
        if result.proposed_change_kind is not None or result.proposed_change_payload:
            msg = "explanations cannot contain mutation proposals"
            raise CopilotError(msg)
    else:
        if result.proposed_change_kind not in _ALLOWED_CHANGE_KINDS:
            msg = (
                "Copilot may draft only dependency repair or evidence request proposals"
            )
            raise CopilotError(msg)
        payload_keys = {key for key, _value in result.proposed_change_payload}
        forbidden = {
            "ready",
            "ranking_position",
            "authority",
            "gate_state",
            "lifecycle",
            "completion",
        }
        if payload_keys & forbidden:
            msg = "Copilot proposal attempts to alter authoritative product truth"
            raise CopilotError(msg)
    return CopilotResult(
        text=result.text.strip(),
        citations=citations,
        proposed_change_kind=result.proposed_change_kind,
        proposed_change_payload=tuple(sorted(result.proposed_change_payload)),
    )
