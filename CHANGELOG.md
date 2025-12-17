# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2025-12

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

#### Notification System
- Multi-channel notifications via Apprise (80+ services)
- Native support for Slack, Discord, Email, NTFY
- Custom webhook integration
- Event-based notification rules with priority levels
- Cooldown support to prevent notification spam
- Notification history and delivery status tracking

#### System Monitoring
- Host system metrics (CPU, memory, disk)
- NFS connection status monitoring
- SSL certificate expiration tracking
- Container health check integration
- Power controls with confirmation safeguards

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
