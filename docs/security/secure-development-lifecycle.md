---
title: Work Frontier — Secure Development Lifecycle
id: WF-SEC-005
version: 2.0.0
status: canonical
owner: Security Architecture
last_updated: "2026-07-12"
replaces: 1.0.0
supersedes: null
---

# Secure Development Lifecycle Specification

> **Purpose**: Defines the security practices embedded in every phase of Work Frontier's development process. Security is not a gate at the end; it's a discipline woven into design, implementation, testing, deployment, and operations.

---

## 1. SDL Phases

```
Design → Implement → Test → Deploy → Operate → Respond
  │          │          │        │         │          │
  ▼          ▼          ▼        ▼         ▼          ▼
Threat     Secure     Security  Secure    Monitoring  Incident
Model      Coding     Testing   Config    & Audit     Response
```

Each phase has mandatory security activities. No phase is skipped.

---

## 2. Secure Design

### 2.1 Threat Model as Design Input

| Rule | Description |
|------|-------------|
| SDL-D-01 | Every new feature or significant change starts with a threat model review using the [Capability-Oriented Threat Model](threat-model.md). |
| SDL-D-02 | The threat model review is documented: which threats apply, what mitigations are designed, and what residual risk is accepted. |
| SDL-D-03 | Features that change the trust boundary (new Connections, new roles, new data flows) require a dedicated threat model session, not just a review checklist. |
| SDL-D-04 | The threat model is reviewed against the [Authorization](authorization.md) model to ensure new features don't create privilege escalation paths. |

### 2.2 Security Requirements

Every feature spec must include:

