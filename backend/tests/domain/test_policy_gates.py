from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from work_frontier.domain.authority import AuthorityStatus
from work_frontier.domain.entities import Lifecycle
from work_frontier.domain.errors import DomainErrorCode, DomainInvariantError
from work_frontier.domain.identifiers import ActorId, EvidenceId, GateId, WorkItemId
from work_frontier.domain.policies import (
    Attestation,
    AttestationMethod,
    CompletionContext,
    CompletionPolicy,
    CompletionPolicyKind,
    CompletionResult,
    CompositeOperator,
    EvidenceProducerKind,
    EvidenceType,
    GateEvaluation,
    GatePhase,
    GatePolicy,
    GateState,
    GateType,
    GateWaiver,
    PolicyEvidenceRecord,
    evaluate_completion,
    evaluate_gate,
    evaluate_lifecycle_transition,
    evaluate_phase,
    parse_policy_bundle,
)

NOW = datetime(2026, 7, 13, 10, 0, tzinfo=UTC)
GATE_ID = GateId("01ARZ3NDEKTSV4RRFFQ69G5FAV")
ITEM_ID = WorkItemId("01ARZ3NDEKTSV4RRFFQ69G5FAW")
EVIDENCE_ID = EvidenceId("01ARZ3NDEKTSV4RRFFQ69G5FAX")
ACTOR_ID = ActorId("01ARZ3NDEKTSV4RRFFQ69G5FAY")


def _gate(
    *,
    phase: GatePhase = GatePhase.ENTRY,
    gate_type: GateType = GateType.QUALITY,
    waivable: bool = True,
    attestation_required: bool = False,
) -> GatePolicy:
    return GatePolicy(
        gate_id=GATE_ID,
        name="Quality proof",
        phase=phase,
        gate_type=gate_type,
        accepted_evidence_types=(EvidenceType.COMPUTED,),
        attestation_required=attestation_required,
        waivable=waivable,
        safety_critical=gate_type is GateType.SAFETY,
    )


def _evidence(
    *,
    revision: str = "revision-2",
    authority: AuthorityStatus = AuthorityStatus.AUTHORITATIVE,
    valid_until: datetime | None = None,
    attestation: Attestation | None = None,
) -> PolicyEvidenceRecord:
    return PolicyEvidenceRecord(
        evidence_id=EVIDENCE_ID,
        gate_id=GATE_ID,
        item_id=ITEM_ID,
        evidence_type=EvidenceType.COMPUTED,
        revision=revision,
        source="ci",
        producer_kind=EvidenceProducerKind.AUTOMATION,
        timestamp=NOW - timedelta(minutes=1),
        content=(("passed", True),),
        authority_status=authority,
        valid_until=valid_until,
        attestation=attestation,
    )


def _declared_evidence(*, valid_until: datetime | None = None) -> PolicyEvidenceRecord:
    return PolicyEvidenceRecord(
        evidence_id=EVIDENCE_ID,
        gate_id=GATE_ID,
        item_id=ITEM_ID,
        evidence_type=EvidenceType.DECLARED,
        revision="revision-2",
        source="human-review",
        producer_kind=EvidenceProducerKind.HUMAN,
        timestamp=NOW - timedelta(minutes=1),
        content=(("declared", True),),
        authority_status=AuthorityStatus.AUTHORITATIVE,
        valid_until=valid_until,
    )


def _evaluation(
    *,
    phase: GatePhase,
    state: GateState,
) -> GateEvaluation:
    return GateEvaluation(
        gate=_gate(phase=phase),
        state=state,
        valid_evidence_ids=(),
        reasons=(),
    )


