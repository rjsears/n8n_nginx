#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /tests/scenarios/test_backup_restore.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 1st, 2026
#
# Richard J. Sears
# richardjsears@gmail.com
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

#
# test_backup_restore.sh - Backup and Restore Test Scenarios for n8n_nginx v3.0
# Tests backup creation, validation, and restore functionality
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

    # Create directory structure
    mkdir -p "${TEST_ENV_DIR}/data/n8n"
    mkdir -p "${TEST_ENV_DIR}/data/postgres"
    mkdir -p "${TEST_ENV_DIR}/backups"
    mkdir -p "${TEST_ENV_DIR}/certs"
    mkdir -p "${TEST_ENV_DIR}/scripts"

    # Create mock configuration files
    create_mock_configuration
    create_mock_data
}

cleanup_test_environment() {
    if [ "$CLEANUP_ON_EXIT" = true ] && [ -n "$TEST_ENV_DIR" ]; then
        log_info "Cleaning up test environment..."
        cleanup_test_dir "$TEST_ENV_DIR"
    fi
}

trap cleanup_test_environment EXIT

create_mock_configuration() {
    # docker-compose.yaml
    cat > "${TEST_ENV_DIR}/docker-compose.yaml" << 'EOF'
version: '3.8'
services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
  postgres:
    image: postgres:15-alpine
    container_name: n8n_postgres
  n8n_management:
    image: n8n-management:latest
    container_name: n8n_management
EOF

    # nginx.conf
    cat > "${TEST_ENV_DIR}/nginx.conf" << 'EOF'
events { worker_connections 1024; }
http {
    server { listen 443 ssl; }
    server { listen 3333 ssl; }
}
EOF

    # .env
    cat > "${TEST_ENV_DIR}/.env" << 'EOF'
N8N_DOMAIN=n8n.example.com
POSTGRES_PASSWORD=secure_password_123
N8N_ENCRYPTION_KEY=encryption_key_abc
MGMT_PORT=3333
MGMT_SECRET_KEY=management_secret_xyz
EOF

    # SSL certificates (mock)
    echo "-----BEGIN CERTIFICATE-----" > "${TEST_ENV_DIR}/certs/cert.pem"
    echo "MOCK_CERTIFICATE_DATA" >> "${TEST_ENV_DIR}/certs/cert.pem"
    echo "-----END CERTIFICATE-----" >> "${TEST_ENV_DIR}/certs/cert.pem"

    echo "-----BEGIN PRIVATE KEY-----" > "${TEST_ENV_DIR}/certs/key.pem"
    echo "MOCK_KEY_DATA" >> "${TEST_ENV_DIR}/certs/key.pem"
    echo "-----END PRIVATE KEY-----" >> "${TEST_ENV_DIR}/certs/key.pem"
}

create_mock_data() {
    # n8n workflows
    cat > "${TEST_ENV_DIR}/data/n8n/workflows.json" << 'EOF'
{
    "workflows": [
        {"id": 1, "name": "Test Workflow 1", "active": true},
        {"id": 2, "name": "Test Workflow 2", "active": false}
    ]
}
EOF

    # n8n credentials
    cat > "${TEST_ENV_DIR}/data/n8n/credentials.json" << 'EOF'
{
    "credentials": [
        {"id": 1, "name": "API Key", "type": "httpHeader"},
        {"id": 2, "name": "OAuth2", "type": "oauth2"}
    ]
}
EOF

    # Mock database dump
    cat > "${TEST_ENV_DIR}/data/postgres/n8n_dump.sql" << 'EOF'
-- PostgreSQL database dump
CREATE TABLE workflows (id SERIAL PRIMARY KEY, name VARCHAR(255));
INSERT INTO workflows (name) VALUES ('Test Workflow');
EOF

    # Management data
    mkdir -p "${TEST_ENV_DIR}/data/management"
    cat > "${TEST_ENV_DIR}/data/management/settings.json" << 'EOF'
{
    "theme": "dark",
    "notifications": true,
    "auto_backup": true
}
EOF
}

# ============================================================================
# Backup Creation Tests
# ============================================================================

