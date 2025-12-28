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
    NotificationGroupCreate,
    NotificationGroupUpdate,
    NotificationGroupResponse,
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
from api.models.notifications import NotificationService as NotificationServiceModel

router = APIRouter()
logger = logging.getLogger(__name__)


# Import sync function lazily to avoid circular imports
async def _sync_ntfy_channel_to_topic(db: AsyncSession, service: NotificationServiceModel, action: str = "create"):
    """Sync NTFY notification channel to NTFY topic if pointing to local server."""
    try:
        from api.routers.ntfy import sync_notification_channel_to_ntfy_topic
        await sync_notification_channel_to_ntfy_topic(db, service, action)
    except Exception as e:
        logger.warning(f"Failed to sync NTFY channel to topic: {e}")

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
    """List all notification services (channels)."""
    service = NotificationService(db)
    services = await service.get_services()

    # Redact sensitive config values and add group info
    result = []
    for s in services:
        config = dict(s.config)
        for key in ["password", "token", "secret", "api_key"]:
            if key in config:
                config[key] = "***"

        # Get groups this service belongs to
        groups = await service.get_groups_for_service(s.id)
        group_slugs = [g.slug for g in groups]

        response = NotificationServiceResponse(
            id=s.id,
            name=s.name,
            slug=s.slug or "",
            service_type=s.service_type,
            enabled=s.enabled,
            webhook_enabled=s.webhook_enabled,
            config=config,
            priority=s.priority,
            last_test=s.last_test,
            last_test_result=s.last_test_result,
            last_test_error=s.last_test_error,
            created_at=s.created_at,
            updated_at=s.updated_at,
            groups=group_slugs,
        )
        result.append(response)

    return result


