#!/bin/bash

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                                                                           ║
# ║     n8n HTTPS Interactive Setup Script with Let's Encrypt + DNS           ║
# ║                                                                           ║
# ║     Automated SSL certificate setup and deployment for n8n                ║
# ║     with PostgreSQL, Nginx reverse proxy, and auto-renewal                ║
# ║                                                                           ║
# ║     Version 3.0.0                                                         ║
# ║     Richard J. Sears                                                      ║
# ║     richardjsears@gmail.com                                               ║
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
INSTALL_NTFY=false
NTFY_BASE_URL=""
NTFY_PUBLIC_URL=""
NTFY_INTERNAL_URL=""

# Internal IP ranges that get full access (space-separated CIDR blocks)
DEFAULT_INTERNAL_IP_RANGES="100.64.0.0/10 172.16.0.0/12 10.0.0.0/8 192.168.0.0/16"
INTERNAL_IP_RANGES="${INTERNAL_IP_RANGES:-$DEFAULT_INTERNAL_IP_RANGES}"
CUSTOM_INTERNAL_IPS=""

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

    echo -ne "${WHITE}  $prompt [$default]${NC}: "
    read value

    if [ -z "$value" ]; then
        eval "$var_name='$default'"
    else
        eval "$var_name='$value'"
    fi
}

confirm_prompt() {
    local prompt="$1"
    local default="${2:-y}"

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

# Install required utilities (curl, git, openssl, jq)
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
            print_info "Please install manually: curl git openssl jq"
            return 1
            ;;
    esac

    # Verify installation
    local failed=""
    command_exists curl || failed="$failed curl"
    command_exists git || failed="$failed git"
    command_exists openssl || failed="$failed openssl"
    command_exists jq || failed="$failed jq"

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
SAVED_TAILSCALE_HOST_IP="$TAILSCALE_HOST_IP"
SAVED_INSTALL_ADMINER="$INSTALL_ADMINER"
SAVED_ADMINER_PORT="$ADMINER_PORT"
SAVED_INSTALL_DOZZLE="$INSTALL_DOZZLE"
SAVED_DOZZLE_PORT="$DOZZLE_PORT"
SAVED_INSTALL_NTFY="$INSTALL_NTFY"
SAVED_NTFY_BASE_URL="$NTFY_BASE_URL"
SAVED_NTFY_PUBLIC_URL="$NTFY_PUBLIC_URL"
SAVED_NTFY_INTERNAL_URL="$NTFY_INTERNAL_URL"

# Access Control
SAVED_INTERNAL_IP_RANGES="$INTERNAL_IP_RANGES"
SAVED_CUSTOM_INTERNAL_IPS="$CUSTOM_INTERNAL_IPS"
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
        TAILSCALE_HOST_IP="${SAVED_TAILSCALE_HOST_IP:-}"
        INSTALL_ADMINER="${SAVED_INSTALL_ADMINER:-false}"
        ADMINER_PORT="${SAVED_ADMINER_PORT:-}"
        INSTALL_DOZZLE="${SAVED_INSTALL_DOZZLE:-false}"
        DOZZLE_PORT="${SAVED_DOZZLE_PORT:-}"
        INSTALL_NTFY="${SAVED_INSTALL_NTFY:-false}"
        NTFY_BASE_URL="${SAVED_NTFY_BASE_URL:-}"
        NTFY_PUBLIC_URL="${SAVED_NTFY_PUBLIC_URL:-}"
        NTFY_INTERNAL_URL="${SAVED_NTFY_INTERNAL_URL:-}"

        # Access Control
        INTERNAL_IP_RANGES="${SAVED_INTERNAL_IP_RANGES:-$DEFAULT_INTERNAL_IP_RANGES}"
        CUSTOM_INTERNAL_IPS="${SAVED_CUSTOM_INTERNAL_IPS:-}"

        CURRENT_STEP="${SAVED_STEP_NUM:-0}"
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
                DNS_CERTBOT_IMAGE="certbot/dns-cloudflare:latest"
                DNS_CREDENTIALS_FILE="cloudflare.ini"
                ;;
            route53)
                DNS_CERTBOT_IMAGE="certbot/dns-route53:latest"
                DNS_CREDENTIALS_FILE="route53.ini"
                ;;
            google)
                DNS_CERTBOT_IMAGE="certbot/dns-google:latest"
                DNS_CREDENTIALS_FILE="google.json"
                ;;
            digitalocean)
                DNS_CERTBOT_IMAGE="certbot/dns-digitalocean:latest"
                DNS_CREDENTIALS_FILE="digitalocean.ini"
                ;;
            manual|*)
                DNS_CERTBOT_IMAGE="certbot/certbot:latest"
                DNS_CREDENTIALS_FILE="credentials.ini"
                ;;
        esac
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
        if $DOCKER_SUDO docker run --rm \
            -v letsencrypt:/source:ro \
            -v "${backup_dir}/letsencrypt:/backup" \
            alpine sh -c "cp -rL /source/* /backup/ 2>/dev/null || true" 2>/dev/null; then
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
        $DOCKER_SUDO docker run --rm -v letsencrypt:/source:ro -v "${safety_backup}/letsencrypt:/backup" \
            alpine sh -c "cp -rL /source/* /backup/ 2>/dev/null || true" 2>/dev/null
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
        if $DOCKER_SUDO docker run --rm \
            -v "${backup_dir}/letsencrypt:/source:ro" \
            -v letsencrypt:/dest \
            alpine sh -c "rm -rf /dest/* && cp -rL /source/* /dest/" 2>/dev/null; then
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

