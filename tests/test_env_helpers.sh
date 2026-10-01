#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /tests/test_env_helpers.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#
# Regression tests for the .env handling in setup.sh (no Docker required):
#   * re-running the installer (reconfigure / migration) must keep existing
#     secrets (POSTGRES_PASSWORD, N8N_ENCRYPTION_KEY, ...) and every key it
#     does not manage (N8N_API_KEY, NTFY_TOKEN, custom variables, comments)
#   * values with special characters must round-trip through the installer,
#     `source .env` and the management console's Python parser
#   * a required secret that ends up empty aborts instead of writing .env
#
# Usage: bash tests/test_env_helpers.sh
#

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

# ---------------------------------------------------------------------------
# Extract the functions under test from setup.sh (without running main)
# ---------------------------------------------------------------------------
extract_function() {
    awk -v name="$1" '
        $0 ~ "^" name "\\(\\) \\{" { printing = 1 }
        printing { print }
        printing && /^}/ { exit }
    ' "$SETUP_SH"
}

FUNCS=(env_quote_value env_unquote_value env_get_key env_set_key env_key_map
       env_adopt_existing_values n8n_config_extract_key random_secret generate_env_file)
for f in "${FUNCS[@]}"; do
    body="$(extract_function "$f")"
    if [ -z "$body" ]; then
        echo "Could not extract function '$f' from setup.sh" >&2
        exit 1
    fi
    eval "$body"
done

# Stubs for installer helpers / Docker access
print_info() { :; }
print_success() { :; }
print_warning() { :; }
print_error() { echo "    [error] $*" >&2; }
command_exists() { command -v "$1" >/dev/null 2>&1; }
STUB_VOLUME_KEY=""
STUB_PG_VOLUME=false
read_n8n_encryption_key_from_volume() { [ -n "$STUB_VOLUME_KEY" ] && printf '%s' "$STUB_VOLUME_KEY"; }
detect_running_postgres_password() { return 1; }
find_compose_volume() { [ "$STUB_PG_VOLUME" = true ] && echo "proj_$1"; }

DEFAULT_POSTGRES_CONTAINER="n8n_postgres"
DEFAULT_N8N_CONTAINER="n8n"
DEFAULT_NGINX_CONTAINER="n8n_nginx"
DEFAULT_CERTBOT_CONTAINER="n8n_certbot"
DEFAULT_MANAGEMENT_CONTAINER="n8n_management"
DEFAULT_MGMT_PORT="3333"
eval "$(grep '^CERTBOT_VERSION=' "$SETUP_SH")"

# Values that historically broke the installer / compose
SPECIAL_VALUES=(
    'plainValue123'
    'abc+/def=='
    'p@ss/w&rd=1'
    'a$b${HOME}$(id)'
    "it's"
    '"double"'
    'back\slash\\n'
    'tick`id`'
    'with space'
    '#hash'
    'a # not a comment'
    "mix'\"\$\\all"
    "q'uote \\\\ \$HOME"
    '='
    '&|;<>*?~!'
    ''
    'C:\dir\'
    '\'
    'Pa55w0rd\'
    "it's\\"
)

ENV_FILE_PY="${PROJECT_ROOT}/management/api/services/env_file.py"
python_decode() {  # python_decode FILE KEY -> value via management/api/services/env_file.py
    # Load the module by path: the api package __init__ pulls in FastAPI/SQLAlchemy
    python3 - "$ENV_FILE_PY" "$1" "$2" << 'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("env_file", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
v = mod.read_env_value(sys.argv[2], sys.argv[3])
sys.stdout.write("<None>" if v is None else v)
PY
}
python_encode() {  # python_encode VALUE -> encoded .env value via env_file.encode_env_value
    python3 - "$ENV_FILE_PY" "$1" << 'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("env_file", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
try:
    sys.stdout.write(mod.encode_env_value(sys.argv[2]))
except ValueError:
    sys.stdout.write("<rejected>")
PY
}
HAVE_PY=false
if command -v python3 >/dev/null 2>&1 && [ -f "$ENV_FILE_PY" ]; then
    HAVE_PY=true
