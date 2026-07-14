# Module: Control Plane API

**Path:** `backend/src/work_frontier/interfaces/api`
**Role:** FastAPI application with route registration, session/scope middleware, security hardening (rate limiting, CSRF, browser security headers), and optional setup integration routes.

## Public interface

- `create_app(service, setup_service, setup_secret_store)` — creates the FastAPI web process with injected application services.
- `create_setup_app(service, bootstrap_token, secret_store, static_directory)` — creates a setup-only FastAPI process with no data-plane routes.
- `install_persistent_setup_routes(app, service, secret_store)` — installs optional setup routes into the main application.
- `install_security_middleware(app)` — installs CSRF, rate limiting, and browser security header middleware.

## Internal structure

- `app.py` — main application factory with FastAPI setup, error handlers, scope middleware, read/write routes for frontier, leases, proposals, and sync. Directly imports `install_persistent_setup_routes` at module level.
- `setup_app.py` — setup-only FastAPI application factory with bootstrap token exchange, session management, detect/plan/apply workflow routes, secret and signing key routes, and static file serving.
- `setup_routes.py` — persistent setup routes that can be installed into the main app.
- `security.py` — FastAPI middleware for rate limiting (sliding window), CSRF protection (stateless HMAC), and security header injection.
- `browser_security.py` — SlidingWindowRateLimiter, CsrfProtector, and security_headers (CSP, HSTS, XFO, CORS policies).
- `models.py` — Pydantic request/response models for all API endpoints.
- `services.py` — InMemoryControlPlane service with session validation, frontier pagination, claim, proposal, approval, and attention endpoints.
- `errors.py` — typed `ControlPlaneError` exception for API error handling.

## Depends on

- **`contracts`** — uses SetupEnvelope, SetupPlan, DetectionSnapshot for setup API routes (`backend/src/work_frontier/interfaces/api/setup_app.py:20`)
- **`setup-application`** — uses SetupService for setup workflow orchestration (`backend/src/work_frontier/interfaces/api/setup_app.py:32`)
- external: `fastapi` — HTTP framework for route registration and middleware (`backend/src/work_frontier/interfaces/api/app.py:7`)
- external: `uvicorn` — ASGI server for setup app (`backend/src/work_frontier/interfaces/cli/setup.py:16`)
- external: `cryptography` — Ed25519 signing key generation in setup app (`backend/src/work_frontier/interfaces/api/setup_app.py:13`)

## Used by

- **`control-plane-cli`** — imports `create_setup_app` and `SecretWriter` for CLI setup server (`backend/src/work_frontier/interfaces/cli/setup.py:24,26`)
- **`deployment-infrastructure`** — the web process container serves the FastAPI application (`infra/docker/Dockerfile:1`)
- **`process-interfaces`** — uses ControlPlaneService for process iteration (`backend/src/work_frontier/interfaces/processes/scheduler.py:8`)

## Data & side effects

- Serves HTTP routes; validates sessions and scopes; no direct database access.

## Notes / discrepancies vs existing docs

- The API uses an in-memory control plane service; persistent database-backed service is not implemented yet.
- Security middleware only applies browser controls when the client sends cookies.

---

_Traced from source on 2026-07-14. Files examined in depth: all 9 files._
