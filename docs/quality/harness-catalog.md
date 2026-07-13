---
title: "Executable Harness Catalog"
version: "1.0.0"
status: "canonical"
owner: "work-frontier"
last_updated: "2026-07-12"
requirement_prefix: "WF-HAR"
---

# Executable Harness Catalog

Every harness below is a required contract for future implementation. Each has a unique
WF-HAR ID, an intended command path, expected artifacts, and pass criteria. "Harness
exists" means the harness must run, produce structured output, and that output must be
part of the release evidence chain. These are specifications for what must exist, not
claims that tests already exist. All commands reference proposed Work Frontier paths.

---

## Naming Convention

```
WF-HAR-{LAYER}-{SEQUENCE}-{NAME}

LAYER: STATIC | DOMAIN | PROPERTY | META | CONTRACT | INTEG | PRODUCT | OPS
SEQUENCE: 01, 02, 03 ... (execution order within layer)
NAME: short lowercase identifier
```

---

## Layer 1: Static (WF-HAR-STATIC)

### WF-HAR-PREFLIGHT-01: ADR-006 Foundation Contract Gate

| Field | Value |
|-------|-------|
| **Command** | `node .omo/preflight/adr-006/validate.mjs && node --test .omo/preflight/adr-006/validate.test.mjs` |
| **What it runs** | Contract-specific P0 positive payloads and negative mutations for WF-P0-01..07 plus behavioral sabotage suite |
| **Artifact** | `.omo/evidence/preflight-adr-006/validation.json` |
| **Pass criteria** | Gate status passed; all positive documents validate; all negative fixtures reject with expected failure IDs; behavioral tests pass |
| **Blocks release** | Yes |

### WF-HAR-STATIC-01: Type Checking

| Field | Value |
|-------|-------|
| **Command** | `uv run basedpyright && pnpm --dir frontend exec tsc --noEmit` |
| **What it runs** | basedpyright (Python strict) and TypeScript `tsc --noEmit` for frontend |
| **Artifact** | `.omo/evidence/static/WF-HAR-STATIC-01.json` |
| **Pass criteria** | Zero errors |
| **Blocks release** | Yes |

### WF-HAR-STATIC-02: Import Boundary Enforcement

| Field | Value |
|-------|-------|
| **Command** | `uv run python scripts/check_import_boundaries.py` |
| **What it runs** | Scans `backend/src/work_frontier` imports, verifies ADR-006 Domain/Platform/Application/Interfaces/Adapter seams and Application-owned ports |
| **Artifact** | `.omo/evidence/static/import-boundaries.json` |
| **Pass criteria** | Zero violations of ADR-006 and architecture import matrix; unknown layers fail closed; 36-pair behavioral fixtures pass |
| **Blocks release** | Yes |

### WF-HAR-STATIC-03: Dead Code Detection

| Field | Value |
|-------|-------|
| **Command** | `uv run vulture backend/src --min-confidence 90 && pnpm --dir frontend exec ts-prune` |
| **What it runs** | Detects unused functions, classes, variables above confidence threshold |
| **Artifact** | `.omo/evidence/static/dead-code.json` |
| **Pass criteria** | No new dead code since last release. Existing dead code tracked in tech-debt backlog. |
| **Blocks release** | No (informational) |

### WF-HAR-STATIC-04: Lint and Format

| Field | Value |
|-------|-------|
| **Command** | `uv run ruff check backend/src backend/tests scripts && uv run ruff format --check backend/src backend/tests scripts && pnpm --dir frontend run check` |
| **What it runs** | Ruff lint/format and Biome + tsc frontend check |
| **Artifact** | `.omo/evidence/static/WF-HAR-STATIC-04.json` |
| **Pass criteria** | Zero violations |
| **Blocks release** | Yes |

### WF-HAR-STATIC-05: Secret Detection

| Field | Value |
|-------|-------|
| **Command** | `gitleaks detect --source . --report-format json --report-path "${WF_HARNESS_ARTIFACT:-.omo/evidence/static/secrets.json}"` |
| **What it runs** | Scans entire repo history for committed secrets |
| **Artifact** | `.omo/evidence/static/secrets.json` |
| **Pass criteria** | Zero findings |
| **Blocks release** | Yes |

---

## Layer 2: Domain (WF-HAR-DOMAIN)

