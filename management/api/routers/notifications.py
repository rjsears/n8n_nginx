"""
Notifications API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, UTC
import secrets
import logging

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
    WebhookNotificationRequest,
    WebhookNotificationResponse,
)
from api.schemas.common import SuccessResponse, PaginatedResponse
from api.models.settings import Settings as SettingsModel

router = APIRouter()
logger = logging.getLogger(__name__)

# Webhook API key constants
WEBHOOK_API_KEY_SETTING = "webhook_api_key"
WEBHOOK_API_KEY_CATEGORY = "notifications"


async def get_webhook_api_key_from_db(db: AsyncSession) -> Optional[str]:
    """Get webhook API key from database."""
    result = await db.execute(
        select(SettingsModel).where(SettingsModel.key == WEBHOOK_API_KEY_SETTING)
    )
    setting = result.scalar_one_or_none()
    if setting and setting.value:
        return setting.value.get("key")
    return None


async def save_webhook_api_key_to_db(db: AsyncSession, api_key: str, user_id: int = None) -> None:
    """Save webhook API key to database."""
    result = await db.execute(
        select(SettingsModel).where(SettingsModel.key == WEBHOOK_API_KEY_SETTING)
    )
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = {"key": api_key, "created_at": datetime.now(UTC).isoformat()}
        setting.updated_at = datetime.now(UTC)
        setting.updated_by = user_id
    else:
        setting = SettingsModel(
            key=WEBHOOK_API_KEY_SETTING,
            value={"key": api_key, "created_at": datetime.now(UTC).isoformat()},
            category=WEBHOOK_API_KEY_CATEGORY,
            description="API key for n8n webhook notification endpoint",
            is_secret=True,
            updated_by=user_id,
        )
        db.add(setting)

    await db.commit()
    logger.info("Webhook API key saved to database")


def generate_api_key() -> str:
    """Generate a new secure API key."""
    return secrets.token_urlsafe(32)


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
        webhook_enabled=data.webhook_enabled,
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


# Webhook

@router.post("/webhook", response_model=WebhookNotificationResponse)
async def send_webhook_notification(
    request: WebhookNotificationRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Send notification to all webhook-enabled channels.

    This endpoint is designed for n8n workflows to send notifications
    without needing to configure each notification channel individually.

    Authentication: Include API key as either:
    - Header: X-API-Key: your-api-key
    - Header: Authorization: Bearer your-api-key
    """
    # Extract API key from headers
    api_key = x_api_key
    if not api_key and authorization:
        if authorization.startswith("Bearer "):
            api_key = authorization[7:]

    # Validate API key from database
    expected_key = await get_webhook_api_key_from_db(db)
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook API key not configured. Generate one in the management console.",
        )

    if not api_key or not secrets.compare_digest(api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Send to all webhook-enabled services
    service = NotificationService(db)
    result = await service.send_webhook_notification(
        title=request.title,
        message=request.message,
        priority=request.priority.value,
    )

    return WebhookNotificationResponse(**result)


@router.get("/webhook/info")
async def get_webhook_info(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get webhook endpoint information including API key.
    Only accessible to authenticated users.
    """
    api_key = await get_webhook_api_key_from_db(db)

    return {
        "endpoint": "/api/notifications/webhook",
        "api_key": api_key,
        "has_key": api_key is not None,
        "method": "POST",
        "headers": {
            "X-API-Key": "your-api-key",
            "Content-Type": "application/json",
        },
        "body_schema": {
            "title": "string (optional, default: 'Notification')",
            "message": "string (required)",
            "priority": "string (optional: 'low', 'normal', 'high', 'critical')",
        },
    }


@router.post("/webhook/generate-key")
async def generate_webhook_key(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a new webhook API key.
    Only generates if no key exists. Use regenerate to replace existing key.
    """
    existing_key = await get_webhook_api_key_from_db(db)
    if existing_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key already exists. Use regenerate endpoint to create a new one.",
        )

    new_key = generate_api_key()
    await save_webhook_api_key_to_db(db, new_key, user.id)

    return {
        "success": True,
        "message": "Webhook API key generated successfully",
        "api_key": new_key,
    }


@router.post("/webhook/regenerate-key")
async def regenerate_webhook_key(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Regenerate the webhook API key (revokes the old key).
    Use this if your API key is compromised.
    WARNING: This will invalidate any existing n8n credentials using the old key.
    """
    new_key = generate_api_key()
    await save_webhook_api_key_to_db(db, new_key, user.id)

    return {
        "success": True,
        "message": "Webhook API key regenerated. Update your n8n credentials with the new key.",
        "api_key": new_key,
    }


@router.get("/webhook/n8n-status")
async def get_n8n_api_status(
    _=Depends(get_current_user),
):
    """
    Check n8n API connection status.
    Returns whether n8n API is configured and reachable.
    """
    from api.services.n8n_api_service import n8n_api

    if not n8n_api.is_configured():
        return {
            "configured": False,
            "connected": False,
            "message": "n8n API key not configured. Set N8N_API_KEY environment variable.",
        }

    result = await n8n_api.test_connection()
    return {
        "configured": True,
        "connected": result.get("success", False),
        "message": result.get("message") or result.get("error"),
    }


@router.post("/webhook/create-test-workflow")
async def create_test_workflow(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a test notification workflow in n8n.

    This creates a workflow that:
    1. Has a Manual Trigger (click to run)
    2. Sends a test notification to the webhook endpoint
    3. Shows success/failure result

    Note: After creation, you must configure the HTTP Header Auth credential
    in n8n with your webhook API key.
    """
    from api.services.n8n_api_service import n8n_api

    # Check n8n API is configured
    if not n8n_api.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="n8n API not configured. Set N8N_API_KEY environment variable.",
        )

    # Check we have a webhook API key
    webhook_api_key = await get_webhook_api_key_from_db(db)
    if not webhook_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generate a webhook API key first.",
        )

    # Build webhook URL (use internal Docker network URL for n8n)
    # n8n will call management container internally
    webhook_url = "http://n8n_management:8000/api/notifications/webhook"

    # Create the workflow
    result = await n8n_api.create_notification_test_workflow(webhook_url, webhook_api_key)

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to create workflow"),
        )

    return {
        "success": True,
        "message": "Test workflow created in n8n. Configure the HTTP Header Auth credential with your API key, then click 'Execute Workflow' to test.",
        "workflow_id": result.get("workflow_id"),
        "workflow_name": "Management Console - Test Notifications",
        "next_steps": [
            "1. Open n8n and find the 'Management Console - Test Notifications' workflow",
            "2. Click on the 'Send Notification' node",
            "3. Create a new 'Header Auth' credential with Name: 'X-API-Key' and Value: your webhook API key",
            "4. Save and click 'Execute Workflow' to test",
        ],
    }
