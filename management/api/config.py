"""
Application configuration using Pydantic Settings.
All configuration is loaded from environment variables.
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

    # NFS Configuration
    nfs_server: Optional[str] = Field(default=None, description="NFS server hostname")
    nfs_path: Optional[str] = Field(default=None, description="NFS export path")
    nfs_mount_point: str = Field(default="/mnt/backups", description="Local mount point for NFS")

    # Backup settings
    backup_staging_dir: str = Field(default="/app/backups", description="Local backup staging directory")
    backup_compression: str = Field(default="gzip", description="Compression: none, gzip, zstd")

    # Timezone
    timezone: str = Field(default="America/Los_Angeles", alias="TZ")

    # Docker
    docker_socket: str = Field(default="/var/run/docker.sock", description="Docker socket path")
    container_prefix: str = Field(default="n8n_", description="Container name prefix for this project")

    # API settings
    api_rate_limit: int = Field(default=30, description="API requests per second per IP")
    login_rate_limit: int = Field(default=5, description="Login attempts per minute per IP")

    # Webhook API key for n8n notification routing
    webhook_api_key: Optional[str] = Field(
        default=None,
        description="API key for webhook notification endpoint. If not set, a random key is generated on startup."
    )

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
