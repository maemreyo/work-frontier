---
id: WF-ARCH
title: "Work Frontier — Canonical Architecture"
status: current
owner: Work Frontier architecture
version: 3.0
date: 2026-07-12
scope: |
  Modular monolith architecture, seam topology, module contracts, process
  layout, persistence model, durable queue, sync/reconciliation, REST/OpenAPI
  and CLI surface, capacity envelope, extension model, and extraction boundary.
cross_refs:
  - doc: "../integrations/GITHUB.md"
    label: "GitHub integration"
  - doc: "../domain/work-item.md"
    label: "WorkItem domain"
  - doc: "../domain/decision-record.md"
    label: "DecisionRecord domain"
  - doc: "../security/threat-model.md"
    label: "Security model"
  - doc: "../quality/performance-envelope.md"
    label: "Performance envelope"
  - doc: "../operations/deployment-profiles.md"
    label: "Deployment profiles"
  - doc: "../decisions/"
    label: "Architecture Decision Records"
---

# Work Frontier — Architecture

## 1. What Work Frontier Is

Work Frontier is a **standalone dependency-aware readiness control plane**. It
ingests work items from external trackers, normalizes them into a dependency
graph, computes readiness and ranking, and surfaces the single recommended next
task. It is not coupled to any consumer; it has no knowledge of oh-my-class or
any other system that queries it.

The oh-my-class repo contains a `work-frontier/` directory that houses this
package. GitHub issue #539 is a reference fixture for development, not an
architectural dependency. Work Frontier imports nothing from `packages/`,
`services/`, `apps/`, or `common/`.

---

## 2. Modular Monolith, Not Microservices

Work Frontier is a single deployable package. Its internal structure is a
**deep modular monolith**: separate domain modules behind clean seams, shipped
together, with forbidden import edges that prevent circular dependencies and
keep extraction possible.

Microservices are off the table. The seam discipline (section 3) keeps the
door open without paying the cost. See [ADR-003](../decisions/ADR-003-modular-monolith.md).

---

## 3. Module Taxonomy

Work Frontier's modules are organized in four layers plus adapters. The layers
enforce a strict dependency direction.

### 3.1 The Thirteen Modules

| Module | Layer | Responsibility |
|--------|-------|---------------|
| `identity` | Domain | Actor identification, machine vs user identity, token context |
| `tenancy` | Domain | Tenant scoping, tenant config, cross-tenant isolation |
| `connections` | Domain | Tracker connection registry, credential lifecycle, adapter binding |
| `graph` | Domain | Dependency graph construction, topological sort, cycle detection |
| `policies` | Domain | Readiness rules, blocking logic, priority calculation, configurable policy engine |
| `decisions` | Domain | DecisionRecord (core entity), lifecycle states, state machines, **deterministic frontier and ranking** |
| `ingestion` | Application | Pulls raw data from adapters, drives sync cycles, cursor management |
| `normalization` | Application | Maps tracker-native types to domain types, field extraction |
| `projections` | Application | Current-state views, safe auto-projections, authoritative mutation gating |
| `approvals` | Application | Gated mutations, approval workflows, human-in-the-loop checkpoints |
| `copilot` | Application | Explanations, proposals, recommendation context (not ranking) |
| `audit` | Application / Infrastructure | Append-only audit trail, checksum chain, tamper detection, evidence recording |
| `control-room` | Interfaces | REST/OpenAPI surface, CLI surface, health endpoints |

### 3.2 Layer Diagram

