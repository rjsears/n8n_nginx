"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/database.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
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
        from api.models import auth, settings as settings_models, notifications, backups, email, audit, ntfy, system_notifications

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    # Run schema migrations for any new columns
    await run_schema_migrations()

    # Seed default system notification events
    await seed_system_notification_events()

    # Ensure global settings singleton exists
    await seed_system_notification_global_settings()

    logger.info("Database initialized successfully")


async def _migrate_notification_service_slugs(conn) -> None:
    """Generate slugs for existing notification services that don't have one."""
    import re

    def generate_slug(name: str) -> str:
        """Generate a URL-friendly slug from a name."""
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9]+', '_', slug)
        slug = slug.strip('_')
        slug = re.sub(r'_+', '_', slug)
        return slug

    try:
        # Get all services without slugs
        result = await conn.execute(text("""
            SELECT id, name FROM notification_services
            WHERE slug IS NULL OR slug = ''
        """))
        services = result.fetchall()

        if not services:
            return

        logger.info(f"Generating slugs for {len(services)} notification services...")

        # Get existing slugs to avoid duplicates
        existing = await conn.execute(text("""
            SELECT slug FROM notification_services WHERE slug IS NOT NULL AND slug != ''
        """))
        existing_slugs = {row[0] for row in existing.fetchall()}

        for service_id, name in services:
            base_slug = generate_slug(name)
            slug = base_slug
            counter = 1

            # Ensure uniqueness
            while slug in existing_slugs:
                slug = f"{base_slug}_{counter}"
                counter += 1

            existing_slugs.add(slug)

            await conn.execute(text("""
                UPDATE notification_services SET slug = :slug WHERE id = :id
            """), {"slug": slug, "id": service_id})
            logger.info(f"Generated slug '{slug}' for service '{name}'")

    except Exception as e:
        logger.warning(f"Failed to migrate notification service slugs: {e}")


async def run_schema_migrations() -> None:
    """
    Run schema migrations to add missing columns to existing tables.
    This handles the case where tables exist but new columns were added to models.
    """
    logger.info("Checking for schema migrations...")

    # Define migrations as (table_name, column_name, column_definition)
    migrations = [
        # notification_services.webhook_enabled added for webhook routing
        ("notification_services", "webhook_enabled", "BOOLEAN DEFAULT FALSE"),
        # notification_services.slug added for targeted webhook routing
        ("notification_services", "slug", "VARCHAR(100)"),
        # system_notification_container_configs.monitor_stopped for container stopped events
        ("system_notification_container_configs", "monitor_stopped", "BOOLEAN DEFAULT TRUE"),
        # system_notification_container_configs.enabled for master enable/disable
        ("system_notification_container_configs", "enabled", "BOOLEAN DEFAULT TRUE"),
        # system_notification_container_configs resource monitoring fields
        ("system_notification_container_configs", "monitor_high_cpu", "BOOLEAN DEFAULT FALSE"),
        ("system_notification_container_configs", "cpu_threshold", "INTEGER DEFAULT 80"),
        ("system_notification_container_configs", "monitor_high_memory", "BOOLEAN DEFAULT FALSE"),
        ("system_notification_container_configs", "memory_threshold", "INTEGER DEFAULT 80"),
        # system_notification_targets.escalation_timeout_minutes for per-target L2 timeout
        ("system_notification_targets", "escalation_timeout_minutes", "INTEGER"),
        # backup_history protection and pending deletion columns (Phase 7)
        ("backup_history", "is_protected", "BOOLEAN DEFAULT FALSE"),
        ("backup_history", "protected_at", "TIMESTAMP WITH TIME ZONE"),
        ("backup_history", "protected_reason", "VARCHAR(200)"),
        ("backup_history", "deletion_status", "VARCHAR(20)"),
        ("backup_history", "scheduled_deletion_at", "TIMESTAMP WITH TIME ZONE"),
        ("backup_history", "deletion_reason", "VARCHAR(100)"),
        # backup_configuration tiered retention columns (GFS strategy)
        ("backup_configuration", "retention_daily_count", "INTEGER DEFAULT 7"),
        ("backup_configuration", "retention_weekly_count", "INTEGER DEFAULT 4"),
        ("backup_configuration", "retention_monthly_count", "INTEGER DEFAULT 6"),
        # backup_configuration workflow and verification columns
        ("backup_configuration", "backup_workflow", "VARCHAR(20) DEFAULT 'direct'"),
        ("backup_configuration", "verify_frequency", "INTEGER DEFAULT 1"),
    ]

    async with engine.begin() as conn:
        for table_name, column_name, column_def in migrations:
            try:
                # Check if column exists
                result = await conn.execute(text(f"""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = :table AND column_name = :column
                """), {"table": table_name, "column": column_name})

                if result.fetchone() is None:
                    # Column doesn't exist, add it
                    logger.info(f"Adding column {table_name}.{column_name}")
                    await conn.execute(text(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
                    ))
                    logger.info(f"Added column {table_name}.{column_name}")
            except Exception as e:
                logger.warning(f"Migration check for {table_name}.{column_name} failed: {e}")

        # Generate slugs for existing notification services that don't have one
        await _migrate_notification_service_slugs(conn)

        # Fix certificate_expiring event category (move from security to ssl)
        await _migrate_certificate_event_category(conn)


async def _migrate_certificate_event_category(conn) -> None:
    """Move certificate_expiring event from security category to ssl category."""
    try:
        result = await conn.execute(text("""
            UPDATE system_notification_events
            SET category = 'ssl'
            WHERE event_type = 'certificate_expiring' AND category = 'security'
        """))
        if result.rowcount > 0:
            logger.info(f"Migrated certificate_expiring event to ssl category")
    except Exception as e:
        logger.warning(f"Failed to migrate certificate event category: {e}")


async def seed_system_notification_events() -> None:
    """
    Seed default system notification events if they don't exist.
    This ensures all default event types are available on first run.
    """
    from api.models.system_notifications import SystemNotificationEvent, DEFAULT_SYSTEM_EVENTS

    logger.info("Checking system notification events...")

    async with async_session_maker() as session:
        try:
            # Check which events already exist
            result = await session.execute(text(
                "SELECT event_type FROM system_notification_events"
            ))
            existing_types = {row[0] for row in result.fetchall()}

            events_to_add = []
            for event_config in DEFAULT_SYSTEM_EVENTS:
                if event_config["event_type"] not in existing_types:
                    event = SystemNotificationEvent(**event_config)
                    events_to_add.append(event)

            if events_to_add:
                session.add_all(events_to_add)
                await session.commit()
                logger.info(f"Seeded {len(events_to_add)} system notification events")
            else:
                logger.info("All system notification events already exist")

        except Exception as e:
            logger.warning(f"Failed to seed system notification events: {e}")
            await session.rollback()


async def seed_system_notification_global_settings() -> None:
    """
    Ensure global settings singleton exists.
    """
    from api.models.system_notifications import SystemNotificationGlobalSettings

    async with async_session_maker() as session:
        try:
            result = await session.execute(text(
                "SELECT id FROM system_notification_global_settings LIMIT 1"
            ))
            if result.fetchone() is None:
                settings_obj = SystemNotificationGlobalSettings()
                session.add(settings_obj)
                await session.commit()
                logger.info("Created system notification global settings")
        except Exception as e:
            logger.warning(f"Failed to seed global settings: {e}")
            await session.rollback()


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
