---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-14
---

# Recommended Next

**WF-DOM-14**: Recommended Next is the top-ranked [DecisionRecord](decision-record.md) from the current [ranking](readiness-ranking.md#ranking), presented with full context and rationale. It is the engine's answer to "what should I do next?"

## What Recommended Next Is

Recommended Next is a projection of the latest [DecisionRecord](decision-record.md) for the top-ranked WorkItem. It is computed on every engine cycle by selecting the top item from the ranking pipeline and attaching:

| Component | Source |
|-----------|--------|
| The [DecisionRecord](decision-record.md) | The latest persisted decision for this WorkItem. |
| Ranking rationale | Which comparators placed this item first, with trace. |
| [Authority status](authority-statuses.md) | The authority status of each field the ranking used. |
| Active [AttentionItems](attention-items.md) | Items related to this WorkItem that need human attention. |
| Active [WorkLease](work-lease.md) | Who holds the coordination lease, if anyone. |
| [Gates](gates-and-evidence.md) | Gate states and pending evidence requirements. |
| Dependency context | What this item blocks (fan-out) and what blocks it. |

## What Recommended Next Is Not

- It is not a mutation. Viewing Recommended Next does not change any WorkItem's state.
- It is not a command. The human can ignore, override, or defer it.
- It is not persistent. Recommended Next is recomputed every cycle. The DecisionRecord it references is persisted; the recommendation itself is a live projection.
- It is not authoritative. It is the engine's best computation. The human's judgment supersedes it, subject to [safety override constraints](authority-statuses.md#safety-override-constraints).

## Ranking Pipeline

Recommended Next is the output of a configurable, deterministic, lexicographic [ranking pipeline](readiness-ranking.md#ranking). Default comparator order:

1. **Program priority** — Higher program priority = higher rank.
2. **Work class** — `foundation` > `implementation` > `certification`.
3. **Downstream unlock count desc** — More items unblocked = higher rank.
4. **Age desc** — Older items rank higher.
5. **Stable ID** — ULID tie-break. Deterministic, immutable.

The pipeline is configurable. The human can reorder, disable, or add comparators. See [Ranking](readiness-ranking.md#ranking) for the full specification.

## Recommended Next and Authority

Recommended Next is a computed projection. Its authority is [provisional](authority-statuses.md#authority-statuses): it reflects the engine's current computation and may change on the next cycle. The underlying [DecisionRecord](decision-record.md) carries its own authority status, which must be `authoritative` for the recommendation to be actionable. The human's decision to act on (or override) Recommended Next is an [authoritative mutation](work-item.md#safe-projections-vs-authoritative-mutations) — scoped, authorized, audited, time-bounded, and subject to [safety override constraints](authority-statuses.md#safety-override-constraints).

## Recommended Next and the Control Room

The Control Room displays Recommended Next prominently. It includes:

- The [DecisionRecord](decision-record.md): title, description, current state, and full decision context.
- The ranking rationale: which comparators placed it first, with detail.
- Any AttentionItems that apply.
- The dependency context: what this item blocks and what blocks it.
- Quick actions: claim, start, defer, override ranking, add evidence.

The human's response (act, override, defer) is recorded and feeds back into future ranking via the override comparator.
