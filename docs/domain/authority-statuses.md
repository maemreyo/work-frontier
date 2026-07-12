---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-17
---

# Authority Statuses

**WF-DOM-17**: Every piece of data in Work Frontier carries an **authority status** indicating how trustworthy its current value is. Authority statuses are: `authoritative`, `provisional`, `stale`, `conflicted`, and `unavailable`. Source precedence is a strict six-level ladder. Conflicts between sources are surfaced, never silently resolved. Authority statuses apply to [decisions](decision-record.md) and snapshots. Only an authoritative decision can support claiming a [WorkLease](work-lease.md).

## Why Authority Statuses Exist

Multiple sources provide state for the same [WorkItem](work-item.md). When sources agree, the value is trustworthy. When they disagree, the conflict must be tracked and surfaced. Authority statuses make trust explicit.

## Authority Statuses

| Status | Meaning | When it applies |
|--------|---------|----------------|
| `authoritative` | Value confirmed by the authoritative source, consistent with current data. | Fresh sync, no conflicts, no overrides. |
| `provisional` | Value from a source that may change. Not yet confirmed. | Pending sync, newly computed, recent input not yet validated. |
| `stale` | Value from a source that hasn't been refreshed within the staleness threshold. | Sync interval exceeded, override older than configured TTL. |
| `conflicted` | Multiple sources provide different values for the same field. | Sources disagree on a field value. |
| `unavailable` | No source has a value for this field. | Tracker unreachable, field not mapped, incomplete data. |

## Source Precedence

When multiple sources provide values for the same field, the engine applies a strict six-level precedence ladder:

```
human override > configured policy > native tracker > structured metadata > parsed Markdown > inference
```

| Level | Source | What it provides | Example |
|-------|--------|-----------------|---------|
| 1 (highest) | **Human override** | Explicit, scoped, authorized, time-bounded decision by a human. | "Mark this priority as critical." |
| 2 | **Configured policy** | Rules set by an operator or admin. Applies globally or per-Program. | "All safety-gated items have priority high." |
| 3 | **Native tracker** | The tracker's own authoritative state fields. | GitHub issue status "open", assignee "alice". |
| 4 | **Structured metadata** | Labels, tags, milestones, and other structured fields from the tracker. | GitHub label "bug", milestone "v2.0". |
| 5 | **Parsed Markdown** | Content extracted from free-text fields (descriptions, comments). | "This blocks #42" parsed into a `blocks` edge. |
| 6 (lowest) | **Inference** | Engine-computed values. Always labeled as inferred. | Ranking score, readiness boolean, fan-out count. |

Note: AI-suggested values are always at the inference level (level 6). AI never provides authoritative, provisional, or higher-precedence values.

### Conflict Surfacing

When two sources at different precedence levels provide different values for the same field:

1. The higher-precedence value is used as the current value.
2. The field's authority status is set to `conflicted`.
3. A `ConflictDetail` is attached with both values, their sources, and their precedence levels.
4. An [AttentionItem](attention-items.md) of type `authority_downgraded` is emitted.
5. The human sees both values in the Control Room and can resolve the conflict.

**Critical rule:** Conflicts are surfaced, not silently resolved. The engine applies precedence to determine the current value, but it always shows that a conflict exists and what the alternative value is.

### Precedence Examples

| Field | Level 3 (tracker) | Level 1 (override) | Result |
|-------|-------------------|-------------------|--------|
| `status` | "open" | "done" (authorized override) | "done" — override wins, but conflict surfaced if tracker still says "open". |
| `priority` | "low" | — | "low" — tracker value used, no conflict. |
| `labels` | ["bug"] | ["bug", "urgent"] (override) | ["bug", "urgent"] — override wins. |

### Safety Override Constraints

**Human overrides are scoped, authorized, audited, and time-bounded.** They do not always supersede global safety or completion policy:

