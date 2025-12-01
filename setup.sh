#!/bin/bash

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                                                                           ║
# ║     n8n HTTPS Interactive Setup Script with Let's Encrypt + DNS           ║
# ║                                                                           ║
# ║     Automated SSL certificate setup and deployment for n8n                ║
# ║     with PostgreSQL, Nginx reverse proxy, and auto-renewal                ║
# ║                                                                           ║
# ║     Version 2.0.0                                                         ║
# ║     Richard J. Sears                                                      ║
# ║     richardjsears@gmail.com                                               ║
# ║     November 2025                                                         ║
# ║                                                                           ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

set -e

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_VERSION="2.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/.n8n_setup_config"

# Detect the real user (handles both direct execution and sudo ./setup.sh)
# SUDO_USER is set when someone runs "sudo ./setup.sh"
# If not set, fall back to USER, then to whoami
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

# Default database settings
DEFAULT_DB_NAME="n8n"
DEFAULT_DB_USER="n8n"

# ═══════════════════════════════════════════════════════════════════════════════
# COLORS & STYLING
# ═══════════════════════════════════════════════════════════════════════════════

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# Bold variants
BOLD='\033[1m'
DIM='\033[2m'
UNDERLINE='\033[4m'

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Print a decorated header
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

# Print a section header
print_section() {
    local title="$1"
    echo ""
    echo -e "${BLUE}┌─────────────────────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${BLUE}│${NC} ${WHITE}${BOLD}$title${NC}                                                    ${BLUE}│${NC}"
    echo -e "${BLUE}└─────────────────────────────────────────────────────────────────────────────┘${NC}"
}

# Print a section header
print_section_one() {
    local title="$1"
    echo ""
    echo -e "${BLUE}┌─────────────────────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${BLUE}│${NC} ${WHITE}${BOLD}$title${NC}                                                   ${BLUE}│${NC}"
    echo -e "${BLUE}└─────────────────────────────────────────────────────────────────────────────┘${NC}"
}

print_section_two() {
    local title="$1"
    echo ""
    echo -e "${BLUE}┌─────────────────────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${BLUE}│${NC} ${WHITE}${BOLD}$title${NC}                                                  ${BLUE}│${NC}"
    echo -e "${BLUE}└─────────────────────────────────────────────────────────────────────────────┘${NC}"
}


# Print a subsection
print_subsection() {
    echo ""
    echo -e "${GRAY}───────────────────────────────────────────────────────────────────────────────${NC}"
    echo ""
}

# Print success message
print_success() {
    echo -e "${GREEN}  ✓${NC} $1"
}

# Print error message
print_error() {
    echo -e "${RED}  ✗${NC} $1"
}

# Print warning message
print_warning() {
    echo -e "${YELLOW}  ⚠${NC} $1"
}

# Print info message
print_info() {
    echo -e "${CYAN}  ℹ${NC} $1"
}

# Print a step indicator
print_step() {
    local step_num="$1"
    local total_steps="$2"
    local description="$3"
    echo ""
    echo -e "${MAGENTA}  [$step_num/$total_steps]${NC} ${WHITE}${BOLD}$description${NC}"
    echo ""
}

# Spinner function for long operations
spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    while ps -p $pid > /dev/null 2>&1; do
        for i in $(seq 0 9); do
            printf "\r${CYAN}  ${spinstr:$i:1}${NC} %s" "$2"
            sleep $delay
        done
    done
    printf "\r"
}

# Prompt for input with default value
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

# Yes/No prompt
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

# Select from list
select_from_list() {
    local prompt="$1"
    shift
    local options=("$@")
    local selected=0

    echo -e "\n${WHITE}  $prompt${NC}\n"

    for i in "${!options[@]}"; do
        echo -e "    ${CYAN}$((i+1))${NC}) ${options[$i]}"
    done

    echo ""
    while true; do
        echo -ne "${WHITE}  Enter your choice [1-${#options[@]}]${NC}: "
        read choice

        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#options[@]}" ]; then
            selected=$((choice-1))
            break
        else
            print_error "Invalid selection. Please enter a number between 1 and ${#options[@]}"
        fi
    done

    return $selected
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
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
    # Check for /.dockerenv (not LXC, but container)
    if [ -f /run/host/container-manager ]; then
        return 0
    fi
    return 1
}

# Get local IP addresses
get_local_ips() {
    hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' || \
    ip addr show 2>/dev/null | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}' | cut -d'/' -f1 || \
    ifconfig 2>/dev/null | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}'
}

# ═══════════════════════════════════════════════════════════════════════════════
# DOCKER INSTALLATION
# ═══════════════════════════════════════════════════════════════════════════════

check_and_install_docker() {
    print_section "Docker Environment Check"

    # Detect platform for later use
    local CURRENT_PLATFORM=""
    if [ "$(uname)" = "Darwin" ]; then
        CURRENT_PLATFORM="macos"
    elif grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null; then
        CURRENT_PLATFORM="wsl"
    else
        CURRENT_PLATFORM="linux"
    fi

    # Check if Docker is installed
    if command_exists docker; then
        local docker_version=$(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',')
        print_success "Docker is installed (version: $docker_version)"

        # Check if Docker daemon is running
        if docker info >/dev/null 2>&1; then
            print_success "Docker daemon is running"
        else
            print_warning "Docker is installed but daemon is not running"

            if [ "$CURRENT_PLATFORM" = "macos" ]; then
                echo ""
                echo -e "  ${CYAN}Please start Docker Desktop:${NC}"
                echo -e "    - Open Docker from Applications folder"
                echo -e "    - Wait for the whale icon to appear in the menu bar"
                echo ""
                if confirm_prompt "Have you started Docker Desktop?"; then
                    if docker info >/dev/null 2>&1; then
                        print_success "Docker daemon is running"
                    else
                        print_error "Docker daemon is still not running. Please start Docker Desktop and try again."
                        exit 1
                    fi
                else
                    print_error "Docker daemon is required. Please start Docker Desktop and run this script again."
                    exit 1
                fi
            else
                if confirm_prompt "Would you like to start the Docker daemon?"; then
                    sudo systemctl start docker
                    sudo systemctl enable docker
                    print_success "Docker daemon started and enabled"
                else
                    print_error "Docker daemon is required. Please start it manually."
                    exit 1
                fi
            fi
        fi
    else
        print_warning "Docker is not installed"

        if confirm_prompt "Would you like to install Docker?"; then
            install_docker
        else
            print_error "Docker is required to continue. Please install it manually."
            exit 1
        fi
    fi

    # Check if Docker Compose is available (v2 as plugin)
    if docker compose version >/dev/null 2>&1; then
        local compose_version=$(docker compose version --short 2>/dev/null)
        print_success "Docker Compose is available (version: $compose_version)"
    elif command_exists docker-compose; then
        local compose_version=$(docker-compose --version 2>/dev/null | cut -d' ' -f4 | tr -d ',')
        print_success "Docker Compose (standalone) is available (version: $compose_version)"
        # Set flag to use docker-compose instead of docker compose
        USE_STANDALONE_COMPOSE=true
    else
        print_warning "Docker Compose is not available"

        if confirm_prompt "Would you like to install Docker Compose?"; then
            install_docker
        else
            print_error "Docker Compose is required to continue."
            exit 1
        fi
    fi

    # Test Docker functionality
    if [ "$CURRENT_PLATFORM" = "linux" ]; then
        if ! docker run --rm hello-world >/dev/null 2>&1; then
            # Check if this is an AppArmor issue
            local docker_error=$(docker run --rm hello-world 2>&1)
            if echo "$docker_error" | grep -q "AppArmor"; then
                echo ""
                print_warning "AppArmor is blocking Docker"
                echo ""
                echo -e "  ${GRAY}Docker cannot load its AppArmor security profile.${NC}"
                echo ""
                echo -e "  ${GRAY}Options:${NC}"
                echo -e "    ${WHITE}1)${NC} Remove AppArmor (recommended for dedicated n8n servers)"
                echo -e "    ${WHITE}2)${NC} Skip - I'll handle this myself"
                echo ""

                local apparmor_choice=""
                while [[ ! "$apparmor_choice" =~ ^[12]$ ]]; do
                    echo -ne "${WHITE}  Enter your choice [1-2]${NC}: "
                    read apparmor_choice
                done

                case $apparmor_choice in
                    1)
                        print_info "Removing AppArmor..."
                        sudo apt remove --purge apparmor -y >/dev/null 2>&1 || true
                        sudo systemctl restart docker 2>/dev/null || true
                        sleep 2
                        if docker run --rm hello-world >/dev/null 2>&1; then
                            print_success "AppArmor removed - Docker working"
                        else
                            print_warning "Docker still has issues - continuing with setup"
                        fi
                        ;;
                    2)
                        print_info "Skipping AppArmor fix"
                        print_warning "You may need to remove AppArmor manually: sudo apt remove --purge apparmor"
                        ;;
                esac
            else
                print_warning "Docker container test failed"
                print_info "This may be a network issue - continuing with setup"
            fi
        else
            print_success "Docker can run containers"
        fi
    fi

    # If running as root, no need for sudo or docker group
    if [ "$(id -u)" -eq 0 ]; then
        DOCKER_SUDO=""
        print_success "Running as root - no sudo required for Docker commands"
    # macOS Docker Desktop handles permissions automatically
    elif [ "$CURRENT_PLATFORM" = "macos" ]; then
        DOCKER_SUDO=""
        print_success "Docker Desktop on macOS handles permissions automatically"
    # Check if current user can run docker without sudo (Linux/WSL)
    elif ! docker ps >/dev/null 2>&1; then
        print_warning "Current user cannot run Docker commands without sudo"

        if confirm_prompt "Would you like to add your user to the docker group? (requires logout/login)"; then
            sudo usermod -aG docker $REAL_USER
            print_success "User added to docker group"
            print_warning "You may need to log out and back in for this to take effect"
            print_info "Alternatively, you can run: newgrp docker"
            echo ""
            if confirm_prompt "Would you like to continue with sudo for now?"; then
                DOCKER_SUDO="sudo"
            else
                print_info "Please log out and back in, then run this script again."
                exit 0
            fi
        else
            DOCKER_SUDO="sudo"
        fi
    else
        DOCKER_SUDO=""
    fi
}

