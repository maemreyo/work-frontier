---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-PROD-01, WF-PROD-02, WF-PROD-03
---

# Product Overview

**WF-PROD-03**: Work Frontier has three layers: the **Frontier Engine** (pure snapshot+policy to DecisionRecord-set computation), the **Product** (persistence, ingestion, and state management), and the **Frontier Control Room** (human interface). This doc shows how they connect.

## Architecture at a Glance

```
  Tracker (GitHub, Linear, Jira, ...)
       │
       │  sync contract
       ▼
  ┌──────────────────────┐
  │  TrackerConnection    │  ← normalizes tracker state into WorkItem
  │  (adapter layer)      │    snapshots with authority status
  └──────────┬───────────┘
             │
             ▼
  ┌───────────────────────────────────────────────────┐
  │  Product (Persistence Layer)                       │
  │                                                    │
  │  Persists: WorkItem snapshots, current state,      │
  │  decision history (DecisionRecords), edges,         │
  │  gates, evidence, leases, Programs                 │
  │                                                    │
  │  Manages: TrackerConnections, edge graph,          │
  │  gate state, completion evaluation, rollups         │
  └──────────┬────────────────────────────────────────┘
             │  snapshot + policies
             ▼
  ┌───────────────────────────────────────────────────┐
  │              Frontier Engine                        │
  │                                                    │
   │  Pure computation: snapshot + policy → DecisionRecord set
  │  Stateless. No persistence. No side effects.       │
  │  Each cycle: read snapshot, apply policies,        │
   │  produce immutable DecisionRecords.                │
  └──────────┬────────────────────────────────────────┘
             │  DecisionRecord set
             ▼
  ┌───────────────────────────────────────────────────┐
  │  Product (Persistence Layer)                       │
  │                                                    │
   │  Persists DecisionRecords to decision history.     │
  │  Updates current state. Emits AttentionItems.      │
  └──────────┬────────────────────────────────────────┘
             │
             ▼
  ┌──────────────────────────────┐
  │  Frontier Control Room        │  ← human interface: sees Recommended Next,
  │                               │    overrides, context, evidence, authority
  └──────────────────────────────┘
```

## Frontier Engine

The Frontier Engine is a pure, stateless computation. It takes a snapshot of current state plus a versioned policy bundle and produces one immutable [DecisionRecord](../domain/decision-record.md) per evaluated WorkItem as a single decision set. The product layer persists that set atomically.

**Input:** A snapshot containing WorkItem state, edges, gates, leases, authority statuses, and configuration policies.

**Output:** A decision set whose per-WorkItem DecisionRecords capture ranking rationale, gate outcomes, evidence chain, authority map, and dependency context at a point in time.

The engine does not:
- Persist state.
- Maintain the edge graph.
- Evaluate gates over time.
- Hold WorkLeases.
- Call external services.

The engine is re-invoked on every cycle. Between cycles, the product layer manages all state.

## Product (Persistence Layer)

The product layer manages everything the engine does not:

1. **Persists WorkItem snapshots** with [authority status](../domain/authority-statuses.md) from [TrackerConnections](../domain/tracker-connection.md).
2. **Persists current state:** edge graph, gate states, WorkItem lifecycle, completion status, WorkLeases, Programs.
3. **Persists decision history:** append-only list of [DecisionRecords](../domain/decision-record.md) per WorkItem.
4. **Manages TrackerConnections:** sync inbound snapshots, translate outbound proposals.
5. **Evaluates completion policies** using persisted state.
6. **Normalizes tracker statuses** into canonical [lifecycle](../domain/lifecycle-and-completion.md) states.
7. **Computes Program rollups** including portfolio-level status through the containment DAG.
8. **Emits [AttentionItems](../domain/attention-items.md)** when deterministic conditions are met.
9. **Serves the Control Room** with projections of current state and decision history.

## TrackerConnections

[TrackerConnections](../domain/tracker-connection.md) bridge tracker-specific APIs and the engine's normalized model. Each connection:

- Pulls (or receives webhooks for) state changes from one translator tracker-specific fields, statuses, and relationships into WorkItem snapshots with authority status.
- Normalizes tracker-native statuses into the five canonical lifecycle states: `planned`, `active`, `completed`, `cancelled`, `unknown`.
- Pushes engine proposals (labels, comments, status suggestions) back to the tracker when the human confirms.

