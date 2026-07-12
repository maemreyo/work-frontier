---
title: Work Frontier — Tenancy, Isolation, and Data Governance
id: WF-SEC-002
version: 2.0.0
status: canonical
owner: Security Architecture
last_updated: "2026-07-12"
replaces: 1.0.0
supersedes: null
---

# Tenancy, Isolation, and Data Governance Specification

> **Purpose**: Defines the multi-tenancy model, data isolation boundaries, data governance policies, and retention rules for Work Frontier. Applies to both hosted and self-hosted deployments.

---

## 1. Tenancy Model

### 1.1 Tenant Hierarchy

```
Installation (self-hosted: one org; hosted: one or more orgs)
 ├── Tenant (the top-level multi-tenancy boundary)
 │    ├── Organization (maps to a GitHub organization)
 │    │    ├── Workspace (the primary data boundary)
 │    │    │    ├── Users (members with roles)
 │    │    │    ├── Programs (readiness initiatives)
 │    │    │    │    ├── WorkItems (readiness requirements)
 │    │    │    │    ├── Decisions (authority determinations)
 │    │    │    │    ├── Evidence (proof of readiness)
 │    │    │    │    └── ProposedChanges (suggestions)
 │    │    │    ├── Repositories (ingested GitHub repos)
 │    │    │    ├── Connections (GitHub App, CI/CD, SSO)
 │    │    │    ├── Policies (readiness rules)
 │    │    │    └── Audit log (operational and authorization events)
 │    │    └── (additional workspaces)
 │    └── (additional organizations)
 └── (additional tenants)
```

### 1.2 Tenant Boundary Rules

| Rule | Description |
|------|-------------|
| TEN-01 | A workspace is the strictest data isolation boundary. Data in workspace A is never accessible from workspace B, period. |
| TEN-02 | Cross-workspace data access is denied by mandatory database RLS, transaction-local workspace context, API authorization, and cache/object/job namespaces. |
| TEN-03 | A user may belong to multiple workspaces. Their session is scoped to one workspace at a time. Switching workspaces terminates the current session context. |
| TEN-04 | Hosted tenants may share managed database infrastructure, never data scope: RLS, encryption keys, cache/object/job/inbox/audit namespaces, and backup/restore controls remain tenant/workspace-scoped. Dedicated infrastructure is an optional deployment tier, not the only safe model. |
| TEN-05 | In self-hosted deployments, a single installation hosts one organization. Multiple workspaces may share a database only under the same mandatory RLS and scoped-namespace rules as hosted. |
| TEN-06 | A Repository is scoped within a workspace. A GitHub repository may appear in multiple workspaces (each with its own ingestion), but data from one workspace's ingestion is never visible in another. |

---

## 2. Data Isolation

### 2.1 Isolation Mechanisms

| Layer | Mechanism | Enforcement |
|-------|-----------|-------------|
| **Database** | PostgreSQL RLS is mandatory for every workspace-owned production table. `FORCE ROW LEVEL SECURITY` is enabled; app roles lack `BYPASSRLS`; every table/index/FK carrying scoped references includes `workspace_id`. | On transaction begin, middleware sets `SET LOCAL work_frontier.workspace_id`; policies deny rows when absent or mismatched. Application query predicates are mandatory defense in depth, never an alternative. |
| **API** | Every API request carries an authenticated workspace context. Handlers resolve resources only through scoped repositories. | Middleware sets transaction-local context. Handlers never receive a bare resource ID without workspace context. |
| **Cache** | Cache keys include tenant and workspace namespace plus resource revision. | Cache layer rejects missing scope; invalidation is workspace-scoped. |
| **File storage** | Objects use tenant/workspace paths and per-workspace encryption-key references. | Storage layer rejects paths/key references outside current scope. |
| **Connections** | Connections, credentials, installations, webhook inboxes, source revisions, jobs, outbox records, and idempotency keys are workspace-scoped. | Schema composite uniqueness and RLS prevent a Connection in workspace A feeding B. |
| **Logs and audit** | Operational logs include workspace_id; audit chains are segmented per workspace. | Log queries, retention, anchors, and export are workspace-scoped. |

