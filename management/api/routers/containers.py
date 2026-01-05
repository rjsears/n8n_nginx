"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/routers/containers.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from api.database import get_db
from api.dependencies import get_current_user
from api.services.container_service import ContainerService
from api.schemas.common import SuccessResponse

router = APIRouter()


@router.get("/", response_model=List[Dict[str, Any]])
async def list_containers(
    all: bool = True,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all project containers."""
    service = ContainerService(db)
    return await service.list_containers(all=all)


@router.get("/stats", response_model=List[Dict[str, Any]])
async def get_container_stats(
    _=Depends(get_current_user),
):
    """Get resource usage stats for all containers."""
    service = ContainerService()
    return await service.get_stats()


@router.get("/health")
async def check_containers_health(
    _=Depends(get_current_user),
):
    """Check health of all project containers."""
    service = ContainerService()
    return await service.check_health()


@router.get("/{name}")
async def get_container(
    name: str,
    _=Depends(get_current_user),
):
    """Get container details."""
    service = ContainerService()
    container = await service.get_container(name)

    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Container not found or not a project container",
        )

    return container


@router.post("/{name}/start", response_model=SuccessResponse)
async def start_container(
    name: str,
    _=Depends(get_current_user),
):
    """Start a container."""
    service = ContainerService()

    try:
        await service.start_container(name)
        return SuccessResponse(message=f"Container {name} started")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{name}/stop", response_model=SuccessResponse)
async def stop_container(
    name: str,
    timeout: int = 30,
    _=Depends(get_current_user),
):
    """Stop a container."""
    service = ContainerService()

    try:
        await service.stop_container(name, timeout=timeout)
        return SuccessResponse(message=f"Container {name} stopped")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{name}/restart", response_model=SuccessResponse)
async def restart_container(
    name: str,
    timeout: int = 30,
    _=Depends(get_current_user),
):
    """Restart a container."""
    service = ContainerService()

    try:
        await service.restart_container(name, timeout=timeout)
        return SuccessResponse(message=f"Container {name} restarted")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{name}/logs")
async def get_container_logs(
    name: str,
    tail: int = 100,
    since: int = None,
    timestamps: bool = True,
    _=Depends(get_current_user),
):
    """Get container logs."""
    service = ContainerService()

    try:
        logs = await service.get_logs(
            name=name,
            tail=tail,
            since=since,
            timestamps=timestamps,
        )
        return {"container": name, "logs": logs}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete("/{name}", response_model=SuccessResponse)
async def remove_container(
    name: str,
    force: bool = False,
    _=Depends(get_current_user),
):
    """Remove a stopped container."""
    service = ContainerService()

    try:
        await service.remove_container(name, force=force)
        return SuccessResponse(message=f"Container {name} removed")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{name}/recreate")
async def recreate_container(
    name: str,
    pull: bool = False,
    _=Depends(get_current_user),
):
    """
    Recreate a container using docker compose.

    This will remove the container and create a new one with the same configuration.
    Any non-persisted data will be lost.

    Args:
        name: Container name
        pull: If True, pull the latest image before recreating
    """
    service = ContainerService()

    try:
        result = await service.recreate_container(name, pull=pull)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


