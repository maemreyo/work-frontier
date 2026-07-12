---
id: WF-DEL-002
title: "Traceability Matrix: Work Frontier Requirements"
status: accepted
owner: Work Frontier delivery
date: 2026-07-12
scope: Work Frontier
classification: delivery
depends_on: [WF-REF-001, WF-DEL-001, ADR-002, ADR-003, ADR-004]
---

# WF-DEL-002: Traceability Matrix

## Purpose

Maps every Work Frontier requirement family to its implementing module(s), documentation reference, harness gate(s), and evidence requirement.

---

## 1. Requirement Family → Module Mapping

### Domain Layer

| Requirement Family | Module | Key invariants | Harness Gate |
|-------------------|--------|---------------|-------------|
| Actor identification | `identity` | Machine vs user correctly resolved | Stage 2a: identity resolution |
| Tenant isolation | `tenancy` | Cross-tenant access blocked | Stage 2a: isolation test |
| Tracker connection | `connections` | Credential lifecycle managed | Stage 3: fixture import |
| Dependency graph | `graph` | Containment cycles rejected; dependency SCCs isolated fail-closed | Stage 5: typed cycle handling |
| Readiness policy | `policies` | Deterministic: same input → same output | Stage 5: policy determinism |
| Decision lifecycle | `decisions` | State changes via approved transitions only | Stage 5: state machine integrity |
| Evidence ledger | `audit` | Append-only, checksum chain | Stage 2b: ledger immutability |

### Application Layer

| Requirement Family | Module | Key invariants | Harness Gate |
|-------------------|--------|---------------|-------------|
| Data ingestion | `ingestion` | Idempotent sync, cursor management | Stage 3: fixture import |
| Type normalization | `normalization` | Tracker-native → domain types | Stage 3: marker/edge accuracy |
| Safe projections | `projections` | Auto-projections labeled; mutations require approval | Stage 7: projection labeling |
| Approval workflows | `approvals` | No mutation without approval record | Stage 7: approval enforcement |
| Recommended Next | `decisions` | Deterministic frontier and lexicographic ranking | Stage 5: decision determinism |
| Recommendation explanation | `copilot` | Bounded explanation or proposal; never ranking authority | Stage 11: AI boundary |

### Interfaces Layer

| Requirement Family | Module | Key invariants | Harness Gate |
|-------------------|--------|---------------|-------------|
| REST/OpenAPI | `control-room` | Spec valid, endpoints typed | Stage 9: OpenAPI validation |
| CLI | `control-room` | Commands execute correctly | Stage 9: CLI smoke test |
| Health probes | `control-room` | Liveness/readiness correct | Stage 12: deployment smoke |
| Control Room UX | `control-room` | Recommended Next displayed, overrides tracked | Stage 10: display accuracy |

---

## 2. Requirement Family → Documentation Mapping

| Requirement Family | Primary doc | Reference doc |
|-------------------|------------|--------------|
| Domain types | ARCHITECTURE.md §4 | ADR-003 |
| Tracker neutrality | ADR-002 | ARCHITECTURE.md §3 |
| Evidence ledger | ARCHITECTURE.md §4.1 | ADR-004 |
| Graph/policy | ARCHITECTURE.md §4.1 | WF-DEL-001 Stage 5 |
| Cutover | WF-REF-002 | ADR-005 |
| Fixture facts | WF-REF-001 | WF-DEL-001 Stage 3 |
| Completion standard | ADR-004 | WF-DEL-001 Stage 13 |
| Module taxonomy | ADR-003 | ARCHITECTURE.md §3 |

---

## 3. Requirement Family → Harness Gate + Evidence Mapping

