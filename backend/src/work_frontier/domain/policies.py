"""Versioned policy DSL, phased gates, evidence, and completion semantics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final, cast

from work_frontier.domain.authority import AuthorityStatus
from work_frontier.domain.entities import Lifecycle
from work_frontier.domain.errors import DomainErrorCode, DomainInvariantError
from work_frontier.domain.identifiers import ActorId, EvidenceId, GateId, WorkItemId

if TYPE_CHECKING:
    from datetime import datetime

POLICY_SCHEMA_VERSION: Final = "1.0.0"
_MIN_WAIVER_REASON_LENGTH: Final = 10
_MIN_COMPOSITE_OPERANDS: Final = 2
_ALLOWED_EVIDENCE_AUTHORITIES: Final = frozenset(
    {AuthorityStatus.AUTHORITATIVE, AuthorityStatus.PROVISIONAL}
)


type EvidenceScalar = str | int | float | bool | None
type EvidenceContent = tuple[tuple[str, EvidenceScalar], ...]
type TruthValue = bool | None


class GatePhase(StrEnum):
    """Lifecycle phase constrained by a gate."""

    ENTRY = "entry"
    COMPLETION = "completion"
    CERTIFICATION = "certification"


class GateType(StrEnum):
    """Canonical gate categories."""

    DEPENDENCY = "dependency"
    EVIDENCE = "evidence"
    APPROVAL = "approval"
    QUALITY = "quality"
    SAFETY = "safety"


class GateState(StrEnum):
    """Canonical gate evaluation states."""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    WAIVED = "waived"


class EvidenceType(StrEnum):
    """Canonical evidence production modes."""

    COMPUTED = "computed"
    OBSERVED = "observed"
    DECLARED = "declared"


class EvidenceProducerKind(StrEnum):
    """Kinds of evidence producers; AI is explicitly prohibited."""

    AUTOMATION = "automation"
    HUMAN = "human"
    AI = "ai"


class AttestationMethod(StrEnum):
    """Supported evidence attestation methods."""

    SIGNATURE = "signature"
    CRYPTOGRAPHIC = "cryptographic"
    WITNESSED = "witnessed"
    DECLARED = "declared"


class CompletionPolicyKind(StrEnum):
    """Supported completion-policy AST node kinds."""

    ALL_GATES_PASSED = "all_gates_passed"
    ALL_DEPENDENCIES_COMPLETE = "all_dependencies_complete"
    ALL_CHILDREN_COMPLETE = "all_children_complete"
    EVIDENCE_DECLARED = "evidence_declared"
    COMPOSITE = "composite"
    MANUAL_ONLY = "manual_only"


class CompositeOperator(StrEnum):
    """Boolean operators accepted by composite completion policies."""

    AND = "and"
    OR = "or"


class CompletionResult(StrEnum):
    """Structured completion outcomes independent from lifecycle."""

    SATISFIED = "satisfied"
    INCOMPLETE = "incomplete"
    CLOSED_UNVERIFIED = "closed_unverified"
    PENDING_REVIEW = "pending_review"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Attestation:
    """Immutable evidence attestation."""

    attestor: str
    method: AttestationMethod
    timestamp: datetime
    content: str

    def __post_init__(self) -> None:
        """Validate attestation identity, content, and timestamp."""
        _require_text(self.attestor, "attestor", DomainErrorCode.INVALID_EVIDENCE)
        _require_text(self.content, "content", DomainErrorCode.INVALID_EVIDENCE)
        _require_aware(
            self.timestamp,
            "attestation.timestamp",
            DomainErrorCode.INVALID_EVIDENCE,
        )


@dataclass(frozen=True, slots=True)
class GatePolicy:
    """One parsed gate definition from a versioned policy bundle."""

    gate_id: GateId
    name: str
    phase: GatePhase
    gate_type: GateType
    accepted_evidence_types: tuple[EvidenceType, ...]
    attestation_required: bool
    waivable: bool
    safety_critical: bool

    def __post_init__(self) -> None:
        """Validate and canonicalize gate policy invariants."""
        _require_text(self.name, "name", DomainErrorCode.INVALID_GATE)
        accepted = tuple(sorted(set(self.accepted_evidence_types), key=str))
        if not accepted:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_GATE,
                "accepted_evidence_types",
                "at least one evidence type is required",
            )
        object.__setattr__(self, "accepted_evidence_types", accepted)

        if self.gate_type is GateType.SAFETY:
            if self.waivable:
                raise DomainInvariantError(
                    DomainErrorCode.SAFETY_GATE_WAIVER,
                    "waivable",
                    "safety gates cannot be waived",
                )
            if not self.safety_critical or not self.attestation_required:
                raise DomainInvariantError(
                    DomainErrorCode.INVALID_GATE,
                    "safety_critical",
                    "safety gates require safety_critical and attestation_required",
                )
        elif self.safety_critical:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_GATE,
                "safety_critical",
                "only safety gates may be safety-critical",
            )

        if self.waivable and self.gate_type not in {
            GateType.EVIDENCE,
            GateType.QUALITY,
        }:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_GATE,
                "waivable",
                "only evidence and quality gates may be waived",
            )


@dataclass(frozen=True, slots=True)
class PolicyEvidenceRecord:
    """Pure domain evidence bound to one gate, item, and revision."""

    evidence_id: EvidenceId
    gate_id: GateId
    item_id: WorkItemId
    evidence_type: EvidenceType
    revision: str
    source: str
    producer_kind: EvidenceProducerKind
    timestamp: datetime
    content: EvidenceContent
    authority_status: AuthorityStatus
    valid_until: datetime | None = None
    attestation: Attestation | None = None

    def __post_init__(self) -> None:
        """Validate scope, authority provenance, timestamps, and producer type."""
        _require_text(self.revision, "revision", DomainErrorCode.INVALID_EVIDENCE)
        _require_text(self.source, "source", DomainErrorCode.INVALID_EVIDENCE)
        _require_aware(
            self.timestamp,
            "timestamp",
            DomainErrorCode.INVALID_EVIDENCE,
        )
        if self.valid_until is not None:
            _require_aware(
                self.valid_until,
                "valid_until",
                DomainErrorCode.INVALID_EVIDENCE,
            )
            if self.valid_until <= self.timestamp:
                raise DomainInvariantError(
                    DomainErrorCode.INVALID_EVIDENCE,
                    "valid_until",
                    "must be later than timestamp",
                )
        if self.producer_kind is EvidenceProducerKind.AI:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_EVIDENCE,
                "producer_kind",
                "AI output never qualifies as evidence",
            )
        if (
            self.evidence_type in {EvidenceType.OBSERVED, EvidenceType.DECLARED}
            and self.producer_kind is not EvidenceProducerKind.HUMAN
        ):
            raise DomainInvariantError(
                DomainErrorCode.INVALID_EVIDENCE,
                "producer_kind",
                "observed and declared evidence require a human producer",
            )
        if (
            self.evidence_type is EvidenceType.COMPUTED
            and self.producer_kind is not EvidenceProducerKind.AUTOMATION
        ):
            raise DomainInvariantError(
                DomainErrorCode.INVALID_EVIDENCE,
                "producer_kind",
                "computed evidence requires an automation producer",
            )
        if self.attestation is not None and self.attestation.timestamp < self.timestamp:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_EVIDENCE,
                "attestation.timestamp",
                "attestation must not predate evidence",
            )
        object.__setattr__(self, "content", _canonical_content(self.content))


@dataclass(frozen=True, slots=True)
class GateWaiver:
    """Human waiver request with explicit provenance."""

    gate_id: GateId
    actor_id: ActorId
    reason: str
    waived_at: datetime

    def __post_init__(self) -> None:
        """Validate waiver reason and timestamp."""
        _require_text(self.reason, "reason", DomainErrorCode.INVALID_GATE)
        if len(self.reason.strip()) < _MIN_WAIVER_REASON_LENGTH:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_GATE,
                "reason",
                "waiver reason must contain at least 10 characters",
            )
        _require_aware(self.waived_at, "waived_at", DomainErrorCode.INVALID_GATE)


@dataclass(frozen=True, slots=True)
class GateEvaluation:
    """Deterministic evaluation result for one gate."""

    gate: GatePolicy
    state: GateState
    valid_evidence_ids: tuple[EvidenceId, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        """Canonicalize evidence identifiers and reasons."""
        if self.gate.gate_type is GateType.SAFETY and self.state is GateState.WAIVED:
            raise DomainInvariantError(
                DomainErrorCode.SAFETY_GATE_WAIVER,
                "state",
                "safety gates cannot enter waived state",
            )
        evidence_ids = tuple(sorted(set(self.valid_evidence_ids), key=str))
        object.__setattr__(self, "valid_evidence_ids", evidence_ids)
        object.__setattr__(self, "reasons", tuple(sorted(set(self.reasons))))


@dataclass(frozen=True, slots=True)
class PhaseEvaluation:
    """Aggregate gate result for one lifecycle phase."""

    phase: GatePhase
    lifecycle: Lifecycle
    evaluations: tuple[GateEvaluation, ...]
    allows_transition: bool


@dataclass(frozen=True, slots=True)
class CompletionPolicy:
    """Validated parse-don't-validate completion-policy AST node."""

    kind: CompletionPolicyKind
    operator: CompositeOperator | None = None
    operands: tuple[CompletionPolicy, ...] = ()

    def __post_init__(self) -> None:
        """Validate structural invariants for composite and leaf nodes."""
        if self.kind is CompletionPolicyKind.COMPOSITE:
            if self.operator is None or len(self.operands) < _MIN_COMPOSITE_OPERANDS:
                raise DomainInvariantError(
                    DomainErrorCode.INVALID_POLICY,
                    "completion_policy",
                    "composite requires an operator and at least two operands",
                )
        elif self.operator is not None or self.operands:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_POLICY,
                "completion_policy",
                "leaf completion policies cannot define operator or operands",
            )


