"""
Database initialization and table creation helpers.
"""

from backend.db.base import Base
from backend.db.models import *  # noqa: F401, F403
from backend.db.session import async_engine, sync_engine


async def init_async_db() -> None:
    """Creates all database tables asynchronously."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_sync_db() -> None:
    """Creates all database tables synchronously."""
    Base.metadata.create_all(bind=sync_engine)


async def drop_async_db() -> None:
    """Drops all database tables asynchronously (used in tests)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def drop_sync_db() -> None:
    """Drops all database tables synchronously (used in tests)."""
    Base.metadata.drop_all(bind=sync_engine)
