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

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_alpine_container_sync(docker_client, command: list, **kwargs) -> bytes:
    """
    Run an alpine container with guaranteed cleanup.

    Uses detach mode with manual cleanup to ensure containers don't get orphaned
    even if remove=True fails due to exceptions or timeouts.
    """
    container = None
    try:
        # Don't use remove=True - we'll handle cleanup manually
        kwargs.pop("remove", None)

        container = docker_client.containers.run(
            "alpine:latest",
            command=command,
            detach=True,
            **kwargs
        )

        # Wait for container to complete (timeout after 30 seconds)
        result = container.wait(timeout=30)

        # Get logs before removing
        output = container.logs(stdout=True, stderr=False)

        return output

    except Exception as e:
        logger.debug(f"Alpine container error: {e}")
        raise

    finally:
        # Always try to clean up the container
        if container:
            try:
                container.remove(force=True)
            except Exception as cleanup_err:
                logger.debug(f"Failed to remove container: {cleanup_err}")


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
        result = _run_alpine_container_sync(
            client,
            command=["sh", "-c", commands],
            network_mode="host",
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


@router.post("/ssl/renew")
async def force_renew_ssl_certificate(
    _=Depends(get_current_user),
):
    """
    Force renewal of SSL certificates using certbot.
    After successful renewal, nginx is reloaded to apply new certificates.
    """
    import docker
    import logging

    logger = logging.getLogger(__name__)
    result = {
        "success": False,
        "message": "",
        "renewal_output": "",
        "nginx_reloaded": False,
    }

    try:
        client = docker.from_env()

        # Find certbot container
        try:
            certbot_container = client.containers.get("n8n_certbot")
        except docker.errors.NotFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Certbot container (n8n_certbot) not found. Is it running?",
            )

        if certbot_container.status != "running":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Certbot container is not running (status: {certbot_container.status})",
            )

        # Run certbot renew --force-renewal
        logger.info("Starting forced SSL certificate renewal...")
        exec_result = certbot_container.exec_run(
            cmd="certbot renew --force-renewal",
            demux=True,
        )

        stdout = exec_result.output[0].decode("utf-8") if exec_result.output[0] else ""
        stderr = exec_result.output[1].decode("utf-8") if exec_result.output[1] else ""
        renewal_output = stdout + stderr

        result["renewal_output"] = renewal_output

        if exec_result.exit_code != 0:
            logger.error(f"Certbot renewal failed with exit code {exec_result.exit_code}: {renewal_output}")
            result["message"] = f"Certificate renewal failed (exit code {exec_result.exit_code})"
            return result

        logger.info("Certificate renewal completed successfully")

        # Now reload nginx to apply new certificates
        try:
            nginx_container = client.containers.get("n8n_nginx")
            if nginx_container.status == "running":
                reload_result = nginx_container.exec_run(
                    cmd="nginx -s reload",
                    demux=True,
                )
                if reload_result.exit_code == 0:
                    result["nginx_reloaded"] = True
                    logger.info("Nginx reloaded successfully")
                else:
                    reload_err = reload_result.output[1].decode("utf-8") if reload_result.output[1] else ""
                    logger.warning(f"Nginx reload failed: {reload_err}")
                    result["message"] = "Certificate renewed but nginx reload failed"
                    result["success"] = True  # Renewal succeeded even if reload failed
                    return result
        except docker.errors.NotFound:
            logger.warning("Nginx container not found for reload")
            result["message"] = "Certificate renewed but nginx container not found for reload"
            result["success"] = True
            return result

        result["success"] = True
        result["message"] = "Certificate renewed and nginx reloaded successfully"
        return result

    except docker.errors.APIError as e:
        logger.error(f"Docker API error during certificate renewal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Docker error: {str(e)}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during certificate renewal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


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


@router.get("/external-services")
async def get_external_services(
    _=Depends(get_current_user),
):
    """Detect external services from nginx.conf location blocks."""
    import re

    # Known services with their metadata
    known_services = {
        "portainer": {
            "name": "Portainer",
            "description": "Docker container management",
            "color": "bg-blue-100 dark:bg-blue-500/20",
            "icon_color": "text-blue-500",
        },
        "dozzle": {
            "name": "Dozzle",
            "description": "Real-time Docker log viewer",
            "color": "bg-emerald-100 dark:bg-emerald-500/20",
            "icon_color": "text-emerald-500",
        },
        "adminer": {
            "name": "Adminer",
            "description": "Database management",
            "color": "bg-amber-100 dark:bg-amber-500/20",
            "icon_color": "text-amber-500",
        },
        "pgadmin": {
            "name": "pgAdmin",
            "description": "PostgreSQL administration",
            "color": "bg-indigo-100 dark:bg-indigo-500/20",
            "icon_color": "text-indigo-500",
        },
        "grafana": {
            "name": "Grafana",
            "description": "Monitoring & observability",
            "color": "bg-orange-100 dark:bg-orange-500/20",
            "icon_color": "text-orange-500",
        },
        "prometheus": {
            "name": "Prometheus",
            "description": "Metrics & alerting",
            "color": "bg-red-100 dark:bg-red-500/20",
            "icon_color": "text-red-500",
        },
        "traefik": {
            "name": "Traefik Dashboard",
            "description": "Reverse proxy dashboard",
            "color": "bg-cyan-100 dark:bg-cyan-500/20",
            "icon_color": "text-cyan-500",
        },
        "n8n": {
            "name": "n8n",
            "description": "Workflow automation",
            "color": "bg-rose-100 dark:bg-rose-500/20",
            "icon_color": "text-rose-500",
        },
    }

    services = []

    try:
        import docker
        client = docker.from_env()

        # Get nginx container to read config
        nginx_container = None
        try:
            nginx_container = client.containers.get("n8n_nginx")
        except Exception:
            pass

        if nginx_container:
            # Read nginx.conf to find location blocks
            exit_code, output = nginx_container.exec_run(
                "cat /etc/nginx/nginx.conf",
                demux=True
            )

            if exit_code == 0 and output[0]:
                nginx_conf = output[0].decode("utf-8")

                # Find all location blocks like: location /dozzle/ { or location /adminer {
                # Pattern matches location /path or location /path/
                location_pattern = r'location\s+(/[a-zA-Z0-9_-]+)/?[\s{]'
                locations = re.findall(location_pattern, nginx_conf)

                # Get running containers to check service status
                running_containers = {c.name.lower(): c for c in client.containers.list(all=False)}

                for location in locations:
                    path = location.strip('/')
                    path_lower = path.lower()

                    # Check if this is a known service
                    for service_key, service_info in known_services.items():
                        if service_key in path_lower or path_lower in service_key:
                            # Check if container is running
                            running = False
                            for container_name in running_containers:
                                if service_key in container_name:
                                    running = True
                                    break

                            services.append({
                                "name": service_info["name"],
                                "description": service_info["description"],
                                "path": f"/{path}",
                                "running": running,
                                "color": service_info["color"],
                                "iconColor": service_info["icon_color"],
                            })
                            break

    except Exception as e:
        return {"services": [], "error": str(e)}

    # Remove duplicates (keep first occurrence)
    seen = set()
    unique_services = []
    for s in services:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique_services.append(s)

    return {"services": unique_services}


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
                    # Try curl first (more common), then wget
                    exit_code, output = cf_container.exec_run(
                        "curl -s http://localhost:2000/metrics 2>/dev/null || wget -q -O- http://localhost:2000/metrics 2>/dev/null",
                        demux=True
                    )
                    metrics_text = None
                    if exit_code == 0 and output[0]:
                        metrics_text = output[0].decode("utf-8")

                    if metrics_text and len(metrics_text) > 100:
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
                    else:
                        status_info["metrics_error"] = "No metrics data available (port 2000 may not be exposed)"

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
                        # Use as fallback for edge_locations if not set from metrics
                        if "edge_locations" not in status_info:
                            status_info["edge_locations"] = list(location_counts.keys())

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
                result = _run_alpine_container_sync(
                    client,
                    command=["sh", "-c", "which tailscale && tailscale status --json 2>/dev/null || echo 'not_found'"],
                    network_mode="host",
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
    quick: bool = False,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Comprehensive system health check - checks all components.
    Returns detailed health status for containers, databases, services, resources, and more.
    Mirrors the functionality of health_check.sh script.

    Args:
        quick: If True, skip slower checks (SSL details, log analysis) for faster response
    """
    import socket
    import re

    health_data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "3.0.0",
        "overall_status": "healthy",
        "warnings": 0,
        "errors": 0,
        "passed": 0,
        "checks": {},
        "container_memory": {},
        "ssl_certificates": [],
        "ssl_configured": False,
        "docker_disk_usage_gb": 0,
    }

    def set_check(category: str, status: str, details: dict = None):
        """Set a category's health check result."""
        # Normalize status: healthy -> ok
        normalized_status = "ok" if status == "healthy" else status

        health_data["checks"][category] = {
            "status": normalized_status,
            "details": details or {},
        }

        if status == "warning":
            health_data["warnings"] += 1
        elif status == "error":
            health_data["errors"] += 1
        else:
            health_data["passed"] += 1

    try:
        import docker
        client = docker.from_env()

        # ========================================
        # Docker Container Health
        # ========================================
        docker_details = {
            "running": 0,
            "stopped": 0,
            "unhealthy": 0,
            "unhealthy_containers": [],
        }
        docker_status = "healthy"
        container_memory = {}

        try:
            # Check Docker daemon
            client.ping()

            # Get all containers
            containers = client.containers.list(all=True)
            core_containers = ["n8n", "n8n_postgres", "n8n_nginx", "n8n_management"]

            for container in containers:
                name = container.name

                if container.status == "running":
                    docker_details["running"] += 1

                    # Check health status if available
                    health = container.attrs.get("State", {}).get("Health", {})
                    health_status = health.get("Status", "none")
                    if health_status == "unhealthy":
                        docker_details["unhealthy"] += 1
                        docker_details["unhealthy_containers"].append(name)
                        docker_status = "error"

                    # Get memory usage from container attrs (faster than stats API)
                    # Skip detailed stats collection as it's slow (~2-5s per container)
                    try:
                        # Try to get memory from inspect data if available
                        host_config = container.attrs.get("HostConfig", {})
                        memory_limit = host_config.get("Memory", 0)
                        if memory_limit:
                            container_memory[name] = round(memory_limit / (1024 * 1024), 1)
                    except Exception:
                        pass
                else:
                    docker_details["stopped"] += 1
                    if name in core_containers:
                        docker_status = "error"

            health_data["container_memory"] = container_memory

        except Exception as e:
            docker_status = "error"
            docker_details["error"] = str(e)

        set_check("docker", docker_status, docker_details)

        # ========================================
        # Core Services Health (n8n, Nginx, Management)
        # ========================================
        services_details = {}
        services_status = "healthy"

        # Find nginx container for checks
        nginx_container = None
        for c in client.containers.list():
            if "nginx" in c.name.lower():
                nginx_container = c
                break

        # Check n8n API (with timeout)
        try:
            if nginx_container:
                exit_code, output = nginx_container.exec_run(
                    "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 10 http://n8n:5678/healthz",
                    demux=True
                )
                if exit_code == 0 and output[0]:
                    status_code = output[0].decode("utf-8").strip()
                    if status_code == "200":
                        services_details["n8n_api"] = "ok"
                    else:
                        services_details["n8n_api"] = f"error (HTTP {status_code})"
                        services_status = "error"
                else:
                    services_details["n8n_api"] = "error (no response)"
                    services_status = "error"
            else:
                services_details["n8n_api"] = "unknown (nginx not found)"
        except Exception as e:
            services_details["n8n_api"] = f"error ({type(e).__name__})"
            services_status = "error"

        # Check Nginx
        try:
            if nginx_container:
                exit_code, output = nginx_container.exec_run("nginx -t", demux=True)
                if exit_code == 0:
                    services_details["nginx"] = "ok"
                else:
                    stderr = output[1].decode("utf-8").strip() if output[1] else "unknown error"
                    services_details["nginx"] = f"error ({stderr[:50]})"
                    services_status = "error"
            else:
                services_details["nginx"] = "error (container not found)"
                services_status = "error"
        except Exception as e:
            services_details["nginx"] = f"error ({type(e).__name__})"
            services_status = "error"

        # Management API (we're running, so it's ok)
        services_details["management"] = "ok"

        set_check("services", services_status, services_details)

        # ========================================
        # PostgreSQL Health (dynamically get user from container environment)
        # ========================================
        database_details = {}
        database_status = "healthy"

        try:
            postgres_container = None
            for c in client.containers.list():
                if "postgres" in c.name.lower():
                    postgres_container = c
                    break

            if postgres_container:
                # Get the database user from container environment
                # Default to 'n8n' but check POSTGRES_USER env var
                db_user = "n8n"  # default
                try:
                    env_vars = postgres_container.attrs.get("Config", {}).get("Env", [])
                    for env in env_vars:
                        if env.startswith("POSTGRES_USER="):
                            db_user = env.split("=", 1)[1]
                            break
                except Exception:
                    pass

                database_details["user"] = db_user

                # Check if PostgreSQL is accepting connections
                exit_code, _ = postgres_container.exec_run(
                    f"pg_isready -U {db_user}",
                    demux=True
                )
                if exit_code == 0:
                    database_details["connection"] = "ok"

                    # Check n8n database
                    exit_code, _ = postgres_container.exec_run(
                        f"psql -U {db_user} -d n8n -c 'SELECT 1' -t",
                        demux=True
                    )
                    if exit_code == 0:
                        database_details["n8n_db"] = "ok"
                    else:
                        database_details["n8n_db"] = "error"
                        database_status = "error"

                    # Check management database
                    exit_code, _ = postgres_container.exec_run(
                        f"psql -U {db_user} -d n8n_management -c 'SELECT 1' -t",
                        demux=True
                    )
                    if exit_code == 0:
                        database_details["management_db"] = "ok"
                    else:
                        database_details["management_db"] = "warning"
                        if database_status == "healthy":
                            database_status = "warning"

                    # Get version
                    exit_code, output = postgres_container.exec_run(
                        f"psql -U {db_user} -d n8n -c 'SELECT version()' -t",
                        demux=True
                    )
                    if exit_code == 0 and output[0]:
                        version_str = output[0].decode("utf-8").strip()
                        # Extract just the version number
                        match = re.search(r'PostgreSQL (\d+\.\d+)', version_str)
                        if match:
                            database_details["version"] = match.group(1)

                    # Also expose as 'query' for frontend compatibility
                    database_details["query"] = database_details.get("n8n_db", "error")
                else:
                    database_details["connection"] = "error"
                    database_status = "error"
            else:
                database_details["connection"] = "error"
                database_status = "error"

        except Exception as e:
            database_details["connection"] = "error"
            database_details["error"] = str(e)
            database_status = "error"

        set_check("database", database_status, database_details)

        # ========================================
        # System Resources
        # ========================================
        resources_details = {}
        resources_status = "healthy"

        try:
            # Disk
            disk = psutil.disk_usage("/")
            resources_details["disk_percent"] = round(disk.percent, 1)
            resources_details["disk_free_gb"] = round(disk.free / (1024**3), 1)
            resources_details["disk_total_gb"] = round(disk.total / (1024**3), 1)

            if disk.percent >= 90:
                resources_status = "error"
            elif disk.percent >= 80:
                if resources_status == "healthy":
                    resources_status = "warning"

            # Memory
            memory = psutil.virtual_memory()
            resources_details["memory_percent"] = round(memory.percent, 1)
            resources_details["memory_total_mb"] = round(memory.total / (1024**2))
            resources_details["memory_available_mb"] = round(memory.available / (1024**2))

            if memory.percent >= 90:
                resources_status = "error"
            elif memory.percent >= 80:
                if resources_status == "healthy":
                    resources_status = "warning"

            # CPU (use interval=0.1 for faster response, interval=None uses cached value)
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg()
            load_percent = round((load_avg[0] / cpu_count) * 100, 1) if cpu_count else 0

            resources_details["cpu_percent"] = round(cpu_percent, 1)
            resources_details["cpu_count"] = cpu_count
            resources_details["load_1m"] = round(load_avg[0], 2)
            resources_details["load_percent"] = load_percent

            if load_percent >= 90:
                resources_status = "error"
            elif load_percent >= 80:
                if resources_status == "healthy":
                    resources_status = "warning"

            # Docker disk usage
            try:
                df_result = client.df()
                docker_usage = 0
                for image in df_result.get("Images", []):
                    docker_usage += image.get("Size", 0)
                health_data["docker_disk_usage_gb"] = round(docker_usage / (1024**3), 2)
            except Exception:
                pass

        except Exception as e:
            resources_details["error"] = str(e)
            resources_status = "error"

        set_check("resources", resources_status, resources_details)

        # ========================================
        # SSL Certificates (using openssl s_client like health_check.sh)
        # Skip if quick mode to speed up response
        # ========================================
        ssl_details = {}
        ssl_status = "healthy"
        ssl_certs = []

        if quick:
            # Quick mode: just check if SSL is configured without full cert details
            # Uses same method as full check - grep nginx.conf for ssl_certificate
            ssl_details["message"] = "Skipped detailed check in quick mode"
            ssl_status = "skipped"
            try:
                if nginx_container:
                    exit_code, output = nginx_container.exec_run(
                        "grep -m1 'ssl_certificate ' /etc/nginx/nginx.conf",
                        demux=True
                    )
                    if exit_code == 0 and output[0]:
                        config_line = output[0].decode("utf-8").strip()
                        match = re.search(r'/live/([^/]+)/', config_line)
                        if match:
                            health_data["ssl_configured"] = True
                            ssl_details["domain"] = match.group(1)
            except Exception:
                pass  # ssl_configured stays False
        else:
            try:
                if nginx_container:
                    # Get the domain from nginx.conf inside the container (like health_check.sh)
                    domain = None

                    exit_code, output = nginx_container.exec_run(
                        "grep -m1 'ssl_certificate ' /etc/nginx/nginx.conf",
                        demux=True
                    )

                    if exit_code == 0 and output[0]:
                        config_line = output[0].decode("utf-8").strip()
                        match = re.search(r'/live/([^/]+)/', config_line)
                        if match:
                            domain = match.group(1)

                    if domain:
                        ssl_details["domain"] = domain
                        expiry_str = None

                        # Run openssl in alpine container sharing nginx's network
                        # This ensures openssl is available and can connect to nginx's localhost:443
                        try:
                            result = _run_alpine_container_sync(
                                client,
                                command=["sh", "-c", f"apk add --no-cache openssl >/dev/null 2>&1 && echo | openssl s_client -servername {domain} -connect localhost:443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null"],
                                network_mode=f"container:{nginx_container.id}",
                            )
                            cert_output = result.decode("utf-8").strip()
                            if cert_output.startswith("notAfter="):
                                expiry_str = cert_output.replace("notAfter=", "").strip()
                        except Exception:
                            pass

                        # Fallback: read cert file directly via nginx container with cat + python parsing
                        if not expiry_str:
                            try:
                                exit_code, output = nginx_container.exec_run(
                                    f"cat /etc/letsencrypt/live/{domain}/fullchain.pem",
                                    demux=True
                                )
                                if exit_code == 0 and output[0]:
                                    cert_pem = output[0].decode("utf-8")
                                    # Parse cert with cryptography library
                                    from cryptography import x509
                                    from cryptography.hazmat.backends import default_backend
                                    cert = x509.load_pem_x509_certificate(cert_pem.encode(), default_backend())
                                    expiry_date = cert.not_valid_after_utc.replace(tzinfo=None)
                                    days_left = (expiry_date - datetime.now()).days

                                    ssl_certs.append({
                                        "domain": domain,
                                        "expires": expiry_date.strftime("%b %d %H:%M:%S %Y GMT"),
                                        "days_until_expiry": days_left,
                                    })
                                    ssl_details["days_until_expiry"] = days_left

                                    if days_left <= 7:
                                        ssl_status = "error"
                                    elif days_left <= 30:
                                        ssl_status = "warning"

                                    expiry_str = "parsed"  # Mark as successful
                            except Exception as cert_err:
                                ssl_details["cert_read_error"] = str(cert_err)

                        # Parse the openssl output if we got it
                        if expiry_str and expiry_str != "parsed":
                            try:
                                expiry_date = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
                                days_left = (expiry_date - datetime.now()).days

                                ssl_certs.append({
                                    "domain": domain,
                                    "expires": expiry_str,
                                    "days_until_expiry": days_left,
                                })
                                ssl_details["days_until_expiry"] = days_left

                                if days_left <= 7:
                                    ssl_status = "error"
                                elif days_left <= 30:
                                    ssl_status = "warning"
                            except Exception:
                                ssl_details["parse_error"] = f"Could not parse date: {expiry_str}"

                        if not ssl_certs:
                            ssl_details["error"] = "Cannot read SSL certificate"
                            ssl_status = "warning"
                    else:
                        ssl_details["message"] = "No SSL certificate configured"
                        ssl_status = "warning"

                    health_data["ssl_certificates"] = ssl_certs
                    health_data["ssl_configured"] = len(ssl_certs) > 0

            except Exception as e:
                ssl_details["error"] = str(e)
                ssl_status = "warning"

        set_check("ssl", ssl_status, ssl_details)

        # ========================================
        # Network Connectivity
        # ========================================
        network_details = {}
        network_status = "healthy"

        try:
            # DNS check
            try:
                socket.gethostbyname("google.com")
                network_details["dns"] = "ok"
            except Exception:
                network_details["dns"] = "error"
                network_status = "error"

            # Internet connectivity (check npm registry like health_check.sh)
            if nginx_container:
                exit_code, output = nginx_container.exec_run(
                    "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 https://registry.npmjs.org/",
                    demux=True
                )
                if exit_code == 0 and output[0]:
                    status_code = output[0].decode("utf-8").strip()
                    if status_code == "200":
                        network_details["internet"] = "ok"
                    else:
                        network_details["internet"] = "warning"
                        if network_status == "healthy":
                            network_status = "warning"
                else:
                    network_details["internet"] = "warning"
                    if network_status == "healthy":
                        network_status = "warning"

        except Exception as e:
            network_details["error"] = str(e)
            network_status = "warning"

        set_check("network", network_status, network_details)

        # ========================================
        # Backup Status (from database)
        # ========================================
        backups_details = {
            "recent_count": 0,
            "failed_count": 0,
            "total_size_bytes": 0,
            "total_size_display": "0 B",
        }
        backups_status = "healthy"

        try:
            from api.models.backups import BackupHistory

            # Get backups from the last 24 hours
            cutoff_24h = datetime.now(UTC) - timedelta(hours=24)

            # Count recent successful backups (status = 'success')
            recent_success_result = await db.execute(
                select(func.count(BackupHistory.id)).where(
                    BackupHistory.created_at >= cutoff_24h,
                    BackupHistory.status == "success"
                )
            )
            recent_success_count = recent_success_result.scalar() or 0

            # Count recent failed backups (status = 'failed')
            recent_failed_result = await db.execute(
                select(func.count(BackupHistory.id)).where(
                    BackupHistory.created_at >= cutoff_24h,
                    BackupHistory.status == "failed"
                )
            )
            recent_failed_count = recent_failed_result.scalar() or 0

            # Get the most recent backup (any status)
            last_backup_result = await db.execute(
                select(BackupHistory)
                .where(BackupHistory.status == "success")
                .order_by(BackupHistory.created_at.desc())
                .limit(1)
            )
            last_backup = last_backup_result.scalar_one_or_none()

            # Calculate total size of all successful backups
            total_size_result = await db.execute(
                select(func.sum(BackupHistory.file_size)).where(
                    BackupHistory.status == "success",
                    BackupHistory.deleted_at.is_(None)
                )
            )
            total_size_bytes = total_size_result.scalar() or 0

            # Format size for display
            def format_size(size_bytes):
                if size_bytes < 1024:
                    return f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    return f"{size_bytes / 1024:.1f} KB"
                elif size_bytes < 1024 * 1024 * 1024:
                    return f"{size_bytes / (1024 * 1024):.1f} MB"
                else:
                    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

            backups_details["recent_count"] = recent_success_count
            backups_details["failed_count"] = recent_failed_count
            backups_details["total_size_bytes"] = total_size_bytes
            backups_details["total_size_display"] = format_size(total_size_bytes)

            if last_backup:
                backups_details["last_backup"] = last_backup.created_at.isoformat()

                # Warn if last successful backup is older than 7 days
                days_old = (datetime.now(UTC) - last_backup.created_at.replace(tzinfo=UTC)).days
                if days_old > 7:
                    backups_status = "warning"
                    backups_details["message"] = f"Last successful backup is {days_old} days old"

            # Set status based on recent failures and backup existence
            if recent_failed_count > 0:
                backups_status = "warning"
                backups_details["message"] = f"{recent_failed_count} backup(s) failed in the last 24h"
            elif recent_success_count == 0 and not last_backup:
                backups_status = "warning"
                backups_details["message"] = "No backups found in database"

        except Exception as e:
            backups_details["error"] = str(e)
            backups_status = "warning"

        set_check("backups", backups_status, backups_details)

        # ========================================
        # Recent Error Analysis
        # Skip if quick mode to speed up response
        # ========================================
        logs_details = {
            "error_count": 0,
            "warning_count": 0,
            "recent_errors": [],
            "by_container": {},  # Per-container breakdown
        }
        logs_status = "healthy"

        if quick:
            logs_details["message"] = "Skipped in quick mode"
            logs_status = "skipped"
        else:
            try:
                total_errors = 0
                total_warnings = 0

                # Containers to analyze - expanded list
                containers_to_check = ["n8n", "n8n_nginx", "n8n_postgres", "n8n_management", "n8n_cloudflared", "n8n_tailscale"]

                # Common noise patterns to skip
                skip_patterns = [
                    "cert.pem",
                    "buffer size",
                    "Cannot determine default origin certificate",
                    "failed to sufficiently increase receive buffer",
                    "Update check",
                ]

                for container in client.containers.list():
                    if container.name in containers_to_check:
                        container_errors = 0
                        container_warnings = 0
                        container_recent = []

                        try:
                            logs = container.logs(
                                since=datetime.now(UTC) - timedelta(hours=1),
                                timestamps=True  # Include timestamps
                            ).decode("utf-8", errors="ignore")
                            lines = logs.split("\n")

                            for line in lines:
                                if not line.strip():
                                    continue

                                line_lower = line.lower()

                                # Skip common noise
                                if any(skip in line for skip in skip_patterns):
                                    continue

                                # Check for errors
                                if "error" in line_lower or "ERR" in line or "FATAL" in line or "panic" in line_lower:
                                    container_errors += 1
                                    total_errors += 1

                                    # Parse timestamp and message
                                    # Docker timestamp format: 2024-01-15T10:30:45.123456789Z
                                    timestamp = ""
                                    message = line
                                    if line and len(line) > 30 and line[4] == '-' and 'T' in line[:25]:
                                        try:
                                            timestamp_end = line.index(' ', 20) if ' ' in line[20:50] else 30
                                            timestamp = line[:timestamp_end].strip()
                                            message = line[timestamp_end:].strip()
                                        except (ValueError, IndexError):
                                            pass

                                    # Capture recent errors (up to 10 per container, 20 total)
                                    if len(container_recent) < 10 and len(logs_details["recent_errors"]) < 20:
                                        error_entry = {
                                            "container": container.name,
                                            "timestamp": timestamp[:19] if timestamp else "",  # Trim to readable format
                                            "message": message[:200],  # Limit message length
                                            "level": "error",
                                        }
                                        container_recent.append(error_entry)
                                        logs_details["recent_errors"].append(error_entry)

                                elif "warn" in line_lower:
                                    container_warnings += 1
                                    total_warnings += 1

                        except Exception as e:
                            logs_details["by_container"][container.name] = {
                                "error_count": 0,
                                "warning_count": 0,
                                "status": "error",
                                "message": f"Failed to read logs: {str(e)[:50]}",
                            }
                            continue

                        # Store per-container stats
                        if container_errors > 0 or container_warnings > 0:
                            logs_details["by_container"][container.name] = {
                                "error_count": container_errors,
                                "warning_count": container_warnings,
                                "status": "error" if container_errors > 10 else "warning" if container_errors > 0 else "ok",
                            }

                logs_details["error_count"] = total_errors
                logs_details["warning_count"] = total_warnings

                # Sort recent errors by timestamp (newest first)
                logs_details["recent_errors"].sort(
                    key=lambda x: x.get("timestamp", ""),
                    reverse=True
                )

                if total_errors > 50:
                    logs_status = "error"
                elif total_errors > 10:
                    logs_status = "warning"

            except Exception as e:
                logs_details["error"] = str(e)
                logs_status = "warning"

        set_check("logs", logs_status, logs_details)

    except Exception as e:
        import traceback
        health_data["overall_status"] = "error"
        health_data["error"] = str(e)
        health_data["error_traceback"] = traceback.format_exc() if settings.debug else None
        health_data["error_type"] = type(e).__name__

    # Determine overall status
    if health_data["errors"] > 0:
        health_data["overall_status"] = "error"
    elif health_data["warnings"] > 0:
        health_data["overall_status"] = "warning"
    else:
        health_data["overall_status"] = "healthy"

    return health_data


@router.get("/debug")
async def get_debug_status(
    _=Depends(get_current_user),
):
    """Get current debug mode status and settings."""
    return {
        "debug_enabled": settings.debug,
        "log_level": settings.log_level,
        "environment": {
            "debug": settings.debug,
            "database_url": "***" if settings.database_url else None,
            "docker_socket": settings.docker_socket,
            "container_prefix": settings.container_prefix,
        }
    }


@router.post("/debug/test-error")
async def test_error_handling(
    _=Depends(get_current_user),
):
    """Test endpoint that intentionally raises an error for debugging."""
    raise HTTPException(
        status_code=500,
        detail={
            "message": "This is a test error for debugging",
            "debug_info": {
                "timestamp": datetime.now(UTC).isoformat(),
                "debug_mode": settings.debug,
            }
        }
    )


@router.get("/host-metrics/cached")
async def get_host_metrics_cached(
    history_minutes: int = 60,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Get host metrics from the database cache (instant, no network latency).

    Metrics are collected every minute by the scheduler using psutil and the Docker API,
    then stored in PostgreSQL. This endpoint reads from the database for instant access.

    Args:
        history_minutes: Number of minutes of history to return for charts (default 60)

    Returns:
        - latest: The most recent metrics snapshot
        - history: Array of historical data points for charting
        - available: Whether metrics data is available
    """
    from api.models.audit import HostMetricsSnapshot
    from sqlalchemy import select, desc
    from datetime import timedelta
    import zoneinfo

    # Get the configured timezone for displaying timestamps
    try:
        local_tz = zoneinfo.ZoneInfo(settings.timezone)
    except Exception:
        local_tz = UTC  # Fallback to UTC if invalid timezone

    # Get the latest snapshot
    result = await db.execute(
        select(HostMetricsSnapshot)
        .order_by(desc(HostMetricsSnapshot.collected_at))
        .limit(1)
    )
    latest = result.scalar_one_or_none()

    if not latest:
        return {
            "available": False,
            "enabled": True,
            "error": "No metrics data available yet. Please wait for the collector to run (runs every minute).",
            "latest": None,
            "history": [],
        }

    # Get historical data for charts (last N minutes)
    cutoff = datetime.now(UTC) - timedelta(minutes=history_minutes)
    result = await db.execute(
        select(HostMetricsSnapshot)
        .where(HostMetricsSnapshot.collected_at >= cutoff)
        .order_by(HostMetricsSnapshot.collected_at)
    )
    history_rows = result.scalars().all()

    # Format the response
    def format_snapshot(s):
        return {
            "collected_at": s.collected_at.isoformat() if s.collected_at else None,
            "system": {
                "hostname": s.hostname,
                "platform": s.platform,
                "uptime_seconds": s.uptime_seconds,
            },
            "cpu": {
                "percent": s.cpu_percent,
                "core_count": s.cpu_core_count,
                "load_avg_1m": s.load_avg_1m,
                "load_avg_5m": s.load_avg_5m,
                "load_avg_15m": s.load_avg_15m,
            },
            "memory": {
                "percent": s.memory_percent,
                "used_bytes": s.memory_used_bytes,
                "total_bytes": s.memory_total_bytes,
                "swap_percent": s.swap_percent,
                "swap_used_bytes": s.swap_used_bytes,
                "swap_total_bytes": s.swap_total_bytes,
            },
            "disk": {
                "percent": s.disk_percent,
                "used_bytes": s.disk_used_bytes,
                "total_bytes": s.disk_total_bytes,
                "free_bytes": s.disk_free_bytes,
            },
            "disks": s.disks_detail or [],
            "network": {
                "rx_bytes": s.network_rx_bytes,
                "tx_bytes": s.network_tx_bytes,
            },
            "containers": {
                "total": s.containers_total,
                "running": s.containers_running,
                "stopped": s.containers_stopped,
                "healthy": s.containers_healthy,
                "unhealthy": s.containers_unhealthy,
            },
        }

    # Build history array optimized for charting (just key values)
    # Calculate network I/O rates (bytes/second) from consecutive readings
    history = []
    for i, s in enumerate(history_rows):
        # Convert UTC timestamp to local timezone for display
        local_time = ""
        if s.collected_at:
            # Ensure the timestamp has UTC timezone info
            utc_time = s.collected_at.replace(tzinfo=UTC) if s.collected_at.tzinfo is None else s.collected_at
            local_time = utc_time.astimezone(local_tz).strftime("%H:%M")

        entry = {
            "time": local_time,
            "cpu": s.cpu_percent,
            "memory": s.memory_percent,
            "disk": s.disk_percent,
            "network_rx": s.network_rx_bytes,
            "network_tx": s.network_tx_bytes,
            "network_rx_rate": 0,  # bytes/second
            "network_tx_rate": 0,  # bytes/second
        }

        # Calculate rate from previous reading
        if i > 0:
            prev = history_rows[i - 1]
            if prev.collected_at and s.collected_at:
                time_diff = (s.collected_at - prev.collected_at).total_seconds()
                if time_diff > 0:
                    # Calculate bytes/second
                    rx_diff = (s.network_rx_bytes or 0) - (prev.network_rx_bytes or 0)
                    tx_diff = (s.network_tx_bytes or 0) - (prev.network_tx_bytes or 0)
                    # Handle counter resets (can happen on system restart)
                    if rx_diff >= 0:
                        entry["network_rx_rate"] = round(rx_diff / time_diff)
                    if tx_diff >= 0:
                        entry["network_tx_rate"] = round(tx_diff / time_diff)

        history.append(entry)

    # Calculate current network rate (average of last 5 readings for smoother display)
    current_rx_rate = 0
    current_tx_rate = 0
    if len(history) >= 2:
        # Take up to last 5 readings for averaging
        recent = history[-5:] if len(history) >= 5 else history
        rx_rates = [h.get("network_rx_rate", 0) for h in recent if h.get("network_rx_rate", 0) > 0]
        tx_rates = [h.get("network_tx_rate", 0) for h in recent if h.get("network_tx_rate", 0) > 0]

        if rx_rates:
            current_rx_rate = int(sum(rx_rates) / len(rx_rates))
        if tx_rates:
            current_tx_rate = int(sum(tx_rates) / len(tx_rates))

    return {
        "available": True,
        "enabled": True,
        "latest": format_snapshot(latest),
        "history": history,
        "history_count": len(history),
        "network_rates": {
            "rx_bytes_per_sec": current_rx_rate,
            "tx_bytes_per_sec": current_tx_rate,
        },
    }


@router.get("/scheduler/status")
async def get_scheduler_status(
    _=Depends(get_current_user),
):
    """Get scheduler status and list all scheduled jobs."""
    from api.tasks.scheduler import get_scheduler

    scheduler = get_scheduler()
    if scheduler is None:
        return {
            "running": False,
            "message": "Scheduler not initialized",
            "jobs": [],
        }

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return {
        "running": scheduler.running,
        "timezone": str(scheduler.timezone),
        "job_count": len(jobs),
        "jobs": jobs,
    }
