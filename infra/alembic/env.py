"""Alembic environment for Work Frontier infrastructure migrations."""

from __future__ import annotations

import os
from logging.config import fileConfig
from typing import Final

from alembic import context
from sqlalchemy import MetaData, engine_from_config, pool

CONFIG = context.config
DATABASE_URL_ENVIRONMENT: Final = "DATABASE_URL"
DATABASE_URL_MISSING: Final = "DATABASE_URL must be set"
TARGET_METADATA = MetaData()

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