### 2.2 Isolation Verification

| Rule | Description |
|------|-------------|
| ISO-01 | Integration tests use the same non-BYPASSRLS database role as production. They create two workspaces, set transaction-local scope, and prove direct SQL, repository, API, cache, object, queue, inbox, audit, and idempotency access cannot cross scope. |
| ISO-02 | Tests prove absent/malformed workspace context fails closed; a privileged migration/admin role is never usable by application processes. |
| ISO-03 | Hosted staging runs the isolation suite against production-like shared infrastructure. Self-hosted certification runs it against the supplied Compose profile. |

---

## 3. Data Governance

### 3.1 Data Classification

| Classification | Description | Examples |
|---------------|-------------|---------|
| **Public** | Data intended for external sharing. | Exported readiness reports. |
| **Internal** | Data used within the workspace. Not secret, but not for external distribution. | Program names, WorkItem titles, readiness status. |
| **Confidential** | Data with restricted access within the workspace. | Decision rationale, evidence content, ProposedChange details, copilot interactions. |
| **Sensitive** | Data subject to regulatory requirements. | User PII (email, name), Connection credentials, audit logs. |

### 3.2 Data Handling Rules

| Classification | At Rest | In Transit | Access |
|---------------|---------|------------|--------|
| **Public** | Standard storage | HTTPS | Any authenticated user in the workspace. |
| **Internal** | Standard storage | HTTPS | Users with read permission on the resource. |
| **Confidential** | Encrypted at rest (AES-256) | HTTPS (TLS 1.2+) | Users with explicit read permission on the resource. |
| **Sensitive** | Encrypted at rest (AES-256), separate key management | HTTPS (TLS 1.3 preferred) | Tenant Administrator role only, or the data subject themselves (for PII). |

### 3.3 PII Handling

| Rule | Description |
|------|-------------|
| PII-01 | Work Frontier collects the minimum PII needed: display name and email for user identification. No other PII is collected by the platform. |
| PII-02 | User PII is never stored in Program data, WorkItem content, Evidence records, or audit logs beyond the user_id reference. |
| PII-03 | Users can export their own PII (name, email, activity history) via a data subject access request. |
| PII-04 | Users can request deletion of their account and associated PII. Deletion cascades to remove the user's role assignments but preserves anonymized activity records in the audit log (user_id replaced with `deleted-user-{hash}`). |
| PII-05 | PII is never transmitted to copilot or AI services. Copilot interactions are keyed by user_id, not by name or email. |

---

## 4. Data Retention

### 4.1 Retention Periods

Retention is governed by a **classification/purpose model**. Each data type has a default retention period, but the Policy Administrator can configure retention within the bounds below. No data type is hard-coded as "indefinite" without configurability.

| Data Type | Default Retention | Configurable Range | Classification | Deletion Method |
|-----------|-------------------|-------------------|----------------|-----------------|
| **Program data** (names, settings) | 365 days | 90 days to indefinite | Internal | Soft delete (30-day recovery window), then hard delete. |
| **WorkItem data** (titles, status, assignments) | 365 days | 90 days to indefinite | Internal | Hard delete with Program. |
| **Decision history** | 365 days | 90 days to indefinite | Confidential | Hard delete with WorkItem. |
| **Evidence** | 365 days | 90 days to indefinite | Confidential | Hard delete with WorkItem. |
| **ProposedChanges** | 90 days | 30 days to 365 days | Confidential | Automated purge. |
| **Policies** | Until retired | N/A (retention not applicable) | Internal | Hard delete. Retired policies archived. |
| **Audit logs** | 1 year | 90 days to 7 years | Sensitive | Automated purge after retention period. |
| **Copilot interaction logs** | 90 days | **0 days** to 1 year | Confidential | Automated purge. Setting to 0 disables copilot logging entirely. |
| **Connection credentials** | Until rotated or deleted | N/A (retention not applicable) | Sensitive | Hard delete on removal. Encrypted blobs destroyed. |
| **Exported files** | Not stored server-side | N/A | N/A | Exports are generated on-demand and streamed to the client. No server-side cache beyond the request lifecycle. |
| **User accounts** | Until user requests deletion | N/A | Sensitive | Cascade: remove roles, anonymize audit entries, hard delete profile. |