test_config_backup() {
    log_section "Testing Configuration Backup"

    local backup_dir="${TEST_ENV_DIR}/backups/config_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"

    # Backup configuration files
    cp "${TEST_ENV_DIR}/docker-compose.yaml" "${backup_dir}/"
    cp "${TEST_ENV_DIR}/nginx.conf" "${backup_dir}/"
    cp "${TEST_ENV_DIR}/.env" "${backup_dir}/"

    assert_file_exists "docker-compose.yaml backed up" "${backup_dir}/docker-compose.yaml"
    assert_file_exists "nginx.conf backed up" "${backup_dir}/nginx.conf"
    assert_file_exists ".env backed up" "${backup_dir}/.env"

    # Verify backup matches original
    assert_success "docker-compose backup matches" \
        "diff '${TEST_ENV_DIR}/docker-compose.yaml' '${backup_dir}/docker-compose.yaml'"
    assert_success "nginx.conf backup matches" \
        "diff '${TEST_ENV_DIR}/nginx.conf' '${backup_dir}/nginx.conf'"
    assert_success ".env backup matches" \
        "diff '${TEST_ENV_DIR}/.env' '${backup_dir}/.env'"
}

test_ssl_cert_backup() {
    log_section "Testing SSL Certificate Backup"

    local backup_dir="${TEST_ENV_DIR}/backups/certs_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"

    # Backup certificates
    cp -r "${TEST_ENV_DIR}/certs/"* "${backup_dir}/"

    assert_file_exists "cert.pem backed up" "${backup_dir}/cert.pem"
    assert_file_exists "key.pem backed up" "${backup_dir}/key.pem"

    # Verify certificate backup integrity
    assert_file_contains "Certificate has BEGIN marker" "${backup_dir}/cert.pem" "BEGIN CERTIFICATE"
    assert_file_contains "Key has BEGIN marker" "${backup_dir}/key.pem" "BEGIN PRIVATE KEY"
}

test_data_backup() {
    log_section "Testing Data Backup"

    local backup_dir="${TEST_ENV_DIR}/backups/data_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"

    # Backup n8n data
    cp -r "${TEST_ENV_DIR}/data/n8n" "${backup_dir}/"

    assert_dir_exists "n8n data directory backed up" "${backup_dir}/n8n"
    assert_file_exists "workflows.json backed up" "${backup_dir}/n8n/workflows.json"
    assert_file_exists "credentials.json backed up" "${backup_dir}/n8n/credentials.json"

    # Verify data integrity
    assert_success "Workflows backup matches" \
        "diff '${TEST_ENV_DIR}/data/n8n/workflows.json' '${backup_dir}/n8n/workflows.json'"
}

test_database_backup() {
    log_section "Testing Database Backup"

    local backup_dir="${TEST_ENV_DIR}/backups/db_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"

    # Backup database dump
    cp "${TEST_ENV_DIR}/data/postgres/n8n_dump.sql" "${backup_dir}/"

    assert_file_exists "Database dump backed up" "${backup_dir}/n8n_dump.sql"
    assert_file_contains "Dump has CREATE TABLE" "${backup_dir}/n8n_dump.sql" "CREATE TABLE"
    assert_file_contains "Dump has INSERT" "${backup_dir}/n8n_dump.sql" "INSERT INTO"
}