configure_nfs() {
    print_section "NFS Backup Storage Configuration"

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

            # Create local mount point
            print_info "Creating local mount point: $nfs_local_mount"
            mkdir -p "$nfs_local_mount"

            # Check if already in fstab
            if grep -q "${nfs_server}:${nfs_path}" /etc/fstab 2>/dev/null; then
                print_warning "NFS entry already exists in /etc/fstab, updating..."
                # Remove old entry
                run_privileged sed -i "\|${nfs_server}:${nfs_path}|d" /etc/fstab
            fi

            # Add to fstab
            print_info "Adding NFS mount to /etc/fstab..."
            echo "${nfs_server}:${nfs_path} ${nfs_local_mount} nfs defaults,_netdev 0 0" | run_privileged tee -a /etc/fstab > /dev/null

            # Mount the NFS share
            print_info "Mounting NFS share..."
            if mount "$nfs_local_mount" 2>/dev/null; then
                print_success "NFS share mounted at $nfs_local_mount"
            else
                # Try with explicit options
                if mount -t nfs -o rw,nolock,soft "${nfs_server}:${nfs_path}" "$nfs_local_mount" 2>/dev/null; then
                    print_success "NFS share mounted at $nfs_local_mount"
                else
                    print_error "Failed to mount NFS share. Check /etc/fstab and try 'mount -a'"
                fi
            fi

            # Verify mount is writable
            if touch "${nfs_local_mount}/.n8n_test_write" 2>/dev/null; then
                rm -f "${nfs_local_mount}/.n8n_test_write"
                print_success "NFS share is writable"
            else
                print_warning "NFS share may not be writable - check permissions on NFS server"
            fi

            NFS_SERVER="$nfs_server"
            NFS_PATH="$nfs_path"
            NFS_LOCAL_MOUNT="$nfs_local_mount"
            NFS_CONFIGURED="true"

            save_state "nfs" "complete"
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

run_migration_v2_to_v3() {
    print_header "Migration: v2.0 → v3.0"

    local docker_compose_cmd="docker compose"
    if [ "$USE_STANDALONE_COMPOSE" = true ]; then
        docker_compose_cmd="docker-compose"
    fi
    if [ -n "$DOCKER_SUDO" ]; then
        docker_compose_cmd="$DOCKER_SUDO $docker_compose_cmd"
    fi

    # Phase 1: Pre-migration backup
    print_section "Phase 1: Pre-Migration Backup"
    save_state "migration" "backup"

    print_info "Creating complete backup before migration..."

    # Backup docker-compose.yaml
    cp "${SCRIPT_DIR}/docker-compose.yaml" "${SCRIPT_DIR}/docker-compose.yaml.v2.backup"
    print_success "Backed up docker-compose.yaml"

    # Backup nginx.conf
    if [ -f "${SCRIPT_DIR}/nginx.conf" ]; then
        cp "${SCRIPT_DIR}/nginx.conf" "${SCRIPT_DIR}/nginx.conf.v2.backup"
        print_success "Backed up nginx.conf"
    fi

    # Backup PostgreSQL database
    print_info "Backing up PostgreSQL database..."
    mkdir -p "${SCRIPT_DIR}/backups"

    local backup_file="backups/n8n_pre_migration_$(date +%Y%m%d_%H%M%S).dump"
    if $DOCKER_SUDO docker exec $POSTGRES_CONTAINER pg_dump -U $DB_USER -d $DB_NAME -F c -f /tmp/n8n_pre_migration.dump 2>/dev/null; then
        $DOCKER_SUDO docker cp ${POSTGRES_CONTAINER}:/tmp/n8n_pre_migration.dump "${SCRIPT_DIR}/${backup_file}"
        print_success "Database backup saved to ${backup_file}"
    else
        print_warning "Could not backup database (container may not be running)"
    fi

    print_success "Pre-migration backup complete"

    # Phase 2: Stop services
    print_section "Phase 2: Stopping Services"
    save_state "migration" "stop_services"

    print_info "Stopping n8n services..."
    cd "$SCRIPT_DIR"
    $docker_compose_cmd stop n8n 2>/dev/null || true
    $docker_compose_cmd stop nginx 2>/dev/null || true
    print_success "Services stopped"

    # Phase 3: Database preparation
    print_section "Phase 3: Database Preparation"
    save_state "migration" "database"

    # Generate management database password
    if command_exists openssl; then
        MGMT_DB_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
    else
        MGMT_DB_PASSWORD=$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 32)
    fi

    print_info "Creating management database..."
    $DOCKER_SUDO docker exec $POSTGRES_CONTAINER psql -U $DB_USER -c "CREATE DATABASE ${DEFAULT_MGMT_DB_NAME};" 2>/dev/null || true
    print_success "Management database created"

    # Phase 4: Configure new features
    print_section "Phase 4: Configuring v3.0 Features"
    save_state "migration" "config"

    # Get existing config values
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE" 2>/dev/null || true
    fi

    # Configure management port
    configure_management_port

    # Configure NFS (optional)
    configure_nfs

    # Configure notifications (optional)
    configure_notifications

    # Create admin user
    create_admin_user

    # Generate .env file with all configuration values
    generate_env_file

    # Generate authentication files for tools (Portainer, Dozzle)
    generate_tool_auth_files

    # Generate new docker-compose.yaml with management services
    generate_docker_compose_v3

    # Update nginx.conf with management port
    generate_nginx_conf_v3

    # Phase 5: Build and start new services
    print_section "Phase 5: Starting v3.0 Services"
    save_state "migration" "start_services"

    print_info "Starting all services..."
    cd "$SCRIPT_DIR"
    $docker_compose_cmd up -d

    # Wait for services to be healthy
    wait_for_services

    # Phase 6: Verification
    print_section "Phase 6: Verification"
    save_state "migration" "verify"

    if verify_migration; then
        print_success "Migration completed successfully!"

        # Record migration for rollback window
        cat > "$MIGRATION_STATE_FILE" << EOF
{
    "migrated_at": "$(date -Iseconds)",
    "from_version": "2.0",
    "to_version": "3.0",
    "rollback_available_until": "$(date -d '+30 days' -Iseconds 2>/dev/null || date -v+30d -Iseconds 2>/dev/null || echo 'unknown')",
    "backup_files": [
        "docker-compose.yaml.v2.backup",
        "nginx.conf.v2.backup",
        "${backup_file}"
    ]
}
EOF

        echo ""
        print_info "Management interface: https://${N8N_DOMAIN}:${MGMT_PORT}"
        print_info "Rollback available for 30 days if needed"

        # Clear setup state
        clear_state
    else
        print_error "Migration verification failed!"
        if confirm_prompt "Rollback to v2.0?"; then
            rollback_to_v2
        fi
    fi
}