| Constraint | Rule |
|-----------|------|
| **Scoped** | An override applies only to the specific field and WorkItem it targets. It does not cascade to children or siblings. |
| **Authorized** | Only the primary owner (or an admin) can override. Participants cannot override lifecycle or safety fields. |
| **Audited** | Every override is logged with: who, when, what field, what value, what reason, what authority level. |
| **Time-bounded** | Overrides expire. All TTLs are configurable. No hard-coded defaults. |
| **Non-weakening safety** | An override **cannot** weaken a non-overridable safety constraint. Safety gates remain enforced regardless of overrides. An override that would bypass a safety gate is rejected at override time with an explanation. |
| **Non-weakening completion** | An override **cannot** mark a WorkItem as `completed` if the assigned [completion policy](lifecycle-and-completion.md#completion) has not been satisfied. The override is rejected with a list of unsatisfied policy conditions. |

## Authority and Decisions

Authority statuses apply to [DecisionRecords](decision-record.md) and snapshots. The key rule:

- **Only an authoritative decision can support claiming a [WorkLease](work-lease.md).** If the decision authority is `provisional`, `stale`, `conflicted`, or `unavailable`, the claimant cannot acquire a lease based on it.
- **Decision authority lifecycle:** A DecisionRecord starts as `provisional` when first computed. It becomes `authoritative` when validated against current snapshots and no conflicts exist. It becomes `stale` when the underlying snapshots change. It becomes `conflicted` when snapshots from multiple sources disagree about the basis of the decision.

## Provenance

Every value on a WorkItem carries provenance: who provided it, when, from what source level, and why.

### Provenance Structure

| Field | Type | Description |
|-------|------|-------------|
| `field` | string | The WorkItem field this provenance applies to. |
| `value` | any | The value at this point in time. |
| `source_level` | enum | The precedence level: `override`, `policy`, `tracker`, `metadata`, `parsed`, `inference`. |
| `source_id` | string | Specific source: tracker connection ID, policy rule ID, user ID. |
| `timestamp` | ISO 8601 | When this value was recorded. |
| `authority` | AuthorityStatus | The authority status of this value at this time. |
| `conflict` | ConflictDetail or null | If authority is `conflicted`, details of the conflict. |

### ConflictDetail

| Field | Type | Description |
|-------|------|-------------|
| `field` | string | The conflicting field. |
| `values` | list[ProvenanceEntry] | The conflicting values from different sources, each with source_level. |
| `resolution` | enum | `pending` (needs human decision), `auto_resolved` (precedence applied), `waived` (human chose to ignore). |
| `resolved_by` | string or null | Who resolved it, if resolved. |
| `resolved_at` | ISO 8601 or null | When it was resolved. |

## Staleness Detection

| Source | Staleness condition |
|--------|-------------------|
| Human override | Override TTL exceeded (all TTLs configurable). |
| Configured policy | Policy rule modified since value was last evaluated. |
| Native tracker | `last_sync_at` exceeds the TrackerConnection sync interval. |
| Structured metadata | Same as native tracker (synced together). |
| Parsed Markdown | Description field changed since last parse. |
| Inference | Recomputed on each engine cycle; persisted DecisionRecord snapshots become stale when their source revisions or policy bundle change. |

Stale values are still used (precedence still applies), but the authority status is `stale` and an [AttentionItem](attention-items.md) is emitted.

## Authority Status and the Engine

| Computation | Authority-aware? | Effect |
|------------|-----------------|--------|
| [Readiness](readiness-ranking.md#readiness) | Yes | `unavailable` or `conflicted` authority on safety-critical fields → readiness `false`. |
| [Ranking](readiness-ranking.md#ranking) | Yes | `stale` authority flagged in ranking rationale. |
| [Gate evaluation](gates-and-evidence.md) | Yes | Gates require `authoritative` or `provisional` evidence. `stale`/`conflicted` evidence does not pass. |
| [Completion](lifecycle-and-completion.md#completion) | Yes | Completion requires authoritative data for safety-critical fields. |

## Authority Status Lifecycle

```
unavailable → provisional → authoritative
                              ↓
                           stale
                              ↓
                        unavailable (if source disconnects)

provisional → conflicted (when a second source disagrees)
                ↓
           authoritative (when conflict resolved and sources agree)
```

The full state machine is in [State Machines](state-machines.md#authority-status-lifecycle).