def test_parse_policy_bundle_returns_typed_ast() -> None:
    payload: dict[str, object] = {
        "schema_version": "1.0.0",
        "policy_id": "standard-policy",
        "gates": [
            {
                "gate_id": str(GATE_ID),
                "name": "Entry quality",
                "phase": "entry",
                "gate_type": "quality",
                "accepted_evidence_types": ["computed"],
                "attestation_required": False,
                "waivable": True,
                "safety_critical": False,
            }
        ],
        "completion_policy": {
            "kind": "composite",
            "operator": "and",
            "operands": [
                {"kind": "all_gates_passed"},
                {"kind": "all_dependencies_complete"},
            ],
        },
    }

    bundle = parse_policy_bundle(payload)

    assert bundle.schema_version == "1.0.0"
    assert bundle.policy_id == "standard-policy"
    assert bundle.gates[0].gate_id == GATE_ID
    assert bundle.completion_policy.operator is CompositeOperator.AND


@pytest.mark.parametrize(
    "mutation",
    [
        {"unknown": True},
        {"completion_policy": {"kind": "made_up"}},
        {"schema_version": "2.0.0"},
    ],
)
def test_parse_policy_bundle_rejects_unknown_constructs(
    mutation: dict[str, object],
) -> None:
    payload: dict[str, object] = {
        "schema_version": "1.0.0",
        "policy_id": "standard-policy",
        "gates": [],
        "completion_policy": {"kind": "manual_only"},
    }
    payload.update(mutation)

    with pytest.raises(DomainInvariantError) as exc_info:
        _ = parse_policy_bundle(payload)

    assert exc_info.value.code is DomainErrorCode.INVALID_POLICY


def test_ai_output_cannot_be_constructed_as_evidence() -> None:
    with pytest.raises(DomainInvariantError) as exc_info:
        _ = PolicyEvidenceRecord(
            evidence_id=EVIDENCE_ID,
            gate_id=GATE_ID,
            item_id=ITEM_ID,
            evidence_type=EvidenceType.COMPUTED,
            revision="revision-2",
            source="ai",
            producer_kind=EvidenceProducerKind.AI,
            timestamp=NOW - timedelta(minutes=1),
            content=(("passed", True),),
            authority_status=AuthorityStatus.PROVISIONAL,
        )

    assert exc_info.value.code is DomainErrorCode.INVALID_EVIDENCE


def test_valid_revision_bound_evidence_passes_gate() -> None:
    evaluation = evaluate_gate(
        gate=_gate(),
        item_id=ITEM_ID,
        current_revision="revision-2",
        condition_met=True,
        evidence_records=(_evidence(),),
        now=NOW,
    )

    assert evaluation.state is GateState.PASSED
    assert evaluation.valid_evidence_ids == (EVIDENCE_ID,)


def test_condition_met_without_evidence_is_pending() -> None:
    evaluation = evaluate_gate(
        gate=_gate(),
        item_id=ITEM_ID,
        current_revision="revision-2",
        condition_met=True,
        evidence_records=(),
        now=NOW,
    )

    assert evaluation.state is GateState.PENDING
    assert evaluation.reasons == ("evidence_missing",)


@pytest.mark.parametrize(
    ("evidence", "reason"),
    [
        (_evidence(revision="revision-1"), "evidence_revision_mismatch"),
        (
            _evidence(valid_until=NOW - timedelta(seconds=1)),
            "evidence_expired",
        ),
        (
            _evidence(authority=AuthorityStatus.CONFLICTED),
            "evidence_authority_conflicted",
        ),
    ],
)
def test_invalid_evidence_fails_closed(
    evidence: PolicyEvidenceRecord,
    reason: str,
) -> None:
    evaluation = evaluate_gate(
        gate=_gate(),
        item_id=ITEM_ID,
        current_revision="revision-2",
        condition_met=True,
        evidence_records=(evidence,),
        now=NOW,
    )

    assert evaluation.state is GateState.FAILED
    assert reason in evaluation.reasons


