# n8n Management Console API Reference

<p align="center">
  <em>Complete REST API documentation for the n8n Management Console</em>
</p>

<p align="center">
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-Python%203.11+-009688?logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="#authentication"><img src="https://img.shields.io/badge/Auth-JWT%20Bearer-blue" alt="JWT Auth"></a>
  <a href="#"><img src="https://img.shields.io/badge/API%20Version-3.0.0-orange" alt="API Version"></a>
</p>

---

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
  - [Authentication](#authentication-endpoints)
  - [Backups](#backup-endpoints)
  - [Notifications](#notification-endpoints)
  - [NTFY](#ntfy-endpoints)
  - [System Notifications](#system-notification-endpoints)
  - [Containers](#container-endpoints)
  - [Workflows](#workflow-endpoints)
  - [System](#system-endpoints)
  - [Email](#email-endpoints)
  - [Settings](#settings-endpoints)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [WebSocket Endpoints](#websocket-endpoints)
- [OpenAPI Documentation](#openapi-documentation)

### Other Documentation

- [Backup Guide](./BACKUP_GUIDE.md) - Backup and restore procedures
- [Certbot Guide](./CERTBOT.md) - SSL certificate management
- [Cloudflare Guide](./CLOUDFLARE.md) - Cloudflare Tunnel setup
- [Migration Guide](./MIGRATION.md) - Upgrading from v2.0 to v3.0
- [Notifications Guide](./NOTIFICATIONS.md) - Alert and notification setup
- [Tailscale Guide](./TAILSCALE.md) - Tailscale VPN integration
- [Troubleshooting](./TROUBLESHOOTING.md) - Common issues and solutions

---

## Overview

The n8n Management Console API is a RESTful API built with FastAPI that provides comprehensive management capabilities for your n8n deployment. All endpoints return JSON responses.

### Base URL

```
https://your-domain.com/management/api
```

### Content Type

All requests and responses use `application/json` unless otherwise specified.

---

## Authentication

The API uses JWT (JSON Web Token) Bearer authentication. Most endpoints require authentication.

### Obtaining a Token

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your-password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### Using the Token

Include the token in the `Authorization` header:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Token Refresh

```http
POST /api/auth/refresh
Authorization: Bearer <current-token>
```

---

## API Endpoints

### Authentication Endpoints

#### Login

Authenticate and obtain a JWT token.

```http
POST /api/auth/login
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes | Username |
| `password` | string | Yes | Password |

**Response:** `200 OK`
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 86400
}
```

#### Logout

Invalidate the current session.

```http
POST /api/auth/logout
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "message": "Logged out successfully"
}
```

#### Verify Token

Check if the current token is valid.

```http
GET /api/auth/verify
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "valid": true,
  "user": {
    "id": 1,
    "username": "admin"
  }
}
```

#### Change Password

Update the current user's password.

```http
POST /api/auth/change-password
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `current_password` | string | Yes | Current password |
| `new_password` | string | Yes | New password (min 8 characters) |

**Response:** `200 OK`
```json
{
  "message": "Password changed successfully"
}
```

---

### Backup Endpoints

#### List Backups

Get a paginated list of all backups.

```http
GET /api/backups
Authorization: Bearer <token>
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Number of results per page |
| `offset` | integer | 0 | Number of results to skip |
| `status` | string | - | Filter by status (success, failed, in_progress) |

**Response:** `200 OK`
```json
{
  "backups": [
    {
      "id": 1,
      "filename": "n8n_backup_20241220_120000.tar.gz",
      "file_size": 1048576,
      "status": "success",
      "backup_type": "full",
      "created_at": "2024-12-20T12:00:00Z",
      "verified": true,
      "protected": false,
      "description": "Scheduled daily backup"
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

#### Get Backup Details

Get detailed information about a specific backup.

```http
GET /api/backups/{backup_id}
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "filename": "n8n_backup_20241220_120000.tar.gz",
  "file_size": 1048576,
  "status": "success",
  "backup_type": "full",
  "created_at": "2024-12-20T12:00:00Z",
  "verified": true,
  "verified_at": "2024-12-20T12:05:00Z",
  "protected": false,
  "description": "Scheduled daily backup",
  "checksum": "sha256:abc123...",
  "workflows": [
    {
      "id": "workflow-uuid",
      "name": "My Workflow",
      "active": true,
      "node_count": 5
    }
  ]
}
```

#### Create Backup

Trigger a new backup.

```http
POST /api/backups
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `backup_type` | string | No | Type: "full" or "database" (default: "full") |
| `description` | string | No | Optional description |
| `compression` | string | No | Compression: "gzip", "zstd", "none" |

**Response:** `202 Accepted`
```json
{
  "id": 2,
  "status": "in_progress",
  "message": "Backup started"
}
```

#### Get Backup Status

Get the current status of a backup operation.

```http
GET /api/backups/{backup_id}/status
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "id": 2,
  "status": "in_progress",
  "progress": 45,
  "current_step": "Dumping database",
  "started_at": "2024-12-20T12:00:00Z"
}
```

#### Download Backup

Download a backup file.

```http
GET /api/backups/{backup_id}/download
Authorization: Bearer <token>
```

**Response:** `200 OK` (binary file stream)

#### Verify Backup

Verify the integrity of a backup.

```http
POST /api/backups/{backup_id}/verify
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "verified": true,
  "checksum_valid": true,
  "archive_valid": true,
  "database_valid": true,
  "verified_at": "2024-12-20T12:10:00Z"
}
```

#### Restore Backup

Restore from a backup.

```http
POST /api/backups/{backup_id}/restore
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `restore_type` | string | No | "full", "workflows", "credentials" |
| `workflow_ids` | array | No | Specific workflow IDs to restore |
| `overwrite` | boolean | No | Overwrite existing data (default: false) |

**Response:** `202 Accepted`
```json
{
  "restore_id": "restore-uuid",
  "status": "in_progress",
  "message": "Restore started"
}
```

#### Delete Backup

Delete a backup file.

```http
DELETE /api/backups/{backup_id}
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "message": "Backup deleted successfully"
}
```

#### Protect/Unprotect Backup

Toggle backup protection status.

```http
POST /api/backups/{backup_id}/protect
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `protected` | boolean | Yes | Protection status |

**Response:** `200 OK`
```json
{
  "id": 1,
  "protected": true,
  "message": "Backup protection updated"
}
```

#### Get Backup Schedules

List all backup schedules.

```http
GET /api/backups/schedules
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "schedules": [
    {
      "id": 1,
      "name": "Daily Backup",
      "enabled": true,
      "cron_expression": "0 2 * * *",
      "backup_type": "full",
      "retention_days": 30,
      "next_run": "2024-12-21T02:00:00Z"
    }
  ]
}
```

#### Create Backup Schedule

Create a new backup schedule.

```http
POST /api/backups/schedules
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Schedule name |
| `cron_expression` | string | Yes | Cron expression |
| `backup_type` | string | No | "full" or "database" |
| `retention_days` | integer | No | Days to retain backups |
| `enabled` | boolean | No | Enable schedule (default: true) |

**Response:** `201 Created`

#### Update Backup Schedule

```http
PUT /api/backups/schedules/{schedule_id}
Authorization: Bearer <token>
```

#### Delete Backup Schedule

```http
DELETE /api/backups/schedules/{schedule_id}
Authorization: Bearer <token>
```

#### Get Backup Settings

Get backup configuration settings.

```http
GET /api/backups/settings
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "retention": {
    "daily": 7,
    "weekly": 4,
    "monthly": 12
  },
  "compression": "gzip",
  "storage_path": "/app/backups",
  "nfs_enabled": false,
  "auto_verify": true,
  "max_concurrent": 1
}
```

#### Update Backup Settings

```http
PUT /api/backups/settings
Authorization: Bearer <token>
```

#### Mount Backup for Selective Restore

Mount a backup to browse and selectively restore items.

```http
POST /api/backups/{backup_id}/mount
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "status": "success",
  "message": "Backup mounted with 15 workflows and 8 credentials",
  "backup_id": 123,
  "backup_info": {
    "backup_id": 123,
    "filename": "n8n_backup_20241220.tar.gz",
    "workflow_count": 15,
    "credential_count": 8,
    "mounted_at": "2024-12-20T12:00:00Z"
  },
  "workflows": [
    {"id": "abc123", "name": "My Workflow", "active": true}
  ],
  "credentials": [
    {"id": "def456", "name": "API Key", "type": "httpHeaderAuth"}
  ]
}
```

#### Unmount Backup

Unmount a mounted backup and clean up resources.

```http
POST /api/backups/{backup_id}/unmount
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "status": "success",
  "message": "Backup unmounted and container stopped"
}
```

#### Get Mount Status

Check if a backup is currently mounted.

```http
GET /api/backups/mount/status
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "mounted": true,
  "backup_id": 123,
  "backup_info": {
    "backup_id": 123,
    "filename": "n8n_backup_20241220.tar.gz",
    "mounted_at": "2024-12-20T12:00:00Z"
  }
}
```

#### Download Workflow from Backup

Download a specific workflow as JSON from a mounted backup.

```http
GET /api/backups/{backup_id}/workflows/{workflow_id}/download
Authorization: Bearer <token>
```

**Response:** `200 OK` (JSON file download)
```json
{
  "name": "My Workflow",
  "nodes": [...],
  "connections": {...},
  "settings": {...}
}
```

#### Restore Workflow to n8n

Restore a workflow from a mounted backup directly to n8n.

```http
POST /api/backups/{backup_id}/restore/workflow
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workflow_id` | string | Yes | ID of workflow to restore |
| `rename_format` | string | No | Format for new name (default: `{name}_backup_{date}`) |

**Response:** `200 OK`
```json
{
  "status": "success",
  "new_name": "My Workflow_backup_20241220",
  "new_id": "xyz789",
  "message": "Workflow restored successfully"
}
```

#### Download Credential from Backup

Download a specific credential as JSON from a mounted backup.

```http
GET /api/backups/{backup_id}/credentials/{credential_id}/download
Authorization: Bearer <token>
```

**Response:** `200 OK` (JSON file download)
```json
{
  "name": "API Key",
  "type": "httpHeaderAuth",
  "data": {...},
  "_note": "The 'data' field contains encrypted values from the backup. You may need to reconfigure these credentials after import."
}
```

**Note:** Credential data is encrypted. If restoring to a different n8n instance, you may need to reconfigure the values manually.

#### List Config Files in Backup

List configuration files available in a mounted backup.

```http
GET /api/backups/{backup_id}/restore/config-files
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "config_files": [
    {
      "path": "config/.env",
      "name": ".env",
      "size": 1024,
      "is_ssl": false
    },
    {
      "path": "ssl/cert.pem",
      "name": "cert.pem",
      "size": 2048,
      "is_ssl": true
    }
  ]
}
```

#### Download Config File from Backup

Download a specific config file from a mounted backup.

```http
GET /api/backups/{backup_id}/config-files/{config_path}/download
Authorization: Bearer <token>
```

**Response:** `200 OK` (file download)

#### Restore Config File

Restore a config file from backup to the system.

```http
POST /api/backups/{backup_id}/restore/config
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `config_path` | string | Yes | Path of config file in backup |
| `create_backup` | boolean | No | Backup existing file first (default: true) |

**Response:** `200 OK`
```json
{
  "status": "success",
  "message": "Config file restored",
  "backup_created": "/path/to/backup.bak"
}
```

#### Cleanup Restore Container

Manually clean up the restore container if it wasn't properly unmounted.

```http
POST /api/backups/restore/cleanup
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Restore container cleaned up"
}
```

---

### Notification Endpoints

#### List Notification Channels

Get all configured notification channels.

```http
GET /api/notifications/channels
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "channels": [
    {
      "id": 1,
      "name": "Discord Alerts",
      "type": "apprise",
      "enabled": true,
      "priority": "normal",
      "apprise_url": "discord://***",
      "created_at": "2024-12-20T10:00:00Z"
    }
  ]
}
```

#### Create Notification Channel

```http
POST /api/notifications/channels
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Channel name |
| `type` | string | Yes | "apprise", "ntfy", "email", "webhook" |
| `enabled` | boolean | No | Enable channel (default: true) |
| `priority` | string | No | "low", "normal", "high", "critical" |
| `apprise_url` | string | Conditional | Required for apprise type |
| `webhook_url` | string | Conditional | Required for webhook type |

**Response:** `201 Created`

#### Update Notification Channel

```http
PUT /api/notifications/channels/{channel_id}
Authorization: Bearer <token>
```

#### Delete Notification Channel

```http
DELETE /api/notifications/channels/{channel_id}
Authorization: Bearer <token>
```

#### Test Notification Channel

Send a test notification through a channel.

```http
POST /api/notifications/channels/{channel_id}/test
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Test notification sent"
}
```

#### List Notification Groups

```http
GET /api/notifications/groups
Authorization: Bearer <token>
```

#### Create Notification Group

```http
POST /api/notifications/groups
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Group name |
| `channel_ids` | array | Yes | Array of channel IDs |

#### Send Notification

Send a notification through specified channels.

```http
POST /api/notifications/send
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Notification title |
| `message` | string | Yes | Notification body |
| `priority` | string | No | Priority level |
| `channel_ids` | array | No | Specific channels (or uses default) |
| `group_id` | integer | No | Send to a group |

**Response:** `200 OK`
```json
{
  "sent": 3,
  "failed": 0,
  "results": [
    {"channel_id": 1, "success": true},
    {"channel_id": 2, "success": true},
    {"channel_id": 3, "success": true}
  ]
}
```

#### Webhook Receiver

Receive notifications from external sources (e.g., n8n workflows).

```http
POST /api/notifications/webhook
X-API-Key: <webhook-api-key>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Notification title |
| `message` | string | Yes | Notification body |
| `priority` | string | No | Priority level |
| `channel` | string | No | Target channel name |

---

### NTFY Endpoints

#### Get NTFY Configuration

```http
GET /api/ntfy/config
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "server_url": "https://ntfy.example.com",
  "default_topic": "n8n-alerts",
  "auth_enabled": true,
  "configured": true
}
```

#### Update NTFY Configuration

```http
PUT /api/ntfy/config
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `server_url` | string | Yes | NTFY server URL |
| `default_topic` | string | No | Default topic name |
| `username` | string | No | Authentication username |
| `password` | string | No | Authentication password |
| `token` | string | No | Authentication token |

#### List NTFY Topics

```http
GET /api/ntfy/topics
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "topics": [
    {
      "id": 1,
      "name": "n8n-alerts",
      "display_name": "n8n Alerts",
      "default_priority": 3,
      "default_tags": ["n8n", "automation"]
    }
  ]
}
```

#### Create NTFY Topic

```http
POST /api/ntfy/topics
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Topic name (alphanumeric) |
| `display_name` | string | No | Friendly display name |
| `default_priority` | integer | No | Default priority (1-5) |
| `default_tags` | array | No | Default emoji tags |

#### Update NTFY Topic

```http
PUT /api/ntfy/topics/{topic_id}
Authorization: Bearer <token>
```

#### Delete NTFY Topic

```http
DELETE /api/ntfy/topics/{topic_id}
Authorization: Bearer <token>
```

#### Send NTFY Message

Send a message to an NTFY topic.

```http
POST /api/ntfy/send
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `topic` | string | Yes | Topic name |
| `title` | string | No | Message title |
| `message` | string | Yes | Message body |
| `priority` | integer | No | Priority 1-5 (default: 3) |
| `tags` | array | No | Emoji tags |
| `actions` | array | No | Action buttons |
| `click` | string | No | URL to open on click |
| `attach` | string | No | Attachment URL |

**Response:** `200 OK`
```json
{
  "success": true,
  "message_id": "abc123",
  "topic": "n8n-alerts"
}
```

#### Test NTFY Connection

```http
POST /api/ntfy/test
Authorization: Bearer <token>
```

#### Get NTFY Message History

```http
GET /api/ntfy/history
Authorization: Bearer <token>
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Number of messages |
| `topic` | string | - | Filter by topic |

#### List NTFY Templates

```http
GET /api/ntfy/templates
Authorization: Bearer <token>
```

#### Create NTFY Template

```http
POST /api/ntfy/templates
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Template name |
| `title_template` | string | No | Go template for title |
| `body_template` | string | Yes | Go template for body |
| `default_priority` | integer | No | Default priority |
| `default_tags` | array | No | Default tags |

---

### System Notification Endpoints

#### List System Events

Get all configurable system events.

```http
GET /api/system-notifications/events
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "events": [
    {
      "id": 1,
      "event_type": "backup_success",
      "category": "backup",
      "display_name": "Backup Success",
      "description": "Triggered when a backup completes successfully",
      "enabled": true,
      "severity": "info",
      "channel_ids": [1, 2],
      "cooldown_minutes": 5
    }
  ]
}
```

#### Update System Event Configuration

```http
PUT /api/system-notifications/events/{event_type}
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enabled` | boolean | No | Enable/disable event |
| `severity` | string | No | "info", "warning", "critical" |
| `channel_ids` | array | No | Channels to notify |
| `cooldown_minutes` | integer | No | Minimum time between notifications |
| `escalation_enabled` | boolean | No | Enable L2 escalation |
| `escalation_delay_minutes` | integer | No | Delay before escalation |
| `escalation_channel_ids` | array | No | L2 escalation channels |

#### Get Global Notification Settings

```http
GET /api/system-notifications/settings
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "global_enabled": true,
  "maintenance_mode": false,
  "quiet_hours_enabled": false,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "07:00",
  "default_cooldown_minutes": 5,
  "flapping_detection_enabled": true,
  "flapping_threshold": 5,
  "flapping_window_minutes": 10
}
```

#### Update Global Notification Settings

```http
PUT /api/system-notifications/settings
Authorization: Bearer <token>
```

#### Get Container-Specific Settings

```http
GET /api/system-notifications/containers/{container_name}
Authorization: Bearer <token>
```

#### Update Container-Specific Settings

```http
PUT /api/system-notifications/containers/{container_name}
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enabled` | boolean | No | Enable notifications for container |
| `override_events` | object | No | Per-event overrides |
| `cpu_threshold` | integer | No | CPU alert threshold % |
| `memory_threshold` | integer | No | Memory alert threshold % |

#### Get Notification History

```http
GET /api/system-notifications/history
Authorization: Bearer <token>
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Number of entries |
| `event_type` | string | - | Filter by event type |
| `category` | string | - | Filter by category |

