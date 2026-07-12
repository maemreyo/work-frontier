---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DEC-01, WF-DEC-02
---

# Work Frontier Documentation

Work Frontier is a **dependency-aware readiness control plane**. Its core engine, the **Frontier Engine**, is a pure, stateless computation: snapshot plus policy produces an immutable, persisted [DecisionRecord](domain/decision-record.md). The **product layer** handles persistence, ingestion, and state management. The **Frontier Control Room** is the human-facing surface.

These docs define the product scope, domain model, and engineering conventions for Work Frontier. English is the canonical language. Every normative concept appears in exactly one file; other files link to it.

## Canonical Visible Entities

The Control Room exposes these entities to the user:

| Entity | Purpose | Domain doc |
|--------|---------|-----------|
| **Program** | Logical grouping of related WorkItems with typed containment DAG, status rollup, and external blockers. | [Program](domain/program.md) |
| **WorkItem** | Base unit of work. The universal representation of a task. | [WorkItem](domain/work-item.md) |
| **DecisionRecord** | Immutable, persisted decision output from the Frontier Engine. Each cycle produces a new record. | [DecisionRecord](domain/decision-record.md) |
| **Recommended Next** | Top-ranked DecisionRecord with full context and rationale. | [Recommended Next](domain/recommended-next.md) |
| **Gate** | Checkpoint requiring evidence before lifecycle advancement. | [Gate](domain/gates-and-evidence.md) |
| **EvidenceRecord** | Typed, revision-bound, signed/attested proof that a gate condition has been met. AI output never counts as evidence. | [EvidenceRecord](domain/gates-and-evidence.md#evidencerecord) |
| **WorkLease** | Coordination lease held by a claimant (human, agent, or automation). Not a mutation lock. Never held by engine or tracker. | [WorkLease](domain/work-lease.md) |
| **AttentionItem** | Signal requiring human judgment. Fixed categories: decision_changed, authority_downgraded, claim_at_risk, approval_required, evidence_required, graph_conflict, connection_degraded, certification_ready, security_action, capacity_action. | [AttentionItem](domain/attention-items.md) |
| **TrackerConnection** | Live link to an external tracker. | [TrackerConnection](domain/tracker-connection.md) |

## Docs Tree

```
docs/
├── index.md                                    ← you are here
│
├── product/
│   ├── vision.md                               WF-PROD-01  Vision and positioning
│   ├── users-and-jobs.md                       WF-PROD-02  Users, jobs-to-be-done, non-goals
│   └── overview.md                             WF-PROD-03  Product overview (ties product to domain)
│
├── domain/
│   ├── terminology.md                          WF-DOM-01   Canonical glossary
│   ├── work-item.md                            WF-DOM-12   WorkItem (base entity)
│   ├── decision-record.md                      WF-DOM-07   DecisionRecord (immutable decision output)
│   ├── program.md                              WF-DOM-13   Program (containment DAG, rollup)
│   ├── recommended-next.md                     WF-DOM-14   Recommended Next (ranking output)
│   ├── tracker-connection.md                   WF-DOM-15   TrackerConnection (adapter)
│   ├── edges.md                                WF-DOM-16   Typed edges (contains/blocks/requires_gate/related_to)
│   ├── authority-statuses.md                   WF-DOM-17   Authority statuses and precedence
│   ├── readiness-ranking.md                    WF-DOM-18   Readiness and lexicographic ranking pipeline
│   ├── gates-and-evidence.md                   WF-DOM-06   Gates and EvidenceRecords
│   ├── work-lease.md                           WF-DOM-19   WorkLease (coordination lease)
│   ├── attention-items.md                      WF-DOM-10   AttentionItem
│   ├── lifecycle-and-completion.md             WF-DOM-04   Lifecycle and completion policies
│   └── state-machines.md                       WF-DOM-11   Formal state machine definitions
│
├── architecture/
│   └── ARCHITECTURE.md                         WF-ARCH-01  System architecture overview
│
├── decisions/
│   ├── ADR-index.md                            ADR         ADR index and process
│   ├── ADR-002-tracker-neutral-engine.md       ADR-002     Tracker-neutral engine design
│   ├── ADR-003-modular-monolith.md             ADR-003     Modular monolith deployment
│   ├── ADR-004-evidence-backed-completion.md   ADR-004     Evidence-backed completion
│   └── ADR-005-github-first-controlled-cutover.md ADR-005  GitHub-first controlled cutover
│
├── integrations/
│   └── GITHUB.md                               WF-INT-01   GitHub TrackerConnection
│
├── ux/
│   ├── ux-architecture.md                      WF-UX-01    Control Room architecture
│   ├── ux-critical-journeys.md                 WF-UX-02    Critical user journeys
│   ├── ux-onboarding.md                        WF-UX-03    Onboarding flow
│   └── ux-accessibility-design-system.md       WF-UX-04    Accessibility and design system
│
├── security/
│   ├── threat-model.md                         WF-SEC-01   Threat model
│   ├── authorization.md                        WF-SEC-02   Authorization model
│   ├── ai-governance.md                        WF-SEC-03   AI governance bounds
│   ├── tenancy-isolation.md                    WF-SEC-04   Tenancy and data isolation
│   └── secure-development-lifecycle.md         WF-SEC-05   Secure development lifecycle
│
├── quality/
│   ├── verification-strategy.md                WF-HAR-01   Verification strategy
│   ├── harness-catalog.md                      WF-HAR-02   Test harness catalog
│   ├── performance-envelope.md                 WF-PERF-01  Performance envelope
│   └── release-certification.md                WF-HAR-03   Release certification
│
├── operations/
│   ├── deployment-profiles.md                  WF-OPS-01   Deployment profiles
│   ├── slo-observability.md                    WF-OPS-02   SLOs and observability
│   ├── incident-response.md                    WF-OPS-03   Incident response runbook
│   ├── backup-restore-dr.md                    WF-OPS-04   Backup, restore, disaster recovery
│   └── upgrades-compatibility.md               WF-OPS-05   Upgrades and compatibility
│
├── delivery/
│   ├── implementation-sequence.md              WF-DEL-01   Implementation sequence
│   └── traceability-matrix.md                  WF-DEL-02   Requirement traceability
│
├── reference/
│   └── oh-my-class/
│       ├── verified-facts.md                   WF-REF-01   Verified facts (oh-my-class)
│       └── shadow-compare-cutover.md           WF-REF-02   Shadow compare cutover
│
└── vi/
    ├── work-frontier-overview.md               (Vietnamese) Product overview
    ├── glossary.md                             (Vietnamese) Glossary
    ├── operations-overview.md                  (Vietnamese) Operations overview
    └── user-journeys.md                        (Vietnamese) User journeys
```

## Metadata Convention

Every doc carries YAML frontmatter with these fields:

```yaml
---
Status: Draft | Active | Deprecated
Owner: <team or person>
Last reviewed: YYYY-MM-DD
Source of truth: <file path or external URL>
Related requirements: <comma-separated WF-IDs or ADR-NNN>
---
```

- **Status** is `Draft` until reviewed by its Owner and at least one domain stakeholder. Moves to `Active` after review. Becomes `Deprecated` when superseded, which must link back.
- **Owner** is accountable for accuracy. Every change must be reviewable by Owner.
- **Last reviewed** tracks staleness, not last edit. Review means someone read the whole file and confirmed it reflects reality.
- **Source of truth** is where the canonical version lives. If defined in code, point to the source file.

## Requirement ID Convention

| Prefix | Scope | Where defined |
|--------|-------|---------------|
| `WF-PROD` | Product: what the system does, who it serves, what it doesn't | `docs/product/` |
| `WF-DOM` | Domain: entity definitions, state machines, invariants, graph rules | `docs/domain/` |
| `WF-ARCH` | Architecture: system structure, deployment, module boundaries | `docs/architecture/` |
| `WF-INT` | Integrations: TrackerConnection contracts, sync protocols | `docs/integrations/` |
| `WF-UX` | User experience: Control Room design, journeys, accessibility | `docs/ux/` |
| `WF-SEC` | Security: threat model, authorization, AI governance, tenancy | `docs/security/` |
| `WF-HAR` | Quality/verification: test strategy, harnesses, release certification | `docs/quality/` |
| `WF-PERF` | Performance: latency, throughput, resource envelopes | `docs/quality/` |
| `WF-OPS` | Operations: deployment, monitoring, incident response, DR | `docs/operations/` |
| `WF-REF` | Reference: verified facts, external documentation | `docs/reference/` |
| `WF-DEL` | Delivery: implementation sequence, traceability | `docs/delivery/` |
| `ADR` | Architecture Decision Records: irreversible design choices | `docs/decisions/` |

IDs are sequential within their prefix. When a requirement splits, the original retains its ID and the new one gets the next available number with a reference back. IDs are never reused.

## Reading Order

1. [product/vision.md](product/vision.md) — what and why.
2. [product/users-and-jobs.md](product/users-and-jobs.md) — who.
3. [product/overview.md](product/overview.md) — how the pieces connect.
4. [domain/terminology.md](domain/terminology.md) — shared vocabulary.
5. [domain/work-item.md](domain/work-item.md) — the core entity.
6. Then pick by interest: [readiness-ranking.md](domain/readiness-ranking.md) for the control plane core, [edges.md](domain/edges.md) for the graph model, [authority-statuses.md](domain/authority-statuses.md) for the trust model.

## Cross-Linking Rules

- Every domain entity is defined once, in its own file. Other files reference it by name and link.
- No doc repeats a definition. Link to [terminology.md](domain/terminology.md) or the entity's own file.
- Diagrams spanning multiple concepts go in the most specific file and are referenced elsewhere.
- When two files disagree, the narrower scope wins. If equal scope, the lower WF-ID wins.
