# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# n8n_status/src/collectors/host_metrics.py
#
# Collects host system metrics (CPU, memory, disk)
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import logging
import os
from typing import Any

import psutil

from .base import BaseCollector
from ..config import config

logger = logging.getLogger(__name__)


class HostMetricsCollector(BaseCollector):
    """
    Collects host system metrics including CPU, memory, and disk usage.

    This runs inside a container but accesses host metrics via:
    - psutil for CPU and memory (works in container)
    - /host/proc mount for more accurate host data if available
    """

    key = "system:host_metrics"
    interval = config.poll_interval_metrics
    ttl = 30  # Short TTL since metrics change frequently

    def collect(self) -> Any:
        """Collect system metrics."""
        try:
            return {
                "cpu": self._get_cpu_info(),
                "memory": self._get_memory_info(),
                "disk": self._get_disk_info(),
                "load_average": self._get_load_average(),
                "uptime": self._get_uptime(),
            }
        except Exception as e:
            logger.error(f"Failed to collect host metrics: {e}")
            raise

    def _get_cpu_info(self) -> dict:
        """Get CPU usage information."""
        try:
            # Get CPU percentages (per-core and overall)
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_percent_per_cpu = psutil.cpu_percent(interval=0, percpu=True)
            cpu_count = psutil.cpu_count()
            cpu_count_logical = psutil.cpu_count(logical=True)

            # CPU frequency if available
            cpu_freq = None
            try:
                freq = psutil.cpu_freq()
                if freq:
                    cpu_freq = {
                        "current": freq.current,
                        "min": freq.min,
                        "max": freq.max,
                    }
            except Exception:
                pass

            return {
                "percent": cpu_percent,
                "percent_per_cpu": cpu_percent_per_cpu,
                "count_physical": cpu_count,
                "count_logical": cpu_count_logical,
                "frequency": cpu_freq,
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU info: {e}")
            return {"percent": 0, "error": str(e)}

    def _get_memory_info(self) -> dict:
        """Get memory usage information."""
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return {
                "total": mem.total,
                "available": mem.available,
                "used": mem.used,
                "percent": mem.percent,
                "swap_total": swap.total,
                "swap_used": swap.used,
                "swap_percent": swap.percent,
                # Human-readable versions
                "total_human": self._bytes_to_human(mem.total),
                "available_human": self._bytes_to_human(mem.available),
                "used_human": self._bytes_to_human(mem.used),
            }
        except Exception as e:
            logger.warning(f"Failed to get memory info: {e}")
            return {"percent": 0, "error": str(e)}

    def _get_disk_info(self) -> dict:
        """Get disk usage information."""
        try:
            # Get root partition usage
            disk = psutil.disk_usage("/")

            # Get all disk partitions
            partitions = []
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent,
                    })
                except (PermissionError, OSError):
                    # Skip partitions we can't access
                    continue

            return {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent,
                "total_human": self._bytes_to_human(disk.total),
                "used_human": self._bytes_to_human(disk.used),
                "free_human": self._bytes_to_human(disk.free),
                "partitions": partitions,
            }
        except Exception as e:
            logger.warning(f"Failed to get disk info: {e}")
            return {"percent": 0, "error": str(e)}

    def _get_load_average(self) -> dict:
        """Get system load average."""
        try:
            load1, load5, load15 = os.getloadavg()
            cpu_count = psutil.cpu_count() or 1

            return {
                "load_1": round(load1, 2),
                "load_5": round(load5, 2),
                "load_15": round(load15, 2),
                # Normalized by CPU count
                "load_1_normalized": round(load1 / cpu_count * 100, 1),
                "load_5_normalized": round(load5 / cpu_count * 100, 1),
                "load_15_normalized": round(load15 / cpu_count * 100, 1),
            }
        except Exception as e:
            logger.warning(f"Failed to get load average: {e}")
            return {"load_1": 0, "load_5": 0, "load_15": 0, "error": str(e)}

    def _get_uptime(self) -> dict:
        """Get system uptime."""
        try:
            boot_time = psutil.boot_time()
            import time
            uptime_seconds = time.time() - boot_time

            days, remainder = divmod(uptime_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)

            return {
                "boot_time": boot_time,
                "uptime_seconds": int(uptime_seconds),
                "uptime_human": f"{int(days)}d {int(hours)}h {int(minutes)}m",
            }
        except Exception as e:
            logger.warning(f"Failed to get uptime: {e}")
            return {"uptime_seconds": 0, "error": str(e)}

    @staticmethod
    def _bytes_to_human(bytes_val: int) -> str:
        """Convert bytes to human-readable string."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(bytes_val) < 1024.0:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} PB"
