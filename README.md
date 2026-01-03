<p align="center">
  <img src="images/n8n_repo_banner.jpg" alt="n8n Management Suite" width="800"/>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://github.com/rjsears/n8n_nginx/commits"><img src="https://img.shields.io/github/last-commit/rjsears/n8n_nginx" alt="GitHub last commit"></a>
  <a href="https://github.com/rjsears/n8n_nginx/issues"><img src="https://img.shields.io/github/issues/rjsears/n8n_nginx" alt="GitHub issues"></a>
  <a href="docs/CHANGELOG.md"><img src="https://img.shields.io/badge/Version-3.0.0-orange" alt="Version"></a>
</p>

<p align="center">
  <a href="https://n8n.io"><img src="https://img.shields.io/badge/n8n-Workflow%20Automation-FF6D5A?logo=n8n&logoColor=white" alt="n8n"></a>
  <a href="https://www.postgresql.org"><img src="https://img.shields.io/badge/PostgreSQL-16%20with%20pgvector-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL"></a>
  <a href="https://docker.com"><img src="https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker&logoColor=white" alt="Docker"></a>
  <a href="https://nginx.org"><img src="https://img.shields.io/badge/Nginx-Reverse%20Proxy-009639?logo=nginx&logoColor=white" alt="Nginx"></a>
  <a href="https://letsencrypt.org"><img src="https://img.shields.io/badge/Let's%20Encrypt-SSL%2FTLS-003A70?logo=letsencrypt&logoColor=white" alt="Let's Encrypt"></a>
</p>

<p align="center">
  <a href="https://vuejs.org"><img src="https://img.shields.io/badge/Vue.js-3-4FC08D?logo=vuedotjs&logoColor=white" alt="Vue.js"></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-Python-009688?logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="https://tailscale.com"><img src="https://img.shields.io/badge/Tailscale-VPN%20Ready-242424?logo=tailscale&logoColor=white" alt="Tailscale"></a>
  <a href="https://ntfy.sh"><img src="https://img.shields.io/badge/ntfy-Push%20Notifications-57A143" alt="ntfy"></a>
</p>

> ### *"Automation means solving a problem once, then putting the solution on autopilot."* — Michael Hyatt

---

# n8n Management Suite

