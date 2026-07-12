---
title: Work Frontier — Authorization
id: WF-SEC-001
version: 2.0.0
status: canonical
owner: Security Architecture
last_updated: "2026-07-12"
replaces: 1.0.0
supersedes: null
---

# Authorization Specification

> **Purpose**: Defines the role-based access control model, resource scoping, separation of duties, and break-glass emergency procedures for Work Frontier. This spec applies equally to hosted and self-hosted deployments.

---

## 1. Authorization Principles

1. **Deny by default.** Every permission is denied unless explicitly granted. There are no implicit allows.
2. **Least privilege.** Users receive the minimum permissions needed for their role.
3. **Separation of duties.** No single role can both perform and approve the same action.
4. **Resource-scoped.** Permissions apply to specific resources, not globally.
5. **Auditable.** Every authorization decision is logged. Every break-glass use is logged and reviewed.

---

## 2. Roles

### 2.1 Role Definitions

| Role | Description | Default For |
|------|-------------|-------------|
| **Viewer** | Read-only access to readiness data within their scope. Can view Programs, WorkItems, Decisions, and evidence. Cannot modify, claim, or approve anything. | Stakeholders, auditors, external reviewers. |
| **Builder** | Works on readiness: claims WorkItems (creates coordination leases), collects evidence, proposes readiness state changes. Uses the Builder view. | All new users (in addition to Viewer permissions). |
| **Coordinator** | Manages team readiness: assigns WorkItems, resolves conflicts, views cross-Program blocked work. Uses the Coordinator view. | Team leads. |
| **Operator** | Manages sync health: monitors Connections, reconciles discrepancies, handles operational incidents. Uses the Operator view. | DevOps, SRE. |
| **Policy Administrator** | Creates, updates, and retires readiness Policies. Controls what "ready" means for Programs. Cannot assign roles or manage users. | Compliance leads, release managers. |
| **Tenant Administrator** | Manages users, roles, workspace settings, Connections, and break-glass procedures. The highest privilege level. Requires four-eyes for sensitive operations. | Organization admins. |

**Executive** is not a distinct role. It is an **adapted view/read capability** available to any user with read access to Programs. The Executive view projects readiness data as terminal outcomes and risk without exposing WorkItem-level editing or operational details. Users who need only Executive-level visibility are granted the Viewer role.

### 2.2 Role Assignment Rules

| Rule | Description |
|------|-------------|
| AUTH-01 | An actor may hold multiple resource-scoped role grants; effective capabilities are the union after deny rules, scope, source permission, and separation-of-duties checks. |
| AUTH-02 | Role grants never imply global scope. Every grant names Tenant, Organization, Workspace, Program, Repository, or Connection scope. |
| AUTH-03 | Role assignment requires Tenant Administrator approval. Users cannot self-assign. |
| AUTH-04 | The Tenant Administrator role requires **four-eyes** approval: one Tenant Administrator assigns, another Tenant Administrator confirms. |
| AUTH-05 | A single-user self-hosted deployment bootstraps one Tenant Administrator grant. Other scoped roles are assigned explicitly; multi-approver operations remain blocked unless an external approver or break-glass path is configured. |

---

## 3. Permission Matrix

### 3.1 Resource Scope

Permissions are scoped to six resource levels:

| Scope | Description | Examples |
|-------|-------------|---------|
| **Tenant** | The top-level multi-tenancy boundary. A tenant owns one or more organizations. | Tenant-wide settings, user roster across organizations. |
| **Organization** | A group of workspaces within a tenant. Maps to a GitHub organization. | Organization-wide Connection management, billing. |
| **Workspace** | The primary data boundary. All readiness data belongs to a workspace. | Settings, user roles, Policies, Connections. |
| **Program** | A readiness initiative within a workspace. | WorkItems, Decisions, Evidence. |
| **Repository** | A GitHub repository ingested into a workspace. Programs and WorkItems trace back to repositories. | Ingested issues, PRs, check statuses. |
| **Connection** | An integration that feeds readiness data (GitHub App, CI/CD, SSO). Scoped within a workspace. | GitHub tokens, webhook configurations. |

### 3.2 Permission Table