### 4.2 AI Provider Retention

AI providers may retain data according to their own policies, independent of Work Frontier's configuration. Work Frontier does not control provider-side retention. The following rules apply:

| Rule | Description |
|------|-------------|
| AIR-01 | The administrator configures Work Frontier's retention for copilot data independently of the provider's policy. |
| AIR-02 | Setting copilot interaction log retention to 0 days disables server-side logging. The provider may still retain data per their policy. |
| AIR-03 | Work Frontier documents which AI provider is in use and links to the provider's data handling documentation. |
| AIR-04 | The UI shows which provider handles copilot requests and notes that provider-side retention is separate from Work Frontier's configuration. |

### 4.3 Retention Rules

| Rule | Description |
|------|-------------|
| RET-01 | Retention periods are enforced automatically. No manual purge is required. |
| RET-02 | Purge operations are logged: "Purged [N] records of [type] older than [date]." |
| RET-03 | Users are notified 30 days before their data is subject to purge (for configurable retention types). |
| RET-04 | Hard-deleted data is not recoverable. There is no "undelete" for data past the recovery window. |
| RET-05 | In self-hosted deployments, the Policy Administrator configures retention. The platform enforces the configured periods. |
| RET-06 | The retention configuration is itself auditable. Changes to retention periods are logged in the audit log. |

### 4.3 Purpose Limitation

| Rule | Description |
|------|-------------|
| PL-01 | Data collected for one purpose is never used for another purpose without explicit user consent. |
| PL-02 | Copilot interaction data is used solely for improving the copilot experience within the workspace that generated it. It is never used to train models across workspaces. |
| PL-03 | Audit log data is used solely for security monitoring and compliance. It is never used for performance monitoring or user profiling. |

---

## 5. Self-Hosted vs. Hosted Isolation

| Aspect | Hosted | Self-Hosted |
|--------|--------|-------------|
| Tenant boundary | Workspace (RLS + application enforcement) | Workspace (RLS + application enforcement) |
| Database isolation | Shared database permitted only with forced RLS and scoped keys/namespaces; dedicated database remains tier-dependent | Single database permitted only with forced RLS and scoped keys/namespaces |
| Encryption at rest | Platform-managed keys (AES-256) | Customer-managed keys (bring your own key) |
| Backup scope | Per-organization backups. Cross-org restore is impossible. | Per-installation backups. Customer controls backup scope. |
| Network isolation | VPC-level isolation between organizations in hosted tier | Customer controls network topology |
| Data residency | Configurable per workspace (region selection) | Customer controls where they deploy |

---

## 6. Cross-References

| Document | Section | Relevance |
|----------|---------|-----------|
| [Authorization](authorization.md) | §2 Roles, §3 Permission Matrix, §3.1 Resource Scope | Authorization scopes are workspace-bound. Resource scopes include Tenant/Organization/Workspace/Program/Repository/Connection. |
| [AI Governance](ai-governance.md) | §2 Copilot Bounds, §4 Purpose-Limited Retention | Copilot data retention is a subset of this spec. AI can be configured to retain zero days. |
| [Threat Model](threat-model.md) | §3 Threat Categories | Data exfiltration and cross-tenant access are rated threats. |
| [Secure Development Lifecycle](secure-development-lifecycle.md) | §2 Secure Design | Isolation requirements feed into the SDL threat model. |
| [UX Architecture](../ux/ux-architecture.md) | §2 Views | Views operate within workspace scope. |
| [Onboarding](../ux/ux-onboarding.md) | §2 Onboarding Flow | Ingested data is workspace-scoped per TEN-01. |
