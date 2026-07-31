# Appendix

Reference material: troubleshooting tables, the master index of every screenshot in this manual that requires blurring before publishing, and a few quick-reference sections.

## Troubleshooting

This is the manual's quick-symptom triage table. Each entry points to the relevant page in the manual or to one of the canonical detail docs.

### "Failed to start restore container" / Selective Restore mount fails silently {: #tb-mount-fail }

**Symptom:** Clicking **Selective Restore → Mount Backup** spins for a few seconds and reverts to the "Mount Backup" prompt without an error toast (or with one that disappears too quickly to read). The verification or mount API call returns HTTP 200 with body `{"status":"failed","error":"Failed to start restore container"}`.

**Cause:** The management container's Python code spawns a temporary helper container (PostgreSQL or Alpine) via a `docker run` shell call. When the management container itself runs inside an unprivileged LXC, Docker can't apply the default AppArmor profile to a child container — it needs `--security-opt apparmor=unconfined` on the spawn command. If a recently-added `docker run` shell call missed the flag, every helper-spawn fails.

**Fix:** Search the management API codebase for missing flags:

```
grep -rn '"docker", "run"' management/api/ --include="*.py"
```

Each match should have `"--security-opt", "apparmor=unconfined",` in the args list. Affects: `restore_service.py`, `verification_service.py`, and (historically) `tasks/scheduler.py`, `routers/system.py`, `routers/terminal.py`.

**Where to look for the actual error:** `docker logs n8n_management` only shows supervisord events. The Python traceback is in `/app/logs/uvicorn.log` inside the container:

```
docker exec n8n_management tail -200 /app/logs/uvicorn.log
```

### SSL Force Renewal times out from the UI {: #tb-ssl }

