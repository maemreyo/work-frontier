---
title: Work Frontier — Capability-Oriented Threat Model
id: WF-SEC-004
version: 2.0.0
status: canonical
owner: Security Architecture
last_updated: "2026-07-12"
replaces: 1.0.0
supersedes: null
---

# Capability-Oriented Threat Model

> **Purpose**: Identifies and rates threats organized by the capabilities an attacker seeks to exploit, not by the technical component they target. Each threat maps to a mitigation owned by a specific document. Both hosted and self-hosted deployments share the same correctness and security bar.

---

## 1. Threat Modeling Approach

This model is **capability-oriented**: it asks "what can the attacker *do*?" rather than "what component can they reach?" This avoids the trap of designing defenses around internal module boundaries that attackers don't respect.

### 1.1 Severity Ratings

| Rating | CVSS-equivalent | Description |
|--------|----------------|-------------|
| **Critical** | 9.0–10.0 | Immediate, widespread impact. Data breach, full system compromise, or cross-tenant data exposure. |
| **High** | 7.0–8.9 | Significant impact. Localized data exposure, privilege escalation, or service disruption. |
| **Medium** | 4.0–6.9 | Limited impact. Information disclosure, limited privilege escalation, or degraded service. |
| **Low** | 0.1–3.9 | Minimal impact. Annoyance, minor information leakage, or theoretical concern. |

### 1.2 Attacker Profiles

| Profile | Access | Motivation |
|---------|--------|------------|
| **External attacker** | No valid credentials. Internet-accessible. | Data theft, crypto mining, reputational damage. |
| **Malicious insider** | Valid user credentials (low-privilege role). | Data theft, privilege escalation, sabotage. |
| **Compromised GitHub content** | Controls a GitHub issue, PR, or check result that Work Frontier ingests. | Prompt injection, evidence spoofing, readiness manipulation. |
| **Compromised extension** | A Work Frontier extension (plugin, integration) has been tampered with. | Data exfiltration, privilege escalation. |
| **Compromised AI provider** | The AI model returns manipulated outputs. | Data exfiltration via prompt responses, content injection. |

---

## 2. Threat Categories

### 2.1 Data Exfiltration

| ID | Threat | Severity | Attacker | Description |
|----|--------|----------|----------|-------------|
| T-DEXFIL-01 | Cross-workspace data leak | Critical | External, insider | Attacker reads data from a workspace they don't belong to. |
| T-DEXFIL-02 | Evidence content exfiltration | High | Insider | Authorized user exports or copies Evidence content they shouldn't access. |
| T-DEXFIL-03 | Credential extraction | Critical | External, insider | Attacker extracts Connection credentials (GitHub tokens, API keys). |
| T-DEXFIL-04 | Audit log extraction | Medium | Insider | Attacker reads audit logs to learn about other users' activities. |
| T-DEXFIL-05 | Copilot data exfiltration | High | External | Attacker uses copilot interactions to extract workspace data through crafted prompts. |

**Mitigations:**

