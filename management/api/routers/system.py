"""
System API routes - health, metrics, audit logs.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Dict, Any
from datetime import datetime, timedelta, UTC
import os
import psutil

from api.database import get_db, check_db_connection
from api.dependencies import get_current_user
from api.models.audit import AuditLog, SystemMetricsCache
from api.config import settings
from api.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    System health check endpoint.
    Does not require authentication.
    """
    db_status = "connected" if await check_db_connection() else "disconnected"

    # Check NFS if configured
    nfs_status = None
    if settings.nfs_server:
        nfs_status = "connected" if os.path.ismount(settings.nfs_mount_point) else "disconnected"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        version="3.0.0",
        service="n8n-management",
        database=db_status,
        nfs=nfs_status,
    )


@router.get("/metrics")
async def get_system_metrics(
    _=Depends(get_current_user),
):
    """Get current system metrics."""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()

    # Memory
    memory = psutil.virtual_memory()

    # Disk
    disk = psutil.disk_usage("/")

    # Network
    net_io = psutil.net_io_counters()

    # NFS if mounted
    nfs_metrics = None
    if settings.nfs_server and os.path.ismount(settings.nfs_mount_point):
        try:
            nfs_disk = psutil.disk_usage(settings.nfs_mount_point)
            nfs_metrics = {
                "total_bytes": nfs_disk.total,
                "used_bytes": nfs_disk.used,
                "free_bytes": nfs_disk.free,
                "percent": nfs_disk.percent,
            }
        except Exception:
            pass

    return {
        "cpu": {
            "percent": cpu_percent,
            "count": cpu_count,
        },
        "memory": {
            "total_bytes": memory.total,
            "available_bytes": memory.available,
            "used_bytes": memory.used,
            "percent": memory.percent,
        },
        "disk": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "percent": disk.percent,
        },
        "network": {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
        },
        "nfs": nfs_metrics,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/audit")