---

### Container Endpoints

#### List Containers

Get all Docker containers.

```http
GET /api/containers
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "containers": [
    {
      "id": "abc123def456",
      "name": "n8n",
      "image": "n8nio/n8n:latest",
      "status": "running",
      "state": "running",
      "health": "healthy",
      "created": "2024-12-20T10:00:00Z",
      "ports": ["5678/tcp"],
      "cpu_percent": 2.5,
      "memory_usage": 256000000,
      "memory_limit": 1073741824
    }
  ]
}
```

#### Get Container Details

```http
GET /api/containers/{container_id}
Authorization: Bearer <token>
```

#### Get Container Logs

```http
GET /api/containers/{container_id}/logs
Authorization: Bearer <token>
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tail` | integer | 100 | Number of lines |
| `since` | string | - | Timestamp or duration (e.g., "1h") |
| `timestamps` | boolean | false | Include timestamps |

**Response:** `200 OK`
```json
{
  "logs": "2024-12-20 10:00:00 Starting n8n...\n...",
  "container_id": "abc123def456"
}
```

#### Start Container

```http
POST /api/containers/{container_id}/start
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "message": "Container started",
  "container_id": "abc123def456"
}
```

#### Stop Container

```http
POST /api/containers/{container_id}/stop
Authorization: Bearer <token>
```