else
    echo "  (python3 not found - console parser checks skipped)"
fi

# ---------------------------------------------------------------------------
echo "1. special characters round-trip (installer, bash source, console parser)"
# ---------------------------------------------------------------------------
f="${WORK_DIR}/special.env"
: > "$f"
i=0
for v in "${SPECIAL_VALUES[@]}"; do
    env_set_key "$f" "KEY_$i" "$v" || fail "env_set_key KEY_$i"
    i=$((i + 1))
done
i=0
for v in "${SPECIAL_VALUES[@]}"; do
    got=$(env_get_key "$f" "KEY_$i")
    assert_eq "env_get_key KEY_$i [$v]" "$v" "$got"
    sourced=$(set -a; . "$f"; eval "printf '%s' \"\${KEY_$i}\"")
    assert_eq "bash source KEY_$i [$v]" "$v" "$sourced"
    if [ "$HAVE_PY" = true ]; then
        assert_eq "python parser KEY_$i [$v]" "$v" "$(python_decode "$f" "KEY_$i")"
        assert_eq "python encoder matches setup.sh KEY_$i [$v]" "$(env_quote_value "$v")" "$(python_encode "$v")"
    fi
    i=$((i + 1))
done
if env_set_key "$f" BAD $'line1\nline2' 2>/dev/null; then
    fail "newline value must be rejected"
else
    pass "newline value rejected"
fi
if env_set_key "$f" BAD "it's \`x\`" 2>/dev/null; then
    fail "value with both ' and \` must be rejected"
else
    pass "value with both ' and \` rejected"
fi
if env_set_key "$f" BAD 'tick`x`\' 2>/dev/null; then
    fail "value with \` and a trailing backslash must be rejected"
else
    pass "value with \` and a trailing backslash rejected"
fi
if [ "$HAVE_PY" = true ]; then
    assert_eq "python encoder rejects \` + trailing backslash" "<rejected>" "$(python_encode 'tick`x`\')"
fi
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
    cdir="${WORK_DIR}/compose_special"
    mkdir -p "$cdir"
    cp "$f" "${cdir}/.env"
    {
        printf 'services:\n  t:\n    image: busybox\n    environment:\n'
        i=0
        for v in "${SPECIAL_VALUES[@]}"; do
            printf '      - V%d=${KEY_%d}\n' "$i" "$i"
            i=$((i + 1))
        done
    } > "${cdir}/docker-compose.yaml"
    cjson=$(cd "$cdir" && docker compose config --format json 2>/dev/null)
    i=0
    for v in "${SPECIAL_VALUES[@]}"; do
        # `compose config` re-escapes literal $ as $$ in its output; undo that
        got=$(printf '%s' "$cjson" | jq -r ".services.t.environment.V$i // \"\"" | sed 's/\$\$/$/g')
        assert_eq "docker compose KEY_$i [$v]" "$v" "$got"
        i=$((i + 1))
    done
else
    echo "  skip - docker compose / jq not available (compose parsing not checked)"
fi

# ---------------------------------------------------------------------------
echo "2. env_set_key preserves other lines, handles export/duplicates, mode 600"
# ---------------------------------------------------------------------------
f="${WORK_DIR}/preserve.env"
cat > "$f" << 'EOF'
# leading comment
FOO=bar
export TARGET=old
UNRELATED='keep $me'
TARGET=duplicate
# trailing comment
EOF
chmod 644 "$f"
env_set_key "$f" TARGET 'n&w/v@l$'
assert_eq "TARGET updated" 'n&w/v@l$' "$(env_get_key "$f" TARGET)"
assert_eq "TARGET appears once" "1" "$(grep -c 'TARGET=' "$f")"
assert_eq "FOO kept" "bar" "$(env_get_key "$f" FOO)"
assert_eq "UNRELATED kept verbatim" "UNRELATED='keep \$me'" "$(grep '^UNRELATED=' "$f")"
assert_eq "comments kept" "2" "$(grep -c '^#' "$f")"
assert_eq "file mode 600" "600" "$(stat -c '%a' "$f")"
before=$(cat "$f")
env_set_key "$f" FOO bar
assert_eq "unchanged value leaves file untouched" "$before" "$(cat "$f")"
env_set_key "$f" NEWKEY 'x y'
assert_eq "new key appended" "x y" "$(env_get_key "$f" NEWKEY)"
ls "$f".tmp.* >/dev/null 2>&1 && fail "temp file left behind" || pass "no temp files left behind"

