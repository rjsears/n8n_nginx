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
        "connections": [],
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

                # Try to get tunnel info
                try:
                    # Get tunnel status - cloudflared tunnel info requires tunnel name/id
                    # First try to get it from environment or config
                    env_vars = cf_container.attrs.get("Config", {}).get("Env", [])
                    for env in env_vars:
                        if env.startswith("TUNNEL_TOKEN="):
                            status_info["has_token"] = True
                        elif env.startswith("TUNNEL_NAME="):
                            status_info["tunnel_name"] = env.split("=", 1)[1]

                    # Try to get metrics/status from cloudflared
                    # cloudflared has a metrics endpoint on :2000/metrics by default
                    exit_code, output = cf_container.exec_run(
                        "wget -q -O- http://localhost:2000/ready 2>/dev/null || echo 'not_ready'",
                        demux=True
                    )
                    if exit_code == 0 and output[0]:
                        ready_output = output[0].decode("utf-8").strip()
                        status_info["ready"] = ready_output == "200 OK" or "ready" in ready_output.lower()

                    # Try to get connection info from metrics
                    exit_code, output = cf_container.exec_run(
                        "wget -q -O- http://localhost:2000/metrics 2>/dev/null | grep -E 'cloudflared_tunnel_|tunnel_server'",
                        demux=True
                    )
                    if exit_code == 0 and output[0]:
                        metrics = output[0].decode("utf-8")
                        # Parse some useful metrics
                        if "cloudflared_tunnel_active_streams" in metrics:
                            match = re.search(r'cloudflared_tunnel_active_streams\s+(\d+)', metrics)
                            if match:
                                status_info["active_streams"] = int(match.group(1))

                        # Look for connection info
                        conn_matches = re.findall(r'tunnel_server_locations\{.*?location="([^"]+)".*?\}', metrics)
                        if conn_matches:
                            status_info["locations"] = list(set(conn_matches))

                except Exception as e:
                    status_info["metrics_error"] = str(e)

                # Get recent logs for connection status
                try:
                    logs = cf_container.logs(tail=50).decode("utf-8")
                    if "Connection" in logs and "registered" in logs.lower():
                        status_info["connected"] = True
                    if "ERR" in logs or "error" in logs.lower():
                        # Get last error
                        for line in reversed(logs.split("\n")):
                            if "ERR" in line or "error" in line.lower():
                                status_info["last_error"] = line[:200]
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

                        # Peer info
                        peers = ts_status.get("Peer", {})
                        if peers:
                            peer_list = []
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

                                peer_list.append({
                                    "id": peer_id[:12] if peer_id else None,
                                    "hostname": hostname,
                                    "dns_name": dns_name,
                                    "ip": peer_info.get("TailscaleIPs", [None])[0],
                                    "online": is_online,
                                    "os": peer_info.get("OS"),
                                    "last_seen": peer_info.get("LastSeen"),
                                    "rx_bytes": peer_info.get("RxBytes"),
                                    "tx_bytes": peer_info.get("TxBytes"),
                                })
                            # Sort peers: online first, then by hostname
                            peer_list.sort(key=lambda p: (not p.get("online", False), p.get("hostname", "").lower()))
                            status_info["peers"] = peer_list
                            status_info["peer_count"] = len(peer_list)
                            status_info["online_peers"] = sum(1 for p in peer_list if p.get("online"))

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