### WF-HAR-DOMAIN-01: DecisionRecord Determinism

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/domain/test_frontier_computation.py -v` (intended) |
| **What it runs** | Imports fixed hierarchy, textual blockers, and configured policy gates; computes deterministic full-solve frontier; compares canonical DecisionRecord envelope hash, snapshot/graph/policy/pipeline/engine identifiers, and ranking trace to golden data |
| **Artifact** | `evidence/domain/frontier-computation.json` |
| **Pass criteria** | DecisionRecord envelope hash matches golden data exactly. Replaying the identified normalized snapshot, source revision set, graph revision, policy bundle, ranking pipeline, and engine version yields identical output. No item missing or ordering discrepancy. |
| **Blocks release** | Yes |

### WF-HAR-DOMAIN-02: Precedence Determinism

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/domain/test_precedence.py -v` (intended) |
| **What it runs** | Table-driven: every (source_level_pair, field_type) combination; verifies same precedence ladder produces identical result |
| **Artifact** | `evidence/domain/precedence.json` |
| **Pass criteria** | All precedence evaluations deterministic. Conflicts surfaced, not silently resolved. |
| **Blocks release** | Yes |

### WF-HAR-DOMAIN-03: Dependency Chain Resolution

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/domain/test_dependency_chains.py -v` (intended) |
| **What it runs** | Exhaustive typed graph shapes; verifies containment-cycle rejection and dependency-SCC isolation with AttentionItems |
| **Artifact** | `evidence/domain/dependency-chains.json` |
| **Pass criteria** | Acyclic chains resolve correctly. Containment cycles are rejected. Cyclic dependency SCCs are isolated fail-closed with their paths reported, while unaffected components remain evaluable. |
| **Blocks release** | Yes |

### WF-HAR-DOMAIN-04: Policy Gate Evaluation

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/domain/test_policy_gates.py -v` (intended) |
| **What it runs** | Matrix: every (item_state, gate_config) triple; verifies gate evaluation per configured policy (policy gates are not body edges) |
| **Artifact** | `evidence/domain/policy-gates.json` |
| **Pass criteria** | Every gate correctly classifies items. Safety gates cannot be waived. Localized fail-closed when uncertain. |
| **Blocks release** | Yes |

### WF-HAR-DOMAIN-05: Source Revision and Freshness Authority

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/domain/test_source_authority.py -v` (intended) |
| **What it runs** | Table-driven: every (source_type, staleness_condition) pair; verifies authority status downgraded correctly per staleness rules |
| **Artifact** | `evidence/domain/source-authority.json` |
| **Pass criteria** | Stale sources flagged. Authority status downgraded. AttentionItem emitted for stale sources. |
| **Blocks release** | Yes |

---

## Layer 3: Property (WF-HAR-PROPERTY)

### WF-HAR-PROPERTY-01: DecisionRecord Stability

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/property/test_frontier_determinism.py --hypothesis-seed=0` (intended) |
| **What it runs** | Hypothesis generates random valid hierarchies + textual blockers + configured policy gates; verifies DecisionRecord hash is identical on replay |
| **Inputs** | 10,000 random valid frontier inputs |
| **Artifact** | `evidence/property/frontier-determinism.json` |
| **Pass criteria** | 10,000 inputs, zero cases where replay produces different DecisionRecord hash. |
| **Blocks release** | Yes |

### WF-HAR-PROPERTY-02: Dependency Acyclicity

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/property/test_dependency_acyclicity.py --hypothesis-seed=0` (intended) |
| **What it runs** | Generates random dependency graphs with intentional cycle injection; verifies SCC-based DAG check |
| **Inputs** | 10,000 random graphs (mix of acyclic and cyclic) |
| **Artifact** | `evidence/property/dependency-acyclicity.json` |
| **Pass criteria** | Acyclic graphs accepted. All cyclic graphs detected via SCC and rejected with cycle path reported. |
| **Blocks release** | Yes |

### WF-HAR-PROPERTY-03: Readiness Monotonicity

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/property/test_readiness_monotonicity.py --hypothesis-seed=0` (intended) |
| **What it runs** | Generates random edge mutations; verifies closing valid blocker never shrinks readiness and adding open blocker never grows frontier |
| **Inputs** | 10,000 random edge mutation sequences |
| **Artifact** | `evidence/property/readiness-monotonicity.json` |
| **Pass criteria** | No case where closing a valid blocker shrinks readiness or adding an open blocker increases frontier. |
| **Blocks release** | Yes |

### WF-HAR-PROPERTY-04: Projection Convergence

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/property/test_projection_convergence.py --hypothesis-seed=0` (intended) |
| **What it runs** | Generates random partial updates; computes incremental projection; compares to full-solve |
| **Inputs** | 10,000 random update sequences |
| **Artifact** | `evidence/property/projection-convergence.json` |
| **Pass criteria** | Incremental projection converges to full-solve result for every input. No items lost or reordered. |
| **Blocks release** | Yes |

### WF-HAR-PROPERTY-05: Input Ordering Invariance

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/property/test_input_ordering.py --hypothesis-seed=0` (intended) |
| **What it runs** | Generates random input sequences; shuffles processing order; verifies identical output |
| **Inputs** | 10,000 random shuffled sequences |
| **Artifact** | `evidence/property/input-ordering.json` |
| **Pass criteria** | Output identical regardless of input processing order. No ordering-dependent behavior. |
| **Blocks release** | Yes |

