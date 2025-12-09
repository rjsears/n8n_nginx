# Notification System Guide

## Overview

The notification system alerts you about important events like backup failures, container issues, and system warnings. It supports multiple channels and granular routing rules.

---

## Supported Services

### Apprise (80+ Services)

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

| Service | URL Format | Example |
|---------|------------|---------|
| Slack | `slack://tokenA/tokenB/tokenC` | `slack://T0123/B0456/abcdef` |
| Discord | `discord://webhook_id/webhook_token` | `discord://123456/abcdef` |
| Telegram | `tgram://bot_token/chat_id` | `tgram://123:ABC/987654` |
| Teams | `msteams://TokenA/TokenB/TokenC` | `msteams://abc/def/ghi` |
| Pushover | `pover://user_key/api_token` | `pover://abc123/def456` |
| Email | `mailto://user:pass@host` | `mailto://user:pass@smtp.gmail.com` |

See: https://github.com/caronc/apprise/wiki for complete documentation.

### NTFY (Push Notifications)

Free push notifications to your phone via ntfy.sh or self-hosted server.

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
1. Install NTFY app on your phone (iOS/Android)
2. Subscribe to your topic in the app
3. Configure service in management UI
4. Test the notification

**Self-Hosted NTFY:**
```json
{
  "service_type": "ntfy",
  "config": {
    "server": "https://ntfy.your-domain.com",
    "topic": "n8n-alerts",
    "username": "admin",
    "password": "your-password"
  }
}
```

### Email

Direct email notifications via your email provider.

**Gmail Corporate Relay:**
```json
{
  "service_type": "email",
  "config": {
    "to": "alerts@company.com"
  }
}
```

Requires email provider configured in **Settings** → **Email**.

**SMTP Configuration (in Settings):**
```json
{
  "provider": "smtp",
  "smtp_host": "smtp.your-server.com",
  "smtp_port": 587,
  "smtp_user": "notifications@company.com",
  "smtp_password": "your-password",
  "smtp_tls": true,
  "from_email": "n8n-alerts@company.com",
  "from_name": "n8n Management"
}
```

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
      "Authorization": "Bearer token123",
      "Content-Type": "application/json"
    }
  }
}
```

**Webhook Payload:**
```json
{
  "event": "backup.failed",
  "timestamp": "2024-01-15T12:00:00Z",
  "priority": "high",
  "title": "Backup Failed",
  "message": "The postgres_n8n backup failed: Connection refused",
  "data": {
    "backup_type": "postgres_n8n",
    "error": "Connection refused"
  }
}
```

---

## Event Types

### Backup Events

| Event | Description | Default Priority |
|-------|-------------|------------------|
| `backup.started` | Backup job started | low |
| `backup.success` | Backup completed successfully | normal |
| `backup.failed` | Backup job failed | high |
| `backup.warning` | Backup completed with warnings | normal |

### Verification Events

| Event | Description | Default Priority |
|-------|-------------|------------------|
| `verification.started` | Verification job started | low |
| `verification.passed` | Backup verified successfully | normal |
| `verification.failed` | Backup verification failed | high |

### Container Events

| Event | Description | Default Priority |
|-------|-------------|------------------|
| `container.started` | Container started | low |
| `container.stopped` | Container stopped | normal |
| `container.restarted` | Container restarted | normal |
| `container.unhealthy` | Container health check failing | high |
| `container.recovered` | Container recovered from unhealthy | normal |

### System Events

| Event | Description | Default Priority |
|-------|-------------|------------------|
| `system.high_cpu` | CPU usage above threshold (default 90%) | high |
| `system.high_memory` | Memory usage above threshold (default 90%) | high |
| `system.disk_warning` | Disk usage above 80% | normal |
| `system.disk_critical` | Disk usage above 90% | critical |
| `system.nfs_connected` | NFS connection established | low |
| `system.nfs_disconnected` | NFS connection lost | high |

### Security Events

| Event | Description | Default Priority |
|-------|-------------|------------------|
| `security.login_success` | Successful admin login | low |
| `security.login_failed` | Failed login attempt | normal |
| `security.account_locked` | Account locked after failures | high |

---

## Creating Notification Services

### Via Management UI

1. Go to **Notifications** → **Services**
2. Click **Add Service**
3. Fill in:
   - **Name**: Descriptive name (e.g., "Slack - Ops Channel")
   - **Type**: Select service type
   - **Configuration**: Service-specific settings
   - **Enabled**: Toggle on
4. Click **Test** to verify
5. Click **Save**

### Via API

```bash
curl -X POST https://your-domain.com:3333/api/notifications/services \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Slack Ops Channel",
    "service_type": "apprise",
    "config": {
      "url": "slack://T0123/B0456/abcdef"
    },
    "enabled": true
  }'