wait_for_services() {
    print_info "Waiting for services to be healthy..."

    local max_attempts=60
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        local all_healthy=true

        # Check PostgreSQL
        if ! $DOCKER_SUDO docker exec $POSTGRES_CONTAINER pg_isready -U $DB_USER >/dev/null 2>&1; then
            all_healthy=false
        fi

        # Check n8n
        if ! $DOCKER_SUDO docker exec $N8N_CONTAINER wget -q -O - http://localhost:5678/healthz >/dev/null 2>&1; then
            all_healthy=false
        fi

        if [ "$all_healthy" = true ]; then
            print_success "All services are healthy"
            return 0
        fi

        attempt=$((attempt + 1))
        sleep 2
        printf "\r  ${GRAY}Waiting for services... (%d/%d)${NC}" $attempt $max_attempts
    done

    echo ""
    print_warning "Some services may not be fully healthy yet"
    return 1
}

verify_migration() {
    local all_ok=true

    # Check all containers are running
    for container in $N8N_CONTAINER $POSTGRES_CONTAINER $NGINX_CONTAINER $DEFAULT_MANAGEMENT_CONTAINER; do
        if ! $DOCKER_SUDO docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            print_error "Container $container is not running"
            all_ok=false
        else
            print_success "Container $container is running"
        fi
    done

    # Check n8n is responding
    if curl -sf "http://localhost:5678/healthz" > /dev/null 2>&1; then
        print_success "n8n health check passed"
    else
        print_warning "n8n health check failed (may still be starting)"
    fi

    # Check management API is responding
    if curl -sf "http://localhost:${MGMT_PORT}/api/health" > /dev/null 2>&1; then
        print_success "Management API health check passed"
    else
        print_warning "Management API health check failed (may still be starting)"
    fi

    # Check PostgreSQL
    if $DOCKER_SUDO docker exec $POSTGRES_CONTAINER pg_isready -U $DB_USER > /dev/null 2>&1; then
        print_success "PostgreSQL health check passed"
    else
        print_error "PostgreSQL health check failed"
        all_ok=false
    fi

    $all_ok
}

rollback_to_v2() {
    print_header "Rolling Back to v2.0"

    local docker_compose_cmd="docker compose"
    if [ "$USE_STANDALONE_COMPOSE" = true ]; then
        docker_compose_cmd="docker-compose"
    fi
    if [ -n "$DOCKER_SUDO" ]; then
        docker_compose_cmd="$DOCKER_SUDO $docker_compose_cmd"
    fi

    print_info "Stopping v3.0 services..."
    cd "$SCRIPT_DIR"
    $docker_compose_cmd down 2>/dev/null || true

    print_info "Restoring v2.0 configuration..."
    if [ -f "${SCRIPT_DIR}/docker-compose.yaml.v2.backup" ]; then
        mv "${SCRIPT_DIR}/docker-compose.yaml.v2.backup" "${SCRIPT_DIR}/docker-compose.yaml"
        print_success "Restored docker-compose.yaml"
    fi

    if [ -f "${SCRIPT_DIR}/nginx.conf.v2.backup" ]; then
        mv "${SCRIPT_DIR}/nginx.conf.v2.backup" "${SCRIPT_DIR}/nginx.conf"
        print_success "Restored nginx.conf"
    fi

    print_info "Starting v2.0 services..."
    $docker_compose_cmd up -d

    print_success "Rollback complete. System restored to v2.0"

    # Clean up migration state
    rm -f "$MIGRATION_STATE_FILE"
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

generate_bcrypt_hash() {
    local password="$1"
    local hash=""

    # Try Python with bcrypt first
    if command_exists python3; then
        hash=$(python3 -c "
import sys
try:
    import bcrypt
    print(bcrypt.hashpw(sys.argv[1].encode(), bcrypt.gensalt()).decode())
except ImportError:
    try:
        from passlib.hash import bcrypt as passlib_bcrypt
        print(passlib_bcrypt.hash(sys.argv[1]))
    except ImportError:
        sys.exit(1)
" "$password" 2>/dev/null)
    fi

    # Fallback to htpasswd if available
    if [ -z "$hash" ] && command_exists htpasswd; then
        hash=$(htpasswd -nbB admin "$password" 2>/dev/null | cut -d: -f2)
    fi

    # Fallback to Docker if available
    if [ -z "$hash" ] && command_exists docker; then
        hash=$(docker run --rm httpd:2.4-alpine htpasswd -nbB admin "$password" 2>/dev/null | cut -d: -f2)
    fi

    echo "$hash"
}

generate_tool_auth_files() {
    print_info "Generating authentication files for tools..."

    # Generate bcrypt hash of admin password
    local bcrypt_hash
    bcrypt_hash=$(generate_bcrypt_hash "$ADMIN_PASS")

    if [ -z "$bcrypt_hash" ]; then
        print_warn "Could not generate bcrypt hash - tools will use default authentication"
        return 1
    fi

    # Save hash for Portainer (will be used in docker-compose)
    PORTAINER_ADMIN_HASH="$bcrypt_hash"

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
# GENERATE .env FILE
# ═══════════════════════════════════════════════════════════════════════════════

generate_env_file() {
    print_info "Generating .env file..."

    # Read existing .env file to preserve values not stored in config
    if [ -f "${SCRIPT_DIR}/.env" ]; then
        # Source existing .env to get values we might not have in memory
        # Use a subshell to avoid polluting current environment unexpectedly
        while IFS='=' read -r key value; do
            # Skip comments and empty lines
            [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
            # Remove any leading/trailing whitespace from key
            key=$(echo "$key" | xargs)
            # Only set if not already set in current environment
            if [ -z "${!key}" ] && [ -n "$value" ]; then
                export "$key=$value"
            fi
        done < "${SCRIPT_DIR}/.env"
    fi

    # Generate secrets if not already set
    if command_exists openssl; then
        MGMT_SECRET_KEY=${MGMT_SECRET_KEY:-$(openssl rand -base64 32)}
    else
        MGMT_SECRET_KEY=${MGMT_SECRET_KEY:-$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 32)}
    fi

    cat > "${SCRIPT_DIR}/.env" << EOF
# n8n Management System v3.0 - Environment Variables
# Generated by setup.sh on $(date)
# WARNING: This file contains sensitive credentials - do not commit to git!

# ===========================================
# Required Settings
# ===========================================

# Domain name (both variables for compatibility)
DOMAIN=${N8N_DOMAIN}
N8N_DOMAIN=${N8N_DOMAIN}

# PostgreSQL credentials
POSTGRES_USER=${DB_USER}
POSTGRES_PASSWORD=${DB_PASSWORD}
POSTGRES_DB=${DB_NAME}

# n8n encryption key
N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}

# Management console (uses same DB credentials as n8n)
MGMT_SECRET_KEY=${MGMT_SECRET_KEY}
MGMT_DB_USER=${DB_USER}
MGMT_DB_PASSWORD=${DB_PASSWORD}
MGMT_PORT=${MGMT_PORT:-3333}

# Admin credentials (for management console)
ADMIN_USER=${ADMIN_USER}
ADMIN_PASS=${ADMIN_PASS}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@localhost}

# Timezone
TIMEZONE=${N8N_TIMEZONE}

# ===========================================
# Optional: NFS Backup Storage
# ===========================================
NFS_SERVER=${NFS_SERVER:-}
NFS_PATH=${NFS_PATH:-}
NFS_LOCAL_MOUNT=${NFS_LOCAL_MOUNT:-}

# ===========================================
# Optional: Cloudflare Tunnel
# ===========================================
CLOUDFLARE_TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN:-}

# ===========================================
# Optional: Tailscale VPN
# ===========================================
TAILSCALE_AUTH_KEY=${TAILSCALE_AUTH_KEY:-}
TAILSCALE_HOST_IP=${TAILSCALE_HOST_IP:-}

# ===========================================
# Container Names (generally don't change)
# ===========================================
POSTGRES_CONTAINER=${POSTGRES_CONTAINER}
N8N_CONTAINER=${N8N_CONTAINER}
NGINX_CONTAINER=${NGINX_CONTAINER}
CERTBOT_CONTAINER=${CERTBOT_CONTAINER}
MANAGEMENT_CONTAINER=${DEFAULT_MANAGEMENT_CONTAINER}
EOF

    # Secure the .env file
    chmod 600 "${SCRIPT_DIR}/.env"
    print_success ".env file generated"
}

