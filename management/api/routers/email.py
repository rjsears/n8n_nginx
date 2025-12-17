"""
Email API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from api.database import get_db
from api.dependencies import get_current_user
from api.services.email_service import EmailService
from api.schemas.email import (
    EmailConfigUpdate,
    EmailConfigResponse,
    EmailTemplateUpdate,
    EmailTemplateResponse,
    EmailTestRequest,
    EmailTestResponse,
    EmailTestHistoryResponse,
    EmailTemplatePreviewRequest,
    EmailTemplatePreviewResponse,
)
from api.schemas.common import SuccessResponse

router = APIRouter()


@router.get("/config", response_model=EmailConfigResponse)
async def get_email_config(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get email configuration (passwords redacted)."""
    service = EmailService(db)
    config = await service.get_config()

    if not config:
        return EmailConfigResponse(
            provider="",
            from_email="",
            from_name="",
            configured=False,
        )

    return EmailConfigResponse(
        provider=config.get("provider", ""),
        from_email=config.get("from_email", ""),
        from_name=config.get("from_name", "n8n Management"),
        smtp_host=config.get("smtp_host"),
        smtp_port=config.get("smtp_port"),
        smtp_username=config.get("smtp_username"),
        use_tls=config.get("use_tls", True),
        configured=True,
    )


@router.put("/config", response_model=SuccessResponse)
async def update_email_config(
    data: EmailConfigUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update email configuration."""
    service = EmailService(db)

    config = {
        "provider": data.provider.value,
        "from_email": data.from_email,
        "from_name": data.from_name,
        "smtp_host": data.smtp_host,
        "smtp_port": data.smtp_port,
        "smtp_username": data.smtp_username,
        "smtp_password": data.smtp_password,
        "use_tls": data.use_tls,
        "api_key": data.api_key,
    }

    # Remove None values
    config = {k: v for k, v in config.items() if v is not None}

    await service.save_config(config)

    return SuccessResponse(message="Email configuration updated")


@router.post("/test", response_model=EmailTestResponse)
async def test_email(
    data: EmailTestRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send test email."""
    service = EmailService(db)
    result = await service.test(
        recipient=data.recipient,
        user_id=user.id,
    )

    return EmailTestResponse(**result)


@router.get("/test-history", response_model=List[EmailTestHistoryResponse])
async def get_test_history(
    limit: int = 20,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get email test history."""
    service = EmailService(db)
    history = await service.get_test_history(limit=limit)
    return [EmailTestHistoryResponse.model_validate(h) for h in history]


# Templates

@router.get("/templates", response_model=List[EmailTemplateResponse])
async def list_templates(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all email templates."""
    service = EmailService(db)
    templates = await service.get_templates()
    return [EmailTemplateResponse.model_validate(t) for t in templates]


@router.get("/templates/{template_key}", response_model=EmailTemplateResponse)
async def get_template(
    template_key: str,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get an email template."""
    service = EmailService(db)
    template = await service.get_template(template_key)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return EmailTemplateResponse.model_validate(template)


@router.put("/templates/{template_key}", response_model=EmailTemplateResponse)
async def update_template(
    template_key: str,
    data: EmailTemplateUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an email template."""
    service = EmailService(db)

    updates = data.model_dump(exclude_unset=True)
    updated = await service.update_template(template_key, **updates)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return EmailTemplateResponse.model_validate(updated)


@router.post("/templates/preview", response_model=EmailTemplatePreviewResponse)
async def preview_template(
    data: EmailTemplatePreviewRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Preview a rendered template."""
    service = EmailService(db)

    try:
        preview = await service.preview_template(
            template_key=data.template_key,
            variables=data.variables,
        )
        return EmailTemplatePreviewResponse(**preview)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