# ---------------------------------------------------------------------------
echo "3. reconfigure keeps existing secrets and console-managed/unknown keys"
# ---------------------------------------------------------------------------
proj="${WORK_DIR}/reconfigure"
mkdir -p "$proj"
cat > "${proj}/.env" << 'EOF'
# n8n Management System v3.0 - Environment Variables
DOMAIN=n8n.example.com
POSTGRES_USER=n8n
POSTGRES_PASSWORD='s3cr/t&$x"q'
POSTGRES_DB=n8n
N8N_ENCRYPTION_KEY=Abc+/123keyFromInstall==
MGMT_SECRET_KEY=mgmtSecret+/=
MGMT_DB_USER=n8n
MGMT_DB_PASSWORD='s3cr/t&$x"q'
ADMIN_USER=admin
ADMIN_PASS=oldAdminPass
TIMEZONE=Europe/Berlin
NFS_SERVER=10.0.0.5
NFS_PATH=/export/backups
CLOUDFLARE_TUNNEL_TOKEN=cfTokenFromConsole
TAILSCALE_AUTH_KEY=tskey-auth-console
# Custom Variables
N8N_API_KEY=eyJhbGciOiJIUzI1NiJ9.console.key
NTFY_TOKEN=tk_consoletoken
MGMT_ENCRYPTION_KEY='mgmt$enc'
NTFY_ENABLE_LOGIN=true
MY_CUSTOM_SETTING="keep \"me\""
EOF
chmod 600 "${proj}/.env"
(
    # Simulate "Reconfigure -> Domain & SSL": config file values are loaded,
    # secrets are not (DB_PASSWORD was never saved in .n8n_setup_config).
    SCRIPT_DIR="$proj"
    N8N_DOMAIN="new.example.com"
    DB_NAME=n8n; DB_USER=n8n
    POSTGRES_CONTAINER=n8n_postgres; N8N_CONTAINER=n8n; NGINX_CONTAINER=n8n_nginx; CERTBOT_CONTAINER=n8n_certbot
    N8N_TIMEZONE=Europe/Berlin; ADMIN_USER=admin; MGMT_PORT=3333
    INSTALL_PUBLIC_WEBSITE=false
    DNS_CERTBOT_IMAGE="certbot/dns-cloudflare:latest"
    unset DB_PASSWORD N8N_ENCRYPTION_KEY MGMT_SECRET_KEY ADMIN_PASS NFS_SERVER NFS_PATH
    generate_env_file >/dev/null
) || fail "generate_env_file (reconfigure) exited non-zero"
e="${proj}/.env"
assert_eq "DOMAIN updated" "new.example.com" "$(env_get_key "$e" DOMAIN)"
assert_eq "POSTGRES_PASSWORD kept" 's3cr/t&$x"q' "$(env_get_key "$e" POSTGRES_PASSWORD)"
assert_eq "MGMT_DB_PASSWORD kept" 's3cr/t&$x"q' "$(env_get_key "$e" MGMT_DB_PASSWORD)"
assert_eq "N8N_ENCRYPTION_KEY kept" "Abc+/123keyFromInstall==" "$(env_get_key "$e" N8N_ENCRYPTION_KEY)"
assert_eq "MGMT_SECRET_KEY kept" "mgmtSecret+/=" "$(env_get_key "$e" MGMT_SECRET_KEY)"
assert_eq "ADMIN_PASS kept" "oldAdminPass" "$(env_get_key "$e" ADMIN_PASS)"
assert_eq "NFS_SERVER kept" "10.0.0.5" "$(env_get_key "$e" NFS_SERVER)"
assert_eq "CLOUDFLARE_TUNNEL_TOKEN kept" "cfTokenFromConsole" "$(env_get_key "$e" CLOUDFLARE_TUNNEL_TOKEN)"
assert_eq "TAILSCALE_AUTH_KEY kept" "tskey-auth-console" "$(env_get_key "$e" TAILSCALE_AUTH_KEY)"
assert_eq "N8N_API_KEY kept" "eyJhbGciOiJIUzI1NiJ9.console.key" "$(env_get_key "$e" N8N_API_KEY)"
assert_eq "NTFY_TOKEN kept" "tk_consoletoken" "$(env_get_key "$e" NTFY_TOKEN)"
assert_eq "MGMT_ENCRYPTION_KEY kept" 'mgmt$enc' "$(env_get_key "$e" MGMT_ENCRYPTION_KEY)"
assert_eq "NTFY_ENABLE_LOGIN kept" "true" "$(env_get_key "$e" NTFY_ENABLE_LOGIN)"
assert_eq "custom key kept" 'keep "me"' "$(env_get_key "$e" MY_CUSTOM_SETTING)"
assert_eq "custom comment kept" "1" "$(grep -c '^# Custom Variables' "$e")"
# a floating :latest certbot image from an older install is pinned
assert_eq "DNS_CERTBOT_IMAGE written (pinned)" "certbot/dns-cloudflare:${CERTBOT_VERSION}" "$(env_get_key "$e" DNS_CERTBOT_IMAGE)"
assert_eq ".env mode 600" "600" "$(stat -c '%a' "$e")"
sourced=$(set -a; . "$e"; printf '%s' "$POSTGRES_PASSWORD")
assert_eq "POSTGRES_PASSWORD via bash source" 's3cr/t&$x"q' "$sourced"
if [ "$HAVE_PY" = true ]; then
    assert_eq "POSTGRES_PASSWORD via console parser" 's3cr/t&$x"q' "$(python_decode "$e" POSTGRES_PASSWORD)"
