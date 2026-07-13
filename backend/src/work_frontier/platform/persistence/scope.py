"""Mandatory tenant/workspace scope value objects and SQL predicates."""

from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa


@dataclass(frozen=True, slots=True)
class WorkspaceScope:
    """Explicit data-isolation scope required by every repository operation."""

    tenant_id: str
    workspace_id: str

    def __post_init__(self) -> None:
        """Reject absent or blank scope dimensions."""
        if not self.tenant_id.strip() or not self.workspace_id.strip():
            msg = "tenant_id and workspace_id are required"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ScopedResourceId:
    """Resource identity that cannot exist without its isolation scope."""

    scope: WorkspaceScope
    resource_id: str

    def __post_init__(self) -> None:
        """Reject blank resource identities."""
        if not self.resource_id.strip():
            msg = "resource_id is required"
            raise ValueError(msg)


def workspace_predicate(
    table: sa.Table, scope: WorkspaceScope
) -> sa.ColumnElement[bool]:
    """Return defense-in-depth tenant and workspace SQL predicates."""
    return sa.and_(
        table.c.tenant_id == scope.tenant_id,
        table.c.workspace_id == scope.workspace_id,
    )
