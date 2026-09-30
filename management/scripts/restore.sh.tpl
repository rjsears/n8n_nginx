#!/usr/bin/env bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /restore.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 2026
#
# Richard J. Sears
# richard@n8nmanagement.net
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# ============================================================================
# n8n Bare Metal Recovery Script
# ============================================================================
# Generated automatically by n8n Management Console
# (template: management/scripts/restore.sh.tpl)
#
# This script performs a COMPLETE bare metal restore of an n8n installation
# from an extracted backup archive (metadata.json, config/, databases/, ssl/).
#
# It can also be downloaded on its own from the management console
# (Backups > Bare Metal > "Download latest restore.sh") and copied over the
# restore.sh inside an OLDER archive before running it.
#
# Order of operations:
#   1. Pre-flight checks (backup contents, OS, system requirements, utilities)
#   2. Docker / Docker Compose
#   3. Configuration files (including dotfiles such as .env)
#   4. DNS / NFS validation
#   5. Docker volumes and SSL certificates (full /etc/letsencrypt tree with
#      symlinks preserved, so certbot can keep renewing)
#   6. Public website files
#   7. Start ONLY the postgres service, wait for it to accept connections
#      and restore each database with pg_restore (single transaction, stops on
#      the first error) - nothing else is running against the databases
#   8. Start the rest of the stack
#   9. Health checks
#
# Any failing command aborts the script and reports the line that failed.
# ============================================================================

set -Eeuo pipefail
shopt -s nullglob

RESTORE_SCRIPT_VERSION="__RESTORE_SCRIPT_VERSION__"

# ============================================================================
# Configuration
# ============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Default values
TARGET_DIR="/opt/n8n"
SKIP_DOCKER=false
SKIP_SSL=false
SKIP_DB=false
SKIP_CONFIG=false
SKIP_NFS=false
SKIP_PUBLIC_WEBSITE=false
SKIP_DNS_CHECK=false
SKIP_SYSTEM_CHECK=false
DRY_RUN=false
FORCE=false
AUTO_MODE=false

# Minimum requirements
MIN_DISK_GB=5
MIN_RAM_MB=2048

# How long to wait for PostgreSQL (attempts x 2 seconds)
PG_READY_ATTEMPTS=60

# Database settings (overridden from the backup's .env in Step 4)
PG_USER="n8n"
PG_DB="n8n"
MGMT_USER="n8n_mgmt"

# Detected values
DISTRO=""
DISTRO_FAMILY=""
PKG_MANAGER=""

# Get script directory (where backup was extracted)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================================
# Error handling
# ============================================================================

on_error() {
    local exit_code="$1"
    local line="$2"
    local cmd="$3"
    echo "" >&2
    echo -e "${RED}[FATAL]${NC} restore.sh aborted at line ${line} (exit code ${exit_code}): ${cmd}" >&2
    echo -e "${RED}[FATAL]${NC} The restore did NOT complete. Fix the problem shown above and re-run the script." >&2
}
trap 'on_error "$?" "$LINENO" "$BASH_COMMAND"' ERR

# ============================================================================
# Helper Functions
# ============================================================================

usage() {
    cat <<'EOF'
Usage: ./restore.sh [options]

Options:
  --target-dir DIR       Directory to restore to (default: /opt/n8n)
  --skip-docker          Skip Docker installation check
  --skip-ssl             Skip SSL certificate restoration
  --skip-db              Skip database restoration
  --skip-config          Skip config file restoration
  --skip-nfs             Skip NFS setup even if configured in backup
  --skip-public-website  Skip public website restoration
  --skip-dns-check       Skip DNS validation (use with caution)
  --skip-system-check    Skip system requirements check
  --dry-run              Show what would be done without making changes
  --force                Skip all confirmation prompts
  --auto                 Fully automatic mode (implies --force)
  --version              Print the restore script version
  -h, --help             Show this help message
EOF
}

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
log_step() { echo -e "\n${MAGENTA}═══ $1 ═══${NC}"; }
dry_run_note() { echo -e "${CYAN}  [DRY-RUN] $1${NC}"; }

run_cmd() {
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${CYAN}  [DRY-RUN] Would run:${NC} $*"
        return 0
    fi
    "$@"
}

run_privileged() {
    if [[ $EUID -eq 0 ]]; then
        "$@"
    elif command -v sudo &>/dev/null; then
        sudo "$@"
    else
        log_error "Need root privileges but sudo not available"
        exit 1
    fi
}

confirm() {
    if [[ "$FORCE" == "true" ]]; then
        return 0
    fi
    local response=""
    read -r -p "$1 [y/N] " response || true
    [[ "$response" =~ ^[Yy]$ ]]
}

command_exists() {
    command -v "$1" &>/dev/null
}

# Docker Compose wrapper (plugin or standalone)
compose() {
    if docker compose version &>/dev/null; then
        docker compose "$@"
    elif command_exists docker-compose; then
        docker-compose "$@"
    else
        log_error "Docker Compose not found"
        return 1
    fi
}

