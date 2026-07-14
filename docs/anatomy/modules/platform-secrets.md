# Module: Platform Secrets

**Path:** `backend/src/work_frontier/platform/secrets`
**Role:** OS-keyring and environment-backed secret reference providers for storing and resolving secrets behind opaque references.

## Public interface

- `KeyringSecretStore` — stores/resolves secrets using the OS keyring, returns opaque `keyring://` URIs.
- `EnvironmentSecretStore` — read-only secret references resolved from an injected environment mapping (`env://` URIs).
- `CompositeSecretResolver` — resolves both environment and OS-keyring references without exposing values.

## Internal structure

- `stores.py` — contains all secret store implementations.

## Depends on

- **`contracts`** — uses SecretReference model for opaque reference URIs (`backend/src/work_frontier/platform/secrets/stores.py:13`)
- external: `keyring` — OS keyring integration for persistent secret storage (`backend/src/work_frontier/platform/secrets/stores.py:8`)

## Used by

None confirmed.

## Data & side effects

- Reads and writes secrets via OS keyring; reads environment variables.

---

_Traced from source on 2026-07-14. Files examined in depth: all 2 files._