def test_attestation_required_gate_rejects_unattested_evidence() -> None:
    evaluation = evaluate_gate(
        gate=_gate(attestation_required=True),
        item_id=ITEM_ID,
        current_revision="revision-2",
        condition_met=True,
        evidence_records=(_evidence(),),
        now=NOW,
    )

    assert evaluation.state is GateState.FAILED
    assert "evidence_attestation_missing" in evaluation.reasons


def test_attested_safety_evidence_passes() -> None:
    attestation = Attestation(
        attestor="safety-controller",
        method=AttestationMethod.CRYPTOGRAPHIC,
        timestamp=NOW,
        content="sha256:abcdef",
    )
    evaluation = evaluate_gate(
        gate=_gate(
            gate_type=GateType.SAFETY,
            waivable=False,
            attestation_required=True,
        ),
        item_id=ITEM_ID,
        current_revision="revision-2",
        condition_met=True,
        evidence_records=(_evidence(attestation=attestation),),
        now=NOW,
    )

    assert evaluation.state is GateState.PASSED


def test_safety_gate_waiver_is_rejected() -> None:
    waiver = GateWaiver(
        gate_id=GATE_ID,
        actor_id=ACTOR_ID,
        reason="Emergency exception requested",
        waived_at=NOW,
    )

    with pytest.raises(DomainInvariantError) as exc_info:
        _ = evaluate_gate(
            gate=_gate(
                gate_type=GateType.SAFETY,
                waivable=False,
                attestation_required=True,
            ),
            item_id=ITEM_ID,
            current_revision="revision-2",
            condition_met=False,
            evidence_records=(),
            now=NOW,
            waiver=waiver,
        )

    assert exc_info.value.code is DomainErrorCode.SAFETY_GATE_WAIVER


def test_quality_gate_can_be_validly_waived() -> None:
    waiver = GateWaiver(
        gate_id=GATE_ID,
        actor_id=ACTOR_ID,
        reason="Approved temporary quality exception",
        waived_at=NOW,
    )

    evaluation = evaluate_gate(
        gate=_gate(),
        item_id=ITEM_ID,
        current_revision="revision-2",
        condition_met=False,
        evidence_records=(),
        now=NOW,
        waiver=waiver,
    )

    assert evaluation.state is GateState.WAIVED


@pytest.mark.parametrize("lifecycle", tuple(Lifecycle))
@pytest.mark.parametrize("phase", tuple(GatePhase))
@pytest.mark.parametrize("state", tuple(GateState))
def test_phase_matrix_only_considers_matching_gate_phase(
    lifecycle: Lifecycle,
    phase: GatePhase,
    state: GateState,
) -> None:
    evaluation = _evaluation(phase=phase, state=state)
    result = evaluate_phase(
        phase=GatePhase.ENTRY,
        evaluations=(evaluation,),
        lifecycle=lifecycle,
    )

    expected = phase is not GatePhase.ENTRY or state in {
        GateState.PASSED,
        GateState.WAIVED,
    }
    assert result.allows_transition is expected


def test_completion_gate_does_not_block_start() -> None:
    completion_failure = _evaluation(
        phase=GatePhase.COMPLETION,
        state=GateState.FAILED,
    )

    entry = evaluate_phase(
        phase=GatePhase.ENTRY,
        evaluations=(completion_failure,),
        lifecycle=Lifecycle.PLANNED,
    )

    assert entry.allows_transition is True


def test_all_gates_passed_completion_policy_satisfies_active_item() -> None:
    context = CompletionContext(
        item_id=ITEM_ID,
        lifecycle=Lifecycle.ACTIVE,
        current_revision="revision-2",
        now=NOW,
        gate_evaluations=(
            _evaluation(phase=GatePhase.COMPLETION, state=GateState.PASSED),
        ),
        evidence_records=(),
        dependencies_complete=True,
        children_complete=True,
        human_confirmed=False,
    )

    result = evaluate_completion(
        CompletionPolicy(kind=CompletionPolicyKind.ALL_GATES_PASSED),
        context,
    )

    assert result.result is CompletionResult.SATISFIED


