---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-19
---

# WorkLease

**WF-DOM-19**: A WorkLease is a coordination lease on a [WorkItem](work-item.md), held by a claimant. WorkLeases coordinate who is working on what. They are not mutation locks.

## Purpose

Without coordination leases, two actors could work on the same WorkItem without awareness, producing inconsistent decisions. A WorkLease signals: "this claimant is coordinating work on this item, based on this decision, under these policies, for this duration."

## Key Distinction

A WorkLease is **not** a mutation lock. It does not prevent other actors from reading the WorkItem, viewing its state, or proposing changes. It coordinates: the claimant signals intent to work, and other actors see the lease and defer or negotiate accordingly.

## Structure

| Field | Type | Description |
|-------|------|-------------|
| `lease_id` | ULID | Unique identifier. |
| `item_id` | string | The WorkItem this lease coordinates. |
| `claimant` | string | Who holds it: user ID, agent ID, or automation process ID. |
| `claimant_type` | enum | `human`, `agent`, or `automation`. Determines duration and priority. |
| `mode` | enum | `exclusive` or `collaborative`. Exclusive means the claimant has sole coordination. Collaborative allows shared work with other leaseholders. |
| `decision_id` | string | The [DecisionRecord](decision-record.md) this lease is based on. Only an authoritative decision can support claiming. |
| `source_revisions` | list[string] | The WorkItem field revisions the claimant read when acquiring this lease. Enables staleness detection. |
| `policy_hash` | string | Hash of the active [completion policies](lifecycle-and-completion.md#completion) and safety constraints at lease time. If policies change, the lease is flagged. |
| `acquired_at` | ISO 8601 | When acquired. |
| `ttl` | duration | Maximum hold duration. Auto-releases when exceeded. |
| `heartbeat_at` | ISO 8601 or null | Last heartbeat from the claimant. Extends effective lease life. |
| `suspended` | boolean | Whether the lease is temporarily suspended (e.g., claimant stepped away). |
| `renewal_count` | int | How many times renewed. |
| `reason` | string or null | Why acquired. |
| `source` | enum | How the lease was created: `user`, `agent`, or `automation`. External tracker assignments are reconciliation inputs, not lease holders. |
| `status` | enum | `active`, `renewed`, `expired`, `released`, `broken`. |

## Lease Durations

All durations are configurable. The defaults below are starting points, not hard-coded constants.

| Claimant type | Default TTL | Max renewals | Max hold |
|--------------|------------|-------------|---------|
| human | 4h | 3 | 16h |
| agent | 30m | 2 | 90m |
| automation | 1h | 1 | 2h |

## WorkLease Lifecycle

| State | Meaning |
|-------|---------|
| `active` | Valid. Claimant has coordination. |
| `renewed` | Renewed (extends TTL). |
| `expired` | TTL exceeded. Auto-released. |
| `released` | Claimant explicitly released before expiry. |
| `broken` | Higher-priority actor took the lease, or policy changed. |

Full state machine in [State Machines](state-machines.md#worklease-lifecycle).

## Lease Priority

| Priority | Claimant type | Rationale |
|---------|---------------|-----------|
| 1 (highest) | Human (primary owner) | Owner has permanent priority. |
| 2 | Human (non-owner) | Any human outranks automated claimants. |
| 3 | Agent | AI-assisted work. |
| 4 (lowest) | Automation | Background processes, lowest priority. |

## WorkLease and Readiness

A WorkItem with an active exclusive WorkLease held by another claimant is not claimable by that actor. Its underlying eligibility remains visible, while the DecisionRecord explains that coordination availability is blocked. Collaborative leases do not block approved collaborators.

## WorkLease and Lifecycle

| Event | Effect on lifecycle |
|-------|-------------------|
| Lease acquired on `planned` | `planned` → `active`. |
| Lease released on `active` (no work logged) | `active` → `planned`. |
| Lease released on `active` (work logged) | Stays `active`. |

## Conflict Resolution

| Scenario | Resolution |
|----------|-----------|
| Lease expires naturally | Auto-release. |
| Higher-priority claimant requests | Request handoff or an authorized lease override. Never break silently. Log provenance and emit `claim_at_risk`. |
| Lower-priority claimant requests | Rejected. Emit `claim_at_risk` AttentionItem. |
| Authorized human overrides a lease | Allowed only by scoped policy or break-glass procedure. Always logged and always produces AttentionItem. |
| Simultaneous lease attempt | First acquires. Second rejected. |
| Policy hash mismatch | Lease flagged for renewal or break. Emit `claim_at_risk` AttentionItem. |

No silent breaks. Every forced release produces an [AttentionItem](attention-items.md).

Breaking a lease is subject to [safety override constraints](authority-statuses.md#safety-override-constraints):

- **Authorized** — only the primary owner or a scoped administrator can force an override; a higher-priority claimant may request handoff but cannot break it unilaterally.
- **Audited** — every break is logged with who, when, why.
- **Time-bounded** — the replacement lease follows normal TTL rules.

## Invariants

- INV-WL-01: A WorkItem can have multiple active collaborative leases but at most one active exclusive lease.
- INV-WL-02: Every WorkLease has a non-null `ttl`.
- INV-WL-03: WorkLeases auto-release when TTL is exceeded.
- INV-WL-04: Forced breaks are always logged with provenance.
- INV-WL-05: Lease priority is deterministic: owner > non-owner human > agent > automation.
- INV-WL-06: Only an authoritative [DecisionRecord](decision-record.md) can support acquiring a lease.
- INV-WL-07: The engine never holds a WorkLease. A tracker never holds a WorkLease.
- INV-WL-08: `source_revisions` captures what the claimant read when acquiring, enabling staleness detection.
