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

All backup routes are mounted under the `/api/backups` prefix
(`management/api/main.py: include_router(backups.router, prefix="/api/backups")`).
The router is implemented in `management/api/routers/backups.py` and the
response/request models live in `management/api/schemas/backups.py`.

The endpoints below are grouped by purpose (history, schedules, run, retention,
verification, contents, mount, restore, configuration, pruning, public-website
restore). Field names in the example responses match the actual Pydantic
schemas; see the schema file for the full list of optional fields.

---

#### History — List Backups

Paginated history of every completed (or in-progress) backup. Replaces the
older `GET /api/backups` listing endpoint.

```http
GET /api/backups/history
Authorization: Bearer <token>
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Page size |
| `offset` | integer | 0 | Pagination offset |
| `backup_type` | string | - | Filter by type (e.g., `full`, `database`) |
| `status` | string | - | Filter by status (e.g., `completed`, `failed`, `in_progress`) |

**Response:** `200 OK` — `BackupHistoryPaginatedResponse`
```json
{
  "items": [
    {
      "id": 1,
      "backup_type": "full",
      "schedule_id": 2,
      "filename": "n8n_backup_20260427_120000.tar.gz",
      "filepath": "/app/backups/n8n_backup_20260427_120000.tar.gz",
      "storage_location": "local",
      "file_size": 1048576,
      "compressed_size": 524288,
      "compression": "gzip",
      "checksum": "sha256:...",
      "started_at": "2026-04-27T12:00:00Z",
      "completed_at": "2026-04-27T12:00:42Z",
      "duration_seconds": 42,
      "status": "completed",
      "verification_status": "passed",
      "is_protected": false
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0,
  "has_more": true
}
```

#### History — Count

Lightweight counter, useful for badges and dashboards.

```http
GET /api/backups/history/count
Authorization: Bearer <token>
```

**Response:** `200 OK` — `{ "total": <int> }`

#### History — Single Backup Detail

Full extended record for one backup, including protection and pending-deletion
metadata.

```http
GET /api/backups/history/{backup_id}
Authorization: Bearer <token>
```

**Response:** `200 OK` — `BackupHistoryExtendedResponse`. Adds `is_protected`,
`protected_at`, `protected_reason`, `deletion_status`,
`scheduled_deletion_at`, `deletion_reason` on top of the history fields.

---

#### Run — Trigger Manual Backup

Kick off a backup of the chosen type immediately.

```http
POST /api/backups/run
Authorization: Bearer <token>
```

**Request Body:** `BackupRunRequest`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `backup_type` | string | Yes | Backup type identifier (`full`, `database`, `n8n_db`, `config`, `workflows`) |
| `compression` | string | No | `gzip` (default), `zstd`, or `none` |
| `skip_auto_verify` | boolean | No | Skip the post-backup verification even if it is globally enabled |

**Response:** `200 OK` — `BackupRunResponse`
```json
{ "backup_id": 42, "status": "started", "message": "Full backup started" }
```

#### Run — Trigger Full Backup (everything)

Convenience endpoint for kicking off a complete backup including databases,
config, SSL certs and (if installed) the public-website volume.

```http
POST /api/backups/run-full
Authorization: Bearer <token>
```

**Response:** `200 OK` — `BackupRunResponse`

---

#### Schedules — List

```http
GET /api/backups/schedules
Authorization: Bearer <token>
```

**Response:** `200 OK` — `BackupScheduleResponse[]`
```json
[
  {
    "id": 1,
    "name": "Daily full backup",
    "backup_type": "full",
    "enabled": true,
    "frequency": "daily",
    "hour": 2,
    "minute": 0,
    "timezone": "America/Los_Angeles",
    "compression": "gzip",
    "last_run": "2026-04-27T02:00:00Z",
    "next_run": "2026-04-28T02:00:00Z",
    "created_at": "2026-01-15T00:00:00Z",
    "updated_at": "2026-04-25T00:00:00Z"
  }
]
```

#### Schedules — Create

```http
POST /api/backups/schedules
Authorization: Bearer <token>
```

**Request Body:** schedule definition
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Display name |
| `backup_type` | string | Yes | Backup type identifier |
| `enabled` | boolean | No | Default: `true` |
| `frequency` | string | Yes | `hourly`, `daily`, `weekly`, `monthly` |
| `hour` | integer | conditional | 0–23, required for daily/weekly/monthly |
| `minute` | integer | Yes | 0–59 |
| `day_of_week` | integer | conditional | 0=Mon … 6=Sun, required for weekly |
| `day_of_month` | integer | conditional | 1–31, required for monthly |
| `timezone` | string | No | IANA tz name (default: system tz) |
| `compression` | string | No | `gzip` (default), `zstd`, `none` |

**Response:** `201 Created` — `BackupScheduleResponse`

#### Schedules — Get / Update / Delete

```http
GET    /api/backups/schedules/{schedule_id}
PUT    /api/backups/schedules/{schedule_id}
DELETE /api/backups/schedules/{schedule_id}
```

PUT accepts the same body as create; DELETE returns `SuccessResponse`.

---

#### Download — Full Archive

Stream the backup file with the embedded restore script.

```http
GET /api/backups/download/{backup_id}
Authorization: Bearer <token>
```

**Response:** `200 OK` (binary octet-stream).

#### Download — Data-Only

Stream the data portion of the archive without the bare-metal recovery script.

```http
GET /api/backups/download/{backup_id}/data-only
Authorization: Bearer <token>
```

**Response:** `200 OK` (binary octet-stream).

---

#### Delete Backup

```http
DELETE /api/backups/{backup_id}
Authorization: Bearer <token>
```

**Response:** `200 OK` — `SuccessResponse`. Protected backups are refused
with `409 Conflict`.

#### Protect / Unprotect Backup

Mark a backup as protected from automatic pruning, or remove that mark.

```http
POST /api/backups/{backup_id}/protect
Authorization: Bearer <token>
```

**Request Body:** `BackupProtectRequest`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `protected` | boolean | Yes | True to protect, false to unprotect |
| `reason` | string | No | Optional note (max 200 chars) |

**Response:** `200 OK` — `BackupHistoryExtendedResponse`

#### List Protected Backups

```http
GET /api/backups/protected
Authorization: Bearer <token>
```

**Response:** `200 OK` — `BackupHistoryExtendedResponse[]`

---

#### Retention Policies

Per-backup-type retention rules (the GFS-style daily/weekly/monthly counts).

```http
GET /api/backups/retention
PUT /api/backups/retention/{backup_type}
Authorization: Bearer <token>
```

**Update body:** `RetentionPolicyUpdate`
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `keep_hourly` | integer | 24 | Hourly snapshots to keep (0–168) |
| `keep_daily` | integer | 7 | Daily snapshots to keep (0–90) |
| `keep_weekly` | integer | 4 | Weekly snapshots to keep (0–52) |
| `keep_monthly` | integer | 12 | Monthly snapshots to keep (0–60) |
| `max_total_size_gb` | integer | null | Optional total-size cap |

**Response:** `200 OK` — `RetentionPolicyResponse`

---

#### Verification

Verification can be scheduled, triggered manually, or performed as a quick
integrity-only check.

```http
GET  /api/backups/verification/schedule
PUT  /api/backups/verification/schedule
POST /api/backups/verification/run/{backup_id}
POST /api/backups/{backup_id}/verify
POST /api/backups/{backup_id}/verify/quick
GET  /api/backups/{backup_id}/verification/status
GET  /api/backups/verification/container/status
POST /api/backups/verification/cleanup
Authorization: Bearer <token>
```

**Verification Schedule body:** `VerificationScheduleUpdate`
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | true | Master toggle |
| `frequency` | string | `weekly` | `daily`, `weekly`, `monthly` |
| `day_of_week` | integer | 0 | 0=Mon … 6=Sun |
| `hour` | integer | 3 | Hour to run (0–23) |
| `verify_latest_count` | integer | 5 | How many of the most-recent backups to verify each run (1–20) |

**Run / Quick Verify Response:** `VerifyBackupResponse` / `VerificationRunResponse`
```json
{ "backup_id": 42, "status": "passed", "details": { "checksum": "ok", "archive": "ok", "database": "ok" } }
```

`/{backup_id}/verify` performs the comprehensive verification (loads database
into a temporary container and validates schema, row counts, workflow
checksums); `/{backup_id}/verify/quick` does the integrity-only path.

---

#### Statistics

Aggregate counters for dashboards.

```http
GET /api/backups/stats
Authorization: Bearer <token>
```

**Response:** `200 OK` — `BackupStatsResponse`
```json
{
  "total_backups": 134,
  "successful_backups": 130,
  "failed_backups": 4,
  "total_size_bytes": 12345678901,
  "last_backup": "2026-04-27T12:00:00Z",
  "last_successful_backup": "2026-04-27T12:00:00Z",
  "by_type": { "full": 60, "database": 50, "config": 24 },
  "by_status": { "completed": 130, "failed": 4 }
}
```

---

#### Backup Contents (Browsing)

The contents endpoints surface metadata captured at backup time without
loading the archive into a database. Useful for showing what a backup
contains in the UI.

```http
GET /api/backups/contents/{backup_id}
GET /api/backups/contents/{backup_id}/workflows
GET /api/backups/contents/{backup_id}/config-files
Authorization: Bearer <token>
```

**Response (full contents):** `200 OK` — `BackupContentsResponse` with
`workflow_count`, `credential_count`, `config_file_count`, plus a
`workflows`, `credentials`, `config_files`, `public_website_files`,
`databases` listing (each item is the corresponding `*ManifestItem`).

The `/workflows` and `/config-files` sub-endpoints return just those slices.

---

#### Mount / Unmount (Selective Restore Workspace)

Mounting starts a restore-side helper container with the backup contents
exposed read-only. The mount is required before downloading or restoring
individual workflows, credentials, or config files.

```http
POST /api/backups/{backup_id}/mount
POST /api/backups/{backup_id}/unmount
GET  /api/backups/mount/status
Authorization: Bearer <token>
```

**Mount Response:** `MountBackupResponse`
```json
{
  "status": "success",
  "message": "Backup mounted",
  "backup_id": 42,
  "backup_info": {
    "backup_id": 42,
    "filename": "n8n_backup_20260427.tar.gz",
    "workflow_count": 15,
    "credential_count": 8,
    "mounted_at": "2026-04-27T12:00:00Z"
  },
  "workflows": [{ "id": "abc123", "name": "My Workflow", "active": true }],
  "credentials": [{ "id": "def456", "name": "API Key", "type": "httpHeaderAuth" }]
}
```

**Mount Status Response:** `MountStatusResponse` — same shape as above with
`"mounted": true|false`.

---

#### Selective Restore — Workflows & Credentials

Once a backup is mounted, browse and download or restore individual items.

```http
GET  /api/backups/{backup_id}/restore/workflows
GET  /api/backups/{backup_id}/workflows/{workflow_id}/download
POST /api/backups/{backup_id}/restore/workflow
GET  /api/backups/{backup_id}/credentials/{credential_id}/download
Authorization: Bearer <token>
```

**Restore-workflow body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workflow_id` | string | Yes | Workflow id from the mount listing |
| `rename_format` | string | No | Naming pattern for the imported copy (default `{name}_backup_{date}`) |

**Response:** `WorkflowRestoreResponse`
```json
{ "status": "success", "new_id": "xyz789", "new_name": "My Workflow_backup_20260427", "message": "Workflow restored successfully" }
```

Credential downloads return JSON with the encrypted `data` blob — restoring
to a different instance usually requires re-entering credential values.

---

#### Selective Restore — Config Files

```http
GET  /api/backups/{backup_id}/restore/config-files
GET  /api/backups/{backup_id}/config-files/{config_path:path}/download
POST /api/backups/{backup_id}/restore/config
Authorization: Bearer <token>
```

**Restore-config body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `config_path` | string | Yes | Path within the backup |
| `create_backup` | boolean | No | Snapshot the existing file first (default: `true`) |

---

#### Full / Database / Preview Restore

Restore that doesn't require a separate selective workflow.

```http
GET  /api/backups/{backup_id}/restore/preview
POST /api/backups/{backup_id}/restore/database
POST /api/backups/{backup_id}/restore/full
GET  /api/backups/restore/status
POST /api/backups/restore/cleanup
Authorization: Bearer <token>
```

`/restore/preview` returns a dry-run summary of what will change.
`/restore/database` and `/restore/full` accept an optional
`create_pre_restore_backup` boolean (default `true`).
`/restore/status` reports the running restore session, if any.
`/restore/cleanup` tears down a stuck restore container.

---

#### Configuration

System-wide backup configuration (separate from per-schedule and per-type
retention settings).

```http
GET  /api/backups/configuration
PUT  /api/backups/configuration
POST /api/backups/configuration/validate-path
GET  /api/backups/configuration/detect-storage
Authorization: Bearer <token>
```

**Get/Update Response:** `BackupConfigurationResponse` (selected fields):
```json
{
  "id": 1,
  "primary_storage_path": "/app/backups",
  "nfs_storage_path": null,
  "nfs_enabled": false,
  "storage_preference": "local",
  "compression_enabled": true,
  "compression_algorithm": "gzip",
  "compression_level": 6,
  "retention_enabled": true,
  "retention_daily_count": 7,
  "retention_weekly_count": 4,
  "retention_monthly_count": 12,
  "include_n8n_config": true,
  "include_ssl_certs": true,
  "include_env_files": true,
  "include_public_website": true,
  "auto_verify_enabled": true,
  "verify_after_backup": true,
  "verify_frequency": 1
}
```

`validate-path` checks whether a given filesystem path is writable and has
free space; `detect-storage` returns the recommended storage location based
on what NFS mounts and local disks the host actually exposes.

---

#### Storage & Pruning

Pruning runs as a background job; these endpoints expose the configuration
and let an operator preview / force a pruning pass.

```http
GET  /api/backups/storage/usage
GET  /api/backups/pruning/settings
PUT  /api/backups/pruning/settings
GET  /api/backups/pruning/candidates
GET  /api/backups/pruning/pending
POST /api/backups/pruning/run
POST /api/backups/pruning/execute-pending
POST /api/backups/{backup_id}/cancel-deletion
Authorization: Bearer <token>
```

**Pruning Settings Body / Response:** `BackupPruningSettingsResponse`
```json
{
  "id": 1,
  "time_based_enabled": true,
  "max_age_days": 90,
  "space_based_enabled": true,
  "min_free_space_percent": 20,
  "size_based_enabled": false,
  "max_total_size_gb": 500,
  "notify_before_delete": true,
  "notify_hours_before": 24,
  "critical_space_threshold": 5,
  "critical_space_action": "force_delete_unprotected"
}
```

`pruning/candidates` lists what *would* be removed by the current rules;
`pruning/pending` lists backups already scheduled for deletion (typically
24h ahead so the operator can intervene). `cancel-deletion` rescinds a
pending delete.

---

#### Public-Website Restore

When the optional public-website hosting feature is installed, these
endpoints surface the public-website slice of the backup.

```http
POST /api/backups/restore/{backup_id}/public-website/mount
POST /api/backups/restore/public-website/unmount
GET  /api/backups/restore/public-website/status
GET  /api/backups/restore/{backup_id}/public-website/files
GET  /api/backups/restore/{backup_id}/public-website/preview
GET  /api/backups/restore/{backup_id}/public-website/download
POST /api/backups/restore/{backup_id}/public-website/check
POST /api/backups/restore/{backup_id}/public-website/restore
Authorization: Bearer <token>
```

`/files` lists every file with size and checksum; `/preview` returns the
text/HTML body of a file when it's small enough; `/check` runs a dry-run
restore reporting which files would change; `/restore` performs the actual
copy back into the live volume.

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
