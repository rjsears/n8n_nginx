# Integration Agent Prompt - n8n Management System v3.0

## Role and Expertise
You are a QA/Integration Engineer specializing in end-to-end testing, shell scripting, migration strategies, and system integration. You have deep expertise in bash scripting, Docker orchestration, database migrations, and creating robust installation workflows.

## Project Context

### System Overview
- **Current Version**: v2.0 with n8n, PostgreSQL, nginx, certbot
- **Target Version**: v3.0 adds management container, backup system, notifications, optional tunneling
- **Installation**: Interactive setup.sh script
- **Access**: Management at `https://{domain}:{port}` (default port 3333)

### Critical Requirements
1. **Seamless v2→v3 migration** with rollback capability (30 days)
2. **Zero data loss** during migration
3. **Backward compatible** setup.sh that handles both fresh installs and upgrades
4. **Resume capability** for interrupted setup operations
5. **Comprehensive testing** of all integration points

---

## Assigned Tasks

### Task 1: Enhance setup.sh for v3.0

Modify `/home/user/n8n_nginx/setup.sh` to add the following sections:

**State Management for Resume Capability:**
```bash
STATE_FILE=".n8n_setup_state"

save_state() {
    local phase=$1
    local step=$2
    cat > "$STATE_FILE" << EOF
{
    "version": "3.0",
    "phase": "$phase",
    "step": "$step",
    "timestamp": "$(date -Iseconds)",
    "domain": "$DOMAIN",
    "mgmt_port": "$MGMT_PORT",
    "nfs_configured": "$NFS_CONFIGURED",
    "notifications_configured": "$NOTIFICATIONS_CONFIGURED"
}
EOF
}

load_state() {
    if [ -f "$STATE_FILE" ]; then
        # Parse JSON state file
        SAVED_PHASE=$(jq -r '.phase' "$STATE_FILE" 2>/dev/null)
        SAVED_STEP=$(jq -r '.step' "$STATE_FILE" 2>/dev/null)
        SAVED_DOMAIN=$(jq -r '.domain' "$STATE_FILE" 2>/dev/null)
        return 0
    fi
    return 1
}

check_resume() {
    if load_state; then
        print_warning "Previous installation detected at phase: $SAVED_PHASE, step: $SAVED_STEP"
        if confirm_prompt "Would you like to resume from where you left off?"; then
            return 0  # Resume
        fi
    fi
    return 1  # Start fresh
}
```

**Version Detection:**
```bash
detect_current_version() {
    if [ -f "docker-compose.yaml" ]; then
        if grep -q "n8n_management" docker-compose.yaml; then
            echo "3.0"
        elif grep -q "n8n:" docker-compose.yaml; then
            echo "2.0"
        else
            echo "unknown"
        fi
    else
        echo "none"
    fi
}

handle_upgrade() {
    local current_version=$(detect_current_version)

    case $current_version in
        "3.0")
            print_info "Version 3.0 detected. Running configuration update..."
            run_config_update
            ;;
        "2.0")
            print_header "UPGRADE: v2.0 → v3.0"
            if confirm_prompt "Upgrade from v2.0 to v3.0?"; then
                run_migration_v2_to_v3
            fi
            ;;
        "none")
            print_info "Fresh installation detected"
            run_fresh_install
            ;;
        *)
            print_error "Unknown version detected. Manual intervention required."
            exit 1
            ;;
    esac
}
```

**Management Port Configuration:**
```bash
configure_management_port() {
    print_section "Management Interface Configuration"

    local default_port=3333

    while true; do
        echo ""
        read -p "$(echo -e "${CYAN}Management interface port${NC} [${default_port}]: ")" mgmt_port
        mgmt_port=${mgmt_port:-$default_port}

        # Validate port number
        if ! [[ "$mgmt_port" =~ ^[0-9]+$ ]]; then
            print_error "Invalid port number"
            continue
        fi

        if [ "$mgmt_port" -lt 1024 ] || [ "$mgmt_port" -gt 65535 ]; then
            print_error "Port must be between 1024 and 65535"
            continue
        fi

        # Check reserved ports
        local reserved_ports="80 443 5432 5678 8080 8443"
        if echo "$reserved_ports" | grep -qw "$mgmt_port"; then
            print_error "Port $mgmt_port is reserved for other services"
            continue
        fi

        # Check if port is in use
        if ss -tuln 2>/dev/null | grep -q ":${mgmt_port} "; then
            print_error "Port $mgmt_port is already in use"
            continue
        fi

        break
    done

    MGMT_PORT=$mgmt_port
    print_success "Management interface will be available at https://${DOMAIN}:${MGMT_PORT}"
}
```

