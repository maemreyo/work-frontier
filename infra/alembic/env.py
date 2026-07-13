"""Alembic environment for Work Frontier infrastructure migrations."""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path
from typing import Final

from alembic import context
from sqlalchemy import engine_from_config, pool

CONFIG = context.config
DATABASE_URL_ENVIRONMENT: Final = "DATABASE_URL"
DATABASE_URL_MISSING: Final = "DATABASE_URL must be set"
ROOT: Final = Path(__file__).resolve().parents[2]
BACKEND_SRC: Final = ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from work_frontier.platform.persistence.schema import (  # noqa: E402
    metadata as TARGET_METADATA,
)

if CONFIG.config_file_name is not None:
    fileConfig(CONFIG.config_file_name)


def database_url() -> str:
    """Return the required database URL for migration execution."""
    value = os.environ.get(DATABASE_URL_ENVIRONMENT)
    if value is None:
        raise RuntimeError(DATABASE_URL_MISSING)
    return value


def run_migrations_offline() -> None:
    """Run migrations without a live database connection."""
    context.configure(
        url=database_url(),
        target_metadata=TARGET_METADATA,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the configured PostgreSQL database."""
    section = CONFIG.get_section(CONFIG.config_ini_section, {})
    section["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=TARGET_METADATA)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