#### Restart Container

```http
POST /api/containers/{container_id}/restart
Authorization: Bearer <token>
```

#### Get Container Stats

Get real-time resource statistics.

```http
GET /api/containers/{container_id}/stats
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "cpu_percent": 2.5,
  "memory_usage": 256000000,
  "memory_limit": 1073741824,
  "memory_percent": 23.8,
  "network_rx_bytes": 1048576,
  "network_tx_bytes": 524288,
  "block_read_bytes": 0,
  "block_write_bytes": 1024
}
```

---

### Workflow Endpoints

#### List Workflows

Get all n8n workflows via the n8n API.

```http
GET /api/flows
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "workflows": [
    {
      "id": "workflow-uuid",
      "name": "My Workflow",
      "active": true,
      "created_at": "2024-12-20T10:00:00Z",
      "updated_at": "2024-12-20T12:00:00Z",
      "tags": ["production"],
      "node_count": 5
    }
  ],
  "total": 25
}
```

#### Get Workflow Details

```http
GET /api/flows/{workflow_id}
Authorization: Bearer <token>
```

#### Activate Workflow

```http
POST /api/flows/{workflow_id}/activate
Authorization: Bearer <token>
```

#### Deactivate Workflow

```http
POST /api/flows/{workflow_id}/deactivate
Authorization: Bearer <token>
```

