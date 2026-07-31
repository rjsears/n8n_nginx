<!-- -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
     /README.md

     Part of the "n8n_nginx/n8n_management" suite
     Version 3.0.0 - January 1st, 2026

     Richard J. Sears
     richard@n8nmanagement.net
     https://github.com/rjsears
     -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= -->

<p align="center">
  <img src="images/n8n_repo_banner.jpg" alt="n8n Management Suite" width="800"/>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://rjsears.github.io/n8n_nginx/"><img src="https://img.shields.io/badge/docs-rjsears.github.io%2Fn8n__nginx-blue" alt="Documentation"></a>
  <a href="docs/CHANGELOG.md"><img src="https://img.shields.io/badge/Version-3.0.0-orange" alt="Version"></a>
  <a href="https://github.com/rjsears/n8n_nginx/commits"><img src="https://img.shields.io/github/last-commit/rjsears/n8n_nginx" alt="GitHub last commit"></a>
  <a href="https://github.com/rjsears/n8n_nginx/issues"><img src="https://img.shields.io/github/issues/rjsears/n8n_nginx" alt="GitHub issues"></a>
</p>

<p align="center">
  <a href="https://n8n.io"><img src="https://img.shields.io/badge/n8n-Workflow%20Automation-FF6D5A?logo=n8n&logoColor=white" alt="n8n"></a>
  <a href="https://www.postgresql.org"><img src="https://img.shields.io/badge/PostgreSQL-16%20with%20pgvector-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL"></a>
  <a href="https://docker.com"><img src="https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker&logoColor=white" alt="Docker"></a>
  <a href="https://nginx.org"><img src="https://img.shields.io/badge/Nginx-Reverse%20Proxy-009639?logo=nginx&logoColor=white" alt="Nginx"></a>
  <a href="https://letsencrypt.org"><img src="https://img.shields.io/badge/Let's%20Encrypt-SSL%2FTLS-003A70?logo=letsencrypt&logoColor=white" alt="Let's Encrypt"></a>
  <a href="https://tailscale.com"><img src="https://img.shields.io/badge/Tailscale-VPN%20Ready-242424?logo=tailscale&logoColor=white" alt="Tailscale"></a>
</p>

# n8n Management Suite

> ### *"Automation means solving a problem once, then putting the solution on autopilot."* — Michael Hyatt

A production-ready, self-hosted **n8n** deployment with automatic HTTPS, PostgreSQL 16 + pgvector, and a full-featured FastAPI/Vue.js management console for backups, notifications, container management, and system monitoring — all driven by one interactive `setup.sh`.

### 📚 Full documentation: **https://rjsears.github.io/n8n_nginx/**

The User Manual, Getting Started guides, and full Reference docs (installation, backups, notifications, SSL, Tailscale, Cloudflare Tunnel, the REST API, and troubleshooting) all live on the docs site — this README is just the landing page.

<p align="center">
  <img src="docs/images/screenshots/dashboard-01-overview.png" alt="Management Console dashboard overview" width="800"/>
</p>

## Features

- **One-command interactive setup** — `setup.sh` handles Docker installation, SSL acquisition, and full deployment end to end
- **Automatic HTTPS** via Let's Encrypt DNS-01 challenges, with Cloudflare, AWS Route 53, Google Cloud DNS, and DigitalOcean support
- **PostgreSQL 16 + pgvector** for n8n workflow data and AI/RAG vector embeddings
- **Management Console** — real-time system dashboards, full Docker container control, and an in-browser terminal
- **Backup & disaster recovery** — scheduled or on-demand backups, GFS retention, integrity verification, selective and bare-metal restore
- **Multi-channel notifications** — 80+ services via Apprise plus native NTFY push, with L1/L2 escalation and quiet hours
- **Optional public website hosting** — a network-isolated static site with an integrated file browser
- **Secure remote access** — optional Tailscale VPN or Cloudflare Tunnel integration, no open inbound ports required
- **Workflow management** — activate, deactivate, and monitor n8n workflow executions from the console
- **Dark/light themes** with configurable top or side navigation layout

## Architecture