**NFS Configuration Section:**
```bash
configure_nfs() {
    print_section "NFS Backup Storage Configuration"

    echo ""
    echo "NFS storage allows centralized backup storage on a remote server."
    echo "If you skip this, backups will be stored locally in the container."
    echo ""

    if ! confirm_prompt "Configure NFS for backup storage?"; then
        NFS_CONFIGURED="false"
        print_info "Skipping NFS configuration. Backups will be stored locally."
        return
    fi

    # Check NFS client
    if ! command -v showmount &> /dev/null; then
        print_warning "NFS client not installed. Installing..."
        apt-get update && apt-get install -y nfs-common
    fi

    # Get NFS server
    while true; do
        read -p "NFS server address (e.g., 192.168.1.100 or nfs.example.com): " nfs_server

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

    # Show available exports
    echo ""
    print_info "Available NFS exports:"
    showmount -e "$nfs_server" | tail -n +2

    # Get export path
    read -p "NFS export path (e.g., /mnt/backups): " nfs_path

    # Test mount
    print_info "Testing NFS mount..."
    local test_mount="/tmp/nfs_test_$$"
    mkdir -p "$test_mount"

    if mount -t nfs -o ro,nolock,soft,timeo=10 "${nfs_server}:${nfs_path}" "$test_mount" 2>/dev/null; then
        print_success "NFS mount successful"
        umount "$test_mount"
        rmdir "$test_mount"

        NFS_SERVER="$nfs_server"
        NFS_PATH="$nfs_path"
        NFS_CONFIGURED="true"

        save_state "nfs" "complete"
    else
        print_error "Failed to mount NFS share"
        if confirm_prompt "Continue without NFS?"; then
            NFS_CONFIGURED="false"
        else
            exit 1
        fi
    fi
}
```

**Notification Configuration Section:**
```bash
configure_notifications() {
    print_section "Notification System Configuration"

    echo ""
    echo "The notification system can alert you about backups, container issues, and more."
    echo "You can configure this later through the management interface."
    echo ""

    if ! confirm_prompt "Configure notifications now?"; then
        NOTIFICATIONS_CONFIGURED="false"
        print_info "Skipping notification setup. Configure later in the management UI."
        return
    fi

    echo ""
    echo "Select notification method:"
    echo "  1) Email (SMTP)"
    echo "  2) Slack"
    echo "  3) Discord"
    echo "  4) NTFY (Push notifications)"
    echo "  5) Skip for now"
    echo ""

    read -p "Choice [1-5]: " notif_choice

    case $notif_choice in
        1)
            configure_email_notifications
            ;;
        2)
            configure_slack_notifications
            ;;
        3)
            configure_discord_notifications
            ;;
        4)
            configure_ntfy_notifications
            ;;
        *)
            print_info "Skipping notification setup"
            NOTIFICATIONS_CONFIGURED="false"
            return
            ;;
    esac

    NOTIFICATIONS_CONFIGURED="true"
    save_state "notifications" "complete"
}

configure_email_notifications() {
    echo ""
    echo "Email Provider Options:"
    echo "  1) Gmail Corporate Relay (IP whitelisted, no password)"
    echo "  2) Gmail with App Password"
    echo "  3) Custom SMTP server"
    echo ""

    read -p "Email provider [1-3]: " email_provider

    case $email_provider in
        1)
            EMAIL_PROVIDER="gmail_relay"
            EMAIL_HOST="smtp-relay.gmail.com"
            EMAIL_PORT="587"
            read -p "From email address: " EMAIL_FROM
            echo ""
            print_warning "Ensure your server's IP is whitelisted in Google Admin Console"
            ;;
        2)
            EMAIL_PROVIDER="gmail_app_password"
            EMAIL_HOST="smtp.gmail.com"
            EMAIL_PORT="587"
            read -p "Gmail address: " EMAIL_FROM
            read -sp "App Password (from Google Account settings): " EMAIL_PASSWORD
            echo ""
            ;;
        3)
            EMAIL_PROVIDER="smtp"
            read -p "SMTP host: " EMAIL_HOST
            read -p "SMTP port [587]: " EMAIL_PORT
            EMAIL_PORT=${EMAIL_PORT:-587}
            read -p "Username: " EMAIL_USER
            read -sp "Password: " EMAIL_PASSWORD
            echo ""
            read -p "From email: " EMAIL_FROM
            ;;
    esac

    # Test email
    if confirm_prompt "Send a test email?"; then
        read -p "Test recipient email: " test_email
        # Test will be performed after management container is running
        TEST_EMAIL_RECIPIENT="$test_email"
    fi
}
```

