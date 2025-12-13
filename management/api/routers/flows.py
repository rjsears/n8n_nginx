"""
Flows API routes - n8n workflow extraction and restoration.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from api.database import get_db, get_n8n_db
from api.dependencies import get_current_user
from api.services.backup_service import BackupService
from api.services.n8n_api_service import n8n_api

router = APIRouter()


class ToggleWorkflowRequest(BaseModel):
    """Request to toggle workflow active state."""
    active: bool


class ExecuteWorkflowResponse(BaseModel):
    """Response from workflow execution."""
    success: bool
    execution_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


class FlowInfo(BaseModel):
    """Workflow information."""
    id: str
    name: str
    active: bool
    node_count: int
    created_at: str
    updated_at: str


class FlowExportRequest(BaseModel):
    """Bulk flow export request."""
    flow_ids: List[str]


class FlowRestoreRequest(BaseModel):
    """Restore flow from backup request."""
    backup_id: int
    flow_id: str
    conflict_action: str = "rename"  # 'rename', 'skip', 'overwrite'


class FlowRestoreResponse(BaseModel):
    """Flow restore response."""
    status: str
    flow_id: Optional[str] = None
    flow_name: Optional[str] = None
    reason: Optional[str] = None


class ExecutionInfo(BaseModel):
    """Workflow execution information."""
    id: str
    workflowId: str
    workflowName: str
    status: str  # success, error, waiting, running
    startedAt: Optional[str] = None
    stoppedAt: Optional[str] = None
    executionTime: Optional[int] = None  # milliseconds


@router.get("/list", response_model=List[FlowInfo])
async def list_flows(
    active_only: bool = False,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_n8n_db),
):
    """
    List all workflows in the n8n database.
    Requires read access to n8n database.
    """
    from sqlalchemy import text
    import logging

    logger = logging.getLogger(__name__)

    try:
        # First test the connection
        await db.execute(text("SELECT 1"))

        query = """
            SELECT id, name, active,
                   COALESCE(json_array_length(nodes), 0) as node_count,
                   "createdAt", "updatedAt"
            FROM workflow_entity
        """
        if active_only:
            query += " WHERE active = true"
        query += " ORDER BY name"

        result = await db.execute(text(query))
        rows = result.fetchall()

        return [
            FlowInfo(
                id=str(row[0]),
                name=row[1],
                active=row[2],
                node_count=row[3] or 0,
                created_at=row[4].isoformat() if row[4] else "",
                updated_at=row[5].isoformat() if row[5] else "",
            )
            for row in rows
        ]
    except Exception as e:
        import traceback
        full_error = traceback.format_exc()
        logger.error(f"Failed to list flows from n8n database: {e}\n{full_error}")
        # Provide more specific error message with the actual error for debugging
        error_msg = str(e)
        if "password authentication failed" in error_msg.lower():
            detail = f"n8n database authentication failed. Check N8N_DATABASE_URL password. Error: {error_msg}"
        elif "could not connect" in error_msg.lower() or "connection refused" in error_msg.lower():
            detail = f"Cannot connect to n8n database. Ensure postgres container is running. Error: {error_msg}"
        elif "does not exist" in error_msg.lower():
            detail = f"n8n database or table not found. Error: {error_msg}"
        else:
            detail = f"Failed to list flows: {error_msg}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )


@router.get("/executions", response_model=List[ExecutionInfo])
async def list_executions(
    limit: int = 20,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_n8n_db),
):
    """
    List recent workflow executions from the n8n database.
    """
    from sqlalchemy import text
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Query execution_entity table with workflow name join
        query = """
            SELECT
                e.id,
                e."workflowId",
                COALESCE(w.name, 'Unknown Workflow') as workflow_name,
                e.status,
                e."startedAt",
                e."stoppedAt"
            FROM execution_entity e
            LEFT JOIN workflow_entity w ON e."workflowId"::text = w.id::text
            ORDER BY e."startedAt" DESC
            LIMIT :limit
        """

        result = await db.execute(text(query), {"limit": limit})
        rows = result.fetchall()

        executions = []
        for row in rows:
            started_at = row[4]
            stopped_at = row[5]

            # Calculate execution time in milliseconds
            execution_time = None
            if started_at and stopped_at:
                try:
                    diff = stopped_at - started_at
                    execution_time = int(diff.total_seconds() * 1000)
                except Exception:
                    pass

            executions.append(ExecutionInfo(
                id=str(row[0]),
                workflowId=str(row[1]) if row[1] else "",
                workflowName=row[2] or "Unknown",
                status=row[3] or "unknown",
                startedAt=started_at.isoformat() if started_at else None,
                stoppedAt=stopped_at.isoformat() if stopped_at else None,
                executionTime=execution_time,
            ))

        return executions
    except Exception as e:
        logger.error(f"Failed to list executions: {e}")
        # Return empty list instead of error for executions
        # This allows the page to load even if execution history isn't available
        return []


@router.post("/{workflow_id}/toggle")
async def toggle_workflow(
    workflow_id: str,
    request: ToggleWorkflowRequest,
    _=Depends(get_current_user),
):
    """
    Toggle workflow active state (activate/deactivate).
    Requires n8n API key to be configured.
    """
    import logging
    logger = logging.getLogger(__name__)

    if not n8n_api.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="n8n API key not configured. Set N8N_API_KEY environment variable to enable workflow management.",
        )

    try:
        result = await n8n_api.activate_workflow(workflow_id, request.active)

        if result.get("success"):
            action = "activated" if request.active else "deactivated"
            return {"success": True, "message": f"Workflow {action} successfully"}
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"Failed to toggle workflow {workflow_id}: {error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to toggle workflow: {error}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error toggling workflow: {str(e)}",
        )


@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    _=Depends(get_current_user),
):
    """
    Execute a workflow manually.
    Requires n8n API key to be configured.
    Note: This may not work for all workflow types - workflows with webhook triggers
    should be triggered via their webhook URL instead.
    """
    import logging
    logger = logging.getLogger(__name__)

    if not n8n_api.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="n8n API key not configured. Set N8N_API_KEY environment variable to enable workflow execution.",
        )

    try:
        result = await n8n_api.execute_workflow(workflow_id)

        if result.get("success"):
            return ExecuteWorkflowResponse(
                success=True,
                execution_id=result.get("execution_id"),
                message="Workflow execution started",
            )
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"Failed to execute workflow {workflow_id}: {error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing workflow: {str(e)}",
        )


@router.get("/export/{flow_id}")
async def export_flow(
    flow_id: str,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_n8n_db),
):
    """
    Export a single workflow as JSON.
    """
    from sqlalchemy import text

    try:
        result = await db.execute(
            text("""
                SELECT id, name, nodes, connections, settings, "staticData",
                       active, "createdAt", "updatedAt"
                FROM workflow_entity
                WHERE id = :flow_id
            """),
            {"flow_id": flow_id},
        )
        row = result.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found",
            )

        # Build n8n-compatible export format
        workflow = {
            "id": str(row[0]),
            "name": row[1],
            "nodes": row[2] or [],
            "connections": row[3] or {},
            "settings": row[4] or {},
            "staticData": row[5],
            "active": row[6],
            "createdAt": row[7].isoformat() if row[7] else None,
            "updatedAt": row[8].isoformat() if row[8] else None,
        }

        return JSONResponse(
            content=workflow,
            headers={
                "Content-Disposition": f'attachment; filename="{row[1]}.json"',
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export flow: {e}",
        )


@router.post("/export/bulk")
async def export_flows_bulk(
    request: FlowExportRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_n8n_db),
):
    """
    Export multiple workflows as JSON array.
    """
    from sqlalchemy import text

    try:
        # Build parameterized query
        placeholders = ", ".join([f":id_{i}" for i in range(len(request.flow_ids))])
        params = {f"id_{i}": fid for i, fid in enumerate(request.flow_ids)}

        result = await db.execute(
            text(f"""
                SELECT id, name, nodes, connections, settings, "staticData",
                       active, "createdAt", "updatedAt"
                FROM workflow_entity
                WHERE id IN ({placeholders})
            """),
            params,
        )
        rows = result.fetchall()

        workflows = []
        for row in rows:
            workflows.append({
                "id": str(row[0]),
                "name": row[1],
                "nodes": row[2] or [],
                "connections": row[3] or {},
                "settings": row[4] or {},
                "staticData": row[5],
                "active": row[6],
                "createdAt": row[7].isoformat() if row[7] else None,
                "updatedAt": row[8].isoformat() if row[8] else None,
            })

        return JSONResponse(
            content=workflows,
            headers={
                "Content-Disposition": 'attachment; filename="workflows_export.json"',
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export flows: {e}",
        )


@router.get("/from-backup/{backup_id}", response_model=List[FlowInfo])
async def list_flows_from_backup(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List workflows contained in a backup file.
    Note: This requires extracting and temporarily restoring the backup,
    which may take some time for large backups.
    """
    # For now, return a placeholder - full implementation would require
    # spinning up a temporary postgres container
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Backup flow extraction not yet implemented. Use the backup download and manual inspection.",
    )


