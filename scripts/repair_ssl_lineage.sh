#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /scripts/repair_ssl_lineage.sh
#
# Part of the "n8n_nginx/n8n_management" suite
#
# Detects and repairs broken Let's Encrypt certificate lineages in the
# `letsencrypt` Docker volume.
#
# Installs made by older versions of setup.sh issued certificates into a
# temporary directory and copied them into the volume with `cp -rL`, which
# turned live/<name>/*.pem into regular files instead of symlinks into
# archive/<name>/. certbot treats such a lineage as broken and silently skips
# it, so the certificate expires after ~90 days.
#
# Usage (run from the n8n_nginx install directory, as a user that can run docker):
#   ./scripts/repair_ssl_lineage.sh --check          # only report, change nothing
#   ./scripts/repair_ssl_lineage.sh                  # repair + renewal dry-run
#   ./scripts/repair_ssl_lineage.sh --force-renew    # repair + dry-run + issue a fresh certificate now
#   ./scripts/repair_ssl_lineage.sh --reissue NAME   # move lineage NAME aside and re-issue it
#                                                    #   (certonly --force-renewal --cert-name NAME)
#
# Repair is non-destructive: the current live/<name>/ files are backed up to
# /etc/letsencrypt/lineage-repair-backup/ in the volume, then live/<name>/*.pem
# are re-created as symlinks to archive/<name>/<kind>N.pem (re-using the newest
# archive version when it is identical, otherwise adding the live files as a
# new archive version). No request is made to Let's Encrypt unless
# --force-renew or --reissue is given.
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VOLUME="letsencrypt"
MODE="repair"
REISSUE_NAME=""

while [ $# -gt 0 ]; do
    case "$1" in
        --check) MODE="check" ;;
        --force-renew) MODE="force" ;;
        --reissue) MODE="reissue"; REISSUE_NAME="${2:-}"; shift ;;
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

# --- helpers -----------------------------------------------------------------

env_value() {
    # Read KEY=value from .env without sourcing it
    local key="$1" default="${2:-}" val=""
    if [ -f "${SCRIPT_DIR}/.env" ]; then
        val=$(grep -E "^${key}=" "${SCRIPT_DIR}/.env" | tail -n 1 | cut -d= -f2-)
        val="${val%\"}"; val="${val#\"}"
    fi
    echo "${val:-$default}"
}

DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
    if sudo -n docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1; then
        DOCKER="sudo docker"
    else
        echo "ERROR: cannot talk to Docker (try running with sudo)" >&2
        exit 1
    fi
fi

APPARMOR_OPT=""
if ! probe=$($DOCKER run --rm alpine true 2>&1) && echo "$probe" | grep -qiE "apparmor|policy admin"; then
    APPARMOR_OPT="--security-opt apparmor=unconfined"
fi

CERTBOT_IMAGE=$(env_value DNS_CERTBOT_IMAGE "certbot/dns-cloudflare:latest")
CRED_FILE=$(env_value DNS_CREDENTIALS_FILE "cloudflare.ini")
CRED_TARGET=$(env_value DNS_CREDENTIALS_TARGET "/credentials.ini")
NGINX_CONTAINER=$(env_value NGINX_CONTAINER "n8n_nginx")

run_certbot() {
    # Runs certbot in a one-off container with the same mounts as the compose
    # certbot service, so the deploy hook can reload nginx.
    local cred_opt=()
    if [ -f "${SCRIPT_DIR}/${CRED_FILE}" ]; then
        cred_opt=(-v "${SCRIPT_DIR}/${CRED_FILE}:${CRED_TARGET}:ro")
    else
        echo "WARNING: credentials file ${SCRIPT_DIR}/${CRED_FILE} not found" >&2
    fi
    # shellcheck disable=SC2086
    $DOCKER run --rm $APPARMOR_OPT \
        -v "${VOLUME}:/etc/letsencrypt" \
        -v /var/run/docker.sock:/var/run/docker.sock:ro \
        -e NGINX_CONTAINER="$NGINX_CONTAINER" \
        ${cred_opt[@]+"${cred_opt[@]}"} \
        "$CERTBOT_IMAGE" "$@"
}

run_alpine() {
    # shellcheck disable=SC2086
    $DOCKER run --rm -i $APPARMOR_OPT -v "${VOLUME}:/etc/letsencrypt" alpine sh -s -- "$@"
}

# --- checks ------------------------------------------------------------------

if ! $DOCKER volume inspect "$VOLUME" >/dev/null 2>&1; then
    echo "ERROR: Docker volume '$VOLUME' does not exist - nothing to repair. Run ./setup.sh to obtain a certificate." >&2
    exit 1