**Optional Services Configuration:**
```bash
configure_optional_services() {
    print_section "Optional Services"

    # Cloudflare Tunnel
    echo ""
    echo "Cloudflare Tunnel provides secure external access without opening ports."

    if confirm_prompt "Configure Cloudflare Tunnel?"; then
        configure_cloudflare_tunnel
    fi

    # Tailscale
    echo ""
    echo "Tailscale provides VPN-based access to your services."

    if confirm_prompt "Configure Tailscale?"; then
        configure_tailscale
    fi

    # Portainer
    echo ""
    echo "Portainer provides a web UI for Docker management."

    if confirm_prompt "Install Portainer?"; then
        configure_portainer
    fi
}

configure_cloudflare_tunnel() {
    echo ""
    echo "To use Cloudflare Tunnel, you need a tunnel token from the Cloudflare dashboard."
    echo "Visit: https://dash.cloudflare.com → Zero Trust → Access → Tunnels"
    echo ""

    read -p "Cloudflare Tunnel Token: " cf_token

    if [ -n "$cf_token" ]; then
        CLOUDFLARE_TUNNEL_TOKEN="$cf_token"
        CLOUDFLARE_ENABLED="true"
        print_success "Cloudflare Tunnel configured"
    else
        CLOUDFLARE_ENABLED="false"
    fi
}

configure_portainer() {
    # Check for existing Portainer
    if docker ps -a --format '{{.Names}}' | grep -q "portainer"; then
        print_info "Existing Portainer installation detected"

        if confirm_prompt "Install Portainer Agent instead of full Portainer?"; then
            PORTAINER_MODE="agent"
        else
            print_info "Skipping Portainer - using existing installation"
            PORTAINER_MODE="skip"
        fi
    else
        echo ""
        echo "Portainer options:"
        echo "  1) Portainer CE (Full installation)"
        echo "  2) Portainer Agent (Connect to existing Portainer)"
        echo "  3) Skip"
        echo ""

        read -p "Choice [1-3]: " portainer_choice

        case $portainer_choice in
            1) PORTAINER_MODE="full" ;;
            2) PORTAINER_MODE="agent" ;;
            *) PORTAINER_MODE="skip" ;;
        esac
    fi
}
```

**Admin User Creation:**
```bash
create_admin_user() {
    print_section "Management Admin User"

    echo ""
    echo "Create the admin user for the management interface."
    echo ""

    read -p "Admin username [admin]: " admin_user
    admin_user=${admin_user:-admin}

    while true; do
        read -sp "Admin password: " admin_pass
        echo ""
        read -sp "Confirm password: " admin_pass_confirm
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

    # Store for later use (will be hashed by the management container)
    ADMIN_USER="$admin_user"
    ADMIN_PASS="$admin_pass"

    # Optional email
    read -p "Admin email (optional, for notifications): " admin_email
    ADMIN_EMAIL="$admin_email"
}
```

---

### Task 2: v2.0 to v3.0 Migration Script

Create migration logic within setup.sh:

