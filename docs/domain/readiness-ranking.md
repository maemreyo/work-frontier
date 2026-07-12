---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-18
---

# Readiness and Ranking

**WF-DOM-18**: Work Frontier computes two properties for every [WorkItem](work-item.md): **readiness** (can this be worked on?) and **ranking** (where does it sit among ready items?). Ranking uses a configurable, deterministic, lexicographic pipeline with no AI influence and a stable tie-break.

## Readiness

Readiness is a computed boolean. `true` means the WorkItem is available for work right now. `false` means something blocks it.

### Readiness Evaluation

| Condition | Check | Effect |
|-----------|-------|--------|
| Hard [`blocks` edges](edges.md#blocks) | All hard blockers are `completed` | Any incomplete → `false` |
| Claim availability | No other claimant holds an active exclusive [WorkLease](work-lease.md) | Another claimant holds it → underlying eligibility remains visible, but it is excluded from that actor's claimable frontier |
| Entry/readiness [Gates](gates-and-evidence.md) | All gates applicable before work starts are `passed` or validly waived | Any applicable `failed` or `pending` → `false`; completion-only gates do not block starting work |
| [Lifecycle](lifecycle-and-completion.md) state | State is `planned` or `active` | `completed`, `cancelled`, `unknown` → `false` |
| [Authority status](authority-statuses.md) | Safety-critical fields are not `unavailable` or `conflicted` | Unsafe authority → `false` |

All conditions must pass. If any fails, readiness is `false`.

### Readiness Provenance

Every readiness evaluation carries provenance: which conditions passed, which failed, and why.

### Readiness vs Lifecycle State

| Lifecycle state | Typical readiness | Why |
|----------------|------------------|-----|
| `planned` | `true` (if no other blocks) | Available for claiming. |
| `active` | `true` when no other condition blocks it | Active work can remain actionable; an exclusive lease controls who may claim or continue it. |
| `completed` | `false` | Complete. Nothing to do. |
| `cancelled` | `false` | Abandoned. |
| `unknown` | `false` | Cannot determine availability. |

## Ranking

Ranking sorts all ready WorkItems into a single ordered list. The top item is [Recommended Next](recommended-next.md).

### Ranking Pipeline

Ranking is a **configurable lexicographic pipeline**: a sequence of comparators applied in order. The first comparator that distinguishes two items determines their relative order. Later comparators are not consulted for that pair.

```
Ready Items → [Comparator 1] → [Comparator 2] → ... → [Comparator N] → Ranked List
```

### Comparator Specification

Every comparator implements the same interface:

```
compare(itemA, itemB) → -1 | 0 | 1
```

- `-1`: A ranks higher than B.
- `0`: A and B are equal (defer to next comparator).
- `1`: B ranks higher than A.

### Default Comparator Pipeline

| Order | Comparator | What it compares | Deterministic? |
|-------|-----------|-----------------|----------------|
| 1 | `program_priority` | The priority assigned to the item's [Program](program.md). Higher program priority = higher rank. | Yes |
| 2 | `work_class` | The item's work class: `foundation` > `implementation` > `certification`. Foundation work ranks first because it unblocks everything downstream. | Yes |
| 3 | `downstream_unlock_count_desc` | Count of downstream items this item unblocks (fan-out via [`blocks` edges](edges.md#blocks)). Higher count = higher rank. | Yes |
| 4 | `age_desc` | Time since `created_at`. Older items rank higher (stale ready work signals neglect). | Yes |
| 5 | `stable_id` | `item_id` (ULID). Deterministic, immutable tie-break. Never changes. | Yes |

**Tie-break:** When all comparators return `0` for two items, `stable_id` (ULID, time-sortable) determines order. This guarantees a total order with no randomness.

### Configuring the Pipeline

The human can:

- **Reorder comparators.** Move `downstream_unlock_count_desc` before `work_class` if leverage matters more than work class.
- **Disable comparators.** Remove `age_desc` if item age is irrelevant.
- **Add custom comparators.** Define new comparators via configuration (e.g., "items in the current sprint rank higher").
- **Set comparator parameters.** For example, set the age threshold at which an item gets a boost.

Configuration changes take effect on the next engine cycle. The pipeline is recompiled from configuration, not hard-coded.

### What Ranking Is Not

- **Not weighted.** No scoring function combines signals with weights. Comparators are applied lexicographically.
- **Not AI-influenced.** No AI model contributes to ranking. Every comparator is deterministic and auditable.
- **Not persistent.** Ranking is recomputed every cycle. If conditions change, the order changes.
- **Not authoritative.** Ranking is a projection. The human can override it (subject to [override safety constraints](authority-statuses.md#safety-override-constraints)).

### User Overrides

A human can pin a WorkItem to the top of the ranking. This creates a user-authority snapshot with [human override](authority-statuses.md#source-precedence) precedence. Overrides are:

- **Scoped** to the specific WorkItem.
- **Authorized** — only primary owner or admin can pin.
- **Audited** — logged with who, when, why.
- **Time-bounded** — all TTLs are configurable. No hard-coded defaults.
- **Non-weakening** — cannot bypass safety gates or completion policies.

The `override_asc` comparator places pinned items first. Overrides carry provenance and can be retracted.

## Readiness x Ranking Interaction

```
TrackerConnection sync → WorkItem snapshot (with authority status)
                              │
                              ▼
                    ┌─────────────────┐
                    │ Readiness check  │ ← edges, gates, leases, lifecycle, authority
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Ranking pipeline │ ← lexicographic comparators, configurable
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Recommended Next │ ← top-ranked ready WorkItem + rationale
                    └─────────────────┘
```

The human acts on Recommended Next. Their action produces a new user snapshot with [human override](authority-statuses.md#source-precedence) precedence. The next cycle incorporates it and re-computes readiness and ranking. The engine produces a new [DecisionRecord](decision-record.md) capturing the decision at that point in time.

## Invariants

- INV-RANK-01: The ranking pipeline is deterministic. Same inputs → same output.
- INV-RANK-02: No AI model contributes to ranking comparators.
- INV-RANK-03: Comparator order is configurable and auditable.
- INV-RANK-04: `stable_id` (ULID) guarantees a total order with no randomness.
- INV-RANK-05: User overrides are scoped, authorized, audited, time-bounded, and cannot weaken safety or completion policies.
- INV-RANK-06: Readiness is computed on each engine cycle and persisted only as an immutable DecisionRecord snapshot, never as mutable source truth.
- INV-RANK-07: Readiness and ranking are independent. Readiness filters; ranking sorts.
