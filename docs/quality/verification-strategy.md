---
title: "Verification Strategy"
version: "1.0.0"
status: "canonical"
owner: "work-frontier"
last_updated: "2026-07-12"
requirement_prefix: "WF-HAR"
---

# Verification Strategy

Production-ready is proven by executable harness and signed evidence, not asserted.
Every claim about correctness, safety, or performance must trace to a harness that ran
against real code, hit real services, and produced verifiable artifacts.

> **Note:** Harness entries below are required contracts for future implementation.
> They specify what must exist and pass before release. They are not claims that tests
> already exist. All commands reference proposed Work Frontier paths, not oh-my-class
> parent paths.

---

## Principles

1. **Evidence over assertion.** "Tests pass" is not proof. A signed harness artifact
   pinned to a commit, containing structured results with timestamps and service
   versions, is proof.

2. **No single layer suffices.** Static analysis catches syntax. Property tests catch
   invariants. Metamorphic tests catch logic. Integration tests catch wiring. Product-path
   tests catch UX. Each layer covers gaps the others miss.

3. **Failure injection is not optional.** A system that has never been broken on purpose
   does not know how it breaks. Every deployment profile must exercise controlled failure
   at least quarterly.

4. **Mocks are for speed, not proof.** Mocked dependencies prove the code under test
   works with the mock. They do not prove the code works with the real thing. Every
   mock-heavy harness must have a corresponding integration harness hitting real services.

5. **Coverage is a floor, not a ceiling.** 100% line coverage means every line executed,
   not every behavior verified. Coverage numbers never substitute for explicit
   behavioral assertions.

---

## Layer Architecture

Verification layers run bottom-up. Each layer depends on the ones below it. A failure
in an early layer blocks execution of later layers, because later layers build on
correctness established below.

```
┌─────────────────────────────────────────────┐
│  Layer 8: Operational                       │  smoke, soak, DR drill
├─────────────────────────────────────────────┤
│  Layer 7: Product-Path                      │  E2E user journeys
├─────────────────────────────────────────────┤
│  Layer 6: Integration                       │  real services, real DB
├─────────────────────────────────────────────┤
│  Layer 5: Contract                          │  API/schema compatibility
├─────────────────────────────────────────────┤
│  Layer 4: Metamorphic                       │  input transformations
├─────────────────────────────────────────────┤
│  Layer 3: Property                          │  invariant-based fuzzing
├─────────────────────────────────────────────┤
│  Layer 2: Domain                            │  business logic correctness
├─────────────────────────────────────────────┤
│  Layer 1: Static                            │  types, lint, dead code
└─────────────────────────────────────────────┘
```

---

## Layer 1: Static (WF-HAR-STATIC)

Structural correctness without execution. Catches entire categories of bugs before
any runtime involvement.

| Check | Tool | Failure Mode |
|-------|------|-------------|
| Type correctness | mypy / tsc strict | Rejects untyped flows, narrows unions |
| Import boundaries | custom CI check | Prevents package/contract violations |
| Dead code elimination | vulture / ts-prune | Removes unreachable paths before review |
| Lint (Python) | ruff with full rule set | Enforces formatting, import order, naming |
| Lint (TypeScript) | Biome | Enforces formatting, import order, naming |
| Secret detection | gitleaks | Blocks committed credentials |
| License audit | license-checker | Flags incompatible dependencies |

**Pass criteria:** Zero errors across all static checks. Warnings tracked but do not
block unless explicitly promoted to error in CI config.

**Executable:** `make check-static` runs the full static suite. Exit code 0 is the
only acceptable outcome.

---

## Layer 2: Domain (WF-HAR-DOMAIN)

Work Frontier business logic correctness in isolation. Each domain rule has a
dedicated test that exercises the frontier-specific behavior directly.

| Domain Rule | What It Proves | Harness Pattern |
|-------------|---------------|-----------------|
| DecisionRecord determinism | Same snapshot + policy + engine → same canonical DecisionRecord hash | Fixed inputs produce identical DecisionRecord; golden-file diff |
| Readiness monotonicity | Closing a valid blocker cannot shrink readiness unless policy or source changes | Table-driven: close blocker, verify readiness does not regress |
| Frontier monotonicity | Adding an open blocker cannot increase the frontier set | Table-driven: add blocker edge, verify frontier does not grow |
| Input ordering invariance | Result is independent of input processing order | Shuffle input sequences, compare output |
| Invalid component localization | Invalid components are localized and rejected without corrupting neighbors | Inject invalid component, verify neighbors unaffected |
| Precedence determinism | Same source precedence ladder applied deterministically to every field | Matrix: every (source_level_pair, field_type) combination |
| Cycle detection (SCC) | Dependency cycles detected via SCC and rejected with AttentionItem | Exhaustive: every acyclic and cyclic graph shape |
| Source revision/freshness | Stale sources flagged; authority status downgraded per staleness rules | Table-driven: every (source_type, staleness_condition) pair |
| Projection parity | Full-solve and incremental projection produce consistent item ordering | Compare full vs. incremental on identical data; ordering must agree |

