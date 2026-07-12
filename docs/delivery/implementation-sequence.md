---
id: WF-DEL-001
title: "Implementation Sequence: Work Frontier Product"
status: accepted
owner: Work Frontier delivery
date: 2026-07-12
scope: Work Frontier delivery
classification: delivery
depends_on: [WF-REF-001, WF-REF-002, ADR-002, ADR-003, ADR-006]
---

# WF-DEL-001: Implementation Sequence

## Purpose

Complete standalone product implementation plan for Work Frontier aligned with the 13-module architecture and foundation contracts (ADR-006). Covers preflight through certification. Includes blocking edges, parallel lanes, and full harness gates.

---

## 1. Build Stages

### Dependency Graph

```
Stage 0: ADR-006 Foundation Contract Gate
    │
    ▼
Stage 1: Foundation / Contracts + Domain
    ├──► Stage 2a: Tenancy + Identity ────────────────────┐
    ├──► Stage 2b: Persistence + Ledger + Queue ───────┐  │
    └──► Stage 3: GitHub Connection + Ingestion + Normalization
                                                       │  │
Stage 3 + Stage 2b ──► Stage 4: Reconciliation ───────┤  │
Stage 2a + Stage 2b + Stage 4 ──► Stage 5: Graph + Policy + Decision Authority
                                                       │
Stage 5 + Stage 4 ──► Stage 6: Evidence + Gates ──────┤
                                                       ▼
                                             Stage 7: Projections + Proposals + Approvals
                                                       │
                                             Stage 8: Claims + Attention
                                                       │
                                             Stage 9: REST + CLI
                                                       │
                                             Stage 10: Control Room UX
                                                       │
                                             Stage 11: Copilot (Bounded)
                                                       │
                                             Stage 12: Operations + Security
                                                       │
                                             Stage 13: Certification + Cutover
```

### Parallel Lanes

| Lane | Stages | Notes |
|------|--------|-------|
| **Domain lane** | 0 → 1 → 5 | Pure domain logic, no I/O |
| **Platform lane** | 0 → 2a / 2b → 5 | Identity, tenancy, persistence, ledger, queue |
| **Integration lane** | 0 → 3 → 4 → 6 | GitHub connection and data flow |
| **Convergence** | 3 + 2b → 4; 2a + 2b + 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 | Stage 4 merges Integration and persistence; sequential after graph convergence |

---

## 2. Stage Details

### Stage 0: ADR-006 Foundation Contract Gate

**Modules:** Taxonomy and cross-cutting contracts; no runtime implementation.

| Deliverable | Description |
|-------------|------------|
| Contract manifest | Machine-readable taxonomy, port ownership, reproducibility, tenancy, audit, atomic-commit, and queue contracts |
| Negative fixtures | Deterministic failures for contract drift and each P0 invariant violation |
| Canonical alignment | Architecture, security, domain, integration, delivery, quality, and Vietnamese summary docs agree with ADR-006 |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Foundation contract validation | Manifest validates all P0 fields and references; every required negative fixture fails with its contract ID |
| Taxonomy/port boundary | Domain is pure; only `application.ports` can be imported by Platform/Adapters for implementation |
| Consistency protocol | Inbox → snapshot → DecisionRecord → projection → audit → outbox → cursor is defined as one internal transaction |

**Depends on:** ADR-006 acceptance. **Blocks:** Stages 1–13.

### Stage 1: Foundation / Contracts + Domain

**Modules:** Domain types, entity definitions, value objects.

| Deliverable | Description |
|-------------|------------|
| WorkItem schema | Core entity with identity, state, metadata |
| Edge types | `contains`, `blocks`, `requires_gate`, `related_to` |
| Authority statuses | Source precedence rules, provenance tracking |
| DecisionRecord schema | Immutable per-WorkItem decision output with snapshot and policy provenance |
| Decision reproducibility | Complete snapshot/source/graph/policy/pipeline/engine/profile/causation/correlation envelope |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Schema validation | All domain types pass Pydantic/Zod validation |
| Invariant documentation | Every entity has documented invariants |
| Round-trip test | Serialize → deserialize produces identical output |
| Reproducibility rejection | Missing or altered decision-input identity fails deterministically |

---

### Stage 2a: Tenancy + Identity

**Modules:** Platform `identity`, `tenancy`.

| Deliverable | Description |
|-------------|------------|
| Actor identification | Machine vs user identity, token context |
| Tenant scoping | Tenant config, forced RLS, transaction-local workspace context, scoped namespaces |
| Access boundaries | Module-level tenant enforcement |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Isolation test | Production-equivalent non-BYPASSRLS role blocks missing/mismatched context and all cross-workspace paths |
| Identity resolution | Actor correctly identified from token |

**Depends on:** Stage 1.

---

### Stage 2b: Persistence + Ledger + Queue

**Modules:** Platform `audit`, persistence layer, durable queue.