```mermaid
flowchart TB
    subgraph Interfaces ["Interfaces Layer"]
        CR["control-room"]
    end

    subgraph Application ["Application Layer"]
        ING["ingestion"]
        NORM["normalization"]
        PROJ["projections"]
        APRV["approvals"]
        COP["copilot"]
        AUD["audit"]
    end

    subgraph Adapters ["Adapters Layer"]
        GH["GitHubAdapter"]
        FA["FileAdapter"]
        FIX["FixtureAdapter"]
        MEM["InMemoryAdapter"]
    end

    subgraph Domain ["Domain Layer (pure)"]
        ID["identity"]
        TEN["tenancy"]
        CONN["connections"]
        GRA["graph"]
        POL["policies"]
        DEC["decisions"]
    end

    CR --> ING
    CR --> COP
    CR --> PROJ
    CR --> APRV

    ING --> NORM
    ING --> CONN
    ING --> AUD
    NORM --> DEC
    NORM --> GRA
    PROJ --> DEC
    PROJ --> GRA
    COP --> GRA
    COP --> POL
    COP --> DEC
    APRV --> DEC
    APRV --> POL

    GH --> CONN
    FA --> CONN
    FIX --> CONN
    MEM --> CONN

    DEC --> TEN
    DEC --> ID
    GRA --> DEC
    POL --> DEC
    AUD --> DEC

    style Domain fill:#e8f5e9,stroke:#2e7d32
    style Application fill:#e3f2fd,stroke:#1565c0
    style Adapters fill:#fff3e0,stroke:#e65100
    style Interfaces fill:#fce4ec,stroke:#c62828
```

### 3.3 Forbidden Import Edges

```
domain/       ──X──>  application/
domain/       ──X──>  adapters/
domain/       ──X──>  interfaces/
application/  ──X──>  interfaces/
application/  ──X──>  adapters/    (uses adapter port interfaces only)
adapters/     ──X──>  application/
adapters/     ──X──>  interfaces/
interfaces/   ──X──>  domain/      (may only import via application layer)
interfaces/   ──X──>  adapters/    (may only import via application layer)
```

Adapters implement domain interfaces. Application defines port interfaces;
adapters satisfy those ports. Application never imports concrete adapter
implementations.

### 3.4 Module Roles: Domain vs Application

Domain modules contain pure business rules. No I/O, no infrastructure
dependencies. Application modules orchestrate domain logic with infrastructure
concerns (persistence, messaging, external APIs).

`audit` sits in the Application/Infrastructure layer because it records
evidence to persistent storage. It is not a pure domain concept; it is the
infrastructure-facing witness that everything else writes through.

`copilot` sits in the Application layer because it composes domain queries
(readiness, ranking, dependency context) into explanation payloads and
mutation proposals. It does **not** own ranking or frontier computation.
Those are deterministic domain computations owned by `decisions`.

---

## 4. Module Contracts and Ownership

Every module has a single owning directory. The owner defines the public
interface, invariants, and failure behavior.

### 4.1 Key Invariants

| Module | Key Invariant | Failure Mode | Recovery |
|--------|--------------|--------------|----------|
| `decisions` | Core entity; state changes only via approved transitions; owns frontier/ranking | State corruption | Replay from immutable source snapshots |
| `audit` | Append-only; entries are immutable once written | Checksum mismatch | Halt writes, alert, manual review |
| `graph` | Typed validation detects containment cycles and dependency SCCs, then isolates invalid components | Cycle detected | Localized fail-closed; unaffected components continue |
| `policies` | Policy evaluation is pure; same input yields same readiness | Stale policy config | Re-evaluate; reads are side-effect-free |
| `projections` | Safe projections auto-apply; authoritative mutations require approval | Projection drift | Rebuild from source-item snapshots |
| `approvals` | No authoritative mutation lands without an approval record | Unauthorized write | Reject, audit event, alert |
| `ingestion` | Sync is idempotent; replaying the same window produces identical state | Partial sync | Resume from last committed cursor |
| `connections` | Credentials are never stored in the audit trail | Credential leak | Immediate rotation, audit alert |
| `identity` | Machine and user identities are never confused | Impersonation | Reject, audit event |
| `tenancy` | Every query and write is tenant-scoped | Cross-tenant leak | Fail closed |
| `copilot` | Explanations and proposals never become authority without deterministic validation and approval | Provider failure or unsafe output | Disable copilot path; deterministic decisions remain available |
| `normalization` | Tracker-native types map deterministically to domain types | Mapping drift | Re-evaluate with current profile |

### 4.2 Adapters

Adapters satisfy domain interfaces. Each adapter owns its own persistence,
transport, and error handling.