**Pass criteria:** Every domain rule in the domain model has at least one executable
harness. Missing rules are defects, not "nice to haves."

---

## Layer 3: Property (WF-HAR-PROPERTY)

Invariant-based testing that finds edge cases table-driven tests miss. Uses Hypothesis
(Python) or fast-check (TypeScript) for generative input. All properties exercise
Work Frontier's frontier computation, not generic data structures.

| Property Category | Example Invariant | Generation Strategy |
|-------------------|-------------------|---------------------|
| DecisionRecord stability | Same snapshot + policy + engine → identical DecisionRecord hash | Random valid inputs, replayed |
| Dependency acyclicity | Computed dependency graph is always a DAG; SCC detection rejects cycles | Generate random graphs with cycle injection |
| Readiness monotonicity | Closing valid blocker never shrinks readiness; adding open blocker never grows frontier | Random edge mutations |
| Projection convergence | Incremental projection converges to full-solve result | Random partial updates, compare to full |
| Input ordering invariance | Output identical regardless of input processing order | Random shuffle sequences |

**Pass criteria:** Minimum 10,000 random inputs per property. Shrinking on failure
must reproduce a minimal counterexample. Counterexamples become regression tests.

---

## Layer 4: Metamorphic (WF-HAR-METAMORPHIC)

Tests that cannot verify a single output (because the correct output is unknown or
expensive to compute) but can verify relationships between inputs and outputs. All
relations are specific to Work Frontier's frontier computation domain.

| Metamorphic Relation | Input Transform | Expected Output Relationship |
|---------------------|-----------------|------------------------------|
| DecisionRecord determinism | Re-run on identical snapshot | DecisionRecord hash identical (bit-for-bit) |
| Frontier monotonicity | Add an open blocker edge | Frontier set does not grow; blocked item removed from ready set |
| Readiness monotonicity | Close a valid blocker | Readiness does not shrink unless policy or source changes |
| Projection parity | Full solve vs. incremental on same data | Item ordering agrees; no item reachable in one but not the other |
| Invalid component isolation | Inject invalid component into valid graph | Valid components unaffected; invalid component rejected |

**Pass criteria:** Every metamorphic relation has at least 500 input-transform pairs.
No violated relation in the output.

---

## Layer 5: Contract (WF-HAR-CONTRACT)

API and schema compatibility. Ensures that versions communicate correctly and that
changes to interfaces do not break consumers.

| Contract Type | What It Proves | Tool |
|---------------|---------------|------|
| API request/response schema | Requests match expected shape; responses match documented shape | schemathesis (REST) |
| Database migration contract | Migration applies cleanly; data survives forward and backward | migration harness |
| Event schema contract | Published events match consumer expectations | Avro/JSON schema registry check |
| Inter-service contract | Worker ↔ Web ↔ Scheduler agree on queue message format | Contract test suite |
| Python ↔ TypeScript schema | Pydantic models match Zod schemas exactly | Cross-language roundtrip test |

**Pass criteria:** Zero contract violations. Schema drift detection runs on every PR.
Breaking changes require a versioned migration plan reviewed in the same PR.

---

## Layer 6: Integration (WF-HAR-INTEGRATION)

Real services, real databases, real queues. No mocks. Docker Compose spins up the
full stack in an isolated network.

| Integration Surface | Real Service | What It Proves |
|--------------------|-------------|-----------------|
| PostgreSQL | Postgres 16 container | Migrations, queries, connection pooling, transactions |
| Object storage | MinIO container | Upload, download, presigned URL, lifecycle policies |
| Durable queue | PostgreSQL LISTEN/NOTIFY + table queue | Enqueue, dequeue, retry, dead letter, ordering |
| Web server | FastAPI in test mode | Request routing, middleware, auth, response format |
| Worker | Background worker process | Job pickup, execution, retry, failure handling |
| Scheduler | Cron scheduler process | Schedule creation, trigger, overlap prevention |

**Execution environment:** Docker Compose with health checks. Tests wait for all
services healthy before proceeding. Tests clean up all state between runs.

**Pass criteria:** Full integration suite passes against real services. No test relies
on a mock or stub. Connection leak detection enabled (no dangling connections after suite).

---

## Layer 7: Product-Path (WF-HAR-PRODUCT-PATH)

End-to-end user journeys through the actual product UI and API. These tests prove
that a real user can accomplish real goals.