install_docker() {
    print_subsection
    echo -e "${WHITE}  Installing Docker and Docker Compose...${NC}"
    echo ""

    # Detect OS and platform
    local PLATFORM=""
    local OS=""
    local VERSION_CODENAME=""

    # Check for macOS
    if [ "$(uname)" = "Darwin" ]; then
        PLATFORM="macos"
        OS="macos"
    # Check for WSL
    elif grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null; then
        PLATFORM="wsl"
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            OS=$ID
            VERSION_CODENAME=$VERSION_CODENAME
        fi
    # Check for Linux
    elif [ -f /etc/os-release ]; then
        PLATFORM="linux"
        . /etc/os-release
        OS=$ID
        VERSION_CODENAME=$VERSION_CODENAME
    else
        print_error "Cannot detect operating system"
        exit 1
    fi

    case $PLATFORM in
        macos)
            print_info "Detected macOS"
            echo ""

            # Check if Homebrew is installed
            if command_exists brew; then
                print_info "Homebrew detected"

                if confirm_prompt "Install Docker Desktop using Homebrew?"; then
                    print_info "Installing Docker Desktop via Homebrew..."
                    brew install --cask docker

                    echo ""
                    print_success "Docker Desktop installed!"
                    echo ""
                    echo -e "  ${YELLOW}IMPORTANT: You need to start Docker Desktop manually:${NC}"
                    echo -e "    1. Open Docker from Applications folder"
                    echo -e "    2. Complete the Docker Desktop setup wizard"
                    echo -e "    3. Wait for Docker to start (whale icon in menu bar)"
                    echo -e "    4. Run this script again"
                    echo ""

                    if confirm_prompt "Have you started Docker Desktop and it's running?"; then
                        if docker info >/dev/null 2>&1; then
                            print_success "Docker is running!"
                        else
                            print_error "Docker doesn't appear to be running yet"
                            print_info "Please start Docker Desktop and run this script again"
                            exit 1
                        fi
                    else
                        print_info "Please start Docker Desktop and run this script again"
                        exit 0
                    fi
                else
                    echo ""
                    echo -e "  ${CYAN}To install Docker Desktop manually:${NC}"
                    echo -e "    1. Download from: https://www.docker.com/products/docker-desktop/"
                    echo -e "    2. Open the .dmg file and drag Docker to Applications"
                    echo -e "    3. Start Docker Desktop from Applications"
                    echo -e "    4. Run this script again"
                    echo ""
                    exit 0
                fi
            else
                print_warning "Homebrew is not installed"
                echo ""
                echo -e "  ${CYAN}You have two options:${NC}"
                echo ""
                echo -e "  ${WHITE}Option 1: Install Homebrew first (recommended):${NC}"
                echo -e "    /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                echo -e "    Then run this script again"
                echo ""
                echo -e "  ${WHITE}Option 2: Install Docker Desktop manually:${NC}"
                echo -e "    Download from: https://www.docker.com/products/docker-desktop/"
                echo ""
                exit 0
            fi
            ;;

        wsl)
            print_info "Detected WSL (Windows Subsystem for Linux)"
            echo ""

            # Check if Docker Desktop is available (via Windows)
            if docker info >/dev/null 2>&1; then
                print_success "Docker is already available (likely via Docker Desktop for Windows)"
                return 0
            fi

            echo -e "  ${CYAN}You have two options for Docker in WSL:${NC}"
            echo ""
            echo -e "  ${WHITE}Option 1: Docker Desktop for Windows (recommended):${NC}"
            echo -e "    1. Download Docker Desktop from: https://www.docker.com/products/docker-desktop/"
            echo -e "    2. Install and enable 'Use WSL 2 based engine' in settings"
            echo -e "    3. Enable integration with your WSL distro in Settings > Resources > WSL Integration"
            echo -e "    4. Run this script again"
            echo ""
            echo -e "  ${WHITE}Option 2: Native Docker in WSL2:${NC}"
            echo -e "    Install Docker directly in your WSL distro (requires WSL2)"
            echo ""

            if confirm_prompt "Would you like to install Docker natively in WSL2?"; then
                # Fall through to Linux installation
                print_info "Installing Docker natively in WSL..."

                case $OS in
                    ubuntu|debian)
                        print_info "Detected $OS $VERSION_CODENAME in WSL"

                        # Update package index
                        print_info "Updating package index..."
                        sudo apt update -qq

                        # Install prerequisites
                        print_info "Installing prerequisites..."
                        sudo apt install -y -qq ca-certificates curl gnupg

                        # Add Docker's official GPG key
                        print_info "Adding Docker GPG key..."
                        sudo install -m 0755 -d /etc/apt/keyrings
                        curl -fsSL https://download.docker.com/linux/$OS/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
                        sudo chmod a+r /etc/apt/keyrings/docker.gpg

                        # Set up the repository
                        print_info "Adding Docker repository..."
                        echo \
                            "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$OS \
                            "$VERSION_CODENAME" stable" | \
                            sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

                        # Update package index again
                        sudo apt update -qq

                        # Install Docker
                        print_info "Installing Docker Engine and Docker Compose..."
                        sudo apt install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

                        # Start Docker (WSL doesn't use systemd by default)
                        print_info "Starting Docker daemon..."
                        sudo service docker start || sudo dockerd &

                        print_success "Docker and Docker Compose installed successfully!"
                        print_warning "Note: You may need to start Docker manually after WSL restarts:"
                        echo -e "  ${GRAY}sudo service docker start${NC}"
                        ;;
                    *)
                        print_error "Unsupported WSL distribution: $OS"
                        print_info "Please install Docker Desktop for Windows instead"
                        exit 1
                        ;;
                esac
            else
                print_info "Please install Docker Desktop for Windows and run this script again"
                exit 0
            fi
            ;;

        linux)
            case $OS in
                ubuntu|debian)
                    print_info "Detected $OS $VERSION_CODENAME"

                    # Update package index
                    print_info "Updating package index..."
                    sudo apt update -qq

                    # Install prerequisites
                    print_info "Installing prerequisites..."
                    sudo apt install -y -qq ca-certificates curl gnupg

                    # Add Docker's official GPG key
                    print_info "Adding Docker GPG key..."
                    sudo install -m 0755 -d /etc/apt/keyrings
                    curl -fsSL https://download.docker.com/linux/$OS/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
                    sudo chmod a+r /etc/apt/keyrings/docker.gpg

                    # Set up the repository
                    print_info "Adding Docker repository..."
                    echo \
                        "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$OS \
                        "$VERSION_CODENAME" stable" | \
                        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

                    # Update package index again
                    sudo apt update -qq

                    # Install Docker
                    print_info "Installing Docker Engine and Docker Compose..."
                    sudo apt install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

                    # Start and enable Docker first (creates AppArmor profile)
                    sudo systemctl start docker
                    sudo systemctl enable docker

                    print_success "Docker and Docker Compose installed successfully!"

                    # Wait for Docker daemon to be fully ready
                    print_info "Waiting for Docker daemon to initialize..."
                    local docker_ready=false
                    for i in $(seq 1 30); do
                        if docker info >/dev/null 2>&1; then
                            docker_ready=true
                            break
                        fi
                        sleep 1
                        printf "\r  ${GRAY}Waiting for Docker daemon... (%d/30)${NC}" $i
                    done
                    echo ""

                    if [ "$docker_ready" = true ]; then
                        print_success "Docker daemon is responding"
                    else
                        print_warning "Docker daemon took longer than expected to start"
                        print_info "Will check Docker functionality after installation completes"
                    fi
                    ;;

                centos|rhel|fedora|rocky|almalinux)
                    print_info "Detected $OS"

                    # Remove old versions
                    sudo yum remove -y docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine 2>/dev/null || true

                    # Install prerequisites
                    sudo yum install -y yum-utils

                    # Add Docker repository
                    sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

                    # Install Docker
                    sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

                    # Start and enable Docker
                    sudo systemctl start docker
                    sudo systemctl enable docker

                    print_success "Docker and Docker Compose installed successfully!"
                    ;;

                *)
                    print_error "Unsupported operating system: $OS"
                    print_info "Please install Docker manually: https://docs.docker.com/engine/install/"
                    exit 1
                    ;;
            esac
            ;;
    esac

    # macOS Docker Desktop handles permissions automatically - no docker group needed
    if [ "$PLATFORM" = "macos" ]; then
        DOCKER_SUDO=""
        print_success "Docker Desktop on macOS handles permissions automatically"
        return 0
    fi

    # If running as root, no need for docker group or sudo
    if [ "$(id -u)" -eq 0 ]; then
        DOCKER_SUDO=""
        print_success "Running as root - no docker group membership needed"
    else
        # Ask about adding user to docker group (Linux/WSL only)
        if confirm_prompt "Would you like to add your user to the docker group? (recommended)"; then
            sudo usermod -aG docker $REAL_USER
            print_success "User added to docker group"
            print_warning "You will need to log out and back in for this to take effect"
            DOCKER_SUDO="sudo"
        else
            DOCKER_SUDO="sudo"
        fi
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

