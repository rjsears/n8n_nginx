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

Blocking (Docker exec / subprocess); call from async code via
``asyncio.to_thread``.
"""

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


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

    # Try to get SSL info from nginx container
    try:
        import docker
        client = docker.from_env()

        # Find nginx container (prioritize router, then main nginx)
        # Skip n8n_nginx_public as it has no SSL config
        nginx_container = None
        try:
            nginx_container = client.containers.get("n8n_nginx_router")
        except Exception:
            try:
                nginx_container = client.containers.get("n8n_nginx")
            except Exception:
                pass

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
