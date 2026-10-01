# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### September 2026 Updates

#### Removed
- **Controls that were stored and displayed but never did anything.** A
  setting that looks configured and is not enforced is worse than no
  setting, so these are gone from the UI and the API (the database columns
  stay so existing installs load, marked RETIRED in the models):
  - *Daily Digest* card and the per-event `include_in_digest` flag. A real
    digest needs a queue and a delivery job; it was a checkbox.
  - *Emergency Contact* channel select. Nothing ever sent to it, and no
    behaviour was ever defined for it.
  - Per-event *flapping detection* fields (`flapping_*`) and the flapping
    columns on the state endpoint. Never implemented; without an
    acknowledgement concept it would only hide the second alert.
  - Container `custom_targets`. No UI wrote it and dispatch never read it.
  - `escalation_timeout_minutes` on events and targets. The delayed L2 path
    that read it was removed earlier this month.
  - `retry_count` and `rule_id` on history responses. There is no retry
    worker and no rules.
- **The `notification_rules` engine.** `NotificationService.dispatch`, the
  rules CRUD endpoints (`/api/notifications/rules`) and their schemas had
  no callers and no UI. They implemented a second, independent suppression
  scheme (own `cooldown_minutes`, own `last_triggered`) beside the real
  one. Deleted so the next person fixes the right dispatcher. The
  `notification_rules` table is left in place.
- The `severity` argument to `dispatch_notification`. Every caller passed
  one and the dispatcher ignored all of them in favour of the event's
  configured severity, which is what the Settings page shows. The
  parameter is gone so it cannot look meaningful again.
- **Eight registered notification events that could never fire now have
  producers.** `disk_space_low`, `high_memory`, `high_cpu`,
  `container_high_cpu`, `container_high_memory`, `container_healthy`,
  `certificate_expiring` and `security_event` each had a card, a toggle and
  threshold controls in Settings → System Notifications, but no code path
  dispatched them. Now (`api/services/system_monitors.py`):
  - Host disk / memory / CPU are compared against the event's threshold at
    every 5-minute metrics sample. `high_cpu` honours its
    `duration_minutes`: every sample inside that window must be over the
    threshold.
  - Per-container CPU / memory use each container's own thresholds from
    Containers → Alerts (a new 5-minute job; skipped entirely when no
    container has resource monitoring on).
  - `container_healthy` fires when a container that was announced unhealthy
    or stopped is healthy again, if the problem event's "notify on
    recovery" is on. Recovery closes the episode, so the next problem
    alerts immediately instead of waiting out the cooldown.
  - `certificate_expiring` is checked daily at 06:00 against the "days
    before expiration" threshold; each certificate throttles separately and
    an already-expired certificate is sent as critical.
  - `security_event` fires on an account lockout (with the client IP) and
    on a notification-webhook call with a wrong API key.
- **`update_available` removed.** No update checker exists anywhere in the
  codebase, so the event could never fire. The registry row is deleted on
  next start (its targets cascade). Writing a real update check is a
  feature for another day, not a notification fix.
- **Quiet hours, rate limiting, frequency and blackout window are now
  enforced.** All four were stored, shown in the UI and documented, but the
  dispatcher never read them. They are now checked by a single gate
  (`api/services/notification_gate.py`) that every delivery path consults:
  - *Frequency*: an event set to `once_per_hour`, `once_per_day` and so on
    is throttled to that window. Previously only `cooldown_minutes`
    throttled anything, whatever the frequency select said. Cooldown now
    applies only to `every_time` events, which is what the UI already
    implied by hiding the cooldown slider for other frequencies.
  - *Quiet hours*: critical events pass untouched. Non-critical events are
    delivered at low priority or muted, per a new choice in the Quiet Hours
    dialog (the stored `quiet_hours_reduce_priority` setting, previously
    unexposed). Times are in the console's `TIMEZONE`.
  - *Rate limit*: the "This Hour" counter now counts real deliveries, and
    notifications over `max_notifications_per_hour` are suppressed. The UI
    text claiming they were "queued and delivered when the limit resets"
    described a queue that never existed; it now says what happens.
  - *Blackout window* (API only): total suppression, critical included.
  Every suppression writes a history row whose `suppression_reason` names
  the dial that stopped it (`maintenance`, `blackout`,
  `frequency (once_per_day)`, `cooldown (15min)`, `quiet_hours`,
  `rate_limit (50/hour)`).
