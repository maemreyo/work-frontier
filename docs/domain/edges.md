---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-16
---

# Edges

**WF-DOM-16**: Work Frontier models four typed relationships between [WorkItems](work-item.md) and between WorkItems and [Programs](program.md): **contains**, **blocks**, **requires_gate**, and **related_to**. Each type has distinct semantics, [lifecycle](lifecycle-and-completion.md) effects, and [readiness](readiness-ranking.md#readiness) implications.

## Edge Types

### contains

A hierarchical parent-child relationship. The parent owns the child's scope.

| Property | Value |
|----------|-------|
| Direction | Parent → Child |
| Lifecycle effect | Parent cannot reach `completed` until all children are terminal (`completed` or `cancelled`). |
| Readiness effect | None. |
| Cycle rule | Must be a DAG (no cycles, shared children allowed across Programs). |

**Valid parent → child combinations:**

| Parent | Child | Meaning |
|--------|-------|---------|
| Program | WorkItem | Belongs to this Program's scope. |
| Program | Program | Nested containment via typed DAG. Enables portfolio rollups. |
| WorkItem | WorkItem | Sub-decision within the parent's scope. |

### blocks

A directional dependency: "A blocks B" means "B cannot complete until A completes."

| Property | Value |
|----------|-------|
| Direction | Blocker → Blocked |
| Lifecycle effect | Blocked item cannot transition to `completed` until blocker is `completed`. |
| Readiness effect | `hard`: readiness `false`. `soft`: readiness `true` (can start, cannot complete). |
| Cycle rule | Dependency SCCs are invalid for readiness evaluation. The affected SCC is isolated fail-closed and emits an [AttentionItem](attention-items.md); unaffected graph regions continue. |

**Subtypes:**

| Subtype | Meaning | Readiness effect |
|---------|---------|-----------------|
| `hard` | Cannot start until blocker is completed. | `false`. |
| `soft` | Can start but cannot complete until blocker is completed. | `true`. |

### requires gate

A [Gate](gates-and-evidence.md) must pass before the dependent WorkItem can advance.

| Property | Value |
|----------|-------|
| Direction | Gate → Dependent WorkItem |
| Lifecycle effect | Cannot advance past the gated transition until gate passes. |
| Readiness effect | `false` only when an `entry` gate is `failed` or `pending`; completion/certification gates constrain their own outcomes. |
| Cycle rule | Multiple `requires_gate` edges can target the same WorkItem. |

### related to

A loose association with no lifecycle or readiness impact.

| Property | Value |
|----------|-------|
| Direction | Bidirectional |
| Lifecycle effect | None. |
| Readiness effect | None. |
| Cycle rule | No restrictions. |

## Edge Structure

| Field | Type | Description |
|-------|------|-------------|
| `edge_id` | ULID | Unique identifier. |
| `edge_type` | enum | `contains`, `blocks`, `requires_gate`, `related_to`. |
| `source_id` | string | Source entity (WorkItem, Program, or Gate). |
| `target_id` | string | Target entity (WorkItem or Program). |
| `subtype` | string or null | For `blocks`: `hard` or `soft`. |
| `created_at` | ISO 8601 | When created. |
| `source` | enum | `tracker` or `user`. Edges are not created by the engine; they are ingested or manually created. |
| `provenance` | string | Why this edge exists. |

## Edge Invariants

- INV-EDGE-01: `contains` edges form a DAG. Cycles are rejected.
- INV-EDGE-02: Cyclic `blocks` SCCs are isolated fail-closed with provenance; unaffected components remain evaluable.
- INV-EDGE-03: `requires_gate` edges point from Gate to WorkItem.
- INV-EDGE-04: `related_to` edges have no lifecycle or readiness effects.
- INV-EDGE-05: Edge source is tracked with provenance.
- INV-EDGE-06: Edges are immutable once created.

## Edge and Readiness Interaction

| Edge type | Readiness effect on target |
|-----------|--------------------------|
| `blocks` (hard) | `false` until source is `completed`. |
| `blocks` (soft) | `true` (can start), but completion blocked. |
| `requires_gate` | `false` if an applicable `entry` gate is `failed` or `pending`; later-phase gates do not block starting work. |
| `contains` | No effect. |
| `related_to` | No effect. |

## Edge and Ranking Interaction

Edges affect [ranking](readiness-ranking.md#ranking) through the `downstream_unlock_count_desc` comparator: items with more downstream items unblocked via `blocks` edges rank higher. See [Ranking](readiness-ranking.md#ranking) for the full comparator pipeline.
