### 4.1 Welcome Screen

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                n8n HTTPS Interactive Setup v3.0.0                         ║
╚═══════════════════════════════════════════════════════════════════════════╝

  This script will guide you through setting up a production-ready
  n8n instance with HTTPS, PostgreSQL, and optional automatic SSL
  configuration and renewal.

  Features:
    - Automated SSL certificates via Let's Encrypt
    - DNS-01 challenge (no port 80/443 exposure needed)
    - PostgreSQL 16 with pgvector for AI/RAG workflows
    - Nginx reverse proxy with security headers
    - Automatic certificate renewal every 12 hours

  Ready to begin? [Y/n]:
```

---

### 4.2 Running as Root

If you run the script as root (common for server administrators), you'll see a note:

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                n8n HTTPS Interactive Setup v3.0.0                         ║
╚═══════════════════════════════════════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════════════════════╗
║                              NOTE                                         ║
║  You are running this script as root. While this will work, it's          ║
║  recommended to run as a regular user (the script uses sudo internally).  ║
╚═══════════════════════════════════════════════════════════════════════════╝

  Continue as root? [Y/n]: y
```

The script intelligently handles different execution contexts:

| Scenario | sudo for commands | Docker group prompt |
|----------|------------------|---------------------|
| Running as root | Not needed | Skipped |
| Running via `sudo ./setup.sh` | Not needed | Offered (for real user) |
| Running as regular user | Used when needed | Offered |

---

### 4.3 Docker Installation

The script checks if Docker and Docker Compose are installed. If not, it offers to install them automatically.

**When running as a regular user:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Docker Environment Check                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
  ✓ Docker is installed (version: 24.0.7)
  ✓ Docker daemon is running
  ✓ Docker Compose is available (version: 2.21.0)
```

**When running as root:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Docker Environment Check                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
  ✓ Docker is installed (version: 24.0.7)
  ✓ Docker daemon is running
  ✓ Docker Compose is available (version: 2.21.0)
  ✓ Running as root - no sudo required for Docker commands
```

**If Docker is not installed (regular user):**

```
  ⚠ Docker is not installed
  Would you like to install Docker? [Y/n]: y

───────────────────────────────────────────────────────────────────────────────

  Installing Docker and Docker Compose...

  ℹ Detected ubuntu 22.04
  ℹ Updating package index...
  ℹ Installing prerequisites...
  ℹ Adding Docker GPG key...
  ℹ Adding Docker repository...
  ℹ Installing Docker Engine and Docker Compose...
  ✓ Docker and Docker Compose installed successfully!
  ℹ Verifying installation...
  ✓ Docker is working correctly
  Would you like to add your user to the docker group? (recommended) [Y/n]: y
  ✓ User added to docker group
  ⚠ You will need to log out and back in for this to take effect
```

**If Docker is not installed (as root):**

```
  ⚠ Docker is not installed
  Would you like to install Docker? [Y/n]: y

───────────────────────────────────────────────────────────────────────────────

  Installing Docker and Docker Compose...

  ℹ Detected ubuntu 22.04
  ℹ Updating package index...
  ℹ Installing prerequisites...
  ℹ Adding Docker GPG key...
  ℹ Adding Docker repository...
  ℹ Installing Docker Engine and Docker Compose...
  ✓ Docker and Docker Compose installed successfully!
  ℹ Verifying installation...
  ✓ Docker is working correctly
  ✓ Running as root - no docker group membership needed
```

**On macOS (with Homebrew):**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Docker Environment Check                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
  ⚠ Docker is not installed
  Would you like to install Docker? [Y/n]: y

───────────────────────────────────────────────────────────────────────────────

  Installing Docker and Docker Compose...

  ℹ Detected macOS
  ℹ Homebrew detected
  Install Docker Desktop using Homebrew? [Y/n]: y
  ℹ Installing Docker Desktop via Homebrew...
  ✓ Docker Desktop installed!

  IMPORTANT: You need to start Docker Desktop manually:
    1. Open Docker from Applications folder
    2. Complete the Docker Desktop setup wizard
    3. Wait for Docker to start (whale icon in menu bar)
    4. Run this script again

  Have you started Docker Desktop and it's running? [y/N]: y
  ✓ Docker is running!
