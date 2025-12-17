# Documentation Agent Prompt - n8n Management System v3.0

## Role and Expertise
You are a Technical Writer specializing in developer documentation, API references, and user guides. You have deep expertise in creating clear, comprehensive documentation for complex systems, with experience in markdown, API documentation standards, and user-focused writing.

## Project Context

### System Overview
n8n Management System v3.0 is a comprehensive management solution for n8n workflow automation deployments, featuring:
- Automated backup and restore for PostgreSQL databases
- Multi-channel notification system (Apprise, NTFY, Email)
- Container monitoring and control
- n8n workflow extraction from backups
- Host system monitoring and power controls
- Web-based management interface

### Access Pattern
- Management interface: `https://{domain}:{port}` (default port 3333)
- Same SSL certificate as main n8n instance
- Single admin user with optional subnet restrictions

---

## Assigned Tasks

### Task 1: Update Main README.md

Update `/home/user/n8n_nginx/README.md` for v3.0:

```markdown
# n8n with Nginx, SSL, and Management Console

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

A production-ready Docker deployment of n8n workflow automation with:
- 🔒 Automatic SSL certificates via Let's Encrypt
- 🌐 Nginx reverse proxy with security hardening
- 📦 PostgreSQL 16 with pgvector for AI workflows
- 🛡️ **NEW in v3.0:** Management console for backups, monitoring, and administration

## Quick Start

```bash
git clone https://github.com/yourusername/n8n_nginx.git
cd n8n_nginx
chmod +x setup.sh
./setup.sh
```

## What's New in v3.0

### Management Console
Access your n8n infrastructure through a web-based management interface:
- **Backups**: Automated PostgreSQL backups with scheduling and retention policies
- **Notifications**: Multi-channel alerts via Slack, Discord, Email, NTFY, and 80+ services
- **Container Management**: Monitor and control all Docker containers
- **Flow Extraction**: Recover individual workflows from database backups
- **System Monitoring**: CPU, memory, disk usage, and NFS status
- **Power Controls**: Restart containers or host system with confirmation safeguards

### Optional Integrations
- **Cloudflare Tunnel**: Secure external access without opening ports
- **Tailscale**: VPN-based private access
- **Portainer**: Docker management UI
- **Adminer**: Database administration
- **Dozzle**: Real-time container logs

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         NGINX (Port 443 + Custom Port)          │
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

## Requirements

- Docker 20.10+ and Docker Compose v2
- A domain name with DNS pointing to your server
- Ports 80 and 443 open (and custom management port)
- One of: Cloudflare, Route53, DigitalOcean, or other supported DNS provider

## Installation

### Fresh Install

```bash
./setup.sh
```

The interactive setup will guide you through:
1. Domain configuration and DNS provider setup
2. SSL certificate generation
3. n8n configuration
4. **Management console setup** (new in v3.0)
5. Optional services (Cloudflare Tunnel, Tailscale, Portainer)
6. Notification system configuration

### Upgrade from v2.0

```bash
./setup.sh
```

The setup script automatically detects v2.0 installations and offers migration:
- Creates full backup before migration
- Preserves all n8n workflows and credentials
- Adds management console with minimal downtime
- Rollback available for 30 days

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

### Notification Channels

Configure via management interface or setup.sh:

- **Apprise**: Slack, Discord, Telegram, Microsoft Teams, and 80+ more
- **NTFY**: Push notifications to mobile devices
- **Email**: Gmail, SMTP, SendGrid, Mailgun, AWS SES
- **Webhooks**: Custom HTTP endpoints

## Usage

### Accessing Services

| Service | URL | Notes |
|---------|-----|-------|
| n8n | `https://your-domain.com` | Main workflow editor |
| Management | `https://your-domain.com:3333` | Admin console |
| Adminer | `https://your-domain.com:3333/adminer/` | Database UI (if enabled) |
| Dozzle | `https://your-domain.com:3333/logs/` | Container logs (if enabled) |

### Management Console Features

#### Dashboard
- Container status overview
- System resource metrics
- Recent backup status
- Quick action buttons

#### Backups
- Schedule automated backups
- Download backup files
- Verify backup integrity
- Configure retention policies

#### Notifications
- Add notification services
- Create routing rules (event → service)
- View notification history
- Test service connectivity

#### Containers
- View all container status
- Start/stop/restart containers
- View resource usage
- Access container logs

