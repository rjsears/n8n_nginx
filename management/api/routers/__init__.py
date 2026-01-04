"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/routers/__init__.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
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
from api.routers import env_config

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
    "env_config",
]
