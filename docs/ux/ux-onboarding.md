---
title: Work Frontier — Onboarding, Import, and Activation
id: WF-UX-005
version: 2.0.0
status: canonical
owner: UX Architecture
last_updated: "2026-07-12"
replaces: 1.0.0
supersedes: null
---

# Onboarding, Import, and Activation Specification

> **Purpose**: Defines the first-use experience — from GitHub App installation through ingestion analysis, simulated frontier, explicit activation, and authoritative reconciliation. Every new user reaches a working Builder view with at least one Program within their first 10 minutes.

---

## 1. Onboarding Principles

1. **Show the frontier, not a tutorial.** The user sees a simulated view of what their readiness frontier will look like before committing.
2. **One decision at a time.** Onboarding never asks the user to configure more than one thing before showing progress.
3. **Safe defaults where valid.** Optional mapping choices may use reviewed defaults; profile selection, conflict review, activation, and reconciliation cannot be skipped.
4. **Resumable.** If a user leaves mid-onboarding and returns later, they pick up exactly where they left off, not from the start.
5. **Explicit activation.** The system does not become authoritative until the user explicitly activates it. Before activation, everything is simulated.
6. **Role-blind entry.** All users see the same onboarding regardless of eventual role. Role-specific surfaces (Coordinator, Executive, Operator) reveal themselves naturally when the user navigates to them.

---

## 2. Onboarding Flow

### 2.1 Step 1: GitHub App Installation

The user installs the Work Frontier GitHub App on their organization or personal account.

