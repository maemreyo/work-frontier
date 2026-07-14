# Module: Platform Configuration

**Path:** `backend/src/work_frontier/platform/configuration`
**Role:** Small versioned TOML configuration store, SQLite setup journal, and Pydantic runtime settings.

## Public interface

- `SetupPaths.from_root(root)` / `for_user()` — returns platform-appropriate configuration paths.
- `TomlConfigurationStore(paths)` — atomic compare-and-swap configuration persistence.
- `SqliteSetupJournal(path)` — transactional reviewed-plan and action-state journal.
- `SetupRuntimeSettings` — Pydantic settings model for runtime configuration.

## Internal structure

- `settings.py` — `SetupRuntimeSettings` Pydantic model for configuring setup behavior.
- `setup_storage.py` — `SetupPaths`, `TomlConfigurationStore`, `SqliteSetupJournal` implementations.

## Depends on

- **`contracts`** — uses setup contracts for plan and action models (`backend/src/work_frontier/platform/configuration/setup_storage.py:16`)
- external: `platformdirs` — platform-appropriate user config/state/log directories (`backend/src/work_frontier/platform/configuration/setup_storage.py:11`)
- external: `tomlkit` — TOML parsing and rendering (`backend/src/work_frontier/platform/configuration/setup_storage.py:13`)

## Used by

None confirmed.

## Data & side effects

- Reads and writes TOML configuration files; reads and writes SQLite journal files.

---

_Traced from source on 2026-07-14. Files examined in depth: all 3 files._
