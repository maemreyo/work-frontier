# full-product-implementation - Work Plan

## TL;DR (For humans)
**What you'll get:** A complete standalone Work Frontier product: deterministic readiness engine, GitHub integration, secure multi-tenant control plane, accessible Control Room, operational deployment profiles, certified release evidence, and controlled #539 cutover with rollback.

**Why this approach:** The build starts only after a hard foundation-contract gate proves a single module taxonomy, port ownership, reproducible decisions, payload-safe audit evidence, forced workspace isolation, and atomic internal consistency. It then proceeds as tested vertical slices through the pure engine, persistence, GitHub, workflows, interfaces, UI, and production certification.

**What it will NOT do:** It will not split into microservices, turn audit history into event-sourced current state, add other production trackers, give AI decision authority, or claim production capacity without executable proof.

**Effort:** XL
**Risk:** High - greenfield implementation spans security-critical domain logic, three runtime processes, external GitHub cutover, and 67 release harnesses.
**Decisions to sanity-check:** Python/FastAPI backend plus React/Vite frontend; PostgreSQL-backed queue with MinIO/S3; Copilot disabled by default; full 72-hour soak retained for GA certification.

Your next move: run a high-accuracy review or start execution through the dedicated worker. Full execution detail follows below.

---

> TL;DR (machine): XL/high-risk greenfield build; 35 dependency-ordered implementation todos plus four independent final gates deliver all 13 modules, 67 harnesses, Standard certification, and #539 cutover.

## Scope
### Must have
- A standalone repository with Python backend, React/TypeScript Control Room, PostgreSQL 16, S3-compatible evidence storage, and reproducible local/CI environments.
- All 13 canonical modules behind enforced import seams; `audit` is Platform, not Domain.
- ADR-006 foundation-contract preflight completes before any Todo 1–5 work: one canonical taxonomy, Application-owned outbound ports, reproducible DecisionRecord envelope, payload-safe segmented audit chain, forced RLS, and atomic inbox/outbox protocol.
- Pure deterministic snapshot + policy → immutable DecisionRecord-set engine, phased gates, authority provenance, typed containment-cycle rejection, and localized dependency-SCC isolation.
- Resource-scoped identity/tenancy/RBAC/SoD, append-only-with-retention evidence/audit, durable inbox/queue, idempotent sync, reconciliation, and stale-write fencing.
- GitHub Level-3 production adapter and frozen #539 reference fixture; explicit `legacy_active`, `shadow`, and `projection_active` writer ownership.
- REST/OpenAPI, CLI parity, web/worker/scheduler processes, four accessible Control Room views, optional provider-neutral Copilot, hosted/self-hosted deployment artifacts, and signed release certification.
- All 67 harness contracts implemented. Sixty-four block every Standard-envelope release; Large and Tenant Aggregate capacity harnesses block only releases declaring those envelopes.

### Must NOT have (guardrails, anti-slop, scope boundaries)
- No microservices, event-sourced current state, non-GitHub production adapter, mandatory cache, or consumer-specific imports.
- No AI influence over readiness, ranking, gates, evidence, lifecycle, or approvals; the product must be fully usable with Copilot disabled.
- No hand-maintained duplicate Python/TypeScript contracts, `any`, type suppression, bare secrets, silent conflict resolution, silent truncation, or unscoped database access.
- No direct GitHub projection write before cutover approval and writer-lease ownership; deployment never implies activation.
- No claim of HA, Large-envelope, Tenant Aggregate, or production certification without its executable evidence.
- Do not copy stale `packages/`, `services/`, `apps/`, or oh-my-class `AGENTS.md` harness paths; translate every command to this standalone layout.

## Intentional Deviations from Original Plan

### React/Vite Frontend
**Original Plan**: React/Vite frontend for Control Room (mentioned in lines 12, 22)  
**Current Implementation**: TypeScript/Vitest/Zod stack without React UI framework  
**Rationale**: Current stack is sufficient for contract testing and type safety. Frontend directory exists with working TypeScript configuration, Vitest test infrastructure, and Zod contract validation.  
**Future Path**: Playwright is available for E2E testing when backend UI implementation begins. React/Vite can be added at that time without disrupting the current contract testing foundation.  
**Status**: Intentionally deferred, not missing.

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: strict TDD. Python uses pytest + Hypothesis + Schemathesis; TypeScript uses Vitest; browser paths use Playwright + axe; capacity uses k6; security uses ZAP/gitleaks/pip-audit/npm audit.
- Each todo starts with a failing contract/integration/product test, implements the smallest passing vertical slice, and emits structured evidence under its numbered `.omo/evidence/task-*-full-product-implementation/` directory.
- `Makefile` is the stable orchestration surface: `make check-static`, `make test-domain`, `make test-contract`, `make test-integration`, `make test-product`, `make test-security`, `make test-ops`, and `make certify-standard`.
- Unit tests may fake ports; integration tests use real PostgreSQL 16 and MinIO. GitHub deterministic tests use frozen fixtures; Level-3 certification uses an isolated GitHub sandbox.
- Every claimed pass must include command, exit code, machine-readable result, relevant logs, and for UI paths screenshots plus API trace. Self-report and grep-only checks do not count.
- Generated OpenAPI/Zod/types and migration outputs are checked for a clean regeneration diff.

## Execution strategy
### Parallel execution waves
> Target 5-8 todos per wave. Fewer than 3 (except the final) means you under-split.

