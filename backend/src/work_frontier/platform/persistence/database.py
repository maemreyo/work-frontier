"""Async SQLAlchemy engine/session utilities with mandatory workspace context."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from work_frontier.platform.persistence.scope import WorkspaceScope

APP_DATABASE_ROLE = "work_frontier_app"


def create_engine(database_url: str) -> AsyncEngine:
    """Create the production async engine without implicit workspace state."""
    if not database_url.startswith("postgresql+"):
        raise ValueError("Work Frontier persistence requires PostgreSQL")
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create non-expiring async sessions for transaction-scoped repositories."""
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def workspace_session(
    factory: async_sessionmaker[AsyncSession],
    scope: WorkspaceScope,
) -> AsyncGenerator[AsyncSession]:
    """Open one transaction, assume the app role, and set mandatory local scope."""
    async with factory() as session, session.begin():
        _ = await session.execute(text("SET LOCAL ROLE work_frontier_app"))
        _ = await session.execute(
            text("SELECT set_config('work_frontier.tenant_id', :value, true)"),
            {"value": scope.tenant_id},
        )
        _ = await session.execute(
            text("SELECT set_config('work_frontier.workspace_id', :value, true)"),
            {"value": scope.workspace_id},
        )
        yield session
