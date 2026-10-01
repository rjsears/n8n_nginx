#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /tests/test_setup_flows.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#
# Control-flow tests for setup.sh with Docker stubbed out (no daemon needed):
#   * certificate lineage: the cert name chosen once by
#     determine_ssl_cert_domain is what certbot is asked for (--cert-name)
#     and what nginx.conf points at, for wildcard and exact-domain choices
#   * v2 -> v3 migration: aborts before stopping anything if the database
#     dump fails, restores v2 (files + stack) on any later failure, checks
#     health inside the containers and prints the /management/ URL
#   * load_state never yields a non-numeric resume step
#
# Usage: bash tests/test_setup_flows.sh
#

# Variables set inside run_case are read by the sourced setup.sh functions
# shellcheck disable=SC2034

set -u

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$TESTS_DIR")"
SETUP_SH="${PROJECT_ROOT}/setup.sh"

PASS=0
FAIL=0
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

pass() { PASS=$((PASS + 1)); echo "  ok   - $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL - $1"; }
assert_eq() {  # assert_eq DESC EXPECTED ACTUAL
    if [ "$2" = "$3" ]; then pass "$1"; else fail "$1 (expected [$2], got [$3])"; fi
}
assert_contains() {  # assert_contains DESC NEEDLE FILE
    if grep -qF -- "$2" "$3" 2>/dev/null; then pass "$1"; else fail "$1 (missing [$2])"; fi
}
assert_not_contains() {
    if grep -qF -- "$2" "$3" 2>/dev/null; then fail "$1 (unexpected [$2])"; else pass "$1"; fi
}

# setup.sh without its final `main "$@"` line
SETUP_LIB="${WORK_DIR}/setup_lib.sh"
sed '$d' "$SETUP_SH" > "$SETUP_LIB"
if [ "$(tail -n1 "$SETUP_SH")" != 'main "$@"' ]; then
    echo "setup.sh no longer ends with main \"\$@\" - update this test" >&2
    exit 1
fi

# Runs "$@" in a subshell with setup.sh loaded, a scratch SCRIPT_DIR and a
# logging docker stub. Output goes to $WORK_DIR/out, docker calls to
# $WORK_DIR/docker.log. Returns the subshell's exit code.
run_case() {
    local dir="$1"; shift
    rm -rf "$dir"; mkdir -p "$dir"
    : > "${WORK_DIR}/docker.log"
    (
        set +u   # setup.sh is not written for nounset
        # shellcheck disable=SC1090
        source "$SETUP_LIB"
        SCRIPT_DIR="$dir"
        CONFIG_FILE="${dir}/.n8n_setup_config"
        STATE_FILE="${dir}/.n8n_setup_state"
        MIGRATION_STATE_FILE="${dir}/.migration_state"
        MIGRATION_PROGRESS_FILE="${dir}/.migration_progress"
        DOCKER_SUDO=""
        DOCKER_APPARMOR_OPT=""
        PRECONFIG_MODE=false
        PRECONFIG_AUTO_CONFIRM=false
        clear() { :; }
        sleep() { :; }
        DOCKER_LOG="${WORK_DIR}/docker.log"
        docker() { stub_docker "$@"; }
        docker-compose() { stub_docker compose "$@"; }
        "$@"
    ) > "${WORK_DIR}/out" 2>&1 < /dev/null
}

# ---------------------------------------------------------------------------
# 1. Certificate lineage: one cert name for certbot and nginx
# ---------------------------------------------------------------------------
echo "1. certificate lineage name is shared by certbot and nginx.conf"

cert_case() {  # cert_case <wildcard answer y|n> <public website true|false>
    local answer="$1" public="$2"
    stub_docker() {
        echo "docker $*" >> "$DOCKER_LOG"
        case "$1 $2" in
            "volume inspect") return 1 ;;   # fresh host: no letsencrypt volume yet
            "volume create") return 0 ;;
            "run --rm")
                case "$*" in
                    *certonly*) return 0 ;;
                    *"echo ok"*) echo ok ;;  # verify_ssl_cert_lineage_for_nginx
                esac
                return 0 ;;
        esac
        return 0
    }
    N8N_DOMAIN="n8n.example.com"
    INSTALL_PUBLIC_WEBSITE="$public"
    SSL_CERT_DOMAIN=""
    SAVED_SSL_CERT_DOMAIN=""
    DNS_PROVIDER_NAME="cloudflare"
    DNS_CREDENTIALS_FILE="cloudflare.ini"
    DNS_CERTBOT_IMAGE="certbot/dns-cloudflare:${CERTBOT_VERSION}"
    LETSENCRYPT_EMAIL="admin@example.com"
    MGMT_PORT=3333
    INTERNAL_IP_RANGES="$DEFAULT_INTERNAL_IP_RANGES"
    confirm_prompt() { [ "$answer" = "y" ]; }
    ensure_dns_credentials_file() { :; }
    determine_ssl_cert_domain
    generate_nginx_conf_v3
    generate_public_nginx_conf
    generate_nginx_router_conf
    obtain_ssl_certificate
    verify_ssl_cert_lineage_for_nginx
    echo "SSL_CERT_DOMAIN=$SSL_CERT_DOMAIN"
}