---

## Layer 4: Metamorphic (WF-HAR-META)

### WF-HAR-META-01: DecisionRecord Determinism (Replay)

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/metamorphic/test_frontier_replay.py` (intended) |
| **What it runs** | Re-runs DecisionRecord computation on identical snapshot twice; verifies bit-for-bit identical hash |
| **Inputs** | 500 identical snapshot pairs |
| **Artifact** | `evidence/metamorphic/frontier-replay.json` |
| **Pass criteria** | DecisionRecord hash identical across all 500 replay pairs |
| **Blocks release** | Yes |

### WF-HAR-META-02: Frontier Monotonicity

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/metamorphic/test_frontier_monotonicity.py` (intended) |
| **What it runs** | Adds an open blocker edge; verifies frontier set does not grow; blocked item removed from ready set |
| **Inputs** | 500 dependency graph mutations |
| **Artifact** | `evidence/metamorphic/frontier-monotonicity.json` |
| **Pass criteria** | Adding an open blocker never increases the frontier set |
| **Blocks release** | Yes |

### WF-HAR-META-03: Readiness Monotonicity

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/metamorphic/test_readiness_monotonicity.py` (intended) |
| **What it runs** | Closes a valid blocker; verifies readiness does not shrink unless policy or source changes |
| **Inputs** | 500 blocker-close scenarios |
| **Artifact** | `evidence/metamorphic/readiness-monotonicity.json` |
| **Pass criteria** | Closing a valid blocker never shrinks readiness unless policy or source changes |
| **Blocks release** | Yes |

### WF-HAR-META-04: Projection Parity

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/metamorphic/test_projection_parity.py` (intended) |
| **What it runs** | Full solve vs. incremental on same data; verifies item ordering agrees |
| **Inputs** | 500 data snapshots × full vs. incremental |
| **Artifact** | `evidence/metamorphic/projection-parity.json` |
| **Pass criteria** | Item ordering agrees between full and incremental. No item reachable in one but not the other. |
| **Blocks release** | Yes |

### WF-HAR-META-05: Invalid Component Isolation

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/metamorphic/test_invalid_component_isolation.py` (intended) |
| **What it runs** | Injects invalid component into valid graph; verifies valid components unaffected |
| **Inputs** | 500 injection scenarios across valid graphs |
| **Artifact** | `evidence/metamorphic/invalid-component-isolation.json` |
| **Pass criteria** | Valid components unaffected. Invalid component rejected with localized error. No corruption of neighbors. |
| **Blocks release** | Yes |

---

## Layer 5: Contract (WF-HAR-CONTRACT)

### WF-HAR-CONTRACT-01: API Schema Validation

| Field | Value |
|-------|-------|
| **Command** | `schemathesis run tests/contract/openapi.yaml --hypothesis-max-examples=1000` |
| **What it runs** | Generates requests matching API schema; verifies responses match |
| **Artifact** | `evidence/contract/api-schema.json` |
| **Pass criteria** | Zero schema violations across 1,000 generated requests per endpoint |
| **Blocks release** | Yes |

### WF-HAR-CONTRACT-02: Migration Contract

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/contract/test_migrations.py -v` |
| **What it runs** | Applies each migration forward; optionally back; verifies data integrity |
| **Artifact** | `evidence/contract/migration.json` |
| **Pass criteria** | All migrations apply cleanly. Data round-trips for reversible migrations. |
| **Blocks release** | Yes |

### WF-HAR-CONTRACT-03: Event Schema Contract

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/contract/test_event_schemas.py -v` |
| **What it runs** | Verifies published events match registered schemas |
| **Artifact** | `evidence/contract/event-schema.json` |
| **Pass criteria** | All event types match their registered schema version |
| **Blocks release** | Yes |

### WF-HAR-CONTRACT-04: Inter-Service Contract

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/contract/test_inter_service.py -v` |
| **What it runs** | Web ↔ Worker ↔ Scheduler message format compatibility |
| **Artifact** | `evidence/contract/inter-service.json` |
| **Pass criteria** | All message types deserialize correctly on receiving end |
| **Blocks release** | Yes |

### WF-HAR-CONTRACT-05: Python ↔ TypeScript Schema