| Requirement | Description |
|-------------|-------------|
| **Authentication**: How does the user prove identity? | If the feature is behind an auth gate, specify which gate. |
| **Authorization**: What roles can access this feature? | Map to the [Permission Matrix](authorization.md#32-permission-table). |
| **Data classification**: What data does this feature handle? | Map to [Data Governance §3.1](tenancy-isolation.md#31-data-classification). |
| **Input validation**: What inputs does this feature accept? | Specify validation rules, types, and bounds. |
| **Output encoding**: How is output rendered? | Specify encoding rules for HTML, JSON, and other contexts. |
| **Error handling**: What errors can occur? | Specify user-facing messages (never raw technical errors). |
| **Audit logging**: What events are logged? | Specify event type, severity, and data captured. |

### 2.3 Secure Design Principles

| Principle | Description |
|-----------|-------------|
| **Deny by default** | Every permission is denied unless explicitly granted (see [Authorization §1](authorization.md#1-authorization-principles)). |
| **Least privilege** | Users and services receive the minimum permissions needed. |
| **Separation of duties** | No single actor can both perform and approve sensitive actions. |
| **Defense in depth** | Multiple layers of controls. No single point of failure. |
| **Fail securely** | System defaults to a secure state on failure, not an open one. |

---

## 3. Secure Coding

### 3.1 Language and Framework Standards

| Language | Standards | Enforcement |
|----------|-----------|-------------|
| **Python** | Pydantic v2 for input validation. Parameterized queries only (no string interpolation). Type hints on all public interfaces. | Linter (ruff), type checker (basedpyright), CI gate. |
| **TypeScript** | Strict mode. Zod schemas for input validation. No `any` type. No `eval()`. | Compiler (tsc --strict), linter (Biome), CI gate. |

### 3.2 Input Validation

| Rule | Description |
|------|-------------|
| SDL-C-01 | All external input (API parameters, file uploads, GitHub webhook payloads) is validated against a schema before processing. |
| SDL-C-02 | Validation is performed at the API boundary, not inside business logic. |
| SDL-C-03 | GitHub webhook payloads are validated against GitHub's webhook signature before processing. |
| SDL-C-04 | URLs in ingested GitHub content (issue bodies, PR descriptions) are validated against an allowlist. Private IP ranges (RFC 1918, loopback, link-local) are blocked for SSRF prevention. |
| SDL-C-05 | Copilot prompts are validated against a maximum length and character set before reaching the AI model. |

### 3.3 Output Encoding

| Rule | Description |
|------|-------------|
| SDL-C-06 | HTML output is sanitized (DOMPurify or equivalent) before rendering. |
| SDL-C-07 | JSON output uses library-provided encoding. No manual string concatenation of JSON. |
| SDL-C-08 | User-supplied content displayed in the UI is HTML-entity-encoded by default. Rich text rendering requires an explicit sanitization step. |
| SDL-C-09 | Copilot responses are sanitized before rendering in the Builder canvas, same as any user-supplied content. |
| SDL-C-10 | GitHub issue/PR body content is sanitized before rendering in the Builder canvas. GitHub content is untrusted. |

### 3.4 Secrets Management

| Rule | Description |
|------|-------------|
| SDL-C-11 | Secrets (API keys, tokens, passwords) are never hardcoded in source code. |
| SDL-C-12 | Secrets are stored in environment variables or a secrets manager, never in config files committed to version control. |
| SDL-C-13 | Pre-commit hooks scan for secret patterns (API keys, tokens, passwords) before allowing commits. |
| SDL-C-14 | Secrets are never logged. Application logging redacts any field that matches a secret pattern. |

---

## 4. Security Testing

### 4.1 Automated Testing

| Test Type | Scope | Frequency | Tool |
|-----------|-------|-----------|------|
| **Static Application Security Testing (SAST)** | All source code | Every PR | Language-specific linters (ruff, Biome) + dedicated SAST scanner. |
| **Software Composition Analysis (SCA)** | All dependencies | Every PR | Dependency scanner (Dependabot, Snyk, or equivalent). |
| **Secret scanning** | All source code and commits | Every commit (pre-commit hook) + every PR | Pre-commit hook + CI scanner. |
| **Container scanning** | Docker images | Every build | Trivy or equivalent. |
| **Infrastructure scanning** | Deployment configs (Docker Compose, Kubernetes manifests) | Every release | Policy-as-code scanner. |
| **Accessibility automated checks** | All UI components | Every PR | axe-core in CI pipeline. |

### 4.2 Manual Testing

| Test Type | Scope | Frequency | Owner |
|-----------|-------|-----------|-------|
| **Penetration testing** | Full system | Every major release (quarterly minimum) | External security firm or internal red team. |
| **Authorization testing** | All API endpoints | Every release candidate | QA team, using the [Permission Matrix](authorization.md#32-permission-table). |
| **Isolation testing** | Cross-workspace boundaries | Every release | Automated integration tests + manual verification. |
| **Keyboard/screen reader testing** | All critical journeys | Every release candidate | QA team, per [Accessibility Task Harness](../ux/ux-accessibility-design-system.md#7-task-harness-acceptance-criteria). |
| **AI safety testing** | Copilot interactions | Every copilot model change | Security team, testing prompt injection, data exfiltration, and output safety. |

### 4.3 Security Test Acceptance Criteria

| Criterion | Requirement |
|-----------|-------------|
| **No Critical findings** | Zero unresolved Critical-severity findings in SAST, SCA, or penetration test. |
| **No High findings without mitigation** | Every High-severity finding has a documented mitigation or accepted risk. |
| **All authorization tests pass** | Every endpoint returns 403 for unauthorized access, never 404. |
| **Isolation test passes** | Cross-workspace data access is impossible at every layer. |
| **Accessibility task harness passes** | All blocking task harness entries pass (see [Accessibility §7](../ux/ux-accessibility-design-system.md#7-task-harness-acceptance-criteria)). |

---

## 5. Secure Deployment

### 5.1 Deployment Security

| Rule | Description |
|------|-------------|
| SDL-DP-01 | All communication uses TLS 1.2+ (TLS 1.3 preferred). |
| SDL-DP-02 | HTTP to HTTPS redirect is enforced. No mixed content. |
| SDL-DP-03 | Security headers are set on every response: `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`, `Referrer-Policy`, `Permissions-Policy`. |
| SDL-DP-04 | The Content Security Policy prohibits external scripts, `eval()`, and inline scripts (except nonce-marked scripts). |
| SDL-DP-05 | Database connections use encrypted channels. |
| SDL-DP-06 | Container images are built from minimal base images. No unnecessary packages. |
| SDL-DP-07 | Containers run as non-root users. |

### 5.2 Configuration Security

| Rule | Description |
|------|-------------|
| SDL-CF-01 | Default configurations are secure. No "development mode" settings leak into production. |
| SDL-CF-02 | Self-hosted deployments ship with a hardened configuration template. |
| SDL-CF-03 | Configuration files are validated at startup. Invalid or insecure configurations prevent startup with a clear error message. |
| SDL-CF-04 | Feature flags that weaken security (e.g., disable CSRF protection, relax CSP) require Tenant Administrator confirmation and are logged. |

---

## 6. Security Operations

### 6.1 Monitoring and Alerting

| Signal | What It Catches | Alert Threshold |
|--------|----------------|-----------------|
| **Failed login attempts** | Credential stuffing, brute force | > 5 failures per account in 5 minutes |
| **Permission check failures** | Privilege escalation attempts | > 10 failures per user in 1 hour |
| **Cross-workspace query attempts** | Isolation breach | Any attempt (zero tolerance) |
| **Break-glass invocations** | Emergency access usage | Every invocation |
| **Runner anomalies** | Runner compromise, failure cascade | Heartbeat miss > 2 minutes, error rate > 10% |
| **CSP violations** | XSS attempts | Any violation |
| **Dependency vulnerabilities** | Supply chain compromise | Any Critical or High CVE |
| **AI safety classification anomalies** | Prompt injection, output safety | Safety classification distribution shift > 2σ |
| **GitHub webhook anomalies** | Tampered or replayed webhooks | Signature mismatch, timestamp drift > 5 minutes |

### 6.2 Incident Response

| Phase | Description | Time Target |
|-------|-------------|-------------|
| **Detection** | Automated alert or user report triggers investigation. | Immediate. |
| **Triage** | Assess severity, affected scope, and data exposure. | Within 1 hour. |
| **Containment** | Block the attack vector. Revoke compromised credentials. Quarantine affected components. | Within 4 hours for Critical, 24 hours for High. |
| **Eradication** | Remove the root cause. Patch the vulnerability. | Within 24 hours for Critical, 1 week for High. |
| **Recovery** | Restore service. Verify integrity. | Within 48 hours for Critical. |
| **Post-incident** | Root cause analysis. Threat model update. Process improvement. | Within 1 week. |

### 6.3 Security Patching

| Rule | Description |
|------|-------------|
| SDL-SP-01 | Critical vulnerabilities in dependencies are patched within 48 hours. |
| SDL-SP-02 | High vulnerabilities are patched within 1 week. |
| SDL-SP-03 | Security patches are released as point releases, not bundled with feature releases. |
| SDL-SP-04 | Self-hosted deployments receive security advisories with version-specific patch instructions. |
| SDL-SP-05 | The Operator view shows a "Security updates available" indicator when the installed version has known vulnerabilities. |

---

## 7. Dependency Governance

| Rule | Description |
|------|-------------|
| SDL-DG-01 | All dependencies are pinned to specific versions. No floating version ranges in production. |
| SDL-DG-02 | New dependencies require a security review: license compatibility, known vulnerabilities, maintenance status, and attack surface. |
| SDL-DG-03 | Dependencies are scanned for vulnerabilities on every PR and on a weekly schedule. |
| SDL-DG-04 | Dependencies with known Critical vulnerabilities are blocked from merging. |
| SDL-DG-05 | A Software Bill of Materials (SBOM) is generated for every release. |

---

## 8. Security Documentation

| Document | Purpose | Maintenance |
|----------|---------|-------------|
| [Threat Model](threat-model.md) | Identifies and rates threats | Updated on every major release and after security incidents. |
| [Authorization](authorization.md) | Defines the access control model | Updated when roles, permissions, or SoD constraints change. |
| [Tenancy & Isolation](tenancy-isolation.md) | Defines data isolation boundaries | Updated when the tenancy model changes. |
| [AI Governance](ai-governance.md) | Defines AI bounds and safety | Updated when AI capabilities change. |
| This document (SDL) | Defines the development process | Updated when the process changes. |
| Deployment guide | Customer-facing security configuration | Updated on every release. |

---

## 9. Cross-References

| Document | Section | Relevance |
|----------|---------|-----------|
| [Threat Model](threat-model.md) | Full document | Feeds into SDL design phase. |
| [Authorization](authorization.md) | Full document | Authorization testing validates the permission model. |
| [Tenancy & Isolation](tenancy-isolation.md) | §2 Data Isolation | Isolation testing is part of the SDL. |
| [AI Governance](ai-governance.md) | §5 AI Safety Layers | AI safety testing is part of the SDL. |
| [UX Architecture](../ux/ux-architecture.md) | §3 Decision Semantics, §7 Additional Rules | Decision type visibility is a security control (human oversight). |
| [Accessibility](../ux/ux-accessibility-design-system.md) | §7 Task Harness | Accessibility testing is part of the SDL. |
