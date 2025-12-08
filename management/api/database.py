"""
Database setup using SQLAlchemy 2.0 with async support.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event, text
from typing import AsyncGenerator
import logging

from api.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Secondary engine for n8n database (read-only)
n8n_engine = create_async_engine(
    settings.n8n_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=5,
)

n8n_session_maker = async_sessionmaker(
    n8n_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_n8n_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting n8n database session (read-only)."""
    async with n8n_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database - create tables if they don't exist."""
    logger.info("Initializing database...")

    async with engine.begin() as conn:
        # Import all models to ensure they're registered
        from api.models import auth, settings as settings_models, notifications, backups, email, audit

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized successfully")


async def close_db() -> None:
    """Close database connections."""
    logger.info("Closing database connections...")
    await engine.dispose()
    await n8n_engine.dispose()
    logger.info("Database connections closed")


async def check_db_connection() -> bool:
    """Check if database is accessible."""
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
