# Module: Infrastructure Smoke

**Path:** `scripts`  
**Role:** Proves PostgreSQL migration rollback behavior and MinIO object lifecycle behavior against local containers.

## Public interface

- `python scripts/migration_smoke.py` — validates migration rollback/recovery.
- `python scripts/minio_roundtrip.py` — validates object storage lifecycle.
- `python scripts/build_harness_registry.py` — rebuilds the machine-readable harness registry from the Markdown catalog; now derives prerequisite relationships from section/layer layout.

## Depends on

- **`contracts`** — emits structured evidence for infrastructure checks (`scripts/migration_smoke.py:159`)
- external: `postgresql` — runs Alembic upgrade, failure injection, rollback and re-upgrade checks (`scripts/migration_smoke.py:159`)
- external: `minio` — creates a bucket and verifies put/get/delete object lifecycle (`scripts/minio_roundtrip.py:39`)
- external: `docker-compose` — provides PostgreSQL and MinIO services (`docker-compose.yml:3`)

## Used by

- **`delivery-ci`** — starts services and executes database/object-store smokes (`.github/workflows/ci.yml:52`)

## Data & side effects

- Mutates temporary PostgreSQL migration state and MinIO buckets/objects, then cleans up.

---

_Traced from source on 2026-07-13. Files examined in depth: all files listed in this module’s internal structure or public interface._
