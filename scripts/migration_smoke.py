"""Exercise Alembic upgrade, downgrade, and re-upgrade against PostgreSQL."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

DATABASE_URL_ENVIRONMENT: Final = "DATABASE_URL"
MARKER_TABLE: Final = "bootstrap_markers"
MIGRATION_FAILURE_PROBE: Final = "migration_failure_probe"
DOWNGRADE_RETAINED_MARKER: Final = "downgrade retained bootstrap marker"
INVALID_DDL: Final = "THIS IS INVALID SQL"
INVALID_DDL_PARTIAL_SCHEMA: Final = "invalid DDL left partial schema"
REUPGRADE_MISSING_MARKER: Final = "re-upgrade missing bootstrap marker"
UNSUPPORTED_MIGRATION_OPERATION: Final = "unsupported migration operation"
UPGRADE_MISSING_MARKER: Final = "upgrade missing bootstrap marker"


class MigrationSmokeError(RuntimeError):
    """Signal a failed migration lifecycle assertion."""


def database_url() -> str:
    """Return the required database URL for the migration smoke test."""
    value = os.environ.get(DATABASE_URL_ENVIRONMENT)
    if value is None:
        raise MigrationSmokeError(DATABASE_URL_ENVIRONMENT)
    return value


def run_alembic(*arguments: str) -> None:
    """Run one Alembic lifecycle command."""
    config = Config("alembic.ini")
    match arguments:
        case ("upgrade", revision):
            _ = command.upgrade(config, revision)
        case ("downgrade", revision):
            _ = command.downgrade(config, revision)
        case _:
            raise MigrationSmokeError(UNSUPPORTED_MIGRATION_OPERATION)


def marker_table_exists(url: str) -> bool:
    """Return whether the baseline table exists in PostgreSQL."""
    engine = create_engine(url)
    with engine.connect() as connection:
        return MARKER_TABLE in inspect(connection).get_table_names()


def seed_marker(url: str) -> None:
    """Insert a seed row into the migrated baseline table."""
    engine = create_engine(url)
    with engine.begin() as connection:
        _ = connection.execute(
            text("INSERT INTO bootstrap_markers (label) VALUES (:label)"),
            {"label": "seeded"},
        )


def invalid_ddl_rolls_back(url: str) -> bool:
    """Return whether PostgreSQL rolls back a failed transactional DDL batch."""
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            create_probe = f"CREATE TABLE {MIGRATION_FAILURE_PROBE} (id int)"
            _ = connection.execute(text(create_probe))
            _ = connection.execute(text(INVALID_DDL))
    except DBAPIError:
        with engine.connect() as connection:
            return MIGRATION_FAILURE_PROBE not in inspect(connection).get_table_names()
    return False


def main() -> int:
    """Verify upgrade, downgrade, and re-upgrade behavior."""
    from work_frontier.contracts.evidence_record import Artifact, Result
    from work_frontier.contracts.evidence_writer import write_evidence

    start_time = datetime.now(UTC)
    repo_root = Path(__file__).parent.parent

    results: list[Result] = []
    error_detail = None
    exit_code = 0

    try:
        url = database_url()

        run_alembic("upgrade", "head")
        results.append(
            Result(kind="alembic_upgrade_head", passed=True, detail="Upgraded to head")
        )

        if not marker_table_exists(url):
            raise MigrationSmokeError(UPGRADE_MISSING_MARKER)
        results.append(
            Result(
                kind="marker_table_check",
                passed=True,
                detail="Marker table exists after upgrade",
            )
        )

        seed_marker(url)
        results.append(
            Result(kind="seed_marker", passed=True, detail="Seeded marker data")
        )

        if not invalid_ddl_rolls_back(url):
            raise MigrationSmokeError(INVALID_DDL_PARTIAL_SCHEMA)
        results.append(
            Result(
                kind="ddl_rollback_check",
                passed=True,
                detail="Invalid DDL rolled back correctly",
            )
        )

        run_alembic("downgrade", "base")
        results.append(
            Result(
                kind="alembic_downgrade_base", passed=True, detail="Downgraded to base"
            )
        )

        if marker_table_exists(url):
            raise MigrationSmokeError(DOWNGRADE_RETAINED_MARKER)
        results.append(
            Result(
                kind="marker_table_removed",
                passed=True,
                detail="Marker table removed after downgrade",
            )
        )

        run_alembic("upgrade", "head")
        results.append(
            Result(
                kind="alembic_reupgrade_head", passed=True, detail="Re-upgraded to head"
            )
        )

        if not marker_table_exists(url):
            raise MigrationSmokeError(REUPGRADE_MISSING_MARKER)
        results.append(
            Result(
                kind="marker_table_restored",
                passed=True,
                detail="Marker table restored after re-upgrade",
            )
        )

    except MigrationSmokeError as e:
        error_detail = str(e)
        exit_code = 1
        results.append(
            Result(kind="migration_error", passed=False, detail=error_detail)
        )
    except Exception as e:
        error_detail = f"{type(e).__name__}: {e}"
        exit_code = 1
        results.append(
            Result(kind="unexpected_error", passed=False, detail=error_detail)
        )

    end_time = datetime.now(UTC)

    artifacts = [
        Artifact(path="alembic.ini"),
        Artifact(path="backend/migrations"),
    ]

    _ = write_evidence(
        harness_id="WF-HAR-SMOKE-01",
        status="fail" if exit_code != 0 else "pass",
        command="python migration_smoke.py",
        exit_code=exit_code,
        working_directory=str(repo_root),
        start_time=start_time,
        end_time=end_time,
        tool_name="migration_smoke",
        artifacts=artifacts,
        results=results,
        property_bag={
            "migration_smoke": {
                "database_url_configured": DATABASE_URL_ENVIRONMENT in os.environ,
                "error": error_detail,
            }
        },
        output_filename="migration-smoke.json",
        repo_root=repo_root,
    )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
