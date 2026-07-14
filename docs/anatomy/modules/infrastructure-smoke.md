# Module: Infrastructure Smoke

**Path:** `scripts`
**Role:** Proves PostgreSQL migration rollback behavior, MinIO object lifecycle, contract generation, harness registry building, setup asset building, and release/security/operations certification against local containers.

## Public interface

- `python scripts/migration_smoke.py` — validates migration rollback/recovery.
- `python scripts/minio_roundtrip.py` — validates object storage lifecycle.
- `python scripts/build_harness_registry.py` — rebuilds the machine-readable harness registry from the Markdown catalog.
- `node scripts/build_setup_assets.mjs` — builds frontend setup center static assets from TypeScript sources.
- `python scripts/run_ops_harness.py` — runs operations-level harnesses for SLO, backup, restore, and failure injection.
- `python scripts/run_security_harness.py` — runs security harnesses for CSRF, rate limiting, upload validation, egress policy, and encryption.
- `python scripts/run_release_certification.py` — runs Standard release certification against the harness registry.
- `python scripts/run_final_harness.py` — runs final verification harnesses.
- `python scripts/run_final_audits.py` — runs final audit checks.
- `python scripts/finalize_final_verification.py` — finalizes verification evidence.
- `python scripts/run_cutover_539.py` — runs the 539 cutover workflow.
- `python scripts/certify_plan_through_item_35.py` — certifies the implementation plan through item 35.
- `python scripts/check_setup_assets.py` — checks setup asset integrity and drift.
- `python scripts/check_anatomy_drift.py` — checks anatomy documentation content drift against current source.

## Depends on

- **`contracts`** — emits structured evidence for infrastructure checks (`scripts/migration_smoke.py:159`)
- **`contract-generation`** — generates setup contract Zod artifacts (`scripts/build_setup_assets.mjs:1`)
- external: `postgresql` — runs Alembic upgrade, failure injection, rollback and re-upgrade checks (`scripts/migration_smoke.py:159`)
- external: `minio` — creates a bucket and verifies put/get/delete object lifecycle (`scripts/minio_roundtrip.py:39`)
- external: `docker-compose` — provides PostgreSQL and MinIO services (`docker-compose.yml:3`)

## Used by

- **`delivery-ci`** — starts services and executes database/object-store smokes (`.github/workflows/ci.yml:52`)

## Data & side effects

- Mutates temporary PostgreSQL migration state and MinIO buckets/objects, then cleans up.

---

_Traced from source on 2026-07-14. Files examined in depth: all 30 files._
