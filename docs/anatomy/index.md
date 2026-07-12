# System Trace: Work Frontier

Work Frontier currently provides a source-controlled foundation verification and evidence toolchain for a future dependency-aware readiness control plane. The executable system is primarily Python and Node/TypeScript tooling: strict contracts, preflight mutation tests, import-boundary enforcement, harness execution, evidence capture, and local PostgreSQL/MinIO smoke tests. The business control-plane runtime described in architecture documents is not implemented yet.

**Generated:** 2026-07-12 · **Mode:** full trace · **Source commit:** `35e29a933534452757fe0515e29af7e6c6189b52`

## Tech stack & key dependencies

- **Languages:** Python, TypeScript/JavaScript, shell, YAML
- **Frameworks/libraries confirmed in use:** Pydantic, Zod, Vitest, Alembic
- **Datastores:** PostgreSQL bootstrap schema; file-based evidence artifacts
- **Message broker / queue:** none implemented
- **Key external tooling:** Git, Node, pnpm, Docker Compose, Gitleaks, SBOM tooling
- **Infra / deployment:** local PostgreSQL and MinIO via Docker Compose; see [deployment.md](deployment.md)

## Modules

| Module | Responsibility | Depends on | File |
| --- | --- | --- | --- |
| `foundation-preflight` | Validates the seven foundation baselines and proves negative fixtures fail with typed failure IDs. | `contracts` | [modules/foundation-preflight.md](modules/foundation-preflight.md) |
| `contracts` | Defines canonical DecisionRecord and EvidenceRecord schemas plus harness registry contracts. | — | [modules/contracts.md](modules/contracts.md) |
| `evidence-runtime` | Executes registered harnesses and writes reproducible evidence bound to the tested Git revision. | `contracts` | [modules/evidence-runtime.md](modules/evidence-runtime.md) |
| `architecture-enforcement` | Statically scans Python imports and enforces the allowed dependency matrix between architectural layers. | `contracts` | [modules/architecture-enforcement.md](modules/architecture-enforcement.md) |
| `contract-generation` | Generates JSON Schema and frontend Zod artifacts from the canonical Pydantic contract and checks drift. | `contracts` | [modules/contract-generation.md](modules/contract-generation.md) |
| `infrastructure-smoke` | Proves PostgreSQL migration rollback behavior and MinIO object lifecycle behavior against local containers. | `contracts` | [modules/infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `frontend-foundation` | Contains TypeScript contract artifacts, evidence helper code and test/tooling configuration, but no product UI shell yet. | `contract-generation` | [modules/frontend-foundation.md](modules/frontend-foundation.md) |
| `delivery-ci` | Orchestrates preflight, contract drift, static checks, tests, infrastructure smokes, security scans and evidence collection. | `foundation-preflight`, `contract-generation`, `architecture-enforcement`, `evidence-runtime`, `infrastructure-smoke`, `frontend-foundation` | [modules/delivery-ci.md](modules/delivery-ci.md) |

## Entry points

- Primary execution surfaces are repository scripts, Make/package commands, and GitHub Actions jobs.
- No product composition root exists. `backend/src/work_frontier/bootstrap.py` is a foundation placeholder rather than an application assembly root.
- Full source-verified inventory: [entry-points.md](entry-points.md)

## Architecture at a glance

See [system-diagram.md](system-diagram.md) or the standalone [system-diagram.html](system-diagram.html). The current architecture is a build-time and CI-time verification pipeline, not a running service architecture. Canonical Pydantic contracts feed generated frontend validators; a registry drives executable harnesses; each run produces evidence tied to a Git subject SHA. PostgreSQL and MinIO exist only as smoke-test dependencies. The largest architectural risk is documentation/runtime divergence: target-state docs describe a layered readiness platform while the codebase currently contains mostly foundation scaffolding.

[data-model.md](data-model.md) covers the sole current table. [deployment.md](deployment.md) covers the verification-only Compose topology.

## Codebase health signals

**Most-connected modules** (combined confirmed inbound and outbound internal edges):

1. `delivery-ci` — 6 connections
2. `contracts` — 5 connections
3. `contract-generation` — 3 connections
4. `architecture-enforcement` — 2 connections
5. `evidence-runtime` — 2 connections
6. `foundation-preflight` — 2 connections
7. `frontend-foundation` — 2 connections
8. `infrastructure-smoke` — 2 connections

**Possible dead code / orphan modules:** the empty `domain`, `application`, `adapters`, `interfaces`, and `platform` packages are intentional scaffolds but have no confirmed runtime edges. `backend/src/work_frontier/bootstrap.py` is also not a real composition root yet.

**Dependency cycles:** none found among the traced modules.

**Trace coverage:** all 8 selected current-state modules were traced in full. Empty future-layer packages were inventoried and disclosed as scaffolds rather than promoted to modules with invented behavior.

## Important discrepancies

- Frontend evidence construction is not schema-equivalent to the canonical backend `EvidenceRecord`.
- Two overlapping Python evidence APIs exist.
- `WF-HAR-STATIC-05` registry wording and its command do not describe the same check.
- The Zod generator requests v3 output while the frontend declares Zod 4.x.
- Target architecture documents describe planned modules and flows that are absent from executable source.

## How this was generated

This documentation was generated by tracing actual source rather than summarizing README claims. `_manifest.json` tracks traced state for future incremental updates; deleting it forces a full re-trace. `_graph.json` is a machine-readable snapshot. `_diagram-data.json` is the canonical source for both diagram formats.