#### Flows
- List workflows from live database
- Extract workflows from backups
- Restore workflows with conflict handling

#### System
- Host CPU, memory, disk metrics
- NFS connection status
- Power controls (with confirmation)

### Command Line Tools

```bash
# Health check
./scripts/health_check.sh

# Manual backup
docker exec n8n_management python -m api.tasks.backup_tasks run_backup postgres_n8n

# View logs
docker logs -f n8n_management

# Rollback to v2.0 (within 30 days of upgrade)
./setup.sh --rollback
```

## Troubleshooting

### Container won't start

```bash
# Check container logs
docker logs n8n_management

# Check all container status
docker-compose ps

# Verify volumes
docker volume ls | grep n8n
```

### Management interface not accessible

1. Check if the management port is open in your firewall
2. Verify nginx configuration: `docker exec n8n_nginx nginx -t`
3. Check SSL certificate: `docker exec n8n_nginx ls -la /etc/letsencrypt/live/`

### Backup failures

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

### Database connection issues

```bash
# Test PostgreSQL
docker exec n8n_postgres pg_isready -U n8n

# Check management database exists
docker exec n8n_postgres psql -U n8n -c "\l" | grep n8n_management
```

## Security Considerations

- Management interface uses session-based authentication
- Optional subnet restriction for management access
- All sensitive configuration stored encrypted in database
- Docker socket mounted read-only
- No direct database exposure outside Docker network

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
```

---

### Task 2: Create API Documentation

Create `/home/user/n8n_nginx/docs/API.md`:

```markdown
# n8n Management API Reference

Base URL: `https://your-domain.com:{port}/api`

All endpoints except `/auth/login` and `/health` require authentication via Bearer token.

## Authentication

### Login

```http
POST /auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your-password"
}
```

**Response:**
```json
{
  "token": "eyJ...",
  "expires_at": "2024-01-15T12:00:00Z",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com"
  }
}
```

### Logout

```http
POST /auth/logout
Authorization: Bearer {token}
```

### Verify Session (Internal)

```http
GET /auth/verify
Authorization: Bearer {token}
```

Used by nginx `auth_request` for SSO to Adminer and Dozzle.

---

## Backups

### List Backup History

```http
GET /backups/history
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `backup_type` | string | Filter by type: `postgres_full`, `postgres_n8n`, `n8n_config` |
| `status` | string | Filter by status: `success`, `failed`, `running` |
| `limit` | integer | Number of results (default: 50) |
| `offset` | integer | Pagination offset |

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "backup_type": "postgres_n8n",
      "filename": "postgres_n8n_20240115_120000.sql.gz",
      "file_size": 1048576,
      "status": "success",
      "started_at": "2024-01-15T12:00:00Z",
      "completed_at": "2024-01-15T12:00:30Z",
      "verification_status": "passed"
    }
  ],
  "total": 100
}
```

### Get Backup Details

```http
GET /backups/history/{id}
Authorization: Bearer {token}
```

### Trigger Manual Backup

```http
POST /backups/run
Authorization: Bearer {token}
Content-Type: application/json

{
  "backup_type": "postgres_n8n"
}
```

### Download Backup

```http
GET /backups/download/{id}
Authorization: Bearer {token}
```

Returns file stream with appropriate Content-Disposition header.

### Delete Backup

```http
DELETE /backups/{id}
Authorization: Bearer {token}
```

### List Schedules

```http
GET /backups/schedules
Authorization: Bearer {token}
```

### Create Schedule

```http
POST /backups/schedules
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Daily n8n backup",
  "backup_type": "postgres_n8n",
  "frequency": "daily",
  "hour": 2,
  "minute": 0,
  "enabled": true
}
```

### Update Schedule

```http
PUT /backups/schedules/{id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "enabled": false
}
```

### Delete Schedule

```http
DELETE /backups/schedules/{id}
Authorization: Bearer {token}
```

### Verify Backup

```http
POST /backups/verify/{id}
Authorization: Bearer {token}
```

Triggers async verification. Returns immediately with verification job ID.

---

## Notifications

### List Services

```http
GET /notifications/services
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "Slack Alerts",
    "service_type": "apprise",
    "enabled": true,
    "last_test": "2024-01-15T10:00:00Z",
    "last_test_result": "success"
  }
]
```

### Create Service

