"""
Async SQLAlchemy database engine, session management, and initialization.
Uses asyncpg as the PostgreSQL driver for full async support.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Async Engine ───────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# ── Session Factory ────────────────────────────────────────────────────
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Declarative Base ───────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# ── Dependency Injection ───────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.
    Automatically commits on success and rolls back on exception.

    Usage:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions outside of FastAPI routes.
    Used in background tasks, agent pipelines, etc.

    Usage:
        async with get_db_context() as db:
            result = await db.execute(query)
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Database Initialization ────────────────────────────────────────────
async def init_db() -> None:
    """
    Create all database tables from ORM models.
    Called during application startup via the lifespan handler.
    """
    # Import models so they register with Base.metadata
    import models.incident  # noqa: F401
    import models.app_target  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")


async def check_db_health() -> bool:
    """
    Verify database connectivity with a simple query.
    Used by the health check endpoint.
    """
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def close_db() -> None:
    """
    Dispose of the engine connection pool.
    Called during application shutdown.
    """
    await engine.dispose()
    logger.info("Database connections closed")
