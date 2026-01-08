# Interactive Setup Guide

This document provides a detailed walkthrough of the `setup.sh` interactive setup script, showing every screen, prompt, and response option in the exact order they appear.

---

## 1. Welcome Screen

When you run `./setup.sh`, you'll see:

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                n8n HTTPS Interactive Setup v3.0.0                         ║
╚═══════════════════════════════════════════════════════════════════════════╝

  This script will set up a production-ready n8n instance with:
    • Automated SSL certificates via Let's Encrypt (DNS-01)
    • PostgreSQL 16 with pgvector for AI workflows
    • Nginx reverse proxy with security headers
    • NEW: Management console for backups and monitoring

  Optional services available:
    • Cloudflare Tunnel - Secure access without exposing ports
    • Tailscale - Private mesh VPN network access
    • NTFY - Self-hosted push notification server
    • Adminer - Web-based database management
    • Dozzle - Real-time container log viewer
    • Portainer / Portainer Agent - Container management UI

  Ready to begin? [Y/n]:
```

---

## 2. Existing Installation Detection

If an existing v3.0 installation is detected in the directory, you'll see this **instead** of the welcome screen:

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                n8n HTTPS Interactive Setup v3.0.0                         ║
╚═══════════════════════════════════════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║                     ⚡  EXISTING SETUP DETECTED  ⚡                        ║
║                                                                           ║
║             Version 3.0 installation found in this directory              ║
║            Your existing configuration and data are preserved             ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝

  What would you like to do?

    1) Reconfigure existing installation
    2) Start Fresh (will backup existing config)
    3) Exit

  Enter your choice [1-3]:
```

### Reconfigure Menu (Option 1)

If you choose to reconfigure:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Reconfigure Options                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
  Select what you want to reconfigure:

    1) Domain & SSL settings
    2) Database credentials
    3) Optional services (Cloudflare, Tailscale, NTFY, etc.)
    4) Access control (IP ranges)
    5) Admin credentials
    6) NFS backup storage
    7) Regenerate all config files (keeps settings)
    8) Full reconfiguration (all settings)
    9) Rollback to previous configuration
    0) Exit

  Enter your choice [0-9]:
```

---

## 3. LXC Container Warning

If running inside an LXC container (e.g., Proxmox), you'll see:

```
  ╔═══════════════════════════════════════════════════════════════════════════╗
  ║                          LXC CONTAINER DETECTED                           ║
  ╠═══════════════════════════════════════════════════════════════════════════╣
  ║                                                                           ║
  ║  IMPORTANT: Docker inside LXC requires special Proxmox configuration.     ║
  ║                                                                           ║
  ║  On your Proxmox host, add this line to the container config:             ║
  ║                                                                           ║
  ║      /etc/pve/lxc/<CTID>.conf                                             ║
  ║                                                                           ║
  ║      lxc.apparmor.profile: unconfined                                     ║
  ║                                                                           ║
  ║  Then restart this container from Proxmox before continuing.              ║
  ║                                                                           ║
  ╚═══════════════════════════════════════════════════════════════════════════╝

  Have you added this configuration and restarted the container? [Y/n]:
```

---

## 4. Resume Incomplete Installation

If a previous incomplete installation is detected:

```
  ⚠ Previous incomplete installation detected.

  Last completed step: DNS Provider
  Domain: n8n.example.com

  Options:
    1) Resume from where you left off
    2) Start fresh (clears saved progress)

  Enter your choice [1-2]:
```

---

## 5. System Preparation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ System Preparation                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
  ✓ Detected OS: ubuntu (debian)

  Update system packages before continuing? [Y/n]:
```

If you choose yes, the script updates packages and installs required utilities:

```
  ℹ Updating system packages...
  ✓ System packages updated
  ℹ Checking and installing required utilities...
  ✓ All required utilities are already installed
```

---

## 6. Docker Environment Check

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Docker Environment Check                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
  ✓ Docker is installed (version: 24.0.7)
  ✓ Docker daemon is running
  ✓ Docker Compose is available (version: 2.21.0)
```

**If Docker is not installed:**

```
  ⚠ Docker is not installed.

  Would you like to install Docker now? [Y/n]: y

  ℹ Installing Docker...
  ℹ Detected ubuntu (debian)
  ℹ Updating package index...
  ℹ Installing prerequisites...
  ℹ Adding Docker GPG key...
  ℹ Adding Docker repository...
  ℹ Installing Docker Engine and Docker Compose...
  ✓ Docker and Docker Compose installed successfully!
