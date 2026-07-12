---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-PROD-02
---

# Users, Jobs-to-Be-Done, and Non-Goals

**WF-PROD-02**: Work Frontier serves specific users with specific jobs. Anything outside this scope is explicitly a non-goal.

## Users

### Builders

Developers, engineers, and individual contributors who do the work. They use Work Frontier to know what to work on next and to understand dependency context.

**Characteristics:**
- Work across multiple repositories or projects.
- Use GitHub Issues, Linear, or similar as their primary tracker.
- Have 20 to 500+ open items at any time.
- Make most prioritization decisions alone or within a small team.
- Spend 10 to 30 minutes per day figuring out what to work on.

### Coordinators

Tech leads and engineering managers who need visibility across a team's work. They use Work Frontier to understand the team's landscape and suggest where each person should focus, without imposing heavy process.

**Characteristics:**
- Manage 2 to 20+ contributors, each with their own focus area.
- Need cross-person visibility but respect individual autonomy.
- Use [Recommended Next](../domain/recommended-next.md) recommendations as conversation starters, not mandates.
- Care about dependency chains and blocked work more than individual item priority.

### Executives

Leaders who need portfolio-level visibility. They use Work Frontier's [Program](../domain/program.md) rollups and the typed containment DAG to understand aggregate status across multiple Programs and teams, without drilling into individual WorkItems.

**Characteristics:**
- Want aggregate status, not individual item detail.
- Use Program rollups and portfolio views.
- Care about cross-team blockers and capacity.
- Need confidence that work is progressing, not micromanagement of tasks.

### Operators

People who maintain Work Frontier itself: deployment, configuration, monitoring, incident response. They configure [TrackerConnections](../domain/tracker-connection.md), tune [completion policies](../domain/lifecycle-and-completion.md#completion), manage [authority](../domain/authority-statuses.md) settings, and ensure the system stays healthy.

**Characteristics:**
- Configure tracker integrations and status mappings.
- Monitor system health, sync freshness, and connection status.
- Manage override TTLs, lease durations, and policy parameters.
- Respond to incidents and degrade gracefully.

### Policy and Tenant Admins

Administrators who set rules for how Work Frontier operates within their organization. They define safety constraints, completion policies, authorization rules, and tenancy boundaries.

**Characteristics:**
- Set global or per-Program policies (safety gates, completion requirements).
- Manage authorization: who can override, who can claim, who can archive.
- Configure tenancy isolation and data access rules.
- Audit decision history and override logs.

## Jobs-to-Be-Done

### Job 1: "Tell me what to do next"

The core job. The user has context-switched away from a project and needs to resume. They open the Control Room and want a single, justified [Recommended Next](../domain/recommended-next.md) within 30 seconds. The recommendation must include enough context that the user does not need to read the original tracker item to understand why it was ranked first.

**Trigger:** Returning to work after context switch, start of day, post-meeting recovery.
**Success:** User acts on the recommendation without further investigation.

### Job 2: "Show me what's blocked and why"

The user wants to understand the dependency landscape. Which [WorkItems](../domain/work-item.md) are waiting on other items? Which `blocks` edges are the highest-leverage to unblock? This job produces a view, not a single recommendation.

**Trigger:** Planning session, identifying bottlenecks, preparing for a focus period.
**Success:** User can identify the top 3 bottlenecks and take action on at least one.

### Job 3: "Help me decide between competing priorities"

Two items are both ready and both seem important. The user needs help breaking the tie. Work Frontier presents evidence for each side: [authority statuses](../domain/authority-statuses.md), dependency fan-out, age, and any overrides the user has previously made.

**Trigger:** Competing ready items with similar apparent priority.
**Success:** User makes a faster, more confident decision than they would have without the tool.

### Job 4: "Keep my tracker state honest"

The user suspects their tracker has drifted from reality. Items marked "in progress" that nobody is actually working on. Items marked "done" that still have unresolved sub-tasks. Work Frontier surfaces these discrepancies as [AttentionItems](../domain/attention-items.md).

**Trigger:** Periodic review, pre-release checklist, onboarding a new team member.
**Success:** User identifies and resolves at least one stale state discrepancy.

### Job 5: "Show me the big picture"

The user needs aggregate visibility across Programs and the portfolio. They want to see status rollups, cross-team blockers, and capacity distribution without drilling into individual items.

**Trigger:** Executive review, portfolio planning, cross-team coordination.
**Success:** User understands aggregate status and can identify where to focus attention at the portfolio level.

### Job 6: "Enforce our quality and safety rules"

The policy admin needs to ensure that WorkItems cannot bypass quality gates or safety constraints. They configure completion policies, gate requirements, and override constraints, then audit the decision history to verify compliance.

**Trigger:** Compliance review, audit preparation, policy update.
**Success:** Policy is enforced consistently across all WorkItems, with full audit trail.

## Non-Goals

| Non-Goal | Why it's excluded |
|----------|-------------------|
| Tracker replacement | Work Frontier reads from and suggests to trackers. The tracker is the system of record. |
| Workflow enforcement | Work Frontier does not define or enforce workflows. It works with whatever workflow the tracker uses. |
| Sprint/iteration planning | Work Frontier ranks by readiness and priority, not by time-boxed iteration. |
| Time tracking | Work Frontier does not track how long items take or estimate effort. |
| Resource allocation | Work Frontier does not assign people to work or manage capacity. |
| Generic business intelligence | Work Frontier provides readiness rollups and auditable exports, but it does not replace a general-purpose analytics platform. |
| Code generation | Work Frontier is a readiness control plane, not a coding assistant. |
| Collaboration features | Work Frontier does not host comments, threads, or real-time editing. |
| AI autonomy | AI has bounded scope. It never makes decisions, changes state, or acts without human confirmation. |
| AI-driven ranking | The [ranking pipeline](../domain/readiness-ranking.md#ranking) is deterministic and lexicographic. No AI model influences ranking. |