| Journey | Entry Point | Proof Artifact |
|---------|------------|----------------|
| Onboarding first authoritative recommendation | Web UI | First Recommended Next displayed with rationale; screenshot + API trace |
| Why-blocked chain resolution | Web UI + API | Blocked item drills to root cause; dependency chain correct |
| Atomic claim race | API (concurrent) | Two concurrent claims on same item; exactly one succeeds; state consistent |
| Proposed dependency repair approval | Web UI | Dependency repair proposal shown; approval updates frontier correctly |
| Stale decision rejection | API + Engine | Stale authority detected; decision rejected; AttentionItem emitted |
| Projection update after mutation | API + Engine | Mutation triggers recomputation; projection reflects new state |

**Execution:** Playwright against deployed test environment. Every journey captures:
request/response pairs, screenshots at decision points, console logs, network traces.

**Pass criteria:** Every defined product journey completes successfully. Journey
definitions reviewed quarterly against actual user workflows.

---

## Layer 8: Operational (WF-HAR-OPERATIONAL)

Proves the system survives real operational conditions. This is the layer that catches
the bugs users find.

| Operational Concern | What It Proves | Frequency |
|--------------------|---------------|-----------|
| Smoke test | System starts, accepts requests, returns correct responses | Every deployment |
| Load test | System sustains expected throughput at p95 latency targets | Every release |
| Soak test | System runs stable for extended period without degradation | 72h per release; 4h quick-soak on every deployment |
| Failure injection | System recovers from component failures without data loss | Quarterly |
| DR drill | Backup restores correctly; failover completes within RTO | Quarterly |
| Migration test | Schema changes apply on live-size data within maintenance window | Every migration |

**Pass criteria:** No operational harness required by the release's declared
capacity envelope may be skipped. Standard-envelope harnesses are required for
every release. Large and Tenant Aggregate harnesses are required when certifying
those envelopes and may otherwise be recorded as not applicable under the
[ReleaseCertification](release-certification.md) skip rules.

---

## Cross-Cutting Concerns

### GitHub Sandbox (WF-HAR-GITHUB-SANDBOX)

Every harness that exercises integration, product-path, or operational layers runs
against a real GitHub sandbox, not a mocked API. The sandbox provides:

- Real repository creation and deletion
- Real webhook delivery and verification
- Real OAuth flow (with test credentials)
- Real rate limiting behavior
- Real permissions model

The sandbox resets between test runs. State leakage between runs is a harness bug.

### Issue #539 Replay (WF-HAR-539-REPLAY)

Regression harness that replays the exact hierarchy, textual blockers, and configured
policy gates observed in issue #539, computes the deterministic frontier, processes
close/reopen cycles (which update source state and frontier), verifies generated
managed projection parity, and compares the canonical DecisionRecord hash. Policy gates
are configured gate rules, not body edges. This is a living test: if the failure mode
changes, the harness updates to match.

| Step | Operation | Assertion |
|------|-----------|-----------|
| 1 | Import observed hierarchy (item tree with parent/child `contains` edges) | Hierarchy loads without cycle detection errors |
| 2 | Import observed program markers (program priority, work class, textual blockers) | Program markers resolve correctly per precedence ladder |
| 3 | Import observed dependency graph (`blocks` edges, hard and soft) | Dependency DAG validated; SCC detection rejects any cycles |
| 4 | Import configured policy gates (gate rules, not body edges) | Gate config loads; each item evaluated against correct gate |
| 5 | Compute deterministic full-solve frontier | DecisionRecord hash matches golden-file snapshot (canonical hash match) |
| 6 | Process close events (valid blockers closed during original incident) | Closing valid blocker does not shrink readiness unless policy or source changes; source state updated |
| 7 | Process reopen events (items reopened after original fix) | Reopening does not increase frontier; source state updated; frontier recomputed |
| 8 | Re-compute frontier after close/reopen | Updated DecisionRecord hashes match updated golden-file snapshot |
| 9 | Compute managed projection from the same snapshot | Managed projection agrees with full-solve frontier (projection parity) |
| 10 | Verify no regression of original failure mode | All invariants from #539 hold: no incorrect blocking, no missing items, no order violations |

**Pass criteria:** Every step produces structured evidence with content hashes of
imported data and computed frontiers. The harness runs on every CI build and on every
deployment. Failure blocks release.

### Security Harness (WF-HAR-SECURITY)