@dataclass(frozen=True, slots=True)
class PolicyBundle:
    """Versioned, immutable policy bundle."""

    schema_version: str
    policy_id: str
    gates: tuple[GatePolicy, ...]
    completion_policy: CompletionPolicy

    def __post_init__(self) -> None:
        """Validate bundle version, identity, and unique gate IDs."""
        if self.schema_version != POLICY_SCHEMA_VERSION:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_POLICY,
                "schema_version",
                f"unsupported policy schema version: {self.schema_version!r}",
            )
        _require_text(self.policy_id, "policy_id", DomainErrorCode.INVALID_POLICY)
        gates = tuple(sorted(self.gates, key=lambda gate: str(gate.gate_id)))
        gate_ids = tuple(gate.gate_id for gate in gates)
        if len(gate_ids) != len(set(gate_ids)):
            raise DomainInvariantError(
                DomainErrorCode.INVALID_POLICY,
                "gates",
                "gate IDs must be unique",
            )
        object.__setattr__(self, "gates", gates)


@dataclass(frozen=True, slots=True)
class CompletionContext:
    """All pure inputs needed to evaluate completion."""

    item_id: WorkItemId
    lifecycle: Lifecycle
    current_revision: str
    now: datetime
    gate_evaluations: tuple[GateEvaluation, ...]
    evidence_records: tuple[PolicyEvidenceRecord, ...]
    dependencies_complete: bool | None
    children_complete: bool | None
    human_confirmed: bool

    def __post_init__(self) -> None:
        """Validate deterministic completion input identities and time."""
        _require_text(
            self.current_revision,
            "current_revision",
            DomainErrorCode.INVALID_POLICY,
        )
        _require_aware(self.now, "now", DomainErrorCode.INVALID_POLICY)


