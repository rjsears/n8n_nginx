#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /install.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 1st, 2026
#
# Richard J. Sears
# richard@n8nmanagement.net
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

set -e

# ═══════════════════════════════════════════════════════════════════════════════
# COLORS & FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

REPO_URL="https://github.com/rjsears/n8n_nginx.git"
INSTALL_DIR="n8n_nginx"

# Branch to install (default: main, override with BRANCH env var)
# Usage: curl -fsSL https://raw.githubusercontent.com/rjsears/n8n_nginx/main/install.sh | BRANCH=dev bash
BRANCH="${BRANCH:-main}"

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                           ║"
    echo "║                    n8n_nginx Quick Installer                              ║"
    echo "║                                                                           ║"
    echo "║     Automated n8n deployment with Nginx, SSL, and Management UI           ║"
    echo "║                                                                           ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

detect_package_manager() {
    if command -v apt-get &> /dev/null; then
        echo "apt"
    elif command -v dnf &> /dev/null; then
        echo "dnf"
    elif command -v yum &> /dev/null; then
        echo "yum"
    elif command -v pacman &> /dev/null; then
        echo "pacman"
    elif command -v brew &> /dev/null; then
        echo "brew"
    elif command -v apk &> /dev/null; then
        echo "apk"
    else
        echo "unknown"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# GIT INSTALLATION
# ═══════════════════════════════════════════════════════════════════════════════

install_git() {
    local pkg_manager=$1

    info "Installing git..."

    case $pkg_manager in
        apt)
            sudo apt-get update -qq
            sudo apt-get install -y -qq git
            ;;
        dnf)
            sudo dnf install -y -q git
            ;;
        yum)
            sudo yum install -y -q git
            ;;
        pacman)
            sudo pacman -Sy --noconfirm git
            ;;
        brew)
            brew install git
            ;;
        apk)
            sudo apk add --quiet git
            ;;
        *)
            error "Could not detect package manager. Please install git manually and re-run this script."
            ;;
    esac

    if command -v git &> /dev/null; then
        success "Git installed successfully"
    else
        error "Git installation failed. Please install git manually."
    fi
}

check_git() {
    if command -v git &> /dev/null; then
        local git_version=$(git --version | awk '{print $3}')
        success "Git is installed (version $git_version)"
        return 0
    else
        return 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN INSTALLATION
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    print_banner

    info "Starting n8n_nginx installation..."
    if [ "$BRANCH" != "main" ]; then
        info "Using branch: $BRANCH"
    fi
    echo ""

    # Check/install git
    if ! check_git; then
        warning "Git is not installed"
        local pkg_manager=$(detect_package_manager)
        info "Detected package manager: $pkg_manager"
        install_git "$pkg_manager"
    fi

    echo ""

    # Check if directory already exists
    if [ -d "$INSTALL_DIR" ]; then
        warning "Directory '$INSTALL_DIR' already exists"
        info "Updating existing installation..."
        cd "$INSTALL_DIR"
        git fetch origin
        git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" "origin/$BRANCH"
        git pull --ff-only || {
            warning "Could not update. You may have local changes."
            info "Continuing with existing files..."
        }
    else
        # Clone the repository
        info "Cloning repository..."
        git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
        success "Repository cloned successfully"
        cd "$INSTALL_DIR"
    fi

    echo ""

    # Make setup.sh executable and run it
    if [ -f "setup.sh" ]; then
        chmod +x setup.sh
        success "Repository ready"
        echo ""

        echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
        echo ""
        echo -e "${GREEN}${BOLD}Installation complete!${NC}"
        echo ""
        echo -e "To start setup, run:"
        echo ""
        echo -e "    ${YELLOW}cd $(pwd) && ./setup.sh${NC}"
        echo ""
        echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
    else
        error "setup.sh not found in repository. Installation may be incomplete."
    fi
}

# Run main function
main
