"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/main.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.datastructures import Headers
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
    from api.services.redis_cache_service import init_redis_cache, close_redis_cache

    # Startup
    logger.info(f"Starting n8n Management API v{__version__}")

    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")

        # Backup/verify/restore jobs recorded as running belonged to the
        # previous process: report them as interrupted.
        from api.services.operation_jobs import mark_interrupted_jobs
        await mark_interrupted_jobs()

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

        # A verification container left by a crashed run holds a full copy of
        # the database; nothing can be verifying yet, so remove it now.
        try:
            from api.services.verification_service import remove_stale_verify_container
            await remove_stale_verify_container()
        except Exception as e:
            logger.warning(f"Leftover verification container cleanup failed: {e}")

        # Temporary restore containers left behind by a crash or restart
        try:
            from api.services.restore_service import cleanup_leftover_restore_containers
            await cleanup_leftover_restore_containers()
        except Exception as e:
            logger.warning(f"Leftover restore container cleanup failed: {e}")

        # Initialize scheduler
        await init_scheduler()
        logger.info("Scheduler initialized")

        # Initialize Redis cache
        await init_redis_cache()
        logger.info("Redis cache initialized")

    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down n8n Management API")
    try:
        from api.services.operation_jobs import cancel_all as cancel_operation_jobs
        await cancel_operation_jobs()
        await shutdown_scheduler()
        await close_redis_cache()
        await close_db()
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


import os

from api.security import (
    CSRF_HEADER_NAME,
    UNSAFE_METHODS,
    configured_allowed_origins,
    is_origin_allowed,
)

# Get root path from environment (set by uvicorn --root-path or directly)
ROOT_PATH = os.environ.get("ROOT_PATH", "/management")

app = FastAPI(
    title="n8n Management API",
    description="Management API for n8n infrastructure - backups, monitoring, and administration",
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,  # Disabled - using custom endpoint below
    openapi_url="/api/openapi.json",
    root_path=ROOT_PATH,
)

class CSRFMiddleware:
    """
    Reject cross-site state-changing requests that ride on the session cookie.

    The console authenticates with the HttpOnly "session" cookie (also used
    by nginx auth_request for File Browser/Adminer/Dozzle), and a browser
    attaches that cookie to requests other pages trigger. So a POST/PUT/
    PATCH/DELETE that carries the cookie must also carry the custom
    X-Requested-With header - which a cross-origin page cannot add without a
    CORS preflight we never grant - and, if the browser sent an Origin
    header, it must name this console.

    The rule keys on the presence of any Cookie header rather than on finding
    the session cookie in it: cookie parsers disagree on malformed input
    (http.cookies.SimpleCookie silently stops at the first value it cannot
    parse, e.g. a JSON value), so a request the auth dependency accepts must
    never be one this check skipped. Requests with an Authorization header
    authenticate with it alone (the cookie is ignored), and requests without
    any cookie (bearer API clients, n8n calling the notification webhook with
    its API key) are not exposed to CSRF; both pass through unchanged.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] in UNSAFE_METHODS:
            headers = Headers(scope=scope)
            if not headers.get("authorization") and headers.get("cookie", "").strip():
                origin = headers.get("origin")
                reason = None
                if not headers.get(CSRF_HEADER_NAME):
                    reason = f"missing {CSRF_HEADER_NAME} header"
                elif origin is not None and not is_origin_allowed(origin, headers.get("host")):
                    reason = f"origin {origin!r} not allowed"
                if reason:
                    logger.warning(f"CSRF check failed for {scope['method']} {scope['path']}: {reason}")
                    response = JSONResponse({"detail": "CSRF check failed"}, status_code=403)
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


app.add_middleware(CSRFMiddleware)

# CORS: the console is served from the same origin as the API, so no CORS is
# needed and none is granted by default. Reflecting any Origin with
# credentials (the old allow_origins=["*"] + allow_credentials) let any site
# read authenticated responses. Only origins listed in ALLOWED_ORIGINS are
# allowed when an operator really serves the UI from elsewhere.
if configured_allowed_origins():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", CSRF_HEADER_NAME],
    )

# Include routers
from api.routers import auth, settings, notifications, backups, containers, system, email, flows, terminal, ntfy, system_notifications, env_config, cache

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
app.include_router(env_config.router, prefix="/api/env-config", tags=["Environment Configuration"])
app.include_router(cache.router, prefix="/api/cache", tags=["Cache"])


@app.get("/api/health")
async def health_check():
    """Basic health check endpoint (no auth required)."""
    # Check Redis status
    redis_status = {"enabled": False}
    try:
        from api.services.redis_cache_service import get_redis_cache
        from api.config import settings
        if settings.redis_enabled:
            redis_cache = await get_redis_cache()
            redis_info = await redis_cache.get_info()
            redis_status = redis_info
    except Exception as e:
        redis_status = {"enabled": True, "connected": False, "error": str(e)}

    return {
        "status": "healthy",
        "version": __version__,
        "service": "n8n-management",
        "redis": redis_status,
    }


@app.get("/api/redoc", include_in_schema=False)
async def custom_redoc():
    """Custom ReDoc endpoint with explicit spec URL for reverse proxy compatibility."""
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
    <title>n8n Management API - ReDoc</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
        body {{ margin: 0; padding: 0; }}
    </style>
</head>
<body>
    <redoc spec-url="{ROOT_PATH}/api/openapi.json"></redoc>
    <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
