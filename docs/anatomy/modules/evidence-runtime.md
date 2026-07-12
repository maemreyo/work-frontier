# Module: Evidence Runtime

**Path:** `backend/src/work_frontier/contracts`  
**Role:** Executes registered harnesses and writes reproducible evidence bound to the tested Git revision.

## Public interface

- `python -m work_frontier.contracts.harness_runner` — executes selected or blocking harnesses.
- `write_evidence_record(...)` — persists canonical evidence, stdout and stderr artifacts.

## Internal structure

- `harness_runner.py` — selects and executes harness commands.
- `evidence_writer.py` — writes immutable evidence artifacts.
- `backend/lib/evidence_collector.py` — parallel helper API with overlapping responsibility.

## Depends on

- **`contracts`** — loads registry and evidence schemas and serializes validated records (`backend/src/work_frontier/contracts/harness_runner.py:53`)
- external: `git` — captures and validates the subject commit SHA (`backend/src/work_frontier/contracts/evidence_writer.py:25`)
- external: `subprocess` — executes harness commands and captures stdout/stderr (`backend/src/work_frontier/contracts/harness_runner.py:53`)

## Used by

- **`delivery-ci`** — runs blocking harnesses and uploads evidence in CI (`.github/workflows/ci.yml:52`)

## Data & side effects

- Runs subprocesses; reads Git metadata; writes evidence, stdout and stderr files.

## Notes / discrepancies vs existing docs

- `backend/lib/evidence_collector.py` overlaps with `contracts/evidence_writer.py`; the repository currently has two Python evidence construction APIs.

---

_Traced from source on 2026-07-12. Files examined in depth: all files listed in this module’s internal structure or public interface._
