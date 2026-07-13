# Module: Canonical Contracts

**Path:** `backend/src/work_frontier/contracts`  
**Role:** Defines canonical DecisionRecord and EvidenceRecord schemas plus harness registry contracts.

## Public interface

- `DecisionRecordContract` — strict, frozen canonical decision record model.
- `EvidenceRecord` — canonical harness evidence model with semantic field validation (no leading slash on paths, required `os` environment key, duration consistency, status contradiction checks).
- `load_registry()` / `validate_foundation_closure()` — load and verify the harness registry.
- `get_prerequisites()` — returns prerequisite harness IDs for a given harness.
- `get_harness()` — looks up a single harness entry by ID.

## Internal structure

- `decision_record.py` — canonical decision contract and canonical JSON behavior.
- `evidence_record.py` — evidence schema with stricter validation: `Invocation.working_directory` and `Artifact.path` require POSIX relative paths (no leading slash); environment field requires `"os"` key; duration, status-contradiction and path-traversal semantic validators.
- `harness_registry.py` — registry parsing, declared artifact path validation (rejects absolute, UNC, traversal, remote, and Windows drive-letter paths), prerequisite graph validation (duplicate/self-referential/unknown/cyclical), foundation closure extraction.
- `harness_runner.py` — command execution, revision-bound and dirty-tree certification, post-closure tamper detection with evidence manifest, prerequisite-satisfaction gating.
- `evidence_writer.py` — environment, tool-version, hash, tree SHA and stream capture.

## Depends on

- external: `pydantic` — enforces strict immutable runtime validation and JSON schema generation (`backend/src/work_frontier/contracts/decision_record.py:87`)

## Used by

- **`architecture-enforcement`** — writes EvidenceRecord-compatible results for the boundary check (`scripts/check_import_boundaries.py:297`)
- **`contract-generation`** — imports canonical DecisionRecord and EvidenceRecord models as the source schemas (`scripts/generate_contracts.py:15`)
- **`evidence-runtime`** — loads registry and evidence schemas, validates prerequisites (`backend/src/work_frontier/contracts/harness_runner.py:30`)
- **`foundation-preflight`** — validates DecisionRecord-shaped baseline documents and hash fields (`.omo/preflight/adr-006/validate.mjs:67`)
- **`infrastructure-smoke`** — emits structured evidence for infrastructure checks (`scripts/migration_smoke.py:159`)

## Data & side effects

- Pure validation models except registry loading; no direct network calls.

## Notes / discrepancies vs existing docs

- Architecture documents describe many future business contracts, but only DecisionRecord/EvidenceRecord and harness-related contracts are executable today.

---

_Traced from source on 2026-07-13. Files examined in depth: all files listed in this module’s internal structure or public interface._