fi

# Second run must be a no-op for secrets (idempotent)
cp "$e" "${WORK_DIR}/after_first_run.env"
(
    SCRIPT_DIR="$proj"; N8N_DOMAIN="new.example.com"; DB_NAME=n8n; DB_USER=n8n
    N8N_TIMEZONE=Europe/Berlin; ADMIN_USER=admin; MGMT_PORT=3333; INSTALL_PUBLIC_WEBSITE=false
    POSTGRES_CONTAINER=n8n_postgres; N8N_CONTAINER=n8n; NGINX_CONTAINER=n8n_nginx; CERTBOT_CONTAINER=n8n_certbot
    DNS_CERTBOT_IMAGE="certbot/dns-cloudflare:latest"
    unset DB_PASSWORD N8N_ENCRYPTION_KEY MGMT_SECRET_KEY ADMIN_PASS NFS_SERVER NFS_PATH
    generate_env_file >/dev/null
) || fail "generate_env_file (second run) exited non-zero"
if cmp -s "$e" "${WORK_DIR}/after_first_run.env"; then pass "second reconfigure run is idempotent"; else fail "second reconfigure run changed .env"; fi

# ---------------------------------------------------------------------------
echo "4. optional settings: unset adopts, explicit empty disables"
# ---------------------------------------------------------------------------
(
    SCRIPT_DIR="$proj"; N8N_DOMAIN="new.example.com"; DB_NAME=n8n; DB_USER=n8n
    N8N_TIMEZONE=Europe/Berlin; ADMIN_USER=admin; INSTALL_PUBLIC_WEBSITE=false
    unset DB_PASSWORD N8N_ENCRYPTION_KEY MGMT_SECRET_KEY ADMIN_PASS NFS_PATH
    NFS_SERVER=""   # user disabled NFS in the reconfigure menu
    generate_env_file >/dev/null
) || fail "generate_env_file (disable NFS) exited non-zero"
assert_eq "NFS_SERVER cleared when disabled" "" "$(env_get_key "$e" NFS_SERVER)"
assert_eq "NFS_PATH kept when unset" "/export/backups" "$(env_get_key "$e" NFS_PATH)"

