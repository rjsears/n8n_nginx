"""
System API routes - health, metrics, audit logs.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Dict, Any
from datetime import datetime, timedelta, UTC
import os
import psutil

from api.database import get_db, check_db_connection
from api.dependencies import get_current_user
from api.models.audit import AuditLog, SystemMetricsCache
from api.config import settings
from api.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    System health check endpoint.
    Does not require authentication.
    """
    db_status = "connected" if await check_db_connection() else "disconnected"

    # Check NFS if configured
    nfs_status = None
    if settings.nfs_server:
        nfs_status = "connected" if os.path.ismount(settings.nfs_mount_point) else "disconnected"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        version="3.0.0",
        service="n8n-management",
        database=db_status,
        nfs=nfs_status,
    )


@router.get("/metrics")
async def get_system_metrics(
    _=Depends(get_current_user),
):
    """Get current system metrics."""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()

    # Memory
    memory = psutil.virtual_memory()

    # Disk
    disk = psutil.disk_usage("/")

    # Network
    net_io = psutil.net_io_counters()

    # NFS if mounted
    nfs_metrics = None
    if settings.nfs_server and os.path.ismount(settings.nfs_mount_point):
        try:
            nfs_disk = psutil.disk_usage(settings.nfs_mount_point)
            nfs_metrics = {
                "total_bytes": nfs_disk.total,
                "used_bytes": nfs_disk.used,
                "free_bytes": nfs_disk.free,
                "percent": nfs_disk.percent,
            }
        except Exception:
            pass

    return {
        "cpu": {
            "percent": cpu_percent,
            "count": cpu_count,
        },
        "memory": {
            "total_bytes": memory.total,
            "available_bytes": memory.available,
            "used_bytes": memory.used,
            "percent": memory.percent,
        },
        "disk": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "percent": disk.percent,
        },
        "network": {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
        },
        "nfs": nfs_metrics,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/audit")
async def list_audit_logs(
    action: str = None,
    user_id: int = None,
    limit: int = 50,
    offset: int = 0,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get audit logs."""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())

    if action:
        query = query.where(AuditLog.action == action)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "username": log.username,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "ip_address": str(log.ip_address) if log.ip_address else None,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.get("/audit/actions")
async def list_audit_actions(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List distinct audit actions."""
    result = await db.execute(
        select(AuditLog.action).distinct().order_by(AuditLog.action)
    )
    return [row[0] for row in result.all()]


@router.get("/info")
async def get_system_info(
    _=Depends(get_current_user),
):
    """Get system information."""
    import platform

    # Get uptime
    boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=UTC)
    uptime = datetime.now(UTC) - boot_time

    return {
        "hostname": platform.node(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "boot_time": boot_time.isoformat(),
        "uptime_seconds": int(uptime.total_seconds()),
        "uptime_human": str(uptime).split(".")[0],  # Remove microseconds
    }


@router.get("/docker/info")
async def get_docker_info(
    _=Depends(get_current_user),
):
    """Get Docker daemon information."""
    try:
        import docker
        client = docker.from_env()
        info = client.info()

        return {
            "version": info.get("ServerVersion"),
            "containers": info.get("Containers"),
            "containers_running": info.get("ContainersRunning"),
            "containers_paused": info.get("ContainersPaused"),
            "containers_stopped": info.get("ContainersStopped"),
            "images": info.get("Images"),
            "driver": info.get("Driver"),
            "memory_total": info.get("MemTotal"),
            "cpus": info.get("NCPU"),
            "kernel_version": info.get("KernelVersion"),
            "operating_system": info.get("OperatingSystem"),
            "architecture": info.get("Architecture"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Docker info: {e}",
        )


@router.get("/timezone")
async def get_timezone(
    _=Depends(get_current_user),
):
    """Get configured timezone."""
    import zoneinfo

    tz_name = settings.timezone
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
        now = datetime.now(tz)
        return {
            "timezone": tz_name,
            "offset": now.strftime("%z"),
            "current_time": now.isoformat(),
        }
    except Exception:
        return {
            "timezone": tz_name,
            "offset": "unknown",
            "current_time": datetime.now(UTC).isoformat(),
        }
