#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /scripts/health_check.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 1st, 2026
#
# Richard J. Sears
# richard@n8nmanagement.net
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

#
# health_check.sh - System Health Check Script for n8n_nginx v3.0
# Performs comprehensive health checks on all system components
#
# Host-side alerting (--alert): the management console's own notifications
# live in PostgreSQL and run inside n8n_management, so they cannot report
# Postgres or the management container being down. Run this from cron or a
# systemd timer with --alert and it POSTs a plain-text alert to
# ALERT_FALLBACK_URL (environment or .env; an ntfy topic URL works as is)
# when a check fails, repeats every ALERT_REPEAT_MINUTES (default 60) while it
# stays failing, and sends one recovery message when it passes again:
#
#   */5 * * * * /opt/n8n_nginx/scripts/health_check.sh --quiet --alert
#

set -e

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_ROOT}/logs/health_check.log"
STATE_FILE="${PROJECT_ROOT}/.health_state"
ALERT_STATE_FILE="${PROJECT_ROOT}/.health_alert_state"
ENV_FILE="${PROJECT_ROOT}/.env"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Health check results
declare -A HEALTH_STATUS
OVERALL_STATUS="healthy"
WARNINGS=0
ERRORS=0

# ============================================================================
# Utility Functions
# ============================================================================

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date "+%Y-%m-%d %H:%M:%S")

    # Create log directory if needed
    mkdir -p "$(dirname "$LOG_FILE")"

    # Log to file
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"

    # Output to console with colors
    case "$level" in
        INFO)
            echo -e "${BLUE}[INFO]${NC} $message"
            ;;
        OK)
            echo -e "${GREEN}[OK]${NC} $message"
            ;;
        WARN)
            echo -e "${YELLOW}[WARN]${NC} $message"
            WARNINGS=$((WARNINGS + 1))
            ;;
        ERROR)
            echo -e "${RED}[ERROR]${NC} $message"
            ERRORS=$((ERRORS + 1))
            OVERALL_STATUS="unhealthy"
            ;;
        *)
            echo "[$level] $message"
            ;;
    esac
}

# Value of KEY from the environment, else from the project's .env (read, not
# sourced). Surrounding quotes are stripped.
env_value() {
    local key="$1"
    local value="${!key:-}"
    if [ -z "$value" ] && [ -f "$ENV_FILE" ]; then
        value=$(grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2-)
        value="${value%\"}"
        value="${value#\"}"
        value="${value%\'}"
        value="${value#\'}"
    fi
    printf '%s' "$value"
}

section() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

# ============================================================================
# Docker Health Checks
# ============================================================================

check_docker_daemon() {
    log INFO "Checking Docker daemon..."

    if ! command -v docker &> /dev/null; then
        log ERROR "Docker is not installed"
        HEALTH_STATUS["docker_installed"]="error"
        return 1
    fi

    if ! docker info &> /dev/null; then
        log ERROR "Docker daemon is not running"
        HEALTH_STATUS["docker_daemon"]="error"
        return 1
    fi

    log OK "Docker daemon is running"
    HEALTH_STATUS["docker_daemon"]="healthy"
    return 0
}

check_container_status() {
    local container_name="$1"
    local required="${2:-true}"

    log INFO "Checking container: $container_name"

    if ! docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        if [ "$required" = "true" ]; then
            log ERROR "Container $container_name does not exist"
            HEALTH_STATUS["container_${container_name}"]="error"
            return 1
        else
            log WARN "Container $container_name does not exist (optional)"
            HEALTH_STATUS["container_${container_name}"]="missing"
            return 0
        fi
    fi

    local status
    status=$(docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null)

    if [ "$status" = "running" ]; then
        log OK "Container $container_name is running"
        HEALTH_STATUS["container_${container_name}"]="healthy"
        return 0
    else
        log ERROR "Container $container_name is not running (status: $status)"
        HEALTH_STATUS["container_${container_name}"]="error"
        return 1
    fi
}

