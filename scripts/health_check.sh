#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /scripts/health_check.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 1st, 2026
#
# Richard J. Sears
# richardjsears@gmail.com
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

#
# health_check.sh - System Health Check Script for n8n_nginx v3.0
# Performs comprehensive health checks on all system components
#

set -e

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_ROOT}/logs/health_check.log"
STATE_FILE="${PROJECT_ROOT}/.health_state"

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
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

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

    local backup_dir="${PROJECT_ROOT}/backups"

    if [ ! -d "$backup_dir" ]; then
        log WARN "Backup directory does not exist"
        HEALTH_STATUS["backups"]="warning"
        return 0
    fi

    # Find most recent backup
    local latest_backup
    latest_backup=$(find "$backup_dir" -maxdepth 1 -type d -name "backup_*" -printf '%T+ %p\n' 2>/dev/null | sort -r | head -1 | cut -d' ' -f2-)

    if [ -z "$latest_backup" ]; then
        log WARN "No backups found"
        HEALTH_STATUS["backups"]="warning"
        return 0
    fi

    # Check backup age
    local backup_age
    backup_age=$(( ($(date +%s) - $(stat -c %Y "$latest_backup" 2>/dev/null || stat -f %m "$latest_backup" 2>/dev/null)) / 86400 ))

    if [ "$backup_age" -gt 7 ]; then
        log WARN "Latest backup is $backup_age days old"
        HEALTH_STATUS["backups"]="warning"
    else
        log OK "Latest backup is $backup_age days old"
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
# Main Execution
# ============================================================================

run_health_checks() {
    echo ""
    echo -e "${CYAN}n8n_nginx v3.0 Health Check${NC}"
    echo "Started: $(date)"
    echo ""

    # Run all health checks
    check_all_containers
    check_n8n_api
    check_postgres_connection
    check_nginx_status
    check_management_api
    check_disk_space
    check_memory_usage
    check_cpu_usage
    check_ssl_certificates
    check_network_connectivity
    check_backup_status
    check_recent_errors

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

EOF
}

# Parse arguments
QUIET_MODE=false
JSON_OUTPUT=false
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
            check_all_containers
            ;;
        n8n)
            check_n8n_api
            ;;
        postgres)
            check_postgres_connection
            ;;
        nginx)
            check_nginx_status
            ;;
        management)
            check_management_api
            ;;
        resources)
            check_disk_space
            check_memory_usage
            check_cpu_usage
            ;;
        ssl)
            check_ssl_certificates
            ;;
        network)
            check_network_connectivity
            ;;
        backups)
            check_backup_status
            ;;
        logs)
            check_recent_errors
            ;;
        *)
            echo "Unknown component: $CHECK_COMPONENT"
            exit 1
            ;;
    esac
    generate_report
else
    run_health_checks
fi

# Restore output if quiet mode was used
if [ "$QUIET_MODE" = true ]; then
    exec 1>&3 2>&4
fi

# Output JSON if requested
if [ "$JSON_OUTPUT" = true ]; then
    cat "$STATE_FILE"
fi

exit $?
