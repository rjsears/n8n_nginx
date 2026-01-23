"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/config.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://n8n_mgmt:password@postgres:5432/n8n_management",
        description="PostgreSQL connection URL for management database"
    )
    n8n_database_url: str = Field(
        default="postgresql+asyncpg://n8n:password@postgres:5432/n8n",
        description="PostgreSQL connection URL for n8n database (read-only access)"
    )

    # Security
    secret_key: str = Field(
        default="change-me-in-production",
        description="Secret key for signing tokens and sessions"
    )
    encryption_key: str = Field(
        default="change-me-in-production-32chars!",
        description="32-character key for AES-256 encryption of sensitive data"
    )

    # Default admin credentials (from environment)
    admin_username: str = Field(
        default="admin",
        description="Default admin username"
    )
    admin_password: str = Field(
        default="changeme",
        description="Default admin password"
    )
    admin_email: Optional[str] = Field(
        default=None,
        description="Default admin email"
    )

    # Session settings
    session_expire_hours: int = Field(default=24, description="Session expiration in hours")
    max_failed_attempts: int = Field(default=5, description="Max failed login attempts before lockout")
    lockout_minutes: int = Field(default=30, description="Account lockout duration in minutes")

    # Password hashing
    bcrypt_rounds: int = Field(default=12, description="Bcrypt hashing rounds")

    # NFS Configuration (host-level mount, bind-mounted into container)
    nfs_server: Optional[str] = Field(default=None, description="NFS server hostname")
    nfs_path: Optional[str] = Field(default=None, description="NFS export path on remote server")
    nfs_local_mount: Optional[str] = Field(default=None, description="Host-level NFS mount point (e.g., /opt/n8n_backups)")
    nfs_mount_point: str = Field(default="/mnt/backups", description="Container mount point for NFS (bind-mounted from host)")

    # Backup settings
    backup_staging_dir: str = Field(default="/app/backups", description="Local backup staging directory")
    backup_compression: str = Field(default="gzip", description="Compression: none, gzip, zstd")

    # Timezone
    timezone: str = Field(default="America/Los_Angeles", alias="TZ")

    # Docker
    docker_socket: str = Field(default="/var/run/docker.sock", description="Docker socket path")
    container_prefix: str = Field(default="n8n_", description="Container name prefix for this project")

    # Public Website Backup/Restore
    public_site_enable: bool = Field(
        default=False,
        description="Enable public website backup/restore features"
    )
    public_website_volume: str = Field(
        default="public_web_root",
        description="Docker volume name for public website files"
    )
    public_website_checksum_algorithm: str = Field(
        default="sha256",
        description="Checksum algorithm for file integrity: sha256 or md5"
    )
    public_website_batch_size: int = Field(
        default=100,
        description="Number of files to restore per batch operation"
    )
    public_website_mount_dir: str = Field(
        default="/tmp/public_website_restore",
        description="Temporary directory for mounting public website backup archives"
    )

    # Domain configuration
    domain: Optional[str] = Field(
        default=None,
        description="Domain for external URLs (e.g., n8n.example.com)"
    )

    # n8n API integration
    n8n_api_url: str = Field(
        default="http://n8n:5678/api/v1",
        description="n8n REST API URL (internal Docker network)"
    )
    n8n_api_key: Optional[str] = Field(
        default=None,
        description="n8n API key for workflow management (generate in n8n Settings > API)"
    )
    n8n_editor_base_url: Optional[str] = Field(
        default=None,
        description="n8n web UI URL (browser-accessible). Uses existing N8N_EDITOR_BASE_URL env var."
    )

    # API settings
    api_rate_limit: int = Field(default=30, description="API requests per second per IP")
    login_rate_limit: int = Field(default=5, description="Login attempts per minute per IP")

    # Webhook API key for n8n notification routing
    webhook_api_key: Optional[str] = Field(
        default=None,
        description="API key for webhook notification endpoint. If not set, a random key is generated on startup."
    )

    # Redis cache settings
    redis_host: str = Field(default="redis", description="Redis server hostname")
    redis_port: int = Field(default=6379, description="Redis server port")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_enabled: bool = Field(default=True, description="Enable Redis caching for status data")

    # Debug
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        # Allow environment variables to override
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience access
settings = get_settings()
