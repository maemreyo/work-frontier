# Module: Evidence Runtime

**Path:** `scripts/run_harness.py`
**Role:** Executes registered harnesses and writes reproducible evidence bound to the tested Git revision with tamper detection and prerequisite-satisfaction gating.

## Public interface

- `python scripts/run_harness.py --id WF-HAR-...` — executes one registry-backed harness.
- `python scripts/run_harness.py --recertify-foundation` — runs the foundation closure and writes supersession evidence.

## Internal structure

- `harness_runner.py` — selects and executes harness commands; evidence root uses run-scoped paths (`.omo/evidence/runs/<run_id>/` instead of `.omo/evidence/static/`), eliminates legacy global-artifact fallback; supports prerequisite-satisfaction gating, TOCTOU guards, and post-closure tamper detection via evidence manifest.
- `evidence_writer.py` — writes immutable evidence artifacts.
- `scripts/run_harness.py` — CLI entry point that wraps `harness_runner` for single-harness and recertification runs.

## Depends on

- **`contracts`** — loads registry and evidence schemas, validates prerequisites (`backend/src/work_frontier/contracts/harness_runner.py:30`)
- external: `git` — captures and validates the subject commit SHA and working-tree cleanliness (`backend/src/work_frontier/contracts/evidence_writer.py:25`)
- external: `subprocess` — executes harness commands and captures stdout/stderr (`backend/src/work_frontier/contracts/harness_runner.py:53`)

## Used by

- **`delivery-ci`** — executes registered harnesses and records evidence (`.github/workflows/ci.yml:52`)

## Data & side effects

- Runs subprocesses; reads Git metadata; writes evidence, stdout and stderr files under run-scoped directory (`.omo/evidence/runs/<run_id>/`).

## Notes / discrepancies vs existing docs

- `backend/lib/evidence_collector.py` overlaps with `contracts/evidence_writer.py`; the repository currently has two Python evidence construction APIs.

---

_Traced from source on 2026-07-14. Files examined in depth: all 1 files._