| Permission | Viewer | Builder | Coordinator | Operator | Policy Admin | Tenant Admin |
|------------|--------|---------|-------------|----------|-------------|-------------|
| **Program: create** | No | Yes | Yes | No | No | Yes |
| **Program: read** (member) | Yes | Yes | Yes | Yes | Yes | Yes |
| **Program: read** (all) | No | No | Yes | Yes | Yes | Yes |
| **Program: update** (member) | No | No | Yes (reassign) | No | No | Yes |
| **Program: update** (all) | No | No | Yes (reassign) | No | No | Yes |
| **Program: delete** | No | No | No | No | No | Yes (four-eyes) |
| **WorkItem: create** | No | Yes | Yes | No | No | Yes |
| **WorkItem: read** | Yes | Yes | Yes | Yes | Yes | Yes |
| **WorkItem: update** (own) | No | Yes | Yes (reassign) | No | No | Yes |
| **WorkItem: update** (all) | No | No | Yes (reassign) | No | No | Yes |
| **WorkItem: claim** | No | Yes | Yes | No | No | Yes |
| **WorkItem: submit for approval** | No | Yes | No | No | No | Yes |
| **Decision: create** | No | Yes | No | No | No | Yes |
| **Decision: override** | No | Yes | No | No | No | Yes (four-eyes) |
| **Decision: view history** | Yes | Yes | Yes | Yes | Yes | Yes |
| **Policy: read** | Yes | Yes | Yes | Yes | Yes | Yes |
| **Policy: create/update** | No | No | No | No | Yes | Yes |
| **Evidence: collect** | No | Yes | No | No | No | Yes |
| **Evidence: verify** | Yes | Yes | Yes | No | Yes | Yes |
| **Evidence: view** | Yes | Yes | Yes | Yes | Yes | Yes |
| **ProposedChange: accept/dismiss** | No | Yes | No | No | No | Yes |
| **ProposedChange: view** | Yes | Yes | Yes | Yes | Yes | Yes |
| **Copilot: use** (explanations/proposals) | No | Yes | No | No | No | Yes |
| **Connection: view** | No | No | No | Yes | No | Yes |
| **Connection: configure** | No | No | No | No | No | Yes (four-eyes) |
| **Connection: reconnect** | No | No | No | Yes | No | Yes |
| **Workspace: settings** | No | No | No | No | No | Yes |
| **User: invite** | No | No | No | No | No | Yes |
| **User: assign role** | No | No | No | No | No | Yes (four-eyes) |
| **Audit log: view** | No | No | No | Yes | No | Yes |
| **Break-glass: invoke** | No | No | No | No | No | Yes (see §5) |

### 3.3 Permission Check Rules

| Rule | Description |
|------|-------------|
| AUTH-06 | Permission checks occur on every API call, not just on UI rendering. |
| AUTH-07 | If a user's role changes mid-session, the next API call enforces the new role. Existing UI state is not retroactively locked; the user sees "Your access has changed" on next interaction. |
| AUTH-08 | Permission failures use typed, non-leaking responses. APIs may return 404 when revealing resource existence would leak cross-scope information; otherwise they return 403 with an actionable explanation. |
| AUTH-09 | Read permissions on a resource do not imply read permissions on that resource's children. Each level is checked independently. |

---

## 4. Separation of Duties

### 4.1 SoD Constraints

| Constraint | Rationale |
|------------|-----------|
| A user who claims a WorkItem cannot be the sole approver of its readiness Decision. | Prevents a single person from both doing the work and signing off on it. |
| A user who configures a Connection cannot be the sole operator who reconnects it. | Prevents a single person from both introducing and operating integrations. |
| A user who invites another user cannot assign that user a Tenant Administrator role without a second Tenant Administrator confirming. | Prevents privilege escalation through social engineering. **Four-eyes** principle. |
| The copilot user (who accepts ProposedChanges) cannot also be the sole reviewer of the same Program's readiness. | Prevents unchecked AI-generated proposals from affecting readiness assessments. |
| Policy Administrators cannot assign roles or manage users. | Separates policy authority from identity authority. |
| Tenant Administrators cannot create WorkItems directly without going through the normal proposal flow. | Prevents bypassing the readiness process. |

### 4.2 SoD Enforcement

| Rule | Description |
|------|-------------|
| SOD-01 | SoD constraints are enforced at the API layer, not just in the UI. |
| SOD-02 | SoD violations are logged as security events and visible in the audit log. |
| SOD-03 | Single-user self-hosted deployments do not silently waive SoD. Operations requiring multiple approvers remain unavailable unless an external approver is configured or the explicit break-glass flow is used and certified as reduced assurance. |

---

## 5. Break-Glass Procedure

Break-glass is an emergency mechanism that grants temporary elevated access when normal authorization paths are unavailable.

### 5.1 When Break-Glass Applies

| Scenario | Description |
|----------|-------------|
| All Tenant Administrators are locked out | No active Tenant Administrator account exists or can authenticate. |
| Connection failure cascade | No Operator can reach a failing Connection, and the failure affects production readiness assessments. |
| Security incident | An incident requires immediate access to audit logs or credential rotation. |

### 5.2 Break-Glass Mechanics