```

**On WSL2:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Docker Environment Check                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
  ⚠ Docker is not installed
  Would you like to install Docker? [Y/n]: y

───────────────────────────────────────────────────────────────────────────────

  Installing Docker and Docker Compose...

  ℹ Detected WSL (Windows Subsystem for Linux)

  You have two options for Docker in WSL:

  Option 1: Docker Desktop for Windows (recommended):
    1. Download Docker Desktop from: https://www.docker.com/products/docker-desktop/
    2. Install and enable 'Use WSL 2 based engine' in settings
    3. Enable integration with your WSL distro in Settings > Resources > WSL Integration
    4. Run this script again

  Option 2: Native Docker in WSL2:
    Install Docker directly in your WSL distro (requires WSL2)

  Would you like to install Docker natively in WSL2? [y/N]: y
  ℹ Installing Docker natively in WSL...
  ℹ Detected ubuntu 22.04 in WSL
  ℹ Updating package index...
  ℹ Installing prerequisites...
  ℹ Adding Docker GPG key...
  ℹ Adding Docker repository...
  ℹ Installing Docker Engine and Docker Compose...
  ℹ Starting Docker daemon...
  ✓ Docker and Docker Compose installed successfully!
  ⚠ Note: You may need to start Docker manually after WSL restarts:
    sudo service docker start
```

---

### 4.4 System Checks

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ System Requirements Check                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
  ✓ Disk space: 45GB available (5GB required)
  ✓ Memory: 4GB total (2GB required)
  ✓ Port 443 is available
  ✓ OpenSSL is available
  ✓ curl is available
  ✓ Internet connectivity OK
```

---

### 4.5 DNS Provider Selection

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ DNS Provider Configuration                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
  Let's Encrypt uses DNS validation to issue SSL certificates.
  This requires API access to your DNS provider.

  Select your DNS provider:

    1) Cloudflare
    2) AWS Route 53
    3) Google Cloud DNS
    4) DigitalOcean
    5) Other (manual configuration)

  Enter your choice [1-5]: 1

───────────────────────────────────────────────────────────────────────────────

  Cloudflare API Configuration

  You need a Cloudflare API token with the following permissions:
    - Zone:DNS:Edit (for your domain's zone)

  Create one at: https://dash.cloudflare.com/profile/api-tokens

  Enter your Cloudflare API token [hidden]:
  ✓ Cloudflare credentials saved to cloudflare.ini
```

---

### 4.6 Domain Configuration

The script validates your domain and checks if it resolves to your server:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Domain Configuration                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
  Enter the fully qualified domain name where n8n will be accessible.
  Example: n8n.yourdomain.com

  Enter your n8n domain [n8n.example.com]: n8n.mycompany.com

───────────────────────────────────────────────────────────────────────────────

  Validating domain configuration...

  ℹ Resolving n8n.mycompany.com...
  ✓ Domain resolves to: 192.168.113.50
  ✓ Domain IP matches this server
  ℹ Testing connectivity to 192.168.113.50...
  ✓ Host 192.168.113.50 is reachable
```

**If domain doesn't match server IP:**

```
  ⚠ Domain IP (198.51.100.25) does not match any local IP

  Local IP addresses on this machine:
    - 192.168.113.50
    - 10.0.0.5

  IMPORTANT:
  The domain n8n.mycompany.com points to 198.51.100.25
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

  Do you understand the risks and want to continue? [y/N]:
