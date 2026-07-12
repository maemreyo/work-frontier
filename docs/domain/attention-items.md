---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-10
---

# AttentionItem

**WF-DOM-10**: Work Frontier emits **AttentionItems** when the engine detects situations requiring human judgment. AttentionItems are not [WorkItems](work-item.md); they are signals the engine produces when it cannot proceed autonomously. AI may suggest attention items, but they are only emitted after deterministic validation.

## Purpose

The engine is bounded (see [Vision](../product/vision.md#design-principles)). It cannot:

- Resolve ambiguous tracker state.
- Decide between competing interpretations of evidence.
- Override safety constraints.
- Interpret human intent from tracker actions.

When the engine encounters any of these situations, it emits an AttentionItem instead of guessing or skipping.

## Structure

| Field | Type | Description |
|-------|------|-------------|
| `item_id` | ULID | Unique identifier. |
| `record_id` | string or null | The [WorkItem](work-item.md) this item relates to. Null for system-level items. |
| `group_id` | string or null | The [Program](program.md) this item relates to, if applicable. |
| `category` | enum | The kind of attention required. See [Categories](#categories). |
| `severity` | enum | `info`, `warning`, `critical`. Assigned at emission time based on the category and context. |
| `title` | string | Short description. Max 200 chars. |
| `detail` | string | Full explanation and what action is needed. |
| `suggested_action` | string or null | The engine's suggestion. Not binding. |
| `created_at` | ISO 8601 | When emitted. |
| `resolved_at` | ISO 8601 or null | When resolved. |
| `resolved_by` | string or null | Who resolved it. |
| `resolution` | string or null | `accepted`, `dismissed`, `auto_resolved`. |
| `deterministic_basis` | string | The deterministic rule or check that triggered this item. Required field. |

## Categories

These ten categories are the only valid AttentionItem categories. Severity is determined at emission time by the category and context, not escalated by age.

| Category | Typical severity | Trigger | Deterministic basis |
|----------|-----------------|---------|-------------------|
| `decision_changed` | warning | A [DecisionRecord](decision-record.md) changed from the previous cycle for the same WorkItem. | `prev_decision_id != current_decision_id`. |
| `authority_downgraded` | warning | A field's [authority status](authority-statuses.md) moved to a lower trust level. | `authority(prev) > authority(current)`. |
| `claim_at_risk` | warning | A [WorkLease](work-lease.md) is about to expire, was broken, or its policy hash is stale. | `lease_ttl_remaining < threshold OR lease_broken OR policy_hash_mismatch`. |
| `approval_required` | info | A decision or action requires human approval before proceeding. | `gate_type == approval AND gate_state == pending`. |
| `evidence_required` | info | A [Gate](gates-and-evidence.md#gate) needs an [EvidenceRecord](gates-and-evidence.md#evidencerecord) to advance. | `gate_state == pending AND evidence_missing`. |
| `graph_conflict` | critical | An edge would create a cycle, or the [edge graph](edges.md) has an inconsistency. | `cycle_detected(analysis) == true OR graph_inconsistency`. |
| `connection_degraded` | warning | A [TrackerConnection](tracker-connection.md) is stale, errored, or unreachable. | `last_sync_at > sync_interval OR connection_status == error`. |
| `certification_ready` | info | All quality and evidence conditions are met for a release or certification gate. | `all_certification_gates_passed == true`. |
| `security_action` | critical | A safety gate failed, or a security constraint was violated. Cannot be waived. | `gate_type == safety AND gate_state == failed`. |
| `capacity_action` | info | A claimant or [Program](program.md) has reached capacity limits or needs resource attention. | `capacity_threshold_exceeded OR resource_needed`. |

## Generation Rules

1. **Deterministic basis required.** Every AttentionItem must have a `deterministic_basis`. Items without one are not emitted.
2. **AI may suggest, not emit.** AI can propose attention items, but they are only emitted after deterministic validation confirms the triggering condition. AI-suggested items that fail validation are discarded.
3. **One item per situation.** No duplicate items for the same WorkItem and category within the same cycle.
4. **Idempotent emission.** If the situation persists, the engine does not create a new item. It updates the existing item if severity changes.
5. **Automatic resolution.** Some items resolve when the situation clears (e.g., `connection_degraded` resolves when the tracker reconnects).
6. **Human resolution.** Most items require human action: `accepted` or `dismissed`.
7. **No silent dismissal.** Every resolution is logged.

## Severity

Severity is assigned at emission time based on category and context. There is no age-based severity escalation. A `warning` item that has been open for a week remains `warning` unless the underlying condition changes to warrant a different severity.

| Severity | Meaning |
|----------|---------|
| `info` | For awareness. No immediate action required. |
| `warning` | Action recommended. Something needs attention soon. |
| `critical` | Action required now. Blocks progress or safety. |

Severity can be reassessed if the underlying condition changes (e.g., an `info` item becomes `warning` because the stale tracker data is now significantly outdated). This is driven by the deterministic basis, not by age.

## AttentionItems and Readiness

| Category | Effect on related WorkItem's readiness |
|----------|---------------------------------------|
| `graph_conflict` | `false`. |
| `security_action` | `false`. |
| `decision_changed` | Re-evaluates. |
| `authority_downgraded` | Re-evaluates. |
| All others | No direct effect. |

## AttentionItems and Recommended Next

AttentionItems related to the current [Recommended Next](recommended-next.md) are shown alongside the recommendation. A `critical` item on the top-ranked WorkItem may cause the engine to suggest addressing it first.

## Invariants

- INV-AI-01: Every AttentionItem has a `deterministic_basis`. No item is emitted without it.
- INV-AI-02: AI may suggest attention items but they are only emitted after deterministic validation.
- INV-AI-03: AttentionItems are immutable once created (except severity reassignment on condition change and resolution).
- INV-AI-04: Every resolved item carries a resolution type and resolver.
- INV-AI-05: Severity is assigned at emission time, not escalated by age.
- INV-AI-06: `critical` AttentionItems on a WorkItem prevent it from being Recommended Next.
