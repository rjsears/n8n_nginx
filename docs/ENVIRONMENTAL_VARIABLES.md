# Environment Variables Reference

## n8n Management Console - Complete Environment Configuration Guide

**Version 3.0.0 - January 2026**

---

## ⚠️ Important Notice

**The `setup.sh` script automatically configures ALL required environment variables during installation.** Under normal circumstances, you should **NEVER need to manually edit** the `.env` file or change these settings through the Management Console.

### When You Should NOT Modify Environment Variables

- The system is working correctly
- You're not migrating to a new domain
- You haven't been specifically instructed by support
- You're not an experienced administrator who understands the implications

### Risks of Modifying Environment Variables

Incorrect changes to environment variables can cause:

- **Complete system failure** - Services may refuse to start
- **Loss of access** - You may lock yourself out of the Management Console
- **Data corruption** - Encryption key changes will make credentials unreadable
- **Service interruptions** - Container communication may break
- **Security vulnerabilities** - Weak passwords or exposed credentials

---

## Variable Categories

### 1. Required Settings (`required`)

These are the core settings that MUST be configured for the system to function.

| Variable | Description | Default | Required | Sensitive |
|----------|-------------|---------|----------|-----------|
| `DOMAIN` | Your n8n domain (e.g., `n8n.example.com`). Used for SSL certificates, webhook URLs, and all external access. Must be a valid FQDN. | *None* | ✅ Yes | No |
| `N8N_MANAGEMENT_HOST_IP` | Internal IP address of the Docker host. Critical for Cloudflare Tunnels and Tailscale to route traffic correctly. This IP must resolve to the DOMAIN hostname internally. | *None* | No | No |

**Example:**
```bash
DOMAIN=n8n.example.com
N8N_MANAGEMENT_HOST_IP=192.168.1.100
```

---

### 2. Database Configuration (`database`)

PostgreSQL database credentials used by both n8n and the Management Console.

| Variable | Description | Default | Required | Sensitive |
|----------|-------------|---------|----------|-----------|
| `POSTGRES_USER` | Database username for n8n and management console | `n8n` | ✅ Yes | No |
| `POSTGRES_PASSWORD` | Database password. **Changing this requires database migration and container restart.** | *Generated* | ✅ Yes | ✅ Yes |
| `POSTGRES_DB` | Name of the primary n8n database | `n8n` | ✅ Yes | No |

**⚠️ Warning:** Changing `POSTGRES_PASSWORD` after initial setup requires:
1. Stopping all containers
2. Updating the password in PostgreSQL
3. Updating the `.env` file
4. Restarting all containers

**Example:**
```bash
POSTGRES_USER=n8n
POSTGRES_PASSWORD=your-secure-password-here
POSTGRES_DB=n8n
```

---

### 3. Security & Authentication (`security`)

Encryption keys and admin credentials for the management console.

| Variable | Description | Default | Required | Sensitive |
|----------|-------------|---------|----------|-----------|
| `N8N_ENCRYPTION_KEY` | Used to encrypt all credentials stored in n8n workflows. **DO NOT CHANGE after initial setup!** | *Generated (64 chars)* | ✅ Yes | ✅ Yes |
| `MGMT_SECRET_KEY` | Secret key for management console session tokens and CSRF protection | *Generated (64 chars)* | ✅ Yes | ✅ Yes |
| `ADMIN_USER` | Username for management console login | *Set during setup* | ✅ Yes | No |
| `ADMIN_PASS` | Password for management console login | *Set during setup* | ✅ Yes | ✅ Yes |
| `ADMIN_EMAIL` | Email address for admin notifications | `admin@localhost` | No | No |

**🚨 Critical Warning about `N8N_ENCRYPTION_KEY`:**

The `N8N_ENCRYPTION_KEY` is used to encrypt ALL stored credentials in n8n (API keys, OAuth tokens, database passwords, etc.). If you change this value:

- **All existing credentials become permanently unreadable**
- You will need to re-enter every credential in every workflow
- There is NO way to recover the encrypted data

This variable is marked as **non-editable** in the Management Console for this reason.