# ═══════════════════════════════════════════════════════════════════════════════
# GENERATE v3.0 DOCKER COMPOSE
# ═══════════════════════════════════════════════════════════════════════════════

generate_docker_compose_v3() {
    print_info "Generating docker-compose.yaml for v3.0..."

    # Determine credential mount
    local cred_mount=""
    case $DNS_PROVIDER_NAME in
        cloudflare|digitalocean)
            cred_mount="./${DNS_CREDENTIALS_FILE}:/credentials.ini:ro"
            ;;
        route53)
            cred_mount="./${DNS_CREDENTIALS_FILE}:/root/.aws/credentials:ro"
            ;;
        google)
            cred_mount="./${DNS_CREDENTIALS_FILE}:/credentials.json:ro"
            ;;
        *)
            cred_mount="./${DNS_CREDENTIALS_FILE:-credentials.ini}:/credentials.ini:ro"
            ;;
    esac

    cat > "${SCRIPT_DIR}/docker-compose.yaml" << 'EOF'
services:
  # ===========================================================================
  # PostgreSQL Database
  # ===========================================================================
  postgres:
    image: pgvector/pgvector:pg16
    container_name: ${POSTGRES_CONTAINER:-n8n_postgres}
    restart: always
    environment:
      - POSTGRES_USER=${POSTGRES_USER:-n8n}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB:-n8n}
    volumes:
      - postgres_data:/var/lib/postgresql/data
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
    image: n8nio/n8n:latest
    container_name: ${N8N_CONTAINER:-n8n}
    restart: always
    environment:
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=${POSTGRES_DB:-n8n}
      - DB_POSTGRESDB_USER=${POSTGRES_USER:-n8n}
      - DB_POSTGRESDB_PASSWORD=${POSTGRES_PASSWORD}
      - N8N_HOST=${DOMAIN}
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=https://${DOMAIN}
      - N8N_EDITOR_BASE_URL=https://${DOMAIN}
      - GENERIC_TIMEZONE=${TIMEZONE:-America/Los_Angeles}
      - TZ=${TIMEZONE:-America/Los_Angeles}
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
      - N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
      - N8N_COMMUNITY_PACKAGES_ENABLED=true
      - N8N_TRUST_PROXY=true
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

  # ===========================================================================
  # Management Console (NEW in v3.0)
  # ===========================================================================
  n8n_management:
    build:
      context: ./management
      dockerfile: Dockerfile
    container_name: ${MANAGEMENT_CONTAINER:-n8n_management}
    restart: always
    environment:
      # Database
      - DATABASE_URL=postgresql+asyncpg://${MGMT_DB_USER:-n8n_mgmt}:${MGMT_DB_PASSWORD}@postgres:5432/n8n_management
      - N8N_DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-n8n}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-n8n}
      # PostgreSQL connection for backups (pg_dump)
      - POSTGRES_HOST=\${POSTGRES_CONTAINER:-n8n_postgres}
      - POSTGRES_USER=\${POSTGRES_USER:-n8n}
      - POSTGRES_PASSWORD=\${POSTGRES_PASSWORD}
      # Security
      - SECRET_KEY=${MGMT_SECRET_KEY}
      # Admin user (created on first startup)
      - ADMIN_USERNAME=${ADMIN_USER}
      - ADMIN_PASSWORD=${ADMIN_PASS}
      - ADMIN_EMAIL=${ADMIN_EMAIL:-admin@localhost}
      # Server
      - HOST=0.0.0.0
      - PORT=8000
      - DEBUG=false
      # NFS Configuration (host-level mount, bind-mounted into container)
      - NFS_SERVER=\${NFS_SERVER:-}
      - NFS_PATH=\${NFS_PATH:-}
      - NFS_LOCAL_MOUNT=\${NFS_LOCAL_MOUNT:-}
      # Timezone
      - TZ=${TIMEZONE:-America/Los_Angeles}
      # n8n API Integration (for creating test workflows)
      - N8N_API_KEY=${N8N_API_KEY:-}
      - N8N_EDITOR_BASE_URL=${N8N_EDITOR_BASE_URL:-}
EOF

    # Add notification environment variables if configured
    if [ "$NOTIFICATIONS_CONFIGURED" = "true" ]; then
        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
      # Notifications
      - NOTIF_TYPE=${NOTIF_TYPE:-}
      - NOTIF_CONFIG=${NOTIF_CONFIG:-}
EOF
        if [ -n "$EMAIL_HOST" ]; then
            cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
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
        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
      # NTFY Push Notifications
      - NTFY_BASE_URL=${NTFY_BASE_URL}