check_container_health() {
    local container_name="$1"

    log INFO "Checking container health: $container_name"

    if ! docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        return 1
    fi

    local health
    health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_name" 2>/dev/null)

    case "$health" in
        healthy)
            log OK "Container $container_name health check: healthy"
            HEALTH_STATUS["health_${container_name}"]="healthy"
            return 0
            ;;
        unhealthy)
            log ERROR "Container $container_name health check: unhealthy"
            HEALTH_STATUS["health_${container_name}"]="unhealthy"
            return 1
            ;;
        starting)
            log WARN "Container $container_name health check: starting"
            HEALTH_STATUS["health_${container_name}"]="starting"
            return 0
            ;;
        none)
            log INFO "Container $container_name has no health check configured"
            HEALTH_STATUS["health_${container_name}"]="none"
            return 0
            ;;
        *)
            log WARN "Container $container_name health check: $health"
            HEALTH_STATUS["health_${container_name}"]="unknown"
            return 0
            ;;
    esac
}

check_all_containers() {
    section "Docker Container Health"

    check_docker_daemon || return 1

    # Core containers
    check_container_status "n8n" true
    check_container_status "n8n_postgres" true
    check_container_status "n8n_nginx" true

    # v3.0 management container (optional for v2 installations)
    check_container_status "n8n_management" false

    # Health checks for running containers
    for container in n8n n8n_postgres n8n_nginx n8n_management; do
        if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            check_container_health "$container"
        fi
    done
}

# ============================================================================
# Service Health Checks
# ============================================================================

check_n8n_api() {
    section "n8n API Health"

    log INFO "Checking n8n API availability..."

    # Try via nginx container (which can reach n8n on Docker network)
    if docker exec n8n_nginx curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://n8n:5678/healthz" 2>/dev/null | grep -q "^[23]"; then
        log OK "n8n API is responding"
        HEALTH_STATUS["n8n_api"]="healthy"
        return 0
    fi

    # Try via wget in n8n container (n8n image has wget but not curl)
    if docker exec n8n wget -q -O /dev/null --timeout=5 "http://localhost:5678/healthz" 2>/dev/null; then
        log OK "n8n API is responding (via container)"
        HEALTH_STATUS["n8n_api"]="healthy"
        return 0
    fi

    log ERROR "n8n API is not responding"
    HEALTH_STATUS["n8n_api"]="error"
    return 1
}

check_postgres_connection() {
    section "PostgreSQL Health"

    log INFO "Checking PostgreSQL connection..."

    if ! docker ps --format '{{.Names}}' | grep -q "^n8n_postgres$"; then
        log ERROR "PostgreSQL container is not running"
        HEALTH_STATUS["postgres"]="error"
        return 1
    fi

    # Check if PostgreSQL is accepting connections
    if docker exec n8n_postgres pg_isready -U n8n &> /dev/null; then
        log OK "PostgreSQL is accepting connections"
        HEALTH_STATUS["postgres"]="healthy"
    else
        log ERROR "PostgreSQL is not accepting connections"
        HEALTH_STATUS["postgres"]="error"
        return 1
    fi

    # Check n8n database
    if docker exec n8n_postgres psql -U n8n -d n8n -c "SELECT 1" &> /dev/null; then
        log OK "n8n database is accessible"
        HEALTH_STATUS["postgres_n8n_db"]="healthy"
    else
        log ERROR "n8n database is not accessible"
        HEALTH_STATUS["postgres_n8n_db"]="error"
        return 1
    fi

    # Check management database (v3.0)
    if docker exec n8n_postgres psql -U n8n -d n8n_management -c "SELECT 1" &> /dev/null; then
        log OK "Management database is accessible"
        HEALTH_STATUS["postgres_mgmt_db"]="healthy"
    else
        log WARN "Management database is not accessible (may be v2.0 installation)"
        HEALTH_STATUS["postgres_mgmt_db"]="missing"
    fi

    return 0
}