async def list_audit_logs(
    action: str = None,
    user_id: int = None,
    limit: int = 50,
    offset: int = 0,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get audit logs."""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())

    if action:
        query = query.where(AuditLog.action == action)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "username": log.username,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "ip_address": str(log.ip_address) if log.ip_address else None,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.get("/audit/actions")
async def list_audit_actions(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List distinct audit actions."""
    result = await db.execute(
        select(AuditLog.action).distinct().order_by(AuditLog.action)
    )
    return [row[0] for row in result.all()]


@router.get("/info")
async def get_system_info(
    _=Depends(get_current_user),
):
    """Get system information."""
    import platform

    # Get uptime
    boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=UTC)
    uptime = datetime.now(UTC) - boot_time

    return {
        "hostname": platform.node(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "boot_time": boot_time.isoformat(),
        "uptime_seconds": int(uptime.total_seconds()),
        "uptime_human": str(uptime).split(".")[0],  # Remove microseconds
    }


@router.get("/docker/info")
async def get_docker_info(
    _=Depends(get_current_user),
):
    """Get Docker daemon information."""
    try:
        import docker
        client = docker.from_env()
        info = client.info()

        return {
            "version": info.get("ServerVersion"),
            "containers": info.get("Containers"),
            "containers_running": info.get("ContainersRunning"),
            "containers_paused": info.get("ContainersPaused"),
            "containers_stopped": info.get("ContainersStopped"),
            "images": info.get("Images"),
            "driver": info.get("Driver"),
            "memory_total": info.get("MemTotal"),
            "cpus": info.get("NCPU"),
            "kernel_version": info.get("KernelVersion"),
            "operating_system": info.get("OperatingSystem"),
            "architecture": info.get("Architecture"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Docker info: {e}",
        )


@router.get("/timezone")
async def get_timezone(
    _=Depends(get_current_user),
):
    """Get configured timezone."""
    import zoneinfo

    tz_name = settings.timezone
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
        now = datetime.now(tz)
        return {
            "timezone": tz_name,
            "offset": now.strftime("%z"),
            "current_time": now.isoformat(),
        }
    except Exception:
        return {
            "timezone": tz_name,
            "offset": "unknown",
            "current_time": datetime.now(UTC).isoformat(),
        }


@router.get("/network")
async def get_network_info(
    _=Depends(get_current_user),
):
    """Get network configuration information from the Docker host."""
    import socket
    import subprocess
    import re

    # Try to get host network info via Docker (since we're in a container)
    try:
        import docker
        client = docker.from_env()

        # Run commands in a container with host networking to get real host info
        # Use alpine since it's small and likely already pulled for terminal
        commands = """
hostname
hostname -f 2>/dev/null || hostname
ip -4 addr show | grep -E 'inet [0-9]' | grep -v '127.0.0.1'
ip route | grep default | head -1
cat /etc/resolv.conf | grep nameserver
"""
        result = client.containers.run(
            "alpine:latest",
            command=["sh", "-c", commands],
            network_mode="host",
            remove=True,
            stdout=True,
            stderr=False,
        )

        output = result.decode("utf-8").strip()
        lines = output.split("\n")

        # Parse the output
        hostname = lines[0] if len(lines) > 0 else "unknown"
        fqdn = lines[1] if len(lines) > 1 else hostname

        # Parse interfaces from ip addr output
        interfaces = []
        current_iface = None
        for line in lines[2:]:
            line = line.strip()
            if not line:
                continue

            # Parse "inet 192.168.1.100/24 brd 192.168.1.255 scope global eth0"
            if line.startswith("inet "):
                match = re.match(
                    r'inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)\s+(?:brd\s+(\d+\.\d+\.\d+\.\d+)\s+)?.*?(\w+)$',
                    line
                )
                if match:
                    ip_addr = match.group(1)
                    prefix = int(match.group(2))
                    broadcast = match.group(3)
                    iface_name = match.group(4)

                    # Convert prefix to netmask
                    netmask = '.'.join([
                        str((0xffffffff << (32 - prefix) >> i) & 0xff)
                        for i in [24, 16, 8, 0]
                    ])

                    # Find or create interface entry
                    iface = next((i for i in interfaces if i["name"] == iface_name), None)
                    if not iface:
                        iface = {"name": iface_name, "addresses": []}
                        interfaces.append(iface)

                    iface["addresses"].append({
                        "type": "ipv4",
                        "address": ip_addr,
                        "netmask": netmask,
                        "broadcast": broadcast,
                    })

            # Parse gateway from "default via 192.168.1.1 dev eth0"
            elif line.startswith("default via"):
                match = re.search(r'default via (\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    gateway = match.group(1)

            # Parse DNS from "nameserver 8.8.8.8"
            elif line.startswith("nameserver"):
                parts = line.split()
                if len(parts) >= 2 and not parts[1].startswith("#"):
                    if "dns_servers" not in locals():
                        dns_servers = []
                    dns_servers.append(parts[1])

        # Ensure variables exist
        gateway = locals().get("gateway")
        dns_servers = locals().get("dns_servers", [])

        return {
            "hostname": hostname,
            "fqdn": fqdn,
            "interfaces": interfaces,
            "gateway": gateway,
            "dns_servers": dns_servers,
            "source": "host",
        }

    except Exception as e:
        # Fallback to container's own network info if Docker method fails
        import logging
        logging.getLogger(__name__).warning(f"Failed to get host network via Docker: {e}")

    # Fallback: get container's network info
    interfaces = []
    for name, addrs in psutil.net_if_addrs().items():
        # Skip loopback
        if name == "lo":
            continue

        iface_info = {"name": name, "addresses": []}
        for addr in addrs:
            if addr.family == socket.AF_INET:
                iface_info["addresses"].append({
                    "type": "ipv4",
                    "address": addr.address,
                    "netmask": addr.netmask,
                    "broadcast": addr.broadcast,
                })
            elif addr.family == socket.AF_INET6:
                iface_info["addresses"].append({
                    "type": "ipv6",
                    "address": addr.address,
                    "netmask": addr.netmask,
                })

        if iface_info["addresses"]:
            interfaces.append(iface_info)

    # Get default gateway
    gateway = None
    try:
        with open("/proc/net/route", "r") as f:
            for line in f.readlines()[1:]:
                parts = line.strip().split()
                if len(parts) >= 3 and parts[1] == "00000000":
                    gw_hex = parts[2]
                    gw_bytes = bytes.fromhex(gw_hex)
                    gateway = f"{gw_bytes[3]}.{gw_bytes[2]}.{gw_bytes[1]}.{gw_bytes[0]}"
                    break
    except Exception:
        pass

    # Get DNS servers from /etc/resolv.conf
    dns_servers = []
    try:
        with open("/etc/resolv.conf", "r") as f:
            for line in f:
                if line.strip().startswith("nameserver"):
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        dns_servers.append(parts[1])
    except Exception:
        pass

    # Get hostname
    hostname = socket.gethostname()
    try:
        fqdn = socket.getfqdn()
    except Exception:
        fqdn = hostname

    return {
        "hostname": hostname,
        "fqdn": fqdn,
        "interfaces": interfaces,
        "gateway": gateway,
        "dns_servers": dns_servers,
        "source": "container",
    }


@router.get("/ssl")
async def get_ssl_info(
    _=Depends(get_current_user),
):
    """Get SSL certificate information from the nginx container."""
    import re

    ssl_info = {
        "configured": False,
        "certificates": [],
    }

    def parse_cert_output(output: str, domain: str, cert_path: str) -> dict:
        """Parse openssl x509 output into certificate info dict."""
        cert_info = {
            "domain": domain,
            "path": cert_path,
            "type": "Let's Encrypt",
        }

        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("subject="):
                cert_info["subject"] = line.replace("subject=", "").strip()
            elif line.startswith("issuer="):
                cert_info["issuer"] = line.replace("issuer=", "").strip()
            elif line.startswith("notBefore="):
                cert_info["valid_from"] = line.replace("notBefore=", "").strip()
            elif line.startswith("notAfter="):
                cert_info["valid_until"] = line.replace("notAfter=", "").strip()
            elif "DNS:" in line:
                sans = [s.strip().replace("DNS:", "") for s in line.split(",") if "DNS:" in s]
                cert_info["san"] = sans

        # Calculate days until expiry
        if "valid_until" in cert_info:
            try:
                expiry = datetime.strptime(
                    cert_info["valid_until"],
                    "%b %d %H:%M:%S %Y %Z"
                )
                days_left = (expiry.replace(tzinfo=None) - datetime.now()).days
                cert_info["days_until_expiry"] = days_left
                cert_info["status"] = "valid" if days_left > 0 else "expired"
                if days_left <= 7:
                    cert_info["warning"] = "Certificate expiring soon!"
                elif days_left <= 30:
                    cert_info["warning"] = "Certificate expires within 30 days"
            except Exception:
                pass

        return cert_info

    # Try to get SSL info from nginx container
    try:
        import docker
        client = docker.from_env()

        # Find nginx container
        nginx_container = None
        for container in client.containers.list():
            if "nginx" in container.name.lower():
                nginx_container = container
                break

        if nginx_container:
            # First, list certificate directories
            try:
                exit_code, output = nginx_container.exec_run(
                    "ls /etc/letsencrypt/live/",
                    demux=True
                )
                if exit_code == 0 and output[0]:
                    domains = output[0].decode("utf-8").strip().split("\n")
                    domains = [d for d in domains if d and not d.startswith("README")]

                    for domain in domains:
                        cert_path = f"/etc/letsencrypt/live/{domain}/cert.pem"

                        # Get certificate info using openssl
                        exit_code, output = nginx_container.exec_run(
                            f"openssl x509 -in {cert_path} -noout -subject -issuer -dates -ext subjectAltName",
                            demux=True
                        )

                        if exit_code == 0 and output[0]:
                            cert_output = output[0].decode("utf-8")
                            cert_info = parse_cert_output(cert_output, domain, cert_path)
                            ssl_info["certificates"].append(cert_info)
                            ssl_info["configured"] = True

            except Exception as e:
                ssl_info["error"] = f"Failed to read certificates from nginx: {str(e)}"

            ssl_info["source"] = "nginx_container"
        else:
            ssl_info["error"] = "Nginx container not found"
            ssl_info["source"] = "none"

    except Exception as e:
        ssl_info["error"] = f"Docker error: {str(e)}"

    # Fallback: check local paths if no certs found via nginx
    if not ssl_info["configured"] and not ssl_info.get("error"):
        letsencrypt_path = "/etc/letsencrypt/live"
        try:
            if os.path.exists(letsencrypt_path):
                for domain_dir in os.listdir(letsencrypt_path):
                    if domain_dir.startswith("README"):
                        continue
                    cert_path = os.path.join(letsencrypt_path, domain_dir, "cert.pem")

                    if os.path.exists(cert_path):
                        import subprocess
                        result = subprocess.run(
                            ["openssl", "x509", "-in", cert_path, "-noout",
                             "-subject", "-issuer", "-dates", "-ext", "subjectAltName"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )

                        if result.returncode == 0:
                            cert_info = parse_cert_output(result.stdout, domain_dir, cert_path)
                            ssl_info["certificates"].append(cert_info)
                            ssl_info["configured"] = True
                            ssl_info["source"] = "local"

        except PermissionError:
            if not ssl_info.get("error"):
                ssl_info["error"] = "Permission denied reading certificate directory"
        except Exception as e:
            if not ssl_info.get("error"):
                ssl_info["error"] = str(e)

    return ssl_info


@router.get("/terminal/targets")
async def get_terminal_targets(
    _=Depends(get_current_user),
):
    """Get available terminal connection targets (containers)."""
    try:
        import docker
        client = docker.from_env()

        targets = []

        # Add option for host (if privileged mode is available)
        targets.append({
            "id": "host",
            "name": "Host System",
            "type": "host",
            "status": "available",
            "description": "Connect directly to the Docker host filesystem",
        })

        # List running containers
        containers = client.containers.list(all=False)  # Only running containers
        for container in containers:
            targets.append({
                "id": container.id[:12],
                "name": container.name,
                "type": "container",
                "status": container.status,
                "image": container.image.tags[0] if container.image.tags else "unknown",
            })

        return {"targets": targets}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list terminal targets: {e}",
        )


@router.get("/cloudflare")
async def get_cloudflare_status(
    _=Depends(get_current_user),
):
    """Get Cloudflare Tunnel status from cloudflared container."""
    import re

    status_info = {
        "installed": False,
        "running": False,
        "tunnel_name": None,
        "tunnel_id": None,
        "connector_id": None,
        "version": None,
        "connections": [],
        "metrics": {},
        "error": None,
    }

    try:
        import docker
        client = docker.from_env()

        # Find cloudflared container (common names: cloudflared, cloudflare-tunnel, cf-tunnel)
        cf_container = None
        for container in client.containers.list(all=True):
            name = container.name.lower()
            if "cloudflare" in name or "cloudflared" in name or "cf-tunnel" in name:
                cf_container = container
                break

        if cf_container:
            status_info["installed"] = True
            status_info["container_name"] = cf_container.name
            status_info["container_status"] = cf_container.status

            if cf_container.status == "running":
                status_info["running"] = True

                # Get cloudflared version
                try:
                    exit_code, output = cf_container.exec_run(
                        "cloudflared version",
                        demux=True
                    )
                    if exit_code == 0 and output[0]:
                        version_output = output[0].decode("utf-8").strip()
                        # Parse "cloudflared version 2024.1.0 (built 2024-01-15-1234)"
                        match = re.search(r'version\s+([\d.]+)', version_output)
                        if match:
                            status_info["version"] = match.group(1)
                except Exception:
                    pass

                # Get tunnel info from environment
                try:
                    env_vars = cf_container.attrs.get("Config", {}).get("Env", [])
                    for env in env_vars:
                        if env.startswith("TUNNEL_TOKEN="):
                            status_info["has_token"] = True
                        elif env.startswith("TUNNEL_NAME="):
                            status_info["tunnel_name"] = env.split("=", 1)[1]
                except Exception:
                    pass

                # Try to get metrics/status from cloudflared
                # cloudflared has a metrics endpoint on :2000/metrics by default
                try:
                    exit_code, output = cf_container.exec_run(
                        "wget -q -O- http://localhost:2000/ready 2>/dev/null || echo 'not_ready'",
                        demux=True
                    )
                    if exit_code == 0 and output[0]:
                        ready_output = output[0].decode("utf-8").strip()
                        status_info["ready"] = ready_output == "200 OK" or "ready" in ready_output.lower()
                except Exception:
                    pass

                # Get full metrics from Prometheus endpoint
                try:
                    exit_code, output = cf_container.exec_run(
                        "wget -q -O- http://localhost:2000/metrics 2>/dev/null",
                        demux=True
                    )
                    if exit_code == 0 and output[0]:
                        metrics_text = output[0].decode("utf-8")
                        metrics = status_info["metrics"]

                        # Active streams
                        match = re.search(r'cloudflared_tunnel_active_streams\s+(\d+)', metrics_text)
                        if match:
                            metrics["active_streams"] = int(match.group(1))

                        # Total requests
                        match = re.search(r'cloudflared_tunnel_total_requests\s+(\d+)', metrics_text)
                        if match:
                            metrics["total_requests"] = int(match.group(1))

                        # Request errors
                        match = re.search(r'cloudflared_tunnel_request_errors\s+(\d+)', metrics_text)
                        if match:
                            metrics["request_errors"] = int(match.group(1))

                        # HA connections (number of connections to Cloudflare edge)
                        match = re.search(r'cloudflared_tunnel_ha_connections\s+(\d+)', metrics_text)
                        if match:
                            metrics["ha_connections"] = int(match.group(1))

                        # Timer retries
                        match = re.search(r'cloudflared_tunnel_timer_retries\s+(\d+)', metrics_text)
                        if match:
                            metrics["connection_retries"] = int(match.group(1))

                        # Response codes - extract all status codes
                        response_codes = {}
                        for match in re.finditer(r'cloudflared_tunnel_response_by_code\{.*?status="(\d+)".*?\}\s+(\d+)', metrics_text):
                            code = match.group(1)
                            count = int(match.group(2))
                            if count > 0:
                                response_codes[code] = count
                        if response_codes:
                            metrics["response_codes"] = response_codes

                        # Edge locations (where tunnel is connected)
                        locations = []
                        for match in re.finditer(r'cloudflared_tunnel_server_locations\{.*?location="([^"]+)".*?\}\s+(\d+)', metrics_text):
                            loc = match.group(1)
                            count = int(match.group(2))
                            if count > 0 and loc not in locations:
                                locations.append(loc)
                        if locations:
                            status_info["edge_locations"] = locations

                        # Concurrent requests per tunnel
                        match = re.search(r'cloudflared_tunnel_concurrent_requests_per_tunnel\{.*?\}\s+(\d+)', metrics_text)
                        if match:
                            metrics["concurrent_requests"] = int(match.group(1))

                except Exception as e:
                    status_info["metrics_error"] = str(e)

                # Get recent logs for connection status and IDs
                try:
                    logs = cf_container.logs(tail=100).decode("utf-8")

                    # Check if connected
                    if "Connection" in logs and "registered" in logs.lower():
                        status_info["connected"] = True

                    # Extract tunnel ID from logs
                    # Format: "tunnelID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    tunnel_id_match = re.search(r'tunnelID=([a-f0-9-]{36})', logs)
                    if tunnel_id_match:
                        status_info["tunnel_id"] = tunnel_id_match.group(1)

                    # Extract connector ID
                    # Format: "connectorID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    connector_match = re.search(r'connectorID=([a-f0-9-]{36})', logs)
                    if connector_match:
                        status_info["connector_id"] = connector_match.group(1)

                    # Count connections per location from logs
                    # Format: "Registered tunnel connection" with location info
                    connection_events = []
                    for line in logs.split("\n"):
                        if "Registered tunnel connection" in line or "Connection registered" in line:
                            # Extract location like "location=lax"
                            loc_match = re.search(r'location=(\w+)', line)
                            if loc_match:
                                connection_events.append(loc_match.group(1))

                    if connection_events:
                        # Count connections per location
                        from collections import Counter
                        location_counts = Counter(connection_events)
                        status_info["connections_per_location"] = dict(location_counts)

                    # Get last error (skip common non-error warnings)
                    skip_patterns = [
                        "cert.pem",  # Token auth doesn't need cert
                        "Cannot determine default origin certificate",
                        "Update check",
                        "failed to sufficiently increase receive buffer size",
                    ]
                    for line in reversed(logs.split("\n")):
                        if "ERR" in line or "level=error" in line.lower():
                            # Check if it's a real error (not a common warning)
                            if any(skip in line for skip in skip_patterns):
                                continue
                            status_info["last_error"] = line[:200]
                            break

                    # Get tunnel uptime from logs (first registration time)
                    for line in logs.split("\n"):
                        if "Registered tunnel connection" in line or "Connection registered" in line:
                            # Try to extract timestamp
                            time_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
                            if time_match:
                                status_info["first_connection_time"] = time_match.group(1)
                            break

                except Exception:
                    pass

        else:
            status_info["error"] = "Cloudflare tunnel container not found"

    except Exception as e:
        status_info["error"] = f"Docker error: {str(e)}"

    return status_info


@router.get("/tailscale")
async def get_tailscale_status(
    _=Depends(get_current_user),
):
    """Get Tailscale status from tailscale container or host."""
    import json as json_module

    status_info = {
        "installed": False,
        "running": False,
        "logged_in": False,
        "tailscale_ip": None,
        "hostname": None,
        "dns_name": None,
        "peers": [],
        "error": None,
    }

    try:
        import docker
        client = docker.from_env()

        # Find tailscale container
        ts_container = None
        for container in client.containers.list(all=True):
            name = container.name.lower()
            if "tailscale" in name:
                ts_container = container
                break

        if ts_container:
            status_info["installed"] = True
            status_info["container_name"] = ts_container.name
            status_info["container_status"] = ts_container.status

            if ts_container.status == "running":
                status_info["running"] = True

                # Get tailscale status
                try:
                    exit_code, output = ts_container.exec_run(
                        "tailscale status --json",
                        demux=True
                    )

                    if exit_code == 0 and output[0]:
                        ts_status = json_module.loads(output[0].decode("utf-8"))

                        # Parse the status
                        status_info["logged_in"] = ts_status.get("BackendState") == "Running"
                        status_info["backend_state"] = ts_status.get("BackendState")

                        # Self info
                        self_info = ts_status.get("Self", {})
                        if self_info:
                            status_info["hostname"] = self_info.get("HostName")
                            status_info["dns_name"] = self_info.get("DNSName", "").rstrip(".")
                            status_info["user"] = self_info.get("UserID")
                            status_info["online"] = self_info.get("Online", False)

                            # Get Tailscale IPs
                            ts_ips = self_info.get("TailscaleIPs", [])
                            if ts_ips:
                                status_info["tailscale_ip"] = ts_ips[0]  # Primary IP
                                status_info["tailscale_ips"] = ts_ips

                        # Build device list including self and peers
                        device_list = []

                        # Add self as first device (this node)
                        if self_info:
                            self_dns = (self_info.get("DNSName") or "").strip().rstrip(".")
                            self_hostname = self_dns.split(".")[0] if self_dns else self_info.get("HostName", "this-node")
                            device_list.append({
                                "id": "self",
                                "hostname": self_hostname,
                                "dns_name": self_dns,
                                "ip": self_info.get("TailscaleIPs", [None])[0],
                                "online": self_info.get("Online", True),  # Self is always online if we can query it
                                "os": self_info.get("OS"),
                                "is_self": True,
                            })

                        # Add peers
                        peers = ts_status.get("Peer", {})
                        for peer_id, peer_info in peers.items():
                            # Check multiple fields for online status
                            # Tailscale uses "Online" but also check "Active" and "CurAddr"
                            is_online = (
                                peer_info.get("Online", False) or
                                peer_info.get("Active", False) or
                                bool(peer_info.get("CurAddr"))  # Has current address = connected
                            )

                            # Get the best available name
                            # Priority: DNSName (first part) > HostName > node key
                            # DNSName is more reliable as it's assigned by Tailscale
                            dns_name = (peer_info.get("DNSName") or "").strip().rstrip(".")
                            raw_hostname = (peer_info.get("HostName") or "").strip()

                            # Prefer DNS name's first component as it's the Tailscale machine name
                            if dns_name:
                                # Extract first part of DNS name (before first dot)
                                hostname = dns_name.split(".")[0]
                            elif raw_hostname and raw_hostname.lower() not in ("localhost", ""):
                                hostname = raw_hostname
                            else:
                                # Use shortened node key as fallback
                                hostname = peer_id[:8] if peer_id else "unknown"

                            device_list.append({
                                "id": peer_id[:12] if peer_id else None,
                                "hostname": hostname,
                                "dns_name": dns_name,
                                "ip": peer_info.get("TailscaleIPs", [None])[0],
                                "online": is_online,
                                "os": peer_info.get("OS"),
                                "last_seen": peer_info.get("LastSeen"),
                                "rx_bytes": peer_info.get("RxBytes"),
                                "tx_bytes": peer_info.get("TxBytes"),
                                "is_self": False,
                            })

                        # Sort: self first, then online devices, then by hostname
                        device_list.sort(key=lambda p: (
                            not p.get("is_self", False),  # Self always first
                            not p.get("online", False),   # Online before offline
                            p.get("hostname", "").lower()
                        ))
                        status_info["peers"] = device_list
                        status_info["peer_count"] = len(device_list)
                        status_info["online_peers"] = sum(1 for p in device_list if p.get("online"))

                        # Current tailnet
                        status_info["tailnet"] = ts_status.get("CurrentTailnet", {}).get("Name")

                except json_module.JSONDecodeError:
                    # Try plain text status
                    exit_code, output = ts_container.exec_run(
                        "tailscale status",
                        demux=True
                    )
                    if exit_code == 0 and output[0]:
                        status_info["status_text"] = output[0].decode("utf-8")
                        status_info["logged_in"] = True

                except Exception as e:
                    status_info["status_error"] = str(e)

        else:
            # Try host tailscale via alpine container with host networking
            try:
                result = client.containers.run(
                    "alpine:latest",
                    command=["sh", "-c", "which tailscale && tailscale status --json 2>/dev/null || echo 'not_found'"],
                    network_mode="host",
                    remove=True,
                    stdout=True,
                    stderr=False,
                )
                output = result.decode("utf-8").strip()
                if output != "not_found" and output:
                    try:
                        # Skip first line if it's the path
                        lines = output.split("\n")
                        json_start = 0
                        for i, line in enumerate(lines):
                            if line.strip().startswith("{"):
                                json_start = i
                                break
                        json_output = "\n".join(lines[json_start:])
                        ts_status = json_module.loads(json_output)
                        status_info["installed"] = True
                        status_info["running"] = True
                        status_info["source"] = "host"
                        # Parse same as above
                        status_info["logged_in"] = ts_status.get("BackendState") == "Running"
                        self_info = ts_status.get("Self", {})
                        if self_info:
                            status_info["hostname"] = self_info.get("HostName")
                            status_info["tailscale_ip"] = self_info.get("TailscaleIPs", [None])[0]
                    except Exception:
                        pass
            except Exception:
                status_info["error"] = "Tailscale not found (no container or host installation)"

    except Exception as e:
        status_info["error"] = f"Docker error: {str(e)}"

    return status_info


@router.get("/health/full")
async def get_full_health_check(
    _=Depends(get_current_user),
):
    """
    Comprehensive system health check - checks all components.
    Returns detailed health status for containers, databases, services, resources, and more.
    """
    import socket
    import re

    health_data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "3.0.0",
        "overall_status": "healthy",
        "warnings": 0,
        "errors": 0,
        "checks": {},
    }

    def add_check(category: str, name: str, status: str, message: str, details: dict = None):
        """Add a health check result."""
        if category not in health_data["checks"]:
            health_data["checks"][category] = []

        check = {
            "name": name,
            "status": status,  # healthy, warning, error
            "message": message,
        }
        if details:
            check["details"] = details

        health_data["checks"][category].append(check)

        if status == "warning":
            health_data["warnings"] += 1
        elif status == "error":
            health_data["errors"] += 1

    try:
        import docker
        client = docker.from_env()

        # ========================================
        # Docker Container Health
        # ========================================
        try:
            # Check Docker daemon
            client.ping()
            add_check("docker", "docker_daemon", "healthy", "Docker daemon is running")

            # Get all containers
            containers = client.containers.list(all=True)
            core_containers = ["n8n", "n8n_postgres", "n8n_nginx", "n8n_management"]

            container_memory = {}
            for container in containers:
                name = container.name

                # Check if running
                if container.status == "running":
                    add_check("docker", f"container_{name}", "healthy", f"Container {name} is running")

                    # Check health status if available
                    health = container.attrs.get("State", {}).get("Health", {})
                    health_status = health.get("Status", "none")
                    if health_status == "healthy":
                        add_check("docker", f"health_{name}", "healthy", f"Container {name} health check: healthy")
                    elif health_status == "unhealthy":
                        add_check("docker", f"health_{name}", "error", f"Container {name} health check: unhealthy")
                    elif health_status == "starting":
                        add_check("docker", f"health_{name}", "warning", f"Container {name} health check: starting")

                    # Get memory usage
                    try:
                        stats = container.stats(stream=False)
                        memory_stats = stats.get("memory_stats", {})
                        memory_usage = memory_stats.get("usage", 0)
                        memory_limit = memory_stats.get("limit", 0)
                        if memory_usage and memory_limit:
                            container_memory[name] = {
                                "usage_mb": round(memory_usage / (1024 * 1024), 1),
                                "limit_mb": round(memory_limit / (1024 * 1024), 1),
                                "percent": round((memory_usage / memory_limit) * 100, 1) if memory_limit else 0,
                            }
                    except Exception:
                        pass

                elif name in core_containers:
                    add_check("docker", f"container_{name}", "error", f"Container {name} is not running")

            health_data["container_memory"] = container_memory

        except Exception as e:
            add_check("docker", "docker_daemon", "error", f"Docker error: {str(e)}")

        # ========================================
        # n8n API Health
        # ========================================
        try:
            nginx_container = None
            for c in client.containers.list():
                if "nginx" in c.name.lower():
                    nginx_container = c
                    break

            if nginx_container:
                exit_code, output = nginx_container.exec_run(
                    "curl -s -o /dev/null -w '%{http_code}' http://n8n:5678/healthz",
                    demux=True
                )
                if exit_code == 0 and output[0]:
                    status_code = output[0].decode("utf-8").strip()
                    if status_code == "200":
                        add_check("services", "n8n_api", "healthy", "n8n API is responding")
                    else:
                        add_check("services", "n8n_api", "warning", f"n8n API returned status {status_code}")
                else:
                    add_check("services", "n8n_api", "error", "n8n API is not responding")
            else:
                add_check("services", "n8n_api", "warning", "Cannot check n8n API (nginx not found)")

        except Exception as e:
            add_check("services", "n8n_api", "error", f"n8n API check failed: {str(e)}")

        # ========================================
        # PostgreSQL Health
        # ========================================
        try:
            postgres_container = None
            for c in client.containers.list():
                if "postgres" in c.name.lower():
                    postgres_container = c
                    break

            if postgres_container:
                exit_code, output = postgres_container.exec_run(
                    "pg_isready -U postgres",
                    demux=True
                )
                if exit_code == 0:
                    add_check("database", "postgres", "healthy", "PostgreSQL is accepting connections")

                    exit_code, output = postgres_container.exec_run(
                        "psql -U postgres -d n8n -c 'SELECT 1' -t",
                        demux=True
                    )
                    if exit_code == 0:
                        add_check("database", "postgres_n8n_db", "healthy", "n8n database is accessible")
                    else:
                        add_check("database", "postgres_n8n_db", "error", "n8n database is not accessible")

                    exit_code, output = postgres_container.exec_run(
                        "psql -U postgres -d n8n_management -c 'SELECT 1' -t",
                        demux=True
                    )
                    if exit_code == 0:
                        add_check("database", "postgres_mgmt_db", "healthy", "Management database is accessible")
                    else:
                        add_check("database", "postgres_mgmt_db", "error", "Management database is not accessible")
                else:
                    add_check("database", "postgres", "error", "PostgreSQL is not accepting connections")
            else:
                add_check("database", "postgres", "error", "PostgreSQL container not found")

        except Exception as e:
            add_check("database", "postgres", "error", f"PostgreSQL check failed: {str(e)}")

        # ========================================
        # Nginx Health
        # ========================================
        try:
            nginx_container = None
            for c in client.containers.list():
                if "nginx" in c.name.lower() and "n8n" in c.name.lower():
                    nginx_container = c
                    break

            if nginx_container:
                exit_code, output = nginx_container.exec_run("nginx -t", demux=True)
                if exit_code == 0:
                    add_check("services", "nginx_config", "healthy", "Nginx configuration is valid")
                else:
                    error_msg = output[1].decode("utf-8") if output[1] else "Unknown error"
                    add_check("services", "nginx_config", "error", f"Nginx config error: {error_msg[:100]}")

                exit_code, output = nginx_container.exec_run(
                    "curl -s -o /dev/null -w '%{http_code}' -k https://localhost/management/api/health",
                    demux=True
                )
                if exit_code == 0 and output[0]:
                    status_code = output[0].decode("utf-8").strip()
                    if status_code in ["200", "301", "302"]:
                        add_check("services", "nginx_https", "healthy", "Nginx HTTPS is responding")
                    else:
                        add_check("services", "nginx_https", "warning", f"Nginx HTTPS returned {status_code}")
                else:
                    add_check("services", "nginx_https", "warning", "Nginx HTTPS check inconclusive")

        except Exception as e:
            add_check("services", "nginx", "error", f"Nginx check failed: {str(e)}")

        # Management API
        add_check("services", "management_api", "healthy", "Management API is responding")

        # ========================================
        # System Resources
        # ========================================
        try:
            disk = psutil.disk_usage("/")
            disk_percent = disk.percent
            disk_details = {
                "total_gb": round(disk.total / (1024**3), 1),
                "used_gb": round(disk.used / (1024**3), 1),
                "free_gb": round(disk.free / (1024**3), 1),
                "percent": disk_percent,
            }

            if disk_percent >= 90:
                add_check("resources", "disk_root", "error", f"Disk usage critical: {disk_percent}%", disk_details)
            elif disk_percent >= 80:
                add_check("resources", "disk_root", "warning", f"Disk usage high: {disk_percent}%", disk_details)
            else:
                add_check("resources", "disk_root", "healthy", f"Disk usage: {disk_percent}%", disk_details)

            try:
                df_result = client.df()
                docker_usage = 0
                for image in df_result.get("Images", []):
                    docker_usage += image.get("Size", 0)
                docker_gb = round(docker_usage / (1024**3), 2)
                health_data["docker_disk_usage_gb"] = docker_gb
            except Exception:
                pass

        except Exception as e:
            add_check("resources", "disk_root", "error", f"Disk check failed: {str(e)}")

        try:
            memory = psutil.virtual_memory()
            memory_details = {
                "total_mb": round(memory.total / (1024**2)),
                "used_mb": round(memory.used / (1024**2)),
                "available_mb": round(memory.available / (1024**2)),
                "percent": memory.percent,
            }

            if memory.percent >= 90:
                add_check("resources", "memory", "error", f"Memory usage critical: {memory.percent}%", memory_details)
            elif memory.percent >= 80:
                add_check("resources", "memory", "warning", f"Memory usage high: {memory.percent}%", memory_details)
            else:
                add_check("resources", "memory", "healthy", f"Memory usage: {memory.percent}%", memory_details)

        except Exception as e:
            add_check("resources", "memory", "error", f"Memory check failed: {str(e)}")

        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg()
            cpu_details = {
                "percent": cpu_percent,
                "count": cpu_count,
                "load_1m": round(load_avg[0], 2),
                "load_5m": round(load_avg[1], 2),
                "load_15m": round(load_avg[2], 2),
                "load_percent": round((load_avg[0] / cpu_count) * 100, 1) if cpu_count else 0,
            }

            if cpu_details["load_percent"] >= 90:
                add_check("resources", "cpu", "error", f"CPU load critical: {cpu_details['load_percent']}%", cpu_details)
            elif cpu_details["load_percent"] >= 80:
                add_check("resources", "cpu", "warning", f"CPU load high: {cpu_details['load_percent']}%", cpu_details)
            else:
                add_check("resources", "cpu", "healthy", f"CPU load: {cpu_details['load_percent']}%", cpu_details)

        except Exception as e:
            add_check("resources", "cpu", "error", f"CPU check failed: {str(e)}")

        # ========================================
        # SSL Certificates
        # ========================================
        try:
            nginx_container = None
            for c in client.containers.list():
                if "nginx" in c.name.lower():
                    nginx_container = c
                    break

            if nginx_container:
                exit_code, output = nginx_container.exec_run("ls /etc/letsencrypt/live/", demux=True)
                if exit_code == 0 and output[0]:
                    domains = [d for d in output[0].decode("utf-8").strip().split("\n")
                               if d and not d.startswith("README")]

                    ssl_certs = []
                    for domain in domains:
                        cert_path = f"/etc/letsencrypt/live/{domain}/cert.pem"
                        exit_code, output = nginx_container.exec_run(
                            f"openssl x509 -in {cert_path} -noout -dates -subject",
                            demux=True
                        )
                        if exit_code == 0 and output[0]:
                            cert_output = output[0].decode("utf-8")
                            expiry_match = re.search(r'notAfter=(.+)', cert_output)
                            if expiry_match:
                                expiry_str = expiry_match.group(1).strip()
                                try:
                                    expiry_date = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
                                    days_left = (expiry_date - datetime.now()).days

                                    cert_info = {"domain": domain, "expires": expiry_str, "days_left": days_left}
                                    ssl_certs.append(cert_info)

                                    if days_left <= 7:
                                        add_check("ssl", f"cert_{domain}", "error",
                                                  f"SSL certificate expires in {days_left} days!", cert_info)
                                    elif days_left <= 30:
                                        add_check("ssl", f"cert_{domain}", "warning",
                                                  f"SSL certificate expires in {days_left} days", cert_info)
                                    else:
                                        add_check("ssl", f"cert_{domain}", "healthy",
                                                  f"SSL certificate valid for {days_left} days", cert_info)
                                except Exception:
                                    pass

                    health_data["ssl_certificates"] = ssl_certs

        except Exception as e:
            add_check("ssl", "ssl_check", "warning", f"SSL check failed: {str(e)}")

        # ========================================
        # Network Connectivity
        # ========================================
        try:
            try:
                socket.gethostbyname("google.com")
                add_check("network", "dns", "healthy", "DNS resolution working")
            except Exception:
                add_check("network", "dns", "error", "DNS resolution failed")

            if nginx_container:
                exit_code, output = nginx_container.exec_run(
                    "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 https://registry.npmjs.org/",
                    demux=True
                )
                if exit_code == 0 and output[0]:
                    status_code = output[0].decode("utf-8").strip()
                    if status_code == "200":
                        add_check("network", "internet", "healthy", "Internet connectivity OK")
                    else:
                        add_check("network", "internet", "warning", f"Internet check returned {status_code}")
                else:
                    add_check("network", "internet", "warning", "Internet connectivity check inconclusive")

        except Exception as e:
            add_check("network", "network_check", "warning", f"Network check failed: {str(e)}")

        # ========================================
        # Backup Status
        # ========================================
        try:
            backup_paths = ["/backups", "/var/backups", "./backups"]
            backup_found = False

            for path in backup_paths:
                if os.path.exists(path) and os.path.isdir(path):
                    backup_found = True
                    files = os.listdir(path)
                    if files:
                        add_check("backups", "backup_status", "healthy", f"Backup directory exists with {len(files)} files")
                    else:
                        add_check("backups", "backup_status", "warning", "Backup directory is empty")
                    break

            if not backup_found:
                add_check("backups", "backup_status", "warning", "Backup directory does not exist")

        except Exception as e:
            add_check("backups", "backup_status", "warning", f"Backup check failed: {str(e)}")

        # ========================================
        # Recent Error Analysis
        # ========================================
        try:
            for container in client.containers.list():
                if container.name in ["n8n", "n8n_nginx"]:
                    logs = container.logs(since=datetime.now(UTC) - timedelta(hours=1)).decode("utf-8")
                    error_count = len([line for line in logs.split("\n") if "error" in line.lower() or "ERR" in line])

                    log_name = container.name.replace("n8n_", "")
                    if error_count == 0:
                        add_check("logs", f"logs_{log_name}", "healthy", f"{log_name}: 0 errors in last hour")
                    elif error_count < 10:
                        add_check("logs", f"logs_{log_name}", "warning",
                                  f"{log_name}: {error_count} errors in last hour", {"error_count": error_count})
                    else:
                        add_check("logs", f"logs_{log_name}", "error",
                                  f"{log_name}: {error_count} errors in last hour", {"error_count": error_count})

        except Exception as e:
            add_check("logs", "log_check", "warning", f"Log analysis failed: {str(e)}")

    except Exception as e:
        health_data["overall_status"] = "error"
        health_data["error"] = str(e)

    # Determine overall status
    if health_data["errors"] > 0:
        health_data["overall_status"] = "error"
    elif health_data["warnings"] > 0:
        health_data["overall_status"] = "warning"
    else:
        health_data["overall_status"] = "healthy"

    return health_data
