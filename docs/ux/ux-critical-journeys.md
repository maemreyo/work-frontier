---
title: Work Frontier — Critical User Journeys
id: WF-UX-006
version: 2.0.0
status: canonical
owner: UX Architecture
last_updated: "2026-07-12"
replaces: 1.0.0
supersedes: null
---

# Critical User Journeys

> **Purpose**: Defines the end-to-end paths through Work Frontier's most important readiness workflows. Each journey specifies the entry point, every screen transition, the expected time, and the success condition. These are the reference paths for implementation, QA, and accessibility auditing.

---

## 1. Journey Conventions

Each journey follows this structure:

- **Persona**: Which view/role combination initiates the journey.
- **Entry point**: Where the user starts.
- **Steps**: Screen-by-screen transitions with the action at each step.
- **Decision points**: Where the user makes a choice that branches the path.
- **Time target**: Expected duration for a proficient user.
- **Success condition**: What "done" looks like.
- **Failure modes**: What goes wrong and how the UI communicates it.

All journeys must be completable via keyboard alone, announced properly to screen readers, and tested at 375px and 1280px viewports (see [Accessibility](ux-accessibility-design-system.md)).

---

## 2. Journey: Claim a WorkItem and Resolve Why It Is Blocked

> The core readiness loop. Claiming creates a coordination lease. Every other journey supports or extends this one.

**Persona**: Builder
**Entry point**: Builder view with an active Program
**Time target**: < 5 minutes for a straightforward WorkItem

### Steps

| # | Screen | Action | Notes |
|---|--------|--------|-------|
| 1 | Builder (What next) | Review the recommended WorkItem | Shows title, authority, freshness, why selected, blockers, evidence status. |
| 2 | Builder (WorkItem detail) | Expand the WorkItem to see evidence requirements | L3 disclosure: full evidence list, what's collected, what's missing, what's stale. |
| 3 | Builder (WorkItem detail) | Claim the WorkItem | Creates a coordination lease (visible to all participants). Changes status to "In progress." |
| 4 | Builder (WorkItem detail) | Collect missing evidence | Evidence can be: GitHub check status (auto-collected), manual upload, or attestation. |
| 5 | Builder (WorkItem detail) | Resolve blockers (if any) | Blockers are upstream WorkItems. The user sees why this item is blocked and what upstream work would unlock it. |
| 6 | Builder (WorkItem detail) | Open in GitHub (if action is needed there) | Opens the relevant GitHub issue or PR in a new tab. |
| 7 | Builder (WorkItem detail) | Submit for approval | Only available when all evidence is collected and all blockers are resolved. This does NOT auto-advance the WorkItem. It creates a ProposedChange that requires normal approval flow. |

### Decision Points

- **Step 3**: Whether to claim the WorkItem (create a coordination lease) or leave it for someone else.
- **Step 5**: Whether to resolve the blocker directly or escalate.
- **Step 7**: Confirmation: "Submit [WorkItem] for readiness approval?" with a note that this creates a ProposedChange, not an immediate Decision.

### Failure Modes

| Failure | User Experience |
|---------|----------------|
| Evidence collection fails (GitHub check unreachable) | "Could not reach GitHub check. Retry or provide manual evidence." Retry button. |
| Blocker cannot be resolved | WorkItem shows "Blocked" with the blocking chain. The user can view the blocker but not advance the blocked item. |
| Conflict with another user's claim | "This WorkItem was claimed by [user] since you opened it. Refresh to see current state." |
| Claim expired | Coordination lease expired. The claim is released. User is notified and can re-claim. |

---

## 3. Journey: Review and Act on Copilot Proposal

> The primary copilot interaction loop. Tests the decision semantics model end-to-end.

**Persona**: Builder
**Entry point**: Builder view with a ProposedChange on a WorkItem
**Time target**: < 2 minutes per proposal cycle

### Steps

