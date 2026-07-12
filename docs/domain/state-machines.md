---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-11
---

# State Machines

**WF-DOM-11**: Formal state machine definitions for all entities in Work Frontier. Every transition is deterministic, auditable, and constrained by linked domain docs.

## WorkItem Lifecycle

States: `planned`, `active`, `completed`, `cancelled`, `unknown`

```mermaid
stateDiagram-v2
    [*] --> planned

    planned --> active : WorkLease acquired or tracker shows work started
    active --> completed : Completion policy satisfied + confirmed
    active --> cancelled : Human cancels or tracker shows cancellation
    planned --> cancelled : Human cancels or tracker shows cancellation

    unknown --> planned : Tracker reconnects with clear state
    unknown --> active : Tracker reconnects with clear state
    unknown --> completed : Tracker reconnects with clear state
    unknown --> cancelled : Tracker reconnects with clear state

    completed --> unknown : Tracker state becomes ambiguous
```

### Transition Rules

| From | To | Trigger | Conditions |
|------|----|---------|-----------|
| `planned` | `active` | [WorkLease](work-lease.md) acquired or tracker sync | Entry gates pass and no active exclusive lease is held by another claimant. |
| `active` | `completed` | [Completion policy](lifecycle-and-completion.md#completion) satisfied | All Gates pass, EvidenceRecords accepted, human confirms. |
| `active` | `cancelled` | Human cancels or tracker sync | Explicit action. Subject to [safety constraints](authority-statuses.md#safety-override-constraints). |
| `planned` | `cancelled` | Human cancels or tracker sync | Explicit action. |
| `unknown` | any | Tracker reconnects | Tracker provides clear state via [TrackerConnection](tracker-connection.md). |
| `completed` | `unknown` | Tracker state ambiguous | Rare. Signals tracker drift. |

### Forbidden Transitions

- `completed` → `planned`, `completed` → `active`
- `cancelled` → `planned`, `cancelled` → `active`
- `planned` → `completed` (must go through `active`, except tracker sync showing direct completion)

## Program Lifecycle

States: `active`, `stalled`, `complete`, `archived`

```mermaid
stateDiagram-v2
    [*] --> active

    active --> stalled : No active members + at least one blocked
    stalled --> active : At least one member becomes active

    active --> complete : All members completed or cancelled
    stalled --> complete : All members completed or cancelled

    complete --> archived : Human archives
    active --> archived : Human archives
    stalled --> archived : Human archives
```

### Rollup Logic

```
if all members in (completed, cancelled):
    status = complete
elif no members in active and any member blocked:
    status = stalled
else:
    status = active
```

Empty Program → `archived` + `capacity_action` [AttentionItem](attention-items.md).

## WorkLease Lifecycle

States: `active`, `renewed`, `expired`, `released`, `broken`

```mermaid
stateDiagram-v2
    [*] --> active : Lease acquired

    active --> renewed : Renewed before TTL
    renewed --> active : Renewal confirmed

    active --> expired : TTL exceeded
    renewed --> expired : TTL exceeded after renewal

    active --> released : Voluntary release
    renewed --> released : Voluntary release

    active --> broken : Higher-priority claimant or policy change
    renewed --> broken : Higher-priority claimant or policy change
```

## Gate Lifecycle

States: `pending`, `passed`, `failed`, `waived`

```mermaid
stateDiagram-v2
    [*] --> pending : Gate defined

    pending --> passed : Condition met + valid [EvidenceRecord](gates-and-evidence.md#evidencerecord)
    pending --> failed : Condition evaluated and not met

    failed --> pending : New evidence or condition changed
    failed --> passed : Condition met + valid evidence

    passed --> pending : EvidenceRecord expires

    pending --> waived : Human waives (non-safety only)
    failed --> waived : Human waives (non-safety only)
```

### Forbidden Transitions

- `passed` → `failed`: Goes through `pending`.
- `waived` → anything: Waived is terminal.

## AttentionItem Lifecycle

States: `open`, `acknowledged`, `resolved`

```mermaid
stateDiagram-v2
    [*] --> open : Engine emits (deterministic basis required)

    open --> acknowledged : Human views
    acknowledged --> resolved : Human resolves
    open --> resolved : Human resolves or auto-resolves
```

Every AttentionItem must have a `deterministic_basis`. AI may suggest items but they are only emitted after deterministic validation.

### Severity

Severity is assigned at emission time based on [category and context](attention-items.md#categories). There is no age-based severity escalation. Severity can be reassessed if the underlying condition changes, driven by the deterministic basis, not by age.

## Authority Status Lifecycle

States: `authoritative`, `provisional`, `stale`, `conflicted`, `unavailable`

```mermaid
stateDiagram-v2
    [*] --> unavailable : No source data

    unavailable --> provisional : Source provides value
    provisional --> authoritative : Source confirmed, no conflicts
    authoritative --> stale : Source exceeds staleness threshold
    stale --> authoritative : Fresh sync received
    stale --> unavailable : Source disconnects

    provisional --> conflicted : Second source disagrees
    authoritative --> conflicted : Second source disagrees
    conflicted --> authoritative : Conflict resolved, sources agree
    conflicted --> provisional : One source withdrawn
```

## Cross-Entity Interactions

| Event | Affected entities | Effect |
|-------|------------------|--------|
| WorkLease acquired on `planned` | WorkItem, WorkLease | `planned` → `active`. |
| WorkLease expires | WorkItem, WorkLease | Lease: `active` → `expired`. Lifecycle: `active` → `planned` (if no work logged). |
| Completion gate passes on `active` item | WorkItem, Gate | Gate: `pending`/`failed` → `passed`. If the completion policy is satisfied and required confirmation exists: `active` → `completed`. |
| `blocks` dependency completes | Downstream WorkItem | Readiness re-evaluates. |
| All Program members `completed` | Program | `active`/`stalled` → `complete`. |
| Safety Gate fails | WorkItem | `security_action` AttentionItem. An entry safety gate blocks readiness; later-phase safety gates block their corresponding outcomes. |
| User override on lifecycle | WorkItem | Lifecycle set to user's value, subject to [safety override constraints](authority-statuses.md#safety-override-constraints). [Precedence](authority-statuses.md#source-precedence): human override > configured policy > native tracker > structured metadata > parsed Markdown > inference. |

These interactions are deterministic. Given the same inputs, the engine produces the same transitions every cycle.
