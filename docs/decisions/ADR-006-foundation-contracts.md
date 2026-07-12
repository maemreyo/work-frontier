---
id: ADR-006
title: "Foundation Contracts: Taxonomy, Ports, Reproducibility, and Consistency"
status: accepted
owner: Work Frontier architecture
date: 2026-07-12
scope: Work Frontier pre-implementation architecture contracts
classification: decision
supersedes: [ADR-003 module taxonomy paragraph]
related: [ADR-002, ADR-003, ADR-004, ADR-005, WF-ARCH, WF-DOM-07, WF-SEC-002]
---

# ADR-006: Foundation Contracts

## Status

Accepted. This ADR is a mandatory precondition for implementation bootstrap.

## Context

The original blueprint chose the correct deep modular-monolith direction, but
left five safety-critical contracts ambiguous: module taxonomy, port ownership,
reproducible decision identity, audit tamper evidence, and workspace isolation.
Those ambiguities must be resolved before code creates package seams, database
tables, or release harnesses.

## Decision

### Canonical taxonomy

| Layer | Modules | Responsibility |
|---|---|---|
| Domain | `graph`, `policies`, `decisions` | Pure readiness model, typed graph validation, policy evaluation, deterministic decision computation. |
| Platform | `identity`, `tenancy`, `connections`, `audit` | Actor/session context, workspace enforcement, credential/connection lifecycle, persistence, queue, outbox, and tamper evidence. |
| Application | `ingestion`, `normalization`, `projections`, `approvals`, `copilot` | Use-case orchestration over Domain and Platform interfaces. |
| Interfaces | `control-room` | HTTP/OpenAPI, CLI, and browser-facing interaction adapters. |
| Adapters | GitHub, object storage, AI provider, harness adapters | Concrete implementations of Platform-owned external-capability interfaces. |

There remain exactly thirteen named modules. Persistence, queue, and storage are
Platform implementations owned by their named Platform modules; they are not
additional business modules.

### Port ownership

The **Application layer owns every port interface** that crosses from a
use-case into infrastructure or an external system. Domain modules expose only
pure types and deterministic functions. Adapters implement Application-owned
outbound ports. Interfaces invoke Application-owned inbound use cases. Neither
Domain nor Adapters imports the other.

### Reproducible decisions

A DecisionRecord is a reproducible decision envelope. It identifies the exact
workspace, normalized snapshot, graph revision, policy bundle, ranking
pipeline, engine build, normalization profile, source revisions, causation, and
correlation from which its output was computed. A current projection may cache
derived readiness/ranking only when it names the immutable DecisionRecord that
produced it.

### Integrity and consistency

Audit chains are segmented per workspace and protect a canonical event envelope
and canonical payload hash. Database-local chains detect accidental or partial
tampering; external signed anchors or WORM retention are required where the
threat model includes a privileged database administrator.

The durable inbox, normalized snapshot, DecisionRecord set, current projection,
audit event, and transactional outbox commit atomically. External GitHub writes
occur only after commit from the outbox with an idempotency key and projection
fingerprint. Queue claims use compare-and-swap state transitions, `FOR UPDATE
SKIP LOCKED`, lease ownership, retry scheduling, dead-letter quarantine, and
tenant-fair selection.

### Tenancy

Workspace isolation is mandatory in every profile. PostgreSQL RLS with `FORCE
ROW LEVEL SECURITY` is required for production tables, and the application DB
role must not have `BYPASSRLS`. Application query scoping is defense in depth,
not an alternative. Shared hosted databases are permitted only when their
tenant/workspace state is isolated by RLS, per-workspace keys, and scoped cache,
object, queue, inbox, audit, and idempotency namespaces.

## Consequences

- Bootstrap cannot create source layout, migrations, or harness registry until
  the ADR's interfaces and invariants are represented in the canonical docs and
  contract tests.
- ADR-003's former placement of `audit` in Domain is superseded.
- A release cannot claim deterministic, auditable, or tenant-safe behavior from
  documentation alone; it requires the revised harness evidence.

## Change Log

| Date | Change | Author |
|---|---|---|
| 2026-07-12 | Accepted as P0 pre-implementation contract gate. | Work Frontier |
