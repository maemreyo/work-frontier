---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-06
---

# Gates and Evidence

**WF-DOM-06**: Work Frontier uses **Gates** to enforce quality, evidence, and authority constraints before a [WorkItem](work-item.md) advances in its [lifecycle](lifecycle-and-completion.md). Every Gate requires **EvidenceRecords**: typed, revision-bound, signed or attested proof that the gate condition has been met. AI output never counts as evidence. The engine is localized fail-closed: when it cannot determine whether a gate passes, it fails the gate and emits an [AttentionItem](attention-items.md).

## Gate

A Gate is a named checkpoint on a [WorkItem](work-item.md). A WorkItem can have zero or more Gates. Gates are linked to WorkItems via [`requires_gate` edges](edges.md#requires-gate). Gates are evaluated on every engine cycle.

Each Gate declares an **applicability phase**: `entry`, `completion`, or `certification`. Entry gates participate in readiness; completion and certification gates participate only when evaluating their corresponding outcome. This prevents evidence required to finish work from incorrectly blocking the work from starting.

### Gate States

| State | Meaning |
|-------|---------|
| `pending` | Not yet evaluated, or the condition has not been met. |
| `passed` | Condition is met, backed by [EvidenceRecord](#evidencerecord). The WorkItem can advance. |
| `failed` | Condition is not met, or evidence is insufficient. The WorkItem cannot advance past this gate. |
| `waived` | A human explicitly waived this gate. Tracked with provenance. Safety gates cannot be waived. |

### Gate Types

| Type | What it checks | Default evidence | Can waive? |
|------|---------------|-----------------|-----------|
| **dependency** | All hard `blocks` dependencies are complete. | Dependency WorkItems in `completed` lifecycle state. | N/A (binary). |
| **evidence** | Required EvidenceRecords have been attached. | Evidence artifact with valid timestamp. | Yes, with provenance. |
| **approval** | A human has approved the WorkItem. | User snapshot with approval signal. | N/A (the approval IS the action). |
| **quality** | The WorkItem meets quality criteria. | Automated quality check result. | Yes, with provenance. |
| **safety** | The WorkItem does not violate safety constraints. | Deterministic check. | **No.** Hard blocks. |

### Gate Evaluation

The engine evaluates Gates as follows:

1. Check if the Gate condition is satisfied using the WorkItem's [merged state](authority-statuses.md).
2. If satisfied, check for supporting [EvidenceRecords](#evidencerecord).
3. If EvidenceRecords exist and are valid, set gate state to `passed`.
4. If the condition is not met, set gate state to `failed`.
5. If the condition is met but EvidenceRecords are missing, set gate state to `pending`.
6. If a human has waived the gate, set gate state to `waived`.

### Gate Authority

| Gate type | Can the engine auto-pass? | Can a human waive it? |
|-----------|--------------------------|----------------------|
| dependency | Yes, when dependencies complete. | N/A. |
| evidence | No. Evidence must be provided. | Yes, with provenance. |
| approval | No. Requires human action. | N/A. |
| quality | Yes, when automated checks pass. | Yes, with provenance. |
| safety | Yes, when deterministic checks pass. | **No.** Cannot be waived or overridden. |

### Safety Gates and Overrides

Safety gates are **non-overridable**. A human override cannot bypass, weaken, or waive a safety gate. This is a hard constraint:

- An override that would mark a WorkItem as `completed` while a safety gate is `failed` is rejected at override time.
- An override that would change lifecycle state to bypass a safety gate transition is rejected.
- Safety gate status is immutable evidence of a hard constraint.

## EvidenceRecord

An EvidenceRecord is typed, revision-bound, signed or attested proof that a [Gate](#gate) condition has been met. Every gate pass must be backed by at least one valid EvidenceRecord. AI output never counts as evidence under any circumstance.

### EvidenceRecord Structure

| Field | Type | Description |
|-------|------|-------------|
| `evidence_id` | ULID | Unique identifier. |
| `gate_id` | string | The Gate this EvidenceRecord supports. |
| `item_id` | string | The WorkItem this EvidenceRecord belongs to. |
| `type` | enum | `computed`, `observed`, or `declared`. |
| `revision` | string | The revision of the WorkItem this evidence pertains to. Ties evidence to a specific state. |
| `source` | string | What produced the evidence. |
| `attestation` | Attestation or null | Signature or attestation where required. See below. |
| `timestamp` | ISO 8601 | When the evidence was captured. |
| `content` | object | The evidence itself. |
| `valid_until` | ISO 8601 or null | Expiry. Stale evidence triggers re-evaluation. |
| `authority_status` | AuthorityStatus | The [authority status](authority-statuses.md#authority-statuses) of this evidence. |

### Attestation

When required by gate type or policy, an EvidenceRecord carries an attestation:

| Field | Type | Description |
|-------|------|-------------|
| `attestor` | string | Who attested: user ID or system process ID. |
| `method` | enum | `signature`, `cryptographic`, `witnessed`, `declared`. |
| `timestamp` | ISO 8601 | When attested. |
| `content` | string | The attestation statement or signature hash. |

Attestation is required for:
- Safety gate evidence.
- Completion evidence on safety-critical WorkItems.
- Any evidence type designated by configuration.

### Evidence Types

| Type | Who produces it | Trust level | Examples |
|------|----------------|-------------|---------|
| `computed` | Automated systems (CI, linters, tests) | High (if system trusted) | Test results, lint output, CI status. |
| `observed` | Human observation | High (firsthand) | Screenshot, log excerpt, manual verification. |
| `declared` | Human declaration | Medium (self-report) | "I tested this manually." |

**AI output is never evidence.** AI-generated text, suggestions, or analysis cannot serve as an EvidenceRecord, regardless of type. AI may assist in evidence collection (e.g., generating a test that a human then runs and records the result), but the evidence is the test result, not the AI output. An AI-suggested item that passes deterministic validation becomes an [AttentionItem](attention-items.md), not evidence.

### Revision Binding

Every EvidenceRecord is bound to a specific revision of the WorkItem. The `revision` field captures what state the evidence pertains to. When the WorkItem changes, existing evidence is not automatically valid for the new revision. Gates re-evaluate: evidence valid for a prior revision does not pass gates on the current revision unless the evidence explicitly covers the current revision.

### Evidence Rules

1. **Every pass requires evidence.** A Gate cannot transition to `passed` without at least one valid EvidenceRecord.
2. **Evidence can expire.** When `valid_until` is exceeded, the evidence becomes stale. The Gate re-evaluates.
3. **Evidence is append-only within its governed retention lifetime.** New EvidenceRecords are added and existing records are never rewritten; retention expiry or governed deletion removes the containing evidence set with audit proof where policy permits.
4. **Evidence is scoped.** One EvidenceRecord supports exactly one Gate on exactly one WorkItem, at a specific revision.
5. **Authority-aware.** Gates require `authoritative` or `provisional` evidence. `stale` or `conflicted` evidence does not pass Gates.
6. **AI evidence is excluded.** AI output never qualifies as evidence, regardless of type or attestation status.
7. **Revision-bound.** Evidence is valid only for the revision it records. WorkItem changes require new evidence.

### Localized Fail-Closed

When the engine cannot determine Gate state, it defaults to `failed`:

- Evidence is ambiguous → gate fails.
- Evidence source is untrusted → gate fails.
- Evidence is expired with no fresh replacement → gate fails.
- Evidence is for a prior revision → gate fails.
- Gate condition cannot be evaluated → gate fails.

The engine never assumes a Gate passes. It always requires proof.

## Gates and Lifecycle

| Transition | Required Gates |
|-----------|---------------|
| `planned` → `active` | All applicable `entry` gates must be `passed` or validly waived. Safety gates cannot be waived. |
| `active` → `completed` | All applicable `completion` gates must be `passed` or validly waived. Safety gates cannot be waived. |
| `completed` → certified outcome | All applicable `certification` gates must be `passed` or validly waived. Safety gates cannot be waived. |
| `any` → `cancelled` | None. |

## Gates and Readiness

Only applicable `entry` gates affect [readiness](readiness-ranking.md#readiness): a WorkItem with a failed or pending entry gate has readiness `false`. Completion and certification gates constrain those outcomes, not the ability to begin work.
