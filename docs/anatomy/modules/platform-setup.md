# Module: Platform Setup

**Path:** `backend/src/work_frontier/platform/setup`
**Role:** Local system probes and allowlisted process setup action runners for the interactive Setup Center.

## Public interface

- `LocalSystemProbe` — detects supported local tools and services without mutations (git, uv, node, pnpm, docker-compose, GitHub CLI auth, DB port, object-store port, legacy environment).
- `ProcessSetupActionRunner` — maps reviewed setup actions to repository-owned commands (infra-up, migration-smoke, storage-smoke, check, test-ops, certify-standard).

## Internal structure

- `local.py` — contains `LocalSystemProbe`, `ProcessSetupActionRunner`, `SubprocessPort`, and `SetupActionExecutionError`.

## Depends on

- **`contracts`** — uses DetectionCheck, CheckState, SetupAction, SetupProfile models (`backend/src/work_frontier/platform/setup/local.py:15`)
- external: `subprocess` — runs allowlisted commands (`backend/src/work_frontier/platform/setup/local.py:7`)

## Used by

None confirmed.

## Data & side effects

- Runs subprocesses for tool detection and action execution; reads environment variables.

---

_Traced from source on 2026-07-14. Files examined in depth: all 2 files._