| Requirement Family | Stage | Gate | Evidence required |
|-------------------|-------|------|------------------|
| Domain schema | 1 | Schema validation | Round-trip test |
| Tenancy isolation | 2a | Isolation test | Cross-tenant block test |
| Identity resolution | 2a | Identity test | Token resolution test |
| Ledger integrity | 2b | Immutability + checksum | Write-sequence test |
| Queue idempotency | 2b | Replay test | Identical-output test |
| Marker extraction | 3 | 100% on fixture | WF-REF-001 marker coverage |
| Edge extraction | 3 | 100% on fixture | WF-REF-001 §6 edge coverage |
| No invented facts | 3 | Negative tests | Empty-output on invalid input |
| Reconciliation | 4 | Precedence test | Conflict resolution test |
| Typed cycle handling | 5 | Containment-cycle rejection and dependency-SCC isolation | Localized fail-closed test |
| Policy determinism | 5 | Same-input test | Identical-readiness test |
| Gate-evidence wiring | 6 | Gate enforcement | Evidence-required test |
| Projection labeling | 7 | Label check | Auto-projection test |
| Approval enforcement | 7 | Approval gate | No-mutation-without-approval test |
| Attention emission | 8 | Anomaly surfacing | Anomaly-detection test |
| REST validation | 9 | OpenAPI spec | Spec-valid test |
| CLI smoke | 9 | Command execution | All-commands-pass test |
| UX accuracy | 10 | Display match | Recommended-Next match test |
| Ranking determinism | 11 | Same-input ranking | Identical-output test |
| AI boundary | 11 | Lifecycle isolation | AI-no-state-change test |
| Security audit | 12 | Auth + isolation | Pen-test or checklist |
| Backup/restore | 12 | Restore drill | Successful-restore test |
| Fixture certification | 13 | 100% fixture coverage | WF-REF-001 full processing |
| Cutover semantic parity | 13 | Exact canonical parity; approved presentation-only differences recorded | WF-REF-002 comparison report |
| Rollback speed | 13 | < 5 min | Timed rollback test |

---

## 4. Fixture → Module → Gate Mapping

How the oh-my-class fixture (WF-REF-001) exercises the system:

| Fixture fact (WF-REF-001) | Module processing it | Gate validating it |
|--------------------------|---------------------|-------------------|
| `<!-- omc-program:...; issue:... -->` markers | `normalization` | Stage 3: marker extraction |
| `## Blocked by` dependencies | `normalization`, `graph` | Stage 3: edge extraction |
| `## Parent` prose detection | `normalization` | Stage 3: parent prose detection |
| 5 Epics, 5 terminals | `normalization` | Stage 3: fixture import |
| Policy edges (#538→#503, etc.) | `graph` | Stage 5: WF-REF-001 edge coverage |
| `ready-for-agent` = scoped | `policies` | Stage 5: label semantics |
| Execution checklist = assertion | `decisions` | Stage 5: checklist-as-assertion |

---

## 5. Coverage Check

Every requirement family has: module, doc, gate, evidence. No orphan.

| Family | Module | Doc | Gate | Evidence | Coverage |
|--------|--------|-----|------|----------|----------|
| Domain schema | Yes | Yes | Yes | Yes | Complete |
| Tenancy | Yes | Yes | Yes | Yes | Complete |
| Identity | Yes | Yes | Yes | Yes | Complete |
| Connections | Yes | Yes | Yes | Yes | Complete |
| Ingestion | Yes | Yes | Yes | Yes | Complete |
| Normalization | Yes | Yes | Yes | Yes | Complete |
| Graph | Yes | Yes | Yes | Yes | Complete |
| Policies | Yes | Yes | Yes | Yes | Complete |
| Decisions | Yes | Yes | Yes | Yes | Complete |
| Audit | Yes | Yes | Yes | Yes | Complete |
| Projections | Yes | Yes | Yes | Yes | Complete |
| Approvals | Yes | Yes | Yes | Yes | Complete |
| Copilot | Yes | Yes | Yes | Yes | Complete |
| Control Room | Yes | Yes | Yes | Yes | Complete |
| Security | Yes | Yes | Yes | Yes | Complete |
| Cutover | Yes | Yes | Yes | Yes | Complete |

---

## 6. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-12 | Initial (incorrect: oh-my-class issue mapping). | Work Frontier |
| 2026-07-12 | Rewritten: requirement families → modules/docs/harness/evidence. | Work Frontier |
| 2026-07-12 | Principal audit: verified consistency with corrected WF-REF-001 §6 policy edges. | Work Frontier |
