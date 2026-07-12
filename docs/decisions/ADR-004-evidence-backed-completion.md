---
id: ADR-004
title: "Evidence-Backed Completion"
status: accepted
owner: Work Frontier architecture
date: 2026-07-12
scope: Work Frontier issue completion
classification: decision
related: [WF-REF-001 §8, WF-DEL-002]
---

# ADR-004: Evidence-Backed Completion

## Status

Accepted

## Context

WF-REF-001 §8 observed that `ready-for-agent` appears on blocked terminal issues, meaning it indicates "scoped and well-defined," not "ready to ship." The team needs a completion standard tying issue closure to verifiable evidence recorded as typed `EvidenceRecord` entries in the evidence ledger.

## Decision

Issue closure requires typed `EvidenceRecord` entries in the evidence ledger satisfying completion policies:

| Completion Policy | Required EvidenceRecord type | Gate |
|-------------------|------------------------------|------|
| **Automated verification** | `EvidenceRecord(type="automated_check", result="pass")` — lint, type-check, tests | CI gate passes; record logged to ledger |
| **Functional verification** | `EvidenceRecord(type="functional_check", result="pass")` — fixture comparison, E2E, or manual test against acceptance criteria | Functional gate passes; record logged to ledger |

Optional policies (per WorkItem type):

| Completion Policy | Required EvidenceRecord type | Gate |
|-------------------|------------------------------|------|
| **Fixture fidelity** | `EvidenceRecord(type="fidelity_check", delta=<0.05)` | Projection comparison passes |
| **Performance** | `EvidenceRecord(type="perf_check", baseline_met=true)` | Benchmark within threshold |
| **Rollback** | `EvidenceRecord(type="rollback_drill", duration_sec=<300)` | Timed rollback passes |

Each `EvidenceRecord` is an append-only ledger entry containing: record type, result, actor (machine or user), timestamp, and the WorkItem it applies to. The ledger's checksum chain ensures immutability.

No WorkItem may reach verified completion without the EvidenceRecords required by its versioned completion policy. Evidence uses the canonical `computed`, `observed`, or `declared` types; policies constrain acceptable sources, attestations, revisions, and combinations rather than inventing additional evidence types.

## Consequences

**+** Typed, auditable completion via evidence ledger and versioned policy. Completion status is reproducible from the relevant snapshot, policy bundle, and evidence chain. Supports cutover comparison (WF-REF-002) with verifiable evidence chains.
**-** Evidence collection and policy evaluation add operational overhead proportional to the configured completion requirements.

---

| Date | Change | Author |
|------|--------|--------|
| 2026-07-12 | Accepted. | Work Frontier |
| 2026-07-12 | Principal audit: replaced generic CI+screenshots with typed EvidenceRecord completion policies. | Work Frontier |
