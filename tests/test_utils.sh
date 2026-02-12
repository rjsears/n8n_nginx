#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /tests/test_utils.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 1st, 2026
#
# Richard J. Sears
# richard@n8nmanagement.net
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

#
# test_utils.sh - Test Utility Functions for n8n_nginx v3.0
# Common functions used across all test scripts
#

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Test results array
declare -a TEST_RESULTS=()

# ============================================================================
# Output Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_skip() {
    echo -e "${CYAN}[SKIP]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

# ============================================================================
# Test Assertion Functions
# ============================================================================

# Assert that a command succeeds (exit code 0)
assert_success() {
    local description="$1"
    shift
    local cmd="$@"

    TESTS_RUN=$((TESTS_RUN + 1))

    if eval "$cmd" > /dev/null 2>&1; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_success "$description"
        TEST_RESULTS+=("PASS: $description")
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log_error "$description"
        log_error "  Command: $cmd"
        TEST_RESULTS+=("FAIL: $description")
        return 1
    fi
}

# Assert that a command fails (non-zero exit code)
assert_failure() {
    local description="$1"
    shift
    local cmd="$@"

    TESTS_RUN=$((TESTS_RUN + 1))

    if ! eval "$cmd" > /dev/null 2>&1; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_success "$description"
        TEST_RESULTS+=("PASS: $description")
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log_error "$description"
        log_error "  Command unexpectedly succeeded: $cmd"
        TEST_RESULTS+=("FAIL: $description")
        return 1
    fi
}

# Assert that two values are equal
assert_equals() {
    local description="$1"
    local expected="$2"
    local actual="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ "$expected" = "$actual" ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_success "$description"
        TEST_RESULTS+=("PASS: $description")
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log_error "$description"
        log_error "  Expected: $expected"
        log_error "  Actual:   $actual"
        TEST_RESULTS+=("FAIL: $description")
        return 1
    fi
}

# Assert that two values are not equal
assert_not_equals() {
    local description="$1"
    local unexpected="$2"
    local actual="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ "$unexpected" != "$actual" ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_success "$description"
        TEST_RESULTS+=("PASS: $description")
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log_error "$description"
        log_error "  Value should not be: $unexpected"
        TEST_RESULTS+=("FAIL: $description")
        return 1
    fi
}

# Assert that a string contains a substring
assert_contains() {
    local description="$1"
    local haystack="$2"
    local needle="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [[ "$haystack" == *"$needle"* ]]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_success "$description"
        TEST_RESULTS+=("PASS: $description")
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log_error "$description"
        log_error "  String does not contain: $needle"
        TEST_RESULTS+=("FAIL: $description")
        return 1
    fi
}

# Assert that a file exists
assert_file_exists() {
    local description="$1"
    local filepath="$2"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ -f "$filepath" ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_success "$description"
        TEST_RESULTS+=("PASS: $description")
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log_error "$description"
        log_error "  File not found: $filepath"
        TEST_RESULTS+=("FAIL: $description")
        return 1
    fi
}

# Assert that a directory exists
assert_dir_exists() {
    local description="$1"
    local dirpath="$2"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ -d "$dirpath" ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_success "$description"
        TEST_RESULTS+=("PASS: $description")
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log_error "$description"
        log_error "  Directory not found: $dirpath"
        TEST_RESULTS+=("FAIL: $description")
        return 1
    fi
}

# Assert that a file contains a pattern
assert_file_contains() {
    local description="$1"
    local filepath="$2"
    local pattern="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ -f "$filepath" ] && grep -q "$pattern" "$filepath" 2>/dev/null; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_success "$description"
        TEST_RESULTS+=("PASS: $description")
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log_error "$description"
        log_error "  File '$filepath' does not contain: $pattern"
        TEST_RESULTS+=("FAIL: $description")
        return 1
    fi
}

# Assert that a Docker container is running
assert_container_running() {
    local description="$1"
    local container_name="$2"

    TESTS_RUN=$((TESTS_RUN + 1))

    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${container_name}$"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_success "$description"
        TEST_RESULTS+=("PASS: $description")
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log_error "$description"
        log_error "  Container not running: $container_name"
        TEST_RESULTS+=("FAIL: $description")
        return 1
    fi
}

# Assert that a port is listening
assert_port_listening() {
    local description="$1"
    local port="$2"

    TESTS_RUN=$((TESTS_RUN + 1))

    if netstat -tuln 2>/dev/null | grep -q ":${port} " || ss -tuln 2>/dev/null | grep -q ":${port} "; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_success "$description"
        TEST_RESULTS+=("PASS: $description")
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log_error "$description"
        log_error "  Port not listening: $port"
        TEST_RESULTS+=("FAIL: $description")
        return 1
    fi
}

# Assert HTTP status code
assert_http_status() {
    local description="$1"
    local url="$2"
    local expected_status="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    local actual_status
    actual_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null)

    if [ "$actual_status" = "$expected_status" ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_success "$description"
        TEST_RESULTS+=("PASS: $description")
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log_error "$description"
        log_error "  Expected HTTP status: $expected_status"
        log_error "  Actual HTTP status:   $actual_status"
        TEST_RESULTS+=("FAIL: $description")
        return 1
    fi
}

# Skip a test with reason
skip_test() {
    local description="$1"
    local reason="$2"

    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
    log_skip "$description"
    log_skip "  Reason: $reason"
    TEST_RESULTS+=("SKIP: $description - $reason")
}