# Read KEY from a dotenv file without sourcing it (values may contain
# characters that are not valid shell).
env_get() {
    local file="$1"
    local key="$2"
    local value=""
    [[ -f "$file" ]] || return 0
    value=$(grep -E "^[[:space:]]*(export[[:space:]]+)?${key}=" "$file" | tail -n 1 | cut -d= -f2- || true)
    value="${value%$'\r'}"
    if [[ "$value" =~ ^\"(.*)\"$ ]] || [[ "$value" =~ ^\'(.*)\'$ ]]; then
        value="${BASH_REMATCH[1]}"
    fi
    printf '%s' "$value"
}

# Read a top-level key from metadata.json
meta_get() {
    local key="$1"
    local default="$2"
    local value=""
    if command_exists python3; then
        value=$(python3 -c 'import json,sys; v=json.load(open(sys.argv[1])).get(sys.argv[2]); print("" if v is None else v)' \
            "$SCRIPT_DIR/metadata.json" "$key" 2>/dev/null || true)
    elif command_exists jq; then
        value=$(jq -r --arg k "$key" '.[$k] // empty' "$SCRIPT_DIR/metadata.json" 2>/dev/null || true)
    fi
    printf '%s' "${value:-$default}"
}

# Check if running in LXC container
is_lxc_container() {
    if command_exists systemd-detect-virt && [[ "$(systemd-detect-virt 2>/dev/null || true)" == "lxc" ]]; then
        return 0
    fi
    if grep -qa 'container=lxc' /proc/1/environ 2>/dev/null; then
        return 0
    fi
    if [[ -f /run/host/container-manager ]]; then
        return 0
    fi
    return 1
}

# ============================================================================
# Argument Parsing
# ============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --target-dir)
                if [[ $# -lt 2 ]] || [[ -z "$2" ]]; then
                    log_error "--target-dir requires a directory"
                    exit 1
                fi
                TARGET_DIR="$2"; shift 2 ;;
            --skip-docker) SKIP_DOCKER=true; shift ;;
            --skip-ssl) SKIP_SSL=true; shift ;;
            --skip-db) SKIP_DB=true; shift ;;
            --skip-config) SKIP_CONFIG=true; shift ;;
            --skip-nfs) SKIP_NFS=true; shift ;;
            --skip-public-website) SKIP_PUBLIC_WEBSITE=true; shift ;;
            --skip-dns-check) SKIP_DNS_CHECK=true; shift ;;
            --skip-system-check) SKIP_SYSTEM_CHECK=true; shift ;;
            --dry-run) DRY_RUN=true; shift ;;
            --force) FORCE=true; shift ;;
            --auto) AUTO_MODE=true; FORCE=true; shift ;;
            --version) echo "restore.sh version ${RESTORE_SCRIPT_VERSION}"; exit 0 ;;
            -h|--help) usage; exit 0 ;;
            *) log_error "Unknown option: $1"; usage; exit 1 ;;
        esac
    done
}

# ============================================================================
# OS Detection
# ============================================================================

detect_os() {
    if [[ -f /etc/os-release ]]; then
        local ID=""
        # shellcheck source=/dev/null
        . /etc/os-release
        DISTRO="${ID:-unknown}"
        case "$DISTRO" in
            ubuntu|debian|linuxmint|pop|raspbian)
                DISTRO_FAMILY="debian"; PKG_MANAGER="apt-get" ;;
            centos|rhel|fedora|rocky|almalinux)
                DISTRO_FAMILY="rhel"
                if command_exists dnf; then PKG_MANAGER="dnf"; else PKG_MANAGER="yum"; fi ;;
            alpine)
                DISTRO_FAMILY="alpine"; PKG_MANAGER="apk" ;;
            *)
                DISTRO_FAMILY="unknown"
                if command_exists apt-get; then PKG_MANAGER="apt-get"
                elif command_exists dnf; then PKG_MANAGER="dnf"
                elif command_exists yum; then PKG_MANAGER="yum"
                fi ;;
        esac
    elif [[ -f /etc/debian_version ]]; then
        DISTRO="debian"; DISTRO_FAMILY="debian"; PKG_MANAGER="apt-get"
    elif [[ -f /etc/redhat-release ]]; then
        DISTRO="rhel"; DISTRO_FAMILY="rhel"; PKG_MANAGER="yum"
    fi

    log_info "Detected OS: ${DISTRO:-unknown} (family: ${DISTRO_FAMILY:-unknown})"
}

pkg_update() {
    case "$PKG_MANAGER" in
        apt-get) run_privileged apt-get update -qq ;;
        dnf|yum) run_privileged "$PKG_MANAGER" check-update || true ;;
        apk) run_privileged apk update -q ;;
        *) log_warning "No supported package manager detected"; return 1 ;;
    esac
}

pkg_install() {
    case "$PKG_MANAGER" in
        apt-get) run_privileged apt-get install -y -qq "$@" ;;
        dnf|yum) run_privileged "$PKG_MANAGER" install -y -q "$@" ;;
        apk) run_privileged apk add -q "$@" ;;
        *) log_warning "No supported package manager detected"; return 1 ;;
    esac
}

# ============================================================================
# System Requirement Checks
# ============================================================================

check_system_requirements() {
    log_info "Checking system requirements..."
    local all_passed=true
    local available_gb="" total_ram_mb=""

    # Check disk space
    available_gb=$(df -BG "$SCRIPT_DIR" 2>/dev/null | awk 'NR==2 {print $4}' | tr -d 'G' || true)
    if [[ "$available_gb" =~ ^[0-9]+$ ]] && [[ "$available_gb" -ge "$MIN_DISK_GB" ]]; then
        log_success "Disk space: ${available_gb}GB available (${MIN_DISK_GB}GB required)"
    else
        log_warning "Disk space: ${available_gb:-unknown}GB available (${MIN_DISK_GB}GB required)"
        all_passed=false
    fi

    # Check memory
    total_ram_mb=$(free -m 2>/dev/null | awk '/^Mem:/ {print $2}' || true)
    if [[ "$total_ram_mb" =~ ^[0-9]+$ ]] && [[ "$total_ram_mb" -ge "$MIN_RAM_MB" ]]; then
        log_success "Memory: ${total_ram_mb}MB available (${MIN_RAM_MB}MB required)"
    else
        log_warning "Memory: ${total_ram_mb:-unknown}MB available (${MIN_RAM_MB}MB required)"
        all_passed=false
    fi

    # Check internet connectivity (needed for Docker image pulls)
    log_info "Checking internet connectivity..."
    if ping -c 1 -W 5 8.8.8.8 &>/dev/null || ping -c 1 -W 5 1.1.1.1 &>/dev/null; then
        log_success "Internet connectivity available"
    else
        log_warning "Cannot reach internet - Docker image pulls may fail"
        all_passed=false
    fi

    if is_lxc_container; then
        log_warning "Running inside LXC container - some features may require special configuration"
    fi

    if [[ "$all_passed" != "true" ]]; then
        log_warning "Some system requirements not met"
        if ! confirm "Continue anyway?"; then
            exit 1
        fi
    fi
}

