# Module: Contract Generation

**Path:** `scripts/generate_contracts.py`  
**Role:** Generates JSON Schema and frontend Zod artifacts from the canonical Pydantic contract and checks drift.

## Public interface

- `python scripts/generate_contracts.py --check` — verifies generated frontend contract artifacts are current.
- `python scripts/generate_contracts.py --write` — regenerates schema and Zod outputs.

## Depends on

- **`contracts`** — imports the canonical DecisionRecord model as the source schema (`scripts/generate_contracts.py:15`)
- external: `node` — runs the JSON Schema to Zod conversion helper (`scripts/generate_contracts.py:42`)
- external: `zod` — emits the frontend runtime validator (`scripts/generate_zod.mjs:24`)

## Used by

- **`frontend-foundation`** — provides generated TypeScript validation artifacts (`frontend/src/contracts/decision-record.generated.ts:3`)
- **`delivery-ci`** — runs the contract drift check (`.github/workflows/ci.yml:34`)

## Data & side effects

- Reads Python model metadata; writes JSON Schema and TypeScript artifacts; invokes Node.

## Notes / discrepancies vs existing docs

- `generate_zod.mjs` requests Zod v3 generation while the frontend declares Zod 4.x; generated output currently remains simple enough to work, but the configuration should be aligned.

---

_Traced from source on 2026-07-12. Files examined in depth: all files listed in this module’s internal structure or public interface._
