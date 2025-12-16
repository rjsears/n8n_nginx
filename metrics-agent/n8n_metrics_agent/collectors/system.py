"""
System metrics collector using psutil.

Collects CPU, memory, disk, and general system information.
"""

import os
import psutil
import platform
import socket
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import logging

from n8n_metrics_agent.models import (
    CPUMetrics,
    MemoryMetrics,
    DiskMetrics,
    SystemMetrics,
)
from n8n_metrics_agent.config import config

logger = logging.getLogger(__name__)


class SystemCollector:
    """Collects system-level metrics using psutil."""

    def __init__(self):
        self._last_cpu_percent = 0.0
        self._last_cpu_per_core = []
        # Initialize CPU percent tracking (first call returns 0)
        psutil.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None, percpu=True)

    def get_cpu_metrics(self) -> CPUMetrics:
        """Get CPU usage metrics."""
        try:
            # Get CPU percentages (non-blocking after first call)
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)

            # Get load averages (Unix only)
            try:
                load_avg = psutil.getloadavg()
            except (AttributeError, OSError):
                load_avg = (0.0, 0.0, 0.0)

            # Get CPU frequency
            try:
                freq = psutil.cpu_freq()
                frequency_mhz = freq.current if freq else None
            except Exception:
                frequency_mhz = None

            return CPUMetrics(
                percent=cpu_percent,
                percent_per_cpu=cpu_per_core,
                load_avg_1m=load_avg[0],
                load_avg_5m=load_avg[1],
                load_avg_15m=load_avg[2],
                core_count=psutil.cpu_count() or 1,
                frequency_mhz=frequency_mhz,
            )
        except Exception as e:
            logger.error(f"Failed to get CPU metrics: {e}")
            return CPUMetrics(
                percent=0.0,
                percent_per_cpu=[],
                load_avg_1m=0.0,
                load_avg_5m=0.0,
                load_avg_15m=0.0,
                core_count=1,
            )

    def get_memory_metrics(self) -> MemoryMetrics:
        """Get memory usage metrics."""
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return MemoryMetrics(
                total_bytes=mem.total,
                available_bytes=mem.available,
                used_bytes=mem.used,
                percent=mem.percent,
                swap_total_bytes=swap.total,
                swap_used_bytes=swap.used,
                swap_percent=swap.percent,
            )
        except Exception as e:
            logger.error(f"Failed to get memory metrics: {e}")
            return MemoryMetrics(
                total_bytes=0,
                available_bytes=0,
                used_bytes=0,
                percent=0.0,
                swap_total_bytes=0,
                swap_used_bytes=0,
                swap_percent=0.0,
            )

    def get_disk_metrics(self) -> List[DiskMetrics]:
        """Get disk usage metrics for all relevant mount points."""
        disks = []
        try:
            # Get disk I/O stats
            try:
                disk_io = psutil.disk_io_counters(perdisk=True)
            except Exception:
                disk_io = {}

            # Get partition info
            partitions = psutil.disk_partitions(all=False)

            for partition in partitions:
                # Skip excluded filesystem types
                if partition.fstype in config.excluded_fs_types:
                    continue

                # If specific mount points are configured, only include those
                if config.disk_mount_points:
                    if partition.mountpoint not in config.disk_mount_points:
                        continue

                try:
                    usage = psutil.disk_usage(partition.mountpoint)

                    # Try to get I/O stats for this device
                    device_name = partition.device.split("/")[-1]
                    io_stats = disk_io.get(device_name, None)

                    disks.append(DiskMetrics(
                        mount_point=partition.mountpoint,
                        device=partition.device,
                        fs_type=partition.fstype,
                        total_bytes=usage.total,
                        used_bytes=usage.used,
                        free_bytes=usage.free,
                        percent=usage.percent,
                        read_bytes=io_stats.read_bytes if io_stats else None,
                        write_bytes=io_stats.write_bytes if io_stats else None,
                    ))
                except PermissionError:
                    logger.debug(f"Permission denied accessing {partition.mountpoint}")
                except Exception as e:
                    logger.debug(f"Error accessing {partition.mountpoint}: {e}")

        except Exception as e:
            logger.error(f"Failed to get disk metrics: {e}")

        return disks

    def _get_container_uptime(self) -> Optional[float]:
        """
        Get container uptime by checking PID 1's start time.
        This works in LXC/Docker containers where psutil.boot_time() returns host time.
        """
        try:
            # Read the start time of PID 1 (container's init process)
            with open('/proc/1/stat', 'r') as f:
                stat = f.read().split()
                # Field 22 (index 21) is starttime in clock ticks since boot
                starttime_ticks = int(stat[21])

            # Get clock ticks per second
            clk_tck = os.sysconf(os.sysconf_names['SC_CLK_TCK'])

            # Get system uptime from /proc/uptime
            with open('/proc/uptime', 'r') as f:
                system_uptime = float(f.read().split()[0])

            # Calculate container uptime: system_uptime - (starttime_ticks / clk_tck)
            container_start_offset = starttime_ticks / clk_tck
            container_uptime = system_uptime - container_start_offset

            # If the value is negative or very small, we're likely not in a container
            if container_uptime < 0:
                return None

            return container_uptime
        except Exception as e:
            logger.debug(f"Could not determine container uptime: {e}")
            return None

    def _is_in_container(self) -> bool:
        """Check if we're running inside a container (LXC, Docker, etc.)."""
        try:
            # Check for LXC
            if os.path.exists('/dev/lxc'):
                return True
            # Check cgroup for container indicators
            with open('/proc/1/cgroup', 'r') as f:
                cgroup = f.read()
                if 'lxc' in cgroup or 'docker' in cgroup or 'kubepods' in cgroup:
                    return True
            # Check for .dockerenv
            if os.path.exists('/.dockerenv'):
                return True
            # Check for container environment variable
            if os.environ.get('container'):
                return True
        except Exception:
            pass
        return False

    def get_system_metrics(self) -> SystemMetrics:
        """Get general system information."""
        try:
            # Try to get container-specific uptime first
            container_uptime = self._get_container_uptime()

            if container_uptime is not None and self._is_in_container():
                # We're in a container, use container uptime
                uptime = container_uptime
                boot_time = datetime.now(timezone.utc) - timedelta(seconds=uptime)
            else:
                # Use standard system boot time
                boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
                uptime = (datetime.now(timezone.utc) - boot_time).total_seconds()

            # Get logged in users count
            try:
                users = len(psutil.users())
            except Exception:
                users = 0

            return SystemMetrics(
                hostname=socket.gethostname(),
                platform=platform.system().lower(),
                platform_version=platform.version(),
                uptime_seconds=uptime,
                boot_time=boot_time,
                users_logged_in=users,
            )
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return SystemMetrics(
                hostname="unknown",
                platform="unknown",
                platform_version="unknown",
                uptime_seconds=0.0,
                boot_time=datetime.now(timezone.utc),
                users_logged_in=0,
            )