perform_system_checks() {
    print_section_one "System Requirements Check"

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
        # macOS uses different df output format
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
        # macOS: get memory in bytes, convert to GB
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
        # macOS: use lsof or netstat with different flags
        if lsof -iTCP:443 -sTCP:LISTEN 2>/dev/null | grep -q LISTEN; then
            port_in_use=true
        fi
    else
        # Linux: use ss or netstat
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
# DNS PROVIDER CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

configure_dns_provider() {
    print_section_two "DNS Provider Configuration"

    echo -e "  ${GRAY}Let's Encrypt uses DNS validation to issue SSL certificates.${NC}"
    echo -e "  ${GRAY}This requires API access to your DNS provider.${NC}"
    echo ""

    local providers=("Cloudflare" "AWS Route 53" "Google Cloud DNS" "DigitalOcean" "Other (manual configuration)")
    select_from_list "Select your DNS provider:" "${providers[@]}"
    DNS_PROVIDER=$?

    case $DNS_PROVIDER in
        0) # Cloudflare
            configure_cloudflare
            ;;
        1) # AWS Route 53
            configure_route53
            ;;
        2) # Google Cloud DNS
            configure_google_dns
            ;;
        3) # DigitalOcean
            configure_digitalocean
            ;;
        4) # Other
            configure_other_dns
            ;;
    esac
}

configure_cloudflare() {
    DNS_PROVIDER_NAME="cloudflare"
    DNS_CERTBOT_IMAGE="certbot/dns-cloudflare:latest"
    DNS_CREDENTIALS_FILE="cloudflare.ini"

    print_subsection
    echo -e "${WHITE}  Cloudflare API Configuration${NC}"
    echo ""
    echo -e "  ${GRAY}You need a Cloudflare API token with the following permissions:${NC}"
    echo -e "  ${GRAY}  - Zone:DNS:Edit (for your domain's zone)${NC}"
    echo ""
    echo -e "  ${GRAY}Create one at: https://dash.cloudflare.com/profile/api-tokens${NC}"
    echo ""

    prompt_with_default "Enter your Cloudflare API token" "" "CF_API_TOKEN"

    if [ -z "$CF_API_TOKEN" ]; then
        print_error "API token is required for Cloudflare"
        exit 1
    fi

    # Create cloudflare.ini file
    cat > "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}" << EOF
# Cloudflare API credentials for Let's Encrypt DNS validation
# Generated by n8n setup script

dns_cloudflare_api_token = ${CF_API_TOKEN}
EOF

    chmod 600 "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}"
    print_success "Cloudflare credentials saved to ${DNS_CREDENTIALS_FILE}"

    DNS_CERTBOT_FLAGS="--dns-cloudflare --dns-cloudflare-credentials /credentials.ini --dns-cloudflare-propagation-seconds 60"
}

configure_route53() {
    DNS_PROVIDER_NAME="route53"
    DNS_CERTBOT_IMAGE="certbot/dns-route53:latest"
    DNS_CREDENTIALS_FILE="route53.ini"

    print_subsection
    echo -e "${WHITE}  AWS Route 53 Configuration${NC}"
    echo ""
    echo -e "  ${GRAY}You need AWS credentials with Route 53 access.${NC}"
    echo -e "  ${GRAY}Required IAM policy: AmazonRoute53FullAccess or equivalent${NC}"
    echo ""

    prompt_with_default "Enter your AWS Access Key ID" "" "AWS_ACCESS_KEY_ID"
    prompt_with_default "Enter your AWS Secret Access Key" "" "AWS_SECRET_ACCESS_KEY"

    if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
        print_error "Both AWS Access Key ID and Secret Access Key are required"
        exit 1
    fi

    # Create route53.ini file
    cat > "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}" << EOF
# AWS credentials for Let's Encrypt DNS validation
# Generated by n8n setup script

[default]
aws_access_key_id = ${AWS_ACCESS_KEY_ID}
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}
EOF

    chmod 600 "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}"
    print_success "AWS credentials saved to ${DNS_CREDENTIALS_FILE}"

    DNS_CERTBOT_FLAGS="--dns-route53"
}