#### Get Workflow Executions

```http
GET /api/flows/{workflow_id}/executions
Authorization: Bearer <token>
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Number of executions |
| `status` | string | - | Filter by status |

#### Deploy Test Workflow

Deploy a test workflow to verify system functionality.

```http
POST /api/flows/test/deploy
Authorization: Bearer <token>
```

---

### System Endpoints

#### Health Check (Public)

Check system health status. Does not require authentication.

```http
GET /api/system/health
```

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "version": "3.0.0",
  "service": "n8n-management",
  "database": "connected",
  "nfs": null
}
```

#### Full Health Check

Comprehensive health check of all components.

```http
GET /api/system/health/full
Authorization: Bearer <token>
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `quick` | boolean | false | Skip slow checks for faster response |

**Response:** `200 OK`
```json
{
  "timestamp": "2024-12-20T12:00:00Z",
  "version": "3.0.0",
  "overall_status": "healthy",
  "warnings": 0,
  "errors": 0,
  "passed": 7,
  "checks": {
    "docker": {"status": "ok", "details": {"running": 5, "stopped": 0}},
    "services": {"status": "ok", "details": {"n8n_api": "ok", "nginx": "ok"}},
    "database": {"status": "ok", "details": {"connection": "ok", "version": "16.0"}},
    "resources": {"status": "ok", "details": {"disk_percent": 45.2, "memory_percent": 62.1}},
    "ssl": {"status": "ok", "details": {"days_until_expiry": 75}},
    "network": {"status": "ok", "details": {"dns": "ok", "internet": "ok"}},
    "backups": {"status": "ok", "details": {"recent_count": 7}}
  }
}
```

#### Get System Metrics

Get current system resource metrics.

```http
GET /api/system/metrics
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "cpu": {
    "percent": 15.2,
    "count": 4
  },
  "memory": {
    "total_bytes": 8589934592,
    "available_bytes": 4294967296,
    "used_bytes": 4294967296,
    "percent": 50.0
  },
  "disk": {
    "total_bytes": 107374182400,
    "used_bytes": 53687091200,
    "free_bytes": 53687091200,
    "percent": 50.0
  },
  "network": {
    "bytes_sent": 1048576,
    "bytes_recv": 2097152
  },
  "timestamp": "2024-12-20T12:00:00Z"
}
```

#### Get Cached Host Metrics

Get host metrics from database cache (faster, includes history).

```http
GET /api/system/host-metrics/cached
Authorization: Bearer <token>
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `history_minutes` | integer | 60 | Minutes of history for charts |