```bash
run_migration_v2_to_v3() {
    print_header "Migration: v2.0 → v3.0"

    # Phase 1: Pre-migration backup
    print_section "Phase 1: Pre-Migration Backup"
    save_state "migration" "backup"

    print_info "Creating complete backup before migration..."

    # Backup docker-compose.yaml
    cp docker-compose.yaml docker-compose.yaml.v2.backup

    # Backup nginx.conf
    cp nginx.conf nginx.conf.v2.backup

    # Backup PostgreSQL database
    print_info "Backing up PostgreSQL database..."
    docker exec n8n_postgres pg_dump -U n8n -d n8n -F c -f /tmp/n8n_pre_migration.dump

    # Copy dump out of container
    docker cp n8n_postgres:/tmp/n8n_pre_migration.dump ./backups/n8n_pre_migration_$(date +%Y%m%d_%H%M%S).dump

    print_success "Pre-migration backup complete"

    # Phase 2: Stop services
    print_section "Phase 2: Stopping Services"
    save_state "migration" "stop_services"

    print_info "Stopping n8n services..."
    docker-compose stop n8n
    docker-compose stop nginx

    # Phase 3: Database preparation
    print_section "Phase 3: Database Preparation"
    save_state "migration" "database"

    print_info "Creating management database..."
    docker exec n8n_postgres psql -U n8n -c "CREATE DATABASE n8n_management;" 2>/dev/null || true
    docker exec n8n_postgres psql -U n8n -c "CREATE USER n8n_mgmt WITH PASSWORD '${MGMT_DB_PASSWORD}';" 2>/dev/null || true
    docker exec n8n_postgres psql -U n8n -c "GRANT ALL PRIVILEGES ON DATABASE n8n_management TO n8n_mgmt;"

    print_success "Management database created"

    # Phase 4: Update configuration files
    print_section "Phase 4: Updating Configuration"
    save_state "migration" "config"

    # Generate new docker-compose.yaml with management services
    generate_docker_compose_v3

    # Update nginx.conf with management port
    generate_nginx_conf_v3

    # Phase 5: Build and start new services
    print_section "Phase 5: Starting v3.0 Services"
    save_state "migration" "start_services"

    print_info "Building management container..."
    docker-compose build n8n_management

    print_info "Starting all services..."
    docker-compose up -d

    # Wait for services to be healthy
    wait_for_services

    # Phase 6: Verification
    print_section "Phase 6: Verification"
    save_state "migration" "verify"

    if verify_migration; then
        print_success "Migration completed successfully!"

        # Record migration for rollback window
        cat > .migration_state << EOF
{
    "migrated_at": "$(date -Iseconds)",
    "from_version": "2.0",
    "to_version": "3.0",
    "rollback_available_until": "$(date -d '+30 days' -Iseconds)",
    "backup_files": [
        "docker-compose.yaml.v2.backup",
        "nginx.conf.v2.backup",
        "backups/n8n_pre_migration_*.dump"
    ]
}
EOF

        echo ""
        print_info "Management interface: https://${DOMAIN}:${MGMT_PORT}"
        print_info "Rollback available for 30 days if needed"

        # Clear setup state
        rm -f "$STATE_FILE"
    else
        print_error "Migration verification failed!"
        if confirm_prompt "Rollback to v2.0?"; then
            rollback_to_v2
        fi
    fi
}

verify_migration() {
    local all_ok=true

    # Check all containers are running
    for container in n8n n8n_postgres n8n_nginx n8n_management; do
        if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            print_error "Container $container is not running"
            all_ok=false
        fi
    done

    # Check n8n is responding
    if ! curl -sf "http://localhost:5678/healthz" > /dev/null 2>&1; then
        print_error "n8n health check failed"
        all_ok=false
    fi

    # Check management API is responding
    if ! curl -sf "http://localhost:${MGMT_PORT}/api/health" > /dev/null 2>&1; then
        print_error "Management API health check failed"
        all_ok=false
    fi

    # Check PostgreSQL
    if ! docker exec n8n_postgres pg_isready -U n8n > /dev/null 2>&1; then
        print_error "PostgreSQL health check failed"
        all_ok=false
    fi

    $all_ok
}

rollback_to_v2() {
    print_header "Rolling Back to v2.0"

    print_info "Stopping v3.0 services..."
    docker-compose down

    print_info "Restoring v2.0 configuration..."
    mv docker-compose.yaml.v2.backup docker-compose.yaml
    mv nginx.conf.v2.backup nginx.conf

    print_info "Starting v2.0 services..."
    docker-compose up -d

    print_success "Rollback complete. System restored to v2.0"
}
```

---

### Task 3: End-to-End Test Suite

Create test scripts in `/home/user/n8n_nginx/tests/`:

**tests/test_installation.sh:**
```bash
#!/bin/bash
set -e

# Test suite for n8n Management System v3.0

source "$(dirname "$0")/test_utils.sh"

TESTS_PASSED=0
TESTS_FAILED=0

# ===================
# Container Tests
# ===================

test_containers_running() {
    describe "All containers should be running"

    local containers=("n8n" "n8n_postgres" "n8n_nginx" "n8n_management")

    for container in "${containers[@]}"; do
        if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            pass "Container $container is running"
        else
            fail "Container $container is NOT running"
        fi
    done
}

test_container_health() {
    describe "All containers should be healthy"

    # PostgreSQL
    if docker exec n8n_postgres pg_isready -U n8n > /dev/null 2>&1; then
        pass "PostgreSQL is ready"
    else
        fail "PostgreSQL is not ready"
    fi

    # n8n
    if curl -sf "http://localhost:5678/healthz" > /dev/null 2>&1; then
        pass "n8n is healthy"
    else
        fail "n8n health check failed"
    fi

    # Management API
    local mgmt_port=${MGMT_PORT:-3333}
    if curl -sf "http://localhost:${mgmt_port}/api/health" > /dev/null 2>&1; then
        pass "Management API is healthy"
    else
        fail "Management API health check failed"
    fi
}

# ===================
# API Tests
# ===================

test_auth_endpoints() {
    describe "Authentication endpoints should work"

    local mgmt_url="http://localhost:${MGMT_PORT:-3333}"

    # Login should reject invalid credentials
    local response=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "${mgmt_url}/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"username":"invalid","password":"invalid"}')

    if [ "$response" = "401" ]; then
        pass "Login rejects invalid credentials (401)"
    else
        fail "Login should return 401 for invalid credentials, got $response"
    fi

    # Login with valid credentials
    local login_response=$(curl -s -X POST "${mgmt_url}/api/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"${TEST_ADMIN_USER}\",\"password\":\"${TEST_ADMIN_PASS}\"}")

    if echo "$login_response" | grep -q "token"; then
        pass "Login accepts valid credentials"
        export AUTH_TOKEN=$(echo "$login_response" | jq -r '.token')
    else
        fail "Login failed with valid credentials"
    fi
}

test_backup_endpoints() {
    describe "Backup API endpoints should work"

    local mgmt_url="http://localhost:${MGMT_PORT:-3333}"

    # List backups (requires auth)
    local response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        "${mgmt_url}/api/backups/history")

    if [ "$response" = "200" ]; then
        pass "GET /api/backups/history returns 200"
    else
        fail "GET /api/backups/history returned $response"
    fi

    # List schedules
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        "${mgmt_url}/api/backups/schedules")

    if [ "$response" = "200" ]; then
        pass "GET /api/backups/schedules returns 200"
    else
        fail "GET /api/backups/schedules returned $response"
    fi
}

test_container_endpoints() {
    describe "Container API endpoints should work"

    local mgmt_url="http://localhost:${MGMT_PORT:-3333}"

    # List containers
    local response=$(curl -s \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        "${mgmt_url}/api/containers")

    if echo "$response" | grep -q "n8n"; then
        pass "GET /api/containers returns container list"
    else
        fail "GET /api/containers did not return expected data"
    fi

    # Container stats
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        "${mgmt_url}/api/containers/stats")

    if [ "$response" = "200" ]; then
        pass "GET /api/containers/stats returns 200"
    else
        fail "GET /api/containers/stats returned $response"
    fi
}

# ===================
# Backup Tests
# ===================

test_backup_execution() {
    describe "Backup should execute successfully"

    local mgmt_url="http://localhost:${MGMT_PORT:-3333}"

    # Trigger manual backup
    local response=$(curl -s -X POST \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{"backup_type": "postgres_n8n"}' \
        "${mgmt_url}/api/backups/run")

    if echo "$response" | grep -q "id"; then
        pass "Manual backup triggered successfully"
        local backup_id=$(echo "$response" | jq -r '.id')

        # Wait for backup to complete (max 60 seconds)
        local attempts=0
        while [ $attempts -lt 12 ]; do
            sleep 5
            local status=$(curl -s \
                -H "Authorization: Bearer ${AUTH_TOKEN}" \
                "${mgmt_url}/api/backups/history/${backup_id}" | jq -r '.status')

            if [ "$status" = "success" ]; then
                pass "Backup completed successfully"
                return
            elif [ "$status" = "failed" ]; then
                fail "Backup failed"
                return
            fi

            attempts=$((attempts + 1))
        done

        fail "Backup did not complete within timeout"
    else
        fail "Failed to trigger manual backup"
    fi
}

# ===================
# NFS Tests (if configured)
# ===================

test_nfs_connection() {
    describe "NFS connection should work (if configured)"

    # Check if NFS is configured
    if docker exec n8n_management cat /app/config/nfs_status.json 2>/dev/null | grep -q '"status": "connected"'; then
        pass "NFS is connected"

        # Test write capability
        if docker exec n8n_management touch /mnt/backups/.test_write 2>/dev/null; then
            docker exec n8n_management rm /mnt/backups/.test_write
            pass "NFS is writable"
        else
            fail "NFS is not writable"
        fi
    else
        skip "NFS is not configured"
    fi
}

# ===================
# Notification Tests
# ===================

test_notification_service() {
    describe "Notification service should work"

    local mgmt_url="http://localhost:${MGMT_PORT:-3333}"

    # Create a test webhook service
    local response=$(curl -s -X POST \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{
            "name": "Test Webhook",
            "service_type": "webhook",
            "config": {"url": "https://httpbin.org/post", "method": "POST"}
        }' \
        "${mgmt_url}/api/notifications/services")

    if echo "$response" | grep -q "id"; then
        pass "Notification service created"
        local service_id=$(echo "$response" | jq -r '.id')

        # Test the service
        local test_response=$(curl -s -X POST \
            -H "Authorization: Bearer ${AUTH_TOKEN}" \
            "${mgmt_url}/api/notifications/services/${service_id}/test")

        if echo "$test_response" | grep -q '"status": "success"'; then
            pass "Notification test succeeded"
        else
            warn "Notification test may have failed (external service)"
        fi

        # Cleanup
        curl -s -X DELETE \
            -H "Authorization: Bearer ${AUTH_TOKEN}" \
            "${mgmt_url}/api/notifications/services/${service_id}" > /dev/null

    else
        fail "Failed to create notification service"
    fi
}

# ===================
# Run All Tests
# ===================

run_tests() {
    echo "========================================"
    echo "  n8n Management System v3.0 Tests"
    echo "========================================"
    echo ""

    test_containers_running
    test_container_health
    test_auth_endpoints
    test_backup_endpoints
    test_container_endpoints
    test_backup_execution
    test_nfs_connection
    test_notification_service

    echo ""
    echo "========================================"
    echo "  Results: $TESTS_PASSED passed, $TESTS_FAILED failed"
    echo "========================================"

    if [ $TESTS_FAILED -gt 0 ]; then
        exit 1
    fi
}

# Test utilities
describe() { echo -e "\n\033[1m$1\033[0m"; }
pass() { echo -e "  \033[32m✓\033[0m $1"; TESTS_PASSED=$((TESTS_PASSED + 1)); }
fail() { echo -e "  \033[31m✗\033[0m $1"; TESTS_FAILED=$((TESTS_FAILED + 1)); }
skip() { echo -e "  \033[33m○\033[0m $1 (skipped)"; }
warn() { echo -e "  \033[33m!\033[0m $1"; }

run_tests
```