```

---

#### Understanding DNS Configuration: Cloudflare Tunnel vs Port Forwarding

How your domain should be configured depends on how external traffic reaches your n8n server:

**Option 1: Cloudflare Tunnel**

If you're using Cloudflare Tunnel, your domain MUST resolve to the **INTERNAL IP address** of your server (an RFC1918 private IP like `192.168.x.x`, `10.x.x.x`, or `172.16-31.x.x`).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CLOUDFLARE TUNNEL - DNS Configuration                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ n8n.yourdomain.com ──► Local host Record/Internal DNS Sever: 192.168.113.50 │
│                        (Your server's INTERNAL IP)                          │
│                                                                             │
│   Why Internal IP?                                                          │
│   The cloudflared daemon performs a LOCAL host lookup for your domain       │
│   and uses that IP (192.168.113.50) as the routing endpoint.                │
│                                                                             │
│   Example: host n8n.mycompany.com → 192.168.113.50                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Setup Script Behavior for Cloudflare Tunnel:**
- Validates that your domain resolves to your server's **INTERNAL IP**
- The cloudflared daemon performs a local host lookup for your domain
- This internal IP is used as the tunnel's routing endpoint
- Prompts for your Cloudflare Tunnel token
- Configures the cloudflared container automatically

**Option 2: Port Forwarding (No Cloudflare Tunnel)**

If you're NOT using Cloudflare Tunnel and are instead using traditional port forwarding through your router/firewall, your domain should resolve to your **EXTERNAL (public) IP address**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PORT FORWARDING - DNS Configuration                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   n8n.yourdomain.com ──────► A Record: 203.0.113.1                          │
│                              (Your firewall's EXTERNAL/PUBLIC IP)           │
│                                                                             │
│   Your firewall/router must forward port 443 to your server:                │
│   External:443 ──────► Internal Server: 192.168.113.50:443                  │
│                                                                             │
│   Example: n8n.mycompany.com → A → 203.0.113.1 (public IP)                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Setup Script Behavior for Port Forwarding:**
- **Skips IP validation** (no automatic check)
- Performs an nslookup on your domain and displays the resolved IP
- Informs you that this IP should be the **EXTERNAL IP** on your firewall
- Tells you to forward port 443 to your server's internal IP (where n8n is installed)
- Example: If your server's internal IP is 192.168.50.50, port 443 on your firewall should forward to 192.168.50.50:443

**Important Notes:**
- **SSL certificates are required for both methods** - n8n requires HTTPS for webhooks and CORS compliance
- Both methods use DNS-01 challenge for Let's Encrypt (no port 80 exposure needed)

---

### 4.7 Database Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PostgreSQL Database Configuration                                           │
└─────────────────────────────────────────────────────────────────────────────┘
  Configure your PostgreSQL database settings.
  These credentials will be used by n8n to store data.

  Database name [n8n]:
  Database username [n8n]:

  Enter a strong password for the database.
  Leave blank to auto-generate a secure password.

  Database password [hidden]:
  ✓ Generated secure database password
  ✓ pgvector extension automatically created
```

---

### 4.8 Container Names

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Container Names Configuration                                               │
└─────────────────────────────────────────────────────────────────────────────┘
  The following default container names will be used:

    PostgreSQL:  n8n_postgres
    n8n:         n8n
    Nginx:       n8n_nginx
    Certbot:     n8n_certbot

  Would you like to customize these names? [y/N]: n
  ✓ Container names configured
```

---

### 4.9 Email & Timezone

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Let's Encrypt Email Configuration                                           │
└─────────────────────────────────────────────────────────────────────────────┘
  Let's Encrypt requires an email address for:
    - Certificate expiration notifications
    - Account recovery

  Email address for Let's Encrypt [admin@mycompany.com]:

┌─────────────────────────────────────────────────────────────────────────────┐
│ Timezone Configuration                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
  Detected system timezone: America/New_York

  Use America/New_York as the timezone for n8n? [Y/n]:
  ✓ Timezone set to: America/New_York
```

---

### 4.10 Encryption Key

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Encryption Key Configuration                                                │
└─────────────────────────────────────────────────────────────────────────────┘
  n8n uses an encryption key to secure credentials stored in the database.
  This key should be kept secret and backed up securely.

  ✓ Generated secure encryption key using OpenSSL

  ⚠ IMPORTANT: Save your encryption key in a secure location!
  If you lose this key, you will not be able to decrypt stored credentials.
```

---

### 4.11 Portainer Agent (Optional)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Portainer Agent Configuration                                               │
└─────────────────────────────────────────────────────────────────────────────┘
  Portainer is a popular container management UI.
  If you're running Portainer on another server, you can install
  the Portainer Agent here to manage this n8n stack remotely.

  Are you using Portainer to manage your containers? [y/N]: y
  ✓ Portainer Agent will be included in docker-compose.yaml

  The agent will be accessible on port 9001.
  Add this server to Portainer using: <this-server-ip>:9001
```

---

### 4.12 Configuration Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Configuration Summary                                                       │
└─────────────────────────────────────────────────────────────────────────────┘

  Domain & URL:
    Domain:              n8n.mycompany.com
    URL:                 https://n8n.mycompany.com

  DNS Provider:
    Provider:            cloudflare
    Credentials file:    cloudflare.ini

  Database:
    Name:                n8n
    User:                n8n
    Password:            [configured]

  Container Names:
    PostgreSQL:          n8n_postgres
    n8n:                 n8n
    Nginx:               n8n_nginx
    Certbot:             n8n_certbot

  Other Settings:
    Email:               admin@mycompany.com
    Timezone:            America/New_York
    Encryption key:      [configured]
    Portainer Agent:     enabled