A production-ready, self-hosted deployment solution for [n8n](https://n8n.io) workflow automation with integrated HTTPS/SSL certificate management, PostgreSQL database with pgvector for AI/RAG workflows, comprehensive backup and disaster recovery, multi-channel notifications, and a full-featured web-based management console.

---

## Table of Contents

### Part I: Introduction
- [1. Overview](#1-overview)
  - [1.1 What is the "n8n Management Suite"?](#11-what-is-n8n-enterprise-deployment-suite)
  - [1.2 Key Features at a Glance](#12-key-features-at-a-glance)
  - [1.3 Architecture Overview](#13-architecture-overview)
  - [1.4 Technology Stack](#14-technology-stack)
- [2. System Requirements](#2-system-requirements)
  - [2.1 Hardware Requirements](#21-hardware-requirements)
  - [2.2 Software Requirements](#22-software-requirements)
  - [2.3 Supported Operating Systems](#23-supported-operating-systems)
  - [2.4 Network Requirements](#24-network-requirements)
  - [2.5 DNS Provider Requirements](#25-dns-provider-requirements)

### Part II: Installation
- [3. Pre-Installation Preparation](#3-pre-installation-preparation)
  - [3.1 Gathering Required Information](#31-gathering-required-information)
  - [3.2 Preparing Your Server](#32-preparing-your-server)
  - [3.3 Downloading the Repository](#33-downloading-the-repository)
- [4. Installation Methods](#4-installation-methods)
  - [4.1 Unattended Installation (Pre-Configuration)](#41-unattended-installation-pre-configuration)
- [5. Interactive Setup](#5-interactive-setup)
  - [5.1 Welcome Screen](#51-welcome-screen)
  - [5.2 Running as Root](#52-running-as-root)
  - [5.3 Docker Installation](#53-docker-installation)
  - [5.4 System Checks](#54-system-checks)
  - [5.5 DNS Provider Selection](#55-dns-provider-selection)
  - [5.6 Domain Configuration](#56-domain-configuration)
  - [5.7 Database Configuration](#57-database-configuration)
  - [5.8 Container Names](#58-container-names)
  - [5.9 Email & Timezone](#59-email--timezone)
  - [5.10 Encryption Key](#510-encryption-key)
  - [5.11 Portainer Agent](#511-portainer-agent)
  - [5.12 Configuration Summary](#512-configuration-summary)
  - [5.13 Deployment & Testing](#513-deployment--testing)

### Part III: Initial Configuration
- [6. First-Time Setup](#6-first-time-setup)
  - [6.1 Accessing the n8n Interface](#61-accessing-the-n8n-interface)
  - [6.2 Accessing the Management Console](#62-accessing-the-management-console)
  - [6.3 Configuring the n8n API Connection](#63-configuring-the-n8n-api-connection)
  - [6.4 Deploying Test Workflows](#64-deploying-test-workflows)
  - [6.5 IP Access Control Configuration](#65-ip-access-control-configuration)

### Part IV: Management Console Reference
- [7. Dashboard](#7-dashboard)
- [7. Backup Management](#7-backup-management)
  - [7.1 Understanding the Backup System](#71-understanding-the-backup-system)
  - [7.2 Backup History](#72-backup-history)
  - [7.3 Manual Backups](#73-manual-backups)
  - [7.4 Scheduled Backups](#74-scheduled-backups)
  - [7.5 Backup Verification](#75-backup-verification)
  - [7.6 Restoration](#76-restoration)
  - [7.7 Backup Settings](#77-backup-settings)
  - [7.8 Backup Notifications](#78-backup-notifications)
- [8. Notification System](#8-notification-system)
  - [8.1 Notification Architecture](#81-notification-architecture)
  - [8.2 Notification Channels](#82-notification-channels)
  - [8.3 Creating Notification Channels](#83-creating-notification-channels)
  - [8.4 Notification Groups](#84-notification-groups)
  - [8.5 NTFY Configuration](#85-ntfy-configuration)
  - [8.6 Standalone NTFY Server Setup](#86-standalone-ntfy-server-setup)
  - [8.7 n8n Webhook Integration](#87-n8n-webhook-integration)
- [9. System Notifications](#9-system-notifications)
  - [9.1 Event Types](#91-event-types)
  - [9.2 Event Configuration Options](#92-event-configuration-options)
  - [9.3 Escalation](#93-escalation)
  - [9.4 Global Settings](#94-global-settings)
  - [9.5 Per-Container Configuration](#95-per-container-configuration)
  - [9.6 Flapping Detection](#96-flapping-detection)
- [10. Container Management](#10-container-management)
- [11. Workflow Management](#11-workflow-management)
- [12. System Monitoring](#12-system-monitoring)
- [13. Settings](#13-settings)

### Part V: Operations and Maintenance
- [14. Daily Operations](#14-daily-operations)
- [15. SSL Certificate Management](#15-ssl-certificate-management)
- [16. Database Management](#16-database-management)
- [17. Container Maintenance](#17-container-maintenance)
- [18. Backup Best Practices](#18-backup-best-practices)

### Part VI: Advanced Configuration
- [19. Tailscale Integration](#19-tailscale-integration)
- [20. Cloudflare Tunnel](#20-cloudflare-tunnel)
- [21. NFS Backup Storage](#21-nfs-backup-storage)
- [22. Custom Nginx Configuration](#22-custom-nginx-configuration)
- [23. Environment Variables Reference](#23-environment-variables-reference)

### Part VII: Troubleshooting
- [24. Common Issues and Solutions](#24-common-issues-and-solutions)
- [25. Logs and Diagnostics](#25-logs-and-diagnostics)

### Part VIII: Reference
- [26. Command Reference](#26-command-reference)
- [27. File Locations](#27-file-locations)
- [28. Glossary](#28-glossary)

### Appendices
- [Appendix A: DNS Provider Credential Setup](#appendix-a-dns-provider-credential-setup)
- [Appendix B: Tailscale Auth Key Generation](#appendix-b-tailscale-auth-key-generation)
- [Appendix C: Cloudflare Tunnel Token Generation](#appendix-c-cloudflare-tunnel-token-generation)
- [Appendix D: n8n API Key Generation](#appendix-d-n8n-api-key-generation)

### Detailed Guides
- [API Reference](./docs/API.md) - REST API documentation
- [Backup Guide](./docs/BACKUP_GUIDE.md) - Backup and restore procedures
- [Certbot Guide](./docs/CERTBOT.md) - SSL certificate management with Let's Encrypt
- [Cloudflare Guide](./docs/CLOUDFLARE.md) - Cloudflare Tunnel setup and configuration
- [Migration Guide](./docs/MIGRATION.md) - Upgrading from v2.0 to v3.0
- [Notifications Guide](./docs/NOTIFICATIONS.md) - Alert and notification setup
- [Tailscale Guide](./docs/TAILSCALE.md) - Tailscale VPN integration
- [Troubleshooting](./docs/TROUBLESHOOTING.md) - Common issues and solutions

---

# Part I: Introduction

## 1. Overview

### 1.1 What is n8n Management Suite?

The n8n Management Suite is a comprehensive, production-ready deployment and management solution for self-hosted n8n workflow automation. It combines:

- **Automated Deployment**: A single interactive script that handles everything from Docker installation to SSL certificate acquisition
- **Enterprise Software**: PostgreSQL 16 with pgvector for AI/RAG workflows, Nginx reverse proxy with automatic HTTPS, and Let's Encrypt certificate management
- **Management Console**: A full-featured web application for monitoring, backup management, notifications, and system administration
- **Disaster Recovery**: Comprehensive backup system with verification, selective restoration, and bare-metal recovery capabilities
- **Multi-Channel Notifications**: Support for 30+ notification providers through Apprise, plus native NTFY push notifications

Whether you are running n8n for personal automation or deploying it for an organization, this suite provides the infrastructure, monitoring, and management tools typically found only in expensive enterprise solutions.

### 1.2 Key Features at a Glance

#### Deployment and Infrastructure
- One-command interactive setup with automatic Docker installation
- Automatic SSL/TLS certificate acquisition and renewal via Let's Encrypt
- Certbot / Let's Encrypt support for multiple DNS providers (Cloudflare, AWS Route 53, Google Cloud DNS, DigitalOcean)
- PostgreSQL 16 with pgvector extension for AI vector embeddings
- Nginx reverse proxy with optimized configuration for n8n
- Optional Tailscale VPN and Cloudflare Tunnel integration

#### Management Console
- Real-time system metrics dashboard (CPU, memory, disk, network)
- Docker container management (start, stop, restart, recreate, alerts, logs)
- Realtime web-based terminal access to any running container
- n8n workflow monitoring and control
- Comprehensive backup, alert and notifications settings management
- Dark/light theme support

#### Backup and Recovery
- Scheduled and on-demand backups
- Multiple storage backends (local, NFS)
- Backup verification with integrity checking
- Selective workflow restoration - recover any workflow from any backup
- Full system bare-metal recovery
- Grandfather-Father-Son (GFS) retention policies
- Automatic pruning with space management

#### Notifications
- 80+ notification providers via Apprise integration
- Native NTFY push notification support via ntfy.sh
- Optional locally hosted and integrated NFTY container
- Email notifications with customizable templates
- Webhook integration for notifications within n8n workflows
- System event notifications with configurable triggers
- L1/L2 escalation support
- Maintenance mode and quiet hours
- API for full notification support from n8n workflows
- Create notification 'groups' from any configured notification channel

### 1.3 Architecture Overview

```mermaid
flowchart TB
    subgraph Internet["Internet"]
        User["User Browser"]
        Webhook["External Webhooks"]
    end

    subgraph Docker["Docker Environment"]
        subgraph Proxy["Reverse Proxy Layer"]
            Nginx["Nginx<br/>:443 HTTPS"]
        end

        subgraph Core["Core Services"]
            N8N["n8n<br/>:5678"]
            PG[("PostgreSQL 16<br/>with pgvector")]
        end

        subgraph Management["Management Layer"]
            MGMT["Management Console<br/>/management"]
            API["FastAPI Backend"]
        end

        subgraph Optional["Optional Services"]
            NTFY["NTFY Server"]
            Portainer["Portainer"]
            Adminer["Adminer"]
            Dozzle["Dozzle"]
            Tailscale["Tailscale"]
        end

        subgraph SSL["Certificate Management"]
            Certbot["Certbot"]
        end
    end

    subgraph External["External Services"]
        LE["Let's Encrypt"]
        DNS["DNS Provider API"]
    end

    User --> Nginx
    Webhook --> Nginx
    Nginx --> N8N
    Nginx --> MGMT
    N8N --> PG
    MGMT --> API
    API --> PG
    API --> N8N
    Certbot --> LE
    Certbot --> DNS
```

#### Component Overview

| Component              | Purpose                                                                 |
|------------------------|-------------------------------------------------------------------------|
| **Nginx**              | Reverse proxy handling HTTPS termination, routing, and security headers |
| **n8n**                | Workflow automation engine                                              |
| **PostgreSQL**         | Primary database with pgvector for AI/ML vector operations              |
| **Management Console** | Web-based administration interface                                      |
| **FastAPI Backend**    | REST API powering the management console                                |
| **Certbot**            | Optional Automatic SSL certificate acquisition and renewal              |
| **NTFY**               | Optional self-hosted push notification server                           |
| **Portainer**          | Optional container management UI                                        |
| **Adminer**            | Optional database administration UI                                     |
| **Dozzle**             | Optional real-time log viewer                                           |
| **Tailscale**          | Optional VPN for secure remote access                                   |
| **Cloudflared**        | Optional Cloudflare Tunnel for external access without port forwarding  |

### 1.4 Technology Stack

#### Backend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Management console backend |
| FastAPI | Latest | Async web framework for REST API |
| SQLAlchemy | 2.0 | Async ORM for database operations |
| PostgreSQL | 16 | Primary database |
| pgvector | Latest | Vector embeddings for AI/RAG |
| APScheduler | Latest | Task scheduling for backups |
| Bcrypt | Latest | Password hashing |
| Cryptography | Latest | AES-256 encryption |

#### Frontend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| Vue.js | 3 | Frontend framework |
| Vite | Latest | Build tool |
| Pinia | Latest | State management |
| Vue Router | Latest | Client-side routing |
| Tailwind CSS | Latest | Styling framework |
| Chart.js | Latest | Metrics visualization |
| Axios | Latest | HTTP client |

#### Infrastructure Technologies

| Technology | Purpose |
|------------|---------|
| Docker | Container runtime |
| Docker Compose | Container orchestration |
| Nginx | Reverse proxy and SSL termination |
| Certbot | Let's Encrypt certificate automation |
| Let's Encrypt | Free SSL/TLS certificates |

---

## 2. System Requirements

### 2.1 Hardware Requirements

#### Minimum Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Storage | 20 GB | 50+ GB SSD |
| Network | 10 Mbps | 100+ Mbps |

#### Storage Considerations

- **Operating System**: ~5 GB
- **Docker Images**: ~3 GB
- **PostgreSQL Data**: Varies with workflow complexity (plan 5-20 GB)
- **Backups**: Plan for 2-3x your database size
- **n8n Data**: Varies with execution history settings

> **Note**: If using NFS for backup storage, local storage requirements for backups are reduced.

### 2.2 Software Requirements

#### Required Software

| Software | Notes |
|----------|-------|
| Docker | Automatically installed by setup.sh if not present |
| Docker Compose | V2 plugin preferred; automatically configured |
| curl | Required for setup script |
| OpenSSL | Required for key generation |

#### Automatically Installed

The setup script will automatically install these if not present:
- Docker Engine
- Docker Compose plugin
- Required Docker images
- curl
- OpenSSL

### 2.3 Supported Operating Systems

| Operating System | Versions | Notes |
|------------------|----------|-------|
| Ubuntu | 20.04, 22.04, 24.04 | Recommended |
| Debian | 11, 12 | Fully supported |
| CentOS | 8, 9 | Stream versions |
| RHEL | 8, 9 | Enterprise Linux |
| Fedora | 38+ | Latest releases |
| Rocky Linux | 8, 9 | RHEL-compatible |
| AlmaLinux | 8, 9 | RHEL-compatible |
| macOS | 10.15+ | Requires Docker Desktop |
| Windows | 10/11 | Via WSL2 with Docker Desktop |

#### Special Environments

| Environment | Support Level | Notes                                                       |
|-------------|---------------|-------------------------------------------------------------|
| Proxmox LXC | Supported | Requires `nesting=1` and `lxc.apparmor.profile: unconfined` |
| WSL2 | Supported | Requires Docker Desktop for Windows                         |
| Virtual Machines | Supported | Any hypervisor (Proxmox, VMware, VirtualBox, Hyper-V, KVM)  |

### 2.4 Network Requirements

#### Firewall Considerations

- Port 443 must be accessible from the internet for webhook functionality
- Consider using Tailscale or Cloudflare Tunnel for secure remote access

### 2.5 DNS Provider Requirements

SSL certificate acquisition requires API access to your DNS provider for DNS-01 challenge validation. The following providers are supported:

| Provider | Required Credentials | Recommended |
|----------|---------------------|-------------|
| Cloudflare | API Token with Zone:DNS:Edit permission | Yes |
| AWS Route 53 | Access Key ID + Secret Access Key | Yes |
| Google Cloud DNS | Service Account JSON key | Yes |
| DigitalOcean | API Token with read/write access | Yes |
| Manual | None (requires manual DNS record creation) | No |

> **Recommendation**: Cloudflare is recommended due to fast DNS propagation (60 seconds) and straightforward API token creation.

---

# Part II: Installation

## 3. Pre-Installation Preparation

### 3.1 Gathering Required Information

Before running the setup script, gather the following information:

#### Required Information

| Item | Description | Where to Get It |
|------|-------------|-----------------|
| Domain Name | The domain for your n8n instance (e.g., `n8n.example.com`) | Your domain registrar |
| DNS Provider Credentials | API credentials for your DNS provider | See [Appendix A](#appendix-a-dns-provider-credential-setup) |
| Email Address | For Let's Encrypt certificate notifications | Your email |
| Admin Password | Password for the management console (min 8 characters) | Create a strong password |

#### Optional Information

| Item | Description | When Needed |
|------|-------------|-------------|
| Tailscale Auth Key | Pre-authenticated key for Tailscale VPN | If using Tailscale for secure access |
| Cloudflare Tunnel Token | Token for Cloudflare Zero Trust tunnel | If using Cloudflare Tunnel |
| NFS Server Details | Server address and export path | If using NFS for backup storage |

### 3.2 Preparing Your Server

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

### 3.3 Downloading the Repository

```bash
# Clone the repository
git clone https://github.com/rjsears/n8n_nginx.git

# Navigate to the directory
cd n8n_nginx

# Make setup script executable
chmod +x setup.sh
```

---


---

## 4. Installation Methods

The setup script supports two installation methods: **Interactive Setup** (guided wizard) and **Unattended Installation** (pre-configured).

### 4.1 Unattended Installation (Pre-Configuration)

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

## 5. Interactive Setup



### 5.1 Welcome Screen

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

### 5.2 Running as Root

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

### 5.3 Docker Installation

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

### 5.4 System Checks

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

### 5.5 DNS Provider Selection

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

### 5.6 Domain Configuration

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

### 5.7 Database Configuration

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

### 5.8 Container Names

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

### 5.9 Email & Timezone

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

### 5.10 Encryption Key

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

### 5.11 Portainer Agent (Optional)

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

### 5.12 Configuration Summary

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

### 5.13 Deployment & Testing

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


# Part III: Initial Configuration

## 5. First-Time Setup

After installation is complete, you need to perform initial configuration of both n8n and the management console.

### 5.1 Accessing the n8n Interface

#### Creating Your Owner Account

1. Open your browser and navigate to `https://n8n.your-domain.com`
2. You will see the n8n setup page
3. Create your owner account:
   - Enter your email address
   - Create a password
   - Enter your first and last name
4. Click **Next** to complete setup

<!-- SCREENSHOT: n8n owner account creation -->
*[Screenshot placeholder: n8n initial setup - owner account creation]*

#### Initial n8n Configuration

After creating your account, you will be taken to the n8n editor. Before proceeding, note the following:

- Your n8n instance is now accessible at `https://n8n.your-domain.com`
- Webhooks are accessible at `https://n8n.your-domain.com/webhook/`
- The editor is fully functional and ready for workflow creation

### 5.2 Accessing the Management Console

#### Login Process

1. Navigate to `https://n8n.your-domain.com/management`
2. Enter the admin credentials you created during setup
3. Click **Login**

<!-- SCREENSHOT: Management console login page -->
*[Screenshot placeholder: Management console login screen]*

#### Dashboard Overview

After logging in, you will see the following options:

- **Dashboard**: View CPU, memory, disk usage, basic system overview
- **Backups**: Configure and manage system and n8n backups
- **Notifications**: Configure, create and manage notification channels and optionally expose them to n8n
- **Containers**: View and manage all system containers
- **Flows**: Backup, activate, deactivate and download flows from n8n
- **System**: View system health, network information and gain container terminal access
- **Settings**: Configure various system, security, access control, appearance, n8n API and debug settings 

<!-- SCREENSHOT: Management console dashboard -->
*[Screenshot placeholder: Dashboard overview with all widgets]*

### 5.3 Configuring the n8n API Connection

The management console communicates with n8n through its REST API. You need to configure this connection for full functionality.

#### Step 1: Generate an n8n API Key

1. In n8n, click your profile icon (bottom left)
2. Select **Settings**
3. Navigate to **API** in the left sidebar
4. Click **Create an API key**
5. Give it a name (e.g., "Management Console")
6. Copy the generated API key

<!-- SCREENSHOT: n8n API key generation -->
*[Screenshot placeholder: n8n Settings > API > Create API key]*

> **Important**: The API key is shown only once. Copy it immediately.

#### Step 2: Enter the API Key in Management Console

1. In the management console, go to **Settings**
2. Click the **API** tab
3. Paste your n8n API key
4. Click **Save**

<!-- SCREENSHOT: Management console API configuration -->
*[Screenshot placeholder: Settings > API tab with API key field]*

#### Step 3: Test the Connection

1. Click **Test Connection**
2. You should see a success message
3. If the test fails, verify:
   - The API key is correct
   - n8n is running (`docker compose ps`)
   - Network connectivity between containers

```
API Connection Test
-------------------
Status: Connected
n8n Version: 1.xx.x
Workflows: 0
Active Workflows: 0
```

### 5.4 Deploying Test Workflows

To verify everything is working correctly, you can deploy the test workflows.  
You can use these later to test your webhook enabled notifications.    

#### Available Test Workflows

The management console can deploy sample workflows to verify:
- Webhook functionality
- n8n execution
- API connectivity

#### Verification Process

1. Go to **Flows** in the management console
2. Click **Deploy Test Workflow**
3. The system will:
   - Create a simple webhook workflow
   - Activate the workflow
   - Test the webhook endpoint
   - Verify the response
4. Check the results

```
Test Workflow Deployment
------------------------
Workflow Created: Yes
Workflow Activated: Yes
Webhook Test: Passed
Response Time: 45ms
Status: All tests passed
```

<!-- SCREENSHOT: Test workflow deployment results -->
*[Screenshot placeholder: Test workflow verification results]*

### 5.5 IP Access Control Configuration

The management console supports IP-based access control to restrict who can access the administrative interface.

#### Understanding Subnet Restrictions

By default, the management console is accessible from common internal IP ranges:
- `10.0.0.0/8` (Private Class A)
- `172.16.0.0/12` (Private Class B)
- `192.168.0.0/16` (Private Class C)
- `100.64.0.0/10` (Carrier-grade NAT / Tailscale)

#### Adding Allowed IP Ranges

1. Go to **Settings** > **Security**
2. In the **Allowed Subnets** section, click **Add**
3. Enter the CIDR notation for the allowed range
4. Add a description
5. Click **Save**

| Example | CIDR | Description |
|---------|------|-------------|
| Single IP | `203.0.113.50/32` | Your office IP |
| Small network | `203.0.113.0/24` | Office network |
| Tailscale | `100.64.0.0/10` | Tailscale network |

<!-- SCREENSHOT: IP access control settings -->
*[Screenshot placeholder: Settings > Security > Allowed Subnets]*

#### Tailscale Network Integration

If you enabled Tailscale during setup, your management console is automatically accessible via your Tailscale network:

1. Tailscale assigns IPs in the `100.64.0.0/10` range
2. This range is allowed by default
3. Access the console using the Tailscale IP or MagicDNS name

```bash
# Find your Tailscale IP
tailscale ip

# Access via Tailscale
https://your-machine.tailnet-name.ts.net/management
```

---

# Part IV: Management Console Reference

## 6. Dashboard

The dashboard provides an at-a-glance overview of your system's health and status.

<!-- SCREENSHOT: Full dashboard view -->
*[Screenshot placeholder: Complete dashboard with all widgets]*

### Dashboard Components

| Component            | Description                                                    |
|----------------------|----------------------------------------------------------------|
| **System Overview**  | Real-time CPU, memory, and disk usage with graphs, host uptime |
| **Container Status** | Health status of all Docker containers                         |
| **Network I/O**      | Current I/O of the n8n_management container nic                |
| **Download History** | One hour download network history                              |
| **Upload History**   | One hour upload network history                                |

### System Metrics

The metrics panel displays:
- **CPU Usage**: Current and historical CPU utilization
- **Memory Usage**: RAM usage with available/total
- **Disk Usage**: Storage utilization for each mount point
- **Uptime**: This is the uptime of the container host

### Container Status

Quick view of all containers:
- Green indicator: Running and healthy
- Yellow indicator: Running but unhealthy
- Red indicator: Stopped or exited
- Gray indicator: Unknown status

Click any container metric to navigate to the Containers page for details.

---

## 7. Backup Management

The backup system provides comprehensive data protection for your n8n instance.

### 7.1 Understanding the Backup System

#### Backup Architecture

```mermaid
flowchart LR
    subgraph Trigger["Backup Triggers"]
        Manual["Manual Trigger"]
        Schedule["Scheduled Job"]
    end

    subgraph Process["Backup Process"]
        PGDump["PostgreSQL Dump<br/>(pg_dump)"]
        Config["Configuration Files"]
        Certs["SSL Certificates"]
        Meta["Workflow Metadata<br/>Extraction"]
    end

    subgraph Storage["Storage"]
        Local["Local Storage<br/>/app/backups"]
        NFS["NFS Mount<br/>(optional)"]
    end

    subgraph Verify["Verification"]
        Archive["Archive Integrity"]
        DBValid["Database Validation"]
        Checksum["SHA-256 Checksums"]
    end

    Manual --> Process
    Schedule --> Process
    PGDump --> Storage
    Config --> Storage
    Certs --> Storage
    Meta --> Storage
    Storage --> Verify
```

#### What Gets Backed Up

| Component | Contents | Format |
|-----------|----------|--------|
| **PostgreSQL Database** | All n8n data (workflows, credentials, executions) | pg_dump custom format |
| **Configuration Files** | .env, docker-compose.yaml, nginx.conf | Original files |
| **SSL Certificates** | Let's Encrypt certificates | Certificate files |
| **Workflow Metadata** | Extracted workflow details for browsing | JSON manifest |

#### Storage Options

| Option | Location | Use Case |
|--------|----------|----------|
| **Local** | `/app/backups` (Docker volume) | Single-server deployments |
| **NFS** | Network mount point | Off-site backup storage |

### 7.2 Backup History

The Backup History page displays all backups with their status and details.

<!-- SCREENSHOT: Backup history list -->
*[Screenshot placeholder: Backup history table with multiple entries]*

#### Backup Status Indicators

| Status | Meaning |
|--------|---------|
| **Completed** | Backup finished successfully |
| **In Progress** | Backup currently running |
| **Failed** | Backup encountered an error |
| **Verified** | Backup passed verification |
| **Protected** | Backup protected from automatic deletion |

#### Viewing Backup Contents

Click any backup to view its contents without restoring:

1. **Workflows Tab**: List of all workflows in the backup
   - Workflow name and ID
   - Active/inactive status
   - Node count
   - Created/updated dates

2. **Credentials Tab**: Credential types (no sensitive data shown)
   - Credential name
   - Type (e.g., OAuth2, API Key)
   - Associated workflows

3. **Configuration Tab**: Configuration files included
   - File name and path
   - File size
   - Checksum

<!-- SCREENSHOT: Backup contents viewer -->
*[Screenshot placeholder: Backup contents dialog showing workflows]*

#### Protecting Backups

To prevent automatic deletion of important backups:

1. Click the backup row
2. Click **Protect**
3. The backup will be excluded from retention policies

Protected backups show a shield icon in the list.

### 7.3 Manual Backups

#### Triggering a Manual Backup

1. Navigate to **Backups**
2. Click **Create Backup**
3. Select backup options:
   - **Backup Type**: Full or n8n database only
   - **Compression**: gzip, zstd, or none
   - **Verify after backup**: Toggle to automatically verify backup integrity after completion
4. Click **Start Backup**

#### Verify After Backup

When **Verify after backup** is enabled:
1. The backup completes normally
2. Verification automatically starts
3. Archive integrity and database validation are performed
4. Results are shown in the progress modal

This is recommended for critical backups where you want immediate confirmation of backup validity.

<!-- SCREENSHOT: Manual backup dialog -->
*[Screenshot placeholder: Create backup dialog with options]*

#### Monitoring Backup Progress

A progress modal shows:
- Current step (e.g., "Dumping database")
- Progress percentage
- Elapsed time
- Log output

<!-- SCREENSHOT: Backup progress modal -->
*[Screenshot placeholder: Backup progress with percentage and logs]*

### 7.4 Scheduled Backups

#### Creating a Backup Schedule

1. Go to **Backups** and click **Configure**
2. Select the **Schedule** tab
3. Configure:
   - **Enable Scheduled Backups**: Toggle on
   - **Frequency**: Hourly, Daily, Weekly, or Monthly
   - **Time**: When to run (for daily/weekly/monthly)
   - **Day**: Which day (for weekly/monthly)
4. Click **Save Changes**

<!-- SCREENSHOT: Schedule configuration -->
*[Screenshot placeholder: Backup schedule creation form]*

#### Schedule Frequency Options

| Frequency | Description | Typical Use |
|-----------|-------------|-------------|
| **Hourly** | Every hour | High-change environments |
| **Daily** | Once per day at specified time | Standard production |
| **Weekly** | Once per week on specified day | Long-term archives |
| **Monthly** | Once per month on specified day | Compliance archives |

### 7.5 Backup Verification

Verification ensures backups are valid and can be restored.

#### How Verification Works

The verification process:

1. **Archive Integrity**: Tests that the backup archive is not corrupted
2. **Database Validation**: Runs `pg_restore --list` to validate the dump
3. **Checksum Verification**: Compares SHA-256 checksums
4. **Manifest Validation**: Verifies all expected files are present

#### Manual Verification

1. In Backup History, click a backup
2. Click **Verify**
3. Wait for verification to complete
4. Review the verification report

```
Verification Report
-------------------
Archive Integrity: Passed
Database Validation: Passed
Checksum Match: Passed
Files Verified: 15/15
Status: Backup is valid and restorable
```

<!-- SCREENSHOT: Verification results -->
*[Screenshot placeholder: Verification report dialog]*

#### Auto-Verification

Configure automatic verification to run after backups complete:

1. Go to **Backups** and click **Configure**
2. Select the **Verification** tab
3. Enable **Auto-Verification**
4. Choose verification frequency:
   - **Every backup** (frequency = 1): Verify every backup immediately
   - **Every 3rd, 5th, or 10th**: Verify periodically to balance thoroughness and performance
   - **Custom frequency**: Enter any number from 1-100

| Frequency | Use Case |
|-----------|----------|
| Every backup | Critical production environments requiring maximum assurance |
| Every 3rd | Balanced approach for most deployments |
| Every 5th-10th | High-volume backup schedules where verification overhead matters |

<!-- SCREENSHOT: Auto-verification settings -->
*[Screenshot placeholder: Verification tab with frequency options]*

### 7.6 Restoration

#### Workflow Restoration

Restore individual workflows from a backup:

1. In Backup History, click a backup
2. Click **View Contents**
3. Go to the **Workflows** tab
4. Select the workflows to restore
5. Click **Restore Selected**

<!-- SCREENSHOT: Workflow restore selection -->
*[Screenshot placeholder: Workflow selection for restore]*

#### Conflict Resolution

If a workflow already exists:

| Option | Behavior |
|--------|----------|
| **Rename** | Restore with "(restored)" suffix |
| **Skip** | Do not restore this workflow |
| **Overwrite** | Replace the existing workflow |

<!-- SCREENSHOT: Conflict resolution dialog -->
*[Screenshot placeholder: Restore conflict resolution options]*

#### Credential Handling

When restoring workflows:
- Credentials are restored if they do not exist
- Existing credentials are not overwritten
- Workflows are linked to matching credentials by name

#### Full System Restoration

For bare-metal recovery or disaster recovery:

1. Click **System Restore** on a backup
2. Review the warnings:
   - All current data will be replaced
   - n8n will be restarted
   - Users will be logged out
3. Confirm the restoration
4. Wait for the process to complete

```mermaid
flowchart TD
    Start[Start System Restore] --> Stop[Stop n8n Service]
    Stop --> Backup[Backup Current State]
    Backup --> Extract[Extract Backup Archive]
    Extract --> RestoreDB[Restore PostgreSQL]
    RestoreDB --> RestoreConfig[Restore Config Files]
    RestoreConfig --> RestoreCerts[Restore SSL Certs]
    RestoreCerts --> Restart[Restart All Services]
    Restart --> Verify[Verify Services]
    Verify --> Complete[Restoration Complete]
```

<!-- SCREENSHOT: System restore confirmation -->
*[Screenshot placeholder: System restore warning dialog]*

### 7.7 Backup Settings

#### Storage Configuration

Configure where backups are stored:

**Local Storage:**
- Default path: `/app/backups`
- Automatically created during setup
- Persists in Docker volume

**NFS Storage:**
- Server address (e.g., `nfs.example.com`)
- Export path (e.g., `/export/n8n_backups`)
- Mount options

<!-- SCREENSHOT: Storage settings -->
*[Screenshot placeholder: Backup storage configuration]*

#### Compression Options

| Option | Extension | Speed | Size |
|--------|-----------|-------|------|
| **gzip** | `.gz` | Medium | Medium |
| **zstd** | `.zst` | Fast | Small |
| **none** | (none) | Fastest | Largest |

#### Retention Policies (GFS Strategy)

The Grandfather-Father-Son retention strategy:

| Level | Retention | Purpose |
|-------|-----------|---------|
| **Daily** | Keep 7 days | Recent point-in-time recovery |
| **Weekly** | Keep 4 weeks | Weekly snapshots |
| **Monthly** | Keep 6 months | Long-term archives |
| **Minimum** | Keep 3 oldest | Disaster recovery baseline |

<!-- SCREENSHOT: Retention policy settings -->
*[Screenshot placeholder: GFS retention configuration]*

#### Pruning Settings

Automatic deletion of old backups:

**Time-Based Pruning:**
- Delete backups older than X days
- Respects retention policy

**Space-Based Pruning:**
- Trigger when free space below X%
- Delete oldest unprotected backups

**Size-Based Pruning:**
- Keep total backup size under X GB
- Delete oldest when exceeded

**Critical Space Handling:**
- Emergency threshold (default: 5% free)
- Options: Delete oldest immediately or stop backups and alert

<!-- SCREENSHOT: Pruning settings -->
*[Screenshot placeholder: Pruning configuration page]*

### 7.8 Backup Notifications

Configure notifications for backup events:

1. Go to **System Notifications**
2. Find backup-related events:
   - `backup_success` - Backup completed
   - `backup_failure` - Backup failed
   - `backup_started` - Backup began
   - `backup_pending_deletion` - Backup scheduled for deletion
   - `backup_critical_space` - Low disk space for backups
3. Configure targets (channels/groups)
4. Set escalation if needed

---

## 8. Notification System

The notification system provides multi-channel alerting for system events.

### 8.1 Notification Architecture

```mermaid
flowchart TB
    Event[System Event] --> Evaluate[Rule Evaluation]
    Evaluate --> Check{Channel<br/>Enabled?}
    Check -->|No| Skip[Skip]
    Check -->|Yes| Cooldown{Cooldown<br/>Active?}
    Cooldown -->|Yes| Skip
    Cooldown -->|No| Route[Route to Channel]

    Route --> Apprise[Apprise<br/>30+ Services]
    Route --> NTFY[NTFY<br/>Push Notifications]
    Route --> Email[Email<br/>SMTP]
    Route --> Webhook[Webhook<br/>HTTP POST]

    Apprise --> Discord[Discord]
    Apprise --> Slack[Slack]
    Apprise --> Telegram[Telegram]
    Apprise --> More[... 27+ more]
```

### 8.2 Notification Channels

#### Apprise Integration

Apprise supports 30+ notification services:

| Category | Services |
|----------|----------|
| **Chat** | Discord, Slack, Telegram, Microsoft Teams, Mattermost, Rocket.Chat |
| **Email** | SMTP, Gmail, SendGrid, Mailgun, AWS SES |
| **Push** | Pushover, Pushbullet, Join, Simplepush |
| **SMS** | Twilio, Nexmo, MessageBird |
| **Webhooks** | Custom HTTP endpoints, IFTTT, Zapier |
| **Other** | Home Assistant, Gotify, Matrix, XMPP |

#### NTFY Push Notifications

Native NTFY integration provides:
- Mobile push notifications (iOS/Android)
- Desktop notifications
- Email forwarding
- Action buttons
- Priority levels
- Scheduled delivery

**Understanding Topics vs Channel Slugs:**

| Concept | Purpose | Example |
|---------|---------|---------|
| **Topic** | What you subscribe to in the NTFY app to receive notifications | `backup_alerts` |
| **Channel Slug** | What you use in n8n webhook payloads to route messages | `channel:ntfy_backup_alerts` |

The topic is the NTFY subscription identifier, while the channel slug is how n8n's notification system routes messages to that topic.

**Bidirectional Sync:**
Topics created in the NTFY Push section automatically create corresponding notification channels, and vice versa. Use the **Sync Channels** button to ensure both sections are synchronized.

#### Email Notifications

Direct SMTP integration:
- Configurable SMTP server
- TLS/SSL support
- Custom templates
- HTML and plain text

#### Webhook Integration

Send HTTP POST requests to any endpoint:
- Custom payload format
- Header configuration
- Authentication support

### 8.3 Creating Notification Channels

#### Adding an Apprise Channel

1. Go to **Notifications** > **Channels**
2. Click **Add Channel**
3. Select **Apprise**
4. Enter the Apprise URL:
   ```
   discord://webhook_id/webhook_token
   slack://token_a/token_b/token_c
   tgram://bot_token/chat_id
   ```
5. Set priority and description
6. Click **Save**

<!-- SCREENSHOT: Add channel dialog -->
*[Screenshot placeholder: Apprise channel configuration]*

#### Apprise URL Examples

| Service | URL Format |
|---------|------------|
| Discord | `discord://webhook_id/webhook_token` |
| Slack | `slack://token_a/token_b/token_c/#channel` |
| Telegram | `tgram://bot_token/chat_id` |
| Email | `mailto://user:pass@smtp.example.com` |
| Pushover | `pover://user_key@api_token` |

#### Adding an NTFY Channel

1. Select **NTFY** as the type
2. Configure:
   - **Server URL**: NTFY server address
   - **Topic**: Topic name (spaces are automatically converted to underscores)
   - **Priority**: Default priority (1-5)
   - **Authentication**: Username/password if required
3. Click **Save**

**Local NTFY Server Detection:**
When adding an NTFY channel that points to your local NTFY server, the system automatically:
- Adds "NTFY: " prefix to the channel name
- Generates a slug in the format `ntfy_{topic_name}`
- Displays a "Local" badge and megaphone icon to distinguish it from external NTFY channels
- Syncs the topic to the NTFY Push section

**Success Dialog:**
After creating a local NTFY channel, a helpful dialog appears explaining:
- **Topic** (amber): What you subscribe to in your NTFY app (e.g., `my_alerts`)
- **Channel Slug** (blue): What you use in n8n webhook payloads (e.g., `channel:ntfy_my_alerts`)

> **Important:** Subscribe to the *topic* in your NTFY app to receive notifications. Use the *channel slug* in your n8n workflows to send notifications.

#### Testing Channels

After creating a channel:
1. Click the channel row
2. Click **Test**
3. A test notification is sent
4. Verify you received it

### 8.4 Notification Groups

Groups allow routing notifications to multiple channels at once.

#### Creating Groups

1. Go to **Notifications** > **Groups**
2. Click **Add Group**
3. Enter a name (e.g., "On-Call Team")
4. Select channels to include
5. Click **Save**

<!-- SCREENSHOT: Group creation -->
*[Screenshot placeholder: Notification group configuration]*

#### Use Cases for Groups

| Group | Channels | Purpose |
|-------|----------|---------|
| **Critical Alerts** | SMS + Pushover + Discord | Immediate attention required |
| **Daily Summary** | Email + Slack | Non-urgent notifications |
| **DevOps Team** | Discord + PagerDuty | Technical team alerts |

### 8.5 NTFY Configuration

#### NTFY Server Settings

Configure the NTFY integration:

1. Go to **Notifications** > **NTFY**
2. Click **Server Settings**
3. Configure:
   - **Server URL**: Your NTFY server (e.g., `https://ntfy.sh` or self-hosted)
   - **Default Topic**: Default topic for notifications
   - **Authentication**: Enable if server requires auth
   - **Username/Password**: If authentication enabled

<!-- SCREENSHOT: NTFY server settings -->
*[Screenshot placeholder: NTFY server configuration]*

#### Topic Management

Organize notifications with topics:

1. Go to **NTFY** > **Topics**
2. Click **New Topic**
3. Configure:
   - **Name**: Topic identifier (e.g., `n8n-alerts`)
   - **Description**: Optional description
   - **Access Level**: Read & Write, Read Only, or Write Only
   - **Default Priority**: Min (1) to Urgent (5)
   - **Default Tags**: Emoji tags (e.g., `warning`, `backup`)
   - **Require Authentication**: Enable if topic needs auth

**Topic Name Sanitization:**
Topic names are automatically sanitized to meet NTFY requirements:
- Spaces are converted to underscores (e.g., "my alerts" → "my_alerts")
- Invalid characters are removed (only alphanumeric, dashes, underscores allowed)
- Multiple consecutive underscores/dashes are collapsed

**Success Dialog:**
After creating a topic, a helpful dialog appears explaining:
- **Topic** (amber): The name to subscribe to in your NTFY app
- **Channel Slug** (blue): The slug to use in n8n webhook payloads (e.g., `channel:ntfy_my_alerts`)

**Sync Channels Button:**
Click **Sync Channels** to synchronize topics with the Notification Channels section. This creates corresponding notification channels that can be used in notification groups.

<!-- SCREENSHOT: Topic management -->
*[Screenshot placeholder: NTFY topics list]*

#### Message Composer

Send ad-hoc notifications:

1. Go to **NTFY** > **Compose**
2. Select a topic
3. Enter message details:
   - **Title**: Message title
   - **Message**: Body text (supports Markdown)
   - **Priority**: Urgency level
   - **Tags**: Emoji indicators
   - **Actions**: Clickable buttons (optional)
4. Click **Send**

<!-- SCREENSHOT: Message composer -->
*[Screenshot placeholder: NTFY message composition form]*

#### Template Builder

Create reusable message templates:

1. Go to **NTFY** > **Templates**
2. Click **Add Template**
3. Configure:
   - **Name**: Template identifier
   - **Title Template**: With Go template variables
   - **Body Template**: Message body with variables
   - **Default Priority**: Priority level
   - **Tags**: Default tags

**Available Template Variables:**

| Variable | Description |
|----------|-------------|
| `{{ .EventType }}` | Type of event (e.g., `backup_success`) |
| `{{ .Timestamp }}` | Event timestamp |
| `{{ .Severity }}` | Event severity level |
| `{{ .Message }}` | Event message |
| `{{ .Details }}` | Additional event details (JSON) |

**Example Template:**
```
Title: {{ .Severity | upper }}: {{ .EventType }}
Body: {{ .Message }}

Occurred at: {{ .Timestamp | formatTime }}
Details: {{ .Details | toJSON }}
```

<!-- SCREENSHOT: Template builder -->
*[Screenshot placeholder: NTFY template creation form]*

#### Saved Messages

Save frequently used messages:

1. Compose a message
2. Click **Save as Template**
3. Give it a name
4. Access later from **Saved Messages**

#### Message History

View sent NTFY messages:

1. Go to **NTFY** > **History**
2. View all sent messages with:
   - Timestamp
   - Topic
   - Title/message
   - Delivery status

### 8.6 Standalone NTFY Server Setup

If you enabled NTFY during setup, you have a self-hosted push notification server.

#### Accessing the NTFY Server

- **Web UI**: `https://your-domain.com/ntfy/`
- **API**: `https://your-domain.com/ntfy/`

#### Client Setup

**Mobile Apps:**
- iOS: Download "ntfy" from App Store
- Android: Download "ntfy" from Google Play or F-Droid

**Configuration:**
1. Open the ntfy app
2. Add your server: `https://your-domain.com/ntfy/`
3. Subscribe to your topics
4. Enable notifications

**Desktop:**
- Use the web UI at `https://your-domain.com/ntfy/`
- Or install the ntfy CLI tool

#### NTFY Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NTFY_BASE_URL` | (your domain) | Public URL for NTFY |
| `NTFY_ENABLE_LOGIN` | `true` | Require authentication |
| `NTFY_ENABLE_SIGNUP` | `false` | Allow user registration |
| `NTFY_AUTH_DEFAULT_ACCESS` | `read-write` | Default permission level |

### 8.7 n8n Webhook Integration

Send notifications from n8n workflows to the management console.

#### Webhook URL Format

```
POST https://your-domain.com/management/api/notifications/webhook
```

#### API Key Generation

1. Go to **Notifications** > **Channels**
2. Add a **Webhook** type channel
3. An API key is generated automatically
4. Copy the API key for use in n8n

#### n8n Workflow Example

Create an HTTP Request node in n8n:

```json
{
  "method": "POST",
  "url": "https://your-domain.com/management/api/notifications/webhook",
  "headers": {
    "X-API-Key": "your-api-key",
    "Content-Type": "application/json"
  },
  "body": {
    "title": "Workflow Completed",
    "message": "The data sync workflow finished successfully.",
    "priority": "normal",
    "channel": "default"
  }
}
```

---

## 9. System Notifications

> **📚 Detailed Guide Available**: For comprehensive documentation including proper setup order and technical configuration, see **[docs/NOTIFICATIONS.md](docs/NOTIFICATIONS.md)**.

System notifications automatically alert you to important events.

### 9.1 Event Types

Events are organized into five categories:

#### Backup Events (Category: backup)

| Event | Description | Default Severity |
|-------|-------------|------------------|
| `backup_success` | Backup completed successfully | Info |
| `backup_failure` | Backup failed | Critical |
| `backup_started` | Backup began | Info |
| `backup_pending_deletion` | Backup scheduled for retention deletion | Warning |
| `backup_critical_space` | Disk space critically low | Critical |

#### Container Events (Category: container)

| Event | Description | Default Severity |
|-------|-------------|------------------|
| `container_unhealthy` | Container health check failed | Critical |
| `container_restart` | Container restarted | Warning |
| `container_stopped` | Container stopped unexpectedly | Critical |
| `container_started` | Container started | Info |
| `container_removed` | Container was removed | Warning |
| `container_healthy` | Container recovered to healthy | Info |
| `container_high_cpu` | Container CPU above threshold | Warning |
| `container_high_memory` | Container memory above threshold | Warning |

#### Security Events (Category: security)

| Event | Description | Default Severity |
|-------|-------------|------------------|
| `security_event` | Security-related event (e.g., failed logins) | Critical |

#### SSL Certificate Events (Category: ssl)

| Event | Description | Default Severity |
|-------|-------------|------------------|
| `certificate_expiring` | SSL certificate expiring soon | Warning |

#### System Events (Category: system)

| Event | Description | Default Severity |
|-------|-------------|------------------|
| `disk_space_low` | Disk usage above threshold | Warning |
| `high_memory` | System memory above threshold | Warning |
| `high_cpu` | Sustained high CPU usage | Warning |
| `update_available` | Software update available | Info |

### 9.2 Event Configuration Options

Configure each event type individually:

<!-- SCREENSHOT: Event configuration -->
*[Screenshot placeholder: System notification event settings]*

| Setting | Description | Options |
|---------|-------------|---------|
| **Enabled** | Whether notifications are sent | On/Off |
| **Severity** | Priority level | Info, Warning, Critical |
| **Frequency** | How often to notify | Every time, Once per 15m/30m/1h/4h/12h/day/week |
| **Cooldown** | Minimum time between notifications | Minutes |
| **Thresholds** | Trigger conditions | Varies by event type |

#### Quick Setup: Apply to All Events

Each event category (Backup, Container, Security, SSL, System) includes a **Quick Setup** section for bulk target assignment:

1. Expand an event category (e.g., **Container Events**)
2. Click **Apply to All Events** in the Quick Setup section
3. In the modal, select:
   - **Target Type**: Channel or Group
   - **Target**: The specific channel or group
   - **Escalation Level**: L1 (Primary) or L2 (Escalation)
4. Click **Apply to All**

This adds the selected notification target to all events in that category at once. Events that already have the target configured are automatically skipped to avoid duplicates.

This feature simplifies initial setup when you want consistent notification routing for an entire category of events.

#### Threshold Configuration

Some events have configurable thresholds:

| Event | Threshold | Default |
|-------|-----------|---------|
| `disk_space_low` | Percent used | 90% |
| `high_memory` | Percent used | 90% |
| `high_cpu` | Percent + duration | 90% for 5 minutes |
| `certificate_expiring` | Days before expiration | 14 days |

### 9.3 Escalation

L1/L2 escalation ensures critical events are not missed.

#### How Escalation Works

1. **L1 (Primary)**: First notification sent immediately
2. **Wait Period**: Configurable timeout (default: 30 minutes)
3. **L2 (Escalation)**: If not acknowledged, escalate to L2 targets

#### Configuring Escalation

1. Go to **System Notifications**
2. Select an event
3. Enable **Escalation**
4. Set **Escalation Timeout** (minutes)
5. Add **L2 Targets** (different channels/groups than L1)

<!-- SCREENSHOT: Escalation configuration -->
*[Screenshot placeholder: L1/L2 escalation settings]*

### 9.4 Global Settings

System-wide notification controls are located at the top of the **System Notifications** page in the status bar and in the collapsible settings cards below the event categories.

The page includes:
- **Status Bar** (top): Quick access to Maintenance Mode and Quiet Hours toggles, plus Events Enabled and Rate Limit counters
- **Event Categories**: All event types organized by category
- **Rate Limiting**: Collapsible card below the event categories
- **Daily Digest**: Collapsible card below the event categories

<!-- SCREENSHOT: Global notification settings -->
*[Screenshot placeholder: System Notifications page]*

#### Maintenance Mode

Temporarily silence all notifications:

1. Go to **Settings** > **System Notifications**
2. Click the **Maintenance** button in the status bar
3. Optionally set an end time
4. Add a reason note

While in maintenance mode:
- No notifications are sent
- Events are still logged
- Manual notifications still work

#### Quiet Hours

Reduce notification priority during specified hours:

| Setting | Description |
|---------|-------------|
| **Enabled** | Turn quiet hours on/off |
| **Start Time** | When quiet hours begin (e.g., 22:00) |
| **End Time** | When quiet hours end (e.g., 07:00) |
| **Action** | Reduce priority or mute completely |

#### Daily Digest

Aggregate low-priority notifications:

1. Enable **Daily Digest**
2. Set digest time (e.g., 08:00)
3. Select which severity levels to include
4. Receive a summary email daily

#### Rate Limiting

Prevent notification storms:

| Setting | Description | Default |
|---------|-------------|---------|
| **Max per Hour** | Maximum notifications per hour | 50 |
| **Emergency Contact** | Override channel for rate limit warnings | None |

### 9.5 Per-Container Configuration

Container-specific notification settings are managed directly from the **Containers** view:

1. Go to **Containers** (main menu)
2. Click on the container you want to configure
3. Go to the **Alerts** tab
4. Configure:
   - **Enable Notifications**: Master on/off for this container
   - **Monitor Stopped**: Stop events
   - **Monitor Unhealthy**: Health check failures
   - **Monitor Restart**: Restart events
   - **CPU Threshold**: Custom CPU limit (%) with slider
   - **Memory Threshold**: Custom memory limit (%) with slider

#### Prerequisite Enforcement

The notification system enforces a proper setup order to prevent misconfiguration:

1. **Global events must be enabled first** - Before per-container alerts will work, you must enable the corresponding container event types in **Settings** > **System Notifications** > **Container Events**.

2. **Individual toggles reflect global state** - Each per-container toggle (Stopped, Unhealthy, High CPU, etc.) is disabled if the corresponding global event is not enabled. A message indicates which events need to be enabled globally.

3. **Warning when disabling global events** - If you try to disable a global container event that has per-container configurations, a confirmation dialog shows which containers will be affected.

> **Important**: Even with per-container settings configured, notifications won't be sent unless you have notification targets configured in the global Container Events settings.

<!-- SCREENSHOT: Per-container configuration -->
*[Screenshot placeholder: Container Alerts tab]*

### 9.6 Flapping Detection

Prevents notification spam when services rapidly toggle states.

#### How Flapping Detection Works

1. System tracks event frequency per target
2. If events exceed threshold within time window, "flapping" is detected
3. During flapping:
   - Individual notifications are suppressed
   - Summary notifications are sent at intervals
4. When stable, a recovery notification is sent

#### Flapping Settings

| Setting | Description | Default |
|---------|-------------|---------|
| **Enabled** | Turn flapping detection on/off | Yes |
| **Threshold Count** | Events to trigger flapping | 3 |
| **Threshold Minutes** | Time window for counting | 10 |
| **Summary Interval** | Minutes between summaries | 15 |
| **Notify on Recovery** | Send notification when stable | Yes |

---

## 10. Container Management

Monitor and control Docker containers.

<!-- SCREENSHOT: Container list -->
*[Screenshot placeholder: Container management overview]*

### Container List

Containers are displayed in a collapsible card format:

**Collapsed View (default)**:
- Status icon and color indicator
- Container name and image
- Status badge (Running/Stopped/etc.)
- Health badge (Healthy/Unhealthy)
- Remove button (for stopped containers)

**Expanded View** (click to expand):
- Recreate button (for N8N project containers)
- Stats grid: Uptime, CPU, Memory, Network
- Memory usage progress bar
- Action buttons

### Container Operations

| Action | Description |
|--------|-------------|
| **Start** | Start a stopped container |
| **Stop** | Gracefully stop a running container |
| **Restart** | Stop and start a running container |
| **Recreate** | Remove and recreate container (with optional image pull) |
| **Alerts** | Configure container-specific notifications |
| **Logs** | Display container log output with filtering |
| **Terminal** | Open interactive terminal session |
| **Remove** | Delete a stopped container |

> **Note**: Restart, Alerts, Logs, and Terminal buttons are only available for running containers. Stopped containers show only Start and Remove options.

### Viewing Container Logs

1. Click a container to expand it
2. Click **Logs** to open the log viewer

**Log Viewer Controls**:
- **Lines**: Select number of lines (50, 100, 200, 500, 1000, or All)
- **Since**: Filter logs by time (e.g., "1h", "30m", "2024-01-01")
- **Follow**: Enable real-time log streaming (auto-refreshes every 2 seconds)
- **Refresh**: Manually refresh logs
- **Search**: Filter displayed logs by keyword

The search feature filters logs client-side and shows a match count. Use the "Since" field to reduce server load when viewing large log files.

<!-- SCREENSHOT: Container logs viewer -->
*[Screenshot placeholder: Enhanced container log viewer with controls]*

### Resource Monitoring

Expand a container to view current metrics:
- **Uptime**: Time since container started
- **CPU**: Current CPU usage percentage
- **Memory**: Current memory usage in MB
- **Network**: Network I/O (download bytes)
- **Memory Bar**: Visual progress bar showing memory percentage

---

## 11. Workflow Management

Monitor and manage n8n workflows.

<!-- SCREENSHOT: Workflow list -->
*[Screenshot placeholder: Workflow management page]*

### Workflow List

View all workflows with:
- **Name**: Workflow name
- **ID**: Unique identifier
- **Active**: Enabled/disabled status
- **Nodes**: Number of nodes
- **Created**: Creation date
- **Updated**: Last modification date

### Filtering and Searching

- **Search**: Filter by workflow name
- **Status Filter**: Show all, active only, or inactive only
- **Sort**: By name, date, or status

### Workflow Operations

| Action | Description |
|--------|-------------|
| **Activate** | Enable workflow execution |
| **Deactivate** | Disable workflow execution |
| **View Executions** | See recent execution history |
| **Open in n8n** | Open workflow in n8n editor |

### Execution History

View recent executions for each workflow:
- Execution ID
- Status (success, error, waiting)
- Start time
- Duration
- Error message (if failed)

<!-- SCREENSHOT: Execution history -->
*[Screenshot placeholder: Workflow execution history]*

---

## 12. System Monitoring

Monitor system health and resources.

<!-- SCREENSHOT: System monitoring dashboard -->
*[Screenshot placeholder: System health overview]*

### Health Dashboard

Quick status of all services:
- n8n: API health check
- PostgreSQL: Database connectivity
- Nginx: Configuration validation
- Certbot: Certificate status
- Management: Console health

### Resource Graphs

Real-time visualization of:
- **CPU Usage**: Usage percentage over time
- **Memory Usage**: Used/available over time
- **Load Average**: 1/5/15 minute averages
- **Disk I/O**: Read/write operations

### Disk Usage

Storage information for all mount points:
- Mount point
- Total size
- Used space
- Free space
- Usage percentage
- Warning indicators for low space

### SSL Certificate Status

View certificate information:
- Domain name
- Expiration date
- Days until expiration
- Issuer (Let's Encrypt)
- Last renewal date

<!-- SCREENSHOT: Certificate status -->
*[Screenshot placeholder: SSL certificate information]*

### Docker Information

System Docker details:
- Docker version
- Number of containers (running/total)
- Number of images
- Total volume size
- Network information

---

## 13. Settings

Configure the management console.

### Appearance Settings

| Setting | Options |
|---------|---------|
| **Theme** | Light, Dark, System |
| **Layout** | Sidebar, Horizontal |

### Security Settings

#### Password Management

Change your admin password:
1. Enter current password
2. Enter new password (minimum 8 characters)
3. Confirm new password
4. Click **Change Password**

#### IP Access Control

See [Section 5.5](#55-ip-access-control-configuration) for details.

### n8n API Configuration

Configure the connection to n8n:
- **API Key**: Your n8n API key
- **Base URL**: n8n editor URL (auto-detected)
- **Test Connection**: Verify connectivity

### Email Configuration

Configure SMTP for email notifications:

| Setting | Description |
|---------|-------------|
| **SMTP Server** | Mail server hostname |
| **Port** | SMTP port (25, 465, 587) |
| **Security** | None, TLS, STARTTLS |
| **Username** | SMTP authentication username |
| **Password** | SMTP authentication password |
| **From Address** | Sender email address |
| **From Name** | Sender display name |

#### Email Templates

Customize notification emails:
1. Go to **Settings** > **Email** > **Templates**
2. Select a template
3. Edit the HTML/text content
4. Use variables for dynamic content
5. Preview and save

### Debug Mode

Enable verbose logging:
1. Toggle **Debug Mode** on
2. Log level increases to DEBUG
3. More detailed information in logs
4. Disable for production use

### About

View version information:
- Management Console version
- API version
- Frontend version
- Build date
- System information

---

# Part V: Operations and Maintenance

## 14. Daily Operations

### Recommended Daily Checks

1. **Dashboard Review**: Check the management console dashboard for any alerts
2. **Backup Status**: Verify the most recent backup completed successfully
3. **Container Health**: Ensure all containers show healthy status
4. **Disk Space**: Monitor disk usage, especially on backup storage

### Monitoring Best Practices

| Check | Frequency | Action if Failed |
|-------|-----------|------------------|
| Container health | Continuous (automated) | Investigate logs, restart if needed |
| Backup completion | Daily | Check backup logs, run manual backup |
| Disk space | Daily | Clean old backups, expand storage |
| Certificate expiration | Weekly | Verify certbot is running |

### Log Review

Review logs regularly for issues:

```bash
# View all container logs
docker compose logs --tail=100

# View specific container logs
docker logs n8n --tail=100
docker logs n8n_management --tail=100

# Follow logs in real-time
docker compose logs -f
```

### Health Checks

The system performs automatic health checks:
- **PostgreSQL**: Connection test every 5 seconds
- **n8n**: HTTP health endpoint check
- **Nginx**: Configuration validation on restart
- **Management**: API health endpoint

---

## 15. SSL Certificate Management

### Automatic Renewal

Certificates are automatically renewed by Certbot:
- Renewal check runs every 12 hours
- Certificates renew when less than 30 days remain
- Nginx is automatically reloaded after renewal

### Manual Renewal

Force certificate renewal:

```bash
# Dry run (test renewal)
docker exec n8n_certbot certbot renew --dry-run

# Force renewal
docker exec n8n_certbot certbot renew --force-renewal

# Reload nginx after renewal
docker exec n8n_nginx nginx -s reload
```

### Certificate Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Renewal fails | DNS API credentials expired | Update credentials in DNS provider file |
| Certificate not loading | Nginx not reloaded | Restart nginx container |
| Certificate expired | Certbot not running | Check certbot container logs |

### Viewing Certificate Status

```bash
# View certificate details
docker exec n8n_certbot certbot certificates

# Check certificate expiration
openssl s_client -connect your-domain.com:443 -servername your-domain.com 2>/dev/null | openssl x509 -noout -dates
```

---

## 16. Database Management

### PostgreSQL Overview

The system uses PostgreSQL 16 with pgvector extension for:
- n8n workflow data
- Execution history
- Credential storage
- Management console data
- Vector embeddings for AI workflows

### Database Commands

```bash
# Connect to database
docker exec -it n8n_postgres psql -U n8n -d n8n

# List databases
docker exec n8n_postgres psql -U n8n -c "\l"

# List tables in n8n database
docker exec n8n_postgres psql -U n8n -d n8n -c "\dt"

# Check database size
docker exec n8n_postgres psql -U n8n -c "SELECT pg_database.datname, pg_size_pretty(pg_database_size(pg_database.datname)) FROM pg_database;"
```

### Using Adminer

If Adminer is enabled, access it at `https://your-domain.com/adminer/`

1. Select **PostgreSQL** as system
2. Server: `postgres`
3. Username: `n8n` (or your configured user)
4. Password: (from .env file)
5. Database: `n8n` or `n8n_management`

### pgvector for AI/RAG Workflows

The pgvector extension enables:
- Vector similarity search
- Embedding storage
- AI/ML integration with n8n

Example usage in n8n SQL queries:
```sql
-- Create embeddings table
CREATE TABLE embeddings (
  id SERIAL PRIMARY KEY,
  content TEXT,
  embedding vector(1536)
);

-- Similarity search
SELECT content FROM embeddings
ORDER BY embedding <-> '[0.1, 0.2, ...]'
LIMIT 5;
```

---

## 17. Container Maintenance

### Updating Containers

Update to latest images:

```bash
# Pull latest images
docker compose pull

# Restart with new images
docker compose up -d

# Remove old images
docker image prune -f
```

### Viewing Logs with Dozzle

If Dozzle is enabled, access it at `https://your-domain.com/logs/`

Features:
- Real-time log streaming
- Multi-container view
- Log search and filtering
- Download logs

### Managing with Portainer

If Portainer is enabled, access it at `https://your-domain.com:9000`

Features:
- Visual container management
- Resource monitoring
- Container terminal access
- Image management
- Volume management

### Container Resource Limits

Default resource limits can be adjusted in `docker-compose.yaml`:

```yaml
services:
  n8n:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '0.5'
          memory: 512M
```

---

## 18. Backup Best Practices

### Recommended Backup Strategy

| Backup Type | Frequency | Retention | Purpose |
|-------------|-----------|-----------|---------|
| Full database | Daily | 7 days | Point-in-time recovery |
| Weekly archive | Weekly | 4 weeks | Weekly snapshots |
| Monthly archive | Monthly | 12 months | Long-term retention |

### Off-Site Backup with NFS

For disaster recovery, store backups on a separate NFS server:

1. Configure NFS server address in settings
2. Set NFS export path
3. Enable NFS backup storage
4. Backups are written to both local and NFS

### Backup Verification Schedule

| Verification | Frequency | Purpose |
|--------------|-----------|---------|
| Archive integrity | Each backup | Ensure backup is not corrupted |
| Database validation | Weekly | Verify database dump is valid |
| Full restore test | Monthly | Confirm complete recovery works |

### Disaster Recovery Planning

1. **Document recovery procedures**
2. **Test restores regularly**
3. **Store encryption keys securely** (separate from backups)
4. **Maintain off-site backup copies**
5. **Keep configuration files backed up**

### Recovery Time Objectives

| Scenario | Recovery Method | Estimated Time |
|----------|-----------------|----------------|
| Single workflow loss | Workflow restore | 5 minutes |
| Database corruption | Database restore | 15-30 minutes |
| Full system loss | Bare-metal recovery | 1-2 hours |

---

# Part VI: Advanced Configuration

## 19. Tailscale Integration

> **📚 Detailed Guide Available**: For comprehensive documentation including account creation, auth key generation, and detailed explanation of subnet routing, see **[docs/TAILSCALE.md](docs/TAILSCALE.md)**.

### Setting Up Tailscale

If you enabled Tailscale during setup, the container is already configured with:
- **TS_ROUTES**: Advertises your Docker host IP to the Tailscale network
- **TS_SERVE**: Exposes your n8n instance via Tailscale's HTTPS proxy
- **TS_AUTH_ONCE**: Prevents re-authentication on container restarts

For manual setup:

1. Generate an auth key at [Tailscale Admin Console](https://login.tailscale.com/admin/settings/keys)
2. Add to `.env`:
   ```
   TAILSCALE_AUTH_KEY=tskey-auth-xxx
   TAILSCALE_HOST_IP=192.168.1.10  # Your Docker host's local IP
   ```
3. Restart the stack:
   ```bash
   docker compose up -d
   ```

### Approving Advertised Routes (Required)

**IMPORTANT**: After the Tailscale container starts, you must approve the advertised routes in the Tailscale Admin Console:

1. Visit [Tailscale Admin - Machines](https://login.tailscale.com/admin/machines)
2. Find your **n8n-tailscale** node in the list
3. Click on the node to open its settings
4. Look for the **Subnets** section showing the advertised route (e.g., `192.168.1.10/32`)
5. Click **Approve** to enable the route
6. If prompted about **Serve**, enable it to allow HTTPS proxying

Without approving the routes, you won't be able to access your Docker host via the Tailscale network.

### Tailscale Serve (Automatic)

Tailscale Serve is configured via `TS_SERVE_CONFIG` using the `tailscale-serve.json` file. This proxies HTTPS traffic from your Tailscale Magic DNS name to your n8n domain.

**If using setup.sh**: The file is generated automatically with your domain.

**If configuring manually**: Edit `tailscale-serve.json` and replace `your-domain.com` with your actual domain:
```json
{
  "TCP": { "443": { "HTTPS": true } },
  "Web": {
    "${TS_CERT_DOMAIN}:443": {
      "Handlers": {
        "/": { "Proxy": "https://your-actual-domain.com:443" }
      }
    }
  }
}
```

The `${TS_CERT_DOMAIN}` placeholder is automatically replaced by Tailscale with your node's FQDN.

To verify serve is enabled:
```bash
docker exec n8n_tailscale tailscale serve status
```

### Accessing Services via Tailscale

Once routes are approved, you can access your services from any device on your Tailscale network:

#### Using Magic DNS (n8n via Tailscale Serve)
```
https://n8n-tailscale.your-tailnet.ts.net
```
This uses Tailscale's HTTPS proxy to securely access n8n.

#### Using the Advertised Route (Docker Host Access)
The advertised route gives you direct access to your Docker host IP via Tailscale:

| Service | URL |
|---------|-----|
| **n8n** | `https://192.168.1.10` |
| **Management Console** | `https://192.168.1.10/management/` |
| **SSH to Docker Host** | `ssh user@192.168.1.10` |

Replace `192.168.1.10` with your actual `TAILSCALE_HOST_IP` value.

### Restricting Access to Tailscale IPs

To restrict management console access to Tailscale only:

1. Go to **Settings** > **Security**
2. Remove public IP ranges
3. Keep only `100.64.0.0/10` (Tailscale range)
4. Access via Tailscale IP only

### Finding Your Tailscale IP

To find the container's Tailscale IP:
```bash
docker exec n8n_tailscale tailscale ip
```

### Troubleshooting Tailscale

If routes aren't working:
1. Check the container logs: `docker logs n8n_tailscale`
2. Verify the route is advertised: `docker exec n8n_tailscale tailscale status`
3. Ensure routes are approved in the admin console
4. Check that `TAILSCALE_HOST_IP` in `.env` matches your Docker host's actual IP

---

## 20. Cloudflare Tunnel

> **📚 Detailed Guide Available**: For comprehensive documentation including account creation, Zero Trust setup, and tunnel configuration, see **[docs/CLOUDFLARE.md](docs/CLOUDFLARE.md)**.

### Tunnel Configuration

Cloudflare Tunnel provides secure access without exposing ports.

1. Create a tunnel in [Cloudflare Zero Trust](https://one.dash.cloudflare.com/)
2. Copy the tunnel token
3. Add to `.env`:
   ```
   CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoixxxx
   ```
4. Restart the stack

### DNS Setup

Configure your Cloudflare DNS:

1. In Cloudflare dashboard, go to DNS
2. The tunnel automatically creates CNAME records
3. Verify records point to your tunnel

### Zero Trust Access

Add access policies:

1. Go to **Access** > **Applications**
2. Create an application for n8n
3. Add access policies (email, IP, etc.)
4. Users must authenticate before accessing

---

## 21. NFS Backup Storage

### NFS Server Requirements

The NFS server must:
- Export a directory with read/write access
- Allow connections from your n8n server
- Have sufficient storage space

### Example NFS Server Configuration

On the NFS server (`/etc/exports`):
```
/export/n8n_backups  192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
```

Apply changes:
```bash
exportfs -ra
```

### Configuration

In the management console:

1. Go to **Backups** and click **Configure**
2. Select the **Storage** tab
3. Enable NFS storage
4. Enter:
   - **Server**: `nfs.example.com`
   - **Path**: `/export/n8n_backups`
5. Test the connection
6. Click **Save Changes**

### Troubleshooting NFS

| Issue | Cause | Solution |
|-------|-------|----------|
| Mount fails | Firewall blocking | Open NFS ports (2049, 111) |
| Permission denied | Export permissions | Check `/etc/exports` configuration |
| Slow performance | Network issues | Check network connectivity |

Check NFS status:
```bash
docker exec n8n_management cat /app/config/nfs_status.json
```

---

## 22. Custom Nginx Configuration

### Configuration File Location

The nginx configuration is at `./nginx.conf` in your project directory.

### Adding Custom Headers

Add security headers in the `server` block:

```nginx
add_header X-Content-Type-Options nosniff;
add_header X-Frame-Options SAMEORIGIN;
add_header X-XSS-Protection "1; mode=block";
add_header Referrer-Policy strict-origin-when-cross-origin;
add_header Content-Security-Policy "default-src 'self'";
```

### Rate Limiting

Add rate limiting to prevent abuse:

```nginx
# In http block
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

# In location block
location /webhook/ {
    limit_req zone=api burst=20 nodelay;
    # ... rest of config
}
```

### Applying Changes

After modifying nginx.conf:

```bash
# Test configuration
docker exec n8n_nginx nginx -t

# Reload nginx
docker exec n8n_nginx nginx -s reload
```

---

## 23. Environment Variables Reference

### Core Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DOMAIN` | Your domain name | Required |
| `MGMT_PORT` | Management console port | `3333` |
| `TIMEZONE` | System timezone | Auto-detected |

### Database Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_USER` | PostgreSQL username | `n8n` |
| `POSTGRES_PASSWORD` | PostgreSQL password | Auto-generated |
| `POSTGRES_DB` | Database name | `n8n` |

### Security Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `N8N_ENCRYPTION_KEY` | n8n credential encryption | Auto-generated |
| `MGMT_SECRET_KEY` | Session signing key | Auto-generated |
| `MGMT_ENCRYPTION_KEY` | Settings encryption key | Auto-generated |

### Admin Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ADMIN_USER` | Admin username | `admin` |
| `ADMIN_PASS` | Admin password | Set during setup |
| `ADMIN_EMAIL` | Admin email | Set during setup |

### Optional Service Variables

| Variable | Description |
|----------|-------------|
| `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare tunnel authentication |
| `TAILSCALE_AUTH_KEY` | Tailscale pre-auth key |
| `NFS_SERVER` | NFS server address |
| `NFS_PATH` | NFS export path |

### n8n Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `N8N_HOST` | n8n hostname | Your domain |
| `N8N_PROTOCOL` | Protocol | `https` |
| `N8N_PORT` | Internal port | `5678` |
| `WEBHOOK_URL` | Webhook base URL | `https://domain/webhook/` |

---

# Part VII: Troubleshooting

## 24. Common Issues and Solutions

### Installation Issues

#### Docker Not Starting

**Symptoms**: Docker commands fail, daemon not running

**Solutions**:
```bash
# Check Docker status
sudo systemctl status docker

# Start Docker
sudo systemctl start docker

# Enable Docker on boot
sudo systemctl enable docker
```

#### AppArmor Blocking Docker (Proxmox LXC)

**Symptoms**: Container creation fails, permission denied errors

**Solution**:
1. On Proxmox host, edit container config
2. Add:
   ```
   lxc.apparmor.profile: unconfined
   features: nesting=1
   ```
3. Restart the container

#### DNS Validation Failures

**Symptoms**: Certificate acquisition fails, DNS challenge fails

**Solutions**:
1. Verify domain resolves correctly: `dig +short your-domain.com`
2. Check DNS provider credentials
3. Wait for DNS propagation (up to 5 minutes)
4. Verify API token permissions

#### Certificate Acquisition Failures

**Symptoms**: Certbot fails, SSL errors

**Solutions**:
1. Check certbot logs: `docker logs n8n_certbot`
2. Verify DNS credentials file permissions: `chmod 600 cloudflare.ini`
3. Test DNS challenge manually
4. Check rate limits (Let's Encrypt has limits)

### Runtime Issues

#### Container Will Not Start

**Diagnosis**:
```bash
# Check container status
docker compose ps

# View container logs
docker logs [container_name]

# Check for port conflicts
sudo netstat -tlnp | grep 443
```

**Common causes**:
- Port already in use
- Missing environment variables
- Volume permission issues

#### Database Connection Errors

**Symptoms**: n8n cannot connect, management console errors

**Solutions**:
```bash
# Check PostgreSQL status
docker exec n8n_postgres pg_isready

# View PostgreSQL logs
docker logs n8n_postgres

# Test connection
docker exec n8n_postgres psql -U n8n -c "SELECT 1"
```

#### SSL Certificate Errors

**Symptoms**: Browser shows certificate warning, HTTPS fails

**Solutions**:
1. Check certificate exists:
   ```bash
   docker exec n8n_nginx ls -la /etc/letsencrypt/live/
   ```
2. Verify nginx configuration:
   ```bash
   docker exec n8n_nginx nginx -t
   ```
3. Reload nginx:
   ```bash
   docker exec n8n_nginx nginx -s reload
   ```

#### Webhook Not Accessible

**Symptoms**: External webhooks fail, timeout errors

**Checklist**:
1. Port 443 open in firewall
2. Domain DNS correct
3. n8n container running
4. Webhook URL format correct: `https://domain/webhook/[path]`

### Management Console Issues

#### Cannot Login

**Symptoms**: Login fails, credentials rejected

**Solutions**:
1. Verify credentials (case-sensitive)
2. Check IP is in allowed subnets
3. View management logs: `docker logs n8n_management`
4. Reset admin password (requires database access)

#### API Key Not Working

**Symptoms**: n8n connection fails, workflows not loading

**Solutions**:
1. Regenerate API key in n8n
2. Update key in management console
3. Test connection in settings

#### Backups Failing

**Symptoms**: Backup shows failed status

**Diagnosis**:
```bash
# Check backup logs
docker logs n8n_management | grep -i backup

# Check disk space
df -h

# Check NFS connection (if used)
docker exec n8n_management cat /app/config/nfs_status.json
```

### Performance Issues

**Symptoms**: Slow response, high resource usage

**Solutions**:
1. Check resource usage: `docker stats`
2. Increase container limits in docker-compose.yaml
3. Review n8n execution history settings
4. Optimize PostgreSQL (increase shared_buffers)

---

## 25. Logs and Diagnostics

### Log Locations

| Component | Command |
|-----------|---------|
| All containers | `docker compose logs` |
| n8n | `docker logs n8n` |
| PostgreSQL | `docker logs n8n_postgres` |
| Nginx | `docker logs n8n_nginx` |
| Certbot | `docker logs n8n_certbot` |
| Management | `docker logs n8n_management` |

### Reading Docker Logs

```bash
# Last 100 lines
docker logs n8n --tail 100

# Follow logs in real-time
docker logs n8n -f

# Logs since specific time
docker logs n8n --since 2024-01-01T00:00:00

# Logs with timestamps
docker logs n8n -t
```

### Debug Mode

Enable debug logging in management console:

1. Go to **Settings**
2. Enable **Debug Mode**
3. Log level increases to DEBUG
4. View detailed logs: `docker logs n8n_management`

Remember to disable debug mode in production.

### Health Check Commands

```bash
# Overall system health
docker compose ps

# PostgreSQL health
docker exec n8n_postgres pg_isready

# n8n health
curl -k https://localhost/healthz

# Nginx configuration
docker exec n8n_nginx nginx -t

# Certificate status
docker exec n8n_certbot certbot certificates
```

---

# Part VIII: Reference

## 26. Command Reference

### Docker Compose Commands

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart all services
docker compose restart

# Restart specific service
docker compose restart n8n

# View status
docker compose ps

# View logs
docker compose logs -f

# Pull latest images
docker compose pull

# Rebuild containers
docker compose up -d --build
```

### Database Commands

```bash
# Connect to PostgreSQL
docker exec -it n8n_postgres psql -U n8n -d n8n

# Backup database
docker exec n8n_postgres pg_dump -U n8n -d n8n -Fc > backup.dump

# Restore database
docker exec -i n8n_postgres pg_restore -U n8n -d n8n < backup.dump

# List tables
docker exec n8n_postgres psql -U n8n -d n8n -c "\dt"
```

### Certificate Commands

```bash
# View certificates
docker exec n8n_certbot certbot certificates

# Test renewal
docker exec n8n_certbot certbot renew --dry-run

# Force renewal
docker exec n8n_certbot certbot renew --force-renewal

# Reload nginx
docker exec n8n_nginx nginx -s reload
```

### Backup Commands

```bash
# View backup status
docker exec n8n_management ls -la /app/backups

# Check NFS mount
docker exec n8n_management df -h | grep nfs
```

---

## 27. File Locations

| File | Purpose |
|------|---------|
| `docker-compose.yaml` | Container definitions |
| `.env` | Environment variables |
| `nginx.conf` | Nginx configuration |
| `cloudflare.ini` | Cloudflare credentials |
| `.n8n_setup_config` | Setup configuration backup |

### Docker Volumes

| Volume | Contents |
|--------|----------|
| `n8n_data` | n8n workflow data |
| `postgres_data` | PostgreSQL database |
| `letsencrypt` | SSL certificates |
| `mgmt_backup_staging` | Backup staging area |
| `mgmt_logs` | Management console logs |
| `mgmt_config` | Management configuration |

---

## 28. Glossary

| Term | Definition |
|------|------------|
| **Apprise** | Multi-service notification library |
| **Certbot** | Let's Encrypt certificate automation tool |
| **DNS-01 Challenge** | Domain validation via DNS TXT record |
| **GFS** | Grandfather-Father-Son backup rotation strategy |
| **Let's Encrypt** | Free SSL/TLS certificate authority |
| **n8n** | Workflow automation platform |
| **NFS** | Network File System for remote storage |
| **NTFY** | Push notification service |
| **pgvector** | PostgreSQL extension for vector operations |
| **Tailscale** | VPN service using WireGuard |
| **Webhook** | HTTP callback for event notifications |

---

# Appendices

## Appendix A: DNS Provider Credential Setup

### Cloudflare API Token

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Click your profile icon (top right)
3. Select **My Profile**
4. Go to **API Tokens** tab
5. Click **Create Token**
6. Use the **Edit zone DNS** template
7. Under **Permissions**, ensure:
   - Zone - DNS - Edit
8. Under **Zone Resources**:
   - Include - Specific zone - (select your zone)
9. Click **Continue to summary**
10. Click **Create Token**
11. Copy the token immediately (shown only once)

<!-- SCREENSHOT: Cloudflare token creation -->
*[Screenshot placeholder: Cloudflare API token creation steps]*

### AWS Route 53

1. Log in to [AWS Console](https://console.aws.amazon.com)
2. Go to **IAM** > **Users**
3. Create a new user or select existing
4. Attach the following policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "route53:ListHostedZones",
                "route53:GetChange"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": "route53:ChangeResourceRecordSets",
            "Resource": "arn:aws:route53:::hostedzone/YOUR_ZONE_ID"
        }
    ]
}
```

5. Create access keys for the user
6. Save the Access Key ID and Secret Access Key

### Google Cloud DNS

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to **IAM & Admin** > **Service Accounts**
3. Click **Create Service Account**
4. Enter a name and description
5. Grant the **DNS Administrator** role
6. Click **Create Key** > **JSON**
7. Save the JSON file securely

### DigitalOcean

1. Log in to [DigitalOcean](https://cloud.digitalocean.com)
2. Go to **API** > **Tokens/Keys**
3. Click **Generate New Token**
4. Enter a name
5. Select **Read** and **Write** scopes
6. Click **Generate Token**
7. Copy the token immediately (shown only once)

---

## Appendix B: Tailscale Auth Key Generation

1. Log in to [Tailscale Admin Console](https://login.tailscale.com/admin)
2. Go to **Settings** > **Keys**
3. Click **Generate auth key**
4. Configure:
   - **Reusable**: Yes (recommended for containers)
   - **Ephemeral**: No
   - **Expiration**: Set appropriate expiration
   - **Tags**: Optional, for access control
5. Click **Generate key**
6. Copy the key (starts with `tskey-auth-`)

<!-- SCREENSHOT: Tailscale key generation -->
*[Screenshot placeholder: Tailscale auth key creation]*

---

## Appendix C: Cloudflare Tunnel Token Generation

1. Log in to [Cloudflare Zero Trust](https://one.dash.cloudflare.com)
2. Go to **Networks** > **Tunnels**
3. Click **Create a tunnel**
4. Select **Cloudflared** connector
5. Enter a tunnel name
6. Click **Save tunnel**
7. Copy the tunnel token (long string starting with `eyJ`)

Configure the tunnel:
1. Add public hostnames for n8n and management console
2. Point to `http://nginx:443` (internal Docker network)
3. Enable **No TLS Verify** for internal routing

<!-- SCREENSHOT: Cloudflare tunnel setup -->
*[Screenshot placeholder: Cloudflare tunnel configuration]*

---

## Appendix D: n8n API Key Generation

1. Log in to your n8n instance
2. Click your profile icon (bottom left)
3. Select **Settings**
4. Navigate to **API** in the left sidebar
5. Click **+ Create an API key**
6. Enter a label (e.g., "Management Console")
7. Click **Create**
8. Copy the API key immediately (shown only once)

<!-- SCREENSHOT: n8n API key -->
*[Screenshot placeholder: n8n API key generation]*

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Support

- **Documentation**: This README and [docs/](docs/) folder
- **Issues**: [GitHub Issues](https://github.com/rjsears/n8n_nginx/issues)
- **API Reference**: See [API.md](docs/API.md)
- **n8n Community**: [community.n8n.io](https://community.n8n.io)

---

## Acknowledgments

- [n8n.io](https://n8n.io) - Workflow automation platform
- [Let's Encrypt](https://letsencrypt.org) - Free SSL/TLS certificates
- [PostgreSQL](https://www.postgresql.org) - Database
- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity search
- [FastAPI](https://fastapi.tiangolo.com) - Python web framework
- [Vue.js](https://vuejs.org) - JavaScript framework
- [Tailwind CSS](https://tailwindcss.com) - CSS framework
- [Docker](https://docker.com) - Containerization
- [Nginx](https://nginx.org) - Web server
- [Apprise](https://github.com/caronc/apprise) - Notification library
- [ntfy](https://ntfy.sh) - Push notifications

  
* **My Amazing and loving family!** My family puts up with all my coding and automation projects and encourages me in everything. Without them, my projects would not be possible.
* **My brother James**, who is a continual source of inspiration to me and others. Everyone should have a brother as awesome as mine!

