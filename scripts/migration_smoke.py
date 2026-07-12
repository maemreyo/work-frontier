"""Exercise Alembic upgrade, failed-revision, downgrade, and re-upgrade."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

DATABASE_URL_ENVIRONMENT: Final = "DATABASE_URL"
MARKER_TABLE: Final = "bootstrap_markers"
FAIL_TABLE: Final = "failing_revision_probe"
DOWNGRADE_RETAINED_MARKER: Final = "downgrade retained bootstrap marker"
FAILED_REVISION_NOT_ROLLED_BACK: Final = "failed Alembic revision left partial schema"
FAILED_REVISION_VERSION_ADVANCED: Final = (
    "failed Alembic revision advanced alembic_version"
)
REUPGRADE_MISSING_MARKER: Final = "re-upgrade missing bootstrap marker"
UNSUPPORTED_MIGRATION_OPERATION: Final = "unsupported migration operation"
UPGRADE_MISSING_MARKER: Final = "upgrade missing bootstrap marker"
FAILING_REVISION_ID: Final = "0002_failing_revision_probe"
VERSIONS_DIR: Final = Path("infra/alembic/versions")
FAILING_REVISION_PATH: Final = VERSIONS_DIR / f"{FAILING_REVISION_ID}.py"

FAILING_REVISION_SOURCE: Final = '''"""Temporary failing revision for smoke probe.

Revision ID: 0002_failing_revision_probe
Revises: 0001_bootstrap_marker
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_failing_revision_probe"
down_revision = "0001_bootstrap_marker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "failing_revision_probe",
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    op.execute("THIS IS INVALID SQL FROM ALEMBIC REVISION")


def downgrade() -> None:
    op.drop_table("failing_revision_probe")
'''


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


def table_exists(url: str, table_name: str) -> bool:
    engine = create_engine(url)
    with engine.connect() as connection:
        return table_name in inspect(connection).get_table_names()


def current_alembic_version(url: str) -> str | None:
    engine = create_engine(url)
    with engine.connect() as connection:
        if "alembic_version" not in inspect(connection).get_table_names():
            return None
        row = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).first()
        return None if row is None else str(row[0])


def seed_marker(url: str) -> None:
    """Insert a seed row into the migrated baseline table."""
    engine = create_engine(url)
    with engine.begin() as connection:
        _ = connection.execute(
            text("INSERT INTO bootstrap_markers (label) VALUES (:label)"),
            {"label": "seeded"},
        )


def marker_row_exists(url: str, label: str) -> bool:
    """Return whether a row with the given label exists."""
    engine = create_engine(url)
    with engine.connect() as connection:
        cursor = connection.execute(
            text("SELECT 1 FROM bootstrap_markers WHERE label = :label"),
            {"label": label},
        )
        return cursor.first() is not None


def install_failing_revision() -> Path:
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    _ = FAILING_REVISION_PATH.write_text(FAILING_REVISION_SOURCE, encoding="utf-8")
    return FAILING_REVISION_PATH


def remove_failing_revision() -> None:
    if FAILING_REVISION_PATH.exists():
        FAILING_REVISION_PATH.unlink()
    pycache = VERSIONS_DIR / "__pycache__"
    if pycache.exists():
        for path in pycache.glob(f"{FAILING_REVISION_ID}*"):
            path.unlink(missing_ok=True)


def failing_alembic_revision_rolls_back(url: str) -> None:
    """Inject a real failing revision, upgrade through Alembic, assert full rollback."""
    version_before = current_alembic_version(url)
    _ = install_failing_revision()
    try:
        failed = False
        try:
            run_alembic("upgrade", "head")
        except Exception:
            failed = True
        if not failed:
            raise MigrationSmokeError(FAILED_REVISION_NOT_ROLLED_BACK)

        if table_exists(url, FAIL_TABLE):
            raise MigrationSmokeError(FAILED_REVISION_NOT_ROLLED_BACK)

        version_after = current_alembic_version(url)
        if version_after != version_before:
            raise MigrationSmokeError(FAILED_REVISION_VERSION_ADVANCED)
    finally:
        remove_failing_revision()
        run_alembic("upgrade", "head")


def main() -> int:
    """Verify upgrade, failed revision, downgrade, and re-upgrade behavior."""
    from work_frontier.contracts.evidence_record import Artifact, Result
    from work_frontier.contracts.evidence_writer import hash_file, write_evidence

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

        if not marker_row_exists(url, "seeded"):
            raise MigrationSmokeError("seed row not found after seeding")
        results.append(
            Result(
                kind="seed_verified",
                passed=True,
                detail="Seed row confirmed present",
            )
        )

        failing_alembic_revision_rolls_back(url)
        results.append(
            Result(
                kind="failed_revision_rollback",
                passed=True,
                detail="Failed Alembic revision rolled back schema and version",
            )
        )

        if not marker_row_exists(url, "seeded"):
            raise MigrationSmokeError("seed row lost after failed revision rollback")
        results.append(
            Result(
                kind="seed_preserved_after_failure",
                passed=True,
                detail="Seed row survives failed revision",
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
    finally:
        remove_failing_revision()

    end_time = datetime.now(UTC)

    versions_dir = repo_root / "infra" / "alembic" / "versions"
    artifacts = [
        Artifact(
            path="alembic.ini",
            hashes={"sha256": hash_file(repo_root / "alembic.ini")},
        ),
        Artifact(
            path="infra/alembic/versions/0001_bootstrap_marker.py",
            hashes={"sha256": hash_file(versions_dir / "0001_bootstrap_marker.py")},
        ),
    ]

    _ = write_evidence(
        harness_id="WF-HAR-INTEG-01",
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