@dataclass(frozen=True, slots=True)
class CompletionEvaluation:
    """Structured completion result with condition-level diagnostics."""

    result: CompletionResult
    satisfied_conditions: tuple[str, ...]
    unsatisfied_conditions: tuple[str, ...]
    unknown_conditions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LifecycleTransitionDecision:
    """Decision for one normalized lifecycle transition."""

    current: Lifecycle
    target: Lifecycle
    allowed: bool
    reasons: tuple[str, ...]


def parse_policy_bundle(payload: Mapping[str, object]) -> PolicyBundle:
    """Parse an untrusted mapping into a strict versioned policy AST."""
    _require_keys(
        payload,
        allowed={"schema_version", "policy_id", "gates", "completion_policy"},
        required={"schema_version", "policy_id", "gates", "completion_policy"},
        field="policy_bundle",
    )
    schema_version = _expect_str(payload["schema_version"], "schema_version")
    policy_id = _expect_str(payload["policy_id"], "policy_id")
    raw_gates = _expect_list(payload["gates"], "gates")
    gates = tuple(_parse_gate(item, index) for index, item in enumerate(raw_gates))
    completion_policy = _parse_completion_policy(
        payload["completion_policy"],
        field="completion_policy",
    )
    return PolicyBundle(
        schema_version=schema_version,
        policy_id=policy_id,
        gates=gates,
        completion_policy=completion_policy,
    )