- **The n8n webhook endpoint (`POST /api/notifications/webhook`) now honours
  the global controls.** It previously checked only the API key, so
  workflow messages went out during maintenance windows and ignored quiet
  hours and the rate limit. It now passes through the same gate (global
  dials only; it has no event, so cooldown and frequency do not apply). A
  suppressed call returns `success: false` with a new `suppressed` field
  naming the reason, and is recorded in the notification history.
- **Maintenance mode now expires.** The dispatcher only checked the
  `maintenance_mode` flag and ignored `maintenance_until`, so a window that
  had lapsed kept suppressing every notification (the UI showed "Expired"
  while nothing was delivered). A lapsed window now clears itself on the
  next event, and notifications suppressed by an active window are recorded
  in history with `suppression_reason = "maintenance"` instead of vanishing.
- **`container_recreated` notifications were dropped silently.** The
  management console dispatched the event when recreating a container, but
  it was not in the event registry, so it was discarded with no history row.
  It is now a registered Container event (seeded on next start) with its own
  message.
- **L2 escalation ignored its own switch.** `escalation_enabled` was stored
  and shown in the UI but never read; L2 targets fired whenever they
  existed. It is now enforced.
- **L2 escalation could only ever fire once per event/target.** The
  `escalation_sent` state flag was set on the first escalation and never
  cleared, so every later occurrence skipped L2. Each new occurrence now
  starts a fresh escalation cycle.
- **`POST /api/system-notifications/test` did not send anything.** It
  recorded a `sent` history row without contacting any channel, so a broken
  channel passed the test. It now delivers a real test message to every
  target on the event and returns `502` when none accepts it.
- **`GET /api/notifications/services/{id}` returned channel secrets in
  clear text** while the list and group endpoints masked them. All channel
  responses now use the same redaction.
- The System Notifications "N/M enabled" badge counted hidden SSL events in
  both numbers when SSL was not configured. It now counts only the events
  shown.

#### Changed
- The four copies of the transport `if/elif` chain (apprise / ntfy /
  webhook / email) are replaced by one `NotificationDispatcher.send()`.
  Webhook channels now receive a consistent payload (`event_data` plus
  `priority`) from every sender instead of a different shape from each.
- **Time-delayed L2 escalation removed.** The "Escalation Timeout" on L2
  targets scheduled a job that re-sent to L2 after N minutes unconditionally:
  it checked neither maintenance mode nor whether the event was still
  enabled, and the UI's "if L1 hasn't acknowledged" had no acknowledgement
  behind it. L2 targets now fire immediately when the event is critical or
  when no L1 target accepted the message. The timeout picker is gone from
  the add-target dialog; the stored `escalation_timeout_minutes` value is
  no longer read.

#### Added
- **Backend test suite** under `management/tests/` (`cd management && pytest`).
  Runs the real models and dispatcher against in-memory SQLite with the
  transports stubbed. Includes a registry check that fails when an event is
  dispatched but not registered, or registered without a producer beyond the
  known list, and a column check that fails when a notification setting is
  added without being either enforced or explicitly classified as pending.

### July 2026 Updates

#### Fixed
- **Scheduled SSL renewal was silently failing.** The certbot container's
  deploy hook (`docker exec ... nginx -s reload`) requires the Docker CLI,
  which the stock certbot images do not include. Certbot's hook validation
  failed with `Unable to find deploy-hook command docker in the PATH` and
  aborted every renewal attempt before it started. The certbot entrypoint
  now installs `docker-cli` at container start, so the hook validates and
  renewals run. (See `CERTBOT.md` "Renewals Silently Failing".)
- Deploy hook now also reloads `n8n_nginx_router` on Public Website
  installs. The router terminates SSL on port 443 in that topology; without
  the reload it kept serving the pre-renewal certificate from memory until
  the container was restarted.
- The scheduled 12-hour renewal loop now passes `--no-random-sleep-on-renew`
  (previously only on-demand renewals used it).

