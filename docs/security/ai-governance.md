---
title: Work Frontier — Bounded AI Governance
id: WF-SEC-003
version: 2.0.0
status: canonical
owner: Security Architecture
last_updated: "2026-07-12"
replaces: 1.0.0
supersedes: null
---

# Bounded AI Governance Specification

> **Purpose**: Defines the constraints, trust boundaries, and operational rules for AI components in Work Frontier. AI is a suggestion engine, not a readiness authority. Every AI output requires human judgment before it becomes a Decision.

---

## 1. AI Governance Principles

1. **AI explains and proposes, never decides.** No AI output becomes a Decision without explicit human acceptance. AI does not determine canonical readiness edges, rankings, or gates.
2. **AI-disabled is a first-class mode.** Work Frontier's core readiness functions work fully without AI. AI enhances; it never gates.
3. **AI data is workspace-scoped.** Copilot interactions never leave the workspace that generated them.
4. **AI is transparent.** Users can always see what the AI proposed, why, and who accepted or rejected it.
5. **AI is bounded.** The copilot's capabilities are defined by an allowlist, not a blocklist. Everything not explicitly allowed is forbidden.

---

## 2. Copilot Bounds

### 2.1 What the Copilot May Do

The copilot operates strictly in the domain of **explanations** and **ProposedChanges**. It does not create canonical data structures or make readiness determinations.

| Capability | Condition | Human Required |
|-----------|-----------|----------------|
| **Explain** why a WorkItem is recommended next | Based on authority, freshness, blocking relationships, and evidence status | No (informational) |
| **Explain** what a Decision means | Based on the Decision's provenance (human, policy, or computed) | No (informational) |
| **Explain** what evidence is missing or stale | Based on the WorkItem's evidence requirements and freshness | No (informational) |
| **Propose** a change to a WorkItem's status | Based on evidence analysis | Accept or dismiss |
| **Propose** a new Policy rule | Based on patterns in readiness data | Accept or dismiss (Policy Administrator or Tenant Administrator only) |
| **Propose** an evidence association | Based on matching evidence to WorkItem requirements | Accept or dismiss |
| **Answer** questions about Program readiness | Based on WorkItems, Decisions, and Evidence in the current Program | No (read-only, informational) |
| **Summarize** readiness status and trends | Based on Program data and Decision history | No (read-only, informational) |

### 2.2 What the Copilot May NOT Do