# ============================================================================
# Package Installation Functions
# ============================================================================

install_base_utilities() {
    log_info "Checking base utilities..."

    local missing=()
    local tool
    for tool in curl git openssl jq; do
        command_exists "$tool" || missing+=("$tool")
    done

    if [[ ${#missing[@]} -eq 0 ]]; then
        log_success "All base utilities already installed"
        return 0
    fi

    log_info "Installing missing utilities: ${missing[*]}"

    if [[ "$DRY_RUN" == "true" ]]; then
        dry_run_note "Would install: ${missing[*]}"
        return 0
    fi

    pkg_update || true
    pkg_install "${missing[@]}" || true

    local failed=()
    for tool in "${missing[@]}"; do
        command_exists "$tool" || failed+=("$tool")
    done

    if [[ ${#failed[@]} -gt 0 ]]; then
        log_warning "Failed to install: ${failed[*]} (may not be critical)"
    else
        log_success "Base utilities installed"
    fi
}

install_docker() {
    log_info "Installing Docker..."

    case "$DISTRO_FAMILY" in
        debian)
            run_privileged apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
            run_privileged apt-get update
            run_privileged apt-get install -y ca-certificates curl gnupg lsb-release
            run_privileged install -m 0755 -d /etc/apt/keyrings
            curl -fsSL "https://download.docker.com/linux/${DISTRO}/gpg" | run_privileged gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
            run_privileged chmod a+r /etc/apt/keyrings/docker.gpg
            local codename
            # shellcheck source=/dev/null
            codename=$(. /etc/os-release && echo "${VERSION_CODENAME:-}")
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${DISTRO} ${codename} stable" | \
                run_privileged tee /etc/apt/sources.list.d/docker.list > /dev/null
            run_privileged apt-get update
            run_privileged apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
        rhel)
            run_privileged "$PKG_MANAGER" remove -y docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine 2>/dev/null || true
            run_privileged "$PKG_MANAGER" install -y yum-utils
            run_privileged yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            run_privileged "$PKG_MANAGER" install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
        *)
            log_error "Unsupported distribution for automatic Docker installation: ${DISTRO}"
            log_info "Please install Docker manually: https://docs.docker.com/engine/install/"
            exit 1
            ;;
    esac

    run_privileged systemctl start docker
    run_privileged systemctl enable docker

    if [[ -n "${SUDO_USER:-}" ]] && [[ "${SUDO_USER}" != "root" ]]; then
        run_privileged usermod -aG docker "$SUDO_USER"
        log_warning "Added $SUDO_USER to docker group. You may need to log out and back in."
    fi

    if docker --version &>/dev/null; then
        log_success "Docker installed successfully: $(docker --version)"
    else
        log_error "Docker installation failed"
        exit 1
    fi
}

install_nfs_client() {
    log_info "Installing NFS client..."
    case "$DISTRO_FAMILY" in
        debian) pkg_install nfs-common ;;
        rhel|alpine) pkg_install nfs-utils ;;
        *)
            log_error "Cannot install NFS client for this distribution"
            return 1
            ;;
    esac
    log_success "NFS client installed"
}

# ============================================================================
# Validation Functions
# ============================================================================

validate_dns() {
    local domain="$1"
    local expected_ip="$2"

    if [[ "$SKIP_DNS_CHECK" == "true" ]]; then
        log_warning "Skipping DNS validation (--skip-dns-check)"
        return 0
    fi

    if [[ -z "$domain" ]]; then
        log_warning "Cannot validate DNS - domain not set in backup"
        return 0
    fi

    log_info "Validating DNS configuration for: $domain"

    local server_ips=""
    server_ips=$(hostname -I 2>/dev/null || ip addr show 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 | tr '\n' ' ' || true)
    log_info "This server's IP addresses: ${server_ips:-unknown}"

    local resolved_ip=""
    if command_exists dig; then
        resolved_ip=$(dig +short "$domain" 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)
    elif command_exists getent; then
        resolved_ip=$(getent hosts "$domain" 2>/dev/null | awk '{print $1}' | head -1 || true)
    elif command_exists host; then
        resolved_ip=$(host "$domain" 2>/dev/null | grep 'has address' | awk '{print $4}' | head -1 || true)
    elif command_exists nslookup; then
        resolved_ip=$(nslookup "$domain" 2>/dev/null | grep -A1 'Name:' | grep 'Address:' | awk '{print $2}' | head -1 || true)
    fi

    if [[ -z "$resolved_ip" ]]; then
        log_error "Cannot resolve domain: $domain"
        echo ""
        echo -e "  ${YELLOW}This could mean:${NC}"
        echo -e "    - The DNS record hasn't been created yet"
        echo -e "    - The DNS hasn't propagated yet"
        echo -e "    - The domain name is incorrect"
        echo ""
        if ! confirm "Continue anyway? (NOT RECOMMENDED - services will likely fail)"; then
            exit 1
        fi
        return 1
    fi

    log_info "Domain $domain resolves to: $resolved_ip"

    local ip
    for ip in $server_ips; do
        if [[ "$ip" == "$resolved_ip" ]]; then
            log_success "DNS validated: $domain -> $resolved_ip (matches this server)"
            return 0
        fi
    done

    log_error "DNS MISMATCH DETECTED!"
    echo ""
    echo -e "  ${RED}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "  ${RED}║                              WARNING                                      ║${NC}"
    echo -e "  ${RED}║  The domain does NOT point to this server!                                ║${NC}"
    echo -e "  ${RED}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${YELLOW}Domain $domain resolves to: ${WHITE}$resolved_ip${NC}"
    echo -e "  ${YELLOW}This server's IPs are:      ${WHITE}$server_ips${NC}"
    if [[ -n "$expected_ip" ]]; then
        echo -e "  ${YELLOW}Original server IP was:     ${WHITE}$expected_ip${NC}"
    fi
    echo ""
    echo -e "  ${YELLOW}This will cause the n8n stack to fail because:${NC}"
    echo -e "    - SSL certificate validation will fail"
    echo -e "    - Webhooks won't reach this server"
    echo -e "    - The n8n UI won't be accessible"
    echo ""
    echo -e "  ${WHITE}To fix this, update your DNS records to point $domain to one of:${NC}"
    for ip in $server_ips; do
        echo -e "    ${CYAN}$ip${NC}"
    done
    echo ""
    if ! confirm "Continue anyway? (Services will likely NOT work)"; then
        exit 1
    fi
    return 1
}

