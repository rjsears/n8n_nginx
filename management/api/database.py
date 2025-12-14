"""
Database setup using SQLAlchemy 2.0 with async support.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event, text
from typing import AsyncGenerator
from urllib.parse import urlparse, urlunparse, quote
import logging

from api.config import settings

logger = logging.getLogger(__name__)


def encode_database_url(url: str) -> str:
    """
    URL-encode the password in a database URL to handle special characters.
    Example: postgresql+asyncpg://user:p@ss!word@host:5432/db
    becomes: postgresql+asyncpg://user:p%40ss%21word@host:5432/db
    """
    try:
        parsed = urlparse(url)
        if parsed.password:
            # URL-encode the password (safe='' means encode everything except alphanumerics)
            encoded_password = quote(parsed.password, safe='')
            # Reconstruct the netloc with encoded password
            if parsed.port:
                netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}:{parsed.port}"
            else:
                netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}"
            # Rebuild the URL
            return urlunparse((
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
        return url
    except Exception as e:
        logger.warning(f"Failed to encode database URL: {e}, using original")
        return url


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Create async engine with URL-encoded credentials
_encoded_db_url = encode_database_url(settings.database_url)
logger.info(f"Connecting to management database at: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'configured host'}")
engine = create_async_engine(
    _encoded_db_url,
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

# Secondary engine for n8n database (read-only) with URL-encoded credentials
_encoded_n8n_url = encode_database_url(settings.n8n_database_url)
logger.info(f"Connecting to n8n database at: {settings.n8n_database_url.split('@')[-1] if '@' in settings.n8n_database_url else 'configured host'}")
n8n_engine = create_async_engine(
    _encoded_n8n_url,
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
        from api.models import auth, settings as settings_models, notifications, backups, email, audit, ntfy

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