| Adapter | Role | Certification |
|---------|------|--------------|
| `GitHubAdapter` | Production tracker adapter | Level 3 (see [GITHUB.md](../integrations/GITHUB.md) section 4) |
| `FileAdapter` | Harness adapter for deterministic tests | Level 1 |
| `FixtureAdapter` | Harness adapter for snapshot tests | Level 1 |
| `InMemoryAdapter` | Harness adapter for unit tests | Level 0 |

GitHub is the only production tracker. File, Fixture, and InMemory adapters
exist solely to support deterministic test harnesses. See
[GITHUB.md](../integrations/GITHUB.md) section 4 for adapter certification.

### 4.3 Tenant-Aware Persistence

Every query and write is scoped to a tenant. The tenant id is threaded through
from the Interfaces layer down to every adapter call. Adapters that ignore the
tenant scope are considered buggy and must fail closed.

---

## 5. Process Topology

Work Frontier runs as **three runtime processes**:

```mermaid
flowchart LR
    subgraph Runtime ["work-frontier runtime"]
        direction TB
        WebAPI["web/API process"]
        Worker["worker process"]
        Scheduler["scheduler process"]
    end

    WebAPI --> PG[("PostgreSQL")]
    Worker --> PG
    Scheduler --> PG

    WebAPI --> S3[("S3-compatible store")]
    Worker --> S3

    WebAPI --> Cache[("Optional cache")]
```

### 5.1 web/API Process

FastAPI-based. Serves the REST API, OpenAPI spec, and health endpoints.
Runs in uvicorn with a configurable worker count. `GET /healthz` returns
liveness and readiness separately.

### 5.2 worker Process

Consumes jobs from the durable queue (section 7). Executes ingestion cycles,
normalization, projection updates, and reconciliation. Coordinates through
PostgreSQL; no in-process message passing with the web/API process.

### 5.3 scheduler Process

Drives time-based triggers: periodic sync, reconciliation sweeps, cache
invalidation, stale-job detection. Enqueues jobs into the durable queue.
Does not execute them.

### 5.4 Why Three Processes

Separating them allows independent scaling and failure isolation. A slow
ingestion cycle cannot block API responses. A burst of webhooks cannot starve
scheduled reconciliation.

---

## 6. Persistence Model

Work Frontier uses **PostgreSQL** as the authoritative store for all operational
state. An **append-only audit trail** records every event for traceability.
An **S3-compatible store** holds bulky evidence artifacts. An **optional cache**
accelerates reads.

This is **not** event sourcing. PostgreSQL current tables are the authoritative
source of truth for operational state. The audit trail is a permanent,
append-only record of what happened, but you cannot and must not attempt to
rebuild current state by replaying it.

### 6.1 PostgreSQL: Authoritative Current State

PostgreSQL holds the operational truth. All reads and writes go through these
tables.

**Core entity tables:**

- `work_items` — WorkItem entities with lifecycle state, computed fields, and
  metadata. Immutable source-item versions stored alongside for diff tracking.
- `decision_records` — immutable, context-complete decisions produced from a
  specific normalized snapshot and policy bundle. They retain ranking
  rationale, gate outcomes, authority status, and recommendation context.
- `connections` — Tracker connection config, credential references, active
  ingestion profile.
- `tenants` — Tenant registry and configuration.

**Infrastructure tables:**

- `gate_evaluations` — Per-item gate evaluation results and evidence.
- `attempts` — Sync and processing attempts with timing and outcome.
- `approvals` — Approval records for gated mutations.
- `overrides` — Scoped, time-bounded human overrides with provenance.
- `audit_events` — Append-only audit trail entries (see section 6.2).
- `source_item_versions` — Immutable snapshots of what the tracker reported
  at each sync. Used for diff and drift detection.
- `job_queue` — Durable queue for background work (see section 7).

### 6.2 Audit Trail (Append-Only)

The audit trail is a permanent, immutable record of every event Work Frontier
has observed or produced. It is the traceability layer. It is **not** the
source of truth for current state.

Each entry carries:

