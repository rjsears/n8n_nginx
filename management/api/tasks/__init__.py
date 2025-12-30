"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/tasks/__init__.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from api.tasks.scheduler import init_scheduler, shutdown_scheduler, get_scheduler

__all__ = [
    "init_scheduler",
    "shutdown_scheduler",
    "get_scheduler",
]
