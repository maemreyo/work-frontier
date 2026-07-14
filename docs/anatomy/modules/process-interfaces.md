# Module: Process Interfaces

**Path:** `backend/src/work_frontier/interfaces/processes`
**Role:** Independent runnable process entry points for scheduler, worker, and web processes.

## Public interface

- `run_scheduler_once(service)` — executes one fenced scheduler iteration through the application port.
- `run_worker_once(service)` — executes one durable worker iteration through the application port.
- `run_web(service)` — placeholder for the web process entrypoint.

## Internal structure

- `scheduler.py` — scheduler process entrypoint.
- `worker.py` — worker process entrypoint.
- `web.py` — web process entrypoint placeholder.

## Depends on

- **`control-plane-api`** — uses ControlPlaneService for process iteration (`backend/src/work_frontier/interfaces/processes/scheduler.py:8`)

## Used by

None confirmed.

## Data & side effects

- Intended to be run as separate processes; currently delegates to the in-memory control plane service.

---

_Traced from source on 2026-07-14. Files examined in depth: all 4 files._
