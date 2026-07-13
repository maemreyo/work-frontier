# Module: Frontend Foundation

**Path:** `frontend`  
**Role:** Contains TypeScript contract artifacts, evidence helper code and test/tooling configuration, but no product UI shell yet.

## Public interface

- `pnpm --dir frontend test` — runs Vitest.
- `pnpm --dir frontend typecheck` — validates TypeScript.
- `buildEvidenceRecord(...)` — builds a frontend evidence-shaped object; currently not schema-equivalent to the canonical backend model.
- `validateEvidenceRecordSemantic(...)` — two-layer validation pipeline: structural validation via generated Zod schema, then semantic validation for path traversal, duration consistency, status contradictions, and applicability-reason length.

## Internal structure

- `src/contracts/decision-record.generated.ts` — generated Zod validator for DecisionRecord.
- `src/contracts/evidence-record.generated.ts` — generated Zod validator for EvidenceRecord.
- `src/contracts/evidence-record-semantic.ts` — hand-written semantic validation rules (path traversal, duration mismatch, status contradictions, applicability-reason check) mirroring backend Pydantic field validators.
- `lib/evidence-collector.ts` — manually maintained evidence helper.
- `src/hello.ts` — minimal placeholder source.

## Depends on

- **`contract-generation`** — consumes generated Zod schemas for both DecisionRecord and EvidenceRecord (`frontend/src/contracts/decision-record.generated.ts:3`, `frontend/src/contracts/evidence-record.generated.ts:3`)
- external: `typescript` — type-checks frontend foundation code (`frontend/package.json:12`)
- external: `vitest` — runs frontend unit tests (`frontend/package.json:12`)
- external: `zod` — validates generated contract values at runtime (`frontend/src/contracts/decision-record.generated.ts:3`)

## Used by

- **`delivery-ci`** — runs frontend quality checks (`.github/workflows/ci.yml:52`)

## Data & side effects

- No deployed network behavior; tests and generated-artifact validation only.

## Notes / discrepancies vs existing docs

- `lib/evidence-collector.ts` does not include all canonical `EvidenceRecord` fields such as `run_id`, `subject_sha`, canonical environment and stream references.
- The new `evidence-record-semantic.ts` mirrors backend Pydantic validators; both layers must stay in sync when the backend schema changes.
- The frontend dependency manifest contains TypeScript/Vitest/Zod tooling but no React or Vite application runtime.

---

_Traced from source on 2026-07-13. Files examined in depth: all files listed in this module’s internal structure or public interface._
