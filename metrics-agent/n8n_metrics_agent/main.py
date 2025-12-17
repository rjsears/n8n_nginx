"""
n8n Metrics Agent - Main FastAPI Application

A lightweight host-level metrics collector that exposes system and Docker
container metrics via a REST API.
"""

import time
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware

from n8n_metrics_agent import __version__
from n8n_metrics_agent.config import config
from n8n_metrics_agent.models import (
    MetricsResponse,
    HealthResponse,
    ContainerMetrics,
    ContainerEvent,
)
from n8n_metrics_agent.collectors import (
    SystemCollector,
    DockerCollector,
    NetworkCollector,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Collectors (initialized on startup)
system_collector: Optional[SystemCollector] = None
docker_collector: Optional[DockerCollector] = None
network_collector: Optional[NetworkCollector] = None
start_time: float = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global system_collector, docker_collector, network_collector, start_time

    # Startup
    logger.info(f"Starting n8n Metrics Agent v{__version__}")
    start_time = time.time()

    system_collector = SystemCollector()
    docker_collector = DockerCollector()
    network_collector = NetworkCollector()

    logger.info(f"Listening on {config.host}:{config.port}")
    if config.api_key:
        logger.info("API key authentication enabled")
    else:
        logger.warning("No API key configured - endpoints are unprotected")

    yield

    # Shutdown
    logger.info("Shutting down n8n Metrics Agent")


# Create FastAPI app
app = FastAPI(
    title="n8n Metrics Agent",
    description="Host-level system and Docker metrics collector",
    version=__version__,
    lifespan=lifespan,
)

# Add CORS middleware (restrictive - only localhost by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# Authentication dependency
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key if configured."""
    if not config.api_key:
        return True  # No key configured, allow access

    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not secrets.compare_digest(x_api_key, config.api_key):
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
        )

    return True


# Endpoints

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint (no authentication required).

    Returns the agent's health status and availability of subsystems.
    """
    docker_available = docker_collector.is_available if docker_collector else False

    return HealthResponse(
        status="healthy" if docker_available else "degraded",
        version=__version__,
        uptime_seconds=time.time() - start_time,
        docker_available=docker_available,
        checks={
            "system": True,  # psutil is always available
            "docker": docker_available,
            "network": True,
        },
    )


@app.get("/metrics", response_model=MetricsResponse, dependencies=[Depends(verify_api_key)])
async def get_metrics(
    include_container_stats: bool = Query(
        False,
        description="Include detailed container resource stats (slower)"
    ),
):
    """
    Get all system metrics.

    Returns CPU, memory, disk, network, and container metrics in a single response.
    """
    if not system_collector or not docker_collector or not network_collector:
        raise HTTPException(status_code=503, detail="Collectors not initialized")

    return MetricsResponse(
        timestamp=datetime.now(timezone.utc),
        agent_version=__version__,
        system=system_collector.get_system_metrics(),
        cpu=system_collector.get_cpu_metrics(),
        memory=system_collector.get_memory_metrics(),
        disks=system_collector.get_disk_metrics(),
        network=network_collector.get_network_metrics(),
        containers=docker_collector.get_container_metrics(include_stats=include_container_stats),
    )


@app.get("/metrics/system", dependencies=[Depends(verify_api_key)])
async def get_system_metrics():
    """Get system-level metrics only (CPU, memory, disk)."""
    if not system_collector:
        raise HTTPException(status_code=503, detail="System collector not initialized")

    return {
        "timestamp": datetime.now(timezone.utc),
        "system": system_collector.get_system_metrics(),
        "cpu": system_collector.get_cpu_metrics(),
        "memory": system_collector.get_memory_metrics(),
        "disks": system_collector.get_disk_metrics(),
    }


@app.get("/metrics/containers", dependencies=[Depends(verify_api_key)])
async def get_container_metrics(
    include_stats: bool = Query(False, description="Include resource stats"),
):
    """Get Docker container metrics."""
    if not docker_collector:
        raise HTTPException(status_code=503, detail="Docker collector not initialized")

    if not docker_collector.is_available:
        raise HTTPException(status_code=503, detail="Docker is not available")

    return {
        "timestamp": datetime.now(timezone.utc),
        "containers": docker_collector.get_container_metrics(include_stats=include_stats),
    }


@app.get("/metrics/containers/{name}", response_model=ContainerMetrics, dependencies=[Depends(verify_api_key)])
async def get_container_by_name(name: str):
    """Get metrics for a specific container by name."""
    if not docker_collector:
        raise HTTPException(status_code=503, detail="Docker collector not initialized")

    container = docker_collector.get_container_by_name(name)
    if not container:
        raise HTTPException(status_code=404, detail=f"Container '{name}' not found")

    return container


@app.get("/metrics/network", dependencies=[Depends(verify_api_key)])
async def get_network_metrics():
    """Get network interface metrics."""
    if not network_collector:
        raise HTTPException(status_code=503, detail="Network collector not initialized")

    return {
        "timestamp": datetime.now(timezone.utc),
        "interfaces": network_collector.get_network_metrics(),
        "total": network_collector.get_total_bandwidth(),
    }


@app.get("/events/containers", dependencies=[Depends(verify_api_key)])
async def get_container_events():
    """
    Get container state change events since last check.

    This endpoint tracks container health changes, status changes, and restarts.
    Call it periodically to detect events.
    """
    if not docker_collector:
        raise HTTPException(status_code=503, detail="Docker collector not initialized")

    if not docker_collector.is_available:
        raise HTTPException(status_code=503, detail="Docker is not available")

    events = docker_collector.detect_state_changes()

    return {
        "timestamp": datetime.now(timezone.utc),
        "events": events,
        "event_count": len(events),
    }


def run():
    """Run the metrics agent server."""
    import uvicorn

    uvicorn.run(
        "n8n_metrics_agent.main:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
        access_log=False,  # Reduce log noise
    )


if __name__ == "__main__":
    run()