check_nginx_status() {
    section "Nginx Health"

    log INFO "Checking Nginx status..."

    if ! docker ps --format '{{.Names}}' | grep -q "^n8n_nginx$"; then
        log ERROR "Nginx container is not running"
        HEALTH_STATUS["nginx"]="error"
        return 1
    fi

    # Check nginx configuration
    if docker exec n8n_nginx nginx -t &> /dev/null; then
        log OK "Nginx configuration is valid"
        HEALTH_STATUS["nginx_config"]="healthy"
    else
        log ERROR "Nginx configuration is invalid"
        HEALTH_STATUS["nginx_config"]="error"
        return 1
    fi

    # Check if nginx is accepting connections on port 443
    if curl -s -o /dev/null -k --max-time 5 "https://localhost" 2>/dev/null; then
        log OK "Nginx HTTPS is responding"
        HEALTH_STATUS["nginx_https"]="healthy"
    else
        log WARN "Nginx HTTPS may not be accessible externally"
        HEALTH_STATUS["nginx_https"]="warning"
    fi

    return 0
}

check_management_api() {
    section "Management API Health"

    log INFO "Checking Management API..."

    if ! docker ps --format '{{.Names}}' | grep -q "^n8n_management$"; then
        log WARN "Management container is not running (may be v2.0 installation)"
        HEALTH_STATUS["management_api"]="missing"
        return 0
    fi

    # Check management API health endpoint
    local mgmt_url="http://localhost:8000/api/health"

    if docker exec n8n_management curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$mgmt_url" 2>/dev/null | grep -q "^[23]"; then
        log OK "Management API is responding"
        HEALTH_STATUS["management_api"]="healthy"
        return 0
    else
        log ERROR "Management API is not responding"
        HEALTH_STATUS["management_api"]="error"
        return 1
    fi
}

# ============================================================================
# Resource Health Checks
# ============================================================================

check_disk_space() {
    section "Disk Space"

    log INFO "Checking disk space..."

    # Check root partition
    local disk_usage
    disk_usage=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')

    if [ "$disk_usage" -ge 90 ]; then
        log ERROR "Disk usage critical: ${disk_usage}%"
        HEALTH_STATUS["disk_root"]="error"
    elif [ "$disk_usage" -ge 80 ]; then
        log WARN "Disk usage high: ${disk_usage}%"
        HEALTH_STATUS["disk_root"]="warning"
    else
        log OK "Disk usage: ${disk_usage}%"
        HEALTH_STATUS["disk_root"]="healthy"
    fi

    # Check Docker volumes
    local docker_usage
    if command -v docker &> /dev/null; then
        docker_usage=$(docker system df --format '{{.Size}}' 2>/dev/null | head -1)
        log INFO "Docker disk usage: $docker_usage"
    fi
}

check_memory_usage() {
    section "Memory Usage"

    log INFO "Checking memory usage..."

    local mem_total mem_used mem_percent
    mem_total=$(free -m | awk '/^Mem:/ {print $2}')
    mem_used=$(free -m | awk '/^Mem:/ {print $3}')
    mem_percent=$((mem_used * 100 / mem_total))

    if [ "$mem_percent" -ge 90 ]; then
        log ERROR "Memory usage critical: ${mem_percent}% (${mem_used}MB / ${mem_total}MB)"
        HEALTH_STATUS["memory"]="error"
    elif [ "$mem_percent" -ge 80 ]; then
        log WARN "Memory usage high: ${mem_percent}% (${mem_used}MB / ${mem_total}MB)"
        HEALTH_STATUS["memory"]="warning"
    else
        log OK "Memory usage: ${mem_percent}% (${mem_used}MB / ${mem_total}MB)"
        HEALTH_STATUS["memory"]="healthy"
    fi

    # Check container memory usage
    if command -v docker &> /dev/null && docker ps -q &> /dev/null; then
        log INFO "Container memory usage:"
        docker stats --no-stream --format "  {{.Name}}: {{.MemUsage}}" 2>/dev/null || true
    fi
}