for c in "y false example.com" "n false n8n.example.com" "n true example.com"; do
    set -- $c
    d="${WORK_DIR}/cert_$1_$2"
    if run_case "$d" cert_case "$1" "$2"; then
        pass "wildcard=$1 public=$2: deploy steps succeed"
    else
        fail "wildcard=$1 public=$2: exited non-zero"; sed 's/^/      /' "${WORK_DIR}/out" | tail -n 15
    fi
    assert_contains "wildcard=$1 public=$2: SSL_CERT_DOMAIN=$3" "SSL_CERT_DOMAIN=$3" "${WORK_DIR}/out"
    assert_contains "wildcard=$1 public=$2: certbot --cert-name $3" "--cert-name $3 " "${WORK_DIR}/docker.log"
    # TLS is terminated by nginx_router when the public website is enabled
    tls_conf="$d/nginx.conf"; [ "$2" = true ] && tls_conf="$d/nginx-router.conf"
    assert_contains "wildcard=$1 public=$2: $(basename "$tls_conf") uses live/$3" \
        "ssl_certificate /etc/letsencrypt/live/$3/fullchain.pem;" "$tls_conf"
    if [ "$3" = "example.com" ]; then
        assert_contains "wildcard=$1 public=$2: wildcard requested" "-d example.com -d *.example.com" "${WORK_DIR}/docker.log"
    else
        assert_not_contains "wildcard=$1 public=$2: no wildcard requested" "*.example.com" "${WORK_DIR}/docker.log"
    fi
    other="n8n.example.com"; [ "$3" = "n8n.example.com" ] && other="example.com"
    assert_not_contains "wildcard=$1 public=$2: $(basename "$tls_conf") never uses live/$other" "live/$other/" "$tls_conf"
    cp "$d/nginx.conf" "${WORK_DIR}/nginx_$1_$2.conf"
done

# Saved choice is reused, and the wildcard question is not asked again
reuse_case() {
    stub_docker() { echo "docker $*" >> "$DOCKER_LOG"; return 1; }
    N8N_DOMAIN="n8n.example.com"; INSTALL_PUBLIC_WEBSITE=false
    SSL_CERT_DOMAIN="example.com"
    confirm_prompt() { echo "ASKED"; return 1; }
    determine_ssl_cert_domain
    echo "SSL_CERT_DOMAIN=$SSL_CERT_DOMAIN"
}
run_case "${WORK_DIR}/reuse" reuse_case
assert_contains "saved wildcard lineage is reused" "SSL_CERT_DOMAIN=example.com" "${WORK_DIR}/out"
assert_not_contains "saved lineage: no second prompt" "ASKED" "${WORK_DIR}/out"

# ---------------------------------------------------------------------------
# 2. load_state: non-numeric step from older migration runs
# ---------------------------------------------------------------------------
echo "2. load_state sanitises the resume step"
state_case() {
    printf 'SAVED_STEP_NAME="migration"\nSAVED_STEP_NUM="backup"\nSAVED_N8N_DOMAIN="n8n.example.com"\n' > "$STATE_FILE"
    load_state
    echo "CURRENT_STEP=$CURRENT_STEP SSL_CERT_DOMAIN=[$SSL_CERT_DOMAIN]"
}
run_case "${WORK_DIR}/state" state_case
assert_contains "non-numeric SAVED_STEP_NUM becomes 0" "CURRENT_STEP=0 " "${WORK_DIR}/out"
assert_contains "no cert lineage is assumed before it is chosen" "SSL_CERT_DOMAIN=[]" "${WORK_DIR}/out"

# ---------------------------------------------------------------------------
# 3. v2 -> v3 migration control flow
# ---------------------------------------------------------------------------
echo "3. v2 -> v3 migration"