---

### Task 4: Integration Test Scenarios

Create comprehensive test scenarios:

**tests/scenarios/test_migration.sh:**
```bash
#!/bin/bash
# Test v2.0 to v3.0 migration

set -e
source "$(dirname "$0")/../test_utils.sh"

echo "=== Migration Test Scenario ==="

# Setup: Create v2.0 environment
setup_v2_environment() {
    echo "Setting up v2.0 test environment..."

    # Use v2 docker-compose
    cp fixtures/docker-compose.v2.yaml docker-compose.yaml
    cp fixtures/nginx.v2.conf nginx.conf

    # Start services
    docker-compose up -d

    # Wait for services
    sleep 30

    # Create test data in n8n
    create_test_workflows 5
}

# Test: Run migration
test_migration() {
    echo "Running migration..."

    # Run migration (non-interactive)
    ./setup.sh --migrate --non-interactive \
        --mgmt-port 3333 \
        --admin-user testadmin \
        --admin-pass testpass123

    # Verify migration
    verify_all_containers_running
    verify_n8n_workflows_intact
    verify_management_api_accessible
}

# Test: Rollback
test_rollback() {
    echo "Testing rollback capability..."

    ./setup.sh --rollback

    # Verify v2.0 is restored
    verify_v2_configuration
    verify_n8n_workflows_intact
}

# Cleanup
cleanup() {
    docker-compose down -v
    rm -f docker-compose.yaml nginx.conf
}

trap cleanup EXIT

setup_v2_environment
test_migration
test_rollback

echo "=== Migration Test Passed ==="
```