fi

# Prints one line per lineage: "<name> <ok|broken|noconf>"
LINEAGES=$(run_alpine << 'SH'
LE=/etc/letsencrypt
for dir in "$LE"/live/*/; do
    [ -d "$dir" ] || continue
    name=$(basename "$dir")
    state=ok
    for k in cert chain fullchain privkey; do
        [ -L "$dir$k.pem" ] || state=broken
    done
    [ -f "$LE/renewal/$name.conf" ] || state=noconf
    echo "$name $state"
done
SH
)

if [ -z "$LINEAGES" ]; then
    echo "No certificate lineages found in volume '$VOLUME'."
    exit 1
fi

echo "Certificate lineages in volume '$VOLUME':"
echo "$LINEAGES" | sed 's/^/  /'
echo ""

BROKEN=$(echo "$LINEAGES" | awk '$2=="broken"{print $1}')
NOCONF=$(echo "$LINEAGES" | awk '$2=="noconf"{print $1}')

if [ -n "$NOCONF" ]; then
    echo "WARNING: no renewal configuration for: $NOCONF"
    echo "         These cannot be repaired in place. Re-issue with: $0 --reissue <name>"
    echo ""
fi

if [ "$MODE" = "check" ]; then
    if [ -n "$BROKEN" ] || [ -n "$NOCONF" ]; then
        echo "Broken lineage(s) found. Run $0 to repair."
        exit 1
    fi
    echo "All lineages are healthy."
    exit 0
fi

# --- re-issue ----------------------------------------------------------------

if [ "$MODE" = "reissue" ]; then
    if [ -z "$REISSUE_NAME" ]; then
        echo "ERROR: --reissue needs a certificate name (one of: $(echo "$LINEAGES" | awk '{print $1}' | xargs))" >&2
        exit 2
    fi
    case "$CERTBOT_IMAGE" in
        *dns-cloudflare*)   AUTH=(--dns-cloudflare --dns-cloudflare-credentials "$CRED_TARGET" --dns-cloudflare-propagation-seconds 60) ;;
        *dns-digitalocean*) AUTH=(--dns-digitalocean --dns-digitalocean-credentials "$CRED_TARGET" --dns-digitalocean-propagation-seconds 60) ;;
        *dns-google*)       AUTH=(--dns-google --dns-google-credentials "$CRED_TARGET" --dns-google-propagation-seconds 120) ;;
        *dns-route53*)      AUTH=(--dns-route53) ;;
        *)
            echo "ERROR: cannot re-issue automatically with image $CERTBOT_IMAGE (manual DNS provider)." >&2
            echo "       Re-run ./setup.sh from an interactive terminal instead." >&2
            exit 1
            ;;
    esac
    # Domains of the current certificate (SAN list)
    # shellcheck disable=SC2086
    DOMAINS=$($DOCKER run --rm $APPARMOR_OPT -v "${VOLUME}:/etc/letsencrypt:ro" alpine/openssl \
        x509 -in "/etc/letsencrypt/live/${REISSUE_NAME}/cert.pem" -noout -ext subjectAltName 2>/dev/null \
        | grep -o 'DNS:[^,]*' | sed 's/DNS://' | xargs)
    if [ -z "$DOMAINS" ]; then
        echo "ERROR: could not read the domains of live/${REISSUE_NAME}/cert.pem" >&2
        exit 1
    fi
    D_ARGS=()
    read -r -a DOMAIN_LIST <<< "$DOMAINS"   # no globbing of "*.example.com"
    for d in "${DOMAIN_LIST[@]}"; do D_ARGS+=(-d "$d"); done
    echo "Re-issuing '${REISSUE_NAME}' for: $DOMAINS"

    STAMP=$(date +%Y%m%d%H%M%S)
    # Move the broken lineage aside (inside the volume) so certbot creates a clean one with the same name
    run_alpine "$REISSUE_NAME" "$STAMP" << 'SH' || { echo "ERROR: could not move old lineage aside" >&2; exit 1; }
set -e
LE=/etc/letsencrypt; n="$1"; b="$LE/lineage-repair-backup/$n-$2"
mkdir -p "$b"
[ -e "$LE/live/$n" ] && cp -a "$LE/live/$n" "$b/live" && rm -rf "$LE/live/$n"
[ -e "$LE/archive/$n" ] && mv "$LE/archive/$n" "$b/archive"
[ -e "$LE/renewal/$n.conf" ] && mv "$LE/renewal/$n.conf" "$b/renewal.conf"
echo "Old lineage saved to $b"
SH
    if run_certbot certonly "${AUTH[@]}" --cert-name "$REISSUE_NAME" "${D_ARGS[@]}" \
            --force-renewal --non-interactive --agree-tos --register-unsafely-without-email; then
        echo "Certificate re-issued. Reloading nginx..."
        $DOCKER kill -s HUP "$NGINX_CONTAINER" >/dev/null 2>&1 || true
        $DOCKER kill -s HUP n8n_nginx_router >/dev/null 2>&1 || true
        echo "Done. Verify with: docker exec \${CERTBOT_CONTAINER:-n8n_certbot} certbot renew --dry-run"
        exit 0
    fi
    echo "ERROR: re-issue failed - restoring the previous files so nginx keeps working" >&2
    run_alpine "$REISSUE_NAME" "$STAMP" << 'SH'
LE=/etc/letsencrypt; n="$1"; b="$LE/lineage-repair-backup/$n-$2"
rm -rf "$LE/live/$n" "$LE/archive/$n" "$LE/renewal/$n.conf"
[ -e "$b/live" ] && cp -a "$b/live" "$LE/live/$n"
[ -e "$b/archive" ] && cp -a "$b/archive" "$LE/archive/$n"
[ -e "$b/renewal.conf" ] && cp -a "$b/renewal.conf" "$LE/renewal/$n.conf"
SH
    exit 1
fi

# --- in-place repair ---------------------------------------------------------

if [ -z "$BROKEN" ]; then
    echo "No broken lineages (live/*.pem are symlinks)."
else
    for name in $BROKEN; do
        echo "Repairing lineage '$name'..."
        if ! run_alpine "$name" << 'SH'
set -e
LE=/etc/letsencrypt; n="$1"
live="$LE/live/$n"; arch="$LE/archive/$n"
backup="$LE/lineage-repair-backup/$n-$(date +%Y%m%d%H%M%S)"
mkdir -p "$backup" "$arch"
cp -a "$live/." "$backup/"
echo "  backup of live files: $backup"
for k in cert chain fullchain privkey; do
    [ -e "$live/$k.pem" ] || { echo "  ERROR: $live/$k.pem missing - use --reissue $n"; exit 1; }
done
# Newest version present in archive/
max=0
for f in "$arch"/cert*.pem; do
    [ -e "$f" ] || continue
    v=${f##*/cert}; v=${v%.pem}
    case "$v" in ''|*[!0-9]*) continue ;; esac
    [ "$v" -gt "$max" ] && max=$v