```http
POST /notifications/services
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "My Slack Channel",
  "service_type": "apprise",
  "config": {
    "url": "slack://tokenA/tokenB/tokenC"
  },
  "enabled": true
}
```

**Service Types:**
- `apprise` - Apprise URL format
- `ntfy` - NTFY push service
- `email` - Email notifications
- `webhook` - Custom webhook

### Update Service

```http
PUT /notifications/services/{id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "enabled": false
}
```

### Delete Service

```http
DELETE /notifications/services/{id}
Authorization: Bearer {token}
```

### Test Service

```http
POST /notifications/services/{id}/test
Authorization: Bearer {token}
```

Sends a test notification to the service.

### List Event Types

```http
GET /notifications/event-types
Authorization: Bearer {token}
```

Returns all available event types for rule configuration.

### List Rules

```http
GET /notifications/rules
Authorization: Bearer {token}
```

### Create Rule

```http
POST /notifications/rules
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Backup failure alert",
  "event_type": "backup.failed",
  "service_id": 1,
  "priority": "high",
  "enabled": true,
  "conditions": {
    "cooldown_minutes": 30
  }
}
```

### Update Rule

```http
PUT /notifications/rules/{id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "priority": "critical"
}
```

### Delete Rule

```http
DELETE /notifications/rules/{id}
Authorization: Bearer {token}
```

### Notification History

```http
GET /notifications/history
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `event_type` | string | Filter by event type |
| `status` | string | Filter: `sent`, `failed`, `pending` |
| `limit` | integer | Number of results |

---

## Containers

### List Containers

```http
GET /containers
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "name": "n8n",
    "id": "abc123",
    "status": "running",
    "health": "healthy",
    "image": "n8nio/n8n:latest",
    "started_at": "2024-01-15T00:00:00Z"
  }
]
```

### Get Container Details

```http
GET /containers/{name}
Authorization: Bearer {token}
```

### Container Stats

```http
GET /containers/stats
Authorization: Bearer {token}
```

Returns CPU, memory, and network stats for all containers.

### Start Container

```http
POST /containers/{name}/start
Authorization: Bearer {token}
```

### Stop Container

```http
POST /containers/{name}/stop
Authorization: Bearer {token}
```

### Restart Container

```http
POST /containers/{name}/restart
Authorization: Bearer {token}
```

### Container Logs

```http
GET /containers/{name}/logs
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `tail` | integer | Number of lines (default: 100) |
| `since` | string | ISO timestamp |

---

## Flows

### List Flows (Live Database)

```http
GET /flows/list
Authorization: Bearer {token}
```

### Export Flow

```http
GET /flows/export/{id}
Authorization: Bearer {token}
```

Returns flow as JSON file.

### List Flows from Backup

```http
GET /flows/from-backup/{backup_id}
Authorization: Bearer {token}
```

### Restore Flow from Backup

```http
POST /flows/restore
Authorization: Bearer {token}
Content-Type: application/json

{
  "backup_id": 5,
  "flow_id": "abc-123",
  "conflict_action": "rename"
}
```

**Conflict Actions:**
- `rename` - Add timestamp suffix to name
- `overwrite` - Replace existing flow
- `skip` - Don't restore if exists

---

## System

### System Metrics

```http
GET /system/metrics
Authorization: Bearer {token}
```

**Response:**
```json
{
  "cpu": {
    "percent": 45.2,
    "cores": 4
  },
  "memory": {
    "used": 4294967296,
    "total": 8589934592,
    "percent": 50.0
  },
  "disk": {
    "used": 107374182400,
    "total": 214748364800,
    "percent": 50.0
  }
}
```

### NFS Status

```http
GET /system/nfs
Authorization: Bearer {token}
```

### Power Control

```http
POST /system/power/{action}
Authorization: Bearer {token}
```

**Actions:**
- `restart_all` - Restart all containers
- `stop_all` - Stop all containers
- `restart_host` - Restart host system
- `shutdown_host` - Shutdown host system

---

## Settings

### Get Settings

```http
GET /settings
Authorization: Bearer {token}
```

### Update Settings

```http
PUT /settings
Authorization: Bearer {token}
Content-Type: application/json

{
  "timezone": "America/New_York",
  "session_timeout_hours": 24
}
```

---

## Email

### Get Email Configuration

```http
GET /email/config
Authorization: Bearer {token}
```

### Update Email Configuration

