"""Create tenant-scoped platform schema, RLS, and immutability guards.

Revision ID: 0002_platform_core
Revises: 0001_bootstrap_marker
Create Date: 2026-07-13
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

from work_frontier.platform.persistence.schema import (
    APPEND_ONLY_TABLES,
    WORKSPACE_TABLES,
    metadata,
)

revision = "0002_platform_core"
down_revision = "0001_bootstrap_marker"
branch_labels = None
depends_on = None

_APP_ROLE = "work_frontier_app"


def _policy_expression() -> str:
    return (
        "tenant_id = current_setting('work_frontier.tenant_id', true) "
        "AND workspace_id = current_setting('work_frontier.workspace_id', true)"
    )


def upgrade() -> None:
    """Create operational tables and enforce workspace isolation in PostgreSQL."""
    bind = op.get_bind()
    metadata.create_all(bind=bind)
    bind.execute(
        text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'work_frontier_app') THEN
                CREATE ROLE work_frontier_app
                  NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
              END IF;
            END
            $$;
            """
        )
    )
    bind.execute(text(f"GRANT USAGE ON SCHEMA public TO {_APP_ROLE}"))

    expression = _policy_expression()
    for table in WORKSPACE_TABLES:
        name = table.name
        policy = f"workspace_isolation_{name}"
        bind.execute(text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))
        bind.execute(text(f'ALTER TABLE "{name}" FORCE ROW LEVEL SECURITY'))
        bind.execute(
            text(
                f'CREATE POLICY "{policy}" ON "{name}" '
                f"USING ({expression}) WITH CHECK ({expression})"
            )
        )
        bind.execute(
            text(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{name}" TO {_APP_ROLE}'
            )
        )

    bind.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION work_frontier_reject_mutation()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
              RAISE EXCEPTION 'append-only table % rejects %', TG_TABLE_NAME, TG_OP
                USING ERRCODE = '55000';
            END
            $$;
            """
        )
    )
    for table in APPEND_ONLY_TABLES:
        bind.execute(
            text(
                f'CREATE TRIGGER "reject_mutation_{table.name}" '
                f'BEFORE UPDATE OR DELETE ON "{table.name}" '
                "FOR EACH ROW EXECUTE FUNCTION work_frontier_reject_mutation()"
            )
        )


def downgrade() -> None:
    """Remove platform tables and role after dropping dependent policies."""
    bind = op.get_bind()
    metadata.drop_all(bind=bind)
    bind.execute(text("DROP FUNCTION IF EXISTS work_frontier_reject_mutation()"))
    bind.execute(text(f"DROP ROLE IF EXISTS {_APP_ROLE}"))