```

---

## 7. System Requirements Check

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ System Requirements Check                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
  ✓ Disk space: 45GB available (5GB required)
  ✓ Memory: 4GB total (2GB required)
  ✓ Port 443 is available
  ✓ OpenSSL is available
  ✓ curl is available
  ✓ Internet connectivity OK
```

**If checks fail:**

```
  ⚠ Port 443 is currently in use

  Some checks failed. Continue anyway? [Y/n]:
```

---

## 8. DNS Provider Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ DNS Provider Configuration                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
  Let's Encrypt uses DNS validation to issue SSL certificates.
  This requires API access to your DNS provider.

  Select your DNS provider:
    1) Cloudflare
    2) AWS Route 53
    3) Google Cloud DNS
    4) DigitalOcean
    5) Other (manual configuration)

  Enter your choice [1-5]:
```

### Cloudflare (Option 1)

```
───────────────────────────────────────────────────────────────────────────────

  Cloudflare API Configuration

  You need a Cloudflare API token with Zone:DNS:Edit permission.
  Create one at: https://dash.cloudflare.com/profile/api-tokens

  Enter your Cloudflare API token: [first 10 chars visible, rest masked]
  ✓ Cloudflare credentials saved
```

### AWS Route 53 (Option 2)

```
───────────────────────────────────────────────────────────────────────────────

  AWS Route 53 Configuration

  Enter your AWS Access Key ID: [masked]
  Enter your AWS Secret Access Key: [masked]
  ✓ AWS credentials saved
```

### Google Cloud DNS (Option 3)

```
───────────────────────────────────────────────────────────────────────────────

  Google Cloud DNS Configuration

  Enter the path to your service account JSON file: /path/to/credentials.json
  ✓ Google credentials saved
```

### DigitalOcean (Option 4)

```
───────────────────────────────────────────────────────────────────────────────

  DigitalOcean DNS Configuration

  Enter your DigitalOcean API token: [masked]
  ✓ DigitalOcean credentials saved
```

### Other/Manual (Option 5)

```
  ⚠ Manual DNS configuration selected
  You will need to configure certbot manually.
```

---

## 9. Domain Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Domain Configuration                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
  Enter the domain name where n8n will be accessible.
  Example: n8n.yourdomain.com

  Enter your n8n domain [n8n.example.com]: n8n.mycompany.com
```

### Domain Validation

```
───────────────────────────────────────────────────────────────────────────────

  Validating domain configuration...

  This server's IP addresses:
    192.168.1.50
    10.0.0.5

  ℹ Resolving n8n.mycompany.com...
  ✓ Domain resolves to: 192.168.1.50
  ✓ Domain IP matches this server
  ℹ Testing connectivity to 192.168.1.50...
  ✓ Host 192.168.1.50 is reachable
```

**If domain doesn't match:**

```
  ⚠ Domain IP (203.0.113.25) does not match any local IP

  IMPORTANT:
  The domain n8n.mycompany.com points to 203.0.113.25
  but this server's IPs are different.

  This will cause the n8n stack to fail because:
    - SSL certificate validation will fail
    - Webhooks won't reach this server
    - The n8n UI won't be accessible

  ╔═══════════════════════════════════════════════════════════════════════════╗
  ║                              WARNING                                      ║
  ║  The domain validation found issues that may prevent n8n from working.    ║
  ║  Please ensure your DNS is properly configured before continuing.         ║
  ╚═══════════════════════════════════════════════════════════════════════════╝

  Options:
    1) Re-enter domain name (if misspelled)
    2) Continue anyway (I understand the risks)
    3) Exit setup

  Enter your choice [1-3]:
```

---

## 10. Database Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PostgreSQL Database Configuration                                            │
└─────────────────────────────────────────────────────────────────────────────┘
  Database name [n8n]:
  Database username [n8n]:

  Enter a password or leave blank to auto-generate.
  Database password []:
  ✓ Generated secure database password
```

---

## 11. Container Names Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Container Names Configuration                                                │
└─────────────────────────────────────────────────────────────────────────────┘
  ✓ Using default container names
```

The default container names are:
- PostgreSQL: `n8n_postgres`
- n8n: `n8n`
- Nginx: `n8n_nginx`
- Certbot: `n8n_certbot`

