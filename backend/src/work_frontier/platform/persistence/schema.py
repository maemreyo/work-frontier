"""SQLAlchemy 2 metadata for tenant-scoped operational persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from sqlalchemy.sql.schema import SchemaItem

metadata = sa.MetaData()
_JSON = sa.JSON().with_variant(JSONB(), "postgresql")
_ID_LENGTH: Final = 64
_HASH_LENGTH: Final = 64


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


tenants = sa.Table(
    "tenants",
    metadata,
    sa.Column("tenant_id", sa.String(_ID_LENGTH), primary_key=True),
    sa.Column("name", sa.String(200), nullable=False),
)

organizations = sa.Table(
    "organizations",
    metadata,
    sa.Column("tenant_id", sa.String(_ID_LENGTH), primary_key=True),
    sa.Column("organization_id", sa.String(_ID_LENGTH), primary_key=True),
    sa.Column("name", sa.String(200), nullable=False),
    sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
)

workspaces = sa.Table(
    "workspaces",
    metadata,
    sa.Column("tenant_id", sa.String(_ID_LENGTH), primary_key=True),
    sa.Column("workspace_id", sa.String(_ID_LENGTH), primary_key=True),
    sa.Column("organization_id", sa.String(_ID_LENGTH), nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.ForeignKeyConstraint(
        ["tenant_id", "organization_id"],
        ["organizations.tenant_id", "organizations.organization_id"],
        ondelete="CASCADE",
    ),
    info={"workspace_scoped": True},
)


def _workspace_entity(
    name: str,
    id_name: str,
    *,
    append_only: bool = False,
    extra_columns: tuple[SchemaItem, ...] = (),
    constraints: tuple[sa.Constraint, ...] = (),
) -> sa.Table:
    tenant_id, workspace_id = _scope_columns()
    return sa.Table(
        name,
        metadata,
        tenant_id,
        workspace_id,
        sa.Column(id_name, sa.String(_ID_LENGTH), nullable=False),
        *extra_columns,
        _workspace_fk(f"fk_{name}_workspace"),
        sa.PrimaryKeyConstraint("tenant_id", "workspace_id", id_name),
        *constraints,
        info={"append_only": append_only, "workspace_scoped": True},
    )


programs = _workspace_entity(
    "programs",
    "program_id",
    extra_columns=(
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ),
)

work_items = _workspace_entity(
    "work_items",
    "item_id",
    extra_columns=(
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("lifecycle", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", _JSON, nullable=False, server_default=sa.text("'{}'")),
    ),
)

source_item_versions = _workspace_entity(
    "source_item_versions",
    "source_version_id",
    append_only=True,
    extra_columns=(
        sa.Column("connection_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("item_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("source_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("revision", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
        sa.Column("payload_hash", sa.String(_HASH_LENGTH), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "workspace_id", "item_id"],
            ["work_items.tenant_id", "work_items.workspace_id", "work_items.item_id"],
            ondelete="CASCADE",
        ),
    ),
    constraints=(
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "source_id",
            "revision",
            name="uq_source_revision_scope",
        ),
    ),
)

normalized_snapshots = _workspace_entity(
    "normalized_snapshots",
    "snapshot_id",
    append_only=True,
    extra_columns=(
        sa.Column("content_hash", sa.String(_HASH_LENGTH), nullable=False),
        sa.Column("source_revision_set", _JSON, nullable=False),
        sa.Column("graph_revision", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("profile_version", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
    ),
    constraints=(
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "content_hash",
            name="uq_snapshot_hash_scope",
        ),
    ),
)

edges = _workspace_entity(
    "edges",
    "edge_id",
    extra_columns=(
        sa.Column("edge_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("target_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("payload", _JSON, nullable=False, server_default=sa.text("'{}'")),
    ),
)

policy_bundles = _workspace_entity(
    "policy_bundles",
    "policy_bundle_id",
    append_only=True,
    extra_columns=(
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("content_hash", sa.String(_HASH_LENGTH), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
    ),
)

decision_records = _workspace_entity(
    "decision_records",
    "decision_id",
    append_only=True,
    extra_columns=(
        sa.Column("cycle_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("item_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
        sa.Column("payload_hash", sa.String(_HASH_LENGTH), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "workspace_id", "item_id"],
            ["work_items.tenant_id", "work_items.workspace_id", "work_items.item_id"],
            ondelete="CASCADE",
        ),
    ),
)

current_projections = _workspace_entity(
    "current_projections",
    "item_id",
    extra_columns=(
        sa.Column("cycle_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("derived_from_decision_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("source_snapshot_hash", sa.String(_HASH_LENGTH), nullable=False),
        sa.Column("graph_revision", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("policy_bundle_hash", sa.String(_HASH_LENGTH), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "workspace_id", "derived_from_decision_id"],
            [
                "decision_records.tenant_id",
                "decision_records.workspace_id",
                "decision_records.decision_id",
            ],
            ondelete="CASCADE",
        ),
    ),
)

gates = _workspace_entity(
    "gates",
    "gate_id",
    extra_columns=(
        sa.Column("item_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("gate_type", sa.String(32), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
    ),
)

evidence_records = _workspace_entity(
    "evidence_records",
    "evidence_id",
    append_only=True,
    extra_columns=(
        sa.Column("gate_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("item_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("revision", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
        sa.Column("payload_hash", sa.String(_HASH_LENGTH), nullable=False),
    ),
)

approvals = _workspace_entity(
    "approvals",
    "approval_id",
    append_only=True,
    extra_columns=(
        sa.Column("item_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("actor_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
    ),
)

overrides = _workspace_entity(
    "overrides",
    "override_id",
    append_only=True,
    extra_columns=(
        sa.Column("item_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("actor_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
    ),
)

work_leases = _workspace_entity(
    "work_leases",
    "lease_id",
    extra_columns=(
        sa.Column("item_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("lease_owner", sa.String(_ID_LENGTH), nullable=False),
        sa.Column(
            "collaborators", _JSON, nullable=False, server_default=sa.text("'[]'")
        ),
        sa.Column("mode", sa.String(32), nullable=False, server_default="exclusive"),
        sa.Column("state", sa.String(32), nullable=False, server_default="active"),
        sa.Column("decision_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("handoff_to", sa.String(_ID_LENGTH)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ),
)

attention_items = _workspace_entity(
    "attention_items",
    "attention_id",
    extra_columns=(
        sa.Column("item_id", sa.String(_ID_LENGTH)),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("deterministic_basis", sa.Text(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolution", sa.Text()),
    ),
)

connections = _workspace_entity(
    "connections",
    "connection_id",
    extra_columns=(
        sa.Column("connection_type", sa.String(64), nullable=False),
        sa.Column("credential_reference", sa.String(256), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
    ),
)

webhook_inbox = _workspace_entity(
    "webhook_inbox",
    "delivery_id",
    extra_columns=(
        sa.Column("payload_hash", sa.String(_HASH_LENGTH), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
    ),
)

transactional_outbox = _workspace_entity(
    "transactional_outbox",
    "outbox_id",
    extra_columns=(
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
    ),
    constraints=(
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "idempotency_key",
            name="uq_outbox_idempotency_scope",
        ),
    ),
)

job_queue = _workspace_entity(
    "job_queue",
    "job_id",
    extra_columns=(
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
        sa.Column("result", _JSON),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dead_letter_reason", sa.Text()),
        sa.Column("replay_of", sa.String(_ID_LENGTH)),
        sa.Column(
            "attempt_history", _JSON, nullable=False, server_default=sa.text("'[]'")
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ),
    constraints=(
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "idempotency_key",
            name="uq_job_idempotency_scope",
        ),
    ),
)

audit_segments = _workspace_entity(
    "audit_segments",
    "segment_id",
    extra_columns=(
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("final_checksum", sa.String(_HASH_LENGTH)),
        sa.Column("external_anchor", _JSON),
    ),
)

audit_events = sa.Table(
    "audit_events",
    metadata,
    *_scope_columns(),
    sa.Column("segment_id", sa.String(_ID_LENGTH), nullable=False),
    sa.Column("seq", sa.Integer(), nullable=False),
    sa.Column("event_id", sa.String(_ID_LENGTH), nullable=False),
    sa.Column("event_type", sa.String(64), nullable=False),
    sa.Column("actor", sa.String(256), nullable=False),
    sa.Column("subject_id", sa.String(_ID_LENGTH)),
    sa.Column("causation_id", sa.String(_ID_LENGTH), nullable=False),
    sa.Column("correlation_id", sa.String(_ID_LENGTH), nullable=False),
    sa.Column("payload", _JSON, nullable=False),
    sa.Column("payload_hash", sa.String(_HASH_LENGTH), nullable=False),
    sa.Column("previous_checksum", sa.String(_HASH_LENGTH), nullable=False),
    sa.Column("checksum", sa.String(_HASH_LENGTH), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    _workspace_fk("fk_audit_events_workspace"),
    sa.ForeignKeyConstraint(
        ["tenant_id", "workspace_id", "segment_id"],
        [
            "audit_segments.tenant_id",
            "audit_segments.workspace_id",
            "audit_segments.segment_id",
        ],
        ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("tenant_id", "workspace_id", "segment_id", "seq"),
    sa.UniqueConstraint(
        "tenant_id",
        "workspace_id",
        "event_id",
        name="uq_audit_event_scope",
    ),
    info={"append_only": True, "workspace_scoped": True},
)

scheduler_leases = _workspace_entity(
    "scheduler_leases",
    "schedule_key",
    extra_columns=(
        sa.Column("lease_owner", sa.String(128), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ),
)

decision_cycles = _workspace_entity(
    "decision_cycles",
    "cycle_id",
    append_only=True,
    extra_columns=(
        sa.Column("snapshot_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("snapshot_hash", sa.String(_HASH_LENGTH), nullable=False),
        sa.Column("graph_revision", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("policy_bundle_hash", sa.String(_HASH_LENGTH), nullable=False),
        sa.Column("source_revision", sa.String(256), nullable=False),
        sa.Column("decision_set_hash", sa.String(_HASH_LENGTH), nullable=False),
        sa.Column("recommended_item_id", sa.String(_ID_LENGTH)),
    ),
)

workspace_frontiers = sa.Table(
    "workspace_frontiers",
    metadata,
    *_scope_columns(),
    sa.Column("active_cycle_id", sa.String(_ID_LENGTH), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    _workspace_fk("fk_workspace_frontiers_workspace"),
    sa.PrimaryKeyConstraint("tenant_id", "workspace_id"),
    info={"workspace_scoped": True},
)

source_cursors = _workspace_entity(
    "source_cursors",
    "connection_id",
    extra_columns=(sa.Column("revision", sa.String(256), nullable=False),),
)

local_identities = _workspace_entity(
    "local_identities",
    "actor_id",
    extra_columns=(
        sa.Column("username", sa.String(256), nullable=False),
        sa.Column("password_salt_b64", sa.Text(), nullable=False),
        sa.Column("password_verifier_b64", sa.Text(), nullable=False),
        sa.Column("mfa_credential_id", sa.String(_ID_LENGTH)),
        sa.Column("role_revision", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    ),
    constraints=(
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "username",
            name="uq_local_identity_username_scope",
        ),
    ),
)

sessions = _workspace_entity(
    "sessions",
    "session_id",
    extra_columns=(
        sa.Column("actor_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("token_hash", sa.String(_HASH_LENGTH), nullable=False),
        sa.Column("scope", _JSON, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("role_revision", sa.Integer(), nullable=False),
    ),
    constraints=(
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "token_hash",
            name="uq_session_token_hash_scope",
        ),
    ),
)

role_grants = _workspace_entity(
    "role_grants",
    "grant_id",
    extra_columns=(
        sa.Column("actor_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("scope", _JSON, nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
    ),
)

credential_envelopes = _workspace_entity(
    "credential_envelopes",
    "credential_id",
    extra_columns=(
        sa.Column("key_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("nonce_b64", sa.Text(), nullable=False),
        sa.Column("ciphertext_b64", sa.Text(), nullable=False),
        sa.Column("associated_data_b64", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(_HASH_LENGTH), nullable=False),
    ),
)

writer_states = _workspace_entity(
    "writer_states",
    "writer_state_id",
    extra_columns=(
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("active_writer", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ),
    constraints=(
        sa.UniqueConstraint("tenant_id", "workspace_id", name="uq_writer_state_scope"),
    ),
)

writer_leases = _workspace_entity(
    "writer_leases",
    "writer_lease_id",
    extra_columns=(
        sa.Column("owner", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    ),
)

shadow_comparisons = _workspace_entity(
    "shadow_comparisons",
    "comparison_id",
    append_only=True,
    extra_columns=(
        sa.Column("source_revision", sa.String(256), nullable=False),
        sa.Column("local_version", sa.Integer(), nullable=False),
        sa.Column("semantic_equal", sa.Boolean(), nullable=False),
        sa.Column("payload_hash", sa.String(_HASH_LENGTH), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ),
)

proposed_changes = _workspace_entity(
    "proposed_changes",
    "proposal_id",
    append_only=True,
    extra_columns=(
        sa.Column("item_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("proposer", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("base_decision_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("expected_source_revision", sa.String(256), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ),
)

proposal_dispositions = _workspace_entity(
    "proposal_dispositions",
    "disposition_id",
    append_only=True,
    extra_columns=(
        sa.Column("proposal_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("actor_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ),
)

approval_records = _workspace_entity(
    "approval_records",
    "approval_record_id",
    append_only=True,
    extra_columns=(
        sa.Column("proposal_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("approver", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("decision_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("source_revision", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ),
)

break_glass_grants = _workspace_entity(
    "break_glass_grants",
    "grant_id",
    append_only=True,
    extra_columns=(
        sa.Column("actor_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("permission", sa.String(128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=False),
    ),
)

break_glass_reviews = _workspace_entity(
    "break_glass_reviews",
    "review_id",
    append_only=True,
    extra_columns=(
        sa.Column("grant_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("reviewer", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
    ),
)

retention_jobs = _workspace_entity(
    "retention_jobs",
    "retention_job_id",
    extra_columns=(
        sa.Column("policy_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    ),
)

retention_proofs = _workspace_entity(
    "retention_proofs",
    "retention_proof_id",
    append_only=True,
    extra_columns=(
        sa.Column("retention_job_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("policy_id", sa.String(_ID_LENGTH), nullable=False),
        sa.Column("subject_fingerprint", sa.String(_HASH_LENGTH), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ),
)

WORKSPACE_TABLES: Final = tuple(
    table for table in metadata.tables.values() if table.info.get("workspace_scoped")
)
APPEND_ONLY_TABLES: Final = tuple(
    table for table in metadata.tables.values() if table.info.get("append_only")
)