**Symptom:** Clicking **Force Renew** on the [System → SSL Certificates](system.md#health-ssl) card returns a timeout error in the browser, but checking afterward shows the certificate was actually renewed.

**Cause:** Certbot's default random sleep delay (up to 8 minutes) exceeded the previous web request timeout.

**Fix:** The Management Console now uses `--no-random-sleep-on-renew` automatically and waits up to 5 minutes. Pull the latest management image:

```
docker compose pull n8n_management
docker compose up -d n8n_management
```

**Related issues:**

- **Missing dns-cloudflare plugin** — set `DNS_CERTBOT_IMAGE=certbot/dns-cloudflare` in `.env` and recreate the certbot container.
- **Broken cert symlinks** — after manual renewals the `/etc/letsencrypt/live/<domain>/*.pem` symlinks may point to an older archive version. Recreate them to point at the highest-numbered file in `archive/`.

See the canonical [Certbot guide](../CERTBOT.md) for the full rate-limit table and DNS provider setup details.

### SSL renewals silently failing (deploy hook can't find docker) {: #tb-ssl-silent }

**Symptom:** `docker logs n8n_certbot` shows `Unable to find deploy-hook command docker in the PATH.` every 12 hours. Nothing looks broken day-to-day, but the certificate's remaining validity keeps shrinking on the [System → SSL Certificates](system.md#health-ssl) card.

**Cause:** The certbot container's renewal loop uses a deploy hook (`docker exec … nginx -s reload`) to make nginx pick up renewed certificates. The stock certbot images don't include the Docker CLI, and certbot validates hook commands *before* renewing — a failed validation aborts the entire run. So this isn't just a broken reload: **no renewal is ever attempted**, and the certificate eventually expires.

**Fix:** Update `docker-compose.yaml` to the current version — the certbot entrypoint now installs the CLI at container start (`apk add docker-cli`) — then recreate the container and verify:

```
docker compose up -d --force-recreate certbot
docker exec n8n_certbot which docker   # should print a path
```

If the certificate is already close to expiry, renew immediately instead of waiting for the next 12-hour cycle:

```
docker exec n8n_certbot certbot renew --no-random-sleep-on-renew
docker exec n8n_nginx nginx -s reload
docker exec n8n_nginx_router nginx -s reload   # Public Website installs only
```

**Public Website installs:** the `n8n_nginx_router` container terminates SSL on port 443 and must be reloaded after any renewal or it keeps serving the old certificate from memory. The current deploy hook does this automatically.

### Many Alpine containers stuck in "Created" state {: #tb-stuck-alpine }

**Symptom:** Running `docker ps -a --filter "ancestor=alpine:latest"` shows dozens of orphaned Alpine containers in `Created` state that never ran. Common when running Docker inside an LXC.

**Cause:** The host's AppArmor profile blocks Alpine containers from starting inside an unprivileged LXC. The container is created but cannot transition to running state.

**Solution:** The Management Suite spawns short-lived Alpine containers for system metrics collection and SSL renewal. As of the AppArmor fix, all such containers are launched with `security_opt=["apparmor=unconfined"]`. Pull the latest image and clean up orphans:

```
docker compose pull n8n_management
docker compose up -d n8n_management
docker ps -a --filter "ancestor=alpine:latest" --filter "status=created" -q | xargs -r docker rm -f
docker ps -a --filter "ancestor=alpine:latest" --filter "status=exited" -q | xargs -r docker rm -f
```

### Container creation fails: "docker-default profile could not be loaded" {: #tb-apparmor-compose }

**Symptom:** Creating or recreating *any* container (e.g. `docker compose up -d --force-recreate certbot`) fails with `Error response from daemon: AppArmor enabled on system but the docker-default profile could not be loaded … apparmor_parser: Access denied. You need policy admin privileges to manage profiles.` Long-running containers keep working, so the error can appear "out of nowhere" months after install — it only triggers on container creation.

**Cause:** The same root condition as the two AppArmor entries above, but at the Docker-daemon level: inside an LXC guest (e.g. Proxmox), Docker shares the host's kernel and may not be allowed to load AppArmor policy into it. Creating a container with default confinement requires loading the `docker-default` profile, and the load is denied. This affects **every** compose service, not just the management console's helper containers.

**Fix:** Every service in `docker-compose.yaml` needs:

```
    security_opt:
      - apparmor:unconfined
```

Current `setup.sh` handles this automatically — during the Docker environment check it probes whether the daemon can load AppArmor policy, and on affected hosts it generates every compose service with the `security_opt` entry (helper `docker run` commands get `--security-opt apparmor=unconfined` too). Unaffected hosts keep standard Docker confinement.

**Important:** if you replace or regenerate `docker-compose.yaml` on an affected host, make sure the `security_opt` entries survive. A compose file without them deploys fine but fails on the next container recreate — re-running the current `setup.sh` restores them.

### Stale data showing in tabs {: #tb-cache-stale }

**Symptom:** A container you just stopped still appears running. A backup that just completed isn't in the history yet. Network metrics not updating.

**Cause:** The management console's data collectors pre-populate Redis with snapshots; tabs read from Redis. If a collector is stuck or Redis is in an odd state, you see a stale snapshot.

**Fix:**

1. Go to [System → Cache](system.md#cache) and check Data Collectors statuses.
2. If a specific collector is failing, restart the `n8n_status` container.
3. If the entire cache is suspect, click **Flush** on the Cache tab. The cache will rebuild within ~30 seconds.
4. For an immediate force-refresh on a single page, hit the page's Refresh button (typically top-right).

### Locked out of the management console {: #tb-auth-locked }

**Symptom:** Login fails with valid-looking credentials, or the account is locked due to too many failed attempts.

**Recovery:** Reset password via CLI inside the management container.

```
docker exec n8n_management python -c "
from core.database import SessionLocal
from models.user import User
from core.security import get_password_hash
db = SessionLocal()
user = db.query(User).filter(User.username == 'admin').first()
user.hashed_password = get_password_hash('new-password-here')
user.failed_login_attempts = 0
user.locked_until = None
db.commit()
print('Password updated, account unlocked')
"
```

!!! warning

    The management container only contains one user by design. If *that* account is the one locked, you must use this CLI path — there's no second admin to log in and reset for you.

### File Browser issues {: #tb-filebrowser }

| Symptom | Likely fix |
|---|---|
| File Browser shows its own login prompt instead of using management console session | Confirm `.filebrowser.json` has `"auth": {"method": "proxy", "header": "X-Remote-User"}`. |
| 500 error when opening `/files/` | Check `docker logs n8n_nginx --tail 50 \| grep files`. Often the `auth_request` directive is misconfigured. |
| UI partially loads, CSS/JS missing | Confirm `.filebrowser.json` has `"baseURL": "/files"`. |
| iframe too small in management console | Was fixed in PR #322. Pull latest `n8n_management` image and recreate. |

### Symptom → section {: #tb-symptoms }

| You see this | Go here |
|---|---|
| Backup history shows red Failed status | [Backups → Backup History](backups.md#history) |
| Unhealthy count > 0 on Dashboard or Containers | [Containers → Health badges](containers.md#health-badges) |
| Workflow toggle does nothing | [Flows → n8n API integration](flows.md#api-integration) (likely missing API key) |
| SSL Certificates card shows < 7 days valid | [System → SSL Certificates](system.md#health-ssl) (Force Renew or wait for auto-renewal) |
| `Unable to find deploy-hook command docker` in certbot logs | [SSL renewals silently failing](#tb-ssl-silent) |
| `docker-default profile could not be loaded` when (re)creating a container | [Container creation fails (AppArmor)](#tb-apparmor-compose) |
| Notifications not arriving | [Notifications → Channels](notifications.md#channels) (test the channel) |
| Page shows "loading" or blank tiles | [System → Cache](system.md#cache) (check collectors) |
| Need to recover from a corrupted host | [Backups → Bare Metal](backups.md#bare-metal) |
| Want to roll back a single workflow | [Backups → Selective Restore](backups.md#selective-restore) |

For symptoms not covered here, the canonical full troubleshooting document is [TROUBLESHOOTING.md](../TROUBLESHOOTING.md).

## Security Flag Index {: #security-index }

Screenshots in this manual that contain sensitive data. Blur the indicated regions before publishing or sharing this manual outside your organization.

| Page | Screenshot | What's exposed / what to blur |
|---|---|---|
| [Notifications](notifications.md#ntfy) | `notifications-07-ntfy-push-tab.png` | NTFY topic name, NTFY server URL, any auth tokens visible under the Settings sub-tab. |
| [Notifications](notifications.md#n8n-webhook) | `notifications-14-n8n-webhook-expanded.png` | Webhook URL (deployment hostname) and the API Key used to authenticate to it. The API Key is a credential — rotate it if leaked. |
| [Settings](settings.md#access-control) | `settings-04-access-control.png` | Full nginx route inventory (every URL the stack serves) and direct-access CIDR allowlist (internal subnets). |
| [Settings](settings.md#api-debug) | `settings-07-n8n-api-debug.png` | n8n API key (shown truncated but exposed in full via the Update API Key dialog). |
| [Settings](settings.md#env-editor) | `settings-08-environment-editor.png` | Category structure of the environment editor. Variable values are revealed when categories are expanded. |
| [Settings](settings.md#env-editor) | `settings-09-environment-required-expanded.png` | `DOMAIN` and `N8N_MANAGEMENT_HOST_IP` values shown in plain text. Other categories (Database Configuration, Security & Authentication, Cloudflare Tunnel, Tailscale VPN, n8n API Integration) expose *secrets* when expanded. |
| [System](system.md#network) | `system-05-network.png` | Internal IPs, MAC addresses, Cloudflare tunnel ID, Tailscale node info (login email + tailnet IP), edge-location identifiers. |

!!! note

    Inline security flags (the red badges below specific figures throughout the manual) are the source of truth for this index. If you add a new flagged figure, add a corresponding row here.

## Quick reference {: #quick-ref }

### Default ports

| Port | Service |
|---|---|
| 80 / 443 | nginx (public website + management console) |
| 5678 | n8n itself (proxied through nginx) |
| 5432 | PostgreSQL (n8n + management DBs) |
| 6379 | Redis (cache) |
| 8000 | Management API uvicorn (proxied through nginx as `/management/api/`) |

### Key paths inside the management container

| Path | Contents |
|---|---|
| `/app/api/` | FastAPI Python source |
| `/app/logs/uvicorn.log` | Application stdout (FastAPI request logs and Python `print()`) |
| `/app/logs/uvicorn_error.log` | Application stderr (Python tracebacks) |
| `/app/logs/supervisord.log` | Supervisor lifecycle events |
| `/app/backups/` | Local backup staging area |

### Useful one-liners

```
# Tail application logs
docker exec n8n_management tail -200 /app/logs/uvicorn.log

# Find every docker run call in the API code (for AppArmor audit)
grep -rn '"docker", "run"' management/api/ --include="*.py"

# Force-refresh the Redis cache
redis-cli FLUSHDB

# Check certificate expiration
docker exec n8n_nginx openssl x509 -in /etc/letsencrypt/live/your-domain.com/fullchain.pem -noout -dates

# Clean orphaned Alpine containers
docker ps -a --filter "ancestor=alpine:latest" --filter "status=exited" -q | xargs -r docker rm -f
```