**Example:**
```bash
N8N_ENCRYPTION_KEY=a1b2c3d4e5f6...  # 64-character random string
MGMT_SECRET_KEY=x9y8z7w6v5u4...    # 64-character random string
ADMIN_USER=admin
ADMIN_PASS=your-secure-admin-password
ADMIN_EMAIL=admin@example.com
```

---

### 4. Management Console (`management`)

Settings specific to the management console application.

| Variable | Description | Default | Required | Sensitive |
|----------|-------------|---------|----------|-----------|
| `MGMT_PORT` | Port where the management console is accessible (via nginx) | `3333` | No | No |
| `MGMT_DB_USER` | Database user for management console (usually same as `POSTGRES_USER`) | *Uses POSTGRES_USER* | No | No |
| `MGMT_DB_PASSWORD` | Database password for management console | *Uses POSTGRES_PASSWORD* | No | ✅ Yes |
| `TIMEZONE` | System timezone for logs, scheduled tasks, and display | `America/Los_Angeles` | No | No |

**Valid Timezone Values:**
Use standard IANA timezone names: `America/New_York`, `Europe/London`, `Asia/Tokyo`, `UTC`, etc.

**Example:**
```bash
MGMT_PORT=3333
TIMEZONE=America/Los_Angeles
```

---

### 5. NFS Backup Storage (`nfs`)

Optional configuration for remote NFS backup storage.

| Variable | Description | Default | Required | Sensitive |
|----------|-------------|---------|----------|-----------|
| `NFS_SERVER` | Hostname or IP address of the NFS server | *None* | No | No |
| `NFS_PATH` | Export path on the NFS server | *None* | No | No |
| `NFS_LOCAL_MOUNT` | Local directory path where NFS share is mounted | *None* | No | No |

**Note:** NFS mounting is performed at the host level, not inside containers. The `setup.sh` script configures this automatically if you enable NFS during setup.

**Example:**
```bash
NFS_SERVER=nas.local
NFS_PATH=/exports/n8n-backups
NFS_LOCAL_MOUNT=/opt/n8n_backups
```

---

### 6. Cloudflare Tunnel (`cloudflare`)

Optional Cloudflare Tunnel for secure, zero-trust access to your n8n instance.

| Variable | Description | Default | Required | Sensitive |
|----------|-------------|---------|----------|-----------|
| `CLOUDFLARE_TUNNEL_TOKEN` | Authentication token for Cloudflare Tunnel | *None* | No | ✅ Yes |

**How to Get a Tunnel Token:**
1. Go to Cloudflare Zero Trust Dashboard
2. Navigate to Networks → Tunnels
3. Create a new tunnel or use an existing one
4. Copy the tunnel token from the connector setup

**Example:**
```bash
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiNzk...  # Long JWT token
```

See [CLOUDFLARE.md](./CLOUDFLARE.md) for detailed setup instructions.

---

### 7. Tailscale VPN (`tailscale`)

Optional Tailscale VPN integration for secure private network access.

| Variable | Description | Default | Required | Sensitive |
|----------|-------------|---------|----------|-----------|
| `TAILSCALE_AUTH_KEY` | Tailscale authentication key for automatic device registration | *None* | No | ✅ Yes |
| `TAILSCALE_ROUTES` | CIDR notation routes to advertise to the Tailscale network | *None* | No | No |

**How to Get an Auth Key:**
1. Go to Tailscale Admin Console
2. Navigate to Settings → Keys
3. Generate a new auth key (reusable recommended for containers)

**Example:**
```bash
TAILSCALE_AUTH_KEY=tskey-auth-...
TAILSCALE_ROUTES=192.168.1.0/24
```

See [TAILSCALE.md](./TAILSCALE.md) for detailed setup instructions.

---

### 8. Container Names (`containers`)

Docker container naming configuration. These should match your `docker-compose.yaml` settings.

