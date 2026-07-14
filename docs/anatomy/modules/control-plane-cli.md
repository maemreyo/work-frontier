# Module: Control Plane CLI

**Path:** `backend/src/work_frontier/interfaces/cli`
**Role:** Typer-based CLI with endpoint parity for the control plane API, interactive setup center, and headless configuration repair.

## Public interface

- `uv run work-frontier setup` or `work-frontier setup` — starts the loopback interactive Setup Center and opens the browser.
- `work-frontier setup status` — shows environment capability readiness.
- `work-frontier setup repair` — opens the persistent setup experience for repair.
- `work-frontier setup plan` — creates a secret-free setup plan for a profile.
- `work-frontier setup apply` — revalidates and applies a serialized reviewed plan.
- `work-frontier config show` — shows redacted configuration.
- `work-frontier frontier` — lists frontier items.
- `work-frontier item <id>` — shows one frontier item.
- `work-frontier claim <id>` — claims a work item.
- `work-frontier sync` — schedules a workspace sync.
- `work-frontier proposal approve` — approves a proposal.
- `work-frontier connection list` — lists connections.
- `work-frontier writer state` — shows writer state.
- `work-frontier certify` — shows certification status.

## Internal structure

- `main.py` — builds the Typer CLI bound to the public control-plane API via client.
- `setup.py` — interactive Setup Center CLI commands and server launcher (loopback FastAPI with uvicorn). Uses a `_SetupComposition` dataclass (`__main__.py` injects factories via `configure()`) instead of bare module-level globals.
- `client.py` — HTTP client for the control plane API.

## Depends on

- **`contracts`** — uses SetupPlan, CapabilityReport, SetupProfile for CLI commands (`backend/src/work_frontier/interfaces/cli/setup.py:25`)
- **`control-plane-api`** — imports `create_setup_app` and `SecretWriter` for CLI setup server (`backend/src/work_frontier/interfaces/cli/setup.py:24,26`)
- **`bootstrap-root`** — imports `build_setup_service` from bootstrap (`backend/src/work_frontier/__main__.py:7`)
- external: `typer` — CLI framework (`backend/src/work_frontier/interfaces/cli/main.py:8`)
- external: `rich` — table rendering for status output (`backend/src/work_frontier/interfaces/cli/setup.py:17`)
- external: `uvicorn` — ASGI server for the setup loopback app (`backend/src/work_frontier/interfaces/cli/setup.py:16`)

## Used by

None confirmed.

## Data & side effects

- Makes HTTP requests to the control plane API; starts a temporary loopback web server for interactive setup.

---

_Traced from source on 2026-07-14. Files examined in depth: all 4 files._