| Field | Value |
|-------|-------|
| **Command** | `uv run python scripts/generate_contracts.py --check && uv run pytest backend/tests/contracts/test_decision_record_contract.py -v && pnpm --dir frontend exec vitest run tests/contracts/decision-record.generated.test.ts` |
| **What it runs** | Contract generation drift check plus shared DecisionRecord fixtures through Pydantic and Zod with canonical SHA-256 parity |
| **Artifact** | `.omo/evidence/static/contracts.json` |
| **Pass criteria** | Zero generation drift; all required fixtures present; valid fixtures pass both runtimes with matching canonical hashes; invalid fixtures rejected by both |
| **Blocks release** | Yes |

---

## Layer 6: Integration (WF-HAR-INTEG)

### WF-HAR-INTEG-01: PostgreSQL Integration

| Field | Value |
|-------|-------|
| **Command** | `make migration-smoke` |
| **What it runs** | Data-service baseline: Alembic upgrade, seeded lifecycle, real failing revision rollback, downgrade, re-upgrade against Postgres 16. Full RLS/CRUD/pooling deferred to later platform todos. |
| **Environment** | Docker Compose: postgres:16 |
| **Artifact** | `.omo/evidence/static/migration-smoke.json` |
| **Pass criteria** | Marker table present after upgrade; seed row survives failed-revision rollback; failing revision does not advance alembic_version; downgrade/re-upgrade succeed |
| **Blocks release** | Yes |

### WF-HAR-INTEG-02: Object Storage Integration

| Field | Value |
|-------|-------|
| **Command** | `make storage-smoke` |
| **What it runs** | MinIO create-bucket/put/get/delete round trip with failure-safe cleanup |
| **Environment** | Docker Compose: minio |
| **Artifact** | `.omo/evidence/static/minio-roundtrip.json` |
| **Pass criteria** | Upload/download payload match; bucket cleaned up on success and failure paths |
| **Blocks release** | Yes |

### WF-HAR-INTEG-03: Durable Queue Integration

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/integration/test_durable_queue.py -v` |
| **What it runs** | Atomic `FOR UPDATE SKIP LOCKED` claims, lease-owner CAS, tenant-fair selection, retry scheduling/backoff, poison-message quarantine, dead-letter/replay, and transactional-outbox handoff against real PostgreSQL |
| **Environment** | Docker Compose: postgres:16 |
| **Artifact** | `evidence/integration/durable-queue.json` |
| **Pass criteria** | No duplicate ownership; stale worker cannot complete after lease loss; retry backs off correctly; dead letter/replay is auditable; outbox intent cannot exist without its internal state transaction. |
| **Blocks release** | Yes |

### WF-HAR-INTEG-04: Web Server Integration

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/integration/test_web_server.py -v` |
| **What it runs** | FastAPI test client against real middleware stack, auth, routing |
| **Environment** | Docker Compose: full stack |
| **Artifact** | `evidence/integration/web-server.json` |
| **Pass criteria** | All routes respond correctly. Auth enforced. Middleware executes in order. |
| **Blocks release** | Yes |

### WF-HAR-INTEG-05: Worker Integration

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/integration/test_worker.py -v` |
| **What it runs** | Worker picks up jobs, executes, handles retries and failures against real queue |
| **Environment** | Docker Compose: full stack with worker |
| **Artifact** | `evidence/integration/worker.json` |
| **Pass criteria** | Jobs execute. Failures retry. Dead letters captured. No orphaned jobs. |
| **Blocks release** | Yes |

### WF-HAR-INTEG-06: Scheduler Integration

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/integration/test_scheduler.py -v` |
| **What it runs** | Schedule creation, trigger execution, overlap prevention against real Postgres |
| **Environment** | Docker Compose: full stack with scheduler |
| **Artifact** | `evidence/integration/scheduler.json` |
| **Pass criteria** | Schedules trigger on time. Overlapping executions prevented. State persisted. |
| **Blocks release** | Yes |

---

## Layer 7: Product-Path (WF-HAR-PRODUCT)

### WF-HAR-PRODUCT-01: Onboarding First Authoritative Recommendation

| Field | Value |
|-------|-------|
| **Command** | `playwright test tests/product/onboarding-recommendation.spec.ts` (intended) |
| **What it runs** | Loads Control Room; verifies first Recommended Next is displayed with ranking rationale |
| **Artifact** | `evidence/product/onboarding-recommendation/` (screenshots, API trace, latency metrics) |
| **Pass criteria** | First Recommended Next displayed. Ranking rationale visible. p95 read latency < 500ms. No console errors. |
| **Blocks release** | Yes |

