"""
NTFY API routes for the management console.
Provides endpoints for message sending, templates, topics, and server configuration.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional
from datetime import datetime, UTC, timedelta
import logging
import json

from api.database import get_db
from api.dependencies import get_current_user
from api.models.ntfy import (
    NtfyTemplate,
    NtfyTopic,
    NtfySavedMessage,
    NtfyMessageHistory,
    NtfyServerConfig,
)
from api.models.notifications import NotificationService, generate_slug
from api.schemas.ntfy import (
    NtfyHealthResponse,
    NtfyStatusResponse,
    NtfyMessageRequest,
    NtfyMessageResponse,
    NtfyTemplatedMessageRequest,
    NtfyTemplateCreate,
    NtfyTemplateUpdate,
    NtfyTemplateResponse,
    NtfyTemplatePreviewRequest,
    NtfyTemplatePreviewResponse,
    NtfyTopicCreate,
    NtfyTopicUpdate,
    NtfyTopicResponse,
    NtfySavedMessageCreate,
    NtfySavedMessageResponse,
    NtfyMessageHistoryResponse,
    NtfyServerConfigUpdate,
    NtfyServerConfigResponse,
    EmojiSearchResponse,
    IntegrationExample,
    WebhookUrlResponse,
)
from api.services.ntfy_service import ntfy_service, COMMON_EMOJIS

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Helper: Sync NTFY Topic to Notification Channel
# =============================================================================

async def sync_ntfy_topic_to_notification_channel(
    db: AsyncSession,
    topic: NtfyTopic,
    action: str = "create"  # "create", "update", or "delete"
) -> Optional[NotificationService]:
    """
    Sync an NTFY topic to a notification channel.
    This allows NTFY topics to be used as notification channels and added to groups.
    """
    # Generate a consistent slug for the notification service
    service_slug = f"ntfy_{generate_slug(topic.name)}"

    # Check if a notification service already exists for this topic
    existing_result = await db.execute(
        select(NotificationService).where(NotificationService.slug == service_slug)
    )
    existing_service = existing_result.scalar_one_or_none()

    if action == "delete":
        # Delete the corresponding notification service
        if existing_service:
            await db.delete(existing_service)
            logger.info(f"Deleted notification channel for NTFY topic: {topic.name}")
        return None

    # Build the notification service config
    service_config = {
        "server": ntfy_service.base_url,  # Internal URL for sending
        "topic": topic.name,
        "tags": topic.default_tags or [],
    }

    # Add auth token if topic requires auth
    if topic.requires_auth:
        # Note: The token would need to be configured separately or pulled from server config
        service_config["requires_auth"] = True

    if action == "create" and not existing_service:
        # Create new notification service
        new_service = NotificationService(
            name=f"NTFY: {topic.name}",
            slug=service_slug,
            service_type="ntfy",
            enabled=topic.enabled,
            config=service_config,
            priority=topic.default_priority or 3,
            webhook_enabled=True,  # Allow webhook routing to this channel
        )
        db.add(new_service)
        logger.info(f"Created notification channel for NTFY topic: {topic.name}")
        return new_service

    elif action == "update" and existing_service:
        # Update existing notification service
        existing_service.name = f"NTFY: {topic.name}"
        existing_service.enabled = topic.enabled
        existing_service.config = service_config
        existing_service.priority = topic.default_priority or 3
        logger.info(f"Updated notification channel for NTFY topic: {topic.name}")
        return existing_service

    elif action == "create" and existing_service:
        # Service already exists, just update it
        existing_service.name = f"NTFY: {topic.name}"
        existing_service.enabled = topic.enabled
        existing_service.config = service_config
        existing_service.priority = topic.default_priority or 3
        logger.info(f"Updated existing notification channel for NTFY topic: {topic.name}")
        return existing_service

    return existing_service


# =============================================================================
# Health & Status
# =============================================================================

@router.get("/health", response_model=NtfyHealthResponse)
async def get_ntfy_health(
    _=Depends(get_current_user),
):
    """Check NTFY server health status."""
    result = await ntfy_service.health_check()
    return NtfyHealthResponse(
        healthy=result["healthy"],
        status=result["status"],
        message=result["message"],
        details=result.get("details"),
    )


@router.get("/status", response_model=NtfyStatusResponse)
async def get_ntfy_status(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full NTFY service status including database stats."""
    # Health check
    health = await ntfy_service.health_check()

    # Count topics
    topics_result = await db.execute(select(func.count(NtfyTopic.id)))
    topics_count = topics_result.scalar() or 0

    # Count templates
    templates_result = await db.execute(select(func.count(NtfyTemplate.id)))
    templates_count = templates_result.scalar() or 0

    # Today's messages
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    messages_result = await db.execute(
        select(func.count(NtfyMessageHistory.id))
        .where(NtfyMessageHistory.created_at >= today_start)
    )
    messages_today = messages_result.scalar() or 0

    # Last message
    last_msg_result = await db.execute(
        select(NtfyMessageHistory.sent_at)
        .where(NtfyMessageHistory.status == "sent")
        .order_by(desc(NtfyMessageHistory.sent_at))
        .limit(1)
    )
    last_message = last_msg_result.scalar()

    return NtfyStatusResponse(
        server_healthy=health["healthy"],
        server_url=ntfy_service.base_url,
        topics_count=topics_count,
        templates_count=templates_count,
        messages_today=messages_today,
        last_message_at=last_message,
    )