- **Preflight P0 — Foundation contracts:** ADR-006 and the canonical docs/harness registry must pass the contract gate before Todo 1 begins; this is a hard blocker, not a documentation-only sign-off.
- **Wave 0 — Bootstrap:** Todos 1-5 in dependency order where noted; establishes repository truth and executable gates after Preflight P0.
- **Wave 1 — Pure core:** Todos 6-10 parallel by module after contracts land; converges on deterministic DecisionRecord sets.
- **Wave 2 — Platform:** Todos 11-15 parallel around one migration baseline; converges on transactional persistence and security context.
- **Wave 3 — GitHub tracer bullet:** Todos 16-20; frozen fixture and adapter can proceed in parallel, then ingest/reconcile/solve converge.
- **Wave 4 — Workflow and interfaces:** Todos 21-25; gates/approvals/leases feed API, CLI, and three processes.
- **Wave 5 — Control Room:** Todos 26-30 parallel by view after API contracts stabilize.
- **Wave 6 — Production:** Todos 31-35; Copilot remains optional while security, operations, certification, and cutover finish.
- **Wave 7 — Final verification:** F1-F4 run in parallel only after all implementation todos pass.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| P0 | ADR-006 canonical documentation | 1-35 | — |
| 1 | P0 | 2-5 | — |
| 2 | 1 | 6-35 | 3,4 |
| 3 | 1 | 11,16,33 | 2,4 |
| 4 | 1 | 26-30 | 2,3 |
| 5 | 2-4 | all feature waves | — |
| 6-10 | 2,5 | 14,19,21 | each other where types are stable |
| 11 | 3,6 | 12-25 | 15 after base schema settles |
| 12 | 3,9,11 | 13,19,21,23,32,34 | 15 |
| 13 | 3,11,12 | 18,19,22,23,34 | 15 |
| 14 | 10-13 | 19,21,24 | 15 |
| 15 | 11,12 | 18,21-24,32,34 | 13-14 after base schema settles |
| 16 | 5,6 | 19,34 | 17 |
| 17 | 2,6 | 18,19,34 | 16 |
| 18 | 13,15,17 | 19,34,35 | 16 after 17's contract stabilizes |
| 19 | 7-18 | 20-25 | — |
| 20 | 19 | 33,35 | — |
| 21-23 | 10,12-15,19 | 24-30 | each other |
| 24-25 | 21-23 | 26-35 | each other |
| 26-30 | 24 | 33-35 | each other |
| 31 | 24,26 | 34 | 32,33 |
| 32 | 11-15,24-30 | 34 | 31,33 |
| 33 | 3,20,24-30 | 34,35 | 31,32 |
| 34 | 1-33 | 35,F1-F4 | — |
| 35 | 18-20,25,33,34 | F1-F4 | — |

## Todos
> Implementation + Test = ONE todo. Never separate.
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->
- [x] P0. Pass the ADR-006 foundation-contract gate before implementation
  What to do / Must NOT do: Reconcile all canonical and curated docs to ADR-006; define a machine-readable manifest with exactly `WF-P0-01` taxonomy/port ownership, `WF-P0-02` DecisionRecord reproducibility, `WF-P0-03` forced-RLS workspace isolation, `WF-P0-04` canonical audit/anchor integrity, `WF-P0-05` atomic inbox-to-outbox consistency, `WF-P0-06` lease/CAS queue safety, and `WF-P0-07` honest p95/p99 measurement. Do not scaffold runtime packages, migrations, or product features until this gate passes.
  Parallelization: Preflight P0 | Blocked by: ADR-006 | Blocks: 1-35
  References: `docs/decisions/ADR-006-foundation-contracts.md`; `docs/architecture/ARCHITECTURE.md:58-237,302-472`; `docs/domain/decision-record.md`; `docs/security/tenancy-isolation.md`; `docs/quality/verification-strategy.md:54-74`; `docs/quality/harness-catalog.md`
  Acceptance criteria: canonical-doc/link/term validator passes; manifest contains exactly `WF-P0-01` through `WF-P0-07`; positive fixtures validate all seven contracts; negative fixtures fail deterministically with their contract ID: `WF-P0-01` taxonomy drift/Domain I-O or wrong port owner; `WF-P0-02` each missing or altered reproducibility identity; `WF-P0-03` absent/mismatched workspace plus direct SQL/cache/object/job/inbox/audit/idempotency cross-scope matrix; `WF-P0-04` payload/actor/timestamp/order/envelope/segment-rewrite tampering and missing required anchor/WORM proof; `WF-P0-05` every internal crash boundary, stale outbox fingerprint, and partial commit; `WF-P0-06` duplicate claim, lease-loss completion, retry, dead-letter, and controlled poison replay; `WF-P0-07` rejected outlier removal and missing failure/timeout reporting. Evidence `.omo/evidence/preflight-adr-006/`.
  QA scenarios: happy—validate all seven manifest contracts and their positive fixtures against canonical docs; failure—inject every listed fixture and assert its precise `WF-P0-*` failure ID. Evidence `.omo/evidence/preflight-adr-006/`.
  Evidence: `.omo/evidence/preflight-adr-006/validation.json` records 7/7 contract IDs, 7 positive fixtures, 16 negative fixtures, and zero validation failures.
  Commit: Y | `docs(architecture): gate implementation on foundation contracts`

- [x] 1. Bootstrap the standalone repository and pin toolchains
  What to do / Must NOT do: Create `backend/src/work_frontier/{domain,platform,application,adapters,interfaces}`, `frontend/src`, `tests`, `scripts`, `infra`, `evidence`; pin Python 3.13 with uv/`pyproject.toml`, Node LTS with package manager lockfile, React/Vite/TypeScript strict, pytest/Hypothesis, Ruff, basedpyright, Biome, Vitest, Playwright. Add `Makefile`, `.env.example`, `.editorconfig`, ignore files, license/readme. Do not create oh-my-class-style directories or runtime coupling.
  Parallelization: Wave 0 | Blocked by: P0 | Blocks: 2-35
  References: `docs/decisions/ADR-006-foundation-contracts.md`; `docs/architecture/ARCHITECTURE.md:46-186,587-606`; `docs/quality/harness-catalog.md:20-82`
  Acceptance criteria: `make bootstrap && make check-static` exits 0 from a clean clone; Python and TypeScript hello-contract tests pass; lockfiles are present and reproducible.
  QA scenarios: happy—run bootstrap twice and compare clean status; failure—inject forbidden import and type error, assert gates fail. Evidence `.omo/evidence/task-1-full-product-implementation/`.
  Evidence: `.omo/evidence/task-1-full-product-implementation/verification.json` records passing bootstrap, static, test, Python import, and frontend contract checks.
  Commit: Y | `chore(repo): bootstrap standalone toolchains`

