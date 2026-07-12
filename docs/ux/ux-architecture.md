---
title: Work Frontier — UX Architecture Specification
id: WF-UX-001
version: 2.0.0
status: canonical
owner: UX Architecture
last_updated: "2026-07-12"
replaces: 1.0.0
supersedes: null
---

# UX Architecture Specification

> **Purpose**: Defines the information architecture, view hierarchy, decision semantics, and progressive disclosure model for Work Frontier — a readiness control plane. All product surfaces must conform to this spec. Cross-references to [Security Authorization](../security/authorization.md) and [AI Governance](../security/ai-governance.md) are authoritative where linked.

---

## 1. Information Architecture Principle

Work Frontier organizes around **readiness**, not content production. Every screen, navigation path, and data structure answers the question: *"Is this program ready, and what should happen next to make it more ready?"*

Internal technical modules (sync engines, queue processors, reconciliation workers) never appear in navigation labels, URL slugs, or user-facing terminology. Users discover system capabilities through the readiness state those capabilities surface.

### 1.1 Core Resources

| Resource | What It Is | User-Facing Analogy |
|----------|-----------|-------------------|
| **Program** | A readiness initiative (e.g., "Q2 Production Launch", "SOC 2 Audit"). Groups related WorkItems under a common objective. | A project board. |
| **WorkItem** | A single readiness requirement — a check, gate, or task that must be satisfied. Each has an authority, a freshness indicator, and evidence requirements. | A checklist entry. |
| **Decision** | An authoritative determination about a WorkItem or Program — whether it is ready, blocked, or waived. Decisions carry provenance (human, policy, or computed). | A sign-off. |
| **Policy** | A rule that governs readiness assessment. Policies define what "ready" means for a Program, including required evidence types, blocking conditions, and quality thresholds. | A compliance rule. |
| **Connection** | An integration that feeds readiness data (e.g., a GitHub App, a CI/CD pipeline, an SSO provider). Connections are scoped within a tenant. | A data source. |
| **Evidence** | Proof that a WorkItem has been satisfied — a test result, a review approval, a certification, a GitHub check status. Evidence has provenance and freshness. | A receipt. |
| **ProposedChange** | A suggestion (human or AI-generated) to modify a WorkItem, Decision, or evidence association. ProposedChanges are never auto-applied. They require normal approval flow. | A suggestion. |
| **Claim** | A coordination lease on a WorkItem. Claims are temporary, scoped, and visible to all participants. Claiming does not imply ownership or technically lock edits; it prevents duplicate work through explicit coordination. | A visible work reservation. |

### 1.2 Navigation Topology

Work Frontier uses a **flat-primary, deep-secondary** navigation model:

- **Primary nav** (always visible): Up to 4 top-level destinations corresponding to the 4 views.
- **Secondary nav** (contextual): Appears within a view, scoped to the current Program or list.
- **Tertiary nav** (transient): Drawers, modals, and panels that overlay the current view without navigating away.

Breadcrumbs are never the primary navigation mechanism. They appear as supplementary context only.

---

## 2. Views

Work Frontier exposes four views. Every user lands on **Builder** by default, regardless of role. Views are not permission gates; they are lenses on the same underlying readiness data, surfaced at different levels of detail and control.

### 2.1 Builder View

> **Default home for all users.**

Builder is the working surface. It answers: *"What should I do next to advance readiness, and why?"*

**Builder surfaces (exact display priority, top to bottom):**

1. **What next** — the single most impactful action the user can take right now, selected by the system based on authority, freshness, and blocking relationships. This is the first thing a user sees and reads.
2. **Authority & freshness** — who decided the WorkItem's current state (human, policy, or computed) and how current that determination is. Always visible alongside "What next."
3. **Why** — a plain-language explanation of why this item is recommended next (e.g., "This blocks 3 downstream WorkItems and its evidence expired 2 days ago").
4. **Evidence** — what evidence is needed, what evidence exists, and what is stale or missing.
5. **Attention indicators** — blockers, conflicts, degraded connections, or stale decisions that need human intervention.

