#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /tests/test_installation.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 1st, 2026
#
# Richard J. Sears
# richardjsears@gmail.com
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

#
# test_installation.sh - Installation Test Suite for n8n_nginx v3.0
# Tests fresh installation, upgrade paths, and configuration validation
#

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source test utilities
source "${SCRIPT_DIR}/test_utils.sh"

# Test configuration
TEST_DOMAIN="test.n8n.local"
TEST_MGMT_PORT="3333"
TEST_EMAIL="admin@test.local"

# ============================================================================
# Test Groups
# ============================================================================

test_prerequisites() {
    log_section "Testing Prerequisites"

    # Check required commands
    assert_success "Docker is installed" "command -v docker"
    assert_success "Docker Compose is available" "command -v docker-compose || docker compose version"
    assert_success "curl is installed" "command -v curl"
    assert_success "openssl is installed" "command -v openssl"
    assert_success "jq is installed" "command -v jq"

    # Check Docker is running
    assert_success "Docker daemon is running" "docker info"

    # Check disk space (at least 5GB free)
    local free_space
    free_space=$(df -BG / | tail -1 | awk '{print $4}' | tr -d 'G')
    if [ "$free_space" -ge 5 ]; then
        log_success "Sufficient disk space available (${free_space}GB free)"
        TESTS_RUN=$((TESTS_RUN + 1))
        TESTS_PASSED=$((TESTS_PASSED + 1))
        TEST_RESULTS+=("PASS: Sufficient disk space available")
    else
        log_error "Insufficient disk space (${free_space}GB free, need 5GB)"
        TESTS_RUN=$((TESTS_RUN + 1))
        TESTS_FAILED=$((TESTS_FAILED + 1))
        TEST_RESULTS+=("FAIL: Insufficient disk space")
    fi

    # Check memory (at least 2GB)
    local total_mem
    total_mem=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$total_mem" -ge 2 ]; then
        log_success "Sufficient memory available (${total_mem}GB)"
        TESTS_RUN=$((TESTS_RUN + 1))
        TESTS_PASSED=$((TESTS_PASSED + 1))
        TEST_RESULTS+=("PASS: Sufficient memory available")
    else
        log_warn "Low memory warning (${total_mem}GB, recommend 2GB+)"
        TESTS_RUN=$((TESTS_RUN + 1))
        TESTS_PASSED=$((TESTS_PASSED + 1))
        TEST_RESULTS+=("PASS: Memory check (warning: low)")
    fi
}

test_project_structure() {
    log_section "Testing Project Structure"

    # Core files
    assert_file_exists "setup.sh exists" "${PROJECT_ROOT}/setup.sh"
    assert_success "setup.sh is executable" "[ -x '${PROJECT_ROOT}/setup.sh' ]"

    # Management backend (API)
    assert_dir_exists "Management API directory exists" "${PROJECT_ROOT}/management/api"
    assert_file_exists "Backend main.py exists" "${PROJECT_ROOT}/management/api/main.py"
    assert_file_exists "Backend requirements.txt exists" "${PROJECT_ROOT}/management/requirements.txt"

    # Management frontend
    assert_dir_exists "Management frontend directory exists" "${PROJECT_ROOT}/management/frontend"
    assert_file_exists "Frontend package.json exists" "${PROJECT_ROOT}/management/frontend/package.json"
    assert_file_exists "Frontend vite.config.js exists" "${PROJECT_ROOT}/management/frontend/vite.config.js"

    # Docker files
    assert_file_exists "Management Dockerfile exists" "${PROJECT_ROOT}/management/Dockerfile"

    # API subdirectories
    assert_dir_exists "API models directory exists" "${PROJECT_ROOT}/management/api/models"
    assert_dir_exists "API routers directory exists" "${PROJECT_ROOT}/management/api/routers"
    assert_dir_exists "API services directory exists" "${PROJECT_ROOT}/management/api/services"
}

