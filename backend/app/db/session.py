"""One asynchronous database session per request or task."""

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


@lru_cache
def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=10
    )
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    # Internal table-export reads share one read-only snapshot across pages.
    export_session = request.scope.get("state", {}).get("_table_export_read_session")
    if export_session is not None:
        yield export_session
        return
    async with session_factory()() as session:
        yield session
        if session.in_transaction():
            await session.rollback()
