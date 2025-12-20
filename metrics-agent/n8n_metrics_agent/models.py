"""
Pydantic models for API responses.
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class CPUMetrics(BaseModel):
    """CPU usage metrics."""
    percent: float  # Overall CPU usage percentage
    percent_per_cpu: List[float]  # Per-core usage
    load_avg_1m: float  # 1-minute load average
    load_avg_5m: float  # 5-minute load average
    load_avg_15m: float  # 15-minute load average
    core_count: int  # Number of CPU cores
    frequency_mhz: Optional[float] = None  # Current frequency


class MemoryMetrics(BaseModel):
    """Memory usage metrics."""
    total_bytes: int
    available_bytes: int
    used_bytes: int
    percent: float
    swap_total_bytes: int
    swap_used_bytes: int
    swap_percent: float


class DiskMetrics(BaseModel):
    """Disk usage metrics for a single mount point."""
    mount_point: str
    device: str
    fs_type: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float
    read_bytes: Optional[int] = None  # Total bytes read (if available)
    write_bytes: Optional[int] = None  # Total bytes written (if available)


class NetworkInterfaceMetrics(BaseModel):
    """Network metrics for a single interface."""
    name: str
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errors_in: int
    errors_out: int
    is_up: bool


class ContainerMetrics(BaseModel):
    """Docker container status and metrics."""
    id: str
    name: str
    image: str
    status: str  # running, paused, exited, etc.
    state: str  # created, running, paused, restarting, removing, exited, dead
    health: Optional[str] = None  # healthy, unhealthy, starting, none
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    restart_count: int = 0
    cpu_percent: Optional[float] = None
    memory_usage_bytes: Optional[int] = None
    memory_limit_bytes: Optional[int] = None
    memory_percent: Optional[float] = None
    network_rx_bytes: Optional[int] = None
    network_tx_bytes: Optional[int] = None
    labels: Dict[str, str] = {}


class SystemMetrics(BaseModel):
    """Overall system metrics."""
    hostname: str
    platform: str  # linux, darwin, windows
    platform_version: str
    uptime_seconds: float
    boot_time: datetime
    users_logged_in: int


class MetricsResponse(BaseModel):
    """Complete metrics response."""
    timestamp: datetime
    agent_version: str
    system: SystemMetrics
    cpu: CPUMetrics
    memory: MemoryMetrics
    disks: List[DiskMetrics]
    network: List[NetworkInterfaceMetrics]
    containers: List[ContainerMetrics]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str  # healthy, degraded
    version: str
    uptime_seconds: float
    docker_available: bool
    checks: Dict[str, bool]


class ContainerEvent(BaseModel):
    """Container state change event."""
    container_id: str
    container_name: str
    event_type: str  # health_changed, status_changed, restart
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    timestamp: datetime
    details: Dict[str, Any] = {}