#### Get System Information

```http
GET /api/system/info
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "hostname": "n8n-server",
  "platform": "Linux",
  "platform_release": "5.15.0",
  "architecture": "x86_64",
  "python_version": "3.11.0",
  "boot_time": "2024-12-19T08:00:00Z",
  "uptime_seconds": 100800,
  "uptime_human": "1 day, 4:00:00"
}
```

#### Get Docker Information

```http
GET /api/system/docker/info
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "version": "24.0.7",
  "containers": 5,
  "containers_running": 5,
  "containers_stopped": 0,
  "images": 12,
  "driver": "overlay2",
  "memory_total": 8589934592,
  "cpus": 4
}
```

#### Get Network Information

```http
GET /api/system/network
Authorization: Bearer <token>
```

#### Get SSL Certificate Information

```http
GET /api/system/ssl
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "configured": true,
  "certificates": [
    {
      "domain": "n8n.example.com",
      "type": "Let's Encrypt",
      "valid_from": "Dec 01 00:00:00 2024 GMT",
      "valid_until": "Mar 01 00:00:00 2025 GMT",
      "days_until_expiry": 71,
      "status": "valid"
    }
  ]
}
```

#### Force SSL Certificate Renewal

```http
POST /api/system/ssl/renew
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Certificate renewed and nginx reloaded successfully",
  "nginx_reloaded": true
}
```

