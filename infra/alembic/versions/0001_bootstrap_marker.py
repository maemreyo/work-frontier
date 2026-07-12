"""Create the bootstrap migration marker.

Revision ID: 0001_bootstrap_marker
Revises:
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_bootstrap_marker"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the baseline migration marker."""
    op.create_table(
        "bootstrap_markers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(length=128), nullable=False),
    )


def downgrade() -> None:
    """Remove the baseline migration marker."""
    op.drop_table("bootstrap_markers")