| Check | What It Proves | Tool |
|-------|---------------|------|
| Auth bypass | No endpoint accessible without valid auth | schemathesis + custom auth fuzzer |
| Input sanitization | SQL injection, XSS, path traversal blocked | OWASP ZAP baseline |
| SSRF | No server-side request forgery via user-controlled URLs | SSRF fuzzer against all URL-accepting endpoints |
| IDOR | Insecure direct object reference blocked; items scoped to authorized context | Matrix: every (endpoint, object_id, user_role) triple |
| CSRF | State-changing endpoints reject cross-origin requests without valid token | CSRF token validation tests |
| Rate limiting | Brute-force and enumeration attacks throttled | Load test with credential stuffing patterns |
| Dependency vulnerabilities | No known CVEs in dependencies | `npm audit` + `pip-audit` |
| Secrets in transit | All inter-service communication encrypted | TLS certificate verification |
| Permission escalation | Lower roles cannot perform higher-role actions | Matrix test over all endpoints |
| Safety gate bypass | Override cannot bypass, weaken, or waive safety gates | Attempt safety-gate-circumventing overrides |
| Override constraint bypass | Override cannot weaken completion policies or cascade beyond scope | Attempt scope-violating and policy-weakening overrides |
| Authority status manipulation | Authority status cannot be set to `authoritative` without proper source | Attempt spoofed authority status |
| TrackerConnection credential exposure | Tracker credentials not logged, not in API responses, not in state dumps | Credential scan of all output paths |
| Evidence record tampering | EvidenceRecords are append-only; old records cannot be modified or deleted | Attempt mutation of existing evidence |
| Audit log integrity | Audit entries immutable once written | Attempt overwrite of audit log entries |

### Accessibility Harness (WF-HAR-A11Y)

| Check | Standard | Tool |
|-------|----------|------|
| WCAG 2.2 AA compliance | Automated axe-core scan | axe-playwright |
| Keyboard navigation | All interactive elements reachable | Playwright keyboard tests |
| Screen reader compatibility | ARIA labels present and correct | Manual + automated audit |
| Color contrast | 4.5:1 minimum for text | axe-core contrast check |
| Focus appearance (WCAG 2.2) | Focus indicator meets 2.2 AA sizing and contrast | axe-core + manual verification |
| Dragging alternatives (WCAG 2.2) | All drag operations have pointer and keyboard alternatives | Manual verification |

---

## Evidence Requirements

Every harness run produces:

1. **Structured results file** (JSON) with test IDs, pass/fail, timestamps, durations
2. **Service version manifest** listing every dependency version at execution time
3. **Commit SHA** the harness ran against (full 40-char SHA, pinned at build time)
4. **Runner metadata** (OS, runtime version, resource availability)
5. **Signature** over the results file using the release signing key
6. **SBOM/provenance** (SPDX or CycloneDX format) listing every dependency, its
   version, license, and source URL — generated from lockfiles, not declared configs
7. **Migration evidence** — if the commit includes schema changes, the migration log
   with forward timing, row counts, and rollback verification
8. **Adapter evidence** — if the commit changes any external integration adapter
   (GitHub, webhooks, etc.), the integration test results against the real sandbox
9. **Security evidence** — WF-HAR-SEC-* results bundled with the certification
10. **Performance evidence** — WF-HAR-OPS-02 (load test) results with p95/p99 latencies
11. **Restore evidence** — most recent DR drill results proving backup can be restored
12. **Accessibility evidence** — WF-HAR-A11Y-* results bundled with the certification
13. **Replay hash** — SHA-256 of the golden-file snapshots used by WF-HAR-539-REPLAY,
    pinned to this commit so drift is detectable
14. **Rollback evidence** — the previous version's image tag and the rollback command
    that would restore service, recorded at build time

Results without all applicable components are not valid evidence. Components marked
N/A for a given commit (e.g., no migration) must be explicitly recorded as N/A, not
omitted.

---

## Harness Execution Order

Layers execute bottom-up. Within a layer, harnesses execute in dependency order.
A layer must fully pass before the next layer begins.

```
Static → Domain → Property → Metamorphic → Contract → Integration → Product-Path → Operational
```

> See [harness-catalog.md](../quality/harness-catalog.md) for the full executable
> catalog with commands and artifacts. See [release-certification.md](../quality/release-certification.md)
> for how evidence chains into a signed release certificate. See
> [performance-envelope.md](../quality/performance-envelope.md) for the latency
> targets that operational harnesses verify.

If any layer fails:
1. The pipeline stops.
2. The failure produces a structured artifact (test ID, error, reproduction steps).
3. The fix must address the specific failure and re-run the full layer.
4. No layer is skipped to "save time." Time is saved by fixing the root cause.

---

## Anti-Patterns

| Anti-Pattern | Why It Fails | What To Do Instead |
|-------------|-------------|-------------------|
| "Coverage is green" as release signal | Coverage proves execution, not correctness | Require explicit behavioral assertions |
| Mocked integration tests | Proves code works with the mock, not the service | Run against real services in Docker |
| Manual QA as primary gate | Unrepeatable, slow, does not scale | Automated harnesses with manual supplement |
| "Works on my machine" | Environment-specific | Dockerized harness with pinned deps |
| Skipping operational layer | Production surprises | Operational harnesses are mandatory for release |
| Diagrams as architecture proof | Diagrams describe intent, not reality | Code-generated diagrams from runtime tracing |