def evaluate_gate(  # noqa: PLR0913 - explicit auditable domain inputs
    *,
    gate: GatePolicy,
    item_id: WorkItemId,
    current_revision: str,
    condition_met: bool | None,
    evidence_records: tuple[PolicyEvidenceRecord, ...],
    now: datetime,
    waiver: GateWaiver | None = None,
) -> GateEvaluation:
    """Evaluate one gate with revision, authority, expiry, and waiver checks."""
    _require_text(
        current_revision,
        "current_revision",
        DomainErrorCode.INVALID_GATE,
    )
    _require_aware(now, "now", DomainErrorCode.INVALID_GATE)

    if waiver is not None:
        return _evaluate_waiver(gate, waiver)
    if condition_met is None:
        return GateEvaluation(
            gate=gate,
            state=GateState.FAILED,
            valid_evidence_ids=(),
            reasons=("condition_unknown",),
        )
    if not condition_met:
        return GateEvaluation(
            gate=gate,
            state=GateState.FAILED,
            valid_evidence_ids=(),
            reasons=("condition_not_met",),
        )

    candidates = tuple(
        evidence
        for evidence in evidence_records
        if evidence.gate_id == gate.gate_id and evidence.item_id == item_id
    )
    if not candidates:
        return GateEvaluation(
            gate=gate,
            state=GateState.PENDING,
            valid_evidence_ids=(),
            reasons=("evidence_missing",),
        )

    valid_ids: list[EvidenceId] = []
    failures: list[str] = []
    for evidence in candidates:
        reason = _evidence_failure_reason(
            gate=gate,
            evidence=evidence,
            current_revision=current_revision,
            now=now,
        )
        if reason is None:
            valid_ids.append(evidence.evidence_id)
        else:
            failures.append(reason)
    if valid_ids:
        return GateEvaluation(
            gate=gate,
            state=GateState.PASSED,
            valid_evidence_ids=tuple(valid_ids),
            reasons=(),
        )
    return GateEvaluation(
        gate=gate,
        state=GateState.FAILED,
        valid_evidence_ids=(),
        reasons=tuple(failures) or ("evidence_invalid",),
    )


def evaluate_phase(
    *,
    phase: GatePhase,
    evaluations: tuple[GateEvaluation, ...],
    lifecycle: Lifecycle,
) -> PhaseEvaluation:
    """Evaluate only gates applicable to one phase."""
    applicable = tuple(
        sorted(
            (
                evaluation
                for evaluation in evaluations
                if evaluation.gate.phase is phase
            ),
            key=lambda evaluation: str(evaluation.gate.gate_id),
        )
    )
    allowed = all(
        evaluation.state in {GateState.PASSED, GateState.WAIVED}
        for evaluation in applicable
    )
    return PhaseEvaluation(
        phase=phase,
        lifecycle=lifecycle,
        evaluations=applicable,
        allows_transition=allowed,
    )


def evaluate_completion(
    policy: CompletionPolicy,
    context: CompletionContext,
) -> CompletionEvaluation:
    """Evaluate completion policy independently from normalized lifecycle."""
    value, satisfied, unsatisfied, unknown = _evaluate_policy_node(policy, context)
    if value is True:
        result = CompletionResult.SATISFIED
    elif value is None:
        result = CompletionResult.UNKNOWN
    elif _contains_manual_only(policy):
        result = CompletionResult.PENDING_REVIEW
    elif context.lifecycle is Lifecycle.COMPLETED:
        result = CompletionResult.CLOSED_UNVERIFIED
    else:
        result = CompletionResult.INCOMPLETE
    return CompletionEvaluation(
        result=result,
        satisfied_conditions=tuple(sorted(set(satisfied))),
        unsatisfied_conditions=tuple(sorted(set(unsatisfied))),
        unknown_conditions=tuple(sorted(set(unknown))),
    )


