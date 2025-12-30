# Notification System Guide

## Overview

The notification system alerts you about important events like backup failures, container issues, and system warnings. All configuration is done through the **Management Console UI** - no manual file editing required.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Notification Channels](#notification-channels)
3. [NTFY Push Notifications](#ntfy-push-notifications)
4. [Event Types](#event-types)
5. [Using the Management Console](#using-the-management-console)
6. [Common Service Setups](#common-service-setups)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

### Other Documentation

- [API Reference](./API.md) - REST API documentation
- [Backup Guide](./BACKUP_GUIDE.md) - Backup and restore procedures
- [Certbot Guide](./CERTBOT.md) - SSL certificate management
- [Cloudflare Guide](./CLOUDFLARE.md) - Cloudflare Tunnel setup
- [Migration Guide](./MIGRATION.md) - Upgrading from v2.0 to v3.0
- [Tailscale Guide](./TAILSCALE.md) - Tailscale VPN integration
- [Troubleshooting](./TROUBLESHOOTING.md) - Common issues and solutions

---

## Quick Start

The notification system enforces a proper setup order to prevent misconfiguration:

### Step 1: Create Notification Channels

Set up where notifications will be sent:

1. Go to **Settings** > **Notifications**
2. Click **Add Channel**
3. Select the service type (Slack, Discord, NTFY, etc.)
4. Fill in the required fields
5. Click **Test** to verify delivery
6. Click **Save**

### Step 2: Create Notification Groups (Optional)

Group channels together for easier management:

1. Go to **Settings** > **Notifications** > **Groups**
2. Create groups like "Critical Alerts" or "Daily Digest"
3. Add channels to groups

### Step 3: Enable Global Event Types

**This is critical** - Global events must be enabled before per-container settings work:

1. Go to **Settings** > **System Notifications** > **Global Event Settings**
2. Expand each category (Backup, Container, Security, SSL, System)
3. Enable the event types you want to monitor
4. Add notification targets using **Quick Setup** > **Apply to All Events**

### Step 4: Configure Per-Container Settings (Optional)

After global events are enabled, customize individual containers:

1. Go to **Settings** > **System Notifications** > **Container Config**
2. Add containers you want custom settings for
3. Toggle which events to monitor per container

### Status Indicators

| Status | Color | Meaning |
|--------|-------|---------|
| **Monitoring** | Green | Properly configured and working |
| **No Targets** | Amber | No notification targets configured |
| **No Global Events** | Red | Global event type not enabled |
| **Disabled** | Gray | Notifications turned off |

---

## Notification Channels

### Supported Services

All channel configuration is done through the Management Console UI. Here are the supported services:

| Service Type | Description | Use Case |
|--------------|-------------|----------|
| **Apprise** | Universal notification library (80+ services) | Slack, Discord, Teams, Telegram, etc. |
| **NTFY** | Push notifications to phone | Mobile alerts |
| **Email** | SMTP email | Record keeping, digests |
| **Webhook** | Custom HTTP endpoints | Integration with other systems |

### Apprise (Recommended for Chat Services)

Apprise is a universal notification library that supports 80+ services with a simple URL format.

**Adding an Apprise Channel:**

1. Go to **Settings** > **Notifications** > **Add Channel**
2. Select **Apprise**
3. Enter a name (e.g., "Slack - Ops Channel")
4. Enter the Apprise URL for your service
5. Test and save

**Common Apprise URL Formats:**

| Service | URL Format |
|---------|------------|
| Slack | `slack://TokenA/TokenB/TokenC/#channel` |
| Discord | `discord://webhook_id/webhook_token` |
| Telegram | `tgram://bot_token/chat_id` |
| Microsoft Teams | `msteams://TokenA/TokenB/TokenC` |
| Pushover | `pover://user_key/api_token` |
| Email | `mailto://user:pass@smtp.gmail.com` |

For complete documentation: https://github.com/caronc/apprise/wiki

### Email

Email notifications use your configured email provider.

**Setup:**

1. First, configure your email provider in **Settings** > **Email**
2. Then go to **Settings** > **Notifications** > **Add Channel**
3. Select **Email**
4. Enter recipient email addresses
5. Test and save

### Webhook

Custom HTTP webhooks for integration with other systems.

**Adding a Webhook Channel:**

1. Go to **Settings** > **Notifications** > **Add Channel**
2. Select **Webhook**
3. Enter the webhook URL
4. Optionally add headers (like Authorization)
5. Test and save

**Payload Format:**

When an event triggers, the webhook receives a JSON payload like:

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

## NTFY Push Notifications

NTFY provides instant push notifications to your phone. There are two options:

### Option 1: Public ntfy.sh (Recommended for Getting Started)

The free public server at `ntfy.sh` - no setup required.

**Pros:**
- Zero setup - just subscribe to a topic
- Free for personal use
- Works immediately

**Cons:**
- Topics are public (anyone who guesses your topic can see messages)
- No authentication by default
- Subject to rate limits
- Limited customization

**Setup:**

1. Install the NTFY app on your phone ([iOS](https://apps.apple.com/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy))
2. Subscribe to a unique topic (e.g., `n8n-alerts-8472xkj`)
3. In Management Console, go to **Settings** > **Notifications** > **Add Channel**
4. Select **NTFY**
5. Server: `https://ntfy.sh`
6. Topic: your unique topic name
7. Test and save

> **Security Tip:** Use a long, random topic name since public topics are guessable.

---

### Option 2: Self-Hosted NTFY (Recommended for Production)

Run your own NTFY server for full control, authentication, and advanced features.

**Pros:**
- Full authentication (username/password or tokens)
- Message templates
- Email notifications from NTFY
- Attachments and file sharing
- Rate limiting control
- Complete privacy

**Cons:**
- Requires subdomain configuration
- Additional Cloudflare Tunnel setup

### Critical Requirement: Subdomain Required

**Self-hosted NTFY requires its own subdomain.** It will NOT work as a path on your n8n domain.

| Configuration | Works? | Example |
|--------------|--------|---------|
| `ntfy.yourdomain.com` | ✅ Yes | Required for self-hosted |
| `n8n.yourdomain.com/ntfy` | ❌ No | Will not work |

**Why a subdomain is required:**

1. NTFY uses WebSocket connections for real-time push notifications
2. The NTFY protocol expects to be at the root path (`/`)
3. Mobile apps and the web UI don't support path-based routing
4. UnifiedPush (Android) requires a root domain

### Setting Up Self-Hosted NTFY

#### Step 1: Enable NTFY During Setup

When running `./setup.sh`, select NTFY as an optional service:

```
  Optional Components:
    ...
    5. NTFY (push notifications)
    ...

  Enable NTFY? [y/N]: y
```

Or add to your `.env` file:

```env
# NTFY public URL - MUST be a subdomain
NTFY_BASE_URL=https://ntfy.yourdomain.com

# Authentication settings
NTFY_AUTH_DEFAULT_ACCESS=read-write
NTFY_ENABLE_LOGIN=true
NTFY_ENABLE_SIGNUP=false

# Cache and attachment settings
NTFY_CACHE_DURATION=24h
NTFY_ATTACHMENT_TOTAL_SIZE_LIMIT=100M
NTFY_ATTACHMENT_FILE_SIZE_LIMIT=15M
NTFY_ATTACHMENT_EXPIRY_DURATION=24h
NTFY_KEEPALIVE_INTERVAL=45s

# Optional: SMTP for email notifications from NTFY
NTFY_SMTP_SENDER_ADDR=smtp.gmail.com:587
NTFY_SMTP_SENDER_USER=your-email@gmail.com
NTFY_SMTP_SENDER_PASS=your-app-password
NTFY_SMTP_SENDER_FROM=your-email@gmail.com
```

#### Step 2: Configure Cloudflare Tunnel for NTFY Subdomain

Self-hosted NTFY requires an additional public hostname in your Cloudflare Tunnel.

1. Go to [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com)
2. Navigate to **Networks** > **Tunnels**
3. Click on your tunnel (e.g., `n8n-tunnel`)
4. Go to the **Public Hostname** tab
5. Click **Add a public hostname**

**Configure the NTFY hostname:**

| Field | Value |
|-------|-------|
| Subdomain | `ntfy` |
| Domain | `yourdomain.com` |
| Type | `HTTP` |
| URL | `n8n_ntfy:80` |

**Additional Settings:**

| Setting | Value |
|---------|-------|
| TLS > No TLS Verify | Leave disabled (NTFY uses HTTP internally) |
| HTTP Settings > HTTP Host Header | `ntfy.yourdomain.com` |

6. Click **Save hostname**

> **Important:** Notice the URL is `HTTP` to `n8n_ntfy:80`, not HTTPS. The NTFY container exposes port 80 internally. Cloudflare provides the HTTPS termination.

#### Step 3: Create NTFY Users

After deployment, create user accounts for authentication:

```bash
# Enter the NTFY container
docker exec -it n8n_ntfy sh

# Add a user
ntfy user add admin

# Set password when prompted
# Grant admin role if needed
ntfy user change-role admin admin

# List users
ntfy user list

# Exit container
exit
```

#### Step 4: Configure Access Tokens

For the Management Console to send notifications:

```bash
# Create an access token for the management console
docker exec n8n_ntfy ntfy token add admin

# This outputs a token like: tk_xxxxxxxxxxxxxxxxxxxxx
# Save this token for the notification channel configuration
```

#### Step 5: Add NTFY Channel in Management Console

1. Go to **Settings** > **Notifications** > **Add Channel**
2. Select **NTFY**
3. Configure:
   - **Server:** `https://ntfy.yourdomain.com`
   - **Topic:** `alerts` (or any topic name)
   - **Token:** `tk_xxxxxxxxxxxxxxxxxxxxx` (from Step 4)
4. Test and save

### Self-Hosted NTFY Advanced Features

These features are only available with self-hosted NTFY:

#### Message Templates

Create custom message templates in the NTFY web UI:

1. Access `https://ntfy.yourdomain.com`
2. Log in with your admin account
3. Go to Settings > Templates

#### Priority and Tags

Configure different priority levels with visual indicators:

| Priority | Mobile Behavior |
|----------|----------------|
| `min` / `1` | No sound, no vibration |
| `low` / `2` | No sound |
| `default` / `3` | Sound + vibration |
| `high` / `4` | Sound + vibration + display on |
| `urgent` / `5` | Bypasses Do Not Disturb |

#### Action Buttons

Add clickable action buttons to notifications:

```
Click to view logs: view, https://n8n.yourdomain.com/management
```

#### Scheduled Delivery

Delay notifications for future delivery:

```
Delay: 1h (deliver in 1 hour)
At: 9am (deliver at next 9 AM)
```

#### Email Forwarding

Forward notifications to email (requires SMTP configuration in `.env`):

1. Go to NTFY web UI
2. Subscribe to your topic
3. Enable email notifications for that subscription

### Firewall Configuration (Non-Cloudflare Users)

If you're not using Cloudflare Tunnel and exposing NTFY directly:

```bash
# Allow NTFY subdomain traffic
# Replace with your actual firewall commands

# UFW example
ufw allow 443/tcp

# iptables example
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

You'll also need:
- DNS A/CNAME record pointing `ntfy.yourdomain.com` to your server
- SSL certificate (Let's Encrypt via Certbot)
- nginx configuration for the NTFY subdomain

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

## Using the Management Console

### Adding a Notification Channel

1. Navigate to **Settings** > **Notifications**
2. Click **Add Channel**
3. Select the service type
4. Fill in the configuration form:

   **For Apprise:**
   - Name: Descriptive name
   - URL: The Apprise URL for your service

   **For NTFY:**
   - Name: Descriptive name
   - Server: `https://ntfy.sh` or your self-hosted URL
   - Topic: Your topic name
   - Token: (optional, for self-hosted with auth)

   **For Email:**
   - Name: Descriptive name
   - To: Recipient email addresses

   **For Webhook:**
   - Name: Descriptive name
   - URL: Your webhook endpoint
   - Headers: (optional) Key-value pairs

5. Click **Test** to verify
6. Click **Save**

### Creating Notification Groups

Groups allow you to send to multiple channels at once:

1. Go to **Settings** > **Notifications** > **Groups**
2. Click **Add Group**
3. Enter a group name (e.g., "Critical Alerts")
4. Select channels to include
5. Save

### Configuring Global Events

1. Go to **Settings** > **System Notifications**
2. Select the **Global Event Settings** tab
3. Expand each event category
4. For each event type:
   - Toggle to enable/disable
   - Add notification targets (channels or groups)
5. Save changes

### Per-Container Configuration

1. Go to **Settings** > **System Notifications**
2. Select the **Container Config** tab
3. Click **Add Container**
4. Select the container
5. Configure:
   - Which events to monitor
   - Custom CPU/memory thresholds
   - Override notification targets
6. Save

### Testing Notifications

Always test before relying on notifications:

1. Go to **Settings** > **Notifications**
2. Find your channel
3. Click the **Test** button
4. Verify you received the test message

### Viewing Notification History

1. Go to **Settings** > **Notifications** > **History**
2. Filter by:
   - Event type
   - Channel
   - Status (sent, failed, pending)
   - Date range
3. Click on any notification to see details

---

## Common Service Setups

### Slack

1. **Create a Slack App:**
   - Go to https://api.slack.com/apps
   - Click **Create New App** > **From scratch**
   - Name it (e.g., "n8n Alerts")
   - Select your workspace

2. **Add Incoming Webhooks:**
   - Go to **Incoming Webhooks**
   - Toggle **Activate Incoming Webhooks** on
   - Click **Add New Webhook to Workspace**
   - Select the channel
   - Copy the webhook URL

3. **Extract Apprise tokens from the webhook URL:**
   ```
   https://hooks.slack.com/services/T0123ABCD/B0456EFGH/xyzXYZ123abcABC456def
                                       └─TokenA─┘ └─TokenB──┘ └────TokenC────┘
   ```

4. **In Management Console:**
   - Add Apprise channel
   - URL: `slack://T0123ABCD/B0456EFGH/xyzXYZ123abcABC456def/#channel-name`

### Discord

1. **Create a Webhook:**
   - In Discord, go to Server Settings > Integrations > Webhooks
   - Click **New Webhook**
   - Name it and select the channel
   - Copy the webhook URL

2. **Extract tokens from the URL:**
   ```
   https://discord.com/api/webhooks/1234567890/abcdefghijklmnop
                                    └─webhook_id─┘└──webhook_token──┘
   ```

3. **In Management Console:**
   - Add Apprise channel
   - URL: `discord://1234567890/abcdefghijklmnop`

### Microsoft Teams

1. **Create an Incoming Webhook:**
   - In Teams, go to the channel
   - Click **...** > **Connectors**
   - Find **Incoming Webhook** and click **Configure**
   - Name it and copy the URL

2. **In Management Console:**
   - Add Apprise channel
   - URL: `msteams://TokenA/TokenB/TokenC` (extract from webhook URL)

### Telegram

1. **Create a Bot:**
   - Message @BotFather on Telegram
   - Send `/newbot`
   - Follow prompts to name your bot
   - Copy the bot token

2. **Get your Chat ID:**
   - Message @userinfobot
   - It replies with your chat ID

3. **In Management Console:**
   - Add Apprise channel
   - URL: `tgram://BOT_TOKEN/CHAT_ID`

### PagerDuty

1. **Create a Service:**
   - In PagerDuty, go to Services
   - Create a new service or use existing
   - Add an integration (Events API v2)
   - Copy the Integration Key

2. **In Management Console:**
   - Add Apprise channel
   - URL: `pagerduty://INTEGRATION_KEY`

---

## Best Practices

### 1. Start Simple

Begin with one notification channel for critical events:
- Configure Slack/Discord for `backup.failed`
- Test thoroughly before adding more

### 2. Use Multiple Channels

Don't rely on a single notification method:

| Priority | Primary | Backup |
|----------|---------|--------|
| Critical | PagerDuty + Phone | Slack |
| High | Slack | Email |
| Normal | Slack | - |
| Low | Email digest | - |

### 3. Set Appropriate Priorities

| Priority | Use For | Example |
|----------|---------|---------|
| Critical | Requires immediate action | Backup failure, disk full |
| High | Important, can wait briefly | Container unhealthy |
| Normal | Should be reviewed soon | Backup warnings |
| Low | Informational only | Successful backups |

### 4. Use Cooldowns

Prevent alert fatigue by setting cooldown periods in event configuration:

| Priority | Suggested Cooldown |
|----------|-------------------|
| Critical | 0-5 minutes |
| High | 15-30 minutes |
| Normal | 1-4 hours |
| Low | Daily digest |

### 5. Test Regularly

- Test notifications monthly
- Verify all channels work after configuration changes
- Include notification testing in disaster recovery drills

### 6. Document Your Setup

- Keep a list of notification channels and their purposes
- Document who receives what alerts
- Update documentation when rules change

---

## Troubleshooting

### Notifications Not Sending

1. **Check channel is enabled:**
   - Go to **Notifications** > find your channel
   - Verify the toggle is on

2. **Check event is enabled:**
   - Go to **System Notifications** > **Global Event Settings**
   - Verify the event type is enabled

3. **Test the channel:**
   - Click **Test** on the channel
   - Check for error messages

4. **Check notification history:**
   - Go to **Notifications** > **History**
   - Look for failed notifications with error details

### NTFY Not Working

**Public ntfy.sh:**

1. Verify you're subscribed to the correct topic in the app
2. Check topic name matches exactly (case-sensitive)
3. Test from command line:
   ```bash
   curl -d "Test message" https://ntfy.sh/your-topic
   ```

**Self-hosted NTFY:**

1. Verify the subdomain is accessible:
   ```bash
   curl https://ntfy.yourdomain.com/v1/health
   ```
   Should return: `{"healthy":true}`

2. Check Cloudflare Tunnel configuration:
   - Verify public hostname exists for `ntfy.yourdomain.com`
   - Verify URL is `n8n_ntfy:80` (HTTP, not HTTPS)

3. Check container is running:
   ```bash
   docker logs n8n_ntfy
   ```

4. Verify authentication token is valid:
   ```bash
   docker exec n8n_ntfy ntfy token list admin
   ```

### Apprise URL Not Working

1. Test the URL directly:
   ```bash
   docker exec n8n_management apprise -t "Test" -b "Message" "your-apprise-url"
   ```

2. Check URL format matches the service documentation

3. Verify tokens/API keys are correct and not expired

### Email Notifications Failing

1. Check email provider configuration in **Settings** > **Email**

2. Send a test email from that page

3. Common issues:
   - Port blocked by firewall
   - Authentication required
   - TLS/SSL misconfiguration
   - App password needed (Gmail, etc.)

### Too Many Notifications

1. Add cooldowns to event configuration

2. Adjust thresholds:
   - Go to **Settings** > **System**
   - Increase CPU/memory/disk thresholds

3. Disable low-priority events you don't need

---

## Quick Reference

### Management Console Paths

| Task | Location |
|------|----------|
| Add notification channel | Settings > Notifications > Add Channel |
| Create channel group | Settings > Notifications > Groups |
| Enable global events | Settings > System Notifications > Global Event Settings |
| Per-container config | Settings > System Notifications > Container Config |
| View history | Settings > Notifications > History |
| Configure email | Settings > Email |

### Environment Variables (for Self-Hosted NTFY)

| Variable | Required | Description |
|----------|----------|-------------|
| `NTFY_BASE_URL` | Yes | Public URL (e.g., `https://ntfy.yourdomain.com`) |
| `NTFY_AUTH_DEFAULT_ACCESS` | No | Default: `read-write` |
| `NTFY_ENABLE_LOGIN` | No | Default: `true` |
| `NTFY_ENABLE_SIGNUP` | No | Default: `false` |
| `NTFY_CACHE_DURATION` | No | Default: `24h` |
| `NTFY_SMTP_SENDER_ADDR` | No | SMTP server for email notifications |
| `NTFY_SMTP_SENDER_USER` | No | SMTP username |
| `NTFY_SMTP_SENDER_PASS` | No | SMTP password |
| `NTFY_SMTP_SENDER_FROM` | No | From email address |

### NTFY Commands

```bash
# Check NTFY health
curl https://ntfy.yourdomain.com/v1/health

# Add user
docker exec n8n_ntfy ntfy user add USERNAME

# Create token
docker exec n8n_ntfy ntfy token add USERNAME

# List users
docker exec n8n_ntfy ntfy user list

# View logs
docker logs n8n_ntfy
```