**tests/scenarios/test_backup_restore.sh:**
```bash
#!/bin/bash
# Test backup and restore functionality

set -e

echo "=== Backup/Restore Test Scenario ==="

# Create test workflow
echo "Creating test workflow..."
WORKFLOW_ID=$(create_test_workflow "Test Workflow $(date +%s)")

# Run backup
echo "Running backup..."
BACKUP_ID=$(trigger_backup "postgres_n8n")
wait_for_backup_complete $BACKUP_ID

# Delete workflow
echo "Deleting test workflow..."
delete_workflow $WORKFLOW_ID

# Verify workflow is gone
if workflow_exists $WORKFLOW_ID; then
    echo "ERROR: Workflow should be deleted"
    exit 1
fi

# Restore from backup
echo "Restoring workflow from backup..."
restore_flow_from_backup $BACKUP_ID $WORKFLOW_ID

# Verify workflow is restored
if workflow_exists $WORKFLOW_ID; then
    echo "SUCCESS: Workflow restored successfully"
else
    echo "ERROR: Workflow restoration failed"
    exit 1
fi

echo "=== Backup/Restore Test Passed ==="
```

---

### Task 5: Health Check Script

**scripts/health_check.sh:**
```bash
#!/bin/bash
# Comprehensive health check for n8n Management System

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

MGMT_PORT=${MGMT_PORT:-3333}
ISSUES=0

check() {
    local name=$1
    local cmd=$2

    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name"
        return 0
    else
        echo -e "${RED}✗${NC} $name"
        ISSUES=$((ISSUES + 1))
        return 1
    fi
}

warn() {
    local name=$1
    local cmd=$2

    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name"
    else
        echo -e "${YELLOW}!${NC} $name (warning)"
    fi
}

echo "================================"
echo "  n8n System Health Check"
echo "================================"
echo ""

echo "--- Containers ---"
check "n8n container running" "docker ps | grep -q n8n_n8n"
check "PostgreSQL container running" "docker ps | grep -q n8n_postgres"
check "Nginx container running" "docker ps | grep -q n8n_nginx"
check "Management container running" "docker ps | grep -q n8n_management"

echo ""
echo "--- Services ---"
check "PostgreSQL accepting connections" "docker exec n8n_postgres pg_isready -U n8n"
check "n8n API responding" "curl -sf http://localhost:5678/healthz"
check "Management API responding" "curl -sf http://localhost:${MGMT_PORT}/api/health"
check "Nginx responding on 443" "curl -sf -k https://localhost/"

echo ""
echo "--- Storage ---"
check "n8n data volume exists" "docker volume inspect n8n_data"
check "PostgreSQL data volume exists" "docker volume inspect postgres_data"
warn "NFS connected" "docker exec n8n_management cat /app/config/nfs_status.json 2>/dev/null | grep -q connected"

echo ""
echo "--- Database ---"
check "n8n database accessible" "docker exec n8n_postgres psql -U n8n -d n8n -c 'SELECT 1'"
check "Management database accessible" "docker exec n8n_postgres psql -U n8n -d n8n_management -c 'SELECT 1'"

echo ""
echo "--- Disk Space ---"
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo -e "${GREEN}✓${NC} Disk usage: ${DISK_USAGE}%"
elif [ "$DISK_USAGE" -lt 90 ]; then
    echo -e "${YELLOW}!${NC} Disk usage: ${DISK_USAGE}% (warning)"
else
    echo -e "${RED}✗${NC} Disk usage: ${DISK_USAGE}% (critical)"
    ISSUES=$((ISSUES + 1))
fi

echo ""
echo "================================"
if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}All checks passed${NC}"
    exit 0
else
    echo -e "${RED}$ISSUES issue(s) found${NC}"
    exit 1
fi
```

---

## Dependencies on Other Agents

- **DevOps Agent**: Provides container configurations to test
- **Backend Agent**: Provides API endpoints to test
- **Frontend Agent**: UI will use tested APIs

---

## File Deliverables Checklist

- [ ] Updated `/home/user/n8n_nginx/setup.sh` with v3.0 sections
- [ ] `/home/user/n8n_nginx/tests/test_installation.sh`
- [ ] `/home/user/n8n_nginx/tests/test_utils.sh`
- [ ] `/home/user/n8n_nginx/tests/scenarios/test_migration.sh`
- [ ] `/home/user/n8n_nginx/tests/scenarios/test_backup_restore.sh`
- [ ] `/home/user/n8n_nginx/scripts/health_check.sh`
- [ ] `/home/user/n8n_nginx/scripts/rollback.sh`
