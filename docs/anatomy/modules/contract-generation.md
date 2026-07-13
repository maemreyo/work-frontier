# Module: Contract Generation

**Path:** `scripts/generate_contracts.py`  
**Role:** Generates JSON Schema and frontend Zod artifacts for both DecisionRecord and EvidenceRecord from the canonical Pydantic contracts and checks drift.

## Public interface

- `python scripts/generate_contracts.py --check` — verifies generated frontend contract artifacts are current (both DecisionRecord and EvidenceRecord).
- `python scripts/generate_contracts.py --write` — regenerates JSON Schema, DecisionRecord Zod schema, and EvidenceRecord Zod schema.

## Depends on

- **`contracts`** — imports canonical DecisionRecord and EvidenceRecord models as the source schemas (`scripts/generate_contracts.py:15`)
- external: `node` — runs the JSON Schema to Zod conversion helper for both contract types (`scripts/generate_contracts.py:42`)
- external: `zod` — emits the frontend runtime validator (`scripts/generate_zod.mjs:24`)

## Used by

- **`delivery-ci`** — checks generated contract drift (`.github/workflows/ci.yml:34`)
- **`frontend-foundation`** — consumes generated Zod schemas for both DecisionRecord and EvidenceRecord (`frontend/src/contracts/decision-record.generated.ts:3`, `frontend/src/contracts/evidence-record.generated.ts:3`)

## Data & side effects

- Reads Python model metadata; writes JSON Schema and TypeScript artifacts; invokes Node.

## Notes / discrepancies vs existing docs

- `generate_zod_from_schema.mjs` requests Zod v3 generation while the frontend declares Zod 4.x; generated output currently remains simple enough to work, but the configuration should be aligned.

---

_Traced from source on 2026-07-13. Files examined in depth: all files listed in this module’s internal structure or public interface._
