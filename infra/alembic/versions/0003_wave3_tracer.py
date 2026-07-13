"""Add atomic decision-cycle, identity, and Wave-3 tracer persistence.

Revision ID: 0003_wave3_tracer
Revises: 0002_platform_core
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_wave3_tracer"
down_revision = "0002_platform_core"
branch_labels = None
depends_on = None

_ID_LENGTH = 64
_HASH_LENGTH = 64
_APP_ROLE = "work_frontier_app"
_NEW_WORKSPACE_TABLES = (
    "decision_cycles",
    "workspace_frontiers",
    "source_cursors",
    "sessions",
    "local_identities",
    "role_grants",
    "credential_envelopes",
)


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {
        str(column["name"])
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def _add_column_if_missing(table_name: str, column: sa.Column[object]) -> None:
    if column.name not in _column_names(table_name):
        op.add_column(table_name, column)


def _workspace_columns() -> tuple[sa.Column[str], sa.Column[str]]:
    return (
        sa.Column("tenant_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("workspace_id", sa.String(_ID_LENGTH), nullable=False),
    )


def _workspace_fk(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", "workspace_id"],
        ["workspaces.tenant_id", "workspaces.workspace_id"],
        name=name,
        ondelete="CASCADE",
    )


def _create_wave3_tables() -> None:
    tables = _table_names()
    if "decision_cycles" not in tables:
        op.create_table(
            "decision_cycles",
            *_workspace_columns(),
            sa.Column("cycle_id", sa.String(_ID_LENGTH), nullable=False),
            sa.Column("snapshot_id", sa.String(_ID_LENGTH), nullable=False),
            sa.Column("snapshot_hash", sa.String(_HASH_LENGTH), nullable=False),
            sa.Column("graph_revision", sa.String(_ID_LENGTH), nullable=False),
            sa.Column("policy_bundle_hash", sa.String(_HASH_LENGTH), nullable=False),
            sa.Column("source_revision", sa.String(256), nullable=False),
            sa.Column("decision_set_hash", sa.String(_HASH_LENGTH), nullable=False),
            sa.Column("recommended_item_id", sa.String(_ID_LENGTH)),
            _workspace_fk("fk_decision_cycles_workspace"),
            sa.PrimaryKeyConstraint(
                "tenant_id", "workspace_id", "cycle_id"
            ),
        )
    if "workspace_frontiers" not in tables:
        op.create_table(
            "workspace_frontiers",
            *_workspace_columns(),
            sa.Column("active_cycle_id", sa.String(_ID_LENGTH), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            _workspace_fk("fk_workspace_frontiers_workspace"),
            sa.PrimaryKeyConstraint("tenant_id", "workspace_id"),
        )
    if "source_cursors" not in tables:
        op.create_table(
            "source_cursors",
            *_workspace_columns(),
            sa.Column("connection_id", sa.String(_ID_LENGTH), nullable=False),
            sa.Column("revision", sa.String(256), nullable=False),
            _workspace_fk("fk_source_cursors_workspace"),
            sa.PrimaryKeyConstraint(
                "tenant_id", "workspace_id", "connection_id"
            ),
        )
    if "local_identities" not in tables:
        op.create_table(
            "local_identities",
            *_workspace_columns(),
            sa.Column("actor_id", sa.String(_ID_LENGTH), nullable=False),
            sa.Column("username", sa.String(256), nullable=False),
            sa.Column("password_salt_b64", sa.Text(), nullable=False),
            sa.Column("password_verifier_b64", sa.Text(), nullable=False),
            sa.Column("mfa_credential_id", sa.String(_ID_LENGTH)),
            sa.Column("role_revision", sa.Integer(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            _workspace_fk("fk_local_identities_workspace"),
            sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "actor_id"),
            sa.UniqueConstraint(
                "tenant_id",
                "workspace_id",
                "username",
                name="uq_local_identity_username_scope",
            ),
        )
    if "sessions" not in tables:
        op.create_table(
            "sessions",
            *_workspace_columns(),
            sa.Column("session_id", sa.String(_ID_LENGTH), nullable=False),
            sa.Column("actor_id", sa.String(_ID_LENGTH), nullable=False),
            sa.Column("token_hash", sa.String(_HASH_LENGTH), nullable=False),
            sa.Column("scope", JSONB(), nullable=False),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True)),
            sa.Column("role_revision", sa.Integer(), nullable=False),
            _workspace_fk("fk_sessions_workspace"),
            sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "session_id"),
            sa.UniqueConstraint(
                "tenant_id",
                "workspace_id",
                "token_hash",
                name="uq_session_token_hash_scope",
            ),
        )
    if "role_grants" not in tables:
        op.create_table(
            "role_grants",
            *_workspace_columns(),
            sa.Column("grant_id", sa.String(_ID_LENGTH), nullable=False),
            sa.Column("actor_id", sa.String(_ID_LENGTH), nullable=False),
            sa.Column("role", sa.String(64), nullable=False),
            sa.Column("scope", JSONB(), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            _workspace_fk("fk_role_grants_workspace"),
            sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "grant_id"),
        )
    if "credential_envelopes" not in tables:
        op.create_table(
            "credential_envelopes",
            *_workspace_columns(),
            sa.Column("credential_id", sa.String(_ID_LENGTH), nullable=False),
            sa.Column("key_id", sa.String(_ID_LENGTH), nullable=False),
            sa.Column("nonce_b64", sa.Text(), nullable=False),
            sa.Column("ciphertext_b64", sa.Text(), nullable=False),
            sa.Column("associated_data_b64", sa.Text(), nullable=False),
            sa.Column("fingerprint", sa.String(_HASH_LENGTH), nullable=False),
            _workspace_fk("fk_credential_envelopes_workspace"),
            sa.PrimaryKeyConstraint(
                "tenant_id", "workspace_id", "credential_id"
            ),
        )


def _add_wave3_columns() -> None:
    zero_hash = "0" * _HASH_LENGTH
    _add_column_if_missing(
        "source_item_versions",
        sa.Column(
            "connection_id",
            sa.String(_ID_LENGTH),
            nullable=False,
            server_default="legacy-connection",
        ),
    )
    _add_column_if_missing(
        "source_item_versions",
        sa.Column(
            "payload_hash",
            sa.String(_HASH_LENGTH),
            nullable=False,
            server_default=zero_hash,
        ),
    )
    _add_column_if_missing(
        "decision_records",
        sa.Column(
            "cycle_id",
            sa.String(_ID_LENGTH),
            nullable=False,
            server_default="legacy-cycle",
        ),
    )
    for name, type_, default in (
        ("cycle_id", sa.String(_ID_LENGTH), "legacy-cycle"),
        ("source_snapshot_hash", sa.String(_HASH_LENGTH), zero_hash),
        ("graph_revision", sa.String(_ID_LENGTH), "legacy-graph"),
        ("policy_bundle_hash", sa.String(_HASH_LENGTH), zero_hash),
    ):
        _add_column_if_missing(
            "current_projections",
            sa.Column(name, type_, nullable=False, server_default=default),
        )


def _apply_rls_and_grants() -> None:
    bind = op.get_bind()
    expression = (
        "tenant_id = current_setting('work_frontier.tenant_id', true) "
        "AND workspace_id = current_setting('work_frontier.workspace_id', true)"
    )
    for table in _NEW_WORKSPACE_TABLES:
        policy = f"workspace_isolation_{table}"
        bind.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        bind.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        bind.execute(
            sa.text(
                f"""
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE schemaname = 'public'
                      AND tablename = '{table}'
                      AND policyname = '{policy}'
                  ) THEN
                    CREATE POLICY "{policy}" ON "{table}"
                    USING ({expression}) WITH CHECK ({expression});
                  END IF;
                END
                $$;
                """
            )
        )
        bind.execute(
            sa.text(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{table}" '
                f"TO {_APP_ROLE}"
            )
        )
    bind.execute(
        sa.text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'reject_mutation_decision_cycles'
              ) THEN
                CREATE TRIGGER reject_mutation_decision_cycles
                BEFORE UPDATE OR DELETE ON decision_cycles
                FOR EACH ROW EXECUTE FUNCTION work_frontier_reject_mutation();
              END IF;
            END
            $$;
            """
        )
    )


def upgrade() -> None:
    """Add upgrade-safe Wave-3 tables, columns, RLS, and immutability."""
    _create_wave3_tables()
    _add_wave3_columns()
    _apply_rls_and_grants()


def downgrade() -> None:
    """Remove the Wave-3 persistence surface in reverse dependency order."""
    op.drop_column("current_projections", "policy_bundle_hash")
    op.drop_column("current_projections", "graph_revision")
    op.drop_column("current_projections", "source_snapshot_hash")
    op.drop_column("current_projections", "cycle_id")
    op.drop_column("decision_records", "cycle_id")
    op.drop_column("source_item_versions", "payload_hash")
    op.drop_column("source_item_versions", "connection_id")
    for table in reversed(_NEW_WORKSPACE_TABLES):
        op.drop_table(table)
