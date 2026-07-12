# Module: Canonical Contracts

**Path:** `backend/src/work_frontier/contracts`  
**Role:** Defines canonical DecisionRecord and EvidenceRecord schemas plus harness registry contracts.

## Public interface

- `DecisionRecordContract` — strict, frozen canonical decision record model.
- `EvidenceRecord` — canonical harness evidence model.
- `load_registry()` / `validate_foundation_closure()` — load and verify the harness registry.

## Internal structure

- `decision_record.py` — canonical decision contract and canonical JSON behavior.
- `evidence_record.py` — evidence schema and nested result/artifact models.
- `harness_registry.py` — registry parsing and foundation closure validation.
- `harness_runner.py` — command execution and evidence verification.
- `evidence_writer.py` — environment, tool-version, hash and stream capture.

## Depends on

- external: `pydantic` — enforces strict immutable runtime validation and JSON schema generation (`backend/src/work_frontier/contracts/decision_record.py:87`)

## Used by

- **`contract-generation`** — imports the Pydantic contract to emit JSON Schema and TypeScript/Zod (`scripts/generate_contracts.py:15`)
- **`evidence-runtime`** — constructs and validates EvidenceRecord artifacts (`backend/src/work_frontier/contracts/evidence_writer.py:25`)
- **`foundation-preflight`** — mirrors contract-specific executable validation rules (`.omo/preflight/adr-006/validate.mjs:67`)

## Data & side effects

- Pure validation models except registry loading; no direct network calls.

## Notes / discrepancies vs existing docs

- Architecture documents describe many future business contracts, but only DecisionRecord/EvidenceRecord and harness-related contracts are executable today.

---

_Traced from source on 2026-07-12. Files examined in depth: all files listed in this module’s internal structure or public interface._