---

## 12. Email Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Let's Encrypt Email Configuration                                            │
└─────────────────────────────────────────────────────────────────────────────┘

  Let's Encrypt requires a valid email for certificate expiration notices.

  Email address for Let's Encrypt: admin@mycompany.com
  Confirm email address: admin@mycompany.com
  ✓ Email set to: admin@mycompany.com
```

**If email looks like a placeholder:**

```
  ⚠ This looks like a placeholder email address.
  Are you sure you want to use 'test@example.com'? [y/N]:
```

---

## 13. Timezone Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Timezone Configuration                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
  System timezone detected: America/New_York

  Use America/Los_Angeles as the timezone? [Y/n]: n
  Timezone [America/New_York]: America/New_York
  ✓ Timezone set to: America/New_York
```

---

## 14. Encryption Key Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Encryption Key Configuration                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
  ✓ Generated secure encryption key
  ⚠ IMPORTANT: Save your encryption key in a secure location!
```

---

## 15. Management Interface Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Management Interface Configuration                                           │
└─────────────────────────────────────────────────────────────────────────────┘
  The management console provides a web interface for:
    • Backup scheduling and management
    • Container monitoring and control
    • Notification configuration
    • System health monitoring

  ✓ Management interface will be available at https://${DOMAIN}/management/
```

---

## 16. NFS Backup Storage Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ NFS Backup Storage Configuration                                             │
└─────────────────────────────────────────────────────────────────────────────┘

  NFS storage allows centralized backup storage on a remote server.
  The NFS share will be mounted on this host and bind-mounted into Docker.
  If you skip this, backups will be stored locally in the container.

  Configure NFS for backup storage? [y/N]:
```

**If you choose to configure NFS:**

```
  NFS server address (e.g., 192.168.1.100 or nfs.example.com): 192.168.1.100
  ℹ Testing connection to 192.168.1.100...
  ✓ NFS server is reachable

  ℹ Checking for accessible NFS exports...
  This server's IP addresses:
    192.168.1.50

  ✓ Found 2 accessible exports

  Select NFS export:

    1) /exports/backups
    2) /exports/data
    3) [Enter path manually]

  Enter your choice [1-3]:

  Local mount point [/opt/n8n_backups]:
  ℹ Testing NFS mount: 192.168.1.100:/exports/backups...
  ✓ NFS mount test successful
  ℹ Creating local mount point: /opt/n8n_backups
  ℹ Adding NFS mount to /etc/fstab...
  ℹ Mounting NFS share...
  ✓ NFS share mounted at /opt/n8n_backups
  ✓ NFS share is writable
```

---

## 17. Notification System

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Notification System                                                          │
└─────────────────────────────────────────────────────────────────────────────┘

  Notifications are configured via the Management Console after setup.

  Supported notification services (via Apprise):
    • Email (SMTP, Gmail, SES)
    • Slack, Discord, Microsoft Teams
    • Telegram, Pushover, Pushbullet
    • Twilio SMS, NTFY
    • And 80+ more services

  Configure at: https://${DOMAIN}/management/ → Settings → Notifications

  ✓ Notifications will be configured in the Management Console
```

---

## 18. Management Admin User

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Management Admin User                                                        │
└─────────────────────────────────────────────────────────────────────────────┘

  Create the admin user for the management interface.

  Admin username [admin]:
  Admin password: ********
  Confirm password: ********
  Admin email (optional, for notifications): admin@mycompany.com
  ✓ Admin user configured
```

**Password requirements:**
- Minimum 8 characters
- Passwords must match

---

## 19. Optional Services Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Optional Services Configuration                                              │
└─────────────────────────────────────────────────────────────────────────────┘

  The following optional services can be added to your installation:

  Container Management:
    • Portainer - Docker container management UI

  External Access:
    • Cloudflare Tunnel - Secure access without exposing ports
    • Tailscale - Private mesh VPN network access

  Development Tools:
    • Adminer - Web-based database management
    • Dozzle - Real-time container log viewer

  Notifications:
    • NTFY - Self-hosted push notifications server

  Would you like to configure optional services? [y/N]:
```

**If you choose to configure optional services:**