configure_google_dns() {
    DNS_PROVIDER_NAME="google"
    DNS_CERTBOT_IMAGE="certbot/dns-google:latest"
    DNS_CREDENTIALS_FILE="google.json"

    print_subsection
    echo -e "${WHITE}  Google Cloud DNS Configuration${NC}"
    echo ""
    echo -e "  ${GRAY}You need a Google Cloud service account JSON key file.${NC}"
    echo -e "  ${GRAY}The service account needs the DNS Administrator role.${NC}"
    echo ""

    prompt_with_default "Enter the path to your service account JSON file" "" "GOOGLE_JSON_PATH"

    if [ ! -f "$GOOGLE_JSON_PATH" ]; then
        print_error "File not found: $GOOGLE_JSON_PATH"
        exit 1
    fi

    # Copy the JSON file
    cp "$GOOGLE_JSON_PATH" "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}"
    chmod 600 "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}"
    print_success "Google credentials saved to ${DNS_CREDENTIALS_FILE}"

    DNS_CERTBOT_FLAGS="--dns-google --dns-google-credentials /credentials.ini --dns-google-propagation-seconds 120"
}

configure_digitalocean() {
    DNS_PROVIDER_NAME="digitalocean"
    DNS_CERTBOT_IMAGE="certbot/dns-digitalocean:latest"
    DNS_CREDENTIALS_FILE="digitalocean.ini"

    print_subsection
    echo -e "${WHITE}  DigitalOcean DNS Configuration${NC}"
    echo ""
    echo -e "  ${GRAY}You need a DigitalOcean API token with read/write access.${NC}"
    echo -e "  ${GRAY}Create one at: https://cloud.digitalocean.com/account/api/tokens${NC}"
    echo ""

    prompt_with_default "Enter your DigitalOcean API token" "" "DO_API_TOKEN"

    if [ -z "$DO_API_TOKEN" ]; then
        print_error "API token is required for DigitalOcean"
        exit 1
    fi

    # Create digitalocean.ini file
    cat > "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}" << EOF
# DigitalOcean API credentials for Let's Encrypt DNS validation
# Generated by n8n setup script

dns_digitalocean_token = ${DO_API_TOKEN}
EOF

    chmod 600 "${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}"
    print_success "DigitalOcean credentials saved to ${DNS_CREDENTIALS_FILE}"

    DNS_CERTBOT_FLAGS="--dns-digitalocean --dns-digitalocean-credentials /credentials.ini --dns-digitalocean-propagation-seconds 60"
}

configure_other_dns() {
    DNS_PROVIDER_NAME="manual"

    print_subsection
    echo -e "${WHITE}  Manual DNS Provider Configuration${NC}"
    echo ""
    echo -e "  ${GRAY}For other DNS providers, you'll need to configure certbot manually.${NC}"
    echo -e "  ${GRAY}See: https://certbot.eff.org/docs/using.html#dns-plugins${NC}"
    echo ""

    print_warning "Manual configuration selected. You will need to:"
    echo -e "    1. Create the appropriate credentials file"
    echo -e "    2. Update docker-compose.yaml with the correct certbot image"
    echo -e "    3. Update the certbot command with appropriate flags"
    echo ""

    if ! confirm_prompt "Do you want to continue with a placeholder configuration?"; then
        exit 1
    fi

    # Set placeholder values
    DNS_CERTBOT_IMAGE="certbot/certbot:latest"
    DNS_CREDENTIALS_FILE="credentials.ini"
    DNS_CERTBOT_FLAGS="--manual --preferred-challenges dns"
}

# ═══════════════════════════════════════════════════════════════════════════════
# URL CONFIGURATION & VALIDATION
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
            echo -e "  ${GRAY}Local IP addresses on this machine:${NC}"
            for local_ip in $local_ips; do
                echo -e "    - $local_ip"
            done
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

    # Ping test
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

        if ! confirm_prompt "Do you understand the risks and want to continue?"; then
            echo ""
            print_info "Please configure your DNS correctly and run this script again."
            exit 1
        fi
    fi

    # Set derived URL values
    N8N_URL="https://${N8N_DOMAIN}"
    WEBHOOK_URL="https://${N8N_DOMAIN}"
    EDITOR_BASE_URL="https://${N8N_DOMAIN}"
}

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