@router.post("/services", response_model=NotificationServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    data: NotificationServiceCreate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a notification service (channel)."""
    service = NotificationService(db)
    created = await service.create_service(
        name=data.name,
        slug=data.slug,
        service_type=data.service_type.value,
        config=data.config,
        enabled=data.enabled,
        webhook_enabled=data.webhook_enabled,
        priority=data.priority,
    )

    # Sync NTFY channels to NTFY topics if pointing to local server
    if data.service_type.value == "ntfy":
        await _sync_ntfy_channel_to_topic(db, created, "create")

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

    # Sync NTFY channels to NTFY topics if pointing to local server
    if updated.service_type == "ntfy":
        await _sync_ntfy_channel_to_topic(db, updated, "update")

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


# Groups

@router.get("/groups", response_model=List[NotificationGroupResponse])
async def list_groups(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all notification groups."""
    service = NotificationService(db)
    groups = await service.get_groups()

    result = []
    for g in groups:
        # Get channels in this group with redacted config
        channels = []
        for membership in g.memberships:
            s = membership.service
            config = dict(s.config)
            for key in ["password", "token", "secret", "api_key"]:
                if key in config:
                    config[key] = "***"

            channels.append(NotificationServiceResponse(
                id=s.id,
                name=s.name,
                slug=s.slug or "",
                service_type=s.service_type,
                enabled=s.enabled,
                webhook_enabled=s.webhook_enabled,
                config=config,
                priority=s.priority,
                last_test=s.last_test,
                last_test_result=s.last_test_result,
                last_test_error=s.last_test_error,
                created_at=s.created_at,
                updated_at=s.updated_at,
                groups=[],  # Don't nest groups info
            ))

        result.append(NotificationGroupResponse(
            id=g.id,
            name=g.name,
            slug=g.slug,
            description=g.description,
            enabled=g.enabled,
            channel_count=len(channels),
            channels=channels,
            created_at=g.created_at,
            updated_at=g.updated_at,
        ))

    return result


@router.post("/groups", response_model=NotificationGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: NotificationGroupCreate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a notification group."""
    service = NotificationService(db)

    try:
        created = await service.create_group(
            name=data.name,
            slug=data.slug,
            description=data.description,
            enabled=data.enabled,
            channel_ids=data.channel_ids,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Build response with channels
    channels = []
    for membership in created.memberships:
        s = membership.service
        config = dict(s.config)
        for key in ["password", "token", "secret", "api_key"]:
            if key in config:
                config[key] = "***"

        channels.append(NotificationServiceResponse(
            id=s.id,
            name=s.name,
            slug=s.slug or "",
            service_type=s.service_type,
            enabled=s.enabled,
            webhook_enabled=s.webhook_enabled,
            config=config,
            priority=s.priority,
            last_test=s.last_test,
            last_test_result=s.last_test_result,
            last_test_error=s.last_test_error,
            created_at=s.created_at,
            updated_at=s.updated_at,
            groups=[],
        ))

    return NotificationGroupResponse(
        id=created.id,
        name=created.name,
        slug=created.slug,
        description=created.description,
        enabled=created.enabled,
        channel_count=len(channels),
        channels=channels,
        created_at=created.created_at,
        updated_at=created.updated_at,
    )


@router.get("/groups/{group_id}", response_model=NotificationGroupResponse)
async def get_group(
    group_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a notification group."""
    service = NotificationService(db)
    group = await service.get_group(group_id)

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    # Build response with channels
    channels = []
    for membership in group.memberships:
        s = membership.service
        config = dict(s.config)
        for key in ["password", "token", "secret", "api_key"]:
            if key in config:
                config[key] = "***"

        channels.append(NotificationServiceResponse(
            id=s.id,
            name=s.name,
            slug=s.slug or "",
            service_type=s.service_type,
            enabled=s.enabled,
            webhook_enabled=s.webhook_enabled,
            config=config,
            priority=s.priority,
            last_test=s.last_test,
            last_test_result=s.last_test_result,
            last_test_error=s.last_test_error,
            created_at=s.created_at,
            updated_at=s.updated_at,
            groups=[],
        ))

    return NotificationGroupResponse(
        id=group.id,
        name=group.name,
        slug=group.slug,
        description=group.description,
        enabled=group.enabled,
        channel_count=len(channels),
        channels=channels,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


@router.put("/groups/{group_id}", response_model=NotificationGroupResponse)
async def update_group(
    group_id: int,
    data: NotificationGroupUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a notification group."""
    service = NotificationService(db)

    try:
        updated = await service.update_group(
            group_id=group_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            enabled=data.enabled,
            channel_ids=data.channel_ids,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    # Build response with channels
    channels = []
    for membership in updated.memberships:
        s = membership.service
        config = dict(s.config)
        for key in ["password", "token", "secret", "api_key"]:
            if key in config:
                config[key] = "***"

        channels.append(NotificationServiceResponse(
            id=s.id,
            name=s.name,
            slug=s.slug or "",
            service_type=s.service_type,
            enabled=s.enabled,
            webhook_enabled=s.webhook_enabled,
            config=config,
            priority=s.priority,
            last_test=s.last_test,
            last_test_result=s.last_test_result,
            last_test_error=s.last_test_error,
            created_at=s.created_at,
            updated_at=s.updated_at,
            groups=[],
        ))

    return NotificationGroupResponse(
        id=updated.id,
        name=updated.name,
        slug=updated.slug,
        description=updated.description,
        enabled=updated.enabled,
        channel_count=len(channels),
        channels=channels,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete("/groups/{group_id}", response_model=SuccessResponse)
async def delete_group(
    group_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification group."""
    service = NotificationService(db)
    deleted = await service.delete_group(group_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    return SuccessResponse(message="Group deleted")


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
    Send notification to targeted channels.

    This endpoint is designed for n8n workflows to send notifications
    to specific channels or groups.

    Targets:
    - "all" - sends to all webhook-enabled channels
    - "channel:slug" - sends to a specific channel by its slug
    - "group:slug" - sends to all channels in a group

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

    # Send to targeted channels
    service = NotificationService(db)
    result = await service.send_webhook_notification(
        title=request.title,
        message=request.message,
        priority=request.priority.value,
        targets=request.targets,
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

    # Get available channels and groups for targeting
    service = NotificationService(db)
    services = await service.get_webhook_enabled_services()
    groups = await service.get_groups()

    available_targets = {
        "all": "Send to all webhook-enabled channels",
        "channels": [{"slug": s.slug, "name": s.name} for s in services if s.slug],
        "groups": [{"slug": g.slug, "name": g.name} for g in groups if g.enabled],
    }

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
            "targets": "array of strings (required): 'all', 'channel:slug', or 'group:slug'",
        },
        "available_targets": available_targets,
        "examples": [
            {"targets": ["all"], "description": "Send to all webhook-enabled channels"},
            {"targets": ["channel:devops_slack"], "description": "Send to a specific channel"},
            {"targets": ["group:dev_ops"], "description": "Send to all channels in a group"},
            {"targets": ["channel:ceo_phone", "group:management"], "description": "Multiple targets"},
        ],
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
    try:
        existing_key = await get_webhook_api_key_from_db(db)
        if existing_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key already exists. Use regenerate endpoint to create a new one.",
            )

        new_key = generate_api_key()
        await save_webhook_api_key_to_db(db, new_key, user.id if user else None)

        return {
            "success": True,
            "message": "Webhook API key generated successfully",
            "api_key": new_key,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate webhook API key")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate API key: {str(e)}",
        )


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
    try:
        new_key = generate_api_key()
        await save_webhook_api_key_to_db(db, new_key, user.id if user else None)

        return {
            "success": True,
            "message": "Webhook API key regenerated. Update your n8n credentials with the new key.",
            "api_key": new_key,
        }
    except Exception as e:
        logger.exception("Failed to regenerate webhook API key")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate API key: {str(e)}",
        )


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
    workflow_type: str = "broadcast",
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a test notification workflow in n8n.

    Workflow types:
    - broadcast: Sends to ALL webhook-enabled channels (targets: ["all"])
    - channel: Template for targeting a SPECIFIC channel (targets: ["channel:slug"])
    - group: Template for targeting a notification GROUP (targets: ["group:slug"])

    Each workflow includes:
    1. Manual Trigger (click to run)
    2. HTTP Request to webhook endpoint
    3. Success/failure result display
    4. Setup instructions as sticky notes

    Note: After creation, you must:
    1. Configure the Header Auth credential with your API key
    2. For channel/group workflows, edit the JSON body to specify the target slug
    """
    from api.services.n8n_api_service import n8n_api

    valid_types = ["broadcast", "channel", "group"]
    if workflow_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid workflow_type. Must be one of: {', '.join(valid_types)}",
        )

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
    webhook_url = "http://n8n_management:8000/api/notifications/webhook"

    # Create the appropriate workflow
    if workflow_type == "broadcast":
        result = await n8n_api.create_notification_test_workflow(webhook_url, webhook_api_key)
        workflow_name = "Notification Test - Broadcast to All Channels"
        next_steps = [
            "1. Open n8n and find the workflow",
            "2. Click on the 'Send to All Channels' node",
            "3. Create a new 'Header Auth' credential:",
            "   - Name (header name): X-API-Key",
            "   - Value: paste your webhook API key",
            "4. Save and click 'Execute Workflow' to test",
        ]
    elif workflow_type == "channel":
        result = await n8n_api.create_channel_test_workflow(webhook_url)
        workflow_name = "Notification Test - Target Specific Channel"
        next_steps = [
            "1. Open n8n and find the workflow",
            "2. Click on the 'Send to Channel' node",
            "3. Edit the JSON body: replace YOUR_CHANNEL_SLUG with your actual channel slug",
            "4. Create a new 'Header Auth' credential:",
            "   - Name (header name): X-API-Key",
            "   - Value: paste your webhook API key",
            "5. Save and click 'Execute Workflow' to test",
            "",
            "Find channel slugs in Management Console → Notifications → Channels tab",
        ]
    else:  # group
        result = await n8n_api.create_group_test_workflow(webhook_url)
        workflow_name = "Notification Test - Target Group"
        next_steps = [
            "1. First, create a group in Management Console → Notifications → Groups tab",
            "2. Add channels to the group",
            "3. Open n8n and find the workflow",
            "4. Click on the 'Send to Group' node",
            "5. Edit the JSON body: replace YOUR_GROUP_SLUG with your actual group slug",
            "6. Create a new 'Header Auth' credential:",
            "   - Name (header name): X-API-Key",
            "   - Value: paste your webhook API key",
            "7. Save and click 'Execute Workflow' to test",
        ]

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to create workflow"),
        )

    return {
        "success": True,
        "message": f"Test workflow '{workflow_name}' created in n8n. See setup instructions in the workflow's sticky notes.",
        "workflow_id": result.get("workflow_id"),
        "workflow_name": workflow_name,
        "workflow_type": workflow_type,
        "next_steps": next_steps,
    }


@router.post("/webhook/create-all-test-workflows")
async def create_all_test_workflows(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create ALL three test notification workflows in n8n at once.

    Creates:
    1. Broadcast workflow - sends to all webhook-enabled channels
    2. Channel workflow - template for targeting specific channels
    3. Group workflow - template for targeting notification groups

    Each workflow includes setup instructions as sticky notes.
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

    webhook_url = "http://n8n_management:8000/api/notifications/webhook"

    results = []
    errors = []

    # Create broadcast workflow
    try:
        result = await n8n_api.create_notification_test_workflow(webhook_url, webhook_api_key)
        if result.get("success"):
            results.append({
                "type": "broadcast",
                "name": "Notification Test - Broadcast to All Channels",
                "workflow_id": result.get("workflow_id"),
            })
        else:
            errors.append(f"Broadcast: {result.get('error')}")
    except Exception as e:
        errors.append(f"Broadcast: {str(e)}")

    # Create channel workflow
    try:
        result = await n8n_api.create_channel_test_workflow(webhook_url)
        if result.get("success"):
            results.append({
                "type": "channel",
                "name": "Notification Test - Target Specific Channel",
                "workflow_id": result.get("workflow_id"),
            })
        else:
            errors.append(f"Channel: {result.get('error')}")
    except Exception as e:
        errors.append(f"Channel: {str(e)}")

    # Create group workflow
    try:
        result = await n8n_api.create_group_test_workflow(webhook_url)
        if result.get("success"):
            results.append({
                "type": "group",
                "name": "Notification Test - Target Group",
                "workflow_id": result.get("workflow_id"),
            })
        else:
            errors.append(f"Group: {result.get('error')}")
    except Exception as e:
        errors.append(f"Group: {str(e)}")

    return {
        "success": len(results) > 0,
        "message": f"Created {len(results)} test workflow(s) in n8n.",
        "workflows_created": results,
        "errors": errors if errors else None,
        "next_steps": [
            "1. Open n8n to see the new workflows",
            "2. Each workflow has setup instructions in sticky notes",
            "3. Configure the Header Auth credential in each workflow:",
            "   - Name (header name): X-API-Key",
            "   - Value: your webhook API key from Management Console",
            "4. For channel/group workflows, edit the target slug in the JSON body",
        ],
    }