───────────────────────────────────────────────────────────────────────────────

  Is this configuration correct? [Y/n]:
```

---

### 4.13 Deployment & Testing

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Generating Configuration Files                                              │
└─────────────────────────────────────────────────────────────────────────────┘

  [1/4] Generating docker-compose.yaml

  ✓ docker-compose.yaml generated

  [2/4] Generating nginx.conf

  ✓ nginx.conf generated

  [3/4] Saving configuration backup

  ✓ Configuration saved to /home/user/n8n_nginx/.n8n_setup_config

  [4/4] Creating Let's Encrypt Docker volume

  ✓ Volume 'letsencrypt' created

  ✓ All configuration files generated successfully!

  Would you like to deploy the stack now? [Y/n]: y

┌─────────────────────────────────────────────────────────────────────────────┐
│ Deploying n8n Stack                                                         │
└─────────────────────────────────────────────────────────────────────────────┘

  [1/6] Starting PostgreSQL database

  Waiting for PostgreSQL to be ready...
  ✓ PostgreSQL is running and healthy

  [2/6] Obtaining SSL certificate from Let's Encrypt

  Domain: n8n.mycompany.com
  This uses DNS-01 challenge (no ports 80/443 exposure required)

  Saving debug log to /var/log/letsencrypt/letsencrypt.log
  Requesting a certificate for n8n.mycompany.com
  Waiting 60 seconds for DNS propagation

  Successfully received certificate.
  Certificate is saved at: /etc/letsencrypt/live/n8n.mycompany.com/fullchain.pem
  Key is saved at:         /etc/letsencrypt/live/n8n.mycompany.com/privkey.pem

  ✓ SSL certificate obtained successfully!

  [3/6] Copying certificates to Docker volume

  ✓ Certificates copied to Docker volume

  [4/6] Starting all services

  Waiting for services to start...
  ✓ All services started

  [5/6] Verifying services

  Checking PostgreSQL...
  ✓ PostgreSQL is responding
  ✓ PostgreSQL authentication successful
  Checking n8n...
  ✓ n8n is responding
  Checking Nginx...
  ✓ Nginx configuration is valid

  Container Status:
  NAMES          STATUS                   PORTS
  n8n_postgres   Up 2 minutes (healthy)
  n8n            Up About a minute
  n8n_nginx      Up About a minute        0.0.0.0:443->443/tcp
  n8n_certbot    Up About a minute

  [6/6] Testing SSL certificate and connectivity

  Testing HTTPS connectivity to https://n8n.mycompany.com...
  ✓ SSL certificate is valid
  notBefore=Nov 29 00:00:00 2025 GMT
  notAfter=Feb 27 23:59:59 2026 GMT
  ✓ n8n is accessible via HTTPS

  ✓ All connectivity tests passed!

╔═══════════════════════════════════════════════════════════════════════════╗
║                           Setup Complete!                                 ║
╚═══════════════════════════════════════════════════════════════════════════╝

  Your n8n instance is now running!

  Access your n8n instance:
    https://n8n.mycompany.com

  Useful Commands:
    View logs:         docker compose logs -f
    View n8n logs:     docker compose logs -f n8n
    Stop services:     docker compose down
    Start services:    docker compose up -d
    Restart services:  docker compose restart
    View status:       docker compose ps

  Important Files:
    Docker Compose:    /home/user/n8n_nginx/docker-compose.yaml
    Nginx Config:      /home/user/n8n_nginx/nginx.conf
    DNS Credentials:   /home/user/n8n_nginx/cloudflare.ini
    Setup Config:      /home/user/n8n_nginx/.n8n_setup_config

  Security Reminders:
    - Create your n8n owner account immediately
    - Back up your encryption key securely
    - Keep your DNS credentials file secure (chmod 600)
    - SSL certificates auto-renew every 12 hours

───────────────────────────────────────────────────────────────────────────────

  Thank you for using n8n Management Setup Script v3.0.0
  Created by Richard J. Sears - richardjsears@gmail.com
```