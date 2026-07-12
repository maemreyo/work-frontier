# Entry Points: Work Frontier

This is a source-verified inventory of executable surfaces found at commit `35e29a933534452757fe0515e29af7e6c6189b52`. No HTTP routes, queue consumers, cron jobs, deployed worker process, or product UI bootstrap were confirmed.

## CLI commands

| Command | Module | What it does | File |
| --- | --- | --- | --- |
| `node .omo/preflight/adr-006/validate.mjs` | `foundation-preflight` | Validates foundation baselines and negative mutations | [foundation-preflight.md](modules/foundation-preflight.md) |
| `node --test .omo/preflight/adr-006/validate.test.mjs` | `foundation-preflight` | Runs executable preflight tests | [foundation-preflight.md](modules/foundation-preflight.md) |
| `python scripts/generate_contracts.py --check` | `contract-generation` | Checks contract artifact drift | [contract-generation.md](modules/contract-generation.md) |
| `python scripts/generate_contracts.py --write` | `contract-generation` | Regenerates JSON Schema and Zod artifacts | [contract-generation.md](modules/contract-generation.md) |
| `python scripts/check_import_boundaries.py` | `architecture-enforcement` | Enforces Python layer import boundaries | [architecture-enforcement.md](modules/architecture-enforcement.md) |
| `python -m work_frontier.contracts.harness_runner` | `evidence-runtime` | Executes registered harnesses and writes evidence | [evidence-runtime.md](modules/evidence-runtime.md) |
| `python scripts/migration_smoke.py` | `infrastructure-smoke` | Proves migration rollback/recovery | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/minio_smoke.py` | `infrastructure-smoke` | Proves MinIO put/get/delete lifecycle | [infrastructure-smoke.md](modules/infrastructure-smoke.md) |
| `python scripts/build_harness_registry.py` | `evidence-runtime` | Rebuilds the machine-readable harness registry | [evidence-runtime.md](modules/evidence-runtime.md) |

## CI-triggered entry points

| Trigger | Module | What it does | File |
| --- | --- | --- | --- |
| GitHub Actions push / pull request | `delivery-ci` | Runs preflight, drift check, verification, infrastructure, security and evidence jobs | [delivery-ci.md](modules/delivery-ci.md) |

## Confirmed absent runtime surfaces

The trace found no FastAPI/Flask/Django route registration, ASGI/WSGI application, React/Vite bootstrap, queue subscription, webhook handler, scheduler registration, or cron manifest. This is a source-verified inventory, not a formal proof against every possible dynamic framework.
