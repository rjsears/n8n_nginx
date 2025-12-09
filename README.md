# n8n with Nginx, SSL, and Management Console

<p align="center">
  <img src="./images/n8n_repo_banner.jpg" alt="n8n HTTPS Setup Banner">
</p>

**Version:** 3.0.0
**Release Date:** December 2025

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()
![Last Commit](https://img.shields.io/github/last-commit/rjsears/n8n_nginx)
![Issues](https://img.shields.io/github/issues/rjsears/n8n_nginx)

A production-ready Docker deployment of n8n workflow automation with:
- 🔒 Automatic SSL certificates via Let's Encrypt
- 🌐 Nginx reverse proxy with security hardening
- 📦 PostgreSQL 16 with pgvector for AI workflows
- 🛡️ **NEW in v3.0:** Management console for backups, monitoring, and administration

---

## Table of Contents

- [What's New in v3.0](#whats-new-in-v30)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Management Console](#management-console)
- [Command Line Tools](#command-line-tools)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)

---

## What's New in v3.0

### Management Console

Access your n8n infrastructure through a web-based management interface:

| Feature | Description |
|---------|-------------|
| **Backups** | Automated PostgreSQL backups with scheduling and retention policies |
| **Notifications** | Multi-channel alerts via Slack, Discord, Email, NTFY, and 80+ services |
| **Container Management** | Monitor and control all Docker containers |
| **Flow Extraction** | Recover individual workflows from database backups |
| **System Monitoring** | CPU, memory, disk usage, and NFS status |
| **Power Controls** | Restart containers or host system with confirmation safeguards |

### Enhanced Setup Script

The v3.0 setup script includes:

- **State Management**: Resume interrupted installations
- **Version Detection**: Automatic detection of v2.0 installations with migration support
- **NFS Configuration**: Built-in NFS setup wizard for remote backup storage
- **Notification Setup**: Configure Email, Slack, Discord, or NTFY during installation
- **Rollback Support**: 30-day rollback window for v2→v3 migrations

### Optional Integrations

- **Adminer**: Database administration UI
- **Dozzle**: Real-time container log viewer
- **Cloudflare Tunnel**: Secure external access without opening ports
- **Tailscale**: VPN-based private access
- **Portainer**: Docker management UI

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/rjsears/n8n_nginx.git
cd n8n_nginx

# Run the interactive setup
chmod +x setup.sh
./setup.sh
```

The interactive setup will guide you through:
1. Domain configuration and DNS provider setup
2. SSL certificate generation
3. n8n configuration
4. **Management console setup** (new in v3.0)
5. Optional services (Adminer, Dozzle, Portainer)
6. Notification system configuration

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     NGINX (Port 443 + Custom Port)              │
│   ┌─────────────────────────────┐  ┌─────────────────────────┐  │
│   │     n8n (Port 443)          │  │  Management (Port 3333) │  │
│   └─────────────────────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐  ┌──────────────┐  ┌────────────┐  ┌───────────┐  │
│  │   n8n   │  │  PostgreSQL  │  │ Management │  │  Certbot  │  │
│  │  :5678  │  │    :5432     │  │   :8000    │  │           │  │
│  └─────────┘  └──────────────┘  └────────────┘  └───────────┘  │
│                      │                 │                        │
│              ┌───────┴───────┐         │                        │
│              │  n8n database │         │                        │
│              │  mgmt database│◄────────┘                        │
│              └───────────────┘                                  │
│                                                                 │
│  Optional:  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌───────────┐ │
│             │ Adminer │ │ Dozzle  │ │Cloudflare│ │ Tailscale │ │
│             └─────────┘ └─────────┘ └──────────┘ └───────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Requirements

### Minimum Requirements

- **Server/VPS/Desktop** with:
  - 2 CPU cores (recommended)
  - 2GB RAM minimum (4GB recommended for management console)
  - 10GB disk space
  - Internet access
- **Domain name** with DNS managed by a supported provider
- **DNS API access** (API token/credentials from your DNS provider)

### Supported Operating Systems

| OS | Versions | Auto-Install Docker |
|----|----------|---------------------|
| **Ubuntu** | 20.04, 22.04, 24.04 | ✅ Yes |
| **Debian** | 11, 12 | ✅ Yes |
| **CentOS/RHEL** | 8, 9 | ✅ Yes |
| **Rocky/AlmaLinux** | 8, 9 | ✅ Yes |
| **Fedora** | 38+ | ✅ Yes |
| **macOS** | 10.15+ | ✅ Via Homebrew |

### Supported DNS Providers

- Cloudflare (recommended)
- AWS Route 53
- Google Cloud DNS
- DigitalOcean
- And more via manual configuration

---

## Installation

### Fresh Install

```bash
./setup.sh
```

### Upgrade from v2.0

```bash
./setup.sh
```

The setup script automatically detects v2.0 installations and offers migration:

- Creates full backup before migration
- Preserves all n8n workflows and credentials
- Adds management console with minimal downtime
- Rollback available for 30 days

See [docs/MIGRATION.md](docs/MIGRATION.md) for detailed upgrade instructions.

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DOMAIN` | Your domain name | Required |
| `N8N_ENCRYPTION_KEY` | n8n encryption key | Auto-generated |
| `POSTGRES_PASSWORD` | PostgreSQL password | Auto-generated |
| `MGMT_PORT` | Management interface port | `3333` |
| `MGMT_SECRET_KEY` | Management session secret | Auto-generated |
| `NFS_SERVER` | NFS server for backups | Optional |
| `NFS_PATH` | NFS export path | Optional |

### Backup Configuration

Backups are configured through the management interface:

| Setting | Options | Default |
|---------|---------|---------|
| Frequency | Hourly, Daily, Weekly, Monthly | Daily |
| Retention | Configurable per frequency | 7 daily, 4 weekly, 12 monthly |
| Compression | None, Gzip, Zstd | Gzip |
| Storage | Local, NFS | Local |
| Verification | Enabled/Disabled | Weekly |

See [docs/BACKUP_GUIDE.md](docs/BACKUP_GUIDE.md) for comprehensive backup documentation.

### Notification Channels

Configure via management interface or setup.sh:

- **Apprise**: Slack, Discord, Telegram, Microsoft Teams, and 80+ more
- **NTFY**: Push notifications to mobile devices
- **Email**: Gmail, SMTP, SendGrid, Mailgun, AWS SES
- **Webhooks**: Custom HTTP endpoints

See [docs/NOTIFICATIONS.md](docs/NOTIFICATIONS.md) for notification setup.

---

## Usage

### Accessing Services

| Service | URL | Notes |
|---------|-----|-------|
| n8n | `https://your-domain.com` | Main workflow editor |
| Management | `https://your-domain.com:3333` | Admin console |
| Adminer | `https://your-domain.com:3333/adminer/` | Database UI (if enabled) |
| Dozzle | `https://your-domain.com:3333/logs/` | Container logs (if enabled) |

### Initial Setup

1. **Access n8n**: Open `https://your-domain.com`
2. **Create owner account**: First user becomes admin
3. **Access Management**: Open `https://your-domain.com:3333`
4. **Log in**: Use credentials from setup

---

## Management Console

### Dashboard

- Container status overview
- System resource metrics (CPU, memory, disk)
- Recent backup status
- Quick action buttons

### Backups

- Schedule automated backups
- Download backup files
- Verify backup integrity
- Configure retention policies
- Restore from backups

### Notifications

- Add notification services
- Create routing rules (event → service)
- View notification history
- Test service connectivity

### Containers

- View all container status
- Start/stop/restart containers
- View resource usage
- Access container logs

### Flows

- List workflows from live database
- Extract workflows from backups
- Restore workflows with conflict handling

### System

- Host CPU, memory, disk metrics
- NFS connection status
- Power controls (with confirmation)

---

## Command Line Tools

### Health Check

```bash
./scripts/health_check.sh
```

Performs comprehensive system health checks including:
- Docker container status
- Service connectivity (n8n, PostgreSQL, nginx)
- Resource usage (disk, memory, CPU)
- SSL certificate expiration
- Backup status

### Manual Backup

```bash
docker exec n8n_management python -m api.tasks.backup_tasks run_backup postgres_n8n
```

### View Logs

```bash
# All services
docker compose logs -f

# Management console
docker logs -f n8n_management

# n8n
docker logs -f n8n
```

### Rollback to v2.0

```bash
./setup.sh --rollback
```

Available for 30 days after migration.

---

## Troubleshooting

### Container Won't Start

```bash
# Check container logs
docker logs n8n_management

# Check all container status
docker compose ps

# Verify volumes
docker volume ls | grep n8n
```

### Management Interface Not Accessible

1. Check if the management port is open in your firewall
2. Verify nginx configuration: `docker exec n8n_nginx nginx -t`
3. Check SSL certificate: `docker exec n8n_nginx ls -la /etc/letsencrypt/live/`

### Backup Failures

1. Check NFS connection (if configured):
   ```bash
   docker exec n8n_management cat /app/config/nfs_status.json
   ```
2. Verify PostgreSQL connectivity:
   ```bash
   docker exec n8n_management pg_isready -h postgres -U n8n
   ```
3. Check disk space:
   ```bash
   df -h
   ```

### Database Connection Issues

```bash
# Test PostgreSQL
docker exec n8n_postgres pg_isready -U n8n

# Check management database exists
docker exec n8n_postgres psql -U n8n -c "\l" | grep n8n_management
```

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for more solutions.

---

## Security

### Authentication

- Management interface uses session-based JWT authentication
- Password requirements enforced (minimum 12 characters)
- Optional subnet restriction for management access

### Network Security

- All internal communication within Docker network
- Only ports 443 and management port exposed
- No direct database exposure outside Docker network

### Data Protection

- All sensitive configuration stored encrypted in database
- Docker socket mounted read-only
- Automatic secret generation during setup

### SSL/TLS

- TLS 1.2 and 1.3 only
- Strong cipher suites (ECDHE, AES-GCM)
- Auto-renewal every 12 hours
- Security headers configured

---

## API Documentation

The management console provides a REST API for automation and integration.

See [docs/API.md](docs/API.md) for complete API documentation.

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Reporting Issues

When reporting issues, please include:
- Operating system and version
- Docker and Docker Compose versions
- Full error messages and logs
- Steps to reproduce

---

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [n8n.io](https://n8n.io) - Workflow automation platform
- [Let's Encrypt](https://letsencrypt.org) - Free SSL certificates
- [PostgreSQL](https://www.postgresql.org) - Database
- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity search
- [FastAPI](https://fastapi.tiangolo.com) - Management API framework
- [Vue.js](https://vuejs.org) - Management UI framework

---

## Support

- **Documentation:** [docs/](docs/)
- **Issues:** [GitHub Issues](https://github.com/rjsears/n8n_nginx/issues)
- **Discussions:** [GitHub Discussions](https://github.com/rjsears/n8n_nginx/discussions)
- **n8n Community:** [n8n.io/community](https://n8n.io/community)

---

**Created by Richard J. Sears** - richardjsears@gmail.com
