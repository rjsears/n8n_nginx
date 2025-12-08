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

router = APIRouter()


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

    try:
        query = """
            SELECT id, name, active,
                   COALESCE(jsonb_array_length(nodes), 0) as node_count,
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list flows: {e}",
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
