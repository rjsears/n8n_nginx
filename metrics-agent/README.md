# n8n Metrics Agent

A lightweight host-level system metrics collector for the n8n Management System.

## Overview

The n8n Metrics Agent runs directly on the host system (not in Docker) to collect accurate system metrics that cannot be obtained from within containers. It exposes a REST API that the n8n Management container can poll.

## Features

- **System Metrics**: CPU usage, memory, disk space, uptime, load averages
- **Docker Metrics**: Container status, health, restart counts, resource usage
- **Network Metrics**: Interface statistics, bandwidth usage
- **Event Detection**: Detects container health changes, restarts, and status changes
- **Secure**: API key authentication, localhost-only by default

## Requirements

- Python 3.9 or higher
- Docker (optional, for container metrics)
- Linux (tested on Ubuntu, Debian, CentOS)

## Quick Installation

```bash
# Clone or copy the metrics-agent directory to your server
cd /path/to/n8n_nginx/metrics-agent

# Run the installer as root
sudo ./install.sh
```

The installer will:
1. Create a virtual environment in `/opt/n8n-metrics-agent`
2. Install all dependencies
3. Generate a secure API key
4. Create and start a systemd service

## Manual Installation

```bash
# Create installation directory
sudo mkdir -p /opt/n8n-metrics-agent
cd /opt/n8n-metrics-agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install from source
pip install -e /path/to/metrics-agent

# Run directly
METRICS_AGENT_API_KEY="your-key" n8n-metrics-agent
```

## Configuration

Configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `METRICS_AGENT_HOST` | `127.0.0.1` | Bind address (use `0.0.0.0` for remote access) |
| `METRICS_AGENT_PORT` | `9100` | Listen port |
| `METRICS_AGENT_API_KEY` | (none) | API key for authentication |
| `DOCKER_SOCKET` | `/var/run/docker.sock` | Docker socket path |
| `METRICS_LOG_LEVEL` | `INFO` | Logging level |
| `METRICS_DISK_MOUNTS` | (all) | Comma-separated mount points to monitor |
| `METRICS_CONTAINER_FILTER` | (all) | Container name patterns to monitor |

## API Endpoints

### Health Check (no auth required)
```bash
curl http://127.0.0.1:9100/health
```

### Get All Metrics
```bash
curl -H "X-API-Key: YOUR_KEY" http://127.0.0.1:9100/metrics
```

### Get System Metrics Only
```bash
curl -H "X-API-Key: YOUR_KEY" http://127.0.0.1:9100/metrics/system
```

### Get Container Metrics
```bash
curl -H "X-API-Key: YOUR_KEY" http://127.0.0.1:9100/metrics/containers

# With resource stats (slower)
curl -H "X-API-Key: YOUR_KEY" "http://127.0.0.1:9100/metrics/containers?include_stats=true"
```

### Get Specific Container
```bash
curl -H "X-API-Key: YOUR_KEY" http://127.0.0.1:9100/metrics/containers/n8n
```

### Get Container Events
```bash
curl -H "X-API-Key: YOUR_KEY" http://127.0.0.1:9100/events/containers
```

## Service Management

```bash
# Check status
sudo systemctl status n8n-metrics-agent

# View logs
sudo journalctl -u n8n-metrics-agent -f

# Restart
sudo systemctl restart n8n-metrics-agent

# Stop
sudo systemctl stop n8n-metrics-agent

# Disable
sudo systemctl disable n8n-metrics-agent
```

## Uninstallation

```bash
sudo ./uninstall.sh
```

Or manually:
```bash
sudo systemctl stop n8n-metrics-agent
sudo systemctl disable n8n-metrics-agent
sudo rm /etc/systemd/system/n8n-metrics-agent.service
sudo rm -rf /opt/n8n-metrics-agent
sudo systemctl daemon-reload
```

## Security Notes

1. **Localhost Only**: By default, the agent only listens on `127.0.0.1`. The management container accesses it via the host network.

2. **API Key**: Always set an API key in production. The installer generates one automatically.

3. **Docker Socket Access**: The agent requires access to the Docker socket to collect container metrics. Run as root or add to the docker group.

4. **Firewall**: If you change the bind address to allow remote access, ensure proper firewall rules are in place.

## Integration with n8n Management

1. Install the metrics agent on the host
2. Note the API key from installation
3. Configure the n8n Management container to connect to `http://host.docker.internal:9100` (or `http://172.17.0.1:9100` on Linux)
4. Add the API key to the management console settings

## Troubleshooting

### Service won't start
```bash
journalctl -u n8n-metrics-agent -n 50 --no-pager
```

### Docker metrics unavailable
- Check Docker socket permissions
- Verify the user can run `docker ps`

### High CPU usage
- The agent uses minimal resources, but if container stats are enabled, each container query takes ~1 second
- Reduce polling frequency in the management console
