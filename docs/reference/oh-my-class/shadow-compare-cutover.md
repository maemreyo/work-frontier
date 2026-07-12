---
id: WF-REF-002
title: "Cutover Plan: Legacy Script Writer to Work Frontier Managed Projection"
status: accepted
owner: Work Frontier integration maintainers
date: 2026-07-12
scope: Work Frontier cutover pipeline
classification: reference
depends_on: [WF-REF-001]
---

# WF-REF-002: Cutover Plan

## Purpose

Defines the controlled cutover from the **legacy script writer** (the ad-hoc script producing the single generated issue #539) to **Work Frontier's managed projection** (the deterministic pipeline producing reference facts, delivery plans, ADRs, and curated docs from issue snapshots). The cut replaces a single-owner script writer with a full-body projection under controlled writer ownership.

---

## 1. What Is Being Cut Over

| | Legacy script writer | Work Frontier managed projection |
|---|---|---|
| Scope | Single generated issue (#539) | Full-body projection: reference facts, delivery plans, ADRs, curated docs |
| Input | Script reads GitHub issues directly | Importer reads via API into Snapshot Store |
| Processing | Script-specific, no normalization | Deterministic pipeline with typed domain models |
| Output | One report (#539) | Coordinated doc set with projection markers |
| Writer ownership | Script owns all output | One owner (Work Frontier pipeline); stale-write detection prevents out-of-date writes |
| Traceability | None | Evidence ledger, provenance chain |
| Marker handling | Script writes markers directly | Reads markers; proposes changes via approval workflow |
| Rollback | Re-run script | Rollback restores old writer |

---

## 2. Cutover Principles

| Principle | Rationale |
|-----------|----------|
| Legacy script stays deployable | Re-run at any time to restore old output |
| Shadow mode runs both | Only legacy output ships until comparison passes |
| One owner | Single projection pipeline owns all output; no competing writers |
| Stale-write detection | Projection refuses to write when input snapshot is older than current output |
| Projection markers | All projection output carries markers identifying provenance |
| Marker ownership is safe | Projection never overwrites markers without approval |
| Rollback restores old writer | Flip restores legacy script as active writer |

---

## 3. Cutover Phases

### Phase 1: Import

**Goal:** Reliable ingestion of the #539 fixture into a normalized snapshot.

| Activity | Harness Gate |
|----------|-------------|
| Parse GitHub issue bodies, labels, states | Schema validation |
| Extract `<!-- omc-program:...; issue:... -->` markers | 100% marker extraction on fixture |
| Extract `## Blocked by` dependency references | All WF-REF-001 §6 edges reproduced |
| Classify nodes (Epic, terminal, generated report) | Classification matches WF-REF-001 §5 |
| Detect `## Parent` prose sections | Prose sections detected (not parsed) |

**Exit:** 100% of WF-REF-001 facts reproduced. No invented facts.

### Phase 2: Shadow

**Goal:** Projection runs alongside legacy; only legacy ships.

| Activity | Harness Gate |
|----------|-------------|
| Both engines process same fixture | Both complete without error |
| Log projection output | Output schema valid |
| Semantic comparison | Exact canonical semantic parity; differences are classified before approval |

### Phase 3: Compare Exact DecisionRecord/Report

**Goal:** Field-by-field comparison of the exact DecisionRecord/report output.

| Activity | Harness Gate |
|----------|-------------|
| Compare canonical DecisionRecord and managed report semantics | Exact semantic parity; presentation-only differences require explicit approval |
| Projection marker present on all output | 100% marker coverage |
| Link integrity | 100% resolve |
| ADR compliance | 100% format |

### Phase 4: Approval

**Goal:** Team reviews comparison evidence and approves cutover.

| Activity | Harness Gate |
|----------|-------------|
| Team review of comparison report | Majority approval |
| Rollback tested | Restores old writer in < 5 min |
| Stale-write detection tested | Rejects stale snapshot |

### Phase 5: Disable Old Workflow and Claim Owner

**Goal:** Legacy script is disabled; Work Frontier becomes the sole writer.

| Activity | Harness Gate |
|----------|-------------|
| Disable legacy script writer | Legacy cannot produce output |
| Work Frontier claims writer ownership | One owner confirmed |
| Stale-write guard active | Out-of-date snapshots rejected |

### Phase 6: Publish

**Goal:** Projection output ships as the authoritative source.

| Activity | Harness Gate |
|----------|-------------|
| Projection output published | All projection markers present |
| No regression in output semantics | Exact semantic parity maintained; approved presentation differences recorded |
| Legacy preserved for rollback | Rollback test passes |

### Phase 7: Observe

**Goal:** Monitor stability of projection-owned output.

| Activity | Harness Gate |
|----------|-------------|
| Monitor output stability | Error rate < 1% |
| Stale-write incidents | Zero unintended stale writes |
| Edge-case processing | Robustness confirmed |

### Phase 8: Legacy Verify-Only/Retire

**Goal:** Legacy script moves to verify-only, then retires.

| Activity | Harness Gate |
|----------|-------------|
| Legacy in verify-only mode | Can read but not write |
| Archive legacy script | Version control |
| Remove legacy write paths | CI green |
| Doc update | Links verified |

---

## 4. Marker Safety

| Action | Allowed? | Gate |
|--------|---------|------|
| Read markers | Yes | Import |
| Propose changes | Yes | Approval workflow |
| Write without approval | **No** | Blocked by design |
| Delete markers | **No** | Blocked by design |

---

## 5. Rollback

| Trigger | Action |
|---------|--------|
| Any unapproved canonical semantic difference | Rollback: restore old writer |
| Error rate > 5% | Rollback: restore old writer |
| Critical inaccuracy | Rollback, investigate |
| Stale-write incident | Rollback: restore old writer |

Rollback restores the legacy script as active writer. < 5 min. No deploy.

---

## 6. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-12 | Initial (incorrect model). | Work Frontier |
| 2026-07-12 | Rewritten: legacy generator script → managed projection. Added marker safety. | Work Frontier |
| 2026-07-12 | Principal audit: corrected to 8 phases (import→shadow→compare exact DecisionRecord/report→approval→disable old workflow and claim owner→publish→observe→legacy verify-only/retire). Removed canary traffic, output types, A/B preference, invented 8.5-week schedule. Added one owner, stale-write detection, projection markers. Rollback restores old writer. | Work Frontier |