EOF
    fi

    cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - mgmt_backup_staging:/app/backups
      - mgmt_logs:/app/logs
      - mgmt_config:/app/config
      - ./.env:/app/host_env/.env:rw
EOF

    # Add NFS bind mount if configured (host-level NFS mount)
    if [ "$NFS_CONFIGURED" = "true" ] && [ -n "$NFS_LOCAL_MOUNT" ]; then
        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
      - ${NFS_LOCAL_MOUNT}:/mnt/backups
EOF
    fi

    cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
    expose:
      - "80"
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - n8n_network

  # ===========================================================================
  # Nginx Reverse Proxy
  # ===========================================================================
  nginx:
    image: nginx:alpine
    container_name: ${NGINX_CONTAINER:-n8n_nginx}
    restart: always
    ports:
      - "443:443"
EOF

    # Note: All services (Management, Adminer, Dozzle, Portainer) accessed via paths on port 443

    cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
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

  # ===========================================================================
  # Certbot SSL Certificate Manager
  # ===========================================================================
  certbot:
    image: ${DNS_CERTBOT_IMAGE:-certbot/certbot:latest}
    container_name: ${CERTBOT_CONTAINER}
    volumes:
      - letsencrypt:/etc/letsencrypt
      - certbot_data:/var/www/certbot
      - ${cred_mount}
      - /var/run/docker.sock:/var/run/docker.sock:ro
    entrypoint: /bin/sh -c "trap exit TERM; while :; do certbot renew ${DNS_CERTBOT_FLAGS:-} --deploy-hook 'docker exec ${NGINX_CONTAINER} nginx -s reload' || true; sleep 12h & wait \$\${!}; done;"
    networks:
      - n8n_network

EOF

    # Add full Portainer if configured
    if [ "$INSTALL_PORTAINER" = true ]; then
        # Build Portainer command with optional admin password
        local portainer_cmd="--base-url /portainer"
        if [ -n "$PORTAINER_ADMIN_HASH" ]; then
            # Escape $ as $$ for Docker Compose
            local escaped_hash="${PORTAINER_ADMIN_HASH//\$/\$\$}"
            portainer_cmd="$portainer_cmd --admin-password='${escaped_hash}'"
        fi

        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
  # ===========================================================================
  # Portainer - Container Management UI
  # ===========================================================================
  portainer:
    image: portainer/portainer-ce:latest
    container_name: n8n_portainer
    restart: always
    command: ${portainer_cmd}
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
        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << 'EOF'
  # ===========================================================================
  # Portainer Agent (for remote Portainer server)
  # ===========================================================================
  portainer_agent:
    image: portainer/agent:latest
    container_name: portainer_agent
    restart: always
    ports:
      - "9001:9001"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /var/lib/docker/volumes:/var/lib/docker/volumes
      - /:/host
    networks:
      - n8n_network

EOF
    fi

    # Add Cloudflare Tunnel if configured
    if [ "$INSTALL_CLOUDFLARE_TUNNEL" = true ]; then
        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << 'EOF'
  # ===========================================================================
  # Cloudflare Tunnel
  # ===========================================================================
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: n8n_cloudflared
    restart: always
    command: tunnel run
    environment:
      - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
    networks:
      - n8n_network

EOF
    fi

    # Add Tailscale if configured
    if [ "$INSTALL_TAILSCALE" = true ]; then
        # Generate tailscale-serve.json for Tailscale Serve
        generate_tailscale_serve_config

        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << 'EOF'
  # ===========================================================================
  # Tailscale VPN
  # ===========================================================================
  tailscale:
    image: tailscale/tailscale:latest
    container_name: n8n_tailscale
    restart: always
    hostname: n8n-tailscale
    environment:
      - TS_AUTHKEY=${TAILSCALE_AUTH_KEY}
      - TS_STATE_DIR=/var/lib/tailscale
      - TS_USERSPACE=true
      - TS_EXTRA_ARGS=--accept-routes
      - TS_ROUTES=${TAILSCALE_HOST_IP}/32
      - TS_AUTH_ONCE=true
      - TS_SERVE_CONFIG=/config/tailscale-serve.json
    volumes:
      - tailscale_data:/var/lib/tailscale
      - ./tailscale-serve.json:/config/tailscale-serve.json:ro
    cap_add:
      - NET_ADMIN
    networks:
      - n8n_network

EOF
    fi

    # Add Adminer if configured
    if [ "$INSTALL_ADMINER" = true ]; then
        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
  # ===========================================================================
  # Adminer - Database Management
  # ===========================================================================
  adminer:
    image: adminer:latest
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
        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
  # ===========================================================================
  # Dozzle - Container Log Viewer
  # ===========================================================================
  dozzle:
    image: amir20/dozzle:latest
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
        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
  # ===========================================================================
  # NTFY - Push Notification Server
  # Accessible via its own subdomain (configured in Cloudflare Tunnel)
  # ===========================================================================
  ntfy:
    image: binwiederhier/ntfy:latest
    container_name: n8n_ntfy
    restart: unless-stopped
    init: true
    command:
      - serve
    environment:
      - TZ=\${TIMEZONE:-America/Los_Angeles}
      # NTFY_BASE_URL: Public URL for NTFY (must match Cloudflare Tunnel hostname)
      - NTFY_BASE_URL=${NTFY_PUBLIC_URL}
      - NTFY_UPSTREAM_BASE_URL=https://ntfy.sh
      - NTFY_BEHIND_PROXY=true
      - NTFY_CACHE_FILE=/var/cache/ntfy/cache.db
      - NTFY_AUTH_FILE=/var/lib/ntfy/auth.db
      - NTFY_AUTH_DEFAULT_ACCESS=\${NTFY_AUTH_DEFAULT_ACCESS:-read-write}
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

    # Add volumes section
    cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
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
EOF

    # NFS is now mounted at host level and bind-mounted into container
    # No Docker NFS volume needed - using ${NFS_LOCAL_MOUNT}:/mnt/backups bind mount

    # Add Tailscale volume if configured
    if [ "$INSTALL_TAILSCALE" = true ]; then
        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
  tailscale_data:
    driver: local
EOF
    fi

    # Add Portainer volume if full Portainer is configured
    if [ "$INSTALL_PORTAINER" = true ]; then
        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
  portainer_data:
    driver: local