# ---------------------------------------------------------------------------
echo "5. DB password is not changed in .env unless ALTER ROLE was applied"
# ---------------------------------------------------------------------------
(
    SCRIPT_DIR="$proj"; N8N_DOMAIN="new.example.com"; DB_NAME=n8n; DB_USER=n8n
    STUB_PG_VOLUME=true
    DB_PASSWORD="someOtherPassword"
    generate_env_file >/dev/null
) || fail "generate_env_file (unapplied password change) exited non-zero"
assert_eq "unapplied password change ignored" 's3cr/t&$x"q' "$(env_get_key "$e" POSTGRES_PASSWORD)"
(
    SCRIPT_DIR="$proj"; N8N_DOMAIN="new.example.com"; DB_NAME=n8n; DB_USER=n8n
    STUB_PG_VOLUME=true
    DB_PASSWORD="n3w'Pa\$\$word"; DB_PASSWORD_CHANGE_APPLIED=true
    generate_env_file >/dev/null
) || fail "generate_env_file (applied password change) exited non-zero"
assert_eq "applied password change written" "n3w'Pa\$\$word" "$(env_get_key "$e" POSTGRES_PASSWORD)"
assert_eq "MGMT_DB_PASSWORD follows" "n3w'Pa\$\$word" "$(env_get_key "$e" MGMT_DB_PASSWORD)"

# ---------------------------------------------------------------------------
echo "6. encryption key from the n8n data volume wins over a mismatching key"
# ---------------------------------------------------------------------------
(
    SCRIPT_DIR="$proj"; N8N_DOMAIN="new.example.com"; DB_NAME=n8n; DB_USER=n8n
    STUB_VOLUME_KEY="volumeKey123"
    N8N_ENCRYPTION_KEY="freshlyGeneratedWrongKey"
    generate_env_file >/dev/null
) || fail "generate_env_file (volume key) exited non-zero"
assert_eq "volume key written" "volumeKey123" "$(env_get_key "$e" N8N_ENCRYPTION_KEY)"
cfg=$'{\n\t"encryptionKey": "Zx9+/abc=="\n}'
assert_eq "n8n config key parsed" "Zx9+/abc==" "$(printf '%s' "$cfg" | n8n_config_extract_key)"
assert_eq "compact n8n config key parsed" "k1" "$(printf '{"encryptionKey":"k1","x":1}' | n8n_config_extract_key)"

# ---------------------------------------------------------------------------
echo "7. empty required secret aborts without writing .env"
# ---------------------------------------------------------------------------
proj2="${WORK_DIR}/broken"
mkdir -p "$proj2"
(
    SCRIPT_DIR="$proj2"; N8N_DOMAIN="n8n.example.com"; DB_NAME=n8n; DB_USER=n8n
    N8N_ENCRYPTION_KEY="k"; unset DB_PASSWORD
    generate_env_file >/dev/null 2>&1
)
rc=$?
if [ "$rc" -ne 0 ]; then pass "aborts on empty POSTGRES_PASSWORD (rc=$rc)"; else fail "did not abort on empty POSTGRES_PASSWORD"; fi
[ -f "${proj2}/.env" ] && fail ".env written despite missing secret" || pass ".env not written"

