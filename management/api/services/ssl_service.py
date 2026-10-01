"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/ssl_service.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

Reads the Let's Encrypt certificates the stack serves and reports how long
each has left. Used by the /api/system/ssl endpoint and by the daily
certificate-expiry check that produces the ``certificate_expiring`` event.

Reads /etc/letsencrypt/live directly (the management container mounts the
letsencrypt volume) and falls back to the nginx container (NGINX_CONTAINER)
when nothing is found locally.

Blocking (Docker exec / subprocess); call from async code via
``asyncio.to_thread``.
"""

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

LETSENCRYPT_LIVE = "/etc/letsencrypt/live"


def nginx_container_names() -> list:
    """Containers that may hold the certificates, most specific first."""
    names = []
    for name in (os.environ.get("NGINX_CONTAINER", "").strip(), "n8n_nginx", "n8n_nginx_router"):
        if name and name not in names:
            names.append(name)
    return names


def get_ssl_info() -> dict:
    """
    Certificate inventory: ``{"configured": bool, "certificates": [...], ...}``.
    Each certificate dict carries ``domain``, ``valid_until`` and, when the
    date parsed, ``days_until_expiry`` and ``status``.
    """
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

    def read_local() -> None:
        """The management container mounts the letsencrypt volume: read it directly."""
        import subprocess

        letsencrypt_path = LETSENCRYPT_LIVE
        try:
            if not os.path.isdir(letsencrypt_path):
                return
            for domain_dir in sorted(os.listdir(letsencrypt_path)):
                if domain_dir.startswith("README"):
                    continue
                cert_path = os.path.join(letsencrypt_path, domain_dir, "cert.pem")
                if not os.path.exists(cert_path):
                    continue
                result = subprocess.run(
                    ["openssl", "x509", "-in", cert_path, "-noout",
                     "-subject", "-issuer", "-dates", "-ext", "subjectAltName"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    ssl_info["certificates"].append(parse_cert_output(result.stdout, domain_dir, cert_path))
                    ssl_info["configured"] = True
                    ssl_info["source"] = "local"
        except PermissionError:
            ssl_info["local_error"] = "Permission denied reading certificate directory"
        except Exception as e:
            ssl_info["local_error"] = str(e)

    def read_from_nginx() -> None:
        """Fallback: ask the nginx container (NGINX_CONTAINER, then the old names)."""
        try:
            import docker
            client = docker.from_env()

            nginx_container = None
            for name in nginx_container_names():
                try:
                    nginx_container = client.containers.get(name)
                    break
                except Exception:
                    continue

            if not nginx_container:
                ssl_info["error"] = "Nginx container not found"
                ssl_info["source"] = "none"
                return

            ssl_info["source"] = "nginx_container"
            try:
                exit_code, output = nginx_container.exec_run(f"ls {LETSENCRYPT_LIVE}/", demux=True)
                if exit_code == 0 and output[0]:
                    domains = output[0].decode("utf-8").strip().split("\n")
                    domains = [d for d in domains if d and not d.startswith("README")]

                    for domain in domains:
                        cert_path = f"{LETSENCRYPT_LIVE}/{domain}/cert.pem"
                        exit_code, output = nginx_container.exec_run(
                            ["openssl", "x509", "-in", cert_path, "-noout",
                             "-subject", "-issuer", "-dates", "-ext", "subjectAltName"],
                            demux=True,
                        )
                        if exit_code == 0 and output[0]:
                            cert_output = output[0].decode("utf-8")
                            ssl_info["certificates"].append(parse_cert_output(cert_output, domain, cert_path))
                            ssl_info["configured"] = True
            except Exception as e:
                ssl_info["error"] = f"Failed to read certificates from nginx: {str(e)}"
        except Exception as e:
            ssl_info["error"] = f"Docker error: {str(e)}"

    read_local()
    if not ssl_info["configured"]:
        local_error = ssl_info.pop("local_error", None)
        read_from_nginx()
        if local_error and not ssl_info["configured"] and not ssl_info.get("error"):
            ssl_info["error"] = local_error
    else:
        ssl_info.pop("local_error", None)

    return ssl_info
