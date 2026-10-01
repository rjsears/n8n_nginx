#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /tests/test_image_pins.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#
# Installs use the compose file that setup.sh generates, not the reference
# docker-compose.yaml in the repository; Dependabot only bumps the latter.
# This check fails when the two disagree on an image tag, so a Dependabot PR
# cannot merge until the same pin is made in setup.sh.
#
# Usage: bash tests/test_image_pins.sh
#

set -u

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$TESTS_DIR")"
SETUP_SH="${PROJECT_ROOT}/setup.sh"
COMPOSE="${PROJECT_ROOT}/docker-compose.yaml"

# "repo tag" for every pinned image: line in a file. ${VAR:-default}
# resolves to its default; images with no default (${MANAGEMENT_IMAGE}) and
# locally built ones are skipped.
image_pins() {
    sed -n 's/^[[:space:]]*image:[[:space:]]*//p' "$1" \
        | sed 's/\\\$/$/g; s/[[:space:]]*$//; s/^"//; s/"$//' \
        | sed -E 's/^\$\{[A-Z0-9_]+:-(.+)\}$/\1/; s/^([^:$]+):\$\{[A-Z0-9_]+:-(.+)\}$/\1:\2/' \
        | grep -v '\$' \
        | grep -v ':local$' \
        | sed -E 's/^(.+):([^:/]+)$/\1 \2/' \
        | sort -u
}

script_version=$(sed -n 's/^SCRIPT_VERSION="\(.*\)"$/\1/p' "$SETUP_SH" | head -1)
certbot_version=$(sed -n 's/^CERTBOT_VERSION="\(.*\)"$/\1/p' "$SETUP_SH" | head -1)

FAIL=0
fail() { FAIL=$((FAIL + 1)); echo "  FAIL - $1"; }

setup_pins=$(image_pins "$SETUP_SH"; echo "certbot/certbot ${certbot_version}"; \
    echo "rjsears/n8n_management ${script_version}"; echo "rjsears/n8n_status ${script_version}")
compose_pins=$(image_pins "$COMPOSE")

if [ -z "$compose_pins" ] || [ -z "$(image_pins "$SETUP_SH")" ]; then
    echo "Could not read any image pins" >&2
    exit 1
fi

while read -r repo tag; do
    [ -n "$repo" ] || continue
    setup_tags=$(printf '%s\n' "$setup_pins" | awk -v r="$repo" '$1 == r { print $2 }' | sort -u | tr '\n' ' ')
    if [ -z "$setup_tags" ]; then
        fail "$repo:$tag is in docker-compose.yaml but setup.sh never uses $repo"
    elif [ "$setup_tags" != "$tag " ]; then
        fail "$repo: docker-compose.yaml pins $tag, setup.sh pins ${setup_tags% }"
    else
        echo "  ok   - $repo:$tag"
    fi
done <<< "$compose_pins"

# Within setup.sh one image must not be pinned to two tags.
while read -r repo; do
    [ -n "$repo" ] || continue
    fail "setup.sh pins $repo to more than one tag: $(printf '%s\n' "$setup_pins" | awk -v r="$repo" '$1 == r { print $2 }' | sort -u | tr '\n' ' ')"
done < <(printf '%s\n' "$setup_pins" | sort -u | awk '{ print $1 }' | uniq -d)

if [ "$FAIL" -gt 0 ]; then
    echo "$FAIL image pin mismatch(es): bump the tag in setup.sh (generate_docker_compose_v3 / *_VERSION) too"
    exit 1
fi
echo "Image pins agree"
