# Module: Bootstrap and Composition Root

**Path:** `backend/src/work_frontier`
**Role:** Contains the executable composition root (`__main__.py` and `bootstrap.py`), adapters, platform infrastructure (audit, crypto, object store, queue), and interfaces wiring.

## Public interface

- `uv run work-frontier setup` — entry point via `__main__.py`, composes CLI dependencies and starts interactive setup.
- `build_setup_service()` — wires concrete local setup adapters into the application service.
- `ComposedSetupActionRunner` — dispatches setup actions across local process and GitHub adapters.

## Internal structure

- `__main__.py` — executable composition root; composes CLI dependencies from bootstrap, CLI setup, and secret stores.
- `bootstrap.py` — stable composition root with `build_setup_service()` factory and `ComposedSetupActionRunner`.
- `adapters/connections/` — in-memory/file/fixture/loader connection adapters.
- `adapters/github/` — GitHub adapter, app identity, webhook handling, and setup verifier.
- `adapters/copilot/` — Copilot AI assistant adapter with fake implementation.
- `adapters/reference_539.py` — reference 539 data migration adapter.
- `interfaces/setup_static/` — setup center static HTML/JS/CSS assets.
- `platform/audit.py` — immutable event-ledger with hash chain.
- `platform/crypto.py` — AEAD encryption/decryption with key commitment.
- `platform/object_store.py` — content-addressed object storage port.
- `platform/queue.py` — work queue and durable message port.

## Depends on

- **`contracts`** — uses canonical contracts for adapter types (`backend/src/work_frontier/contracts/setup.py:1`)
- external: `httpx` — HTTP client for GitHub API calls (`backend/src/work_frontier/bootstrap.py:11`)
- external: `cryptography` — AEAD encryption for platform crypto (`backend/src/work_frontier/platform/crypto.py:10`)

## Used by

- **`control-plane-cli`** — imports `build_setup_service` from bootstrap (`backend/src/work_frontier/__main__.py:7`)

## Data & side effects

- Reads configuration from environment and keyring; writes secrets via platform adapters.

## Notes / discrepancies vs existing docs

- The adapters directory contains both production (github, copilot) and test-support (connections/fixture, connections/memory) adapters.

---

_Traced from source on 2026-07-14. Files examined in depth: all 110 files._