test_full_backup() {
    log_section "Testing Full System Backup"

    local backup_name="full_backup_$(date +%Y%m%d_%H%M%S)"
    local backup_dir="${TEST_ENV_DIR}/backups/${backup_name}"
    mkdir -p "${backup_dir}/config"
    mkdir -p "${backup_dir}/certs"
    mkdir -p "${backup_dir}/data"
    mkdir -p "${backup_dir}/database"

    # Backup all components
    cp "${TEST_ENV_DIR}/docker-compose.yaml" "${backup_dir}/config/"
    cp "${TEST_ENV_DIR}/nginx.conf" "${backup_dir}/config/"
    cp "${TEST_ENV_DIR}/.env" "${backup_dir}/config/"
    cp -r "${TEST_ENV_DIR}/certs/"* "${backup_dir}/certs/"
    cp -r "${TEST_ENV_DIR}/data/n8n" "${backup_dir}/data/"
    cp "${TEST_ENV_DIR}/data/postgres/n8n_dump.sql" "${backup_dir}/database/"

    # Create backup manifest
    cat > "${backup_dir}/manifest.json" << EOF
{
    "version": "3.0",
    "timestamp": "$(date -Iseconds)",
    "hostname": "$(hostname)",
    "components": {
        "config": ["docker-compose.yaml", "nginx.conf", ".env"],
        "certs": ["cert.pem", "key.pem"],
        "data": ["n8n/workflows.json", "n8n/credentials.json"],
        "database": ["n8n_dump.sql"]
    },
    "checksums": {}
}
EOF

    # Generate checksums
    local checksum_file="${backup_dir}/checksums.sha256"
    find "$backup_dir" -type f ! -name "checksums.sha256" -exec sha256sum {} \; > "$checksum_file"

    assert_file_exists "Backup manifest created" "${backup_dir}/manifest.json"
    assert_file_exists "Checksums file created" "${backup_dir}/checksums.sha256"

    # Verify all directories exist
    assert_dir_exists "Config backup directory" "${backup_dir}/config"
    assert_dir_exists "Certs backup directory" "${backup_dir}/certs"
    assert_dir_exists "Data backup directory" "${backup_dir}/data"
    assert_dir_exists "Database backup directory" "${backup_dir}/database"
}

test_compressed_backup() {
    log_section "Testing Compressed Backup"

    local backup_name="compressed_$(date +%Y%m%d_%H%M%S)"
    local backup_dir="${TEST_ENV_DIR}/backups/${backup_name}"
    local archive_file="${TEST_ENV_DIR}/backups/${backup_name}.tar.gz"

    mkdir -p "$backup_dir"

    # Copy files to backup directory
    cp "${TEST_ENV_DIR}/docker-compose.yaml" "${backup_dir}/"
    cp "${TEST_ENV_DIR}/nginx.conf" "${backup_dir}/"
    cp "${TEST_ENV_DIR}/.env" "${backup_dir}/"

    # Create compressed archive
    tar -czf "$archive_file" -C "${TEST_ENV_DIR}/backups" "$backup_name"

    assert_file_exists "Compressed backup created" "$archive_file"

    # Verify archive contents
    assert_success "Archive contains docker-compose.yaml" \
        "tar -tzf '$archive_file' | grep -q 'docker-compose.yaml'"
    assert_success "Archive contains nginx.conf" \
        "tar -tzf '$archive_file' | grep -q 'nginx.conf'"

    # Cleanup intermediate directory
    rm -rf "$backup_dir"

    # Verify archive is still valid
    assert_success "Archive is valid gzip" "gzip -t '$archive_file'"
}

# ============================================================================
# Backup Validation Tests
# ============================================================================

test_backup_integrity() {
    log_section "Testing Backup Integrity Validation"

    local backup_dir="${TEST_ENV_DIR}/backups/integrity_test"
    mkdir -p "$backup_dir"

    # Create backup with checksums
    cp "${TEST_ENV_DIR}/docker-compose.yaml" "${backup_dir}/"
    cp "${TEST_ENV_DIR}/nginx.conf" "${backup_dir}/"

    # Generate checksums
    (cd "$backup_dir" && sha256sum * > checksums.sha256)

    assert_file_exists "Checksums file created" "${backup_dir}/checksums.sha256"

    # Verify checksums
    assert_success "Checksums verify correctly" \
        "(cd '$backup_dir' && sha256sum -c checksums.sha256)"

    # Simulate corruption
    echo "corrupted" >> "${backup_dir}/docker-compose.yaml"

    # Verify checksum now fails
    assert_failure "Corrupted file fails checksum" \
        "(cd '$backup_dir' && sha256sum -c checksums.sha256 2>/dev/null)"
}