check_cpu_usage() {
    section "CPU Usage"

    log INFO "Checking CPU usage..."

    # Get 1-minute load average
    local load_avg
    load_avg=$(cat /proc/loadavg | awk '{print $1}')
    local cpu_count
    cpu_count=$(nproc)
    local load_percent
    load_percent=$(echo "$load_avg $cpu_count" | awk '{printf "%.0f", ($1 / $2) * 100}')

    if [ "$load_percent" -ge 100 ]; then
        log WARN "CPU load high: ${load_avg} (${load_percent}% of capacity)"
        HEALTH_STATUS["cpu"]="warning"
    else
        log OK "CPU load: ${load_avg} (${load_percent}% of capacity)"
        HEALTH_STATUS["cpu"]="healthy"
    fi
}

# ============================================================================
# SSL Certificate Check
# ============================================================================

check_ssl_certificates() {
    section "SSL Certificates"

    log INFO "Checking SSL certificates..."

    # Check if openssl is available on the host
    if ! command -v openssl &> /dev/null; then
        log WARN "openssl not installed - cannot check SSL certificates"
        HEALTH_STATUS["ssl_cert"]="unknown"
        return 0
    fi

    # Check if nginx container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^n8n_nginx$"; then
        log WARN "Nginx container not running - cannot check SSL certificates"
        HEALTH_STATUS["ssl_cert"]="unknown"
        return 0
    fi

    # Get the domain from nginx.conf inside the container
    local domain
    domain=$(docker exec n8n_nginx grep -m1 'ssl_certificate ' /etc/nginx/nginx.conf 2>/dev/null | sed -n 's|.*live/\([^/]*\)/.*|\1|p')

    if [ -z "$domain" ]; then
        log WARN "Cannot determine domain from nginx config"
        HEALTH_STATUS["ssl_cert"]="unknown"
        return 0
    fi

    log INFO "Checking certificate for domain: $domain"

    # Check certificate expiration by connecting to the HTTPS server
    # This works regardless of where the cert files are stored
    local expiry_date
    expiry_date=$(echo | timeout 10 openssl s_client -servername "$domain" -connect localhost:443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)

    if [ -z "$expiry_date" ]; then
        # Fallback: try connecting to the domain directly
        expiry_date=$(echo | timeout 10 openssl s_client -servername "$domain" -connect "${domain}:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
    fi

    if [ -z "$expiry_date" ]; then
        log ERROR "Cannot read SSL certificate from server"
        HEALTH_STATUS["ssl_cert"]="error"
        return 1
    fi

    local expiry_epoch current_epoch days_until_expiry
    expiry_epoch=$(date -d "$expiry_date" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$expiry_date" +%s 2>/dev/null)
    current_epoch=$(date +%s)
    days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))

    if [ "$days_until_expiry" -lt 0 ]; then
        log ERROR "SSL certificate has EXPIRED"
        HEALTH_STATUS["ssl_cert"]="error"
    elif [ "$days_until_expiry" -lt 7 ]; then
        log ERROR "SSL certificate expires in $days_until_expiry days"
        HEALTH_STATUS["ssl_cert"]="error"
    elif [ "$days_until_expiry" -lt 30 ]; then
        log WARN "SSL certificate expires in $days_until_expiry days"
        HEALTH_STATUS["ssl_cert"]="warning"
    else
        log OK "SSL certificate valid for $days_until_expiry days (expires: $expiry_date)"
        HEALTH_STATUS["ssl_cert"]="healthy"
    fi
}

# ============================================================================
# Network Connectivity Check
# ============================================================================

check_network_connectivity() {
    section "Network Connectivity"

    log INFO "Checking network connectivity..."

    # Check DNS resolution
    if host google.com &> /dev/null || nslookup google.com &> /dev/null; then
        log OK "DNS resolution working"
        HEALTH_STATUS["network_dns"]="healthy"
    else
        log ERROR "DNS resolution failed"
        HEALTH_STATUS["network_dns"]="error"
    fi

    # Check internet connectivity (npm registry is used for community nodes)
    if curl -s -o /dev/null --max-time 10 "https://registry.npmjs.org" 2>/dev/null; then
        log OK "Internet connectivity OK (npm registry reachable)"
        HEALTH_STATUS["network_internet"]="healthy"
    else
        log WARN "Cannot reach npm registry (may affect community node updates)"
        HEALTH_STATUS["network_internet"]="warning"
    fi
}

