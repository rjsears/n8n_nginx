<p align="center">
  <img src="images/n8n_repo_banner.jpg" alt="n8n Enterprise Deployment Suite" width="800"/>
</p>

<p align="center">
  <em>"Enterprise-grade automation infrastructure shouldn't require an enterprise budget."</em>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://github.com/rjsears/n8n_nginx/commits"><img src="https://img.shields.io/github/last-commit/rjsears/n8n_nginx" alt="GitHub last commit"></a>
  <a href="https://github.com/rjsears/n8n_nginx/issues"><img src="https://img.shields.io/github/issues/rjsears/n8n_nginx" alt="GitHub issues"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Version-3.0.0-orange" alt="Version"></a>
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

---

# n8n Enterprise Deployment Suite

A production-ready, self-hosted deployment solution for [n8n](https://n8n.io) workflow automation with integrated HTTPS/SSL certificate management, PostgreSQL database with pgvector for AI/RAG workflows, comprehensive backup and disaster recovery, multi-channel notifications, and a full-featured web-based management console.

---

## Table of Contents

### Part I: Introduction
- [1. Overview](#1-overview)
  - [1.1 What is n8n Enterprise Deployment Suite?](#11-what-is-n8n-enterprise-deployment-suite)
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
- [4. Interactive Setup](#4-interactive-setup)
  - [4.1 Starting the Setup](#41-starting-the-setup)
  - [4.2 Docker Installation](#42-docker-installation)
  - [4.3 Domain Configuration](#43-domain-configuration)
  - [4.4 DNS Provider Selection](#44-dns-provider-selection)
  - [4.5 Database Configuration](#45-database-configuration)
  - [4.6 Administrator Account Setup](#46-administrator-account-setup)
  - [4.7 Security Configuration](#47-security-configuration)
  - [4.8 Container Naming](#48-container-naming)
  - [4.9 Timezone Configuration](#49-timezone-configuration)
  - [4.10 Optional Services](#410-optional-services)
  - [4.11 Configuration Summary](#411-configuration-summary)
  - [4.12 Deployment Process](#412-deployment-process)
  - [4.13 Post-Installation Summary](#413-post-installation-summary)

### Part III: Initial Configuration
- [5. First-Time Setup](#5-first-time-setup)
  - [5.1 Accessing the n8n Interface](#51-accessing-the-n8n-interface)
  - [5.2 Accessing the Management Console](#52-accessing-the-management-console)
  - [5.3 Configuring the n8n API Connection](#53-configuring-the-n8n-api-connection)
  - [5.4 Deploying Test Workflows](#54-deploying-test-workflows)
  - [5.5 IP Access Control Configuration](#55-ip-access-control-configuration)

### Part IV: Management Console Reference
- [6. Dashboard](#6-dashboard)
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

---

# Part I: Introduction

## 1. Overview

### 1.1 What is n8n Enterprise Deployment Suite?

The n8n Enterprise Deployment Suite is a comprehensive, production-ready deployment and management solution for self-hosted n8n workflow automation. It combines:

- **Automated Deployment**: A single interactive script (`setup.sh`) that handles everything from Docker installation to SSL certificate acquisition
- **Enterprise Infrastructure**: PostgreSQL 16 with pgvector for AI/RAG workflows, Nginx reverse proxy with automatic HTTPS, and Let's Encrypt certificate management
- **Management Console**: A full-featured web application for monitoring, backup management, notifications, and system administration
- **Disaster Recovery**: Comprehensive backup system with verification, selective restoration, and bare-metal recovery capabilities
- **Multi-Channel Notifications**: Support for 30+ notification providers through Apprise, plus native NTFY push notifications

Whether you are running n8n for personal automation or deploying it for an organization, this suite provides the infrastructure, monitoring, and management tools typically found only in expensive enterprise solutions.

### 1.2 Key Features at a Glance

#### Deployment and Infrastructure
- One-command interactive setup with automatic Docker installation
- Automatic SSL/TLS certificate acquisition and renewal via Let's Encrypt
- Support for multiple DNS providers (Cloudflare, AWS Route 53, Google Cloud DNS, DigitalOcean)
- PostgreSQL 16 with pgvector extension for AI vector embeddings
- Nginx reverse proxy with optimized configuration for n8n
- Optional Tailscale VPN and Cloudflare Tunnel integration

#### Management Console
- Real-time system metrics dashboard (CPU, memory, disk, network)
- Docker container management (start, stop, restart, logs)
- n8n workflow monitoring and control
- Comprehensive settings management
- Dark/light theme support

#### Backup and Recovery
- Scheduled and on-demand backups
- Multiple storage backends (local, NFS)
- Backup verification with integrity checking
- Selective workflow restoration
- Full system bare-metal recovery
- Grandfather-Father-Son (GFS) retention policies
- Automatic pruning with space management

#### Notifications
- 30+ notification providers via Apprise integration
- Native NTFY push notification support
- Email notifications with customizable templates
- Webhook integration for n8n workflows
- System event notifications with configurable triggers
- L1/L2 escalation support
- Maintenance mode and quiet hours

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
            MGMT["Management Console<br/>:3333"]
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

| Component | Purpose |
|-----------|---------|
| **Nginx** | Reverse proxy handling HTTPS termination, routing, and security headers |
| **n8n** | Workflow automation engine |
| **PostgreSQL** | Primary database with pgvector for AI/ML vector operations |
| **Management Console** | Web-based administration interface |
| **FastAPI Backend** | REST API powering the management console |
| **Certbot** | Automatic SSL certificate acquisition and renewal |
| **NTFY** | Optional self-hosted push notification server |
| **Portainer** | Optional container management UI |
| **Adminer** | Optional database administration UI |
| **Dozzle** | Optional real-time log viewer |
| **Tailscale** | Optional VPN for secure remote access |

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

| Environment | Support Level | Notes |
|-------------|---------------|-------|
| Proxmox LXC | Supported | Requires `nesting=1` and `lxc.apparmor.profile: unconfined` |
| WSL2 | Supported | Requires Docker Desktop for Windows |
| Virtual Machines | Supported | Any hypervisor (VMware, VirtualBox, Hyper-V, KVM) |

### 2.4 Network Requirements

#### Required Ports

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 443 | TCP | Inbound | HTTPS (n8n and webhooks) |
| 3333 | TCP | Inbound | Management Console (configurable) |

#### Optional Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 9001 | TCP | Portainer Agent |
| 8080 | TCP | Adminer (database UI) |
| 9999 | TCP | Dozzle (log viewer) |
| 80 | TCP | NTFY (if enabled) |

#### Firewall Considerations

- Port 443 must be accessible from the internet for webhook functionality
- Management console port (3333) should be restricted to trusted networks
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

#### Step 1: Update Your System

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL/Rocky/AlmaLinux
sudo dnf update -y

# Fedora
sudo dnf upgrade -y
```

#### Step 2: Ensure Required Utilities Are Installed

```bash
# Ubuntu/Debian
sudo apt install -y curl git openssl

# CentOS/RHEL/Rocky/AlmaLinux/Fedora
sudo dnf install -y curl git openssl
```

#### Step 3: Configure DNS

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

## 4. Interactive Setup

The setup script (`setup.sh`) provides a fully interactive installation experience. It guides you through each configuration step with clear prompts and validation.

### 4.1 Starting the Setup

```bash
./setup.sh
```

The setup script will display a welcome banner and begin the configuration process.

<!-- SCREENSHOT: Setup welcome screen -->
*[Screenshot placeholder: Setup script welcome banner]*

### 4.2 Docker Installation

The script automatically checks for Docker and Docker Compose. If not installed, it will offer to install them.

#### Automatic Detection

The script detects:
- Operating system type and version
- Existing Docker installation
- Docker Compose version (v1 vs v2)
- Proxmox LXC environment
- WSL2 environment

#### Docker Installation Process

If Docker is not found:

1. The script asks if you want to install Docker
2. For supported operating systems, installation is automatic
3. The script adds your user to the docker group
4. You may need to log out and back in for group changes to take effect

```
Docker is not installed. Would you like to install it now? [Y/n]
```

<!-- SCREENSHOT: Docker installation prompt -->
*[Screenshot placeholder: Docker installation prompt]*

#### AppArmor Handling (Proxmox LXC)

If running in a Proxmox LXC container, the script detects AppArmor restrictions:

```
AppArmor detected. This may prevent Docker from running properly.
Would you like to disable AppArmor for this container? [Y/n]
```

For Proxmox LXC, you need to add these settings to the container configuration:

```
lxc.apparmor.profile: unconfined
features: nesting=1
```

### 4.3 Domain Configuration

#### Entering Your Domain

```
Enter your domain name (e.g., n8n.example.com):
```

Enter the fully qualified domain name (FQDN) for your n8n instance.

#### DNS Validation

The script validates your domain configuration:

1. **Format Validation**: Checks that the domain is properly formatted
2. **DNS Resolution**: Verifies the domain resolves to an IP address
3. **IP Matching**: Confirms the domain points to your server's IP

```
Validating domain configuration...
  Domain format: Valid
  DNS resolution: 203.0.113.50
  Server IP match: Yes
```

#### Troubleshooting DNS Issues

If validation fails:

| Issue | Cause | Solution |
|-------|-------|----------|
| Domain does not resolve | DNS record not created | Add A record in DNS provider |
| IP mismatch | Domain points to wrong server | Update A record with correct IP |
| DNS propagation | Changes haven't propagated | Wait 5-30 minutes and retry |

### 4.4 DNS Provider Selection

The script supports multiple DNS providers for Let's Encrypt certificate acquisition:

```
Select your DNS provider:
  1) Cloudflare (Recommended)
  2) AWS Route 53
  3) Google Cloud DNS
  4) DigitalOcean
  5) Manual/Other
```

<!-- SCREENSHOT: DNS provider selection menu -->
*[Screenshot placeholder: DNS provider selection]*

#### Cloudflare Setup (Recommended)

If you select Cloudflare:

```
Enter your Cloudflare API Token:
```

**How to get a Cloudflare API Token:**

1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Go to **My Profile** (top right) > **API Tokens**
3. Click **Create Token**
4. Use the **Edit zone DNS** template
5. Under **Zone Resources**, select your zone
6. Click **Continue to summary** > **Create Token**
7. Copy the token (it will only be shown once)

<!-- SCREENSHOT: Cloudflare API token creation -->
*[Screenshot placeholder: Cloudflare API token creation page]*

The script creates `cloudflare.ini` with your credentials:

```ini
dns_cloudflare_api_token = your-api-token-here
```

#### AWS Route 53 Setup

If you select AWS Route 53:

```
Enter your AWS Access Key ID:
Enter your AWS Secret Access Key:
```

**Required IAM Policy:**

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "route53:ListHostedZones",
                "route53:GetChange",
                "route53:ChangeResourceRecordSets"
            ],
            "Resource": "*"
        }
    ]
}
```

See [Appendix A](#appendix-a-dns-provider-credential-setup) for detailed IAM setup instructions.

#### Google Cloud DNS Setup

If you select Google Cloud DNS:

```
Enter the path to your Google Cloud service account JSON file:
```

The service account requires the **DNS Administrator** role.

See [Appendix A](#appendix-a-dns-provider-credential-setup) for service account creation instructions.

#### DigitalOcean Setup

If you select DigitalOcean:

```
Enter your DigitalOcean API Token:
```

Generate a token at [DigitalOcean API Tokens](https://cloud.digitalocean.com/account/api/tokens) with read and write access.

#### Manual DNS Setup

If you select Manual/Other, you will need to manually create DNS TXT records during certificate acquisition. This requires you to be present during the initial setup and each certificate renewal.

> **Warning**: Manual DNS setup is not recommended for production environments as it requires manual intervention for certificate renewals.

### 4.5 Database Configuration

The script configures PostgreSQL for both n8n and the management console.

#### Database Settings

```
Database Configuration
----------------------
Database name [n8n]:
Database username [n8n]:
Generate random password? [Y/n]
```

Default values are provided in brackets. Press Enter to accept defaults.

| Setting | Default | Notes |
|---------|---------|-------|
| Database Name | `n8n` | Name of the n8n database |
| Database Username | `n8n` | PostgreSQL user |
| Database Password | Auto-generated | 32-character random password |

The script automatically creates a second database (`n8n_management`) for the management console.

### 4.6 Administrator Account Setup

Configure the management console administrator account:

```
Administrator Account Setup
---------------------------
Admin username [admin]:
Admin password (min 8 characters):
Confirm password:
Admin email address:
```

<!-- SCREENSHOT: Admin account setup -->
*[Screenshot placeholder: Admin account configuration]*

| Field | Requirements |
|-------|--------------|
| Username | Alphanumeric, 3-50 characters |
| Password | Minimum 8 characters |
| Email | Valid email format |

### 4.7 Security Configuration

#### Encryption Key Generation

The script generates encryption keys for securing sensitive data:

```
Generating encryption keys...
  n8n Encryption Key: Generated (32 characters)
  Management Secret Key: Generated (64 characters)
  Management Encryption Key: Generated (32 characters)
```

> **Critical**: These keys are displayed only once during setup. Save them in a secure location such as a password manager. If lost, encrypted data cannot be recovered.

<!-- SCREENSHOT: Encryption key display -->
*[Screenshot placeholder: Encryption key generation with save warning]*

#### What the Keys Are Used For

| Key | Purpose |
|-----|---------|
| n8n Encryption Key | Encrypts credentials stored in n8n workflows |
| Management Secret Key | Signs session tokens for the management console |
| Management Encryption Key | Encrypts sensitive settings in the management database |

### 4.8 Container Naming

Customize Docker container names (optional):

```
Container Naming
----------------
PostgreSQL container name [n8n_postgres]:
n8n container name [n8n]:
Nginx container name [n8n_nginx]:
Certbot container name [n8n_certbot]:
Management container name [n8n_management]:
```

Default names are recommended unless you have specific requirements (e.g., running multiple instances).

### 4.9 Timezone Configuration

```
Timezone Configuration
----------------------
Detected timezone: America/Los_Angeles
Use detected timezone? [Y/n]
```

The script auto-detects your system timezone. You can accept it or enter a different timezone in IANA format (e.g., `Europe/London`, `Asia/Tokyo`).

### 4.10 Optional Services

The script offers several optional services:

```
Optional Services
-----------------
Enable Portainer (container management UI)? [y/N]
Enable Cloudflare Tunnel? [y/N]
Enable Tailscale VPN? [y/N]
Enable Adminer (database UI)? [y/N]
Enable Dozzle (log viewer)? [y/N]
Enable NTFY (push notifications)? [y/N]
```

<!-- SCREENSHOT: Optional services selection -->
*[Screenshot placeholder: Optional services menu]*

#### Portainer

A web-based container management UI that provides:
- Visual container management
- Resource monitoring
- Log viewing
- Container terminal access

Access: `https://your-domain:9000`

#### Cloudflare Tunnel

Secure access without opening ports:
- No public IP required
- Built-in DDoS protection
- Zero Trust access policies

```
Enter your Cloudflare Tunnel token:
```

See [Appendix C](#appendix-c-cloudflare-tunnel-token-generation) for token generation instructions.

#### Tailscale VPN

Private network access via Tailscale:
- Secure remote access
- No public port exposure for management
- MagicDNS for easy access

```
Enter your Tailscale auth key:
```

See [Appendix B](#appendix-b-tailscale-auth-key-generation) for auth key generation.

#### Adminer

Lightweight database administration tool:
- Browse database tables
- Run SQL queries
- Export data

Access: `https://your-domain:3333/adminer/`

#### Dozzle

Real-time Docker log viewer:
- Live log streaming
- Multi-container view
- Log search and filtering

Access: `https://your-domain:3333/logs/`

#### NTFY

Self-hosted push notification server:
- Mobile push notifications
- Desktop notifications
- Email forwarding

Access: `https://your-domain/ntfy/` or dedicated port

### 4.11 Configuration Summary

Before deployment, the script displays a complete summary:

```
Configuration Summary
=====================

Domain: n8n.example.com
DNS Provider: Cloudflare
Let's Encrypt Email: admin@example.com

Database:
  Name: n8n
  User: n8n
  Password: ********

Admin Account:
  Username: admin
  Email: admin@example.com

Containers:
  PostgreSQL: n8n_postgres
  n8n: n8n
  Nginx: n8n_nginx
  Certbot: n8n_certbot
  Management: n8n_management

Optional Services:
  Portainer: Disabled
  Cloudflare Tunnel: Disabled
  Tailscale: Enabled
  Adminer: Enabled
  Dozzle: Enabled
  NTFY: Disabled

Timezone: America/Los_Angeles

Proceed with installation? [Y/n]
```

<!-- SCREENSHOT: Configuration summary -->
*[Screenshot placeholder: Full configuration summary]*

Review all settings carefully before proceeding.

### 4.12 Deployment Process

The deployment process runs automatically after confirmation:

```mermaid
flowchart TD
    Start[Start Deployment] --> Network[Create Docker Network]
    Network --> Volumes[Create Docker Volumes]
    Volumes --> PG[Start PostgreSQL]
    PG --> WaitPG{PostgreSQL Ready?}
    WaitPG -->|No| WaitPG
    WaitPG -->|Yes| InitDB[Initialize Databases]
    InitDB --> Cert[Obtain SSL Certificate]
    Cert --> CertOK{Certificate OK?}
    CertOK -->|No| CertFail[Display Error & Exit]
    CertOK -->|Yes| CopyCert[Copy Certificates]
    CopyCert --> StartAll[Start All Services]
    StartAll --> Health[Health Check]
    Health --> Complete[Deployment Complete]
```

#### Step 1: Create Docker Network and Volumes

```
Creating Docker network: n8n_network
Creating Docker volumes...
  - n8n_data
  - postgres_data
  - letsencrypt (external)
```

#### Step 2: Start PostgreSQL

```
Starting PostgreSQL...
Waiting for PostgreSQL to be ready... [OK]
Creating databases...
  - n8n: Created
  - n8n_management: Created
```

#### Step 3: Obtain SSL Certificate

```
Obtaining SSL certificate from Let's Encrypt...
  DNS Provider: Cloudflare
  Domain: n8n.example.com
  Challenge: DNS-01
  Propagation wait: 60 seconds
  Certificate: Obtained successfully
```

<!-- SCREENSHOT: SSL certificate acquisition -->
*[Screenshot placeholder: Certificate acquisition progress]*

#### Step 4: Start All Services

```
Starting all services...
  PostgreSQL: Running
  n8n: Running
  Nginx: Running
  Certbot: Running
  Management: Running
  Tailscale: Running
  Adminer: Running
  Dozzle: Running
```

#### Step 5: Health Verification

```
Verifying services...
  PostgreSQL connectivity: OK
  n8n health endpoint: OK
  Nginx configuration: OK
  SSL certificate: Valid (expires in 90 days)
  Management console: OK
```

### 4.13 Post-Installation Summary

After successful deployment:

```
============================================
    Installation Complete
============================================

Access your services:
  n8n:        https://n8n.example.com
  Management: https://n8n.example.com:3333
  Adminer:    https://n8n.example.com:3333/adminer/
  Dozzle:     https://n8n.example.com:3333/logs/

Management Console Credentials:
  Username: admin
  Password: (the password you entered)

IMPORTANT - Save these encryption keys:
  n8n Encryption Key: abc123...
  Management Keys: (saved in .env file)

Configuration saved to: .n8n_setup_config

Useful Commands:
  View all logs:     docker compose logs -f
  Restart services:  docker compose restart
  Stop services:     docker compose down
  Start services:    docker compose up -d

Next Steps:
  1. Access n8n and create your owner account
  2. Log in to the management console
  3. Configure the n8n API connection
  4. Set up backup schedules
  5. Configure notification channels

============================================
```

<!-- SCREENSHOT: Installation complete summary -->
*[Screenshot placeholder: Post-installation summary with all URLs]*

---

# Part III: Initial Configuration

## 5. First-Time Setup

After installation is complete, you need to perform initial configuration of both n8n and the management console.

### 5.1 Accessing the n8n Interface

#### Creating Your Owner Account

1. Open your browser and navigate to `https://your-domain.com`
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

- Your n8n instance is now accessible at `https://your-domain.com`
- Webhooks are accessible at `https://your-domain.com/webhook/`
- The editor is fully functional and ready for workflow creation

### 5.2 Accessing the Management Console

#### Login Process

1. Navigate to `https://your-domain.com:3333`
2. Enter the admin credentials you created during setup
3. Click **Login**

<!-- SCREENSHOT: Management console login page -->
*[Screenshot placeholder: Management console login screen]*

#### Dashboard Overview

After logging in, you will see the dashboard with:

- **System Metrics**: CPU, memory, disk usage
- **Container Status**: Health status of all containers
- **Backup Status**: Recent backup information
- **Quick Actions**: Common administrative tasks

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

To verify everything is working correctly, you can deploy test workflows.

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
https://your-machine.tailnet-name.ts.net:3333
```

---

# Part IV: Management Console Reference

## 6. Dashboard

The dashboard provides an at-a-glance overview of your system's health and status.

<!-- SCREENSHOT: Full dashboard view -->
*[Screenshot placeholder: Complete dashboard with all widgets]*

### Dashboard Components

| Component | Description |
|-----------|-------------|
| **System Metrics** | Real-time CPU, memory, and disk usage with graphs |
| **Container Status** | Health status of all Docker containers |
| **Backup Summary** | Last backup status and next scheduled backup |
| **Quick Actions** | Common administrative shortcuts |
| **Network Status** | Network interface information |

### System Metrics

The metrics panel displays:
- **CPU Usage**: Current and historical CPU utilization
- **Memory Usage**: RAM usage with available/total
- **Disk Usage**: Storage utilization for each mount point
- **Load Average**: 1, 5, and 15-minute load averages

### Container Status

Quick view of all containers:
- Green indicator: Running and healthy
- Yellow indicator: Running but unhealthy
- Red indicator: Stopped or exited
- Gray indicator: Unknown status

Click any container to navigate to the Containers page for details.

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
| **Both** | Local with NFS replication | Redundant storage |

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
   - **Description**: Optional note
4. Click **Start Backup**

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

1. Go to **Backups** > **Settings** > **Schedules**
2. Click **Add Schedule**
3. Configure:
   - **Name**: Schedule identifier
   - **Frequency**: Hourly, Daily, Weekly, or Monthly
   - **Time**: When to run (for daily/weekly/monthly)
   - **Day**: Which day (for weekly/monthly)
   - **Compression**: Compression type
   - **Enabled**: Toggle on/off

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

#### Scheduled Verification

Configure automatic verification:

1. Go to **Backups** > **Settings** > **Verification**
2. Enable scheduled verification
3. Set frequency (e.g., verify each backup, weekly verification)
4. Save settings

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
   - **Topic**: Topic name
   - **Priority**: Default priority (1-5)
   - **Authentication**: Username/password if required
3. Click **Save**

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
2. Click **Add Topic**
3. Configure:
   - **Name**: Topic identifier (e.g., `n8n-alerts`)
   - **Display Name**: Friendly name
   - **Default Priority**: 1 (min) to 5 (max)
   - **Default Tags**: Emoji tags (e.g., `warning`, `backup`)

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
POST https://your-domain.com:3333/api/notifications/webhook
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
  "url": "https://your-domain.com:3333/api/notifications/webhook",
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

System-wide notification controls:

<!-- SCREENSHOT: Global notification settings -->
*[Screenshot placeholder: Global settings panel]*

#### Maintenance Mode

Temporarily silence all notifications:

1. Go to **Settings** > **System Notifications**
2. Enable **Maintenance Mode**
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

Configure monitoring for individual containers:

1. Go to **System Notifications** > **Container Config**
2. Click **Add Container**
3. Select the container
4. Configure:
   - **Enable Monitoring**: Master on/off
   - **Monitor Unhealthy**: Health check failures
   - **Monitor Restart**: Restart events
   - **Monitor Stopped**: Stop events
   - **CPU Threshold**: Custom CPU limit (%)
   - **Memory Threshold**: Custom memory limit (%)
   - **Custom Targets**: Override default notification targets

<!-- SCREENSHOT: Per-container configuration -->
*[Screenshot placeholder: Container-specific notification settings]*

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

View all containers with:
- **Name**: Container name
- **Status**: Running, Stopped, Exited
- **Health**: Healthy, Unhealthy, None
- **CPU**: Current CPU usage
- **Memory**: Current memory usage
- **Network**: I/O statistics
- **Uptime**: Time since container started

### Container Operations

| Action | Description |
|--------|-------------|
| **Start** | Start a stopped container |
| **Stop** | Gracefully stop a running container |
| **Restart** | Stop and start a container |
| **View Logs** | Display container log output |

### Viewing Container Logs

1. Click a container
2. Click **View Logs**
3. Options:
   - **Lines**: Number of lines to show
   - **Follow**: Stream new logs in real-time
   - **Since**: Show logs since timestamp
4. Use search to filter logs

<!-- SCREENSHOT: Container logs viewer -->
*[Screenshot placeholder: Container log output]*

### Resource Monitoring

Click a container to view detailed metrics:
- CPU usage over time
- Memory usage over time
- Network I/O over time
- Block I/O statistics

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