configure_database() {
    print_section "PostgreSQL Database Configuration"

    echo -e "  ${GRAY}Configure your PostgreSQL database settings.${NC}"
    echo -e "  ${GRAY}These credentials will be used by n8n to store data.${NC}"
    echo ""

    prompt_with_default "Database name" "$DEFAULT_DB_NAME" "DB_NAME"
    prompt_with_default "Database username" "$DEFAULT_DB_USER" "DB_USER"

    echo ""
    echo -e "  ${GRAY}Enter a strong password for the database.${NC}"
    echo -e "  ${GRAY}Leave blank to auto-generate a secure password.${NC}"
    echo ""

    prompt_with_default "Database password" "" "DB_PASSWORD"

    if [ -z "$DB_PASSWORD" ]; then
        if command_exists openssl; then
            DB_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
            print_success "Generated secure database password"
        else
            print_error "OpenSSL not found and no password provided"
            prompt_with_default "Please enter a database password" "" "DB_PASSWORD"
            if [ -z "$DB_PASSWORD" ]; then
                print_error "Database password is required"
                exit 1
            fi
        fi
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONTAINER CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

configure_containers() {
    print_section "Container Names Configuration"

    echo -e "  ${GRAY}The following default container names will be used:${NC}"
    echo ""
    echo -e "    ${WHITE}PostgreSQL:${NC}  $DEFAULT_POSTGRES_CONTAINER"
    echo -e "    ${WHITE}n8n:${NC}         $DEFAULT_N8N_CONTAINER"
    echo -e "    ${WHITE}Nginx:${NC}       $DEFAULT_NGINX_CONTAINER"
    echo -e "    ${WHITE}Certbot:${NC}     $DEFAULT_CERTBOT_CONTAINER"
    echo ""

    if confirm_prompt "Would you like to customize these names?" "n"; then
        echo ""
        prompt_with_default "PostgreSQL container name" "$DEFAULT_POSTGRES_CONTAINER" "POSTGRES_CONTAINER"
        prompt_with_default "n8n container name" "$DEFAULT_N8N_CONTAINER" "N8N_CONTAINER"
        prompt_with_default "Nginx container name" "$DEFAULT_NGINX_CONTAINER" "NGINX_CONTAINER"
        prompt_with_default "Certbot container name" "$DEFAULT_CERTBOT_CONTAINER" "CERTBOT_CONTAINER"
    else
        POSTGRES_CONTAINER="$DEFAULT_POSTGRES_CONTAINER"
        N8N_CONTAINER="$DEFAULT_N8N_CONTAINER"
        NGINX_CONTAINER="$DEFAULT_NGINX_CONTAINER"
        CERTBOT_CONTAINER="$DEFAULT_CERTBOT_CONTAINER"
    fi

    print_success "Container names configured"
}

# ═══════════════════════════════════════════════════════════════════════════════
# EMAIL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

configure_email() {
    print_section "Let's Encrypt Email Configuration"

    echo -e "  ${GRAY}Let's Encrypt requires an email address for:${NC}"
    echo -e "    - Certificate expiration notifications"
    echo -e "    - Account recovery"
    echo ""

    prompt_with_default "Email address for Let's Encrypt" "admin@yourdomain.com" "LETSENCRYPT_EMAIL"

    # Validate email format
    if [[ ! "$LETSENCRYPT_EMAIL" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
        print_warning "Email format may be invalid: $LETSENCRYPT_EMAIL"
        if ! confirm_prompt "Continue anyway?"; then
            configure_email
        fi
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# TIMEZONE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

configure_timezone() {
    print_section "Timezone Configuration"

    # Detect current system timezone
    local system_tz=""
    if [ -f /etc/timezone ]; then
        system_tz=$(cat /etc/timezone)
    elif command_exists timedatectl; then
        system_tz=$(timedatectl show -p Timezone --value 2>/dev/null)
    fi

    if [ -z "$system_tz" ]; then
        system_tz="America/Los_Angeles"
    fi

    echo -e "  ${GRAY}Detected system timezone: $system_tz${NC}"
    echo ""

    if confirm_prompt "Use $system_tz as the timezone for n8n?" "y"; then
        N8N_TIMEZONE="$system_tz"
    else
        echo ""
        echo -e "  ${GRAY}Enter your timezone (e.g., America/New_York, Europe/London, Asia/Tokyo)${NC}"
        echo -e "  ${GRAY}See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones${NC}"
        echo ""
        prompt_with_default "Timezone" "$system_tz" "N8N_TIMEZONE"
    fi

    print_success "Timezone set to: $N8N_TIMEZONE"
}

# ═══════════════════════════════════════════════════════════════════════════════
# ENCRYPTION KEY GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

generate_encryption_key() {
    print_section "Encryption Key Configuration"

    echo -e "  ${GRAY}n8n uses an encryption key to secure credentials stored in the database.${NC}"
    echo -e "  ${GRAY}This key should be kept secret and backed up securely.${NC}"
    echo ""

    if command_exists openssl; then
        N8N_ENCRYPTION_KEY=$(openssl rand -base64 32)
        print_success "Generated secure encryption key using OpenSSL"
    else
        print_warning "OpenSSL not found. Cannot auto-generate encryption key."
        echo ""
        echo -e "  ${GRAY}Please enter a secure key (minimum 32 characters recommended).${NC}"
        echo -e "  ${GRAY}You can generate one with: openssl rand -base64 32${NC}"
        echo ""

        prompt_with_default "Enter encryption key" "" "N8N_ENCRYPTION_KEY"

        if [ ${#N8N_ENCRYPTION_KEY} -lt 10 ]; then
            print_error "Encryption key must be at least 10 characters"
            exit 1
        fi
    fi

    echo ""
    print_warning "IMPORTANT: Save your encryption key in a secure location!"
    echo -e "  ${GRAY}If you lose this key, you will not be able to decrypt stored credentials.${NC}"
}

# ═══════════════════════════════════════════════════════════════════════════════
# PORTAINER AGENT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

configure_portainer() {
    print_section "Portainer Agent Configuration"

    echo -e "  ${GRAY}Portainer is a popular container management UI.${NC}"
    echo -e "  ${GRAY}If you're running Portainer on another server, you can install${NC}"
    echo -e "  ${GRAY}the Portainer Agent here to manage this n8n stack remotely.${NC}"
    echo ""

    if confirm_prompt "Are you using Portainer to manage your containers?" "n"; then
        INSTALL_PORTAINER_AGENT=true
        print_success "Portainer Agent will be included in docker-compose.yaml"

        echo ""
        echo -e "  ${GRAY}The agent will be accessible on port 9001.${NC}"
        echo -e "  ${GRAY}Add this server to Portainer using: ${WHITE}<this-server-ip>:9001${NC}"
    else
        INSTALL_PORTAINER_AGENT=false
        print_info "Portainer Agent will be commented out in docker-compose.yaml"
        echo -e "  ${GRAY}You can enable it later by uncommenting the section in docker-compose.yaml${NC}"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

show_configuration_summary() {
    print_section "Configuration Summary"

    echo ""
    echo -e "  ${WHITE}${BOLD}Domain & URL:${NC}"
    echo -e "    Domain:              ${CYAN}$N8N_DOMAIN${NC}"
    echo -e "    URL:                 ${CYAN}$N8N_URL${NC}"
    echo ""

    echo -e "  ${WHITE}${BOLD}DNS Provider:${NC}"
    echo -e "    Provider:            ${CYAN}$DNS_PROVIDER_NAME${NC}"
    echo -e "    Credentials file:    ${CYAN}$DNS_CREDENTIALS_FILE${NC}"
    echo ""

    echo -e "  ${WHITE}${BOLD}Database:${NC}"
    echo -e "    Name:                ${CYAN}$DB_NAME${NC}"
    echo -e "    User:                ${CYAN}$DB_USER${NC}"
    echo -e "    Password:            ${GRAY}[configured]${NC}"
    echo ""

    echo -e "  ${WHITE}${BOLD}Container Names:${NC}"
    echo -e "    PostgreSQL:          ${CYAN}$POSTGRES_CONTAINER${NC}"
    echo -e "    n8n:                 ${CYAN}$N8N_CONTAINER${NC}"
    echo -e "    Nginx:               ${CYAN}$NGINX_CONTAINER${NC}"
    echo -e "    Certbot:             ${CYAN}$CERTBOT_CONTAINER${NC}"
    echo ""

    echo -e "  ${WHITE}${BOLD}Other Settings:${NC}"
    echo -e "    Email:               ${CYAN}$LETSENCRYPT_EMAIL${NC}"
    echo -e "    Timezone:            ${CYAN}$N8N_TIMEZONE${NC}"
    echo -e "    Encryption key:      ${GRAY}[configured]${NC}"
    if [ "$INSTALL_PORTAINER_AGENT" = true ]; then
        echo -e "    Portainer Agent:     ${GREEN}enabled${NC}"
    else
        echo -e "    Portainer Agent:     ${GRAY}disabled (commented out)${NC}"
    fi
    echo ""

    echo -e "${GRAY}───────────────────────────────────────────────────────────────────────────────${NC}"
    echo ""

    if ! confirm_prompt "Is this configuration correct?"; then
        echo ""
        print_info "Let's go through the configuration again..."
        return 1
    fi

    return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# GENERATE CONFIGURATION FILES
# ═══════════════════════════════════════════════════════════════════════════════

generate_docker_compose() {
    print_step "1" "4" "Generating docker-compose.yaml"

    # Determine the credential mount path based on provider
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
            DNS_CERTBOT_FLAGS="--dns-google --dns-google-credentials /credentials.json --dns-google-propagation-seconds 120"
            ;;
        manual)
            cred_mount="./${DNS_CREDENTIALS_FILE}:/credentials.ini:ro"
            ;;
    esac

    cat > "${SCRIPT_DIR}/docker-compose.yaml" << EOF
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: ${POSTGRES_CONTAINER}
    restart: always
    environment:
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=${DB_NAME}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -h localhost -U ${DB_USER} -d ${DB_NAME}']
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - n8n_network

  n8n:
    image: n8nio/n8n:latest
    container_name: ${N8N_CONTAINER}
    restart: always
    environment:
      # Database Configuration
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=${DB_NAME}
      - DB_POSTGRESDB_USER=${DB_USER}
      - DB_POSTGRESDB_PASSWORD=${DB_PASSWORD}

      # n8n Configuration - HTTPS
      - N8N_HOST=${N8N_DOMAIN}
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=${WEBHOOK_URL}
      - N8N_EDITOR_BASE_URL=${EDITOR_BASE_URL}

      # Timezone
      - GENERIC_TIMEZONE=${N8N_TIMEZONE}
      - TZ=${N8N_TIMEZONE}

      # Execution Configuration
      - EXECUTIONS_MODE=regular
      - EXECUTIONS_DATA_SAVE_ON_ERROR=all
      - EXECUTIONS_DATA_SAVE_ON_SUCCESS=all
      - EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS=true

      # Security
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
      - N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true

      # Performance & Isolation
      - N8N_PAYLOAD_SIZE_MAX=16
      - N8N_METRICS=false

      # Logging
      - N8N_LOG_LEVEL=info
      - N8N_LOG_OUTPUT=console

      # Community Nodes
      - N8N_COMMUNITY_PACKAGES_ENABLED=true
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - n8n_network

  nginx:
    image: nginx:alpine
    container_name: ${NGINX_CONTAINER}
    restart: always
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - certbot_data:/var/www/certbot:ro
      - letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - n8n
    networks:
      - n8n_network

  certbot:
    image: ${DNS_CERTBOT_IMAGE}
    container_name: ${CERTBOT_CONTAINER}
    volumes:
      - letsencrypt:/etc/letsencrypt
      - certbot_data:/var/www/certbot
      - ${cred_mount}
      - /var/run/docker.sock:/var/run/docker.sock:ro
    entrypoint: /bin/sh -c "trap exit TERM; while :; do certbot renew ${DNS_CERTBOT_FLAGS} --deploy-hook 'docker exec ${NGINX_CONTAINER} nginx -s reload' || true; sleep 12h & wait \$\${!}; done;"
    networks:
      - n8n_network

EOF

    # Add Portainer Agent section (commented or uncommented based on user choice)
    if [ "$INSTALL_PORTAINER_AGENT" = true ]; then
        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << 'PORTAINER_ENABLED'
  # ─────────────────────────────────────────────────────────────────────────────
  # Portainer Agent - Remote container management
  # Add this server to your Portainer instance using: <server-ip>:9001
  # ─────────────────────────────────────────────────────────────────────────────
  portainer_agent:
    image: portainer/agent:latest
    # Tested with version 2.33.1 - pin to specific version if you experience issues
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

PORTAINER_ENABLED
    else
        cat >> "${SCRIPT_DIR}/docker-compose.yaml" << 'PORTAINER_DISABLED'
  # ─────────────────────────────────────────────────────────────────────────────
  # Portainer Agent - Remote container management (DISABLED)
  # Uncomment the section below to enable Portainer Agent
  # Add this server to your Portainer instance using: <server-ip>:9001
  # ─────────────────────────────────────────────────────────────────────────────
  # portainer_agent:
  #   image: portainer/agent:latest
  #   # Tested with version 2.33.1 - pin to specific version if you experience issues
  #   container_name: portainer_agent
  #   restart: always
  #   ports:
  #     - "9001:9001"
  #   volumes:
  #     - /var/run/docker.sock:/var/run/docker.sock
  #     - /var/lib/docker/volumes:/var/lib/docker/volumes
  #     - /:/host
  #   networks:
  #     - n8n_network

PORTAINER_DISABLED
    fi

    # Add volumes and networks sections
    cat >> "${SCRIPT_DIR}/docker-compose.yaml" << EOF
volumes:
  n8n_data:
    driver: local
  postgres_data:
    driver: local
  letsencrypt:
    external: true
  certbot_data:
    driver: local

networks:
  n8n_network:
    driver: bridge
EOF

    print_success "docker-compose.yaml generated"
}

generate_nginx_conf() {
    print_step "2" "4" "Generating nginx.conf"

    cat > "${SCRIPT_DIR}/nginx.conf" << EOF
events {
    worker_connections 1024;
}

http {
    # Increase buffer sizes for large payloads (PDF processing)
    client_max_body_size 50M;
    client_body_buffer_size 10M;

    # Timeouts for long-running workflows
    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;
    send_timeout 600s;

    # Upstream to n8n
    upstream n8n {
        server ${N8N_CONTAINER}:5678;
    }

    # HTTPS Server
    server {
        listen 443 ssl http2;
        server_name ${N8N_DOMAIN};

        # SSL Certificate paths
        ssl_certificate /etc/letsencrypt/live/${N8N_DOMAIN}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${N8N_DOMAIN}/privkey.pem;

        # Modern SSL configuration
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        # Security headers
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;

        # CORS-enabled webhook endpoint for web chat example
        location /webhook/ {
            # CORS headers
            add_header 'Access-Control-Allow-Origin' '*' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'Content-Type, Authorization' always;
            add_header X-Frame-Options "SAMEORIGIN" always;
            add_header X-Content-Type-Options "nosniff" always;
            add_header X-XSS-Protection "1; mode=block" always;

            # Handle preflight OPTIONS request
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
            proxy_set_header X-Forwarded-Host \$host;
            proxy_set_header X-Forwarded-Port \$server_port;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_buffering off;
        }

        # Default proxy settings (n8n UI and other endpoints)
        location / {
            add_header X-Frame-Options "SAMEORIGIN" always;

            proxy_pass http://n8n;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_set_header X-Forwarded-Host \$host;
            proxy_set_header X-Forwarded-Port \$server_port;

            # WebSocket support (for real-time updates)
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";

            # Disable buffering for streaming responses
            proxy_buffering off;
        }

        # Health check endpoint
        location /healthz {
            access_log off;
            return 200 "healthy\n";
        }
    }
}
EOF

    print_success "nginx.conf generated"
}

save_configuration() {
    print_step "3" "4" "Saving configuration backup"

    # Save configuration to a file for future reference (without sensitive data)
    cat > "${CONFIG_FILE}" << EOF
# n8n Setup Configuration
# Generated: $(date)
# Version: ${SCRIPT_VERSION}

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
PORTAINER_AGENT_ENABLED=${INSTALL_PORTAINER_AGENT}
EOF

    chmod 600 "${CONFIG_FILE}"
    print_success "Configuration saved to ${CONFIG_FILE}"
}

create_letsencrypt_volume() {
    print_step "4" "4" "Creating Let's Encrypt Docker volume"

    if $DOCKER_SUDO docker volume inspect letsencrypt >/dev/null 2>&1; then
        print_info "Volume 'letsencrypt' already exists"
    else
        $DOCKER_SUDO docker volume create letsencrypt
        print_success "Volume 'letsencrypt' created"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT
# ═══════════════════════════════════════════════════════════════════════════════

deploy_stack() {
    print_section "Deploying n8n Stack"

    local total_steps=6
    local docker_compose_cmd="docker compose"

    if [ "$USE_STANDALONE_COMPOSE" = true ]; then
        docker_compose_cmd="docker-compose"
    fi

    if [ -n "$DOCKER_SUDO" ]; then
        docker_compose_cmd="$DOCKER_SUDO $docker_compose_cmd"
    fi

    # Step 1: Start PostgreSQL
    print_step "1" "$total_steps" "Starting PostgreSQL database"
    cd "$SCRIPT_DIR"
    $docker_compose_cmd up -d postgres

    echo -e "  ${GRAY}Waiting for PostgreSQL to be ready...${NC}"
    local max_attempts=30
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if $DOCKER_SUDO docker exec $POSTGRES_CONTAINER pg_isready -U $DB_USER -d $DB_NAME >/dev/null 2>&1; then
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
        printf "\r  ${GRAY}Waiting for PostgreSQL... (%d/%d)${NC}" $attempt $max_attempts
    done
    echo ""

    if [ $attempt -eq $max_attempts ]; then
        print_error "PostgreSQL failed to start within timeout"
        exit 1
    fi
    print_success "PostgreSQL is running and healthy"

    # Step 2: Obtain SSL certificate
    print_step "2" "$total_steps" "Obtaining SSL certificate from Let's Encrypt"
    echo -e "  ${GRAY}Domain: $N8N_DOMAIN${NC}"
    echo -e "  ${GRAY}This uses DNS-01 challenge (no ports 80/443 exposure required)${NC}"
    echo ""

    # Determine credential mount for certbot
    local cred_mount=""
    local cred_volume_opt=""
    case $DNS_PROVIDER_NAME in
        cloudflare|digitalocean)
            cred_mount="/credentials.ini"
            cred_volume_opt="-v $(pwd)/${DNS_CREDENTIALS_FILE}:${cred_mount}:ro"
            ;;
        route53)
            cred_mount="/root/.aws/credentials"
            cred_volume_opt="-v $(pwd)/${DNS_CREDENTIALS_FILE}:${cred_mount}:ro"
            ;;
        google)
            cred_mount="/credentials.json"
            cred_volume_opt="-v $(pwd)/${DNS_CREDENTIALS_FILE}:${cred_mount}:ro"
            ;;
        manual)
            cred_mount="/credentials.ini"
            cred_volume_opt="-v $(pwd)/${DNS_CREDENTIALS_FILE}:${cred_mount}:ro"
            ;;
    esac

    # Adjust certbot flags for initial certificate acquisition
    local certbot_initial_flags=""
    case $DNS_PROVIDER_NAME in
        cloudflare)
            certbot_initial_flags="--dns-cloudflare --dns-cloudflare-credentials ${cred_mount} --dns-cloudflare-propagation-seconds 60"
            ;;
        digitalocean)
            certbot_initial_flags="--dns-digitalocean --dns-digitalocean-credentials ${cred_mount} --dns-digitalocean-propagation-seconds 60"
            ;;
        route53)
            certbot_initial_flags="--dns-route53"
            ;;
        google)
            certbot_initial_flags="--dns-google --dns-google-credentials ${cred_mount} --dns-google-propagation-seconds 120"
            ;;
        manual)
            certbot_initial_flags="--manual --preferred-challenges dns"
            ;;
    esac

    # Run certbot to obtain certificate
    mkdir -p "${SCRIPT_DIR}/letsencrypt-temp"

    if ! $DOCKER_SUDO docker run --rm \
        -v "$(pwd)/letsencrypt-temp:/etc/letsencrypt" \
        $cred_volume_opt \
        $DNS_CERTBOT_IMAGE \
        certonly \
        $certbot_initial_flags \
        -d "$N8N_DOMAIN" \
        --agree-tos \
        --non-interactive \
        --email "$LETSENCRYPT_EMAIL"; then

        print_error "Failed to obtain SSL certificate"
        echo ""
        echo -e "  ${YELLOW}Troubleshooting tips:${NC}"
        echo -e "    - Verify your DNS provider API credentials are correct"
        echo -e "    - Ensure the domain $N8N_DOMAIN is in your DNS provider account"
        echo -e "    - Check that your API token has the required permissions"
        echo -e "    - Wait a few minutes if you just created DNS records"
        echo ""

        if confirm_prompt "Would you like to view the certbot logs?"; then
            cat "${SCRIPT_DIR}/letsencrypt-temp/letsencrypt.log" 2>/dev/null || echo "No log file found"
        fi
        exit 1
    fi

    print_success "SSL certificate obtained successfully!"

    # Step 3: Copy certificates to Docker volume
    print_step "3" "$total_steps" "Copying certificates to Docker volume"

    $DOCKER_SUDO docker run --rm \
        -v "$(pwd)/letsencrypt-temp:/source:ro" \
        -v letsencrypt:/dest \
        alpine \
        sh -c "cp -rL /source/* /dest/"

    rm -rf "${SCRIPT_DIR}/letsencrypt-temp"
    print_success "Certificates copied to Docker volume"

    # Step 4: Start all services
    print_step "4" "$total_steps" "Starting all services"
    cd "$SCRIPT_DIR"
    $docker_compose_cmd up -d

    echo -e "  ${GRAY}Waiting for services to start...${NC}"
    sleep 10
    print_success "All services started"

    # Step 5: Verify services
    print_step "5" "$total_steps" "Verifying services"
    verify_services

    # Step 6: Test SSL and connectivity
    print_step "6" "$total_steps" "Testing SSL certificate and connectivity"
    test_ssl_and_connectivity
}

