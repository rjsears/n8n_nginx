#!/bin/bash
#
# n8n Metrics Agent Uninstallation Script
#

set -e

INSTALL_DIR="/opt/n8n-metrics-agent"
SERVICE_NAME="n8n-metrics-agent"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[*]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[✗]${NC} This script must be run as root (use sudo)"
    exit 1
fi

echo ""
echo -e "${YELLOW}This will completely remove the n8n Metrics Agent.${NC}"
read -p "Are you sure? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Stop service
if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
    print_status "Stopping service..."
    systemctl stop $SERVICE_NAME
fi

# Disable service
if systemctl is-enabled --quiet $SERVICE_NAME 2>/dev/null; then
    print_status "Disabling service..."
    systemctl disable $SERVICE_NAME
fi

# Remove service file
if [[ -f /etc/systemd/system/$SERVICE_NAME.service ]]; then
    print_status "Removing systemd service..."
    rm /etc/systemd/system/$SERVICE_NAME.service
    systemctl daemon-reload
fi

# Remove installation directory
if [[ -d "$INSTALL_DIR" ]]; then
    print_status "Removing installation directory..."
    rm -rf "$INSTALL_DIR"
fi

print_success "n8n Metrics Agent has been uninstalled."
echo ""
