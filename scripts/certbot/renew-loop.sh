#!/bin/sh
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /scripts/certbot/renew-loop.sh
#
# Part of the "n8n_nginx/n8n_management" suite
#
# Entrypoint of the certbot container (mounted read-only at /opt/n8n-certbot).
#
#  - Installs the nginx reload deploy hook into
#    /etc/letsencrypt/renewal-hooks/deploy/, so EVERY `certbot renew`
#    (this loop, the management console's "force renew", the repair script)
#    reloads nginx after a successful renewal. The hook talks to the Docker
#    API over the socket with Python's stdlib, so nothing has to be installed
#    at container start (the previous `apk add docker-cli` needed network
#    access on every start and its failures were silently discarded).
#  - Runs `certbot renew` every RENEW_INTERVAL (default 12h). Failures are
#    NOT swallowed: they are logged to stdout (`docker logs n8n_certbot`) and
#    to /etc/letsencrypt/n8n-renewal.log, the result is written to
#    /etc/letsencrypt/n8n-renewal-status.json, and the loop retries after
#    RENEW_RETRY_INTERVAL (default 1h) instead of dying.
#  - Warns about broken lineages (live/*.pem that are regular files instead of
#    symlinks into archive/), which certbot refuses to renew.
#    Fix those with ./scripts/repair_ssl_lineage.sh on the host.
#
# certbot renew re-uses the authenticator and credentials path recorded in
# /etc/letsencrypt/renewal/<name>.conf at issuance, so no DNS flags are
# passed here (passing them would override every lineage's own settings).
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

LE_DIR="/etc/letsencrypt"
LOG_FILE="${LE_DIR}/n8n-renewal.log"
STATUS_FILE="${LE_DIR}/n8n-renewal-status.json"
HOOK_SRC="/opt/n8n-certbot/reload-nginx-hook.py"
HOOK_DIR="${LE_DIR}/renewal-hooks/deploy"
HOOK_DST="${HOOK_DIR}/n8n-reload-nginx"
RENEW_INTERVAL="${RENEW_INTERVAL:-12h}"
RENEW_RETRY_INTERVAL="${RENEW_RETRY_INTERVAL:-1h}"
OUT_FILE="/tmp/n8n-certbot-renew.out"

log() {
    line="$(date -u '+%Y-%m-%dT%H:%M:%SZ') [n8n-certbot] $*"
    echo "$line"
    echo "$line" >> "$LOG_FILE" 2>/dev/null || true
}

trim_log() {
    # Keep the log file bounded (last 2000 lines once it exceeds 5000)
    if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE")" -gt 5000 ]; then
        tail -n 2000 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
    fi
}

write_status() {
    # $1 = ok|failed  $2 = certbot exit code  $3 = broken lineages (space separated)
    printf '{"status": "%s", "exit_code": %s, "last_run": "%s", "broken_lineages": "%s", "log_file": "%s"}\n' \
        "$1" "$2" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$3" "$LOG_FILE" > "${STATUS_FILE}.tmp" \
        && mv "${STATUS_FILE}.tmp" "$STATUS_FILE"
}

install_hook() {
    if [ ! -f "$HOOK_SRC" ]; then
        log "ERROR: deploy hook $HOOK_SRC not found - nginx will NOT be reloaded after renewal"
        return 1
    fi
    if mkdir -p "$HOOK_DIR" && cp "$HOOK_SRC" "$HOOK_DST" && chmod 755 "$HOOK_DST"; then
        log "Installed nginx reload deploy hook: $HOOK_DST"
    else
        log "ERROR: could not install deploy hook into $HOOK_DIR"
        return 1
    fi
}

find_broken_lineages() {
    broken=""
    for dir in "$LE_DIR"/live/*/; do
        [ -d "$dir" ] || continue
        name=$(basename "$dir")
        for kind in cert chain fullchain privkey; do
            if [ ! -L "${dir}${kind}.pem" ]; then
                broken="$broken $name"
                break
            fi
        done
    done
    echo "$broken" | sed 's/^ *//'
}

trap 'log "Received stop signal, exiting"; exit 0' TERM INT

log "Starting certbot renewal loop (interval ${RENEW_INTERVAL}, retry after failure ${RENEW_RETRY_INTERVAL})"
install_hook

while :; do
    trim_log
    broken=$(find_broken_lineages)
    if [ -n "$broken" ]; then
        log "ERROR: broken certificate lineage(s): ${broken}"
        log "ERROR: live/*.pem are regular files, not symlinks into archive/ - certbot will NOT renew them."
        log "ERROR: repair on the host with: ./scripts/repair_ssl_lineage.sh  (see docs/CERTBOT.md)"
    fi

    log "Running: certbot renew --no-random-sleep-on-renew"
    certbot renew --no-random-sleep-on-renew > "$OUT_FILE" 2>&1
    rc=$?
    cat "$OUT_FILE"
    cat "$OUT_FILE" >> "$LOG_FILE" 2>/dev/null || true

    if [ "$rc" -eq 0 ] && [ -z "$broken" ]; then
        log "certbot renew finished successfully; next check in ${RENEW_INTERVAL}"
        write_status "ok" "$rc" ""
        sleep_for="$RENEW_INTERVAL"
    else
        if [ "$rc" -ne 0 ]; then
            log "ERROR: certbot renew FAILED (exit code ${rc}) - certificates are NOT being renewed. Retrying in ${RENEW_RETRY_INTERVAL}."
        else
            log "ERROR: certbot renew skipped broken lineage(s): ${broken}. Retrying in ${RENEW_RETRY_INTERVAL}."
        fi
        write_status "failed" "$rc" "$broken"
        sleep_for="$RENEW_RETRY_INTERVAL"
    fi

    sleep "$sleep_for" &
    wait $!
done
