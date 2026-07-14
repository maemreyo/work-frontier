# System Trace: Work Frontier

Work Frontier is a dependency-aware readiness control plane under active development. The executable system spans Python and TypeScript/JS tooling: canonical contracts, preflight mutation tests, import-boundary enforcement, harness execution, evidence capture, PostgreSQL/MinIO smoke tests, an interactive Setup Center, a FastAPI control plane API with browser security, a Typer-based CLI, operations certification models, and deployment infrastructure.

**Generated:** 2026-07-14 · **Mode:** incremental update

## Tech stack & key dependencies

- **Languages:** Python, TypeScript/JavaScript, shell, YAML, CSS, HTML
- **Frameworks/libraries confirmed in use:** Pydantic, FastAPI, Typer, SQLAlchemy, Alembic, Zod, Vitest, Playwright, React, TanStack Query
- **Datastores:** PostgreSQL (production and test); SQLite (setup journal); file-based evidence artifacts
- **Message broker / queue:** PostgreSQL-backed durable queue
- **Key external tooling:** Git, Node, pnpm, uv, Docker Compose, Gitleaks, SBOM tooling, keyring
- **Infra / deployment:** local PostgreSQL and MinIO via Docker Compose; production Docker image, Kubernetes manifests, Prometheus/Grafana observability; see [deployment.md](deployment.md)

## Modules