- **Claim / Open in GitHub** — the user can claim a WorkItem (create a coordination lease) or open it directly in GitHub to take action.

**Builder does NOT contain:**

- Cross-Program dashboards
- Admin or settings surfaces
- Team or roster management
- Content editing or evidence fabrication

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│ Builder Header: Program · Readiness status · Actions│
├─────────────────────────────────────────────────────┤
│ What Next                                            │
│ ┌─────────────────────────────────────────────────┐ │
│ │ WorkItem title                                   │ │
│ │ Authority: Policy (fired 2h ago) · Fresh: OK    │ │
│ │ Why: "Blocks deployment gate, evidence expired"  │ │
│ │ Evidence: 3/5 collected, 1 stale                │ │
│ │ Attention: 2 upstream blockers                   │ │
│ │ [Claim] [Open in GitHub]                         │ │
│ └─────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────┤
│ WorkItem list (scrollable, filterable)              │
│  Each: title, authority badge, freshness, blockers  │
└─────────────────────────────────────────────────────┘
                                    │
                              Copilot sidebar (toggle)
```

### 2.2 Coordinator View

Coordinator shows the readiness landscape across a team or program. It answers: *"Where is work blocked, what would unlocking it impact, and are there conflicts?"*

**Coordinator surfaces:**

- **Blocked WorkItems** — items blocked by upstream dependencies, with the blocking chain visualized.
- **Unlock impact** — what downstream items would become unblocked if this blocker is resolved.
- **Conflicts** — overlapping or contradictory Proposals from the AI copilot or from different team members.
- **Proposals** — a feed of ProposedChanges awaiting human review, grouped by affected Program.

**Coordinator does NOT contain:**

- Individual WorkItem editing
- System configuration
- Evidence collection

### 2.3 Executive View

Executive distills readiness data into terminal outcomes and risk. It answers: *"Are we on track, and what is at risk?"*

Executive is an **adapted view/read capability**, not necessarily a distinct role. Any user with read access to Programs may reach Executive-level views. The view presents a read-only, high-level projection of readiness data. Users who need this view but hold no Builder or Coordinator role are granted read-only access through the Viewer role (see [Authorization](../security/authorization.md)).

**Executive surfaces:**

- **Terminal outcomes** — Programs classified as Ready, Not Ready, or At Risk, with a confidence indicator.
- **Risk matrix** — WorkItems at risk of missing their deadline, with the impact of each.
- **Trend charts** — readiness score over time, blocked-work trends, evidence coverage.
- **Export / reporting** — readiness reports for stakeholders.

**Executive does NOT contain:**

- WorkItem-level editing
- Runner or infrastructure status
- Copilot interactions

### 2.4 Operator View

Operator exposes sync health and reconciliation status. It answers: *"Is the system in sync with its sources of truth, and what needs intervention?"*

**Operator surfaces:**

- **Sync status** — for each Connection, whether it is healthy, degraded, or disconnected.
- **Queue depth** — pending sync operations, ingestion tasks, and reconciliation work.
- **Reconciliation** — discrepancies between what GitHub/CI reports and what Work Frontier has recorded, with one-click reconciliation actions.
- **Audit log** — operational events filtered to sync, ingestion, and reconciliation.

**Operator does NOT contain:**

- WorkItem content editing
- Team management
- Readiness assessments

### 2.5 View Selection Rules

| Rule | Description |
|------|-------------|
| VF-01 | Builder is the default view on login, for every role. |
| VF-02 | View switching never loses scroll position or pending state in the previous view. |
| VF-03 | Deep links target a specific view and, where applicable, a specific WorkItem within that view. |
| VF-04 | If a user lacks permission to see a view's primary content, they see an explanatory empty state, not a 403 page. |
| VF-05 | Mobile and narrow viewport collapse secondary nav into a bottom sheet or hamburger; Builder goes single-column. |

---

## 3. Decision Semantics

Every screen that shows a decision must distinguish five types visually and semantically. Users must never confuse what kind of authority produced a decision.

### 3.1 Decision Types

| Type | Label | Visual Treatment | What It Means |
|------|-------|-----------------|---------------|
| **Computed Decision** | `Computed` | Solid border, neutral fill, checkmark icon | Deterministic system logic produced this. No LLM involved. Reversible by the same deterministic path. |
| **Policy Decision** | `Policy` | Dashed border, warning tint, shield icon | A configured policy rule fired. The rule was written by a human; the match was automatic. |
| **Human Override** | `Human override` | Solid border, accent fill, person icon | A human explicitly overrode a computed or policy decision. Audit trail records who and when. |
| **AI Suggestion** | `AI suggestion` | Dotted border, subtle tint, sparkle icon | The copilot proposed this. It requires human acceptance or rejection. Never auto-applied. |
| **Degradation** | `Degraded` | Striped border, caution fill, alert icon | The system fell back to a lower-confidence path. The original path failed or was unavailable. |

### 3.2 Decision Display Rules

| Rule | Description |
|------|-------------|
| DD-01 | Decision type is always visible in the UI, never buried in a tooltip or expand-only section. |
| DD-02 | AI suggestions carry a visible "Requires acceptance" badge until acted upon. |
| DD-03 | Degraded decisions carry a visible explanation of what failed and what fallback was used. |
| DD-04 | Human overrides show the previous decision and the override reason inline. |
| DD-05 | Computed and policy decisions show a "Why?" link that opens a one-line rationale without navigating away. |
| DD-06 | All five types appear in the same visual hierarchy. No type is de-emphasized by default. |
| DD-07 | Decision history (all five types) is accessible from the WorkItem's event timeline. |

### 3.3 Copilot Proposals in Context

When the copilot proposes a change within the Builder canvas:

1. The proposal appears as a **ProposedChange** inline at the relevant WorkItem.
2. It carries the `AI suggestion` visual treatment (see §3.1).
3. Two actions are always present: **Accept** and **Dismiss**.
4. A **View reasoning** disclosure reveals the copilot's rationale (collapsed by default).
5. **Accepting an AI suggestion creates a ProposedChange that requires normal approval flow.** It does not become a Human Override immediately. The ProposedChange enters the same review and approval path as any other ProposedChange.
6. Dismissal is logged but carries no audit weight beyond the event.

The copilot never auto-applies proposals. It does not determine canonical readiness edges, rankings, or gates. See [AI Governance](../security/ai-governance.md) for bounds on what the copilot may propose.

---

## 4. Progressive Disclosure

Work Frontier follows a **calm, action-first** progressive disclosure model. Every screen leads with what the user should do next, not what the system knows.

### 4.1 Disclosure Levels

| Level | Name | What Appears | When |
|-------|------|-------------|------|
| L1 | **Action surface** | Recommended Next, Program name, readiness status, next step | Always. First render. |
| L2 | **Working detail** | WorkItem list, authority badges, freshness indicators, copilot proposals | On focus or when the Program is active. No click required. |
| L3 | **Rich context** | Full WorkItem detail, evidence list, decision rationale, blocking chain | On demand (expand, click, keyboard shortcut). |
| L4 | **Administrative** | Program settings, Connection management, Policy configuration | Behind explicit "Settings" or "More" action. |

### 4.2 Disclosure Rules

| Rule | Description |
|------|-------------|
| PD-01 | L1 never requires scrolling on any viewport ≥ 320px wide. |
| PD-02 | L2 content is visible "above the fold" on a 768px viewport without scrolling. |
| PD-03 | L3 content replaces or overlays L2; it never destroys L1. |
| PD-04 | L4 is never exposed to users without the required permission (see [Authorization](../security/authorization.md)). |
| PD-05 | Empty states at every level carry a single, clear next action, not a list of possibilities. |
| PD-06 | On narrow viewports (< 768px), L2 and L3 collapse into a single scrollable column with sticky action bar. |

### 4.3 Information Density

- **Default density**: Comfortable. Adequate whitespace, 16px body text, clear visual grouping.
- **Compact density**: Available via user preference. Reduces spacing and font size by one step. Never removes decision type labels or action buttons.
- **No density setting ever hides**: decision types, action affordances, status indicators, or accessibility landmarks.

---

## 5. Authority and Freshness Indicators

Users must always know whether the data they see is current, who holds authority for it, and whether that authority is trustworthy.

### 5.1 Authority Statuses

Every authority determination carries one of five statuses. The UI must make the status visually distinct and always visible.

| Status | Label | Visual Treatment | What It Means |
|--------|-------|-----------------|---------------|
| **Authoritative** | `Authoritative` | Solid border, neutral fill, shield icon | A human, policy, or computed path determined this. The system treats this as the current truth. |
| **Provisional** | `Provisional` | Dotted border, subtle tint, draft icon | Not yet verified. This data was imported, computed under degraded conditions, or proposed but not approved. Provisional is **not** synonymous with AI-generated. Any unverified source produces provisional status. |
| **Stale** | `Stale` | Amber text badge next to timestamp | The authority determination is older than its freshness threshold (configurable per Policy, default 24h). The data may still be correct, but the system cannot vouch for its currency. |
| **Conflicted** | `Conflicted` | Red left-border accent, "Conflict" badge | Two or more sources disagree about this item. The user must resolve the conflict. The system does not pick a winner. |
| **Unavailable** | `Unavailable` | Grayed-out card, "Source unreachable" label | The upstream source (Connection, API, check) is unreachable. The last-known state is displayed but marked unavailable. |

### 5.2 Staleness Indicators

| Indicator | Trigger | Visual |
|-----------|---------|--------|
| `Stale` | Evidence or authority determination older than the freshness threshold (configurable per Policy, default 24h) | Amber text badge next to the timestamp. |
| `Outdated` | Data contradicts a newer source (e.g., GitHub check status changed since last sync) | Grayed-out card with "Superseded" banner. |
| `Refreshing` | Background sync in progress | Subtle pulse animation on the data region. |

### 5.3 Staleness Rules

| Rule | Description |
|------|-------------|
| SP-01 | Stale data is never silently refreshed. The user must trigger a refresh or acknowledge staleness. |
| SP-02 | Provisional content is never treated as authoritative for readiness assessments. |
| SP-03 | All authority statuses appear in the same visual tier. No status is de-emphasized by default. |
| SP-04 | Exported or shared readiness data carries authority status and freshness metadata in the output. |
| SP-05 | A source change during a draft (e.g., GitHub issue updated while user reviews the draft) invalidates the draft. The user must re-sync before proceeding. |

---

## 6. Cross-References

| Document | Section | Relevance |
|----------|---------|-----------|
| [Authorization](../security/authorization.md) | §2 Roles, §3 Resource Scope | Controls which views and actions a user can access. |
| [AI Governance](../security/ai-governance.md) | §2 Copilot Bounds | Defines what the copilot may and may not propose in Builder. |
| [Tenancy & Isolation](../security/tenancy-isolation.md) | §2 Data Isolation | Determines readiness data visibility boundaries across tenants. |
| [Threat Model](../security/threat-model.md) | §2.3 Injection Attacks | Constrains copilot UI treatment for untrusted content. |
| [Accessibility](ux-accessibility-design-system.md) | Full document | Mandatory for all views, decision displays, and disclosure patterns. |

---

## 7. Additional Rules

| Rule | Description |
|------|-------------|
| NR-01 | **No manual "mark Ready" shortcut.** Readiness is computed deterministically from the current snapshot, policy, gates, evidence, and overrides. Humans change inputs through authorized actions; they do not directly set the computed readiness result. |
| NR-02 | **Claims are coordination leases.** A claim on a WorkItem is a temporary, visible lease that signals intent to work. Claims expire, can be revoked, and do not imply exclusive ownership. Other participants always see who holds a claim. |
| NR-03 | **Only authoritative-ready work is claimable.** Recommended Next is the primary claim action, but another ready WorkItem may be claimed when its latest decision is authoritative and policy permits; the UI records why the user diverged from the recommendation. |