### WF-HAR-PRODUCT-02: Why-Blocked Chain Resolution

| Field | Value |
|-------|-------|
| **Command** | `playwright test tests/product/why-blocked.spec.ts` (intended) |
| **What it runs** | Drills into why-blocked explanations for blocked items; verifies dependency chain resolves to root cause |
| **Artifact** | `evidence/product/why-blocked/` |
| **Pass criteria** | Why-blocked chains resolve to root cause. Dependency paths correct. p95 latency < 1s. |
| **Blocks release** | Yes |

### WF-HAR-PRODUCT-03: Atomic Claim Race

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/product/test_atomic_claim_race.py -v` (intended) |
| **What it runs** | Sends two concurrent claims on the same item; verifies exactly one succeeds and state is consistent |
| **Artifact** | `evidence/product/atomic-claim-race.json` |
| **Pass criteria** | Exactly one claim succeeds. Item state consistent. WorkLease assigned to winner. Loser receives conflict signal. |
| **Blocks release** | Yes |

### WF-HAR-PRODUCT-04: Proposed Dependency Repair Approval

| Field | Value |
|-------|-------|
| **Command** | `playwright test tests/product/dependency-repair.spec.ts` (intended) |
| **What it runs** | Shows dependency repair proposal; approval updates frontier correctly |
| **Artifact** | `evidence/product/dependency-repair/` |
| **Pass criteria** | Repair proposal shown with affected items. Approval creates correct `blocks` edges. Frontier recomputed. |
| **Blocks release** | Yes |

### WF-HAR-PRODUCT-05: Stale Decision Rejection

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/product/test_stale_decision.py -v` (intended) |
| **What it runs** | Submits stale authority decision; verifies rejection and AttentionItem emission |
| **Artifact** | `evidence/product/stale-decision.json` |
| **Pass criteria** | Stale decision rejected. Authority status remains `stale`. AttentionItem emitted. No state mutation. |
| **Blocks release** | Yes |

### WF-HAR-PRODUCT-06: Projection Update After Mutation

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/product/test_projection_update.py -v` (intended) |
| **What it runs** | Applies mutation (human override); verifies projection recomputed and reflects new state |
| **Artifact** | `evidence/product/projection-update.json` |
| **Pass criteria** | Mutation triggers recomputation. Projection reflects new DecisionRecord. Ranking rationale updated. |
| **Blocks release** | Yes |

---

## Layer 8: Operational (WF-HAR-OPS)

### WF-HAR-OPS-01: Smoke Test

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/ops/test_smoke.py -v` |
| **What it runs** | System start, health check, basic request/response cycle |
| **Artifact** | `evidence/ops/smoke.json` |
| **Pass criteria** | All components healthy. Basic CRUD succeeds. Response times within baseline. |
| **Blocks release** | Yes |
| **Frequency** | Every deployment |

### WF-HAR-OPS-02: Load Test

| Field | Value |
|-------|-------|
| **Command** | `k6 run tests/ops/load-test.js --out json=evidence/ops/load-test.json` |
| **What it runs** | Sustained load at Standard envelope limits (10k items, 50k edges, 100 repos) |
| **Artifact** | `evidence/ops/load-test.json` |
| **Pass criteria** | All p95 latencies within targets (see [performance envelope](performance-envelope.md)): Control Room read < 500ms, Program overview/why-blocked < 1s, Webhook-to-decision < 30s, Full solve Standard < 5s, Incremental < 2s. p95/p99 include all valid completed requests with no latency outlier removal; errors/timeouts are separately counted and reported. Error rate < 0.1%. No resource exhaustion. |
| **Blocks release** | Yes |
| **Frequency** | Every release |

### WF-HAR-OPS-02-L: Large Envelope Load Test

| Field | Value |
|-------|-------|
| **Command** | `k6 run tests/ops/load-test-large.js --out json=evidence/ops/load-test-large.json` |
| **What it runs** | Sustained load at Large envelope limits (100k items, 500k edges, 1000 repos) |
| **Artifact** | `evidence/ops/load-test-large.json` |
| **Pass criteria** | Full solve Large < 30s, Incremental < 2s. All other p95 targets per [performance-envelope.md](../quality/performance-envelope.md). Error rate < 0.1%. |
| **Blocks release** | Only for a release declaring Large-envelope support; otherwise not applicable |
| **Frequency** | Every Large-envelope certification and after relevant capacity changes |

### WF-HAR-OPS-02-T: Tenant Aggregate Capacity Test

