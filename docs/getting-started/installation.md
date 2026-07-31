# Installation

A full walkthrough of installing n8n Management Suite, from gathering the information you need through the automated `setup.sh` wizard to a fully deployed, HTTPS-secured stack.

## Pre-Installation Preparation

### Gathering Required Information

Before running the setup script, gather the following information:

#### Required Information

| Item | Description | Where to Get It |
|------|-------------|-----------------|
| Domain Name | The domain for your n8n instance (e.g., `n8n.example.com`) | Your domain registrar |
| DNS Provider Credentials | API credentials for your DNS provider | See [Appendix A](https://github.com/rjsears/n8n_nginx/blob/main/README.md#appendix-a-dns-provider-credential-setup) |
| Email Address | For Let's Encrypt certificate notifications | Your email |
| Admin Password | Password for the management console (min 8 characters) | Create a strong password |

#### Optional Information

| Item | Description | When Needed |
|------|-------------|-------------|
| Tailscale Auth Key | Pre-authenticated key for Tailscale VPN | If using Tailscale for secure access |
| Cloudflare Tunnel Token | Token for Cloudflare Zero Trust tunnel | If using Cloudflare Tunnel |
| NFS Server Details | Server address and export path | If using NFS for backup storage |

### Preparing Your Server

#### Automatic System Preparation

The setup script now **automatically handles system preparation** for you:

- **OS Auto-Detection**: Detects your operating system (Ubuntu, Debian, CentOS, RHEL, Rocky, AlmaLinux, Fedora, openSUSE, Arch Linux, Alpine)
- **Package Manager Detection**: Automatically uses the correct package manager (apt, dnf, yum, zypper, pacman, apk)
- **System Updates**: Optionally updates your system packages
- **Utility Installation**: Installs required utilities (curl, git, openssl, jq) if missing
- **Privilege Handling**: Uses sudo only when necessary (not when running as root)

When you run `./setup.sh`, you'll see:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ System Preparation                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
  ℹ Detected OS: Ubuntu 22.04 (debian family)
  ℹ Package Manager: apt

  Would you like to update system packages? [Y/n]: y

  Updating system packages...
  ✓ System packages updated successfully

  Checking required utilities...
  ✓ curl is installed
  ✓ git is installed
  ✓ openssl is installed
  ✓ jq is installed

  ✓ System preparation complete
```

> **Note:** The script will automatically check for system updates and apply them as part of the setup!

#### Configure DNS

Ensure your domain points to your server's IP address:

1. Log in to your DNS provider's control panel
2. Create an A record pointing your domain to your server's public IP
3. Wait for DNS propagation (typically 5-30 minutes)

Verify DNS resolution:

```bash
# Check if domain resolves to your server
dig +short n8n.yourdomain.com

# Or using nslookup
nslookup n8n.yourdomain.com
```

#### Understanding DNS Configuration: Cloudflare Tunnel vs Port Forwarding

Before configuring DNS, it's important to understand the two main approaches for exposing your n8n instance to the internet:

##### Option 1: Traditional Port Forwarding (A Record)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TRADITIONAL PORT FORWARDING                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Internet Users                                                            │
│         │                                                                   │
│         ▼                                                                   │
│   n8n.yourdomain.com ──────► A Record: 203.0.113.50                         │
│         │                    (Your public IP)                               │
│         ▼                                                                   │
│   Your Router (Port 443) ──► Port Forward to Server                         │
│         │                                                                   │
│         ▼                                                                   │
│   Your Server (Nginx:443) ──► n8n Container                                 │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│   ✓ Direct connection - lowest latency                                      │
│   ✓ Full control over your infrastructure                                   │
│   ✗ Requires static IP or DDNS                                              │
│   ✗ Port 443 must be open in firewall/router                                │
│   ✗ Your server's IP is exposed to the internet                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**DNS Configuration for Port Forwarding:**
1. Create an **A Record** pointing to your server's **public IP address**
2. Open port 443 on your router/firewall
3. The domain should resolve to your server's public IP

##### Option 2: Cloudflare Tunnel (CNAME/Proxied)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CLOUDFLARE TUNNEL                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Internet Users                                                            │
│         │                                                                   │
│         ▼                                                                   │
│   n8n.yourdomain.com ──────► CNAME: xxxxx.cfargotunnel.com                  │
│         │                    (Cloudflare Tunnel endpoint)                   │
│         ▼                                                                   │
│   Cloudflare Edge Network                                                   │
│         │                    DDoS Protection, WAF, Caching                  │
│         ▼                                                                   │
│   ═══════ Encrypted Tunnel ═══════                                          │
│         │                    (Outbound connection from your server)         │
│         ▼                                                                   │
│   cloudflared Container ──► Nginx ──► n8n Container                         │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│   ✓ NO open ports required - server initiates outbound connection           │
│   ✓ Your server IP is HIDDEN from the internet                              │
│   ✓ Built-in DDoS protection and WAF                                        │
│   ✓ Works behind CGNAT or dynamic IPs                                       │
│   ✓ Zero Trust access policies available                                    │
│   ✗ Slightly higher latency (traffic routes through Cloudflare)             │
│   ✗ Requires Cloudflare account and domain on Cloudflare                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**DNS Configuration for Cloudflare Tunnel:**
1. Domain DNS must be managed by Cloudflare
2. Tunnel automatically creates **CNAME records** pointing to your tunnel
3. **No A record needed** - DNS points to Cloudflare, not your server
4. The domain will NOT resolve to your server's IP (this is expected!)

##### Which Should I Choose?

| Factor | Port Forwarding | Cloudflare Tunnel |
|--------|-----------------|-------------------|
| **Home/Residential Network** | Challenging (CGNAT, dynamic IP) | ✓ Recommended |
| **Business/Static IP** | ✓ Works well | ✓ Works well |
| **Security Priority** | Good with proper firewall | ✓ Better (hidden IP) |
| **Latency Sensitive** | ✓ Lower latency | Slightly higher |
| **Complex Firewall/NAT** | May need port forwarding | ✓ No config needed |
| **Multi-site Deployment** | Complex | ✓ Easy |

##### Setup Script Behavior

During setup, the script will ask early on:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Connectivity Method                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
  How will users access your n8n instance?

    1) Port Forwarding / Direct Access
       Your domain's A record points directly to your server's public IP.
       Port 443 must be accessible from the internet.

    2) Cloudflare Tunnel
       No open ports required. Cloudflare Tunnel creates a secure outbound
       connection. Your domain must use Cloudflare DNS.

  Enter your choice [1-2]:
```

**If you choose Cloudflare Tunnel**, the setup script will:
- **Validate** that your domain resolves to your server's **INTERNAL IP** (e.g., 192.168.x.x)
- Show a warning if the domain IP doesn't match any local IP on this server
- The cloudflared daemon uses this internal IP as its routing endpoint
- Prompt for your Cloudflare Tunnel token
- Configure the cloudflared container automatically

**If you choose Port Forwarding**, the setup script will:
- **Skip IP validation** (no automatic check)
- Perform an nslookup on your domain and display the resolved IP
- Inform you that this IP should be the **EXTERNAL IP** on your firewall
- Tell you to forward port 443 to this server's internal IP (where n8n is installed)
- Configure direct SSL termination via Nginx

### Installing the Repository

#### Quick Install (Recommended)

The fastest way to get started is using the one-line installer:

```bash
curl -fsSL https://raw.githubusercontent.com/rjsears/n8n_nginx/main/install.sh | bash
```

This will:
- Check for and install `git` if needed
- Clone the repository
- Automatically launch the setup wizard

> **Testing a specific branch**: Use the `BRANCH` environment variable:
> ```bash
> curl -fsSL https://raw.githubusercontent.com/rjsears/n8n_nginx/main/install.sh | BRANCH=dev bash
> ```

#### Manual Install (Alternative)

If you prefer to clone manually:

```bash
# Clone the repository
git clone https://github.com/rjsears/n8n_nginx.git

# Navigate to the directory
cd n8n_nginx

# Make setup script executable and run it
chmod +x setup.sh
./setup.sh
```

---


---

## Installation Methods

The setup script supports two installation methods: **Interactive Setup** (guided wizard) and **Unattended Installation** (pre-configured).

### Unattended Installation (Pre-Configuration)

For automated deployments, you can use a pre-configuration file to skip the interactive prompts:

#### Step 1: Create Configuration File

```bash
cp setup-config.example setup-config
```

#### Step 2: Edit Configuration

Edit `setup-config` with your values. Key settings include:

```bash
# Required
DOMAIN=n8n.example.com
SSL_METHOD=certbot              # certbot, existing, or none
LETSENCRYPT_EMAIL=admin@example.com
DNS_PROVIDER=cloudflare
CLOUDFLARE_API_TOKEN=your-api-token

# Auto-generated if left blank
POSTGRES_PASSWORD=
N8N_ENCRYPTION_KEY=
MGMT_SECRET_KEY=

# Optional - Tailscale (auto-enables when key provided)
TAILSCALE_AUTH_KEY=tskey-auth-xxxxx

# Optional - Cloudflare Tunnel (auto-enables when token provided)
CLOUDFLARE_TUNNEL_TOKEN=

# Fully unattended mode
AUTO_CONFIRM=true
```

#### Step 3: Run Setup

```bash
./setup.sh --config setup-config
```

#### Smart Defaults

- **Credentials**: If `POSTGRES_PASSWORD`, `N8N_ENCRYPTION_KEY`, or `ADMIN_PASS` are left blank, secure random values are auto-generated and displayed at the end of setup
- **Service Enablement**: Tailscale and Cloudflare Tunnel are automatically enabled when their auth keys/tokens are provided
- **Validation**: The script validates all settings (domain format, DNS credentials, NFS connectivity) and prompts for corrections if needed (unless `AUTO_CONFIRM=true`)

#### Available Options

See `setup-config.example` for all available options including:
- Storage settings (local, NFS)
- Compression settings
- Retention policies
- Optional services (Adminer, Dozzle, Portainer)
- Access control (IP whitelisting)

---

## Interactive Setup



### Welcome Screen

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

### Running as Root

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

### Docker Installation

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

### System Checks

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

### DNS Provider Selection

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

### Domain Configuration

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

### Database Configuration

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

### Container Names

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

### Email & Timezone

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

### Encryption Key

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

### Portainer Agent (Optional)

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

### Configuration Summary

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

### Deployment & Testing

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
  Created by Richard J. Sears - richard@n8nmanagement.net
```