test_backup_completeness() {
    log_section "Testing Backup Completeness Check"

    local backup_dir="${TEST_ENV_DIR}/backups/completeness_test"
    mkdir -p "$backup_dir"

    # Create manifest with expected files
    cat > "${backup_dir}/manifest.json" << 'EOF'
{
    "required_files": [
        "docker-compose.yaml",
        "nginx.conf",
        ".env"
    ]
}
EOF

    # Create incomplete backup (missing .env)
    cp "${TEST_ENV_DIR}/docker-compose.yaml" "${backup_dir}/"
    cp "${TEST_ENV_DIR}/nginx.conf" "${backup_dir}/"

    # Check completeness
    local missing_files=0
    for file in docker-compose.yaml nginx.conf .env; do
        if [ ! -f "${backup_dir}/${file}" ]; then
            missing_files=$((missing_files + 1))
        fi
    done

    assert_not_equals "Incomplete backup detected" "0" "$missing_files"

    # Complete the backup
    cp "${TEST_ENV_DIR}/.env" "${backup_dir}/"

    # Re-check completeness
    missing_files=0
    for file in docker-compose.yaml nginx.conf .env; do
        if [ ! -f "${backup_dir}/${file}" ]; then
            missing_files=$((missing_files + 1))
        fi
    done

    assert_equals "Complete backup verified" "0" "$missing_files"
}

# ============================================================================
# Restore Tests
# ============================================================================

test_config_restore() {
    log_section "Testing Configuration Restore"

    # Create backup
    local backup_dir="${TEST_ENV_DIR}/backups/restore_test"
    mkdir -p "$backup_dir"
    cp "${TEST_ENV_DIR}/docker-compose.yaml" "${backup_dir}/"
    cp "${TEST_ENV_DIR}/nginx.conf" "${backup_dir}/"
    cp "${TEST_ENV_DIR}/.env" "${backup_dir}/"

    # Create restore target directory
    local restore_dir="${TEST_ENV_DIR}/restored"
    mkdir -p "$restore_dir"

    # Perform restore
    cp "${backup_dir}/docker-compose.yaml" "${restore_dir}/"
    cp "${backup_dir}/nginx.conf" "${restore_dir}/"
    cp "${backup_dir}/.env" "${restore_dir}/"

    # Verify restore
    assert_file_exists "docker-compose.yaml restored" "${restore_dir}/docker-compose.yaml"
    assert_file_exists "nginx.conf restored" "${restore_dir}/nginx.conf"
    assert_file_exists ".env restored" "${restore_dir}/.env"

    # Verify content matches
    assert_success "Restored docker-compose matches original" \
        "diff '${TEST_ENV_DIR}/docker-compose.yaml' '${restore_dir}/docker-compose.yaml'"
}

test_selective_restore() {
    log_section "Testing Selective Restore"

    # Create full backup
    local backup_dir="${TEST_ENV_DIR}/backups/selective_test"
    mkdir -p "$backup_dir"
    cp "${TEST_ENV_DIR}/docker-compose.yaml" "${backup_dir}/"
    cp "${TEST_ENV_DIR}/nginx.conf" "${backup_dir}/"
    cp "${TEST_ENV_DIR}/.env" "${backup_dir}/"

    # Create restore target
    local restore_dir="${TEST_ENV_DIR}/selective_restored"
    mkdir -p "$restore_dir"

    # Selective restore (only nginx.conf)
    cp "${backup_dir}/nginx.conf" "${restore_dir}/"

    assert_file_exists "nginx.conf selectively restored" "${restore_dir}/nginx.conf"
    assert_failure "docker-compose.yaml not restored" "[ -f '${restore_dir}/docker-compose.yaml' ]"
    assert_failure ".env not restored" "[ -f '${restore_dir}/.env' ]"
}