# ============================================================================
# Backup Status Check
# ============================================================================

check_backup_status() {
    section "Backup Status"

    log INFO "Checking backup status..."

    # Backups are recorded in the management database (backup_history); the
    # archives live under the backup mount (/opt/n8n_backups on the host) or
    # in the mgmt_backup_staging volume, never in ${PROJECT_ROOT}/backups.
    local max_age_hours pg_user age_seconds=""
    max_age_hours=$(env_value BACKUP_MAX_AGE_HOURS)
    max_age_hours="${max_age_hours:-192}"
    pg_user=$(env_value POSTGRES_USER)
    pg_user="${pg_user:-n8n}"

    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^n8n_postgres$"; then
        age_seconds=$(docker exec n8n_postgres psql -U "$pg_user" -d n8n_management -tAc \
            "SELECT COALESCE((EXTRACT(EPOCH FROM now() - max(completed_at)))::bigint::text, 'none') FROM backup_history WHERE status = 'success'" \
            2>/dev/null | tr -d '[:space:]') || age_seconds=""
    fi

    if [ -z "$age_seconds" ]; then
        # Database unreachable: fall back to the newest archive on the host mount
        local backup_root newest
        backup_root=$(env_value BACKUP_HOST_DIR)
        backup_root="${backup_root:-/opt/n8n_backups}"
        newest=$(find "$backup_root" -type f \( -name '*.tar.gz' -o -name '*.sql.gz' -o -name '*.sql' \) \
            -printf '%T@\n' 2>/dev/null | sort -rn | head -1)
        if [ -n "$newest" ]; then
            age_seconds=$(( $(date +%s) - ${newest%.*} ))
            log INFO "Backup age taken from files in $backup_root (database not reachable)"
        fi
    fi

    if [ -z "$age_seconds" ] || [ "$age_seconds" = "none" ]; then
        log WARN "No successful backup found"
        HEALTH_STATUS["backups"]="warning"
        return 0
    fi

    local age_hours=$(( age_seconds / 3600 ))
    if [ "$age_hours" -gt "$max_age_hours" ]; then
        log ERROR "Latest successful backup is ${age_hours}h old (limit ${max_age_hours}h, BACKUP_MAX_AGE_HOURS)"
        HEALTH_STATUS["backups"]="error"
    else
        log OK "Latest successful backup is ${age_hours}h old"
        HEALTH_STATUS["backups"]="healthy"
    fi
}

# ============================================================================
# Log Analysis
# ============================================================================

check_recent_errors() {
    section "Recent Error Analysis"

    log INFO "Checking for recent errors in logs..."

    # Check n8n container logs for errors
    if docker ps --format '{{.Names}}' | grep -q "^n8n$"; then
        local error_count
        error_count=$(docker logs n8n --since 1h 2>&1 | grep -ci "error") || error_count=0

        if [ "$error_count" -gt 10 ]; then
            log WARN "n8n: $error_count errors in last hour"
            HEALTH_STATUS["logs_n8n"]="warning"
        else
            log OK "n8n: $error_count errors in last hour"
            HEALTH_STATUS["logs_n8n"]="healthy"
        fi
    fi

    # Check nginx logs
    if docker ps --format '{{.Names}}' | grep -q "^n8n_nginx$"; then
        local nginx_errors
        nginx_errors=$(docker logs n8n_nginx --since 1h 2>&1 | grep -ci "error") || nginx_errors=0

        if [ "$nginx_errors" -gt 50 ]; then
            log WARN "nginx: $nginx_errors errors in last hour"
            HEALTH_STATUS["logs_nginx"]="warning"
        else
            log OK "nginx: $nginx_errors errors in last hour"
            HEALTH_STATUS["logs_nginx"]="healthy"
        fi
    fi
}