verify_services() {
    local all_healthy=true

    # Check PostgreSQL
    echo -e "  ${GRAY}Checking PostgreSQL...${NC}"
    if $DOCKER_SUDO docker exec $POSTGRES_CONTAINER pg_isready -U $DB_USER -d $DB_NAME >/dev/null 2>&1; then
        print_success "PostgreSQL is responding"

        # Test database connection with credentials
        if $DOCKER_SUDO docker exec $POSTGRES_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT 1;" >/dev/null 2>&1; then
            print_success "PostgreSQL authentication successful"
        else
            print_warning "PostgreSQL authentication test failed"
            all_healthy=false
        fi
    else
        print_error "PostgreSQL is not responding"
        all_healthy=false
    fi

    # Check n8n
    echo -e "  ${GRAY}Checking n8n...${NC}"
    local n8n_attempts=0
    local n8n_max_attempts=30
    while [ $n8n_attempts -lt $n8n_max_attempts ]; do
        if $DOCKER_SUDO docker exec $N8N_CONTAINER wget -q -O - http://localhost:5678/healthz >/dev/null 2>&1; then
            break
        fi
        n8n_attempts=$((n8n_attempts + 1))
        sleep 2
        printf "\r  ${GRAY}Waiting for n8n to be ready... (%d/%d)${NC}" $n8n_attempts $n8n_max_attempts
    done
    echo ""

    if [ $n8n_attempts -lt $n8n_max_attempts ]; then
        print_success "n8n is responding"
    else
        print_warning "n8n health check timeout (may still be starting)"
        all_healthy=false
    fi

    # Check Nginx
    echo -e "  ${GRAY}Checking Nginx...${NC}"
    if $DOCKER_SUDO docker exec $NGINX_CONTAINER nginx -t >/dev/null 2>&1; then
        print_success "Nginx configuration is valid"
    else
        print_error "Nginx configuration test failed"
        all_healthy=false
    fi

    # Check container status
    echo ""
    echo -e "  ${WHITE}Container Status:${NC}"
    $DOCKER_SUDO docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(${POSTGRES_CONTAINER}|${N8N_CONTAINER}|${NGINX_CONTAINER}|${CERTBOT_CONTAINER}|NAMES)" || true

    if [ "$all_healthy" = false ]; then
        echo ""
        print_warning "Some services may not be fully healthy"
    fi
}