```

---

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
4. Click **Save**

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

**Container health alerts:**
```json
{
  "name": "Container Unhealthy Alert",
  "event_type": "container.unhealthy",
  "service_id": 1,
  "priority": "high",
  "enabled": true,
  "conditions": {
    "containers": ["n8n", "n8n_postgres"]
  }
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

**Disk space warning:**
```json
{
  "name": "Disk Space Warning",
  "event_type": "system.disk_warning",
  "service_id": 1,
  "priority": "normal",
  "enabled": true
}
```

---

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
  "custom_message": "The {{backup_type}} backup has failed. Check the management console immediately.",
  "include_details": true
}
```

**Available Variables:**

| Variable | Events | Description |
|----------|--------|-------------|
| `{{backup_type}}` | backup.* | Type of backup |
| `{{container_name}}` | container.* | Name of container |
| `{{error}}` | *.failed | Error message |
| `{{timestamp}}` | all | Event timestamp |
| `{{hostname}}` | all | Server hostname |

### Multiple Services per Event

Create multiple rules for the same event to notify different channels:

```
Rule 1: backup.failed → Slack (immediate, critical)
Rule 2: backup.failed → Email (digest, normal)
Rule 3: backup.failed → PagerDuty (if critical)
```

### Priority Filtering

Route notifications based on priority:

```json
{
  "name": "Critical to PagerDuty",
  "event_type": "*",
  "service_id": 3,
  "conditions": {
    "min_priority": "critical"
  }
}
```

---

## Setting Up Common Services

### Slack

1. Create a Slack App at https://api.slack.com/apps
2. Add **Incoming Webhooks** feature
3. Create webhook for your channel
4. Copy webhook URL
5. Create Apprise service with URL format:
   ```
   slack://TokenA/TokenB/TokenC/#channel
   ```

**Alternative - Direct Webhook:**
```json
{
  "service_type": "webhook",
  "config": {
    "url": "https://hooks.slack.com/services/T00/B00/XXX",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json"
    }
  }
}
```

### Discord

1. Go to Server Settings → Integrations → Webhooks
2. Create webhook
3. Copy webhook URL
4. Create Apprise service:
   ```
   discord://webhook_id/webhook_token
   ```

### Microsoft Teams

1. In Teams channel, click **⋯** → **Connectors**
2. Add **Incoming Webhook**
3. Copy webhook URL
4. Create Apprise service:
   ```
   msteams://TokenA/TokenB/TokenC
   ```

### Telegram

1. Create bot via @BotFather
2. Get bot token
3. Get your chat ID (message @userinfobot)
4. Create Apprise service:
   ```
   tgram://bot_token/chat_id
   ```

### PagerDuty

1. Create integration in PagerDuty
2. Get integration key
3. Create Apprise service:
   ```
   pagerduty://integration_key
   ```

---

## Testing Notifications

Always test your notification services before relying on them.

### Via Management UI

1. Go to **Notifications** → **Services**
2. Find your service
3. Click **Test**
4. Verify you received the test message

### Via API

```bash
curl -X POST https://your-domain.com:3333/api/notifications/services/1/test \
  -H "Authorization: Bearer $TOKEN"
```

### Via CLI

```bash
# Test Apprise directly
docker exec n8n_management apprise -t "Test" -b "Test message" "your-url"

# Test NTFY
docker exec n8n_management curl -d "Test notification" \
  https://ntfy.sh/your-topic
```

---

## Notification History

View past notifications in the management UI:

1. Go to **Notifications** → **History**
2. Filter by:
   - Event type
   - Service
   - Status (sent, failed, pending)
   - Date range
3. Click on notification to see details

### Via API

```bash
curl "https://your-domain.com:3333/api/notifications/history?limit=50" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Troubleshooting

### Notifications Not Sending

1. **Check service is enabled:**
   - Go to **Notifications** → **Services**
   - Verify service is enabled (toggle on)

2. **Check rule is enabled:**
   - Go to **Notifications** → **Rules**
   - Verify rule is enabled

3. **Test service directly:**
   - Click **Test** on the service
   - Check for error message

4. **Check notification history:**
   - Go to **Notifications** → **History**
   - Look for failed notifications with error details

### Apprise URL Not Working

1. **Verify URL format:**
   - Check Apprise documentation for your service
   - Test URL with Apprise CLI:
     ```bash
     docker exec n8n_management apprise -t "Test" -b "Message" "your-url"
     ```

2. **Check network connectivity:**
   ```bash
   docker exec n8n_management curl -v https://your-service-endpoint
   ```

3. **Check credentials:**
   - Verify tokens/API keys are correct
   - Check for expired credentials

### Email Notifications Failing

1. **Check email provider configuration:**
   - Go to **Settings** → **Email**
   - Verify SMTP settings

2. **Send test email:**
   - Go to **Settings** → **Email** → **Test**
   - Check for error messages

3. **Common SMTP issues:**
   - Port blocked by firewall
   - Authentication required
   - TLS/SSL misconfiguration
   - Sender not authorized

### Too Many Notifications

1. **Add cooldown to rules:**
   ```json
   {
     "conditions": {
       "cooldown_minutes": 30
     }
   }
   ```

2. **Adjust event thresholds:**
   - Go to **Settings** → **System**
   - Adjust CPU/memory/disk thresholds

3. **Consider batching:**
   - Create rules with longer cooldowns for informational events
   - Use digest services for non-critical notifications

### NTFY Not Working

1. **Check topic subscription:**
   - Verify you're subscribed to the correct topic in the app
   - Try subscribing again

2. **Check server connectivity:**
   ```bash
   docker exec n8n_management curl https://ntfy.sh/your-topic
   ```

3. **Check authentication:**
   - If using self-hosted NTFY, verify credentials
   - Check token is valid

---

## Best Practices

### 1. Start Simple

Begin with one notification channel for critical events:
- Configure Slack/Discord for `backup.failed`
- Test thoroughly before adding more

### 2. Use Multiple Channels

Don't rely on a single notification method:
- Primary: Slack/Teams for immediate alerts
- Secondary: Email for record keeping
- Critical: PagerDuty/phone for emergencies

### 3. Set Appropriate Priorities

- **Critical**: Requires immediate action (backup failure, disk full)
- **High**: Important but can wait briefly (container unhealthy)
- **Normal**: Should be reviewed soon (backup warnings)
- **Low**: Informational only (successful backups)

### 4. Use Cooldowns Wisely

Prevent alert fatigue:
- Critical events: No cooldown or short (5 min)
- High priority: 15-30 minutes
- Normal: 1-4 hours
- Low/informational: Daily digest

### 5. Test Regularly

- Test notifications monthly
- Verify all channels work after configuration changes
- Include notification testing in disaster recovery drills

### 6. Document Your Setup

- Keep a list of notification channels and purposes
- Document who receives what alerts
- Update documentation when rules change
