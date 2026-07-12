---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-04
---

# Lifecycle and Completion

**WF-DOM-04**: Work Frontier separates two concepts that trackers conflate: **lifecycle** (the normalized state a [WorkItem](work-item.md) occupies) and **completion** (a separate policy result evaluating whether the WorkItem's intent is fulfilled). Lifecycle states are derived by normalizing tracker-native statuses into five canonical states. Completion is governed by **completion policies**, not a simple boolean. Overrides cannot weaken completion policies.

## Lifecycle

The lifecycle is the normalized set of states a WorkItem can occupy. Tracker-native statuses map into these five canonical states via the [TrackerConnection](tracker-connection.md).

### Lifecycle States

| State | Meaning | Typical tracker sources |
|-------|---------|------------------------|
| `planned` | Work is planned or queued. Not yet started. | `open`, `todo`, `backlog`, `new`. |
| `active` | Work is in progress or being coordinated. | `in_progress`, `in_review`, `blocked`, `claimed`, `doing`. |
| `completed` | Work is done. Terminal state. | `done`, `closed`, `resolved`, `shipped`. |
| `cancelled` | Work was abandoned or won't be done. Terminal state. | `cancelled`, `wontfix`, `invalid`, `duplicate`. |
| `unknown` | Tracker state cannot be determined. | Tracker unreachable, unmapped status, ambiguous state. |

### Normalization Rules

TrackerConnection maps tracker-native statuses to canonical lifecycle states:

| Tracker status | Canonical lifecycle | Condition |
|---------------|-------------------|-----------|
| `open`, `todo`, `backlog`, `new` | `planned` | Default for unstarted work. |
| `in_progress`, `doing`, `claimed` | `active` | Work is happening. |
| `in_review`, `blocked`, `waiting` | `active` | Work is in progress but waiting. These are coordination states, not distinct lifecycle states. |
| `done`, `closed`, `resolved`, `shipped` | `completed` | Work appears finished. |
| `cancelled`, `wontfix`, `invalid`, `duplicate` | `cancelled` | Work abandoned. |
| Unmapped or ambiguous | `unknown` | TrackerConnection cannot determine state. |

The `unknown` state is a valid, honest answer. Work Frontier never guesses at lifecycle when the tracker is unclear.

### Transition Rules

| From | To | Trigger |
|------|----|---------|
| `planned` | `active` | Claimant acquires a [WorkLease](work-lease.md), or tracker sync shows work started. |
| `active` | `completed` | Completion policy satisfied and confirmed. |
| `active` | `cancelled` | Human explicitly cancels, or tracker sync shows cancellation. |
| `planned` | `cancelled` | Human explicitly cancels, or tracker sync shows cancellation. |
| `unknown` | any | Tracker reconnects and provides clear state. |
| `completed` | `unknown` | Tracker state becomes ambiguous (rare, signals drift). |

### Forbidden Transitions

- `completed` → `planned`, `completed` → `active`
- `cancelled` → `planned`, `cancelled` → `active`
- `planned` → `completed` (must go through `active` first, except tracker sync)

The full state machine is in [State Machines](state-machines.md#workitem-lifecycle).

## Completion

Completion is a separate policy result, evaluated independently of lifecycle state. A WorkItem can be in `active` lifecycle while completion evaluation shows `incomplete` or even `closed_unverified`.

### What Completion Is

| Concept | Description |
|---------|-------------|
| Completion | A structured evaluation: does the WorkItem's intent match the satisfaction criteria defined by its completion policy? |
| Lifecycle | Which normalized tracker state the WorkItem occupies. |
| Relationship | Lifecycle and completion are independent axes. A tracker can close an item (lifecycle `completed`) before completion policy is satisfied (`closed_unverified`). Conversely, completion policy can be satisfied while the tracker still shows `active` (`tracker_drift`). |

### Completion Policy Results

| Result | Meaning |
|--------|---------|
| `satisfied` | Completion policy fully met. |
| `incomplete` | Policy conditions not yet met. |
| `closed_unverified` | Tracker marked as closed/done, but completion policy has not been satisfied. The tracker closed the item without evidence. |
| `pending_review` | Policy conditions appear met but await human confirmation. |
| `unknown` | Cannot evaluate (missing data, unreachable source). |

### Completion Policies

| Policy | Definition | When to use |
|--------|-----------|-------------|
| `all_gates_passed` | All [Gates](gates-and-evidence.md#gate) are `passed` or `waived`. | Default for most WorkItems. |
| `all_dependencies_complete` | All [`blocks` dependencies](edges.md#blocks) are `completed`. | For coordination-only WorkItems. |
| `all_children_complete` | All child WorkItems (via [`contains` edges](edges.md#contains)) are `completed`. | For parent WorkItems. |
| `evidence_declared` | At least one [EvidenceRecord](gates-and-evidence.md#evidencerecord) of type `declared` exists. | For human-confirmed completion. |
| `composite` | Combination of the above with AND/OR logic. | For complex completion requirements. |
| `manual_only` | Only human confirmation can mark complete. | For safety-critical or ambiguous work. |

### Completion and Overrides

Overrides **cannot weaken completion policies**:

- An override that would set lifecycle to `completed` while the assigned completion policy has not been satisfied is rejected.
- The engine lists the unsatisfied policy conditions in the rejection message.
- Safety-critical completion policies (`manual_only` on safety-gated items) are **non-overridable**.

### Completion vs Tracker Closure

| Scenario | Tracker says | Lifecycle | Completion | Meaning |
|----------|-------------|-----------|------------|---------|
| Tracker closed, work verified | "closed" | `completed` | `satisfied` | Consistent. |
| Tracker closed, not verified | "closed" | `completed` | `closed_unverified` | Tracker closed without evidence. Emit `authority_downgraded` AttentionItem. |
| Tracker open, work done | "open" | `planned`/`active` | `satisfied` | Tracker not updated. Emit `connection_degraded` AttentionItem. |
| Tracker open, not done | "open" | `planned` | `incomplete` | Consistent. |

### Completion Authority

| Who | Can set lifecycle to `completed`? | Can set completion? |
|-----|-----|-----|
| Engine (automatic) | Yes, when all applicable completion gates pass and the completion policy is satisfied. | Yes, as a computed property per policy. |
| Human (explicit) | Yes only when the completion policy is satisfied and the transition passes [safety constraints](authority-statuses.md#safety-override-constraints). | May attest evidence or approve a pending review; cannot bypass the assigned completion policy. |
| Tracker (sync) | Maps to lifecycle via TrackerConnection normalization. | Maps to a completion signal, not directly to completion. |

### Completion Invariants

- INV-COMP-01: Completion is evaluated per the WorkItem's assigned completion policy.
- INV-COMP-02: The engine never auto-completes a WorkItem with `manual_only` policy.
- INV-COMP-03: Human override of completion is tracked with provenance and subject to safety constraints.
- INV-COMP-04: Completion evaluation is authority-aware: requires `authoritative` or `provisional` data for safety-critical checks.
- INV-COMP-05: Completion and lifecycle are independent axes. One can change without the other.

## Lifecycle and [Authority Statuses](authority-statuses.md)

Lifecycle transitions are driven by the merged state from all sources per the six-level [precedence ladder](authority-statuses.md#source-precedence). When a user overrides the lifecycle state, that override takes precedence, subject to [safety override constraints](authority-statuses.md#safety-override-constraints).

The engine re-evaluates lifecycle on every cycle. If a dependency completes, a WorkItem may transition from one state to another. If a Gate fails, completion policy may change.
