#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /tests/test_health_check.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#
# Tests for scripts/health_check.sh against stubbed docker / curl / resolver
# commands (no Docker required):
#   * container names and the database login come from .env
#   * a missing host/nslookup is not a DNS failure (getent is used)
#   * --alert: alert once, recover once; a --check run never announces a
#     recovery
#   * -j with --check prints this run's results, not a stale state file
#
# Usage: bash tests/test_health_check.sh
#

set -u

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$TESTS_DIR")"

PASS=0
FAIL=0
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass() { PASS=$((PASS + 1)); echo "  ok   - $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL - $1"; }
assert_eq() {  # assert_eq DESC EXPECTED ACTUAL
    if [ "$2" = "$3" ]; then pass "$1"; else fail "$1 (expected [$2], got [$3])"; fi
}
assert_contains() {  # assert_contains DESC NEEDLE FILE
    if grep -qF -- "$2" "$3"; then pass "$1"; else fail "$1 ([$2] not in $3)"; fi
}
assert_not_contains() {
    if grep -qF -- "$2" "$3"; then fail "$1 ([$2] found in $3)"; else pass "$1"; fi
}

# ---------------------------------------------------------------------------
# A fake project: the script, a .env, and a PATH of stubs. Everything else on
# PATH is linked in, except the resolver tools (each test chooses those).
# ---------------------------------------------------------------------------
mkdir -p "$WORK/project/scripts" "$WORK/bin" "$WORK/sys"
cp "$PROJECT_ROOT/scripts/health_check.sh" "$WORK/project/scripts/"
for dir in /usr/local/bin /usr/bin /bin; do
    for tool in "$dir"/*; do
        name="${tool##*/}"
        case "$name" in docker|curl|host|nslookup|getent|df|free) continue ;; esac
        [ -e "$WORK/sys/$name" ] || ln -s "$tool" "$WORK/sys/$name" 2>/dev/null
    done
done

cat > "$WORK/project/.env" <<'EOF'
N8N_CONTAINER=acme_n8n
POSTGRES_CONTAINER=acme_pg
NGINX_CONTAINER=acme_nginx
MANAGEMENT_CONTAINER=acme_mgmt
POSTGRES_USER=acme
POSTGRES_DB="acmedb"
ALERT_FALLBACK_URL=https://alert.example/topic
EOF

# docker: the acme_* containers run; "$WORK/down" makes acme_pg disappear.
cat > "$WORK/bin/docker" <<EOF
#!/bin/bash
echo "\$*" >> "$WORK/docker.log"
case "\$1" in
    info) exit 0 ;;
    ps)
        echo acme_n8n; echo acme_nginx; echo acme_mgmt
        [ -f "$WORK/down" ] || echo acme_pg
        ;;
    inspect) echo running ;;
    exec)
        case "\$*" in
            *curl*) echo 200 ;;
            *psql*-tAc*) echo 3600 ;;
        esac
        exit 0
        ;;
    *) exit 0 ;;
esac
EOF
cat > "$WORK/bin/curl" <<EOF
#!/bin/bash
for a in "\$@"; do last="\$a"; done
if [ "\$last" = "https://alert.example/topic" ]; then echo "ALERT \$*" >> "$WORK/alerts.log"; fi
exit 0
EOF
printf '#!/bin/bash\necho "Filesystem Size Used Avail Use%% Mounted"; echo "/dev/x 10G 1G 9G 10%% /"\n' > "$WORK/bin/df"
printf '#!/bin/bash\necho "              total used"; echo "Mem: 1000 100 900"\n' > "$WORK/bin/free"
chmod +x "$WORK/bin/"*

mkdir -p "$WORK/resolv"
printf '#!/bin/bash\nexit 0\n' > "$WORK/resolv/getent"
chmod +x "$WORK/resolv/getent"

run_hc() {  # run_hc [args...]  -> exit code in $RC, stdout in $WORK/out
    (cd "$WORK/project" && PATH="$WORK/bin:$EXTRA_PATH:$WORK/sys" bash scripts/health_check.sh "$@" > "$WORK/out" 2>&1)
    RC=$?
}
alerts() { local n; n=$(grep -c '^ALERT' "$WORK/alerts.log" 2>/dev/null); echo "${n:-0}"; }
last_alert_title() { grep '^ALERT' "$WORK/alerts.log" | tail -1 | grep -o 'Title: [^-]*' | sed 's/ *$//'; }

EXTRA_PATH="$WORK/resolv"

echo "Container names and database login from .env"
: > "$WORK/docker.log"
run_hc --quiet
assert_eq "healthy stack with custom names exits 0" 0 "$RC"
assert_contains "pg_isready uses POSTGRES_CONTAINER and POSTGRES_USER" "exec acme_pg pg_isready -U acme" "$WORK/docker.log"
assert_contains "n8n database check uses POSTGRES_DB" "exec acme_pg psql -U acme -d acmedb -c SELECT 1" "$WORK/docker.log"
assert_contains "nginx check uses NGINX_CONTAINER" "exec acme_nginx nginx -t" "$WORK/docker.log"
assert_contains "management check uses MANAGEMENT_CONTAINER" "exec acme_mgmt curl" "$WORK/docker.log"
assert_not_contains "no hardcoded n8n_postgres" "n8n_postgres" "$WORK/docker.log"
assert_not_contains "no hardcoded n8n_nginx" "n8n_nginx" "$WORK/docker.log"

echo "DNS check without host/nslookup"
run_hc --check network
assert_contains "getent resolves" "DNS resolution working" "$WORK/out"
EXTRA_PATH="$WORK/empty"
run_hc --check network
assert_eq "no resolver tool at all is not an error" 0 "$RC"
assert_contains "no resolver tool is a warning" "No resolver tool" "$WORK/out"
EXTRA_PATH="$WORK/resolv"

echo "Alerting"
: > "$WORK/alerts.log"
rm -f "$WORK/project/.health_alert_state"
run_hc --quiet --alert
assert_eq "healthy: no alert" 0 "$(alerts)"
touch "$WORK/down"
run_hc --quiet --alert
assert_eq "postgres down: one alert" 1 "$(alerts)"
assert_eq "alert title" "Title: [$(hostname)] n8n stack UNHEALTHY" "$(last_alert_title)"
run_hc --quiet --alert
assert_eq "still down: not repeated within ALERT_REPEAT_MINUTES" 1 "$(alerts)"
rm -f "$WORK/down"
run_hc --quiet --alert --check network
assert_eq "partial clean run announces no recovery" 1 "$(alerts)"
assert_eq "partial clean run keeps the alert state" "down" "$(cut -d' ' -f1 "$WORK/project/.health_alert_state")"
run_hc --quiet --alert
assert_eq "full clean run announces recovery" 2 "$(alerts)"
assert_eq "recovery title" "Title: [$(hostname)] n8n stack recovered" "$(last_alert_title)"
run_hc --quiet --alert
assert_eq "recovery announced once" 2 "$(alerts)"

echo "JSON output"
echo '{"stale": true}' > "$WORK/project/.health_state"
run_hc --quiet -j --check network
assert_not_contains "-j --check does not print the stale state file" '"stale"' "$WORK/out"
assert_contains "-j --check prints this run's components" '"network_dns": "healthy"' "$WORK/out"
assert_contains "-j --check leaves the full-run state file alone" '"stale"' "$WORK/project/.health_state"
run_hc --quiet -j
assert_contains "-j full run prints the fresh state file" '"postgres": "healthy"' "$WORK/out"

echo ""
echo "Passed: $PASS  Failed: $FAIL"
[ "$FAIL" -eq 0 ]