validate_backup_contents() {
    log_info "Validating backup contents..."
    local valid=true

    if [[ ! -f "$SCRIPT_DIR/metadata.json" ]]; then
        log_error "metadata.json not found in $SCRIPT_DIR - is this a valid extracted backup?"
        return 1
    fi
    log_success "metadata.json found"

    if [[ ! -d "$SCRIPT_DIR/config" ]]; then
        log_warning "config directory not found in backup"
        valid=false
    else
        log_success "config directory found"
    fi

    if [[ -f "$SCRIPT_DIR/config/docker-compose.yaml" ]]; then
        log_success "docker-compose.yaml found in backup"
    elif [[ -f "$SCRIPT_DIR/config/docker-compose.yml" ]]; then
        log_success "docker-compose.yml found in backup"
    else
        log_error "docker-compose.yaml NOT found in backup - cannot start services"
        valid=false
    fi

    if [[ -f "$SCRIPT_DIR/config/.env" ]]; then
        log_success ".env file found in backup"
    else
        log_warning ".env file not found in backup - services may not start correctly"
        valid=false
    fi

    if [[ -d "$SCRIPT_DIR/databases" ]]; then
        local dumps=("$SCRIPT_DIR"/databases/*.dump)
        if [[ ${#dumps[@]} -gt 0 ]]; then
            log_success "Found ${#dumps[@]} database dump(s)"
        else
            log_warning "databases directory exists but no .dump files found"
        fi
    else
        log_warning "databases directory not found in backup"
    fi

    if [[ -d "$SCRIPT_DIR/letsencrypt/live" ]]; then
        log_success "Found full letsencrypt tree (renewable certificate lineages)"
    elif [[ -d "$SCRIPT_DIR/ssl" ]]; then
        local ssl_dirs=("$SCRIPT_DIR"/ssl/*/)
        if [[ ${#ssl_dirs[@]} -gt 0 ]]; then
            log_success "Found SSL certificates for ${#ssl_dirs[@]} domain(s)"
        fi
    fi

    if [[ -d "$SCRIPT_DIR/public_website" ]]; then
        local pw_count
        pw_count=$(find "$SCRIPT_DIR/public_website" -type f | wc -l)
        if [[ "$pw_count" -gt 0 ]]; then
            log_success "Found public website files ($pw_count files)"
        fi
    fi

    if [[ "$valid" != "true" ]]; then
        log_warning "Some backup components are missing"
        if ! confirm "Continue anyway?"; then
            exit 1
        fi
    fi
    return 0
}

# ============================================================================
# NFS Setup
# ============================================================================

setup_nfs() {
    local nfs_server="$1"
    local nfs_path="$2"
    local nfs_local_mount="$3"

    if [[ -z "$nfs_server" ]] || [[ -z "$nfs_path" ]]; then
        log_info "NFS not configured in backup - skipping"
        return 0
    fi

    if [[ "$SKIP_NFS" == "true" ]]; then
        log_warning "Skipping NFS setup (--skip-nfs)"
        return 0
    fi

    log_info "Setting up NFS: $nfs_server:$nfs_path -> $nfs_local_mount"

    if ! command_exists mount.nfs && ! command_exists mount.nfs4; then
        if [[ "$DRY_RUN" != "true" ]]; then
            if ! install_nfs_client; then
                log_error "Failed to install NFS client"
                return 1
            fi
        else
            dry_run_note "Would install NFS client"
        fi
    fi

    log_info "Testing connectivity to NFS server: $nfs_server"
    if ! ping -c 1 -W 5 "$nfs_server" &>/dev/null; then
        log_error "Cannot reach NFS server: $nfs_server"
        if ! confirm "Continue without NFS?"; then
            exit 1
        fi
        return 1
    fi
    log_success "NFS server is reachable"

    if [[ "$DRY_RUN" == "true" ]]; then
        dry_run_note "Would create mount point: $nfs_local_mount"
        dry_run_note "Would add to /etc/fstab: $nfs_server:$nfs_path $nfs_local_mount nfs defaults,_netdev 0 0"
        dry_run_note "Would mount NFS share"
        return 0
    fi

    run_privileged mkdir -p "$nfs_local_mount" || return 1

    if grep -qs "${nfs_server}:${nfs_path}" /etc/fstab; then
        log_info "NFS entry already exists in /etc/fstab"
    else
        echo "${nfs_server}:${nfs_path} ${nfs_local_mount} nfs defaults,_netdev 0 0" | run_privileged tee -a /etc/fstab > /dev/null || return 1
        log_success "Added NFS mount to /etc/fstab"
    fi

    if grep -qs " ${nfs_local_mount} " /proc/mounts; then
        log_info "NFS already mounted at $nfs_local_mount"
    else
        if run_privileged mount "$nfs_local_mount" 2>/dev/null || \
           run_privileged mount -t nfs -o rw,nolock,soft "$nfs_server:$nfs_path" "$nfs_local_mount"; then
            log_success "NFS share mounted at $nfs_local_mount"
        else
            log_error "Failed to mount NFS share"
            return 1
        fi
    fi

    if touch "${nfs_local_mount}/.restore_test" 2>/dev/null; then
        rm -f "${nfs_local_mount}/.restore_test"
        log_success "NFS share is writable"
    else
        log_warning "NFS share may not be writable"
    fi
    return 0
}

# ============================================================================
# Database helpers (run inside the postgres container, so the pg_restore
# version always matches the server and no host client is needed)
# ============================================================================

wait_for_postgres() {
    local attempt=0
    log_info "Waiting for PostgreSQL to accept connections..."
    until compose exec -T postgres pg_isready -U "$PG_USER" -d "$PG_DB" &>/dev/null; do
        attempt=$((attempt + 1))
        if [[ $attempt -ge $PG_READY_ATTEMPTS ]]; then
            log_error "PostgreSQL did not become ready after $((PG_READY_ATTEMPTS * 2)) seconds"
            compose logs --tail 50 postgres || true
            return 1
        fi
        sleep 2
    done
    log_success "PostgreSQL is ready"
}

psql_postgres() {
    # Run SQL against the maintenance database; stops on the first error.
    compose exec -T postgres psql -v ON_ERROR_STOP=1 -X -q -t -A -U "$PG_USER" -d postgres "$@"
}

db_restore_failed() {
    log_error "$1"
    log_error "Database restore failed. The remaining services have NOT been started."
    log_error "Fix the problem and re-run: $0 --target-dir $TARGET_DIR --skip-config"
    exit 1
}

restore_one_database() {
    local dump_file="$1"
    local db_name
    db_name=$(basename "$dump_file" .dump)

    if [[ ! "$db_name" =~ ^[A-Za-z0-9_]+$ ]]; then
        db_restore_failed "Refusing to restore database with unexpected name: $db_name"
    fi

    log_info "Restoring database: $db_name ($(du -h "$dump_file" | cut -f1))"

    local exists=""
    exists=$(psql_postgres -c "SELECT 1 FROM pg_database WHERE datname = '${db_name}'") || \
        db_restore_failed "Could not query PostgreSQL for database $db_name"
    if [[ "$exists" != "1" ]]; then
        log_info "Creating database $db_name"
        psql_postgres -c "CREATE DATABASE \"${db_name}\"" || \
            db_restore_failed "Could not create database $db_name"
    fi

    local container_id=""
    container_id=$(compose ps -q postgres) || true
    if [[ -z "$container_id" ]]; then
        db_restore_failed "Cannot find the running postgres container"
    fi

    # Copy the dump into the container: pg_restore needs a seekable file
    # for custom-format archives.
    local in_container="/tmp/restore_${db_name}.dump"
    docker cp "$dump_file" "${container_id}:${in_container}" || \
        db_restore_failed "Could not copy $dump_file into the postgres container"

    local rc=0
    compose exec -T postgres pg_restore \
        -U "$PG_USER" \
        -d "$db_name" \
        --clean --if-exists \
        --no-owner --no-acl \
        --exit-on-error \
        --single-transaction \
        "$in_container" || rc=$?

    compose exec -T postgres rm -f "$in_container" || true

    if [[ $rc -ne 0 ]]; then
        db_restore_failed "pg_restore FAILED for $db_name (exit code $rc). It ran in a single transaction, so $db_name was left as it was before this step."
    fi

    # The dumps are taken with --no-owner/--no-acl. Give the management
    # console's own role access to its restored tables again.
    if [[ "$db_name" == "n8n_management" ]]; then
        local role_exists=""
        role_exists=$(psql_postgres -c "SELECT 1 FROM pg_roles WHERE rolname = '${MGMT_USER}'") || true
        if [[ "$role_exists" == "1" ]]; then
            compose exec -T postgres psql -v ON_ERROR_STOP=1 -X -q -U "$PG_USER" -d "$db_name" \
                -c "GRANT ALL ON SCHEMA public TO \"${MGMT_USER}\";" \
                -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO \"${MGMT_USER}\";" \
                -c "GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO \"${MGMT_USER}\";" || \
                db_restore_failed "Could not grant privileges on $db_name to $MGMT_USER"
            log_success "Granted privileges on $db_name to role $MGMT_USER"
        else
            log_warning "Role $MGMT_USER does not exist - the management console may not be able to connect"
        fi
    fi

    log_success "Database $db_name restored"
}

# ============================================================================
# Main
# ============================================================================

main() {
    parse_args "$@"

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║               n8n Bare Metal Recovery Script                         ║${NC}"
    echo -e "${GREEN}║                   Complete System Restoration                        ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo "  restore.sh version: ${RESTORE_SCRIPT_VERSION}"
    echo ""

    # ========================================================================
    # Step 0: Pre-flight Checks
    # ========================================================================
    log_step "Step 0: Pre-flight Checks"

    if [[ $EUID -ne 0 ]]; then
        log_warning "This script should be run as root for full functionality"
        if ! confirm "Continue as non-root user?"; then
            log_info "Please run with: sudo $0"
            exit 1
        fi
    fi

    detect_os

    validate_backup_contents || exit 1

    if [[ "$SKIP_SYSTEM_CHECK" != "true" ]]; then
        check_system_requirements
    else
        log_warning "Skipping system requirements check (--skip-system-check)"
    fi

    install_base_utilities

    if ! command_exists python3 && ! command_exists jq; then
        log_warning "Neither python3 nor jq found - backup details will show as unknown"
    fi

    local BACKUP_TYPE BACKUP_DATE N8N_VERSION WORKFLOW_COUNT CREDENTIAL_COUNT CONFIG_COUNT ARCHIVE_SCRIPT_VERSION
    BACKUP_TYPE=$(meta_get backup_type unknown)
    BACKUP_DATE=$(meta_get created_at unknown)
    N8N_VERSION=$(meta_get n8n_version unknown)
    WORKFLOW_COUNT=$(meta_get workflow_count 0)
    CREDENTIAL_COUNT=$(meta_get credential_count 0)
    CONFIG_COUNT=$(meta_get config_file_count 0)
    ARCHIVE_SCRIPT_VERSION=$(meta_get restore_script_version "none (created before versioning)")

    echo ""
    echo -e "${CYAN}Backup Information:${NC}"
    echo "─────────────────────────────────────────────────────────────────────"
    echo "  Backup Type:      $BACKUP_TYPE"
    echo "  Created:          $BACKUP_DATE"
    echo "  n8n Version:      $N8N_VERSION"
    echo "  Workflows:        $WORKFLOW_COUNT"
    echo "  Credentials:      $CREDENTIAL_COUNT"
    echo "  Config Files:     $CONFIG_COUNT"
    echo "  Archive script:   $ARCHIVE_SCRIPT_VERSION (running: ${RESTORE_SCRIPT_VERSION})"
    echo "─────────────────────────────────────────────────────────────────────"
    echo ""

    echo -e "${CYAN}Restore Configuration:${NC}"
    echo "  Target Directory:     $TARGET_DIR"
    echo "  Skip Docker:          $SKIP_DOCKER"
    echo "  Skip SSL:             $SKIP_SSL"
    echo "  Skip Database:        $SKIP_DB"
    echo "  Skip Config:          $SKIP_CONFIG"
    echo "  Skip NFS:             $SKIP_NFS"
    echo "  Skip Public Website:  $SKIP_PUBLIC_WEBSITE"
    echo "  Skip DNS Check:       $SKIP_DNS_CHECK"
    echo "  Dry Run:              $DRY_RUN"
    echo "  Auto Mode:            $AUTO_MODE"
    echo ""

    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}════════════════════════════════════════════════════════════════════════${NC}"
        echo -e "${YELLOW}  DRY RUN MODE - No changes will be made to the system${NC}"
        echo -e "${YELLOW}════════════════════════════════════════════════════════════════════════${NC}"
        echo ""
    fi

    if ! confirm "Proceed with restore?"; then
        echo "Restore cancelled."
        exit 0
    fi

    # ========================================================================
    # Step 1: Docker
    # ========================================================================
    log_step "Step 1: Docker Environment"

    if [[ "$SKIP_DOCKER" != "true" ]]; then
        local docker_available=true
        if command_exists docker; then
            log_success "Docker installed: $(docker --version 2>/dev/null || echo unknown)"
        else
            log_warning "Docker not installed"
            if confirm "Install Docker?"; then
                if [[ "$DRY_RUN" != "true" ]]; then
                    install_docker
                else
                    dry_run_note "Would install Docker"
                    docker_available=false
                fi
            else
                log_error "Docker is required for n8n"
                exit 1
            fi
        fi

        if [[ "$docker_available" == "true" ]]; then
            if docker compose version &>/dev/null; then
                log_success "Docker Compose available: $(docker compose version 2>/dev/null || echo unknown)"
            elif command_exists docker-compose; then
                log_success "Docker Compose (standalone): $(docker-compose --version 2>/dev/null || echo unknown)"
            else
                log_error "Docker Compose not found"
                log_info "Please install docker-compose-plugin"
                exit 1
            fi
        fi
    else
        log_info "Skipping Docker check (--skip-docker)"
    fi

    # ========================================================================
    # Step 2: PostgreSQL tooling
    # ========================================================================
    log_step "Step 2: PostgreSQL Tooling"

    if [[ "$SKIP_DB" != "true" ]]; then
        log_info "Databases are restored with pg_restore INSIDE the postgres container,"
        log_info "so the client version always matches the server. No host client needed."
    else
        log_info "Skipping database restoration (--skip-db)"
    fi

    # ========================================================================
    # Step 3: Configuration Files (including dotfiles such as .env)
    # ========================================================================
    log_step "Step 3: Restore Configuration Files"

    if [[ "$SKIP_CONFIG" != "true" ]] && [[ -d "$SCRIPT_DIR/config" ]]; then
        run_cmd mkdir -p "$TARGET_DIR"

        local config_count=0
        local stamp src rel dest
        stamp=$(date +%Y%m%d_%H%M%S)
        while IFS= read -r -d '' src; do
            rel="${src#"$SCRIPT_DIR/config/"}"
            dest="$TARGET_DIR/$rel"

            if [[ -f "$dest" ]]; then
                run_cmd cp -a "$dest" "${dest}.bak.${stamp}"
                log_info "Backed up existing $rel"
            fi

            log_info "Restoring: $rel"
            run_cmd mkdir -p "$(dirname "$dest")"
            run_cmd cp -a "$src" "$dest"

            case "$(basename "$rel")" in
                package.json) ;;
                .env|*.ini|*.json) run_cmd chmod 600 "$dest" ;;
                *) ;;
            esac

            config_count=$((config_count + 1))
        done < <(find "$SCRIPT_DIR/config" -type f -print0 | sort -z)

        log_success "Restored $config_count config file(s)"
    else
        log_info "Skipping config file restoration"
    fi

    # ========================================================================
    # Step 4: Environment Validation (DNS / NFS)
    # ========================================================================
    log_step "Step 4: Environment Validation"

    local ENV_FILE=""
    if [[ -f "$TARGET_DIR/.env" ]]; then
        ENV_FILE="$TARGET_DIR/.env"
    elif [[ -f "$SCRIPT_DIR/config/.env" ]]; then
        ENV_FILE="$SCRIPT_DIR/config/.env"
    fi

    local DOMAIN="" HOST_IP="" NFS_SERVER="" NFS_PATH="" NFS_LOCAL_MOUNT=""
    if [[ -n "$ENV_FILE" ]]; then
        log_info "Reading environment from $ENV_FILE"
        DOMAIN=$(env_get "$ENV_FILE" DOMAIN)
        HOST_IP=$(env_get "$ENV_FILE" N8N_MANAGEMENT_HOST_IP)
        NFS_SERVER=$(env_get "$ENV_FILE" NFS_SERVER)
        NFS_PATH=$(env_get "$ENV_FILE" NFS_PATH)
        NFS_LOCAL_MOUNT=$(env_get "$ENV_FILE" NFS_LOCAL_MOUNT)
        PG_USER=$(env_get "$ENV_FILE" POSTGRES_USER)
        PG_DB=$(env_get "$ENV_FILE" POSTGRES_DB)
        MGMT_USER=$(env_get "$ENV_FILE" MGMT_DB_USER)
        PG_USER="${PG_USER:-n8n}"
        PG_DB="${PG_DB:-n8n}"
        MGMT_USER="${MGMT_USER:-n8n_mgmt}"

        validate_dns "$DOMAIN" "$HOST_IP" || log_warning "Continuing despite DNS validation problems"

        if [[ -n "$NFS_SERVER" ]] && [[ -n "$NFS_PATH" ]]; then
            setup_nfs "$NFS_SERVER" "$NFS_PATH" "${NFS_LOCAL_MOUNT:-/mnt/nfs_backups}" || \
                log_warning "NFS setup incomplete - backups to NFS will not work until it is fixed"
        fi
    else
        log_warning "No .env file found - skipping environment validation"
    fi

    # ========================================================================
    # Step 5: Docker Volumes and SSL Certificates
    # ========================================================================
    log_step "Step 5: Docker Volumes and SSL Certificates"

    # The stack declares 'letsencrypt' as an external volume, so it must exist.
    if [[ "$DRY_RUN" == "true" ]]; then
        dry_run_note "Would create the external 'letsencrypt' Docker volume if it is missing"
    elif command_exists docker; then
        if ! docker volume inspect letsencrypt &>/dev/null; then
            docker volume create letsencrypt
            log_success "Created letsencrypt volume"
        else
            log_info "letsencrypt volume already exists"
        fi
    fi

    if [[ "$SKIP_SSL" == "true" ]]; then
        log_info "Skipping SSL certificate restoration (--skip-ssl)"
    elif [[ -d "$SCRIPT_DIR/letsencrypt/live" ]]; then
        # Complete certbot tree (archive/, live/ symlinks, renewal/, accounts/,
        # renewal-hooks/, ...). Each top-level entry replaces the volume's copy
        # as a whole and is copied with cp -a, so live/ stays a set of symlinks
        # into archive/ and certbot can keep renewing the restored lineages.
        log_info "Restoring the complete /etc/letsencrypt tree (symlinks preserved)"
        local lineage
        for lineage in "$SCRIPT_DIR"/letsencrypt/live/*/; do
            log_info "  certificate lineage: $(basename "$lineage")"
        done
        if [[ "$DRY_RUN" == "true" ]]; then
            dry_run_note "Would replace each top-level entry of the letsencrypt volume with the backup's copy (cp -a)"
        else
            # shellcheck disable=SC2016  # expanded by the container's shell
            docker run --rm \
                -v letsencrypt:/etc/letsencrypt \
                -v "$SCRIPT_DIR/letsencrypt:/source:ro" \
                alpine sh -c 'set -e
                    cd /source
                    for entry in * .[!.]*; do
                        [ -e "$entry" ] || [ -L "$entry" ] || continue
                        rm -rf "/etc/letsencrypt/$entry"
                        cp -a "/source/$entry" "/etc/letsencrypt/$entry"
                    done'
            log_success "SSL certificates restored into the letsencrypt volume"
        fi
    elif [[ -d "$SCRIPT_DIR/ssl" ]]; then
        # Archives created before the full tree was backed up only contain
        # dereferenced copies of live/<domain>/*.pem.
        log_warning "This backup only has plain copies of live/ certificates (older archive format)."
        log_warning "HTTPS will work, but certbot cannot renew these certificates. Re-issue them"
        log_warning "(e.g. re-run the certificate step of setup.sh) before they expire."
        local ssl_count=0 domain_dir
        for domain_dir in "$SCRIPT_DIR"/ssl/*/; do
            log_info "Restoring SSL for: $(basename "$domain_dir")"
            ssl_count=$((ssl_count + 1))
        done
        if [[ "$DRY_RUN" == "true" ]]; then
            dry_run_note "Would copy $ssl_count domain(s) into live/ of the letsencrypt volume (existing certbot lineages are kept)"
        elif [[ $ssl_count -gt 0 ]]; then
            # Never overwrite an existing, renewable (symlinked) lineage with plain files.
            # shellcheck disable=SC2016  # expanded by the container's shell
            docker run --rm \
                -v letsencrypt:/etc/letsencrypt \
                -v "$SCRIPT_DIR/ssl:/source:ro" \
                alpine sh -c 'set -e
                    mkdir -p /etc/letsencrypt/live
                    for d in /source/*/; do
                        n=$(basename "$d")
                        if [ -L "/etc/letsencrypt/live/$n/cert.pem" ]; then
                            echo "  keeping existing certbot lineage for $n"
                            continue
                        fi
                        mkdir -p "/etc/letsencrypt/live/$n"
                        cp "$d"* "/etc/letsencrypt/live/$n/"
                    done'
            log_success "Restored SSL certificates for $ssl_count domain(s)"
        fi
    else
        log_info "No SSL certificates in backup"
    fi

    # ========================================================================
    # Step 6: Public Website Files
    # ========================================================================
    log_step "Step 6: Public Website Files"

    if [[ "$SKIP_PUBLIC_WEBSITE" != "true" ]] && [[ -d "$SCRIPT_DIR/public_website" ]]; then
        log_info "Found public website files in backup"
        if [[ "$DRY_RUN" != "true" ]] && command_exists docker; then
            if ! docker volume inspect public_web_root &>/dev/null; then
                docker volume create public_web_root
                log_success "Created public_web_root volume"
            else
                log_info "public_web_root volume already exists"
            fi

            log_info "Restoring public website files to Docker volume..."
            if docker run --rm \
                -v public_web_root:/dest \
                -v "$SCRIPT_DIR/public_website:/source:ro" \
                alpine \
                sh -c "cp -a /source/. /dest/"; then
                log_success "Restored $(find "$SCRIPT_DIR/public_website" -type f | wc -l) public website file(s)"
            else
                log_warning "Failed to restore some public website files"
            fi
        else
            dry_run_note "Would create public_web_root volume and restore files"
        fi
    elif [[ "$SKIP_PUBLIC_WEBSITE" == "true" ]]; then
        log_info "Skipping public website restoration (--skip-public-website)"
    else
        log_info "No public website files in backup"
    fi

    # ========================================================================
    # Step 7: Database Restoration (postgres only - nothing else running)
    # ========================================================================
    log_step "Step 7: Database Restoration"

    local dumps=()
    if [[ -d "$SCRIPT_DIR/databases" ]]; then
        dumps=("$SCRIPT_DIR"/databases/*.dump)
    fi

    if [[ "$SKIP_DB" == "true" ]]; then
        log_info "Skipping database restoration (--skip-db)"
    elif [[ ${#dumps[@]} -eq 0 ]]; then
        log_warning "No database dumps found in backup - skipping database restoration"
    elif [[ "$DRY_RUN" == "true" ]]; then
        dry_run_note "Would run (in $TARGET_DIR): docker compose up -d postgres"
        dry_run_note "Would wait for pg_isready -U $PG_USER -d $PG_DB"
        local dump_file
        for dump_file in "${dumps[@]}"; do
            dry_run_note "Would restore $(basename "$dump_file" .dump): pg_restore --clean --if-exists --no-owner --no-acl --exit-on-error --single-transaction"
        done
    else
        cd "$TARGET_DIR"
        if [[ ! -f "docker-compose.yaml" ]] && [[ ! -f "docker-compose.yml" ]]; then
            log_error "docker-compose.yaml not found in $TARGET_DIR - cannot start PostgreSQL"
            exit 1
        fi

        if confirm "Pull latest Docker images before starting?"; then
            compose pull || log_warning "Some images failed to pull"
        fi

        log_info "Starting ONLY the postgres service for the database restore..."
        compose up -d postgres

        wait_for_postgres || db_restore_failed "PostgreSQL is not accepting connections"

        local dump_file db_count=0
        for dump_file in "${dumps[@]}"; do
            restore_one_database "$dump_file"
            db_count=$((db_count + 1))
        done
        log_success "Restored $db_count database(s)"
    fi

    # ========================================================================
    # Step 8: Start Services
    # ========================================================================
    log_step "Step 8: Start Services"

    if [[ "$DRY_RUN" != "true" ]]; then
        cd "$TARGET_DIR"
        if [[ -f "docker-compose.yaml" ]] || [[ -f "docker-compose.yml" ]]; then
            log_info "Starting all services with docker compose..."
            compose up -d
            log_success "Services started"

            log_info "Waiting for services to be ready..."
            sleep 10

            echo ""
            echo -e "${CYAN}Service Status:${NC}"
            compose ps || true
        else
            log_error "docker-compose.yaml not found in $TARGET_DIR"
            log_info "Please verify the configuration files were restored correctly"
            exit 1
        fi
    else
        dry_run_note "Would start all services with docker compose up -d"
    fi

    # ========================================================================
    # Step 9: Health Check
    # ========================================================================
    log_step "Step 9: Health Verification"

    local validation_passed=true

    if [[ "$DRY_RUN" != "true" ]] && command_exists docker; then
        cd "$TARGET_DIR"
        echo ""
        local running_count total_count
        running_count=$(compose ps --status running -q 2>/dev/null | wc -l) || running_count=0
        total_count=$(compose ps -q 2>/dev/null | wc -l) || total_count=0

        if [[ "$running_count" -eq "$total_count" ]] && [[ "$total_count" -gt 0 ]]; then
            log_success "All $total_count services are running"
        else
            log_warning "$running_count of $total_count services are running"
            validation_passed=false
        fi

        if [[ -n "$(docker ps --filter "name=n8n" --filter "status=running" -q 2>/dev/null || true)" ]]; then
            log_success "n8n container is running"
        else
            log_warning "n8n container is not running"
            validation_passed=false
        fi

        if [[ -n "$(docker ps --filter "name=nginx" --filter "status=running" -q 2>/dev/null || true)" ]]; then
            log_success "nginx container is running"
        else
            log_warning "nginx container is not running"
            validation_passed=false
        fi
    fi

    # ========================================================================
    # Completion
    # ========================================================================
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${GREEN}║                 DRY RUN COMPLETED SUCCESSFULLY                       ║${NC}"
    else
        echo -e "${GREEN}║                 RESTORE COMPLETED SUCCESSFULLY                       ║${NC}"
    fi
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    if [[ "$DRY_RUN" != "true" ]]; then
        echo -e "${CYAN}Summary:${NC}"
        echo "  Target Directory:  $TARGET_DIR"
        echo "  Services Started:  Yes"
        echo ""
        echo -e "${CYAN}Next Steps:${NC}"
        echo "  1. Verify services: cd $TARGET_DIR && docker compose ps"
        echo "  2. Check logs:      docker compose logs -f"
        echo "  3. Access n8n:      https://${DOMAIN:-your-domain}"
        echo "  4. Access console:  https://${DOMAIN:-your-domain}/management"
        echo ""
        if [[ "$validation_passed" != "true" ]]; then
            echo -e "${YELLOW}⚠ Some validation checks failed - please review the output above${NC}"
            echo ""
        fi
    fi
}

main "$@"
