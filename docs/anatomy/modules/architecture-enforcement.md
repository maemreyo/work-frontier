# Module: Architecture Enforcement

**Path:** `scripts/check_import_boundaries.py`
**Role:** Statically scans Python imports and enforces the allowed dependency matrix between architectural layers.

## Public interface

- `python scripts/check_import_boundaries.py` — scans repository Python imports and fails on forbidden layer edges.

## Depends on

- **`contracts`** — writes EvidenceRecord-compatible results for the boundary check (`scripts/check_import_boundaries.py:297`)
- external: `python-ast` — parses imports without executing application code (`scripts/check_import_boundaries.py:255`)

## Used by

- **`delivery-ci`** — runs import-boundary enforcement through the harness suite (`.github/workflows/ci.yml:52`)

## Data & side effects

- Reads Python source files; writes evidence; does not import or execute scanned modules.

---

_Traced from source on 2026-07-14. Files examined in depth: all 1 files._