| Step | Description |
|------|-------------|
| 1 | An authorized user (any role) initiates break-glass from a dedicated entry point (not buried in settings). |
| 2 | The system requires **strong re-authentication**: the user must re-enter their password and complete a second factor (TOTP, WebAuthn, or email verification). |
| 3 | The system requires a reason (free text, min 20 characters). |
| 4 | The system requires confirmation: "You are invoking emergency access. This will be logged and reviewed." |
| 5 | Elevated access is granted for a **maximum of 2 hours** (short expiry). |
| 6 | All actions taken during break-glass are tagged with `break-glass` in the audit log. |
| 7 | After expiry, the user returns to their normal role. |
| 8 | A Tenant Administrator is notified immediately (email, push notification). |
| 9 | A **mandatory post-incident review** is triggered. The review must be completed within 48 hours. |

### 5.3 Break-Glass Rules

| Rule | Description |
|------|-------------|
| BG-01 | Break-glass grants **read access to all resources** in the workspace, plus the specific elevated permission needed. It does not grant blanket write access. |
| BG-02 | Break-glass cannot be used to assign roles, configure Policies, or delete Connections. |
| BG-03 | Break-glass invocations are limited to 2 per user per 24-hour period. |
| BG-04 | Every break-glass invocation triggers a mandatory post-incident review within 48 hours. The review is recorded in the audit log. |
| BG-05 | In self-hosted deployments, break-glass is available but the notification path falls back to the configured alert channel (email, webhook). |
| BG-06 | Break-glass actions are visible to all Tenant Administrators in real time during the elevated session. |

---

## 6. Connection Credentials

GitHub tokens and other integration credentials are managed under the Tenant Administrator role.

### 6.1 Credential Storage

| Rule | Description |
|------|-------------|
| IC-01 | Credentials are stored encrypted at rest (AES-256 or equivalent). |
| IC-02 | Credentials are never displayed in the UI after initial entry. A masked display (`ghp_****`) is shown. |
| IC-03 | Credentials are scoped to the minimum permissions required by the integration. |
| IC-04 | Credential rotation follows organization policy and provider capability; compromise or installation changes trigger immediate rotation. |
| IC-05 | Credentials are workspace-scoped. A credential in workspace A is not accessible from workspace B. |

### 6.2 Credential Access

| Rule | Description |
|------|-------------|
| IC-06 | Only scoped Tenant Administrators can create, view (masked), rotate, or delete Connection credentials. |
| IC-07 | The Operator role can view whether a credential is valid (green/yellow/red status) without seeing its value. |
| IC-08 | Credential access is logged in the audit log. |

---

## 7. Self-Hosted vs. Hosted Authorization

| Aspect | Hosted | Self-Hosted |
|--------|--------|-------------|
| Authentication | SSO/OAuth enforced. No local passwords. | SSO/OAuth optional. Local passwords allowed. |
| Role assignment | Tenant Administrator role requires four-eyes approval. | Bootstrap grants are explicit and audited; multi-approver operations remain unavailable until an external approver is configured or break-glass is invoked. |
| Break-glass | Strong reauth + email + push notification to all Tenant Administrators. | Strong reauth + configurable alert channel. |
| SoD enforcement | Fully enforced. | Enforced; explicitly declared reduced-assurance break-glass is the only exception. |
| Audit log | Retained per [Data Governance](tenancy-isolation.md). | Retained per local configuration. Must meet the same minimum retention. |
| Credential storage | Platform-managed encryption (AES-256). | Customer-managed encryption. Platform provides the encryption interface. |

### 7.1 Self-Hosted Single-User Safety

Single-user self-hosted deployments bootstrap one Tenant Administrator but must **never silently disable safety controls**:

| Control | Single-User Behavior |
|---------|---------------------|
| SoD constraints | Multi-approver action is blocked unless an external approver is configured or break-glass is invoked. |
| Break-glass | Available. Strong reauth and post-incident review still required. |
| Four-eyes on Tenant Admin assignment | Requires an external approver; break-glass may recover access but cannot silently create a permanent hidden superuser. |
| Audit logging | Always active. Cannot be disabled. |
| Credential display | Credentials remain masked in the UI regardless of role. |

---

## 8. Cross-References

| Document | Section | Relevance |
|----------|---------|-----------|
| [Tenancy & Isolation](tenancy-isolation.md) | §2 Data Isolation | Authorization scopes are enforced per tenant. |
| [AI Governance](ai-governance.md) | §2 Copilot Bounds | Copilot permissions are a subset of Builder permissions. |
| [Threat Model](threat-model.md) | §2 Threat Categories | Authorization bypass is a rated threat. |
| [Secure Development Lifecycle](secure-development-lifecycle.md) | §3 Security Testing | Authorization tests are part of the SDL. |
| [UX Architecture](../ux/ux-architecture.md) | §2 Views, §7 Additional Rules | Views are permission-gated per this spec. Claims are coordination leases. |
| [Critical Journeys](../ux/ux-critical-journeys.md) | §2 Claim Journey, §5 Coordinator Journey | Claiming and bulk actions require specific roles. |