- `seq` — Monotonic sequence number.
- `tenant_id` — Tenant scope.
- `item_id` — Reference to the affected WorkItem, if applicable.
- `event_id` — Idempotency key (UUID). Unique per tenant.
- `event_type` — What happened: `ingested`, `normalized`, `state_changed`,
  `approved`, `rejected`, `override_applied`, `gate_evaluated`, etc.
- `actor` — Who did it: `machine:github`, `user:<id>`, `system:scheduler`.
- `payload` — JSONB event details.
- `checksum` — SHA-256 chain for tamper detection.
- `created_at` — Timestamp.

**Checksum chain**: Each entry's `checksum` is
`SHA256(prev_checksum || event_id || event_type)`. The first entry uses a
zero-padded genesis hash. This chain detects tampering or corruption.

The audit trail is append-only within its governed retention lifetime: entries
are never updated in place or selectively removed. Retention expiry and legal
deletion run as auditable, policy-governed segment purges. Current state lives
in the authoritative PostgreSQL tables above, not in the audit trail.

### 6.3 S3-Compatible Evidence Storage

Large evidence artifacts (full issue bodies, large comment threads, binary
attachments) are stored in an S3-compatible object store. Objects are
referenced by content hash. The audit trail references objects by key; the
objects themselves are never mutated.

```
evidence://{tenant_id}/{item_id}/{event_id}/{artifact_name}
```

Artifacts are stored with their SHA-256 hash as metadata for integrity
verification on retrieval.

### 6.4 Optional Cache

A read-through cache (Redis, Memcached, or in-process) accelerates hot-path
reads: frontier queries, projection lookups, and graph traversals. The cache
is always derived from PostgreSQL; it is never the source of truth.

---

## 7. Durable Queue

Background work is tracked through a durable queue backed by PostgreSQL.

The queue table stores:

- `id` — Job identifier.
- `tenant_id` — Tenant scope.
- `job_type` — What kind of work: `sync`, `normalize`, `reconcile`, etc.
- `state` — `pending`, `claimed`, `completed`, `failed`.
- `idempotency_key` — Derived from job inputs. Unique per tenant.
- `payload` — JSONB job parameters.
- `result` — JSONB outcome on completion.
- `heartbeat_at` — Worker heartbeat timestamp.
- `attempts` / `max_attempts` — Retry tracking.
- `created_at`, `claimed_at`, `completed_at` — Lifecycle timestamps.

### 7.1 Job Lifecycle

1. **Enqueue**: Application layer writes a job row with state `pending` and an
   idempotency key derived from the job's inputs.
2. **Claim**: Worker process selects the oldest `pending` job for its tenant,
   sets state to `claimed`, writes a heartbeat timestamp.
3. **Execute**: Worker runs the job logic. Updates heartbeat every 30 seconds.
4. **Complete/Fail**: Worker sets state to `completed` (with result) or `failed`
   (with error).

### 7.2 Stale Job Recovery

If `heartbeat_at` is older than 90 seconds and the job is in `claimed` state,
the scheduler process considers it stale and re-enqueues it (incrementing
`attempts`). If `attempts >= max_attempts`, the job moves to `failed`
permanently.

---

## 8. Sync / Reconciliation

Work Frontier keeps bidirectional sync between its PostgreSQL state and
external trackers. The `ingestion` module drives this process.

### 8.1 Incremental Sync

1. **Poll for changes**: On each sync cycle, the adapter fetches items modified
   since the last sync cursor (stored in a `sync_cursors` table).
2. **Record evidence**: For each changed item, the `ingestion` module writes an
   `ingested` event to the audit trail atomically.
3. **Normalize**: The `normalization` module maps tracker-native data to a
   versioned normalized WorkItem snapshot.
4. **Decide and project**: The decisions module produces a new immutable
   DecisionRecord; projections update PostgreSQL read/current-state tables.
5. **Advance cursor**: The sync cursor moves forward only after the state
   write commits.

### 8.2 Reconciliation

Reconciliation handles drift between local state and tracker state. The
scheduler process triggers it periodically.

- **Drift detection**: Items where current-state revision disagrees with the
  tracker's revision. Reconciliation applies the configured precedence ladder
  and emits a conflict when sources disagree; it never assumes one source wins
  every field.