EOF
    fi

    # Add NTFY volumes if configured
    if [ "$INSTALL_NTFY" = true ]; then
        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
  ntfy_cache:
    driver: local
  ntfy_data:
    driver: local
EOF
    fi

    # Add networks section
    cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF

# ===========================================================================
# Networks
# ===========================================================================
networks:
  n8n_network:
    driver: bridge
EOF

    print_success "docker-compose.yaml generated for v3.0"
}

generate_nginx_conf_v3() {
    print_info "Generating nginx.conf for v3.0..."

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
        server ${N8N_CONTAINER}:5678;
    }

    # Upstream to management console (connects to internal nginx on port 80)
    upstream management {
        server ${DEFAULT_MANAGEMENT_CONTAINER}:80;
    }

    # ===========================================================================
    # IP-based Access Control
    # ===========================================================================
    # Classifies requests as "internal" (full access) or "external" (restricted)
    # Internal: Tailscale, Docker networks, private IP ranges
    # External: Cloudflare Tunnel, public internet
    geo \$access_level {
        default          "external";
EOF

    # Add internal IP ranges to geo block
    for range in $INTERNAL_IP_RANGES $CUSTOM_INTERNAL_IPS; do
        if [ -n "$range" ]; then
            cat >> "${SCRIPT_DIR}/nginx.conf" << EOF
        ${range}    "internal";
EOF
        fi
    done

    cat >> "${SCRIPT_DIR}/nginx.conf" << EOF
    }

    # ===========================================================================
    # ACCESS CONTROL SUMMARY:
    # ===========================================================================
    # EXTERNALLY ACCESSIBLE (public internet):
    #   - /webhook/     - n8n workflow webhooks
    #   - /ntfy/        - NTFY push notifications (if enabled)
    #
    # INTERNAL ACCESS ONLY (Tailscale, VPN, whitelisted IPs):
    #   - /             - n8n editor
    #   - /management/  - Management console
    #   - /portainer/   - Container management (if enabled)
    #   - /adminer/     - Database management (if enabled)
    #   - /dozzle/      - Log viewer (if enabled)
    # ===========================================================================

    # ===========================================================================
    # Main n8n HTTPS Server (Port 443)
    # ===========================================================================
    server {
        listen 443 ssl;
        http2 on;
        server_name ${N8N_DOMAIN};

        ssl_certificate /etc/letsencrypt/live/${N8N_DOMAIN}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${N8N_DOMAIN}/privkey.pem;

        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;

        # Webhook endpoint with CORS
        location /webhook/ {
            add_header 'Access-Control-Allow-Origin' '*' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'Content-Type, Authorization' always;
            add_header X-Frame-Options "SAMEORIGIN" always;

            if (\$request_method = 'OPTIONS') {
                add_header 'Access-Control-Allow-Origin' '*';
                add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
                add_header 'Access-Control-Allow-Headers' 'Content-Type, Authorization';
                add_header 'Access-Control-Max-Age' 86400;
                add_header 'Content-Length' 0;
                return 204;
            }

            proxy_pass http://n8n;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_buffering off;
        }

        # Default n8n proxy - INTERNAL ACCESS ONLY
        # n8n editor/UI should not be publicly accessible
        location / {
            # Block external access - only allow internal IPs
            if (\$access_level = "external") {
                return 403;
            }

            add_header X-Frame-Options "SAMEORIGIN" always;

            proxy_pass http://n8n;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_buffering off;
        }

        location /healthz {
            access_log off;
            return 200 "healthy\n";
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
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
        }

        location /portainer/api/websocket/ {
            proxy_pass http://n8n_portainer:9000/api/websocket/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
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
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
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
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
EOF
    fi

    # Note: NTFY is accessed via its own subdomain through Cloudflare Tunnel
    # No nginx location block is needed - Cloudflare Tunnel routes directly to n8n_ntfy:80
    if [ "$INSTALL_NTFY" = true ]; then
        cat >> "${SCRIPT_DIR}/nginx.conf" << 'EOF'

        # Note: NTFY is accessed via its own subdomain (e.g., ntfy.example.com)
        # Configure Cloudflare Tunnel to route the NTFY subdomain to n8n_ntfy:80
        # No proxy configuration needed here since Cloudflare Tunnel handles routing
EOF
    fi

    # Add Management Console location block
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
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
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
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
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
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_buffering off;
        }
    }
}
EOF

    print_success "nginx.conf generated for v3.0"
}

# ═══════════════════════════════════════════════════════════════════════════════
# DNS PROVIDER CONFIGURATION (from v2)
# ═══════════════════════════════════════════════════════════════════════════════

configure_dns_provider() {
    print_section "DNS Provider Configuration"

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
    DNS_CERTBOT_IMAGE="certbot/dns-cloudflare:latest"
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
    DNS_CERTBOT_IMAGE="certbot/dns-route53:latest"
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
    DNS_CERTBOT_IMAGE="certbot/dns-google:latest"
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
    DNS_CERTBOT_IMAGE="certbot/dns-digitalocean:latest"
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
    DNS_CERTBOT_IMAGE="certbot/certbot:latest"
    DNS_CREDENTIALS_FILE="credentials.ini"
    DNS_CERTBOT_FLAGS="--manual --preferred-challenges dns"

    print_warning "Manual DNS configuration selected"
    echo -e "  ${GRAY}You will need to configure certbot manually.${NC}"
}

# ═══════════════════════════════════════════════════════════════════════════════
# URL AND DATABASE CONFIGURATION (from v2)
# ═══════════════════════════════════════════════════════════════════════════════

configure_url() {
    print_section "Domain Configuration"

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
                ;;
            3)
                echo ""
                print_info "Please configure your DNS correctly and run this script again."
                exit 1
                ;;
        esac
    fi

    # Set derived URL values
    N8N_URL="https://${N8N_DOMAIN}"
    WEBHOOK_URL="https://${N8N_DOMAIN}"
    EDITOR_BASE_URL="https://${N8N_DOMAIN}"
}

configure_database() {
    print_section "PostgreSQL Database Configuration"

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
}

