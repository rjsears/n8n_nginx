"""
n8n Management API
FastAPI application for managing n8n infrastructure
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

# Version
__version__ = "3.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print(f"Starting n8n Management API v{__version__}")
    # TODO: Initialize database connection
    # TODO: Initialize scheduler
    yield
    # Shutdown
    print("Shutting down n8n Management API")
    # TODO: Close database connections
    # TODO: Shutdown scheduler


app = FastAPI(
    title="n8n Management API",
    description="Management API for n8n infrastructure - backups, monitoring, and administration",
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Will be configured properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": __version__,
        "service": "n8n-management"
    }


@app.get("/api/auth/verify")
async def verify_auth():
    """
    Auth verification endpoint for nginx auth_request.
    TODO: Implement proper session verification.
    """
    # Placeholder - returns 200 for now
    # Will be replaced with actual auth logic
    return {"status": "ok"}


# TODO: Include routers
# from api.routers import auth, settings, notifications, backups, containers, system, email, flows
# app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
# app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
# app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
# app.include_router(backups.router, prefix="/api/backups", tags=["Backups"])
# app.include_router(containers.router, prefix="/api/containers", tags=["Containers"])
# app.include_router(system.router, prefix="/api/system", tags=["System"])
# app.include_router(email.router, prefix="/api/email", tags=["Email"])
# app.include_router(flows.router, prefix="/api/flows", tags=["Flows"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
