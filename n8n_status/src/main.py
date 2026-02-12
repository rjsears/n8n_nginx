# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# n8n_status/src/main.py
#
# Main entry point for the status collector service
# Runs collectors on schedule and exposes health endpoint
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import logging
import signal
import sys
import threading
from datetime import datetime, UTC

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

from .config import config
from .redis_client import redis_client
from .collectors import (
    HostMetricsCollector,
    NetworkCollector,
    ContainerCollector,
    CloudflareCollector,
    TailscaleCollector,
    NtfyCollector,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Create FastAPI app for health endpoint
app = FastAPI(title="n8n Status Collector", version="1.0.0")

# Global state
scheduler: BackgroundScheduler = None
collectors: dict = {}
start_time: datetime = None


def init_collectors():
    """Initialize all collectors."""
    global collectors

    collectors = {
        "host_metrics": HostMetricsCollector(),
        "network": NetworkCollector(),
        "containers": ContainerCollector(),
        "cloudflare": CloudflareCollector(),
        "tailscale": TailscaleCollector(),
        "ntfy": NtfyCollector(),
    }

    logger.info(f"Initialized {len(collectors)} collectors")


def schedule_collectors():
    """Set up scheduler for all collectors."""
    global scheduler

    scheduler = BackgroundScheduler(
        timezone="UTC",
        job_defaults={
            "coalesce": True,  # Combine missed runs
            "max_instances": 1,  # Only one instance of each job
        },
    )

    # Schedule each collector based on its interval
    for name, collector in collectors.items():
        scheduler.add_job(
            collector.run,
            trigger=IntervalTrigger(seconds=collector.interval),
            id=f"collector_{name}",
            name=f"Collect {name}",
            replace_existing=True,
        )
        logger.info(f"Scheduled {name} collector every {collector.interval}s")

    scheduler.start()
    logger.info("Scheduler started")


def run_initial_collection():
    """Run all collectors once at startup."""
    logger.info("Running initial collection...")

    for name, collector in collectors.items():
        try:
            logger.info(f"Initial collection: {name}")
            collector.run()
        except Exception as e:
            logger.error(f"Initial collection failed for {name}: {e}")

    logger.info("Initial collection complete")


def shutdown(signum=None, frame=None):
    """Graceful shutdown handler."""
    logger.info("Shutting down...")

    if scheduler:
        scheduler.shutdown(wait=False)

    logger.info("Shutdown complete")
    sys.exit(0)


# Health endpoint
@app.get("/health")
async def health():
    """Health check endpoint."""
    redis_connected = redis_client.is_connected()
    redis_info = redis_client.get_info() if redis_connected else {}

    collector_status = {
        name: collector.get_status()
        for name, collector in collectors.items()
    }

    # Determine overall health
    healthy = (
        redis_connected
        and all(c.last_error is None for c in collectors.values())
    )

    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "healthy" if healthy else "degraded",
            "uptime_seconds": (datetime.now(UTC) - start_time).total_seconds() if start_time else 0,
            "redis": {
                "connected": redis_connected,
                **redis_info,
            },
            "collectors": collector_status,
            "scheduler": {
                "running": scheduler.running if scheduler else False,
                "jobs": len(scheduler.get_jobs()) if scheduler else 0,
            },
        },
    )


@app.get("/metrics")
async def metrics():
    """Get current cached metrics from Redis."""
    keys = redis_client.get_all_keys()

    metrics = {}
    for key in keys:
        data = redis_client.get_json(key)
        if data:
            metrics[key] = data

    return JSONResponse(content=metrics)


@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "service": "n8n_status",
        "version": "1.0.0",
        "endpoints": {
            "/health": "Health check and collector status",
            "/metrics": "Current cached metrics",
        },
    }


def run_health_server():
    """Run the health endpoint server in a thread."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.health_port,
        log_level="warning",  # Reduce noise
    )


def main():
    """Main entry point."""
    global start_time

    logger.info("=" * 50)
    logger.info("n8n Status Collector starting...")
    logger.info(f"Redis: {config.redis_host}:{config.redis_port}")
    logger.info(f"Health endpoint: http://0.0.0.0:{config.health_port}")
    logger.info("=" * 50)

    # Register signal handlers
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Connect to Redis
    logger.info("Connecting to Redis...")
    max_retries = 30
    for attempt in range(max_retries):
        if redis_client.connect():
            break
        logger.warning(f"Redis connection attempt {attempt + 1}/{max_retries} failed, retrying...")
        import time
        time.sleep(2)
    else:
        logger.error("Failed to connect to Redis after all retries")
        sys.exit(1)

    # Initialize collectors
    init_collectors()

    # Run initial collection
    run_initial_collection()

    # Start scheduler
    schedule_collectors()

    # Record start time
    start_time = datetime.now(UTC)

    # Run health server (this blocks)
    logger.info("Starting health server...")
    run_health_server()


if __name__ == "__main__":
    main()