```
  Install Portainer for container management? [y/N]:
  Configure Cloudflare Tunnel for secure external access? [y/N]:
  Configure Tailscale for private VPN access? [y/N]:
  Install Adminer for database management? [y/N]:
  Install Dozzle for container log viewing? [y/N]:
  Install NTFY for push notifications? [y/N]:
```

### Portainer Configuration

```
───────────────────────────────────────────────────────────────────────────────

  Portainer Configuration

  Portainer provides a web UI for managing Docker containers.

  Portainer Options:
    1) Agent only - Connect to existing Portainer server (installs agent on port 9001)
    2) Full Portainer - Install Portainer server

  Enter your choice [1-2]:
```

### Cloudflare Tunnel Configuration

```
───────────────────────────────────────────────────────────────────────────────

  Cloudflare Tunnel Configuration

  Cloudflare Tunnel provides secure access to your n8n instance
  without exposing any ports to the public internet.

  Requirements:
    • Cloudflare account with your domain
    • Cloudflare Tunnel token from Zero Trust dashboard

  Create a tunnel at: https://one.dash.cloudflare.com
  Navigate to: Networks → Tunnels → Create a tunnel

  Enter your Cloudflare Tunnel token: [masked]
  ✓ Cloudflare Tunnel configured
```

### Tailscale Configuration

```
───────────────────────────────────────────────────────────────────────────────

  Tailscale Configuration

  Tailscale provides private access to your n8n instance
  over a secure mesh VPN network.

  Requirements:
    • Tailscale account
    • Auth key from: https://login.tailscale.com/admin/settings/keys

  Enter your Tailscale auth key: [masked]
  ✓ Auth key accepted

  Tailscale hostname [n8n-server]:
  ✓ Tailscale configured

  ℹ Your n8n instance will be accessible at: n8n-server.your-tailnet.ts.net
```

### Adminer Configuration

```
───────────────────────────────────────────────────────────────────────────────

  Adminer Configuration

  Adminer provides a web-based interface for database management.

  ✓ Adminer will be available at https://${DOMAIN}/adminer/
```

### Dozzle Configuration

```
───────────────────────────────────────────────────────────────────────────────

  Dozzle Configuration

  Dozzle provides real-time container log viewing in your browser.

  ✓ Dozzle will be available at https://${DOMAIN}/dozzle/
  ℹ  Login credentials will be the same as the Management Console
```

### NTFY Configuration

```
───────────────────────────────────────────────────────────────────────────────

  NTFY Push Notifications Configuration

  NTFY is a simple HTTP-based pub-sub notification service.
  It allows you to send push notifications to your phone or desktop.

  Important: NTFY requires its own subdomain (e.g., ntfy.example.com).
  It cannot run on a subpath like /ntfy/ due to how NTFY handles requests.

  You can choose to:
    1. Install a self-hosted NTFY server (recommended)
    2. Use the public ntfy.sh server
    3. Connect to your own existing NTFY server

  Choose option [1/2/3, default: 1]:
```

**For self-hosted NTFY (Option 1):**

```
  Enter the subdomain for your NTFY server.
  This will be the public URL for accessing NTFY.
  NTFY subdomain [default: ntfy.n8n.mycompany.com]:

  ✓ Self-hosted NTFY server will be installed

  ℹ  NTFY Configuration:
      Public URL:   https://ntfy.n8n.mycompany.com
      Internal URL: http://n8n_ntfy:80 (for management console)

  ⚠  Required: Configure Cloudflare Tunnel
      Add a public hostname in Cloudflare Zero Trust:
        - Public hostname: ntfy.n8n.mycompany.com
        - Service type:    HTTP
        - Service URL:     n8n_ntfy:80
```

---