| Threat | Mitigation | Owner |
|--------|-----------|-------|
| T-DEXFIL-01 | Row-level security, workspace-scoped queries, isolation verification tests | [Tenancy & Isolation §2](tenancy-isolation.md#2-data-isolation) |
| T-DEXFIL-02 | Resource-scoped permissions, export logging | [Authorization §3](authorization.md#3-permission-matrix) |
| T-DEXFIL-03 | Encrypted credential storage, masked display, minimum-scope tokens | [Authorization §6](authorization.md#6-connection-credentials) |
| T-DEXFIL-04 | Audit log access restricted to Operator and Tenant Administrator roles | [Authorization §3.2](authorization.md#32-permission-table) |
| T-DEXFIL-05 | Copilot trust boundary, scope check, workspace-scoped AI data | [AI Governance §2.3](ai-governance.md#23-copilot-trust-boundary) |

### 2.2 Privilege Escalation

| ID | Threat | Severity | Attacker | Description |
|----|--------|----------|----------|-------------|
| T-PRIVESC-01 | Role escalation via API | Critical | Insider | User modifies their own role or permissions via direct API calls. |
| T-PRIVESC-02 | Role escalation via UI manipulation | High | Insider | User manipulates UI state to access views or actions outside their role. |
| T-PRIVESC-03 | Admin impersonation | Critical | External | Attacker gains Tenant Administrator role through social engineering or token theft. |
| T-PRIVESC-04 | Break-glass abuse | High | Insider | User invokes break-glass for non-emergency purposes. |

**Mitigations:**

| Threat | Mitigation | Owner |
|--------|-----------|-------|
| T-PRIVESC-01 | Server-side permission checks on every API call, deny-by-default | [Authorization §3.3](authorization.md#33-permission-check-rules) |
| T-PRIVESC-02 | View-level permission enforcement matches API-level enforcement | [Authorization §3.3](authorization.md#33-permission-check-rules) |
| T-PRIVESC-03 | Four-eyes approval for Tenant Administrator assignment, SSO/OAuth enforcement | [Authorization §2.2](authorization.md#22-role-assignment-rules) |
| T-PRIVESC-04 | Rate limiting (2/day), strong reauth, 2-hour expiry, audit logging, mandatory review | [Authorization §5](authorization.md#5-break-glass-procedure) |

### 2.3 Injection Attacks

| ID | Threat | Severity | Attacker | Description |
|----|--------|----------|----------|-------------|
| T-INJECT-01 | XSS in evidence content | Critical | External, insider | Attacker injects malicious scripts into evidence rendered in the Builder canvas. |
| T-INJECT-02 | XSS in copilot responses | High | External (via compromised AI) | AI-generated content contains executable scripts. |
| T-INJECT-03 | Prompt injection via GitHub content | High | External (via GitHub issue/PR) | GitHub issue or PR body contains text crafted to manipulate copilot behavior when ingested. |
| T-INJECT-04 | SQL injection | Critical | External | Attacker injects SQL via API parameters. |
| T-INJECT-05 | SSRF via GitHub content ingestion | High | External | GitHub issue body contains URLs to internal network addresses; ingestion fetches them. |

**Mitigations:**

| Threat | Mitigation | Owner |
|--------|-----------|-------|
| T-INJECT-01 | Content Security Policy, DOMPurify on render, no `eval()`, CSP `script-src 'none'` | [Threat Model §2.3 (this doc)](#23-injection-attacks), [SDL §3.3](secure-development-lifecycle.md#3-secure-coding) |
| T-INJECT-02 | Output filtering, content sanitization on copilot responses, CSP enforcement | [AI Governance §5.2](ai-governance.md#52-output-filtering) |
| T-INJECT-03 | Prompt injection detection, content trust scoring, `Unverified` indicator on ingested content | [AI Governance §5.1](ai-governance.md#51-input-filtering), [Onboarding §2.4](../ux/ux-onboarding.md#24-step-4-draft-normalized-snapshot) |
| T-INJECT-04 | Parameterized queries, ORM usage, input validation on all API parameters | [SDL §3.3](secure-development-lifecycle.md#3-secure-coding) |
| T-INJECT-05 | URL allowlist for fetches, block private IP ranges (RFC 1918, loopback, link-local), DNS rebinding protection | [SDL §3.3](secure-development-lifecycle.md#3-secure-coding) |

### 2.4 Authentication and Session Attacks

| ID | Threat | Severity | Attacker | Description |
|----|--------|----------|----------|-------------|
| T-AUTH-01 | Session hijacking | High | External | Attacker steals or forges a session token. |
| T-AUTH-02 | Credential stuffing | High | External | Attacker uses leaked credentials to log in. |
| T-AUTH-03 | Token replay | Medium | External | Attacker replays a captured API token. |
| T-AUTH-04 | CSRF | Medium | External | Attacker tricks a user into performing an unintended action. |

**Mitigations:**

| Threat | Mitigation | Owner |
|--------|-----------|-------|
| T-AUTH-01 | HttpOnly, Secure, SameSite cookies. Short session lifetime. Token rotation on privilege change. | [SDL §2](secure-development-lifecycle.md#2-secure-design) |
| T-AUTH-02 | SSO/OAuth preferred. Rate limit login attempts. Account lockout after N failures. | [Authorization §2.2](authorization.md#22-role-assignment-rules) |
| T-AUTH-03 | Short-lived tokens, token binding to device fingerprint, revocation on logout. | [SDL §2](secure-development-lifecycle.md#2-secure-design) |
| T-AUTH-04 | CSRF tokens on all state-changing requests, SameSite cookie attribute. | [SDL §3.4](secure-development-lifecycle.md#3-secure-coding) |

### 2.5 Runner and Ingestion Threats

| ID | Threat | Severity | Attacker | Description |
|----|--------|----------|----------|-------------|
| T-RUN-01 | Unauthorized ingestion execution | Critical | Insider | Attacker triggers ingestion of data they shouldn't access. |
| T-RUN-02 | Runner compromise | Critical | External | Attacker gains control of a runner and executes arbitrary code. |
| T-RUN-03 | Runner data exfiltration | High | External, insider | Attacker extracts evidence data from a runner's local storage. |
| T-RUN-04 | Runner denial of service | Medium | External | Attacker overwhelms a runner, preventing legitimate ingestion. |
| T-RUN-05 | Poisoned ingestion via GitHub content | High | External (via GitHub issue/PR) | Imported GitHub content triggers a runner to execute malicious actions. |

**Mitigations:**

| Threat | Mitigation | Owner |
|--------|-----------|-------|
| T-RUN-01 | Runner workspace-scoping, ingestion dispatch authorization check, Operator role required for runner actions | [Authorization §3.2](authorization.md#32-permission-table) |
| T-RUN-02 | Runner authentication (signed tokens), runner isolation (container/sandbox), runner health monitoring | [Authorization §6](authorization.md#6-connection-credentials), [SDL §2](secure-development-lifecycle.md#2-secure-design) |
| T-RUN-03 | Runner data encrypted at rest, runner task logs purged per retention policy, no persistent evidence data on runners | [Tenancy & Isolation §4.1](tenancy-isolation.md#41-retention-periods) |
| T-RUN-04 | Runner rate limiting, queue depth monitoring, automatic scaling (hosted) or alerting (self-hosted) | [Operator view UX](../ux/ux-critical-journeys.md#6-journey-reconcile-sync-discrepancies) |
| T-RUN-05 | Ingested content marked `Unverified`, runner input validation, sandboxed execution | [AI Governance §2.2](ai-governance.md#22-what-the-copilot-may-not-do), [Onboarding §2.4](../ux/ux-onboarding.md#24-step-4-draft-normalized-snapshot) |

### 2.6 Evidence and Content Integrity Threats

| ID | Threat | Severity | Attacker | Description |
|----|--------|----------|----------|-------------|
| T-EVID-01 | Evidence tampering | High | Insider | Attacker modifies evidence after it has been collected or verified. |
| T-EVID-02 | Decision history tampering | Critical | Insider | Attacker modifies the Decision audit trail. |
| T-EVID-03 | Report integrity | High | External | Attacker modifies an exported readiness report between generation and download. |
| T-EVID-04 | GitHub content spoofing | High | External | Attacker creates a GitHub issue that impersonates a trusted source or check result. |

**Mitigations:**

| Threat | Mitigation | Owner |
|--------|-----------|-------|
| T-EVID-01 | Evidence versioning, immutable audit trail, content hash on export | [Tenancy & Isolation §4](tenancy-isolation.md#4-data-retention) |
| T-EVID-02 | Append-only Decision log, cryptographic integrity (hash chain or signature), Tenant Administrator-only access to raw log | [Tenancy & Isolation §4](tenancy-isolation.md#4-data-retention) |
| T-EVID-03 | Signed exports (content hash in download metadata), TLS transport, no server-side export cache | [Tenancy & Isolation §4.1](tenancy-isolation.md#41-retention-periods) |
| T-EVID-04 | `Unverified` provisional indicator, source attribution on ingestion, user verification workflow | [Onboarding §2.4](../ux/ux-onboarding.md#24-step-4-draft-normalized-snapshot) |

### 2.7 Extension Threats

| ID | Threat | Severity | Attacker | Description |
|----|--------|----------|----------|-------------|
| T-EXT-01 | Malicious extension | Critical | External | A Work Frontier extension (plugin, integration) has been tampered with and exfiltrates data. |
| T-EXT-02 | Extension privilege creep | High | Insider | An extension requests more permissions than it needs. |
| T-EXT-03 | Extension data leakage | High | External, insider | An extension leaks workspace data to an external service. |

**Mitigations:**

| Threat | Mitigation | Owner |
|--------|-----------|-------|
| T-EXT-01 | Extension signing, integrity verification on load, sandboxed execution | [SDL §2](secure-development-lifecycle.md#2-secure-design) |
| T-EXT-02 | Extension permission audit, Tenant Administrator approval for extension installation | [Authorization §3.2](authorization.md#32-permission-table) |
| T-EXT-03 | Extension network egress monitoring, workspace-scoped data access | [Tenancy & Isolation §2.1](tenancy-isolation.md#21-isolation-mechanisms) |

### 2.8 Tenant Threats

| ID | Threat | Severity | Attacker | Description |
|----|--------|----------|----------|-------------|
| T-TENANT-01 | Cross-tenant data leakage | Critical | External | Attacker reads data from a different tenant's workspace. |
| T-TENANT-02 | Tenant impersonation | Critical | External | Attacker forges a workspace context to access another tenant's data. |
| T-TENANT-03 | Tenant data residue | Medium | Insider | Data from a deleted workspace remains accessible to a new workspace. |

**Mitigations:**

| Threat | Mitigation | Owner |
|--------|-----------|-------|
| T-TENANT-01 | Row-level security, workspace-scoped queries, isolation verification tests | [Tenancy & Isolation §2](tenancy-isolation.md#2-data-isolation) |
| T-TENANT-02 | Workspace context derived from authenticated session, not from client-provided parameters | [Authorization §3.3](authorization.md#33-permission-check-rules) |
| T-TENANT-03 | Hard delete with cryptographic erasure verification, workspace_id rotation on re-creation | [Tenancy & Isolation §4.3](tenancy-isolation.md#43-retention-rules) |

---

## 3. Threat Response Matrix

| Threat ID | Severity | Detection | Response Time | Escalation |
|-----------|----------|-----------|--------------|------------|
| T-DEXFIL-01 | Critical | Automated (isolation test, anomaly detection) | Immediate block, investigate within 1 hour | Tenant Admin + security team |
| T-DEXFIL-03 | Critical | Automated (credential access logging) | Immediate block, rotate credential within 1 hour | Tenant Admin + security team |
| T-PRIVESC-01 | Critical | Automated (permission check failure logging) | Immediate block, session revocation within 15 minutes | Tenant Admin + security team |
| T-RUN-01 | Critical | Automated (dispatch authorization check) | Immediate block, runner quarantine within 15 minutes | Operator + Tenant Admin |
| T-RUN-02 | Critical | Automated (runner health monitoring) | Runner quarantine immediately, investigate within 1 hour | Operator + security team |
| T-EVID-02 | Critical | Automated (integrity check on append-only log) | Immediate alert, investigate within 4 hours | Tenant Admin + security team |
| T-INJECT-01 | Critical | Automated (CSP violation reporting) | Block render, investigate within 4 hours | Security team |
| T-INJECT-03 | High | Automated (prompt injection detection) | Block prompt, log event, investigate within 24 hours | Security team |
| T-TENANT-01 | Critical | Automated (isolation verification) | Immediate block, investigate within 1 hour | Tenant Admin + security team |
| T-EXT-01 | Critical | Automated (extension integrity check) | Quarantine extension immediately, investigate within 1 hour | Tenant Admin + security team |
| T-AUTH-01 | High | Automated (session anomaly detection) | Session revocation, investigate within 4 hours | Tenant Admin |

---

## 4. Self-Hosted Threat Considerations

Self-hosted deployments share the same correctness bar but have additional threat surface:

| Consideration | Description | Mitigation |
|--------------|-------------|------------|
| **Physical access** | The customer controls the infrastructure. Physical access attacks are the customer's responsibility. | Document this in the self-hosted deployment guide. |
| **Network exposure** | Self-hosted instances may be exposed to the internet without a WAF or reverse proxy. | Provide a hardened deployment template with TLS, rate limiting, and IP allowlisting. |
| **Backup security** | Customer-managed backups may not meet the same encryption standards. | Require encrypted backups in the deployment guide. |
| **Update velocity** | Self-hosted deployments may lag behind security patches. | Publish security advisories with version-specific patch instructions. Auto-update notifications in the Operator view. |
| **Extension trust** | Self-hosted deployments may install unvetted extensions. | Require Tenant Administrator approval for all extension installations. Extension signing verification is mandatory. |

---

## 5. Threat Model Maintenance

| Rule | Description |
|------|-------------|
| TM-01 | This threat model is reviewed and updated on every major release (quarterly minimum). |
| TM-02 | New features require a threat model review before shipping. The review is part of the SDL (see [Secure Development Lifecycle](secure-development-lifecycle.md)). |
| TM-03 | Threat severity ratings are recalculated if the affected component changes its trust boundary. |
| TM-04 | Threats that are mitigated by a design change are marked "Mitigated" with a cross-reference, not deleted. |
| TM-05 | The threat model is tested against the actual system, not just the design document. Penetration testing validates the mitigations. |

---

## 6. Cross-References

| Document | Section | Relevance |
|----------|---------|-----------|
| [Authorization](authorization.md) | Full document | Mitigates privilege escalation and unauthorized access threats. |
| [Tenancy & Isolation](tenancy-isolation.md) | §2 Data Isolation | Mitigates cross-workspace data exfiltration and tenant threats. |
| [AI Governance](ai-governance.md) | §5 AI Safety Layers | Mitigates prompt injection and AI-mediated content attacks. |
| [Secure Development Lifecycle](secure-development-lifecycle.md) | §3 Security Testing | Validates threat mitigations through testing. |
| [UX Architecture](../ux/ux-architecture.md) | §3 Decision Semantics, §7 Additional Rules | Decision type visibility helps users spot anomalous Decisions. Claims are coordination leases. |
| [Critical Journeys](../ux/ux-critical-journeys.md) | §9 Error State Journey, §7 Degraded Connection Journey | Error handling and degraded connection communication prevent information leakage. |