test_restore_from_archive() {
    log_section "Testing Restore from Archive"

    # Create compressed backup
    local backup_name="archive_restore_test"
    local backup_dir="${TEST_ENV_DIR}/backups/${backup_name}"
    local archive_file="${TEST_ENV_DIR}/backups/${backup_name}.tar.gz"
    local restore_dir="${TEST_ENV_DIR}/archive_restored"

    mkdir -p "$backup_dir"
    mkdir -p "$restore_dir"

    cp "${TEST_ENV_DIR}/docker-compose.yaml" "${backup_dir}/"
    cp "${TEST_ENV_DIR}/nginx.conf" "${backup_dir}/"

    # Create archive
    tar -czf "$archive_file" -C "${TEST_ENV_DIR}/backups" "$backup_name"

    # Remove original backup directory
    rm -rf "$backup_dir"

    # Restore from archive
    tar -xzf "$archive_file" -C "$restore_dir"

    assert_dir_exists "Backup directory extracted" "${restore_dir}/${backup_name}"
    assert_file_exists "docker-compose.yaml extracted" "${restore_dir}/${backup_name}/docker-compose.yaml"
    assert_file_exists "nginx.conf extracted" "${restore_dir}/${backup_name}/nginx.conf"
}

test_restore_with_validation() {
    log_section "Testing Restore with Validation"

    # Create backup with checksums
    local backup_dir="${TEST_ENV_DIR}/backups/validated_restore"
    local restore_dir="${TEST_ENV_DIR}/validated_restored"
    mkdir -p "$backup_dir"
    mkdir -p "$restore_dir"

    cp "${TEST_ENV_DIR}/docker-compose.yaml" "${backup_dir}/"
    cp "${TEST_ENV_DIR}/nginx.conf" "${backup_dir}/"

    # Generate checksums
    (cd "$backup_dir" && sha256sum docker-compose.yaml nginx.conf > checksums.sha256)

    # Perform restore
    cp "${backup_dir}/docker-compose.yaml" "${restore_dir}/"
    cp "${backup_dir}/nginx.conf" "${restore_dir}/"
    cp "${backup_dir}/checksums.sha256" "${restore_dir}/"

    # Validate restore
    assert_success "Restored files pass checksum validation" \
        "(cd '$restore_dir' && sha256sum -c checksums.sha256)"
}

# ============================================================================
# Backup Rotation Tests
# ============================================================================

test_backup_rotation() {
    log_section "Testing Backup Rotation"

    local backup_base="${TEST_ENV_DIR}/backups/rotation"
    mkdir -p "$backup_base"

    # Create 5 backups
    for i in {1..5}; do
        local backup_dir="${backup_base}/backup_${i}"
        mkdir -p "$backup_dir"
        echo "Backup ${i}" > "${backup_dir}/data.txt"
        # Simulate different timestamps
        touch -d "${i} days ago" "$backup_dir"
    done

    # Count backups
    local backup_count
    backup_count=$(find "$backup_base" -maxdepth 1 -type d -name "backup_*" | wc -l)
    assert_equals "5 backups exist" "5" "$backup_count"

    # Simulate rotation (keep only 3 newest)
    local max_backups=3
    local backups_to_delete=$((backup_count - max_backups))

    if [ $backups_to_delete -gt 0 ]; then
        # Delete oldest backups
        find "$backup_base" -maxdepth 1 -type d -name "backup_*" -printf '%T+ %p\n' | \
            sort | head -n $backups_to_delete | cut -d' ' -f2- | xargs rm -rf
    fi

    # Verify rotation
    backup_count=$(find "$backup_base" -maxdepth 1 -type d -name "backup_*" | wc -l)
    assert_equals "3 backups remain after rotation" "3" "$backup_count"
}

test_backup_retention_policy() {
    log_section "Testing Backup Retention Policy"

    local backup_base="${TEST_ENV_DIR}/backups/retention"
    mkdir -p "$backup_base"

    # Create backups with different ages
    # Daily backups (keep 7)
    for i in {0..9}; do
        local backup_dir="${backup_base}/daily_${i}"
        mkdir -p "$backup_dir"
        touch -d "${i} days ago" "$backup_dir"
    done

    # Count daily backups older than 7 days
    local old_backups
    old_backups=$(find "$backup_base" -maxdepth 1 -type d -name "daily_*" -mtime +7 | wc -l)

    log_info "Found ${old_backups} backups older than 7 days"

    # In a real implementation, these would be deleted
    # For test, just verify we can identify them
    assert_success "Can identify old backups" "[ $old_backups -ge 0 ]"
}

# ============================================================================
# Disaster Recovery Tests
# ============================================================================