| # | Screen | Action | Notes |
|---|--------|--------|-------|
| 1 | Builder (WorkItem) | Copilot sidebar or inline ProposedChange appears | `AI suggestion` visual treatment per [UX Architecture §3.1](ux-architecture.md#31-decision-types). |
| 2 | Builder (WorkItem) | User reads the proposal | "View reasoning" disclosure is collapsed by default. |
| 3 | Builder (WorkItem) | User expands "View reasoning" (optional) | Opens inline, does not navigate away. Shows why the copilot suggested this change. |
| 4 | Builder (WorkItem) | User clicks **Accept** or **Dismiss** | Both actions are visible. Accept creates a ProposedChange that enters the normal approval flow. It does NOT immediately become a Human Override. |
| 5 | Builder (WorkItem) | A ProposedChange appears with `Provisional` status | The ProposedChange requires review and approval through the standard flow. It carries the copilot's original reasoning and the user's acceptance. |

### Decision Points

- **Step 3**: Whether to view reasoning. If skipped, the user can still accept/dismiss without reading it.
- **Step 4**: Accept, dismiss, or do nothing (proposal remains until dismissed or the WorkItem advances).

### Failure Modes

| Failure | User Experience |
|---------|----------------|
| Proposal conflicts with existing Decision | Both decisions shown side-by-side with a "Conflict" badge. User resolves by picking one. |
| Copilot produces a proposal flagged by provider safety layer | The proposal carries a `Degraded` indicator. The safety layer's schema validation flagged it, not the user. See [AI Governance](../security/ai-governance.md) for bounds. |

---

## 4. Journey: Coordinate Blocked Work

> Tests the Coordinator view and cross-Program visibility.

**Persona**: Coordinator
**Entry point**: Coordinator view
**Time target**: < 3 minutes to assess and intervene

### Steps

| # | Screen | Action | Notes |
|---|--------|--------|-------|
| 1 | Coordinator (blocked list) | View blocked WorkItems grouped by Program | Default: blocked-first sort. Each item shows the blocking chain. |
| 2 | Coordinator (unlock impact) | Click "What if this is unlocked?" | Shows downstream WorkItems that would become unblocked, with the total readiness impact. |
| 3 | Coordinator (conflicts) | Review conflicting Proposals | Two ProposedChanges that affect the same WorkItem are flagged. User resolves by picking one or dismissing both. |
| 4 | Coordinator (bulk action) | Select multiple blocked WorkItems | Checkbox or shift-click range. |
| 5 | Coordinator (bulk action) | Reassign, reprioritize, or escalate selected | Confirmation dialog for destructive actions. |

### Decision Points

- **Step 2**: Whether to prioritize unlocking this blocker based on the impact analysis.
- **Step 3**: Which proposal to accept when two conflict. "Dismiss both" is always an option.
- **Step 5**: Which bulk action to apply.

### Failure Modes

| Failure | User Experience |
|---------|----------------|
| No blocked WorkItems match filters | Empty state: "No blocked WorkItems. Your programs are on track." |
| Bulk action partially fails | "X of Y WorkItems updated. Z failed." Failed items listed with reasons. |

---

## 5. Journey: Assess Program Readiness (Executive)

> Tests the Executive view and terminal outcome model.

**Persona**: Executive
**Entry point**: Executive view
**Time target**: < 2 minutes to assess a Program

### Steps

| # | Screen | Action | Notes |
|---|--------|--------|-------|
| 1 | Executive (summary) | View Program cards with terminal outcomes | Each: Program name, Ready/Not Ready/At Risk badge, confidence indicator. |
| 2 | Executive (Program detail) | Click a Program card | Shows: WorkItem breakdown by status, evidence coverage, risk items. |
| 3 | Executive (risk matrix) | View items at risk | Items that may miss their deadline, with the impact of each. |
| 4 | Executive (trend) | View readiness trend over time | Chart: readiness score by week. Table equivalent available (see [Accessibility §5](ux-accessibility-design-system.md#5-graph-and-table-equivalence)). |
| 5 | Executive (export) | Export readiness report | Format: standalone HTML or JSON. Report carries staleness/provisional metadata. |

### Decision Points

- **Step 1**: Which Program to drill into.
- **Step 5**: Export format and scope (single Program or all Programs).

### Failure Modes

| Failure | User Experience |
|---------|----------------|
| No Programs exist | Empty state: "No Programs yet. Complete onboarding to get started." |
| Readiness data is stale | Amber "Stale" badge on affected Programs. User can trigger a refresh. |

---

## 6. Journey: Reconcile Sync Discrepancies

> Tests the Operator view and reconciliation model.

**Persona**: Operator
**Entry point**: Operator view
**Time target**: < 2 minutes to assess and reconcile

### Steps

| # | Screen | Action | Notes |
|---|--------|--------|-------|
| 1 | Operator (sync status) | View Connection health cards | Each Connection: name, status (healthy/degraded/disconnected), last sync time. |
| 2 | Operator (reconciliation) | View discrepancies | Items where GitHub state differs from Work Frontier's record. |
| 3 | Operator (reconciliation) | Accept Work Frontier state | "Work Frontier is correct" — keeps the local state. |
| 4 | Operator (reconciliation) | Accept GitHub state | "GitHub is correct" — updates the local state to match GitHub. |
| 5 | Operator (reconciliation) | Manual resolution | For ambiguous cases, the user edits the WorkItem directly. |
| 6 | Operator (queue) | View sync queue depth | Pending operations. If deep, shows estimated time to drain. |

### Decision Points

- **Step 3/4/5**: Which source of truth to trust for each discrepancy.

### Failure Modes

| Failure | User Experience |
|---------|----------------|
| GitHub API rate limited | "GitHub is rate-limiting. Retry in [countdown]." |
| Connection disconnected | "Connection lost. Reconnect in Connection settings." Status card shows "Disconnected." |
| Reconciliation timeout | "Reconciliation is taking longer than expected. Continue in background?" |

---

## 7. Journey: Handle a Degraded Connection

> Tests how the system communicates and recovers when a Connection source becomes unreliable.

**Persona**: Builder or Operator
**Entry point**: Any view where a Connection is degraded
**Time target**: < 3 minutes to assess impact and decide

### Steps

| # | Screen | Action | Notes |
|---|--------|--------|-------|
| 1 | Any view | Degradation banner appears | "One or more Connections are degraded. Some evidence may be stale." Banner is persistent, not auto-dismissable. |
| 2 | Builder (WorkItem detail) | Affected WorkItems show `Unavailable` authority status | Evidence from the degraded Connection is marked `Unavailable`. The last-known state is shown but cannot be trusted. |
| 3 | Builder (What next) | "What next" adjusts to avoid recommending items dependent on unavailable evidence | The system skips WorkItems whose evidence depends on the degraded Connection, or marks them as "Waiting for source." |
| 4 | Operator (sync status) | Operator views the degraded Connection | Shows: last successful sync time, error details, and retry options. |
| 5 | Operator (reconciliation) | Operator triggers a manual re-sync or reconnects | If re-sync succeeds, affected WorkItems return to their previous authority status. If it fails, the degradation persists. |

### Decision Points

- **Step 3**: Whether to continue working on unaffected WorkItems or wait for the Connection to recover.
- **Step 5**: Whether to reconnect, wait, or escalate.

### Failure Modes

| Failure | User Experience |
|---------|----------------|
| Connection completely unreachable | Status: `Disconnected`. Banner escalates to a full-width warning. Operator sees "Connection lost" in sync status. |
| Degradation is intermittent | Banner persists between successes. Operator sees a success rate indicator. |
| Multiple Connections degraded | Banner lists all degraded Connections. Operator sees them grouped in sync status. |

---

## 8. Journey: Act on a Stale Decision

> Tests how the system communicates and resolves stale authority determinations.

**Persona**: Builder
**Entry point**: Builder view with a WorkItem carrying a `Stale` authority status
**Time target**: < 2 minutes to assess and resolve

### Steps

| # | Screen | Action | Notes |
|---|--------|--------|-------|
| 1 | Builder (What next) | WorkItem shows `Stale` authority status | Amber badge next to the timestamp. The system still displays the stale determination but marks it clearly. |
| 2 | Builder (WorkItem detail) | User reviews the stale item | Shows: what the current determination is, when it was last verified, what has changed since (if detectable), and why it is stale. |
| 3 | Builder (WorkItem detail) | User triggers a refresh | System re-evaluates the authority determination against current source data. |
| 4 | Builder (WorkItem detail) | Refresh result | Either: the stale status clears (determination confirmed), or the determination changes (new status applied with audit trail). |
| 5 | Builder (What next) | System adjusts recommendation if needed | If the stale determination's update changed blocking relationships, "What next" may change. |

### Decision Points

- **Step 3**: Whether to refresh, dismiss the stale status (acknowledge but don't refresh), or leave it as-is.
- **Step 4**: If the refresh produces a conflicting result, the user resolves the conflict.

### Failure Modes

| Failure | User Experience |
|---------|----------------|
| Refresh fails (source unreachable) | "Source unreachable. The stale status persists." The `Unavailable` badge may also appear. |
| Refresh reveals the old determination was wrong | The old determination is marked `Superseded`. The new one carries a fresh authority status. Audit trail records both. |

---

## 9. Journey: Handle an Error State

> Tests error communication and recovery across all views.

**Persona**: Any
**Entry point**: Any view, any state
**Time target**: Recovery in < 1 minute for recoverable errors

### Error Hierarchy

| Severity | Visual | User Action Required |
|----------|--------|---------------------|
| **Informational** | Subtle toast, auto-dismiss after 5s | None. |
| **Warning** | Persistent banner at top of view | Acknowledge or dismiss. |
| **Error** | Modal or inline error block | Retry, dismiss, or contact support. |
| **Critical** | Full-page error state | Retry or contact support. Navigation disabled until resolved. |

### Error Rules

| Rule | Description |
|------|-------------|
| ER-01 | Errors never show raw technical messages. All error text is human-readable. |
| ER-02 | Every error state includes a recovery action (retry, dismiss, or navigate away). |
| ER-03 | Error states are keyboard-navigable and screen-reader-announced. |
| ER-04 | Network errors trigger automatic retry before showing an error to the user. |
| ER-05 | Error states are not cached. A refreshed page always attempts a fresh request. |

---

## 10. Journey: Accessibility Audit Path

> Verifies that every critical journey works with assistive technology.

**Persona**: Screen reader user / keyboard-only user
**Entry point**: Login screen
**Time target**: Full audit of all critical journeys in < 4 hours

### Audit Checklist (per journey)

| Check | Pass Condition |
|-------|---------------|
| All interactive elements are focusable | Tab order reaches every button, link, and input. |
| Focus order matches visual order | No unexpected jumps. |
| Decision types are announced | Screen reader says the decision type for every decision card. |
| Copilot proposals are announced | "AI suggestion" is read aloud when the proposal appears. |
| Empty states have text alternatives | Every empty state image or illustration has alt text or `aria-label`. |
| Error states are announced | Errors are announced via `aria-live="assertive"` or a focus trap. |
| All form fields have labels | Every input has an associated `<label>` or `aria-label`. |
| Keyboard shortcuts are discoverable | A help overlay lists all shortcuts. Shortcuts don't conflict with screen reader shortcuts. |

See [Accessibility & Design System](ux-accessibility-design-system.md) for the full specification.

---

## 11. Cross-References

| Document | Section | Relevance |
|----------|---------|-----------|
| [UX Architecture](ux-architecture.md) | §2 Views, §3 Decision Semantics | Foundation for all journeys. |
| [Onboarding](ux-onboarding.md) | §2 Onboarding Flow | Precedes all journeys for new users. |
| [Accessibility](ux-accessibility-design-system.md) | Full document | Mandatory for all journeys. |
| [Authorization](../security/authorization.md) | §2 Roles | Determines which journeys a user can initiate. |
| [AI Governance](../security/ai-governance.md) | §2 Copilot Bounds | Constrains copilot proposals in Journey 3. |
| [Threat Model](../security/threat-model.md) | §2.3 Injection Attacks | Constrains GitHub content trust model in Journey 5. |