| Field | Value |
|-------|-------|
| **Command** | `k6 run tests/ops/tenant-aggregate-capacity.js --out json=evidence/ops/tenant-aggregate-capacity.json` (intended) |
| **What it runs** | Validates bounded graph, storage, and query behavior at the Tenant Aggregate upper bounds: 1,000,000 items, 5,000,000 edges, and 10,000 repositories |
| **Artifact** | `evidence/ops/tenant-aggregate-capacity.json` |
| **Pass criteria** | No correctness loss, cross-workspace isolation breach, unbounded memory growth, or silent truncation. Results identify when architectural consultation is required before operation at these bounds. |
| **Blocks release** | Only for a release explicitly certifying Tenant Aggregate bounds; otherwise not applicable |
| **Frequency** | Every Tenant Aggregate certification and after relevant architecture changes |

### WF-HAR-OPS-03: Event Durability Test

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/ops/test_event_durability.py -v` |
| **What it runs** | Enqueues inbox deliveries, simulates crashes at every internal consistency boundary, verifies atomic snapshot/DecisionRecord/projection/audit/outbox commit and measures acknowledged-event loss |
| **Artifact** | `evidence/ops/event-durability.json` |
| **Pass criteria** | Event durability ≥ 99.99%. Zero acknowledged-event loss. No partial internal commit or orphaned external-write intent; unacknowledged events may be lost only before durable inbox persistence and are tracked. |
| **Blocks release** | Yes |
| **Frequency** | Every release |

### WF-HAR-OPS-04: Soak Test

| Field | Value |
|-------|-------|
| **Command** | `k6 run tests/ops/soak-test.js --duration 72h --out json=evidence/ops/soak-test.json` (intended) |
| **What it runs** | Sustained moderate load for 72 hours; monitors for degradation |
| **Artifact** | `evidence/ops/soak-test.json` |
| **Pass criteria** | No memory leak. No connection leak. Latency stable (no upward trend). Event durability maintained. |
| **Blocks release** | Yes |
| **Frequency** | Every release (72h full soak); 4h quick-soak on every deployment |

### WF-HAR-OPS-05: Failure Injection

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/ops/test_failure_injection.py -v` |
| **What it runs** | Kill worker mid-job, disconnect DB, fill disk, network partition; verify event durability |
| **Artifact** | `evidence/ops/failure-injection.json` |
| **Pass criteria** | System recovers. No acknowledged event loss. Jobs retry from last checkpoint. Alerting fires. |
| **Blocks release** | Yes |
| **Frequency** | Quarterly |

### WF-HAR-OPS-06: Disaster Recovery Drill

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/ops/test_dr_drill.py -v` |
| **What it runs** | Restore from backup to clean environment; verify data integrity; measure RTO |
| **Artifact** | `evidence/ops/dr-drill.json` |
| **Pass criteria** | Restore completes within RTO ≤ 60 minutes. RPO ≤ 5 minutes verified. Data integrity verified. Application starts and serves. |
| **Blocks release** | Yes |
| **Frequency** | Quarterly |

### WF-HAR-OPS-07: Migration on Live-Size Data

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/ops/test_migration_live_size.py -v` |
| **What it runs** | Applies pending migrations against Standard-envelope-sized dataset |
| **Artifact** | `evidence/ops/migration-live-size.json` |
| **Pass criteria** | Migration completes within maintenance window. Data intact. Rollback succeeds. |
| **Blocks release** | Yes |
| **Frequency** | Every migration |

---

## Cross-Cutting Harnesses

### WF-HAR-GITHUB-SANDBOX-01: GitHub Sandbox Integration

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/crosscut/test_github_sandbox.py -v` |
| **What it runs** | Real repo creation, webhook delivery, OAuth flow, rate limiting against GitHub sandbox |
| **Environment** | GitHub sandbox org with test credentials |
| **Artifact** | `evidence/crosscut/github-sandbox.json` |
| **Pass criteria** | All GitHub operations succeed against real API. Sandbox resets clean between runs. |
| **Blocks release** | Yes |

### WF-HAR-539-REPLAY-01: Issue #539 Regression

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/crosscut/test_539_replay.py -v` (intended) |
| **What it runs** | Imports program markers + textual blockers + configured policy gates (policy gates are not body edges) from #539; computes deterministic frontier; processes close/reopen (updates source state and frontier); verifies generated managed projection parity and canonical DecisionRecord hash (see [verification-strategy.md](../quality/verification-strategy.md#issue-539-replay-wf-har-539-replay)) |
| **Artifact** | `evidence/crosscut/539-replay.json` |
| **Pass criteria** | DecisionRecord hash matches golden-file. Close/reopen updates source state and frontier correctly. Managed projection agrees with full solve. Content hashes of imported data and computed DecisionRecords recorded. |
| **Blocks release** | Yes |
| **Frequency** | Every CI build |

