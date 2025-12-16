#!/bin/bash
#
# n8n Metrics Agent Installation Script
#
# This script installs the n8n Metrics Agent as a systemd service.
# Run as root or with sudo.
#

set -e

# Configuration
INSTALL_DIR="/opt/n8n-metrics-agent"
SERVICE_NAME="n8n-metrics-agent"
VENV_DIR="$INSTALL_DIR/venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[*]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root (use sudo)"
    exit 1
fi

# Check Python version
print_status "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 9 ]]; then
    print_error "Python 3.9 or higher is required (found $PYTHON_VERSION)"
    exit 1
fi
print_success "Python $PYTHON_VERSION found"

# Check if python3-venv is installed
print_status "Checking for python3-venv..."
if ! python3 -m venv --help &> /dev/null; then
    print_warning "python3-venv is not installed"
    echo ""

    # Determine the package name based on distro
    if command -v apt-get &> /dev/null; then
        VENV_PACKAGE="python${PYTHON_VERSION}-venv (or python3-venv)"
        INSTALL_CMD="apt-get install -y python${PYTHON_VERSION}-venv || apt-get install -y python3-venv"
    elif command -v dnf &> /dev/null; then
        VENV_PACKAGE="python3-virtualenv"
        INSTALL_CMD="dnf install -y python3-virtualenv"
    elif command -v yum &> /dev/null; then
        VENV_PACKAGE="python3-virtualenv"
        INSTALL_CMD="yum install -y python3-virtualenv"
    else
        print_error "Could not determine package manager."
        print_error "Please install python3-venv manually and re-run this script."
        exit 1
    fi

    echo -e "  The metrics agent requires ${BLUE}${VENV_PACKAGE}${NC} to create a virtual environment."
    echo ""
    read -p "  Would you like to install it now? [y/N]: " INSTALL_VENV

    if [[ "$INSTALL_VENV" =~ ^[Yy]$ ]]; then
        print_status "Installing python3-venv..."
        if command -v apt-get &> /dev/null; then
            apt-get update -qq
        fi
        eval $INSTALL_CMD
        if ! python3 -m venv --help &> /dev/null; then
            print_error "Failed to install python3-venv"
            exit 1
        fi
        print_success "python3-venv installed"
    else
        print_warning "python3-venv is required for the metrics agent"
        print_warning "The metrics agent will NOT be installed"
        echo ""
        echo "  To install manually, run:"
        echo "    sudo $INSTALL_CMD"
        echo ""
        echo "  Then re-run this installer."
        exit 1
    fi
else
    print_success "python3-venv is available"
fi

# Check if Docker is available
print_status "Checking Docker..."
if ! command -v docker &> /dev/null; then
    print_warning "Docker not found - container metrics will not be available"
else
    if docker ps &> /dev/null; then
        print_success "Docker is available"
    else
        print_warning "Docker is installed but not accessible - check permissions"
    fi
fi

# Stop existing service if running
if systemctl is-active --quiet $SERVICE_NAME; then
    print_status "Stopping existing $SERVICE_NAME service..."
    systemctl stop $SERVICE_NAME
fi

# Create installation directory
print_status "Creating installation directory..."
mkdir -p "$INSTALL_DIR"

# Copy source files
print_status "Copying source files..."
cp -r "$SCRIPT_DIR/n8n_metrics_agent" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/setup.py" "$INSTALL_DIR/"

# Create virtual environment
print_status "Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"

# Install dependencies
print_status "Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip wheel
"$VENV_DIR/bin/pip" install -e "$INSTALL_DIR"

# Generate API key if not exists
API_KEY_FILE="$INSTALL_DIR/.api_key"
if [[ ! -f "$API_KEY_FILE" ]]; then
    print_status "Generating API key..."
    API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    echo "$API_KEY" > "$API_KEY_FILE"
    chmod 600 "$API_KEY_FILE"
    print_success "API key generated and saved to $API_KEY_FILE"
    echo ""
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║${NC} ${GREEN}IMPORTANT: Save this API key for the management console!${NC}         ${YELLOW}║${NC}"
    echo -e "${YELLOW}║${NC}                                                                    ${YELLOW}║${NC}"
    echo -e "${YELLOW}║${NC} API Key: ${BLUE}$API_KEY${NC}"
    echo -e "${YELLOW}║${NC}                                                                    ${YELLOW}║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
else
    API_KEY=$(cat "$API_KEY_FILE")
    print_success "Using existing API key from $API_KEY_FILE"
fi

# Create systemd service with API key
print_status "Installing systemd service..."
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=n8n Metrics Agent - Host-level system metrics collector
Documentation=https://github.com/your-repo/n8n-management
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=root
Group=docker

# Environment configuration
Environment="METRICS_AGENT_HOST=127.0.0.1"
Environment="METRICS_AGENT_PORT=9100"
Environment="METRICS_AGENT_API_KEY=$API_KEY"
Environment="METRICS_LOG_LEVEL=INFO"

# Working directory
WorkingDirectory=$INSTALL_DIR

# Start command
ExecStart=$VENV_DIR/bin/n8n-metrics-agent

# Restart policy
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=false
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true

# Allow access to Docker socket
ReadWritePaths=/var/run/docker.sock

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=n8n-metrics-agent

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
print_status "Reloading systemd..."
systemctl daemon-reload

# Enable and start service
print_status "Enabling and starting service..."
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# Wait and check status
sleep 2
if systemctl is-active --quiet $SERVICE_NAME; then
    print_success "n8n Metrics Agent installed and running!"
    echo ""
    echo "Service status:"
    systemctl status $SERVICE_NAME --no-pager | head -10
    echo ""
    echo "Test the API:"
    echo "  curl http://127.0.0.1:9100/health"
    echo "  curl -H 'X-API-Key: $API_KEY' http://127.0.0.1:9100/metrics"
    echo ""
    echo "View logs:"
    echo "  journalctl -u $SERVICE_NAME -f"
else
    print_error "Service failed to start. Check logs:"
    echo "  journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi
