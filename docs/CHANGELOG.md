# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-02

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
