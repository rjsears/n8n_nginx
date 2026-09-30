#!/usr/bin/env python3
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /scripts/certbot/reload-nginx-hook.py
#
# Part of the "n8n_nginx/n8n_management" suite
#
# certbot deploy hook: after a certificate is renewed, reload the nginx
# containers that serve it so they pick up the new files.
#
# renew-loop.sh installs it into /etc/letsencrypt/renewal-hooks/deploy/, so it
# runs after every successful `certbot renew`, whoever started it.
#
# It sends SIGHUP (= `nginx -s reload`) through the Docker Engine API on
# /var/run/docker.sock using only the Python standard library, which every
# certbot image already ships. No docker CLI or package install is needed.
#
# Containers: $NGINX_RELOAD_CONTAINERS (space separated) if set, otherwise
# $NGINX_CONTAINER (default n8n_nginx) and n8n_nginx_router.
# Containers that do not exist are skipped.
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import http.client
import os
import socket
import sys
import urllib.parse

DOCKER_SOCKET = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout=30):
        super().__init__("localhost", timeout=timeout)
        self.unix_path = path

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.unix_path)
        self.sock = sock


def send_hup(name):
    conn = UnixHTTPConnection(DOCKER_SOCKET)
    try:
        conn.request("POST", "/containers/%s/kill?signal=HUP" % urllib.parse.quote(name, safe=""))
        resp = conn.getresponse()
        return resp.status, resp.read().decode("utf-8", "replace").strip()
    finally:
        conn.close()


def main():
    names = os.environ.get("NGINX_RELOAD_CONTAINERS", "").split()
    if not names:
        names = [os.environ.get("NGINX_CONTAINER") or "n8n_nginx", "n8n_nginx_router"]
    names = list(dict.fromkeys(names))

    print("[n8n-reload-nginx] certificate renewed: %s" % os.environ.get("RENEWED_LINEAGE", "(unknown)"))

    if not os.path.exists(DOCKER_SOCKET):
        print("[n8n-reload-nginx] ERROR: %s is not mounted - reload nginx manually: docker kill -s HUP %s"
              % (DOCKER_SOCKET, " ".join(names)), file=sys.stderr)
        return 1

    failed = False
    for name in names:
        try:
            status, body = send_hup(name)
        except OSError as exc:
            print("[n8n-reload-nginx] ERROR: cannot reach the Docker API: %s" % exc, file=sys.stderr)
            return 1
        if status == 204:
            print("[n8n-reload-nginx] reloaded %s" % name)
        elif status == 404:
            print("[n8n-reload-nginx] %s does not exist, skipped" % name)
        else:
            failed = True
            print("[n8n-reload-nginx] ERROR: reload of %s failed (HTTP %s): %s" % (name, status, body),
                  file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