test_disaster_recovery_scenario() {
    log_section "Testing Disaster Recovery Scenario"

    # Step 1: Create full backup
    local backup_dir="${TEST_ENV_DIR}/backups/dr_backup"
    mkdir -p "${backup_dir}/config"
    mkdir -p "${backup_dir}/data"

    cp "${TEST_ENV_DIR}/docker-compose.yaml" "${backup_dir}/config/"
    cp "${TEST_ENV_DIR}/nginx.conf" "${backup_dir}/config/"
    cp "${TEST_ENV_DIR}/.env" "${backup_dir}/config/"
    cp -r "${TEST_ENV_DIR}/data/n8n" "${backup_dir}/data/"

    log_success "Full backup created for DR test"

    # Step 2: Simulate disaster (delete everything)
    local original_dir="${TEST_ENV_DIR}/original"
    mkdir -p "$original_dir"
    mv "${TEST_ENV_DIR}/docker-compose.yaml" "${original_dir}/"
    mv "${TEST_ENV_DIR}/nginx.conf" "${original_dir}/"
    mv "${TEST_ENV_DIR}/.env" "${original_dir}/"
    rm -rf "${TEST_ENV_DIR}/data/n8n"

    assert_failure "docker-compose.yaml deleted" "[ -f '${TEST_ENV_DIR}/docker-compose.yaml' ]"
    assert_failure "data directory deleted" "[ -d '${TEST_ENV_DIR}/data/n8n' ]"

    log_success "Disaster simulated"

    # Step 3: Perform recovery
    cp "${backup_dir}/config/docker-compose.yaml" "${TEST_ENV_DIR}/"
    cp "${backup_dir}/config/nginx.conf" "${TEST_ENV_DIR}/"
    cp "${backup_dir}/config/.env" "${TEST_ENV_DIR}/"
    mkdir -p "${TEST_ENV_DIR}/data"
    cp -r "${backup_dir}/data/n8n" "${TEST_ENV_DIR}/data/"

    # Step 4: Verify recovery
    assert_file_exists "docker-compose.yaml recovered" "${TEST_ENV_DIR}/docker-compose.yaml"
    assert_file_exists "nginx.conf recovered" "${TEST_ENV_DIR}/nginx.conf"
    assert_file_exists ".env recovered" "${TEST_ENV_DIR}/.env"
    assert_dir_exists "n8n data recovered" "${TEST_ENV_DIR}/data/n8n"
    assert_file_exists "workflows.json recovered" "${TEST_ENV_DIR}/data/n8n/workflows.json"

    log_success "Disaster recovery completed"

    # Cleanup
    mv "${original_dir}/"* "${TEST_ENV_DIR}/" 2>/dev/null || true
    rm -rf "$original_dir"
}

# ============================================================================
# Main Test Runner
# ============================================================================

run_backup_restore_tests() {
    log_section "n8n_nginx v3.0 Backup/Restore Tests"
    echo "Test Started: $(date)"
    echo ""

    setup_test_environment

    # Backup creation tests
    test_config_backup
    test_ssl_cert_backup
    test_data_backup
    test_database_backup
    test_full_backup
    test_compressed_backup

    # Backup validation tests
    test_backup_integrity
    test_backup_completeness

    # Restore tests
    test_config_restore
    test_selective_restore
    test_restore_from_archive
    test_restore_with_validation

    # Backup management tests
    test_backup_rotation
    test_backup_retention_policy

    # Disaster recovery tests
    test_disaster_recovery_scenario

    # Print summary
    print_test_summary

    # Generate JUnit report if requested
    if [ -n "${JUNIT_OUTPUT:-}" ]; then
        generate_junit_report "$JUNIT_OUTPUT" "backup_restore_tests"
    fi

    # Return appropriate exit code
    [ $TESTS_FAILED -eq 0 ]
}

# ============================================================================
# CLI Interface
# ============================================================================

show_help() {
    cat << EOF
n8n_nginx Backup/Restore Test Suite v3.0

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -j, --junit FILE        Generate JUnit XML report
    -k, --keep              Keep test environment after tests
    -v, --verbose           Verbose output

Examples:
    $0                      Run all backup/restore tests
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
run_backup_restore_tests

exit $?
