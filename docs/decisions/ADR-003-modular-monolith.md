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

Work Frontier is a dependency-aware readiness control plane with 13 modules across 4 layers (ARCHITECTURE.md §3). Small team. The question: microservices or monolith?

## Decision

**Deep modular monolith.** One deployable unit. 13 modules behind clean seams. Forbidden import edges enforce layer direction: Domain ← Application ← Adapters ← Interfaces.

### 13 Modules (from ARCHITECTURE.md)

**Domain:** `identity`, `tenancy`, `connections`, `graph`, `policies`, `decisions`, `audit`
**Application:** `ingestion`, `normalization`, `projections`, `approvals`, `copilot`
**Interfaces:** `control-room`

Each module hides deep implementation behind a small interface (depth-as-leverage). `graph` handles typed cycle detection, dependency-SCC isolation, and deterministic component ordering — callers just query. `policies` handles readiness, blocking, and priority — callers just ask "is this ready?".

## Consequences

**+** Single deployment/rollback. Deep modules. Testable through interfaces. Extraction-ready seams.
**-** Single failure domain. Vertical scaling only (mitigated: I/O-bound).

---

| Date | Change | Author |
|------|--------|--------|
| 2026-07-12 | Accepted. | Work Frontier |