@router.post("/restore", response_model=FlowRestoreResponse)
async def restore_flow(
    request: FlowRestoreRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Restore a workflow from a backup to the live n8n database.
    Note: This is a complex operation that requires careful handling.
    """
    # For now, return a placeholder - full implementation would require
    # spinning up a temporary postgres container
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Backup flow restoration not yet implemented.",
    )


@router.get("/debug-connection")
async def debug_connection(
    _=Depends(get_current_user),
):
    """Debug n8n database connection settings."""
    from api.config import settings
    from api.database import encode_database_url
    from urllib.parse import urlparse

    # Parse the URL to show config without password
    original_url = settings.n8n_database_url
    encoded_url = encode_database_url(original_url)

    try:
        parsed_orig = urlparse(original_url)
        parsed_enc = urlparse(encoded_url)

        return {
            "original": {
                "scheme": parsed_orig.scheme,
                "username": parsed_orig.username,
                "password_length": len(parsed_orig.password) if parsed_orig.password else 0,
                "password_starts_with": parsed_orig.password[:2] if parsed_orig.password and len(parsed_orig.password) > 2 else None,
                "hostname": parsed_orig.hostname,
                "port": parsed_orig.port,
                "database": parsed_orig.path.lstrip('/'),
            },
            "encoded": {
                "scheme": parsed_enc.scheme,
                "username": parsed_enc.username,
                "password_length": len(parsed_enc.password) if parsed_enc.password else 0,
                "hostname": parsed_enc.hostname,
                "port": parsed_enc.port,
                "database": parsed_enc.path.lstrip('/'),
            },
            "raw_url_length": len(original_url),
            "encoded_url_length": len(encoded_url),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/stats")
async def get_flow_stats(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_n8n_db),
):
    """Get workflow statistics from n8n database."""
    from sqlalchemy import text

    try:
        # Total and active counts
        result = await db.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE active = true) as active,
                    COUNT(*) FILTER (WHERE active = false) as inactive
                FROM workflow_entity
            """)
        )
        row = result.fetchone()

        # Recent workflows
        result = await db.execute(
            text("""
                SELECT name, "updatedAt"
                FROM workflow_entity
                ORDER BY "updatedAt" DESC
                LIMIT 5
            """)
        )
        recent = [
            {"name": r[0], "updated_at": r[1].isoformat() if r[1] else None}
            for r in result.fetchall()
        ]

        return {
            "total": row[0],
            "active": row[1],
            "inactive": row[2],
            "recent": recent,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get flow stats: {e}",
        )


@router.get("/n8n-url")
async def get_n8n_url(
    _=Depends(get_current_user),
):
    """
    Get the n8n web URL for linking to workflows and executions.
    Returns the configured N8N_WEB_URL or a default relative path.
    """
    from api.config import settings

    # Use configured URL or default to relative path
    n8n_url = settings.n8n_web_url or "/n8n"

    return {
        "url": n8n_url.rstrip("/"),
        "configured": settings.n8n_web_url is not None,
    }