# ============================================================================
# Report Generation
# ============================================================================

generate_report() {
    section "Health Check Summary"

    echo ""
    echo "Component Status:"
    echo "-----------------"

    for key in "${!HEALTH_STATUS[@]}"; do
        local status="${HEALTH_STATUS[$key]}"
        local color

        case "$status" in
            healthy)
                color="${GREEN}"
                ;;
            warning|missing|starting)
                color="${YELLOW}"
                ;;
            error|unhealthy)
                color="${RED}"
                ;;
            *)
                color="${NC}"
                ;;
        esac

        printf "  %-30s ${color}%s${NC}\n" "$key:" "$status"
    done

    echo ""
    echo "-----------------"
    echo "Warnings: $WARNINGS"
    echo "Errors: $ERRORS"
    echo ""

    if [ "$OVERALL_STATUS" = "healthy" ] && [ "$WARNINGS" -eq 0 ]; then
        echo -e "${GREEN}Overall Status: HEALTHY${NC}"
    elif [ "$OVERALL_STATUS" = "healthy" ]; then
        echo -e "${YELLOW}Overall Status: HEALTHY (with warnings)${NC}"
    else
        echo -e "${RED}Overall Status: UNHEALTHY${NC}"
    fi
}

save_state() {
    # Save health state to file for monitoring integration
    cat > "$STATE_FILE" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "overall_status": "$OVERALL_STATUS",
    "warnings": $WARNINGS,
    "errors": $ERRORS,
    "components": {
$(for key in "${!HEALTH_STATUS[@]}"; do echo "        \"$key\": \"${HEALTH_STATUS[$key]}\","; done | sed '$ s/,$//')
    }
}
EOF
}

# ============================================================================
# Host-side alerting (--alert)
# ============================================================================

send_alert() {
    local title="$1" body="$2" priority="$3" url
    url=$(env_value ALERT_FALLBACK_URL)
    if [ -z "$url" ]; then
        log WARN "ALERT_FALLBACK_URL is not set; cannot send alert: $title"
        return 1
    fi
    if curl -fsS --max-time 15 \
        -H "Title: $title" -H "Priority: $priority" -H "Tags: rotating_light" \
        --data-binary "$body" "$url" > /dev/null 2>&1; then
        log INFO "Alert sent: $title"
        return 0
    fi
    log WARN "Could not deliver alert to ALERT_FALLBACK_URL: $title"
    return 1
}

# Alert when any component is in error; repeat while it stays failing, and
# announce the recovery once.
process_alerts() {
    local repeat_minutes failing="" key previous="" last_sent=0 now host
    repeat_minutes=$(env_value ALERT_REPEAT_MINUTES)
    repeat_minutes="${repeat_minutes:-60}"
    for key in "${!HEALTH_STATUS[@]}"; do
        case "${HEALTH_STATUS[$key]}" in
            error|unhealthy) failing="${failing}${key} " ;;
        esac
    done
    if [ "$ERRORS" -gt 0 ] && [ -z "$failing" ]; then
        failing="(see ${LOG_FILE})"
    fi

    if [ -f "$ALERT_STATE_FILE" ]; then
        read -r previous last_sent < "$ALERT_STATE_FILE" || true
    fi
    now=$(date +%s)
    host=$(hostname 2>/dev/null || echo "host")

    if [ -n "$failing" ]; then
        if [ "$previous" != "down" ] || [ $(( now - ${last_sent:-0} )) -ge $(( repeat_minutes * 60 )) ]; then
            if send_alert "[$host] n8n stack UNHEALTHY" \
                "Failing: ${failing}
Errors: ${ERRORS}, warnings: ${WARNINGS}
Checked: $(date '+%Y-%m-%d %H:%M:%S %Z')
Details: ${LOG_FILE}" 5; then
                echo "down $now" > "$ALERT_STATE_FILE"
            fi
        fi
    elif [ "$previous" = "down" ]; then
        if send_alert "[$host] n8n stack recovered" \
            "All checks pass again ($(date '+%Y-%m-%d %H:%M:%S %Z'))." 3; then
            echo "up $now" > "$ALERT_STATE_FILE"
        fi
    fi
}

