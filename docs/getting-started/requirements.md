# Requirements

The hardware, software, operating system, and network requirements for deploying n8n Management Suite, including supported special environments such as Proxmox LXC, WSL2, and virtual machines.

## Hardware Requirements

### Minimum Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Storage | 20 GB | 50+ GB SSD |
| Network | 10 Mbps | 100+ Mbps |

### Storage Considerations

- **Operating System**: ~5 GB
- **Docker Images**: ~3 GB
- **PostgreSQL Data**: Varies with workflow complexity (plan 5-20 GB)
- **Backups**: Plan for 2-3x your database size
- **n8n Data**: Varies with execution history settings

> **Note**: If using NFS for backup storage, local storage requirements for backups are reduced.

## Software Requirements

### Required Software

| Software | Notes |
|----------|-------|
| Docker | Automatically installed by setup.sh if not present |
| Docker Compose | V2 plugin preferred; automatically configured |
| curl | Required for setup script |
| OpenSSL | Required for key generation |

### Automatically Installed

The setup script will automatically install these if not present:
- Docker Engine
- Docker Compose plugin
- Required Docker images
- curl
- OpenSSL

## Supported Operating Systems

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

### Special Environments

| Environment | Support Level | Notes                                                       |
|-------------|---------------|-------------------------------------------------------------|
| Proxmox LXC | Supported | Requires `nesting=1` and `lxc.apparmor.profile: unconfined`. `setup.sh` also probes whether Docker can load AppArmor policy and automatically configures all containers with `apparmor:unconfined` when it cannot |
| WSL2 | Supported | Requires Docker Desktop for Windows                         |
| Virtual Machines | Supported | Any hypervisor (Proxmox, VMware, VirtualBox, Hyper-V, KVM)  |

## Network Requirements

### Firewall Considerations

- Port 443 must be accessible from the internet for webhook functionality
- Consider using Tailscale or Cloudflare Tunnel for secure remote access

## DNS Provider Requirements

SSL certificate acquisition requires API access to your DNS provider for DNS-01 challenge validation. The following providers are supported:

| Provider | Required Credentials | Recommended |
|----------|---------------------|-------------|
| Cloudflare | API Token with Zone:DNS:Edit permission | Yes |
| AWS Route 53 | Access Key ID + Secret Access Key | Yes |
| Google Cloud DNS | Service Account JSON key | Yes |
| DigitalOcean | API Token with read/write access | Yes |
| Manual | None (requires manual DNS record creation) | No |

> **Recommendation**: Cloudflare is recommended due to fast DNS propagation (60 seconds) and straightforward API token creation.