## 20. Configuration Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Configuration Summary                                                        │
└─────────────────────────────────────────────────────────────────────────────┘

  Domain & URL:
    Domain:              n8n.mycompany.com
    n8n URL:             https://n8n.mycompany.com
    Management URL:      https://n8n.mycompany.com/management/

  Database:
    Name:                n8n
    User:                n8n
    Password:            [generated password shown]

  Management Console:
    URL:                 /management/
    Admin User:          admin
    NFS Storage:         true
    Notifications:       false

  Other Settings:
    Timezone:            America/New_York
    DNS Provider:        cloudflare

  Optional Services:
    Portainer:           enabled (/portainer/)
    Cloudflare Tunnel:   enabled
    Tailscale:           enabled (n8n-server)
    Adminer:             enabled (/adminer/)
    Dozzle:              enabled (/dozzle/)
    NTFY:                enabled (https://ntfy.n8n.mycompany.com)

  Is this configuration correct? [Y/n]:
```

---

## 21. Deployment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Deploying n8n Stack v3.0                                                     │
└─────────────────────────────────────────────────────────────────────────────┘

  [1/4] Starting PostgreSQL database

  Waiting for PostgreSQL...
  ✓ PostgreSQL is running

  [2/4] Obtaining SSL certificate

  ℹ Checking for existing SSL certificate...
  ℹ Requesting certificate for n8n.mycompany.com...
  ✓ SSL certificate obtained successfully

  [3/4] Starting all services

  ✓ All services started

  [4/4] Verifying services

  ✓ PostgreSQL is responding
  ✓ n8n is responding
  ✓ Management API is responding

  ℹ Creating backup of working configuration...
  ✓ Backup complete!
```

---

## 22. Final Summary

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                           Setup Complete!                                 ║
╚═══════════════════════════════════════════════════════════════════════════╝

  Your n8n v3.0 instance is now running!

  Access URLs:
    n8n:                 https://n8n.mycompany.com
    Management Console:  https://n8n.mycompany.com/management/
    Portainer:           https://n8n.mycompany.com/portainer/
    Adminer (DB):        https://n8n.mycompany.com/adminer/
    Dozzle (Logs):       https://n8n.mycompany.com/dozzle/
    NTFY (Push):         https://ntfy.n8n.mycompany.com
                         (Configure in Cloudflare Tunnel)

  Management Login:
    Username:            admin
    Password:            [as configured]

  Database Credentials (for Adminer):
    Server:              postgres
    Username:            n8n
    Password:            [generated password]
    Database:            n8n

  Network Access:
    Cloudflare Tunnel:   Active
    Tailscale:           Active (n8n-server)

  Useful Commands:
    View logs:         docker compose logs -f
    Stop services:     docker compose down
    Start services:    docker compose up -d
    Health check:      ./scripts/health_check.sh

  New in v3.0:
    • Backup scheduling and management
    • Container monitoring and control
    • Multi-channel notifications
    • System health monitoring

  ───────────────────────────────────────────────────────────────────────────────

  Thank you for using n8n Setup Script v3.0.0
```

---

## Upgrade Flow (v2.0 to v3.0)

If a v2.0 installation is detected:

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                     UPGRADE AVAILABLE: v2.0 → v3.0                        ║
╚═══════════════════════════════════════════════════════════════════════════╝

  This upgrade will add:
    • Management console for backups and monitoring
    • Web-based administration interface
    • Automated backup scheduling
    • Multi-channel notifications

  Your existing data will be preserved.

  Upgrade from v2.0 to v3.0? [Y/n]:
```

The migration process then runs through several phases:
1. Pre-Migration Backup
2. Stopping Services
3. Database Preparation
4. Generating New Configuration
5. Deploying Updated Stack
6. Verification

---

## Access Control Configuration

If Cloudflare Tunnel is enabled, access control is configured:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Access Control Configuration                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

  Since you're using Cloudflare Tunnel, your n8n instance will be
  accessible from the public internet. Access control helps protect
  sensitive endpoints from unauthorized access.

  How Access Control Works:
    - Public Access (via Cloudflare Tunnel):
      Only these endpoints are accessible:
        - /webhook/ - n8n workflow webhooks
        - /ntfy/ - Push notification service

    - Internal Access (Tailscale, VPN, Local Network):
      Full access to all endpoints including:
        - / - n8n main interface
        - /management/ - Management console
        - /adminer/ - Database admin (if installed)
        - /dozzle/ - Log viewer (if installed)

  [OK] Tailscale detected - Tailscale IPs (100.64.0.0/10) will have full access

  Default Internal IP Ranges:
    100.64.0.0/10  - Tailscale CGNAT range
    172.16.0.0/12  - Docker/Internal networks
    10.0.0.0/8     - Private network (Class A)
    192.168.0.0/16 - Private network (Class C)

  Would you like to add additional IP ranges? [y/N]:
```

---

## Command Line Options

The setup script also accepts command line arguments:

```bash
./setup.sh --help           # Show help
./setup.sh --version        # Show version
./setup.sh --rollback       # Rollback to previous configuration
./setup.sh --update-access  # Update access control settings only
```
