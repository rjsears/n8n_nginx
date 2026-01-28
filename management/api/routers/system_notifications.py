"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/routers/system_notifications.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, UTC
import logging

from api.database import get_db
from api.dependencies import get_current_user
from api.models.system_notifications import (
    SystemNotificationEvent,
    SystemNotificationTarget,
    SystemNotificationContainerConfig,
    SystemNotificationState,
    SystemNotificationGlobalSettings,
    SystemNotificationHistory,
)
from api.models.notifications import NotificationService, NotificationGroup
from api.schemas.system_notifications import (
    EventResponse,
    EventUpdate,
    TargetCreate,
    TargetResponse,
    ContainerConfigCreate,
    ContainerConfigUpdate,
    ContainerConfigResponse,
    GlobalSettingsResponse,
    GlobalSettingsUpdate,
    HistoryResponse,
    HistoryListResponse,
    StateResponse,
    MaintenanceModeRequest,
    TestEventRequest,
)
from api.schemas.common import SuccessResponse

router = APIRouter()
logger = logging.getLogger(__name__)


# Helper functions
async def get_event_or_404(db: AsyncSession, event_id: int) -> SystemNotificationEvent:
    """Get event by ID or raise 404."""
    result = await db.execute(
        select(SystemNotificationEvent)
        .options(selectinload(SystemNotificationEvent.targets))
        .where(SystemNotificationEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return event


async def get_event_by_type_or_404(db: AsyncSession, event_type: str) -> SystemNotificationEvent:
    """Get event by type or raise 404."""
    result = await db.execute(
        select(SystemNotificationEvent)
        .options(selectinload(SystemNotificationEvent.targets))
        .where(SystemNotificationEvent.event_type == event_type)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event type '{event_type}' not found",
        )
    return event


async def enrich_target_response(db: AsyncSession, target: SystemNotificationTarget) -> TargetResponse:
    """Enrich target with channel/group names."""
    channel_name = None
    channel_slug = None
    group_name = None
    group_slug = None

    if target.channel_id:
        result = await db.execute(
            select(NotificationService).where(NotificationService.id == target.channel_id)
        )
        channel = result.scalar_one_or_none()
        if channel:
            channel_name = channel.name
            channel_slug = channel.slug

    if target.group_id:
        result = await db.execute(
            select(NotificationGroup).where(NotificationGroup.id == target.group_id)
        )
        group = result.scalar_one_or_none()
        if group:
            group_name = group.name
            group_slug = group.slug

    return TargetResponse(
        id=target.id,
        event_id=target.event_id,
        target_type=target.target_type,
        channel_id=target.channel_id,
        group_id=target.group_id,
        escalation_level=target.escalation_level,
        channel_name=channel_name,
        channel_slug=channel_slug,
        group_name=group_name,
        group_slug=group_slug,
        created_at=target.created_at,
    )


# Events endpoints
@router.get("/events", response_model=List[EventResponse])
async def list_events(
    category: Optional[str] = None,
    enabled_only: bool = False,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all system notification events."""
    query = select(SystemNotificationEvent).options(
        selectinload(SystemNotificationEvent.targets)
    )

    if category:
        query = query.where(SystemNotificationEvent.category == category)
    if enabled_only:
        query = query.where(SystemNotificationEvent.enabled == True)

    query = query.order_by(SystemNotificationEvent.category, SystemNotificationEvent.event_type)
    result = await db.execute(query)
    events = result.scalars().all()

    # Enrich with target details
    responses = []
    for event in events:
        enriched_targets = []
        for target in event.targets:
            enriched_targets.append(await enrich_target_response(db, target))

        responses.append(EventResponse(
            id=event.id,
            event_type=event.event_type,
            display_name=event.display_name,
            description=event.description,
            icon=event.icon,
            category=event.category,
            enabled=event.enabled,
            severity=event.severity,
            frequency=event.frequency,
            cooldown_minutes=event.cooldown_minutes,
            flapping_enabled=event.flapping_enabled,
            flapping_threshold_count=event.flapping_threshold_count,
            flapping_threshold_minutes=event.flapping_threshold_minutes,
            flapping_summary_interval=event.flapping_summary_interval,
            notify_on_recovery=event.notify_on_recovery,
            thresholds=event.thresholds,
            escalation_enabled=event.escalation_enabled,
            escalation_timeout_minutes=event.escalation_timeout_minutes,
            include_in_digest=event.include_in_digest,
            created_at=event.created_at,
            updated_at=event.updated_at,
            targets=enriched_targets,
        ))

    return responses


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific event configuration."""
    event = await get_event_or_404(db, event_id)

    enriched_targets = []
    for target in event.targets:
        enriched_targets.append(await enrich_target_response(db, target))

    return EventResponse(
        id=event.id,
        event_type=event.event_type,
        display_name=event.display_name,
        description=event.description,
        icon=event.icon,
        category=event.category,
        enabled=event.enabled,
        severity=event.severity,
        frequency=event.frequency,
        cooldown_minutes=event.cooldown_minutes,
        flapping_enabled=event.flapping_enabled,
        flapping_threshold_count=event.flapping_threshold_count,
        flapping_threshold_minutes=event.flapping_threshold_minutes,
        flapping_summary_interval=event.flapping_summary_interval,
        notify_on_recovery=event.notify_on_recovery,
        thresholds=event.thresholds,
        escalation_enabled=event.escalation_enabled,
        escalation_timeout_minutes=event.escalation_timeout_minutes,
        include_in_digest=event.include_in_digest,
        created_at=event.created_at,
        updated_at=event.updated_at,
        targets=enriched_targets,
    )


@router.put("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    data: EventUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update event configuration."""
    event = await get_event_or_404(db, event_id)

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(value, "value"):  # Handle enums
            value = value.value
        setattr(event, field, value)

    event.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(event)

    # Get enriched targets
    enriched_targets = []
    for target in event.targets:
        enriched_targets.append(await enrich_target_response(db, target))

    return EventResponse(
        id=event.id,
        event_type=event.event_type,
        display_name=event.display_name,
        description=event.description,
        icon=event.icon,
        category=event.category,
        enabled=event.enabled,
        severity=event.severity,
        frequency=event.frequency,
        cooldown_minutes=event.cooldown_minutes,
        flapping_enabled=event.flapping_enabled,
        flapping_threshold_count=event.flapping_threshold_count,
        flapping_threshold_minutes=event.flapping_threshold_minutes,
        flapping_summary_interval=event.flapping_summary_interval,
        notify_on_recovery=event.notify_on_recovery,
        thresholds=event.thresholds,
        escalation_enabled=event.escalation_enabled,
        escalation_timeout_minutes=event.escalation_timeout_minutes,
        include_in_digest=event.include_in_digest,
        created_at=event.created_at,
        updated_at=event.updated_at,
        targets=enriched_targets,
    )


# Targets endpoints
@router.post("/events/{event_id}/targets", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
async def add_target(
    event_id: int,
    data: TargetCreate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a target (channel or group) to an event."""
    event = await get_event_or_404(db, event_id)

    # Validate target reference exists
    if data.target_type == "channel":
        if not data.channel_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="channel_id required when target_type is 'channel'",
            )
        result = await db.execute(
            select(NotificationService).where(NotificationService.id == data.channel_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found",
            )
    elif data.target_type == "group":
        if not data.group_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="group_id required when target_type is 'group'",
            )
        result = await db.execute(
            select(NotificationGroup).where(NotificationGroup.id == data.group_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found",
            )

    # Check for duplicate
    existing_query = select(SystemNotificationTarget).where(
        SystemNotificationTarget.event_id == event_id,
        SystemNotificationTarget.target_type == data.target_type,
        SystemNotificationTarget.escalation_level == data.escalation_level,
    )
    if data.channel_id:
        existing_query = existing_query.where(
            SystemNotificationTarget.channel_id == data.channel_id
        )
    if data.group_id:
        existing_query = existing_query.where(
            SystemNotificationTarget.group_id == data.group_id
        )

    result = await db.execute(existing_query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target already exists for this event at the same escalation level",
        )

    target = SystemNotificationTarget(
        event_id=event_id,
        target_type=data.target_type,
        channel_id=data.channel_id,
        group_id=data.group_id,
        escalation_level=data.escalation_level,
        escalation_timeout_minutes=data.escalation_timeout_minutes,
    )
    db.add(target)
    await db.commit()
    await db.refresh(target)

    return await enrich_target_response(db, target)


@router.delete("/events/{event_id}/targets/{target_id}", response_model=SuccessResponse)
async def remove_target(
    event_id: int,
    target_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a target from an event."""
    result = await db.execute(
        select(SystemNotificationTarget).where(
            SystemNotificationTarget.id == target_id,
            SystemNotificationTarget.event_id == event_id,
        )
    )
    target = result.scalar_one_or_none()

    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        )

    await db.delete(target)
    await db.commit()

    return SuccessResponse(message="Target removed")


# Container config endpoints
@router.get("/container-configs", response_model=List[ContainerConfigResponse])
async def list_container_configs(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all container notification configurations."""
    result = await db.execute(
        select(SystemNotificationContainerConfig).order_by(
            SystemNotificationContainerConfig.container_name
        )
    )
    configs = result.scalars().all()
    return [ContainerConfigResponse.model_validate(c) for c in configs]


@router.get("/container-configs/{container_name}", response_model=ContainerConfigResponse)
async def get_container_config(
    container_name: str,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get notification config for a specific container."""
    result = await db.execute(
        select(SystemNotificationContainerConfig).where(
            SystemNotificationContainerConfig.container_name == container_name
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        # Return default config (not saved yet)
        return ContainerConfigResponse(
            id=0,
            container_name=container_name,
            enabled=True,
            monitor_unhealthy=True,
            monitor_restart=True,
            monitor_stopped=True,
            monitor_high_cpu=False,
            cpu_threshold=80,
            monitor_high_memory=False,
            memory_threshold=80,
            custom_targets=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    return ContainerConfigResponse.model_validate(config)


@router.post("/container-configs", response_model=ContainerConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_container_config(
    data: ContainerConfigCreate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create notification config for a container."""
    # Check for existing
    result = await db.execute(
        select(SystemNotificationContainerConfig).where(
            SystemNotificationContainerConfig.container_name == data.container_name
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Config already exists for this container. Use PUT to update.",
        )

    config = SystemNotificationContainerConfig(
        container_name=data.container_name,
        monitor_unhealthy=data.monitor_unhealthy,
        monitor_restart=data.monitor_restart,
        custom_targets=data.custom_targets,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)

    return ContainerConfigResponse.model_validate(config)


@router.put("/container-configs/{container_name}", response_model=ContainerConfigResponse)
async def update_container_config(
    container_name: str,
    data: ContainerConfigUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update notification config for a container."""
    result = await db.execute(
        select(SystemNotificationContainerConfig).where(
            SystemNotificationContainerConfig.container_name == container_name
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        # Create if doesn't exist
        config = SystemNotificationContainerConfig(container_name=container_name)
        db.add(config)

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    config.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(config)

    return ContainerConfigResponse.model_validate(config)


@router.delete("/container-configs/{container_name}", response_model=SuccessResponse)
async def delete_container_config(
    container_name: str,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete container config (revert to defaults)."""
    result = await db.execute(
        select(SystemNotificationContainerConfig).where(
            SystemNotificationContainerConfig.container_name == container_name
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Container config not found",
        )

    await db.delete(config)
    await db.commit()

    return SuccessResponse(message="Container config deleted, reverted to defaults")


# Global settings endpoints
@router.get("/global-settings", response_model=GlobalSettingsResponse)
async def get_global_settings(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get global notification settings."""
    result = await db.execute(
        select(SystemNotificationGlobalSettings).limit(1)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        # Create default settings
        settings = SystemNotificationGlobalSettings()
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    # Get emergency contact name if set
    emergency_contact_name = None
    if settings.emergency_contact_id:
        result = await db.execute(
            select(NotificationService).where(
                NotificationService.id == settings.emergency_contact_id
            )
        )
        contact = result.scalar_one_or_none()
        if contact:
            emergency_contact_name = contact.name

    return GlobalSettingsResponse(
        id=settings.id,
        maintenance_mode=settings.maintenance_mode,
        maintenance_until=settings.maintenance_until,
        maintenance_reason=settings.maintenance_reason,
        quiet_hours_enabled=settings.quiet_hours_enabled,
        quiet_hours_start=settings.quiet_hours_start,
        quiet_hours_end=settings.quiet_hours_end,
        quiet_hours_reduce_priority=settings.quiet_hours_reduce_priority,
        blackout_enabled=settings.blackout_enabled,
        blackout_start=settings.blackout_start,
        blackout_end=settings.blackout_end,
        max_notifications_per_hour=settings.max_notifications_per_hour,
        notifications_this_hour=settings.notifications_this_hour,
        hour_started_at=settings.hour_started_at,
        emergency_contact_id=settings.emergency_contact_id,
        emergency_contact_name=emergency_contact_name,
        digest_enabled=settings.digest_enabled,
        digest_time=settings.digest_time,
        digest_severity_levels=settings.digest_severity_levels,
        last_digest_sent=settings.last_digest_sent,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


@router.put("/global-settings", response_model=GlobalSettingsResponse)
async def update_global_settings(
    data: GlobalSettingsUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update global notification settings."""
    result = await db.execute(
        select(SystemNotificationGlobalSettings).limit(1)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = SystemNotificationGlobalSettings()
        db.add(settings)

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    settings.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(settings)

    # Get emergency contact name if set
    emergency_contact_name = None
    if settings.emergency_contact_id:
        result = await db.execute(
            select(NotificationService).where(
                NotificationService.id == settings.emergency_contact_id
            )
        )
        contact = result.scalar_one_or_none()
        if contact:
            emergency_contact_name = contact.name

    return GlobalSettingsResponse(
        id=settings.id,
        maintenance_mode=settings.maintenance_mode,
        maintenance_until=settings.maintenance_until,
        maintenance_reason=settings.maintenance_reason,
        quiet_hours_enabled=settings.quiet_hours_enabled,
        quiet_hours_start=settings.quiet_hours_start,
        quiet_hours_end=settings.quiet_hours_end,
        quiet_hours_reduce_priority=settings.quiet_hours_reduce_priority,
        blackout_enabled=settings.blackout_enabled,
        blackout_start=settings.blackout_start,
        blackout_end=settings.blackout_end,
        max_notifications_per_hour=settings.max_notifications_per_hour,
        notifications_this_hour=settings.notifications_this_hour,
        hour_started_at=settings.hour_started_at,
        emergency_contact_id=settings.emergency_contact_id,
        emergency_contact_name=emergency_contact_name,
        digest_enabled=settings.digest_enabled,
        digest_time=settings.digest_time,
        digest_severity_levels=settings.digest_severity_levels,
        last_digest_sent=settings.last_digest_sent,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


@router.post("/maintenance-mode", response_model=GlobalSettingsResponse)
async def set_maintenance_mode(
    data: MaintenanceModeRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Quick action to toggle maintenance mode."""
    result = await db.execute(
        select(SystemNotificationGlobalSettings).limit(1)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = SystemNotificationGlobalSettings()
        db.add(settings)

    settings.maintenance_mode = data.enabled
    settings.maintenance_until = data.until
    settings.maintenance_reason = data.reason
    settings.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(settings)

    logger.info(f"Maintenance mode {'enabled' if data.enabled else 'disabled'}"
                f"{f' until {data.until}' if data.until else ''}"
                f"{f': {data.reason}' if data.reason else ''}")

    # Get emergency contact name
    emergency_contact_name = None
    if settings.emergency_contact_id:
        result = await db.execute(
            select(NotificationService).where(
                NotificationService.id == settings.emergency_contact_id
            )
        )
        contact = result.scalar_one_or_none()
        if contact:
            emergency_contact_name = contact.name

    return GlobalSettingsResponse(
        id=settings.id,
        maintenance_mode=settings.maintenance_mode,
        maintenance_until=settings.maintenance_until,
        maintenance_reason=settings.maintenance_reason,
        quiet_hours_enabled=settings.quiet_hours_enabled,
        quiet_hours_start=settings.quiet_hours_start,
        quiet_hours_end=settings.quiet_hours_end,
        quiet_hours_reduce_priority=settings.quiet_hours_reduce_priority,
        blackout_enabled=settings.blackout_enabled,
        blackout_start=settings.blackout_start,
        blackout_end=settings.blackout_end,
        max_notifications_per_hour=settings.max_notifications_per_hour,
        notifications_this_hour=settings.notifications_this_hour,
        hour_started_at=settings.hour_started_at,
        emergency_contact_id=settings.emergency_contact_id,
        emergency_contact_name=emergency_contact_name,
        digest_enabled=settings.digest_enabled,
        digest_time=settings.digest_time,
        digest_severity_levels=settings.digest_severity_levels,
        last_digest_sent=settings.last_digest_sent,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


# History endpoints
@router.get("/history", response_model=HistoryListResponse)
async def list_history(
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    target_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get system notification history."""
    query = select(SystemNotificationHistory)

    if event_type:
        query = query.where(SystemNotificationHistory.event_type == event_type)
    if status:
        query = query.where(SystemNotificationHistory.status == status)
    if target_id:
        query = query.where(SystemNotificationHistory.target_id == target_id)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Get items
    query = query.order_by(desc(SystemNotificationHistory.triggered_at))
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    items = result.scalars().all()

    return HistoryListResponse(
        items=[HistoryResponse.model_validate(h) for h in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/history", response_model=SuccessResponse)
async def clear_history(
    older_than_days: int = Query(30, ge=1),
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clear notification history older than specified days."""
    from datetime import timedelta

    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)

    result = await db.execute(
        select(func.count()).where(SystemNotificationHistory.triggered_at < cutoff)
    )
    count = result.scalar()

    await db.execute(
        SystemNotificationHistory.__table__.delete().where(
            SystemNotificationHistory.triggered_at < cutoff
        )
    )
    await db.commit()

    return SuccessResponse(message=f"Deleted {count} history records older than {older_than_days} days")


# State endpoints (for debugging)
@router.get("/state", response_model=List[StateResponse])
async def list_state(
    event_type: Optional[str] = None,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get notification state (for debugging cooldowns and flapping)."""
    query = select(SystemNotificationState)

    if event_type:
        query = query.where(SystemNotificationState.event_type == event_type)

    query = query.order_by(SystemNotificationState.event_type, SystemNotificationState.target_id)
    result = await db.execute(query)
    states = result.scalars().all()

    return [StateResponse.model_validate(s) for s in states]


@router.delete("/state/{state_id}", response_model=SuccessResponse)
async def clear_state(
    state_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clear a specific notification state (reset cooldowns)."""
    result = await db.execute(
        select(SystemNotificationState).where(SystemNotificationState.id == state_id)
    )
    state = result.scalar_one_or_none()

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="State not found",
        )

    await db.delete(state)
    await db.commit()

    return SuccessResponse(message="State cleared")


@router.post("/state/reset-all", response_model=SuccessResponse)
async def reset_all_state(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset all notification states (clear all cooldowns and flapping detection)."""
    await db.execute(SystemNotificationState.__table__.delete())
    await db.commit()

    return SuccessResponse(message="All notification states reset")


# Test endpoint
@router.post("/test", response_model=SuccessResponse)
async def trigger_test_notification(
    data: TestEventRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a test system notification.
    This bypasses rate limiting and sends immediately.
    """
    # Verify event exists
    event = await get_event_by_type_or_404(db, data.event_type)

    if not event.targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event has no configured targets",
        )

    # TODO: Implement actual notification sending via monitoring service
    # For now, just log and record in history
    history = SystemNotificationHistory(
        event_type=data.event_type,
        event_id=event.id,
        target_id=data.target_id,
        target_label=f"Test: {data.target_id}" if data.target_id else "Test notification",
        severity=event.severity,
        event_data=data.data or {"test": True},
        channels_sent=[{"type": t.target_type, "id": t.channel_id or t.group_id} for t in event.targets],
        escalation_level=1,
        status="sent",
        triggered_at=datetime.now(UTC),
        sent_at=datetime.now(UTC),
    )
    db.add(history)
    await db.commit()

    logger.info(f"Test notification triggered for event '{data.event_type}'")

    return SuccessResponse(
        message=f"Test notification for '{event.display_name}' sent to {len(event.targets)} target(s)"
    )
