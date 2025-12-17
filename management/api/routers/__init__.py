"""
API routers for n8n Management System.
"""

from api.routers import auth
from api.routers import settings
from api.routers import notifications
from api.routers import backups
from api.routers import containers
from api.routers import system
from api.routers import email
from api.routers import flows
from api.routers import ntfy
from api.routers import system_notifications

__all__ = [
    "auth",
    "settings",
    "notifications",
    "backups",
    "containers",
    "system",
    "email",
    "flows",
    "ntfy",
    "system_notifications",
]