- [x] 2. Encode and enforce the 13-module dependency architecture
  What to do / Must NOT do: Add package public interfaces, dependency rules, `scripts/check_import_boundaries.py`, architecture test fixtures, and root `AGENTS.md` pointing to canonical docs. Follow ADR-006: Domain only pure types/functions; Platform owns identity/tenancy/connections/audit durability; Application owns outbound ports and inbound use cases; Adapters satisfy Application ports; Interfaces call Application. Never allow concrete adapter imports in Application or any I/O dependency in Domain.
  Parallelization: Wave 0 | Blocked by: 1 | Blocks: 6-35
  References: `docs/decisions/ADR-006-foundation-contracts.md`; `docs/architecture/ARCHITECTURE.md:58-186`; `docs/quality/harness-catalog.md:44-52`
  Acceptance criteria: standalone boundary command exits 0; mutation tests for every forbidden edge and wrong port owner fail with path/rule; no external-repo path reference remains.
  QA scenarios: happy—scan valid skeleton; failure—fixture imports adapter from domain and is rejected. Evidence `.omo/evidence/task-2-full-product-implementation/`.
  Evidence: `.omo/evidence/task-2-full-product-implementation/verification.json` records the passing checker, one permitted ports exception, six rejected forbidden edges, and a passing full static/test gate.
  Commit: Y | `build(architecture): enforce module boundaries`

- [x] 3. Establish local/CI infrastructure and migration harness
  What to do / Must NOT do: Create Compose with PostgreSQL 16 and MinIO, backend/dev containers, health checks, isolated CI profile, GitHub Actions pipeline, Alembic baseline, test database lifecycle, SBOM and secret scanning. Compose is single-node and must never be labelled HA.
  Parallelization: Wave 0 | Blocked by: 1 | Blocks: 11,16,33
  References: `docs/operations/deployment-profiles.md:10-69,110-151,179-187`; `docs/architecture/ARCHITECTURE.md:230-284`; `docs/quality/harness-catalog.md:270-278,314-378`
  Acceptance criteria: `docker compose up -d --wait`; Alembic upgrade/downgrade/upgrade passes on empty and seeded DB; MinIO roundtrip passes; CI definition runs static and migration gates.
  QA scenarios: happy—fresh stack reaches healthy; failure—invalid migration rolls back without partial schema. Evidence `.omo/evidence/task-3-full-product-implementation/`.
  Evidence: `.omo/evidence/task-3-full-product-implementation/verification.json` records healthy PostgreSQL/MinIO services, migration and failed-DDL rollback proof, MinIO round trip, full static/test checks, and CI wiring.
  Commit: Y | `build(infra): add reproducible postgres minio stack`

- [x] 4. Create canonical contract generation and compatibility pipeline
  What to do / Must NOT do: Implement Pydantic v2 canonical transport schemas, JSON Schema/OpenAPI export, generated TypeScript/Zod validation, compatibility classification, deterministic generation and drift check. Include ADR-006 DecisionRecord envelope fields and canonical JSON/hash rules. Domain entities remain domain types; transport DTOs adapt them. Never manually edit generated artifacts or use dual hand-maintained schemas.
  Parallelization: Wave 0 | Blocked by: 1 | Blocks: 6-10,24,26-30
  References: `docs/domain/*.md`; WF-HAR-CONTRACT-05 `docs/quality/harness-catalog.md:300-308`; `docs/quality/verification-strategy.md`
  Acceptance criteria: Pydantic→JSON→Zod and reverse fixture roundtrips are lossless; regeneration produces zero diff; incompatible schema changes fail CI; DecisionRecord schema rejects a missing workspace/snapshot/graph/policy/pipeline/engine/source-revision/causation/correlation field.
  QA scenarios: happy—roundtrip representative entities; failure—remove required TS field and assert contract gate fails. Evidence `.omo/evidence/task-4-full-product-implementation/`.
  Evidence: `.omo/evidence/task-4-full-product-implementation/verification.json` records deterministic generated artifact hashes, Python and Zod round trips, mandatory workspace rejection, and a passing full static/test gate.
  Commit: Y | `feat(contracts): generate cross-language schemas`

- [ ] 5. Implement the harness runner and evidence manifest
  What to do / Must NOT do: Encode all 67 harness IDs, commands, blocking scope, expected artifacts, environment prerequisites, and Standard/Large/Tenant applicability in a machine-readable registry. Build `make harness ID=...` and evidence manifest validation. Do not mark intended/unimplemented harnesses passed.
  Parallelization: Wave 0 | Blocked by: 2-4 | Blocks: all implementation completion claims
  References: entire `docs/quality/harness-catalog.md`; `docs/quality/release-certification.md`; `docs/delivery/traceability-matrix.md`
  Acceptance criteria: registry has exactly 67 unique IDs; 64 Standard blockers; missing command/artifact or fabricated pass fails validation; each later task can register real execution.
  QA scenarios: happy—validate registry and one real static harness; failure—omit evidence file and assert certification false. Evidence `.omo/evidence/task-5-full-product-implementation/`.
  Commit: Y | `test(harness): add executable evidence registry`

- [ ] 6. Implement domain identities, value objects, WorkItem, Program, and typed edges
  What to do / Must NOT do: Build strict immutable value objects, branded ULIDs, Actor, tenant/workspace/resource IDs, lifecycle enums, WorkItem, Program, Edge and provenance. Make derived WorkItem caches require `derived_from_decision_id`; source truth does not duplicate readiness/ranking. Use monotonic local ULID generation behind a pure utility; validate contains/blocks/requires_gate/related_to endpoints. No I/O or ORM in Domain.
  Parallelization: Wave 1 | Blocked by: 2,4,5 | Blocks: 7-15
  References: `docs/domain/work-item.md`, `program.md`, `edges.md`, `terminology.md`; `docs/architecture/ARCHITECTURE.md:189-205`
  Acceptance criteria: roundtrip and invariant tests pass; invalid edge endpoint/type fails with typed error; import boundary remains clean.
  QA scenarios: happy—construct nested multi-parent Program; failure—containment self-edge rejected. Evidence `.omo/evidence/task-6-full-product-implementation/`.
  Commit: Y | `feat(domain): add core entities and typed edges`

- [ ] 7. Implement authority merge, provenance, freshness, and conflict semantics
  What to do / Must NOT do: Implement six-level source precedence, five authority statuses, conflict details, TTL/configured freshness, source revision inputs, and Attention basis output. Higher precedence chooses current value but never hides disagreement. AI remains inference-only.
  Parallelization: Wave 1 | Blocked by: 6 | Blocks: 10,14,19
  References: `docs/domain/authority-statuses.md`; `docs/domain/attention-items.md`; WF-HAR-DOMAIN-02/05 and security authority manipulation harnesses.
  Acceptance criteria: exhaustive precedence table and Hypothesis ordering invariance pass; stale/conflicted safety-critical fields fail readiness inputs.
  QA scenarios: happy—tracker and valid override reconcile with conflict provenance; failure—spoofed authoritative inference rejected. Evidence `.omo/evidence/task-7-full-product-implementation/`.
  Commit: Y | `feat(domain): implement authority reconciliation`

