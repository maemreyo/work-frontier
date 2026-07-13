"""Add writer, approval, coordination, emergency, and retention persistence.

Revision ID: 0004_wave4_control_plane
Revises: 0003_wave3_tracer
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_wave4_control_plane"
down_revision = "0003_wave3_tracer"
branch_labels = None
depends_on = None

_ID_LENGTH = 64
_HASH_LENGTH = 64
_APP_ROLE = "work_frontier_app"
_NEW_TABLES = (
    "writer_states",
    "writer_leases",
    "shadow_comparisons",
    "proposed_changes",
    "proposal_dispositions",
    "approval_records",
    "break_glass_grants",
    "break_glass_reviews",
    "retention_jobs",
    "retention_proofs",
)
_APPEND_ONLY = (
    "shadow_comparisons",
    "proposed_changes",
    "proposal_dispositions",
    "approval_records",
    "break_glass_grants",
    "break_glass_reviews",
    "retention_proofs",
)


def _scope_columns() -> tuple[sa.Column[str], sa.Column[str]]:
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


def _create_tables() -> None:
    op.create_table(
        "writer_states",
        *_scope_columns(),
        sa.Column("writer_state_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("active_writer", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _workspace_fk("fk_writer_states_workspace"),
        sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "writer_state_id"),
        sa.UniqueConstraint("tenant_id", "workspace_id", name="uq_writer_state_scope"),
    )
    op.create_table(
        "writer_leases",
        *_scope_columns(),
        sa.Column("writer_lease_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("owner", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        _workspace_fk("fk_writer_leases_workspace"),
        sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "writer_lease_id"),
    )
    op.create_table(
        "shadow_comparisons",
        *_scope_columns(),
        sa.Column("comparison_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("source_revision", sa.String(256), nullable=False),
        sa.Column("local_version", sa.Integer(), nullable=False),
        sa.Column("semantic_equal", sa.Boolean(), nullable=False),
        sa.Column("payload_hash", sa.String(_HASH_LENGTH), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _workspace_fk("fk_shadow_comparisons_workspace"),
        sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "comparison_id"),
    )
    op.create_table(
        "proposed_changes",
        *_scope_columns(),
        sa.Column("proposal_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("item_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("proposer", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("base_decision_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("expected_source_revision", sa.String(256), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _workspace_fk("fk_proposed_changes_workspace"),
        sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "proposal_id"),
    )
    op.create_table(
        "proposal_dispositions",
        *_scope_columns(),
        sa.Column("disposition_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("proposal_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("actor_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _workspace_fk("fk_proposal_dispositions_workspace"),
        sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "disposition_id"),
    )
    op.create_table(
        "approval_records",
        *_scope_columns(),
        sa.Column("approval_record_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("proposal_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("approver", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("decision_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("source_revision", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _workspace_fk("fk_approval_records_workspace"),
        sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "approval_record_id"),
    )
    op.create_table(
        "break_glass_grants",
        *_scope_columns(),
        sa.Column("grant_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("actor_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("permission", sa.String(128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=False),
        _workspace_fk("fk_break_glass_grants_workspace"),
        sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "grant_id"),
    )
    op.create_table(
        "break_glass_reviews",
        *_scope_columns(),
        sa.Column("review_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("grant_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("reviewer", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        _workspace_fk("fk_break_glass_reviews_workspace"),
        sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "review_id"),
    )
    op.create_table(
        "retention_jobs",
        *_scope_columns(),
        sa.Column("retention_job_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("policy_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        _workspace_fk("fk_retention_jobs_workspace"),
        sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "retention_job_id"),
    )
    op.create_table(
        "retention_proofs",
        *_scope_columns(),
        sa.Column("retention_proof_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("retention_job_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("policy_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("subject_fingerprint", sa.String(_HASH_LENGTH), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _workspace_fk("fk_retention_proofs_workspace"),
        sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "retention_proof_id"),
    )


def _alter_coordination_tables() -> None:
    for name, type_, default in (
        ("mode", sa.String(32), "exclusive"),
        ("state", sa.String(32), "active"),
        ("decision_id", sa.String(_ID_LENGTH), "legacy-decision"),
        ("collaborators", JSONB(), "[]"),
        ("heartbeat_at", sa.DateTime(timezone=True), sa.text("CURRENT_TIMESTAMP")),
        ("handoff_to", sa.String(_ID_LENGTH), None),
    ):
        op.add_column(
            "work_leases",
            sa.Column(name, type_, nullable=default is None, server_default=default),
        )
    for name, type_, default in (
        ("severity", sa.String(32), "warning"),
        ("opened_at", sa.DateTime(timezone=True), sa.text("CURRENT_TIMESTAMP")),
        ("resolved_at", sa.DateTime(timezone=True), None),
        ("resolution", sa.Text(), None),
    ):
        op.add_column(
            "attention_items",
            sa.Column(name, type_, nullable=default is None, server_default=default),
        )


def _apply_rls_and_immutability() -> None:
    bind = op.get_bind()
    expression = (
        "tenant_id = current_setting('work_frontier.tenant_id', true) "
        "AND workspace_id = current_setting('work_frontier.workspace_id', true)"
    )
    for table in _NEW_TABLES:
        policy = f"workspace_isolation_{table}"
        bind.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        bind.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        bind.execute(
            sa.text(
                f'CREATE POLICY "{policy}" ON "{table}" '
                f"USING ({expression}) WITH CHECK ({expression})"
            )
        )
        bind.execute(
            sa.text(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{table}" '
                f"TO {_APP_ROLE}"
            )
        )
    for table in _APPEND_ONLY:
        bind.execute(
            sa.text(
                f'CREATE TRIGGER "reject_mutation_{table}" '
                f'BEFORE UPDATE OR DELETE ON "{table}" '
                "FOR EACH ROW EXECUTE FUNCTION work_frontier_reject_mutation()"
            )
        )


def upgrade() -> None:
    """Create Wave-4 persistence and coordination columns."""
    _create_tables()
    _alter_coordination_tables()
    _apply_rls_and_immutability()


def downgrade() -> None:
    """Remove Wave-4 persistence in reverse dependency order."""
    for column in ("resolution", "resolved_at", "opened_at", "severity"):
        op.drop_column("attention_items", column)
    for column in (
        "handoff_to",
        "heartbeat_at",
        "collaborators",
        "decision_id",
        "state",
        "mode",
    ):
        op.drop_column("work_leases", column)
    for table in reversed(_NEW_TABLES):
        op.drop_table(table)