#### Get Timezone

```http
GET /api/system/timezone
Authorization: Bearer <token>
```

#### Get Audit Logs

```http
GET /api/system/audit
Authorization: Bearer <token>
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `action` | string | - | Filter by action type |
| `user_id` | integer | - | Filter by user |
| `limit` | integer | 50 | Number of entries |
| `offset` | integer | 0 | Pagination offset |

#### Get Audit Actions

List distinct audit action types.

```http
GET /api/system/audit/actions
Authorization: Bearer <token>
```

#### Get Terminal Targets

List available terminal connection targets.

```http
GET /api/system/terminal/targets
Authorization: Bearer <token>
```

#### Get External Services

Detect external services from nginx configuration.

```http
GET /api/system/external-services
Authorization: Bearer <token>
```

#### Get Tailscale Status

```http
GET /api/system/tailscale
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "installed": true,
  "running": true,
  "logged_in": true,
  "tailscale_ip": "100.64.1.1",
  "hostname": "n8n-server",
  "dns_name": "n8n-server.tailnet.ts.net",
  "peers": [...],
  "peer_count": 5,
  "online_peers": 3
}
```

#### Get Cloudflare Tunnel Status

```http
GET /api/system/cloudflare
Authorization: Bearer <token>
```

#### Get Scheduler Status

```http
GET /api/system/scheduler/status
Authorization: Bearer <token>
```

---

### Email Endpoints

#### Get Email Configuration

```http
GET /api/email/config
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "provider": "smtp",
  "from_email": "noreply@example.com",
  "from_name": "n8n Management",
  "smtp_host": "smtp.example.com",
  "smtp_port": 587,
  "smtp_username": "user@example.com",
  "use_tls": true,
  "configured": true
}
```

#### Update Email Configuration

```http
PUT /api/email/config
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `provider` | string | Yes | "smtp", "sendgrid", "ses" |
| `from_email` | string | Yes | Sender email address |
| `from_name` | string | No | Sender display name |
| `smtp_host` | string | Conditional | SMTP server host |
| `smtp_port` | integer | Conditional | SMTP server port |
| `smtp_username` | string | Conditional | SMTP username |
| `smtp_password` | string | Conditional | SMTP password |
| `use_tls` | boolean | No | Use TLS (default: true) |
| `api_key` | string | Conditional | API key for SendGrid/SES |

