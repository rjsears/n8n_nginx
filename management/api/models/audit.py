"""
Audit logging and system monitoring models.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, BigInteger, Float, Index
from sqlalchemy.dialects.postgresql import JSONB, INET
from datetime import datetime, UTC

from api.database import Base


class AuditLog(Base):
    """Audit log for tracking user actions."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("admin_user.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(100), nullable=True)  # Denormalized for history

    # Action details
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSONB, nullable=True)

    # Request metadata
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)

    __table_args__ = (
        Index("idx_audit_log_user_id", "user_id"),
        Index("idx_audit_log_action", "action"),
        Index("idx_audit_log_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', user='{self.username}')>"


class ContainerStatusCache(Base):
    """Cache of container status for dashboard display."""

    __tablename__ = "container_status_cache"

    container_name = Column(String(100), primary_key=True)
    container_id = Column(String(64), nullable=True)
    status = Column(String(20), nullable=True)  # 'running', 'stopped', 'restarting', 'unhealthy'
    health = Column(String(20), nullable=True)  # 'healthy', 'unhealthy', 'none'
    started_at = Column(DateTime(timezone=True), nullable=True)
    image = Column(String(255), nullable=True)

    # Resource usage
    cpu_percent = Column(Float, nullable=True)
    memory_usage = Column(BigInteger, nullable=True)
    memory_limit = Column(BigInteger, nullable=True)
    network_rx = Column(BigInteger, nullable=True)
    network_tx = Column(BigInteger, nullable=True)

    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<ContainerStatusCache(name='{self.container_name}', status='{self.status}')>"


class SystemMetricsCache(Base):
    """Cache of system metrics for monitoring."""

    __tablename__ = "system_metrics_cache"

    id = Column(Integer, primary_key=True)
    metric_type = Column(String(50), nullable=False, index=True)  # 'cpu', 'memory', 'disk', 'network', 'nfs'
    metric_data = Column(JSONB, nullable=False)
    collected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)

    __table_args__ = (
        Index("idx_system_metrics_type", "metric_type"),
        Index("idx_system_metrics_collected", "collected_at"),
    )

    def __repr__(self):
        return f"<SystemMetricsCache(id={self.id}, type='{self.metric_type}')>"


class HostMetricsSnapshot(Base):
    """
    Stores periodic snapshots of host system metrics from the metrics-agent.
    Used by the dashboard for instant data retrieval without querying the metrics-agent.
    """

    __tablename__ = "host_metrics_snapshot"

    id = Column(Integer, primary_key=True)
    collected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)

    # System info
    hostname = Column(String(255), nullable=True)
    platform = Column(String(50), nullable=True)
    uptime_seconds = Column(BigInteger, nullable=True)

    # CPU metrics
    cpu_percent = Column(Float, nullable=True)
    cpu_core_count = Column(Integer, nullable=True)
    load_avg_1m = Column(Float, nullable=True)
    load_avg_5m = Column(Float, nullable=True)
    load_avg_15m = Column(Float, nullable=True)

    # Memory metrics
    memory_percent = Column(Float, nullable=True)
    memory_used_bytes = Column(BigInteger, nullable=True)
    memory_total_bytes = Column(BigInteger, nullable=True)
    swap_percent = Column(Float, nullable=True)
    swap_used_bytes = Column(BigInteger, nullable=True)
    swap_total_bytes = Column(BigInteger, nullable=True)

    # Primary disk metrics (/)
    disk_percent = Column(Float, nullable=True)
    disk_used_bytes = Column(BigInteger, nullable=True)
    disk_total_bytes = Column(BigInteger, nullable=True)
    disk_free_bytes = Column(BigInteger, nullable=True)

    # Network totals (sum of all interfaces)
    network_rx_bytes = Column(BigInteger, nullable=True)
    network_tx_bytes = Column(BigInteger, nullable=True)

    # Container summary
    containers_total = Column(Integer, default=0)
    containers_running = Column(Integer, default=0)
    containers_stopped = Column(Integer, default=0)
    containers_healthy = Column(Integer, default=0)
    containers_unhealthy = Column(Integer, default=0)

    # Additional disk info stored as JSON for multiple mount points
    disks_detail = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_host_metrics_collected_at", "collected_at"),
    )

    def __repr__(self):
        return f"<HostMetricsSnapshot(id={self.id}, collected_at='{self.collected_at}')>"
