"""
n8n Management API
FastAPI application for managing n8n infrastructure.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Version
__version__ = "3.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    from api.database import init_db, close_db
    from api.tasks.scheduler import init_scheduler, shutdown_scheduler
    from api.services.email_service import create_default_templates

    # Startup
    logger.info(f"Starting n8n Management API v{__version__}")

    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")

        # Create default admin user if not exists
        from api.database import async_session_maker
        from api.services.auth_service import AuthService
        from api.config import settings as app_settings
        async with async_session_maker() as db:
            auth_service = AuthService(db)
            existing_user = await auth_service.get_user_by_username(app_settings.admin_username)
            if not existing_user:
                # Validate password is not empty
                if not app_settings.admin_password or len(app_settings.admin_password.strip()) < 8:
                    logger.error("ADMIN_PASSWORD must be set and at least 8 characters. Check your environment variables.")
                    raise ValueError("ADMIN_PASSWORD is required and must be at least 8 characters")
                await auth_service.create_user(
                    username=app_settings.admin_username,
                    password=app_settings.admin_password,
                    email=app_settings.admin_email,
                )
                logger.info(f"Default admin user '{app_settings.admin_username}' created")
            else:
                logger.info(f"Admin user '{app_settings.admin_username}' already exists")

        # Create default email templates
        async with async_session_maker() as db:
            await create_default_templates(db)
        logger.info("Default email templates created")

        # Initialize scheduler
        await init_scheduler()
        logger.info("Scheduler initialized")

    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down n8n Management API")
    try:
        await shutdown_scheduler()
        await close_db()
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


import os

# Get root path from environment (set by uvicorn --root-path or directly)
ROOT_PATH = os.environ.get("ROOT_PATH", "/management")

app = FastAPI(
    title="n8n Management API",
    description="Management API for n8n infrastructure - backups, monitoring, and administration",
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    root_path=ROOT_PATH,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Will be configured properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from api.routers import auth, settings, notifications, backups, containers, system, email, flows, terminal, ntfy, system_notifications

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(backups.router, prefix="/api/backups", tags=["Backups"])
app.include_router(containers.router, prefix="/api/containers", tags=["Containers"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(email.router, prefix="/api/email", tags=["Email"])
app.include_router(flows.router, prefix="/api/flows", tags=["Flows"])
app.include_router(terminal.router, prefix="/api", tags=["Terminal"])
app.include_router(ntfy.router, prefix="/api/ntfy", tags=["NTFY"])
app.include_router(system_notifications.router, prefix="/api/system-notifications", tags=["System Notifications"])


@app.get("/api/health")
async def health_check():
    """Basic health check endpoint (no auth required)."""
    return {
        "status": "healthy",
        "version": __version__,
        "service": "n8n-management",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