### WF-HAR-SEC-01: Authentication Bypass

| Field | Value |
|-------|-------|
| **Command** | `schemathesis run tests/security/openapi.yaml --hypothesis-max-examples=1000 --checks all` (intended) |
| **What it runs** | Fuzzes every endpoint without auth; verifies 401/403 |
| **Artifact** | `evidence/security/auth-bypass.json` |
| **Pass criteria** | No endpoint returns 2xx without valid auth |
| **Blocks release** | Yes |

### WF-HAR-SEC-02: Input Sanitization

| Field | Value |
|-------|-------|
| **Command** | `zap-baseline.py -t http://localhost:8001 -r evidence/security/zap-baseline.json` (intended) |
| **What it runs** | OWASP ZAP baseline scan: SQL injection, XSS, path traversal |
| **Artifact** | `evidence/security/zap-baseline.json` |
| **Pass criteria** | No high or medium risk findings |
| **Blocks release** | Yes |

### WF-HAR-SEC-03: SSRF Prevention

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/security/test_ssrf.py -v` (intended) |
| **What it runs** | SSRF fuzzer against all URL-accepting endpoints |
| **Artifact** | `evidence/security/ssrf.json` |
| **Pass criteria** | No server-side request forgery. Internal network access blocked. |
| **Blocks release** | Yes |

### WF-HAR-SEC-04: IDOR Prevention

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/security/test_idor.py -v` (intended) |
| **What it runs** | Matrix: every (endpoint, object_id, user_role) triple; verifies items scoped to authorized context |
| **Artifact** | `evidence/security/idor.json` |
| **Pass criteria** | No unauthorized access to objects outside user's scope. |
| **Blocks release** | Yes |

### WF-HAR-SEC-05: CSRF Protection

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/security/test_csrf.py -v` (intended) |
| **What it runs** | State-changing endpoints reject cross-origin requests without valid token |
| **Artifact** | `evidence/security/csrf.json` |
| **Pass criteria** | All state-changing endpoints reject invalid CSRF tokens. |
| **Blocks release** | Yes |

### WF-HAR-SEC-06: Rate Limiting

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/security/test_rate_limiting.py -v` (intended) |
| **What it runs** | Load test with credential stuffing and enumeration patterns |
| **Artifact** | `evidence/security/rate-limiting.json` |
| **Pass criteria** | Brute-force and enumeration attacks throttled. Repeated failures trigger lockout or delay. |
| **Blocks release** | Yes |

### WF-HAR-SEC-07: Dependency Audit

| Field | Value |
|-------|-------|
| **Command** | `pip-audit && npm audit` (intended) |
| **What it runs** | Scans all dependencies for known CVEs |
| **Artifact** | `evidence/security/dependency-audit.json` |
| **Pass criteria** | No critical or high CVEs. Medium CVEs documented with mitigation plan. |
| **Blocks release** | Yes |

### WF-HAR-SEC-08: TLS Enforcement

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/security/test_tls.py -v` (intended) |
| **What it runs** | Verifies all inter-service communication encrypted; TLS certificate verification |
| **Artifact** | `evidence/security/tls.json` |
| **Pass criteria** | All communication channels use TLS. No plaintext fallback. |
| **Blocks release** | Yes |

### WF-HAR-SEC-09: Permission Escalation

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/security/test_permission_escalation.py -v` (intended) |
| **What it runs** | Matrix test over all endpoints; lower roles cannot perform higher-role actions |
| **Artifact** | `evidence/security/permission-escalation.json` |
| **Pass criteria** | No privilege escalation. Role boundaries enforced at every endpoint. |
| **Blocks release** | Yes |

### WF-HAR-SEC-10: Safety Gate Bypass

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/security/test_safety_gate_bypass.py -v` (intended) |
| **What it runs** | Attempts override that bypasses, weakens, or waives safety gates |
| **Artifact** | `evidence/security/safety-gate-bypass.json` |
| **Pass criteria** | All safety-gate-circumventing overrides rejected. Safety gates remain enforced. |
| **Blocks release** | Yes |

### WF-HAR-SEC-11: Override Constraint Bypass

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/security/test_override_bypass.py -v` (intended) |
| **What it runs** | Attempts scope-violating and policy-weakening overrides |
| **Artifact** | `evidence/security/override-bypass.json` |
| **Pass criteria** | All overrides outside scope rejected. Completion policy not weakened. Cascade beyond scope blocked. |
| **Blocks release** | Yes |