def test_closed_item_without_completion_proof_is_closed_unverified() -> None:
    context = CompletionContext(
        item_id=ITEM_ID,
        lifecycle=Lifecycle.COMPLETED,
        current_revision="revision-2",
        now=NOW,
        gate_evaluations=(
            _evaluation(phase=GatePhase.COMPLETION, state=GateState.FAILED),
        ),
        evidence_records=(),
        dependencies_complete=True,
        children_complete=True,
        human_confirmed=False,
    )

    result = evaluate_completion(
        CompletionPolicy(kind=CompletionPolicyKind.ALL_GATES_PASSED),
        context,
    )

    assert result.result is CompletionResult.CLOSED_UNVERIFIED


def test_manual_only_policy_requires_human_confirmation() -> None:
    policy = CompletionPolicy(kind=CompletionPolicyKind.MANUAL_ONLY)
    context = CompletionContext(
        item_id=ITEM_ID,
        lifecycle=Lifecycle.ACTIVE,
        current_revision="revision-2",
        now=NOW,
        gate_evaluations=(),
        evidence_records=(),
        dependencies_complete=True,
        children_complete=True,
        human_confirmed=False,
    )

    pending = evaluate_completion(policy, context)
    confirmed = evaluate_completion(
        policy,
        CompletionContext(
            item_id=context.item_id,
            lifecycle=context.lifecycle,
            current_revision=context.current_revision,
            now=context.now,
            gate_evaluations=context.gate_evaluations,
            evidence_records=context.evidence_records,
            dependencies_complete=context.dependencies_complete,
            children_complete=context.children_complete,
            human_confirmed=True,
        ),
    )

    assert pending.result is CompletionResult.PENDING_REVIEW
    assert confirmed.result is CompletionResult.SATISFIED


def test_composite_policy_evaluates_and_or_without_weakening() -> None:
    dependencies = CompletionPolicy(kind=CompletionPolicyKind.ALL_DEPENDENCIES_COMPLETE)
    children = CompletionPolicy(kind=CompletionPolicyKind.ALL_CHILDREN_COMPLETE)
    context = CompletionContext(
        item_id=ITEM_ID,
        lifecycle=Lifecycle.ACTIVE,
        current_revision="revision-2",
        now=NOW,
        gate_evaluations=(),
        evidence_records=(),
        dependencies_complete=True,
        children_complete=False,
        human_confirmed=False,
    )

    and_result = evaluate_completion(
        CompletionPolicy(
            kind=CompletionPolicyKind.COMPOSITE,
            operator=CompositeOperator.AND,
            operands=(dependencies, children),
        ),
        context,
    )
    or_result = evaluate_completion(
        CompletionPolicy(
            kind=CompletionPolicyKind.COMPOSITE,
            operator=CompositeOperator.OR,
            operands=(dependencies, children),
        ),
        context,
    )

    assert and_result.result is CompletionResult.INCOMPLETE
    assert or_result.result is CompletionResult.SATISFIED


def test_lifecycle_transition_requires_correct_phase_and_completion() -> None:
    entry_pass = _evaluation(phase=GatePhase.ENTRY, state=GateState.PASSED)
    entry_fail = _evaluation(phase=GatePhase.ENTRY, state=GateState.FAILED)
    completion_pass = _evaluation(
        phase=GatePhase.COMPLETION,
        state=GateState.PASSED,
    )
    completion_satisfied = evaluate_completion(
        CompletionPolicy(kind=CompletionPolicyKind.ALL_GATES_PASSED),
        CompletionContext(
            item_id=ITEM_ID,
            lifecycle=Lifecycle.ACTIVE,
            current_revision="revision-2",
            now=NOW,
            gate_evaluations=(completion_pass,),
            evidence_records=(),
            dependencies_complete=True,
            children_complete=True,
            human_confirmed=False,
        ),
    )

    assert evaluate_lifecycle_transition(
        current=Lifecycle.PLANNED,
        target=Lifecycle.ACTIVE,
        gate_evaluations=(entry_pass,),
    ).allowed
    assert not evaluate_lifecycle_transition(
        current=Lifecycle.PLANNED,
        target=Lifecycle.ACTIVE,
        gate_evaluations=(entry_fail,),
    ).allowed
    assert evaluate_lifecycle_transition(
        current=Lifecycle.ACTIVE,
        target=Lifecycle.COMPLETED,
        gate_evaluations=(completion_pass,),
        completion=completion_satisfied,
    ).allowed
    assert not evaluate_lifecycle_transition(
        current=Lifecycle.PLANNED,
        target=Lifecycle.COMPLETED,
        gate_evaluations=(entry_pass, completion_pass),
        completion=completion_satisfied,
    ).allowed


