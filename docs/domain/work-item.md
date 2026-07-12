---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-12
---

# WorkItem

**WF-DOM-12**: A WorkItem is the base unit of work in the Work Frontier readiness control plane. Every unit of work, regardless of its tracker of origin, is normalized into a WorkItem. The engine operates on WorkItems.

## Structure

### Identity

| Field | Type | Description |
|-------|------|-------------|
| `item_id` | ULID | Globally unique, time-sortable. Generated at creation. Never changes. |
| `tracker_ids` | map[string, string] | Tracker-specific IDs keyed by tracker name. Populated by [TrackerConnection](tracker-connection.md). |
| `program_ids` | list[string] | [Program](program.md) memberships. A WorkItem can belong to zero or more Programs. |

### Content

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Short, human-readable description. Min 1, max 500 chars. |
| `description` | string or null | Detailed context. Sourced from tracker, user, or engine synthesis. |
| `work_type` | enum | `feature`, `bugfix`, `maintenance`, `investigation`, `decision`. |
| `labels` | list[string] | Free-form tags. Merged from tracker and user via [authority status](authority-statuses.md). |

### Authority State

Every field on a WorkItem carries an [authority status](authority-statuses.md) indicating how trustworthy its current value is. The engine evaluates authority on every cycle using the six-level [precedence ladder](authority-statuses.md#source-precedence).

Authority statuses apply to [decisions](decision-record.md) and snapshots. Only an [authoritative decision](authority-statuses.md#authority-statuses) can support claiming a [WorkLease](work-lease.md).

### Lifecycle State

| Field | Type | Description |
|-------|------|-------------|
| `lifecycle` | enum | `planned`, `active`, `completed`, `cancelled`, `unknown`. Tracker-native statuses normalize into these five canonical states. See [Lifecycle](lifecycle-and-completion.md). |
| `completion` | CompletionPolicy | Structured completion evaluation, evaluated independently of lifecycle. See [Completion](lifecycle-and-completion.md#completion). |

### Derived Projection State

| Field | Type | Description |
|-------|------|-------------|
| `derived_from_decision_id` | ULID or null | Immutable [DecisionRecord](decision-record.md) that produced this cache. Required whenever any derived value is exposed. |
| `readiness` | boolean or null | Cache only. Can this be worked on now? Authoritative truth lives in `derived_from_decision_id`. |
| `ranking` | RankingPosition or null | Cache only. Authoritative trace lives in `derived_from_decision_id`. |
| `fan_out` | int or null | Cache only. Authoritative graph revision is named by `derived_from_decision_id`. |

### Ownership

| Field | Type | Description |
|-------|------|-------------|
| `primary_owner` | string or null | The person responsible. Determines notification routing and default [WorkLease](work-lease.md) priority. Can override. |
| `participants` | list[string] | Contributors who can add evidence and review but **cannot** override lifecycle or safety fields. |

### Provenance

| Field | Type | Description |
|-------|------|-------------|
| `created_at` | ISO 8601 | When created in Work Frontier. |
| `updated_at` | ISO 8601 | Last modification time (any source). |
| `created_by` | string | Who created it: user ID, adapter name, or `"engine"`. |
| `source_authorities` | list[SourceAuthority] | Latest [authority status](authority-statuses.md) from each source. |

## Invariants

- INV-WI-01: `item_id` is generated once and never changes.
- INV-WI-02: A WorkItem has at most one primary owner.
- INV-WI-03: Participants cannot override lifecycle or safety fields.
- INV-WI-04: Every field's authority status is evaluated on every engine cycle.
- INV-WI-05: Lifecycle transitions follow the state machine in [State Machines](state-machines.md#workitem-lifecycle).
- INV-WI-06: The `completion` field is governed by a [Completion Policy](lifecycle-and-completion.md#completion), separate from lifecycle state.
- INV-WI-07: A non-null derived `readiness`, `ranking`, or `fan_out` value must
  carry a non-null `derived_from_decision_id` in the same workspace.
- INV-WI-08: A projection is stale and non-authoritative when its referenced
  DecisionRecord snapshot, graph revision, policy bundle, or engine version no
  longer matches current computation inputs.

## WorkItem and DecisionRecord

A [DecisionRecord](decision-record.md) is the immutable, persisted decision output that the engine produces. The WorkItem is the base entity that the engine reads. The DecisionRecord captures the engine's decision at a point in time: ranking rationale, gate outcomes, evidence chain, and authority status. Each engine cycle that changes the decision creates a new DecisionRecord. The product persists the decision history.

## Safe Projections vs Authoritative Mutations

The engine can project outcomes. Current read projections may cache derived
values only with `derived_from_decision_id`; hypothetical "if-then" scenarios
remain labeled and are not persisted as WorkItem truth.

Mutations are actual state changes:

| Source | Scope |
|--------|-------|
| Human (primary owner or admin) | Any field, **subject to override safety constraints**: scoped, authorized, audited, time-bounded, cannot weaken safety or completion policies. |
| Engine (deterministic) | Appends DecisionRecords and updates caches derived from those records only. |
| Tracker (via TrackerConnection) | Tracker-native fields. Merged via [precedence](authority-statuses.md#source-precedence) with provenance. |

A projection becomes a mutation only when a human confirms it, and only if the mutation passes [safety override constraints](authority-statuses.md#safety-override-constraints).
