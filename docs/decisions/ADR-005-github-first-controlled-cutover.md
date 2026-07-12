---
id: ADR-005
title: "GitHub-First Controlled Writer Cutover"
status: accepted
owner: Work Frontier architecture
date: 2026-07-12
scope: Work Frontier delivery and cutover strategy
classification: decision
related: [WF-REF-001, WF-REF-002, WF-DEL-001]
---

# ADR-005: GitHub-First Controlled Writer Cutover

## Status

Accepted

## Context

The legacy script writer producing the single generated issue #539 must be replaced by Work Frontier's managed projection. The fixture's `## Blocked by` edges and `PROGRAM_GATES` policy edges define merge-order constraints. Cutover must be controlled and reversible (WF-REF-002).

## Decision

Three pillars:

### 1. GitHub Issues as Coordination Surface

Dependency tracking via `## Blocked by` in issue bodies, supplemented by `PROGRAM_GATES` policy edges (WF-REF-001 §6). Progress via labels and milestones. Completion evidence per ADR-004.

### 2. Controlled Writer Ownership

| State | Writer | Behavior |
|-------|--------|----------|
| Legacy active | Legacy script | Script writes output; projection reads-only |
| Shadow | Both engines run | Only legacy output ships; projection output logged |
| Projection active | Work Frontier pipeline | Projection writes output; legacy in verify-only or retired |

Writer ownership is binary: exactly one writer is active at any time. No concurrent writes. The cutover switches writer identity, not traffic percentage.

Stale-write guard: projection refuses to write when the input snapshot is older than the current output version.

### 3. Controlled Sequence

Per WF-REF-002 phases (import → shadow → compare → approval → disable old workflow and claim owner → publish → observe → legacy verify-only/retire). Each step: PR review with evidence, CI validation, writer state check, merge. Rollback at every step restores the old writer (< 5 min).

## Consequences

**+** Explicit writer ownership. No split-brain. Deployment ≠ activation. Rollback always available by restoring old writer.
**-** Team discipline required for cutover sequence. Single-writer constraint limits parallelism during transition.

---

| Date | Change | Author |
|------|--------|--------|
| 2026-07-12 | Accepted. | Work Frontier |
| 2026-07-12 | Principal audit: removed feature traffic flags; replaced with controlled writer ownership. | Work Frontier |