done
use=0
if [ "$max" -gt 0 ]; then
    use=$max
    for k in cert chain fullchain privkey; do
        cmp -s "$live/$k.pem" "$arch/$k$max.pem" || use=0
    done
fi
if [ "$use" -eq 0 ]; then
    # live files differ from archive: store them as a new archive version
    use=$((max + 1))
    for k in cert chain fullchain privkey; do
        cp -L "$live/$k.pem" "$arch/$k$use.pem"
    done
    chmod 644 "$arch"/cert$use.pem "$arch"/chain$use.pem "$arch"/fullchain$use.pem
    chmod 600 "$arch/privkey$use.pem"
    echo "  stored live files as archive version $use"
else
    echo "  live files match archive version $use"
fi
for k in cert chain fullchain privkey; do
    ln -sfn "../../archive/$n/$k$use.pem" "$live/$k.pem"
done
ls -l "$live" | sed 's/^/  /'
SH
        then
            echo "ERROR: repair of '$name' failed. Try: $0 --reissue $name" >&2
            exit 1
        fi
    done
    echo ""
fi

echo "Checking that renewal works (certbot renew --dry-run, uses the Let's Encrypt staging server)..."
if ! run_certbot renew --dry-run --no-random-sleep-on-renew; then
    echo ""
    echo "ERROR: renewal dry-run FAILED. Check the DNS credentials file (${CRED_FILE}) and docs/CERTBOT.md." >&2
    exit 1
fi
echo "Renewal dry-run succeeded."

if [ "$MODE" = "force" ]; then
    for name in $(echo "$LINEAGES" | awk '$2!="noconf"{print $1}'); do
        echo "Forcing renewal of '$name'..."
        run_certbot renew --force-renewal --no-random-sleep-on-renew --cert-name "$name" || exit 1
    done
fi

echo ""
echo "Restarting the certbot container so the renewal loop picks up the repaired lineage(s)..."
$DOCKER restart "$(env_value CERTBOT_CONTAINER n8n_certbot)" >/dev/null 2>&1 \
    || echo "  (certbot container not running - start it with: docker compose up -d certbot)"
echo "Done."