- [ ] 8. Implement graph validation and affected-region traversal
  What to do / Must NOT do: Implement containment DAG validation, Tarjan/Kosaraju SCC detection for blocks edges, localized invalid-component quarantine, deterministic component ordering, hard/soft blockers, fan-out and root-cause paths. Never globally disable unaffected components.
  Parallelization: Wave 1 | Blocked by: 6 | Blocks: 10,19,27
  References: `docs/domain/edges.md`; `docs/domain/readiness-ranking.md`; WF-HAR-DOMAIN-03, PROPERTY-02, META-05.
  Acceptance criteria: 10k generated graph cases pass; containment cycles reject mutation; dependency SCC emits localized Attention output; unaffected results are byte-identical.
  QA scenarios: happy—acyclic #539 graph resolves; failure—inject SCC and verify only SCC excluded. Evidence `.omo/evidence/task-8-full-product-implementation/`.
  Commit: Y | `feat(graph): add typed cycle and traversal engine`

- [ ] 9. Implement versioned policy DSL, phased gates, evidence, and completion
  What to do / Must NOT do: Define parse-don't-validate policy AST; implement entry/completion/certification gates, gate types, EvidenceRecord revision binding/attestation/expiry, completion policies and non-waivable safety. Reject unknown policy constructs and AI evidence.
  Parallelization: Wave 1 | Blocked by: 6,7 | Blocks: 10,21,22
  References: `docs/domain/gates-and-evidence.md`; `lifecycle-and-completion.md`; `state-machines.md`; `docs/decisions/ADR-004-evidence-backed-completion.md`
  Acceptance criteria: every state/gate matrix passes; completion-only gates do not block start; safety gate waiver and stale evidence fail closed.
  QA scenarios: happy—entry pass activates then completion evidence completes; failure—prior-revision evidence rejected. Evidence `.omo/evidence/task-9-full-product-implementation/`.
  Commit: Y | `feat(policies): implement phased evidence gates`

- [ ] 10. Implement deterministic readiness, ranking, and DecisionRecord-set engine
  What to do / Must NOT do: Create pure engine input snapshot/policy bundle and atomic per-item immutable outputs; populate the complete reproducibility envelope, comparator item-local inputs/outcomes/tie-break chain, readiness filters, configurable lexicographic comparators, stable tie-break, and Recommended Next projection. No clock/global state/randomness/AI/I/O inside solve.
  Parallelization: Wave 1 convergence | Blocked by: 6-9 | Blocks: 14,19,21,24
  References: `docs/product/overview.md:62-77,122-147`; `docs/domain/decision-record.md`; `readiness-ranking.md`; `recommended-next.md`
  Acceptance criteria: golden envelope hash, replay from identified snapshot/graph/policy/pipeline/engine inputs, ordering invariance, monotonicity and 10k property inputs pass; same input is bit-for-bit identical and an altered payload/input identity is rejected.
  QA scenarios: happy—frozen #539 snapshot returns expected frontier; failure—unsafe authority localizes non-ready reason without corrupting others. Evidence `.omo/evidence/task-10-full-product-implementation/`.
  Commit: Y | `feat(decisions): build deterministic frontier engine`

- [ ] 11. Implement tenant-scoped SQLAlchemy persistence and RLS
  What to do / Must NOT do: Add SQLAlchemy 2 async models/repositories/migrations for tenants, organizations, workspaces, programs, WorkItems, source versions, normalized snapshots, edges, policies, decisions, current projections, gates, evidence, approvals, overrides, leases, attention, connections, inbox, outbox, jobs. Enforce PostgreSQL `ENABLE/FORCE ROW LEVEL SECURITY`, transaction-local workspace context, non-BYPASSRLS app role, workspace composite FKs/uniques and scoped key namespaces. No repository method accepts a bare resource ID.
  Parallelization: Wave 2 | Blocked by: 3,6 | Blocks: 12-25
  References: `docs/architecture/ARCHITECTURE.md:279-317`; `docs/security/tenancy-isolation.md`; `authorization.md:57-68`
  Acceptance criteria: CRUD/version tests and cross-workspace matrix pass against real PostgreSQL using the production-equivalent app role; direct SQL, missing context, cache/object/job/inbox/idempotency cross-scope attempts deny; migration test proves app role cannot BYPASSRLS.
  QA scenarios: happy—same actor uses two explicit workspace contexts; failure—ID from workspace B is invisible in A. Evidence `.omo/evidence/task-11-full-product-implementation/`.
  Commit: Y | `feat(persistence): add tenant-scoped repositories`

- [ ] 12. Implement immutable audit/evidence storage and retention segments
  What to do / Must NOT do: Append per-workspace audit events transactionally with canonical UTF-8 JSON, canonical envelope plus payload hash, 64-zero genesis, SHA-256 chain, causation/correlation, and external signed-anchor/WORM capability; content-address bulky artifacts in S3/MinIO; enforce immutable rows/objects; implement governed segment purge with deletion proof. Do not claim event sourcing or rebuild current state from audit.
  Parallelization: Wave 2 | Blocked by: 3,9,11 | Blocks: 13,19,21,23,32,34
  References: `docs/architecture/ARCHITECTURE.md:318-358`; `docs/security/tenancy-isolation.md:110-150`; audit/evidence security harnesses.
  Acceptance criteria: payload/actor/timestamp/order/envelope tamper tests detect mismatch; privileged-DB threat profile fails without valid signed anchor/WORM proof; object hash roundtrip passes; retention purge cannot selectively rewrite a segment.
  QA scenarios: happy—append and verify segment; failure—SQL update/object overwrite rejected and alerted. Evidence `.omo/evidence/task-12-full-product-implementation/`.
  Commit: Y | `feat(audit): add immutable evidence ledger`

