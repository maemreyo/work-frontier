"""Async tenant-scoped SQLAlchemy repositories with no bare-ID methods."""

from __future__ import annotations

from collections.abc import Mapping

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from work_frontier.platform.persistence.scope import (
    ScopedResourceId,
    workspace_predicate,
)


class ScopedRepository:
    """Generic defense-in-depth repository for one scoped SQLAlchemy table."""

    __slots__: tuple[str, ...] = ("_id_column", "_session", "_table")
    _session: AsyncSession
    _table: sa.Table
    _id_column: str

    def __init__(
        self,
        session: AsyncSession,
        table: sa.Table,
        id_column: str,
    ) -> None:
        """Bind the repository to one session and scoped table."""
        if id_column not in table.c:
            raise ValueError(f"unknown ID column: {id_column}")
        self._session = session
        self._table = table
        self._id_column = id_column

    async def get(self, key: ScopedResourceId) -> Mapping[str, object] | None:
        """Resolve exactly one resource inside the supplied scope."""
        statement = sa.select(self._table).where(
            workspace_predicate(self._table, key.scope),
            self._table.c[self._id_column] == key.resource_id,
        )
        row = (await self._session.execute(statement)).mappings().first()
        return None if row is None else dict(row)

    async def insert(
        self,
        key: ScopedResourceId,
        values: Mapping[str, object],
    ) -> Mapping[str, object]:
        """Insert one resource while overriding any untrusted scope values."""
        payload = {
            **values,
            "tenant_id": key.scope.tenant_id,
            "workspace_id": key.scope.workspace_id,
            self._id_column: key.resource_id,
        }
        statement = sa.insert(self._table).values(**payload).returning(self._table)
        row = (await self._session.execute(statement)).mappings().one()
        return dict(row)