- **Orphan detection**: Items in PostgreSQL that no longer exist in the tracker.
  Orphans are flagged, not deleted.
- **Gap filling**: Missing transitions from sync outages. The reconciler
  backfills from the tracker's event log.

```mermaid
sequenceDiagram
    participant Sched as Scheduler
    participant Ingest as ingestion
    participant Adp as Adapter (GitHub)
    participant PG as PostgreSQL
    participant Audit as audit trail

    Sched->>Ingest: Trigger sync cycle
    Ingest->>PG: Read last cursor
    Ingest->>Adp: Fetch changes since cursor
    Adp-->>Ingest: Changed items
    loop For each changed item
        Ingest->>Audit: Append ingested event (idempotent)
        Ingest->>PG: Update WorkItem / DecisionRecord
    end
    Ingest->>PG: Advance cursor
```

### 8.3 Idempotency and Fencing

- **Idempotency**: Every event carries an `event_id` (UUID). The audit
  trail's unique constraint on `(tenant_id, event_id)` ensures replay safety.
- **Fencing**: The `version` column on current-state tables acts as a fencing
  token. Updates use `WHERE version = $expected_version` and fail if the
  version has advanced.

---

## 9. Public API Surface

Work Frontier exposes a **REST/OpenAPI** surface and a **CLI**. Both are
production interfaces with full parity.

### 9.1 REST / OpenAPI

The REST API is documented by OpenAPI 3.1, generated from the FastAPI app and
served at `GET /openapi.json`.

| Method | Resource | Description |
|--------|----------|-------------|
| `GET` | `/healthz` | Liveness and readiness probe |
| `GET` | `/programs` | List programs (tenant-scoped) |
| `GET` | `/programs/{id}` | Get a single program with summary stats |
| `GET` | `/work-items` | List work items (filtered by program, state, readiness) |
| `GET` | `/work-items/{id}` | Get a single work item with full context |
| `GET` | `/frontier` | Query the latest persisted authoritative frontier and its DecisionRecord IDs |
| `POST` | `/work-items/{id}/revalidation` | Trigger revalidation of a specific item |
| `POST` | `/work-items/{id}/claim` | Claim a work item (lease acquisition) |
| `POST` | `/proposals` | Submit a mutation proposal for approval |
| `GET` | `/proposals` | List pending proposals |
| `POST` | `/proposals/{id}/approve` | Approve a proposal |
| `POST` | `/proposals/{id}/reject` | Reject a proposal |
| `GET` | `/connections` | List tracker connections |
| `GET` | `/audit` | Audit trail entries (paginated, tenant-scoped) |
| `POST` | `/sync` | Trigger an on-demand sync cycle |

The `/frontier` endpoint returns the latest persisted **computed safe output**.
It is the engine's recommendation, not a mutation. Viewing it does not change
state; explicit revalidation creates new immutable DecisionRecords.
See [recommended-next](../domain/recommended-next.md) for the full
specification.

### 9.2 CLI

The CLI provides the same operations as the REST API for scripting and
automation:

```
wf programs list --tenant <id>
wf work-items list --program <id> --state open
wf frontier next --tenant <id>
wf work-items claim --id <id>
wf proposals submit --type priority --item <id> --value high
wf proposals approve --id <id>
wf sync trigger --connection <id>
wf audit tail --tenant <id> --since <timestamp>
```

### 9.3 Extension Model

External consumers interact only through the REST API or CLI. They never
import Work Frontier's modules directly. The API surface is the integration
contract.

Two extension points exist:

1. **Declarative policy DSL**: Operators define readiness rules, blocking
   logic, and priority calculations in a declarative DSL. The `policies`
   module evaluates them. No code deployment required for policy changes.

2. **Isolated executable adapters**: New tracker adapters are isolated
   executables that communicate with the engine through the adapter port
   interface. They are loaded at runtime based on connection configuration.
   Each adapter runs in its own process boundary; a misbehaving adapter cannot
   crash the engine. See [GITHUB.md](../integrations/GITHUB.md) section 4 for
   adapter certification levels.

---