# Same for an existing .env that lost its password
printf 'DOMAIN=x.example.com\nPOSTGRES_PASSWORD=\nN8N_API_KEY=keep\n' > "${proj2}/.env"
cp "${proj2}/.env" "${WORK_DIR}/broken_before.env"
(
    SCRIPT_DIR="$proj2"; N8N_DOMAIN="x.example.com"; DB_NAME=n8n; DB_USER=n8n
    N8N_ENCRYPTION_KEY="k"; unset DB_PASSWORD
    generate_env_file >/dev/null 2>&1
) && fail "did not abort on empty POSTGRES_PASSWORD in existing .env" || pass "aborts when existing .env has empty POSTGRES_PASSWORD"
if cmp -s "${proj2}/.env" "${WORK_DIR}/broken_before.env"; then pass "existing .env left untouched"; else fail "existing .env modified on abort"; fi

# ---------------------------------------------------------------------------
echo "8. brand-new install writes every managed key, special chars survive"
# ---------------------------------------------------------------------------
proj3="${WORK_DIR}/fresh"
mkdir -p "$proj3"
(
    SCRIPT_DIR="$proj3"; N8N_DOMAIN="n8n.example.com"; DB_NAME=n8n; DB_USER=n8n
    DB_PASSWORD="fr\$sh'P&ss/=\"x"; N8N_ENCRYPTION_KEY="k+/="; ADMIN_USER=admin; ADMIN_PASS='adm!n $pass'
    N8N_TIMEZONE=UTC; INSTALL_PUBLIC_WEBSITE=true
    generate_env_file >/dev/null
) || fail "generate_env_file (fresh) exited non-zero"
e3="${proj3}/.env"
missing_keys=""
while IFS='=' read -r key _; do
    grep -q "^${key}=" "$e3" || missing_keys+=" $key"
done < <(env_key_map)
assert_eq "all managed keys present in new .env" "" "$missing_keys"
assert_eq "fresh POSTGRES_PASSWORD" "fr\$sh'P&ss/=\"x" "$(env_get_key "$e3" POSTGRES_PASSWORD)"
assert_eq "fresh ADMIN_PASS" 'adm!n $pass' "$(env_get_key "$e3" ADMIN_PASS)"
assert_eq "fresh MGMT_DB_PASSWORD" "fr\$sh'P&ss/=\"x" "$(env_get_key "$e3" MGMT_DB_PASSWORD)"
assert_eq "fresh PUBLIC_SITE_ENABLE" "true" "$(env_get_key "$e3" PUBLIC_SITE_ENABLE)"
[ -n "$(env_get_key "$e3" MGMT_SECRET_KEY)" ] && pass "MGMT_SECRET_KEY generated" || fail "MGMT_SECRET_KEY empty"
assert_eq "fresh .env mode 600" "600" "$(stat -c '%a' "$e3")"
sourced=$(set -a; . "$e3"; printf '%s|%s' "$POSTGRES_PASSWORD" "$ADMIN_PASS")
assert_eq "fresh .env via bash source" "fr\$sh'P&ss/=\"x|adm!n \$pass" "$sourced"

# ---------------------------------------------------------------------------
echo "9. docker compose reads the values literally (skipped without docker compose)"
# ---------------------------------------------------------------------------
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    cat > "${proj3}/docker-compose.yaml" << 'EOF'
services:
  t:
    image: busybox
    environment:
      - P=${POSTGRES_PASSWORD}
      - A=${ADMIN_PASS}
EOF
    # `compose config` re-escapes literal $ as $$ in its output; undo that
    cfg_out=$(cd "$proj3" && docker compose config --format json 2>/dev/null | sed 's/\$\$/$/g')
    if command -v jq >/dev/null 2>&1 && [ -n "$cfg_out" ]; then
        assert_eq "compose POSTGRES_PASSWORD" "fr\$sh'P&ss/=\"x" "$(printf '%s' "$cfg_out" | jq -r '.services.t.environment.P')"
        assert_eq "compose ADMIN_PASS" 'adm!n $pass' "$(printf '%s' "$cfg_out" | jq -r '.services.t.environment.A')"
    else
        echo "  skip - docker compose config/jq unavailable"
    fi
else
    echo "  skip - docker compose not installed"
fi

echo ""
echo "Passed: $PASS  Failed: $FAIL"
[ "$FAIL" -eq 0 ]
