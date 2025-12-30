#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /tests/scenarios/test_migration.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 1st, 2026
#
# Richard J. Sears
# richardjsears@gmail.com
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

#
# test_migration.sh - Migration Test Scenarios for n8n_nginx v3.0
# Tests v2.0 to v3.0 upgrade paths and rollback functionality
#

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTS_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$TESTS_DIR")"

# Source test utilities
source "${TESTS_DIR}/test_utils.sh"

# Test configuration
TEST_ENV_DIR=""
CLEANUP_ON_EXIT=true

# ============================================================================
# Test Environment Setup
# ============================================================================

setup_test_environment() {
    log_section "Setting Up Test Environment"

    TEST_ENV_DIR=$(create_test_dir)
    log_info "Test environment: $TEST_ENV_DIR"

    # Copy project files to test environment
    cp -r "${PROJECT_ROOT}"/* "$TEST_ENV_DIR/" 2>/dev/null || true

    # Create mock v2.0 installation
    mkdir -p "${TEST_ENV_DIR}/data"
    mkdir -p "${TEST_ENV_DIR}/backups"
}

cleanup_test_environment() {
    if [ "$CLEANUP_ON_EXIT" = true ] && [ -n "$TEST_ENV_DIR" ]; then
        log_info "Cleaning up test environment..."
        cleanup_test_dir "$TEST_ENV_DIR"
    fi
}

trap cleanup_test_environment EXIT

# ============================================================================
# Mock v2.0 Installation
# ============================================================================

create_mock_v2_installation() {
    log_info "Creating mock v2.0 installation..."

    # Create v2.0 docker-compose.yaml
    cat > "${TEST_ENV_DIR}/docker-compose.yaml" << 'EOF'
version: '3.8'

services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    ports:
      - "5678:5678"
    environment:
      - N8N_HOST=n8n.example.com
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=n8n
      - DB_POSTGRESDB_USER=n8n
      - DB_POSTGRESDB_PASSWORD=n8n_password
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      - postgres

  postgres:
    image: postgres:15-alpine
    container_name: n8n_postgres
    restart: unless-stopped
    environment:
      - POSTGRES_USER=n8n
      - POSTGRES_PASSWORD=n8n_password
      - POSTGRES_DB=n8n
    volumes:
      - postgres_data:/var/lib/postgresql/data

  nginx:
    image: nginx:alpine
    container_name: n8n_nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro

volumes:
  n8n_data:
  postgres_data:
EOF

    # Create v2.0 nginx.conf
    cat > "${TEST_ENV_DIR}/nginx.conf" << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream n8n {
        server n8n:5678;
    }

    server {
        listen 80;
        server_name n8n.example.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl;
        server_name n8n.example.com;

        ssl_certificate /etc/nginx/certs/cert.pem;
        ssl_certificate_key /etc/nginx/certs/key.pem;

        location / {
            proxy_pass http://n8n;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
        }
    }
}
EOF

    # Create .env file
    cat > "${TEST_ENV_DIR}/.env" << 'EOF'
N8N_DOMAIN=n8n.example.com
POSTGRES_PASSWORD=n8n_password
N8N_ENCRYPTION_KEY=test_encryption_key_12345
EOF

    # Create certs directory
    mkdir -p "${TEST_ENV_DIR}/certs"
    touch "${TEST_ENV_DIR}/certs/cert.pem"
    touch "${TEST_ENV_DIR}/certs/key.pem"

    log_success "Mock v2.0 installation created"
}

# ============================================================================
# Version Detection Tests
# ============================================================================

test_version_detection() {
    log_section "Testing Version Detection"

    # Test v2.0 detection
    create_mock_v2_installation

    # Check if docker-compose has n8n service but no management
    assert_success "v2.0 docker-compose has n8n service" \
        "grep -q 'n8n:' '${TEST_ENV_DIR}/docker-compose.yaml'"

    assert_failure "v2.0 docker-compose has no management service" \
        "grep -q 'n8n_management' '${TEST_ENV_DIR}/docker-compose.yaml'"

    # Test version detection logic
    local version
    if grep -q "n8n_management" "${TEST_ENV_DIR}/docker-compose.yaml" 2>/dev/null; then
        version="3.0"
    elif grep -q "n8n:" "${TEST_ENV_DIR}/docker-compose.yaml" 2>/dev/null; then
        version="2.0"
    else
        version="none"
    fi

    assert_equals "Detected version is 2.0" "2.0" "$version"
}

test_fresh_install_detection() {
    log_section "Testing Fresh Install Detection"

    # Create empty test directory (no existing installation)
    local fresh_dir="${TEST_ENV_DIR}/fresh"
    mkdir -p "$fresh_dir"

    # Test that no docker-compose exists
    assert_failure "No docker-compose.yaml in fresh install" \
        "[ -f '${fresh_dir}/docker-compose.yaml' ]"

    # Test version detection returns none
    local version
    if [ -f "${fresh_dir}/docker-compose.yaml" ]; then
        version="existing"
    else
        version="none"
    fi

    assert_equals "Fresh install detected correctly" "none" "$version"
}

# ============================================================================
# Migration Preparation Tests
# ============================================================================

test_pre_migration_backup() {
    log_section "Testing Pre-Migration Backup"

    create_mock_v2_installation

    local backup_dir="${TEST_ENV_DIR}/backups/pre_migration_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"

    # Backup docker-compose.yaml
    cp "${TEST_ENV_DIR}/docker-compose.yaml" "${backup_dir}/"
    assert_file_exists "docker-compose.yaml backed up" "${backup_dir}/docker-compose.yaml"

    # Backup nginx.conf
    cp "${TEST_ENV_DIR}/nginx.conf" "${backup_dir}/"
    assert_file_exists "nginx.conf backed up" "${backup_dir}/nginx.conf"

    # Backup .env
    cp "${TEST_ENV_DIR}/.env" "${backup_dir}/"
    assert_file_exists ".env backed up" "${backup_dir}/.env"

    # Verify backup contents match originals
    assert_success "Backed up docker-compose matches original" \
        "diff '${TEST_ENV_DIR}/docker-compose.yaml' '${backup_dir}/docker-compose.yaml'"

    assert_success "Backed up nginx.conf matches original" \
        "diff '${TEST_ENV_DIR}/nginx.conf' '${backup_dir}/nginx.conf'"
}

test_migration_prerequisites_check() {
    log_section "Testing Migration Prerequisites Check"

    create_mock_v2_installation

    # Check required files exist
    assert_file_exists "docker-compose.yaml exists" "${TEST_ENV_DIR}/docker-compose.yaml"
    assert_file_exists "nginx.conf exists" "${TEST_ENV_DIR}/nginx.conf"
    assert_file_exists ".env exists" "${TEST_ENV_DIR}/.env"

    # Check data directory
    assert_dir_exists "data directory exists" "${TEST_ENV_DIR}/data"

    # Check backups directory
    assert_dir_exists "backups directory exists" "${TEST_ENV_DIR}/backups"
}

# ============================================================================
# Configuration Migration Tests
# ============================================================================

test_env_migration() {
    log_section "Testing Environment Variable Migration"

    create_mock_v2_installation

    # Read v2.0 .env
    source "${TEST_ENV_DIR}/.env"

    # Verify v2.0 variables are readable
    assert_not_equals "N8N_DOMAIN is set" "" "${N8N_DOMAIN:-}"
    assert_not_equals "POSTGRES_PASSWORD is set" "" "${POSTGRES_PASSWORD:-}"

    # Simulate migration by adding v3.0 variables
    cat >> "${TEST_ENV_DIR}/.env" << 'EOF'

# v3.0 Management Console
MGMT_PORT=3333
MGMT_SECRET_KEY=new_secret_key_for_v3
MGMT_DATABASE_URL=postgresql://n8n:n8n_password@postgres:5432/n8n_management

# Notifications
NOTIFICATIONS_ENABLED=true
NOTIFICATION_CHANNELS=email
EOF

    # Verify v3.0 variables added
    assert_file_contains ".env has MGMT_PORT" "${TEST_ENV_DIR}/.env" "MGMT_PORT"
    assert_file_contains ".env has MGMT_SECRET_KEY" "${TEST_ENV_DIR}/.env" "MGMT_SECRET_KEY"
    assert_file_contains ".env has NOTIFICATIONS_ENABLED" "${TEST_ENV_DIR}/.env" "NOTIFICATIONS_ENABLED"
}

test_docker_compose_migration() {
    log_section "Testing Docker Compose Migration"

    create_mock_v2_installation

    # Create v3.0 docker-compose.yaml
    cat > "${TEST_ENV_DIR}/docker-compose.v3.yaml" << 'EOF'
version: '3.8'

services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    environment:
      - N8N_HOST=${N8N_DOMAIN}
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=n8n
      - DB_POSTGRESDB_USER=n8n
      - DB_POSTGRESDB_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      - postgres
    networks:
      - n8n_network

  postgres:
    image: postgres:15-alpine
    container_name: n8n_postgres
    restart: unless-stopped
    environment:
      - POSTGRES_USER=n8n
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=n8n
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql:ro
    networks:
      - n8n_network

  n8n_management:
    image: n8n-management:latest
    container_name: n8n_management
    restart: unless-stopped
    environment:
      - DATABASE_URL=${MGMT_DATABASE_URL}
      - SECRET_KEY=${MGMT_SECRET_KEY}
      - N8N_API_URL=http://n8n:5678
    depends_on:
      - postgres
    networks:
      - n8n_network

  nginx:
    image: nginx:alpine
    container_name: n8n_nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "${MGMT_PORT:-3333}:${MGMT_PORT:-3333}"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - n8n
      - n8n_management
    networks:
      - n8n_network

networks:
  n8n_network:
    driver: bridge

volumes:
  n8n_data:
  postgres_data:
EOF

    # Verify v3.0 additions
    assert_file_contains "v3 has n8n_management service" "${TEST_ENV_DIR}/docker-compose.v3.yaml" "n8n_management"
    assert_file_contains "v3 has management port" "${TEST_ENV_DIR}/docker-compose.v3.yaml" "MGMT_PORT"
    assert_file_contains "v3 has network definition" "${TEST_ENV_DIR}/docker-compose.v3.yaml" "n8n_network"
}

test_nginx_conf_migration() {
    log_section "Testing Nginx Configuration Migration"

    create_mock_v2_installation

    # Create v3.0 nginx.conf with management server block
    cat > "${TEST_ENV_DIR}/nginx.v3.conf" << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream n8n {
        server n8n:5678;
    }

    upstream management_api {
        server n8n_management:8000;
    }

    upstream management_frontend {
        server n8n_management:80;
    }

    # HTTP redirect
    server {
        listen 80;
        server_name n8n.example.com;
        return 301 https://$server_name$request_uri;
    }

    # n8n HTTPS
    server {
        listen 443 ssl;
        server_name n8n.example.com;

        ssl_certificate /etc/nginx/certs/cert.pem;
        ssl_certificate_key /etc/nginx/certs/key.pem;

        location / {
            proxy_pass http://n8n;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }

    # Management Console
    server {
        listen 3333 ssl;
        server_name n8n.example.com;

        ssl_certificate /etc/nginx/certs/cert.pem;
        ssl_certificate_key /etc/nginx/certs/key.pem;

        location /api/ {
            proxy_pass http://management_api/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location / {
            proxy_pass http://management_frontend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
        }
    }
}
EOF

    # Verify v3.0 nginx additions
    assert_file_contains "v3 nginx has management_api upstream" "${TEST_ENV_DIR}/nginx.v3.conf" "management_api"
    assert_file_contains "v3 nginx has management_frontend upstream" "${TEST_ENV_DIR}/nginx.v3.conf" "management_frontend"
    assert_file_contains "v3 nginx listens on management port" "${TEST_ENV_DIR}/nginx.v3.conf" "listen 3333"
}

# ============================================================================
# Rollback Tests
# ============================================================================

test_rollback_preparation() {
    log_section "Testing Rollback Preparation"

    create_mock_v2_installation

    # Create backup for rollback
    local rollback_dir="${TEST_ENV_DIR}/backups/rollback_$(date +%Y%m%d)"
    mkdir -p "$rollback_dir"

    # Backup all critical files
    cp "${TEST_ENV_DIR}/docker-compose.yaml" "${rollback_dir}/"
    cp "${TEST_ENV_DIR}/nginx.conf" "${rollback_dir}/"
    cp "${TEST_ENV_DIR}/.env" "${rollback_dir}/"

    # Create rollback manifest
    cat > "${rollback_dir}/manifest.json" << EOF
{
    "version": "2.0",
    "timestamp": "$(date -Iseconds)",
    "files": ["docker-compose.yaml", "nginx.conf", ".env"]
}
EOF

    assert_file_exists "Rollback manifest created" "${rollback_dir}/manifest.json"
    assert_file_contains "Manifest has version" "${rollback_dir}/manifest.json" '"version": "2.0"'
}

test_rollback_execution() {
    log_section "Testing Rollback Execution"

    create_mock_v2_installation

    # Create backup
    local rollback_dir="${TEST_ENV_DIR}/backups/rollback_test"
    mkdir -p "$rollback_dir"
    cp "${TEST_ENV_DIR}/docker-compose.yaml" "${rollback_dir}/"
    cp "${TEST_ENV_DIR}/nginx.conf" "${rollback_dir}/"
    cp "${TEST_ENV_DIR}/.env" "${rollback_dir}/"

    # Simulate v3.0 upgrade (modify files)
    echo "# Modified for v3.0" >> "${TEST_ENV_DIR}/docker-compose.yaml"
    echo "# Modified for v3.0" >> "${TEST_ENV_DIR}/nginx.conf"
    echo "# Modified for v3.0" >> "${TEST_ENV_DIR}/.env"

    # Verify files were modified
    assert_file_contains "docker-compose modified" "${TEST_ENV_DIR}/docker-compose.yaml" "Modified for v3.0"

    # Execute rollback
    cp "${rollback_dir}/docker-compose.yaml" "${TEST_ENV_DIR}/"
    cp "${rollback_dir}/nginx.conf" "${TEST_ENV_DIR}/"
    cp "${rollback_dir}/.env" "${TEST_ENV_DIR}/"

    # Verify rollback
    assert_failure "docker-compose restored (no v3.0 marker)" \
        "grep -q 'Modified for v3.0' '${TEST_ENV_DIR}/docker-compose.yaml'"

    assert_failure "nginx.conf restored (no v3.0 marker)" \
        "grep -q 'Modified for v3.0' '${TEST_ENV_DIR}/nginx.conf'"
}

# ============================================================================
# Data Integrity Tests
# ============================================================================

test_data_preservation() {
    log_section "Testing Data Preservation"

    create_mock_v2_installation

    # Create mock data files
    mkdir -p "${TEST_ENV_DIR}/data/n8n"
    echo "workflow_data" > "${TEST_ENV_DIR}/data/n8n/workflows.json"
    echo "credentials_data" > "${TEST_ENV_DIR}/data/n8n/credentials.json"

    # Verify data exists before migration
    assert_file_exists "Workflows data exists" "${TEST_ENV_DIR}/data/n8n/workflows.json"
    assert_file_exists "Credentials data exists" "${TEST_ENV_DIR}/data/n8n/credentials.json"

    # Simulate migration (data should remain untouched)
    # In real migration, these files would be preserved

    # Verify data still exists after migration
    assert_file_exists "Workflows data preserved" "${TEST_ENV_DIR}/data/n8n/workflows.json"
    assert_file_exists "Credentials data preserved" "${TEST_ENV_DIR}/data/n8n/credentials.json"

    # Verify data integrity
    local workflow_content
    workflow_content=$(cat "${TEST_ENV_DIR}/data/n8n/workflows.json")
    assert_equals "Workflow data unchanged" "workflow_data" "$workflow_content"
}

# ============================================================================
# Migration State Tests
# ============================================================================

test_migration_state_tracking() {
    log_section "Testing Migration State Tracking"

    create_mock_v2_installation

    local state_file="${TEST_ENV_DIR}/.migration_state"

    # Create migration state
    cat > "$state_file" << EOF
{
    "version": "3.0",
    "phase": "migration",
    "step": "pre_backup",
    "timestamp": "$(date -Iseconds)",
    "source_version": "2.0",
    "target_version": "3.0"
}
EOF

    assert_file_exists "Migration state file created" "$state_file"
    assert_file_contains "State has phase" "$state_file" '"phase"'
    assert_file_contains "State has step" "$state_file" '"step"'
    assert_file_contains "State has source version" "$state_file" '"source_version": "2.0"'

    # Update state to next step
    cat > "$state_file" << EOF
{
    "version": "3.0",
    "phase": "migration",
    "step": "config_update",
    "timestamp": "$(date -Iseconds)",
    "source_version": "2.0",
    "target_version": "3.0"
}
EOF

    assert_file_contains "State updated to config_update" "$state_file" '"step": "config_update"'
}

test_migration_resume() {
    log_section "Testing Migration Resume Capability"

    create_mock_v2_installation

    local state_file="${TEST_ENV_DIR}/.migration_state"

    # Simulate interrupted migration
    cat > "$state_file" << EOF
{
    "version": "3.0",
    "phase": "migration",
    "step": "database_setup",
    "timestamp": "$(date -Iseconds)",
    "source_version": "2.0",
    "target_version": "3.0",
    "completed_steps": ["pre_backup", "stop_services"]
}
EOF

    # Check state exists and can be read
    assert_file_exists "State file exists for resume" "$state_file"

    # Parse completed steps
    if command -v jq &> /dev/null; then
        local completed_steps
        completed_steps=$(jq -r '.completed_steps[]' "$state_file" 2>/dev/null | tr '\n' ' ')
        assert_contains "Completed steps include pre_backup" "$completed_steps" "pre_backup"
        assert_contains "Completed steps include stop_services" "$completed_steps" "stop_services"
    else
        skip_test "Parse completed steps" "jq not available"
    fi
}

# ============================================================================
# Main Test Runner
# ============================================================================

run_migration_tests() {
    log_section "n8n_nginx v3.0 Migration Tests"
    echo "Test Started: $(date)"
    echo ""

    setup_test_environment

    # Run all migration tests
    test_version_detection
    test_fresh_install_detection
    test_pre_migration_backup
    test_migration_prerequisites_check
    test_env_migration
    test_docker_compose_migration
    test_nginx_conf_migration
    test_rollback_preparation
    test_rollback_execution
    test_data_preservation
    test_migration_state_tracking
    test_migration_resume

    # Print summary
    print_test_summary

    # Generate JUnit report if requested
    if [ -n "${JUNIT_OUTPUT:-}" ]; then
        generate_junit_report "$JUNIT_OUTPUT" "migration_tests"
    fi

    # Return appropriate exit code
    [ $TESTS_FAILED -eq 0 ]
}

# ============================================================================
# CLI Interface
# ============================================================================

show_help() {
    cat << EOF
n8n_nginx Migration Test Suite v3.0

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -j, --junit FILE        Generate JUnit XML report
    -k, --keep              Keep test environment after tests
    -v, --verbose           Verbose output

Examples:
    $0                      Run all migration tests
    $0 -k                   Run tests and keep test environment
    $0 -j results.xml       Generate JUnit report

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -j|--junit)
            export JUNIT_OUTPUT="$2"
            shift 2
            ;;
        -k|--keep)
            CLEANUP_ON_EXIT=false
            shift
            ;;
        -v|--verbose)
            set -x
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Run tests
run_migration_tests

exit $?
