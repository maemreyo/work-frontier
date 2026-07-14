# Module: Application Layer

**Path:** `backend/src/work_frontier/application`
**Role:** Application services, decision cycles, identity management, data ingestion, copilot integration, and cutover 539 workflow.

## Public interface

- `CopilotService` — coordinates AI assistant interactions for setup and operations.
- `IngestionService` — ingests external data into the decision cycle pipeline.
- `DecisionCycleService` — manages decision lifecycle progression.
- `IdentityService` — manages identity and authorization operations.
- `Cutover539Service` — orchestrates the 539 data migration cutover workflow.
- Port definitions for setup, connections, decision cycles, identity, ingestion, and copilot.

## Internal structure

- `ports/setup.py` — outbound port definitions (ConfigurationStore, SetupJournal, SystemProbe, SetupActionRunner).
- `ports/connections.py` — outbound port for external connection management.
- `ports/decision_cycles.py` — outbound port for decision cycle persistence.
- `ports/identity.py` — outbound port for identity storage.
- `ports/ingestion.py` — outbound port for ingestion event publishing.
- `ports/copilot.py` — outbound port for AI copilot communication.
- `copilot.py` — CopilotService implementation.
- `cutover_539.py` — Cutover539Service implementation.
- `decision_cycles.py` — DecisionCycleService implementation.
- `identity.py` — IdentityService implementation.
- `ingestion.py` — IngestionService implementation.
- `setup/` — separated into `setup-application` module.

## Depends on

- **`contracts`** — uses EventEnvelope, EventType for inter-process communication (`backend/src/work_frontier/application/copilot.py:18`)
- external: `pydantic` — uses Pydantic models for application contracts (`backend/src/work_frontier/application/ingestion.py:12`)

## Used by

- **`setup-application`** — imports ConfigurationStore, SetupJournal, SystemProbe, SetupActionRunner ports (`backend/src/work_frontier/application/ports/setup.py:10`)

## Data & side effects

- Pure orchestration logic; delegates persistence and I/O through defined ports.

---

_Traced from source on 2026-07-14. Files examined in depth: all 19 files._
