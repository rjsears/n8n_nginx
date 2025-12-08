"""
Notifications API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from api.database import get_db
from api.dependencies import get_current_user
from api.services.notification_service import NotificationService
from api.schemas.notifications import (
    NotificationServiceCreate,
    NotificationServiceUpdate,
    NotificationServiceResponse,
    NotificationRuleCreate,
    NotificationRuleUpdate,
    NotificationRuleResponse,
    NotificationHistoryResponse,
    NotificationTestRequest,
    NotificationEventType,
    EventTypeInfo,
)
from api.schemas.common import SuccessResponse, PaginatedResponse

router = APIRouter()


# Services

@router.get("/services", response_model=List[NotificationServiceResponse])
async def list_services(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all notification services."""
    service = NotificationService(db)
    services = await service.get_services()

    # Redact sensitive config values
    result = []
    for s in services:
        config = dict(s.config)
        for key in ["password", "token", "secret", "api_key"]:
            if key in config:
                config[key] = "***"
        s.config = config
        result.append(NotificationServiceResponse.model_validate(s))

    return result


@router.post("/services", response_model=NotificationServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    data: NotificationServiceCreate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a notification service."""
    service = NotificationService(db)
    created = await service.create_service(
        name=data.name,
        service_type=data.service_type.value,
        config=data.config,
        enabled=data.enabled,
        priority=data.priority,
    )
    return NotificationServiceResponse.model_validate(created)


@router.get("/services/{service_id}", response_model=NotificationServiceResponse)
async def get_service(
    service_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a notification service."""
    service = NotificationService(db)
    svc = await service.get_service(service_id)

    if not svc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    return NotificationServiceResponse.model_validate(svc)


@router.put("/services/{service_id}", response_model=NotificationServiceResponse)
async def update_service(
    service_id: int,
    data: NotificationServiceUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a notification service."""
    service = NotificationService(db)

    updates = data.model_dump(exclude_unset=True)
    updated = await service.update_service(service_id, **updates)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    return NotificationServiceResponse.model_validate(updated)


@router.delete("/services/{service_id}", response_model=SuccessResponse)
async def delete_service(
    service_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification service."""
    service = NotificationService(db)
    deleted = await service.delete_service(service_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    return SuccessResponse(message="Service deleted")


@router.post("/services/{service_id}/test")
async def test_service(
    service_id: int,
    request: NotificationTestRequest = None,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Test a notification service."""
    service = NotificationService(db)

    title = request.title if request else "Test Notification"
    message = request.message if request else "This is a test notification from n8n Management."

    result = await service.test_service(service_id, title, message)

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Test failed"),
        )

    return {"success": True, "message": "Test notification sent"}


# Rules

@router.get("/rules", response_model=List[NotificationRuleResponse])
async def list_rules(
    event_type: str = None,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List notification rules."""
    service = NotificationService(db)
    rules = await service.get_rules(event_type)
    return [NotificationRuleResponse.model_validate(r) for r in rules]


@router.post("/rules", response_model=NotificationRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    data: NotificationRuleCreate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a notification rule."""
    service = NotificationService(db)

    kwargs = data.model_dump()
    kwargs["priority"] = kwargs["priority"].value if hasattr(kwargs["priority"], "value") else kwargs["priority"]

    created = await service.create_rule(**kwargs)
    return NotificationRuleResponse.model_validate(created)


@router.get("/rules/{rule_id}", response_model=NotificationRuleResponse)
async def get_rule(
    rule_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a notification rule."""
    service = NotificationService(db)
    rule = await service.get_rule(rule_id)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    return NotificationRuleResponse.model_validate(rule)


@router.put("/rules/{rule_id}", response_model=NotificationRuleResponse)
async def update_rule(
    rule_id: int,
    data: NotificationRuleUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a notification rule."""
    service = NotificationService(db)

    updates = data.model_dump(exclude_unset=True)
    if "priority" in updates and hasattr(updates["priority"], "value"):
        updates["priority"] = updates["priority"].value

    updated = await service.update_rule(rule_id, **updates)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    return NotificationRuleResponse.model_validate(updated)


@router.delete("/rules/{rule_id}", response_model=SuccessResponse)
async def delete_rule(
    rule_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification rule."""
    service = NotificationService(db)
    deleted = await service.delete_rule(rule_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    return SuccessResponse(message="Rule deleted")


# Event Types

@router.get("/event-types", response_model=List[EventTypeInfo])
async def list_event_types(
    _=Depends(get_current_user),
):
    """List all available event types."""
    event_info = {
        # Backup events
        "backup.started": ("backup", "Backup operation started", "normal"),
        "backup.success": ("backup", "Backup completed successfully", "normal"),
        "backup.failed": ("backup", "Backup operation failed", "critical"),
        "backup.warning": ("backup", "Backup completed with warnings", "high"),
        # Verification events
        "verification.started": ("verification", "Backup verification started", "normal"),
        "verification.passed": ("verification", "Backup verification passed", "normal"),
        "verification.failed": ("verification", "Backup verification failed", "critical"),
        # Container events
        "container.started": ("container", "Container started", "normal"),
        "container.stopped": ("container", "Container stopped", "high"),
        "container.restarted": ("container", "Container restarted", "normal"),
        "container.unhealthy": ("container", "Container became unhealthy", "critical"),
        "container.recovered": ("container", "Container recovered to healthy", "normal"),
        # System events
        "system.high_cpu": ("system", "High CPU usage detected", "high"),
        "system.high_memory": ("system", "High memory usage detected", "high"),
        "system.disk_warning": ("system", "Disk space warning (>80%)", "high"),
        "system.disk_critical": ("system", "Disk space critical (>90%)", "critical"),
        "system.nfs_connected": ("system", "NFS storage connected", "normal"),
        "system.nfs_disconnected": ("system", "NFS storage disconnected", "critical"),
        "system.nfs_error": ("system", "NFS storage error", "critical"),
        # Security events
        "security.login_success": ("security", "Successful login", "low"),
        "security.login_failed": ("security", "Failed login attempt", "normal"),
        "security.account_locked": ("security", "Account locked due to failed attempts", "high"),
        # Management events
        "management.settings_changed": ("management", "System settings changed", "normal"),
        "management.user_created": ("management", "New user created", "normal"),
        "management.backup_deleted": ("management", "Backup file deleted", "normal"),
        # Flow events
        "flow.extracted": ("flow", "Workflow extracted from backup", "normal"),
        "flow.restored": ("flow", "Workflow restored to n8n", "normal"),
    }

    return [
        EventTypeInfo(
            event_type=event_type,
            category=info[0],
            description=info[1],
            default_priority=info[2],
        )
        for event_type, info in event_info.items()
    ]


# History

@router.get("/history", response_model=List[NotificationHistoryResponse])
async def list_history(
    event_type: str = None,
    notification_status: str = None,
    limit: int = 50,
    offset: int = 0,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get notification history."""
    service = NotificationService(db)
    history = await service.get_history(
        limit=limit,
        offset=offset,
        event_type=event_type,
        status=notification_status,
    )
    return [NotificationHistoryResponse.model_validate(h) for h in history]
