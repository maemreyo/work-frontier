---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-PROD-01
---

# Vision and Positioning

**WF-PROD-01**: Work Frontier exists to answer one question for a human working on a project: "What should I do next?"

## The Problem

Every project has work items scattered across trackers. They sit in different states, carry different labels, and follow different workflows. A human who wants to know what matters most right now must mentally merge state from multiple sources, resolve conflicts, check dependencies, and rank by importance. This is slow, inconsistent, and error-prone.

The problem gets worse as projects grow. The number of items, the density of dependencies, and the volume of tracker noise all increase. Humans compensate by developing personal heuristics, holding status meetings, or simply picking whatever looks urgent. None of these scale.

## What Work Frontier Does

Work Frontier is a **dependency-aware readiness control plane**. It sits between a human and their trackers. It:

1. **Connects** to trackers through [TrackerConnections](../domain/tracker-connection.md), normalizing tracker-specific state into [WorkItems](../domain/work-item.md) with canonical lifecycle states: `planned`, `active`, `completed`, `cancelled`, `unknown`.
2. **Builds** a typed [edge graph](../domain/edges.md) — contains, blocks, requires_gate, related_to — across all ingested WorkItems.
3. **Evaluates** [readiness](../domain/readiness-ranking.md#readiness) for every WorkItem based on edges, [gates](../domain/gates-and-evidence.md), [WorkLeases](../domain/work-lease.md), and [authority statuses](../domain/authority-statuses.md).
4. **Ranks** ready WorkItems through a configurable, deterministic, lexicographic [ranking pipeline](../domain/readiness-ranking.md#ranking).
5. **Outputs** the top result as [Recommended Next](../domain/recommended-next.md): the single best action for the human right now, with full context and rationale.

Each engine cycle produces an immutable, persisted [DecisionRecord](../domain/decision-record.md): the engine's decision at a point in time, capturing ranking rationale, gate outcomes, evidence chain, and authority status. The product layer persists the decision history. The human acts on the recommendation or overrides it. Every decision is recorded with provenance.

## Positioning

Work Frontier is:

- **A readiness control plane.** Its core function is evaluating what is ready and ranking what matters most. It does not manage workflows, enforce processes, or replace trackers.
- **Tracker-neutral.** It works with GitHub Issues, Linear, Jira, or any tracker that provides a sync contract. No tracker is architecturally privileged.
- **GitHub-first.** GitHub is the default tracker for setup and examples. The first production [TrackerConnection](../domain/tracker-connection.md) targets GitHub Issues. But "first" is a delivery priority, not an architectural commitment.
- **Production-ready from the start.** Every release meets the quality bar for real use.
- **Deterministic.** The ranking pipeline is lexicographic and auditable. No AI model influences ranking. Every computation can be traced.
- **Localized fail-closed.** When the engine cannot determine the right answer, it stops and asks. It never guesses, never silently skips, and never produces a partial result labeled as complete.

Work Frontier is not:

- A tracker replacement. It reads and proposes; trackers remain the system of record for item state.
- A project management tool. It does not define workflows, manage sprints, or produce reports.
- An AI coding assistant. It does not generate code, write PRs, or modify source files.
- A collaboration platform. It does not host comments, reactions, or threaded discussions.

Work Frontier supports:

- Portfolio and [Program](../domain/program.md) rollups through the typed containment DAG, serving builders, coordinators, executives, operators, and policy/tenant admins.
- Multiple user roles from solo maintainers to enterprise programs.

## Design Principles

**Deterministic authority.** When the engine and a tracker disagree, [authority statuses](../domain/authority-statuses.md) and the six-level [precedence ladder](../domain/authority-statuses.md#source-precedence) resolve the conflict. Conflicts are surfaced, never silently resolved. Authority statuses apply to [decisions](../domain/decision-record.md) and snapshots. Only an authoritative decision can claim a [WorkLease](../domain/work-lease.md).

**Localized fail-closed.** When the engine cannot determine the right answer, it fails closed and emits an [AttentionItem](../domain/attention-items.md). It never guesses.

**Safe projections vs approved authoritative mutations.** The engine can project ("if we did X, Y would likely happen"). These projections are labeled as such. Only the human can mutate ("do X"). Mutations are scoped, authorized, audited, time-bounded, and cannot weaken non-overridable safety constraints or completion policies. See [Safety Override Constraints](../domain/authority-statuses.md#safety-override-constraints).

**Bounded AI.** AI within the engine has narrow, well-scoped roles. AI may explain and suggest. AI may **not** interpret evidence authoritatively, count as evidence, generate canonical [AttentionItems](../domain/attention-items.md) without deterministic validation, change lifecycle state, bypass gates, contribute to ranking, or produce outputs without provenance. AI is a tool the engine calls, not an agent that acts.

**Primary ownership, secondary participation.** Every [WorkItem](../domain/work-item.md) has a primary owner responsible for it. Others can participate (add evidence, review) without owning. Primary ownership determines notification routing and default [WorkLease](../domain/work-lease.md) priority.

## Success Criteria

Work Frontier succeeds when a human opens the Control Room and, within 30 seconds, knows exactly what to do next and why. Not a list. Not a dashboard. One clear [Recommended Next](../domain/recommended-next.md) with context.

Secondary success: when the human disagrees with the recommendation and overrides it, the system captures the reason with provenance and the override takes effect on the next cycle, provided it is scoped, authorized, and does not weaken safety or completion policies.