| Action | Detail |
|--------|--------|
| Entry point | "Get started" button on the Work Frontier landing page, or direct link from documentation. |
| GitHub flow | Standard GitHub App installation: select organization, grant repository access (all repos, selected repos, or public repos only). |
| Permissions requested | Installation permission preview includes Issues read/write (managed #539 projection), pull requests read, checks/statuses read, and metadata read. Write access is never exercised before projection ownership is explicitly approved. |
| Completion | GitHub redirects back to Work Frontier with an installation token. |

**Requirement WF-UX-005-01**: GitHub App installation takes ≤ 3 clicks after GitHub authentication. No Work Frontier account creation is required before installation.

### 2.2 Step 2: Repository Selection

The user selects which repositories to ingest into Work Frontier.

| Action | Detail |
|--------|--------|
| Repo list | Repositories where the GitHub App is installed, displayed as a selectable list. |
| Selection | User selects one or more repositories. "Select all" shortcut available. |
| Preview | For each selected repo, a summary: number of open issues, open PRs, CI checks, and labels that suggest readiness concerns (e.g., "blocked", "needs-review"). |

**Requirement WF-UX-005-03**: Repository selection shows a live preview of what will be ingested. The user sees exactly what the system found before confirming.

### 2.3 Step 3: Profile Selection

The user chooses or confirms the readiness profile that governs how ingested data is interpreted.

| Action | Detail |
|--------|--------|
| Profile detection | The system examines repository labels, CI configuration, and issue templates to suggest a profile (e.g., "GitHub Projects with CI", "Manual issues only"). |
| Profile selection | The user selects a profile from a list: suggested profiles first, then generic options. |
| Profile preview | The user sees which readiness signals the profile will look for, and which signals it will ignore. |

A profile determines: which GitHub signals map to which readiness concerns, what evidence types are auto-collected, and what blocking relationships the system infers.

**Requirement WF-UX-005-15**: Profile selection is required before draft generation. The user cannot skip this step.

### 2.4 Step 4: Draft Normalized Snapshot

The system ingests data from selected repositories under the chosen profile and produces a draft snapshot: a proposed set of Programs and WorkItems.

| Action | Detail |
|--------|--------|
| Ingestion | The system reads issues, PRs, check statuses, and labels from GitHub. This is a read-only operation. |
| Normalization | The system maps GitHub signals to readiness concerns using the selected profile. It proposes Programs (grouped by initiative or release) and WorkItems (individual requirements). |
| Snapshot output | A draft set of Programs and WorkItems is produced. This draft is clearly labeled as "Draft" and carries `Provisional` status per [UX Architecture §5](ux-architecture.md#5-authority-and-freshness-indicators). |
| Source tracking | Each draft item records which GitHub source (issue, PR, check) it was derived from. |

**Requirement WF-UX-005-04**: Draft generation completes within 2 minutes for repositories with ≤ 1,000 open issues. A progress indicator is shown.

**Requirement WF-UX-005-05**: The draft is clearly labeled as "Draft — not yet active." The system is not authoritative until explicit activation.

**Requirement WF-UX-005-16**: The system does not infer Programs without a proposal. Every Program in the draft must be traceable to at least one GitHub source or a user-created entry. No phantom Programs appear.

**Requirement WF-UX-005-17**: Source change invalidates draft. If a GitHub source changes (issue closed, PR merged, check status updated) after the draft is generated but before activation, the affected draft items are marked `Stale`. The user must re-sync the draft before proceeding to activation.

### 2.5 Step 5: Inspect Coverage, Conflicts, and Gates

Before simulating the frontier, the user reviews the draft for completeness and conflicts.

| Action | Detail |
|--------|--------|
| Coverage view | For each Program, the user sees: how many WorkItems were generated, evidence coverage (how many have auto-collected evidence), and any gaps (WorkItems with no source). |
| Conflicts view | The system highlights: WorkItems that overlap or contradict each other, Programs that share WorkItems, and any items the profile could not confidently classify. |
| Gate preview | The user sees which activation gates (see §4) are already met and which remain. |
| Editing | The user can propose modifications to the draft: rename, merge, or delete draft Programs and WorkItems. Edits are tracked as ProposedChanges, not direct mutations. No editable canonical relationships exist without a proposal. |

**Requirement WF-UX-005-18**: Coverage, conflicts, and gates are displayed on a single screen. The user does not need to navigate between separate views.

**Requirement WF-UX-005-19**: Proposed modifications to the draft (renames, merges, deletions) are tracked as ProposedChanges with `Provisional` status. They are not applied until activation.

### 2.6 Step 6: Simulated Frontier

The user sees a preview of what their readiness frontier will look like.

| Action | Detail |
|--------|--------|
| Simulated Builder | A read-only version of the Builder view, populated with the draft Programs and WorkItems (with any approved modifications). |
| What next | The system shows what it would recommend as the first action, with a "Why?" explanation. |
| Authority indicators | Each proposed WorkItem carries an authority status per [UX Architecture §5](ux-architecture.md#5-authority-and-freshness-indicators). All items show `Provisional` at this stage. |

**Requirement WF-UX-005-06**: The simulated frontier is fully interactive (scrollable, expandable, filterable) but all data is a preview. Nothing is authoritative yet.

### 2.7 Step 7: Workspace Setup

After reviewing the simulated frontier, the user sets up the workspace that will own the authoritative data.

| Action | Detail |
|--------|--------|
| Workspace name | Single field: "What should we call your workspace?" Default: derived from the GitHub organization name. |
| User identity | If SSO/OAuth is configured, the user authenticates through their provider. If self-hosted without SSO, the user sets an email and password. |
| Completion | Workspace is created. The simulated frontier is associated with it. |

**Requirement WF-UX-005-02**: Workspace name is editable at any time from settings. Changing it does not affect readiness data.

### 2.8 Step 8: Explicit Activation

The user explicitly activates Work Frontier, making it authoritative.

| Action | Detail |
|--------|--------|
| Confirmation | A single screen: "Ready to activate? Work Frontier will start tracking readiness for [N] Programs with [M] WorkItems." |
| Activation action | Single button: **Activate**. A secondary action: **Review again**. |
| Post-activation | Activation records intent and starts full reconciliation. The draft remains non-authoritative until reconciliation succeeds. |

**Requirement WF-UX-005-07**: Activation requires a single, explicit action. There is no auto-activation based on time or activity.

**Requirement WF-UX-005-08**: Before activation, the user sees a summary of what will become authoritative: Programs, WorkItems, Connections, and the initial Policy configuration.

### 2.9 Step 9: Authoritative Reconciliation

After activation, the system performs a full authoritative reconciliation: confirming that its understanding of readiness matches the current state of GitHub.

| Action | Detail |
|--------|--------|
| Reconciliation | The system re-reads GitHub data and compares it to the ingested state. Any discrepancies are flagged. |
| Discrepancies | If GitHub data changed during onboarding (e.g., an issue was closed), the system shows a "Reconciliation needed" indicator on affected WorkItems. |
| Resolution | The user reviews discrepancies and confirms the authoritative state. Auto-resolution is available for minor changes (e.g., issue title updated). |

**Requirement WF-UX-005-09**: Reconciliation is automatic for the first pass. The user only needs to intervene for ambiguous discrepancies.

**Requirement WF-UX-005-10**: Only after reconciliation succeeds does the Builder become fully operational and publish the first authoritative Recommended Next.

---

## 3. Post-Onboarding State

After onboarding completes:

- The user is in **Builder** view with at least one Program.
- The **GitHub App Connection** is active and syncing.
- **WorkItems** are populated from the ingested data.
- **Policies** are set to defaults (configurable by Policy Administrator or Tenant Administrator).
- The **copilot** is available for explanations and proposals (see [AI Governance](../security/ai-governance.md)).
- **Activation gates** (see §4) begin tracking.
- All WorkItems carry authority status per [UX Architecture §5](ux-architecture.md#5-authority-and-freshness-indicators).

---

## 4. Activation Gates

An activation gate is a checkpoint that must be passed before certain capabilities unlock. Gates are not arbitrary; they protect users from misconfiguration that would cause downstream failures.

### 4.1 Gate List

| Gate | What It Unlocks | How to Pass |
|------|----------------|-------------|
| **Workspace created** | Program creation | Complete onboarding step 7. |
| **GitHub App installed** | Repository ingestion, Connection management | Complete onboarding step 1. |
| **First Program activated** | Copilot proposals, What next | Complete onboarding step 8. |
| **First WorkItem claimed** | Coordinator view, team assignment | Claim at least one WorkItem. |
| **First evidence collected** | Evidence feed, freshness tracking | Collect evidence on at least one WorkItem. |
| **Team member invited** | Coordinator view, bulk actions | Invite at least one other user. |

### 4.2 Gate Display Rules

| Rule | Description |
|------|-------------|
| AG-01 | Gates appear as a checklist in the bottom-right corner of Builder, collapsible. |
| AG-02 | Each gate shows its current status: completed (checkmark), available (action link), or locked (grayed, with reason). |
| AG-03 | Completed gates are never re-shown. The checklist shrinks as gates pass. |
| AG-04 | Locked gates show one line explaining why they're locked, not a link to documentation. |
| AG-05 | Gates are never enforced by hiding unrelated functionality. They only gate the specific capability listed above. |

---

## 5. Re-Onboarding and Reconnection

### 5.1 GitHub App Reinstallation

If the GitHub App is uninstalled or loses access:

| Step | User Experience |
|------|----------------|
| Detection | Operator view shows the Connection as "Disconnected." Builder shows a banner: "GitHub App disconnected. Reconnect to resume sync." |
| Reconnection | Single action: **Reconnect**. Standard GitHub App installation flow. |
| Post-reconnect | Reconciliation runs automatically (see §2.7). Discrepancies are flagged. |

### 5.2 Adding New Repositories

| Step | User Experience |
|------|----------------|
| Entry | Connection settings: **Add repository**. |
| Selection | Same as onboarding step 3: repo list, selection, preview. |
| Ingestion | New data is ingested and merged into existing Programs/WorkItems. |
| Reconciliation | New WorkItems are reconciled against existing state. |

---

## 6. Localization of Onboarding

| Requirement | Description |
|-------------|-------------|
| WF-UX-005-11 | Onboarding text is fully localizable. No hardcoded English strings in the UI layer. |
| WF-UX-005-12 | CJK layouts tested: onboarding forms render correctly at 2x text expansion (Japanese) and vertical text flow (where applicable). |
| WF-UX-005-13 | Date/time pickers in onboarding use the user's locale, not a hardcoded format. |
| WF-UX-005-14 | Right-to-left (RTL) layouts are supported for Arabic and Hebrew locales in all onboarding steps. |

---

## 7. Cross-References

| Document | Section | Relevance |
|----------|---------|-----------|
| [UX Architecture](ux-architecture.md) | §2.1 Builder View | Default landing after onboarding. |
| [UX Architecture](ux-architecture.md) | §5 Authority and Freshness | Authority statuses and draft invalidation rules. |
| [Authorization](../security/authorization.md) | §2 Roles | Role assignment after workspace creation. |
| [Authorization](../security/authorization.md) | §5 Break-Glass | Emergency access during onboarding lockdown. |
| [AI Governance](../security/ai-governance.md) | §2 Copilot Bounds | Copilot availability post-onboarding. |
| [Accessibility](ux-accessibility-design-system.md) | §3 Keyboard/Screen Reader | Mandatory for all onboarding forms. |
| [Data Governance](../security/tenancy-isolation.md) | §4 Retention | Ingested data retention policies. |