#### Send Test Email

```http
POST /api/email/test
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `recipient` | string | Yes | Test recipient email |

#### Get Email Test History

```http
GET /api/email/test-history
Authorization: Bearer <token>
```

#### List Email Templates

```http
GET /api/email/templates
Authorization: Bearer <token>
```

#### Get Email Template

```http
GET /api/email/templates/{template_key}
Authorization: Bearer <token>
```

#### Update Email Template

```http
PUT /api/email/templates/{template_key}
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `subject` | string | No | Email subject |
| `body_html` | string | No | HTML body |
| `body_text` | string | No | Plain text body |

#### Preview Email Template

```http
POST /api/email/templates/preview
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `template_key` | string | Yes | Template identifier |
| `variables` | object | No | Template variables |

---

### Settings Endpoints

#### List All Settings

```http
GET /api/settings
Authorization: Bearer <token>
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | string | Filter by category |

#### List Setting Categories

```http
GET /api/settings/categories
Authorization: Bearer <token>
```

#### Get Setting

```http
GET /api/settings/{key}
Authorization: Bearer <token>
```

#### Update Setting

```http
PUT /api/settings/{key}
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `value` | any | Yes | Setting value |
| `description` | string | No | Optional description |

#### Get System Configuration

```http
GET /api/settings/config/{config_type}
Authorization: Bearer <token>
```

#### Update System Configuration

```http
PUT /api/settings/config/{config_type}
Authorization: Bearer <token>
```

#### Get NFS Status

```http
GET /api/settings/nfs/status
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "status": "connected",
  "message": "NFS mounted and writable",
  "server": "192.168.1.100",
  "path": "/exports/backups",
  "mount_point": "/mnt/nfs",
  "is_mounted": true
}
```

#### Update NFS Configuration

```http
PUT /api/settings/nfs/config
Authorization: Bearer <token>
```

#### Get Access Control Configuration

```http
GET /api/settings/access-control
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "enabled": true,
  "ip_ranges": [
    {
      "cidr": "127.0.0.1/32",
      "description": "Localhost",
      "access_level": "internal",
      "protected": true
    },
    {
      "cidr": "192.168.0.0/16",
      "description": "Local network",
      "access_level": "internal",
      "protected": false
    }
  ]
}
```

#### Update Access Control

```http
PUT /api/settings/access-control
Authorization: Bearer <token>
```

#### Add IP Range

```http
POST /api/settings/access-control/ip
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `cidr` | string | Yes | CIDR notation (e.g., "10.0.0.0/8") |
| `description` | string | No | Description |
| `access_level` | string | No | "internal" or "external" |