- [ ] 13. Implement PostgreSQL durable inbox, queue, worker claims, and scheduler fencing
  What to do / Must NOT do: Build workspace-scoped inbox/outbox/job state machines with `received→verified→persisted→claimed→refetched→normalized→solved→projected→completed`, `retry_scheduled`, and `dead_letter`; implement `FOR UPDATE SKIP LOCKED` fair claims, lease owner/expiry CAS, heartbeat, bounded jittered retries, poison replay, per-tenant fairness, transactional outbox and scheduler leader lock. Preserve original payload hash/attempt history. Never acknowledge webhook before durable inbox commit.
  Parallelization: Wave 2 | Blocked by: 3,11,12 | Blocks: 18,19,22,23,34
  References: `docs/architecture/ARCHITECTURE.md:368-400`; `docs/integrations/GITHUB.md:148-244`; WF-HAR-INTEG-03/05/06.
  Acceptance criteria: concurrent workers execute each workspace idempotency key once; lease-losing worker cannot complete; killed worker resumes; max attempts dead-letter with controlled replay; scheduler overlap prevented; crash injection at every internal commit boundary leaves either no state or all snapshot/decision/projection/audit/outbox state.
  QA scenarios: happy—enqueue/process/complete; failure—kill after claim and recover without duplicate effects. Evidence `.omo/evidence/task-13-full-product-implementation/`.
  Commit: Y | `feat(queue): implement durable background processing`

- [ ] 14. Persist DecisionRecord sets atomically and build current projections
  What to do / Must NOT do: Adapt identified normalized DB snapshot into pure engine; in one transaction append complete DecisionRecord set, update latest pointers/current projections carrying `derived_from_decision_id`, append payload-safe audit event, emit outbox intent, and advance source cursor with fencing. Never update an existing DecisionRecord, expose a mixed-cycle frontier, or store computed truth without derivation identity.
  Parallelization: Wave 2 | Blocked by: 10-13 | Blocks: 19,21,24
  References: `docs/domain/decision-record.md`; `docs/product/overview.md:79-91,122-147`; `docs/architecture/ARCHITECTURE.md:404-461`
  Acceptance criteria: injected failure at each write boundary rolls back all outputs; concurrent stale writer loses optimistic fence; `/frontier` sees one cycle only; stale/missing derived decision identity makes projection non-authoritative.
  QA scenarios: happy—append two cycles and diff history; failure—stale expected version rejected with no partial rows. Evidence `.omo/evidence/task-14-full-product-implementation/`.
  Commit: Y | `feat(decisions): persist atomic decision sets`

- [ ] 15. Implement identity, sessions, scoped RBAC, SoD, and credential encryption ports
  What to do / Must NOT do: Add OIDC/OAuth identity port, self-host local credential plus MFA path, opaque revocable sessions, resource-scoped role grants and deny rules, six-level permission checks, SoD decision service, tenant bootstrap, AES-GCM envelope-encryption port. Never trust UI, role-bearing long-lived JWT, or silently waive SoD.
  Parallelization: Wave 2 | Blocked by: 11,12 | Blocks: 18,21-24,32,34
  References: entire `docs/security/authorization.md`; `threat-model.md`; `secure-development-lifecycle.md`
  Acceptance criteria: permission matrix generated tests cover every action/role/scope; role change affects next request; credential plaintext absent from DB/log/API.
  QA scenarios: happy—Builder claims within Program scope; failure—same actor cannot solely approve own claim and cross-scope ID does not leak. Evidence `.omo/evidence/task-15-full-product-implementation/`.
  Commit: Y | `feat(identity): enforce scoped authorization and sod`

- [ ] 16. Freeze and validate the #539 reference fixture corpus
  What to do / Must NOT do: Store raw API-shaped fixture, expected marker/edge classifications, policy edges and canonical expected outputs with provenance/hash. Add updater that requires explicit review but tests never fetch live GitHub. Do not elevate fixture vocabulary into core domain.
  Parallelization: Wave 3 | Blocked by: 5,6 | Blocks: 19,34
  References: `docs/reference/oh-my-class/verified-facts.md`; `docs/delivery/traceability-matrix.md:103-115`; WF-HAR-539-REPLAY.
  Acceptance criteria: fixture hash pinned; all verified hierarchy and policy edges asserted; invalid/ghost reference negative fixtures included.
  QA scenarios: happy—parse frozen corpus; failure—tamper one marker and golden validation fails. Evidence `.omo/evidence/task-16-full-product-implementation/`.
  Commit: Y | `test(fixtures): freeze verified 539 corpus`

- [ ] 17. Implement connection ports and deterministic harness adapters
  What to do / Must NOT do: Define isolated adapter protocol and capability/certification metadata; implement InMemory, File, Fixture adapters with pagination/revision semantics and fault injection; executable adapter loader communicates through typed port. Do not load arbitrary untrusted in-process plugins.
  Parallelization: Wave 3 | Blocked by: 2,6 | Blocks: 18,19,34
  References: `docs/architecture/ARCHITECTURE.md:206-220,515-532`; `docs/integrations/GITHUB.md:248-299`
  Acceptance criteria: certification Levels 0/1 tests pass; all adapters normalize same fixture identically; simulated timeout/rate limit typed.
  QA scenarios: happy—FixtureAdapter pages all issues; failure—malformed adapter response quarantined. Evidence `.omo/evidence/task-17-full-product-implementation/`.
  Commit: Y | `feat(connections): add certified adapter ports`

- [ ] 18. Implement GitHub App adapter and webhook boundary
  What to do / Must NOT do: Add App JWT/install token refresh, OAuth/OIDC user attribution, permissions check, pagination/rate-budget/backoff/circuit breaker, HMAC webhook verification, authoritative refetch, encrypted credential references. Installation tokens remain memory-only. Projection write methods require writer lease and approval token.
  Parallelization: Wave 3 | Blocked by: 13,15,17 | Blocks: 19,34,35
  References: `docs/integrations/GITHUB.md:39-144,148-299,469-518`; `docs/security/authorization.md:179-199`
  Acceptance criteria: mocked transport contract tests plus GitHub sandbox harness pass; invalid signature/install scope/expired token fails before durable processing or write.
  QA scenarios: happy—signed delivery refetches current issue; failure—replayed delivery dedups and unauthorized write method refuses. Evidence `.omo/evidence/task-18-full-product-implementation/`.
  Commit: Y | `feat(github): implement app adapter and webhook security`

- [ ] 19. Build ingestion, normalization, reconciliation, and incremental solve tracer bullet
  What to do / Must NOT do: Execute durable receipt→refetch→source version→profile normalization→authority merge→graph affected region→engine→atomic DecisionRecords/projections→cursor commit. Dedup webhook and polling at source revision. Orphans flag, never delete. Do not advance cursor on partial failure.
  Parallelization: Wave 3 convergence | Blocked by: 7-18 | Blocks: 20-25
  References: `docs/architecture/ARCHITECTURE.md:404-461`; `docs/integrations/GITHUB.md:148-244,390-435`; `docs/delivery/implementation-sequence.md:128-174`
  Acceptance criteria: frozen #539 full sync and one edited issue incremental sync converge to full solve; replay is idempotent; conflict/staleness emits AttentionItems.
  QA scenarios: happy—close/reopen updates source signal and frontier; failure—crash before cursor leaves event retryable with no duplicate decision. Evidence `.omo/evidence/task-19-full-product-implementation/`.
  Commit: Y | `feat(ingestion): deliver end-to-end decision pipeline`

