# Module: Frontend Foundation

**Path:** `frontend`  
**Role:** Contains TypeScript contract artifacts, evidence helper code and test/tooling configuration, but no product UI shell yet.

## Public interface

- `pnpm --dir frontend test` — runs Vitest.
- `pnpm --dir frontend typecheck` — validates TypeScript.
- `buildEvidenceRecord(...)` — builds a frontend evidence-shaped object; currently not schema-equivalent to the canonical backend model.

## Internal structure

- `src/contracts/decision-record.generated.ts` — generated Zod validator.
- `lib/evidence-collector.ts` — manually maintained evidence helper.
- `src/hello.ts` — minimal placeholder source.

## Depends on

- **`contract-generation`** — consumes the generated DecisionRecord Zod schema (`frontend/src/contracts/decision-record.generated.ts:3`)
- external: `typescript` — type-checks frontend foundation code (`frontend/package.json:12`)
- external: `vitest` — runs frontend unit tests (`frontend/package.json:12`)
- external: `zod` — validates generated contract values at runtime (`frontend/src/contracts/decision-record.generated.ts:3`)

## Used by

- **`delivery-ci`** — runs frontend lint, type-check and tests (`.github/workflows/ci.yml:52`)

## Data & side effects

- No deployed network behavior; tests and generated-artifact validation only.

## Notes / discrepancies vs existing docs

- `lib/evidence-collector.ts` does not include all canonical `EvidenceRecord` fields such as `run_id`, `subject_sha`, canonical environment and stream references.
- The frontend dependency manifest contains TypeScript/Vitest/Zod tooling but no React or Vite application runtime.

---

_Traced from source on 2026-07-12. Files examined in depth: all files listed in this module’s internal structure or public interface._
