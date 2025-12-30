# n8n Management API Reference

Base URL: `https://your-domain.com:{port}/api`

All endpoints except `/auth/login` and `/health` require authentication via Bearer token.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Health Check](#health-check)
3. [Backups](#backups)
4. [Containers](#containers)
5. [Workflows](#workflows)
6. [System](#system)
7. [Notifications](#notifications)
8. [Settings](#settings)

### Other Documentation

- [Backup Guide](./BACKUP_GUIDE.md) - Backup and restore procedures
- [Certbot Guide](./CERTBOT.md) - SSL certificate management
- [Cloudflare Guide](./CLOUDFLARE.md) - Cloudflare Tunnel setup
- [Migration Guide](./MIGRATION.md) - Upgrading from v2.0 to v3.0
- [Notifications Guide](./NOTIFICATIONS.md) - Alert and notification setup
- [Tailscale Guide](./TAILSCALE.md) - Tailscale VPN integration
- [Troubleshooting](./TROUBLESHOOTING.md) - Common issues and solutions

---

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

### Verify Session

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

**Backup Types:**
- `postgres_full` - Complete PostgreSQL dump of all databases
- `postgres_n8n` - n8n database only
- `n8n_config` - n8n configuration files

### Download Backup

```http
GET /backups/download/{id}
Authorization: Bearer {token}
```

Returns file stream with appropriate `Content-Disposition` header.

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

**Frequency Options:**
- `hourly` - Runs every hour at specified minute
- `daily` - Runs daily at specified hour and minute
- `weekly` - Runs weekly on specified day, hour, and minute
- `monthly` - Runs monthly on specified day, hour, and minute

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
- `apprise` - Apprise URL format (supports 80+ services)
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

**Priority Levels:**
- `low` - Informational
- `normal` - Standard priority
- `high` - Important
- `critical` - Requires immediate attention

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

**Response:**
```json
[
  {
    "name": "n8n",
    "cpu_percent": 2.5,
    "memory_usage": 268435456,
    "memory_limit": 4294967296,
    "memory_percent": 6.25,
    "network_rx": 1048576,
    "network_tx": 2097152
  }
]
```

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

**Response:**
```json
[
  {
    "id": "abc-123",
    "name": "My Workflow",
    "active": true,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-15T12:00:00Z"
  }
]
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

**Response:**
```json
{
  "configured": true,
  "connected": true,
  "server": "192.168.1.100",
  "path": "/backups",
  "mount_point": "/mnt/nfs",
  "last_check": "2024-01-15T12:00:00Z"
}
```

### Power Control

```http
POST /system/power/{action}
Authorization: Bearer {token}
```

**Actions:**
- `restart_all` - Restart all containers
- `stop_all` - Stop all containers
- `restart_host` - Restart host system (requires confirmation)
- `shutdown_host` - Shutdown host system (requires confirmation)

---

## Settings

### Get Settings

```http
GET /settings
Authorization: Bearer {token}
```

**Response:**
```json
{
  "timezone": "America/New_York",
  "session_timeout_hours": 24,
  "backup_retention": {
    "daily": 7,
    "weekly": 4,
    "monthly": 12
  },
  "notifications_enabled": true
}
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

**Providers:**
- `gmail_relay` - Gmail corporate relay
- `smtp` - Custom SMTP server
- `sendgrid` - SendGrid API
- `mailgun` - Mailgun API
- `ses` - AWS SES

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
  "version": "3.0.0",
  "components": {
    "database": "healthy",
    "n8n": "healthy",
    "nfs": "not_configured"
  }
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

---

## Rate Limiting

The API implements rate limiting to prevent abuse:

| Endpoint Type | Limit |
|---------------|-------|
| Authentication | 5 requests/minute |
| Read operations | 100 requests/minute |
| Write operations | 30 requests/minute |
| Power controls | 1 request/minute |

When rate limited, the API returns HTTP 429 with a `Retry-After` header.

---

## Webhooks

You can configure the management system to send webhooks to external systems when events occur.

### Webhook Payload Format

```json
{
  "event": "backup.completed",
  "timestamp": "2024-01-15T12:00:00Z",
  "data": {
    "backup_id": 123,
    "backup_type": "postgres_n8n",
    "status": "success",
    "file_size": 1048576
  }
}
```

### Webhook Signature

All webhooks include an `X-Signature-256` header containing an HMAC-SHA256 signature of the payload using your webhook secret.

```python
import hmac
import hashlib

def verify_signature(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```