- [ ] 20. Implement writer ownership, shadow comparison, stale-write guard, and rollback primitive
  What to do / Must NOT do: Persist writer state machine and exclusive writer lease; compare canonical semantics in shadow; fence by local projection version plus exact source revision; record approved presentation-only differences; implement activation/rollback commands. Never use percentage canaries or two writers.
  Parallelization: Wave 3 | Blocked by: 14,18,19 | Blocks: 33,35
  References: `docs/integrations/GITHUB.md:439-465`; `docs/reference/oh-my-class/shadow-compare-cutover.md`; `docs/decisions/ADR-005-github-first-controlled-cutover.md`
  Acceptance criteria: shadow performs zero external writes; stale input and absent lease reject; rollback restores `legacy_active` in timed harness under 5 minutes.
  QA scenarios: happy—exact parity activates sole writer; failure—semantic mismatch blocks approval and preserves legacy output. Evidence `.omo/evidence/task-20-full-product-implementation/`.
  Commit: Y | `feat(cutover): enforce single projection writer`

- [ ] 21. Implement projections, ProposedChanges, approvals, overrides, and transactional recompute
  What to do / Must NOT do: Separate safe projections from authoritative mutations; create immutable proposal and disposition records; enforce approval/SoD/staleness; apply approved mutation and recompute in one fenced workflow; overrides scoped/audited/TTL/non-weakening. Copilot acceptance enters proposal flow, never direct mutation.
  Parallelization: Wave 4 | Blocked by: 9,12,14,15,19 | Blocks: 24,27,28,31
  References: `docs/integrations/GITHUB.md:302-386`; `docs/domain/work-item.md`; `docs/security/authorization.md:70-136`; UX proposal rules.
  Acceptance criteria: no mutation without approval; stale approval fails; accepted proposal creates new DecisionRecord and projection; safety/completion weakening rejected.
  QA scenarios: happy—approve dependency repair and frontier changes; failure—claimant self-approval denied. Evidence `.omo/evidence/task-21-full-product-implementation/`.
  Commit: Y | `feat(approvals): add gated mutation workflow`

- [ ] 22. Implement WorkLease coordination and AttentionItem lifecycle
  What to do / Must NOT do: Add atomic exclusive/collaborative claims, heartbeats/TTL/renewal/release/suspension, handoff and authorized override; preserve underlying readiness but actor-specific claimability. Emit deterministic AttentionItems for conflicts, stale sources/jobs, invalid SCCs, degraded connection, and break risk.
  Parallelization: Wave 4 | Blocked by: 7,9,11,13-15,19 | Blocks: 24,26-28
  References: `docs/domain/work-lease.md`; `attention-items.md`; `state-machines.md`; WF-HAR-PRODUCT-03/05.
  Acceptance criteria: concurrent claim race yields one winner; expired lease releases; higher priority requests handoff rather than silent break; every forced override audited.
  QA scenarios: happy—claim/heartbeat/release; failure—stale DecisionRecord cannot support lease. Evidence `.omo/evidence/task-22-full-product-implementation/`.
  Commit: Y | `feat(workflow): add leases and attention lifecycle`

- [ ] 23. Implement break-glass and governed retention workflows
  What to do / Must NOT do: Add strong reauth/MFA, reason and confirmation, two-hour scoped elevation, two-per-day rate, forbidden operations, immediate alerts, expiry and 48-hour review; add retention jobs/data-subject anonymization/deletion evidence. Never grant blanket writes or permanent hidden admin.
  Parallelization: Wave 4 | Blocked by: 12,13,15,21 | Blocks: 24,29,32
  References: `docs/security/authorization.md:140-224`; `tenancy-isolation.md:98-159`; `docs/operations/incident-response.md`
  Acceptance criteria: clock-controlled state tests and permission matrix pass; forbidden break-glass role/policy/connection mutations fail; retention leaves allowed proof without PII.
  QA scenarios: happy—scoped emergency credential rotation and expiry; failure—third invocation/short reason rejected. Evidence `.omo/evidence/task-23-full-product-implementation/`.
  Commit: Y | `feat(security): implement break glass and retention`

- [ ] 24. Implement FastAPI/OpenAPI interface and three runnable processes
  What to do / Must NOT do: Add app factory, tenant/session middleware, typed errors, all canonical endpoints, pagination/idempotency, `/healthz`, `/openapi.json`; create web, worker and scheduler entrypoints sharing application modules; optional polling status endpoint. No business logic in handlers and no invented SSE requirement.
  Parallelization: Wave 4 | Blocked by: 14,15,19,21-23 | Blocks: 25-35
  References: `docs/architecture/ARCHITECTURE.md:230-275,465-513`; `docs/security/authorization.md:106-113`; WF-HAR-CONTRACT-01/INTEG-04.
  Acceptance criteria: OpenAPI 3.1 valid; Schemathesis 1,000 examples/endpoint zero violations; all processes start independently; auth/tenant checks on every route.
  QA scenarios: happy—fixture sync then GET frontier/detail/history; failure—cross-scope and malformed IDs return non-leaking typed responses. Evidence `.omo/evidence/task-24-full-product-implementation/`.
  Commit: Y | `feat(api): expose control plane and runtimes`

- [ ] 25. Implement CLI parity and administrative automation
  What to do / Must NOT do: Build Typer CLI as API client (not direct DB access) for programs/items/frontier/claim/proposals/connections/sync/audit/writer state/cert verification; structured JSON and human output; config profiles and safe confirmation for mutations.
  Parallelization: Wave 4 | Blocked by: 24 | Blocks: 33-35
  References: `docs/architecture/ARCHITECTURE.md:499-513`; `docs/ux/ux-critical-journeys.md`; CLI harness requirements in delivery docs.
  Acceptance criteria: command-to-endpoint parity table complete; smoke tests cover success/error/exit codes; no credential in argv/logs.
  QA scenarios: happy—trigger fixture sync and inspect frontier JSON; failure—stale proposal approval exits nonzero with rationale. Evidence `.omo/evidence/task-25-full-product-implementation/`.
  Commit: Y | `feat(cli): add api-parity command surface`