### WF-HAR-SEC-12: Authority Status Manipulation

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/security/test_authority_manipulation.py -v` (intended) |
| **What it runs** | Attempts to set authority status to `authoritative` without proper source level |
| **Artifact** | `evidence/security/authority-manipulation.json` |
| **Pass criteria** | Spoofed authority status rejected. Only legitimate sources can set authority. |
| **Blocks release** | Yes |

### WF-HAR-SEC-13: TrackerConnection Credential Exposure

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/security/test_credential_exposure.py -v` (intended) |
| **What it runs** | Scans all output paths for tracker credentials: logs, API responses, state dumps |
| **Artifact** | `evidence/security/credential-exposure.json` |
| **Pass criteria** | No tracker credentials in logs, API responses, or state dumps. |
| **Blocks release** | Yes |

### WF-HAR-SEC-14: Evidence Record Tampering

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/security/test_evidence_tampering.py -v` (intended) |
| **What it runs** | Attempts mutation of existing EvidenceRecords; verifies append-only enforcement |
| **Artifact** | `evidence/security/evidence-tampering.json` |
| **Pass criteria** | Old evidence records cannot be modified or deleted. Mutation attempts rejected. |
| **Blocks release** | Yes |

### WF-HAR-SEC-15: Audit Log Integrity

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/security/test_audit_integrity.py -v` (intended) |
| **What it runs** | Attempts payload, actor, timestamp, ordering, envelope, and full-segment rewrite tampering; verifies per-workspace chain validation and required external-anchor/WORM policy for privileged-DB threat profiles |
| **Artifact** | `evidence/security/audit-integrity.json` |
| **Pass criteria** | Canonical envelope/payload hash mismatch is detected. Entry overwrite/reorder fails. Privileged-DB threat profile cannot claim tamper resistance unless signed anchor or WORM evidence validates. |
| **Blocks release** | Yes |

### WF-HAR-A11Y-01: WCAG 2.2 AA

| Field | Value |
|-------|-------|
| **Command** | `playwright test tests/accessibility/wcag-audit.spec.ts` (intended) |
| **What it runs** | axe-core scan of all pages against WCAG 2.2 AA |
| **Artifact** | `evidence/accessibility/wcag-aa.json` |
| **Pass criteria** | Zero violations |
| **Blocks release** | Yes |

### WF-HAR-A11Y-02: Keyboard Navigation

| Field | Value |
|-------|-------|
| **Command** | `playwright test tests/accessibility/keyboard-nav.spec.ts` (intended) |
| **What it runs** | Tab through all interactive elements; verify focus order and visibility |
| **Artifact** | `evidence/accessibility/keyboard-nav.json` |
| **Pass criteria** | All interactive elements reachable. Focus visible. Logical tab order. |
| **Blocks release** | Yes |

### WF-HAR-A11Y-03: Focus Appearance (WCAG 2.2)

| Field | Value |
|-------|-------|
| **Command** | `playwright test tests/accessibility/focus-appearance.spec.ts` (intended) |
| **What it runs** | Verifies focus indicator meets WCAG 2.2 AA sizing and contrast requirements |
| **Artifact** | `evidence/accessibility/focus-appearance.json` |
| **Pass criteria** | Focus indicators meet 2.2 AA minimum area and contrast ratio. |
| **Blocks release** | Yes |

### WF-HAR-A11Y-04: Dragging Alternatives (WCAG 2.2)

| Field | Value |
|-------|-------|
| **Command** | `playwright test tests/accessibility/drag-alternatives.spec.ts` (intended) |
| **What it runs** | Verifies all drag operations have pointer and keyboard alternatives |
| **Artifact** | `evidence/accessibility/drag-alternatives.json` |
| **Pass criteria** | All drag operations accessible via keyboard and single-pointer alternatives. |
| **Blocks release** | Yes |

---

## Harness Summary

| Layer | Count | Blocks Release |
|-------|-------|---------------|
| Foundation / Preflight | 1 | 1 |
| Static | 5 | 4 |
| Domain | 5 | 5 |
| Property | 5 | 5 |
| Metamorphic | 5 | 5 |
| Contract | 5 | 5 |
| Integration | 6 | 6 |
| Product-Path | 6 | 6 |
| Operational | 9 | 7 required by default; 2 envelope-scoped |
| Cross-Cutting | 2 | 2 |
| Security | 15 | 15 |
| Accessibility | 4 | 4 |
| **Total** | **68** | **65 required by default; 3 scoped or informational** |

The catalog defines 68 harnesses. Sixty-five block every Standard-envelope
release. Dead-code detection is informational; Large and Tenant Aggregate
capacity harnesses become blocking only when the release declares support for
their respective envelopes. Each Standard release must carry truthful,
revision-bound evidence for all 65 blocking harnesses before it can certify.
