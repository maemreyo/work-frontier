---
id: ADR-003
title: "Deep Modular Monolith"
status: accepted
owner: Work Frontier architecture
date: 2026-07-12
scope: Work Frontier system architecture
classification: decision
related: [ADR-002, WF-DEL-001]
---

# ADR-003: Deep Modular Monolith

## Status

Accepted

## Context

Work Frontier is a dependency-aware readiness control plane with 13 modules across canonical Domain, Platform, Application, and Interfaces layers (ARCHITECTURE.md §3 and ADR-006). Small team. The question: microservices or monolith?

## Decision

**Deep modular monolith.** One deployable unit. Thirteen modules sit behind
clean seams: Domain is pure; Application owns use cases and port contracts;
Platform and Adapters implement only those contracts; Interfaces invoke inbound
use cases through the composition root. Forbidden import edges enforce this
direction without allowing concrete infrastructure into Application.

### 13 Modules

The authoritative taxonomy is ADR-006 and ARCHITECTURE.md §3:

- **Domain:** `graph`, `policies`, `decisions`
- **Platform:** `identity`, `tenancy`, `connections`, `audit`
- **Application:** `ingestion`, `normalization`, `projections`, `approvals`, `copilot`
- **Interfaces:** `control-room`

The original listing placed `audit` in Domain. That placement is superseded by
ADR-006; audit is Platform because it persists tamper-evident evidence.

Each module hides deep implementation behind a small interface (depth-as-leverage). `graph` handles typed cycle detection, dependency-SCC isolation, and deterministic component ordering — callers just query. `policies` handles readiness, blocking, and priority — callers just ask "is this ready?".

## Consequences

**+** Single deployment/rollback. Deep modules. Testable through interfaces. Extraction-ready seams.
**-** Single failure domain. Vertical scaling only (mitigated: I/O-bound).

---

| Date | Change | Author |
|------|--------|--------|
| 2026-07-12 | Accepted. | Work Frontier |
