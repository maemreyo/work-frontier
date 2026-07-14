# Module: Platform Operations

**Path:** `backend/src/work_frontier/platform/operations`
**Role:** Operational capability truth, SLO evaluation, backup/restore manifest creation, and recovery drill evidence.

## Public interface

- `DeploymentProfile` — declared deployment capabilities with validation (single-node vs managed standard, replica counts, TLS, backup).
- `evaluate_slo(samples, p95_target_ms, max_error_rate)` — evaluates all valid completed requests without outlier removal.
- `create_backup_manifest(subject_sha, created_at, database_lsn, objects)` — creates a deterministic sorted backup inventory.
- `BackupManifest` — canonical database/object inventory at one recovery point.
- `RecoveryDrill` — measured restore and recovery point evidence with Standard RPO/RTO enforcement.
- `FailureInjectionReport` — recovery evidence for a controlled failure scenario.

## Internal structure

- `certification.py` — all operations certification types and functions.

## Depends on

- No internal module dependencies; stdlib only (hashlib, json, dataclasses, datetime, enum).

## Used by

None confirmed.

## Data & side effects

- Pure data models and validation; no I/O.

---

_Traced from source on 2026-07-14. Files examined in depth: all 2 files._