@pytest.mark.parametrize("gate_type", tuple(GateType))
def test_every_gate_type_requires_condition_and_valid_evidence(
    gate_type: GateType,
) -> None:
    attestation = None
    if gate_type is GateType.SAFETY:
        attestation = Attestation(
            attestor="safety-controller",
            method=AttestationMethod.CRYPTOGRAPHIC,
            timestamp=NOW,
            content="sha256:abcdef",
        )
    gate = _gate(
        gate_type=gate_type,
        waivable=gate_type in {GateType.EVIDENCE, GateType.QUALITY},
        attestation_required=gate_type is GateType.SAFETY,
    )

    passed = evaluate_gate(
        gate=gate,
        item_id=ITEM_ID,
        current_revision="revision-2",
        condition_met=True,
        evidence_records=(_evidence(attestation=attestation),),
        now=NOW,
    )
    unknown = evaluate_gate(
        gate=gate,
        item_id=ITEM_ID,
        current_revision="revision-2",
        condition_met=None,
        evidence_records=(_evidence(attestation=attestation),),
        now=NOW,
    )

    assert passed.state is GateState.PASSED
    assert unknown.state is GateState.FAILED
    assert unknown.reasons == ("condition_unknown",)


def test_declared_evidence_completion_is_revision_and_expiry_bound() -> None:
    policy = CompletionPolicy(kind=CompletionPolicyKind.EVIDENCE_DECLARED)
    valid = _declared_evidence()
    stale = _declared_evidence(valid_until=NOW - timedelta(seconds=1))
    context = CompletionContext(
        item_id=ITEM_ID,
        lifecycle=Lifecycle.ACTIVE,
        current_revision="revision-2",
        now=NOW,
        gate_evaluations=(),
        evidence_records=(valid,),
        dependencies_complete=True,
        children_complete=True,
        human_confirmed=False,
    )
    stale_context = CompletionContext(
        item_id=ITEM_ID,
        lifecycle=Lifecycle.ACTIVE,
        current_revision="revision-2",
        now=NOW,
        gate_evaluations=(),
        evidence_records=(stale,),
        dependencies_complete=True,
        children_complete=True,
        human_confirmed=False,
    )

    assert evaluate_completion(policy, context).result is CompletionResult.SATISFIED
    assert (
        evaluate_completion(policy, stale_context).result is CompletionResult.INCOMPLETE
    )


def test_unknown_completion_input_remains_unknown() -> None:
    context = CompletionContext(
        item_id=ITEM_ID,
        lifecycle=Lifecycle.ACTIVE,
        current_revision="revision-2",
        now=NOW,
        gate_evaluations=(),
        evidence_records=(),
        dependencies_complete=None,
        children_complete=True,
        human_confirmed=False,
    )

    result = evaluate_completion(
        CompletionPolicy(
            kind=CompletionPolicyKind.ALL_DEPENDENCIES_COMPLETE,
        ),
        context,
    )

    assert result.result is CompletionResult.UNKNOWN
    assert result.unknown_conditions == ("all_dependencies_complete",)
