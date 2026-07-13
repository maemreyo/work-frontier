"""Typed domain invariant failures."""

from __future__ import annotations

from enum import StrEnum


class DomainErrorCode(StrEnum):
    """Stable machine-readable domain failure identifiers."""

    INVALID_ULID = "invalid_ulid"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_SCOPE = "invalid_scope"
    INVALID_ENTITY = "invalid_entity"
    INVALID_EDGE = "invalid_edge"
    CONTAINMENT_CYCLE = "containment_cycle"
    DERIVED_WITHOUT_DECISION = "derived_without_decision"
    INVALID_PROVENANCE = "invalid_provenance"
    INVALID_FRESHNESS_POLICY = "invalid_freshness_policy"
    AUTHORITATIVE_INFERENCE = "authoritative_inference"
    INVALID_POLICY = "invalid_policy"
    INVALID_GATE = "invalid_gate"
    INVALID_EVIDENCE = "invalid_evidence"
    SAFETY_GATE_WAIVER = "safety_gate_waiver"


class DomainInvariantError(ValueError):
    """Raised when a pure domain invariant is violated."""

    code: DomainErrorCode
    field: str
    detail: str

    def __init__(self, code: DomainErrorCode, field: str, detail: str) -> None:
        """Initialize a typed invariant failure."""
        self.code = code
        self.field = field
        self.detail = detail
        super().__init__(f"{code}: {field}: {detail}")
