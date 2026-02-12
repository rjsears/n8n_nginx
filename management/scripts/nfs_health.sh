#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /management/scripts/nfs_health.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 1st, 2026
#
# Richard J. Sears
# richard@n8nmanagement.net
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# NFS Health Check Script
# Monitors NFS connection and updates status file

set -e

NFS_SERVER="${NFS_SERVER:-}"
NFS_PATH="${NFS_PATH:-}"
MOUNT_POINT="${NFS_MOUNT_POINT:-/mnt/backups}"
STATUS_FILE="/app/config/nfs_status.json"
LOG_PREFIX="[NFS-HEALTH]"

log_info() {
    echo "$(date -Iseconds) $LOG_PREFIX INFO: $1"
}

log_error() {
    echo "$(date -Iseconds) $LOG_PREFIX ERROR: $1"
}

update_status() {
    local status=$1
    local message=$2
    local is_mounted="false"

    if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
        is_mounted="true"
    fi

    cat > "$STATUS_FILE" << EOF
{
    "status": "$status",
    "message": "$message",
    "server": "$NFS_SERVER",
    "path": "$NFS_PATH",
    "mount_point": "$MOUNT_POINT",
    "is_mounted": $is_mounted,
    "last_check": "$(date -Iseconds)"
}
EOF
}

# Check if NFS is configured
if [ -z "$NFS_SERVER" ] || [ -z "$NFS_PATH" ]; then
    update_status "disabled" "NFS not configured"
    exit 0
fi

# Check if mount point exists
if [ ! -d "$MOUNT_POINT" ]; then
    mkdir -p "$MOUNT_POINT"
fi

# Check if already mounted
if mountpoint -q "$MOUNT_POINT"; then
    # Test write capability
    TEST_FILE="$MOUNT_POINT/.health_check_$$"
    if touch "$TEST_FILE" 2>/dev/null; then
        rm -f "$TEST_FILE"
        update_status "connected" "NFS mounted and writable"
        log_info "NFS healthy - mounted and writable"
    else
        update_status "degraded" "NFS mounted but write test failed"
        log_error "NFS degraded - mounted but not writable"
    fi
else
    # Attempt to mount
    log_info "NFS not mounted, attempting mount..."

    if mount -t nfs -o rw,nolock,soft,timeo=30,retrans=2 "${NFS_SERVER}:${NFS_PATH}" "$MOUNT_POINT" 2>/dev/null; then
        # Create backup directories if they don't exist
        mkdir -p "$MOUNT_POINT/postgres" 2>/dev/null || true
        mkdir -p "$MOUNT_POINT/n8n_config" 2>/dev/null || true
        mkdir -p "$MOUNT_POINT/flows" 2>/dev/null || true
        mkdir -p "$MOUNT_POINT/verification" 2>/dev/null || true

        update_status "connected" "NFS mounted successfully"
        log_info "NFS mounted successfully"
    else
        update_status "disconnected" "Failed to mount NFS share"
        log_error "Failed to mount NFS share ${NFS_SERVER}:${NFS_PATH}"
    fi
fi