def evaluate_lifecycle_transition(
    *,
    current: Lifecycle,
    target: Lifecycle,
    gate_evaluations: tuple[GateEvaluation, ...],
    completion: CompletionEvaluation | None = None,
) -> LifecycleTransitionDecision:
    """Apply canonical lifecycle transition and phased-gate rules."""
    allowed = False
    reasons: tuple[str, ...] = ("forbidden_lifecycle_transition",)

    unconditional = (
        current is target
        or (
            target is Lifecycle.CANCELLED
            and current in {Lifecycle.PLANNED, Lifecycle.ACTIVE}
        )
        or current is Lifecycle.UNKNOWN
        or (current is Lifecycle.COMPLETED and target is Lifecycle.UNKNOWN)
    )
    if unconditional:
        allowed = True
        reasons = ()
    elif current is Lifecycle.PLANNED and target is Lifecycle.ACTIVE:
        phase = evaluate_phase(
            phase=GatePhase.ENTRY,
            evaluations=gate_evaluations,
            lifecycle=current,
        )
        allowed = phase.allows_transition
        reasons = () if allowed else ("entry_gates_blocked",)
    elif current is Lifecycle.ACTIVE and target is Lifecycle.COMPLETED:
        phase = evaluate_phase(
            phase=GatePhase.COMPLETION,
            evaluations=gate_evaluations,
            lifecycle=current,
        )
        completion_satisfied = (
            completion is not None and completion.result is CompletionResult.SATISFIED
        )
        reason_items: list[str] = []
        if not phase.allows_transition:
            reason_items.append("completion_gates_blocked")
        if not completion_satisfied:
            reason_items.append("completion_policy_unsatisfied")
        allowed = phase.allows_transition and completion_satisfied
        reasons = tuple(reason_items)

    return LifecycleTransitionDecision(
        current=current,
        target=target,
        allowed=allowed,
        reasons=reasons,
    )


def _parse_gate(raw: object, index: int) -> GatePolicy:
    field = f"gates[{index}]"
    mapping = _expect_mapping(raw, field)
    allowed = {
        "gate_id",
        "name",
        "phase",
        "gate_type",
        "accepted_evidence_types",
        "attestation_required",
        "waivable",
        "safety_critical",
    }
    _require_keys(mapping, allowed=allowed, required=allowed, field=field)
    evidence_values = _expect_list(
        mapping["accepted_evidence_types"],
        f"{field}.accepted_evidence_types",
    )
    try:
        accepted = tuple(
            EvidenceType(
                _expect_str(value, f"{field}.accepted_evidence_types[{position}]")
            )
            for position, value in enumerate(evidence_values)
        )
        return GatePolicy(
            gate_id=GateId(_expect_str(mapping["gate_id"], f"{field}.gate_id")),
            name=_expect_str(mapping["name"], f"{field}.name"),
            phase=GatePhase(_expect_str(mapping["phase"], f"{field}.phase")),
            gate_type=GateType(_expect_str(mapping["gate_type"], f"{field}.gate_type")),
            accepted_evidence_types=accepted,
            attestation_required=_expect_bool(
                mapping["attestation_required"],
                f"{field}.attestation_required",
            ),
            waivable=_expect_bool(mapping["waivable"], f"{field}.waivable"),
            safety_critical=_expect_bool(
                mapping["safety_critical"],
                f"{field}.safety_critical",
            ),
        )
    except ValueError as exc:
        raise DomainInvariantError(
            DomainErrorCode.INVALID_POLICY,
            field,
            f"unknown gate construct: {exc}",
        ) from exc


