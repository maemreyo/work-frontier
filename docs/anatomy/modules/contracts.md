# Module: Canonical Contracts

**Path:** `backend/src/work_frontier/contracts`
**Role:** Defines canonical DecisionRecord, EvidenceRecord, setup contracts, event envelopes, release certification, and harness registry schemas.

## Public interface

- `DecisionRecordContract` — strict, frozen canonical decision record model.
- `EvidenceRecord` — canonical harness evidence model with semantic field validation (no leading slash on paths, required `os` environment key, duration consistency, status contradiction checks).
- `load_registry()` / `validate_foundation_closure()` — load and verify the harness registry.
- `get_prerequisites()` — returns prerequisite harness IDs for a given harness.
- `get_harness()` — looks up a single harness entry by ID.
- `SetupProfile`, `SetupPlan`, `DetectionSnapshot`, `SecretReference`, `ActionResult`, `SetupEnvelope` — canonical setup domain models shared by CLI, API, and platform layers.
- `EventEnvelope`, `EventType`, `EventPayload` — versioned inter-process event envelopes with strict payload contracts.
- `HarnessEvidence`, `ReleaseCertification`, `sign_certification()`, `verify_certification()` — signed Standard release certification generation and verification.
- `FinalCertificationInput`, `FinalCertificationArtifact`, `FinalCertificationReport` — final certification input verification contracts.
- `DeclaredHarnessOutcome`, `resolve_declared_outcome()` — fail-closed interpretation of declared harness applicability artifacts; treats non-JSON artifacts as successful output.

## Internal structure

- `decision_record.py` — canonical decision contract and canonical JSON behavior.
- `evidence_record.py` — evidence schema with stricter validation: `Invocation.working_directory` and `Artifact.path` require POSIX relative paths (no leading slash); environment field requires `"os"` key; duration, status-contradiction and path-traversal semantic validators.
- `harness_registry.py` — registry parsing, declared artifact path validation (rejects absolute, UNC, traversal, remote, and Windows drive-letter paths), prerequisite graph validation (duplicate/self-referential/unknown/cyclical), foundation closure extraction.
- `harness_runner.py` — command execution, revision-bound and dirty-tree certification, post-closure tamper detection with evidence manifest, prerequisite-satisfaction gating.
- `evidence_writer.py` — environment, tool-version, hash, tree SHA and stream capture.
- `setup.py` — canonical setup contracts: profiles, check states, action states, plans, detection snapshots, secret references, capability reports, and setup envelopes.
- `events.py` — event type enumeration and strict event envelope with payload validation for inter-process communication.
- `release_certification.py` — signed release certification: harness evidence collection, canonical serialization, Ed25519 signing and verification, Standard threshold enforcement.
- `final_certification.py` — final certification input model with artifact archival and digest verification.
- `harness_applicability.py` — fail-closed resolver for declared harness outcome artifacts; `resolve_declared_outcome()` treats non-JSON outputs as `pass`, requires substantive `applicability_reason` for `not_applicable` status.

## Depends on

- external: `pydantic` — enforces strict immutable runtime validation and JSON schema generation (`backend/src/work_frontier/contracts/decision_record.py:87`)
- external: `cryptography` — Ed25519 signing and verification for release certification (`backend/src/work_frontier/contracts/release_certification.py:14`)

## Used by

- **`application-layer`** — uses EventEnvelope, EventType for inter-process communication (`backend/src/work_frontier/application/copilot.py:18`)
- **`architecture-enforcement`** — writes EvidenceRecord-compatible results for the boundary check (`scripts/check_import_boundaries.py:297`)
- **`bootstrap-root`** — uses canonical contracts for adapter types (`backend/src/work_frontier/contracts/setup.py:1`)
- **`contract-generation`** — imports canonical DecisionRecord, EvidenceRecord, and Setup models as the source schemas (`scripts/generate_contracts.py:15`)
- **`control-plane-api`** — uses SetupEnvelope, SetupPlan, DetectionSnapshot for setup API routes (`backend/src/work_frontier/interfaces/api/setup_app.py:20`)
- **`control-plane-cli`** — uses SetupPlan, CapabilityReport, SetupProfile for CLI commands (`backend/src/work_frontier/interfaces/cli/setup.py:25`)
- **`evidence-runtime`** — loads registry and evidence schemas, validates prerequisites (`backend/src/work_frontier/contracts/harness_runner.py:30`)
- **`foundation-preflight`** — validates DecisionRecord-shaped baseline documents and hash fields (`.omo/preflight/adr-006/validate.mjs:67`)
- **`infrastructure-smoke`** — emits structured evidence for infrastructure checks (`scripts/migration_smoke.py:159`)
- **`platform-configuration`** — uses setup contracts for plan and action models (`backend/src/work_frontier/platform/configuration/setup_storage.py:16`)
- **`platform-secrets`** — uses SecretReference model for opaque reference URIs (`backend/src/work_frontier/platform/secrets/stores.py:13`)
- **`platform-setup`** — uses DetectionCheck, CheckState, SetupAction, SetupProfile models (`backend/src/work_frontier/platform/setup/local.py:15`)
- **`setup-application`** — uses SetupProfile, SetupPlan, DetectionSnapshot, ActionResult, CheckState models (`backend/src/work_frontier/application/setup/service.py:21`)

## Data & side effects

- Pure validation models except registry loading; no direct network calls.

## Notes / discrepancies vs existing docs

- Architecture documents describe many future business contracts, but only DecisionRecord/EvidenceRecord, harness, setup, events, and certification contracts are executable today.

---

_Traced from source on 2026-07-14. Files examined in depth: all 11 files._
