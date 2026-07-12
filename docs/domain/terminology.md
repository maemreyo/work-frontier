---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-01
---

# Terminology

**WF-DOM-01**: Work Frontier uses a precise, bounded vocabulary. Every term in this glossary is the single source of its definition. Other docs reference these definitions; they do not redefine them.

## Core Entities

### Program

A logical grouping of related [WorkItems](#workitem) that share context, receive status rollup, and can be acted on as a unit. Programs form a typed containment DAG with primary ownership and participation. They track external blockers. Programs are engine-level constructs, not tracker concepts. See [Program](program.md).

### WorkItem

The base unit of work in Work Frontier. Every unit of work, regardless of tracker of origin, is normalized into a WorkItem. The engine operates on WorkItems. See [WorkItem](work-item.md).

### DecisionRecord

An immutable, persisted decision output produced by the [Frontier Engine](../product/overview.md#frontier-engine). Each cycle the engine takes a snapshot of current state plus policies and produces a DecisionRecord. DecisionRecords are never recomputed in place; each engine cycle that produces a different result creates a new DecisionRecord. The product layer persists the decision history. See [DecisionRecord](decision-record.md).

### Recommended Next

The top-ranked [DecisionRecord](#decisionrecord) from the current [Ranking Pipeline](#ranking-pipeline), presented with full context and rationale. The engine's answer to "what should I do next?" See [Recommended Next](recommended-next.md).

### Gate

A checkpoint that a [WorkItem](#workitem) must pass before advancing past a specific [lifecycle](#lifecycle) transition. See [Gate](gates-and-evidence.md#gate).

### EvidenceRecord

Proof that a [Gate](#gate) condition has been met. Typed, revision-bound, and signed or attested where required. AI output never counts as evidence. Every gate pass must be backed by an EvidenceRecord. See [EvidenceRecord](gates-and-evidence.md#evidencerecord).

### WorkLease

A coordination lease on a [WorkItem](#workitem) held by a claimant (human, agent, or automation). WorkLeases are coordination mechanisms, not mutation locks. They record the decision_id, source revisions, policy hash, and carry TTL/heartbeat/suspended semantics. WorkLeases are never held by the engine or a tracker. See [WorkLease](work-lease.md).

### AttentionItem

A signal emitted by the engine when it detects a situation requiring human judgment. Not a WorkItem; a signal. AttentionItem categories follow a fixed set: `decision_changed`, `authority_downgraded`, `claim_at_risk`, `approval_required`, `evidence_required`, `graph_conflict`, `connection_degraded`, `certification_ready`, `security_action`, `capacity_action`. AI may suggest attention items but they are only emitted after deterministic validation. See [AttentionItem](attention-items.md).

### TrackerConnection

A live link between Work Frontier and an external tracker (GitHub, Linear, Jira, etc.). The only point where tracker-specific knowledge enters the system. See [TrackerConnection](tracker-connection.md).

## Edge Types

### contains

A hierarchical parent-child relationship. The parent owns the child's scope. See [Edges](edges.md#contains).

### blocks

A directional dependency: "A blocks B" means "B cannot complete until A completes." Subtypes: `hard` (cannot start) and `soft` (can start, cannot complete). See [Edges](edges.md#blocks).

### requires_gate

A [Gate](#gate) must pass before the dependent [WorkItem](#workitem) can advance past a specific lifecycle transition. See [Edges](edges.md#requires-gate).

### related_to

A loose association with no lifecycle or readiness impact. Informational only. See [Edges](edges.md#related-to).

## Authority Concepts

### Authority Status

The trust level of a data point. Five statuses: `authoritative`, `provisional`, `stale`, `conflicted`, `unavailable`. Authority statuses apply to [decisions](#decisionrecord) and [snapshots](../product/overview.md). Only an authoritative decision can claim a [WorkLease](#worklease). See [Authority Statuses](authority-statuses.md#authority-statuses).

### Source Precedence

The six-level ladder that resolves conflicting data: human override > configured policy > native tracker > structured metadata > parsed Markdown > inference. Conflicts are surfaced, never silently resolved. See [Authority Statuses](authority-statuses.md#source-precedence).

### Provenance

The record of who provided a value, when, from what source level, and why. Every value on a WorkItem carries provenance. See [Authority Statuses](authority-statuses.md#provenance).

### Conflict

When multiple sources provide different values for the same field. Conflicts are tracked and surfaced, not silently resolved. See [Authority Statuses](authority-statuses.md#conflict-surfacing).

### Safety Override Constraint

Overrides are scoped, authorized, audited, time-bounded, and cannot weaken non-overridable safety constraints or completion policies. See [Authority Statuses](authority-statuses.md#safety-override-constraints).

## Ranking Concepts

### Readiness

A computed boolean: can this [WorkItem](#workitem) be worked on right now? Requires all hard blockers complete, no active leases by others, all gates passed, and safe authority status. See [Readiness](readiness-ranking.md#readiness).

### Ranking Pipeline

A configurable, deterministic, lexicographic sequence of comparators that sorts ready WorkItems. Default order: program priority, work class, downstream unlock count desc, age desc, stable ID. No AI influence. The top item is [Recommended Next](#recommended-next). See [Ranking](readiness-ranking.md#ranking).

### Comparator

A single sorting function in the [ranking pipeline](#ranking-pipeline). Compares two WorkItems and returns which ranks higher. Deterministic and auditable. See [Ranking](readiness-ranking.md#comparator-specification).

## Lifecycle Concepts

### Lifecycle

The normalized set of states a [WorkItem](#workitem) can occupy, derived from tracker states: `planned`, `active`, `completed`, `cancelled`, `unknown`. Trackers map their native statuses into these five canonical states. See [Lifecycle](lifecycle-and-completion.md#lifecycle).

### Completion

A separate policy result, evaluated independently of lifecycle state. A WorkItem can be in `active` lifecycle while completion is `closed_unverified` (tracker closed it but completion policy not satisfied). Completion is governed by **completion policies**, not a simple boolean. Overrides cannot weaken completion policies. See [Completion](lifecycle-and-completion.md#completion).

## Ownership Concepts

### Primary Owner

The person or role responsible for a [WorkItem](#workitem). Determines notification routing and default [WorkLease](#worklease) priority. Primary owners can override; participants cannot. See [WorkItem](work-item.md#ownership).

### Participant

A person contributing to a [WorkItem](#workitem) without owning it. Participants can add evidence and review but cannot change lifecycle state or override safety fields. See [WorkItem](work-item.md#ownership).

### Override

A human-authored, scoped, authorized, audited, time-bounded state change. Overrides take [precedence](#source-precedence) over other sources but cannot weaken non-overridable safety constraints or completion policies. See [Authority Statuses](authority-statuses.md#safety-override-constraints).

## AI Bounds

AI within Work Frontier has bounded scope. AI may:

- Explain and suggest.
- Contribute to attention item proposals (after deterministic validation).

AI may **not**:

- Interpret evidence authoritatively.
- Count as evidence. AI output never qualifies as an [EvidenceRecord](#evidencerecord).
- Generate canonical AttentionItems without deterministic validation.
- Change lifecycle state.
- Bypass gates.
- Contribute to ranking.
- Produce outputs without provenance.

## Conventions

- **Tracker-neutral language.** The domain model uses "state," "status," and "transition" rather than tracker-specific terms. Tracker-specific mappings happen at the [TrackerConnection](#trackerconnection) layer.
- **No false precision.** When the engine is uncertain, it says so. "Readiness: unknown" is a valid state.
- **One definition per term.** This glossary is canonical. Other usages link here.