# Behaviour knobs (exported into the subshell through the environment)
#   PG_DUMP_FAIL=1  pg_dump fails       COMPOSE_UP_FAIL=1  v3 "up -d" fails
#   GEN_FAIL=1      generate_env_file exits 1
#   UNHEALTHY=1     n8n health check never passes
migration_case() {
    stub_docker() {
        echo "docker $*" >> "$DOCKER_LOG"
        case "$*" in
            "exec n8n_postgres pg_dump"*) [ "${PG_DUMP_FAIL:-0}" = 1 ] && return 1; echo "PGDMP-fake"; return 0 ;;
            "exec -i n8n_postgres pg_restore -l") cat > /dev/null; return 0 ;;
            "exec n8n wget"*) [ "${UNHEALTHY:-0}" = 1 ] && return 1; return 0 ;;
            "compose up -d --remove-orphans") [ "${COMPOSE_UP_FAIL:-0}" = 1 ] && return 1; return 0 ;;
            "ps --format"*) printf 'n8n\nn8n_postgres\nn8n_nginx\nn8n_management\n'; return 0 ;;
            "inspect --format"*) echo healthy; return 0 ;;
            "exec n8n_postgres psql"*) return 0 ;;
        esac
        return 0
    }
    echo "services: {n8n: {image: n8nio/n8n}}  # v2" > "${SCRIPT_DIR}/docker-compose.yaml"
    echo "v2 nginx" > "${SCRIPT_DIR}/nginx.conf"
    printf 'POSTGRES_PASSWORD=pw\nN8N_ENCRYPTION_KEY=key\n' > "${SCRIPT_DIR}/.env"
    N8N_DOMAIN="n8n.example.com"
    POSTGRES_CONTAINER=n8n_postgres; N8N_CONTAINER=n8n; NGINX_CONTAINER=n8n_nginx
    check_n8n_network_subnet_free() { return 0; }
    configure_management_port() { MGMT_PORT=3333; }
    configure_nfs() { :; }
    configure_notifications() { :; }
    create_admin_user() { :; }
    generate_env_file() {
        [ "${GEN_FAIL:-0}" = 1 ] && exit 1
        echo "v3 env" > "${SCRIPT_DIR}/.env"
    }
    generate_tool_auth_files() { :; }
    generate_docker_compose_v3() { echo "services: {n8n_management: {}}  # v3" > "${SCRIPT_DIR}/docker-compose.yaml"; }
    determine_ssl_cert_domain() { SSL_CERT_DOMAIN="$N8N_DOMAIN"; }
    generate_nginx_conf_v3() { echo "v3 nginx" > "${SCRIPT_DIR}/nginx.conf"; }
    verify_ssl_cert_lineage_for_nginx() { :; }
    confirm_prompt() { return 0; }
    run_migration_v2_to_v3
    echo "MIGRATION_RETURNED"
}

# 3a. pg_dump fails: abort, nothing stopped, v2 files untouched
d="${WORK_DIR}/mig_dumpfail"
PG_DUMP_FAIL=1 run_case "$d" migration_case; rc=$?
assert_eq "dump failure: exit 1" "1" "$rc"
assert_not_contains "dump failure: nothing stopped" "compose stop" "${WORK_DIR}/docker.log"
assert_not_contains "dump failure: no compose up/down" "compose down" "${WORK_DIR}/docker.log"
assert_contains "dump failure: v2 compose untouched" "# v2" "$d/docker-compose.yaml"
assert_eq "dump failure: no empty dump left behind" "0" "$(find "$d/backups" -type f 2>/dev/null | wc -l)"

# 3b. config generation fails (exit 1) before anything is stopped
d="${WORK_DIR}/mig_genfail"
GEN_FAIL=1 run_case "$d" migration_case; rc=$?
assert_eq "generation failure: exit 1" "1" "$rc"
assert_not_contains "generation failure: stack not stopped" "compose stop" "${WORK_DIR}/docker.log"
assert_not_contains "generation failure: stack not restarted" "compose up" "${WORK_DIR}/docker.log"
assert_contains "generation failure: v2 compose restored" "# v2" "$d/docker-compose.yaml"
assert_contains "generation failure: v2 .env restored" "POSTGRES_PASSWORD=pw" "$d/.env"

# 3c. v3 "up -d" fails after v2 was stopped (set -e): v2 restarted
d="${WORK_DIR}/mig_upfail"
COMPOSE_UP_FAIL=1 run_case "$d" migration_case; rc=$?
assert_eq "up failure: non-zero exit" "1" "$rc"
assert_contains "up failure: v3 stack taken down" "compose down --remove-orphans" "${WORK_DIR}/docker.log"
assert_contains "up failure: v2 stack restarted" "compose up -d" "$(printf '%s' "${WORK_DIR}/docker.log")"
assert_eq "up failure: v2 'up -d' is the last compose call" "docker compose up -d" "$(grep 'compose' "${WORK_DIR}/docker.log" | tail -n1)"
assert_contains "up failure: v2 compose restored" "# v2" "$d/docker-compose.yaml"
assert_contains "up failure: v2 nginx.conf restored" "v2 nginx" "$d/nginx.conf"
assert_contains "up failure: v2 .env restored" "POSTGRES_PASSWORD=pw" "$d/.env"
assert_not_contains "up failure: no success message" "MIGRATION_RETURNED" "${WORK_DIR}/out"