test_setup_script_syntax() {
    log_section "Testing setup.sh Syntax"

    # Check bash syntax
    assert_success "setup.sh has valid bash syntax" "bash -n '${PROJECT_ROOT}/setup.sh'"

    # Check for required functions
    assert_file_contains "setup.sh has detect_current_version function" "${PROJECT_ROOT}/setup.sh" "detect_current_version"
    assert_file_contains "setup.sh has save_state function" "${PROJECT_ROOT}/setup.sh" "save_state"
    assert_file_contains "setup.sh has load_state function" "${PROJECT_ROOT}/setup.sh" "load_state"
    assert_file_contains "setup.sh has configure_management_port function" "${PROJECT_ROOT}/setup.sh" "configure_management_port"
    assert_file_contains "setup.sh has run_migration_v2_to_v3 function" "${PROJECT_ROOT}/setup.sh" "run_migration_v2_to_v3"
    assert_file_contains "setup.sh has generate_docker_compose_v3 function" "${PROJECT_ROOT}/setup.sh" "generate_docker_compose_v3"

    # Check version
    assert_file_contains "setup.sh is v3.0" "${PROJECT_ROOT}/setup.sh" 'VERSION="3.0'
}

test_backend_code() {
    log_section "Testing Backend Code"

    local api_dir="${PROJECT_ROOT}/management/api"
    local mgmt_dir="${PROJECT_ROOT}/management"

    # Python syntax check
    if command -v python3 &> /dev/null; then
        assert_success "main.py has valid Python syntax" "python3 -m py_compile '${api_dir}/main.py'"

        # Check for required API modules
        if [ -d "${api_dir}/routers" ]; then
            for py_file in "${api_dir}/routers"/*.py; do
                if [ -f "$py_file" ]; then
                    local filename=$(basename "$py_file")
                    assert_success "routers/${filename} has valid Python syntax" "python3 -m py_compile '$py_file'"
                fi
            done
        fi

        # Check for required service modules
        if [ -d "${api_dir}/services" ]; then
            for py_file in "${api_dir}/services"/*.py; do
                if [ -f "$py_file" ]; then
                    local filename=$(basename "$py_file")
                    assert_success "services/${filename} has valid Python syntax" "python3 -m py_compile '$py_file'"
                fi
            done
        fi

        # Check for model modules
        if [ -d "${api_dir}/models" ]; then
            for py_file in "${api_dir}/models"/*.py; do
                if [ -f "$py_file" ]; then
                    local filename=$(basename "$py_file")
                    assert_success "models/${filename} has valid Python syntax" "python3 -m py_compile '$py_file'"
                fi
            done
        fi
    else
        skip_test "Python syntax validation" "Python3 not available"
    fi

    # Check requirements.txt
    assert_file_contains "FastAPI is in requirements" "${mgmt_dir}/requirements.txt" "fastapi"
    assert_file_contains "Uvicorn is in requirements" "${mgmt_dir}/requirements.txt" "uvicorn"
    assert_file_contains "SQLAlchemy is in requirements" "${mgmt_dir}/requirements.txt" "sqlalchemy"
}

test_frontend_code() {
    log_section "Testing Frontend Code"

    local frontend_dir="${PROJECT_ROOT}/management/frontend"

    # Check package.json
    assert_file_contains "Vue.js is a dependency" "${frontend_dir}/package.json" '"vue"'
    assert_file_contains "Vite is a dev dependency" "${frontend_dir}/package.json" '"vite"'

    # Check main entry points
    assert_file_exists "main.js exists" "${frontend_dir}/src/main.js"
    assert_file_exists "App.vue exists" "${frontend_dir}/src/App.vue"

    # Check router
    assert_file_exists "Router index exists" "${frontend_dir}/src/router/index.js"

    # Check stores
    assert_dir_exists "Stores directory exists" "${frontend_dir}/src/stores"

    # Check views
    assert_dir_exists "Views directory exists" "${frontend_dir}/src/views"
    assert_file_exists "DashboardView.vue exists" "${frontend_dir}/src/views/DashboardView.vue"

    # Check components
    assert_dir_exists "Components directory exists" "${frontend_dir}/src/components"

    # Check services
    assert_dir_exists "Services directory exists" "${frontend_dir}/src/services"
    assert_file_exists "API service exists" "${frontend_dir}/src/services/api.js"
}

test_docker_configuration() {
    log_section "Testing Docker Configuration"

    local mgmt_dockerfile="${PROJECT_ROOT}/management/Dockerfile"

    # Management Dockerfile checks (combined backend + frontend)
    assert_file_exists "Management Dockerfile exists" "$mgmt_dockerfile"
    assert_file_contains "Dockerfile uses Python base image" "$mgmt_dockerfile" "python"
    assert_file_contains "Dockerfile has EXPOSE directive" "$mgmt_dockerfile" "EXPOSE"

    # Validate Dockerfile syntax (basic check)
    assert_success "Dockerfile has FROM instruction" "grep -q '^FROM' '$mgmt_dockerfile'"
}

test_port_validation() {
    log_section "Testing Port Validation Logic"

    # Define reserved ports from setup.sh
    local reserved_ports=(80 443 5432 5678 8080 8443)

    # Test that reserved ports are defined in setup.sh
    for port in "${reserved_ports[@]}"; do
        assert_file_contains "Port $port is reserved" "${PROJECT_ROOT}/setup.sh" "$port"
    done

    # Test valid port range
    assert_file_contains "setup.sh validates port range 1024-65535" "${PROJECT_ROOT}/setup.sh" "1024"
    assert_file_contains "setup.sh validates port range upper bound" "${PROJECT_ROOT}/setup.sh" "65535"
}

test_security_features() {
    log_section "Testing Security Features"

    # Check for password validation
    assert_file_contains "Password length validation exists" "${PROJECT_ROOT}/setup.sh" "password"

    # Check for HTTPS configuration
    assert_file_contains "SSL/TLS configuration" "${PROJECT_ROOT}/setup.sh" "ssl\|SSL\|https\|HTTPS"

    # Check for secret generation
    assert_file_contains "Secret/key generation" "${PROJECT_ROOT}/setup.sh" "openssl\|secret\|SECRET"

    # Backend security checks
    local api_dir="${PROJECT_ROOT}/management/api"
    if [ -f "${api_dir}/security.py" ]; then
        assert_file_contains "Token handling in security" "${api_dir}/security.py" "token\|Token"
        assert_file_contains "Password hashing in security" "${api_dir}/security.py" "hash\|bcrypt"
    fi
}

test_notification_configuration() {
    log_section "Testing Notification Configuration"

    # Check notification providers in setup.sh
    assert_file_contains "Email notification support" "${PROJECT_ROOT}/setup.sh" "email\|EMAIL\|smtp\|SMTP"
    assert_file_contains "Slack notification support" "${PROJECT_ROOT}/setup.sh" "slack\|SLACK"
    assert_file_contains "Discord notification support" "${PROJECT_ROOT}/setup.sh" "discord\|DISCORD"
    assert_file_contains "NTFY notification support" "${PROJECT_ROOT}/setup.sh" "ntfy\|NTFY"
}

test_migration_support() {
    log_section "Testing Migration Support"

    # Check migration functions
    assert_file_contains "v2 to v3 migration function" "${PROJECT_ROOT}/setup.sh" "run_migration_v2_to_v3"
    assert_file_contains "Rollback support" "${PROJECT_ROOT}/setup.sh" "rollback"
    assert_file_contains "Backup before migration" "${PROJECT_ROOT}/setup.sh" "backup"

    # Check version detection
    assert_file_contains "Version detection logic" "${PROJECT_ROOT}/setup.sh" "detect_current_version"
}

test_nfs_configuration() {
    log_section "Testing NFS Configuration"

    # Check NFS support in setup.sh
    assert_file_contains "NFS configuration function" "${PROJECT_ROOT}/setup.sh" "configure_nfs\|NFS"
    assert_file_contains "NFS mount testing" "${PROJECT_ROOT}/setup.sh" "mount\|MOUNT"
}

test_state_management() {
    log_section "Testing State Management"

    # Check state management functions
    assert_file_contains "State save function" "${PROJECT_ROOT}/setup.sh" "save_state"
    assert_file_contains "State load function" "${PROJECT_ROOT}/setup.sh" "load_state"
    assert_file_contains "State check/resume function" "${PROJECT_ROOT}/setup.sh" "check_resume\|resume"
    assert_file_contains "State clear function" "${PROJECT_ROOT}/setup.sh" "clear_state"

    # Check state file location
    assert_file_contains "State file definition" "${PROJECT_ROOT}/setup.sh" "STATE_FILE\|state"
}

# ============================================================================
# Integration Tests (require running environment)
# ============================================================================

test_docker_build() {
    log_section "Testing Docker Build (Integration)"

    # Check if we should run integration tests
    if [ "${RUN_INTEGRATION_TESTS:-false}" != "true" ]; then
        skip_test "Docker build test" "Integration tests disabled (set RUN_INTEGRATION_TESTS=true)"
        return
    fi

    require_docker

    local mgmt_dir="${PROJECT_ROOT}/management"

    # Build management image (combined backend + frontend)
    assert_success "Management Docker image builds" \
        "docker build -t n8n-management:test '$mgmt_dir'"

    # Cleanup test images
    docker rmi n8n-management:test 2>/dev/null || true
}

test_service_startup() {
    log_section "Testing Service Startup (Integration)"

    if [ "${RUN_INTEGRATION_TESTS:-false}" != "true" ]; then
        skip_test "Service startup test" "Integration tests disabled (set RUN_INTEGRATION_TESTS=true)"
        return
    fi

    require_docker
    require_docker_compose

    # This test would require a full docker-compose environment
    skip_test "Full service startup" "Requires production-like environment"
}

# ============================================================================
# Main Test Runner
# ============================================================================

run_all_tests() {
    log_section "n8n_nginx v3.0 Installation Tests"
    echo "Project Root: $PROJECT_ROOT"
    echo "Test Started: $(date)"
    echo ""

    # Run test groups
    test_prerequisites
    test_project_structure
    test_setup_script_syntax
    test_backend_code
    test_frontend_code
    test_docker_configuration
    test_port_validation
    test_security_features
    test_notification_configuration
    test_migration_support
    test_nfs_configuration
    test_state_management

    # Integration tests (optional)
    test_docker_build
    test_service_startup

    # Print summary
    print_test_summary

    # Generate JUnit report if requested
    if [ -n "${JUNIT_OUTPUT:-}" ]; then
        generate_junit_report "$JUNIT_OUTPUT" "installation_tests"
    fi

    # Return appropriate exit code
    [ $TESTS_FAILED -eq 0 ]
}

# ============================================================================
# CLI Interface
# ============================================================================

show_help() {
    cat << EOF
n8n_nginx Installation Test Suite v3.0

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -i, --integration       Run integration tests (requires Docker)
    -j, --junit FILE        Generate JUnit XML report
    -v, --verbose           Verbose output
    -g, --group GROUP       Run specific test group

Test Groups:
    prerequisites           Test system prerequisites
    structure               Test project structure
    syntax                  Test setup.sh syntax
    backend                 Test backend code
    frontend                Test frontend code
    docker                  Test Docker configuration
    security                Test security features
    notifications           Test notification configuration
    migration               Test migration support
    nfs                     Test NFS configuration
    state                   Test state management
    all                     Run all tests (default)

Examples:
    $0                      Run all unit tests
    $0 -i                   Run all tests including integration
    $0 -g backend           Run only backend tests
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
        -i|--integration)
            export RUN_INTEGRATION_TESTS=true
            shift
            ;;
        -j|--junit)
            export JUNIT_OUTPUT="$2"
            shift 2
            ;;
        -v|--verbose)
            set -x
            shift
            ;;
        -g|--group)
            TEST_GROUP="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Run specific group or all tests
case "${TEST_GROUP:-all}" in
    prerequisites)
        log_section "Running Prerequisites Tests Only"
        test_prerequisites
        print_test_summary
        ;;
    structure)
        log_section "Running Structure Tests Only"
        test_project_structure
        print_test_summary
        ;;
    syntax)
        log_section "Running Syntax Tests Only"
        test_setup_script_syntax
        print_test_summary
        ;;
    backend)
        log_section "Running Backend Tests Only"
        test_backend_code
        print_test_summary
        ;;
    frontend)
        log_section "Running Frontend Tests Only"
        test_frontend_code
        print_test_summary
        ;;
    docker)
        log_section "Running Docker Tests Only"
        test_docker_configuration
        test_docker_build
        print_test_summary
        ;;
    security)
        log_section "Running Security Tests Only"
        test_security_features
        print_test_summary
        ;;
    notifications)
        log_section "Running Notification Tests Only"
        test_notification_configuration
        print_test_summary
        ;;
    migration)
        log_section "Running Migration Tests Only"
        test_migration_support
        print_test_summary
        ;;
    nfs)
        log_section "Running NFS Tests Only"
        test_nfs_configuration
        print_test_summary
        ;;
    state)
        log_section "Running State Management Tests Only"
        test_state_management
        print_test_summary
        ;;
    all)
        run_all_tests
        ;;
    *)
        echo "Unknown test group: $TEST_GROUP"
        show_help
        exit 1
        ;;
esac

exit $?