test_ssl_and_connectivity() {
    echo ""

    # Test HTTPS connectivity
    echo -e "  ${GRAY}Testing HTTPS connectivity to ${N8N_URL}...${NC}"

    local ssl_test_passed=false
    local connect_test_passed=false

    # Wait a bit for nginx to fully start
    sleep 5

    # Test SSL certificate validity
    if command_exists openssl; then
        local ssl_output=$(echo | openssl s_client -servername "$N8N_DOMAIN" -connect "${N8N_DOMAIN}:443" 2>/dev/null | openssl x509 -noout -dates 2>/dev/null)
        if [ -n "$ssl_output" ]; then
            print_success "SSL certificate is valid"
            echo -e "  ${GRAY}$ssl_output${NC}"
            ssl_test_passed=true
        else
            print_warning "Could not verify SSL certificate (may need more time to propagate)"
        fi
    fi

    # Test HTTP response
    if curl -sk --connect-timeout 10 "${N8N_URL}/healthz" 2>/dev/null | grep -q "healthy"; then
        print_success "n8n is accessible via HTTPS"
        connect_test_passed=true
    else
        # Try localhost with host header
        if curl -sk --connect-timeout 10 -H "Host: ${N8N_DOMAIN}" "https://localhost/healthz" 2>/dev/null | grep -q "healthy"; then
            print_success "n8n is accessible via HTTPS (localhost)"
            connect_test_passed=true
        else
            print_warning "Could not reach n8n via HTTPS (may need DNS propagation)"
        fi
    fi

    if [ "$ssl_test_passed" = true ] && [ "$connect_test_passed" = true ]; then
        echo ""
        print_success "All connectivity tests passed!"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

show_final_summary() {
    print_header "Setup Complete!"

    echo -e "  ${GREEN}Your n8n instance is now running!${NC}"
    echo ""
    echo -e "  ${WHITE}${BOLD}Access your n8n instance:${NC}"
    echo -e "    ${CYAN}${N8N_URL}${NC}"
    echo ""
    echo -e "  ${WHITE}${BOLD}Useful Commands:${NC}"
    echo -e "    ${GRAY}View logs:${NC}         docker compose logs -f"
    echo -e "    ${GRAY}View n8n logs:${NC}     docker compose logs -f n8n"
    echo -e "    ${GRAY}Stop services:${NC}     docker compose down"
    echo -e "    ${GRAY}Start services:${NC}    docker compose up -d"
    echo -e "    ${GRAY}Restart services:${NC}  docker compose restart"
    echo -e "    ${GRAY}View status:${NC}       docker compose ps"
    echo ""
    echo -e "  ${WHITE}${BOLD}Important Files:${NC}"
    echo -e "    ${GRAY}Docker Compose:${NC}    ${SCRIPT_DIR}/docker-compose.yaml"
    echo -e "    ${GRAY}Nginx Config:${NC}      ${SCRIPT_DIR}/nginx.conf"
    echo -e "    ${GRAY}DNS Credentials:${NC}   ${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}"
    echo -e "    ${GRAY}Setup Config:${NC}      ${SCRIPT_DIR}/.n8n_setup_config"
    echo ""
    echo -e "  ${YELLOW}${BOLD}Security Reminders:${NC}"
    echo -e "    - Create your n8n owner account immediately"
    echo -e "    - Back up your encryption key securely"
    echo -e "    - Keep your DNS credentials file secure (chmod 600)"
    echo -e "    - SSL certificates auto-renew every 12 hours"
    echo ""
    echo -e "  ${GRAY}───────────────────────────────────────────────────────────────────────────────${NC}"
    echo ""
    echo -e "  ${WHITE}Thank you for using n8n HTTPS Setup Script v${SCRIPT_VERSION}${NC}"
    echo -e "  ${GRAY}Created by Richard J. Sears - richardjsears@gmail.com${NC}"
    echo ""
}

show_config_only_summary() {
    print_header "Configuration Generated"

    echo -e "  ${GREEN}Configuration files have been generated successfully!${NC}"
    echo ""
    echo -e "  ${WHITE}${BOLD}Files Created/Updated:${NC}"
    echo -e "    - ${SCRIPT_DIR}/docker-compose.yaml"
    echo -e "    - ${SCRIPT_DIR}/nginx.conf"
    echo -e "    - ${SCRIPT_DIR}/${DNS_CREDENTIALS_FILE}"
    echo -e "    - ${SCRIPT_DIR}/.n8n_setup_config"
    echo ""
    echo -e "  ${WHITE}${BOLD}To deploy manually:${NC}"
    echo ""
    echo -e "    ${CYAN}1.${NC} Create the Let's Encrypt volume:"
    echo -e "       ${GRAY}docker volume create letsencrypt${NC}"
    echo ""
    echo -e "    ${CYAN}2.${NC} Start PostgreSQL and wait for it to be ready:"
    echo -e "       ${GRAY}docker compose up -d postgres${NC}"
    echo -e "       ${GRAY}sleep 15${NC}"
    echo ""
    echo -e "    ${CYAN}3.${NC} Obtain SSL certificate (adjust for your DNS provider):"
    echo -e "       ${GRAY}docker run --rm \\${NC}"
    echo -e "       ${GRAY}  -v \"\$(pwd)/letsencrypt-temp:/etc/letsencrypt\" \\${NC}"
    echo -e "       ${GRAY}  -v \"\$(pwd)/${DNS_CREDENTIALS_FILE}:/credentials.ini:ro\" \\${NC}"
    echo -e "       ${GRAY}  ${DNS_CERTBOT_IMAGE} \\${NC}"
    echo -e "       ${GRAY}  certonly ${DNS_CERTBOT_FLAGS} \\${NC}"
    echo -e "       ${GRAY}  -d ${N8N_DOMAIN} --agree-tos --email ${LETSENCRYPT_EMAIL}${NC}"
    echo ""
    echo -e "    ${CYAN}4.${NC} Copy certificates to Docker volume:"
    echo -e "       ${GRAY}docker run --rm \\${NC}"
    echo -e "       ${GRAY}  -v \"\$(pwd)/letsencrypt-temp:/source:ro\" \\${NC}"
    echo -e "       ${GRAY}  -v letsencrypt:/dest \\${NC}"
    echo -e "       ${GRAY}  alpine sh -c \"cp -rL /source/* /dest/\"${NC}"
    echo ""
    echo -e "    ${CYAN}5.${NC} Start all services:"
    echo -e "       ${GRAY}docker compose up -d${NC}"
    echo ""
    echo -e "  ${GRAY}───────────────────────────────────────────────────────────────────────────────${NC}"
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SCRIPT
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    clear

    # Display welcome header
    print_header "n8n HTTPS Interactive Setup v${SCRIPT_VERSION}"

    # Check if running as root directly (not via sudo)
    if [ "$(id -u)" -eq 0 ] && [ -z "$SUDO_USER" ]; then
        echo -e "  ${YELLOW}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "  ${YELLOW}║                              NOTE                                         ║${NC}"
        echo -e "  ${YELLOW}║  You are running this script as root. While this will work, it's          ║${NC}"
        echo -e "  ${YELLOW}║  recommended to run as a regular user (the script uses sudo internally).  ║${NC}"
        echo -e "  ${YELLOW}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        if ! confirm_prompt "Continue as root?"; then
            echo ""
            print_info "Please run as a regular user: ./setup.sh"
            exit 0
        fi
    fi

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

    echo -e "  ${GRAY}This script will guide you through setting up a production-ready${NC}"
    echo -e "  ${GRAY}n8n instance with HTTPS, PostgreSQL, and automatic SSL renewal.${NC}"
    echo ""
    echo -e "  ${WHITE}Features:${NC}"
    echo -e "    - Automated SSL certificates via Let's Encrypt"
    echo -e "    - DNS-01 challenge (no port 80/443 exposure needed)"
    echo -e "    - PostgreSQL 16 with pgvector for AI/RAG workflows"
    echo -e "    - Nginx reverse proxy with security headers"
    echo -e "    - Automatic certificate renewal every 12 hours"
    echo ""

    if ! confirm_prompt "Ready to begin?"; then
        echo ""
        print_info "Setup cancelled. Run this script again when ready."
        exit 0
    fi

    # Run all configuration steps
    check_and_install_docker
    perform_system_checks
    configure_dns_provider
    configure_url
    configure_database
    configure_containers
    configure_email
    configure_timezone
    generate_encryption_key
    configure_portainer

    # Show summary and confirm
    while ! show_configuration_summary; do
        configure_dns_provider
        configure_url
        configure_database
        configure_containers
        configure_email
        configure_timezone
        generate_encryption_key
        configure_portainer
    done

    # Generate configuration files
    print_section "Generating Configuration Files"
    generate_docker_compose
    generate_nginx_conf
    save_configuration
    create_letsencrypt_volume

    print_success "All configuration files generated successfully!"

    # Ask about deployment
    echo ""
    if confirm_prompt "Would you like to deploy the stack now?"; then
        deploy_stack
        show_final_summary
    else
        show_config_only_summary
    fi
}

# Run main function
main "$@"