| Module | Responsibility | Depends on | File |
| --- | --- | --- | --- |
| `foundation-preflight` | Validates the seven foundation baselines and proves negative fixtures fail with typed failure IDs. | `contracts` | [modules/foundation-preflight.md](modules/foundation-preflight.md) |
| `contracts` | Defines canonical DecisionRecord, EvidenceRecord, setup, events, and certification contracts. | — | [modules/contracts.md](modules/contracts.md) |
| `evidence-runtime` | Executes registered harnesses and writes reproducible evidence bound to the tested Git revision. | `contracts` | [modules/evidence-runtime.md](modules/evidence-runtime.md) |
| `architecture-enforcement` | Statically scans Python imports and enforces the allowed dependency matrix between architectural layers. | `contracts` | [modules/architecture-enforcement.md](modules/architecture-enforcement.md) |
| `contract-generation` | Generates JSON Schema and frontend Zod artifacts for DecisionRecord, EvidenceRecord, and Setup contracts. | `contracts` | [modules/contract-generation.md](modules/contract-generation.md) |
| `infrastructure-smoke` | Proves migration, storage, release, security, and operations behavior; builds harness registry and setup assets. | `contracts`, `contract-generation` | [modules/infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `frontend-foundation` | Control Room React app, Setup Center Web Components, Zod contract validators, evidence helpers, and Playwright accessibility tests. | `contract-generation` | [modules/frontend-foundation.md](modules/frontend-foundation.md) |
| `delivery-ci` | Orchestrates preflight, contract drift, static checks, tests, infrastructure smokes, security scans and evidence collection. | `foundation-preflight`, `contract-generation`, `architecture-enforcement`, `evidence-runtime`, `infrastructure-smoke`, `frontend-foundation` | [modules/delivery-ci.md](modules/delivery-ci.md) |
| `bootstrap-root` | Composition root with `__main__.py`, adapters, platform infrastructure (audit, crypto, object store, queue), and static assets. | `contracts` | [modules/bootstrap-root.md](modules/bootstrap-root.md) |
| `control-plane-api` | FastAPI application with route registration, session/scope middleware, CSRF/rate-limit security, and setup integration routes. | `contracts`, `setup-application` | [modules/control-plane-api.md](modules/control-plane-api.md) |
| `control-plane-cli` | Typer CLI with control-plane parity, interactive Setup Center, and headless configuration repair. | `contracts`, `control-plane-api`, `bootstrap-root` | [modules/control-plane-cli.md](modules/control-plane-cli.md) |
| `setup-application` | Coordinates detection, review, apply, resume, and readiness for the Setup Center. | `contracts`, `application-layer` | [modules/setup-application.md](modules/setup-application.md) |
| `platform-setup` | Local system probes and allowlisted process setup action runners. | `contracts` | [modules/platform-setup.md](modules/platform-setup.md) |
| `platform-operations` | SLO evaluation, backup/restore manifests, recovery drills, and failure injection reports. | — | [modules/platform-operations.md](modules/platform-operations.md) |
| `platform-security` | Browser headers, egress policy, upload validation, value redaction, and TLS configuration enforcement. | — | [modules/platform-security.md](modules/platform-security.md) |
| `platform-secrets` | OS-keyring and environment-backed secret reference providers. | `contracts` | [modules/platform-secrets.md](modules/platform-secrets.md) |
| `platform-configuration` | TOML configuration store, SQLite setup journal, and runtime settings. | `contracts` | [modules/platform-configuration.md](modules/platform-configuration.md) |
| `platform-persistence` | SQLAlchemy schema, scoped sessions, repositories, decision cycles, identity, and PostgreSQL-backed queue. | — | [modules/platform-persistence.md](modules/platform-persistence.md) |
| `application-layer` | Application services for copilot, ingestion, decision cycles, identity, and cutover 539. | `contracts` | [modules/application-layer.md](modules/application-layer.md) |
| `domain-layer` | Pure domain entities, authority reconciliation, frontier engine, graph traversal, policies, proposals, authorization, coordination, cutover, and emergency access. | — | [modules/domain-layer.md](modules/domain-layer.md) |
| `process-interfaces` | Scheduler, worker, and web process entry points. | `control-plane-api` | [modules/process-interfaces.md](modules/process-interfaces.md) |
| `deployment-infrastructure` | Production Compose, Docker image, Kubernetes manifests, and observability config. | `control-plane-api` | [modules/deployment-infrastructure.md](modules/deployment-infrastructure.md) |

## Entry points

- Primary execution surfaces: `uv run work-frontier` CLI, repository scripts, Make/package commands, GitHub Actions jobs, and a FastAPI HTTP API.
- The composition root `backend/src/work_frontier/__main__.py` now boots the CLI with full setup and control-plane commands.
- Full source-verified inventory: [entry-points.md](entry-points.md)

## Architecture at a glance

See [system-diagram.md](system-diagram.md) or the standalone [system-diagram.html](system-diagram.html). The architecture has evolved from a build-time verification pipeline into a partial readiness control plane: canonical Pydantic contracts feed generated frontend validators and define setup/event/certification schemas; a registry drives executable harnesses; the Setup Center provides interactive environment detection, planning, and application; the FastAPI control plane serves frontier, proposal, and sync endpoints with browser security middleware; and the domain layer implements authority reconciliation, graph traversal, and policy gates. PostgreSQL and MinIO are used for both smoke tests and production data services.

[data-model.md](data-model.md) covers the database schema. [deployment.md](deployment.md) covers the production Compose, Docker, and Kubernetes topology.

## Codebase health signals

**Most-connected modules** (combined confirmed inbound and outbound internal edges):

1. `contracts` — 13 connections
2. `delivery-ci` — 6 connections
3. `control-plane-api` — 5 connections
4. `contract-generation` — 4 connections
5. `control-plane-cli` — 3 connections
6. `infrastructure-smoke` — 3 connections
7. `setup-application` — 3 connections
8. `application-layer` — 2 connections
9. `architecture-enforcement` — 2 connections
10. `bootstrap-root` — 2 connections

**Orphan candidates:** `domain-layer`, `platform-operations`, `platform-persistence`, `platform-security` (stdlib-only pure logic modules; structurally appropriate)

**Dependency cycles:** none found

**Trace coverage:** 22 of 22 modules were traced in full (all files examined and documented).

## Important discrepancies

- `backend/lib/evidence_collector.py` overlaps with `contracts/evidence_writer.py`; the repository has two Python evidence construction APIs.
- Frontend `lib/evidence-collector.ts` does not match the canonical EvidenceRecord schema.
- The Zod generator requests v3 output while the frontend declares Zod 4.x.
- Target architecture documents describe planned modules and flows that are absent from executable source.
- Several adapters and platform files (adapters/connections, adapters/github) fall under the `bootstrap-root` module path boundary rather than having dedicated modules.

## How this was generated

This documentation was generated by tracing actual source rather than summarizing README claims. `_manifest.json` tracks traced state for future incremental updates; deleting it forces a full re-trace. This was an incremental update after the Setup Center integration: 8 existing module docs were re-traced and 14 new module docs were added. `_graph.json` is a machine-readable snapshot. `_diagram-data.json` is the canonical source for both diagram formats.
