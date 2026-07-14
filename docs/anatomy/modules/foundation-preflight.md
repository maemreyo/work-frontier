# Module: Foundation Preflight

**Path:** `.omo/preflight/adr-006`
**Role:** Validates the seven foundation baselines and proves negative fixtures fail with typed failure IDs.

## Public interface

- `node .omo/preflight/adr-006/validate.mjs` — validates all declared foundation baselines and mutation fixtures.
- `node --test .omo/preflight/adr-006/validate.test.mjs` — exercises positive and negative validation cases.

## Depends on

- **`contracts`** — validates DecisionRecord-shaped baseline documents and hash fields (`.omo/preflight/adr-006/validate.mjs:67`)
- external: `node` — executes the validator and its test suite (`.omo/preflight/adr-006/validate.mjs:1`)

## Used by

- **`delivery-ci`** — runs the preflight gate before verification (`.github/workflows/ci.yml:16`)

## Data & side effects

- Reads baseline documents and fixtures; writes validation evidence; invokes no network services.

## Notes / discrepancies vs existing docs

- This module certifies the foundation baselines; it is not the readiness-control-plane product runtime described by target architecture docs.

---

_Traced from source on 2026-07-14. Files examined in depth: all 29 files._