#### Delete IP Range

```http
DELETE /api/settings/access-control/ip/{cidr}
Authorization: Bearer <token>
```

#### Reload Nginx

Apply access control changes by reloading nginx.

```http
POST /api/settings/access-control/reload-nginx
Authorization: Bearer <token>
```

#### Get Default IP Ranges

```http
GET /api/settings/access-control/defaults
Authorization: Bearer <token>
```

#### Get External Routes

List all externally accessible routes.

```http
GET /api/settings/external-routes
Authorization: Bearer <token>
```

#### Add External Route

```http
POST /api/settings/external-routes
Authorization: Bearer <token>
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | Yes | URL path (e.g., "/ntfy/") |
| `description` | string | No | Route description |
| `upstream` | string | No | Backend service name |
| `upstream_port` | integer | No | Backend port |
| `is_public` | boolean | No | Public access (default: true) |

#### Delete External Route

```http
DELETE /api/settings/external-routes/{path}
Authorization: Bearer <token>
```

#### Get Environment Variable

```http
GET /api/settings/env/{key}
Authorization: Bearer <token>
```

**Allowed Keys:** `N8N_API_KEY`, `NTFY_TOKEN`, `TAILSCALE_AUTH_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`

#### Update Environment Variable

```http
PUT /api/settings/env/{key}
Authorization: Bearer <token>
```

#### Get Debug Mode

```http
GET /api/settings/debug
Authorization: Bearer <token>
```

#### Set Debug Mode

```http
PUT /api/settings/debug
Authorization: Bearer <token>
```

---

## Error Handling

All errors return a JSON response with appropriate HTTP status codes.

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes

| Code | Description |
|------|-------------|
| `200` | Success |
| `201` | Created |
| `202` | Accepted (async operation started) |
| `400` | Bad Request (invalid input) |
| `401` | Unauthorized (missing/invalid token) |
| `403` | Forbidden (insufficient permissions) |
| `404` | Not Found |
| `409` | Conflict (resource already exists) |
| `422` | Validation Error |
| `500` | Internal Server Error |

### Validation Error Response

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Rate Limiting

The API implements rate limiting to prevent abuse:

| Endpoint Category | Limit |
|-------------------|-------|
| Authentication | 10 requests/minute |
| Backup Operations | 5 requests/minute |
| Notification Sending | 30 requests/minute |
| General API | 100 requests/minute |

Rate limit headers are included in responses:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1703073600
```

When rate limited, the API returns `429 Too Many Requests`:

```json
{
  "detail": "Rate limit exceeded. Try again in 60 seconds."
}
```

---

## WebSocket Endpoints

### Container Logs Stream

Real-time container log streaming.

```
WS /api/ws/containers/{container_id}/logs
Authorization: Bearer <token> (via query param or header)
```

### Terminal Session

Interactive terminal session to containers.

```
WS /api/ws/terminal/{target}
Authorization: Bearer <token>
```

---

## OpenAPI Documentation

Interactive API documentation is available at:

- **Swagger UI**: `https://your-domain.com/management/api/docs`
- **ReDoc**: `https://your-domain.com/management/api/redoc`
- **OpenAPI JSON**: `https://your-domain.com/management/api/openapi.json`

---

<p align="center">
  <em>For more information, see the <a href="README.md">main documentation</a>.</em>
</p>
