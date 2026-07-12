"""Exercise Alembic upgrade, downgrade, and re-upgrade against PostgreSQL."""

from __future__ import annotations

import os
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
    url = database_url()
    run_alembic("upgrade", "head")
    if not marker_table_exists(url):
        raise MigrationSmokeError(UPGRADE_MISSING_MARKER)
    seed_marker(url)
    if not invalid_ddl_rolls_back(url):
        raise MigrationSmokeError(INVALID_DDL_PARTIAL_SCHEMA)
    run_alembic("downgrade", "base")
    if marker_table_exists(url):
        raise MigrationSmokeError(DOWNGRADE_RETAINED_MARKER)
    run_alembic("upgrade", "head")
    if not marker_table_exists(url):
        raise MigrationSmokeError(REUPGRADE_MISSING_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
