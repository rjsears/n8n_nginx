#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /setup.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 1st, 2026
#
# Richard J. Sears
# richard@n8nmanagement.net
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                                                                           ║
# ║     n8n HTTPS Interactive Setup Script with Let's Encrypt + DNS           ║
# ║                                                                           ║
# ║     Automated SSL certificate setup and deployment for n8n                ║
# ║     with PostgreSQL, Nginx reverse proxy, and auto-renewal                ║
# ║                                                                           ║
# ║     Version 3.0.0                                                         ║
# ║     Richard J. Sears                                                      ║
# ║     richard@n8nmanagement.net                                               ║
# ║     December 2025                                                         ║
# ║                                                                           ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

set -e

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_VERSION="3.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/.n8n_setup_config"
STATE_FILE="${SCRIPT_DIR}/.n8n_setup_state"
MIGRATION_STATE_FILE="${SCRIPT_DIR}/.migration_state"

# Detect the real user (handles both direct execution and sudo ./setup.sh)
if [ -n "$SUDO_USER" ]; then
    REAL_USER="$SUDO_USER"
elif [ -n "$USER" ]; then
    REAL_USER="$USER"
else
    REAL_USER=$(whoami)
fi

# Default container names
DEFAULT_POSTGRES_CONTAINER="n8n_postgres"
DEFAULT_N8N_CONTAINER="n8n"
DEFAULT_NGINX_CONTAINER="n8n_nginx"
DEFAULT_CERTBOT_CONTAINER="n8n_certbot"
DEFAULT_MANAGEMENT_CONTAINER="n8n_management"

# Default database settings
DEFAULT_DB_NAME="n8n"
DEFAULT_DB_USER="n8n"
DEFAULT_MGMT_DB_NAME="n8n_management"

# Default management settings
DEFAULT_MGMT_PORT="3333"

# Default ports for optional services
DEFAULT_ADMINER_PORT="8080"
DEFAULT_DOZZLE_PORT="9999"
DEFAULT_PORTAINER_PORT="9000"

# Optional service flags (set during configuration)
INSTALL_CLOUDFLARE_TUNNEL=false
INSTALL_TAILSCALE=false
INSTALL_ADMINER=false
INSTALL_DOZZLE=false
INSTALL_PORTAINER=false
INSTALL_PORTAINER_AGENT=false
PORTAINER_AGENT_BIND=""
INSTALL_NTFY=false
NTFY_BASE_URL=""
NTFY_PUBLIC_URL=""

# Management console image settings
# true = use pre-built image from Docker Hub (faster)
# false = build locally from source (for customization)
USE_PREBUILT_MANAGEMENT=true
# Pre-built images are published per release (vX.Y.Z -> X.Y.Z); if the tag is
# not on Docker Hub yet, compose falls back to building ./management locally.
# MGMT_VERSION in .env overrides the tag for an existing install.
DEFAULT_MANAGEMENT_IMAGE='rjsears/n8n_management:${MGMT_VERSION:-'"${SCRIPT_VERSION}"'}'
MANAGEMENT_IMAGE="$DEFAULT_MANAGEMENT_IMAGE"
STATUS_IMAGE='rjsears/n8n_status:${MGMT_VERSION:-'"${SCRIPT_VERSION}"'}'

# Pinned images (no floating :latest). Bump deliberately, after reading the
# upstream release notes; see README "Upgrading". The service images are
# pinned in generate_docker_compose_v3 (and docker-compose.yaml);
# N8N_VERSION / NGINX_VERSION / MGMT_VERSION in .env override the n8n, nginx
# and management/status tags per install (empty = the pinned default).
# Images used by the installer itself:
CERTBOT_VERSION="v5.8.0"
ALPINE_IMAGE="alpine:3.24.2"
OPENSSL_IMAGE="alpine/openssl:3.5.8"
HTPASSWD_IMAGE="httpd:2.4.68-alpine"
NTFY_INTERNAL_URL=""
INSTALL_PUBLIC_WEBSITE=false

# Auto-generated credential tracking (for display at end of setup)
AUTOGEN_DB_PASSWORD=false
AUTOGEN_ENCRYPTION_KEY=false
AUTOGEN_MGMT_SECRET=false
AUTOGEN_ADMIN_PASS=false

# Internal IP ranges that get full access (space-separated CIDR blocks)
# 127.0.0.1/32 is required for nginx healthchecks - DO NOT REMOVE
# These are meant for your real LAN / VPN clients. Traffic that reaches nginx
# through a Docker hop (Cloudflare Tunnel, docker-proxy, other containers) comes
# from N8N_NETWORK_SUBNET, which is always emitted as a more specific
# "external" entry in the nginx geo block (longest prefix wins).
DEFAULT_INTERNAL_IP_RANGES="127.0.0.1/32 100.64.0.0/10 172.16.0.0/12 10.0.0.0/8 192.168.0.0/16"
INTERNAL_IP_RANGES="${INTERNAL_IP_RANGES:-$DEFAULT_INTERNAL_IP_RANGES}"
CUSTOM_INTERNAL_IPS=""

# Pinned subnet for n8n_network (IPv4, network address ending in .0, prefix
# /8-/24). Containers that proxy client traffic get static addresses in it
# (see compute_docker_network_addrs) so nginx can tell them apart.
DEFAULT_N8N_NETWORK_SUBNET="172.30.0.0/24"
N8N_NETWORK_SUBNET="${N8N_NETWORK_SUBNET:-$DEFAULT_N8N_NETWORK_SUBNET}"

# ═══════════════════════════════════════════════════════════════════════════════
# COLORS & STYLING
# ═══════════════════════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;37m'
NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
UNDERLINE='\033[4m'

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

print_header() {
    local title="$1"
    local width=75
    local padding=$(( (width - ${#title} - 2) / 2 ))

    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
    printf "${CYAN}║${NC}%*s${WHITE}${BOLD} %s ${NC}%*s${CYAN}║${NC}\n" $padding "" "$title" $((padding + (width - ${#title} - 2) % 2)) ""
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_section() {
    local title="$1"
    echo ""
    echo -e "${BLUE}┌─────────────────────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${BLUE}│${NC} ${WHITE}${BOLD}$title${NC}"
    echo -e "${BLUE}└─────────────────────────────────────────────────────────────────────────────┘${NC}"
}

print_subsection() {
    echo ""
    echo -e "${GRAY}───────────────────────────────────────────────────────────────────────────────${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}  ✓${NC} $1"
}

print_error() {
    echo -e "${RED}  ✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}  ⚠${NC} $1"
}

print_info() {
    echo -e "${CYAN}  ℹ${NC} $1"
}

print_step() {
    local step_num="$1"
    local total_steps="$2"
    local description="$3"
    echo ""
    echo -e "${MAGENTA}  [$step_num/$total_steps]${NC} ${WHITE}${BOLD}$description${NC}"
    echo ""
}

prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"

    # Check if variable already has a value (from preconfig)
    local current_value="${!var_name}"
    if [ -n "$current_value" ]; then
        default="$current_value"
    fi

    # In auto-confirm mode, use the existing/default value without prompting
    if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
        print_info "Using: $prompt = $default"
        printf -v "$var_name" '%s' "$default"
        return
    fi

    echo -ne "${WHITE}  $prompt [$default]${NC}: "
    read -r value

    # printf -v (not eval) so values containing quotes or $ are stored verbatim
    if [ -z "$value" ]; then
        printf -v "$var_name" '%s' "$default"
    else
        printf -v "$var_name" '%s' "$value"
    fi
}

confirm_prompt() {
    local prompt="$1"
    local default="${2:-y}"

    # In auto-confirm mode, use the default value without prompting
    if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
        if [ "$default" = "y" ]; then
            print_info "Auto-confirming: $prompt [Y]"
            return 0
        else
            print_info "Auto-declining: $prompt [N]"
            return 1
        fi
    fi

    if [ "$default" = "y" ]; then
        echo -ne "${WHITE}  $prompt [Y/n]${NC}: "
    else
        echo -ne "${WHITE}  $prompt [y/N]${NC}: "
    fi

    read response
    response=${response:-$default}

    case "$response" in
        [yY][eE][sS]|[yY]) return 0 ;;
        *) return 1 ;;
    esac
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Run command with sudo only if not root
run_privileged() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

# Detect OS distribution and set package manager variables
# Sets: DISTRO, DISTRO_FAMILY, PKG_MANAGER, PKG_UPDATE, PKG_INSTALL
detect_os() {
    DISTRO=""
    DISTRO_FAMILY=""
    PKG_MANAGER=""
    PKG_UPDATE=""
    PKG_INSTALL=""

    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
        DISTRO_VERSION=$VERSION_ID
    elif [ -f /etc/debian_version ]; then
        DISTRO="debian"
    elif [ -f /etc/redhat-release ]; then
        DISTRO="rhel"
    fi

    case $DISTRO in
        ubuntu|debian|linuxmint|pop|raspbian)
            DISTRO_FAMILY="debian"
            PKG_MANAGER="apt-get"
            PKG_UPDATE="apt-get update"
            PKG_INSTALL="apt-get install -y"
            ;;
        centos|rhel|rocky|almalinux|ol)
            DISTRO_FAMILY="rhel"
            if command_exists dnf; then
                PKG_MANAGER="dnf"
                PKG_UPDATE="dnf check-update || true"
                PKG_INSTALL="dnf install -y"
            else
                PKG_MANAGER="yum"
                PKG_UPDATE="yum check-update || true"
                PKG_INSTALL="yum install -y"
            fi
            ;;
        fedora)
            DISTRO_FAMILY="fedora"
            PKG_MANAGER="dnf"
            PKG_UPDATE="dnf check-update || true"
            PKG_INSTALL="dnf install -y"
            ;;
        opensuse*|sles)
            DISTRO_FAMILY="suse"
            PKG_MANAGER="zypper"
            PKG_UPDATE="zypper refresh"
            PKG_INSTALL="zypper install -y"
            ;;
        arch|manjaro)
            DISTRO_FAMILY="arch"
            PKG_MANAGER="pacman"
            PKG_UPDATE="pacman -Sy"
            PKG_INSTALL="pacman -S --noconfirm"
            ;;
        alpine)
            DISTRO_FAMILY="alpine"
            PKG_MANAGER="apk"
            PKG_UPDATE="apk update"
            PKG_INSTALL="apk add"
            ;;
        *)
            # Fallback: try to detect package manager
            if command_exists apt-get; then
                DISTRO_FAMILY="debian"
                PKG_MANAGER="apt-get"
                PKG_UPDATE="apt-get update"
                PKG_INSTALL="apt-get install -y"
            elif command_exists dnf; then
                DISTRO_FAMILY="rhel"
                PKG_MANAGER="dnf"
                PKG_UPDATE="dnf check-update || true"
                PKG_INSTALL="dnf install -y"
            elif command_exists yum; then
                DISTRO_FAMILY="rhel"
                PKG_MANAGER="yum"
                PKG_UPDATE="yum check-update || true"
                PKG_INSTALL="yum install -y"
            else
                print_error "Could not detect package manager"
                return 1
            fi
            ;;
    esac

    return 0
}

# Update system packages based on detected OS
update_system() {
    print_info "Updating system packages..."

    if [ -z "$PKG_MANAGER" ]; then
        detect_os || return 1
    fi

    case $DISTRO_FAMILY in
        debian)
            run_privileged apt-get update -qq
            run_privileged apt-get upgrade -y -qq
            ;;
        rhel)
            if [ "$PKG_MANAGER" = "dnf" ]; then
                run_privileged dnf update -y -q
            else
                run_privileged yum update -y -q
            fi
            ;;
        fedora)
            run_privileged dnf upgrade -y -q
            ;;
        suse)
            run_privileged zypper refresh -q
            run_privileged zypper update -y -q
            ;;
        arch)
            run_privileged pacman -Syu --noconfirm
            ;;
        alpine)
            run_privileged apk update -q
            run_privileged apk upgrade -q
            ;;
        *)
            print_warning "System update not supported for this distribution"
            return 1
            ;;
    esac

    print_success "System packages updated"
    return 0
}

# Install required utilities (curl, git, openssl, jq, tmux)
install_required_utilities() {
    print_info "Checking and installing required utilities..."

    if [ -z "$PKG_MANAGER" ]; then
        detect_os || return 1
    fi

    local missing_utils=""

    # Check which utilities are missing
    command_exists curl || missing_utils="$missing_utils curl"
    command_exists git || missing_utils="$missing_utils git"
    command_exists openssl || missing_utils="$missing_utils openssl"
    command_exists jq || missing_utils="$missing_utils jq"
    command_exists tmux || missing_utils="$missing_utils tmux"

    if [ -z "$missing_utils" ]; then
        print_success "All required utilities are already installed"
        return 0
    fi

    print_info "Installing missing utilities:$missing_utils"

    # Update package cache first
    run_privileged $PKG_UPDATE

    case $DISTRO_FAMILY in
        debian)
            run_privileged apt-get install -y -qq $missing_utils
            ;;
        rhel|fedora)
            run_privileged $PKG_INSTALL $missing_utils
            ;;
        suse)
            run_privileged zypper install -y $missing_utils
            ;;
        arch)
            run_privileged pacman -S --noconfirm $missing_utils
            ;;
        alpine)
            # Alpine uses different package names for openssl
            local alpine_utils=""
            for util in $missing_utils; do
                if [ "$util" = "openssl" ]; then
                    alpine_utils="$alpine_utils openssl"
                else
                    alpine_utils="$alpine_utils $util"
                fi
            done
            run_privileged apk add $alpine_utils
            ;;
        *)
            print_warning "Could not install utilities automatically for this distribution"
            print_info "Please install manually: curl git openssl jq tmux"
            return 1
            ;;
    esac

    # Verify installation
    local failed=""
    command_exists curl || failed="$failed curl"
    command_exists git || failed="$failed git"
    command_exists openssl || failed="$failed openssl"
    command_exists jq || failed="$failed jq"
    command_exists tmux || failed="$failed tmux"

    if [ -n "$failed" ]; then
        print_error "Failed to install:$failed"
        return 1
    fi

    print_success "Required utilities installed successfully"
    return 0
}

get_local_ips() {
    hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' || \
    ip addr show 2>/dev/null | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}' | cut -d'/' -f1 || \
    ifconfig 2>/dev/null | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}'
}

# Derive the pinned n8n_network addresses from N8N_NETWORK_SUBNET.
# Sets: N8N_NETWORK_SUBNET, N8N_NETWORK_GATEWAY, N8N_NETWORK_IP_RANGE,
#       NGINX_ROUTER_IP, CLOUDFLARED_IP, TAILSCALE_IP
# Static addresses live in .2-.127 of the first /24; Docker hands out dynamic
# addresses only from .128/25 so they can never collide.
compute_docker_network_addrs() {
    local subnet="${N8N_NETWORK_SUBNET:-$DEFAULT_N8N_NETWORK_SUBNET}"
    local re='^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.0/([0-9]{1,2})$'
    if ! [[ "$subnet" =~ $re ]] || [ "${BASH_REMATCH[4]}" -lt 8 ] || [ "${BASH_REMATCH[4]}" -gt 24 ] || \
       [ "${BASH_REMATCH[1]}" -gt 255 ] || [ "${BASH_REMATCH[2]}" -gt 255 ] || [ "${BASH_REMATCH[3]}" -gt 255 ] || \
       ! ipv4_cidr_is_network "$subnet"; then
        # ipv4_cidr_is_network rejects host bits (e.g. 10.20.5.0/16): the
        # static IPs below are derived from the first three octets and would
        # otherwise fall outside the network nginx trusts.
        print_warning "Invalid N8N_NETWORK_SUBNET '${subnet}' (expected a network address, e.g. 172.30.0.0/24, prefix /8-/24) - using ${DEFAULT_N8N_NETWORK_SUBNET}"
        subnet="$DEFAULT_N8N_NETWORK_SUBNET"
    fi
    # Re-match: ipv4_cidr_is_network above overwrites BASH_REMATCH
    [[ "$subnet" =~ $re ]]
    local base="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.${BASH_REMATCH[3]}"
    N8N_NETWORK_SUBNET="$subnet"
    N8N_NETWORK_GATEWAY="${base}.1"
    N8N_NETWORK_IP_RANGE="${base}.128/25"
    NGINX_ROUTER_IP="${base}.10"
    CLOUDFLARED_IP="${base}.11"
    TAILSCALE_IP="${base}.12"
}

# Returns 0 (true) when the running stack's n8n_network does not use the pinned
# N8N_NETWORK_SUBNET (installs from before the subnet was pinned). Such a
# network must be recreated (docker compose down && docker compose up -d):
# until then the nginx geo/realip rules do not match the real addresses.
n8n_network_needs_recreate() {
    compute_docker_network_addrs
    local nginx_c="${NGINX_CONTAINER:-n8n_nginx}"
    local existing_net existing_subnets
    existing_net=$($DOCKER_SUDO docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "$nginx_c" 2>/dev/null | grep 'n8n_network$' | head -1)
    [ -z "$existing_net" ] && return 1
    existing_subnets=$($DOCKER_SUDO docker network inspect -f '{{range .IPAM.Config}}{{.Subnet}} {{end}}' "$existing_net" 2>/dev/null)
    case " ${existing_subnets} " in
        *" ${N8N_NETWORK_SUBNET} "*) return 1 ;;
    esac
    print_warning "Network ${existing_net} uses '${existing_subnets% }', expected ${N8N_NETWORK_SUBNET}"
    return 0
}

# ---------------------------------------------------------------------------
# Pure-bash IPv4 CIDR helpers (no ipcalc/python dependency).
# ---------------------------------------------------------------------------

# Parse an IPv4 address or CIDR ("a.b.c.d" is treated as /32). On success sets
# CIDR_ADDR (the address as an integer), CIDR_PREFIX and CIDR_NET (CIDR_ADDR
# with the host bits cleared). Returns 1 when $1 is not valid IPv4.
ipv4_cidr_parse() {
    local cidr="$1" ip prefix
    ip="${cidr%%/*}"
    if [ "$ip" = "$cidr" ]; then
        prefix=32
    else
        prefix="${cidr#*/}"
    fi
    [[ "$prefix" =~ ^[0-9]{1,2}$ ]] || return 1
    prefix=$((10#$prefix))
    [ "$prefix" -le 32 ] || return 1
    local re='^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$'
    [[ "$ip" =~ $re ]] || return 1
    local o1=$((10#${BASH_REMATCH[1]})) o2=$((10#${BASH_REMATCH[2]}))
    local o3=$((10#${BASH_REMATCH[3]})) o4=$((10#${BASH_REMATCH[4]}))
    [ "$o1" -le 255 ] && [ "$o2" -le 255 ] && [ "$o3" -le 255 ] && [ "$o4" -le 255 ] || return 1
    CIDR_ADDR=$(( (o1 << 24) | (o2 << 16) | (o3 << 8) | o4 ))
    CIDR_PREFIX=$prefix
    ipv4_prefix_mask "$prefix"
    CIDR_NET=$(( CIDR_ADDR & IPV4_MASK ))
    return 0
}

# Sets IPV4_MASK to the netmask (as an integer) for prefix length $1. Sets a
# variable instead of printing so callers need no subshell (these helpers run
# in loops).
ipv4_prefix_mask() {
    if [ "$1" -eq 0 ]; then
        IPV4_MASK=0
    else
        IPV4_MASK=$(( (0xFFFFFFFF << (32 - $1)) & 0xFFFFFFFF ))
    fi
}

# True (0) when the two IPv4 CIDRs share at least one address. Two CIDR blocks
# overlap iff they are equal when both are truncated to the shorter prefix.
# Returns 2 when either argument is not valid IPv4.
ipv4_cidrs_overlap() {
    local net_a prefix_a p
    ipv4_cidr_parse "$1" || return 2
    net_a=$CIDR_NET
    prefix_a=$CIDR_PREFIX
    ipv4_cidr_parse "$2" || return 2
    p=$prefix_a
    [ "$CIDR_PREFIX" -lt "$p" ] && p=$CIDR_PREFIX
    ipv4_prefix_mask "$p"
    [ $(( net_a & IPV4_MASK )) -eq $(( CIDR_NET & IPV4_MASK )) ]
}

# True (0) when $1 is a valid IPv4 CIDR whose host bits are all zero.
ipv4_cidr_is_network() {
    ipv4_cidr_parse "$1" || return 1
    [ "$CIDR_ADDR" -eq "$CIDR_NET" ]
}

# True (0) when an "internal" range would override the pinned Docker subnet in
# the nginx geo block, i.e. it overlaps N8N_NETWORK_SUBNET and is not strictly
# broader than it (geo is longest-prefix match, so broader ranges such as
# 172.16.0.0/12 lose to the more specific "external" subnet entry and are fine).
range_inside_docker_subnet() {
    local range="$1" range_prefix
    ipv4_cidr_parse "$range" || return 1
    range_prefix=$CIDR_PREFIX
    ipv4_cidr_parse "$N8N_NETWORK_SUBNET" || return 1
    [ "$range_prefix" -ge "$CIDR_PREFIX" ] || return 1
    ipv4_cidrs_overlap "$range" "$N8N_NETWORK_SUBNET"
}

# Docker Compose project name for this install (networks are <project>_<name>).
compose_project_name() {
    local name="${COMPOSE_PROJECT_NAME:-$(basename "$SCRIPT_DIR")}"
    printf '%s' "$name" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-' | sed 's/^[^a-z0-9]*//'
}

# Pre-flight check before any "docker compose down/up": N8N_NETWORK_SUBNET
# must not overlap a subnet already used by another Docker network, or
# "docker compose up" fails with "Pool overlaps with other one on this address
# space" (and, after the down that recreates the network, the stack stays
# down). This project's own n8n_network is ignored: it is recreated anyway.
# Returns 1 (after printing what to do) on overlap; 0 otherwise, including
# when Docker cannot be queried.
check_n8n_network_subnet_free() {
    compute_docker_network_addrs
    command_exists docker || return 0

    local project own_net listing
    project=$(compose_project_name)
    own_net=$($DOCKER_SUDO docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' \
        "${NGINX_CONTAINER:-n8n_nginx}" 2>/dev/null | grep 'n8n_network$' | head -1) || true
    # One line per network: name|compose project|compose network|subnets
    # shellcheck disable=SC2086  # DOCKER_SUDO is empty or "sudo"
    listing=$($DOCKER_SUDO docker network ls -q 2>/dev/null | xargs $DOCKER_SUDO docker network inspect \
        -f '{{.Name}}|{{index .Labels "com.docker.compose.project"}}|{{index .Labels "com.docker.compose.network"}}|{{range .IPAM.Config}}{{.Subnet}} {{end}}' \
        2>/dev/null) || true
    [ -n "$listing" ] || return 0

    local name lproj lnet subnets s conflicts="" used=""
    while IFS='|' read -r name lproj lnet subnets; do
        [ -n "$name" ] || continue
        [ -n "$own_net" ] && [ "$name" = "$own_net" ] && continue
        [ "$lnet" = "n8n_network" ] && [ "$lproj" = "$project" ] && continue
        for s in $subnets; do
            ipv4_cidr_parse "$s" || continue   # skips IPv6
            used="${used} ${s}"
            if ipv4_cidrs_overlap "$s" "$N8N_NETWORK_SUBNET"; then
                conflicts="${conflicts}      ${name}: ${s}\n"
            fi
        done
    done <<< "$listing"

    [ -n "$conflicts" ] || return 0

    # Suggest a free /24, avoiding other Docker networks and host routes.
    local routes="" suggestion="" second third cand u clash
    if command_exists ip; then
        routes=$(ip -4 route show 2>/dev/null | awk '{print $1}' | grep -E '^[0-9.]+(/[0-9]+)?$' | grep -v '^0\.0\.0\.0') || true
    fi
    for second in 30 29 28 27 26 25 24; do
        for third in $(seq 0 255); do
            cand="172.${second}.${third}.0/24"
            clash=false
            for u in $used $routes; do
                if ipv4_cidrs_overlap "$u" "$cand"; then clash=true; break; fi
            done
            if [ "$clash" = false ]; then suggestion="$cand"; break 2; fi
        done
    done

    print_error "N8N_NETWORK_SUBNET ${N8N_NETWORK_SUBNET} overlaps existing Docker network(s):"
    echo -e "$conflicts"
    print_info "Docker cannot create n8n_network there (\"Pool overlaps\"). Nothing was stopped."
    print_info "Pick a free subnet and set"
    print_info "  N8N_NETWORK_SUBNET=${suggestion:-<free /24>}"
    print_info "in ${CONFIG_FILE} (or in your preconfig file / the environment for a"
    print_info "fresh install), regenerate the config files (setup.sh -> Reconfigure -> 7)"
    print_info "and deploy again."
    return 1
}

# Check if running inside an LXC container
is_lxc_container() {
    # Check systemd-detect-virt
    if command_exists systemd-detect-virt && [ "$(systemd-detect-virt)" = "lxc" ]; then
        return 0
    fi
    # Check /proc/1/environ for container=lxc
    if grep -qa 'container=lxc' /proc/1/environ 2>/dev/null; then
        return 0
    fi
    # Check for container-manager
    if [ -f /run/host/container-manager ]; then
        return 0
    fi
    return 1
}

# Some hosts cannot load AppArmor policy into the kernel (e.g. Docker inside
# an LXC guest that lacks policy-admin over the shared kernel). There,
# container creation fails outright with "AppArmor enabled on system but the
# docker-default profile could not be loaded ... You need policy admin
# privileges to manage profiles". Probe once with a throwaway container and
# cache the result. When restricted, every generated compose service and
# helper `docker run` gets apparmor unconfined — same approach as the
# management console's helper containers (see docs/TROUBLESHOOTING.md).
APPARMOR_UNCONFINED=""
DOCKER_APPARMOR_OPT=""

apparmor_unconfined_required() {
    if [ -z "$APPARMOR_UNCONFINED" ]; then
        APPARMOR_UNCONFINED="false"
        local probe_output=""
        if ! probe_output=$($DOCKER_SUDO docker run --rm --name n8n_apparmor_probe "$ALPINE_IMAGE" true 2>&1); then
            if echo "$probe_output" | grep -qiE "apparmor|policy admin"; then
                APPARMOR_UNCONFINED="true"
                DOCKER_APPARMOR_OPT="--security-opt apparmor=unconfined"
                print_warning "Docker cannot load its default AppArmor profile on this host"
                print_info "Containers will run with apparmor:unconfined (see docs/TROUBLESHOOTING.md)"
            fi
        fi
        $DOCKER_SUDO docker rm -f n8n_apparmor_probe >/dev/null 2>&1 || true
    fi
    [ "$APPARMOR_UNCONFINED" = "true" ]
}

# Read sensitive input showing first 10 chars, then masking the rest
# Usage: read_masked_token
# Returns: value in $MASKED_INPUT
read_masked_token() {
    MASKED_INPUT=""
    local char=""
    local display=""

    # Disable echo and enable raw mode
    stty -echo

    while IFS= read -r -n1 char; do
        # Check for Enter (empty char after read -n1)
        if [[ -z "$char" ]]; then
            break
        fi

        # Check for backspace (ASCII 127 or 8)
        if [[ "$char" == $'\x7f' ]] || [[ "$char" == $'\x08' ]]; then
            if [[ -n "$MASKED_INPUT" ]]; then
                # Remove last character from input
                MASKED_INPUT="${MASKED_INPUT%?}"
                # Clear line and redisplay
                echo -ne "\r\033[K"
                local len=${#MASKED_INPUT}
                if [[ $len -le 10 ]]; then
                    display="$MASKED_INPUT"
                else
                    display="${MASKED_INPUT:0:10}$(printf '%*s' $((len - 10)) '' | tr ' ' '*')"
                fi
                echo -ne "$display"
            fi
            continue
        fi

        # Add character to input
        MASKED_INPUT+="$char"

        # Display: first 10 chars visible, rest as *
        local len=${#MASKED_INPUT}
        if [[ $len -le 10 ]]; then
            echo -ne "$char"
        else
            echo -ne "*"
        fi
    done

    # Re-enable echo
    stty echo
    echo ""  # New line after input
}

# Numbered selection menu
# Usage: select_from_menu "prompt" "${options[@]}"
# Returns: selected index in $MENU_SELECTION, selected value in $MENU_VALUE
select_from_menu() {
    local prompt="$1"
    shift
    local -a options=("$@")
    local i
    local num_options=${#options[@]}
    local choice=""

    echo ""
    echo -e "  ${WHITE}$prompt${NC}"
    echo ""

    # Display numbered options
    for i in "${!options[@]}"; do
        echo -e "    ${CYAN}$((i + 1)))${NC} ${options[$i]}"
    done
    echo ""

    # Get selection
    while true; do
        echo -ne "${WHITE}  Enter your choice [1-${num_options}]${NC}: "
        read choice

        # Validate input
        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "$num_options" ]; then
            MENU_SELECTION=$((choice - 1))
            MENU_VALUE="${options[$MENU_SELECTION]}"
            break
        else
            print_error "Invalid selection. Please enter a number between 1 and ${num_options}"
        fi
    done
}

# Check if IP matches a CIDR range or host specification
# Usage: ip_matches_spec "192.168.1.50" "192.168.1.0/24"
ip_matches_spec() {
    local ip="$1"
    local spec="$2"

    # Handle wildcards
    if [ "$spec" = "*" ] || [ "$spec" = "(everyone)" ]; then
        return 0
    fi

    # Exact match
    if [ "$ip" = "$spec" ]; then
        return 0
    fi

    # Handle CIDR notation (e.g., 192.168.1.0/24)
    if [[ "$spec" == *"/"* ]]; then
        local network="${spec%/*}"
        local prefix="${spec#*/}"

        # Convert IPs to integers for comparison
        local ip_int=0
        local net_int=0
        local IFS='.'

        read -ra ip_parts <<< "$ip"
        read -ra net_parts <<< "$network"

        ip_int=$(( (ip_parts[0] << 24) + (ip_parts[1] << 16) + (ip_parts[2] << 8) + ip_parts[3] ))
        net_int=$(( (net_parts[0] << 24) + (net_parts[1] << 16) + (net_parts[2] << 8) + net_parts[3] ))

        # Calculate mask
        local mask=$(( 0xFFFFFFFF << (32 - prefix) & 0xFFFFFFFF ))

        if [ $(( ip_int & mask )) -eq $(( net_int & mask )) ]; then
            return 0
        fi
    fi

    # Handle hostname patterns (simple prefix match for things like 192.168.1.)
    if [[ "$ip" == "$spec"* ]]; then
        return 0
    fi

    return 1
}

# Get NFS exports accessible to this machine
# Usage: get_accessible_exports "nfs_server"
# Returns: Array of accessible export paths in ACCESSIBLE_EXPORTS
get_accessible_exports() {
    local nfs_server="$1"
    ACCESSIBLE_EXPORTS=()

    # Get local IPs into an array
    local -a local_ip_array=()
    while IFS= read -r ip; do
        [ -n "$ip" ] && local_ip_array+=("$ip")
    done <<< "$(get_local_ips)"

    # Get all exports
    local exports_output
    exports_output=$(showmount -e "$nfs_server" 2>/dev/null | tail -n +2)

    if [ -z "$exports_output" ]; then
        return 1
    fi

    # Parse each export line
    while IFS= read -r line; do
        [ -z "$line" ] && continue

        # Parse export path and allowed hosts
        # Format: /path/to/export  host1,host2,192.168.1.0/24
        local export_path=$(echo "$line" | awk '{print $1}')
        local allowed_hosts=$(echo "$line" | awk '{print $2}')

        # Check if any local IP matches allowed hosts
        local can_access=false

        # Split allowed hosts by comma (using tr to handle it safely)
        local host_spec
        for host_spec in $(echo "$allowed_hosts" | tr ',' ' '); do
            # Check against each local IP
            local local_ip
            for local_ip in "${local_ip_array[@]}"; do
                if ip_matches_spec "$local_ip" "$host_spec"; then
                    can_access=true
                    break 2
                fi
            done
        done

        if [ "$can_access" = true ]; then
            ACCESSIBLE_EXPORTS+=("$export_path")
        fi
    done <<< "$exports_output"

    if [ ${#ACCESSIBLE_EXPORTS[@]} -eq 0 ]; then
        return 1
    fi

    return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT FOR RESUME CAPABILITY
# ═══════════════════════════════════════════════════════════════════════════════

# Current step tracking (numeric for easy comparison)
CURRENT_STEP=0

save_state() {
    local step_name=$1
    CURRENT_STEP=$2

    cat > "$STATE_FILE" << EOF
# n8n Setup State File - DO NOT EDIT MANUALLY
# Generated: $(date -Iseconds)
SAVED_STEP_NAME="$step_name"
SAVED_STEP_NUM="$CURRENT_STEP"

# DNS Configuration
SAVED_DNS_PROVIDER="$DNS_PROVIDER_NAME"
SAVED_DNS_CERTBOT_IMAGE="$DNS_CERTBOT_IMAGE"
SAVED_DNS_CERTBOT_FLAGS="$DNS_CERTBOT_FLAGS"
SAVED_DNS_CREDENTIALS_FILE="$DNS_CREDENTIALS_FILE"

# Domain Configuration
SAVED_N8N_DOMAIN="$N8N_DOMAIN"
SAVED_LETSENCRYPT_EMAIL="$LETSENCRYPT_EMAIL"
SAVED_SSL_CERT_DOMAIN="$SSL_CERT_DOMAIN"

# Database Configuration
SAVED_DB_NAME="$DB_NAME"
SAVED_DB_USER="$DB_USER"
SAVED_DB_PASSWORD="$DB_PASSWORD"

# Container Names
SAVED_POSTGRES_CONTAINER="$POSTGRES_CONTAINER"
SAVED_N8N_CONTAINER="$N8N_CONTAINER"
SAVED_NGINX_CONTAINER="$NGINX_CONTAINER"
SAVED_CERTBOT_CONTAINER="$CERTBOT_CONTAINER"

# Timezone & Encryption
SAVED_N8N_TIMEZONE="$N8N_TIMEZONE"
SAVED_N8N_ENCRYPTION_KEY="$N8N_ENCRYPTION_KEY"

# Management Configuration
SAVED_MGMT_PORT="$MGMT_PORT"
SAVED_ADMIN_USER="$ADMIN_USER"
SAVED_ADMIN_PASS="$ADMIN_PASS"

# NFS Configuration
SAVED_NFS_CONFIGURED="$NFS_CONFIGURED"
SAVED_NFS_SERVER="$NFS_SERVER"
SAVED_NFS_PATH="$NFS_PATH"
SAVED_NFS_LOCAL_MOUNT="$NFS_LOCAL_MOUNT"

# Optional Services
SAVED_INSTALL_PORTAINER="$INSTALL_PORTAINER"
SAVED_INSTALL_PORTAINER_AGENT="$INSTALL_PORTAINER_AGENT"
SAVED_PORTAINER_PORT="$PORTAINER_PORT"
SAVED_INSTALL_CLOUDFLARE_TUNNEL="$INSTALL_CLOUDFLARE_TUNNEL"
SAVED_CLOUDFLARE_TUNNEL_TOKEN="$CLOUDFLARE_TUNNEL_TOKEN"
SAVED_INSTALL_TAILSCALE="$INSTALL_TAILSCALE"
SAVED_TAILSCALE_AUTH_KEY="$TAILSCALE_AUTH_KEY"
SAVED_TAILSCALE_HOSTNAME="$TAILSCALE_HOSTNAME"
SAVED_TAILSCALE_ROUTES="$TAILSCALE_ROUTES"
SAVED_INSTALL_ADMINER="$INSTALL_ADMINER"
SAVED_ADMINER_PORT="$ADMINER_PORT"
SAVED_INSTALL_DOZZLE="$INSTALL_DOZZLE"
SAVED_DOZZLE_PORT="$DOZZLE_PORT"
SAVED_INSTALL_NTFY="$INSTALL_NTFY"
SAVED_NTFY_BASE_URL="$NTFY_BASE_URL"
SAVED_NTFY_PUBLIC_URL="$NTFY_PUBLIC_URL"
SAVED_NTFY_INTERNAL_URL="$NTFY_INTERNAL_URL"
SAVED_INSTALL_PUBLIC_WEBSITE="$INSTALL_PUBLIC_WEBSITE"
SAVED_PUBLIC_WEBSITE_DOMAIN="$PUBLIC_WEBSITE_DOMAIN"
SAVED_PUBLIC_WEBSITE_ROOT_DOMAIN="$PUBLIC_WEBSITE_ROOT_DOMAIN"
SAVED_PUBLIC_WEBSITE_INCLUDE_ROOT="$PUBLIC_WEBSITE_INCLUDE_ROOT"

# Access Control
SAVED_INTERNAL_IP_RANGES="$INTERNAL_IP_RANGES"
SAVED_CUSTOM_INTERNAL_IPS="$CUSTOM_INTERNAL_IPS"
SAVED_N8N_NETWORK_SUBNET="$N8N_NETWORK_SUBNET"
EOF
    chmod 600 "$STATE_FILE"
}

load_state() {
    if [ -f "$STATE_FILE" ]; then
        # Source the state file to load all variables
        source "$STATE_FILE"

        # Restore all saved values
        DNS_PROVIDER_NAME="${SAVED_DNS_PROVIDER:-}"
        DNS_CERTBOT_IMAGE="${SAVED_DNS_CERTBOT_IMAGE:-}"
        DNS_CERTBOT_FLAGS="${SAVED_DNS_CERTBOT_FLAGS:-}"
        DNS_CREDENTIALS_FILE="${SAVED_DNS_CREDENTIALS_FILE:-}"

        N8N_DOMAIN="${SAVED_N8N_DOMAIN:-}"
        LETSENCRYPT_EMAIL="${SAVED_LETSENCRYPT_EMAIL:-}"
        # Empty until determine_ssl_cert_domain has chosen the lineage
        SSL_CERT_DOMAIN="${SAVED_SSL_CERT_DOMAIN:-}"

        DB_NAME="${SAVED_DB_NAME:-}"
        DB_USER="${SAVED_DB_USER:-}"
        DB_PASSWORD="${SAVED_DB_PASSWORD:-}"

        POSTGRES_CONTAINER="${SAVED_POSTGRES_CONTAINER:-}"
        N8N_CONTAINER="${SAVED_N8N_CONTAINER:-}"
        NGINX_CONTAINER="${SAVED_NGINX_CONTAINER:-}"
        CERTBOT_CONTAINER="${SAVED_CERTBOT_CONTAINER:-}"

        N8N_TIMEZONE="${SAVED_N8N_TIMEZONE:-}"
        N8N_ENCRYPTION_KEY="${SAVED_N8N_ENCRYPTION_KEY:-}"

        MGMT_PORT="${SAVED_MGMT_PORT:-}"
        ADMIN_USER="${SAVED_ADMIN_USER:-}"
        ADMIN_PASS="${SAVED_ADMIN_PASS:-}"

        NFS_CONFIGURED="${SAVED_NFS_CONFIGURED:-false}"
        NFS_SERVER="${SAVED_NFS_SERVER:-}"
        NFS_PATH="${SAVED_NFS_PATH:-}"
        NFS_LOCAL_MOUNT="${SAVED_NFS_LOCAL_MOUNT:-}"

        INSTALL_PORTAINER="${SAVED_INSTALL_PORTAINER:-false}"
        INSTALL_PORTAINER_AGENT="${SAVED_INSTALL_PORTAINER_AGENT:-false}"
        PORTAINER_PORT="${SAVED_PORTAINER_PORT:-}"
        INSTALL_CLOUDFLARE_TUNNEL="${SAVED_INSTALL_CLOUDFLARE_TUNNEL:-false}"
        CLOUDFLARE_TUNNEL_TOKEN="${SAVED_CLOUDFLARE_TUNNEL_TOKEN:-}"
        INSTALL_TAILSCALE="${SAVED_INSTALL_TAILSCALE:-false}"
        TAILSCALE_AUTH_KEY="${SAVED_TAILSCALE_AUTH_KEY:-}"
        TAILSCALE_HOSTNAME="${SAVED_TAILSCALE_HOSTNAME:-}"
        TAILSCALE_ROUTES="${SAVED_TAILSCALE_ROUTES:-}"
        INSTALL_ADMINER="${SAVED_INSTALL_ADMINER:-false}"
        ADMINER_PORT="${SAVED_ADMINER_PORT:-}"
        INSTALL_DOZZLE="${SAVED_INSTALL_DOZZLE:-false}"
        DOZZLE_PORT="${SAVED_DOZZLE_PORT:-}"
        INSTALL_NTFY="${SAVED_INSTALL_NTFY:-false}"
        NTFY_BASE_URL="${SAVED_NTFY_BASE_URL:-}"
        NTFY_PUBLIC_URL="${SAVED_NTFY_PUBLIC_URL:-}"
        NTFY_INTERNAL_URL="${SAVED_NTFY_INTERNAL_URL:-}"
        INSTALL_PUBLIC_WEBSITE="${SAVED_INSTALL_PUBLIC_WEBSITE:-false}"
        PUBLIC_WEBSITE_DOMAIN="${SAVED_PUBLIC_WEBSITE_DOMAIN:-}"
        PUBLIC_WEBSITE_ROOT_DOMAIN="${SAVED_PUBLIC_WEBSITE_ROOT_DOMAIN:-}"
        PUBLIC_WEBSITE_INCLUDE_ROOT="${SAVED_PUBLIC_WEBSITE_INCLUDE_ROOT:-}"

        # Access Control
        INTERNAL_IP_RANGES="${SAVED_INTERNAL_IP_RANGES:-$DEFAULT_INTERNAL_IP_RANGES}"
        CUSTOM_INTERNAL_IPS="${SAVED_CUSTOM_INTERNAL_IPS:-}"
        N8N_NETWORK_SUBNET="${SAVED_N8N_NETWORK_SUBNET:-$N8N_NETWORK_SUBNET}"

        CURRENT_STEP="${SAVED_STEP_NUM:-0}"
        # Older migration runs stored names ("backup", ...) here; a non-numeric
        # step would make every CURRENT_STEP -lt N check misbehave.
        case "$CURRENT_STEP" in
            ''|*[!0-9]*) CURRENT_STEP=0 ;;
        esac
        return 0
    fi
    return 1
}

check_resume() {
    if [ -f "$STATE_FILE" ] && load_state; then
        print_warning "Previous incomplete installation detected."
        echo ""
        echo -e "  ${WHITE}Last completed step:${NC} ${CYAN}${SAVED_STEP_NAME}${NC}"
        if [ -n "$N8N_DOMAIN" ]; then
            echo -e "  ${WHITE}Domain:${NC} ${CYAN}${N8N_DOMAIN}${NC}"
        fi
        echo ""
        echo -e "  ${WHITE}Options:${NC}"
        echo -e "    ${CYAN}1)${NC} Resume from where you left off"
        echo -e "    ${CYAN}2)${NC} Start fresh (clears saved progress)"
        echo ""

        local resume_choice=""
        while [[ ! "$resume_choice" =~ ^[12]$ ]]; do
            echo -ne "${WHITE}  Enter your choice [1-2]${NC}: "
            read resume_choice
        done

        if [ "$resume_choice" = "1" ]; then
            return 0  # Resume
        else
            clear_state
            return 1  # Start fresh
        fi
    fi
    return 1  # No state file, start fresh
}

clear_state() {
    rm -f "$STATE_FILE"
    CURRENT_STEP=0
}

# ═══════════════════════════════════════════════════════════════════════════════
# DNS PROVIDER HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

restore_dns_settings_from_provider() {
    # Restore DNS_CERTBOT_IMAGE and related settings based on DNS_PROVIDER
    # This is needed when loading config that only has DNS_PROVIDER saved
    local provider="${DNS_PROVIDER:-${DNS_PROVIDER_NAME:-}}"

    # Sync variable names (config uses DNS_PROVIDER, code uses DNS_PROVIDER_NAME)
    if [ -n "$DNS_PROVIDER" ] && [ -z "$DNS_PROVIDER_NAME" ]; then
        DNS_PROVIDER_NAME="$DNS_PROVIDER"
    fi

    # Set DNS_CERTBOT_IMAGE based on provider if not already set
    if [ -z "$DNS_CERTBOT_IMAGE" ] && [ -n "$DNS_PROVIDER_NAME" ]; then
        case $DNS_PROVIDER_NAME in
            cloudflare)
                DNS_CERTBOT_IMAGE="certbot/dns-cloudflare:${CERTBOT_VERSION}"
                DNS_CREDENTIALS_FILE="cloudflare.ini"
                ;;
            route53)
                DNS_CERTBOT_IMAGE="certbot/dns-route53:${CERTBOT_VERSION}"
                DNS_CREDENTIALS_FILE="route53.ini"
                ;;
            google)
                DNS_CERTBOT_IMAGE="certbot/dns-google:${CERTBOT_VERSION}"
                DNS_CREDENTIALS_FILE="google.json"
                ;;
            digitalocean)
                DNS_CERTBOT_IMAGE="certbot/dns-digitalocean:${CERTBOT_VERSION}"
                DNS_CREDENTIALS_FILE="digitalocean.ini"
                ;;
            manual|*)
                DNS_CERTBOT_IMAGE="certbot/certbot:${CERTBOT_VERSION}"
                DNS_CREDENTIALS_FILE="credentials.ini"
                ;;
        esac
    fi

    # DNS_CREDENTIALS_FILE must always match the provider (it is written to
    # .env and mounted into the certbot container for renewals)
    if [ -z "$DNS_CREDENTIALS_FILE" ] && [ -n "$DNS_PROVIDER_NAME" ]; then
        case $DNS_PROVIDER_NAME in
            cloudflare)   DNS_CREDENTIALS_FILE="cloudflare.ini" ;;
            route53)      DNS_CREDENTIALS_FILE="route53.ini" ;;
            google)       DNS_CREDENTIALS_FILE="google.json" ;;
            digitalocean) DNS_CREDENTIALS_FILE="digitalocean.ini" ;;
            *)            DNS_CREDENTIALS_FILE="credentials.ini" ;;
        esac
    fi
}

# Path inside the certbot container where the provider's credentials file is
# mounted. Must match the path used at issuance (recorded in the lineage's
# renewal config), otherwise renewals fail. Written to .env as
# DNS_CREDENTIALS_TARGET and used by the certbot service in docker-compose.yaml.
dns_credentials_target() {
    case "${DNS_PROVIDER_NAME:-cloudflare}" in
        route53) echo "/root/.aws/credentials" ;;
        google)  echo "/credentials.json" ;;
        *)       echo "/credentials.ini" ;;
    esac
}

# Make sure the credentials file exists so the certbot bind mount does not make
# Docker create a directory in its place (e.g. for the manual provider).
ensure_dns_credentials_file() {
    local cred_path="${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE:-credentials.ini}"
    if [ -d "$cred_path" ] && [ -z "$(ls -A "$cred_path" 2>/dev/null)" ]; then
        rmdir "$cred_path" 2>/dev/null || true
    fi
    if [ ! -e "$cred_path" ]; then
        touch "$cred_path" && chmod 600 "$cred_path"
    fi
}

restore_optional_services_from_config() {
    # Restore INSTALL_* variables from *_ENABLED variables loaded from config
    # Config saves: CLOUDFLARE_TUNNEL_ENABLED, NTFY_ENABLED, etc.
    # Code uses: INSTALL_CLOUDFLARE_TUNNEL, INSTALL_NTFY, etc.

    # Cloudflare Tunnel
    if [ -n "$CLOUDFLARE_TUNNEL_ENABLED" ]; then
        INSTALL_CLOUDFLARE_TUNNEL="$CLOUDFLARE_TUNNEL_ENABLED"
    fi

    # Tailscale
    if [ -n "$TAILSCALE_ENABLED" ]; then
        INSTALL_TAILSCALE="$TAILSCALE_ENABLED"
    fi

    # Adminer
    if [ -n "$ADMINER_ENABLED" ]; then
        INSTALL_ADMINER="$ADMINER_ENABLED"
    fi

    # Dozzle
    if [ -n "$DOZZLE_ENABLED" ]; then
        INSTALL_DOZZLE="$DOZZLE_ENABLED"
    fi

    # Portainer (full)
    if [ -n "$PORTAINER_ENABLED" ]; then
        INSTALL_PORTAINER="$PORTAINER_ENABLED"
    fi

    # Portainer Agent
    if [ -n "$PORTAINER_AGENT_ENABLED" ]; then
        INSTALL_PORTAINER_AGENT="$PORTAINER_AGENT_ENABLED"
    fi

    # NTFY
    if [ -n "$NTFY_ENABLED" ]; then
        INSTALL_NTFY="$NTFY_ENABLED"
    fi

    # Public Website
    if [ -n "$PUBLIC_WEBSITE_ENABLED" ]; then
        INSTALL_PUBLIC_WEBSITE="$PUBLIC_WEBSITE_ENABLED"
    elif [ -f "${SCRIPT_DIR}/filebrowser.db" ]; then
        # Configs saved by older versions did not record the public website;
        # filebrowser.db only exists when it was installed.
        INSTALL_PUBLIC_WEBSITE=true
    fi

}

# ═══════════════════════════════════════════════════════════════════════════════
# PRE-CONFIGURATION FILE LOADING
# ═══════════════════════════════════════════════════════════════════════════════

load_preconfig() {
    local config_file="$1"

    if [ ! -f "$config_file" ]; then
        print_error "Configuration file not found: $config_file"
        exit 1
    fi

    print_info "Loading configuration from: $config_file"

    # Dry-run in a subshell first: a bad line (e.g. an unquoted value with
    # spaces, which bash runs as a command) would otherwise abort setup.sh
    # under "set -e" without saying why.
    local config_errors
    # (separate bash process: errexit is ignored inside an "if" condition)
    if ! config_errors=$(bash -c 'set -e; source "$1"' _ "$config_file" 2>&1 >/dev/null); then
        print_error "Configuration file $config_file could not be loaded:"
        printf '%s\n' "$config_errors" | sed 's/^/    /'
        print_info "Values containing spaces must be quoted, e.g. INTERNAL_IP_RANGES=\"10.0.0.0/8 192.168.0.0/16\""
        exit 1
    fi

    # Source the config file
    # shellcheck disable=SC1090
    source "$config_file"

    # Map variables to internal names
    N8N_DOMAIN="${DOMAIN:-}"
    DNS_PROVIDER_NAME="${DNS_PROVIDER:-cloudflare}"

    # Database settings
    DB_NAME="${DB_NAME:-n8n}"
    DB_USER="${DB_USER:-n8n}"

    # Container names
    POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-$DEFAULT_POSTGRES_CONTAINER}"
    N8N_CONTAINER="${N8N_CONTAINER:-$DEFAULT_N8N_CONTAINER}"
    NGINX_CONTAINER="${NGINX_CONTAINER:-$DEFAULT_NGINX_CONTAINER}"
    CERTBOT_CONTAINER="${CERTBOT_CONTAINER:-$DEFAULT_CERTBOT_CONTAINER}"

    # Timezone
    N8N_TIMEZONE="${N8N_TIMEZONE:-America/Los_Angeles}"

    # Admin user
    ADMIN_USER="${ADMIN_USER:-admin}"
    ADMIN_PASS="${ADMIN_PASS:-}"
    ADMIN_EMAIL="${ADMIN_EMAIL:-admin@localhost}"

    # Track auto-generated credentials for display at end
    AUTOGEN_DB_PASSWORD=false
    AUTOGEN_ENCRYPTION_KEY=false
    AUTOGEN_MGMT_SECRET=false
    AUTOGEN_ADMIN_PASS=false

    # Database password and n8n encryption key are NOT generated here: an
    # existing installation must keep the secrets stored in its data volumes.
    # configure_database / generate_encryption_key reuse the existing values
    # (or generate new ones for a brand-new install).
    DB_PASSWORD="${POSTGRES_PASSWORD:-}"
    N8N_ENCRYPTION_KEY="${N8N_ENCRYPTION_KEY:-}"

    # Reuse the existing management secret (rotating it logs everyone out)
    if [ -z "$MGMT_SECRET_KEY" ] && [ -f "${SCRIPT_DIR}/.env" ]; then
        MGMT_SECRET_KEY=$(env_get_key "${SCRIPT_DIR}/.env" MGMT_SECRET_KEY) || MGMT_SECRET_KEY=""
    fi

    if [ -z "$MGMT_SECRET_KEY" ] || [ "$MGMT_SECRET_KEY" = "" ]; then
        if command_exists openssl; then
            MGMT_SECRET_KEY=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
        else
            MGMT_SECRET_KEY=$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 32)
        fi
        AUTOGEN_MGMT_SECRET=true
        print_info "Auto-generated management secret key"
    fi

    # Infer service enablement from auth keys/tokens
    # Tailscale: enabled if TAILSCALE_AUTH_KEY is provided
    if [ -n "$TAILSCALE_AUTH_KEY" ] && [ "$TAILSCALE_AUTH_KEY" != "" ]; then
        INSTALL_TAILSCALE=true
        TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-n8n-tailscale}"
        print_success "Tailscale enabled (auth key provided)"
    else
        INSTALL_TAILSCALE=false
    fi

    # Cloudflare Tunnel: enabled if CLOUDFLARE_TUNNEL_TOKEN is provided
    if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ] && [ "$CLOUDFLARE_TUNNEL_TOKEN" != "" ]; then
        INSTALL_CLOUDFLARE_TUNNEL=true
        print_success "Cloudflare Tunnel enabled (token provided)"
    else
        INSTALL_CLOUDFLARE_TUNNEL=false
    fi

    # NTFY: enabled if NTFY_PUBLIC_URL is provided (or explicitly set)
    if [ -n "$NTFY_PUBLIC_URL" ] && [ "$NTFY_PUBLIC_URL" != "" ]; then
        INSTALL_NTFY=true
        NTFY_BASE_URL="$NTFY_PUBLIC_URL"
        print_success "NTFY enabled (public URL provided)"
    elif [ "$NTFY_ENABLED" = "true" ]; then
        INSTALL_NTFY=true
        NTFY_BASE_URL="https://ntfy.${N8N_DOMAIN}"
        NTFY_PUBLIC_URL="$NTFY_BASE_URL"
        print_success "NTFY enabled"
    else
        INSTALL_NTFY=false
    fi

    # Public Website: enabled if PUBLIC_WEBSITE_ENABLED is set
    if [ "$PUBLIC_WEBSITE_ENABLED" = "true" ]; then
        INSTALL_PUBLIC_WEBSITE=true
        print_success "Public Website enabled"
    else
        INSTALL_PUBLIC_WEBSITE=false
    fi

    # Other optional services (use explicit flags)
    INSTALL_ADMINER="${ADMINER_ENABLED:-false}"
    INSTALL_DOZZLE="${DOZZLE_ENABLED:-false}"
    INSTALL_PORTAINER="${PORTAINER_ENABLED:-false}"
    INSTALL_PORTAINER_AGENT="${PORTAINER_AGENT_ENABLED:-false}"

    # Management console image configuration
    # USE_PREBUILT_MANAGEMENT defaults to true if not specified
    USE_PREBUILT_MANAGEMENT="${USE_PREBUILT_MANAGEMENT:-true}"
    MANAGEMENT_IMAGE="${MANAGEMENT_IMAGE:-$DEFAULT_MANAGEMENT_IMAGE}"

    # NFS configuration
    if [ -n "$NFS_SERVER" ] && [ "$NFS_SERVER" != "" ]; then
        # Check if NFS client is installed, install if needed
        if ! command_exists mount.nfs && ! command_exists mount.nfs4; then
            print_info "Installing NFS client packages..."
            detect_os
            if ! install_nfs_client; then
                print_error "Failed to install NFS client. Please install manually."
                exit 1
            fi
        fi

        # Validate NFS server is reachable (with retry loop)
        local nfs_validated=false
        while [ "$nfs_validated" = "false" ]; do
            print_info "Validating NFS server connectivity..."
            if ping -c 1 -W 3 "$NFS_SERVER" >/dev/null 2>&1; then
                print_success "NFS server is reachable: $NFS_SERVER"
                nfs_validated=true
            else
                print_error "Cannot reach NFS server: $NFS_SERVER"
                if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
                    print_error "Cannot continue in auto-confirm mode with unreachable NFS server"
                    exit 1
                fi
                echo ""
                echo -e "  ${WHITE}Options:${NC}"
                echo -e "    ${CYAN}1)${NC} Enter a different NFS server"
                echo -e "    ${CYAN}2)${NC} Retry connection"
                echo -e "    ${CYAN}3)${NC} Skip NFS configuration (use local storage)"
                echo ""
                local nfs_choice=""
                while [[ ! "$nfs_choice" =~ ^[123]$ ]]; do
                    echo -ne "${WHITE}  Enter your choice [1-3]${NC}: "
                    read nfs_choice
                done
                case $nfs_choice in
                    1)
                        echo -ne "${WHITE}  Enter NFS server hostname or IP${NC}: "
                        read NFS_SERVER
                        ;;
                    2)
                        # Retry - loop continues
                        ;;
                    3)
                        NFS_SERVER=""
                        NFS_CONFIGURED=false
                        print_info "Skipping NFS - backups will be stored locally"
                        nfs_validated=true
                        ;;
                esac
            fi
        done

        # Validate NFS export path if server is configured
        if [ -n "$NFS_SERVER" ] && [ "$NFS_SERVER" != "" ]; then
            local export_validated=false
            while [ "$export_validated" = "false" ]; do
                if [ -n "$NFS_PATH" ] && [ "$NFS_PATH" != "" ]; then
                    print_info "Validating NFS export..."
                    if showmount -e "$NFS_SERVER" 2>/dev/null | grep -q "$NFS_PATH"; then
                        print_success "NFS export validated: $NFS_PATH"
                        export_validated=true
                    else
                        print_warning "NFS export '$NFS_PATH' not found on $NFS_SERVER"
                        print_info "Available exports:"
                        showmount -e "$NFS_SERVER" 2>/dev/null | tail -n +2 || echo "  (unable to query exports)"
                        echo ""
                        if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
                            print_error "Cannot continue in auto-confirm mode with invalid NFS export"
                            exit 1
                        fi
                        echo -e "  ${WHITE}Options:${NC}"
                        echo -e "    ${CYAN}1)${NC} Enter a different export path"
                        echo -e "    ${CYAN}2)${NC} Continue anyway (mount may fail later)"
                        echo -e "    ${CYAN}3)${NC} Skip NFS configuration"
                        echo ""
                        local export_choice=""
                        while [[ ! "$export_choice" =~ ^[123]$ ]]; do
                            echo -ne "${WHITE}  Enter your choice [1-3]${NC}: "
                            read export_choice
                        done
                        case $export_choice in
                            1)
                                echo -ne "${WHITE}  Enter NFS export path${NC}: "
                                read NFS_PATH
                                ;;
                            2)
                                print_warning "Continuing with unvalidated NFS export"
                                export_validated=true
                                ;;
                            3)
                                NFS_SERVER=""
                                NFS_CONFIGURED=false
                                print_info "Skipping NFS - backups will be stored locally"
                                export_validated=true
                                ;;
                        esac
                    fi
                else
                    # No export path specified - prompt for one
                    if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
                        print_error "NFS_PATH is required when NFS_SERVER is specified"
                        exit 1
                    fi
                    print_warning "NFS_PATH not specified"
                    print_info "Available exports on $NFS_SERVER:"
                    showmount -e "$NFS_SERVER" 2>/dev/null | tail -n +2 || echo "  (unable to query exports)"
                    echo ""
                    echo -ne "${WHITE}  Enter NFS export path${NC}: "
                    read NFS_PATH
                fi
            done

            # Final NFS configuration
            if [ -n "$NFS_SERVER" ] && [ "$NFS_SERVER" != "" ]; then
                NFS_CONFIGURED=true
                NFS_LOCAL_MOUNT="${NFS_LOCAL_MOUNT:-/mnt/nfs_backups}"
                print_success "NFS backup storage configured"
            fi
        fi
    else
        NFS_CONFIGURED=false
    fi

    # Access control
    INTERNAL_IP_RANGES="${INTERNAL_IP_RANGES:-$DEFAULT_INTERNAL_IP_RANGES}"
    CUSTOM_INTERNAL_IPS="${CUSTOM_INTERNAL_IPS:-}"

    # SSL configuration
    SSL_METHOD="${SSL_METHOD:-certbot}"

    # Set auto-confirm flag early (needed for validation prompts)
    if [ "$AUTO_CONFIRM" = "true" ]; then
        PRECONFIG_AUTO_CONFIRM=true
    else
        PRECONFIG_AUTO_CONFIRM=false
    fi

    # Restore DNS settings based on provider
    restore_dns_settings_from_provider

    # Set up DNS credentials file content based on provider
    # Validate credentials are provided when using certbot (with interactive correction)
    if [ "$SSL_METHOD" = "certbot" ]; then
        case $DNS_PROVIDER_NAME in
            cloudflare)
                while [ -z "$CLOUDFLARE_API_TOKEN" ] || [ "$CLOUDFLARE_API_TOKEN" = "" ]; do
                    print_error "CLOUDFLARE_API_TOKEN is required when DNS_PROVIDER=cloudflare"
                    if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
                        exit 1
                    fi
                    echo -ne "${WHITE}  Enter Cloudflare API token${NC}: "
                    read CLOUDFLARE_API_TOKEN
                done
                mkdir -p "${SCRIPT_DIR}"
                echo "dns_cloudflare_api_token = $CLOUDFLARE_API_TOKEN" > "${SCRIPT_DIR}/cloudflare.ini"
                chmod 600 "${SCRIPT_DIR}/cloudflare.ini"
                print_success "Cloudflare credentials configured"
                ;;
            route53)
                while [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; do
                    print_error "AWS credentials are required when DNS_PROVIDER=route53"
                    if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
                        exit 1
                    fi
                    if [ -z "$AWS_ACCESS_KEY_ID" ]; then
                        echo -ne "${WHITE}  Enter AWS Access Key ID${NC}: "
                        read AWS_ACCESS_KEY_ID
                    fi
                    if [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
                        echo -ne "${WHITE}  Enter AWS Secret Access Key${NC}: "
                        read AWS_SECRET_ACCESS_KEY
                    fi
                done
                mkdir -p "${SCRIPT_DIR}"
                cat > "${SCRIPT_DIR}/route53.ini" << EOF
[default]
aws_access_key_id = $AWS_ACCESS_KEY_ID
aws_secret_access_key = $AWS_SECRET_ACCESS_KEY
EOF
                chmod 600 "${SCRIPT_DIR}/route53.ini"
                print_success "Route53 credentials configured"
                ;;
            digitalocean)
                while [ -z "$DIGITALOCEAN_TOKEN" ] || [ "$DIGITALOCEAN_TOKEN" = "" ]; do
                    print_error "DIGITALOCEAN_TOKEN is required when DNS_PROVIDER=digitalocean"
                    if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
                        exit 1
                    fi
                    echo -ne "${WHITE}  Enter DigitalOcean API token${NC}: "
                    read DIGITALOCEAN_TOKEN
                done
                mkdir -p "${SCRIPT_DIR}"
                echo "dns_digitalocean_token = $DIGITALOCEAN_TOKEN" > "${SCRIPT_DIR}/digitalocean.ini"
                chmod 600 "${SCRIPT_DIR}/digitalocean.ini"
                print_success "DigitalOcean credentials configured"
                ;;
            google)
                while [ -z "$GOOGLE_CREDENTIALS_FILE" ] || [ ! -f "$GOOGLE_CREDENTIALS_FILE" ]; do
                    if [ -z "$GOOGLE_CREDENTIALS_FILE" ]; then
                        print_error "GOOGLE_CREDENTIALS_FILE is required when DNS_PROVIDER=google"
                    else
                        print_error "Google credentials file not found: $GOOGLE_CREDENTIALS_FILE"
                    fi
                    if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
                        exit 1
                    fi
                    echo -ne "${WHITE}  Enter path to Google credentials JSON file${NC}: "
                    read GOOGLE_CREDENTIALS_FILE
                done
                cp "$GOOGLE_CREDENTIALS_FILE" "${SCRIPT_DIR}/google.json"
                chmod 600 "${SCRIPT_DIR}/google.json"
                print_success "Google DNS credentials configured"
                ;;
            manual)
                print_info "Manual DNS validation selected - you will need to add DNS records manually"
                print_warning "Manual DNS needs an interactive terminal and certificates will NOT auto-renew"
                if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
                    print_error "DNS_PROVIDER=manual cannot be used in auto-confirm mode"
                    exit 1
                fi
                ;;
            *)
                print_error "Unknown DNS_PROVIDER: $DNS_PROVIDER_NAME"
                print_info "Valid options: cloudflare, route53, google, digitalocean, manual"
                if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
                    exit 1
                fi
                echo ""
                echo -e "  ${WHITE}Select DNS provider:${NC}"
                echo -e "    ${CYAN}1)${NC} Cloudflare"
                echo -e "    ${CYAN}2)${NC} Route53 (AWS)"
                echo -e "    ${CYAN}3)${NC} Google Cloud DNS"
                echo -e "    ${CYAN}4)${NC} DigitalOcean"
                echo -e "    ${CYAN}5)${NC} Manual"
                echo ""
                local dns_choice=""
                while [[ ! "$dns_choice" =~ ^[1-5]$ ]]; do
                    echo -ne "${WHITE}  Enter your choice [1-5]${NC}: "
                    read dns_choice
                done
                case $dns_choice in
                    1) DNS_PROVIDER_NAME="cloudflare" ;;
                    2) DNS_PROVIDER_NAME="route53" ;;
                    3) DNS_PROVIDER_NAME="google" ;;
                    4) DNS_PROVIDER_NAME="digitalocean" ;;
                    5) DNS_PROVIDER_NAME="manual" ;;
                esac
                restore_dns_settings_from_provider
                # Re-run the validation with new provider (recursive call would be complex, so just notify)
                print_info "Please re-run with correct DNS_PROVIDER in your config file"
                exit 1
                ;;
        esac
    fi

    # Validate required fields with interactive correction
    # Domain validation
    while [ -z "$N8N_DOMAIN" ] || [ "$N8N_DOMAIN" = "" ]; do
        print_error "DOMAIN is required"
        if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
            print_error "Cannot continue in auto-confirm mode without DOMAIN"
            exit 1
        fi
        echo -ne "${WHITE}  Enter your domain (e.g., n8n.example.com)${NC}: "
        read N8N_DOMAIN
    done

    # Validate domain format (basic check)
    while ! echo "$N8N_DOMAIN" | grep -qE '^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)+$'; do
        print_error "Invalid domain format: $N8N_DOMAIN"
        if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
            print_error "Cannot continue in auto-confirm mode with invalid domain"
            exit 1
        fi
        echo -ne "${WHITE}  Enter a valid domain (e.g., n8n.example.com)${NC}: "
        read N8N_DOMAIN
    done
    print_success "Domain validated: $N8N_DOMAIN"

    # Email validation for certbot
    if [ "$SSL_METHOD" = "certbot" ]; then
        while [ -z "$LETSENCRYPT_EMAIL" ] || [ "$LETSENCRYPT_EMAIL" = "" ]; do
            print_error "LETSENCRYPT_EMAIL is required when using certbot"
            if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
                print_error "Cannot continue in auto-confirm mode without LETSENCRYPT_EMAIL"
                exit 1
            fi
            echo -ne "${WHITE}  Enter email for Let's Encrypt notifications${NC}: "
            read LETSENCRYPT_EMAIL
        done

        # Basic email format validation
        while ! echo "$LETSENCRYPT_EMAIL" | grep -qE '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'; do
            print_error "Invalid email format: $LETSENCRYPT_EMAIL"
            if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
                print_error "Cannot continue in auto-confirm mode with invalid email"
                exit 1
            fi
            echo -ne "${WHITE}  Enter a valid email address${NC}: "
            read LETSENCRYPT_EMAIL
        done
        print_success "Email validated: $LETSENCRYPT_EMAIL"
    fi

    # Admin password validation
    if [ -z "$ADMIN_PASS" ] || [ "$ADMIN_PASS" = "" ]; then
        if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
            # Auto-generate admin password in auto-confirm mode
            if command_exists openssl; then
                ADMIN_PASS=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 16)
            else
                ADMIN_PASS=$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 16)
            fi
            AUTOGEN_ADMIN_PASS=true
            print_info "Auto-generated admin password (will be shown at end of setup)"
        else
            print_warning "Admin password not set in config file"
            while [ -z "$ADMIN_PASS" ] || [ ${#ADMIN_PASS} -lt 8 ]; do
                echo -ne "${WHITE}  Enter admin password (min 8 characters)${NC}: "
                read -s ADMIN_PASS
                echo ""
                if [ ${#ADMIN_PASS} -lt 8 ]; then
                    print_error "Password must be at least 8 characters"
                fi
            done
            print_success "Admin password set"
        fi
    fi

    # Warn about public website without Cloudflare Tunnel
    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ] && [ "$INSTALL_CLOUDFLARE_TUNNEL" != "true" ]; then
        print_warning "Public Website enabled without Cloudflare Tunnel"
        echo ""
        echo -e "  ${YELLOW}The public website runs in a separate nginx container (n8n_nginx_public)${NC}"
        echo -e "  ${GRAY}which requires hostname-based routing to be accessible.${NC}"
        echo -e "  ${GRAY}Without Cloudflare Tunnel, you will need manual DNS/proxy configuration.${NC}"
        echo ""
        if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
            print_warning "Continuing in auto-confirm mode without Cloudflare Tunnel"
            print_info "Public website container will be created but may not be accessible"
            print_info "without additional manual configuration"
        else
            if confirm_prompt "Would you like to enter a Cloudflare Tunnel token now?" "n"; then
                echo -ne "${WHITE}  Enter your Cloudflare Tunnel token${NC}: "
                read -s CLOUDFLARE_TUNNEL_TOKEN
                echo ""
                if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
                    INSTALL_CLOUDFLARE_TUNNEL=true
                    print_success "Cloudflare Tunnel enabled - Public Website will work correctly"
                else
                    print_warning "No token provided"
                    print_info "Public website container will be created but may not be accessible"
                fi
            else
                print_info "Public website container will be created but may not be accessible"
                print_info "without additional manual configuration"
            fi
        fi
        echo ""
    fi

    print_success "Configuration loaded and validated successfully"
    echo ""

    # Set flag for preconfig mode
    PRECONFIG_MODE=true

    # Skip deploy if specified
    if [ "$SKIP_DEPLOY" = "true" ]; then
        PRECONFIG_SKIP_DEPLOY=true
    else
        PRECONFIG_SKIP_DEPLOY=false
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# VERSION DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

detect_current_version() {
    # Only consider it an existing installation if the config file exists
    # This prevents false detection from template files in the repo
    if [ ! -f "${CONFIG_FILE}" ]; then
        echo "none"
        return
    fi

    if [ -f "${SCRIPT_DIR}/docker-compose.yaml" ]; then
        if grep -q "n8n_management" "${SCRIPT_DIR}/docker-compose.yaml" 2>/dev/null; then
            echo "3.0"
        elif grep -q "n8n:" "${SCRIPT_DIR}/docker-compose.yaml" 2>/dev/null; then
            echo "2.0"
        else
            echo "unknown"
        fi
    else
        echo "none"
    fi
}

handle_version_detection() {
    local current_version=$(detect_current_version)

    case $current_version in
        "3.0")
            # Show prominent existing setup detection banner
            echo ""
            echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
            echo -e "${YELLOW}║                                                                           ║${NC}"
            echo -e "${YELLOW}║                     ${BOLD}${YELLOW}⚡  EXISTING SETUP DETECTED  ⚡${NC}                       ${YELLOW}║${NC}"
            echo -e "${YELLOW}║                                                                           ║${NC}"
            echo -e "${YELLOW}║             ${WHITE}Version 3.0 installation found in this directory${NC}              ${YELLOW}║${NC}"
            echo -e "${YELLOW}║            ${GRAY}Your existing configuration and data are preserved${NC}             ${YELLOW}║${NC}"
            echo -e "${YELLOW}║                                                                           ║${NC}"
            echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
            echo ""
            echo -e "  ${WHITE}What would you like to do?${NC}"
            echo ""
            echo -e "    ${CYAN}1)${NC} ${GREEN}Reconfigure${NC} existing installation"
            echo -e "    ${CYAN}2)${NC} Start ${RED}Fresh${NC} (will backup existing config)"
            echo -e "       ${GRAY}Docker volumes keep existing data, DB password and encryption key${NC}"
            echo -e "       ${GRAY}unless you choose to delete them in the next step${NC}"
            echo -e "    ${CYAN}3)${NC} Exit"
            echo ""

            local choice=""
            while [[ ! "$choice" =~ ^[123]$ ]]; do
                echo -ne "${WHITE}  Enter your choice [1-3]${NC}: "
                read choice
            done

            case $choice in
                1)
                    INSTALL_MODE="reconfigure"
                    ;;
                2)
                    backup_existing_config
                    # Existing volumes keep the old DB password / n8n key:
                    # keep them (secrets are reused) or explicitly delete them
                    handle_existing_data_on_fresh
                    INSTALL_MODE="fresh"
                    ;;
                3)
                    print_info "Exiting. Your installation remains unchanged."
                    exit 0
                    ;;
            esac
            ;;
        "2.0")
            print_header "UPGRADE AVAILABLE: v2.0 → v3.0"
            echo -e "  ${GRAY}This upgrade will add:${NC}"
            echo -e "    • Management console for backups and monitoring"
            echo -e "    • Web-based administration interface"
            echo -e "    • Automated backup scheduling"
            echo -e "    • Multi-channel notifications"
            echo ""
            echo -e "  ${GREEN}Your existing data will be preserved.${NC}"
            echo ""

            if confirm_prompt "Upgrade from v2.0 to v3.0?"; then
                INSTALL_MODE="upgrade"
            else
                print_info "Upgrade cancelled. Your v2.0 installation remains unchanged."
                exit 0
            fi
            ;;
        "none")
            print_info "Fresh installation detected"
            INSTALL_MODE="fresh"
            ;;
        *)
            print_error "Unknown installation detected. Manual intervention may be required."
            if confirm_prompt "Attempt fresh installation anyway?"; then
                INSTALL_MODE="fresh"
            else
                exit 1
            fi
            ;;
    esac
}

backup_existing_config() {
    # Create timestamped backup directory
    local backup_timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_dir="${SCRIPT_DIR}/.backups/${backup_timestamp}"

    mkdir -p "$backup_dir"

    print_section "Creating Configuration Backup"
    echo -e "  ${WHITE}Backup location:${NC} ${CYAN}${backup_dir}${NC}"
    echo ""

    local backed_up=0

    # Backup .env file (CRITICAL - contains all secrets)
    if [ -f "${SCRIPT_DIR}/.env" ]; then
        cp "${SCRIPT_DIR}/.env" "${backup_dir}/.env"
        print_success "Backed up .env"
        backed_up=$((backed_up + 1))
    fi

    # Backup setup config file
    if [ -f "${SCRIPT_DIR}/.n8n_setup_config" ]; then
        cp "${SCRIPT_DIR}/.n8n_setup_config" "${backup_dir}/.n8n_setup_config"
        print_success "Backed up .n8n_setup_config"
        backed_up=$((backed_up + 1))
    fi

    # Backup setup state file
    if [ -f "${SCRIPT_DIR}/.n8n_setup_state" ]; then
        cp "${SCRIPT_DIR}/.n8n_setup_state" "${backup_dir}/.n8n_setup_state"
        print_success "Backed up .n8n_setup_state"
        backed_up=$((backed_up + 1))
    fi

    # Backup docker-compose.yaml
    if [ -f "${SCRIPT_DIR}/docker-compose.yaml" ]; then
        cp "${SCRIPT_DIR}/docker-compose.yaml" "${backup_dir}/docker-compose.yaml"
        print_success "Backed up docker-compose.yaml"
        backed_up=$((backed_up + 1))
    fi

    # Backup nginx.conf
    if [ -f "${SCRIPT_DIR}/nginx.conf" ]; then
        cp "${SCRIPT_DIR}/nginx.conf" "${backup_dir}/nginx.conf"
        print_success "Backed up nginx.conf"
        backed_up=$((backed_up + 1))
    fi

    # Backup DNS credential files (Cloudflare, Route53, Google, DigitalOcean)
    for cred_file in cloudflare.ini route53.ini google.json digitalocean.ini credentials.ini; do
        if [ -f "${SCRIPT_DIR}/${cred_file}" ]; then
            cp "${SCRIPT_DIR}/${cred_file}" "${backup_dir}/${cred_file}"
            print_success "Backed up ${cred_file}"
            backed_up=$((backed_up + 1))
        fi
    done

    # Backup any tool auth files
    if [ -f "${SCRIPT_DIR}/portainer_password.txt" ]; then
        cp "${SCRIPT_DIR}/portainer_password.txt" "${backup_dir}/portainer_password.txt"
        print_success "Backed up portainer_password.txt"
        backed_up=$((backed_up + 1))
    fi

    if [ -f "${SCRIPT_DIR}/dozzle_users.yml" ]; then
        cp "${SCRIPT_DIR}/dozzle_users.yml" "${backup_dir}/dozzle_users.yml"
        print_success "Backed up dozzle_users.yml"
        backed_up=$((backed_up + 1))
    fi

    # Backup geo-access.conf if it exists
    if [ -f "${SCRIPT_DIR}/geo-access.conf" ]; then
        cp "${SCRIPT_DIR}/geo-access.conf" "${backup_dir}/geo-access.conf"
        print_success "Backed up geo-access.conf"
        backed_up=$((backed_up + 1))
    fi

    # Backup Let's Encrypt certificates from Docker volume
    if $DOCKER_SUDO docker volume inspect letsencrypt >/dev/null 2>&1; then
        mkdir -p "${backup_dir}/letsencrypt"
        if $DOCKER_SUDO docker run --rm $DOCKER_APPARMOR_OPT \
            -v letsencrypt:/source:ro \
            -v "${backup_dir}/letsencrypt:/backup" \
            "$ALPINE_IMAGE" sh -c "cp -a /source/. /backup/ 2>/dev/null || true" 2>/dev/null; then
            # Check if anything was actually copied
            if [ -n "$(ls -A ${backup_dir}/letsencrypt 2>/dev/null)" ]; then
                print_success "Backed up Let's Encrypt certificates"
                backed_up=$((backed_up + 1))
            else
                rmdir "${backup_dir}/letsencrypt" 2>/dev/null
            fi
        fi
    fi

    echo ""
    if [ $backed_up -gt 0 ]; then
        # Create a manifest file listing what was backed up
        echo "# Backup created: $(date)" > "${backup_dir}/MANIFEST"
        echo "# Files backed up: ${backed_up}" >> "${backup_dir}/MANIFEST"
        ls -la "${backup_dir}" >> "${backup_dir}/MANIFEST"

        print_success "Backup complete! ${backed_up} files saved to ${backup_dir}"

        # Keep only last 10 backups to prevent disk fill
        local backup_count=$(ls -d ${SCRIPT_DIR}/.backups/*/ 2>/dev/null | wc -l)
        if [ "$backup_count" -gt 10 ]; then
            print_info "Cleaning up old backups (keeping last 10)..."
            ls -dt ${SCRIPT_DIR}/.backups/*/ | tail -n +11 | xargs rm -rf
        fi
    else
        print_warning "No configuration files found to backup"
        rmdir "$backup_dir" 2>/dev/null
    fi

    echo ""
    LAST_BACKUP_DIR="$backup_dir"
}

list_available_backups() {
    # List all available backup directories
    local backup_base="${SCRIPT_DIR}/.backups"

    if [ ! -d "$backup_base" ] || [ -z "$(ls -A $backup_base 2>/dev/null)" ]; then
        return 1
    fi

    AVAILABLE_BACKUPS=()
    while IFS= read -r backup_dir; do
        if [ -d "$backup_dir" ]; then
            local timestamp=$(basename "$backup_dir")
            local formatted_date=$(echo "$timestamp" | sed 's/\([0-9]\{4\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)_\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)/\1-\2-\3 \4:\5:\6/')
            local file_count=$(ls -1 "$backup_dir" 2>/dev/null | grep -v MANIFEST | wc -l)
            AVAILABLE_BACKUPS+=("${timestamp}|${formatted_date}|${file_count} files")
        fi
    done < <(ls -dt ${backup_base}/*/ 2>/dev/null)

    if [ ${#AVAILABLE_BACKUPS[@]} -eq 0 ]; then
        return 1
    fi

    return 0
}

rollback_config() {
    print_section "Rollback Configuration"

    if ! list_available_backups; then
        print_error "No backups found in ${SCRIPT_DIR}/.backups/"
        echo ""
        print_info "Backups are created automatically before any reconfiguration."
        return 1
    fi

    echo -e "  ${WHITE}Available backups:${NC}"
    echo ""

    local i=1
    for backup_info in "${AVAILABLE_BACKUPS[@]}"; do
        local timestamp=$(echo "$backup_info" | cut -d'|' -f1)
        local formatted_date=$(echo "$backup_info" | cut -d'|' -f2)
        local file_count=$(echo "$backup_info" | cut -d'|' -f3)
        echo -e "    ${CYAN}${i})${NC} ${WHITE}${formatted_date}${NC} (${file_count})"
        i=$((i + 1))
    done
    echo -e "    ${CYAN}${i})${NC} Cancel - return to menu"
    echo ""

    local max_choice=$i
    local choice=""
    while [[ ! "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "$max_choice" ]; do
        echo -ne "${WHITE}  Select backup to restore [1-${max_choice}]${NC}: "
        read choice
    done

    if [ "$choice" -eq "$max_choice" ]; then
        print_info "Rollback cancelled"
        return 0
    fi

    local selected_index=$((choice - 1))
    local selected_backup=$(echo "${AVAILABLE_BACKUPS[$selected_index]}" | cut -d'|' -f1)
    local backup_dir="${SCRIPT_DIR}/.backups/${selected_backup}"

    echo ""
    echo -e "  ${YELLOW}${BOLD}WARNING: This will overwrite your current configuration!${NC}"
    echo ""
    echo -e "  ${WHITE}Files to be restored from ${CYAN}${selected_backup}${NC}:${NC}"
    ls -1 "$backup_dir" | grep -v MANIFEST | while read file; do
        echo -e "    • ${file}"
    done
    echo ""

    if ! confirm_prompt "Are you sure you want to restore this backup?"; then
        print_info "Rollback cancelled"
        return 0
    fi

    # Create a backup of current state before rollback (safety net)
    print_info "Creating safety backup of current state..."
    local safety_backup="${SCRIPT_DIR}/.backups/pre_rollback_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$safety_backup"
    for file in .env .n8n_setup_config .n8n_setup_state docker-compose.yaml nginx.conf cloudflare.ini route53.ini google.json digitalocean.ini credentials.ini portainer_password.txt dozzle_users.yml geo-access.conf; do
        [ -f "${SCRIPT_DIR}/${file}" ] && cp "${SCRIPT_DIR}/${file}" "${safety_backup}/"
    done
    # Also backup current letsencrypt certs
    if $DOCKER_SUDO docker volume inspect letsencrypt >/dev/null 2>&1; then
        mkdir -p "${safety_backup}/letsencrypt"
        $DOCKER_SUDO docker run --rm $DOCKER_APPARMOR_OPT -v letsencrypt:/source:ro -v "${safety_backup}/letsencrypt:/backup" \
            "$ALPINE_IMAGE" sh -c "cp -a /source/. /backup/ 2>/dev/null || true" 2>/dev/null
    fi

    # Restore files from backup
    print_info "Restoring configuration files..."
    local restored=0
    for file in "$backup_dir"/*; do
        local filename=$(basename "$file")
        if [ "$filename" != "MANIFEST" ] && [ "$filename" != "letsencrypt" ]; then
            cp "$file" "${SCRIPT_DIR}/${filename}"
            print_success "Restored ${filename}"
            restored=$((restored + 1))
        fi
    done

    # Restore Let's Encrypt certificates if they exist in backup
    if [ -d "${backup_dir}/letsencrypt" ] && [ -n "$(ls -A ${backup_dir}/letsencrypt 2>/dev/null)" ]; then
        print_info "Restoring Let's Encrypt certificates..."
        # Create volume if it doesn't exist
        $DOCKER_SUDO docker volume create letsencrypt >/dev/null 2>&1 || true
        if $DOCKER_SUDO docker run --rm $DOCKER_APPARMOR_OPT \
            -v "${backup_dir}/letsencrypt:/source:ro" \
            -v letsencrypt:/dest \
            "$ALPINE_IMAGE" sh -c "rm -rf /dest/* && cp -a /source/. /dest/" 2>/dev/null; then
            print_success "Restored Let's Encrypt certificates"
            restored=$((restored + 1))
        else
            print_warning "Could not restore Let's Encrypt certificates"
        fi
    fi

    echo ""
    print_success "Rollback complete! ${restored} items restored."
    echo ""
    echo -e "  ${WHITE}Safety backup saved to:${NC} ${CYAN}${safety_backup}${NC}"
    echo ""

    if confirm_prompt "Would you like to redeploy the stack with the restored configuration?"; then
        # Reload the restored config
        if [ -f "${SCRIPT_DIR}/.n8n_setup_config" ]; then
            source "${SCRIPT_DIR}/.n8n_setup_config" 2>/dev/null || true
            restore_dns_settings_from_provider
            restore_optional_services_from_config
        fi
        deploy_stack_v3
    else
        print_info "Configuration restored. Run './setup.sh' and choose 'Reconfigure' then option 7 to redeploy."
    fi

    return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# MANAGEMENT PORT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

configure_management_port() {
    print_section "Management Interface Configuration"

    echo -e "  ${GRAY}The management console provides a web interface for:${NC}"
    echo -e "    • Backup scheduling and management"
    echo -e "    • Container monitoring and control"
    echo -e "    • Notification configuration"
    echo -e "    • System health monitoring"
    echo ""

    print_success "Management interface will be available at https://\${DOMAIN}/management/"
}

# ═══════════════════════════════════════════════════════════════════════════════
# NFS CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Persist an NFS share in /etc/fstab and mount it on the host.
#   hard        - I/O waits for the server instead of failing part-way
#                 ("soft" can silently truncate a backup archive)
#   nofail, _netdev, x-systemd.automount
#               - boot never blocks or fails on an unreachable server; the
#                 share is mounted on first access (non-systemd mount(8)
#                 ignores the x-systemd.* options)
# The container sees it through an rslave bind (see generate_docker_compose_v3).
NFS_FSTAB_OPTIONS="hard,nofail,_netdev,x-systemd.automount,x-systemd.mount-timeout=30"

setup_nfs_host_mount() {
    local server="$1" path="$2" local_mount="$3"
    local source="${server}:${path}" tmp fstab="${NFS_FSTAB_FILE:-/etc/fstab}"

    print_info "Creating local mount point: $local_mount"
    run_privileged mkdir -p "$local_mount" || return 1

    # Replace any previous entry for this share or this mount point
    tmp=$(mktemp)
    awk -v src="$source" -v mp="$local_mount" \
        '!/^[[:space:]]*#/ && ($1 == src || $2 == mp) { next } { print }' "$fstab" > "$tmp" 2>/dev/null || cp "$fstab" "$tmp"
    printf '%s %s nfs %s 0 0\n' "$source" "$local_mount" "$NFS_FSTAB_OPTIONS" >> "$tmp"
    if ! run_privileged cp "$tmp" "$fstab"; then
        rm -f "$tmp"
        print_error "Could not update $fstab"
        return 1
    fi
    rm -f "$tmp"
    print_success "NFS mount added to $fstab (${NFS_FSTAB_OPTIONS})"
    if command_exists systemctl && [ -d /run/systemd/system ]; then
        run_privileged systemctl daemon-reload 2>/dev/null || true
        run_privileged systemctl restart remote-fs.target 2>/dev/null || true
    fi

    print_info "Mounting NFS share..."
    if ! mountpoint -q "$local_mount" 2>/dev/null; then
        run_privileged mount "$local_mount" 2>/dev/null || \
            run_privileged mount -t nfs -o rw,hard,nolock "$source" "$local_mount" 2>/dev/null || true
    fi
    # Touching the path also triggers an automount
    if run_privileged touch "${local_mount}/.n8n_test_write" 2>/dev/null; then
        run_privileged rm -f "${local_mount}/.n8n_test_write"
    fi
    if ! awk -v mp="$local_mount" '$2 == mp && $3 ~ /^nfs/ { found = 1 } END { exit !found }' /proc/mounts 2>/dev/null; then
        print_error "NFS share ${source} is not mounted at ${local_mount}. Check the server and run 'mount ${local_mount}'"
        return 1
    fi
    print_success "NFS share mounted at $local_mount"
    if run_privileged touch "${local_mount}/.n8n_test_write" 2>/dev/null; then
        run_privileged rm -f "${local_mount}/.n8n_test_write"
        print_success "NFS share is writable"
    else
        print_warning "NFS share may not be writable - check permissions on NFS server"
    fi
    return 0
}

configure_nfs() {
    print_section "NFS Backup Storage Configuration"

    # In preconfig mode, NFS is already configured by load_preconfig
    if [ "$PRECONFIG_MODE" = "true" ]; then
        if [ -n "$NFS_SERVER" ] && [ "$NFS_SERVER" != "" ]; then
            print_info "Using pre-configured NFS: $NFS_SERVER:$NFS_PATH"
            NFS_LOCAL_MOUNT="${NFS_LOCAL_MOUNT:-/opt/n8n_backups}"
            if ! setup_nfs_host_mount "$NFS_SERVER" "$NFS_PATH" "$NFS_LOCAL_MOUNT"; then
                print_warning "Backups would be written to the local disk under ${NFS_LOCAL_MOUNT} until the share mounts"
            fi
            NFS_CONFIGURED="true"
        else
            print_info "NFS not configured - using local storage"
            NFS_CONFIGURED="false"
        fi
        return
    fi

    echo ""
    echo -e "  ${GRAY}NFS storage allows centralized backup storage on a remote server.${NC}"
    echo -e "  ${GRAY}The NFS share will be mounted on this host and bind-mounted into Docker.${NC}"
    echo -e "  ${GRAY}If you skip this, backups will be stored locally in the container.${NC}"
    echo ""

    if ! confirm_prompt "Configure NFS for backup storage?" "n"; then
        NFS_CONFIGURED="false"
        NFS_SERVER=""
        NFS_PATH=""
        NFS_LOCAL_MOUNT=""
        print_info "Skipping NFS configuration. Backups will be stored locally."
        return
    fi

    # Check NFS client
    if ! command_exists showmount; then
        print_warning "NFS client is not installed."
        if confirm_prompt "Would you like to install NFS client now?"; then
            if ! install_nfs_client; then
                NFS_CONFIGURED="false"
                return
            fi
        else
            print_error "NFS client is required for NFS backup storage."
            NFS_CONFIGURED="false"
            return
        fi
    fi

    # Get NFS server
    while true; do
        echo ""
        echo -ne "${WHITE}  NFS server address (e.g., 192.168.1.100 or nfs.example.com)${NC}: "
        read nfs_server

        if [ -z "$nfs_server" ]; then
            print_error "NFS server is required"
            continue
        fi

        # Test connectivity
        print_info "Testing connection to $nfs_server..."
        if ! timeout 5 showmount -e "$nfs_server" &>/dev/null; then
            print_error "Cannot connect to NFS server: $nfs_server"
            if confirm_prompt "Try again?"; then
                continue
            else
                NFS_CONFIGURED="false"
                return
            fi
        fi

        print_success "NFS server is reachable"
        break
    done

    # Get accessible exports filtered by local IP
    echo ""
    print_info "Checking for accessible NFS exports..."

    local local_ips=$(get_local_ips)
    echo -e "  ${WHITE}This server's IP addresses:${NC}"
    for lip in $local_ips; do
        echo -e "    ${CYAN}${lip}${NC}"
    done
    echo ""

    local nfs_path=""
    local use_manual_entry=false

    if get_accessible_exports "$nfs_server"; then
        if [ ${#ACCESSIBLE_EXPORTS[@]} -eq 1 ]; then
            # Only one export available
            print_success "Found 1 accessible export: ${ACCESSIBLE_EXPORTS[0]}"
            if confirm_prompt "Use ${ACCESSIBLE_EXPORTS[0]}?"; then
                nfs_path="${ACCESSIBLE_EXPORTS[0]}"
            else
                use_manual_entry=true
            fi
        else
            # Multiple exports - use arrow menu
            print_success "Found ${#ACCESSIBLE_EXPORTS[@]} accessible exports"

            # Add manual entry option
            local menu_options=("${ACCESSIBLE_EXPORTS[@]}" "[Enter path manually]")

            select_from_menu "Select NFS export:" "${menu_options[@]}"

            if [ "$MENU_VALUE" = "[Enter path manually]" ]; then
                use_manual_entry=true
            else
                nfs_path="$MENU_VALUE"
            fi
        fi
    else
        print_warning "No exports found that allow access from this server's IP addresses"
        echo ""
        echo -e "  ${GRAY}All exports on server:${NC}"
        showmount -e "$nfs_server" 2>/dev/null | tail -n +2 | sed 's/^/    /'
        echo ""
        use_manual_entry=true
    fi

    # Manual entry fallback
    if [ "$use_manual_entry" = true ]; then
        echo ""
        echo -ne "${WHITE}  NFS export path (e.g., /exports/backups)${NC}: "
        read nfs_path

        if [ -z "$nfs_path" ]; then
            print_error "NFS path is required"
            NFS_CONFIGURED="false"
            return
        fi
    fi

    # Get local mount point on host
    echo ""
    echo -e "  ${GRAY}Choose where to mount the NFS share on this host.${NC}"
    echo -e "  ${GRAY}This directory will be created if it doesn't exist.${NC}"
    echo ""
    echo -ne "${WHITE}  Local mount point [/opt/n8n_backups]${NC}: "
    read nfs_local_mount
    nfs_local_mount="${nfs_local_mount:-/opt/n8n_backups}"

    # Test the selected/entered mount with retry loop
    while true; do
        print_info "Testing NFS mount: ${nfs_server}:${nfs_path}..."
        local test_mount="/tmp/nfs_test_$$"
        mkdir -p "$test_mount"

        if mount -t nfs -o ro,nolock,soft,timeo=10 "${nfs_server}:${nfs_path}" "$test_mount" 2>/dev/null; then
            print_success "NFS mount test successful"
            umount "$test_mount" 2>/dev/null || true
            rmdir "$test_mount" 2>/dev/null || true

            setup_nfs_host_mount "$nfs_server" "$nfs_path" "$nfs_local_mount" || true

            NFS_SERVER="$nfs_server"
            NFS_PATH="$nfs_path"
            NFS_LOCAL_MOUNT="$nfs_local_mount"
            NFS_CONFIGURED="true"
            return
        else
            print_error "Failed to mount NFS share: ${nfs_server}:${nfs_path}"
            rmdir "$test_mount" 2>/dev/null || true

            echo ""
            echo -e "  ${WHITE}Options:${NC}"
            echo -e "    ${CYAN}1)${NC} Try a different export path"
            echo -e "    ${CYAN}2)${NC} Try a different NFS server"
            echo -e "    ${CYAN}3)${NC} Continue without NFS (backups stored locally)"
            echo -e "    ${CYAN}4)${NC} Exit setup"
            echo ""

            local nfs_choice=""
            while [[ ! "$nfs_choice" =~ ^[1-4]$ ]]; do
                echo -ne "${WHITE}  Enter your choice [1-4]${NC}: "
                read nfs_choice
            done

            case $nfs_choice in
                1)
                    # Let them pick again or enter manually
                    echo -ne "${WHITE}  NFS export path${NC}: "
                    read nfs_path
                    if [ -z "$nfs_path" ]; then
                        continue
                    fi
                    ;;
                2)
                    # Restart from server selection
                    configure_nfs
                    return
                    ;;
                3)
                    NFS_CONFIGURED="false"
                    NFS_LOCAL_MOUNT=""
                    print_info "Continuing without NFS. Backups will be stored locally."
                    return
                    ;;
                4)
                    exit 1
                    ;;
            esac
        fi
    done
}

# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

configure_notifications() {
    print_section "Notification System"

    echo ""
    echo -e "  ${GRAY}Notifications are configured via the Management Console after setup.${NC}"
    echo ""
    echo -e "  ${WHITE}Supported notification services (via Apprise):${NC}"
    echo -e "    • Email (SMTP, Gmail, SES)"
    echo -e "    • Slack, Discord, Microsoft Teams"
    echo -e "    • Telegram, Pushover, Pushbullet"
    echo -e "    • Twilio SMS, NTFY"
    echo -e "    • And 80+ more services"
    echo ""
    echo -e "  ${CYAN}Configure at:${NC} https://\${DOMAIN}/management/ → Settings → Notifications"
    echo ""

    NOTIFICATIONS_CONFIGURED="false"
    print_success "Notifications will be configured in the Management Console"
}

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN USER CREATION
# ═══════════════════════════════════════════════════════════════════════════════

create_admin_user() {
    print_section "Management Admin User"

    # In preconfig mode, admin user is already configured by load_preconfig
    if [ "$PRECONFIG_MODE" = "true" ]; then
        print_info "Using pre-configured admin user: $ADMIN_USER"
        return
    fi

    echo ""
    echo -e "  ${GRAY}Create the admin user for the management interface.${NC}"
    echo ""

    echo -ne "${WHITE}  Admin username [admin]${NC}: "
    read admin_user
    admin_user=${admin_user:-admin}

    while true; do
        echo -ne "${WHITE}  Admin password${NC}: "
        read -s admin_pass
        echo ""
        echo -ne "${WHITE}  Confirm password${NC}: "
        read -s admin_pass_confirm
        echo ""

        if [ "$admin_pass" != "$admin_pass_confirm" ]; then
            print_error "Passwords do not match"
            continue
        fi

        if [ ${#admin_pass} -lt 8 ]; then
            print_error "Password must be at least 8 characters"
            continue
        fi

        break
    done

    ADMIN_USER="$admin_user"
    ADMIN_PASS="$admin_pass"

    # Optional email
    echo -ne "${WHITE}  Admin email (optional, for notifications)${NC}: "
    read admin_email
    ADMIN_EMAIL="$admin_email"

    print_success "Admin user configured"
}

# ═══════════════════════════════════════════════════════════════════════════════
# v2.0 TO v3.0 MIGRATION
# ═══════════════════════════════════════════════════════════════════════════════

# Progress of a v2 -> v3 migration (numeric step + name). Kept apart from
# STATE_FILE, whose numeric step drives the fresh-install resume logic.
MIGRATION_PROGRESS_FILE="${SCRIPT_DIR}/.migration_progress"
MIGRATION_STACK_TOUCHED=false
MIGRATION_HAD_ENV=false
MIGRATION_DB_DUMP=""
# Set once v3.0's n8n may have started: it migrates the n8n schema on start,
# which v2.0's n8n cannot read, so a rollback must also restore the database.
MIGRATION_DB_TOUCHED=false
# Result of the last restore_v2_stack database step: skipped|restored|failed
MIGRATION_DB_RESTORE_RESULT="skipped"

save_migration_progress() {
    local num="$1" name="$2"
    printf 'MIGRATION_STEP_NUM=%d\nMIGRATION_STEP_NAME=%s\nMIGRATION_STEP_TIME=%s\n' \
        "$num" "$name" "$(date -Iseconds)" > "$MIGRATION_PROGRESS_FILE"
    chmod 600 "$MIGRATION_PROGRESS_FILE" 2>/dev/null || true
}

migration_compose_cmd() {
    local cmd="docker compose"
    if [ "$USE_STANDALONE_COMPOSE" = true ]; then
        cmd="docker-compose"
    fi
    if [ -n "$DOCKER_SUDO" ]; then
        cmd="$DOCKER_SUDO $cmd"
    fi
    echo "$cmd"
}

# The pre-migration dump recorded in MIGRATION_STATE_FILE, else the newest
# backups/n8n_pre_migration_*.dump. Prints the path relative to SCRIPT_DIR.
find_pre_migration_dump() {
    local dump=""
    if [ -f "$MIGRATION_STATE_FILE" ]; then
        dump=$(grep -o '"backups/n8n_pre_migration_[^"]*\.dump"' "$MIGRATION_STATE_FILE" 2>/dev/null | head -n1 | tr -d '"')
    fi
    if [ -z "$dump" ] || [ ! -s "${SCRIPT_DIR}/${dump}" ]; then
        dump=$(cd "$SCRIPT_DIR" 2>/dev/null && find backups -maxdepth 1 -name 'n8n_pre_migration_*.dump' -size +0 2>/dev/null | sort | tail -n1)
    fi
    [ -n "$dump" ] && [ -s "${SCRIPT_DIR}/${dump}" ] || return 1
    printf '%s\n' "$dump"
}

# Put the n8n database back to the pre-migration dump: stop everything that
# connects to it (n8n, management console), make sure PostgreSQL is up, then
# pg_restore --clean --if-exists in one transaction. Uses the running
# (v3.0) PostgreSQL container, so call it before the v3.0 stack is taken down.
restore_pre_migration_db() {
    local dump="$1" attempt
    local pg="${POSTGRES_CONTAINER:-$DEFAULT_POSTGRES_CONTAINER}"
    local db_user="${DB_USER:-$DEFAULT_DB_USER}" db_name="${DB_NAME:-$DEFAULT_DB_NAME}"

    if [ -z "$dump" ] || [ ! -s "${SCRIPT_DIR}/${dump}" ]; then
        print_error "Pre-migration database dump not found (${dump:-none})"
        return 1
    fi

    print_info "Stopping n8n and the management console before restoring the database..."
    $DOCKER_SUDO docker stop "${N8N_CONTAINER:-$DEFAULT_N8N_CONTAINER}" >/dev/null 2>&1 || true
    $DOCKER_SUDO docker stop "${MANAGEMENT_CONTAINER:-$DEFAULT_MANAGEMENT_CONTAINER}" >/dev/null 2>&1 || true

    if ! $DOCKER_SUDO docker exec "$pg" pg_isready -U "$db_user" >/dev/null 2>&1; then
        $DOCKER_SUDO docker start "$pg" >/dev/null 2>&1 || true
        for attempt in $(seq 1 30); do
            $DOCKER_SUDO docker exec "$pg" pg_isready -U "$db_user" >/dev/null 2>&1 && break
            [ "$attempt" -eq 30 ] && { print_error "PostgreSQL (${pg}) is not running; cannot restore the database"; return 1; }
            sleep 2
        done
    fi

    print_info "Restoring the n8n database from ${dump}..."
    if $DOCKER_SUDO docker exec -i "$pg" pg_restore -U "$db_user" -d "$db_name" \
            --clean --if-exists --single-transaction --exit-on-error < "${SCRIPT_DIR}/${dump}"; then
        print_success "n8n database restored to its pre-migration state"
        return 0
    fi
    print_error "Database restore failed. Restore it by hand before starting n8n v2.0:"
    print_info "  docker exec -i ${pg} pg_restore -U ${db_user} -d ${db_name} --clean --if-exists --single-transaction < ${SCRIPT_DIR}/${dump}"
    return 1
}

# Put the v2.0 files back and (if the stack was touched) restart the v2 stack.
# Backups are copied, not moved, so they survive a failed restore. With
# "restore_db" (and MIGRATION_DB_DUMP set) the n8n database is first put back
# to the pre-migration dump; if that fails v2.0 is NOT started, since its n8n
# cannot run on a schema v3.0 has migrated.
restore_v2_stack() {
    local with_db="${1:-}"
    local docker_compose_cmd rc=0 start_v2=true
    docker_compose_cmd=$(migration_compose_cmd)
    cd "$SCRIPT_DIR" || return 1

    MIGRATION_DB_RESTORE_RESULT="skipped"
    if [ "$with_db" = "restore_db" ]; then
        if restore_pre_migration_db "$MIGRATION_DB_DUMP"; then
            MIGRATION_DB_RESTORE_RESULT="restored"
        else
            MIGRATION_DB_RESTORE_RESULT="failed"
            start_v2=false
            rc=1
        fi
    fi

    if [ "$MIGRATION_STACK_TOUCHED" = true ]; then
        print_info "Stopping v3.0 services..."
        $docker_compose_cmd down --remove-orphans 2>/dev/null || true
    fi

    print_info "Restoring v2.0 configuration..."
    if [ -f "${SCRIPT_DIR}/docker-compose.yaml.v2.backup" ]; then
        cp -p "${SCRIPT_DIR}/docker-compose.yaml.v2.backup" "${SCRIPT_DIR}/docker-compose.yaml" && print_success "Restored docker-compose.yaml" || rc=1
    fi
    if [ -f "${SCRIPT_DIR}/nginx.conf.v2.backup" ]; then
        cp -p "${SCRIPT_DIR}/nginx.conf.v2.backup" "${SCRIPT_DIR}/nginx.conf" && print_success "Restored nginx.conf" || rc=1
    fi
    if [ -f "${SCRIPT_DIR}/.env.v2.backup" ]; then
        cp -p "${SCRIPT_DIR}/.env.v2.backup" "${SCRIPT_DIR}/.env" && print_success "Restored .env" || rc=1
    elif [ "$MIGRATION_HAD_ENV" != true ]; then
        rm -f "${SCRIPT_DIR}/.env"
    fi

    if [ "$MIGRATION_STACK_TOUCHED" = true ] && [ "$start_v2" != true ]; then
        print_warning "v2.0 files are back but the stack was NOT started (database not restored)."
        print_info "After restoring the database: cd ${SCRIPT_DIR} && docker compose up -d"
    elif [ "$MIGRATION_STACK_TOUCHED" = true ]; then
        print_info "Starting v2.0 services..."
        if $docker_compose_cmd up -d; then
            print_success "v2.0 stack restarted"
        else
            print_error "Could not restart the v2.0 stack - run 'docker compose up -d' in ${SCRIPT_DIR}"
            rc=1
        fi
    fi
    return $rc
}

# EXIT trap while a migration is in progress: any failure (set -e, an
# "exit 1" in a helper, Ctrl-C) puts v2.0 back instead of leaving the
# services stopped.
migration_on_exit() {
    local rc=$?
    trap - EXIT
    [ "$rc" -eq 0 ] && return 0
    set +e
    echo ""
    print_error "Migration aborted (exit code ${rc}) - restoring v2.0"
    local db_mode=""
    if [ "$MIGRATION_DB_TOUCHED" = true ] && [ -n "$MIGRATION_DB_DUMP" ]; then
        db_mode="restore_db"
    fi
    if restore_v2_stack "$db_mode"; then
        if [ "$MIGRATION_DB_RESTORE_RESULT" = "restored" ]; then
            print_success "v2.0 restored, including the n8n database as it was before the migration."
        else
            print_success "v2.0 restored. n8n v3.0 never started, so the n8n database was not changed."
        fi
    else
        print_error "Automatic restore was incomplete - see the *.v2.backup files in ${SCRIPT_DIR}"
    fi
    [ -n "$MIGRATION_DB_DUMP" ] && print_info "Pre-migration database dump: ${SCRIPT_DIR}/${MIGRATION_DB_DUMP}"
    print_info "Progress of the failed attempt: ${MIGRATION_PROGRESS_FILE}"
    exit "$rc"
}

# Rollback record read by ./setup.sh --rollback
write_migration_state() {
    local backup_file="$1"
    cat > "$MIGRATION_STATE_FILE" << EOF
{
    "migrated_at": "$(date -Iseconds)",
    "from_version": "2.0",
    "to_version": "3.0",
    "rollback_available_until": "$(date -d '+30 days' -Iseconds 2>/dev/null || date -v+30d -Iseconds 2>/dev/null || echo 'unknown')",
    "backup_files": [
        "docker-compose.yaml.v2.backup",
        "nginx.conf.v2.backup",
        ".env.v2.backup",
        "${backup_file}"
    ]
}
EOF
}

run_migration_v2_to_v3() {
    print_header "Migration: v2.0 → v3.0"

    local docker_compose_cmd
    docker_compose_cmd=$(migration_compose_cmd)
    MANAGEMENT_CONTAINER="${MANAGEMENT_CONTAINER:-$DEFAULT_MANAGEMENT_CONTAINER}"

    if [ -f "$MIGRATION_PROGRESS_FILE" ]; then
        local last_step
        last_step=$(sed -n 's/^MIGRATION_STEP_NAME=//p' "$MIGRATION_PROGRESS_FILE" 2>/dev/null)
        print_warning "A previous migration attempt stopped at: ${last_step:-unknown}. Starting over (v2.0 is still in place)."
    fi

    # Recover the existing secrets BEFORE touching anything. The v2 .env uses
    # POSTGRES_PASSWORD (not DB_PASSWORD) and the database/n8n volumes are
    # kept, so the migrated .env must carry the exact same values.
    env_adopt_existing_values "${SCRIPT_DIR}/.env"
    DB_USER="${DB_USER:-$DEFAULT_DB_USER}"
    DB_NAME="${DB_NAME:-$DEFAULT_DB_NAME}"
    POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-$DEFAULT_POSTGRES_CONTAINER}"
    if [ -z "${DB_PASSWORD:-}" ]; then
        DB_PASSWORD=$(detect_running_postgres_password 2>/dev/null) || DB_PASSWORD=""
    fi
    if [ -z "${N8N_ENCRYPTION_KEY:-}" ]; then
        N8N_ENCRYPTION_KEY=$(read_n8n_encryption_key_from_volume 2>/dev/null) || N8N_ENCRYPTION_KEY=""
    fi
    if [ -z "${DB_PASSWORD:-}" ] || [ -z "${N8N_ENCRYPTION_KEY:-}" ]; then
        print_error "Could not determine the existing PostgreSQL password and/or n8n encryption key."
        print_info "Make sure ${SCRIPT_DIR}/.env contains POSTGRES_PASSWORD and N8N_ENCRYPTION_KEY"
        print_info "(or that the v2 containers still exist) and re-run. Nothing has been changed."
        exit 1
    fi
    print_success "Existing database password and encryption key will be preserved"

    # Pre-flight checks that need nothing to be stopped
    cd "$SCRIPT_DIR"
    if ! check_n8n_network_subnet_free; then
        print_error "Migration aborted before touching the running stack."
        exit 1
    fi

    # Phase 1: Pre-migration backup (abort if the database dump fails)
    print_section "Phase 1: Pre-Migration Backup"
    save_migration_progress 1 "backup"

    print_info "Creating complete backup before migration..."

    cp -p "${SCRIPT_DIR}/docker-compose.yaml" "${SCRIPT_DIR}/docker-compose.yaml.v2.backup"
    print_success "Backed up docker-compose.yaml"

    if [ -f "${SCRIPT_DIR}/nginx.conf" ]; then
        cp -p "${SCRIPT_DIR}/nginx.conf" "${SCRIPT_DIR}/nginx.conf.v2.backup"
        print_success "Backed up nginx.conf"
    fi

    if [ -f "${SCRIPT_DIR}/.env" ]; then
        MIGRATION_HAD_ENV=true
        (umask 077 && cp -p "${SCRIPT_DIR}/.env" "${SCRIPT_DIR}/.env.v2.backup")
        print_success "Backed up .env"
    fi

    print_info "Backing up PostgreSQL database..."
    mkdir -p "${SCRIPT_DIR}/backups"
    local backup_file
    backup_file="backups/n8n_pre_migration_$(date +%Y%m%d_%H%M%S).dump"
    if ! (umask 077 && $DOCKER_SUDO docker exec "$POSTGRES_CONTAINER" \
            pg_dump -U "$DB_USER" -d "$DB_NAME" -F c > "${SCRIPT_DIR}/${backup_file}"); then
        rm -f "${SCRIPT_DIR}/${backup_file}"
        print_error "Database backup failed (is ${POSTGRES_CONTAINER} running?). Migration aborted - nothing was changed."
        exit 1
    fi
    if [ ! -s "${SCRIPT_DIR}/${backup_file}" ] || \
       ! $DOCKER_SUDO docker exec -i "$POSTGRES_CONTAINER" pg_restore -l < "${SCRIPT_DIR}/${backup_file}" >/dev/null 2>&1; then
        print_error "Database backup ${backup_file} is empty or unreadable. Migration aborted - nothing was changed."
        exit 1
    fi
    MIGRATION_DB_DUMP="$backup_file"
    print_success "Database backup saved and verified: ${backup_file}"

    # From here on, any failure restores v2.0
    trap migration_on_exit EXIT

    # Phase 2: Configure and generate v3.0 files (v2.0 keeps running)
    print_section "Phase 2: Configuring v3.0 Features"
    save_migration_progress 2 "config"

    # The management console connects with the existing n8n role
    # (init-db.sh never runs on an already-initialised volume, so no separate
    # role exists). generate_env_file writes MGMT_DB_USER/MGMT_DB_PASSWORD
    # from DB_USER/DB_PASSWORD.
    MGMT_DB_USER="${MGMT_DB_USER:-$DB_USER}"

    # Get existing config values
    if [ -f "$CONFIG_FILE" ]; then
        # shellcheck disable=SC1090
        source "$CONFIG_FILE" 2>/dev/null || true
    fi

    configure_management_port
    configure_nfs
    configure_notifications
    create_admin_user

    generate_env_file
    generate_tool_auth_files
    generate_docker_compose_v3

    # One cert lineage for nginx.conf, issuance and renewal
    determine_ssl_cert_domain
    generate_nginx_conf_v3
    generate_public_nginx_conf
    generate_nginx_router_conf

    # nginx would restart-loop without the certificate it now points at
    verify_ssl_cert_lineage_for_nginx

    # Phase 3: Stop v2.0 and prepare the database
    print_section "Phase 3: Stopping Services"
    save_migration_progress 3 "stop_services"
    MIGRATION_STACK_TOUCHED=true

    print_info "Stopping n8n services..."
    $docker_compose_cmd stop n8n 2>/dev/null || true
    $docker_compose_cmd stop nginx 2>/dev/null || true
    print_success "Services stopped"

    print_section "Phase 4: Database Preparation"
    save_migration_progress 4 "database"
    print_info "Creating management database..."
    if $DOCKER_SUDO docker exec "$POSTGRES_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
            "SELECT 1 FROM pg_database WHERE datname='${DEFAULT_MGMT_DB_NAME}'" 2>/dev/null | grep -q 1; then
        print_success "Management database already exists"
    else
        $DOCKER_SUDO docker exec "$POSTGRES_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" \
            -c "CREATE DATABASE ${DEFAULT_MGMT_DB_NAME};" >/dev/null
        print_success "Management database created"
    fi

    # Phase 5: Build and start new services
    print_section "Phase 5: Starting v3.0 Services"
    save_migration_progress 5 "start_services"

    print_info "Starting all services..."
    # n8n v3.0 migrates its schema as soon as it starts, even if "up" later
    # fails: from here on a rollback restores the database too.
    MIGRATION_DB_TOUCHED=true
    $docker_compose_cmd up -d --remove-orphans

    # Phase 6: Verification
    print_section "Phase 6: Verification"
    save_migration_progress 6 "verify"

    local healthy=true
    if ! wait_for_services; then
        healthy=false
    fi
    if ! verify_migration; then
        healthy=false
    fi

    if [ "$healthy" != true ]; then
        print_error "Migration verification failed!"
        if confirm_prompt "Roll back to v2.0 now (the v2.0 stack is restarted)?" "y"; then
            exit 1   # migration_on_exit restores v2.0
        fi
        trap - EXIT
        write_migration_state "$backup_file"
        print_warning "Leaving the v3.0 stack running for troubleshooting."
        print_info "Roll back later with: ./setup.sh --rollback"
        print_info "Pre-migration database dump: ${SCRIPT_DIR}/${backup_file}"
        exit 1
    fi

    trap - EXIT
    print_success "Migration completed successfully!"

    # Record migration for rollback window
    write_migration_state "$backup_file"
    rm -f "$MIGRATION_PROGRESS_FILE"

    echo ""
    print_info "Management interface: https://${N8N_DOMAIN}/management/"
    print_info "Rollback available for 30 days if needed (./setup.sh --rollback)"

    clear_state
}

# Health of the core services, checked inside the containers (the n8n and
# management ports are not published on the host).
wait_for_services() {
    print_info "Waiting for services to be healthy..."

    local max_attempts=60
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        local all_healthy=true

        if ! $DOCKER_SUDO docker exec "$POSTGRES_CONTAINER" pg_isready -U "$DB_USER" >/dev/null 2>&1; then
            all_healthy=false
        fi

        if ! $DOCKER_SUDO docker exec "$N8N_CONTAINER" wget -q -O - http://localhost:5678/healthz >/dev/null 2>&1; then
            all_healthy=false
        fi

        if [ "$all_healthy" = true ]; then
            echo ""
            print_success "All services are healthy"
            return 0
        fi

        attempt=$((attempt + 1))
        sleep 2
        printf "\r  ${GRAY}Waiting for services... (%d/%d)${NC}" $attempt $max_attempts
    done

    echo ""
    print_warning "Some services are not healthy after $((max_attempts * 2))s"
    return 1
}

# Docker healthcheck status of a container: healthy/unhealthy/starting,
# "none" without a healthcheck, empty if the container does not exist.
container_health_status() {
    $DOCKER_SUDO docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$1" 2>/dev/null
}

verify_migration() {
    local all_ok=true container status attempt
    local mgmt="${MANAGEMENT_CONTAINER:-$DEFAULT_MANAGEMENT_CONTAINER}"

    for container in $N8N_CONTAINER $POSTGRES_CONTAINER $NGINX_CONTAINER $mgmt; do
        if ! $DOCKER_SUDO docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            print_error "Container $container is not running"
            all_ok=false
        else
            print_success "Container $container is running"
        fi
    done

    if $DOCKER_SUDO docker exec "$N8N_CONTAINER" wget -q -O - http://localhost:5678/healthz >/dev/null 2>&1; then
        print_success "n8n health check passed"
    else
        print_error "n8n health check failed"
        all_ok=false
    fi

    # Management console: its compose healthcheck (curl /api/health inside
    # the container); allow for the 30s start period.
    status=""
    for attempt in $(seq 1 24); do
        status=$(container_health_status "$mgmt")
        case "$status" in
            healthy|none|"") break ;;
        esac
        sleep 5
    done
    if [ "$status" = "healthy" ]; then
        print_success "Management API health check passed"
    elif [ "$status" = "none" ] && \
         $DOCKER_SUDO docker exec "$mgmt" curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
        print_success "Management API health check passed"
    else
        print_error "Management API health check failed (status: ${status:-missing})"
        all_ok=false
    fi

    if $DOCKER_SUDO docker exec "$NGINX_CONTAINER" nginx -t >/dev/null 2>&1; then
        print_success "nginx configuration test passed"
    else
        print_error "nginx is not running or rejected its configuration (docker logs ${NGINX_CONTAINER})"
        all_ok=false
    fi

    if $DOCKER_SUDO docker exec "$POSTGRES_CONTAINER" pg_isready -U "$DB_USER" > /dev/null 2>&1; then
        print_success "PostgreSQL health check passed"
    else
        print_error "PostgreSQL health check failed"
        all_ok=false
    fi

    $all_ok
}

rollback_to_v2() {
    print_header "Rolling Back to v2.0"

    MIGRATION_STACK_TOUCHED=true
    MIGRATION_HAD_ENV=true

    # Container names and DB login of the running (v3.0) install
    env_adopt_existing_values "${SCRIPT_DIR}/.env"

    # n8n v3.0 has migrated the n8n schema; v2.0's n8n cannot use it.
    local db_mode="" dump
    if dump=$(find_pre_migration_dump); then
        print_warning "n8n v3.0 has migrated the n8n database; n8n v2.0 needs the pre-migration copy."
        print_info "Restoring ${dump} discards everything changed in n8n since the migration"
        print_info "(workflows, credentials, executions). Export anything you need first."
        if confirm_prompt "Restore the n8n database from ${dump}?" "y"; then
            MIGRATION_DB_DUMP="$dump"
            db_mode="restore_db"
        else
            print_warning "Keeping the current database: n8n v2.0 may fail to start on the migrated schema."
        fi
    else
        print_warning "No pre-migration database dump found in ${SCRIPT_DIR}/backups."
        print_warning "Only files are restored; n8n v2.0 may fail to start on the migrated schema."
    fi

    if restore_v2_stack "$db_mode"; then
        if [ "$MIGRATION_DB_RESTORE_RESULT" = "restored" ]; then
            print_success "Rollback complete. System and n8n database restored to v2.0"
        else
            print_success "Rollback complete. Files restored to v2.0 (database unchanged)"
        fi
    else
        print_error "Rollback incomplete - check the *.v2.backup files in ${SCRIPT_DIR}"
        return 1
    fi

    # Clean up migration state
    rm -f "$MIGRATION_STATE_FILE" "$MIGRATION_PROGRESS_FILE"
}

# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY INSTALLATION
# ═══════════════════════════════════════════════════════════════════════════════

install_docker_linux() {
    print_info "Installing Docker..."
    echo ""

    # Detect distribution (use global DISTRO if already set)
    local distro="${DISTRO:-}"
    if [ -z "$distro" ]; then
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            distro=$ID
        elif [ -f /etc/debian_version ]; then
            distro="debian"
        elif [ -f /etc/redhat-release ]; then
            distro="rhel"
        fi
    fi

    case $distro in
        ubuntu|debian|linuxmint|pop)
            print_info "Detected Debian/Ubuntu-based system"
            echo ""

            # Remove old versions
            run_privileged apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

            # Install prerequisites
            run_privileged apt-get update
            run_privileged apt-get install -y \
                ca-certificates \
                curl \
                gnupg \
                lsb-release

            # Add Docker GPG key
            run_privileged install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/$distro/gpg | run_privileged gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            run_privileged chmod a+r /etc/apt/keyrings/docker.gpg

            # Add Docker repository
            echo \
                "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$distro \
                $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
                run_privileged tee /etc/apt/sources.list.d/docker.list > /dev/null

            # Install Docker
            run_privileged apt-get update
            run_privileged apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

            ;;
        centos|rhel|fedora|rocky|almalinux)
            print_info "Detected RHEL/CentOS-based system"
            echo ""

            # Remove old versions
            run_privileged yum remove -y docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine 2>/dev/null || true

            # Install prerequisites
            run_privileged yum install -y yum-utils

            # Add Docker repository
            run_privileged yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

            # Install Docker
            run_privileged yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

            ;;
        *)
            print_error "Unsupported distribution: $distro"
            print_info "Please install Docker manually: https://docs.docker.com/engine/install/"
            exit 1
            ;;
    esac

    # Start and enable Docker
    run_privileged systemctl start docker
    run_privileged systemctl enable docker

    # Add current user to docker group
    if [ -n "$REAL_USER" ] && [ "$REAL_USER" != "root" ]; then
        run_privileged usermod -aG docker "$REAL_USER"
        print_warning "Added $REAL_USER to docker group. You may need to log out and back in for this to take effect."
    fi

    print_success "Docker installed successfully!"

    # Verify installation
    local docker_version=$(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',')
    print_success "Docker version: $docker_version"

    # Run hello-world test
    print_info "Running Docker hello-world test..."
    if run_privileged docker run --rm hello-world >/dev/null 2>&1; then
        print_success "Docker hello-world test passed!"
    elif run_privileged docker run --rm --security-opt apparmor=unconfined hello-world >/dev/null 2>&1; then
        # Container creation works only without AppArmor confinement — this
        # host cannot load Docker's default profile (e.g. LXC guest).
        APPARMOR_UNCONFINED="true"
        DOCKER_APPARMOR_OPT="--security-opt apparmor=unconfined"
        print_success "Docker hello-world test passed (AppArmor unconfined)"
        print_warning "Docker cannot load its default AppArmor profile on this host"
        print_info "Containers will run with apparmor:unconfined (see docs/TROUBLESHOOTING.md)"
    else
        print_error "Docker hello-world test failed!"
        print_info "You may need to log out and back in, then run setup.sh again."
        exit 1
    fi
}

install_nfs_client() {
    print_info "Installing NFS client..."

    # Use detected distribution or detect package manager
    if [ -n "$DISTRO_FAMILY" ]; then
        case $DISTRO_FAMILY in
            debian)
                run_privileged apt-get update -qq
                run_privileged apt-get install -y -qq nfs-common
                ;;
            rhel|fedora)
                run_privileged $PKG_INSTALL nfs-utils
                ;;
            alpine)
                run_privileged apk add nfs-utils
                ;;
            *)
                print_error "Cannot install NFS client for this distribution. Please install manually."
                return 1
                ;;
        esac
    elif command_exists apt-get; then
        run_privileged apt-get update -qq
        run_privileged apt-get install -y -qq nfs-common
    elif command_exists yum; then
        run_privileged yum install -y nfs-utils
    elif command_exists dnf; then
        run_privileged dnf install -y nfs-utils
    elif command_exists apk; then
        run_privileged apk add nfs-utils
    else
        print_error "Cannot determine package manager. Please install NFS client manually."
        return 1
    fi

    print_success "NFS client installed"
    return 0
}

check_and_install_docker() {
    print_section "Docker Environment Check"

    local CURRENT_PLATFORM=""
    if [ "$(uname)" = "Darwin" ]; then
        CURRENT_PLATFORM="macos"
    elif grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null; then
        CURRENT_PLATFORM="wsl"
    else
        CURRENT_PLATFORM="linux"
    fi

    if command_exists docker; then
        local docker_version=$(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',')
        print_success "Docker is installed (version: $docker_version)"

        if docker info >/dev/null 2>&1; then
            print_success "Docker daemon is running"
        else
            print_warning "Docker is installed but daemon is not running"
            if [ "$CURRENT_PLATFORM" = "linux" ]; then
                if confirm_prompt "Would you like to start the Docker daemon?"; then
                    run_privileged systemctl start docker
                    run_privileged systemctl enable docker
                    print_success "Docker daemon started and enabled"
                else
                    print_error "Docker daemon is required. Please start it manually."
                    exit 1
                fi
            else
                print_error "Please start Docker Desktop and run this script again."
                exit 1
            fi
        fi
    else
        print_warning "Docker is not installed."
        echo ""

        if [ "$CURRENT_PLATFORM" = "linux" ]; then
            if confirm_prompt "Would you like to install Docker now?"; then
                install_docker_linux
            else
                print_error "Docker is required. Please install it manually."
                echo -e "  ${GRAY}https://docs.docker.com/engine/install/${NC}"
                exit 1
            fi
        else
            print_error "Please install Docker Desktop and run this script again."
            echo -e "  ${GRAY}macOS: https://docs.docker.com/desktop/install/mac-install/${NC}"
            echo -e "  ${GRAY}Windows: https://docs.docker.com/desktop/install/windows-install/${NC}"
            exit 1
        fi
    fi

    # Check Docker Compose
    if docker compose version >/dev/null 2>&1; then
        local compose_version=$(docker compose version --short 2>/dev/null)
        print_success "Docker Compose is available (version: $compose_version)"
        USE_STANDALONE_COMPOSE=false
    elif command_exists docker-compose; then
        local compose_version=$(docker-compose --version 2>/dev/null | cut -d' ' -f4 | tr -d ',')
        print_success "Docker Compose (standalone) is available (version: $compose_version)"
        USE_STANDALONE_COMPOSE=true
    else
        print_error "Docker Compose is not available. Please install it."
        exit 1
    fi

    # Set DOCKER_SUDO based on permissions
    if [ "$(id -u)" -eq 0 ]; then
        DOCKER_SUDO=""
    elif [ "$CURRENT_PLATFORM" = "macos" ]; then
        DOCKER_SUDO=""
    elif docker ps >/dev/null 2>&1; then
        DOCKER_SUDO=""
    else
        DOCKER_SUDO="sudo"
    fi

    # Detect hosts that cannot load AppArmor policy (e.g. Docker in LXC)
    apparmor_unconfined_required || true
}

perform_system_checks() {
    print_section "System Requirements Check"

    local all_checks_passed=true

    # Detect platform for system checks
    local CHECK_PLATFORM=""
    if [ "$(uname)" = "Darwin" ]; then
        CHECK_PLATFORM="macos"
    else
        CHECK_PLATFORM="linux"
    fi

    # Check available disk space (need at least 5GB)
    local available_space=""
    if [ "$CHECK_PLATFORM" = "macos" ]; then
        available_space=$(df -g "$SCRIPT_DIR" | awk 'NR==2 {print $4}')
    else
        available_space=$(df -BG "$SCRIPT_DIR" | awk 'NR==2 {print $4}' | tr -d 'G')
    fi

    if [ -n "$available_space" ] && [ "$available_space" -ge 5 ] 2>/dev/null; then
        print_success "Disk space: ${available_space}GB available (5GB required)"
    else
        print_warning "Disk space: ${available_space:-unknown}GB available (5GB recommended)"
        all_checks_passed=false
    fi

    # Check available memory (recommend at least 2GB)
    local total_memory=""
    if [ "$CHECK_PLATFORM" = "macos" ]; then
        total_memory=$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1024/1024/1024}')
    else
        total_memory=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}')
    fi

    if [ -n "$total_memory" ] && [ "$total_memory" -ge 2 ] 2>/dev/null; then
        print_success "Memory: ${total_memory}GB total (2GB required)"
    elif [ -n "$total_memory" ]; then
        print_warning "Memory: ${total_memory}GB total (2GB recommended)"
        all_checks_passed=false
    else
        print_info "Memory: Unable to determine (2GB recommended)"
    fi

    # Check if port 443 is available
    local port_in_use=false
    if [ "$CHECK_PLATFORM" = "macos" ]; then
        if lsof -iTCP:443 -sTCP:LISTEN 2>/dev/null | grep -q LISTEN; then
            port_in_use=true
        fi
    else
        if ss -tulpn 2>/dev/null | grep -q ':443 ' || netstat -tulpn 2>/dev/null | grep -q ':443 '; then
            port_in_use=true
        fi
    fi

    if [ "$port_in_use" = true ]; then
        print_warning "Port 443 is currently in use"
        if [ "$CHECK_PLATFORM" = "macos" ]; then
            lsof -iTCP:443 -sTCP:LISTEN 2>/dev/null || true
        else
            ss -tulpn 2>/dev/null | grep ':443 ' || netstat -tulpn 2>/dev/null | grep ':443 ' || true
        fi
        all_checks_passed=false
    else
        print_success "Port 443 is available"
    fi

    # Check if openssl is available
    if command_exists openssl; then
        print_success "OpenSSL is available"
    else
        print_warning "OpenSSL is not installed (needed for encryption key generation)"
        all_checks_passed=false
    fi

    # Check if curl is available
    if command_exists curl; then
        print_success "curl is available"
    else
        print_warning "curl is not installed"
        all_checks_passed=false
    fi

    # Check internet connectivity
    if curl -s --connect-timeout 5 https://hub.docker.com >/dev/null 2>&1; then
        print_success "Internet connectivity OK"
    else
        print_warning "Cannot reach Docker Hub - check internet connection"
        all_checks_passed=false
    fi

    if [ "$all_checks_passed" = false ]; then
        echo ""
        if ! confirm_prompt "Some checks failed. Continue anyway?"; then
            exit 1
        fi
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# GENERATE AUTH FILES FOR TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

# Print a bcrypt hash (cost 12) of $1. The password is passed on stdin, never
# on a command line (where any local user could read it from the process list).
BCRYPT_COST=12
generate_bcrypt_hash() {
    local password="$1"
    local hash=""

    # Try Python with bcrypt first
    if command_exists python3; then
        hash=$(printf '%s' "$password" | python3 -c "
import sys
pw = sys.stdin.buffer.read()
try:
    import bcrypt
    print(bcrypt.hashpw(pw, bcrypt.gensalt(rounds=${BCRYPT_COST})).decode())
except ImportError:
    try:
        from passlib.hash import bcrypt as passlib_bcrypt
        print(passlib_bcrypt.using(rounds=${BCRYPT_COST}).hash(pw.decode()))
    except ImportError:
        sys.exit(1)
" 2>/dev/null)
    fi

    # Fallback to htpasswd if available (-i: password from stdin)
    if [ -z "$hash" ] && command_exists htpasswd; then
        hash=$(printf '%s\n' "$password" | htpasswd -niBC "$BCRYPT_COST" admin 2>/dev/null | cut -d: -f2)
    fi

    # Fallback to Docker if available
    if [ -z "$hash" ] && command_exists docker; then
        hash=$(printf '%s\n' "$password" | ${DOCKER_SUDO:-} docker run --rm -i $DOCKER_APPARMOR_OPT "$HTPASSWD_IMAGE" \
            htpasswd -niBC "$BCRYPT_COST" admin 2>/dev/null | cut -d: -f2)
    fi

    echo "$hash"
}

generate_tool_auth_files() {
    print_info "Generating authentication files for tools..."

    # Portainer reads its initial admin password from this file (mounted as a
    # compose secret); it is only used when Portainer initialises its database.
    if [ "$INSTALL_PORTAINER" = true ]; then
        (umask 077 && printf '%s' "$ADMIN_PASS" > "${SCRIPT_DIR}/portainer_password.txt")
        chmod 600 "${SCRIPT_DIR}/portainer_password.txt"
    fi

    # Generate bcrypt hash of admin password
    local bcrypt_hash
    bcrypt_hash=$(generate_bcrypt_hash "$ADMIN_PASS")

    if [ -z "$bcrypt_hash" ]; then
        print_warning "Could not generate bcrypt hash - tools will use default authentication"
        return 1
    fi

    # Create Dozzle users.yml
    mkdir -p "${SCRIPT_DIR}/dozzle"
    cat > "${SCRIPT_DIR}/dozzle/users.yml" << EOF
users:
  ${ADMIN_USER}:
    password: "${bcrypt_hash}"
    name: "${ADMIN_USER}"
    email: "${ADMIN_EMAIL:-admin@localhost}"
EOF
    chmod 600 "${SCRIPT_DIR}/dozzle/users.yml"

    print_success "Tool authentication files generated"
    return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# .env HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
# These functions are self-contained (no dependency on installer state) so that
# tests/test_env_helpers.sh can extract and exercise them without Docker.
#
# Encoding rules (must stay compatible with `docker compose`, `source .env` in
# bash, and the management console's parser in management/api/services/env_file.py):
#   * plain values ([A-Za-z0-9_./:@,+=%-]) are written unquoted
#   * anything else without a single quote is written '...'  (literal, no $-interpolation)
#   * values containing a single quote, or ending in a backslash (compose would
#     read '...\' as an escaped closing quote), are written "..." with \ " $ escaped
#   * values containing newlines, or a backtick together with a single quote or
#     a trailing backslash, are rejected (compose and bash disagree on escaping
#     ` inside "...")

# Encode a value for a .env file. Returns 1 for values that cannot be stored.
env_quote_value() {
    local v="$1"
    case "$v" in
        *$'\n'*|*$'\r'*) return 1 ;;
        *"'"*'`'*|*'`'*"'"*|*'`'*\\) return 1 ;;
    esac
    if [[ "$v" =~ ^[A-Za-z0-9_./:@,+=%-]*$ ]]; then
        printf '%s' "$v"
    elif [[ "$v" != *"'"* && "$v" != *\\ ]]; then
        printf "'%s'" "$v"
    else
        v="${v//\\/\\\\}"
        v="${v//\"/\\\"}"
        v="${v//\$/\\\$}"
        printf '"%s"' "$v"
    fi
}

# Decode the raw right-hand side of a KEY=VALUE line.
env_unquote_value() {
    local raw="$1" out="" ch i n
    raw="${raw#"${raw%%[![:space:]]*}"}"
    case "$raw" in
        \'*)
            raw="${raw#\'}"
            printf '%s' "${raw%%\'*}"
            ;;
        \"*)
            raw="${raw#\"}"
            n=${#raw}
            for ((i = 0; i < n; i++)); do
                ch="${raw:i:1}"
                if [ "$ch" = "\\" ] && [ $((i + 1)) -lt "$n" ]; then
                    i=$((i + 1))
                    out+="${raw:i:1}"
                elif [ "$ch" = '"' ]; then
                    break
                else
                    out+="$ch"
                fi
            done
            printf '%s' "$out"
            ;;
        *)
            # Unquoted: drop an inline " # comment" and trailing whitespace
            raw="${raw%%[[:space:]]#*}"
            raw="${raw%"${raw##*[![:space:]]}"}"
            printf '%s' "$raw"
            ;;
    esac
}

# env_get_key FILE KEY - print the decoded value of KEY (last occurrence wins).
# Returns 1 if the file or key does not exist.
env_get_key() {
    local file="$1" key="$2" line raw="" found=1
    [ -f "$file" ] || return 1
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"
        if [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=(.*)$ ]] \
            && [ "${BASH_REMATCH[2]}" = "$key" ]; then
            raw="${BASH_REMATCH[3]}"
            found=0
        fi
    done < "$file"
    [ "$found" -eq 0 ] || return 1
    env_unquote_value "$raw"
}

# env_set_key FILE KEY VALUE - set KEY in FILE, preserving every other line
# (comments, ordering, keys the installer does not manage). The file is
# rewritten atomically (temp file created with umask 077, then mv) and left
# with mode 600. A key whose decoded value is already VALUE is left untouched.
env_set_key() {
    local file="$1" key="$2" value="$3" encoded current tmp src
    if ! [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        echo "env_set_key: invalid key name '$key'" >&2
        return 1
    fi
    if ! encoded=$(env_quote_value "$value"); then
        echo "env_set_key: value for $key cannot be stored in .env (newline, or both ' and \`)" >&2
        return 1
    fi
    if [ -f "$file" ] && current=$(env_get_key "$file" "$key") && [ "$current" = "$value" ]; then
        return 0
    fi
    src="$file"
    [ -f "$src" ] || src=/dev/null
    tmp=$(umask 077 && mktemp "${file}.tmp.XXXXXX") || return 1
    if ! ENV_SET_KEY="$key" ENV_SET_LINE="${key}=${encoded}" awk '
        BEGIN { key = ENVIRON["ENV_SET_KEY"]; line = ENVIRON["ENV_SET_LINE"]; done = 0 }
        {
            probe = $0
            sub(/\r$/, "", probe)
            sub(/^[ \t]+/, "", probe)
            sub(/^export[ \t]+/, "", probe)
            if (match(probe, /^[A-Za-z_][A-Za-z0-9_]*[ \t]*=/)) {
                name = substr(probe, 1, RLENGTH - 1)
                sub(/[ \t]+$/, "", name)
                if (name == key) {
                    if (!done) { print line; done = 1 }
                    next
                }
            }
            print
        }
        END { if (!done) print line }
    ' "$src" > "$tmp"; then
        rm -f "$tmp"
        return 1
    fi
    chmod 600 "$tmp"
    if [ -f "$file" ]; then
        chown --reference="$file" "$tmp" 2>/dev/null || true
    fi
    mv -f "$tmp" "$file"
}

# Mapping between .env keys and installer variables, used both to read an
# existing .env back into the installer and to write it out again.
#   KEY=VAR    adopt the .env value when VAR is empty
#   KEY=VAR?   optional setting: adopt only when VAR is unset (empty = disabled)
# Keys NOT listed here (N8N_API_KEY, MGMT_ENCRYPTION_KEY, other NTFY_* keys,
# anything edited in the management console, ...) are never touched on an
# existing .env. NTFY_TOKEN is listed so a value set in the console is adopted
# and kept; the installer only generates it when it is empty.
env_key_map() {
    cat << 'EOF'
DOMAIN=N8N_DOMAIN
N8N_MANAGEMENT_HOST_IP=N8N_MANAGEMENT_HOST_IP?
POSTGRES_USER=DB_USER
POSTGRES_PASSWORD=DB_PASSWORD
POSTGRES_DB=DB_NAME
N8N_ENCRYPTION_KEY=N8N_ENCRYPTION_KEY
MGMT_SECRET_KEY=MGMT_SECRET_KEY
MGMT_DB_USER=MGMT_DB_USER
MGMT_DB_PASSWORD=MGMT_DB_PASSWORD
MGMT_PORT=MGMT_PORT
ADMIN_USER=ADMIN_USER
ADMIN_PASS=ADMIN_PASS
ADMIN_EMAIL=ADMIN_EMAIL
TIMEZONE=N8N_TIMEZONE
NFS_SERVER=NFS_SERVER?
NFS_PATH=NFS_PATH?
NFS_LOCAL_MOUNT=NFS_LOCAL_MOUNT?
BACKUP_ENCRYPTION_PASSPHRASE=BACKUP_ENCRYPTION_PASSPHRASE?
CLOUDFLARE_TUNNEL_TOKEN=CLOUDFLARE_TUNNEL_TOKEN
TAILSCALE_AUTH_KEY=TAILSCALE_AUTH_KEY
TAILSCALE_HOSTNAME=TAILSCALE_HOSTNAME
TAILSCALE_ROUTES=TAILSCALE_ROUTES?
PUBLIC_SITE_ENABLE=INSTALL_PUBLIC_WEBSITE
DNS_CERTBOT_IMAGE=DNS_CERTBOT_IMAGE
DNS_CERTBOT_FLAGS=DNS_CERTBOT_FLAGS?
DNS_CREDENTIALS_FILE=DNS_CREDENTIALS_FILE
DNS_CREDENTIALS_TARGET=DNS_CREDENTIALS_TARGET
POSTGRES_CONTAINER=POSTGRES_CONTAINER
N8N_CONTAINER=N8N_CONTAINER
NGINX_CONTAINER=NGINX_CONTAINER
CERTBOT_CONTAINER=CERTBOT_CONTAINER
MANAGEMENT_CONTAINER=MANAGEMENT_CONTAINER
NTFY_ADMIN_USER=NTFY_ADMIN_USER
NTFY_ADMIN_PASS=NTFY_ADMIN_PASS
NTFY_ADMIN_PASSWORD_HASH=NTFY_ADMIN_PASSWORD_HASH
NTFY_TOKEN=NTFY_TOKEN
PORTAINER_AGENT_SECRET=PORTAINER_AGENT_SECRET
PORTAINER_AGENT_BIND=PORTAINER_AGENT_BIND
N8N_VERSION=N8N_VERSION?
NGINX_VERSION=NGINX_VERSION?
MGMT_VERSION=MGMT_VERSION?
EOF
}

# Generate the self-hosted ntfy server's credentials (only those still empty):
# an admin user for subscribers/the web app and an access token the console
# publishes with. ntfy provisions both from NTFY_AUTH_USERS/NTFY_AUTH_TOKENS.
ensure_ntfy_credentials() {
    NTFY_ADMIN_USER="${NTFY_ADMIN_USER:-admin}"
    if [ -z "${NTFY_ADMIN_PASS:-}" ]; then
        NTFY_ADMIN_PASS=$(random_secret 24)
        NTFY_ADMIN_PASSWORD_HASH=""
    fi
    if [ -z "${NTFY_ADMIN_PASSWORD_HASH:-}" ]; then
        NTFY_ADMIN_PASSWORD_HASH=$(generate_bcrypt_hash "$NTFY_ADMIN_PASS")
        if [ -z "$NTFY_ADMIN_PASSWORD_HASH" ]; then
            print_error "Could not generate a bcrypt hash for the NTFY admin password (needs python3-bcrypt, htpasswd or Docker)"
            exit 1
        fi
    fi
    # ntfy only accepts tokens of the form tk_ + 29 characters
    if [ -n "${NTFY_TOKEN:-}" ] && ! [[ "$NTFY_TOKEN" =~ ^tk_[-_A-Za-z0-9]{29}$ ]]; then
        print_warning "NTFY_TOKEN in .env is not an ntfy token (tk_...); generating a new one for the local server"
        NTFY_TOKEN=""
    fi
    if [ -z "${NTFY_TOKEN:-}" ]; then
        NTFY_TOKEN="tk_$(random_secret 64 | tr 'A-Z' 'a-z' | head -c 29)"
    fi
}

# Load values from an existing .env into installer variables (POSTGRES_PASSWORD
# -> DB_PASSWORD, TIMEZONE -> N8N_TIMEZONE, ...) without overriding anything
# the installer already knows.
env_adopt_existing_values() {
    local file="$1" key var optional val
    [ -f "$file" ] || return 0
    while IFS='=' read -r key var; do
        [ -n "$key" ] || continue
        optional=false
        if [ "${var%\?}" != "$var" ]; then
            optional=true
            var="${var%\?}"
        fi
        if [ "$optional" = true ]; then
            [ -z "${!var+x}" ] || continue
        else
            [ -z "${!var:-}" ] || continue
        fi
        if val=$(env_get_key "$file" "$key"); then
            if [ "$optional" = true ] || [ -n "$val" ]; then
                printf -v "$var" '%s' "$val"
            fi
        fi
    done < <(env_key_map)
    return 0
}

# Extract "encryptionKey" from n8n's ~/.n8n/config JSON (no jq dependency)
n8n_config_extract_key() {
    tr -d '\r\n' | sed -n 's/.*"encryptionKey"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1
}

# ═══════════════════════════════════════════════════════════════════════════════
# EXISTING DATA / SECRET RECOVERY
# ═══════════════════════════════════════════════════════════════════════════════
# PostgreSQL ignores POSTGRES_PASSWORD once its volume is initialised and n8n
# keeps its encryption key in the n8n_data volume, so an existing install must
# keep using the secrets it was created with.

random_secret() {
    local len="${1:-32}"
    if command_exists openssl; then
        openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c "$len"
    else
        head -c 256 /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c "$len"
    fi
}

# Make sure DOCKER_SUDO is set and the daemon is reachable (safe to call
# before check_and_install_docker, e.g. from the reconfigure/start-fresh menu).
ensure_docker_access() {
    command_exists docker || return 1
    if [ -z "${DOCKER_SUDO+x}" ]; then
        if [ "$(id -u)" -eq 0 ] || docker ps >/dev/null 2>&1; then
            DOCKER_SUDO=""
        elif command_exists sudo; then
            DOCKER_SUDO="sudo"
        else
            return 1
        fi
    fi
    $DOCKER_SUDO docker info >/dev/null 2>&1
}

run_compose() {
    local -a cmd=()
    [ -n "${DOCKER_SUDO:-}" ] && cmd+=("$DOCKER_SUDO")
    if [ "${USE_STANDALONE_COMPOSE:-}" = true ] || ! $DOCKER_SUDO docker compose version >/dev/null 2>&1; then
        cmd+=(docker-compose)
    else
        cmd+=(docker compose)
    fi
    (cd "$SCRIPT_DIR" && "${cmd[@]}" "$@")
}

# find_compose_volume NAME - print the real Docker volume name of the compose
# volume NAME (e.g. n8n_data -> n8n_nginx_n8n_data). Returns 1 if absent.
find_compose_volume() {
    local vol="$1" project="" name="" c
    ensure_docker_access || return 1
    for c in "${POSTGRES_CONTAINER:-$DEFAULT_POSTGRES_CONTAINER}" "${N8N_CONTAINER:-$DEFAULT_N8N_CONTAINER}"; do
        project=$($DOCKER_SUDO docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$c" 2>/dev/null) || project=""
        [ -n "$project" ] && [ "$project" != "<no value>" ] && break
        project=""
    done
    if [ -z "$project" ]; then
        project="${COMPOSE_PROJECT_NAME:-}"
        [ -n "$project" ] || project=$(env_get_key "${SCRIPT_DIR}/.env" COMPOSE_PROJECT_NAME 2>/dev/null) || project=""
        [ -n "$project" ] || project=$(basename "$SCRIPT_DIR")
        project=$(printf '%s' "$project" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-' | sed 's/^[^a-z0-9]*//')
    fi
    name=$($DOCKER_SUDO docker volume ls -q \
        --filter "label=com.docker.compose.project=${project}" \
        --filter "label=com.docker.compose.volume=${vol}" 2>/dev/null | head -n 1)
    if [ -z "$name" ] && $DOCKER_SUDO docker volume inspect "${project}_${vol}" >/dev/null 2>&1; then
        name="${project}_${vol}"
    fi
    [ -n "$name" ] || return 1
    printf '%s\n' "$name"
}

# Print the encryption key n8n stored in its data volume (~/.n8n/config).
read_n8n_encryption_key_from_volume() {
    local cfg="" vol="" img="" candidate c="${N8N_CONTAINER:-$DEFAULT_N8N_CONTAINER}" key
    ensure_docker_access || return 1
    # 1) From the n8n container itself (running or stopped) - no image pull needed
    cfg=$($DOCKER_SUDO docker cp "${c}:/home/node/.n8n/config" - 2>/dev/null | tar -xOf - 2>/dev/null) || cfg=""
    # 2) Straight from the volume with a throwaway container
    if [ -z "$cfg" ]; then
        vol=$(find_compose_volume n8n_data) || return 1
        for candidate in "$ALPINE_IMAGE" alpine:latest alpine pgvector/pgvector:0.8.6-pg16 pgvector/pgvector:pg16 nginx:alpine; do
            if $DOCKER_SUDO docker image inspect "$candidate" >/dev/null 2>&1; then
                img="$candidate"
                break
            fi
        done
        cfg=$($DOCKER_SUDO docker run --rm --network none --entrypoint cat \
            -v "${vol}:/n8n_data:ro" "${img:-$ALPINE_IMAGE}" /n8n_data/config 2>/dev/null) || cfg=""
    fi
    key=$(printf '%s' "$cfg" | n8n_config_extract_key)
    [ -n "$key" ] || return 1
    printf '%s' "$key"
}

# Print POSTGRES_PASSWORD from the existing postgres container's environment.
detect_running_postgres_password() {
    local c="${POSTGRES_CONTAINER:-$DEFAULT_POSTGRES_CONTAINER}" line
    ensure_docker_access || return 1
    line=$($DOCKER_SUDO docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$c" 2>/dev/null \
        | grep -m 1 '^POSTGRES_PASSWORD=') || return 1
    line="${line#POSTGRES_PASSWORD=}"
    [ -n "$line" ] || return 1
    printf '%s' "$line"
}

wait_for_postgres_container() {
    local c="${POSTGRES_CONTAINER:-$DEFAULT_POSTGRES_CONTAINER}" i
    if [ "$($DOCKER_SUDO docker inspect -f '{{.State.Running}}' "$c" 2>/dev/null)" != "true" ]; then
        print_info "Starting PostgreSQL container..."
        run_compose up -d postgres >/dev/null 2>&1 || return 1
    fi
    for i in $(seq 1 30); do
        if $DOCKER_SUDO docker exec "$c" pg_isready -q >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    return 1
}

# Change the password of the existing superuser role inside the running
# database. Must succeed BEFORE the new password is written to .env.
apply_db_password_change() {
    local new_pw="$1" role="${2:-$DB_USER}" db="${3:-$DB_NAME}"
    local c="${POSTGRES_CONTAINER:-$DEFAULT_POSTGRES_CONTAINER}" ident lit
    # Validate first: the new password must be storable in .env afterwards
    if [ -z "$new_pw" ] || ! env_quote_value "$new_pw" >/dev/null; then
        print_error "The new database password is empty or cannot be stored in .env (newline, or both ' and \`)"
        return 1
    fi
    if ! ensure_docker_access; then
        print_error "Docker is not reachable - cannot change the password of the existing database role"
        return 1
    fi
    if ! wait_for_postgres_container; then
        print_error "PostgreSQL container '${c}' is not running/ready - password not changed"
        return 1
    fi
    ident="\"${role//\"/\"\"}\""
    lit="'${new_pw//\'/\'\'}'"
    # Send the statement on stdin so the password never appears in a process list
    if printf 'ALTER ROLE %s WITH PASSWORD %s;\n' "$ident" "$lit" \
        | $DOCKER_SUDO docker exec -i "$c" psql -v ON_ERROR_STOP=1 -q -U "$role" -d "${db:-postgres}" >/dev/null; then
        print_success "Database password for role '${role}' changed (ALTER ROLE)"
        print_warning "Running containers keep the old password until the stack is redeployed"
        DB_PASSWORD_CHANGE_APPLIED=true
        return 0
    fi
    print_error "ALTER ROLE failed - the database password was NOT changed"
    return 1
}

# Called when the user picks "Start Fresh" on an existing installation.
handle_existing_data_on_fresh() {
    local n8n_vol="" pg_vol="" v typed choice="" ts dump_file c
    local -a vols=()
    ensure_docker_access || return 0
    n8n_vol=$(find_compose_volume n8n_data 2>/dev/null) || n8n_vol=""
    pg_vol=$(find_compose_volume postgres_data 2>/dev/null) || pg_vol=""
    [ -n "$n8n_vol" ] && vols+=("$n8n_vol")
    [ -n "$pg_vol" ] && vols+=("$pg_vol")
    [ ${#vols[@]} -gt 0 ] || return 0

    print_section "Existing Data Volumes Detected"
    echo -e "  ${YELLOW}Start Fresh regenerates configuration files, but Docker volumes are NOT removed:${NC}"
    for v in "${vols[@]}"; do
        echo -e "    • ${CYAN}${v}${NC}"
    done
    echo ""
    echo -e "  ${GRAY}PostgreSQL keeps the password it was created with and n8n keeps its${NC}"
    echo -e "  ${GRAY}encryption key inside these volumes. New secrets would NOT match them and${NC}"
    echo -e "  ${GRAY}n8n / the management console would fail to start.${NC}"
    echo ""
    echo -e "  ${WHITE}Options:${NC}"
    echo -e "    ${CYAN}1)${NC} Keep existing data and reuse the existing secrets ${GREEN}(recommended)${NC}"
    echo -e "    ${CYAN}2)${NC} ${RED}DELETE${NC} the volumes above and start with empty data"
    echo -e "    ${CYAN}3)${NC} Exit"
    echo ""

    if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
        print_info "AUTO_CONFIRM: keeping existing data (volumes are never deleted automatically)"
        return 0
    fi
    while [[ ! "$choice" =~ ^[123]$ ]]; do
        echo -ne "${WHITE}  Enter your choice [1-3]${NC}: "
        read choice
    done
    case $choice in
        1)
            print_success "Existing data will be kept; existing secrets will be reused"
            return 0
            ;;
        3)
            print_info "Exiting. Your installation remains unchanged."
            exit 0
            ;;
    esac

    if [ -n "$pg_vol" ] && confirm_prompt "Create a pg_dumpall backup of the database before deleting?" "y"; then
        c="${POSTGRES_CONTAINER:-$DEFAULT_POSTGRES_CONTAINER}"
        ts=$(date +%Y%m%d_%H%M%S)
        dump_file="${SCRIPT_DIR}/backups/pre_fresh_${ts}.sql.gz"
        mkdir -p "${SCRIPT_DIR}/backups"
        local dump_user
        dump_user=$(env_get_key "${SCRIPT_DIR}/.env" POSTGRES_USER 2>/dev/null) || dump_user=""
        dump_user="${dump_user:-${DB_USER:-$DEFAULT_DB_USER}}"
        if wait_for_postgres_container \
            && (umask 077 && set -o pipefail && $DOCKER_SUDO docker exec "$c" pg_dumpall -U "$dump_user" | gzip > "$dump_file") \
            && [ -s "$dump_file" ]; then
            print_success "Database backup saved to ${dump_file}"
        else
            rm -f "$dump_file"
            print_error "Database backup failed"
            if ! confirm_prompt "Continue deleting WITHOUT a database backup?" "n"; then
                print_info "Keeping existing data; existing secrets will be reused"
                return 0
            fi
        fi
    fi

    echo ""
    echo -e "  ${RED}This permanently deletes all n8n workflows, credentials, executions and${NC}"
    echo -e "  ${RED}management console data stored in the volumes listed above.${NC}"
    echo -ne "${WHITE}  Type DELETE to confirm${NC}: "
    read typed
    if [ "$typed" != "DELETE" ]; then
        print_info "Not confirmed - keeping existing data; existing secrets will be reused"
        return 0
    fi

    print_info "Stopping the stack..."
    run_compose down --remove-orphans >/dev/null 2>&1 || true
    for v in "${vols[@]}"; do
        # Remove any remaining container still holding the volume
        $DOCKER_SUDO docker ps -aq --filter "volume=${v}" | while read -r c; do
            $DOCKER_SUDO docker rm -f "$c" >/dev/null 2>&1 || true
        done
        if $DOCKER_SUDO docker volume rm "$v" >/dev/null; then
            print_success "Removed volume ${v}"
        else
            print_error "Could not remove volume ${v} - aborting"
            exit 1
        fi
    done

    # The old .env belongs to the deleted data (a copy is in .backups/); start clean
    if [ -f "${SCRIPT_DIR}/.env" ]; then
        mv -f "${SCRIPT_DIR}/.env" "${SCRIPT_DIR}/.env.pre-fresh.$(date +%Y%m%d_%H%M%S)"
        print_info "Previous .env moved aside (.env.pre-fresh.*)"
    fi
    unset DB_PASSWORD N8N_ENCRYPTION_KEY MGMT_SECRET_KEY MGMT_DB_USER MGMT_DB_PASSWORD
}

# ═══════════════════════════════════════════════════════════════════════════════
# GENERATE .env FILE
# ═══════════════════════════════════════════════════════════════════════════════

generate_env_file() {
    local env_file="${SCRIPT_DIR}/.env" key var val old_pw vol_key tmp
    local -a missing=()
    print_info "Generating .env file..."

    # Map an existing .env back onto installer variables
    # (POSTGRES_PASSWORD -> DB_PASSWORD, TIMEZONE -> N8N_TIMEZONE, ...)
    env_adopt_existing_values "$env_file"

    # Last-resort recovery of secrets from the existing stack
    if [ -z "${N8N_ENCRYPTION_KEY:-}" ]; then
        N8N_ENCRYPTION_KEY=$(read_n8n_encryption_key_from_volume 2>/dev/null) || N8N_ENCRYPTION_KEY=""
    fi
    if [ -z "${DB_PASSWORD:-}" ]; then
        DB_PASSWORD=$(detect_running_postgres_password 2>/dev/null) || DB_PASSWORD=""
    fi

    # Never write a key that does not match the one n8n stored in its volume
    if [ "${N8N_KEY_VERIFIED:-false}" != true ]; then
        if vol_key=$(read_n8n_encryption_key_from_volume 2>/dev/null) && [ -n "$vol_key" ] \
            && [ "$vol_key" != "${N8N_ENCRYPTION_KEY:-}" ]; then
            print_warning "N8N_ENCRYPTION_KEY does not match the key stored in the n8n data volume - using the volume's key"
            N8N_ENCRYPTION_KEY="$vol_key"
        fi
    fi

    # Never change POSTGRES_PASSWORD in .env unless the role was actually changed
    if [ -f "$env_file" ] && [ "${DB_PASSWORD_CHANGE_APPLIED:-false}" != true ] \
        && old_pw=$(env_get_key "$env_file" POSTGRES_PASSWORD) && [ -n "$old_pw" ] \
        && [ "$old_pw" != "${DB_PASSWORD:-}" ] && find_compose_volume postgres_data >/dev/null 2>&1; then
        print_warning "POSTGRES_PASSWORD differs from the password of the existing database and was not applied with ALTER ROLE - keeping the existing password"
        DB_PASSWORD="$old_pw"
    fi

    # Generate secrets if not already set
    if [ -z "${MGMT_SECRET_KEY:-}" ]; then
        if command_exists openssl; then
            MGMT_SECRET_KEY=$(openssl rand -base64 32)
        else
            MGMT_SECRET_KEY=$(random_secret 32)
        fi
    fi

    # Defaults
    MGMT_PORT="${MGMT_PORT:-${DEFAULT_MGMT_PORT:-3333}}"
    ADMIN_EMAIL="${ADMIN_EMAIL:-admin@localhost}"
    TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-n8n-server}"
    DNS_CERTBOT_IMAGE="${DNS_CERTBOT_IMAGE:-certbot/certbot:${CERTBOT_VERSION}}"
    # Older installs stored a floating certbot/<plugin>:latest - pin it
    case "$DNS_CERTBOT_IMAGE" in
        certbot/*:latest) DNS_CERTBOT_IMAGE="${DNS_CERTBOT_IMAGE%:latest}:${CERTBOT_VERSION}" ;;
    esac
    DNS_CREDENTIALS_FILE="${DNS_CREDENTIALS_FILE:-cloudflare.ini}"
    # The mount target follows the provider; keep the stored one only when the
    # provider is unknown (e.g. a reconfigure that did not touch DNS settings)
    if [ -n "${DNS_PROVIDER_NAME:-}" ] || [ -z "${DNS_CREDENTIALS_TARGET:-}" ]; then
        DNS_CREDENTIALS_TARGET=$(dns_credentials_target)
    fi
    POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-$DEFAULT_POSTGRES_CONTAINER}"
    N8N_CONTAINER="${N8N_CONTAINER:-$DEFAULT_N8N_CONTAINER}"
    NGINX_CONTAINER="${NGINX_CONTAINER:-$DEFAULT_NGINX_CONTAINER}"
    CERTBOT_CONTAINER="${CERTBOT_CONTAINER:-$DEFAULT_CERTBOT_CONTAINER}"
    MANAGEMENT_CONTAINER="${MANAGEMENT_CONTAINER:-$DEFAULT_MANAGEMENT_CONTAINER}"

    # Management console uses the n8n role unless a separate role was configured
    # Self-hosted ntfy: deny-all server, provisioned admin user + publish token
    if [ "${INSTALL_NTFY:-false}" = true ]; then
        ensure_ntfy_credentials
    fi

    # Portainer Agent only accepts a server that presents this secret
    if [ "${INSTALL_PORTAINER_AGENT:-false}" = true ]; then
        PORTAINER_AGENT_SECRET="${PORTAINER_AGENT_SECRET:-$(random_secret 48)}"
        PORTAINER_AGENT_BIND="${PORTAINER_AGENT_BIND:-127.0.0.1}"
    fi

    MGMT_DB_USER="${MGMT_DB_USER:-$DB_USER}"
    if [ "$MGMT_DB_USER" = "$DB_USER" ]; then
        MGMT_DB_PASSWORD="$DB_PASSWORD"
    else
        MGMT_DB_PASSWORD="${MGMT_DB_PASSWORD:-${DB_PASSWORD_PREVIOUS:-$DB_PASSWORD}}"
    fi

    # Abort rather than write a .env the stack cannot start with
    for var in N8N_DOMAIN:DOMAIN DB_USER:POSTGRES_USER DB_PASSWORD:POSTGRES_PASSWORD DB_NAME:POSTGRES_DB \
               N8N_ENCRYPTION_KEY:N8N_ENCRYPTION_KEY MGMT_SECRET_KEY:MGMT_SECRET_KEY MGMT_DB_PASSWORD:MGMT_DB_PASSWORD; do
        val="${var%%:*}"
        if [ -z "${!val:-}" ]; then
            missing+=("${var#*:}")
        fi
    done
    if [ ${#missing[@]} -gt 0 ]; then
        print_error "Refusing to write .env - required value(s) are empty: ${missing[*]}"
        print_info "Restore a previous .env from ${SCRIPT_DIR}/.backups/ or set the value(s) in your setup-config and re-run."
        exit 1
    fi
    while IFS='=' read -r key var; do
        var="${var%\?}"
        if ! env_quote_value "${!var:-}" >/dev/null; then
            print_error "Value for ${key} cannot be written to .env (it contains a newline, or both ' and \`)"
            exit 1
        fi
    done < <(env_key_map)

    if [ -f "$env_file" ]; then
        # Existing install: update installer-managed keys in place; everything
        # else (console-managed keys, custom variables, comments) is preserved.
        while IFS='=' read -r key var; do
            var="${var%\?}"
            if ! env_set_key "$env_file" "$key" "${!var:-}"; then
                print_error "Failed to update ${key} in .env"
                exit 1
            fi
        done < <(env_key_map)
        chmod 600 "$env_file"
        print_success ".env file updated (existing secrets and custom keys preserved)"
    else
        tmp=$(umask 077 && mktemp "${env_file}.tmp.XXXXXX")
        cat > "$tmp" << EOF
# n8n Management System v3.0 - Environment Variables
# Generated by setup.sh on $(date)
# WARNING: This file contains sensitive credentials - do not commit to git!

# ===========================================
# Required Settings
# ===========================================

# Domain name for n8n (used for URLs, SSL certificates, etc.)
DOMAIN=$(env_quote_value "$N8N_DOMAIN")

# Host IP address (local IP that matches the domain)
N8N_MANAGEMENT_HOST_IP=$(env_quote_value "${N8N_MANAGEMENT_HOST_IP:-}")

# PostgreSQL credentials
POSTGRES_USER=$(env_quote_value "$DB_USER")
POSTGRES_PASSWORD=$(env_quote_value "$DB_PASSWORD")
POSTGRES_DB=$(env_quote_value "$DB_NAME")

# n8n encryption key
N8N_ENCRYPTION_KEY=$(env_quote_value "$N8N_ENCRYPTION_KEY")

# Management console (uses same DB credentials as n8n)
MGMT_SECRET_KEY=$(env_quote_value "$MGMT_SECRET_KEY")
MGMT_DB_USER=$(env_quote_value "$MGMT_DB_USER")
MGMT_DB_PASSWORD=$(env_quote_value "$MGMT_DB_PASSWORD")
MGMT_PORT=$(env_quote_value "$MGMT_PORT")

# Admin credentials (for management console)
ADMIN_USER=$(env_quote_value "${ADMIN_USER:-}")
ADMIN_PASS=$(env_quote_value "${ADMIN_PASS:-}")
ADMIN_EMAIL=$(env_quote_value "$ADMIN_EMAIL")

# Timezone
TIMEZONE=$(env_quote_value "${N8N_TIMEZONE:-}")

# ===========================================
# Optional: NFS Backup Storage
# ===========================================
NFS_SERVER=$(env_quote_value "${NFS_SERVER:-}")
NFS_PATH=$(env_quote_value "${NFS_PATH:-}")
NFS_LOCAL_MOUNT=$(env_quote_value "${NFS_LOCAL_MOUNT:-}")
# Backup archive encryption passphrase (empty = archives are NOT encrypted).
# Keep a copy OFF this server: without it encrypted backups cannot be restored.
BACKUP_ENCRYPTION_PASSPHRASE=$(env_quote_value "${BACKUP_ENCRYPTION_PASSPHRASE:-}")

# ===========================================
# Optional: Cloudflare Tunnel
# ===========================================
CLOUDFLARE_TUNNEL_TOKEN=$(env_quote_value "${CLOUDFLARE_TUNNEL_TOKEN:-}")

# ===========================================
# Optional: Tailscale VPN
# ===========================================
TAILSCALE_AUTH_KEY=$(env_quote_value "${TAILSCALE_AUTH_KEY:-}")
TAILSCALE_HOSTNAME=$(env_quote_value "$TAILSCALE_HOSTNAME")
TAILSCALE_ROUTES=$(env_quote_value "${TAILSCALE_ROUTES:-}")

# ===========================================
# Optional: Public Website
# ===========================================
PUBLIC_SITE_ENABLE=$(env_quote_value "${INSTALL_PUBLIC_WEBSITE:-false}")

# ===========================================
# DNS Provider / SSL Certificate Settings
# ===========================================
DNS_CERTBOT_IMAGE=$(env_quote_value "$DNS_CERTBOT_IMAGE")
DNS_CERTBOT_FLAGS=$(env_quote_value "${DNS_CERTBOT_FLAGS:-}")
DNS_CREDENTIALS_FILE=$(env_quote_value "${DNS_CREDENTIALS_FILE:-cloudflare.ini}")
DNS_CREDENTIALS_TARGET=$(env_quote_value "$DNS_CREDENTIALS_TARGET")

# ===========================================
# Container Names (generally don't change)
# ===========================================
POSTGRES_CONTAINER=$(env_quote_value "$POSTGRES_CONTAINER")
N8N_CONTAINER=$(env_quote_value "$N8N_CONTAINER")
NGINX_CONTAINER=$(env_quote_value "$NGINX_CONTAINER")
CERTBOT_CONTAINER=$(env_quote_value "$CERTBOT_CONTAINER")
MANAGEMENT_CONTAINER=$(env_quote_value "$MANAGEMENT_CONTAINER")

# ===========================================
# Optional: Self-hosted NTFY (anonymous access is denied)
# ===========================================
# Admin login for the ntfy web app / mobile subscriptions. If you change
# NTFY_ADMIN_PASS, clear NTFY_ADMIN_PASSWORD_HASH and re-run setup.sh.
NTFY_ADMIN_USER=$(env_quote_value "${NTFY_ADMIN_USER:-}")
NTFY_ADMIN_PASS=$(env_quote_value "${NTFY_ADMIN_PASS:-}")
NTFY_ADMIN_PASSWORD_HASH=$(env_quote_value "${NTFY_ADMIN_PASSWORD_HASH:-}")
# Access token the management console publishes with
NTFY_TOKEN=$(env_quote_value "${NTFY_TOKEN:-}")

# ===========================================
# Optional: Portainer Agent
# ===========================================
# The remote Portainer server must be started with AGENT_SECRET set to this value
PORTAINER_AGENT_SECRET=$(env_quote_value "${PORTAINER_AGENT_SECRET:-}")
PORTAINER_AGENT_BIND=$(env_quote_value "${PORTAINER_AGENT_BIND:-}")

# ===========================================
# Image versions (empty = the version pinned in docker-compose.yaml)
# ===========================================
# Take a backup and read the release notes before changing these, then:
#   docker compose pull && docker compose up -d
N8N_VERSION=$(env_quote_value "${N8N_VERSION:-}")
NGINX_VERSION=$(env_quote_value "${NGINX_VERSION:-}")
MGMT_VERSION=$(env_quote_value "${MGMT_VERSION:-}")
EOF
        chmod 600 "$tmp"
        mv -f "$tmp" "$env_file"
        print_success ".env file generated"
    fi

    # Secure the .env file
    chmod 600 "$env_file"

    # Create env_backups directory for environment variable backups
    mkdir -p "${SCRIPT_DIR}/env_backups"
    print_info "env_backups directory created"
}

# ═══════════════════════════════════════════════════════════════════════════════
# GENERATE v3.0 DOCKER COMPOSE
# ═══════════════════════════════════════════════════════════════════════════════

generate_docker_compose_v3() {
    print_info "Generating docker-compose.yaml for v3.0..."

    # The certbot service mounts ./${DNS_CREDENTIALS_FILE} at
    # ${DNS_CREDENTIALS_TARGET} (both from .env); make sure the file exists.
    ensure_dns_credentials_file

    # Pinned n8n_network subnet + static IPs for the containers that proxy
    # client traffic (must match the geo/realip rules in nginx.conf)
    compute_docker_network_addrs

    # Build into a temp file and move it into place at the end, so an abort
    # part-way through (set -e) never leaves a truncated docker-compose.yaml.
    local compose_tmp="${SCRIPT_DIR}/.docker-compose.yaml.new"
    rm -f "$compose_tmp"

    cat > "$compose_tmp" << 'EOF'
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /docker-compose.yaml
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 1st, 2026
#
# Richard J. Sears
# richard@n8nmanagement.net
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# n8n with Management Console v3.0
# Includes: n8n, PostgreSQL, Nginx, Certbot, Management Console
# Optional: Adminer, Dozzle, Cloudflare Tunnel, Tailscale, Portainer, NTFY

services:
  # ===========================================================================
  # PostgreSQL Database (shared by n8n and management)
  # ===========================================================================
  postgres:
    image: pgvector/pgvector:0.8.6-pg16
    container_name: ${POSTGRES_CONTAINER:-n8n_postgres}
    restart: always
    environment:
      - POSTGRES_USER=${POSTGRES_USER:-n8n}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}
      - POSTGRES_DB=${POSTGRES_DB:-n8n}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sh:/docker-entrypoint-initdb.d/init-db.sh:ro
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -h localhost -U ${POSTGRES_USER:-n8n} -d ${POSTGRES_DB:-n8n}']
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - n8n_network

  # ===========================================================================
  # n8n Workflow Automation
  # ===========================================================================
  n8n:
    image: n8nio/n8n:${N8N_VERSION:-2.41.4}
    container_name: ${N8N_CONTAINER:-n8n}
    restart: always
    environment:
      # Database Configuration
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=${POSTGRES_DB:-n8n}
      - DB_POSTGRESDB_USER=${POSTGRES_USER:-n8n}
      - DB_POSTGRESDB_PASSWORD=${POSTGRES_PASSWORD}
      # n8n Configuration - HTTPS
      - N8N_HOST=${DOMAIN:?DOMAIN is required}
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=https://${DOMAIN}
      - N8N_EDITOR_BASE_URL=https://${DOMAIN}
      # Timezone
      - GENERIC_TIMEZONE=${TIMEZONE:-America/Los_Angeles}
      - TZ=${TIMEZONE:-America/Los_Angeles}
      # Execution Configuration
      - EXECUTIONS_MODE=regular
      - EXECUTIONS_DATA_SAVE_ON_ERROR=all
      - EXECUTIONS_DATA_SAVE_ON_SUCCESS=all
      - EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS=true
      # Security
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY:?N8N_ENCRYPTION_KEY is required}
      - N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
      # Performance & Isolation
      - N8N_PAYLOAD_SIZE_MAX=16
      - N8N_METRICS=false
      # Logging
      - N8N_LOG_LEVEL=info
      - N8N_LOG_OUTPUT=console
      # Community Nodes
      - N8N_COMMUNITY_PACKAGES_ENABLED=true
      # Proxy
      - N8N_TRUST_PROXY=true
      # Telemetry / Outbound n8n.io traffic (silences 429s on
      # /rest/telemetry/proxy/v1/identify when upstream rate-limits)
      - N8N_DIAGNOSTICS_ENABLED=false
      - N8N_VERSION_NOTIFICATIONS_ENABLED=false
      - N8N_TEMPLATES_ENABLED=false
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ['CMD-SHELL', 'wget -q -O- http://localhost:5678/healthz || exit 1']
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    networks:
      - n8n_network

EOF

    # ===========================================================================
    # Nginx Configuration - conditional based on public website
    # ===========================================================================
    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        # With public website: nginx_router handles SSL and port 443
        # n8n_nginx is internal only (port 80)
        cat >> "$compose_tmp" << EOF
  # ===========================================================================
  # Nginx Router (hostname-based routing for internal access)
  # ===========================================================================
  # This container ONLY routes traffic - it has no access to internal services.
  # It allows internal network access without hairpinning through Cloudflare.
  nginx_router:
    image: nginx:\${NGINX_VERSION:-1.30.5-alpine}
    container_name: n8n_nginx_router
    restart: always
    ports:
      - "443:443"
    volumes:
      - ./nginx-router.conf:/etc/nginx/nginx.conf:ro
      - letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - nginx
      - nginx_public
    healthcheck:
      test: ['CMD-SHELL', 'curl -sf --insecure https://localhost/healthz || exit 1']
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    networks:
      n8n_network:
        # Static IP: n8n_nginx trusts X-Real-IP only from this address
        ipv4_address: ${NGINX_ROUTER_IP}

EOF
        cat >> "$compose_tmp" << 'EOF'
  # ===========================================================================
  # Nginx Reverse Proxy (internal - SSL terminated by router)
  # ===========================================================================
  nginx:
    image: nginx:${NGINX_VERSION:-1.30.5-alpine}
    container_name: ${NGINX_CONTAINER:-n8n_nginx}
    restart: always
    expose:
      - "80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - certbot_data:/var/www/certbot:ro
      - letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - n8n
      - n8n_management
    healthcheck:
      test: ['CMD-SHELL', 'curl -sf http://localhost/healthz || exit 1']
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    networks:
      - n8n_network
      # Only nginx can reach File Browser
      - filebrowser_network
EOF
    else
        # Without public website: n8n_nginx handles SSL directly on port 443
        cat >> "$compose_tmp" << 'EOF'
  # ===========================================================================
  # Nginx Reverse Proxy (SSL termination)
  # ===========================================================================
  nginx:
    image: nginx:${NGINX_VERSION:-1.30.5-alpine}
    container_name: ${NGINX_CONTAINER:-n8n_nginx}
    restart: always
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - certbot_data:/var/www/certbot:ro
      - letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - n8n
      - n8n_management
    healthcheck:
      test: ['CMD-SHELL', 'curl -fsk https://localhost/ || exit 1']
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    networks:
      - n8n_network
EOF
    fi

    cat >> "$compose_tmp" << 'EOF'

  # ===========================================================================
  # Certbot (SSL certificate management)
  # ===========================================================================
  certbot:
    image: ${DNS_CERTBOT_IMAGE:-certbot/certbot:v5.8.0}
    container_name: ${CERTBOT_CONTAINER:-n8n_certbot}
    restart: unless-stopped
    environment:
      - NGINX_CONTAINER=${NGINX_CONTAINER:-n8n_nginx}
    volumes:
      - letsencrypt:/etc/letsencrypt
      - certbot_data:/var/www/certbot
      # Provider credentials, mounted where the renewal config recorded at issuance expects them
      - ./${DNS_CREDENTIALS_FILE:-cloudflare.ini}:${DNS_CREDENTIALS_TARGET:-/credentials.ini}:ro
      # Renewal loop + nginx reload deploy hook (scripts/certbot/)
      - ./scripts/certbot:/opt/n8n-certbot:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    # renew-loop.sh runs `certbot renew` every 12h, logs failures to `docker logs`
    # and /etc/letsencrypt/n8n-renewal.log (status in n8n-renewal-status.json),
    # retries hourly after a failure, and installs a deploy hook that reloads
    # nginx through the Docker API (no docker CLI / apk install needed).
    entrypoint: ["/bin/sh", "/opt/n8n-certbot/renew-loop.sh"]
    networks:
      - n8n_network

  # ===========================================================================
  # Management Console (NEW in v3.0)
  # ===========================================================================
  n8n_management:
EOF

    # Add either pre-built image or build context based on user preference
    # Pre-built: pull the pinned release tag; if it is not published yet,
    # compose falls back to the build context. Local build: never pull.
    if [ "$USE_PREBUILT_MANAGEMENT" = "true" ]; then
        cat >> "$compose_tmp" << EOF
    image: ${MANAGEMENT_IMAGE}
EOF
    else
        cat >> "$compose_tmp" << 'EOF'
    pull_policy: build
EOF
    fi
    cat >> "$compose_tmp" << 'EOF'
    build:
      context: ./management
      dockerfile: Dockerfile
      additional_contexts:
        docs_src: .
EOF

    # Continue with the rest of management service configuration
    cat >> "$compose_tmp" << 'EOF'
    container_name: ${MANAGEMENT_CONTAINER:-n8n_management}
    restart: always
    environment:
      # Database connection (using asyncpg driver for async SQLAlchemy)
      - DATABASE_URL=postgresql+asyncpg://${MGMT_DB_USER:-n8n_mgmt}:${MGMT_DB_PASSWORD:-${POSTGRES_PASSWORD}}@postgres:5432/n8n_management
      - N8N_DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-n8n}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-n8n}
      # Security
      - SECRET_KEY=${MGMT_SECRET_KEY:?MGMT_SECRET_KEY is required}
      - ENCRYPTION_KEY=${MGMT_ENCRYPTION_KEY:-${N8N_ENCRYPTION_KEY}}
      # Admin user (created on first startup)
      - ADMIN_USERNAME=${ADMIN_USER}
      - ADMIN_PASSWORD=${ADMIN_PASS}
      - ADMIN_EMAIL=${ADMIN_EMAIL:-admin@localhost}
      # Server
      - HOST=0.0.0.0
      - PORT=8000
      - DEBUG=false
      # n8n API integration
      - N8N_API_KEY=${N8N_API_KEY:-}
      - N8N_EDITOR_BASE_URL=${N8N_EDITOR_BASE_URL:-}
      # NFS Configuration (optional)
      - NFS_SERVER=${NFS_SERVER:-}
      - NFS_PATH=${NFS_PATH:-}
      - NFS_LOCAL_MOUNT=${NFS_LOCAL_MOUNT:-}
      # Timezone
      - TZ=${TIMEZONE:-America/Los_Angeles}
      # PostgreSQL version (for pg_dump compatibility)
      - POSTGRES_VERSION=16
      # Domain for constructing URLs (used in integration examples)
      - DOMAIN=${DOMAIN:-}
      # NTFY public URL (if different from https://ntfy.${DOMAIN})
      - NTFY_PUBLIC_URL=${NTFY_PUBLIC_URL:-}
      # PostgreSQL connection for backups (pg_dump)
      - POSTGRES_HOST=${POSTGRES_CONTAINER:-n8n_postgres}
      - POSTGRES_USER=${POSTGRES_USER:-n8n}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      # nginx container (certificate status falls back to reading it there)
      - NGINX_CONTAINER=${NGINX_CONTAINER:-n8n_nginx}
      # Redis connection (for status caching)
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      # Public website backup/restore
      - PUBLIC_SITE_ENABLE=${PUBLIC_SITE_ENABLE:-false}
EOF

    # Add notification environment variables if configured
    if [ "$NOTIFICATIONS_CONFIGURED" = "true" ]; then
        cat >> "$compose_tmp" << EOF
      # Notifications
      - NOTIF_TYPE=${NOTIF_TYPE:-}
      - NOTIF_CONFIG=${NOTIF_CONFIG:-}
EOF
        if [ -n "$EMAIL_HOST" ]; then
            cat >> "$compose_tmp" << EOF
      - EMAIL_HOST=${EMAIL_HOST}
      - EMAIL_PORT=${EMAIL_PORT}
      - EMAIL_USER=${EMAIL_USER}
      - EMAIL_PASSWORD=${EMAIL_PASSWORD}
      - EMAIL_FROM=${EMAIL_FROM}
      - EMAIL_USE_TLS=${EMAIL_USE_TLS}
EOF
        fi
    fi

    # Add NTFY environment variable if configured
    if [ -n "$NTFY_BASE_URL" ]; then
        cat >> "$compose_tmp" << EOF
      # NTFY Push Notifications
      - NTFY_BASE_URL=${NTFY_BASE_URL}
EOF
        # Access token the console publishes with (the self-hosted server
        # denies anonymous access; for an external server set it in .env)
        cat >> "$compose_tmp" << 'EOF'
      - NTFY_TOKEN=${NTFY_TOKEN:-}
EOF
    fi

    # Status collector URL - needed for Cache tab to reach n8n_status service
    # n8n_status runs on host network, so we need to use host.docker.internal (Docker Desktop)
    # or the Docker gateway IP (Linux). Users can override via STATUS_COLLECTOR_URL env var.
    cat >> "$compose_tmp" << 'EOF'
      # Status Collector (n8n_status service on host network)
      - STATUS_COLLECTOR_URL=${STATUS_COLLECTOR_URL:-http://host.docker.internal:8080}
      # Web terminal root shell on the Docker host: off unless set to true in .env
      - ENABLE_HOST_TERMINAL=${ENABLE_HOST_TERMINAL:-false}
      # Extra browser origins allowed to use the console API (normally empty)
      - ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-}
EOF

    cat >> "$compose_tmp" << EOF
    volumes:
      # Docker socket for container management (read-only)
      - /var/run/docker.sock:/var/run/docker.sock:ro
      # Local backup staging area
      - mgmt_backup_staging:/app/backups
      # Logs
      - mgmt_logs:/app/logs
      # Configuration persistence
      - mgmt_config:/app/config
      # Mount the entire project directory for config file access
      # This is more reliable than individual file mounts which can be shadowed
      - ./:/app/host_project:rw
      # SSL certificates for backup/restore (read-write for selective restore)
      - letsencrypt:/etc/letsencrypt:rw
EOF

    # Add NFS bind mount if configured (host-level NFS mount)
    if [ "$NFS_CONFIGURED" = "true" ] && [ -n "$NFS_LOCAL_MOUNT" ]; then
        # rslave: a share mounted on the host after the container started
        # (boot order, x-systemd.automount) becomes visible inside it.
        cat >> "$compose_tmp" << 'EOF'
      # NFS backup mount (host-level NFS mount, see /etc/fstab)
      - type: bind
        source: ${NFS_LOCAL_MOUNT:-/opt/n8n_backups}
        target: /mnt/backups
        bind:
          propagation: rslave
          create_host_path: true
EOF
    fi

    # Add public website volume mount if configured (for backup/restore)
    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        cat >> "$compose_tmp" << 'EOF'
      # Public website files (read-only for backup)
      - public_web_root:/app/public_website:ro
EOF
    fi

    # n8n_status follows the management console image choice
    local status_build_lines="    build: ./n8n_status"
    if [ "$USE_PREBUILT_MANAGEMENT" != "true" ]; then
        status_build_lines="${status_build_lines}
    pull_policy: build"
    fi

    cat >> "$compose_tmp" << EOF
    expose:
      - "80"
    extra_hosts:
      # Enable host.docker.internal on Linux (already works on Docker Desktop)
      - "host.docker.internal:host-gateway"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ['CMD-SHELL', 'curl -sf http://localhost:8000/api/health || exit 1']
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    networks:
      - n8n_network

  # ===========================================================================
  # Redis - Cache for status data (collected by n8n_status)
  # ===========================================================================
  redis:
    image: redis:7.4.11-alpine
    container_name: n8n_redis
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 128mb --maxmemory-policy allkeys-lru
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - n8n_network

  # ===========================================================================
  # Status Collector - Caches system metrics in Redis
  # ===========================================================================
  n8n_status:
    image: ${STATUS_IMAGE}
${status_build_lines}
    container_name: n8n_status
    restart: unless-stopped
    network_mode: host
    environment:
      - REDIS_HOST=127.0.0.1
      - REDIS_PORT=6379
      - POLL_INTERVAL_METRICS=5
      - POLL_INTERVAL_NETWORK=30
      - POLL_INTERVAL_CONTAINERS=5
      - POLL_INTERVAL_EXTERNAL=15
      - TZ=\${TIMEZONE:-America/Los_Angeles}
      # Container names for status checks
      - CLOUDFLARE_CONTAINER=\${CLOUDFLARE_CONTAINER:-n8n_cloudflared}
      - TAILSCALE_CONTAINER=\${TAILSCALE_CONTAINER:-n8n_tailscale}
      - NTFY_CONTAINER=\${NTFY_CONTAINER:-n8n_ntfy}
      - NTFY_URL=http://127.0.0.1:8083
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      redis:
        condition: service_healthy

EOF

    # Add full Portainer if configured
    if [ "$INSTALL_PORTAINER" = true ]; then
        # The initial admin password is read from portainer_password.txt
        # (written by generate_tool_auth_files, mode 600) as a compose secret.
        cat >> "$compose_tmp" << 'EOF'
  # ===========================================================================
  # Portainer - Container Management UI
  # ===========================================================================
  portainer:
    image: portainer/portainer-ce:2.45.1
    container_name: n8n_portainer
    restart: always
    command: --base-url /portainer --admin-password-file /run/secrets/portainer_admin_password
    secrets:
      - portainer_admin_password
    expose:
      - "9000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - portainer_data:/data
    networks:
      - n8n_network

EOF
    fi

    # Add Portainer Agent if configured (for remote management)
    if [ "$INSTALL_PORTAINER_AGENT" = true ] && [ "$INSTALL_PORTAINER" != true ]; then
        cat >> "$compose_tmp" << 'EOF'
  # ===========================================================================
  # Portainer Agent (for remote Portainer server)
  # ===========================================================================
  # The agent has the Docker socket and the host root filesystem, so it is
  # only published on PORTAINER_AGENT_BIND (default 127.0.0.1; set a LAN or
  # Tailscale IP the Portainer server can reach) and only accepts a server
  # configured with the same AGENT_SECRET. Published ports bypass ufw.
  # It is deliberately not on n8n_network: nothing in the stack talks to it,
  # and the remote server reaches it only through the published port.
  portainer_agent:
    image: portainer/agent:2.45.1
    container_name: portainer_agent
    restart: always
    environment:
      - AGENT_SECRET=${PORTAINER_AGENT_SECRET:?PORTAINER_AGENT_SECRET is required (re-run setup.sh)}
    ports:
      - "${PORTAINER_AGENT_BIND:-127.0.0.1}:9001:9001"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /var/lib/docker/volumes:/var/lib/docker/volumes
      - /:/host

EOF
    fi

    # Add Cloudflare Tunnel if configured
    if [ "$INSTALL_CLOUDFLARE_TUNNEL" = true ]; then
        cat >> "$compose_tmp" << EOF
  # ===========================================================================
  # Cloudflare Tunnel
  # ===========================================================================
  # Point the tunnel's public hostname at HTTP -> n8n_nginx:8080 (webhook-only
  # listener). The static IP is classified "external" by nginx, so even a
  # tunnel pointed elsewhere can never reach the admin paths.
  cloudflared:
    image: cloudflare/cloudflared:2026.9.3
    container_name: n8n_cloudflared
    restart: always
    command: tunnel run
    environment:
      - TUNNEL_TOKEN=\${CLOUDFLARE_TUNNEL_TOKEN}
    networks:
      n8n_network:
        ipv4_address: ${CLOUDFLARED_IP}

EOF
    fi

    # Add Tailscale if configured
    if [ "$INSTALL_TAILSCALE" = true ]; then
        # Generate tailscale-serve.json for Tailscale Serve
        generate_tailscale_serve_config

        cat >> "$compose_tmp" << EOF
  # ===========================================================================
  # Tailscale VPN
  # ===========================================================================
  tailscale:
    image: tailscale/tailscale:v1.102.5
    container_name: n8n_tailscale
    restart: always
    hostname: n8n-tailscale
    environment:
      - TS_AUTHKEY=\${TAILSCALE_AUTH_KEY}
      - TS_HOSTNAME=\${TAILSCALE_HOSTNAME}
      - TS_STATE_DIR=/var/lib/tailscale
      - TS_USERSPACE=true
      - TS_EXTRA_ARGS=--accept-routes
      - TS_ROUTES=\${TAILSCALE_ROUTES}
      - TS_AUTH_ONCE=true
      - TS_SERVE_CONFIG=/config/tailscale-serve.json
    volumes:
      - tailscale_data:/var/lib/tailscale
      - ./tailscale-serve.json:/config/tailscale-serve.json:ro
    cap_add:
      - NET_ADMIN
    networks:
      n8n_network:
        # Static IP: Tailscale Serve proxies tailnet users to nginx from this
        # address, which nginx trusts as "internal"
        ipv4_address: ${TAILSCALE_IP}

EOF
    fi

    # Add Adminer if configured
    if [ "$INSTALL_ADMINER" = true ]; then
        cat >> "$compose_tmp" << EOF
  # ===========================================================================
  # Adminer - Database Management
  # ===========================================================================
  adminer:
    image: adminer:6.1.1
    container_name: n8n_adminer
    restart: always
    environment:
      - ADMINER_DEFAULT_SERVER=\${POSTGRES_CONTAINER:-n8n_postgres}
      - ADMINER_DESIGN=nette
    expose:
      - "8080"
    depends_on:
      - postgres
    networks:
      - n8n_network

EOF
    fi

    # Add Dozzle if configured
    if [ "$INSTALL_DOZZLE" = true ]; then
        cat >> "$compose_tmp" << EOF
  # ===========================================================================
  # Dozzle - Container Log Viewer
  # ===========================================================================
  dozzle:
    image: amir20/dozzle:v11.1.3
    container_name: n8n_dozzle
    restart: always
    environment:
      - DOZZLE_NO_ANALYTICS=true
      - DOZZLE_BASE=/dozzle
      - DOZZLE_AUTH_PROVIDER=simple
    expose:
      - "8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./dozzle/users.yml:/data/users.yml:ro
    networks:
      - n8n_network

EOF
    fi

    # Add NTFY if configured
    if [ "$INSTALL_NTFY" = true ]; then
        cat >> "$compose_tmp" << EOF
  # ===========================================================================
  # NTFY - Push Notification Server
  # Accessible via its own subdomain (configured in Cloudflare Tunnel)
  # ===========================================================================
  ntfy:
    image: binwiederhier/ntfy:v2.28.0
    container_name: n8n_ntfy
    restart: unless-stopped
    init: true
    command:
      - serve
    environment:
      - TZ=\${TIMEZONE:-America/Los_Angeles}
      # NTFY_BASE_URL: Public URL for NTFY (must match Cloudflare Tunnel hostname)
      - NTFY_BASE_URL=${NTFY_PUBLIC_URL}
      # Only needed for iOS instant push (forwards a poll request to ntfy.sh)
      - NTFY_UPSTREAM_BASE_URL=\${NTFY_UPSTREAM_BASE_URL:-}
      - NTFY_BEHIND_PROXY=true
      - NTFY_CACHE_FILE=/var/cache/ntfy/cache.db
      # Authentication: nobody may read or publish anonymously. The admin user
      # and the console's publish token are provisioned from .env.
      - NTFY_AUTH_FILE=/var/lib/ntfy/auth.db
      - NTFY_AUTH_DEFAULT_ACCESS=\${NTFY_AUTH_DEFAULT_ACCESS:-deny-all}
      - NTFY_AUTH_USERS=\${NTFY_ADMIN_USER:-admin}:\${NTFY_ADMIN_PASSWORD_HASH:?NTFY_ADMIN_PASSWORD_HASH is required (re-run setup.sh)}:admin
      - NTFY_AUTH_TOKENS=\${NTFY_ADMIN_USER:-admin}:\${NTFY_TOKEN:?NTFY_TOKEN is required (re-run setup.sh)}:management-console
      - NTFY_ENABLE_LOGIN=\${NTFY_ENABLE_LOGIN:-true}
      - NTFY_ENABLE_SIGNUP=\${NTFY_ENABLE_SIGNUP:-false}
      - NTFY_CACHE_DURATION=\${NTFY_CACHE_DURATION:-24h}
      - NTFY_ATTACHMENT_TOTAL_SIZE_LIMIT=\${NTFY_ATTACHMENT_TOTAL_SIZE_LIMIT:-100M}
      - NTFY_ATTACHMENT_FILE_SIZE_LIMIT=\${NTFY_ATTACHMENT_FILE_SIZE_LIMIT:-15M}
      - NTFY_ATTACHMENT_EXPIRY_DURATION=\${NTFY_ATTACHMENT_EXPIRY_DURATION:-24h}
      - NTFY_KEEPALIVE_INTERVAL=\${NTFY_KEEPALIVE_INTERVAL:-45s}
      # SMTP Email Notifications (optional)
      - NTFY_SMTP_SENDER_ADDR=\${NTFY_SMTP_SENDER_ADDR:-}
      - NTFY_SMTP_SENDER_USER=\${NTFY_SMTP_SENDER_USER:-}
      - NTFY_SMTP_SENDER_PASS=\${NTFY_SMTP_SENDER_PASS:-}
      - NTFY_SMTP_SENDER_FROM=\${NTFY_SMTP_SENDER_FROM:-}
    expose:
      - "80"
    volumes:
      - ntfy_data:/var/lib/ntfy
      - ntfy_cache:/var/cache/ntfy
      - ./ntfy:/etc/ntfy:ro
    networks:
      - n8n_network
    healthcheck:
      test: ["CMD-SHELL", "wget -q --tries=1 http://localhost:80/v1/health -O - | grep -Eo '\"healthy\"\\\\s*:\\\\s*true' || exit 1"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 40s

EOF
    fi

    # Add File Browser if configured (Public Website)
    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        local fb_db="${SCRIPT_DIR}/filebrowser.db"
        # Only create it on first install. On a re-run it is already owned by
        # UID 1000 with mode 600, so a plain touch as another non-root user
        # would fail (Permission denied) and abort setup under set -e.
        if [ ! -e "$fb_db" ]; then
            touch "$fb_db" 2>/dev/null || run_privileged touch "$fb_db" 2>/dev/null || \
                print_warning "Could not create ${fb_db} - Docker will create it as a directory; create it manually"
        fi
        local fb_db_mode
        fb_db_mode=$(stat -c '%u:%a' "$fb_db" 2>/dev/null || stat -f '%u:%Lp' "$fb_db" 2>/dev/null || true)
        if [ -f "$fb_db" ] && [ "$fb_db_mode" != "1000:600" ]; then
            # filebrowser runs as non-root (UID 1000) and needs write access.
            # The DB holds File Browser users and its JWT signing key: owner-only.
            run_privileged chown 1000:1000 "$fb_db" 2>/dev/null || \
                print_warning "Could not chown filebrowser.db to 1000:1000"
            run_privileged chmod 600 "$fb_db" 2>/dev/null || \
                print_warning "Could not chmod 600 filebrowser.db"
        fi

        # Create File Browser config file with proxy auth. nginx only sets
        # X-Remote-User after auth_request has validated the management
        # console session, and File Browser is reachable only from nginx
        # (filebrowser_network), so the header cannot be spoofed.
        cat > "${SCRIPT_DIR}/.filebrowser.json" << 'FBEOF'
{
  "port": 80,
  "baseURL": "/files",
  "address": "0.0.0.0",
  "log": "stdout",
  "database": "/database/filebrowser.db",
  "root": "/srv",
  "auth": {
    "method": "proxy",
    "header": "X-Remote-User"
  }
}
FBEOF

        cat >> "$compose_tmp" << EOF
  # ===========================================================================
  # File Browser - Public Website Management
  # ===========================================================================
  filebrowser:
    image: filebrowser/filebrowser:v2.63.23
    container_name: n8n_filebrowser
    restart: unless-stopped
    # Set umask 022 so files are created with world-readable permissions (644)
    # This allows nginx_public to serve files uploaded via File Browser
    entrypoint: ["/bin/sh", "-c", "umask 022 && exec /bin/filebrowser -c /config/settings.json"]
    volumes:
      - public_web_root:/srv
      - ./filebrowser.db:/database/filebrowser.db
      - ./.filebrowser.json:/config/settings.json:ro
    networks:
      # Isolated: only nginx is attached to this network. Any other container
      # could otherwise send its own X-Remote-User header.
      - filebrowser_network

  # ===========================================================================
  # Public Website Nginx (separate from main nginx)
  # ===========================================================================
  # This container serves ONLY the public website. Traffic is routed here
  # via Cloudflare Tunnel based on hostname. No external ports exposed.
  nginx_public:
    # stock nginx + an fbuser (uid 1000) account, see nginx_public/Dockerfile
    image: n8n_nginx_public:local
    build: ./nginx_public
    pull_policy: build
    container_name: n8n_nginx_public
    restart: unless-stopped
    expose:
      - "80"
    volumes:
      - ./nginx-public.conf:/etc/nginx/nginx.conf:ro
      - public_web_root:/var/www/public:ro
    networks:
      - n8n_network
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://localhost/healthz || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

EOF
    fi

    # Add volumes section
    cat >> "$compose_tmp" << EOF
# ===========================================================================
# Volumes
# ===========================================================================
volumes:
  n8n_data:
    driver: local
  postgres_data:
    driver: local
  mgmt_backup_staging:
    driver: local
  mgmt_logs:
    driver: local
  mgmt_config:
    driver: local
  letsencrypt:
    external: true
  certbot_data:
    driver: local
  redis_data:
    driver: local
EOF

    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        cat >> "$compose_tmp" << EOF
  public_web_root:
    driver: local
EOF
    fi

    # NFS is now mounted at host level and bind-mounted into container
    # No Docker NFS volume needed - using ${NFS_LOCAL_MOUNT}:/mnt/backups bind mount

    # Add Tailscale volume if configured
    if [ "$INSTALL_TAILSCALE" = true ]; then
        cat >> "$compose_tmp" << EOF
  tailscale_data:
    driver: local
EOF
    fi

    # Add Portainer volume if full Portainer is configured
    if [ "$INSTALL_PORTAINER" = true ]; then
        cat >> "$compose_tmp" << EOF
  portainer_data:
    driver: local
EOF
    fi

    # Add NTFY volumes if configured
    if [ "$INSTALL_NTFY" = true ]; then
        cat >> "$compose_tmp" << EOF
  ntfy_cache:
    driver: local
  ntfy_data:
    driver: local
EOF
    fi

    # Portainer's initial admin password file
    if [ "$INSTALL_PORTAINER" = true ]; then
        cat >> "$compose_tmp" << 'EOF'

# ===========================================================================
# Secrets
# ===========================================================================
secrets:
  portainer_admin_password:
    file: ./portainer_password.txt
EOF
    fi

    # Add networks section
    cat >> "$compose_tmp" << EOF

# ===========================================================================
# Networks
# ===========================================================================
networks:
  n8n_network:
    driver: bridge
    # Pinned subnet: nginx treats this whole range as "external" (except the
    # Tailscale container) so traffic arriving through a Docker hop is never
    # trusted. Change it with N8N_NETWORK_SUBNET and re-run setup.sh.
    ipam:
      config:
        - subnet: ${N8N_NETWORK_SUBNET}
          ip_range: ${N8N_NETWORK_IP_RANGE}
          gateway: ${N8N_NETWORK_GATEWAY}
EOF

    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        cat >> "$compose_tmp" << EOF
  filebrowser_network:
    driver: bridge
    internal: true
EOF
    fi

    # Inject public_web_root volume into nginx service if configured
    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        if [ "$CHECK_PLATFORM" = "macos" ]; then
            sed -i '' '/letsencrypt:\/etc\/letsencrypt:ro/a\
      - public_web_root:/var/www/public:ro' "$compose_tmp"
        else
            sed -i '/letsencrypt:\/etc\/letsencrypt:ro/a\      - public_web_root:/var/www/public:ro' "$compose_tmp"
        fi
    fi

    # Hosts that cannot load AppArmor policy (e.g. Docker inside LXC) need
    # every service unconfined or container creation fails outright.
    if apparmor_unconfined_required; then
        awk '{print} /^    container_name: /{print "    security_opt:"; print "      - apparmor:unconfined"}' \
            "$compose_tmp" > "${SCRIPT_DIR}/docker-compose.yaml.apparmor.tmp"
        mv "${SCRIPT_DIR}/docker-compose.yaml.apparmor.tmp" "$compose_tmp"
        print_info "Added apparmor:unconfined to all generated services"
    fi

    mv -f "$compose_tmp" "${SCRIPT_DIR}/docker-compose.yaml"
    print_success "docker-compose.yaml generated for v3.0"
}

generate_nginx_conf_v3() {
    print_info "Generating nginx.conf for v3.0..."

    # Pinned Docker network addresses (same values as docker-compose.yaml)
    compute_docker_network_addrs

    # Extract root domain for public website config
    local root_domain=$(echo "$N8N_DOMAIN" | awk -F. '{if (NF>2) {print $(NF-1)"."$NF} else {print $0}}')

    # Start nginx.conf with events and http block
    cat > "${SCRIPT_DIR}/nginx.conf" << EOF
events {
    worker_connections 1024;
}

http {
    # Docker internal DNS resolver for dynamic upstream resolution
    resolver 127.0.0.11 valid=30s ipv6=off;
    resolver_timeout 5s;

    # Buffer sizes for large payloads
    client_max_body_size 50M;
    client_body_buffer_size 10M;

    # Timeouts for long-running operations
    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;
    send_timeout 600s;

    # Upstream to n8n
    upstream n8n {
        server ${N8N_CONTAINER:-n8n}:5678;
    }

    # Upstream to management console (connects to internal nginx on port 80)
    upstream management {
        server ${DEFAULT_MANAGEMENT_CONTAINER:-n8n_management}:80;
    }

    # ===========================================================================
    # IP-based Access Control
    # ===========================================================================
    # Classifies requests as "internal" (full access) or "external" (restricted)
    # Internal: localhost, your LAN/VPN ranges, the Tailscale container
    # External: everything arriving through a Docker hop (Cloudflare Tunnel,
    #           docker-proxy for IPv6/localhost, other containers), public internet
    # geo uses longest-prefix match, so the pinned Docker subnet below overrides
    # broader private ranges such as 172.16.0.0/12 or 10.0.0.0/8.
    # Entries tagged [managed] are maintained by setup.sh - do not remove them.
    geo \$access_level {
        default          "external";
        127.0.0.1/32     "internal";  # [managed] Localhost (healthchecks)
EOF

    # Add internal IP ranges to geo block (skipping the managed entries)
    for range in $INTERNAL_IP_RANGES $CUSTOM_INTERNAL_IPS; do
        case "$range" in
            ""|127.0.0.1/32|"$N8N_NETWORK_SUBNET"|"${TAILSCALE_IP}/32") continue ;;
        esac
        if range_inside_docker_subnet "$range"; then
            print_warning "Ignoring internal range ${range}: it lies inside the Docker network ${N8N_NETWORK_SUBNET}, which must stay external"
            continue
        fi
        cat >> "${SCRIPT_DIR}/nginx.conf" << EOF
        ${range}    "internal";
EOF
    done

    cat >> "${SCRIPT_DIR}/nginx.conf" << EOF
        ${N8N_NETWORK_SUBNET}    "external";  # [managed] Docker network n8n_network (proxied traffic)
EOF
    if [ "$INSTALL_TAILSCALE" = "true" ]; then
        cat >> "${SCRIPT_DIR}/nginx.conf" << EOF
        ${TAILSCALE_IP}/32    "internal";  # [managed] Tailscale container (tailnet users via Tailscale Serve)
EOF
    fi

    # Continue with ACCESS CONTROL SUMMARY and server block
    cat >> "${SCRIPT_DIR}/nginx.conf" << EOF
    }

    # ===========================================================================
    # ACCESS CONTROL SUMMARY:
    # ===========================================================================
    # EXTERNALLY ACCESSIBLE (public internet):
    #   - /webhook/     - n8n workflow webhooks
    #   - /ntfy/        - NTFY push notifications (if enabled; ntfy requires
    #                     a login or token, anonymous access is denied)
    #
    # CLOUDFLARE TUNNEL LISTENER (port 8080, not published on the host):
    #   - /webhook/, /webhook-test/, /webhook-waiting/, /form/, /form-test/,
    #     /form-waiting/, /ntfy/ (if enabled) - everything else is dropped
    #
    # INTERNAL ACCESS ONLY (Tailscale, VPN, whitelisted IPs):
    #   - /             - n8n editor
    #   - /management/  - Management console
    #   - /files/       - File Browser (also needs a management console session)
    #   - /portainer/   - Container management (if enabled)
    #   - /adminer/     - Database management (if enabled)
    #   - /dozzle/      - Log viewer (if enabled)
    # ===========================================================================
EOF

    # When public website is enabled, nginx_router handles SSL termination
    # and n8n_nginx listens on port 80. Otherwise, n8n_nginx handles SSL directly.
    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        cat >> "${SCRIPT_DIR}/nginx.conf" << EOF

    # ===========================================================================
    # Main n8n HTTP Server (Port 80) - SSL terminated by nginx_router
    # ===========================================================================
    server {
        listen 80;
        server_name ${N8N_DOMAIN};

        # Clients arrive via nginx_router: use the X-Real-IP it sets as the
        # client address, but only when the connection comes from the router's
        # static IP. Anything else keeps its real source address.
        set_real_ip_from ${NGINX_ROUTER_IP}/32;
        real_ip_header X-Real-IP;

        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
EOF
    else
        cat >> "${SCRIPT_DIR}/nginx.conf" << EOF

    # ===========================================================================
    # Main n8n HTTPS Server (Port 443)
    # ===========================================================================
    server {
        listen 443 ssl;
        http2 on;
        server_name ${N8N_DOMAIN};

        ssl_certificate /etc/letsencrypt/live/${SSL_CERT_DOMAIN:-$N8N_DOMAIN}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${SSL_CERT_DOMAIN:-$N8N_DOMAIN}/privkey.pem;

        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
EOF
    fi

    cat >> "${SCRIPT_DIR}/nginx.conf" << EOF

        # Webhook endpoint - PUBLICLY ACCESSIBLE
        location /webhook/ {
            # No CORS headers here: n8n answers webhook preflights itself and sets
            # Access-Control-Allow-Origin from each Webhook node's "Allowed Origins"
            # option. Adding them in nginx too duplicates the header (browsers then
            # reject the response) and overrides the per-workflow setting.
            add_header X-Frame-Options "SAMEORIGIN" always;

            proxy_pass http://n8n;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$remote_addr;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_buffering off;
        }

        # Default n8n proxy - INTERNAL ACCESS ONLY
        location / {
            # Block external access - only allow internal IPs
            if (\$access_level = "external") {
                return 403;
            }

            add_header X-Frame-Options "SAMEORIGIN" always;

            proxy_pass http://n8n;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$remote_addr;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_buffering off;
        }

        # n8n editor (v2.7+) polls /healthz and parses the body as JSON
        # ({status:"ok"}); plain-text responses make it think the backend is
        # offline. Keep this block returning valid JSON.
        location /healthz {
            access_log off;
            default_type application/json;
            return 200 '{"status":"ok"}';
        }
EOF

    # Add Portainer location if configured
    if [ "$INSTALL_PORTAINER" = true ]; then
        cat >> "${SCRIPT_DIR}/nginx.conf" << 'EOF'

        # Portainer Container Management - INTERNAL ACCESS ONLY
        # (configured with --base-url /portainer)
        location /portainer/ {
            # Block external access
            if ($access_level = "external") {
                return 403;
            }

            proxy_pass http://n8n_portainer:9000/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
        }

        location /portainer/api/websocket/ {
            # Block external access (container exec/attach websockets)
            if ($access_level = "external") {
                return 403;
            }

            proxy_pass http://n8n_portainer:9000/api/websocket/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
EOF
    fi

    # Add Adminer location if configured
    if [ "$INSTALL_ADMINER" = true ]; then
        cat >> "${SCRIPT_DIR}/nginx.conf" << 'EOF'

        # Adminer Database Management - INTERNAL ACCESS ONLY
        location /adminer/ {
            # Block external access
            if ($access_level = "external") {
                return 403;
            }

            proxy_pass http://n8n_adminer:8080/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
        }
EOF
    fi

    # Add Dozzle location if configured
    if [ "$INSTALL_DOZZLE" = true ]; then
        cat >> "${SCRIPT_DIR}/nginx.conf" << 'EOF'

        # Dozzle Log Viewer - INTERNAL ACCESS ONLY
        # (configured with DOZZLE_BASE=/dozzle)
        location /dozzle/ {
            # Block external access
            if ($access_level = "external") {
                return 403;
            }

            proxy_pass http://n8n_dozzle:8080;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
EOF
    fi

    # Add NTFY location if configured
    if [ "$INSTALL_NTFY" = true ]; then
        cat >> "${SCRIPT_DIR}/nginx.conf" << 'EOF'

        # NTFY Push Notification Server - EXTERNALLY ACCESSIBLE
        # Required for mobile apps and external services to receive notifications.
        # ntfy itself enforces authentication (auth-default-access deny-all):
        # every read and publish needs the admin login or an access token.
        # ntfy answers CORS preflights itself, so no extra headers here.
        location /ntfy/ {
            # Use variable to enable runtime DNS resolution (prevents startup failure)
            set $ntfy_upstream http://n8n_ntfy:80;

            # Strip the /ntfy prefix. (proxy_pass with a variable plus a URI part
            # would replace the whole request URI with "/".)
            rewrite ^/ntfy/(.*)$ /$1 break;
            proxy_pass $ntfy_upstream;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_buffering off;
            proxy_request_buffering off;
            proxy_redirect off;
            chunked_transfer_encoding on;
            # Long timeout for SSE/WebSocket notification streams
            proxy_read_timeout 86400s;
            proxy_send_timeout 86400s;
        }
EOF
    fi

    # Add File Browser location if configured
    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        cat >> "${SCRIPT_DIR}/nginx.conf" << 'EOF'

        # File Browser - Public Website Management - INTERNAL ACCESS ONLY
        # Also requires a valid management console session.
        location /files/ {
            # Block external access
            if ($access_level = "external") {
                return 403;
            }

            # Authenticate against the management console session (HttpOnly
            # "session" cookie set at login). 401 if missing/expired.
            auth_request /_auth/management-session;
            auth_request_set $files_auth_user $upstream_http_x_auth_user;

            # Proxy to filebrowser (uses --baseurl=/files via config)
            proxy_pass http://n8n_filebrowser:80;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";

            # File Browser proxy auth: always overwrite any client-supplied
            # X-Remote-User with the user validated by auth_request
            proxy_set_header X-Remote-User $files_auth_user;
        }

        # Internal-only session check used by auth_request above
        location = /_auth/management-session {
            internal;
            proxy_pass http://management/api/auth/verify;
            proxy_pass_request_body off;
            proxy_set_header Content-Length "";
            proxy_set_header Host $host;
            proxy_set_header X-Original-URI $request_uri;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
EOF
    fi

    # Add Management Console location blocks
    cat >> "${SCRIPT_DIR}/nginx.conf" << 'EOF'

        # Management Console - INTERNAL ACCESS ONLY
        location /management/ {
            # Block external access
            if ($access_level = "external") {
                return 403;
            }

            proxy_pass http://management/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_buffering off;
        }

        # WebSocket terminal endpoint (long-lived connections)
        location /management/api/ws/ {
            # Block external access
            if ($access_level = "external") {
                return 403;
            }

            proxy_pass http://management/api/ws/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;

            # WebSocket required headers
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";

            # Long timeouts for terminal sessions (24 hours)
            proxy_connect_timeout 86400s;
            proxy_send_timeout 86400s;
            proxy_read_timeout 86400s;

            proxy_buffering off;
        }

        location /management/api/ {
            # Block external access
            if ($access_level = "external") {
                return 403;
            }

            proxy_pass http://management/api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_buffering off;
        }
    }
EOF

    # Cloudflare Tunnel listener: plain HTTP on 8080 inside the Docker network
    # only (never published on the host). It serves just the public n8n
    # endpoints, so a tunnel pointed here cannot reach any admin path even if
    # the geo rules were misconfigured.
    cat >> "${SCRIPT_DIR}/nginx.conf" << 'EOF'

    # ===========================================================================
    # Cloudflare Tunnel listener (port 8080 - NOT published on the host)
    # ===========================================================================
    # Cloudflare Tunnel public hostname -> Service: HTTP -> n8n_nginx:8080
    # Only public n8n endpoints are served; everything else is dropped (444).
    server {
        listen 8080 default_server;
        server_name _;
EOF
    # cloudflared passes the visitor address (set by the Cloudflare edge) in
    # CF-Connecting-IP. Trust it only from the cloudflared container's static
    # IP so n8n sees the real client (e.g. for webhook IP whitelists) in
    # X-Real-IP / X-Forwarded-For, which clients cannot spoof.
    cat >> "${SCRIPT_DIR}/nginx.conf" << EOF

        set_real_ip_from ${CLOUDFLARED_IP}/32;
        real_ip_header CF-Connecting-IP;
EOF
    cat >> "${SCRIPT_DIR}/nginx.conf" << 'EOF'

        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;

        # n8n webhooks and forms - PUBLICLY ACCESSIBLE
        location ~ ^/(webhook|webhook-test|webhook-waiting|form|form-test|form-waiting)/ {
            # No CORS headers here: n8n answers webhook preflights itself and sets
            # Access-Control-Allow-Origin from each Webhook node's "Allowed Origins"
            # option. Adding them in nginx too duplicates the header (browsers then
            # reject the response) and overrides the per-workflow setting.
            add_header X-Frame-Options "SAMEORIGIN" always;

            proxy_pass http://n8n;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            # TLS is terminated by Cloudflare
            proxy_set_header X-Forwarded-Proto https;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_buffering off;
        }
EOF

    if [ "$INSTALL_NTFY" = true ]; then
        cat >> "${SCRIPT_DIR}/nginx.conf" << 'EOF'

        # NTFY Push Notification Server - PUBLICLY ACCESSIBLE
        # (ntfy denies anonymous access; clients need a login or token)
        location /ntfy/ {
            set $ntfy_upstream http://n8n_ntfy:80;
            # Strip the /ntfy prefix. (proxy_pass with a variable plus a URI part
            # would replace the whole request URI with "/".)
            rewrite ^/ntfy/(.*)$ /$1 break;
            proxy_pass $ntfy_upstream;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto https;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_buffering off;
            proxy_request_buffering off;
            proxy_redirect off;
            proxy_read_timeout 86400s;
            proxy_send_timeout 86400s;
        }
EOF
    fi

    cat >> "${SCRIPT_DIR}/nginx.conf" << 'EOF'

        location = /healthz {
            access_log off;
            default_type application/json;
            return 200 '{"status":"ok"}';
        }

        # Everything else (editor, /rest/, /management/, /files/, tools): drop
        location / {
            return 444;
        }
    }
EOF

    # NOTE: Public Website server block has been moved to nginx-public.conf
    # which is served by the separate n8n_nginx_public container.
    # This ensures proper ECH handling (no multiple server blocks on same nginx).

    # Close the http block
    cat >> "${SCRIPT_DIR}/nginx.conf" << 'EOF'
}
EOF

    print_success "nginx.conf generated for v3.0"
}

# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC WEBSITE NGINX CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
# Generates nginx-public.conf for the separate public website nginx container.
# This container serves ONLY the public website, with no access to internal
# services. It's accessed exclusively via Cloudflare Tunnel.
# ═══════════════════════════════════════════════════════════════════════════════

generate_public_nginx_conf() {
    if [ "$INSTALL_PUBLIC_WEBSITE" != "true" ]; then
        return 0
    fi

    print_info "Generating nginx-public.conf for public website container..."

    # Extract root domain for public website config
    local root_domain=$(echo "$N8N_DOMAIN" | awk -F. '{if (NF>2) {print $(NF-1)"."$NF} else {print $0}}')
    local public_domain="${PUBLIC_WEBSITE_DOMAIN:-www.${root_domain}}"

    cat > "${SCRIPT_DIR}/nginx-public.conf" << EOF
# ═══════════════════════════════════════════════════════════════════════════════
# Public Website Nginx Configuration
# ═══════════════════════════════════════════════════════════════════════════════
# This nginx instance serves ONLY the public website.
# It has no access to n8n, management console, or other internal services.
#
# Traffic routing:
#   - Internal: nginx_router proxies www.* requests here
#   - External: Cloudflare Tunnel routes www.* requests here
#
# This container listens on port 80 (HTTP) internally.
# SSL termination is handled by nginx_router or Cloudflare Tunnel.
# ═══════════════════════════════════════════════════════════════════════════════

# Run workers as fbuser (uid 1000, same as filebrowser) to read uploaded files
# nginx master starts as root to bind port 80, workers run as fbuser
# The fbuser account is created by nginx_public/Dockerfile
user fbuser;

events {
    worker_connections 256;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Performance optimizations
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # Logging
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    server {
        listen 80;
        server_name ${public_domain};

        # Serve static files from public website root
        root /var/www/public;
        index index.html index.htm;

        # Security headers
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # Main location - serve static files
        location / {
            try_files \$uri \$uri/ =404;
        }

        # Health check endpoint
        location /healthz {
            access_log off;
            return 200 "healthy\\n";
            add_header Content-Type text/plain;
        }

        # Block access to hidden files (except .well-known)
        location ~ /\\.(?!well-known) {
            deny all;
            access_log off;
            log_not_found off;
        }

        # Custom error pages
        error_page 404 /404.html;
        error_page 500 502 503 504 /50x.html;
        location = /50x.html {
            root /usr/share/nginx/html;
        }
    }
}
EOF

    print_success "nginx-public.conf generated for public website"
}

# ═══════════════════════════════════════════════════════════════════════════════
# NGINX ROUTER CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
# Generates nginx-router.conf for hostname-based routing.
# This container ONLY routes traffic - it has no access to internal services.
#
# Architecture:
#   External traffic → Cloudflare Tunnel → n8n_nginx:8080 (webhooks only) / nginx_public
#   Internal traffic → nginx_router:443 → n8n_nginx / nginx_public
#
# This container is ONLY added when public website is enabled.
# ═══════════════════════════════════════════════════════════════════════════════

generate_nginx_router_conf() {
    if [ "$INSTALL_PUBLIC_WEBSITE" != "true" ]; then
        return 0
    fi

    print_info "Generating nginx-router.conf for hostname-based routing..."

    # Extract root domain
    local root_domain=$(echo "$N8N_DOMAIN" | awk -F. '{if (NF>2) {print $(NF-1)"."$NF} else {print $0}}')
    local public_domain="${PUBLIC_WEBSITE_DOMAIN:-www.${root_domain}}"

    cat > "${SCRIPT_DIR}/nginx-router.conf" << EOF
# ═══════════════════════════════════════════════════════════════════════════════
# Nginx Router Configuration
# ═══════════════════════════════════════════════════════════════════════════════
# This nginx instance ONLY routes traffic based on hostname.
# It has NO access to internal services, databases, or sensitive data.
#
# Purpose: Allows internal network access to both n8n services and public
# website without hairpinning through Cloudflare Tunnel.
#
# Architecture:
#   External traffic → Cloudflare Tunnel → n8n_nginx:8080 (webhooks only) / nginx_public
#   Internal traffic → nginx_router:443 → n8n_nginx / nginx_public
#
# This container is ONLY added when public website is enabled.
# ═══════════════════════════════════════════════════════════════════════════════

events {
    worker_connections 1024;
}

http {
    # Docker internal DNS resolver
    resolver 127.0.0.11 valid=30s ipv6=off;
    resolver_timeout 5s;

    # Logging
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # Buffer sizes
    client_max_body_size 50M;
    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;

    # ===========================================================================
    # Internal Services (n8n, management, adminer, dozzle, portainer, ntfy, files)
    # Routes to n8n_nginx which handles access control and proxying.
    # n8n_nginx trusts the X-Real-IP set below only from this container's
    # static IP (NGINX_ROUTER_IP), so it must always overwrite, never pass on.
    # ===========================================================================
    server {
        listen 443 ssl;
        http2 on;
        server_name ${N8N_DOMAIN} ~^(management|adminer|dozzle|portainer|ntfy|files)\\.${root_domain//./\\.}\$;

        # SSL Certificate (wildcard)
        ssl_certificate /etc/letsencrypt/live/${SSL_CERT_DOMAIN:-$root_domain}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${SSL_CERT_DOMAIN:-$root_domain}/privkey.pem;

        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        location / {
            proxy_pass http://n8n_nginx:80;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$remote_addr;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_buffering off;
        }
    }

    # ===========================================================================
    # Public Website (www.*)
    # Routes to nginx_public which serves static files
    # ===========================================================================
    server {
        listen 443 ssl;
        http2 on;
        server_name ${public_domain};

        # SSL Certificate (wildcard)
        ssl_certificate /etc/letsencrypt/live/${SSL_CERT_DOMAIN:-$root_domain}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${SSL_CERT_DOMAIN:-$root_domain}/privkey.pem;

        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        location / {
            proxy_pass http://nginx_public:80;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$remote_addr;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_http_version 1.1;
            proxy_buffering off;
        }
    }

    # ===========================================================================
    # Default - Health check endpoint and 444 for unrecognized hostnames
    # ===========================================================================
    server {
        listen 443 ssl default_server;
        server_name _;

        ssl_certificate /etc/letsencrypt/live/${SSL_CERT_DOMAIN:-$root_domain}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${SSL_CERT_DOMAIN:-$root_domain}/privkey.pem;

        # Health check endpoint for Docker
        location /healthz {
            access_log off;
            return 200 "healthy\\n";
            add_header Content-Type text/plain;
        }

        # Reject all other requests to unrecognized hostnames
        location / {
            return 444;
        }
    }
}
EOF

    print_success "nginx-router.conf generated for hostname-based routing"
}

# ═══════════════════════════════════════════════════════════════════════════════
# DNS PROVIDER CONFIGURATION (from v2)
# ═══════════════════════════════════════════════════════════════════════════════

configure_dns_provider() {
    print_section "DNS Provider Configuration"

    # In preconfig mode, DNS provider is already configured by load_preconfig
    if [ "$PRECONFIG_MODE" = "true" ]; then
        print_info "Using pre-configured DNS provider: $DNS_PROVIDER_NAME"
        return
    fi

    echo -e "  ${GRAY}Let's Encrypt uses DNS validation to issue SSL certificates.${NC}"
    echo -e "  ${GRAY}This requires API access to your DNS provider.${NC}"
    echo ""

    echo -e "  ${WHITE}Select your DNS provider:${NC}"
    echo -e "    ${CYAN}1)${NC} Cloudflare"
    echo -e "    ${CYAN}2)${NC} AWS Route 53"
    echo -e "    ${CYAN}3)${NC} Google Cloud DNS"
    echo -e "    ${CYAN}4)${NC} DigitalOcean"
    echo -e "    ${CYAN}5)${NC} Other (manual configuration)"
    echo ""

    local dns_choice=""
    while [[ ! "$dns_choice" =~ ^[1-5]$ ]]; do
        echo -ne "${WHITE}  Enter your choice [1-5]${NC}: "
        read dns_choice
    done

    case $dns_choice in
        1) configure_cloudflare ;;
        2) configure_route53 ;;
        3) configure_google_dns ;;
        4) configure_digitalocean ;;
        5) configure_other_dns ;;
    esac
}

configure_cloudflare() {
    DNS_PROVIDER_NAME="cloudflare"
    DNS_CERTBOT_IMAGE="certbot/dns-cloudflare:${CERTBOT_VERSION}"
    DNS_CREDENTIALS_FILE="cloudflare.ini"

    print_subsection
    echo -e "${WHITE}  Cloudflare API Configuration${NC}"
    echo ""
    echo -e "  ${GRAY}You need a Cloudflare API token with Zone:DNS:Edit permission.${NC}"
    echo -e "  ${GRAY}Create one at: https://dash.cloudflare.com/profile/api-tokens${NC}"
    echo ""

    echo -ne "${WHITE}  Enter your Cloudflare API token${NC}: "
    read_masked_token
    CF_API_TOKEN="$MASKED_INPUT"

    if [ -z "$CF_API_TOKEN" ]; then
        print_error "API token is required for Cloudflare"
        exit 1
    fi

    print_success "Cloudflare credentials saved"

    cat > "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}" << EOF
dns_cloudflare_api_token = ${CF_API_TOKEN}
EOF

    chmod 600 "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}"

    DNS_CERTBOT_FLAGS="--dns-cloudflare --dns-cloudflare-credentials /credentials.ini --dns-cloudflare-propagation-seconds 60"
}

configure_route53() {
    DNS_PROVIDER_NAME="route53"
    DNS_CERTBOT_IMAGE="certbot/dns-route53:${CERTBOT_VERSION}"
    DNS_CREDENTIALS_FILE="route53.ini"

    print_subsection
    echo -e "${WHITE}  AWS Route 53 Configuration${NC}"
    echo ""

    echo -ne "${WHITE}  Enter your AWS Access Key ID${NC}: "
    read_masked_token
    AWS_ACCESS_KEY_ID="$MASKED_INPUT"

    echo -ne "${WHITE}  Enter your AWS Secret Access Key${NC}: "
    read_masked_token
    AWS_SECRET_ACCESS_KEY="$MASKED_INPUT"

    if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
        print_error "Both AWS credentials are required"
        exit 1
    fi

    print_success "AWS credentials saved"

    cat > "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}" << EOF
[default]
aws_access_key_id = ${AWS_ACCESS_KEY_ID}
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}
EOF

    chmod 600 "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}"

    DNS_CERTBOT_FLAGS="--dns-route53"
}

configure_google_dns() {
    DNS_PROVIDER_NAME="google"
    DNS_CERTBOT_IMAGE="certbot/dns-google:${CERTBOT_VERSION}"
    DNS_CREDENTIALS_FILE="google.json"

    print_subsection
    echo -e "${WHITE}  Google Cloud DNS Configuration${NC}"
    echo ""

    echo -ne "${WHITE}  Enter the path to your service account JSON file${NC}: "
    read GOOGLE_JSON_PATH

    if [ ! -f "$GOOGLE_JSON_PATH" ]; then
        print_error "File not found: $GOOGLE_JSON_PATH"
        exit 1
    fi

    cp "$GOOGLE_JSON_PATH" "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}"
    chmod 600 "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}"
    print_success "Google credentials saved"

    DNS_CERTBOT_FLAGS="--dns-google --dns-google-credentials /credentials.json --dns-google-propagation-seconds 120"
}

configure_digitalocean() {
    DNS_PROVIDER_NAME="digitalocean"
    DNS_CERTBOT_IMAGE="certbot/dns-digitalocean:${CERTBOT_VERSION}"
    DNS_CREDENTIALS_FILE="digitalocean.ini"

    print_subsection
    echo -e "${WHITE}  DigitalOcean DNS Configuration${NC}"
    echo ""

    echo -ne "${WHITE}  Enter your DigitalOcean API token${NC}: "
    read_masked_token
    DO_API_TOKEN="$MASKED_INPUT"

    if [ -z "$DO_API_TOKEN" ]; then
        print_error "API token is required"
        exit 1
    fi

    print_success "DigitalOcean credentials saved"

    cat > "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}" << EOF
dns_digitalocean_token = ${DO_API_TOKEN}
EOF

    chmod 600 "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}"

    DNS_CERTBOT_FLAGS="--dns-digitalocean --dns-digitalocean-credentials /credentials.ini --dns-digitalocean-propagation-seconds 60"
}

configure_other_dns() {
    DNS_PROVIDER_NAME="manual"
    DNS_CERTBOT_IMAGE="certbot/certbot:${CERTBOT_VERSION}"
    DNS_CREDENTIALS_FILE="credentials.ini"
    DNS_CERTBOT_FLAGS="--manual --preferred-challenges dns"

    print_warning "Manual DNS configuration selected"
    echo -e "  ${GRAY}During deployment certbot will show a TXT record (_acme-challenge.<domain>)${NC}"
    echo -e "  ${GRAY}that you must create at your DNS provider, then press Enter to continue.${NC}"
    echo -e "  ${YELLOW}${BOLD}Automatic renewal is NOT possible with manual DNS validation.${NC}"
    echo -e "  ${YELLOW}The certificate expires after 90 days; you must re-run ./setup.sh (option 1)${NC}"
    echo -e "  ${YELLOW}and add a new TXT record before then. The certbot container will log an${NC}"
    echo -e "  ${YELLOW}error once the certificate is due for renewal.${NC}"
    ensure_dns_credentials_file
}

# ═══════════════════════════════════════════════════════════════════════════════
# URL AND DATABASE CONFIGURATION (from v2)
# ═══════════════════════════════════════════════════════════════════════════════

configure_url() {
    print_section "Domain Configuration"

    # In preconfig mode, domain is already set by load_preconfig
    if [ "$PRECONFIG_MODE" = "true" ] && [ -n "$N8N_DOMAIN" ]; then
        print_info "Using pre-configured domain: $N8N_DOMAIN"
        # Set derived URL values
        N8N_URL="https://${N8N_DOMAIN}"
        WEBHOOK_URL="https://${N8N_DOMAIN}"
        EDITOR_BASE_URL="https://${N8N_DOMAIN}"
        return
    fi

    echo -e "  ${GRAY}Enter the domain name where n8n will be accessible.${NC}"
    echo -e "  ${GRAY}Example: n8n.yourdomain.com${NC}"
    echo ""

    prompt_with_default "Enter your n8n domain" "n8n.example.com" "N8N_DOMAIN"

    # Validate domain format
    if [[ ! "$N8N_DOMAIN" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$ ]]; then
        print_warning "Domain format may be invalid: $N8N_DOMAIN"
        if ! confirm_prompt "Continue anyway?"; then
            configure_url
            return
        fi
    fi

    validate_domain
}

validate_domain() {
    print_subsection
    echo -e "${WHITE}  Validating domain configuration...${NC}"
    echo ""

    # Get local IP addresses
    local local_ips=$(get_local_ips)
    local domain_ip=""
    local validation_passed=true

    # Show local IPs
    echo -e "  ${WHITE}This server's IP addresses:${NC}"
    for local_ip in $local_ips; do
        echo -e "    ${CYAN}${local_ip}${NC}"
    done
    echo ""

    # Try to resolve the domain
    print_info "Resolving $N8N_DOMAIN..."

    if command_exists dig; then
        domain_ip=$(dig +short "$N8N_DOMAIN" 2>/dev/null | head -1)
    elif command_exists nslookup; then
        domain_ip=$(nslookup "$N8N_DOMAIN" 2>/dev/null | grep -A1 "Name:" | grep "Address:" | awk '{print $2}' | head -1)
    elif command_exists host; then
        domain_ip=$(host "$N8N_DOMAIN" 2>/dev/null | grep "has address" | awk '{print $4}' | head -1)
    elif command_exists getent; then
        domain_ip=$(getent hosts "$N8N_DOMAIN" 2>/dev/null | awk '{print $1}' | head -1)
    fi

    if [ -z "$domain_ip" ]; then
        print_warning "Could not resolve $N8N_DOMAIN to an IP address"
        echo ""
        echo -e "  ${YELLOW}This could mean:${NC}"
        echo -e "    - The DNS record hasn't been created yet"
        echo -e "    - The DNS hasn't propagated yet"
        echo -e "    - The domain name is incorrect"
        echo ""
        validation_passed=false
    else
        print_success "Domain resolves to: $domain_ip"

        # Check if the resolved IP matches any local IP
        local ip_matches=false
        local matched_local_ip=""
        for local_ip in $local_ips; do
            if [ "$local_ip" = "$domain_ip" ]; then
                ip_matches=true
                matched_local_ip="$local_ip"
                break
            fi
        done

        if [ "$ip_matches" = true ]; then
            print_success "Domain IP matches this server"
            # Capture the matched IP for N8N_MANAGEMENT_HOST_IP
            N8N_MANAGEMENT_HOST_IP="$matched_local_ip"
        else
            print_warning "Domain IP ($domain_ip) does not match any local IP"
            echo ""
            echo -e "  ${YELLOW}IMPORTANT:${NC}"
            echo -e "  ${YELLOW}The domain $N8N_DOMAIN points to $domain_ip${NC}"
            echo -e "  ${YELLOW}but this server's IPs are different.${NC}"
            echo ""
            echo -e "  ${YELLOW}This will cause the n8n stack to fail because:${NC}"
            echo -e "    - SSL certificate validation will fail"
            echo -e "    - Webhooks won't reach this server"
            echo -e "    - The n8n UI won't be accessible"
            echo ""
            validation_passed=false
        fi
    fi

    # Ping test (if we got an IP)
    if [ -n "$domain_ip" ]; then
        print_info "Testing connectivity to $domain_ip..."
        if ping -c 1 -W 5 "$domain_ip" >/dev/null 2>&1; then
            print_success "Host $domain_ip is reachable"
        else
            print_warning "Cannot ping $domain_ip (may be blocked by firewall)"
        fi
    fi

    if [ "$validation_passed" = false ]; then
        echo ""
        echo -e "  ${RED}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "  ${RED}║                              WARNING                                      ║${NC}"
        echo -e "  ${RED}║  The domain validation found issues that may prevent n8n from working.    ║${NC}"
        echo -e "  ${RED}║  Please ensure your DNS is properly configured before continuing.         ║${NC}"
        echo -e "  ${RED}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
        echo ""

        echo -e "  ${WHITE}Options:${NC}"
        echo -e "    ${CYAN}1)${NC} Re-enter domain name (if misspelled)"
        echo -e "    ${CYAN}2)${NC} Continue anyway (I understand the risks)"
        echo -e "    ${CYAN}3)${NC} Exit setup"
        echo ""

        local domain_choice=""
        while [[ ! "$domain_choice" =~ ^[1-3]$ ]]; do
            echo -ne "${WHITE}  Enter your choice [1-3]${NC}: "
            read domain_choice
        done

        case $domain_choice in
            1)
                # Re-enter domain
                configure_url
                return
                ;;
            2)
                # Continue with risks
                print_warning "Continuing with unvalidated domain configuration..."
                # Try to set N8N_MANAGEMENT_HOST_IP to the first local IP as fallback
                if [ -z "$N8N_MANAGEMENT_HOST_IP" ]; then
                    local first_local_ip=$(echo "$local_ips" | head -1)
                    if [ -n "$first_local_ip" ]; then
                        N8N_MANAGEMENT_HOST_IP="$first_local_ip"
                        print_info "Using $first_local_ip as management host IP"
                    fi
                fi
                ;;
            3)
                echo ""
                print_info "Please configure your DNS correctly and run this script again."
                exit 1
                ;;
        esac
    fi

    # Ensure N8N_MANAGEMENT_HOST_IP is set (use first local IP as final fallback)
    if [ -z "$N8N_MANAGEMENT_HOST_IP" ]; then
        local first_local_ip=$(echo "$local_ips" | head -1)
        if [ -n "$first_local_ip" ]; then
            N8N_MANAGEMENT_HOST_IP="$first_local_ip"
        fi
    fi

    # Set derived URL values
    N8N_URL="https://${N8N_DOMAIN}"
    WEBHOOK_URL="https://${N8N_DOMAIN}"
    EDITOR_BASE_URL="https://${N8N_DOMAIN}"
}

configure_database() {
    print_section "PostgreSQL Database Configuration"

    local env_file="${SCRIPT_DIR}/.env" pg_volume="" existing_pw="" existing_user="" existing_db=""
    local new_pw="" new_pw_confirm=""
    if [ -f "$env_file" ]; then
        existing_user=$(env_get_key "$env_file" POSTGRES_USER) || existing_user=""
        existing_db=$(env_get_key "$env_file" POSTGRES_DB) || existing_db=""
        existing_pw=$(env_get_key "$env_file" POSTGRES_PASSWORD) || existing_pw=""
    fi
    pg_volume=$(find_compose_volume postgres_data 2>/dev/null) || pg_volume=""
    if [ -n "$pg_volume" ] && [ -z "$existing_pw" ]; then
        existing_pw=$(detect_running_postgres_password 2>/dev/null) || existing_pw=""
    fi

    # ── Existing PostgreSQL data: the role/password are fixed by the volume ──
    if [ -n "$pg_volume" ]; then
        print_warning "Existing PostgreSQL data volume detected: ${pg_volume}"
        echo -e "  ${GRAY}PostgreSQL ignores POSTGRES_PASSWORD once initialised - the existing${NC}"
        echo -e "  ${GRAY}password is kept unless you change it here (applied with ALTER ROLE).${NC}"
        echo ""
        if [ -n "$existing_user" ] && [ -n "${DB_USER:-}" ] && [ "$DB_USER" != "$existing_user" ]; then
            print_warning "Database user '${DB_USER}' ignored - existing data uses '${existing_user}'"
        fi
        if [ -n "$existing_db" ] && [ -n "${DB_NAME:-}" ] && [ "$DB_NAME" != "$existing_db" ]; then
            print_warning "Database name '${DB_NAME}' ignored - existing data uses '${existing_db}'"
        fi
        DB_USER="${existing_user:-${DB_USER:-$DEFAULT_DB_USER}}"
        DB_NAME="${existing_db:-${DB_NAME:-$DEFAULT_DB_NAME}}"
        print_info "Database: ${DB_NAME} (user: ${DB_USER})"

        if [ "$PRECONFIG_MODE" = "true" ]; then
            if [ -z "${DB_PASSWORD:-}" ]; then
                if [ -z "$existing_pw" ]; then
                    print_error "Cannot determine the password of the existing database."
                    print_info "Set POSTGRES_PASSWORD in your config file to the CURRENT database password."
                    exit 1
                fi
                DB_PASSWORD="$existing_pw"
                print_success "Reusing the existing PostgreSQL password"
            elif [ -n "$existing_pw" ] && [ "$DB_PASSWORD" != "$existing_pw" ]; then
                print_warning "POSTGRES_PASSWORD in the config differs from the existing database password"
                if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ] && [ "${FORCE_REGENERATE_SECRETS:-false}" != "true" ]; then
                    print_error "Refusing to change the password of an existing database in AUTO_CONFIRM mode."
                    print_info "Remove POSTGRES_PASSWORD from the config to keep the existing password, or"
                    print_info "set FORCE_REGENERATE_SECRETS=true to apply the new one with ALTER ROLE."
                    exit 1
                fi
                if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ] || confirm_prompt "Change the existing database password now (ALTER ROLE)?" "n"; then
                    if ! apply_db_password_change "$DB_PASSWORD" "$DB_USER" "$DB_NAME"; then
                        print_error "Aborting - .env was not modified"
                        exit 1
                    fi
                    DB_PASSWORD_PREVIOUS="$existing_pw"
                else
                    DB_PASSWORD="$existing_pw"
                    print_success "Keeping the existing PostgreSQL password"
                fi
            fi
            return
        fi

        if [ -n "$existing_pw" ]; then
            if confirm_prompt "Keep the existing database password?" "y"; then
                DB_PASSWORD="$existing_pw"
                print_success "Keeping the existing PostgreSQL password"
                return
            fi
            while true; do
                echo -ne "${WHITE}  New database password${NC}: "
                read -rs new_pw
                echo ""
                echo -ne "${WHITE}  Confirm new password${NC}: "
                read -rs new_pw_confirm
                echo ""
                if [ -z "$new_pw" ]; then
                    print_error "Password cannot be empty"
                elif [ "$new_pw" != "$new_pw_confirm" ]; then
                    print_error "Passwords do not match"
                elif ! env_quote_value "$new_pw" >/dev/null; then
                    print_error "Password cannot contain newlines, or both ' and \`"
                else
                    break
                fi
            done
            if [ "$new_pw" != "$existing_pw" ]; then
                if ! apply_db_password_change "$new_pw" "$DB_USER" "$DB_NAME"; then
                    print_error "Aborting - .env was not modified"
                    exit 1
                fi
                DB_PASSWORD_PREVIOUS="$existing_pw"
            fi
            DB_PASSWORD="$new_pw"
        else
            print_warning "Could not determine the current database password (no .env, container not found)."
            while [ -z "${DB_PASSWORD:-}" ]; do
                echo -ne "${WHITE}  Enter the CURRENT database password${NC}: "
                read -rs DB_PASSWORD
                echo ""
            done
        fi
        return
    fi

    # ── New database ──
    # In preconfig mode, database is already configured by load_preconfig
    if [ "$PRECONFIG_MODE" = "true" ]; then
        if [ -z "${DB_PASSWORD:-}" ]; then
            DB_PASSWORD=$(random_secret 32)
            AUTOGEN_DB_PASSWORD=true
            print_info "Auto-generated PostgreSQL password"
        fi
        print_info "Using pre-configured database: $DB_NAME (user: $DB_USER)"
        return
    fi

    prompt_with_default "Database name" "$DEFAULT_DB_NAME" "DB_NAME"
    prompt_with_default "Database username" "$DEFAULT_DB_USER" "DB_USER"

    echo ""
    echo -e "  ${GRAY}Enter a password or leave blank to auto-generate.${NC}"
    prompt_with_default "Database password" "" "DB_PASSWORD"

    if [ -z "$DB_PASSWORD" ]; then
        if command_exists openssl; then
            DB_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
            print_success "Generated secure database password"
        else
            print_error "OpenSSL not found. Please enter a password."
            prompt_with_default "Database password" "" "DB_PASSWORD"
        fi
    fi
}

configure_containers() {
    print_section "Container Names Configuration"

    POSTGRES_CONTAINER="$DEFAULT_POSTGRES_CONTAINER"
    N8N_CONTAINER="$DEFAULT_N8N_CONTAINER"
    NGINX_CONTAINER="$DEFAULT_NGINX_CONTAINER"
    CERTBOT_CONTAINER="$DEFAULT_CERTBOT_CONTAINER"

    print_success "Using default container names"
}

configure_email() {
    print_section "Let's Encrypt Email Configuration"

    # In preconfig mode, email is already set by load_preconfig
    if [ "$PRECONFIG_MODE" = "true" ] && [ -n "$LETSENCRYPT_EMAIL" ]; then
        print_info "Using pre-configured email: $LETSENCRYPT_EMAIL"
        return
    fi

    echo ""
    echo -e "  ${GRAY}Let's Encrypt requires a valid email for certificate expiration notices.${NC}"
    echo ""

    while true; do
        echo -ne "${WHITE}  Email address for Let's Encrypt${NC}: "
        read email_input

        if [ -z "$email_input" ]; then
            print_error "Email address is required"
            continue
        fi

        # Basic email format validation
        if [[ ! "$email_input" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
            print_error "Invalid email format. Please enter a valid email address."
            continue
        fi

        # Check for placeholder emails
        if [[ "$email_input" =~ (example\.com|yourdomain\.com|test\.com|domain\.com)$ ]]; then
            print_warning "This looks like a placeholder email address."
            if ! confirm_prompt "Are you sure you want to use '$email_input'?" "n"; then
                continue
            fi
        fi

        # Confirm email address
        echo -ne "${WHITE}  Confirm email address${NC}: "
        read email_confirm

        if [ "$email_input" != "$email_confirm" ]; then
            print_error "Email addresses do not match. Please try again."
            continue
        fi

        LETSENCRYPT_EMAIL="$email_input"
        print_success "Email set to: $LETSENCRYPT_EMAIL"
        break
    done
}

configure_timezone() {
    print_section "Timezone Configuration"

    # In preconfig mode, timezone is already set by load_preconfig
    if [ "$PRECONFIG_MODE" = "true" ] && [ -n "$N8N_TIMEZONE" ]; then
        print_info "Using pre-configured timezone: $N8N_TIMEZONE"
        return
    fi

    local default_tz="America/Los_Angeles"
    local system_tz=""

    # Detect system timezone for reference
    if [ -f /etc/timezone ]; then
        system_tz=$(cat /etc/timezone)
    elif command_exists timedatectl; then
        system_tz=$(timedatectl show -p Timezone --value 2>/dev/null)
    fi

    if [ -n "$system_tz" ] && [ "$system_tz" != "$default_tz" ]; then
        echo -e "  ${WHITE}System timezone detected: ${CYAN}$system_tz${NC}"
        echo ""
    fi

    if confirm_prompt "Use $default_tz as the timezone?" "y"; then
        N8N_TIMEZONE="$default_tz"
    else
        local tz_suggestion="${system_tz:-$default_tz}"
        prompt_with_default "Timezone" "$tz_suggestion" "N8N_TIMEZONE"
    fi

    print_success "Timezone set to: $N8N_TIMEZONE"

    # Set the docker host's timezone to match
    if confirm_prompt "Set docker host timezone to match ($N8N_TIMEZONE)?" "y"; then
        set_host_timezone "$N8N_TIMEZONE"
    fi
}

set_host_timezone() {
    local timezone="$1"
    local tz_file="/usr/share/zoneinfo/$timezone"

    # Check if timezone file exists
    if [ ! -f "$tz_file" ]; then
        print_warning "Timezone file not found: $tz_file"
        print_warning "Host timezone will remain unchanged"
        return 1
    fi

    print_info "Setting host timezone to: $timezone"

    # Set timezone using timedatectl if available (preferred method)
    if command_exists timedatectl; then
        if run_privileged timedatectl set-timezone "$timezone" 2>/dev/null; then
            print_success "Host timezone updated using timedatectl"
            return 0
        else
            print_warning "timedatectl failed, trying manual method..."
        fi
    fi

    # Fallback: Manual method
    # Create symlink for /etc/localtime
    if run_privileged ln -sf "$tz_file" /etc/localtime 2>/dev/null; then
        print_success "Updated /etc/localtime symlink"
    else
        print_warning "Failed to update /etc/localtime"
        return 1
    fi

    # Update /etc/timezone file (Debian/Ubuntu)
    if [ -f /etc/timezone ] || [ -d /etc ]; then
        if echo "$timezone" | run_privileged tee /etc/timezone >/dev/null 2>&1; then
            print_success "Updated /etc/timezone file"
        else
            print_warning "Failed to update /etc/timezone"
        fi
    fi

    # Update clock
    if command_exists hwclock; then
        run_privileged hwclock --systohc 2>/dev/null || true
    fi

    print_success "Host timezone updated to: $timezone"
    print_info "Note: APScheduler will use this timezone for backup scheduling"
    return 0
}

generate_encryption_key() {
    print_section "Encryption Key Configuration"

    local vol_key="" env_key="" n8n_volume=""

    # 1) n8n refuses to start if the key differs from the one in its data
    #    volume, so an existing volume's key always wins.
    vol_key=$(read_n8n_encryption_key_from_volume 2>/dev/null) || vol_key=""
    if [ -n "$vol_key" ]; then
        if [ -n "${N8N_ENCRYPTION_KEY:-}" ] && [ "$N8N_ENCRYPTION_KEY" != "$vol_key" ]; then
            print_warning "The configured N8N_ENCRYPTION_KEY does not match the key stored in the"
            print_warning "existing n8n data volume (n8n would refuse to start) - using the volume's key."
        fi
        N8N_ENCRYPTION_KEY="$vol_key"
        N8N_KEY_VERIFIED=true
        AUTOGEN_ENCRYPTION_KEY=false
        print_success "Reusing the encryption key from the existing n8n data volume"
        return 0
    fi

    # 2) Key supplied via setup-config / environment / resumed state
    if [ -n "${N8N_ENCRYPTION_KEY:-}" ]; then
        print_success "Using the configured encryption key"
        return 0
    fi

    # 3) Key from an existing .env
    if [ -f "${SCRIPT_DIR}/.env" ]; then
        env_key=$(env_get_key "${SCRIPT_DIR}/.env" N8N_ENCRYPTION_KEY) || env_key=""
    fi
    if [ -n "$env_key" ]; then
        N8N_ENCRYPTION_KEY="$env_key"
        print_success "Reusing the encryption key from the existing .env"
        return 0
    fi

    # 4) Data exists but its key could not be recovered: generating a new one
    #    would make every stored credential undecryptable.
    n8n_volume=$(find_compose_volume n8n_data 2>/dev/null) || n8n_volume=""
    if [ -n "$n8n_volume" ]; then
        print_warning "Existing n8n data volume '${n8n_volume}' found, but its encryption key could not be read."
        if [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
            if [ "${FORCE_REGENERATE_SECRETS:-false}" != "true" ]; then
                print_error "Refusing to generate a new encryption key for existing n8n data in AUTO_CONFIRM mode."
                print_info "Set N8N_ENCRYPTION_KEY in your config to the existing key, or set"
                print_info "FORCE_REGENERATE_SECRETS=true to accept that stored credentials become unreadable."
                exit 1
            fi
            print_warning "FORCE_REGENERATE_SECRETS=true - generating a NEW key; stored n8n credentials will be unreadable"
        else
            echo -ne "${WHITE}  Enter the existing encryption key (blank = generate a new one)${NC}: "
            read -rs N8N_ENCRYPTION_KEY
            echo ""
            if [ -n "$N8N_ENCRYPTION_KEY" ]; then
                print_success "Using the entered encryption key"
                return 0
            fi
            if ! confirm_prompt "Generate a NEW key? Credentials stored in n8n will become unreadable" "n"; then
                print_error "Aborting - no encryption key available"
                exit 1
            fi
        fi
    fi

    AUTOGEN_ENCRYPTION_KEY=true
    if command_exists openssl; then
        N8N_ENCRYPTION_KEY=$(openssl rand -base64 32)
        print_success "Generated secure encryption key"
    else
        prompt_with_default "Enter encryption key (min 32 chars)" "" "N8N_ENCRYPTION_KEY"
    fi

    print_warning "IMPORTANT: Save your encryption key in a secure location!"
}

configure_portainer() {
    print_subsection
    echo -e "${WHITE}  Portainer Configuration${NC}"
    echo ""
    echo -e "  ${GRAY}Portainer provides a web UI for managing Docker containers.${NC}"
    echo ""
    echo -e "  ${WHITE}Portainer Options:${NC}"
    echo -e "    ${CYAN}1)${NC} Agent only - Connect to existing Portainer server (installs agent on port 9001)"
    echo -e "    ${CYAN}2)${NC} Full Portainer - Install Portainer server"
    echo ""

    local portainer_choice=""
    while [[ ! "$portainer_choice" =~ ^[12]$ ]]; do
        echo -ne "${WHITE}  Enter your choice [1-2]${NC}: "
        read portainer_choice
    done

    case $portainer_choice in
        1)
            INSTALL_PORTAINER=false
            INSTALL_PORTAINER_AGENT=true
            echo ""
            echo -e "  ${YELLOW}Security:${NC} ${GRAY}the agent has full control of Docker and the host filesystem.${NC}"
            echo -e "  ${GRAY}Publish it only on an address your Portainer server reaches privately${NC}"
            echo -e "  ${GRAY}(LAN or Tailscale IP). Docker-published ports bypass ufw; 0.0.0.0 exposes${NC}"
            echo -e "  ${GRAY}it on every interface. The server must also use the generated AGENT_SECRET.${NC}"
            local default_bind="${PORTAINER_AGENT_BIND:-${N8N_MANAGEMENT_HOST_IP:-127.0.0.1}}"
            local agent_bind=""
            while true; do
                echo -ne "${WHITE}  IP address to publish the agent on [${default_bind}]${NC}: "
                read agent_bind
                agent_bind="${agent_bind:-$default_bind}"
                if [[ "$agent_bind" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
                    if [ "$agent_bind" = "0.0.0.0" ] && \
                        ! confirm_prompt "  0.0.0.0 exposes the agent on every interface. Continue?" "n"; then
                        continue
                    fi
                    break
                fi
                print_warning "Enter an IPv4 address"
            done
            PORTAINER_AGENT_BIND="$agent_bind"
            print_success "Portainer Agent will be installed on ${PORTAINER_AGENT_BIND}:9001 (set AGENT_SECRET on your Portainer server; it is PORTAINER_AGENT_SECRET in .env)"
            ;;
        2)
            INSTALL_PORTAINER=true
            INSTALL_PORTAINER_AGENT=false

            print_success "Full Portainer will be installed at /portainer/"
            echo -e "  ${CYAN}ℹ${NC}  ${GRAY}Login credentials will be the same as the Management Console${NC}"
            ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# OPTIONAL SERVICES CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

configure_optional_services() {
    print_section "Optional Services Configuration"

    # In preconfig mode, services are already configured by load_preconfig
    if [ "$PRECONFIG_MODE" = "true" ]; then
        print_info "Using pre-configured optional services"
        [ "$INSTALL_PORTAINER" = "true" ] && print_success "  Portainer: enabled"
        [ "$INSTALL_PORTAINER_AGENT" = "true" ] && print_success "  Portainer Agent: enabled"
        [ "$INSTALL_CLOUDFLARE_TUNNEL" = "true" ] && print_success "  Cloudflare Tunnel: enabled"
        [ "$INSTALL_TAILSCALE" = "true" ] && print_success "  Tailscale: enabled"
        [ "$INSTALL_ADMINER" = "true" ] && print_success "  Adminer: enabled"
        [ "$INSTALL_DOZZLE" = "true" ] && print_success "  Dozzle: enabled"
        [ "$INSTALL_NTFY" = "true" ] && print_success "  NTFY: enabled"
        [ "$INSTALL_PUBLIC_WEBSITE" = "true" ] && print_success "  Public Website: enabled"
        if [ "$USE_PREBUILT_MANAGEMENT" = "true" ]; then
            print_success "  Management Console: using pre-built image"
        else
            print_success "  Management Console: building locally"
        fi
        return
    fi

    echo ""
    echo -e "  ${GRAY}The following optional services can be added to your installation:${NC}"
    echo ""
    echo -e "  ${WHITE}${BOLD}Container Management:${NC}"
    echo -e "    ${CYAN}•${NC} Portainer - Docker container management UI"
    echo ""
    echo -e "  ${WHITE}${BOLD}External Access:${NC}"
    echo -e "    ${CYAN}•${NC} Cloudflare Tunnel - Secure access without exposing ports"
    echo -e "    ${CYAN}•${NC} Tailscale - Private mesh VPN network access"
    echo ""
    echo -e "  ${WHITE}${BOLD}Development Tools:${NC}"
    echo -e "    ${CYAN}•${NC} Adminer - Web-based database management"
    echo -e "    ${CYAN}•${NC} Dozzle - Real-time container log viewer"
    echo ""
    echo -e "  ${WHITE}${BOLD}Notifications:${NC}"
    echo -e "    ${CYAN}•${NC} NTFY - Self-hosted push notifications server"
    echo ""
    echo -e "  ${WHITE}${BOLD}Web Hosting:${NC}"
    echo -e "    ${CYAN}•${NC} Public Website - Host a static website (www.) with File Browser management"
    echo ""

    if confirm_prompt "Would you like to configure optional services?" "n"; then
        # Public Website
        if confirm_prompt "  Host a public website (www.${N8N_DOMAIN#*.})?" "n"; then
            configure_public_website
        fi

        # Portainer
        if confirm_prompt "  Install Portainer for container management?" "n"; then
            configure_portainer
        fi

        # Cloudflare Tunnel
        if confirm_prompt "  Configure Cloudflare Tunnel for secure external access?" "n"; then
            configure_cloudflare_tunnel
        fi

        # Tailscale
        if confirm_prompt "  Configure Tailscale for private VPN access?" "n"; then
            configure_tailscale
        fi

        # Adminer
        if confirm_prompt "  Install Adminer for database management?" "n"; then
            configure_adminer
        fi

        # Dozzle
        if confirm_prompt "  Install Dozzle for container log viewing?" "n"; then
            configure_dozzle
        fi

        # NTFY
        if confirm_prompt "  Install NTFY for push notifications?" "n"; then
            configure_ntfy
        fi
    else
        print_info "Skipping optional services. You can add them later by running setup again."
    fi

    # Configure management console image source
    configure_management_image

    # Validate public website + Cloudflare Tunnel requirement
    validate_public_website_requirements
}

# ===========================================================================
# Validate Public Website Requirements
# ===========================================================================
# Public website works best with Cloudflare Tunnel for proper hostname routing.
# Without it, accessing the public website requires advanced configuration
# (manual DNS/routing setup). The install will continue but with a warning.
# ===========================================================================
validate_public_website_requirements() {
    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ] && [ "$INSTALL_CLOUDFLARE_TUNNEL" != "true" ]; then
        echo ""
        print_warning "Public Website without Cloudflare Tunnel"
        echo ""
        echo -e "  ${YELLOW}You have enabled Public Website but not Cloudflare Tunnel.${NC}"
        echo ""
        echo -e "  ${GRAY}The public website runs in a separate nginx container (n8n_nginx_public)${NC}"
        echo -e "  ${GRAY}which requires hostname-based routing to be accessible.${NC}"
        echo ""
        echo -e "  ${GRAY}Without Cloudflare Tunnel, you will need to manually configure:${NC}"
        echo -e "    • DNS routing to direct traffic to the correct container"
        echo -e "    • A reverse proxy or load balancer for hostname-based routing"
        echo -e "    • Port mapping if accessing directly"
        echo ""
        echo -e "  ${WHITE}Recommended: Enable Cloudflare Tunnel for automatic routing.${NC}"
        echo ""

        if confirm_prompt "Would you like to configure Cloudflare Tunnel now?" "y"; then
            configure_cloudflare_tunnel
            if [ "$INSTALL_CLOUDFLARE_TUNNEL" = "true" ]; then
                print_success "Cloudflare Tunnel enabled - Public Website will work correctly"
            else
                print_warning "Cloudflare Tunnel not configured"
                print_info "Public website container will be created but may not be accessible"
                print_info "without additional manual configuration"
            fi
        else
            print_warning "Continuing without Cloudflare Tunnel"
            print_info "Public website container will be created but may not be accessible"
            print_info "without additional manual configuration"
        fi
        echo ""
    fi
}

# ===========================================================================
# Configure Management Console Image Source
# ===========================================================================
# Users can choose between:
# - Pre-built image from Docker Hub (faster, recommended for most users)
# - Build locally from source (for customization or development)
# ===========================================================================
configure_management_image() {
    # Skip in preconfig mode - handled by preconfig variables
    if [ "$PRECONFIG_MODE" = "true" ]; then
        return
    fi

    print_subsection
    echo -e "${WHITE}  Management Console Image${NC}"
    echo ""
    echo -e "  ${GRAY}The Management Console can be deployed using:${NC}"
    echo ""
    echo -e "    ${CYAN}1)${NC} Pre-built image from Docker Hub (faster, recommended)"
    echo -e "       ${GRAY}Downloads ready-to-run image (~300MB)${NC}"
    echo ""
    echo -e "    ${CYAN}2)${NC} Build locally from source"
    echo -e "       ${GRAY}Builds image on this machine (slower, for customization)${NC}"
    echo ""

    local choice=""
    while [[ ! "$choice" =~ ^[1-2]$ ]]; do
        echo -ne "${WHITE}  Enter your choice [1-2] (default: 1)${NC}: "
        read choice
        choice=${choice:-1}
    done

    case $choice in
        1)
            USE_PREBUILT_MANAGEMENT=true
            print_success "Using pre-built image: ${MANAGEMENT_IMAGE}"
            ;;
        2)
            USE_PREBUILT_MANAGEMENT=false
            print_info "Will build management console locally during deployment"
            ;;
    esac
    echo ""
}

configure_public_website() {
    print_subsection
    echo -e "${WHITE}  Public Website Configuration${NC}"
    
    # Extract root domain logic
    local root_domain=$(echo "$N8N_DOMAIN" | awk -F. '{if (NF>2) {print $(NF-1)"."$NF} else {print $0}}')
    
    echo ""
    echo -e "  ${GRAY}Enter the subdomain for your public website (e.g., 'www').${NC}"
    echo -ne "${WHITE}  Public website subdomain [www]${NC}: "
    read public_subdomain
    public_subdomain=${public_subdomain:-www}
    
    local public_domain="${public_subdomain}.${root_domain}"
    
    echo ""
    echo -e "  ${GRAY}This will configure Nginx to serve a static website at:${NC}"
    echo -e "    - ${CYAN}${public_domain}${NC}"
    echo -e "  ${GRAY}It includes 'File Browser' for managing website files via the Management Console.${NC}"
    echo ""

    # Perform DNS Validation (Matching validate_domain exactly)
    print_info "Validating public domain DNS..."
    
    local local_ips=$(get_local_ips)
    local domain_ip=""
    local validation_passed=true
    
    # Resolve the PUBLIC domain
    print_info "Resolving $public_domain..."
    
    if command_exists dig; then
        domain_ip=$(dig +short "$public_domain" 2>/dev/null | head -1)
    elif command_exists nslookup; then
        domain_ip=$(nslookup "$public_domain" 2>/dev/null | grep -A1 "Name:" | grep "Address:" | awk '{print $2}' | head -1)
    elif command_exists host; then
        domain_ip=$(host "$public_domain" 2>/dev/null | grep "has address" | awk '{print $4}' | head -1)
    elif command_exists getent; then
        domain_ip=$(getent hosts "$public_domain" 2>/dev/null | awk '{print $1}' | head -1)
    fi

    if [ -z "$domain_ip" ]; then
        print_warning "Could not resolve $public_domain to an IP address"
        echo ""
        echo -e "  ${YELLOW}This could mean:${NC}"
        echo -e "    - The DNS record hasn't been created yet"
        echo -e "    - The DNS hasn't propagated yet"
        echo -e "    - The domain name is incorrect"
        echo ""
        validation_passed=false
    else
        print_success "Domain resolves to: $domain_ip"

        # Check if the resolved IP matches any local IP
        local ip_matches=false
        for local_ip in $local_ips; do
            if [ "$local_ip" = "$domain_ip" ]; then
                ip_matches=true
                break
            fi
        done

        if [ "$ip_matches" = true ]; then
            print_success "Domain IP matches this server"
        else
            print_warning "Domain IP ($domain_ip) does not match any local IP"
            echo ""
            echo -e "  ${YELLOW}IMPORTANT:${NC}"
            echo -e "  ${YELLOW}The domain $public_domain points to $domain_ip${NC}"
            echo -e "  ${YELLOW}but this server's IPs are different.${NC}"
            echo ""
            
            # Special hint for Cloudflare Tunnel users
            if [ "$INSTALL_CLOUDFLARE_TUNNEL" = "true" ]; then
                echo -e "  ${YELLOW}Since you are using Cloudflare Tunnel:${NC}"
                echo -e "  You must add a Public Hostname in Cloudflare Zero Trust:"
                echo -e "    - Hostname: ${CYAN}${public_domain}${NC}"
                echo -e "    - Service:  ${CYAN}HTTP${NC} -> ${CYAN}nginx_public:80${NC}"
            else
                echo -e "  ${YELLOW}This will cause the website to fail because:${NC}"
                echo -e "    - SSL certificate validation may fail"
                echo -e "    - Traffic won't reach this server"
            fi
            echo ""
            validation_passed=false
        fi
    fi

    if [ "$validation_passed" = false ]; then
        if ! confirm_prompt "Do you understand the risks and want to continue?" "n"; then
            print_warning "Public website configuration cancelled."
            return
        fi
    fi

    # Save variables for Nginx generation
    PUBLIC_WEBSITE_DOMAIN="$public_domain"
    PUBLIC_WEBSITE_ROOT_DOMAIN="$root_domain"
    INSTALL_PUBLIC_WEBSITE=true
    
    print_success "Public Website enabled"
}

configure_cloudflare_tunnel() {
    print_subsection
    echo -e "${WHITE}  Cloudflare Tunnel Configuration${NC}"
    echo ""
    echo -e "  ${GRAY}Cloudflare Tunnel provides secure access to your n8n instance${NC}"
    echo -e "  ${GRAY}without exposing any ports to the public internet.${NC}"
    echo ""
    echo -e "  ${GRAY}Requirements:${NC}"
    echo -e "    • Cloudflare account with your domain"
    echo -e "    • Cloudflare Tunnel token from Zero Trust dashboard"
    echo ""
    echo -e "  ${GRAY}Create a tunnel at: https://one.dash.cloudflare.com${NC}"
    echo -e "  ${GRAY}Navigate to: Networks → Tunnels → Create a tunnel${NC}"
    echo ""

    echo -ne "${WHITE}  Enter your Cloudflare Tunnel token${NC}: "
    read_masked_token
    CF_TUNNEL_TOKEN="$MASKED_INPUT"

    if [ -z "$CF_TUNNEL_TOKEN" ]; then
        print_error "Tunnel token is required for Cloudflare Tunnel"
        INSTALL_CLOUDFLARE_TUNNEL=false
        return
    fi

    CLOUDFLARE_TUNNEL_TOKEN="$CF_TUNNEL_TOKEN"
    INSTALL_CLOUDFLARE_TUNNEL=true

    print_success "Cloudflare Tunnel configured"
}

configure_tailscale() {
    print_subsection
    echo -e "${WHITE}  Tailscale Configuration${NC}"
    echo ""
    echo -e "  ${GRAY}Tailscale provides private access to your n8n instance${NC}"
    echo -e "  ${GRAY}over a secure mesh VPN network.${NC}"
    echo ""
    echo -e "  ${GRAY}Requirements:${NC}"
    echo -e "    • Tailscale account"
    echo -e "    • Auth key from: https://login.tailscale.com/admin/settings/keys${NC}"
    echo ""

    echo -ne "${WHITE}  Enter your Tailscale auth key${NC}: "
    read_masked_token
    TS_AUTH_KEY="$MASKED_INPUT"

    if [ -z "$TS_AUTH_KEY" ]; then
        print_error "Auth key is required for Tailscale"
        INSTALL_TAILSCALE=false
        return
    fi

    TAILSCALE_AUTH_KEY="$TS_AUTH_KEY"
    INSTALL_TAILSCALE=true

    print_success "Auth key accepted"

    # Optional hostname
    echo ""
    echo -ne "${WHITE}  Tailscale hostname [n8n-server]${NC}: "
    read ts_hostname
    TAILSCALE_HOSTNAME=${ts_hostname:-n8n-server}

    # Capture the host IP for TS_ROUTES (advertise this host to Tailscale network)
    local primary_ip=$(get_local_ips | head -1)
    if [ -n "$primary_ip" ]; then
        TAILSCALE_ROUTES="${primary_ip}/32"
        echo ""
        print_info "Docker host IP detected: ${primary_ip}"
        print_info "Route configured: ${TAILSCALE_ROUTES}"
        print_info "To expose your full subnet, change TAILSCALE_ROUTES in .env to ${primary_ip%.*}.0/24"
    else
        print_warning "Could not detect host IP for TS_ROUTES"
        TAILSCALE_ROUTES=""
    fi

    print_success "Tailscale configured"
    echo ""
    print_info "Your n8n instance will be accessible at: ${TAILSCALE_HOSTNAME}.your-tailnet.ts.net"
    echo ""
    echo -e "  ${YELLOW}IMPORTANT: After deployment, approve advertised routes:${NC}"
    echo -e "    1. Visit: ${CYAN}https://login.tailscale.com/admin/machines${NC}"
    echo -e "    2. Find your ${WHITE}${TAILSCALE_HOSTNAME:-n8n-tailscale}${NC} node"
    echo -e "    3. Click the node and approve the advertised route (${TAILSCALE_ROUTES})"
    echo ""
    echo -e "  ${GRAY}Once approved, access via Tailscale:${NC}"
    echo -e "    • n8n:        ${CYAN}https://${TAILSCALE_HOSTNAME:-n8n-tailscale}.your-tailnet.ts.net${NC}"
    echo -e "    • Management: ${CYAN}https://${TAILSCALE_HOSTNAME:-n8n-tailscale}.your-tailnet.ts.net/management${NC}"
    echo -e "    • SSH:        ${CYAN}ssh user@${TAILSCALE_HOSTNAME:-n8n-tailscale}.your-tailnet.ts.net${NC}"
}

# Generate tailscale-serve.json for TS_SERVE_CONFIG
generate_tailscale_serve_config() {
    print_info "Generating tailscale-serve.json..."

    local ts_config_file="${SCRIPT_DIR}/tailscale-serve.json"

    # Check if tailscale-serve.json exists as a directory (Docker creates this if file was missing)
    if [ -d "$ts_config_file" ]; then
        print_warning "tailscale-serve.json exists as a directory (Docker artifact)"
        print_info "Removing directory and creating proper config file..."
        rm -rf "$ts_config_file"
    fi

    # Proxy straight to the nginx container over n8n_network. Going through
    # the host's published port 443 would make docker-proxy re-originate the
    # connection from the network gateway, which nginx treats as external.
    # From here the source is the Tailscale container's static IP, which is
    # the one Docker address nginx trusts as internal.
    local nginx_c="${NGINX_CONTAINER:-n8n_nginx}"
    local proxy_target="https+insecure://${nginx_c}:443"
    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        # n8n_nginx listens on plain HTTP 80 behind nginx_router
        proxy_target="http://${nginx_c}:80"
    fi

    cat > "$ts_config_file" << EOF
{
  "TCP": { "443": { "HTTPS": true } },
  "Web": {
    "\${TS_CERT_DOMAIN}:443": {
      "Handlers": {
        "/": { "Proxy": "${proxy_target}" }
      }
    }
  }
}
EOF

    chmod 644 "$ts_config_file"
    print_success "tailscale-serve.json generated"
}

configure_adminer() {
    print_subsection
    echo -e "${WHITE}  Adminer Configuration${NC}"
    echo ""
    echo -e "  ${GRAY}Adminer provides a web-based interface for database management.${NC}"
    echo ""

    INSTALL_ADMINER=true

    print_success "Adminer will be available at https://\${DOMAIN}/adminer/"
}

configure_dozzle() {
    print_subsection
    echo -e "${WHITE}  Dozzle Configuration${NC}"
    echo ""
    echo -e "  ${GRAY}Dozzle provides real-time container log viewing in your browser.${NC}"
    echo ""

    INSTALL_DOZZLE=true

    print_success "Dozzle will be available at https://\${DOMAIN}/dozzle/"
    echo -e "  ${CYAN}ℹ${NC}  ${GRAY}Login credentials will be the same as the Management Console${NC}"
}

configure_ntfy() {
    print_subsection
    echo -e "${WHITE}  NTFY Push Notifications Configuration${NC}"
    echo ""
    echo -e "  ${GRAY}NTFY is a simple HTTP-based pub-sub notification service.${NC}"
    echo -e "  ${GRAY}It allows you to send push notifications to your phone or desktop.${NC}"
    echo ""
    echo -e "  ${YELLOW}Important:${NC} ${GRAY}NTFY requires its own subdomain (e.g., ntfy.example.com).${NC}"
    echo -e "  ${GRAY}It cannot run on a subpath like /ntfy/ due to how NTFY handles requests.${NC}"
    echo ""

    INSTALL_NTFY=true
    # Internal URL for management console communication
    NTFY_INTERNAL_URL="http://n8n_ntfy:80"

    # Extract base domain (remove first subdomain if present)
    # e.g., n8n01.example.com -> example.com, or example.com stays as example.com
    local domain_parts=$(echo "${N8N_DOMAIN}" | tr '.' '\n' | wc -l)
    if [ "$domain_parts" -gt 2 ]; then
        local base_domain="${N8N_DOMAIN#*.}"
    else
        local base_domain="${N8N_DOMAIN}"
    fi
    local default_ntfy_subdomain="ntfy.${base_domain}"

    echo -e "  ${GRAY}Enter the subdomain for your NTFY server.${NC}"
    echo -e "  ${GRAY}This will be the public URL for accessing NTFY.${NC}"
    echo -ne "${WHITE}  NTFY subdomain [default: ${default_ntfy_subdomain}]${NC}: "
    read ntfy_subdomain
    ntfy_subdomain=${ntfy_subdomain:-$default_ntfy_subdomain}

    # Set the public URL
    NTFY_PUBLIC_URL="https://${ntfy_subdomain}"
    NTFY_BASE_URL="${NTFY_PUBLIC_URL}"

    create_ntfy_config

    print_success "Self-hosted NTFY server will be installed"
    echo ""
    echo -e "  ${CYAN}ℹ${NC}  ${WHITE}NTFY Configuration:${NC}"
    echo -e "      Public URL:   ${CYAN}${NTFY_PUBLIC_URL}${NC}"
    echo -e "      Internal URL: ${GRAY}${NTFY_INTERNAL_URL}${NC} (for management console)"
    echo ""
    echo -e "  ${YELLOW}⚠${NC}  ${WHITE}Required: Configure Cloudflare Tunnel${NC}"
    echo -e "      ${GRAY}Add a public hostname in Cloudflare Zero Trust:${NC}"
    echo -e "      ${GRAY}  - Public hostname: ${CYAN}${ntfy_subdomain}${NC}"
    echo -e "      ${GRAY}  - Service type:    ${CYAN}HTTP${NC}"
    echo -e "      ${GRAY}  - Service URL:     ${CYAN}n8n_ntfy:80${NC}"
    echo ""
    echo -e "  ${CYAN}ℹ${NC}  ${GRAY}Anonymous access is denied. Subscribe/log in with NTFY_ADMIN_USER and${NC}"
    echo -e "      ${GRAY}NTFY_ADMIN_PASS from .env (generated during setup).${NC}"
    echo ""
}

create_ntfy_config() {
    # Create ntfy config directory and default server.yml
    mkdir -p "${SCRIPT_DIR}/ntfy"

    cat > "${SCRIPT_DIR}/ntfy/server.yml" << 'NTFYEOF'
# NTFY Server Configuration
# See https://ntfy.sh/docs/config/ for all options

# Cache settings
cache-file: /var/cache/ntfy/cache.db
cache-duration: 12h

# Attachment settings
attachment-cache-dir: /var/cache/ntfy/attachments
attachment-total-size-limit: 100M
attachment-file-size-limit: 15M
attachment-expiry-duration: 3h

# Auth settings (managed via environment variables in docker-compose.yaml):
# auth-file /var/lib/ntfy/auth.db, auth-default-access deny-all, and the admin
# user + console token provisioned from NTFY_ADMIN_* / NTFY_TOKEN in .env

# Logging
log-level: info
NTFYEOF
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

show_configuration_summary() {
    print_section "Configuration Summary"

    echo ""
    echo -e "  ${WHITE}${BOLD}Domain & URL:${NC}"
    echo -e "    Domain:              ${CYAN}$N8N_DOMAIN${NC}"
    echo -e "    n8n URL:             ${CYAN}https://$N8N_DOMAIN${NC}"
    echo -e "    Management URL:      ${CYAN}https://$N8N_DOMAIN/management/${NC}"
    echo ""

    echo -e "  ${WHITE}${BOLD}Database:${NC}"
    echo -e "    Name:                ${CYAN}$DB_NAME${NC}"
    echo -e "    User:                ${CYAN}$DB_USER${NC}"
    echo -e "    Password:            ${CYAN}$DB_PASSWORD${NC}"
    echo ""

    echo -e "  ${WHITE}${BOLD}Management Console:${NC}"
    echo -e "    URL:                 ${CYAN}/management/${NC}"
    echo -e "    Admin User:          ${CYAN}$ADMIN_USER${NC}"
    echo -e "    NFS Storage:         ${CYAN}${NFS_CONFIGURED:-false}${NC}"
    echo -e "    Notifications:       ${CYAN}${NOTIFICATIONS_CONFIGURED:-false}${NC}"
    echo ""

    echo -e "  ${WHITE}${BOLD}Other Settings:${NC}"
    echo -e "    Timezone:            ${CYAN}$N8N_TIMEZONE${NC}"
    echo -e "    DNS Provider:        ${CYAN}$DNS_PROVIDER_NAME${NC}"
    echo ""

    # Show optional services if any are enabled
    if [ "$INSTALL_CLOUDFLARE_TUNNEL" = true ] || [ "$INSTALL_TAILSCALE" = true ] || \
       [ "$INSTALL_ADMINER" = true ] || [ "$INSTALL_DOZZLE" = true ] || \
       [ "$INSTALL_PORTAINER" = true ] || [ "$INSTALL_PORTAINER_AGENT" = true ] || \
       [ "$INSTALL_NTFY" = true ] || [ -n "$NTFY_BASE_URL" ] || \
       [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        echo -e "  ${WHITE}${BOLD}Optional Services:${NC}"
        if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
            echo -e "    Public Website:      ${GREEN}enabled${NC} (${PUBLIC_WEBSITE_DOMAIN:-www.${N8N_DOMAIN#*.}})"
        fi
        if [ "$INSTALL_PORTAINER" = true ]; then
            echo -e "    Portainer:           ${GREEN}enabled${NC} (/portainer/)"
        elif [ "$INSTALL_PORTAINER_AGENT" = true ]; then
            echo -e "    Portainer Agent:     ${GREEN}enabled${NC} (${PORTAINER_AGENT_BIND:-127.0.0.1}:9001, AGENT_SECRET required)"
        fi
        if [ "$INSTALL_CLOUDFLARE_TUNNEL" = true ]; then
            echo -e "    Cloudflare Tunnel:   ${GREEN}enabled${NC}"
        fi
        if [ "$INSTALL_TAILSCALE" = true ]; then
            echo -e "    Tailscale:           ${GREEN}enabled${NC} (${TAILSCALE_HOSTNAME})"
        fi
        if [ "$INSTALL_ADMINER" = true ]; then
            echo -e "    Adminer:             ${GREEN}enabled${NC} (/adminer/)"
        fi
        if [ "$INSTALL_DOZZLE" = true ]; then
            echo -e "    Dozzle:              ${GREEN}enabled${NC} (/dozzle/)"
        fi
        if [ "$INSTALL_NTFY" = true ]; then
            echo -e "    NTFY:                ${GREEN}enabled${NC} (${NTFY_PUBLIC_URL:-subdomain})"
        elif [ -n "$NTFY_BASE_URL" ]; then
            echo -e "    NTFY:                ${CYAN}external${NC} (${NTFY_PUBLIC_URL:-$NTFY_BASE_URL})"
        fi
        echo ""
    fi

    if ! confirm_prompt "Is this configuration correct?"; then
        return 1
    fi

    return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT
# ═══════════════════════════════════════════════════════════════════════════════

create_letsencrypt_volume() {
    if $DOCKER_SUDO docker volume inspect letsencrypt >/dev/null 2>&1; then
        print_info "Volume 'letsencrypt' already exists"
    else
        $DOCKER_SUDO docker volume create letsencrypt
        print_success "Volume 'letsencrypt' created"
    fi
}

initialize_public_website() {
    # Initialize the public website with a default landing page
    # Only runs if public_web_root volume is empty

    print_info "Initializing public website..."

    # The real volume name (compose project label), not a guess from the
    # directory name - compose normalises project names differently.
    local volume_name
    if ! volume_name=$(find_compose_volume public_web_root); then
        print_warning "public_web_root volume not found - skipping default landing page"
        return 0
    fi

    # Check if index.html already exists
    local has_index=$($DOCKER_SUDO docker run --rm $DOCKER_APPARMOR_OPT -v "${volume_name}:/data:ro" "$ALPINE_IMAGE" sh -c '[ -f /data/index.html ] && echo "yes" || echo "no"' 2>/dev/null)

    if [ "$has_index" = "yes" ]; then
        print_info "Public website already has content, skipping initialization"
        return 0
    fi

    # Extract root domain for display
    local root_domain=$(echo "$N8N_DOMAIN" | awk -F. '{if (NF>2) {print $(NF-1)"."$NF} else {print $0}}')
    local public_domain="${PUBLIC_WEBSITE_DOMAIN:-www.${root_domain}}"

    # Create the default landing page (WHITE template)
    $DOCKER_SUDO docker run --rm $DOCKER_APPARMOR_OPT -v "${volume_name}:/data" "$ALPINE_IMAGE" sh -c "cat > /data/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Public Website | n8n Management</title>
    <link rel=\"icon\" type=\"image/svg+xml\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0%25' y1='0%25' x2='100%25' y2='100%25'%3E%3Cstop offset='0%25' stop-color='%23ff6d5a'/%3E%3Cstop offset='100%25' stop-color='%23d84a38'/%3E%3C/linearGradient%3E%3C/defs%3E%3Ccircle cx='16' cy='16' r='14' fill='url(%23g)'/%3E%3Cpath d='M10 20V12a2 2 0 012-2h0a2 2 0 012 2v8M18 20V14a2 2 0 012-2h0a2 2 0 012 2v6' stroke='white' stroke-width='2.5' stroke-linecap='round' fill='none'/%3E%3C/svg%3E\">
    <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
    <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
    <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap\" rel=\"stylesheet\">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #ffffff; color: #1e293b; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 2rem; }
        .bg-grid { position: fixed; inset: 0; background-image: linear-gradient(rgba(0,0,0,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,0.03) 1px, transparent 1px); background-size: 50px 50px; pointer-events: none; }
        .container { text-align: center; max-width: 700px; animation: fadeUp 0.6s ease-out; }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .hero-graphic { margin-bottom: 2.5rem; }
        .hero-graphic svg { width: 180px; height: 180px; filter: drop-shadow(0 20px 40px rgba(249, 115, 22, 0.2)); }
        h1 { font-size: 2.5rem; font-weight: 700; color: #0f172a; margin-bottom: 1rem; }
        .subtitle { color: #64748b; font-size: 1.15rem; line-height: 1.7; margin-bottom: 2.5rem; max-width: 500px; margin-left: auto; margin-right: auto; }
        .card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 20px; padding: 2.5rem; margin-bottom: 2rem; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04); }
        .card-title { font-size: 1.1rem; font-weight: 600; color: #0f172a; margin-bottom: 1.5rem; display: flex; align-items: center; justify-content: center; gap: 0.75rem; }
        .card-title svg { width: 24px; height: 24px; fill: #f97316; }
        .steps { list-style: none; text-align: left; max-width: 400px; margin: 0 auto; }
        .steps li { color: #475569; padding: 1rem 0; border-bottom: 1px solid #f1f5f9; display: flex; align-items: center; gap: 1rem; font-size: 1rem; }
        .steps li:last-child { border-bottom: none; }
        .step-num { background: linear-gradient(135deg, #f97316, #ea580c); color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.875rem; font-weight: 700; flex-shrink: 0; }
        .highlight { color: #f97316; font-weight: 600; }
        .btn { display: inline-flex; align-items: center; gap: 0.5rem; background: linear-gradient(135deg, #f97316, #ea580c); color: white; font-size: 1rem; font-weight: 600; padding: 1rem 2rem; border-radius: 12px; text-decoration: none; transition: all 0.2s ease; box-shadow: 0 4px 15px rgba(249, 115, 22, 0.3); }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(249, 115, 22, 0.4); }
        .btn svg { width: 20px; height: 20px; fill: currentColor; }
        .footer { margin-top: 2rem; color: #94a3b8; font-size: 0.875rem; }
        .footer a { color: #f97316; text-decoration: none; font-weight: 500; }
        .footer a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class=\"bg-grid\"></div>
    <div class=\"container\">
        <div class=\"hero-graphic\">
            <svg viewBox=\"0 0 180 180\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\">
                <rect x=\"20\" y=\"20\" width=\"140\" height=\"140\" rx=\"28\" fill=\"url(#grad1)\"/>
                <rect x=\"45\" y=\"55\" width=\"90\" height=\"12\" rx=\"6\" fill=\"white\" opacity=\"0.9\"/>
                <rect x=\"45\" y=\"75\" width=\"70\" height=\"12\" rx=\"6\" fill=\"white\" opacity=\"0.7\"/>
                <rect x=\"45\" y=\"95\" width=\"80\" height=\"12\" rx=\"6\" fill=\"white\" opacity=\"0.5\"/>
                <rect x=\"45\" y=\"115\" width=\"50\" height=\"12\" rx=\"6\" fill=\"white\" opacity=\"0.3\"/>
                <circle cx=\"140\" cy=\"140\" r=\"30\" fill=\"white\" stroke=\"url(#grad1)\" stroke-width=\"4\"/>
                <path d=\"M130 140L137 147L152 132\" stroke=\"url(#grad1)\" stroke-width=\"4\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>
                <defs>
                    <linearGradient id=\"grad1\" x1=\"0\" y1=\"0\" x2=\"180\" y2=\"180\" gradientUnits=\"userSpaceOnUse\">
                        <stop stop-color=\"#f97316\"/>
                        <stop offset=\"1\" stop-color=\"#ea580c\"/>
                    </linearGradient>
                </defs>
            </svg>
        </div>
        <h1>Your Website is Ready!</h1>
        <p class=\"subtitle\">This is your public-facing website. Customize it by uploading your own content through the management console.</p>
        <div class=\"card\">
            <div class=\"card-title\">
                <svg viewBox=\"0 0 24 24\"><path d=\"M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z\"/></svg>
                Quick Start Guide
            </div>
            <ol class=\"steps\">
                <li><span class=\"step-num\">1</span><span>Open the <span class=\"highlight\">Management Console</span></span></li>
                <li><span class=\"step-num\">2</span><span>Log in with your credentials</span></li>
                <li><span class=\"step-num\">3</span><span>Click <span class=\"highlight\">System</span> &rarr; <span class=\"highlight\">Files</span></span></li>
                <li><span class=\"step-num\">4</span><span>Upload your website files</span></li>
            </ol>
        </div>
        <a href=\"/management/\" class=\"btn\">
            <svg viewBox=\"0 0 24 24\"><path d=\"M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z\"/></svg>
            Open Management Console
        </a>
        <p class=\"footer\">Powered by <a href=\"https://github.com/rjsears/n8n_nginx\" target=\"_blank\">n8n Management</a></p>
    </div>
</body>
</html>
HTMLEOF"

    # Set proper permissions
    $DOCKER_SUDO docker run --rm $DOCKER_APPARMOR_OPT -v "${volume_name}:/data" "$ALPINE_IMAGE" chmod -R 755 /data

    print_success "Public website initialized with default landing page"
}

deploy_stack() {
    print_section "Deploying n8n Stack v3.0"

    local docker_compose_cmd="docker compose"
    if [ "$USE_STANDALONE_COMPOSE" = true ]; then
        docker_compose_cmd="docker-compose"
    fi
    if [ -n "$DOCKER_SUDO" ]; then
        docker_compose_cmd="$DOCKER_SUDO $docker_compose_cmd"
    fi

    cd "$SCRIPT_DIR"

    # Must run before any "down": if the pinned subnet is taken, "up" would
    # fail and leave the stack stopped.
    if ! check_n8n_network_subnet_free; then
        print_error "Deployment aborted before touching the running stack."
        exit 1
    fi

    # Existing installs: n8n_network used to get a random Docker subnet. The
    # nginx access control now depends on the pinned subnet, and Docker cannot
    # change the subnet of an existing network, so recreate it (volumes kept).
    if n8n_network_needs_recreate; then
        print_info "Recreating the stack network (docker compose down; data volumes are kept)..."
        $docker_compose_cmd down
    fi

    # Start PostgreSQL
    print_step "1" "4" "Starting PostgreSQL database"
    $docker_compose_cmd up -d postgres

    echo -e "  ${GRAY}Waiting for PostgreSQL...${NC}"
    local max_attempts=30
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if $DOCKER_SUDO docker exec $POSTGRES_CONTAINER pg_isready -U $DB_USER -d $DB_NAME >/dev/null 2>&1; then
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done

    if [ $attempt -eq $max_attempts ]; then
        print_error "PostgreSQL failed to start"
        exit 1
    fi

    # Create management database
    $DOCKER_SUDO docker exec $POSTGRES_CONTAINER psql -U $DB_USER -c "CREATE DATABASE ${DEFAULT_MGMT_DB_NAME};" 2>/dev/null || true
    print_success "PostgreSQL is running"

    # Obtain SSL certificate
    print_step "2" "4" "Obtaining SSL certificate"
    obtain_ssl_certificate
    verify_ssl_cert_lineage_for_nginx

    # Start all services
    print_step "3" "4" "Starting all services"
    $docker_compose_cmd up -d
    sleep 10
    if ! $DOCKER_SUDO docker exec "$NGINX_CONTAINER" nginx -t >/dev/null 2>&1; then
        print_error "nginx is not running or rejected its configuration"
        $DOCKER_SUDO docker exec "$NGINX_CONTAINER" nginx -t 2>&1 | sed 's/^/    /' || true
        print_info "Check: docker logs ${NGINX_CONTAINER}"
        exit 1
    fi
    print_success "All services started"

    # Initialize public website with default index if enabled
    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        initialize_public_website
    fi

    # Verify
    print_step "4" "4" "Verifying services"
    verify_services_v3

    # Make sure certificates will actually renew (dry-run), repair old broken lineages
    if [ "${SSL_METHOD:-certbot}" = "certbot" ]; then
        check_certificate_renewal || true
    fi

    # Create backup of working configuration after successful deployment
    print_info "Creating backup of working configuration..."
    backup_existing_config

    show_final_summary_v3
}

# Persist the installer's choices (read back by reconfigure, --update-access
# and the migration). Called after a fresh install and after every
# reconfigure, so a changed domain, certificate lineage or service selection
# is what the next run starts from.
save_setup_config() {
    cat > "${CONFIG_FILE}" << EOF
N8N_DOMAIN=${N8N_DOMAIN}
DNS_PROVIDER=${DNS_PROVIDER_NAME}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
POSTGRES_CONTAINER=${POSTGRES_CONTAINER}
N8N_CONTAINER=${N8N_CONTAINER}
NGINX_CONTAINER=${NGINX_CONTAINER}
CERTBOT_CONTAINER=${CERTBOT_CONTAINER}
LETSENCRYPT_EMAIL=${LETSENCRYPT_EMAIL}
SSL_CERT_DOMAIN=${SSL_CERT_DOMAIN}
N8N_TIMEZONE=${N8N_TIMEZONE}
PORTAINER_ENABLED=${INSTALL_PORTAINER}
PORTAINER_AGENT_ENABLED=${INSTALL_PORTAINER_AGENT}
MGMT_PORT=${MGMT_PORT}
NFS_CONFIGURED=${NFS_CONFIGURED}
ADMIN_USER=${ADMIN_USER}
# Optional Services
CLOUDFLARE_TUNNEL_ENABLED=${INSTALL_CLOUDFLARE_TUNNEL}
TAILSCALE_ENABLED=${INSTALL_TAILSCALE}
ADMINER_ENABLED=${INSTALL_ADMINER}
ADMINER_PORT=${ADMINER_PORT:-$DEFAULT_ADMINER_PORT}
DOZZLE_ENABLED=${INSTALL_DOZZLE}
DOZZLE_PORT=${DOZZLE_PORT:-$DEFAULT_DOZZLE_PORT}
NTFY_ENABLED=${INSTALL_NTFY}
NTFY_BASE_URL=${NTFY_BASE_URL}
NTFY_PUBLIC_URL=${NTFY_PUBLIC_URL}
NTFY_INTERNAL_URL=${NTFY_INTERNAL_URL:-http://n8n_ntfy:80}
PUBLIC_WEBSITE_ENABLED=${INSTALL_PUBLIC_WEBSITE}
PUBLIC_WEBSITE_DOMAIN=${PUBLIC_WEBSITE_DOMAIN}
# Access control (reused by reconfigure when regenerating nginx.conf)
INTERNAL_IP_RANGES="${INTERNAL_IP_RANGES}"
CUSTOM_INTERNAL_IPS="${CUSTOM_INTERNAL_IPS}"
N8N_NETWORK_SUBNET=${N8N_NETWORK_SUBNET}
EOF
    chmod 600 "${CONFIG_FILE}"
}

# =============================================================================
# SSL CERTIFICATE MANAGEMENT
# =============================================================================

determine_ssl_cert_domain() {
    # Single source of truth for the certificate lineage name (certbot
    # --cert-name, i.e. /etc/letsencrypt/live/<SSL_CERT_DOMAIN>/). Must run
    # BEFORE generate_nginx_conf_v3(); obtain_ssl_certificate() and the
    # renewal/repair tooling reuse the value instead of choosing again.
    #
    #   SSL_CERT_DOMAIN == N8N_DOMAIN   -> exact certificate for N8N_DOMAIN
    #   SSL_CERT_DOMAIN == <root>       -> wildcard: <root> + *.<root>

    # Extract root domain (e.g. n8n.example.com -> example.com)
    local root_domain
    root_domain=$(echo "$N8N_DOMAIN" | awk -F. '{if (NF>2) {print $(NF-1)"."$NF} else {print $0}}')

    # A saved choice (config file / resume state) wins, as long as it still
    # covers N8N_DOMAIN and a public website does not need a wildcard.
    local saved="${SSL_CERT_DOMAIN:-${SAVED_SSL_CERT_DOMAIN:-}}"
    if [ -n "$saved" ] && ssl_cert_name_covers_domain "$saved"; then
        if [ "$INSTALL_PUBLIC_WEBSITE" != "true" ] || [ "$saved" = "$root_domain" ]; then
            SSL_CERT_DOMAIN="$saved"
            print_info "Using configured SSL certificate domain: $SSL_CERT_DOMAIN"
            return 0
        fi
    fi

    # Default to the N8N_DOMAIN
    SSL_CERT_DOMAIN="$N8N_DOMAIN"

    if [ "$root_domain" = "$N8N_DOMAIN" ]; then
        print_info "SSL certificate domain set to: $SSL_CERT_DOMAIN"
        return 0
    fi

    # Public Website (www.<root>, files.<root>) requires the wildcard cert
    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        SSL_CERT_DOMAIN="$root_domain"
        print_info "Public Website enabled - using wildcard certificate domain: $SSL_CERT_DOMAIN"
        return 0
    fi

    # Reuse a certificate that already exists in the letsencrypt volume,
    # unless it has expired (then it is no better than none).
    if $DOCKER_SUDO docker volume inspect letsencrypt >/dev/null 2>&1; then
        local name
        for name in "$root_domain" "$N8N_DOMAIN"; do
            if [ "$($DOCKER_SUDO docker run --rm $DOCKER_APPARMOR_OPT \
                    -v letsencrypt:/etc/letsencrypt:ro "$ALPINE_IMAGE" \
                    sh -c "[ -f /etc/letsencrypt/live/${name}/fullchain.pem ] && echo exists" 2>/dev/null)" = "exists" ]; then
                if [ "$(ssl_lineage_validity "$name")" = "expired" ]; then
                    print_warning "Existing certificate lineage ${name} has expired - not reusing it"
                    continue
                fi
                SSL_CERT_DOMAIN="$name"
                print_info "Found existing certificate lineage: $SSL_CERT_DOMAIN"
                return 0
            fi
        done
    fi

    # Ask once, here. The answer decides both the certbot request and the
    # nginx ssl_certificate paths. Unattended (--config) runs use the exact
    # domain unless the public website needs the wildcard (handled above).
    if [ "$PRECONFIG_MODE" != "true" ]; then
        echo ""
        echo -e "  ${WHITE}Certificate Scope Configuration${NC}"
        echo -e "  ${GRAY}We can request a wildcard certificate for ${WHITE}*.${root_domain}${GRAY}${NC}"
        echo -e "  ${GRAY}This allows hosting other services (like www.${root_domain}) without new certificates.${NC}"
        echo ""
        if confirm_prompt "Do you control the DNS for ${root_domain}?" "y"; then
            SSL_CERT_DOMAIN="$root_domain"
            print_success "Will request wildcard certificate for *.${root_domain}"
        else
            print_info "Using single-domain certificate for ${N8N_DOMAIN}"
        fi
    fi

    print_info "SSL certificate domain set to: $SSL_CERT_DOMAIN"
    return 0
}

# valid / expired / unknown for the certificate of lineage $1 in the
# letsencrypt volume ("unknown" when openssl could not be run on it).
ssl_lineage_validity() {
    local rc=0
    $DOCKER_SUDO docker run --rm $DOCKER_APPARMOR_OPT \
        -v letsencrypt:/etc/letsencrypt:ro --entrypoint openssl "$OPENSSL_IMAGE" \
        x509 -checkend 0 -noout -in "/etc/letsencrypt/live/${1}/fullchain.pem" >/dev/null 2>&1 || rc=$?
    case "$rc" in
        0) echo valid ;;
        1) echo expired ;;   # openssl -checkend: the certificate has expired
        *) echo unknown ;;   # docker/image problem: keep the old behaviour
    esac
}

# True if a lineage named $1 (exact name or wildcard parent) covers N8N_DOMAIN.
ssl_cert_name_covers_domain() {
    local name="$1"
    [ -n "$name" ] || return 1
    [ "$name" = "$N8N_DOMAIN" ] && return 0
    case "$N8N_DOMAIN" in
        *".${name}") return 0 ;;
    esac
    return 1
}

# certbot -d arguments for the lineage chosen by determine_ssl_cert_domain
ssl_cert_domains_arg() {
    # The public website (www./files.<root>) always needs the wildcard, even
    # when n8n itself runs on the apex domain.
    if [ "$SSL_CERT_DOMAIN" = "$N8N_DOMAIN" ] && [ "$INSTALL_PUBLIC_WEBSITE" != "true" ]; then
        echo "-d $N8N_DOMAIN"
    else
        echo "-d $SSL_CERT_DOMAIN -d *.$SSL_CERT_DOMAIN"
    fi
}

check_existing_ssl_certificate() {
    # Check if valid SSL certificate already exists in the letsencrypt volume
    # Returns 0 if valid certificate exists, 1 otherwise
    # Sets CERT_INFO variable with certificate details

    local domain="$1"

    # Check if letsencrypt volume exists
    if ! $DOCKER_SUDO docker volume inspect letsencrypt >/dev/null 2>&1; then
        print_info "No existing letsencrypt volume found"
        return 1
    fi

    # Check if certificate files exist and get info
    CERT_INFO=$($DOCKER_SUDO docker run --rm $DOCKER_APPARMOR_OPT \
        -v letsencrypt:/etc/letsencrypt:ro \
        "$OPENSSL_IMAGE" \
        sh -c "
            CERT_PATH=\"/etc/letsencrypt/live/${domain}/fullchain.pem\"
            KEY_PATH=\"/etc/letsencrypt/live/${domain}/privkey.pem\"

            if [ ! -f \"\$CERT_PATH\" ] || [ ! -f \"\$KEY_PATH\" ]; then
                echo 'NOT_FOUND'
                exit 1
            fi

            # Get certificate info
            SUBJECT=\$(openssl x509 -in \"\$CERT_PATH\" -noout -subject 2>/dev/null | sed 's/subject=//')
            ISSUER=\$(openssl x509 -in \"\$CERT_PATH\" -noout -issuer 2>/dev/null | sed 's/issuer=//' | sed 's/.*CN = //')
            NOT_BEFORE=\$(openssl x509 -in \"\$CERT_PATH\" -noout -startdate 2>/dev/null | sed 's/notBefore=//')
            NOT_AFTER=\$(openssl x509 -in \"\$CERT_PATH\" -noout -enddate 2>/dev/null | sed 's/notAfter=//')
            DAYS_LEFT=\$(openssl x509 -in \"\$CERT_PATH\" -noout -checkend 0 >/dev/null 2>&1 && \
                         echo \$(( (\$(date -d \"\$NOT_AFTER\" +%s) - \$(date +%s)) / 86400 )) || echo '0')

            # Check if expired
            if [ \"\$DAYS_LEFT\" -le 0 ]; then
                echo 'EXPIRED'
                exit 1
            fi

            echo \"VALID|\$SUBJECT|\$ISSUER|\$NOT_BEFORE|\$NOT_AFTER|\$DAYS_LEFT\"
        " 2>/dev/null)

    if [ -z "$CERT_INFO" ] || [ "$CERT_INFO" = "NOT_FOUND" ] || [ "$CERT_INFO" = "EXPIRED" ]; then
        return 1
    fi

    return 0
}

display_certificate_info() {
    # Parse and display certificate information
    local info="$CERT_INFO"

    local status=$(echo "$info" | cut -d'|' -f1)
    local subject=$(echo "$info" | cut -d'|' -f2)
    local issuer=$(echo "$info" | cut -d'|' -f3)
    local not_before=$(echo "$info" | cut -d'|' -f4)
    local not_after=$(echo "$info" | cut -d'|' -f5)
    local days_left=$(echo "$info" | cut -d'|' -f6)

    echo ""
    echo -e "  ${WHITE}${BOLD}Existing SSL Certificate Found:${NC}"
    echo -e "  ============================================="
    echo -e "  Domain(s):     ${CYAN}${N8N_DOMAIN}${NC}"
    echo -e "  Issuer:        ${CYAN}${issuer}${NC}"
    echo -e "  Issued:        ${GRAY}${not_before}${NC}"
    echo -e "  Expires:       ${GRAY}${not_after}${NC}"

    # Color code days left
    if [ "$days_left" -gt 60 ]; then
        echo -e "  Days Left:     ${GREEN}${days_left} days${NC}"
    elif [ "$days_left" -gt 30 ]; then
        echo -e "  Days Left:     ${YELLOW}${days_left} days${NC}"
    else
        echo -e "  Days Left:     ${RED}${days_left} days${NC}"
    fi
    echo -e "  ============================================="
    echo ""
}

obtain_ssl_certificate() {
    local cred_mount=""
    local cred_volume_opt=""
    local force_renew="${FORCE_SSL_RENEWAL:-false}"

    # The lineage name was chosen (and nginx.conf written for it) by
    # determine_ssl_cert_domain; never pick a different one here.
    if [ -z "${SSL_CERT_DOMAIN:-}" ] || ! ssl_cert_name_covers_domain "$SSL_CERT_DOMAIN"; then
        determine_ssl_cert_domain
    fi
    local domains_arg
    domains_arg=$(ssl_cert_domains_arg)
    if [ "$SSL_CERT_DOMAIN" != "$N8N_DOMAIN" ]; then
        print_info "Certificate: wildcard ${SSL_CERT_DOMAIN} + *.${SSL_CERT_DOMAIN} (cert-name ${SSL_CERT_DOMAIN})"
    fi

    # Check for existing valid certificate first (use SSL_CERT_DOMAIN which may be root domain for wildcards)
    local renewal_opt=""
    if check_existing_ssl_certificate "$SSL_CERT_DOMAIN"; then
        display_certificate_info
        # Reaching certonly below means a new certificate was explicitly requested
        renewal_opt="--force-renewal"

        # Check if force renewal via env var
        if [ "$force_renew" = "true" ]; then
            print_info "FORCE_SSL_RENEWAL=true - obtaining new certificate"
        else
            print_success "Your SSL certificate is still valid!"
            echo ""

            # Interactive prompt (skip if non-interactive)
            if [ -t 0 ] && [ "$NON_INTERACTIVE" != "true" ]; then
                echo -e "  ${GRAY}Would you like to request a new certificate anyway?${NC}"
                echo -e "  ${GRAY}(This is usually not necessary unless you need to add domains)${NC}"
                echo ""
                echo -ne "  ${WHITE}Force renewal? [y/N]${NC}: "
                read -r renew_choice

                if [ "$renew_choice" != "y" ] && [ "$renew_choice" != "Y" ]; then
                    print_info "Keeping existing certificate"
                    return 0
                fi

                # Rate limit warning
                echo ""
                echo -e "  ${RED}${BOLD}=== Rate Limit Warning ===${NC}"
                echo -e "  ${YELLOW}Let's Encrypt has strict rate limits:${NC}"
                echo -e "    ${GRAY}- 5 certificates per domain per week${NC}"
                echo -e "    ${GRAY}- 5 failed validations per hour${NC}"
                echo -e "    ${GRAY}- Exceeding limits may block certificate issuance for days${NC}"
                echo ""
                echo -ne "  ${WHITE}Are you sure? Type 'yes' to confirm${NC}: "
                read -r confirm

                if [ "$confirm" != "yes" ]; then
                    print_info "Keeping existing certificate"
                    return 0
                fi
            else
                print_info "Non-interactive mode - keeping existing certificate"
                return 0
            fi
        fi
    fi

    case $DNS_PROVIDER_NAME in
        cloudflare|digitalocean)
            cred_volume_opt="-v $(pwd)/${DNS_CREDENTIALS_FILE}:/credentials.ini:ro"
            ;;
        route53)
            cred_volume_opt="-v $(pwd)/${DNS_CREDENTIALS_FILE}:/root/.aws/credentials:ro"
            ;;
        google)
            cred_volume_opt="-v $(pwd)/${DNS_CREDENTIALS_FILE}:/credentials.json:ro"
            ;;
    esac

    local certbot_flags=""
    case $DNS_PROVIDER_NAME in
        cloudflare)
            certbot_flags="--dns-cloudflare --dns-cloudflare-credentials /credentials.ini --dns-cloudflare-propagation-seconds 60"
            ;;
        digitalocean)
            certbot_flags="--dns-digitalocean --dns-digitalocean-credentials /credentials.ini --dns-digitalocean-propagation-seconds 60"
            ;;
        route53)
            certbot_flags="--dns-route53"
            ;;
        google)
            certbot_flags="--dns-google --dns-google-credentials /credentials.json --dns-google-propagation-seconds 120"
            ;;
    esac

    # Manual DNS: certbot prints the TXT record and waits for the user, so it
    # must run interactively. Such certificates can never renew automatically.
    local interactive_opt="--non-interactive"
    local tty_opt=""
    if [ "$DNS_PROVIDER_NAME" = "manual" ]; then
        if [ ! -t 0 ] || [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
            print_error "Manual DNS validation needs an interactive terminal (TXT records must be added by hand)"
            print_info "Re-run ./setup.sh from a terminal, or choose a supported DNS provider for automatic renewal"
            exit 1
        fi
        certbot_flags="--manual --preferred-challenges dns"
        interactive_opt=""
        tty_opt="-it"
        print_warning "Manual DNS validation: certbot will now ask you to create TXT record(s)."
        print_warning "This certificate will NOT renew automatically - repeat this before it expires (90 days)."
    fi

    # Issue directly into the letsencrypt volume (the same external volume the
    # certbot service uses) so certbot's live/ -> archive/ symlinks stay intact.
    # Copying with `cp -rL` (the old approach) broke the lineage and certbot
    # then silently refused to ever renew it.
    ensure_dns_credentials_file
    $DOCKER_SUDO docker volume create letsencrypt >/dev/null 2>&1 || true

    # A lineage broken by an older install (live/*.pem copied as regular files)
    # would make certbot create "<name>-0001" instead of updating <name>, which
    # nginx does not use. Move it aside (kept in lineage-repair-backup/) first.
    local lineage_backup=""
    if [ "$($DOCKER_SUDO docker run --rm $DOCKER_APPARMOR_OPT -v letsencrypt:/etc/letsencrypt:ro "$ALPINE_IMAGE" \
            sh -c "f=/etc/letsencrypt/live/${SSL_CERT_DOMAIN}/cert.pem; [ -e \$f ] && [ ! -L \$f ] && echo broken" 2>/dev/null)" = "broken" ]; then
        lineage_backup="/etc/letsencrypt/lineage-repair-backup/${SSL_CERT_DOMAIN}-$(date +%Y%m%d%H%M%S)"
        print_warning "Existing certificate lineage for ${SSL_CERT_DOMAIN} is broken (not renewable) - replacing it"
        $DOCKER_SUDO docker run --rm $DOCKER_APPARMOR_OPT -v letsencrypt:/etc/letsencrypt "$ALPINE_IMAGE" sh -c "
            n='${SSL_CERT_DOMAIN}'; b='${lineage_backup}'; mkdir -p \"\$b\"
            cp -a /etc/letsencrypt/live/\$n \"\$b/live\" && rm -rf /etc/letsencrypt/live/\$n
            [ -e /etc/letsencrypt/archive/\$n ] && mv /etc/letsencrypt/archive/\$n \"\$b/archive\"
            [ -e /etc/letsencrypt/renewal/\$n.conf ] && mv /etc/letsencrypt/renewal/\$n.conf \"\$b/renewal.conf\"
            true"
        renewal_opt=""
    fi

    if ! $DOCKER_SUDO docker run --rm $tty_opt $DOCKER_APPARMOR_OPT \
        -v letsencrypt:/etc/letsencrypt \
        $cred_volume_opt \
        $DNS_CERTBOT_IMAGE \
        certonly \
        $certbot_flags \
        $domains_arg \
        --cert-name "$SSL_CERT_DOMAIN" \
        $renewal_opt \
        --agree-tos \
        $interactive_opt \
        --email "$LETSENCRYPT_EMAIL"; then
        print_error "Failed to obtain SSL certificate"
        if [ -n "$lineage_backup" ]; then
            print_info "Restoring the previous certificate files so nginx keeps working"
            $DOCKER_SUDO docker run --rm $DOCKER_APPARMOR_OPT -v letsencrypt:/etc/letsencrypt "$ALPINE_IMAGE" sh -c "
                n='${SSL_CERT_DOMAIN}'; b='${lineage_backup}'
                rm -rf /etc/letsencrypt/live/\$n /etc/letsencrypt/archive/\$n /etc/letsencrypt/renewal/\$n.conf
                [ -e \"\$b/live\" ] && cp -a \"\$b/live\" /etc/letsencrypt/live/\$n
                [ -e \"\$b/archive\" ] && cp -a \"\$b/archive\" /etc/letsencrypt/archive/\$n
                [ -e \"\$b/renewal.conf\" ] && cp -a \"\$b/renewal.conf\" /etc/letsencrypt/renewal/\$n.conf
                true"
        fi
        exit 1
    fi

    print_success "SSL certificate obtained and stored in the letsencrypt volume"
}

# Before nginx starts: the lineage nginx.conf points at must exist, otherwise
# nginx restart-loops. Regenerates the nginx configs if they were written for
# a different cert name (e.g. an older nginx.conf on disk).
verify_ssl_cert_lineage_for_nginx() {
    local live="/etc/letsencrypt/live/${SSL_CERT_DOMAIN}"
    if [ "$($DOCKER_SUDO docker run --rm $DOCKER_APPARMOR_OPT -v letsencrypt:/etc/letsencrypt:ro "$ALPINE_IMAGE" \
            sh -c "[ -s ${live}/fullchain.pem ] && [ -s ${live}/privkey.pem ] && echo ok" 2>/dev/null)" != "ok" ]; then
        print_error "Certificate files not found at ${live}/ in the letsencrypt volume"
        print_info "nginx would fail to start. Re-run ./setup.sh after fixing certificate issuance."
        exit 1
    fi
    # With the public website, nginx_router terminates TLS; otherwise n8n_nginx
    local tls_conf="${SCRIPT_DIR}/nginx.conf"
    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        tls_conf="${SCRIPT_DIR}/nginx-router.conf"
    fi
    if ! grep -q "ssl_certificate ${live}/fullchain.pem;" "$tls_conf" 2>/dev/null; then
        print_warning "$(basename "$tls_conf") does not reference ${live}/ - regenerating nginx configuration"
        generate_nginx_conf_v3
        generate_public_nginx_conf
        generate_nginx_router_conf
    fi
    print_success "nginx certificate paths match lineage ${SSL_CERT_DOMAIN}"
}

# After deployment: make sure certificates can actually be renewed.
# Detects broken lineages (live/*.pem not symlinks, left by older installs),
# offers to repair them, then runs `certbot renew --dry-run` in the running
# certbot container and reports the result.
check_certificate_renewal() {
    local certbot_container="${CERTBOT_CONTAINER:-$DEFAULT_CERTBOT_CONTAINER}"
    local repair_script="${SCRIPT_DIR}/scripts/repair_ssl_lineage.sh"

    print_info "Checking automatic certificate renewal..."

    if ! $DOCKER_SUDO docker ps --format '{{.Names}}' | grep -q "^${certbot_container}$"; then
        print_warning "Certbot container ${certbot_container} is not running - certificates will NOT auto-renew"
        print_info "Check: docker logs ${certbot_container}"
        return 1
    fi

    local broken
    broken=$($DOCKER_SUDO docker exec "$certbot_container" sh -c \
        'for f in /etc/letsencrypt/live/*/cert.pem /etc/letsencrypt/live/*/privkey.pem /etc/letsencrypt/live/*/fullchain.pem; do [ -e "$f" ] && [ ! -L "$f" ] && echo "$f"; done; true' 2>/dev/null || true)
    if [ -n "$broken" ]; then
        print_warning "Broken certificate lineage detected (live files are not symlinks):"
        echo "$broken" | sed 's/^/    /'
        print_info "certbot will never renew these certificates until the lineage is repaired."
        if [ -x "$repair_script" ] && confirm_prompt "Repair the certificate lineage now (non-destructive, backup kept)?" "y"; then
            if $DOCKER_SUDO "$repair_script"; then
                print_success "Certificate lineage repaired and renewal verified"
                return 0
            fi
            print_error "Automatic repair failed - see docs/CERTBOT.md (Repairing a broken lineage)"
            return 1
        fi
        print_warning "Repair later with: ./scripts/repair_ssl_lineage.sh"
        return 1
    fi

    if [ "$DNS_PROVIDER_NAME" = "manual" ]; then
        print_warning "Manual DNS provider: automatic renewal is not possible."
        print_info "Re-run ./setup.sh before the certificate expires to issue a new one."
        return 0
    fi

    echo -e "  ${GRAY}Running certbot renew --dry-run (staging server, may take a few minutes for DNS propagation)...${NC}"
    local dry_run_output="" attempt
    for attempt in 1 2 3; do
        if dry_run_output=$($DOCKER_SUDO docker exec "$certbot_container" certbot renew --dry-run --no-random-sleep-on-renew 2>&1); then
            print_success "Renewal dry-run succeeded - certificates will renew automatically"
            return 0
        fi
        # The renewal loop may be running its start-up `certbot renew` right now
        echo "$dry_run_output" | grep -q "Another instance of Certbot" || break
        sleep 15
    done

    print_error "Renewal dry-run FAILED - certificates will NOT renew automatically until this is fixed"
    echo "$dry_run_output" | tail -n 15 | sed 's/^/    /'
    print_info "Check the DNS credentials file (${DNS_CREDENTIALS_FILE}) and docs/CERTBOT.md"
    print_info "Re-test with: docker exec ${certbot_container} certbot renew --dry-run"
    return 1
}

verify_services_v3() {
    local all_healthy=true

    # Check containers
    for container in $POSTGRES_CONTAINER $N8N_CONTAINER $NGINX_CONTAINER $DEFAULT_MANAGEMENT_CONTAINER; do
        if $DOCKER_SUDO docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            print_success "Container $container is running"
        else
            print_error "Container $container is not running"
            all_healthy=false
        fi
    done

    # Check n8n
    if curl -sf "http://localhost:5678/healthz" > /dev/null 2>&1 || \
       $DOCKER_SUDO docker exec $N8N_CONTAINER wget -q -O - http://localhost:5678/healthz >/dev/null 2>&1; then
        print_success "n8n is responding"
    else
        print_warning "n8n may still be starting"
    fi

    # Check management
    if curl -sf "http://localhost:8000/api/health" > /dev/null 2>&1; then
        print_success "Management API is responding"
    else
        print_warning "Management API may still be starting"
    fi
}

show_final_summary_v3() {
    print_header "Setup Complete!"

    echo -e "  ${GREEN}Your n8n v3.0 instance is now running!${NC}"
    echo ""
    echo -e "  ${WHITE}${BOLD}Access URLs:${NC}"
    echo -e "    n8n:                 ${CYAN}https://${N8N_DOMAIN}${NC}"
    echo -e "    Management Console:  ${CYAN}https://${N8N_DOMAIN}/management/${NC}"
    if [ "$INSTALL_PORTAINER" = true ]; then
        echo -e "    Portainer:           ${CYAN}https://${N8N_DOMAIN}/portainer/${NC}"
    elif [ "$INSTALL_PORTAINER_AGENT" = true ]; then
        echo -e "    Portainer Agent:     ${CYAN}${PORTAINER_AGENT_BIND:-127.0.0.1}:9001${NC}"
        echo -e "                         ${GRAY}start your Portainer server with AGENT_SECRET=<PORTAINER_AGENT_SECRET from .env>${NC}"
    fi
    if [ "$INSTALL_ADMINER" = true ]; then
        echo -e "    Adminer (DB):        ${CYAN}https://${N8N_DOMAIN}/adminer/${NC}"
    fi
    if [ "$INSTALL_DOZZLE" = true ]; then
        echo -e "    Dozzle (Logs):       ${CYAN}https://${N8N_DOMAIN}/dozzle/${NC}"
    fi
    if [ "$INSTALL_NTFY" = true ]; then
        echo -e "    NTFY (Push):         ${CYAN}${NTFY_PUBLIC_URL:-https://ntfy.${N8N_DOMAIN}}${NC}"
        echo -e "                         ${GRAY}login: NTFY_ADMIN_USER / NTFY_ADMIN_PASS in .env (anonymous access denied)${NC}"
        echo -e "                         ${GRAY}(Configure in Cloudflare Tunnel)${NC}"
    fi
    if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        echo -e "    Public Website:      ${CYAN}https://${PUBLIC_WEBSITE_DOMAIN:-www.${N8N_DOMAIN#*.}}${NC}"
    fi
    echo ""
    echo -e "  ${WHITE}${BOLD}Management Login:${NC}"
    echo -e "    Username:            ${CYAN}${ADMIN_USER}${NC}"
    if [ "$AUTOGEN_ADMIN_PASS" = "true" ]; then
        echo -e "    Password:            ${CYAN}${ADMIN_PASS}${NC} ${YELLOW}(auto-generated)${NC}"
    else
        echo -e "    Password:            ${GRAY}[as configured]${NC}"
    fi
    echo ""

    # Show auto-generated credentials section if any were generated
    if [ "$AUTOGEN_DB_PASSWORD" = "true" ] || [ "$AUTOGEN_ENCRYPTION_KEY" = "true" ] || [ "$AUTOGEN_MGMT_SECRET" = "true" ]; then
        echo -e "  ${WHITE}${BOLD}Auto-Generated Credentials:${NC} ${YELLOW}(save these securely!)${NC}"
        if [ "$AUTOGEN_DB_PASSWORD" = "true" ]; then
            echo -e "    PostgreSQL Password: ${CYAN}${DB_PASSWORD}${NC}"
        fi
        if [ "$AUTOGEN_ENCRYPTION_KEY" = "true" ]; then
            echo -e "    n8n Encryption Key:  ${CYAN}${N8N_ENCRYPTION_KEY}${NC}"
        fi
        if [ "$AUTOGEN_MGMT_SECRET" = "true" ]; then
            echo -e "    Management Secret:   ${CYAN}${MGMT_SECRET_KEY}${NC}"
        fi
        echo ""
        echo -e "  ${YELLOW}⚠ These credentials are stored in .env - keep this file secure!${NC}"
        echo ""
    fi

    if [ "$INSTALL_ADMINER" = true ]; then
        echo -e "  ${WHITE}${BOLD}Database Credentials (for Adminer):${NC}"
        echo -e "    Server:              ${CYAN}postgres${NC}"
        echo -e "    Username:            ${CYAN}${DB_USER}${NC}"
        echo -e "    Password:            ${CYAN}${DB_PASSWORD}${NC}"
        echo -e "    Database:            ${CYAN}${DB_NAME}${NC}"
        echo ""
    fi

    # Show optional services info
    if [ "$INSTALL_CLOUDFLARE_TUNNEL" = true ] || [ "$INSTALL_TAILSCALE" = true ]; then
        echo -e "  ${WHITE}${BOLD}Network Access:${NC}"
        if [ "$INSTALL_CLOUDFLARE_TUNNEL" = true ]; then
            echo -e "    Cloudflare Tunnel:   ${GREEN}Active${NC}"
        fi
        if [ "$INSTALL_TAILSCALE" = true ]; then
            echo -e "    Tailscale:           ${GREEN}Active${NC} (${TAILSCALE_HOSTNAME})"
        fi
        echo ""
    fi

    # Tailscale route approval warning
    if [ "$INSTALL_TAILSCALE" = true ] && [ -n "$TAILSCALE_ROUTES" ]; then
        echo -e "  ${YELLOW}${BOLD}⚠ TAILSCALE ACTION REQUIRED:${NC}"
        echo -e "    ${WHITE}You must approve the advertised route in Tailscale admin:${NC}"
        echo ""
        echo -e "    1. Visit: ${CYAN}https://login.tailscale.com/admin/machines${NC}"
        echo -e "    2. Find your ${WHITE}${TAILSCALE_HOSTNAME:-n8n-tailscale}${NC} node"
        echo -e "    3. Click the node and approve the advertised route: ${YELLOW}${TAILSCALE_ROUTES}${NC}"
        echo ""
        echo -e "    ${RED}${BOLD}NOTE:${NC} ${WHITE}For the n8n editor and management console over Tailscale, use${NC}"
        echo -e "          ${CYAN}https://${TAILSCALE_HOSTNAME:-n8n-tailscale}.<your-tailnet>.ts.net${NC} ${WHITE}(Tailscale Serve).${NC}"
        echo -e "          ${WHITE}Connections to the host IP through the advertised route reach nginx${NC}"
        echo -e "          ${WHITE}via Docker's port proxy and are treated as external.${NC}"
        echo ""
    fi

    # Cloudflare Tunnel public website hostname reminder
    if [ "$INSTALL_CLOUDFLARE_TUNNEL" = true ] && [ "$INSTALL_PUBLIC_WEBSITE" = "true" ]; then
        local root_domain=$(echo "$N8N_DOMAIN" | awk -F. '{if (NF>2) {print $(NF-1)"."$NF} else {print $0}}')
        local public_domain="${PUBLIC_WEBSITE_DOMAIN:-www.${root_domain}}"

        echo -e "  ${YELLOW}${BOLD}⚠ CLOUDFLARE ACTION REQUIRED:${NC}"
        echo -e "    ${WHITE}You must add TWO Public Hostnames in Zero Trust:${NC}"
        echo ""
        echo -e "    1. Visit: ${CYAN}https://one.dash.cloudflare.com${NC}"
        echo -e "    2. Go to: Networks → Tunnels → [Your Tunnel] → Configure → Public Hostname"
        echo ""
        echo -e "    ${WHITE}Hostname 1 (n8n webhooks/forms only):${NC}"
        echo -e "      Hostname: ${CYAN}${N8N_DOMAIN}${NC}"
        echo -e "      Service:  ${WHITE}HTTP${NC} -> ${WHITE}${NGINX_CONTAINER:-n8n_nginx}:8080${NC}"
        echo ""
        echo -e "    ${WHITE}Hostname 2 (Public Website):${NC}"
        echo -e "      Hostname: ${CYAN}${public_domain}${NC}"
        echo -e "      Service:  ${WHITE}HTTP${NC} -> ${WHITE}nginx_public:80${NC}"
        echo ""
        echo -e "    ${GRAY}Note: Both use HTTP internally. SSL is terminated by Cloudflare.${NC}"
        echo -e "    ${GRAY}Port 8080 only serves webhooks/forms; the editor, management console${NC}"
        echo -e "    ${GRAY}and admin tools are never reachable through the tunnel.${NC}"
        echo ""
    elif [ "$INSTALL_CLOUDFLARE_TUNNEL" = true ]; then
        echo -e "  ${YELLOW}${BOLD}⚠ CLOUDFLARE ACTION REQUIRED:${NC}"
        echo -e "    ${WHITE}Add a Public Hostname in Zero Trust (Networks → Tunnels → Configure):${NC}"
        echo -e "      Hostname: ${CYAN}${N8N_DOMAIN}${NC}"
        echo -e "      Service:  ${WHITE}HTTP${NC} -> ${WHITE}${NGINX_CONTAINER:-n8n_nginx}:8080${NC}"
        echo -e "    ${GRAY}Port 8080 only serves webhooks/forms; the editor, management console${NC}"
        echo -e "    ${GRAY}and admin tools are never reachable through the tunnel.${NC}"
        echo ""
    fi

    echo -e "  ${WHITE}${BOLD}Useful Commands:${NC}"
    echo -e "    ${GRAY}View logs:${NC}         docker compose logs -f"
    echo -e "    ${GRAY}Stop services:${NC}     docker compose down"
    echo -e "    ${GRAY}Start services:${NC}    docker compose up -d"
    echo -e "    ${GRAY}Health check:${NC}      ./scripts/health_check.sh"
    echo ""
    echo -e "  ${WHITE}${BOLD}New in v3.0:${NC}"
    echo -e "    • Backup scheduling and management"
    echo -e "    • Container monitoring and control"
    echo -e "    • Multi-channel notifications"
    echo -e "    • System health monitoring"
    echo ""
    echo -e "  ${GRAY}───────────────────────────────────────────────────────────────────────────────${NC}"
    echo ""
    echo -e "  ${WHITE}Thank you for using n8n Setup Script v${SCRIPT_VERSION}${NC}"
    echo ""
}

# =============================================================================
# ACCESS CONTROL CONFIGURATION
# =============================================================================

configure_access_control() {
    # Only configure if Cloudflare Tunnel is being used
    if [ "$INSTALL_CLOUDFLARE_TUNNEL" != "true" ]; then
        print_info "No Cloudflare Tunnel configured - skipping access control setup"
        print_info "Default internal IP ranges will be used (Docker network traffic is always external)"
        return
    fi

    print_section "Access Control Configuration"

    echo ""
    echo -e "  ${GRAY}Since you're using Cloudflare Tunnel, your n8n instance will be${NC}"
    echo -e "  ${GRAY}accessible from the public internet. Access control helps protect${NC}"
    echo -e "  ${GRAY}sensitive endpoints from unauthorized access.${NC}"
    echo ""
    echo -e "  ${WHITE}${BOLD}How Access Control Works:${NC}"
    echo -e "    - ${CYAN}Public Access${NC} (via Cloudflare Tunnel -> ${NGINX_CONTAINER:-n8n_nginx}:8080):"
    echo -e "      Only these endpoints are accessible:"
    echo -e "        - ${GREEN}/webhook/${NC}, ${GREEN}/webhook-test/${NC}, ${GREEN}/webhook-waiting/${NC} - n8n webhooks"
    echo -e "        - ${GREEN}/form/${NC}, ${GREEN}/form-test/${NC}, ${GREEN}/form-waiting/${NC} - n8n forms"
    echo -e "        - ${GREEN}/ntfy/${NC} - Push notification service"
    echo ""
    echo -e "    - ${CYAN}Internal Access${NC} (Tailscale, VPN, Local Network):"
    echo -e "      Full access to all endpoints including:"
    echo -e "        - ${GREEN}/${NC} - n8n main interface"
    echo -e "        - ${GREEN}/management/${NC} - Management console"
    echo -e "        - ${GREEN}/adminer/${NC} - Database admin (if installed)"
    echo -e "        - ${GREEN}/dozzle/${NC} - Log viewer (if installed)"
    echo ""

    # Default internal IP ranges
    INTERNAL_IP_RANGES="$DEFAULT_INTERNAL_IP_RANGES"
    CUSTOM_INTERNAL_IPS=""

    # Ask about Tailscale
    compute_docker_network_addrs
    if [ "$INSTALL_TAILSCALE" = "true" ]; then
        echo -e "  ${GREEN}[OK]${NC} Tailscale detected - tailnet users (via Tailscale Serve, ${TAILSCALE_IP}) will have full access"
        echo ""
    fi

    # Show default ranges
    echo -e "  ${WHITE}${BOLD}Default Internal IP Ranges:${NC}"
    echo -e "    ${CYAN}100.64.0.0/10${NC}  - Tailscale CGNAT range"
    echo -e "    ${CYAN}172.16.0.0/12${NC}  - Private network (Class B)"
    echo -e "    ${CYAN}10.0.0.0/8${NC}     - Private network (Class A)"
    echo -e "    ${CYAN}192.168.0.0/16${NC} - Private network (Class C)"
    echo ""
    echo -e "  ${WHITE}${BOLD}Always External:${NC}"
    echo -e "    ${CYAN}${N8N_NETWORK_SUBNET}${NC} - Docker network n8n_network (Cloudflare Tunnel,"
    echo -e "      docker-proxy/IPv6, other containers). More specific, so it wins over the"
    echo -e "      private ranges above. Change with N8N_NETWORK_SUBNET."
    echo ""

    # Ask about custom IP ranges
    if confirm_prompt "  Would you like to add additional IP ranges?" "n"; then
        echo ""
        echo -e "  ${GRAY}Enter IP ranges in CIDR notation (e.g., 203.0.113.0/24)${NC}"
        echo -e "  ${GRAY}Enter 'done' when finished${NC}"
        echo ""

        while true; do
            read -p "  Enter IP range (or 'done'): " ip_range

            if [ "$ip_range" = "done" ] || [ -z "$ip_range" ]; then
                break
            fi

            # Validate CIDR notation
            if [[ "$ip_range" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ ]] && ! ipv4_cidr_parse "$ip_range"; then
                echo -e "    ${RED}[ERROR]${NC} Invalid IPv4 range: $ip_range"
            elif [[ "$ip_range" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ ]] && range_inside_docker_subnet "$ip_range"; then
                # geo is longest-prefix match: a range inside the Docker
                # network would make proxied traffic (e.g. cloudflared at
                # ${CLOUDFLARED_IP}) internal again.
                echo -e "    ${RED}[ERROR]${NC} $ip_range overlaps the Docker network ${N8N_NETWORK_SUBNET},"
                echo -e "      ${GRAY}which must stay external (Cloudflare Tunnel and other containers).${NC}"
            elif [[ "$ip_range" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ ]]; then
                CUSTOM_INTERNAL_IPS="$CUSTOM_INTERNAL_IPS $ip_range"
                echo -e "    ${GREEN}[OK]${NC} Added: $ip_range"
            else
                echo -e "    ${RED}[ERROR]${NC} Invalid CIDR format: $ip_range"
                echo -e "      ${GRAY}Example: 192.168.1.0/24${NC}"
            fi
        done
    fi

    # Show summary
    echo ""
    echo -e "  ${WHITE}${BOLD}Access Control Summary:${NC}"
    echo -e "    ${CYAN}Internal IP Ranges:${NC}"
    for range in $INTERNAL_IP_RANGES $CUSTOM_INTERNAL_IPS; do
        echo -e "      - $range"
    done
    echo ""

    print_success "Access control configured"
}

update_access_control() {
    # Function for --update-access flag
    print_section "Update Access Control"

    echo ""
    echo -e "  ${GRAY}This will update the nginx access control configuration${NC}"
    echo -e "  ${GRAY}without reinstalling other services.${NC}"
    echo ""

    # Load existing state if available (in-progress install), otherwise the
    # saved configuration of a completed install. All optional-service flags
    # are needed: nginx.conf is regenerated as a whole, not just the geo block.
    if [ -f "$STATE_FILE" ]; then
        load_state
    elif [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE" 2>/dev/null || true
        restore_optional_services_from_config
    else
        print_error "No existing configuration found. Please run setup.sh first."
        exit 1
    fi

    if [ -z "$N8N_DOMAIN" ]; then
        print_error "Domain not configured. Please run setup.sh first."
        exit 1
    fi

    echo -e "  ${WHITE}Current Domain:${NC} ${CYAN}$N8N_DOMAIN${NC}"
    echo ""

    # Show current configuration
    echo -e "  ${WHITE}${BOLD}Current Internal IP Ranges:${NC}"
    for range in $INTERNAL_IP_RANGES $CUSTOM_INTERNAL_IPS; do
        echo -e "    ${CYAN}$range${NC}"
    done
    echo ""

    if confirm_prompt "  Would you like to reconfigure access control?" "y"; then
        # Reset and reconfigure
        INTERNAL_IP_RANGES="$DEFAULT_INTERNAL_IP_RANGES"
        CUSTOM_INTERNAL_IPS=""

        configure_access_control

        # Regenerate nginx.conf
        print_info "Regenerating nginx configuration..."
        determine_ssl_cert_domain
        generate_nginx_conf_v3
        generate_public_nginx_conf
        generate_nginx_router_conf

        if ! grep -q 'ipam:' "${SCRIPT_DIR}/docker-compose.yaml" 2>/dev/null || n8n_network_needs_recreate; then
            print_warning "SECURITY: docker-compose.yaml / the running network do not use the pinned subnet ${N8N_NETWORK_SUBNET}."
            print_warning "Until fixed, proxied traffic may still be treated as internal. Run ./setup.sh,"
            print_warning "choose 'Regenerate all config files', then: docker compose down && docker compose up -d"
        fi

        # Reload nginx if running
        local nginx_container="${NGINX_CONTAINER:-n8n_nginx}"
        if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${nginx_container}$"; then
            print_info "Reloading nginx..."
            if docker exec "${nginx_container}" nginx -s reload 2>/dev/null; then
                print_success "Nginx reloaded successfully"
            else
                print_warning "Could not reload nginx. You may need to restart it manually."
            fi
        else
            print_info "Nginx container not running. Configuration will apply on next start."
        fi

        print_success "Access control updated successfully!"
    else
        print_info "No changes made."
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND LINE ARGUMENTS
# ═══════════════════════════════════════════════════════════════════════════════

show_help() {
    echo "n8n Setup Script v${SCRIPT_VERSION}"
    echo ""
    echo "Usage: ./setup.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help              Show this help message"
    echo "  --config <file>     Use pre-configuration file for unattended install"
    echo "  --rollback          Rollback to v2.0 (if migrated within 30 days)"
    echo "  --update-access     Update access control settings (IP whitelist)"
    echo "  --version           Show version information"
    echo ""
    echo "Pre-configuration:"
    echo "  Copy setup-config.example to setup-config, edit values, then run:"
    echo "    ./setup.sh --config setup-config"
    echo ""
}

handle_rollback() {
    if [ ! -f "$MIGRATION_STATE_FILE" ]; then
        print_error "No migration state found. Nothing to rollback."
        exit 1
    fi

    print_warning "This will rollback your installation to v2.0"
    if confirm_prompt "Are you sure you want to rollback?"; then
        if ! ensure_docker_access; then
            print_error "Docker is not reachable; cannot roll back."
            exit 1
        fi
        rollback_to_v2 || exit 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SCRIPT
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    # Initialize preconfig mode flag
    PRECONFIG_MODE=false
    PRECONFIG_AUTO_CONFIRM=false
    PRECONFIG_SKIP_DEPLOY=false

    # Handle command line arguments
    case "${1:-}" in
        --help|-h)
            show_help
            exit 0
            ;;
        --rollback)
            handle_rollback
            exit 0
            ;;
        --update-access)
            update_access_control
            exit 0
            ;;
        --version|-v)
            echo "n8n Setup Script v${SCRIPT_VERSION}"
            exit 0
            ;;
        --config)
            if [ -z "${2:-}" ]; then
                print_error "Usage: ./setup.sh --config <config-file>"
                echo ""
                echo "  Example: ./setup.sh --config setup-config"
                echo ""
                echo "  See setup-config.example for configuration options."
                exit 1
            fi
            load_preconfig "$2"
            ;;
    esac

    clear

    print_header "n8n HTTPS Interactive Setup v${SCRIPT_VERSION}"

    # If preconfig mode with auto-confirm, skip all interactive prompts
    if [ "$PRECONFIG_MODE" = "true" ] && [ "$PRECONFIG_AUTO_CONFIRM" = "true" ]; then
        print_info "Running in non-interactive mode (AUTO_CONFIRM=true)"
        # Set install mode to fresh for preconfig
        INSTALL_MODE="fresh"
        # Re-running on an existing install: back up and reuse its secrets.
        # configure_database / generate_encryption_key refuse to regenerate
        # secrets for existing data unless FORCE_REGENERATE_SECRETS=true.
        if [ -f "${SCRIPT_DIR}/.env" ] || [ "$(detect_current_version)" != "none" ]; then
            print_warning "Existing installation detected - existing secrets and data volumes will be kept"
            backup_existing_config
        fi
    else
        # Check for existing installation FIRST - before showing feature list
        local detected_version=$(detect_current_version)
        if [ "$detected_version" = "3.0" ]; then
            # Existing v3.0 installation - show prominent banner immediately
            handle_version_detection
            # If we get here, user chose reconfigure or fresh - skip the "Ready to begin?" prompt
        else
            # Fresh install or upgrade - show normal welcome screen
            echo -e "  ${GRAY}This script will set up a production-ready n8n instance with:${NC}"
            echo -e "    • Automated SSL certificates via Let's Encrypt (DNS-01)"
            echo -e "    • PostgreSQL 16 with pgvector for AI workflows"
            echo -e "    • Nginx reverse proxy with security headers"
            echo -e "    • ${GREEN}NEW:${NC} Management console for backups and monitoring"
            echo ""
            echo -e "  ${GRAY}Optional services available:${NC}"
            echo -e "    • Cloudflare Tunnel - Secure access without exposing ports"
            echo -e "    • Tailscale - Private mesh VPN network access"
            echo -e "    • NTFY - Self-hosted push notification server"
            echo -e "    • Public Website Hosting - Static website with File Browser"
            echo -e "    • Adminer - Web-based database management"
            echo -e "    • Dozzle - Real-time container log viewer"
            echo -e "    • Portainer / Portainer Agent - Container management UI"
            echo ""

            if ! confirm_prompt "Ready to begin?"; then
                exit 0
            fi

            # Handle v2.0 upgrade or fresh install
            handle_version_detection
        fi
    fi

    # Skip all preliminary checks for reconfigure mode - user already has a working installation
    if [ "$INSTALL_MODE" != "reconfigure" ]; then
        # Check if running in LXC container and show warning
        if is_lxc_container; then
            echo ""
            echo -e "  ${RED}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
            echo -e "  ${RED}║${NC}                          ${WHITE}${BOLD}LXC CONTAINER DETECTED${NC}                           ${RED}║${NC}"
            echo -e "  ${RED}╠═══════════════════════════════════════════════════════════════════════════╣${NC}"
            echo -e "  ${RED}║${NC}                                                                           ${RED}║${NC}"
            echo -e "  ${RED}║${NC}  ${YELLOW}IMPORTANT:${NC} Docker inside LXC requires special Proxmox configuration.     ${RED}║${NC}"
            echo -e "  ${RED}║${NC}                                                                           ${RED}║${NC}"
            echo -e "  ${RED}║${NC}  On your ${WHITE}Proxmox host${NC}, add this line to the container config:             ${RED}║${NC}"
            echo -e "  ${RED}║${NC}                                                                           ${RED}║${NC}"
            echo -e "  ${RED}║${NC}      ${CYAN}/etc/pve/lxc/<CTID>.conf${NC}                                             ${RED}║${NC}"
            echo -e "  ${RED}║${NC}                                                                           ${RED}║${NC}"
            echo -e "  ${RED}║${NC}      ${WHITE}lxc.apparmor.profile: unconfined${NC}                                     ${RED}║${NC}"
            echo -e "  ${RED}║${NC}                                                                           ${RED}║${NC}"
            echo -e "  ${RED}║${NC}  Then restart this container from Proxmox before continuing.              ${RED}║${NC}"
            echo -e "  ${RED}║${NC}                                                                           ${RED}║${NC}"
            echo -e "  ${RED}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
            echo ""
            if ! confirm_prompt "Have you added this configuration and restarted the container?"; then
                echo ""
                print_info "Please configure Proxmox and restart the container, then run this script again."
                exit 0
            fi
        fi

        # Check for resume
        if check_resume; then
            print_info "Resuming from saved state..."
        fi

        # Detect OS and prepare system
        print_section "System Preparation"
        detect_os
        if [ -n "$DISTRO" ]; then
            print_success "Detected OS: $DISTRO ($DISTRO_FAMILY)"
        else
            print_info "Detected package manager: $PKG_MANAGER"
        fi

        # Ask user if they want to update the system
        if confirm_prompt "Update system packages before continuing?"; then
            update_system
        fi

        # Install required utilities
        install_required_utilities

        # Docker check
        check_and_install_docker

        # System requirements check
        perform_system_checks
    fi

    # Note: Version detection already happened at the top of main()

    if [ "$INSTALL_MODE" = "upgrade" ]; then
        # Load existing config
        if [ -f "$CONFIG_FILE" ]; then
            source "$CONFIG_FILE" 2>/dev/null || true
            # Restore settings from config (variable name mapping)
            restore_dns_settings_from_provider
            restore_optional_services_from_config
        fi
        run_migration_v2_to_v3
    elif [ "$INSTALL_MODE" = "reconfigure" ]; then
        # ═══════════════════════════════════════════════════════════════════════
        # MANDATORY BACKUP - DO THIS FIRST BEFORE ANYTHING ELSE
        # ═══════════════════════════════════════════════════════════════════════
        backup_existing_config

        # Load existing config
        if [ -f "$CONFIG_FILE" ]; then
            source "$CONFIG_FILE" 2>/dev/null || true
            # Restore settings from config (variable name mapping)
            restore_dns_settings_from_provider
            restore_optional_services_from_config
            print_success "Loaded existing configuration"
        fi

        # Show reconfigure menu
        print_section "Reconfigure Options"
        echo -e "  ${WHITE}Select what you want to reconfigure:${NC}"
        echo ""
        echo -e "    ${CYAN}1)${NC} Domain & SSL settings"
        echo -e "    ${CYAN}2)${NC} Database credentials"
        echo -e "    ${CYAN}3)${NC} Optional services (Cloudflare, Tailscale, NTFY, etc.)"
        echo -e "    ${CYAN}4)${NC} Access control (IP ranges)"
        echo -e "    ${CYAN}5)${NC} Admin credentials"
        echo -e "    ${CYAN}6)${NC} NFS backup storage"
        echo -e "    ${CYAN}7)${NC} Regenerate all config files (keeps settings)"
        echo -e "    ${CYAN}8)${NC} Full reconfiguration (all settings)"
        echo -e "    ${CYAN}9)${NC} ${YELLOW}Rollback to previous configuration${NC}"
        echo -e "    ${CYAN}0)${NC} Exit"
        echo ""

        local reconfig_choice=""
        while [[ ! "$reconfig_choice" =~ ^[0-9]$ ]]; do
            echo -ne "${WHITE}  Enter your choice [0-9]${NC}: "
            read reconfig_choice
        done

        case $reconfig_choice in
            1)
                configure_dns_provider
                configure_url
                ;;
            2)
                configure_database
                ;;
            3)
                configure_optional_services
                ;;
            4)
                configure_access_control
                ;;
            5)
                create_admin_user
                ;;
            6)
                configure_nfs
                ;;
            7)
                print_info "Regenerating configuration files with current settings..."
                ;;
            8)
                # Full reconfigure - fall through to fresh install flow
                INSTALL_MODE="fresh"
                ;;
            9)
                # Rollback to previous configuration
                rollback_config
                exit 0
                ;;
            0)
                print_info "Exiting without changes"
                exit 0
                ;;
        esac

        # For options 1-7, regenerate config files and optionally redeploy
        if [ "$INSTALL_MODE" = "reconfigure" ]; then
            print_section "Generating Configuration Files"
            generate_env_file
            generate_tool_auth_files
            generate_docker_compose_v3
            determine_ssl_cert_domain
            generate_nginx_conf_v3
            generate_public_nginx_conf
            generate_nginx_router_conf
            save_setup_config

            print_success "Configuration files regenerated!"
            echo ""

            if confirm_prompt "Would you like to redeploy the stack now?"; then
                deploy_stack
            else
                if n8n_network_needs_recreate; then
                    # Docker cannot change an existing network's subnet; a
                    # plain "up -d" would fail or keep the old network.
                    print_info "Configuration saved. When ready, recreate the stack network (data volumes are kept):"
                    print_info "  docker compose down && docker compose up -d"
                else
                    print_info "Configuration saved. Run 'docker compose up -d' when ready."
                fi
            fi
            exit 0
        fi
    fi

    if [ "$INSTALL_MODE" = "fresh" ]; then
        # Fresh install
        # Each step saves state so user can resume if interrupted

        # Step 1: DNS Provider
        if [ "$CURRENT_STEP" -lt 1 ]; then
            configure_dns_provider
            save_state "DNS Provider" 1
        fi

        # Step 2: URL/Domain
        if [ "$CURRENT_STEP" -lt 2 ]; then
            configure_url
            save_state "Domain Configuration" 2
        fi

        # Step 3: Database
        if [ "$CURRENT_STEP" -lt 3 ]; then
            configure_database
            save_state "Database Configuration" 3
        fi

        # Step 4: Container Names
        if [ "$CURRENT_STEP" -lt 4 ]; then
            configure_containers
            save_state "Container Names" 4
        fi

        # Step 5: Email
        if [ "$CURRENT_STEP" -lt 5 ]; then
            configure_email
            save_state "Email Configuration" 5
        fi

        # Step 6: Timezone
        if [ "$CURRENT_STEP" -lt 6 ]; then
            configure_timezone
            save_state "Timezone" 6
        fi

        # Step 7: Encryption Key
        if [ "$CURRENT_STEP" -lt 7 ]; then
            generate_encryption_key
            save_state "Encryption Key" 7
        fi

        # Step 8: Management Port
        if [ "$CURRENT_STEP" -lt 8 ]; then
            configure_management_port
            save_state "Management Port" 8
        fi

        # Step 9: NFS
        if [ "$CURRENT_STEP" -lt 9 ]; then
            configure_nfs
            save_state "NFS Storage" 9
        fi

        # Step 10: Notifications
        if [ "$CURRENT_STEP" -lt 10 ]; then
            configure_notifications
            save_state "Notifications" 10
        fi

        # Step 11: Admin User
        if [ "$CURRENT_STEP" -lt 11 ]; then
            create_admin_user
            save_state "Admin User" 11
        fi

        # Step 12: Optional Services (Portainer, Cloudflare Tunnel, Tailscale, Adminer, Dozzle)
        if [ "$CURRENT_STEP" -lt 12 ]; then
            configure_optional_services
            save_state "Optional Services" 12
        fi

        # Summary and confirmation
        if ! show_configuration_summary; then
            # User wants to reconfigure - restart from NFS
            CURRENT_STEP=9
            configure_nfs
            save_state "NFS Storage" 9
            configure_notifications
            save_state "Notifications" 10
            create_admin_user
            save_state "Admin User" 11
            configure_optional_services
            save_state "Optional Services" 12

            # Show summary again
            if ! show_configuration_summary; then
                print_error "Configuration cancelled"
                exit 1
            fi
        fi

        # Generate files
        print_section "Generating Configuration Files"
        generate_env_file
        generate_tool_auth_files
        generate_docker_compose_v3
        # Determine SSL certificate domain BEFORE generating nginx.conf
        # This is critical for wildcard certificates
        determine_ssl_cert_domain
        generate_nginx_conf_v3
        generate_public_nginx_conf
        generate_nginx_router_conf
        create_letsencrypt_volume

        save_setup_config

        print_success "Configuration files generated!"

        # Deploy
        if confirm_prompt "Would you like to deploy the stack now?"; then
            deploy_stack
        else
            echo ""
            print_info "Configuration saved. Run 'docker compose up -d' when ready."
        fi
    fi

    clear_state
}

main "$@"
