# Module: Contract Generation

**Path:** `scripts/generate_contracts.py`
**Role:** Generates JSON Schema and frontend Zod artifacts for DecisionRecord, EvidenceRecord, and Setup contracts from canonical Pydantic models and checks drift.

## Public interface

- `python scripts/generate_contracts.py --check` — verifies generated frontend contract artifacts are current (DecisionRecord, EvidenceRecord, Setup contracts).
- `python scripts/generate_contracts.py --write` — regenerates JSON Schema, Zod schemas for DecisionRecord, EvidenceRecord, and Setup contracts.

## Internal structure

- `generate_contracts.py` — reads Python Pydantic models and writes JSON Schema + invokes Node for Zod generation.
- `generate_zod_from_schema.mjs` — converts JSON Schema to Zod validator source.
- `build_setup_assets.mjs` — builds frontend setup center static assets from TypeScript sources.

## Depends on

- **`contracts`** — imports canonical DecisionRecord, EvidenceRecord, and Setup models as the source schemas (`scripts/generate_contracts.py:15`)
- external: `node` — runs the JSON Schema to Zod conversion helper (`scripts/generate_contracts.py:42`)
- external: `zod` — emits the frontend runtime validator (`scripts/generate_zod.mjs:24`)

## Used by

- **`delivery-ci`** — checks generated contract drift (`.github/workflows/ci.yml:34`)
- **`frontend-foundation`** — consumes generated Zod schemas for DecisionRecord, EvidenceRecord, and Setup contracts (`frontend/src/contracts/decision-record.generated.ts:3`)
- **`infrastructure-smoke`** — generates setup contract Zod artifacts (`scripts/build_setup_assets.mjs:1`)

## Notes / discrepancies vs existing docs

- `generate_zod_from_schema.mjs` requests Zod v3 generation while the frontend declares Zod 4.x; generated output currently remains simple enough to work, but configuration should be aligned.

---

_Traced from source on 2026-07-14. Files examined in depth: all 1 files._
