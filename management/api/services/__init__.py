"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/__init__.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from api.services.auth_service import AuthService
from api.services.notification_service import NotificationService
from api.services.backup_service import BackupService
from api.services.container_service import ContainerService
from api.services.email_service import EmailService

__all__ = [
    "AuthService",
    "NotificationService",
    "BackupService",
    "ContainerService",
    "EmailService",
]