| Prohibition | Rationale |
|-------------|-----------|
| Auto-apply ProposedChanges without user acceptance | Violates the human-in-the-loop principle. |
| Create, modify, or delete Programs, WorkItems, or Decisions directly | These are readiness actions that require explicit user intent or policy firing. |
| Determine canonical readiness edges (blocking relationships) | Readiness edges are defined by Policies and human configuration, not by AI. |
| Rank or prioritize WorkItems | Prioritization is a human or policy decision. AI can explain why something is recommended; it cannot set the recommendation as the canonical order. |
| Fire Policy rules | Policies are deterministic. AI may propose a new Policy, but it cannot fire one. |
| Set or modify readiness gates | Gates are defined by Policies. AI cannot create, modify, or bypass gates. |
| Access data from other workspaces | Workspace isolation applies to AI, same as to humans. |
| Access user PII (name, email) | Copilot interactions are keyed by user_id only. See [Data Governance §3.3](tenancy-isolation.md#33-pii-handling). |
| Access Connection credentials (tokens, keys) | Credentials are encrypted and never passed to AI context. |
| Perform sync or reconciliation | These are Operator-scope actions with infrastructure implications. |

### 2.3 Copilot Trust Boundary

The copilot operates within a strict trust boundary:

```
┌───────────────────────────────────────────────────┐
│ Copilot Trust Boundary                             │
│                                                    │
│  Input (read-only):                                │
│    - Current Program's WorkItems                   │
│    - Current Program's Decisions                   │
│    - Current Program's Evidence                    │
│    - Current Program's Policies                    │
│    - User's query or prompt                        │
│                                                    │
│  Output:                                           │
│    - Explanation (informational, read-only)        │
│    - ProposedChange (requires human acceptance)    │
│                                                    │
│  Never crosses boundary:                           │
│    - Other workspaces' data                        │
│    - User PII                                     │
│    - Credentials                                  │
│    - System configuration                          │
│    - Authorization decisions                       │
│    - Canonical readiness edges or rankings         │
│    - Policy firing or gate execution               │
└───────────────────────────────────────────────────┘
```

### 2.4 Copilot UI Rules

| Rule | Description |
|------|-------------|
| AI-01 | Every copilot ProposedChange carries the `AI suggestion` visual treatment per [UX Architecture §3.1](../ux/ux-architecture.md#31-decision-types). |
| AI-02 | ProposedChanges are never auto-accepted. Two explicit actions are always present: **Accept** and **Dismiss**. |
| AI-03 | "View reasoning" disclosure is available for every ProposedChange, collapsed by default. |
| AI-04 | Copilot responses carry a "This is an AI suggestion, not a readiness determination" disclaimer in the UI. |
| AI-05 | When the copilot is unavailable (service down, rate limited), the Builder remains fully functional. A subtle status indicator shows "Copilot offline." |
| AI-06 | ProposedChanges that the provider's safety abstraction has flagged carry a `Degraded` indicator per [UX Architecture §3.1](../ux/ux-architecture.md#31-decision-types). |
| AI-07 | **Accepting an AI suggestion creates a ProposedChange that requires normal approval flow.** It does not immediately become a Human Override. The ProposedChange enters the same review path as any other ProposedChange, governed by [Authorization](authorization.md). |

---

## 3. AI-Disabled Core Function

Work Frontier must be fully functional with AI components disabled. This is not a theoretical requirement; it is a tested configuration.

### 3.1 Core Functions Without AI

| Function | AI-Dependent? | Behavior When AI Disabled |
|----------|--------------|--------------------------|
| View Recommended Next | No | Works identically. Recommendation is based on authority, freshness, and blocking — no AI. |
| Claim a WorkItem | No | Works identically. |
| Collect evidence | No | Works identically. |
| Advance a WorkItem to Ready | No | Works identically. |
| View Decisions | No | Works identically. Only computed and policy Decisions appear. No ProposedChanges. |
| Accept/reject Decisions | No | Works identically for computed and policy Decisions. |
| View Coordinator / Executive / Operator | No | Works identically. |
| Copilot ProposedChanges | Yes | Hidden. No placeholder or error. The proposal area simply does not appear. |
| Copilot explanations | Yes | Hidden. No placeholder. |

### 3.2 AI-Disabled Mode Rules

| Rule | Description |
|------|-------------|
| AI-D-01 | The system starts and operates correctly with AI endpoints unreachable or unconfigured. |
| AI-D-02 | No error messages, warnings, or degraded states are shown when AI is disabled. The UI is clean, not apologetic. |
| AI-D-03 | All automated tests run in two modes: AI-enabled and AI-disabled. |
| AI-D-04 | AI-disabled mode is the default for self-hosted deployments until the administrator configures an AI endpoint. |
| AI-D-05 | Readiness assessment completion is never blocked by AI unavailability. |

---

## 4. Purpose-Limited Retention for AI Data

### 4.1 What AI Data Is Retained

| Data Type | Default Retention | Configurable | Purpose |
|-----------|-----------------|--------------|---------|
| **Copilot prompts** (user queries to the copilot) | 90 days (configurable per [Data Governance §4.1](tenancy-isolation.md#41-retention-periods)) | Yes (Policy Administrator can set 0 to 365 days) | Copilot experience improvement within the workspace. AI providers may retain data per their own policy. |
| **Copilot responses** (explanations, ProposedChanges) | 90 days (configurable) | Yes (same range) | Same as above. |
| **Acceptance/rejection events** | Indefinite (tied to WorkItem lifecycle) | No | Audit trail. Determines whether a Decision was human or AI-initiated. |
| **Copilot model metadata** (model version, latency, token count) | 30 days | Yes (Policy Administrator can set 7 to 90 days) | Operational monitoring. No user content. |

AI providers may have their own data retention policies independent of Work Frontier's configuration. Work Frontier does not control provider-side retention. Users and administrators should review their provider's data handling documentation.

### 4.2 Purpose Limitation Rules

| Rule | Description |
|------|-------------|
| PL-01 | Copilot interaction data is never used to train or fine-tune AI models. |
| PL-02 | Copilot interaction data is never shared across workspaces, even in aggregated or anonymized form. |
| PL-03 | Copilot interaction data is never used for user profiling, performance evaluation, or behavioral analysis. |
| PL-04 | Copilot interaction data is subject to the same encryption-at-rest and transit requirements as Confidential data per [Data Governance §3.2](tenancy-isolation.md#32-data-handling-rules). |
| PL-05 | When a user's account is deleted, their copilot interaction data is purged within 30 days. |

---

## 5. AI Safety Layers

### 5.1 Input Filtering

| Layer | Description | Enforcement |
|-------|-------------|-------------|
| **Prompt injection detection** | Inputs that attempt to override copilot behavior, extract system prompts, or bypass trust boundaries are detected and blocked. | Automated. Blocked inputs return a standard "I can't help with that" response. No error details are leaked. |
| **PII scrubbing** | User PII (name, email) is scrubbed from prompts before they reach the AI model. | Automated. PII is replaced with tokens (`[USER_NAME]`, `[USER_EMAIL]`). Tokens are restored in the response if needed for display. |
| **Content policy** | Prompts that request harmful, illegal, or policy-violating content are blocked. | Automated. Standard refusal response. |

### 5.2 Output Filtering

| Layer | Description | Enforcement |
|-------|-------------|-------------|
| **Schema validation** | Copilot outputs are validated against a defined schema (Zod or Pydantic). Outputs that do not match the expected structure are rejected. | Automated. Rejected outputs are replaced with "I can't provide that suggestion." The rejection event is logged. |
| **Provider safety abstraction** | The AI provider's own safety layer may flag outputs. These flags are surfaced as `Degraded` indicators per [UX Architecture §3.1](../ux/ux-architecture.md#31-decision-types). The system does not claim to understand the provider's safety model internals; it treats provider flags as opaque signals. | Automated. Flagged outputs carry a `Degraded` indicator. The user sees the indicator and can still accept or dismiss. |
| **Scope check** | ProposedChanges that would affect resources outside the current Program's scope are blocked. | Automated. The copilot never suggests changes to other Programs, workspace settings, or user permissions. |

### 5.3 AI Safety Rules

| Rule | Description |
|------|-------------|
| AI-S-01 | Safety layers are applied on every copilot interaction. There is no bypass path. |
| AI-S-02 | Safety layer failures are logged and trigger a `Degraded` indicator on the affected ProposedChange. |
| AI-S-03 | Safety layer configuration is workspace-scoped. Different workspaces may have different content policies. |
| AI-S-04 | Safety layer updates are deployed independently of the copilot model. A safety fix does not require a model change. |
| AI-S-05 | The system does not claim to understand or represent the AI provider's internal safety model. Provider safety flags are treated as opaque signals. No "safety model confidence" metric is displayed to users. |

---

## 6. AI Model Governance

| Rule | Description |
|------|-------------|
| AI-M-01 | The copilot model version is recorded on every ProposedChange. The UI shows "Powered by [model-name] v[version]" in the copilot panel. |
| AI-M-02 | Model changes (version updates, provider switches) require a security review per [Secure Development Lifecycle](secure-development-lifecycle.md). |
| AI-M-03 | Model performance metrics (latency, error rate, safety classification distribution) are monitored and alert on anomalies. |
| AI-M-04 | In self-hosted deployments, the administrator chooses the AI provider and model. Work Frontier does not phone home. |
| AI-M-05 | If the chosen AI provider is unreachable, the system enters AI-disabled mode per §3. |

---

## 7. Cross-References

| Document | Section | Relevance |
|----------|---------|-----------|
| [UX Architecture](../ux/ux-architecture.md) | §3 Decision Semantics | AI suggestion visual treatment defined here. |
| [UX Architecture](../ux/ux-architecture.md) | §3.3 Copilot Proposals in Context | Acceptance creates ProposedChange, not Human Override. |
| [Authorization](authorization.md) | §2 Roles, §4 Separation of Duties | Copilot user cannot be sole content reviewer. |
| [Tenancy & Isolation](tenancy-isolation.md) | §2 Data Isolation | AI data is workspace-scoped. |
| [Tenancy & Isolation](tenancy-isolation.md) | §4.3 Purpose Limitation | AI data purpose limitation details. |
| [Threat Model](threat-model.md) | §2.3 Injection Attacks | Prompt injection threat analysis. |
| [Threat Model](threat-model.md) | §2.6 Evidence and Content Integrity | AI-generated content trust model. |
| [SDL](secure-development-lifecycle.md) | §3 Security Testing | AI safety testing requirements. |
