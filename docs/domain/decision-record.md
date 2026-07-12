---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-07
---

# DecisionRecord

**WF-DOM-07**: A DecisionRecord is the immutable, persisted, reproducible decision envelope produced by the [Frontier Engine](../product/overview.md#frontier-engine). Each engine cycle takes an identified normalized snapshot plus a versioned policy bundle and produces one DecisionRecord per evaluated WorkItem. DecisionRecords are never recomputed in place; later cycles append new records. The product layer persists the decision history and may cache a derived projection only when it names this record.

## What a DecisionRecord Is

A DecisionRecord captures everything the engine knew and decided at a point in time:

- The exact workspace, Program context, normalized snapshot, graph revision,
  policy bundle, ranking pipeline, engine build, normalization profile, and
  source-revision set used to decide.
- Which [WorkItem](work-item.md) this decision concerns.
- The ranking position and full comparator trace.
- The [Gate](gates-and-evidence.md#gate) outcomes and pending evidence.
- The [EvidenceRecord](gates-and-evidence.md#evidencerecord) chain.
- The [authority status](authority-statuses.md) of every field used in the decision.
- The [AttentionItems](attention-items.md) active at decision time.
- The [WorkLease](work-lease.md) state at decision time.
- The dependency context: fan-out, blockers, gate dependencies.

## What a DecisionRecord Is Not

- **Not an enriched WorkItem.** A DecisionRecord does not extend or inherit from WorkItem. It is a separate, immutable, persisted entity that references a WorkItem by `item_id`.
- **Not recomputed in place.** Once persisted, a DecisionRecord never changes. The engine may produce a new DecisionRecord on a later cycle; the old one remains as history.
- **Not a projection.** A DecisionRecord is durable. It persists in the decision history. Projections are labeled "if-then" scenarios and are not stored.

## Structure

### Identity

| Field | Type | Description |
|-------|------|-------------|
| `decision_id` | ULID | Unique identifier for this decision. Immutable. |
| `workspace_id` | ULID | Mandatory data-isolation scope. |
| `program_id` | ULID or null | Program context used for priority/rollup, if any. |
| `item_id` | string | The [WorkItem](work-item.md) this decision concerns. |
| `computed_at` | ISO 8601 | When this decision was produced. |
| `causation_id` | ULID or UUID | Direct inbox, mutation, job, or revalidation event that caused computation. |
| `correlation_id` | ULID or UUID | End-to-end operation/trace identity. |

### Reproducibility Envelope

| Field | Type | Description |
|-------|------|-------------|
| `normalized_snapshot_id` | ULID | Immutable normalized input bundle ID. |
| `normalized_snapshot_hash` | SHA-256 | Canonical hash of all normalized fields consumed by the engine. |
| `source_revision_set` | map[source_id, revision] | Exact tracker/user/policy source revisions included in that snapshot. |
| `graph_revision` | ULID or monotonic version | Identifies the typed edge graph consumed. |
| `policy_bundle_id` | ULID | Versioned policy bundle identity. |
| `policy_bundle_hash` | SHA-256 | Canonical hash of policy AST/configuration. |
| `ranking_pipeline_hash` | SHA-256 | Canonical hash of ordered comparator configuration and parameters. |
| `engine_version` | string | Immutable engine build/algorithm version. |
| `normalization_profile_version` | string | Connection profile/version used to normalize source data. |

### Content Snapshot

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | WorkItem title at decision time. |
| `description` | string or null | WorkItem description at decision time. |
| `work_type` | enum | WorkItem type at decision time. |
| `labels` | list[string] | Labels at decision time. |
| `lifecycle` | enum | Lifecycle state at decision time. |
| `completion` | CompletionPolicy | Completion evaluation at decision time. |

### Ranking Context

| Field | Type | Description |
|-------|------|-------------|
| `ranking_position` | int | Position in the current ranking (1 = Recommended Next). |
| `ranking_rationale` | list[ComparatorTrace] | Canonical per-comparator inputs, values, outcome, and tie-break chain. |
| `ready` | boolean | Whether this WorkItem was ready at decision time. |

### ComparatorTrace

| Field | Type | Description |
|-------|------|-------------|
| `comparator` | string | Name (e.g., `program_priority`, `work_class`, `downstream_unlock_count_desc`). |
| `input` | canonical JSON | The item-local input/value consumed by this comparator. |
| `outcome` | enum | `selected`, `equal`, or `deferred_to_next`. |
| `tie_break_position` | int or null | Position in the deterministic tie-break chain when needed. |
| `detail` | string | Human-readable explanation derived from canonical inputs. |

### Gate Summary

| Field | Type | Description |
|-------|------|-------------|
| `gates` | list[GateState] | Current state of each [Gate](gates-and-evidence.md#gate). |
| `gates_passed` | int | Count of `passed` or `waived` gates. |
| `gates_total` | int | Total gates defined. |
| `gates_pending_evidence` | list[string] | Gate IDs awaiting [EvidenceRecord](gates-and-evidence.md#evidencerecord). |

### Dependency Context

| Field | Type | Description |
|-------|------|-------------|
| `blocks_count` | int | Fan-out (items this one blocks). |
| `blocked_by` | list[string] | IDs of incomplete hard blockers. |
| `gate_dependencies` | list[string] | Gate IDs whose failure blocks this item. |

### Attention Context

| Field | Type | Description |
|-------|------|-------------|
| `active_attention_items` | list[AttentionItem] | Items needing human action at decision time. |

### Authority Map

| Field | Type | Description |
|-------|------|-------------|
| `field_authority` | map[string, AuthorityStatus] | Authority status for every field used in ranking. |

## Decision History

The product layer persists an append-only decision history per WorkItem. The history enables:

- **Audit trail.** Every decision the engine made, with full rationale.
- **Diffing.** Comparing consecutive DecisionRecords to understand what changed and why.
- **Override tracking.** When a human overrides a decision, the override is recorded with provenance and the next DecisionRecord reflects it.

| Operation | Rule |
|-----------|------|
| Append | Only the engine or a human override can create a new DecisionRecord. |
| Read | Any authorized actor can read the decision history. |
| Delete | DecisionRecords are never edited or selectively removed. Governed tenant deletion, retention expiry, or legal erasure removes the containing record set and leaves deletion evidence where policy permits. |

## Invariants

- INV-DR-01: `workspace_id`, `item_id`, normalized snapshot, graph revision,
  policy/pipeline hashes, engine version, normalization profile, source revision
  set, causation, and correlation identify the decision's complete input context.
- INV-DR-02: DecisionRecords are immutable once persisted. Never modified.
- INV-DR-03: DecisionRecords are append-only within their governed retention lifetime; they are never rewritten in place.
- INV-DR-04: Ranking rationale is reproducible: every applied comparator records
  canonical item-local input/value and deterministic tie-break participation, not
  merely comparison against an adjacent item.
- INV-DR-05: Gate summary reflects the states at decision time.
- INV-DR-06: Authority map covers every field used in ranking at decision time.
- INV-DR-07: A DecisionRecord for a WorkItem with unavailable data carries partial data with appropriate authority statuses.
- INV-DR-08: Only an authoritative decision can support claiming a [WorkLease](work-lease.md).
- INV-DR-09: Replaying the identified normalized snapshot through the identified
  graph, policy bundle, ranking pipeline, and engine version produces the same
  canonical decision payload hash; mismatch emits a deterministic integrity
  AttentionItem and never overwrites history.