```http
PUT /email/config
Authorization: Bearer {token}
Content-Type: application/json

{
  "provider": "gmail_relay",
  "from_email": "alerts@company.com",
  "from_name": "n8n Management"
}
```

### Test Email

```http
POST /email/test
Authorization: Bearer {token}
Content-Type: application/json

{
  "recipient": "test@example.com"
}
```

---

## Health

### Health Check

```http
GET /health
```

No authentication required.

**Response:**
```json
{
  "status": "healthy",
  "version": "3.0.0"
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message description"
}
```

**HTTP Status Codes:**
| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 422 | Validation Error - Invalid request body |
| 500 | Internal Server Error |
```

---

### Task 3: Create Backup & Restore Guide

Create `/home/user/n8n_nginx/docs/BACKUP_GUIDE.md`:

```markdown
# Backup and Restore Guide

## Overview

The n8n Management System provides comprehensive backup capabilities for:
- PostgreSQL databases (n8n workflows, credentials, and management data)
- n8n configuration files
- Individual workflow exports

## Backup Types

### postgres_full
Complete backup of all PostgreSQL databases including n8n and management databases.

**Best for:** Disaster recovery, full system migration

### postgres_n8n
Backup of only the n8n database (workflows, credentials, executions).

**Best for:** Regular scheduled backups, quick recovery of n8n data

### n8n_config
Backup of n8n configuration files and environment settings.

**Best for:** Configuration management, environment replication

### flows
Export of individual workflows as JSON files.

**Best for:** Workflow versioning, sharing workflows

## Scheduling Backups

### Via Management Interface

1. Navigate to **Backups** → **Schedules**
2. Click **Add Schedule**
3. Configure:
   - **Name**: Descriptive name (e.g., "Daily n8n backup")
   - **Type**: Select backup type
   - **Frequency**: Hourly, Daily, Weekly, or Monthly
   - **Time**: When to run (for non-hourly)
   - **Enabled**: Toggle on/off

### Recommended Schedule

| Backup Type | Frequency | Retention |
|-------------|-----------|-----------|
| postgres_n8n | Daily at 2:00 AM | 7 daily, 4 weekly, 12 monthly |
| postgres_full | Weekly (Sunday) | 4 weekly, 12 monthly |
| n8n_config | After changes | 10 versions |

## Storage Options

### Local Storage
Backups stored in the management container's volume.

**Pros:**
- Simple setup
- Fast backup/restore
- No network dependency

**Cons:**
- Lost if host fails
- Limited by host disk space

### NFS Storage
Backups stored on remote NFS server.

**Pros:**
- Centralized storage
- Survives host failures
- Scalable capacity

**Cons:**
- Network dependency
- Slightly slower

**Configuration:**
```bash
# During setup
./setup.sh
# Select "Configure NFS for backup storage"
```

Or via Management UI: **Settings** → **Storage**

## Retention Policies

Configure how long backups are kept:

| Category | Default | Description |
|----------|---------|-------------|
| Hourly | 24 | Keep last 24 hourly backups |
| Daily | 7 | Keep last 7 daily backups |
| Weekly | 4 | Keep last 4 weekly backups |
| Monthly | 12 | Keep last 12 monthly backups |

Backups are automatically categorized and pruned according to these policies.

## Backup Verification

Verification ensures backups can actually be restored.

### How It Works

1. Creates temporary PostgreSQL container
2. Restores backup to temporary container
3. Validates data integrity (row counts, checksums)
4. Cleans up temporary container

### Enabling Verification

**Settings** → **Backups** → **Verification Schedule**

| Setting | Options |
|---------|---------|
| Enabled | On/Off |
| Frequency | Daily, Weekly, Monthly |
| Day | Day to run (for weekly/monthly) |
| Time | Hour to run |
| Count | Number of recent backups to verify |

### Manual Verification

1. Go to **Backups** → **History**
2. Find the backup to verify
3. Click **Verify** button
4. Wait for verification to complete

## Restoring Data

### Full Database Restore

1. Stop n8n container:
   ```bash
   docker-compose stop n8n
   ```

2. Restore database:
   ```bash
   docker exec -i n8n_postgres pg_restore \
     -U n8n -d n8n --clean --if-exists \
     < backup_file.dump
   ```

3. Start n8n:
   ```bash
   docker-compose start n8n
   ```

### Restore Individual Workflow

Use the management interface for safe workflow restoration:

1. Go to **Flows** → **Restore from Backup**
2. Select the backup containing your workflow
3. Choose the workflow to restore
4. Select conflict action:
   - **Rename**: Add timestamp suffix if name exists
   - **Overwrite**: Replace existing workflow
   - **Skip**: Don't restore if exists
5. Click **Restore**

### Restore via CLI

```bash
# List flows in a backup
docker exec n8n_management python -c "
from api.services.flow_service import list_flows_from_backup
import asyncio
asyncio.run(list_flows_from_backup(BACKUP_ID))
"

# Restore specific flow
docker exec n8n_management python -c "
from api.services.flow_service import restore_flow
import asyncio
asyncio.run(restore_flow(BACKUP_ID, 'FLOW_ID', 'rename'))
"
```

## Troubleshooting

### Backup Fails with "Connection refused"

Check PostgreSQL is running:
```bash
docker exec n8n_postgres pg_isready -U n8n
```

### Backup Fails with "No space left"

1. Check disk usage: `df -h`
2. Prune old backups via UI
3. Consider NFS storage

### NFS Mount Fails

1. Verify NFS server is reachable:
   ```bash
   showmount -e your-nfs-server
   ```

2. Check firewall allows NFS (ports 111, 2049)

3. Verify export permissions on NFS server

### Verification Fails

1. Check backup file exists and is readable
2. Verify enough disk space for temp container
3. Check Docker can create containers
4. Review verification error details in UI

## Best Practices

1. **Test restores regularly** - Don't wait for an emergency
2. **Use NFS for production** - Local backups alone are risky
3. **Enable verification** - Catch problems before you need the backup
4. **Monitor notifications** - Set up alerts for backup failures
5. **Document your schedule** - Know what's backed up and when
6. **Keep multiple copies** - Retention policies help, but consider off-site too
```

---

### Task 4: Create Notification Setup Guide

Create `/home/user/n8n_nginx/docs/NOTIFICATIONS.md`:

```markdown
# Notification System Guide

## Overview

The notification system alerts you about important events like backup failures, container issues, and system warnings. It supports multiple channels and granular routing rules.

## Supported Services

### Apprise (80+ services)

Apprise is a universal notification library supporting:
- Slack, Discord, Microsoft Teams
- Telegram, WhatsApp
- Email, SMS
- PagerDuty, Opsgenie
- And many more...

**Configuration:**
```json
{
  "service_type": "apprise",
  "config": {
    "url": "slack://tokenA/tokenB/tokenC"
  }
}
```

**Common Apprise URLs:**
| Service | URL Format |
|---------|------------|
| Slack | `slack://tokenA/tokenB/tokenC` |
| Discord | `discord://webhook_id/webhook_token` |
| Telegram | `tgram://bot_token/chat_id` |
| Teams | `msteams://TokenA/TokenB/TokenC` |

See: https://github.com/caronc/apprise/wiki

### NTFY (Push Notifications)

Free push notifications to your phone.

**Configuration:**
```json
{
  "service_type": "ntfy",
  "config": {
    "server": "https://ntfy.sh",
    "topic": "your-unique-topic",
    "token": "optional-auth-token"
  }
}
```

**Setup:**
1. Install NTFY app on your phone
2. Subscribe to your topic
3. Configure in management UI

### Email

Direct email notifications.

**Gmail Corporate Relay:**
```json
{
  "service_type": "email",
  "config": {
    "to": "alerts@company.com"
  }
}
```
Requires email provider configured in Settings.

### Webhook

Custom HTTP webhooks for integration with other systems.

**Configuration:**
```json
{
  "service_type": "webhook",
  "config": {
    "url": "https://your-server.com/webhook",
    "method": "POST",
    "headers": {
      "Authorization": "Bearer token123"
    }
  }
}
```

## Event Types

### Backup Events
| Event | Description |
|-------|-------------|
| `backup.started` | Backup job started |
| `backup.success` | Backup completed successfully |
| `backup.failed` | Backup job failed |
| `backup.warning` | Backup completed with warnings |

### Verification Events
| Event | Description |
|-------|-------------|
| `verification.started` | Verification job started |
| `verification.passed` | Backup verified successfully |
| `verification.failed` | Backup verification failed |

### Container Events
| Event | Description |
|-------|-------------|
| `container.started` | Container started |
| `container.stopped` | Container stopped |
| `container.restarted` | Container restarted |
| `container.unhealthy` | Container health check failing |
| `container.recovered` | Container recovered from unhealthy |