# ============================================================================
# Main Execution
# ============================================================================

run_health_checks() {
    echo ""
    echo -e "${CYAN}n8n_nginx v3.0 Health Check${NC}"
    echo "Started: $(date)"
    echo ""

    # Run all health checks. A failing check returns 1; "|| true" keeps
    # set -e from stopping the sweep (and the report and alert) at the first.
    check_all_containers || true
    check_n8n_api || true
    check_postgres_connection || true
    check_nginx_status || true
    check_management_api || true
    check_disk_space || true
    check_memory_usage || true
    check_cpu_usage || true
    check_ssl_certificates || true
    check_network_connectivity || true
    check_backup_status || true
    check_recent_errors || true

    # Generate report
    generate_report

    # Save state
    save_state

    # Return appropriate exit code
    if [ "$OVERALL_STATUS" = "healthy" ]; then
        return 0
    else
        return 1
    fi
}

# ============================================================================
# CLI Interface
# ============================================================================

show_help() {
    cat << EOF
n8n_nginx Health Check Script v3.0

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -q, --quiet             Quiet mode (only show errors)
    -j, --json              Output in JSON format
    -a, --alert             POST an alert to ALERT_FALLBACK_URL when a check fails
                            (and a recovery message when it passes again)
    --check COMPONENT       Check specific component only

Components:
    docker                  Check Docker containers
    n8n                     Check n8n API
    postgres                Check PostgreSQL
    nginx                   Check Nginx
    management              Check Management API
    resources               Check system resources
    ssl                     Check SSL certificates
    network                 Check network connectivity
    backups                 Check backup status
    logs                    Check recent errors

Examples:
    $0                      Run all health checks
    $0 --check docker       Check only Docker containers
    $0 -j                   Output results in JSON format
    $0 --quiet --alert      Cron/systemd timer: alert via ALERT_FALLBACK_URL

EOF
}

# Parse arguments
QUIET_MODE=false
JSON_OUTPUT=false
ALERT_MODE=false
CHECK_COMPONENT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -q|--quiet)
            QUIET_MODE=true
            shift
            ;;
        -j|--json)
            JSON_OUTPUT=true
            shift
            ;;
        -a|--alert)
            ALERT_MODE=true
            shift
            ;;
        --check)
            CHECK_COMPONENT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Redirect output if quiet mode
if [ "$QUIET_MODE" = true ]; then
    exec 3>&1 4>&2
    exec 1>/dev/null 2>&1
fi

# Run specific component or all checks
if [ -n "$CHECK_COMPONENT" ]; then
    case "$CHECK_COMPONENT" in
        docker)
            check_all_containers || true
            ;;
        n8n)
            check_n8n_api || true
            ;;
        postgres)
            check_postgres_connection || true
            ;;
        nginx)
            check_nginx_status || true
            ;;
        management)
            check_management_api || true
            ;;
        resources)
            check_disk_space || true
            check_memory_usage || true
            check_cpu_usage || true
            ;;
        ssl)
            check_ssl_certificates || true
            ;;
        network)
            check_network_connectivity || true
            ;;
        backups)
            check_backup_status || true
            ;;
        logs)
            check_recent_errors || true
            ;;
        *)
            echo "Unknown component: $CHECK_COMPONENT"
            exit 1
            ;;
    esac
    generate_report
else
    run_health_checks || true
fi

if [ "$ALERT_MODE" = true ]; then
    process_alerts || true
fi

# Restore output if quiet mode was used
if [ "$QUIET_MODE" = true ]; then
    exec 1>&3 2>&4
fi

# Output JSON if requested
if [ "$JSON_OUTPUT" = true ]; then
    cat "$STATE_FILE"
fi

if [ "$OVERALL_STATUS" = "healthy" ]; then
    exit 0
fi
exit 1
