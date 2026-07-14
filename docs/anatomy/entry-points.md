# Entry Points: Work Frontier

This is a source-verified inventory of executable surfaces found at the current commit.

## CLI commands

| Command | Module | What it does | File |
| --- | --- | --- | --- |
| `uv run work-frontier setup` | `control-plane-cli` | Starts interactive Setup Center and opens browser | [control-plane-cli.md](modules/control-plane-cli.md) |
| `work-frontier setup status` | `control-plane-cli` | Shows environment capability readiness | [control-plane-cli.md](modules/control-plane-cli.md) |
| `work-frontier setup repair` | `control-plane-cli` | Opens the persistent setup experience for repair | [control-plane-cli.md](modules/control-plane-cli.md) |
| `work-frontier setup plan` | `control-plane-cli` | Creates a secret-free setup plan | [control-plane-cli.md](modules/control-plane-cli.md) |
| `work-frontier setup apply` | `control-plane-cli` | Revalidates and applies a serialized reviewed plan | [control-plane-cli.md](modules/control-plane-cli.md) |
| `work-frontier config show` | `control-plane-cli` | Shows redacted configuration | [control-plane-cli.md](modules/control-plane-cli.md) |
| `work-frontier frontier` | `control-plane-cli` | Lists frontier items | [control-plane-cli.md](modules/control-plane-cli.md) |
| `work-frontier item <id>` | `control-plane-cli` | Shows one frontier item | [control-plane-cli.md](modules/control-plane-cli.md) |
| `work-frontier claim <id>` | `control-plane-cli` | Claims a work item | [control-plane-cli.md](modules/control-plane-cli.md) |
| `work-frontier sync` | `control-plane-cli` | Schedules a workspace sync | [control-plane-cli.md](modules/control-plane-cli.md) |
| `work-frontier proposal approve` | `control-plane-cli` | Approves a proposal | [control-plane-cli.md](modules/control-plane-cli.md) |
| `work-frontier connection list` | `control-plane-cli` | Lists connections | [control-plane-cli.md](modules/control-plane-cli.md) |
| `work-frontier writer state` | `control-plane-cli` | Shows writer state | [control-plane-cli.md](modules/control-plane-cli.md) |
| `work-frontier certify` | `control-plane-cli` | Shows certification status | [control-plane-cli.md](modules/control-plane-cli.md) |
| `node .omo/preflight/adr-006/validate.mjs` | `foundation-preflight` | Validates foundation baselines and negative mutations | [foundation-preflight.md](modules/foundation-preflight.md) |
| `node --test .omo/preflight/adr-006/validate.test.mjs` | `foundation-preflight` | Runs executable preflight tests | [foundation-preflight.md](modules/foundation-preflight.md) |
| `python scripts/generate_contracts.py --check` | `contract-generation` | Checks DecisionRecord, EvidenceRecord, Setup artifact drift | [contract-generation.md](modules/contract-generation.md) |
| `python scripts/generate_contracts.py --write` | `contract-generation` | Regenerates JSON Schema and Zod artifacts | [contract-generation.md](modules/contract-generation.md) |
| `python scripts/check_import_boundaries.py` | `architecture-enforcement` | Enforces Python layer import boundaries | [architecture-enforcement.md](modules/architecture-enforcement.md) |
| `python scripts/run_harness.py --id WF-HAR-...` | `evidence-runtime` | Executes one registry-backed harness | [evidence-runtime.md](modules/evidence-runtime.md) |
| `python scripts/run_harness.py --recertify-foundation` | `evidence-runtime` | Recertifies the foundation closure | [evidence-runtime.md](modules/evidence-runtime.md) |
| `python scripts/migration_smoke.py` | `infrastructure-smoke` | Proves migration rollback/recovery | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/minio_roundtrip.py` | `infrastructure-smoke` | Proves MinIO put/get/delete lifecycle | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/build_harness_registry.py` | `infrastructure-smoke` | Rebuilds the machine-readable harness registry | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `node scripts/build_setup_assets.mjs` | `infrastructure-smoke` | Builds frontend setup center static assets | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/run_ops_harness.py` | `infrastructure-smoke` | Runs operations-level harnesses | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/run_security_harness.py` | `infrastructure-smoke` | Runs security harnesses | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/run_release_certification.py` | `infrastructure-smoke` | Runs Standard release certification | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/run_final_harness.py` | `infrastructure-smoke` | Runs final verification harnesses | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/run_final_audits.py` | `infrastructure-smoke` | Runs final audit checks | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/finalize_final_verification.py` | `infrastructure-smoke` | Finalizes verification evidence | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/run_cutover_539.py` | `infrastructure-smoke` | Runs the 539 cutover workflow | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/certify_plan_through_item_35.py` | `infrastructure-smoke` | Certifies implementation through item 35 | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/check_setup_assets.py` | `infrastructure-smoke` | Checks setup asset integrity and drift | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/check_anatomy_drift.py` | `infrastructure-smoke` | Checks anatomy documentation drift | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |

## HTTP API routes

| Method | Path | Module | What it does | File |
| --- | --- | --- | --- | --- |
| GET | `/healthz` | `control-plane-api` | Process health check | [control-plane-api.md](modules/control-plane-api.md) |
| GET | `/metrics` | `control-plane-api` | Prometheus metrics endpoint | [control-plane-api.md](modules/control-plane-api.md) |
| GET | `/frontier` | `control-plane-api` | Lists frontier items with cursor pagination | [control-plane-api.md](modules/control-plane-api.md) |
| GET | `/frontier/{item_id}` | `control-plane-api` | Shows one frontier item | [control-plane-api.md](modules/control-plane-api.md) |
| GET | `/writer-state` | `control-plane-api` | Shows exclusive writer state | [control-plane-api.md](modules/control-plane-api.md) |
| GET | `/attention` | `control-plane-api` | Shows attention items | [control-plane-api.md](modules/control-plane-api.md) |
| POST | `/leases/{item_id}/claim` | `control-plane-api` | Claims a work item | [control-plane-api.md](modules/control-plane-api.md) |
| POST | `/proposals` | `control-plane-api` | Creates a proposal | [control-plane-api.md](modules/control-plane-api.md) |
| POST | `/proposals/{proposal_id}/approve` | `control-plane-api` | Approves a proposal | [control-plane-api.md](modules/control-plane-api.md) |
| POST | `/sync` | `control-plane-api` | Schedules a sync | [control-plane-api.md](modules/control-plane-api.md) |
| POST | `/api/setup/session/exchange` | `control-plane-api` | One-time bootstrap token exchange | [control-plane-api.md](modules/control-plane-api.md) |
| POST | `/api/setup/session/close` | `control-plane-api` | Closes setup session | [control-plane-api.md](modules/control-plane-api.md) |
| GET | `/api/setup/status` | `control-plane-api` | Setup status with detection and plan | [control-plane-api.md](modules/control-plane-api.md) |
| POST | `/api/setup/detect` | `control-plane-api` | Detects current environment state | [control-plane-api.md](modules/control-plane-api.md) |
| POST | `/api/setup/plan` | `control-plane-api` | Creates a reviewed setup plan | [control-plane-api.md](modules/control-plane-api.md) |
| POST | `/api/setup/apply` | `control-plane-api` | Applies a reviewed plan | [control-plane-api.md](modules/control-plane-api.md) |
| POST | `/api/setup/resume/{session_id}` | `control-plane-api` | Resumes interrupted setup session | [control-plane-api.md](modules/control-plane-api.md) |
| POST | `/api/setup/signing-key` | `control-plane-api` | Generates release signing key | [control-plane-api.md](modules/control-plane-api.md) |
| POST | `/api/setup/secrets` | `control-plane-api` | Stores a secret | [control-plane-api.md](modules/control-plane-api.md) |
| GET | `/setup.html` | `control-plane-api` | Setup Center HTML page | [control-plane-api.md](modules/control-plane-api.md) |
| GET | `/` | `control-plane-api` | Redirects to /setup.html | [control-plane-api.md](modules/control-plane-api.md) |

## CI-triggered entry points

| Trigger | Module | What it does | File |
| --- | --- | --- | --- |
| GitHub Actions push / pull request | `delivery-ci` | Runs preflight, drift check, verification, infrastructure, security and evidence jobs | [delivery-ci.md](modules/delivery-ci.md) |

## Runnable processes

| Process | Module | What it does | File |
| --- | --- | --- | --- |
| `run_scheduler_once(service)` | `process-interfaces` | Executes one fenced scheduler iteration | [process-interfaces.md](modules/process-interfaces.md) |
| `run_worker_once(service)` | `process-interfaces` | Executes one durable worker iteration | [process-interfaces.md](modules/process-interfaces.md) |
| `run_web(service)` | `process-interfaces` | Web process placeholder | [process-interfaces.md](modules/process-interfaces.md) |