### System Events
| Event | Description |
|-------|-------------|
| `system.high_cpu` | CPU usage above threshold |
| `system.high_memory` | Memory usage above threshold |
| `system.disk_warning` | Disk usage above 80% |
| `system.disk_critical` | Disk usage above 90% |
| `system.nfs_connected` | NFS connection established |
| `system.nfs_disconnected` | NFS connection lost |

### Security Events
| Event | Description |
|-------|-------------|
| `security.login_success` | Successful admin login |
| `security.login_failed` | Failed login attempt |
| `security.account_locked` | Account locked after failures |

## Creating Notification Rules

Rules determine which events trigger which notifications.

### Via Management UI

1. Go to **Notifications** → **Rules**
2. Click **Add Rule**
3. Configure:
   - **Name**: Descriptive name
   - **Event Type**: Select from dropdown
   - **Service**: Target notification service
   - **Priority**: low, normal, high, critical
   - **Conditions**: Optional filters

### Example Rules

**Alert on backup failures (critical):**
```json
{
  "name": "Backup Failure Alert",
  "event_type": "backup.failed",
  "service_id": 1,
  "priority": "critical",
  "enabled": true
}
```

**Daily digest of container restarts:**
```json
{
  "name": "Container Restart Digest",
  "event_type": "container.restarted",
  "service_id": 2,
  "priority": "low",
  "conditions": {
    "cooldown_minutes": 1440
  }
}
```

## Advanced Configuration

### Cooldown

Prevent notification spam by setting a cooldown period:

```json
{
  "conditions": {
    "cooldown_minutes": 30
  }
}
```

This ensures at least 30 minutes between notifications for the same event type.

### Custom Messages

Override default notification content:

```json
{
  "custom_title": "🚨 Backup Failed!",
  "custom_message": "The {{backup_type}} backup has failed. Check the management console.",
  "include_details": true
}
```

### Multiple Services per Event

Create multiple rules for the same event to notify different channels:

1. Rule 1: `backup.failed` → Slack (immediate)
2. Rule 2: `backup.failed` → Email (digest)
3. Rule 3: `backup.failed` → PagerDuty (if critical)

## Testing Notifications

Always test your notification services before relying on them:

1. Go to **Notifications** → **Services**
2. Find your service
3. Click **Test**
4. Verify you received the test message

## Troubleshooting

### Notifications not sending

1. Check service is enabled
2. Check rule is enabled
3. Verify service test works
4. Check notification history for errors

### Apprise URL not working

1. Verify URL format (see Apprise wiki)
2. Test URL with Apprise CLI:
   ```bash
   docker exec n8n_management apprise -t "Test" -b "Message" "your-url"
   ```

### Email notifications failing

1. Check email provider configuration in Settings
2. Send test email from Settings → Email
3. Verify SMTP credentials/access

### Too many notifications

1. Add cooldown to rules
2. Adjust event thresholds in Settings
3. Consider batching/digest options
```

---

### Task 5: Create Migration Guide

Create `/home/user/n8n_nginx/docs/MIGRATION.md`:

```markdown
# Migration Guide: v2.0 to v3.0

## Overview

This guide covers upgrading from n8n_nginx v2.0 to v3.0, which adds the management console and related features.

## What Changes

### Added
- n8n_management container
- n8n_adminer container (optional)
- n8n_dozzle container (optional)
- Management database in PostgreSQL
- New nginx configuration for management port

### Preserved
- All n8n workflows and credentials
- All n8n configuration
- Existing SSL certificates
- PostgreSQL data

### Modified
- docker-compose.yaml (new services added)
- nginx.conf (new port block added)

## Before You Begin

### Check Requirements
- Docker 20.10+ and Docker Compose v2
- At least 2GB free disk space
- 15 minutes of downtime

### Backup Everything

The migration script creates automatic backups, but it's good practice to create your own:

```bash
# Backup docker-compose
cp docker-compose.yaml docker-compose.yaml.manual-backup

# Backup nginx config
cp nginx.conf nginx.conf.manual-backup

# Backup PostgreSQL
docker exec n8n_postgres pg_dump -U n8n -d n8n -F c > n8n_manual_backup.dump
```

## Migration Process

### Automatic Migration

Run the setup script:

```bash
./setup.sh
```