generate_encryption_key() {
    print_section "Encryption Key Configuration"

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
            print_success "Portainer Agent will be installed (connect to your existing Portainer server on port 9001)"
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
    echo -e "  ${WHITE}${BOLD}Monitoring:${NC}"
    echo -e "    ${CYAN}•${NC} Metrics Agent - Host-level system monitoring (CPU, memory, disk)"
    echo ""
    echo -e "  ${WHITE}${BOLD}Notifications:${NC}"
    echo -e "    ${CYAN}•${NC} NTFY - Self-hosted push notifications server"
    echo ""

    if confirm_prompt "Would you like to configure optional services?" "n"; then
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
        TAILSCALE_HOST_IP="$primary_ip"
        echo ""
        print_info "Docker host IP detected: ${TAILSCALE_HOST_IP}"
        print_info "This IP will be advertised via TS_ROUTES for Tailscale access"
    else
        print_warning "Could not detect host IP for TS_ROUTES"
        TAILSCALE_HOST_IP=""
    fi

    print_success "Tailscale configured"
    echo ""
    print_info "Your n8n instance will be accessible at: ${TAILSCALE_HOSTNAME}.your-tailnet.ts.net"
    echo ""
    echo -e "  ${YELLOW}IMPORTANT: After deployment, approve advertised routes:${NC}"
    echo -e "    1. Visit: ${CYAN}https://login.tailscale.com/admin/machines${NC}"
    echo -e "    2. Find your ${WHITE}${TAILSCALE_HOSTNAME:-n8n-tailscale}${NC} node"
    echo -e "    3. Click the node and approve the advertised route (${TAILSCALE_HOST_IP}/32)"
    echo ""
    echo -e "  ${GRAY}Once approved, access via Tailscale:${NC}"
    echo -e "    • n8n:        ${CYAN}https://${TAILSCALE_HOSTNAME:-n8n-tailscale}.your-tailnet.ts.net${NC}"
    echo -e "    • Management: ${CYAN}https://${TAILSCALE_HOST_IP}:3333${NC} (via route)"
    echo -e "    • SSH:        ${CYAN}ssh user@${TAILSCALE_HOST_IP}${NC} (via route)"
}

# Generate tailscale-serve.json for TS_SERVE_CONFIG
generate_tailscale_serve_config() {
    print_info "Generating tailscale-serve.json..."

    cat > "${SCRIPT_DIR}/tailscale-serve.json" << EOF
{
  "TCP": { "443": { "HTTPS": true } },
  "Web": {
    "\${TS_CERT_DOMAIN}:443": {
      "Handlers": {
        "/": { "Proxy": "https://${DOMAIN}:443" }
      }
    }
  }
}
EOF

    chmod 644 "${SCRIPT_DIR}/tailscale-serve.json"
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
    echo -e "  ${GRAY}You can choose to:${NC}"
    echo -e "    1. Install a self-hosted NTFY server (recommended)"
    echo -e "    2. Use the public ntfy.sh server"
    echo -e "    3. Connect to your own existing NTFY server"
    echo ""

    echo -ne "${WHITE}  Choose option [1/2/3, default: 1]${NC}: "
    read ntfy_choice
    ntfy_choice=${ntfy_choice:-1}

    case "$ntfy_choice" in
        1)
            INSTALL_NTFY=true
            # Internal URL for management console communication
            NTFY_INTERNAL_URL="http://n8n_ntfy:80"

            # Prompt for subdomain
            local default_ntfy_subdomain="ntfy.${N8N_DOMAIN}"
            echo ""
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
            ;;
        2)
            INSTALL_NTFY=false
            NTFY_BASE_URL="https://ntfy.sh"
            NTFY_PUBLIC_URL="https://ntfy.sh"
            print_success "Using public ntfy.sh server"
            print_warning "Note: Messages sent via ntfy.sh are public unless you use access tokens"
            ;;
        3)
            INSTALL_NTFY=false
            echo -ne "${WHITE}  Enter your NTFY server URL${NC}: "
            read custom_ntfy_url
            if [ -n "$custom_ntfy_url" ]; then
                NTFY_BASE_URL="$custom_ntfy_url"
                NTFY_PUBLIC_URL="$custom_ntfy_url"
                print_success "Using custom NTFY server: $NTFY_BASE_URL"
            else
                print_error "No URL provided, defaulting to self-hosted"
                INSTALL_NTFY=true
                NTFY_INTERNAL_URL="http://n8n_ntfy:80"
                NTFY_PUBLIC_URL="https://ntfy.${N8N_DOMAIN}"
                NTFY_BASE_URL="${NTFY_PUBLIC_URL}"
                create_ntfy_config
            fi
            ;;
        *)
            INSTALL_NTFY=true
            NTFY_INTERNAL_URL="http://n8n_ntfy:80"
            NTFY_PUBLIC_URL="https://ntfy.${N8N_DOMAIN}"
            NTFY_BASE_URL="${NTFY_PUBLIC_URL}"
            create_ntfy_config
            print_success "Self-hosted NTFY server will be installed"
            ;;
    esac
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

# Auth settings (managed via environment variables)
# auth-file: /var/lib/ntfy/auth.db
# auth-default-access: read-write

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
       [ "$INSTALL_NTFY" = true ] || [ -n "$NTFY_BASE_URL" ]; then
        echo -e "  ${WHITE}${BOLD}Optional Services:${NC}"
        if [ "$INSTALL_PORTAINER" = true ]; then
            echo -e "    Portainer:           ${GREEN}enabled${NC} (/portainer/)"
        elif [ "$INSTALL_PORTAINER_AGENT" = true ]; then
            echo -e "    Portainer Agent:     ${GREEN}enabled${NC} (port 9001)"
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

deploy_stack() {
    print_section "Deploying n8n Stack v3.0"

    local docker_compose_cmd="docker compose"
    if [ "$USE_STANDALONE_COMPOSE" = true ]; then
        docker_compose_cmd="docker-compose"
    fi
    if [ -n "$DOCKER_SUDO" ]; then
        docker_compose_cmd="$DOCKER_SUDO $docker_compose_cmd"
    fi

    # Start PostgreSQL
    print_step "1" "4" "Starting PostgreSQL database"
    cd "$SCRIPT_DIR"
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

    # Start all services
    print_step "3" "4" "Starting all services"
    $docker_compose_cmd up -d
    sleep 10
    print_success "All services started"

    # Verify
    print_step "4" "4" "Verifying services"
    verify_services_v3

    # Create backup of working configuration after successful deployment
    print_info "Creating backup of working configuration..."
    backup_existing_config

    show_final_summary_v3
}