| Deliverable | Description |
|-------------|------------|
| Evidence ledger | Segmented canonical-envelope/payload-hash chain, anchors/WORM proof where threat model requires it |
| WorkItem persistence | Save/load with versioning |
| Durable queue | Fair `SKIP LOCKED` queue with lease CAS, retry schedule, dead letter, controlled replay |
| Cursor management | Track sync progress per TrackerConnection |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Ledger immutability | Payload, envelope, order, and privileged-DB rewrite tampering are detected or anchored evidence fails |
| Checksum chain | Per-workspace chain valid after write sequence |
| Queue idempotency | Replaying same window produces identical entries; lease-losing worker cannot complete |
| Persistence round-trip | Save → load produces identical data |

**Depends on:** Stage 1.

---

### Stage 3: GitHub Connection + Ingestion + Normalization

**Modules:** `connections`, `ingestion`, `normalization`. TrackerConnection adapter for GitHub.

| Deliverable | Description |
|-------------|------------|
| GitHub TrackerConnection | API client, credential lifecycle |
| Marker extraction | Parse `<!-- omc-program:...; issue:... -->` from body text |
| Dependency extraction | Parse `## Blocked by` from body text |
| Parent prose detection | Detect `## Parent` sections (not parsed) |
| Ingestion cycle | Pull raw data, drive sync, manage cursors |
| Normalization | Map GitHub-native types to domain WorkItem schema |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Fixture import | 100% of WF-REF-001 facts reproduced from #539 fixture |
| No invented facts | Import produces nothing beyond source data |
| Marker accuracy | All `<!-- omc-program:...; issue:... -->` markers extracted |
| Edge accuracy | All `## Blocked by` references extracted as edges |
| Ghost reference handling | Non-existent issue numbers handled gracefully |

**Depends on:** Stage 1.

---

### Stage 4: Reconciliation

**Modules:** Reconciliation logic within `ingestion`/`normalization`.

| Deliverable | Description |
|-------------|------------|
| Conflict detection | When multiple sources provide conflicting data |
| Authority merge | Source precedence rules applied (from authority statuses) |
| Staleness detection | Identify outdated snapshots |
| Drift alerts | Emit AttentionItems when reconciliation fails |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Conflict resolution | Precedence rules correctly applied |
| Staleness detection | Outdated data correctly identified |
| No silent data loss | Conflicts always surfaced, never silently dropped |

**Depends on:** Stages 2b, 3.

---

### Stage 5: Graph + Policy + Decision Authority

**Modules:** `graph`, `policies`, `decisions`.

| Deliverable | Description |
|-------------|------------|
| Edge graph construction | Build typed dependency graph from ingested edges |
| Component ordering | Order acyclic dependency components deterministically |
| Typed cycle handling | Reject containment cycles; isolate cyclic dependency SCCs fail-closed |
| Readiness evaluation | Per-WorkItem gate evaluation |
| Blocking logic | Determine what blocks what |
| Priority calculation | Configurable priority rules |
| Decision production | Immutable per-WorkItem records with snapshot and policy provenance |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Typed cycle handling | Containment cycles are rejected; dependency SCCs are isolated while unaffected regions continue |
| Policy determinism | Same input → same readiness result |
| Gate evaluation | Gates correctly evaluate dependency satisfaction |
| WF-REF-001 policy edges | #538→#503 and #487/#503/#521→#474 correctly represented |
| State machine integrity | Only approved transitions execute |

**Depends on:** Stages 2a, 2b, 4.

---

### Stage 6: Evidence + Gates

**Modules:** Gate evaluation wired to evidence ledger.

| Deliverable | Description |
|-------------|------------|
| Evidence-backed gates | Gates check for required EvidenceRecords |
| Gate outcomes | Pass/fail with evidence chain |
| Audit trail | Every gate evaluation recorded in ledger |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Gate-evidence wiring | Gates cannot pass without evidence |
| Audit completeness | Every evaluation recorded |
| Replay accuracy | Ledger replay produces identical gate states |

**Depends on:** Stages 4, 5.

---

### Stage 7: Projections + Proposals + Approvals

**Modules:** `projections`, `approvals`.

| Deliverable | Description |
|-------------|------------|
| Safe auto-projections | Current-state views, labeled as projections |
| Authoritative mutations | Require approval workflow |
| Approval workflows | Human-in-the-loop checkpoints |
| Mutation gating | No authoritative write without approval record |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Projection labeling | All auto-projections carry projection label |
| Approval enforcement | No mutation without approval record |
| Rollback capability | Mutations reversible via evidence ledger |

**Depends on:** Stage 6.

---

### Stage 8: Claims + Attention

**Modules:** AttentionItem generation, claim tracking.

| Deliverable | Description |
|-------------|------------|
| AttentionItems | Engine-emitted signals for anomalies, stale state, human judgment needed |
| Claim tracking | Who owns what, primary vs secondary participation |
| Anomaly detection | Stale state, conflicting authority, blocked items |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Attention emission | Anomalies correctly surfaced |
| No silent failures | Engine stops and asks, never guesses |
| Claim accuracy | Ownership correctly tracked |

**Depends on:** Stage 7.

---

### Stage 9: REST + CLI

