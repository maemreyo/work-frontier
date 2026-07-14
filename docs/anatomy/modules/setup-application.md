# Module: Setup Application

**Path:** `backend/src/work_frontier/application/setup`
**Role:** Coordinates detection, review, apply, resume, and readiness across CLI, HTTP, and headless automation for the Setup Center.

## Public interface

- `SetupService` — coordinates detection, planning, application, resume, and status for setup workflows.
- `detect_environment(profile, config_revision, probe)` — returns a sorted canonical snapshot from read-only probes.
- `build_setup_plan(profile, desired, current, snapshot)` — builds a reviewed setup plan from a known snapshot.
- `execute_plan(session_id, plan, current_snapshot, ...)` — applies a reviewed plan with per-action verification and compensation.
- `derive_capability_reports(profile, checks, results)` — derives independent capability readiness reports.

## Internal structure

- `service.py` — `SetupService` class that wires detection, planning, execution, and readiness use cases.
- `detection.py` — `detect_environment()` pure function for read-only environment detection.
- `planning.py` — `build_setup_plan()` for secret-free reviewed plan creation.
- `execution.py` — `execute_plan()` with per-action apply/verify/compensate loop.
- `readiness.py` — `derive_capability_reports()` for capability readiness aggregation.

## Depends on

- **`contracts`** — uses SetupProfile, SetupPlan, DetectionSnapshot, ActionResult, CheckState models (`backend/src/work_frontier/application/setup/service.py:21`)
- **`application-layer`** — imports ConfigurationStore, SetupJournal, SystemProbe, SetupActionRunner ports (`backend/src/work_frontier/application/ports/setup.py:10`)

## Used by

- **`control-plane-api`** — uses SetupService for setup workflow orchestration (`backend/src/work_frontier/interfaces/api/setup_app.py:32`)

## Data & side effects

- No direct I/O; delegates all side effects through ports (configuration store, journal, probe, runner).

---

_Traced from source on 2026-07-14. Files examined in depth: all 6 files._
