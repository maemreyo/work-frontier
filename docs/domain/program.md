---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-13
---

# Program

**WF-DOM-13**: A Program is a logical grouping of related [WorkItems](work-item.md) that share context, receive status rollup, and can be acted on as a unit. Programs support typed containment DAGs, primary ownership with participation, and external blocker tracking. Programs are engine-level constructs, not tracker concepts.

## Purpose

Programs solve four problems:

1. **Status rollup.** Many WorkItems → single status view.
2. **Shared context.** Members share labels, priority signals, and notes.
3. **Coordinated actions.** Group-level operations: archive all completed, escalate all blocked.
4. **Containment structure.** Typed containment DAG allows Programs to nest within other Programs or external structures, supporting portfolio and program rollups.

## Structure

| Field | Type | Description |
|-------|------|-------------|
| `program_id` | ULID | Unique identifier. |
| `name` | string | Human-readable name. Min 1, max 200 chars. |
| `description` | string or null | Shared context. |
| `status` | enum | Computed rollup: `active`, `stalled`, `complete`, `archived`. |
| `member_ids` | list[string] | WorkItem IDs of members. |
| `contained_by` | list[string] | Parent Program IDs in the containment DAG. A Program can be contained by zero or more parent Programs. |
| `contains` | list[string] | Child Program or WorkItem IDs in the containment DAG. |
| `external_blockers` | list[ExternalBlocker] | Blockers from outside the Program's scope that affect its members. |
| `created_at` | ISO 8601 | When created. |
| `updated_at` | ISO 8601 | Last modification. |
| `created_by` | string | Who created it. |
| `labels` | list[string] | Shared labels inherited by members (low-weight ranking signal). |
| `primary_owner` | string or null | Responsible person. Determines notification routing and default [WorkLease](work-lease.md) priority. |
| `participants` | list[string] | Contributors without ownership. Can add evidence and review but cannot override lifecycle or safety fields. |

### ExternalBlocker

| Field | Type | Description |
|-------|------|-------------|
| `blocker_id` | ULID | Unique identifier. |
| `description` | string | What is blocking and why. |
| `source` | string | Where this blocker comes from (e.g., another Program, an external dependency, a team outside Work Frontier). |
| `affected_members` | list[string] | WorkItem IDs within this Program affected by the blocker. |
| `created_at` | ISO 8601 | When identified. |
| `resolved` | boolean | Whether the blocker has been resolved. |

## Containment DAG

Programs form a typed containment DAG, not a strict tree. A Program can be contained by multiple parent Programs, enabling portfolio-level rollups where multiple programs share a parent.

### Containment Properties

| Property | Rule |
|----------|------|
| Direction | Parent → Child (Program → Program or Program → WorkItem). |
| Typing | Each containment edge is typed by the relationship between parent and child. |
| Cycles | Must be a DAG. Containment cycles are rejected. |
| Multiple parents | A child Program can have multiple parent Programs. |
| Depth | No hard limit, but deep nesting is discouraged. Portfolio → Program → WorkItem is the typical depth. |

### Containment Rollup

Status rollup propagates upward through the containment DAG:

- A parent Program's status reflects the aggregate state of its children (direct and transitive).
- External blockers on a child propagate upward: if a child is blocked by an external dependency, the parent sees it.

## Membership

### Adding Members

A WorkItem joins a Program when:

- The user explicitly adds it.
- The tracker adapter maps a tracker relationship to Program membership.
- The engine creates the WorkItem as part of a Program operation.

### Removing Members

A WorkItem leaves a Program when:

- The user explicitly removes it.
- The WorkItem is cancelled.
- The Program is archived.

Removing a member does not affect the WorkItem's lifecycle, gates, or dependencies.

### Membership Invariants

- INV-PGM-01: A WorkItem can belong to zero or more Programs.
- INV-PGM-02: A Program must have at least one member. Empty → auto-archived.
- INV-PGM-03: Membership changes do not affect WorkItem lifecycle, gates, or dependencies.
- INV-PGM-04: Programs can be nested via the containment DAG. Cycles are rejected.

## Status Rollup

| Member states | Program status |
|--------------|---------------|
| All `completed` or `cancelled` | `complete` |
| All `cancelled` | `archived` |
| No `active`, at least one blocked | `stalled` |
| Otherwise | `active` |

### Rollup Metrics

| Metric | Source |
|--------|--------|
| Total members | Count of `member_ids`. |
| Active members | Count with `lifecycle` in (`planned`, `active`). |
| Blocked members | Count with blocked status (gates failed or hard dependencies incomplete). |
| Completed members | Count with `lifecycle` = `completed`. |
| Completion percentage | `completed_count / total_count * 100`. |
| Highest priority | Member with highest `priority`. |
| Oldest active | Member with oldest `created_at` among active. |

## Lifecycle

| State | Meaning |
|-------|---------|
| `active` | In use. Members being worked on. |
| `stalled` | No active members; at least one blocked. |
| `complete` | All members completed or cancelled. |
| `archived` | Retired. Members released. |

### Transitions

| From | To | Trigger |
|------|----|---------|
| `active` | `stalled` | Computed: no active members, at least one blocked. |
| `stalled` | `active` | Computed: at least one member becomes active. |
| `active`/`stalled` | `complete` | Computed: all members completed or cancelled. |
| `any` | `archived` | Human action (explicit archive). |

Full state machine in [State Machines](state-machines.md#program-lifecycle).

## Shared Context

Labels and priority on a Program are shared context, not copied data. Members inherit Program labels as low-weight ranking signals. Member-specific values override when they conflict.

## Program and Authority

The Program does not confer authority over its members. Group-level priority does not change member lifecycle state.

Group-level actions (archive all completed, escalate all blocked) require human confirmation and are subject to [safety override constraints](authority-statuses.md#safety-override-constraints):

- **Scoped** to the specific Program and its members.
- **Authorized** — only the Program's primary owner or an admin can initiate.
- **Audited** — logged with who, when, what action, what reason.
- **Time-bounded** — group-level overrides expire per configuration.
- **Non-weakening** — cannot bypass safety gates or completion policies on any member.

The engine proposes group-level actions via [AttentionItems](attention-items.md); the human approves or rejects them.