# ============================================================================
# Test Environment Functions
# ============================================================================

# Check if running as root
require_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This test requires root privileges"
        exit 1
    fi
}

# Check if Docker is available
require_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is required but not installed"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running or not accessible"
        exit 1
    fi
}

# Check if docker-compose is available
require_docker_compose() {
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is required but not installed"
        exit 1
    fi
}

# Create a temporary test directory
create_test_dir() {
    local test_dir
    test_dir=$(mktemp -d -t n8n_test_XXXXXX)
    echo "$test_dir"
}

# Clean up a test directory
cleanup_test_dir() {
    local test_dir="$1"
    if [ -d "$test_dir" ] && [[ "$test_dir" == /tmp/n8n_test_* ]]; then
        rm -rf "$test_dir"
    fi
}

# Wait for a service to be ready
wait_for_service() {
    local url="$1"
    local max_attempts="${2:-30}"
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null | grep -q "^[23]"; then
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done

    return 1
}

# Wait for a container to be healthy
wait_for_container_healthy() {
    local container_name="$1"
    local max_attempts="${2:-30}"
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        local health
        health=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null)

        if [ "$health" = "healthy" ]; then
            return 0
        fi

        sleep 2
        attempt=$((attempt + 1))
    done

    return 1
}

# ============================================================================
# Backup/Restore Test Helpers
# ============================================================================

# Create a test database entry
create_test_db_entry() {
    local container="$1"
    local db_name="$2"
    local table_name="test_data"
    local test_value="test_$(date +%s)"

    docker exec "$container" psql -U n8n -d "$db_name" -c \
        "CREATE TABLE IF NOT EXISTS $table_name (id SERIAL PRIMARY KEY, value TEXT, created_at TIMESTAMP DEFAULT NOW());" \
        2>/dev/null

    docker exec "$container" psql -U n8n -d "$db_name" -c \
        "INSERT INTO $table_name (value) VALUES ('$test_value');" \
        2>/dev/null

    echo "$test_value"
}

# Verify a test database entry exists
verify_test_db_entry() {
    local container="$1"
    local db_name="$2"
    local test_value="$3"
    local table_name="test_data"

    local result
    result=$(docker exec "$container" psql -U n8n -d "$db_name" -t -c \
        "SELECT value FROM $table_name WHERE value='$test_value';" 2>/dev/null | tr -d ' ')

    [ "$result" = "$test_value" ]
}

# ============================================================================
# Report Functions
# ============================================================================

# Print test summary
print_test_summary() {
    echo ""
    log_section "Test Summary"

    echo -e "Tests Run:    ${TESTS_RUN}"
    echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
    echo -e "Tests Skipped: ${YELLOW}${TESTS_SKIPPED}${NC}"
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    else
        echo -e "${RED}Some tests failed!${NC}"
        echo ""
        echo "Failed tests:"
        for result in "${TEST_RESULTS[@]}"; do
            if [[ "$result" == FAIL:* ]]; then
                echo "  - ${result#FAIL: }"
            fi
        done
        return 1
    fi
}

# Generate JUnit XML report
generate_junit_report() {
    local output_file="${1:-test-results.xml}"
    local suite_name="${2:-n8n_nginx_tests}"

    cat > "$output_file" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="$suite_name" tests="$TESTS_RUN" failures="$TESTS_FAILED" skipped="$TESTS_SKIPPED" time="0">
EOF

    for result in "${TEST_RESULTS[@]}"; do
        local status="${result%%:*}"
        local name="${result#*: }"

        case "$status" in
            PASS)
                echo "    <testcase name=\"$name\" />" >> "$output_file"
                ;;
            FAIL)
                echo "    <testcase name=\"$name\">" >> "$output_file"
                echo "      <failure message=\"Test failed\">$name</failure>" >> "$output_file"
                echo "    </testcase>" >> "$output_file"
                ;;
            SKIP)
                echo "    <testcase name=\"$name\">" >> "$output_file"
                echo "      <skipped message=\"Test skipped\" />" >> "$output_file"
                echo "    </testcase>" >> "$output_file"
                ;;
        esac
    done

    cat >> "$output_file" << EOF
  </testsuite>
</testsuites>
EOF

    log_info "JUnit report generated: $output_file"
}

# ============================================================================
# Mock Data Generators
# ============================================================================

# Generate random string
random_string() {
    local length="${1:-16}"
    tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c "$length"
}

# Generate random email
random_email() {
    echo "test_$(random_string 8)@example.com"
}

# Generate random port (non-privileged)
random_port() {
    local min="${1:-10000}"
    local max="${2:-60000}"
    echo $((RANDOM % (max - min + 1) + min))
}

# ============================================================================
# Export Functions
# ============================================================================

export -f log_info log_success log_error log_warn log_skip log_section
export -f assert_success assert_failure assert_equals assert_not_equals
export -f assert_contains assert_file_exists assert_dir_exists assert_file_contains
export -f assert_container_running assert_port_listening assert_http_status skip_test
export -f require_root require_docker require_docker_compose
export -f create_test_dir cleanup_test_dir wait_for_service wait_for_container_healthy
export -f create_test_db_entry verify_test_db_entry
export -f print_test_summary generate_junit_report
export -f random_string random_email random_port