# 3d. services never become healthy -> rollback accepted -> v2 back
d="${WORK_DIR}/mig_unhealthy"
UNHEALTHY=1 run_case "$d" migration_case; rc=$?
assert_eq "unhealthy: non-zero exit" "1" "$rc"
assert_eq "unhealthy: v2 'up -d' is the last compose call" "docker compose up -d" "$(grep 'compose' "${WORK_DIR}/docker.log" | tail -n1)"
assert_contains "unhealthy: v2 compose restored" "# v2" "$d/docker-compose.yaml"
assert_contains "unhealthy: n8n health checked inside the container" "exec n8n wget" "${WORK_DIR}/docker.log"

# 3e. success
d="${WORK_DIR}/mig_ok"
run_case "$d" migration_case; rc=$?
assert_eq "success: exit 0" "0" "$rc"
assert_contains "success: function returned" "MIGRATION_RETURNED" "${WORK_DIR}/out"
assert_contains "success: dump taken before stop" "pg_dump" "$(printf '%s' "${WORK_DIR}/docker.log")"
first_dump=$(grep -n 'pg_dump' "${WORK_DIR}/docker.log" | head -n1 | cut -d: -f1)
first_stop=$(grep -n 'compose stop' "${WORK_DIR}/docker.log" | head -n1 | cut -d: -f1)
if [ -n "$first_dump" ] && [ -n "$first_stop" ] && [ "$first_dump" -lt "$first_stop" ]; then
    pass "success: database dump precedes stopping services"
else
    fail "success: database dump precedes stopping services (dump line ${first_dump:-none}, stop line ${first_stop:-none})"
fi
assert_eq "success: dump file kept" "1" "$(find "$d/backups" -name 'n8n_pre_migration_*.dump' -size +0 | wc -l)"
assert_contains "success: /management/ URL printed" "https://n8n.example.com/management/" "${WORK_DIR}/out"
assert_not_contains "success: no :3333 URL" "n8n.example.com:3333" "${WORK_DIR}/out"
assert_contains "success: v3 compose in place" "# v3" "$d/docker-compose.yaml"
assert_contains "success: rollback record written" ".env.v2.backup" "$d/.migration_state"
[ -f "$d/.migration_progress" ] && fail "success: progress file removed" || pass "success: progress file removed"
[ -f "$d/.n8n_setup_state" ] && fail "success: no fresh-install state file left" || pass "success: no fresh-install state file left"

# ---------------------------------------------------------------------------
# 4. --config files
# ---------------------------------------------------------------------------
echo "4. setup.sh --config loading"
preconfig_case() {
    stub_docker() { return 1; }
    load_preconfig "$1"
    echo "LOADED DOMAIN=$N8N_DOMAIN RANGES=$INTERNAL_IP_RANGES"
}
# the shipped example with only the required blanks filled in
sed -e 's/^DOMAIN=$/DOMAIN=n8n.example.com/' \
    -e 's/^LETSENCRYPT_EMAIL=$/LETSENCRYPT_EMAIL=admin@example.com/' \
    -e 's/^CLOUDFLARE_API_TOKEN=$/CLOUDFLARE_API_TOKEN=test-token/' \
    -e 's/^ADMIN_PASS=$/ADMIN_PASS=a-long-test-passphrase/' \
    "${PROJECT_ROOT}/setup-config.example" > "${WORK_DIR}/example-config"
run_case "${WORK_DIR}/preconfig_example" preconfig_case "${WORK_DIR}/example-config"; rc=$?
assert_eq "setup-config.example loads" "0" "$rc"
[ "$rc" = 0 ] || sed "s/^/      /" "${WORK_DIR}/out" | tail -n 8
assert_contains "setup-config.example: multi-value INTERNAL_IP_RANGES kept" \
    "RANGES=127.0.0.1/32 100.64.0.0/10" "${WORK_DIR}/out"

printf 'DOMAIN=n8n.example.com\nINTERNAL_IP_RANGES=10.0.0.0/8 192.168.0.0/16\n' > "${WORK_DIR}/bad-config"
run_case "${WORK_DIR}/preconfig_bad" preconfig_case "${WORK_DIR}/bad-config"; rc=$?
assert_eq "unquoted multi-value config: exit 1" "1" "$rc"
assert_contains "unquoted multi-value config: explained" "could not be loaded" "${WORK_DIR}/out"
assert_not_contains "unquoted multi-value config: not half-loaded" "LOADED" "${WORK_DIR}/out"

echo ""
echo "Passed: $PASS  Failed: $FAIL"
[ "$FAIL" -eq 0 ]
