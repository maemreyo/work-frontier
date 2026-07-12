# Module: Delivery and CI

**Path:** `.github/workflows/ci.yml`  
**Role:** Orchestrates preflight, contract drift, static checks, tests, infrastructure smokes, security scans and evidence collection.

## Public interface

- GitHub Actions workflow jobs `preflight-gate`, `contract-drift-check`, and `verify`.
- Make targets and package scripts used by CI to install, lint, test and run harnesses.

## Depends on

- **`foundation-preflight`** — runs the preflight gate before verification (`.github/workflows/ci.yml:16`)
- **`contract-generation`** — checks generated contract drift (`.github/workflows/ci.yml:34`)
- **`architecture-enforcement`** — runs import-boundary enforcement through the harness suite (`.github/workflows/ci.yml:52`)
- **`evidence-runtime`** — executes registered harnesses and records evidence (`.github/workflows/ci.yml:52`)
- **`infrastructure-smoke`** — starts services and executes database/object-store smokes (`.github/workflows/ci.yml:52`)
- **`frontend-foundation`** — runs frontend quality checks (`.github/workflows/ci.yml:52`)
- external: `github-actions` — provides the execution environment and artifact upload (`.github/workflows/ci.yml:1`)
- external: `gitleaks` — performs secret scanning (`.github/workflows/ci.yml:70`)
- external: `sbom-tooling` — produces software bill-of-material evidence (`.github/workflows/ci.yml:78`)

## Used by

- No confirmed in-repository callers; this is the top-level orchestration boundary.

## Data & side effects

- Installs dependencies, starts containers, runs scans/tests, and uploads artifacts in GitHub Actions.

## Notes / discrepancies vs existing docs

- Harness `WF-HAR-STATIC-05` is named as secret detection plus preflight, while its registered command only executes the ADR-006 validator/tests; secret scanning is separately performed by CI.

---

_Traced from source on 2026-07-12. Files examined in depth: all files listed in this module’s internal structure or public interface._
