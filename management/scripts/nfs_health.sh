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
    local is_mounted=$3

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
    update_status "disabled" "NFS not configured" false
    exit 0
fi

if [ ! -d "$MOUNT_POINT" ]; then
    update_status "disconnected" "$MOUNT_POINT does not exist" false
    log_error "$MOUNT_POINT does not exist"
    exit 0
fi

# $MOUNT_POINT is a bind mount of a host directory, so `mountpoint` is always
# true. What matters is the filesystem behind it: NFS/CIFS only when the host
# had the share mounted at that directory when this container started.
# (Mounting from inside the container is not possible: no CAP_SYS_ADMIN.)
FS_TYPE=$(stat -f -c %T "$MOUNT_POINT" 2>/dev/null || echo unknown)
case "$FS_TYPE" in
    nfs*|cifs|smb*|ceph|fuse.glusterfs|fuse.sshfs)
        TEST_FILE="$MOUNT_POINT/.health_check_$$"
        if touch "$TEST_FILE" 2>/dev/null; then
            rm -f "$TEST_FILE"
            update_status "connected" "NFS ($FS_TYPE) mounted and writable" true
            log_info "NFS healthy - $FS_TYPE mounted and writable"
        else
            update_status "degraded" "NFS ($FS_TYPE) mounted but write test failed" true
            log_error "NFS degraded - mounted but not writable"
        fi
        ;;
    *)
        update_status "disconnected" "Share not mounted on the host: $MOUNT_POINT is local storage ($FS_TYPE)" false
        log_error "NFS share ${NFS_SERVER}:${NFS_PATH} is not mounted on the host; $MOUNT_POINT is local storage ($FS_TYPE)"
        ;;
esac