| Variable | Description | Default | Required | Sensitive |
|----------|-------------|---------|----------|-----------|
| `POSTGRES_CONTAINER` | Name of the PostgreSQL container | `n8n_postgres` | No | No |
| `N8N_CONTAINER` | Name of the n8n container | `n8n` | No | No |
| `NGINX_CONTAINER` | Name of the Nginx reverse proxy container | `n8n_nginx` | No | No |
| `CERTBOT_CONTAINER` | Name of the Certbot SSL certificate container | `n8n_certbot` | No | No |
| `MANAGEMENT_CONTAINER` | Name of the management console container | `n8n_management` | No | No |

**⚠️ Warning:** Changing container names after initial setup requires updating both the `.env` file AND stopping/renaming/restarting the actual containers.

**Example:**
```bash
POSTGRES_CONTAINER=n8n_postgres
N8N_CONTAINER=n8n
NGINX_CONTAINER=n8n_nginx
CERTBOT_CONTAINER=n8n_certbot
MANAGEMENT_CONTAINER=n8n_management
```

---

### 9. NTFY Notifications (`ntfy`)

NTFY push notification service settings.

| Variable | Description | Default | Required | Sensitive |
|----------|-------------|---------|----------|-----------|
| `NTFY_BASE_URL` | Internal URL of your NTFY server | `https://ntfy.${DOMAIN}` | No | No |
| `NTFY_PUBLIC_URL` | Public URL for NTFY (used in documentation and examples) | *Same as NTFY_BASE_URL* | No | No |

**Example:**
```bash
NTFY_BASE_URL=https://ntfy.n8n.example.com
NTFY_PUBLIC_URL=https://ntfy.n8n.example.com
```

See [NOTIFICATIONS.md](./NOTIFICATIONS.md) for NTFY configuration details.

---

### 10. Redis Status Cache (`redis`)

Configuration for the Redis status caching system used by n8n_status.

| Variable | Description | Default | Required | Sensitive |
|----------|-------------|---------|----------|-----------|
| `REDIS_HOST` | Hostname of the Redis server | `redis` (or `127.0.0.1` for n8n_status) | No | No |
| `REDIS_PORT` | Port number for Redis | `6379` | No | No |
| `REDIS_ENABLED` | Enable/disable Redis caching in management console | `true` | No | No |

**Note:** The `n8n_status` container runs with `network_mode: host` and connects to Redis via `127.0.0.1:6379`. The management console connects via the Docker network using `redis:6379`.

**Example:**
```bash
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_ENABLED=true
```

---

### 11. n8n_status Collector (`n8n_status`)

Configuration for the status collection service.

| Variable | Description | Default | Required | Sensitive |
|----------|-------------|---------|----------|-----------|
| `POLL_INTERVAL_METRICS` | Seconds between host metrics collection | `5` | No | No |
| `POLL_INTERVAL_NETWORK` | Seconds between network info collection | `30` | No | No |
| `POLL_INTERVAL_CONTAINERS` | Seconds between container stats collection | `5` | No | No |
| `POLL_INTERVAL_EXTERNAL` | Seconds between external service checks | `15` | No | No |
| `CLOUDFLARE_CONTAINER` | Name of Cloudflare tunnel container | `n8n_cloudflared` | No | No |
| `TAILSCALE_CONTAINER` | Name of Tailscale container | `n8n_tailscale` | No | No |
| `NTFY_CONTAINER` | Name of NTFY container | `n8n_ntfy` | No | No |
| `NTFY_URL` | URL for NTFY health checks | `http://127.0.0.1:8083` | No | No |

**Example:**
```bash
POLL_INTERVAL_METRICS=5
POLL_INTERVAL_NETWORK=30
POLL_INTERVAL_CONTAINERS=5
POLL_INTERVAL_EXTERNAL=15
```

---

### 12. n8n API Integration (`n8n_api`)

Settings for n8n API access from the management console.

| Variable | Description | Default | Required | Sensitive |
|----------|-------------|---------|----------|-----------|
| `N8N_API_KEY` | API key for n8n workflow management | *None* | No | ✅ Yes |

**How to Generate an API Key:**
1. Log into your n8n instance
2. Go to Settings → API
3. Enable the API if not already enabled
4. Generate a new API key

