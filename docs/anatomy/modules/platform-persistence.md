# Module: Platform Persistence

**Path:** `backend/src/work_frontier/platform/persistence`
**Role:** SQLAlchemy database schema, scoped sessions, repositories, decision cycle persistence, identity persistence, and PostgreSQL-backed queue.

## Public interface

- `DeclarativeBase` and table definitions for all tracked entities.
- `ScopedSession` — tenant/workspace-scoped database session.
- `Repository` pattern for data access.
- `DecisionCycleRepository` — persistent decision cycle tracking.
- `IdentityRepository` — identity and authorization persistence.
- `PostgresQueue` — durable PostgreSQL-backed work queue.

## Internal structure

- `schema.py` — SQLAlchemy ORM table definitions (all tracked entities).
- `scope.py` — scoped session factory with tenant/workspace partitioning.
- `database.py` — async SQLAlchemy engine and connection management.
- `repositories.py` — base repository pattern for CRUD operations.
- `decision_cycles.py` — decision cycle table and repository.
- `identity.py` — identity and authorization table and repository.
- `postgres_queue.py` — durable PostgreSQL-backed queue implementation.

## Depends on

- external: `sqlalchemy` — ORM and SQL toolkit (`backend/src/work_frontier/platform/persistence/database.py:8`)
- external: `sqlalchemy.ext.asyncio` — async SQLAlchemy support (`backend/src/work_frontier/platform/persistence/database.py:9`)

## Used by

None confirmed.

## Data & side effects

- Direct database access through SQLAlchemy; all queries are scoped by tenant/workspace.

---

_Traced from source on 2026-07-14. Files examined in depth: all 8 files._