def _parse_completion_policy(raw: object, *, field: str) -> CompletionPolicy:
    mapping = _expect_mapping(raw, field)
    if "kind" not in mapping:
        raise DomainInvariantError(
            DomainErrorCode.INVALID_POLICY,
            field,
            "missing required field 'kind'",
        )
    kind_value = _expect_str(mapping["kind"], f"{field}.kind")
    try:
        kind = CompletionPolicyKind(kind_value)
    except ValueError as exc:
        raise DomainInvariantError(
            DomainErrorCode.INVALID_POLICY,
            f"{field}.kind",
            f"unknown completion policy kind: {kind_value!r}",
        ) from exc

    if kind is CompletionPolicyKind.COMPOSITE:
        _require_keys(
            mapping,
            allowed={"kind", "operator", "operands"},
            required={"kind", "operator", "operands"},
            field=field,
        )
        operator_value = _expect_str(mapping["operator"], f"{field}.operator")
        try:
            operator = CompositeOperator(operator_value)
        except ValueError as exc:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_POLICY,
                f"{field}.operator",
                f"unknown composite operator: {operator_value!r}",
            ) from exc
        raw_operands = _expect_list(mapping["operands"], f"{field}.operands")
        operands = tuple(
            _parse_completion_policy(
                operand,
                field=f"{field}.operands[{index}]",
            )
            for index, operand in enumerate(raw_operands)
        )
        return CompletionPolicy(kind=kind, operator=operator, operands=operands)

    _require_keys(
        mapping,
        allowed={"kind"},
        required={"kind"},
        field=field,
    )
    return CompletionPolicy(kind=kind)


def _evaluate_waiver(gate: GatePolicy, waiver: GateWaiver) -> GateEvaluation:
    if waiver.gate_id != gate.gate_id:
        raise DomainInvariantError(
            DomainErrorCode.INVALID_GATE,
            "waiver.gate_id",
            "waiver must target the evaluated gate",
        )
    if gate.gate_type is GateType.SAFETY or gate.safety_critical:
        raise DomainInvariantError(
            DomainErrorCode.SAFETY_GATE_WAIVER,
            "waiver",
            "safety gates cannot be waived or weakened",
        )
    if not gate.waivable:
        raise DomainInvariantError(
            DomainErrorCode.INVALID_GATE,
            "waiver",
            "gate policy does not permit waiver",
        )
    return GateEvaluation(
        gate=gate,
        state=GateState.WAIVED,
        valid_evidence_ids=(),
        reasons=("human_waiver",),
    )


def _evidence_failure_reason(
    *,
    gate: GatePolicy,
    evidence: PolicyEvidenceRecord,
    current_revision: str,
    now: datetime,
) -> str | None:
    if evidence.revision != current_revision:
        return "evidence_revision_mismatch"
    if evidence.evidence_type not in gate.accepted_evidence_types:
        return "evidence_type_not_accepted"
    if evidence.authority_status not in _ALLOWED_EVIDENCE_AUTHORITIES:
        return f"evidence_authority_{evidence.authority_status}"
    if evidence.valid_until is not None and now >= evidence.valid_until:
        return "evidence_expired"
    if gate.attestation_required and evidence.attestation is None:
        return "evidence_attestation_missing"
    return None


def _evaluate_policy_node(
    policy: CompletionPolicy,
    context: CompletionContext,
) -> tuple[TruthValue, list[str], list[str], list[str]]:
    label = policy.kind.value
    if policy.kind is CompletionPolicyKind.ALL_GATES_PASSED:
        completion_phase = evaluate_phase(
            phase=GatePhase.COMPLETION,
            evaluations=context.gate_evaluations,
            lifecycle=context.lifecycle,
        )
        return _truth_result(completion_phase.allows_transition, label)
    if policy.kind is CompletionPolicyKind.ALL_DEPENDENCIES_COMPLETE:
        return _truth_result(context.dependencies_complete, label)
    if policy.kind is CompletionPolicyKind.ALL_CHILDREN_COMPLETE:
        return _truth_result(context.children_complete, label)
    if policy.kind is CompletionPolicyKind.EVIDENCE_DECLARED:
        value = any(
            _declared_evidence_is_current(record, context)
            for record in context.evidence_records
        )
        return _truth_result(value, label)
    if policy.kind is CompletionPolicyKind.MANUAL_ONLY:
        return _truth_result(context.human_confirmed, label)

    child_results = tuple(
        _evaluate_policy_node(operand, context) for operand in policy.operands
    )
    values = tuple(result[0] for result in child_results)
    satisfied = [item for result in child_results for item in result[1]]
    unsatisfied = [item for result in child_results for item in result[2]]
    unknown = [item for result in child_results for item in result[3]]
    if policy.operator is CompositeOperator.AND:
        value = _and_truth(values)
    else:
        value = _or_truth(values)
    return value, satisfied, unsatisfied, unknown


