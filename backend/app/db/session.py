"""One asynchronous database session per request or task."""

from collections.abc import AsyncIterator
from functools import lru_cache
from os import getenv

from fastapi import Request
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


@lru_cache
def session_factory() -> async_sessionmaker[AsyncSession]:
    database_url = settings().database_url
    options = make_url(database_url).query.get("options") or getenv("PGOPTIONS", "")
    if isinstance(options, tuple):
        options = " ".join(options)
    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        # Interactive scoped searches can trigger seconds of JIT compilation
        # for milliseconds of actual work. Apply this only to our connections;
        # PostgreSQL's server defaults and other clients remain unchanged.
        connect_args={"options": f"{options} -c jit=off".strip()},
    )
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    # Internal table-export reads share one read-only snapshot across pages.
    export_session = request.scope.get("state", {}).get("_table_export_read_session")
    if export_session is not None:
        yield export_session
        return
    async with session_factory()() as session:
        # Only fresh, ordinary GET Performance reads may release their connection
        # after retaining primitive source facts. Mutation tasks and internal
        # table-export snapshots never receive this marker.
        session.info["performance_read_api"] = request.method == "GET" and any(
            request.url.path == path or request.url.path.startswith(path + "/")
            for path in ("/api/v1/dashboard", "/api/v1/performance", "/api/v1/reports")
        )
        yield session
        if session.in_transaction():
            await session.rollback()