- [ ] 26. Build Control Room shell, onboarding, design tokens, and generated API client
  What to do / Must NOT do: Create React SPA shell, four-view navigation, workspace/session context, generated typed API client, TanStack Query, responsive token system, onboarding install/profile/reconciliation flow, accessible loading/error/empty states. Do not declare authority until reconciliation succeeds.
  Parallelization: Wave 5 | Blocked by: 4,24 | Blocks: 27-30,33
  References: `docs/ux/ux-architecture.md:18-51,152-162,205-269`; `docs/ux/ux-onboarding.md`; `docs/ux/ux-accessibility-design-system.md`
  Acceptance criteria: onboarding Playwright path reaches first authoritative recommendation; regeneration typechecks; 320/768/1280/1920 layouts pass visual/axe baselines.
  QA scenarios: happy—GitHub fixture onboarding/reconcile; failure—permission conflict keeps Draft state and offers recovery. Evidence `.omo/evidence/task-26-full-product-implementation/`.
  Commit: Y | `feat(ui): add control room shell and onboarding`

- [ ] 27. Implement Builder view and WorkItem decision detail
  What to do / Must NOT do: Render Recommended Next first, authority/freshness, deterministic why, evidence, Attention, claim/open actions, full ready list, detail timeline/diffs and why-blocked root path. Permit other authoritative-ready claims with recorded divergence reason. Never hide decision type.
  Parallelization: Wave 5 | Blocked by: 21,22,24,26 | Blocks: 33,34
  References: `docs/ux/ux-architecture.md:53-98,164-202,237-269`; `docs/domain/recommended-next.md`; product harnesses 01-03/05.
  Acceptance criteria: Playwright asserts ranking matches API DecisionRecord; claim race UX handles 409; keyboard and screen reader labels complete.
  QA scenarios: happy—claim Recommended Next and view timeline; failure—stale/conflicted item disables claim with exact reason. Evidence `.omo/evidence/task-27-full-product-implementation/`.
  Commit: Y | `feat(ui): implement builder decision workspace`

- [ ] 28. Implement Coordinator proposal and dependency workflows
  What to do / Must NOT do: Show blocked chains/unlock impact/conflicts/proposals, approve/reject with SoD and stale checks, graph interaction with keyboard/table alternative, scoped bulk actions. No individual content editing or silent mutation.
  Parallelization: Wave 5 | Blocked by: 21,22,24,26 | Blocks: 33,34
  References: `docs/ux/ux-architecture.md:99-115,190-201`; `ux-critical-journeys.md`; WF-HAR-PRODUCT-02/04/06.
  Acceptance criteria: dependency repair journey recomputes frontier; stale proposal displays refresh requirement; graph alternative satisfies accessibility harness.
  QA scenarios: happy—approve repair and see unlock delta; failure—self/expired approval rejected without optimistic UI lie. Evidence `.omo/evidence/task-28-full-product-implementation/`.
  Commit: Y | `feat(ui): add coordinator workflows`

- [ ] 29. Implement Executive and Operator views
  What to do / Must NOT do: Executive renders terminal outcomes/risk/trends/export with authority metadata; Operator renders connection health, queue depth, attempts/reconciliation/audit and guarded retry/reconcile. Respect roles and explanatory empty states; no readiness editing in Operator.
  Parallelization: Wave 5 | Blocked by: 23,24,26 | Blocks: 33,34
  References: `docs/ux/ux-architecture.md:116-151`; `docs/operations/slo-observability.md`; `docs/security/authorization.md:70-104`
  Acceptance criteria: role/view matrix, export metadata, degraded connection and queue recovery paths pass; sensitive audit payloads redacted.
  QA scenarios: happy—Operator retries dead letter; failure—Viewer sees empty explanation, not operational data. Evidence `.omo/evidence/task-29-full-product-implementation/`.
  Commit: Y | `feat(ui): add executive and operator views`

- [ ] 30. Complete WCAG 2.2 AA, responsive, and visual-system certification
  What to do / Must NOT do: Audit every route/component for semantics, focus, contrast, reduced motion, keyboard, drag alternatives, screen-reader announcements, density and mobile behavior; add Playwright screenshots/axe baselines. Fix actual UI rather than suppressing axe rules.
  Parallelization: Wave 5 convergence | Blocked by: 26-29 | Blocks: 34
  References: `docs/ux/ux-accessibility-design-system.md`; WF-HAR-A11Y-01..04; UX architecture disclosure rules.
  Acceptance criteria: all four A11Y harnesses pass with zero violations; screenshots cover required viewports and five decision types.
  QA scenarios: happy—keyboard-only complete claim/approval; failure—automated focus-loss/contrast mutation is caught. Evidence `.omo/evidence/task-30-full-product-implementation/`.
  Commit: Y | `fix(a11y): certify control room wcag 2.2 aa`

- [ ] 31. Implement provider-neutral, default-off Copilot
  What to do / Must NOT do: Define provider port, redaction/purpose limits, prompt-injection boundaries, grounded explanations and ProposedChange drafts referencing Decision/Evidence IDs, budgets/timeouts/circuit breaker and deterministic fake. Copilot cannot access credentials/PII or call mutation/readiness/ranking methods.
  Parallelization: Wave 6 | Blocked by: 21,24,26 | Blocks: 34
  References: `docs/security/ai-governance.md`; `docs/architecture/ARCHITECTURE.md:167-180,191-205`; UX AI suggestion rules.
  Acceptance criteria: full product suite passes with `COPILOT_PROVIDER=none`; AI lifecycle-isolation and prompt-injection tests pass; output without valid citations rejected.
  QA scenarios: happy—explain missing evidence and draft proposal; failure—provider proposes rank change and boundary rejects/logs it. Evidence `.omo/evidence/task-31-full-product-implementation/`.
  Commit: Y | `feat(copilot): add bounded optional explanations`