## 10. Capacity Envelope

Work Frontier operates within the **Standard** and **Large** capacity envelopes
defined in the [Performance Envelope](../quality/performance-envelope.md).
Deployment sizing is in [Deployment Profiles](../operations/deployment-profiles.md).

### Standard Envelope (default)

10,000 items, 50,000 edges, 100 repositories, 50 concurrent users.

### Large Envelope

100,000 items, 500,000 edges, 1,000 repositories, 200 concurrent users.
Requires explicit infrastructure sizing beyond defaults.

### Operational Limits

| Resource | Limit | Enforcement |
|----------|-------|-------------|
| Concurrent sync cycles | 1 per tenant | Durable queue serializes per tenant |
| Max evidence events per sync | 1,000 | Adapter paginates; ingestion halts and resumes next cycle |
| API request timeout | 30 seconds | uvicorn config |
| Worker job timeout | 5 minutes | Heartbeat detection (section 7.2) |
| GitHub API calls per sync | 5,000 (App token) | Adapter backs off on rate limit |
| PostgreSQL connection pool | Per-process configurable | SQLAlchemy pool |
| S3 object size | 50 MB | Adapter rejects larger artifacts |

Operational limits are enforced at the application layer without truncating
authoritative results. The performance envelope targets (latency, throughput,
resource usage) are in [performance-envelope.md](../quality/performance-envelope.md).

---

## 11. Self-Host and Hosted

Both deployment profiles share the same codebase and artifacts. The difference
is infrastructure management, not software.

- **Self-host (Compose)**: Supported standalone production profile with an
  explicitly single-node, non-HA capability statement. The Docker
  Compose setup runs one PostgreSQL instance with no replication. See
  [deployment-profiles.md](../operations/deployment-profiles.md) for sizing
  and capability matrix.
- **Hosted**: Managed deployment with HA, auto-scaling, automated backups,
  and warm DR.

Neither profile is a different build. Same container images, same database
schema, same API surface.

---

## 12. Standalone Extraction Boundary

Work Frontier is standalone by design. It has no runtime dependency on any
consumer.

### 12.1 Import Boundary

Nothing under `work-frontier/` may import from `packages/`, `services/`,
`apps/`, or `common/`. The reverse is permitted: consumers may depend on Work
Frontier.

### 12.2 Extraction Checklist

When extracting to a separate repository:

1. Move `work-frontier/` to its own repository.
2. Publish the OpenAPI spec as the integration contract.
3. Set up CI/CD for the standalone package.
4. Consumers switch from local import to package registry or git submodule.

---

## 13. Documents Not Duplicated Here

| Concern | Doc Location | Status |
|---------|-------------|--------|
| Domain vocabulary | [domain/work-item.md](../domain/work-item.md), [domain/terminology.md](../domain/terminology.md) | Written |
| DecisionRecord | [domain/decision-record.md](../domain/decision-record.md) | Written |
| Recommended next | [domain/recommended-next.md](../domain/recommended-next.md) | Written |
| Readiness and ranking | [domain/readiness-ranking.md](../domain/readiness-ranking.md) | Written |
| Authority statuses | [domain/authority-statuses.md](../domain/authority-statuses.md) | Written |
| Gates and evidence | [domain/gates-and-evidence.md](../domain/gates-and-evidence.md) | Written |
| Lifecycle and completion | [domain/lifecycle-and-completion.md](../domain/lifecycle-and-completion.md) | Written |
| GitHub adapter | [integrations/GITHUB.md](../integrations/GITHUB.md) | Written |
| Security model | [security/threat-model.md](../security/threat-model.md), [security/authorization.md](../security/authorization.md) | Written |
| Performance envelope | [quality/performance-envelope.md](../quality/performance-envelope.md) | Written |
| Deployment topology | [operations/deployment-profiles.md](../operations/deployment-profiles.md) | Written |
| ADRs | [decisions/ADR-index.md](../decisions/ADR-index.md) | Written |
| API reference | Generated OpenAPI at `/openapi.json` | Runtime |

---

> **Last updated**: 2026-07-12
> **Maintained by**: Core team.