**Modules:** `control-room` (API surface).

| Deliverable | Description |
|-------------|------------|
| REST/OpenAPI | Typed endpoints for all domain operations |
| CLI surface | Command-line interface for power users |
| Health endpoints | Liveness, readiness probes |
| Authentication | Token-based auth wired to `identity` |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| OpenAPI spec valid | Spec passes validation |
| End-to-end API test | Create → read → update → delete cycle |
| CLI smoke test | All commands execute without error |
| Auth enforcement | Unauthenticated requests rejected |

**Depends on:** Stage 7.

---

### Stage 10: Control Room UX

**Modules:** `control-room` (human interface).

| Deliverable | Description |
|-------------|------------|
| Recommended Next display | Top-ranked WorkItem with context and rationale |
| Override interface | Human can act on or override recommendations |
| Evidence visibility | Gate outcomes, provenance chain visible |
| Attention dashboard | AttentionItems with action buttons |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Display accuracy | Recommended Next matches engine output |
| Override recording | Overrides tracked with provenance |
| Accessibility | WCAG compliance |

**Depends on:** Stage 9.

---

### Stage 11: Copilot (Bounded)

**Modules:** `copilot`.

| Deliverable | Description |
|-------------|------------|
| Recommendation explanation | Explain deterministic Recommended Next and its evidence gaps |
| Remediation proposals | Propose bounded actions for deterministic validation and human approval |
| Provider isolation | Copilot failure cannot affect readiness, ranking, or persisted decisions |
| AI boundaries | AI explains evidence gaps and proposes remediation; deterministic evaluators interpret evidence and validate any resulting AttentionItem |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Grounding | Explanations cite the DecisionRecord and EvidenceRecord inputs used |
| Auditability | Every proposal and human disposition is traceable |
| AI boundary enforcement | AI never modifies lifecycle state |
| Ranking correctness | Top-ranked item is genuinely ready |

**Depends on:** Stage 10.

---

### Stage 12: Operations + Security

**Modules:** Operational infrastructure, security hardening.

| Deliverable | Description |
|-------------|------------|
| Monitoring | Dashboards, alerts, metrics |
| Deployment profiles | Dev, staging, production configs |
| Security hardening | Auth, tenant isolation, input validation |
| Incident response | Runbooks, escalation procedures |
| Backup/restore | Data recovery procedures |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Alert firing | Thresholds correctly trigger |
| Security audit | Auth, isolation, input validation pass |
| Backup/restore drill | Successful restore from backup |
| Deployment smoke | System starts and serves in each profile |

**Depends on:** Stage 11.

---

### Stage 13: Certification + Cutover

**Modules:** Full product certification, legacy cutover.

| Deliverable | Description |
|-------------|------------|
| Fixture certification | 100% WF-REF-001 facts processed correctly |
| Cutover execution | Per WF-REF-002 phases |
| Legacy retirement | Generator script archived |
| Production DoD | All criteria from §3 met |

**Harness Gate:**

| Gate | Criterion |
|------|-----------|
| Full E2E pipeline | Import → graph → readiness → ranking → display |
| Cutover comparison | Canonical DecisionRecord and managed report semantics match exactly; presentation-only differences require explicit approval |
| Rollback drill | Full rollback < 5 min |
| Production DoD | All §3 criteria met |

**Depends on:** Stage 12.

---

## 3. Production Definition of Done

Work Frontier is **production-ready** when ALL are true:

1. All 13 stages built and gated.
2. All 13 modules implemented per ARCHITECTURE.md.
3. 100% of WF-REF-001 fixture facts processed correctly.
4. Writer ownership states operational (legacy active, shadow, projection active). Stale-write guard active.
5. Evidence ledger append-only with valid checksum chain.
6. Containment cycles are rejected; dependency SCCs are isolated fail-closed without disabling unaffected graph regions.
7. Policy evaluation deterministic.
8. No AI bypasses lifecycle state or gates.
9. REST/OpenAPI spec valid and tested.
10. CLI smoke tested.
11. Control Room UX accessible.
12. Monitoring, alerts, backup/restore operational.
13. Security audit passed.
14. Cutover comparison has exact canonical decision/report semantic parity, with approved presentation-only differences recorded.
15. Rollback tested < 5 min.
16. No P0/P1 open issues.
17. All WF-REF, WF-DEL, ADR, and Vietnamese docs accepted.

---

## 4. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Schema instability | Versioned schemas, migration tests at every gate |
| GitHub API changes | TrackerConnection adapter isolates blast radius |
| Graph cycles in production | Cycle detection rejects mutations, surfaces error |
| AI boundary violations | Deterministic enforcement, no AI in lifecycle paths |
| Cutover fidelity gap | Comparison engine catches; gate blocks cutover |
| Flag infrastructure failure | Flag store has persistence and rollback tests |

---

## 5. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-12 | Initial (6 simplistic modules). | Work Frontier |
| 2026-07-12 | Rewritten: 13 stages aligned with ARCHITECTURE modules, blocking edges, parallel lanes, full harness gates. | Work Frontier |