#### Changed
- `setup.sh` now detects hosts where the Docker daemon cannot load AppArmor
  policy into the kernel (e.g. Docker inside a Proxmox LXC guest: container
  creation fails with `docker-default profile could not be loaded ... You
  need policy admin privileges`). Detection is a runtime probe, not
  platform guessing. On affected hosts, every generated compose service
  gets `security_opt: - apparmor:unconfined` and all helper `docker run`
  invocations include `--security-opt apparmor=unconfined` — the same
  approach already used by the management console's helper containers.
  Unaffected hosts keep standard Docker AppArmor confinement. This replaces
  the previous state where the compose-level fix existed only as a manual
  server-side edit that regeneration would silently discard. (See
  `TROUBLESHOOTING.md` "Container Creation Fails: docker-default profile
  could not be loaded".)
- The Docker hello-world verification during install retries with AppArmor
  unconfined instead of aborting on affected hosts.

## [3.0.0] - 2026-04

### April 2026 Updates

#### Added
- `DNS_CERTBOT_IMAGE` environment variable to control which Certbot image runs
  during SSL renewal (lets operators pin to a specific tag or DNS plugin
  variant).
- `POSTGRES_HOST` documented in the environment-variables reference (the
  variable was already used by the backup, restore, and verification
  services; only the doc was missing).
- HTML user manual under `docs/manual/` rebuilt with screenshots reflecting
  the current UI (light + dark dashboards, modal interactions, all sub-tabs).

#### Changed
- Let's Encrypt renewal timeout extended from the previous default to five
  minutes (300 s). DNS challenges that hit propagation delays no longer fail
  due to the management console's request timeout.
- Frontend `services/api.js` now sets the corresponding 300 000 ms timeout
  for SSL-related operations.

#### Fixed
- AppArmor LXC mount issue affecting the Selective Restore mount workflow
  inside Proxmox LXC containers. Backup verification and restore Docker
  invocations now use `security_opt=["apparmor=unconfined"]` and Certbot
  runs with `--no-random-sleep-on-renew` so the renewal hook completes
  inside the request window. (See `TROUBLESHOOTING.md` "AppArmor / LXC mount
  failures" and `CERTBOT.md`.)
- Alpine restore container cleanup in `system.py` and the docker container
  cleanup paths so transient Alpine helpers used during selective restore
  are reliably removed even when an operation aborts.

### Added

#### Management Console
- Web-based management interface accessible on configurable port (default 3333)
- Dashboard with container status, system metrics, and quick actions
- Real-time container monitoring and control (start/stop/restart)
- Container resource usage statistics (CPU, memory, network)

#### Backup System
- Automated PostgreSQL backup scheduling (hourly, daily, weekly, monthly)
- Multiple backup types: full database, n8n only, configuration
- Configurable retention policies per backup frequency
- NFS storage support for remote backup storage
- Backup verification with integrity checking
- Individual workflow extraction from backups
- Workflow restore with conflict resolution (rename/overwrite/skip)
- Backup download via web interface
- 30-day backup statistics in Health tab
- Image preview support for public website restore (up to 10MB images)
- Public website backup/restore functionality

#### Redis Status Caching System
- New `n8n_status` container for continuous system metrics collection
- New `n8n_redis` container (Redis 7 Alpine) for status caching
- Cache Status page in System view showing Redis health and cached keys
- Sub-50ms response times for Network, Health, and Container tabs
- Automatic fallback to direct collection when cache unavailable
- Force refresh buttons on cached data views
- Docker build workflow for `n8n_status` container (auto-builds on push)

#### Public Website & File Browser
- File Browser integration for managing public website files
- Public website hosting support (www subdomain)
- `update_public_index.sh` script for updating public landing page
- Light-themed landing page with favicon
- Public Website tab in Backup Contents Dialog

#### Notification System
- Multi-channel notifications via Apprise (80+ services)
- Native support for Slack, Discord, Email, NTFY
- Custom webhook integration
- Event-based notification rules with priority levels
- Cooldown support to prevent notification spam
- Notification history and delivery status tracking
- Redis caching for system notification events

#### System Monitoring
- Host system metrics (CPU, memory, disk)
- NFS connection status monitoring
- SSL certificate expiration tracking
- Container health check integration
- Power controls with confirmation safeguards
- Cloudflare Tunnel status with edge locations, tunnel_id, connector_id
- Tailscale VPN status with full peer list

#### Setup Script Enhancements
- State management for resume capability after interruption
- Automatic version detection (v2.0 vs v3.0 vs fresh install)
- Interactive NFS configuration wizard
- Multi-channel notification setup during install
- Admin user creation with password validation
- Port validation and conflict detection

#### Migration Support
- Automatic v2.0 to v3.0 migration path
- Pre-migration backup creation
- 30-day rollback window
- Configuration preservation during upgrade

#### Testing & Health
- Comprehensive test suite for installation validation
- Migration test scenarios
- Backup/restore test scenarios
- Health check script (`scripts/health_check.sh`)
- JSON output for monitoring integration
- Linting setup for frontend (ESLint) and backend (Ruff)

#### Documentation
- Updated README for v3.0
- API documentation (`docs/API.md`)
- Backup guide (`docs/BACKUP_GUIDE.md`)
- Notification guide (`docs/NOTIFICATIONS.md`)
- Migration guide (`docs/MIGRATION.md`)
- Troubleshooting guide (`docs/TROUBLESHOOTING.md`)

### Changed
- `setup.sh` rewritten for v3.0 with modular architecture
- `docker-compose.yaml` template includes management services
- `nginx.conf` template includes management port configuration
- Increased minimum RAM recommendation to 4GB (from 2GB)
- Increased minimum disk space to 10GB (from 5GB)
- Network collector now filters virtual interfaces (veth, docker bridges, etc.)
- Status collectors use consistent field names matching frontend expectations
- File Browser uses config file (`.filebrowser.json`) instead of command-line args
- Redis port exposed on localhost (127.0.0.1:6379) for n8n_status connectivity
- Enhanced Cloudflare and Tailscale collectors with more detailed metrics
- Status collector URL now configurable
- Cached Keys section defaults to collapsed

### Fixed
- Cloudflare edge_locations, tunnel_id, connector_id now parsed from container logs
- iOS devices now show actual device names instead of "localhost" in Tailscale
- Tailscale peer IPs display correctly in Network tab
- Tailscale self device now included in peers list
- Duplicate scheduled backups prevented with deduplication check
- Atomic row locking for backup job concurrency
- Public website detection unified to use PUBLIC_SITE_ENABLE env var
- Notification target issues (500 error, duplicates, multi-click)
- Various lint errors in Vue components
- File Browser iframe height
- nginx_router health check uses curl instead of wget
- Cloudflare/Tailscale cards showing incorrect status due to field name mismatch
- Network page showing 30+ virtual interfaces instead of physical ones
- File Browser proxy authentication
- Redis connectivity for n8n_status with network_mode: host
- nginx default_server and public website initialization

### Security
- JWT-based authentication for management console
- Minimum 12-character password requirement
- Docker socket mounted read-only
- Optional subnet restriction for management access
- Encrypted storage of sensitive configuration

---

## [2.0.0] - 2025-11-30

### Added
- Fully interactive setup script (no manual file editing required)
- Bare metal support with automatic Docker installation
- DNS provider selection menu (Cloudflare, Route53, Google DNS, DigitalOcean)
- Domain validation with IP matching verification
- Auto-generated secure passwords and encryption keys
- Customizable container names
- Portainer Agent support (optional)
- Comprehensive post-deployment testing
- macOS support via Docker Desktop
- WSL2 support for Windows users
- Proxmox LXC container support with configuration guidance

### Changed
- Complete rewrite of setup.sh for interactive experience
- Improved error handling and user feedback
- Color-coded output with progress indicators
- Section headers for better navigation

### Fixed
- SSL certificate renewal reliability
- Database connection handling
- nginx configuration validation

---

## [1.0.0] - 2025-01

### Added
- Initial release
- n8n with PostgreSQL backend
- PostgreSQL 16 with pgvector extension
- Nginx reverse proxy with SSL termination
- Let's Encrypt SSL certificates via DNS-01 challenge
- Cloudflare DNS support
- Docker Compose deployment
- Basic setup.sh script