def _declared_evidence_is_current(
    evidence: PolicyEvidenceRecord,
    context: CompletionContext,
) -> bool:
    return (
        evidence.item_id == context.item_id
        and evidence.evidence_type is EvidenceType.DECLARED
        and evidence.revision == context.current_revision
        and evidence.authority_status in _ALLOWED_EVIDENCE_AUTHORITIES
        and (evidence.valid_until is None or context.now < evidence.valid_until)
    )


def _truth_result(
    value: TruthValue,
    label: str,
) -> tuple[TruthValue, list[str], list[str], list[str]]:
    if value is True:
        return value, [label], [], []
    if value is False:
        return value, [], [label], []
    return value, [], [], [label]


def _and_truth(values: tuple[TruthValue, ...]) -> TruthValue:
    if any(value is False for value in values):
        return False
    if any(value is None for value in values):
        return None
    return True


def _or_truth(values: tuple[TruthValue, ...]) -> TruthValue:
    if any(value is True for value in values):
        return True
    if any(value is None for value in values):
        return None
    return False


def _contains_manual_only(policy: CompletionPolicy) -> bool:
    if policy.kind is CompletionPolicyKind.MANUAL_ONLY:
        return True
    return any(_contains_manual_only(operand) for operand in policy.operands)


def _canonical_content(content: EvidenceContent) -> EvidenceContent:
    if not content:
        raise DomainInvariantError(
            DomainErrorCode.INVALID_EVIDENCE,
            "content",
            "evidence content must not be empty",
        )
    keys = tuple(key for key, _ in content)
    if any(not key.strip() for key in keys) or len(keys) != len(set(keys)):
        raise DomainInvariantError(
            DomainErrorCode.INVALID_EVIDENCE,
            "content",
            "evidence content keys must be nonblank and unique",
        )
    return tuple(sorted(content, key=lambda item: item[0]))


def _expect_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DomainInvariantError(
            DomainErrorCode.INVALID_POLICY,
            field,
            "expected an object",
        )
    raw_mapping = cast("Mapping[object, object]", value)
    if not all(isinstance(key, str) for key in raw_mapping):
        raise DomainInvariantError(
            DomainErrorCode.INVALID_POLICY,
            field,
            "object keys must be strings",
        )
    return cast("Mapping[str, object]", raw_mapping)


def _expect_list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise DomainInvariantError(
            DomainErrorCode.INVALID_POLICY,
            field,
            "expected an array",
        )
    return cast("list[object]", value)


def _expect_str(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainInvariantError(
            DomainErrorCode.INVALID_POLICY,
            field,
            "expected a nonblank string",
        )
    return value


def _expect_bool(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise DomainInvariantError(
            DomainErrorCode.INVALID_POLICY,
            field,
            "expected a boolean without coercion",
        )
    return value


def _require_keys(
    mapping: Mapping[str, object],
    *,
    allowed: set[str],
    required: set[str],
    field: str,
) -> None:
    keys = set(mapping)
    missing = sorted(required - keys)
    unknown = sorted(keys - allowed)
    if missing or unknown:
        raise DomainInvariantError(
            DomainErrorCode.INVALID_POLICY,
            field,
            f"strict object mismatch: missing={missing}, unknown={unknown}",
        )


def _require_text(
    value: str,
    field: str,
    code: DomainErrorCode,
) -> None:
    if not value.strip():
        raise DomainInvariantError(code, field, "must not be blank")


def _require_aware(
    value: datetime,
    field: str,
    code: DomainErrorCode,
) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainInvariantError(code, field, "timezone-aware datetime required")