**Example:**
```bash
N8N_API_KEY=n8n_api_...
```

---

## Additional Docker Compose Variables

These variables are used in `docker-compose.yaml` but may not appear in the Management Console:

| Variable | Description | Default |
|----------|-------------|---------|
| `DNS_CERTBOT_IMAGE` | Certbot Docker image (changes based on DNS provider) | `certbot/certbot:latest` |
| `DNS_CERTBOT_FLAGS` | Additional flags for Certbot DNS validation | *Provider-specific* |
| `DNS_CREDENTIALS_FILE` | Credentials file for DNS provider | `cloudflare.ini` |

---

## Complete Example .env File

```bash
# =============================================================================
# n8n Management Console - Environment Configuration
# Generated by setup.sh - Modify with caution!
# =============================================================================

# Required Settings
DOMAIN=n8n.example.com
N8N_MANAGEMENT_HOST_IP=192.168.1.100

# Database Configuration
POSTGRES_USER=n8n
POSTGRES_PASSWORD=secure-random-password-here
POSTGRES_DB=n8n

# Security & Authentication
N8N_ENCRYPTION_KEY=64-character-random-string-generated-by-setup
MGMT_SECRET_KEY=another-64-character-random-string
ADMIN_USER=admin
ADMIN_PASS=your-admin-password
ADMIN_EMAIL=admin@example.com

# Management Console
MGMT_PORT=3333
TIMEZONE=America/Los_Angeles

# NFS Backup Storage (Optional)
NFS_SERVER=
NFS_PATH=
NFS_LOCAL_MOUNT=

# Cloudflare Tunnel (Optional)
CLOUDFLARE_TUNNEL_TOKEN=

# Tailscale VPN (Optional)
TAILSCALE_AUTH_KEY=
TAILSCALE_ROUTES=

# Container Names
POSTGRES_CONTAINER=n8n_postgres
N8N_CONTAINER=n8n
NGINX_CONTAINER=n8n_nginx
CERTBOT_CONTAINER=n8n_certbot
MANAGEMENT_CONTAINER=n8n_management

# NTFY Notifications (Optional)
NTFY_BASE_URL=
NTFY_PUBLIC_URL=

# n8n API (Optional)
N8N_API_KEY=

# Redis Status Cache
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_ENABLED=true
```

---

## Troubleshooting

### Common Issues

**1. "Container won't start after changing variables"**
- Check Docker logs: `docker compose logs <container_name>`
- Verify the variable syntax (no extra spaces, proper quotes)
- Restore from backup if necessary

**2. "Can't log into Management Console after password change"**
- The `ADMIN_PASS` change requires container restart
- Run: `docker compose restart n8n_management`

**3. "All my n8n credentials are broken"**
- You likely changed `N8N_ENCRYPTION_KEY`
- **This cannot be fixed** - you must restore from backup or re-enter all credentials

**4. "Database connection failed"**
- Verify `POSTGRES_PASSWORD` matches in all locations
- Check that the PostgreSQL container is running
- Try restarting the stack: `docker compose down && docker compose up -d`

### Getting Help

If you've made changes that broke your system:

1. **Restore from backup** - Use the Management Console's backup restore feature
2. **Check logs** - `docker compose logs -f`
3. **Review changes** - The Management Console creates automatic backups before changes in `env_backups/`

---

## Directory Structure

Environment-related files are stored in:

```
n8n_nginx/
├── .env                    # Main environment file (sensitive!)
├── env_backups/            # Automatic backups of .env file
│   └── .env_backup_*       # Timestamped backups
├── docker-compose.yaml     # Container configuration
└── docs/
    └── ENVIRONMENTAL_VARIABLES.md  # This document
```

---

## Security Best Practices

1. **Never commit `.env` to version control** - It's in `.gitignore` for a reason
2. **Use strong passwords** - The setup script generates secure random values
3. **Limit access** - Only admins should access the Environment Settings
4. **Regular backups** - The system creates backups before any changes
5. **Document changes** - Keep notes of any manual changes made

---

*Document last updated: January 2026*
*Part of the n8n Management Console v3.0.0*