| Component | Purpose |
|---|---|
| **Nginx** | Reverse proxy handling HTTPS termination, routing, and security headers |
| **n8n** | Workflow automation engine |
| **PostgreSQL 16 + pgvector** | Primary database, plus vector storage for AI/ML workflows |
| **Management Console** | FastAPI backend + Vue.js frontend for administration |
| **Redis** | Status caching for sub-50ms system metrics |
| **Certbot** | Automatic SSL certificate acquisition and renewal |
| **Tailscale / Cloudflared** | Optional secure remote access, no open inbound ports |
| **Portainer / Adminer / Dozzle** | Optional container, database, and log management UIs |

Full component diagram and technology stack: [Architecture guide](https://rjsears.github.io/n8n_nginx/getting-started/architecture/).

## Quick Start

```bash
# Clone the repository
git clone https://github.com/rjsears/n8n_nginx.git
cd n8n_nginx

# Run the interactive setup wizard
./setup.sh
```

`setup.sh` walks you through DNS provider selection, domain configuration, and deployment, then verifies HTTPS connectivity automatically. Once it finishes:

1. Open `https://n8n.your-domain.com` and create your n8n owner account
2. Open `https://n8n.your-domain.com/management` and log in with the admin credentials you set during setup

For the full walkthrough — including unattended/pre-configured installs — see the [Installation Guide](https://rjsears.github.io/n8n_nginx/getting-started/installation/).

## Supported Platforms

| Operating System | Versions | Notes |
|---|---|---|
| Ubuntu | 20.04, 22.04, 24.04 | Recommended |
| Debian | 11, 12 | Fully supported |
| CentOS / RHEL | 8, 9 | Stream / Enterprise Linux |
| Fedora | 38+ | Latest releases |
| Rocky Linux / AlmaLinux | 8, 9 | RHEL-compatible |
| macOS | 10.15+ | Requires Docker Desktop |
| Windows 10/11 | — | Via WSL2 with Docker Desktop |
| Proxmox LXC | — | Supported; `setup.sh` auto-detects and configures AppArmor |

Full hardware, software, and network requirements: [Requirements guide](https://rjsears.github.io/n8n_nginx/getting-started/requirements/).

## Documentation

| | |
|---|---|
| [Getting Started](https://rjsears.github.io/n8n_nginx/getting-started/installation/) | Requirements, installation, and architecture |
| [User Manual](https://rjsears.github.io/n8n_nginx/manual/welcome/) | Dashboard, containers, flows, backups, notifications, system, settings |
| [Backup & Restore Guide](https://rjsears.github.io/n8n_nginx/BACKUP_GUIDE/) | Backup types, scheduling, NFS storage |
| [Notifications Guide](https://rjsears.github.io/n8n_nginx/NOTIFICATIONS/) | Apprise, NTFY, escalation |
| [SSL / Certbot Guide](https://rjsears.github.io/n8n_nginx/CERTBOT/) | Let's Encrypt, DNS-01, renewal |
| [Cloudflare Tunnel](https://rjsears.github.io/n8n_nginx/CLOUDFLARE/) · [Tailscale VPN](https://rjsears.github.io/n8n_nginx/TAILSCALE/) | Secure remote access |
| [API Reference](https://rjsears.github.io/n8n_nginx/API/) | REST API for the management console |
| [Troubleshooting](https://rjsears.github.io/n8n_nginx/TROUBLESHOOTING/) | Common issues and diagnostics |

## License & Author

MIT License — see [LICENSE](LICENSE).

Developed and maintained by **Richard J. Sears** ([@rjsears](https://github.com/rjsears)).

- Issues & feature requests: [GitHub Issues](https://github.com/rjsears/n8n_nginx/issues)
- Changelog: [docs/CHANGELOG.md](docs/CHANGELOG.md)

Built on [n8n](https://n8n.io), [PostgreSQL](https://www.postgresql.org) / [pgvector](https://github.com/pgvector/pgvector), [FastAPI](https://fastapi.tiangolo.com), [Vue.js](https://vuejs.org), [Nginx](https://nginx.org), [Let's Encrypt](https://letsencrypt.org), and [Apprise](https://github.com/caronc/apprise).