- [ ] 32. Finish security hardening and all 15 security harnesses
  What to do / Must NOT do: Add CSRF for cookie sessions, CSP/security headers, SSRF egress allowlist, rate limiting, input/file validation, dependency scanning, TLS production config, secret redaction, IDOR/privilege/safety/override/authority/tamper tests and threat-model traceability. No ignored high/critical finding.
  Parallelization: Wave 6 | Blocked by: 12,15,23,24,26-30 | Blocks: 34
  References: `docs/security/threat-model.md`; `secure-development-lifecycle.md`; WF-HAR-SEC-01..15.
  Acceptance criteria: `make test-security` emits all 15 artifacts and passes; ZAP has no medium/high; gitleaks and dependency audits meet policy.
  QA scenarios: happy—authorized flows survive hardening; failure—SSRF/IDOR/CSRF/safety bypass payloads blocked and audited. Evidence `.omo/evidence/task-32-full-product-implementation/`.
  Commit: Y | `fix(security): close production threat controls`

- [ ] 33. Implement deployment, observability, backup/DR, and upgrade operations
  What to do / Must NOT do: Produce hardened multi-stage images, Compose self-host profile with capability truth, hosted manifests/templates, metrics/traces/logs, dashboards/alerts, backup/PITR/object inventory, restore/failover/upgrade/rollback runbooks and executable drills. Never call single-node Compose HA.
  Parallelization: Wave 6 | Blocked by: 3,20,24-30 | Blocks: 34,35
  References: all `docs/operations/*.md`; `docs/architecture/ARCHITECTURE.md:536-583`; operational harnesses.
  Acceptance criteria: smoke/load/event durability/72h soak/failure injection/DR/migration harnesses produce evidence; RPO ≤5m, RTO ≤60m; Standard p95/SLO targets pass.
  QA scenarios: happy—backup clean stack restore and serve; failure—kill worker/DB/disk-full triggers recovery and alerts without acknowledged loss. Evidence `.omo/evidence/task-33-full-product-implementation/`.
  Commit: Y | `feat(ops): add certified deployment and recovery`

- [ ] 34. Complete all 67 harnesses and signed Standard ReleaseCertification
  What to do / Must NOT do: Implement missing commands/artifacts, run bottom-up layers, produce canonical manifest tied to exact commit/service versions, SBOM/provenance, sign Ed25519, publish verification command/key ID and coverage report. Standard certification requires 64 blockers; dead-code informational; scoped capacity marked N/A with reason unless declared.
  Parallelization: Wave 6 convergence | Blocked by: 1-33 | Blocks: 35,F1-F4
  References: `docs/quality/harness-catalog.md`; `verification-strategy.md`; `release-certification.md`; `performance-envelope.md`
  Acceptance criteria: registry and evidence contain 67 unique entries; every Standard blocker passes; signature verifies; missing/tampered artifact, wrong SHA or skipped blocker makes `all_passed=false`.
  QA scenarios: happy—verify signed cert from clean checkout; failure—alter one evidence byte and signature/manifest verification fails. Evidence `.omo/evidence/task-34-full-product-implementation/`.
  Commit: Y | `test(release): certify standard production envelope`

- [ ] 35. Execute #539 exact-parity cutover and rollback certification
  What to do / Must NOT do: Run eight phases: import, shadow, exact DecisionRecord/report compare, approval, disable legacy/claim writer, publish, observe, legacy verify-only/retire. Capture approvals, source revisions, writer lease, markers, links, rollback timing and post-observation evidence. No canary percentages, A/B output preference, or dual writer.
  Parallelization: Wave 6 final | Blocked by: 18-20,25,33,34 | Blocks: F1-F4
  References: `docs/reference/oh-my-class/shadow-compare-cutover.md`; `verified-facts.md`; `docs/decisions/ADR-005-github-first-controlled-cutover.md`; `docs/integrations/GITHUB.md:439-465`
  Acceptance criteria: exact canonical semantic parity; approved presentation-only differences enumerated; marker/link integrity 100%; one writer at all times; timed rollback <5m; observation error/stale-write targets pass.
  QA scenarios: happy—activate then verify-only legacy; failure—inject stale source/semantic mismatch and automatically block or restore legacy owner. Evidence `.omo/evidence/task-35-full-product-implementation/`.
  Commit: Y | `feat(cutover): activate managed 539 projection`

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [ ] F1. Plan compliance audit — independently map every todo, 13 modules, 67 harnesses and Must/NOT guardrail to code plus immutable evidence; reject missing or self-reported completion. Evidence `.omo/evidence/final-plan-compliance.md`.
- [ ] F2. Code quality/security review — run static diagnostics, architecture boundaries, migration review, concurrency/transaction analysis, secret/dependency/security scans, and inspect every changed file; zero introduced errors/high findings. Evidence `.omo/evidence/final-code-quality.md`.
- [ ] F3. Real manual QA — start a clean production-like Standard stack; use browser and CLI to onboard frozen/sandbox GitHub, inspect/claim/approve/reconcile, exercise all views, backup/restore, AI-off behavior and rollback; screenshots/traces required. Evidence `.omo/evidence/final-manual-qa/`.
- [ ] F4. Scope fidelity — compare implementation against canonical docs, OpenAPI, release cert and #539 reference; prove no non-GitHub adapter, AI authority, dual writer, event sourcing, hidden SoD bypass, or unsupported capacity claim. Evidence `.omo/evidence/final-scope-fidelity.md`.

## Commit strategy
- One atomic conventional commit per todo, in listed dependency order; parallel branches rebase before merge and rerun affected gates.
- Never combine refactoring with a behavior change unless required by that todo. Generated files travel with their generator/contract commit.
- Database changes include forward migration, downgrade where safe, compatibility test, and rollback note in the same commit.
- No final squash that destroys cutover/evidence provenance; release tag points to the exact signed certification commit.

## Success criteria
- A clean clone can bootstrap, run the three processes, open the Control Room, ingest the frozen #539 fixture, persist an immutable DecisionRecord set, and show authoritative Recommended Next with Why.
- Every canonical module exists behind enforced seams; deterministic replay and incremental/full-solve convergence pass.
- Tenant isolation, RBAC, SoD, break-glass, credential secrecy, evidence integrity, GitHub durable ingestion, approval and lease race behavior pass executable tests.
- All four UI views satisfy WCAG 2.2 AA and product-path harnesses at required viewports with no console or schema errors.
- The Standard production stack meets SLO/RPO/RTO and all 64 default blocking harnesses; all 67 harness entries have truthful evidence/applicability.
- A signed ReleaseCertification verifies against the exact commit, and #539 reaches `projection_active` only after exact semantic parity with a proven <5-minute rollback.
- F1-F4 all return unconditional approval, and the user explicitly accepts the surfaced final verification results.