# =============================================================================
# Message Sending
# =============================================================================

@router.post("/send", response_model=NtfyMessageResponse)
async def send_message(
    request: NtfyMessageRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send an NTFY notification message."""
    # Build actions list
    actions = None
    if request.actions:
        actions = [
            ntfy_service.build_action(
                action_type=a.action.value,
                label=a.label,
                url=a.url,
                method=a.method,
                headers=a.headers,
                body=a.body,
                intent=a.intent,
                extras=a.extras,
                clear=a.clear,
            )
            for a in request.actions
        ]

    # Validate delay if provided
    if request.delay:
        delay_validation = ntfy_service.validate_delay(request.delay)
        if not delay_validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=delay_validation["error"]
            )

    # Send the message
    result = await ntfy_service.send_message(
        topic=request.topic,
        message=request.message,
        title=request.title,
        priority=request.priority.value,
        tags=request.tags,
        click=request.click,
        attach=request.attach,
        icon=request.icon,
        actions=actions,
        delay=request.delay,
        email=request.email,
        markdown=request.markdown,
    )

    # Record in history
    history = NtfyMessageHistory(
        topic=request.topic,
        title=request.title,
        message=request.message,
        priority=request.priority.value,
        tags=request.tags,
        request_payload={
            "topic": request.topic,
            "message": request.message,
            "title": request.title,
            "priority": request.priority.value,
            "tags": request.tags,
            "click": request.click,
            "attach": request.attach,
            "icon": request.icon,
            "actions": actions,
            "delay": request.delay,
            "email": request.email,
            "markdown": request.markdown,
        },
        status="sent" if result["success"] else "failed",
        response_id=result.get("message_id"),
        error_message=result.get("error"),
        source="manual",
        scheduled_for=datetime.now(UTC) if request.delay else None,
        sent_at=datetime.now(UTC) if result["success"] and not request.delay else None,
    )
    db.add(history)

    # Update topic stats if it exists
    topic_result = await db.execute(
        select(NtfyTopic).where(NtfyTopic.name == request.topic)
    )
    topic = topic_result.scalar_one_or_none()
    if topic:
        topic.message_count += 1
        topic.last_message_at = datetime.now(UTC)

    await db.commit()

    # Optionally save as template
    if request.save_as_template and result["success"]:
        saved_msg = NtfySavedMessage(
            name=request.save_as_template,
            topic=request.topic,
            title=request.title,
            message=request.message,
            priority=request.priority.value,
            tags=request.tags,
            click_url=request.click,
            icon_url=request.icon,
            attach_url=request.attach,
            actions=actions,
            use_markdown=request.markdown,
            delay=request.delay,
            email=request.email,
            created_by=user.id,
        )
        db.add(saved_msg)
        await db.commit()

    return NtfyMessageResponse(
        success=result["success"],
        message_id=result.get("message_id"),
        topic=request.topic,
        scheduled=request.delay is not None,
        error=result.get("error"),
        response=result.get("response"),
    )


@router.post("/send-template", response_model=NtfyMessageResponse)
async def send_templated_message(
    request: NtfyTemplatedMessageRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message using a template."""
    # Check if it's a custom template from our database
    template_result = await db.execute(
        select(NtfyTemplate).where(NtfyTemplate.name == request.template_name)
    )
    template = template_result.scalar_one_or_none()

    if template:
        # Use our custom template - process it locally
        # TODO: Implement Go template processing
        # For now, just use the template's defaults
        result = await ntfy_service.send_message(
            topic=request.topic,
            message=template.message_template or "Message from template",
            title=template.title_template,
            priority=request.priority.value if request.priority else template.default_priority,
            tags=(template.default_tags or []) + request.extra_tags,
            click=template.default_click_url,
            icon=template.default_icon_url,
            markdown=template.use_markdown,
        )

        # Update template usage
        template.use_count += 1
        template.last_used = datetime.now(UTC)
        await db.commit()
    else:
        # Use NTFY's built-in template support
        result = await ntfy_service.send_with_template(
            topic=request.topic,
            template_name=request.template_name,
            data=request.data,
            priority=request.priority.value if request.priority else None,
            extra_tags=request.extra_tags,
        )

    return NtfyMessageResponse(
        success=result["success"],
        topic=request.topic,
        error=result.get("error"),
        response=result.get("response"),
    )


# =============================================================================
# Templates
# =============================================================================

@router.get("/templates", response_model=List[NtfyTemplateResponse])
async def list_templates(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    template_type: Optional[str] = None,
):
    """List all NTFY templates."""
    query = select(NtfyTemplate).order_by(NtfyTemplate.name)
    if template_type:
        query = query.where(NtfyTemplate.template_type == template_type)

    result = await db.execute(query)
    templates = result.scalars().all()
    return [NtfyTemplateResponse.model_validate(t) for t in templates]


@router.post("/templates", response_model=NtfyTemplateResponse)
async def create_template(
    template: NtfyTemplateCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new NTFY template."""
    # Check for duplicate name
    existing = await db.execute(
        select(NtfyTemplate).where(NtfyTemplate.name == template.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template '{template.name}' already exists"
        )

    db_template = NtfyTemplate(
        name=template.name,
        description=template.description,
        template_type=template.template_type,
        based_on=template.based_on,
        title_template=template.title_template,
        message_template=template.message_template,
        default_priority=template.default_priority.value,
        default_tags=template.default_tags,
        default_click_url=template.default_click_url,
        default_icon_url=template.default_icon_url,
        actions_template=[a.model_dump() for a in template.actions_template] if template.actions_template else None,
        use_markdown=template.use_markdown,
        sample_json=template.sample_json,
        created_by=user.id,
    )
    db.add(db_template)
    await db.commit()
    await db.refresh(db_template)

    return NtfyTemplateResponse.model_validate(db_template)


@router.get("/templates/{template_id}", response_model=NtfyTemplateResponse)
async def get_template(
    template_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific NTFY template."""
    result = await db.execute(
        select(NtfyTemplate).where(NtfyTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    return NtfyTemplateResponse.model_validate(template)


@router.put("/templates/{template_id}", response_model=NtfyTemplateResponse)
async def update_template(
    template_id: int,
    update: NtfyTemplateUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an NTFY template."""
    result = await db.execute(
        select(NtfyTemplate).where(NtfyTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    # Update fields
    for field, value in update.model_dump(exclude_unset=True).items():
        if field == "default_priority" and value is not None:
            setattr(template, field, value.value if hasattr(value, 'value') else value)
        elif field == "actions_template" and value is not None:
            setattr(template, field, [a.model_dump() if hasattr(a, 'model_dump') else a for a in value])
        else:
            setattr(template, field, value)

    await db.commit()
    await db.refresh(template)
    return NtfyTemplateResponse.model_validate(template)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an NTFY template."""
    result = await db.execute(
        select(NtfyTemplate).where(NtfyTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    await db.delete(template)
    await db.commit()
    return {"success": True, "message": "Template deleted"}


@router.post("/templates/preview", response_model=NtfyTemplatePreviewResponse)
async def preview_template(
    request: NtfyTemplatePreviewRequest,
    _=Depends(get_current_user),
):
    """Preview a template with sample data."""
    try:
        # Simple variable substitution for preview
        # In production, you'd use proper Go template processing
        rendered_title = request.title_template
        rendered_message = request.message_template

        if request.sample_json:
            for key, value in request.sample_json.items():
                placeholder = "{{ ." + key + " }}"
                str_value = str(value) if value is not None else ""
                if rendered_title:
                    rendered_title = rendered_title.replace(placeholder, str_value)
                if rendered_message:
                    rendered_message = rendered_message.replace(placeholder, str_value)

        return NtfyTemplatePreviewResponse(
            success=True,
            rendered_title=rendered_title,
            rendered_message=rendered_message,
        )
    except Exception as e:
        return NtfyTemplatePreviewResponse(
            success=False,
            error=str(e),
        )


# =============================================================================
# Topics
# =============================================================================

@router.get("/topics", response_model=List[NtfyTopicResponse])
async def list_topics(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all NTFY topics."""
    result = await db.execute(
        select(NtfyTopic).order_by(NtfyTopic.name)
    )
    topics = result.scalars().all()
    return [NtfyTopicResponse.model_validate(t) for t in topics]


@router.post("/topics/sync-channels")
async def sync_topics_to_channels(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync all existing NTFY topics to notification channels.
    This creates notification services for topics that don't have them yet.
    """
    result = await db.execute(select(NtfyTopic))
    topics = result.scalars().all()

    synced = 0
    errors = []

    for topic in topics:
        try:
            service = await sync_ntfy_topic_to_notification_channel(db, topic, action="create")
            if service:
                synced += 1
        except Exception as e:
            errors.append({"topic": topic.name, "error": str(e)})
            logger.error(f"Failed to sync topic {topic.name}: {e}")

    await db.commit()

    return {
        "success": True,
        "synced": synced,
        "total_topics": len(topics),
        "errors": errors if errors else None,
        "message": f"Synced {synced} of {len(topics)} topics to notification channels"
    }


@router.post("/topics", response_model=NtfyTopicResponse)
async def create_topic(
    topic: NtfyTopicCreate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new NTFY topic and sync to notification channels."""
    # Check for duplicate
    existing = await db.execute(
        select(NtfyTopic).where(NtfyTopic.name == topic.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Topic '{topic.name}' already exists"
        )

    db_topic = NtfyTopic(
        name=topic.name,
        description=topic.description,
        access_level=topic.access_level,
        requires_auth=topic.requires_auth,
        default_priority=topic.default_priority.value,
        default_tags=topic.default_tags,
    )
    db.add(db_topic)
    await db.flush()  # Get the ID without committing
    await db.refresh(db_topic)

    # Sync to notification channels - creates a notification service for this topic
    await sync_ntfy_topic_to_notification_channel(db, db_topic, action="create")

    await db.commit()
    await db.refresh(db_topic)

    return NtfyTopicResponse.model_validate(db_topic)


@router.put("/topics/{topic_id}", response_model=NtfyTopicResponse)
async def update_topic(
    topic_id: int,
    update: NtfyTopicUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an NTFY topic and sync to notification channels."""
    result = await db.execute(
        select(NtfyTopic).where(NtfyTopic.id == topic_id)
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found"
        )

    for field, value in update.model_dump(exclude_unset=True).items():
        if field == "default_priority" and value is not None:
            setattr(topic, field, value.value if hasattr(value, 'value') else value)
        else:
            setattr(topic, field, value)

    # Sync to notification channels - updates the corresponding notification service
    await sync_ntfy_topic_to_notification_channel(db, topic, action="update")

    await db.commit()
    await db.refresh(topic)
    return NtfyTopicResponse.model_validate(topic)


@router.delete("/topics/{topic_id}")
async def delete_topic(
    topic_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an NTFY topic and its corresponding notification channel."""
    result = await db.execute(
        select(NtfyTopic).where(NtfyTopic.id == topic_id)
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found"
        )

    # Delete the corresponding notification channel first
    await sync_ntfy_topic_to_notification_channel(db, topic, action="delete")

    await db.delete(topic)
    await db.commit()
    return {"success": True, "message": "Topic deleted"}


# =============================================================================
# Saved Messages
# =============================================================================

@router.get("/saved-messages", response_model=List[NtfySavedMessageResponse])
async def list_saved_messages(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all saved NTFY messages."""
    result = await db.execute(
        select(NtfySavedMessage).order_by(desc(NtfySavedMessage.updated_at))
    )
    messages = result.scalars().all()
    return [NtfySavedMessageResponse.model_validate(m) for m in messages]


@router.post("/saved-messages", response_model=NtfySavedMessageResponse)
async def create_saved_message(
    message: NtfySavedMessageCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a message for later re-use."""
    db_message = NtfySavedMessage(
        name=message.name,
        description=message.description,
        topic=message.topic,
        title=message.title,
        message=message.message,
        priority=message.priority.value,
        tags=message.tags,
        click_url=message.click_url,
        icon_url=message.icon_url,
        attach_url=message.attach_url,
        actions=[a.model_dump() for a in message.actions] if message.actions else None,
        use_markdown=message.use_markdown,
        delay=message.delay,
        email=message.email,
        created_by=user.id,
    )
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)

    return NtfySavedMessageResponse.model_validate(db_message)


@router.post("/saved-messages/{message_id}/send", response_model=NtfyMessageResponse)
async def send_saved_message(
    message_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a saved message."""
    result = await db.execute(
        select(NtfySavedMessage).where(NtfySavedMessage.id == message_id)
    )
    saved = result.scalar_one_or_none()
    if not saved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved message not found"
        )

    # Send the message
    send_result = await ntfy_service.send_message(
        topic=saved.topic,
        message=saved.message,
        title=saved.title,
        priority=saved.priority,
        tags=saved.tags or [],
        click=saved.click_url,
        attach=saved.attach_url,
        icon=saved.icon_url,
        actions=saved.actions,
        delay=saved.delay,
        email=saved.email,
        markdown=saved.use_markdown,
    )

    # Update usage stats
    saved.use_count += 1
    saved.last_used = datetime.now(UTC)
    await db.commit()

    return NtfyMessageResponse(
        success=send_result["success"],
        message_id=send_result.get("message_id"),
        topic=saved.topic,
        scheduled=saved.delay is not None,
        error=send_result.get("error"),
    )


@router.delete("/saved-messages/{message_id}")
async def delete_saved_message(
    message_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a saved message."""
    result = await db.execute(
        select(NtfySavedMessage).where(NtfySavedMessage.id == message_id)
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved message not found"
        )

    await db.delete(message)
    await db.commit()
    return {"success": True, "message": "Saved message deleted"}


# =============================================================================
# Message History
# =============================================================================

@router.get("/history", response_model=List[NtfyMessageHistoryResponse])
async def get_message_history(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    topic: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get NTFY message history."""
    query = select(NtfyMessageHistory).order_by(desc(NtfyMessageHistory.created_at))

    if topic:
        query = query.where(NtfyMessageHistory.topic == topic)
    if status_filter:
        query = query.where(NtfyMessageHistory.status == status_filter)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    messages = result.scalars().all()

    return [NtfyMessageHistoryResponse.model_validate(m) for m in messages]


# =============================================================================
# Server Configuration
# =============================================================================

@router.get("/config", response_model=NtfyServerConfigResponse)
async def get_server_config(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get NTFY server configuration with real-time health check."""
    from datetime import datetime

    result = await db.execute(select(NtfyServerConfig).limit(1))
    config = result.scalar_one_or_none()

    # Run a health check and get real-time status
    health_result = await ntfy_service.health_check()
    health_status = "healthy" if health_result["healthy"] else health_result.get("status", "unknown")
    last_health_check = datetime.utcnow()

    if not config:
        # Create config with health status
        config = NtfyServerConfig(
            health_status=health_status,
            last_health_check=last_health_check,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
    else:
        # Update health status in existing config
        config.health_status = health_status
        config.last_health_check = last_health_check
        await db.commit()

    return NtfyServerConfigResponse(
        base_url=config.base_url,
        upstream_base_url=config.upstream_base_url,
        default_access=config.default_access,
        enable_login=config.enable_login,
        enable_signup=config.enable_signup,
        cache_duration=config.cache_duration,
        attachment_total_size_limit=config.attachment_total_size_limit,
        attachment_file_size_limit=config.attachment_file_size_limit,
        attachment_expiry_duration=config.attachment_expiry_duration,
        visitor_message_daily_limit=config.visitor_message_daily_limit,
        smtp_configured=bool(config.smtp_sender_addr),
        web_push_configured=bool(config.web_push_public_key),
        health_status=health_status,
        last_health_check=last_health_check,
    )


@router.put("/config", response_model=NtfyServerConfigResponse)
async def update_server_config(
    update: NtfyServerConfigUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update NTFY server configuration."""
    from datetime import datetime

    result = await db.execute(select(NtfyServerConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        config = NtfyServerConfig()
        db.add(config)

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(config, field, value)

    # Run a health check and update status
    health_result = await ntfy_service.health_check()
    health_status = "healthy" if health_result["healthy"] else health_result.get("status", "unknown")
    last_health_check = datetime.utcnow()

    config.health_status = health_status
    config.last_health_check = last_health_check

    await db.commit()
    await db.refresh(config)

    return NtfyServerConfigResponse(
        base_url=config.base_url,
        upstream_base_url=config.upstream_base_url,
        default_access=config.default_access,
        enable_login=config.enable_login,
        enable_signup=config.enable_signup,
        cache_duration=config.cache_duration,
        attachment_total_size_limit=config.attachment_total_size_limit,
        attachment_file_size_limit=config.attachment_file_size_limit,
        attachment_expiry_duration=config.attachment_expiry_duration,
        visitor_message_daily_limit=config.visitor_message_daily_limit,
        smtp_configured=bool(config.smtp_sender_addr),
        web_push_configured=bool(config.web_push_public_key),
        health_status=health_status,
        last_health_check=last_health_check,
    )


# =============================================================================
# Emoji Reference
# =============================================================================

@router.get("/emojis/categories")
async def get_emoji_categories(
    _=Depends(get_current_user),
):
    """Get available emoji categories with common shortcodes."""
    return COMMON_EMOJIS


@router.get("/emojis/search", response_model=EmojiSearchResponse)
async def search_emojis(
    q: str = Query(..., min_length=1, max_length=50),
    _=Depends(get_current_user),
):
    """Search emojis by shortcode."""
    query = q.lower()
    results = []

    # Search through all categories
    for category, emojis in COMMON_EMOJIS.items():
        for emoji in emojis:
            if query in emoji.lower():
                results.append({"shortcode": emoji, "category": category})

    return EmojiSearchResponse(
        query=q,
        results=results[:50],  # Limit results
        total=len(results),
    )


# =============================================================================
# Integration Examples
# =============================================================================

@router.get("/integrations/examples", response_model=List[IntegrationExample])
async def get_integration_examples(
    _=Depends(get_current_user),
    category: Optional[str] = None,
):
    """Get example integration code snippets with dynamic NTFY URL."""
    # Use the public URL from ntfy_service (configured from environment)
    ntfy_url = ntfy_service.public_url

    examples = [
        IntegrationExample(
            name="Basic cURL",
            description="Send a simple notification using cURL",
            category="curl",
            code=f'''curl -X POST \\
  -H "Content-Type: application/json" \\
  -d '{{"topic":"alerts","message":"Hello World!","title":"Test"}}' \\
  {ntfy_url}''',
            variables={"topic": "alerts", "message": "Hello World!"},
        ),
        IntegrationExample(
            name="cURL with Priority & Tags",
            description="Send with priority and emoji tags",
            category="curl",
            code=f'''curl -X POST \\
  -H "Content-Type: application/json" \\
  -d '{{
    "topic": "alerts",
    "message": "Server CPU at 95%",
    "title": "High CPU Alert",
    "priority": 4,
    "tags": ["warning", "computer"]
  }}' \\
  {ntfy_url}''',
        ),
        IntegrationExample(
            name="cURL with Actions",
            description="Send notification with action buttons",
            category="curl",
            code=f'''curl -X POST \\
  -H "Content-Type: application/json" \\
  -d '{{
    "topic": "alerts",
    "message": "Deployment ready for approval",
    "title": "Deploy Request",
    "actions": [
      {{"action": "view", "label": "View PR", "url": "https://github.com/..."}},
      {{"action": "http", "label": "Approve", "url": "https://api.example.com/deploy/approve"}}
    ]
  }}' \\
  {ntfy_url}''',
        ),
        IntegrationExample(
            name="n8n HTTP Request (External)",
            description="Configure n8n HTTP Request node to send NTFY notifications externally",
            category="n8n",
            code=f'''{{
  "method": "POST",
  "url": "{ntfy_url}",
  "headers": {{
    "Content-Type": "application/json"
  }},
  "body": {{
    "topic": "{{{{ $json.topic }}}}",
    "message": "{{{{ $json.message }}}}",
    "title": "{{{{ $json.title }}}}",
    "priority": 3,
    "tags": ["n8n", "workflow"]
  }}
}}''',
        ),
        IntegrationExample(
            name="n8n HTTP Request (Internal)",
            description="Configure n8n to send via management API (recommended for internal workflows)",
            category="n8n",
            code='''// Use this URL when n8n and management are on the same Docker network
{
  "method": "POST",
  "url": "http://n8n_management:8000/api/ntfy/send",
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer {{ $credentials.managementApiKey }}"
  },
  "body": {
    "topic": "{{ $json.topic }}",
    "message": "{{ $json.message }}",
    "title": "{{ $json.title }}",
    "priority": 3,
    "tags": ["n8n", "workflow"]
  }
}''',
        ),
        IntegrationExample(
            name="Python requests",
            description="Send notification using Python",
            category="python",
            code=f'''import requests

response = requests.post(
    "{ntfy_url}",
    json={{
        "topic": "alerts",
        "message": "Hello from Python!",
        "title": "Python Notification",
        "priority": 3,
        "tags": ["python", "tada"]
    }}
)
print(response.json())''',
        ),
        IntegrationExample(
            name="Scheduled Message",
            description="Send a delayed/scheduled notification",
            category="curl",
            code=f'''curl -X POST \\
  -H "Content-Type: application/json" \\
  -d '{{
    "topic": "reminders",
    "message": "Time for your meeting!",
    "title": "Reminder",
    "delay": "30m"
  }}' \\
  {ntfy_url}''',
        ),
        IntegrationExample(
            name="JavaScript/Node.js",
            description="Send notification using fetch API",
            category="javascript",
            code=f'''const response = await fetch("{ntfy_url}", {{
  method: "POST",
  headers: {{ "Content-Type": "application/json" }},
  body: JSON.stringify({{
    topic: "alerts",
    message: "Hello from JavaScript!",
    title: "JS Notification",
    priority: 3,
    tags: ["javascript"]
  }})
}});
const result = await response.json();
console.log(result);''',
        ),
    ]

    if category:
        examples = [e for e in examples if e.category == category]

    return examples


@router.get("/integrations/webhook-url", response_model=WebhookUrlResponse)
async def generate_webhook_url(
    topic: str = Query(..., min_length=1, max_length=64),
    _=Depends(get_current_user),
):
    """Generate a webhook URL for a topic with example usage."""
    # Use the public URL for external webhook documentation
    base_url = ntfy_service.public_url

    return WebhookUrlResponse(
        url=f"{base_url}/{topic}",
        topic=topic,
        example_curl=f'''curl -X POST \\
  -H "Content-Type: application/json" \\
  -d '{{"message":"Your message here"}}' \\
  {base_url}/{topic}''',
        example_json={
            "topic": topic,
            "message": "Your message here",
            "title": "Optional title",
            "priority": 3,
            "tags": ["example"],
        },
    )