TrackerConnections are the only place where tracker-specific knowledge lives. The engine never imports tracker types or calls tracker APIs.

See [Integrations](../integrations/) for connection contract details.

## Frontier Control Room

The Control Room is the human-facing interface. It shows:

- **[Recommended Next](../domain/recommended-next.md):** the top-ranked WorkItem with context, evidence, and rationale from the latest [DecisionRecord](../domain/decision-record.md).
- **Ready Next:** the full ranked list of ready WorkItems, with the ability to filter, inspect, and override.
- **[Edge graph view](../domain/edges.md):** a visualization of the contains/blocks/requires_gate/related_to structure.
- **[AttentionItems](../domain/attention-items.md):** things the engine flagged for human review.
- **[WorkLeases](../domain/work-lease.md):** who holds coordination leases on what, and when they expire.
- **[Authority status](../domain/authority-statuses.md):** for each WorkItem, the trust level of each field.
- **Decision history:** the append-only list of DecisionRecords per WorkItem, with diffs between consecutive decisions.
- **Portfolio/Program rollups:** aggregate status across Programs and their containment DAG.

The Control Room is not a tracker. It is a projection of persisted product state. Trackers remain authoritative for tracker-native facts; versioned policies and authorized overrides govern their own fields; immutable DecisionRecords record what Work Frontier decided from a specific snapshot.

See [UX](../ux/) for interaction design details.

## Data Flow

1. [TrackerConnections](../domain/tracker-connection.md) sync state from trackers into WorkItem snapshots with [authority status](../domain/authority-statuses.md). Status fields normalize via [status mapping](../domain/tracker-connection.md#status-mapping) into `planned`, `active`, `completed`, `cancelled`, or `unknown`.
2. The product layer persists the snapshot and updates current state: merges snapshots per the six-level [precedence ladder](../domain/authority-statuses.md#source-precedence), tracking provenance and surfacing conflicts.
3. The product layer re-evaluates the [edge graph](../domain/edges.md): contains, blocks, requires_gate, related_to.
4. The product layer evaluates [Gates](../domain/gates-and-evidence.md) and [EvidenceRecords](../domain/gates-and-evidence.md#evidencerecord).
5. The product layer evaluates [completion policies](../domain/lifecycle-and-completion.md#completion) for each WorkItem.
6. The product layer computes [readiness](../domain/readiness-ranking.md#readiness) for every WorkItem.
7. The product layer prepares a snapshot and passes it to the **Frontier Engine** along with configuration policies.
8. The engine runs the [ranking pipeline](../domain/readiness-ranking.md#ranking) on all ready WorkItems and produces an immutable [DecisionRecord](../domain/decision-record.md) for each evaluated WorkItem.
9. The product layer atomically persists the decision set to decision history.
10. The product layer emits [Recommended Next](../domain/recommended-next.md) and any new [AttentionItems](../domain/attention-items.md).
11. The Control Room renders the new state.
12. The human acts: accept the recommendation, override it with a reason, or address an AttentionItem.
13. The override is recorded with [human override](../domain/authority-statuses.md#source-precedence) precedence. Overrides are scoped, authorized, audited, time-bounded, and cannot weaken safety or completion policies.

## Key Invariants

- The engine never mutates tracker state directly. It proposes; the human confirms.
- The engine is stateless. All state lives in the product layer.
- Every value carries [authority status](../domain/authority-statuses.md): authoritative, provisional, stale, conflicted, or unavailable. Authority statuses apply to decisions and snapshots.
- Only an authoritative decision can support claiming a [WorkLease](../domain/work-lease.md).
- The [ranking pipeline](../domain/readiness-ranking.md#ranking) is deterministic and AI-free. No model influences ranking.
- The engine is tracker-neutral. No tracker-specific logic leaks past the TrackerConnection boundary.
- [DecisionRecords](../domain/decision-record.md) are immutable and append-only. The decision history is an audit trail.
- [Safe projections vs approved authoritative mutations](../domain/work-item.md#safe-projections-vs-authoritative-mutations): projections are labeled; mutations require human confirmation, are scoped, authorized, audited, time-bounded, and cannot weaken non-overridable safety or completion policies.
- The product is not a tracker but supports portfolio and [Program](../domain/program.md) rollups through the containment DAG.