# =============================================================================
# SSL CERTIFICATE MANAGEMENT
# =============================================================================

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
    CERT_INFO=$($DOCKER_SUDO docker run --rm \
        -v letsencrypt:/etc/letsencrypt:ro \
        alpine/openssl \
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

    # Check for existing valid certificate first
    if check_existing_ssl_certificate "$N8N_DOMAIN"; then
        display_certificate_info

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

    mkdir -p "${SCRIPT_DIR}/letsencrypt-temp"

    if ! $DOCKER_SUDO docker run --rm \
        -v "$(pwd)/letsencrypt-temp:/etc/letsencrypt" \
        $cred_volume_opt \
        $DNS_CERTBOT_IMAGE \
        certonly \
        $certbot_flags \
        -d "$N8N_DOMAIN" \
        --agree-tos \
        --non-interactive \
        --email "$LETSENCRYPT_EMAIL"; then
        print_error "Failed to obtain SSL certificate"
        exit 1
    fi

    print_success "SSL certificate obtained"

    # Copy to volume
    $DOCKER_SUDO docker run --rm \
        -v "$(pwd)/letsencrypt-temp:/source:ro" \
        -v letsencrypt:/dest \
        alpine \
        sh -c "cp -rL /source/* /dest/"

    rm -rf "${SCRIPT_DIR}/letsencrypt-temp"
    print_success "Certificates copied to Docker volume"
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
    fi
    if [ "$INSTALL_ADMINER" = true ]; then
        echo -e "    Adminer (DB):        ${CYAN}https://${N8N_DOMAIN}/adminer/${NC}"
    fi
    if [ "$INSTALL_DOZZLE" = true ]; then
        echo -e "    Dozzle (Logs):       ${CYAN}https://${N8N_DOMAIN}/dozzle/${NC}"
    fi
    if [ "$INSTALL_NTFY" = true ]; then
        echo -e "    NTFY (Push):         ${CYAN}${NTFY_PUBLIC_URL:-https://ntfy.${N8N_DOMAIN}}${NC}"
        echo -e "                         ${GRAY}(Configure in Cloudflare Tunnel)${NC}"
    fi
    echo ""
    echo -e "  ${WHITE}${BOLD}Management Login:${NC}"
    echo -e "    Username:            ${CYAN}${ADMIN_USER}${NC}"
    echo -e "    Password:            ${GRAY}[as configured]${NC}"
    echo ""
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
        print_info "All access will be treated as internal (full access)"
        return
    fi

    print_section "Access Control Configuration"

    echo ""
    echo -e "  ${GRAY}Since you're using Cloudflare Tunnel, your n8n instance will be${NC}"
    echo -e "  ${GRAY}accessible from the public internet. Access control helps protect${NC}"
    echo -e "  ${GRAY}sensitive endpoints from unauthorized access.${NC}"
    echo ""
    echo -e "  ${WHITE}${BOLD}How Access Control Works:${NC}"
    echo -e "    - ${CYAN}Public Access${NC} (via Cloudflare Tunnel):"
    echo -e "      Only these endpoints are accessible:"
    echo -e "        - ${GREEN}/webhook/${NC} - n8n workflow webhooks"
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
    if [ "$INSTALL_TAILSCALE" = "true" ]; then
        echo -e "  ${GREEN}[OK]${NC} Tailscale detected - Tailscale IPs (100.64.0.0/10) will have full access"
        echo ""
    fi

    # Show default ranges
    echo -e "  ${WHITE}${BOLD}Default Internal IP Ranges:${NC}"
    echo -e "    ${CYAN}100.64.0.0/10${NC}  - Tailscale CGNAT range"
    echo -e "    ${CYAN}172.16.0.0/12${NC}  - Docker/Internal networks"
    echo -e "    ${CYAN}10.0.0.0/8${NC}     - Private network (Class A)"
    echo -e "    ${CYAN}192.168.0.0/16${NC} - Private network (Class C)"
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
            if [[ "$ip_range" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ ]]; then
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

    # Load existing state if available
    if [ -f "$STATE_FILE" ]; then
        source "$STATE_FILE"
        INTERNAL_IP_RANGES="${SAVED_INTERNAL_IP_RANGES:-$DEFAULT_INTERNAL_IP_RANGES}"
        CUSTOM_INTERNAL_IPS="${SAVED_CUSTOM_INTERNAL_IPS:-}"
        N8N_DOMAIN="${SAVED_N8N_DOMAIN:-}"
        INSTALL_CLOUDFLARE_TUNNEL="${SAVED_INSTALL_CLOUDFLARE_TUNNEL:-false}"
        INSTALL_TAILSCALE="${SAVED_INSTALL_TAILSCALE:-false}"
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
        generate_nginx_conf_v3

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
    echo "  --rollback          Rollback to v2.0 (if migrated within 30 days)"
    echo "  --update-access     Update access control settings (IP whitelist)"
    echo "  --version           Show version information"
    echo ""
}

handle_rollback() {
    if [ ! -f "$MIGRATION_STATE_FILE" ]; then
        print_error "No migration state found. Nothing to rollback."
        exit 1
    fi

    print_warning "This will rollback your installation to v2.0"
    if confirm_prompt "Are you sure you want to rollback?"; then
        rollback_to_v2
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SCRIPT
# ═══════════════════════════════════════════════════════════════════════════════

main() {
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
    esac

    clear

    print_header "n8n HTTPS Interactive Setup v${SCRIPT_VERSION}"

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
        echo -e "    • Adminer - Web-based database management"
        echo -e "    • Dozzle - Real-time container log viewer"
        echo -e "    • Portainer / Portainer Agent - Container management UI"
        echo -e "    • Metrics Agent - Host-level system monitoring"
        echo ""

        if ! confirm_prompt "Ready to begin?"; then
            exit 0
        fi

        # Handle v2.0 upgrade or fresh install
        handle_version_detection
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
            generate_nginx_conf_v3

            print_success "Configuration files regenerated!"
            echo ""

            if confirm_prompt "Would you like to redeploy the stack now?"; then
                deploy_stack
            else
                print_info "Configuration saved. Run 'docker compose up -d' when ready."
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
        generate_nginx_conf_v3
        create_letsencrypt_volume

        # Save config
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
EOF
        chmod 600 "${CONFIG_FILE}"

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