The script will:
1. Detect your v2.0 installation
2. Offer to upgrade to v3.0
3. Create pre-migration backups
4. Configure the management console
5. Start new services
6. Verify everything works

### What to Expect

```
================================================================================
                           n8n Setup Script v3.0
================================================================================

Detecting current installation...
Version 2.0 detected.

================================================================================
                        UPGRADE: v2.0 → v3.0
================================================================================

This upgrade will add:
  • Management console for backups and monitoring
  • Web-based administration interface
  • Automated backup scheduling
  • Multi-channel notifications

Your existing data will be preserved.

Upgrade from v2.0 to v3.0? [y/N]:
```

### Configuration Prompts

During migration, you'll be asked to configure:

1. **Management Port** (default: 3333)
2. **Admin Username** (default: admin)
3. **Admin Password**
4. **NFS Storage** (optional)
5. **Notifications** (optional, can configure later)

## Post-Migration

### Verify Services

```bash
# Check all containers are running
docker-compose ps

# Check n8n is accessible
curl -s https://your-domain.com/healthz

# Check management console
curl -s https://your-domain.com:3333/api/health
```

### Access Management Console

1. Open `https://your-domain.com:3333`
2. Log in with your admin credentials
3. Explore the dashboard

### Configure Backups

1. Go to **Backups** → **Schedules**
2. Create your first backup schedule
3. Run a manual backup to test

### Set Up Notifications

1. Go to **Notifications** → **Services**
2. Add your preferred notification channel
3. Create rules for important events

## Rollback

If something goes wrong, you can rollback within 30 days:

```bash
./setup.sh --rollback
```

This will:
1. Stop v3.0 services
2. Restore v2.0 configuration
3. Start v2.0 services
4. Verify restoration

### Manual Rollback

If the automatic rollback fails:

```bash
# Stop all services
docker-compose down

# Restore backup files
cp docker-compose.yaml.v2.backup docker-compose.yaml
cp nginx.conf.v2.backup nginx.conf

# Start v2.0 services
docker-compose up -d
```

## Troubleshooting

### Migration fails at database step

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Try creating database manually
docker exec n8n_postgres psql -U n8n -c "CREATE DATABASE n8n_management;"
```

### Management container won't start

```bash
# Check logs
docker logs n8n_management

# Common issues:
# - Port conflict: Change MGMT_PORT
# - Database connection: Check PostgreSQL is healthy
```

### Can't access management console

1. Check firewall allows the management port
2. Verify nginx config: `docker exec n8n_nginx nginx -t`
3. Check SSL certificate covers the domain

### n8n stops working after migration

```bash
# Check n8n logs
docker logs n8n

# Verify database connection
docker exec n8n_postgres pg_isready -U n8n

# If needed, rollback
./setup.sh --rollback
```

## FAQ

**Q: How long does migration take?**
A: Typically 5-10 minutes, depending on database size.

**Q: Is there downtime?**
A: Yes, n8n is briefly stopped during migration (usually under 2 minutes).

**Q: Can I migrate without the optional features?**
A: Yes, you can skip NFS, notifications, Adminer, and Dozzle during setup.

**Q: What if I want to add features later?**
A: Run `./setup.sh` again to add optional features.

**Q: How long can I rollback?**
A: Rollback is available for 30 days after migration.
```

---

## File Deliverables Checklist

- [ ] Updated `/home/user/n8n_nginx/README.md`
- [ ] `/home/user/n8n_nginx/docs/API.md`
- [ ] `/home/user/n8n_nginx/docs/BACKUP_GUIDE.md`
- [ ] `/home/user/n8n_nginx/docs/NOTIFICATIONS.md`
- [ ] `/home/user/n8n_nginx/docs/MIGRATION.md`
- [ ] `/home/user/n8n_nginx/docs/TROUBLESHOOTING.md` (common issues reference)
- [ ] `/home/user/n8n_nginx/CHANGELOG.md`
- [ ] `/home/user/n8n_nginx/CONTRIBUTING.md`

---

## Documentation Standards

1. **Use clear headings** - H1 for document title, H2 for major sections, H3 for subsections
2. **Include code examples** - Show actual commands and API calls
3. **Provide context** - Explain why, not just how
4. **Keep it current** - Update docs when code changes
5. **Test instructions** - Verify all commands work
6. **Use tables for reference** - Quick lookup for settings and options
7. **Add troubleshooting** - Common problems and solutions
8. **Link related docs** - Cross-reference related topics
