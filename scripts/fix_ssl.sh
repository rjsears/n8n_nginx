#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /scripts/fix_ssl.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 1st, 2026
#
# Richard J. Sears
# richard@n8nmanagement.net
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# SSL Certificate Diagnostic and Repair Script
# This script diagnoses and fixes SSL certificate issues for nginx

set -e

DOMAIN="${1:-loftai5.loft.aero}"
VOLUME="letsencrypt"

echo "=== SSL Certificate Diagnostic Script ==="
echo "Domain: $DOMAIN"
echo ""

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: docker command not found"
    exit 1
fi

echo "=== Step 1: Checking letsencrypt volume ==="
if docker volume inspect $VOLUME >/dev/null 2>&1; then
    echo "✓ Volume '$VOLUME' exists"
else
    echo "✗ Volume '$VOLUME' does not exist!"
    echo "Creating volume..."
    docker volume create $VOLUME
    echo "You will need to obtain a new certificate. Run: ./setup.sh"
    exit 1
fi

echo ""
echo "=== Step 2: Checking volume contents ==="
echo "Contents of /etc/letsencrypt:"
docker run --rm -v $VOLUME:/certs alpine ls -la /certs/

echo ""
echo "=== Step 3: Checking live directory ==="
if docker run --rm -v $VOLUME:/certs alpine test -d /certs/live; then
    echo "✓ live/ directory exists"
    echo ""
    echo "Available domain directories:"
    docker run --rm -v $VOLUME:/certs alpine ls -la /certs/live/
else
    echo "✗ live/ directory does not exist!"
    echo "The certificate may not have been obtained. Run: ./setup.sh"
    exit 1
fi

echo ""
echo "=== Step 4: Checking specific domain directory ==="
if docker run --rm -v $VOLUME:/certs alpine test -d "/certs/live/$DOMAIN"; then
    echo "✓ live/$DOMAIN/ directory exists"
    echo ""
    echo "Certificate files:"
    docker run --rm -v $VOLUME:/certs alpine ls -la "/certs/live/$DOMAIN/"
else
    echo "✗ live/$DOMAIN/ directory does not exist!"
    echo ""
    echo "Available domains in live/:"
    docker run --rm -v $VOLUME:/certs alpine ls /certs/live/ 2>/dev/null || echo "  (none)"
    echo ""
    echo "The domain in nginx.conf may not match the certificate domain."
    exit 1
fi

echo ""
echo "=== Step 5: Checking certificate files ==="
CERT_EXISTS=$(docker run --rm -v $VOLUME:/certs alpine test -f "/certs/live/$DOMAIN/fullchain.pem" && echo "yes" || echo "no")
KEY_EXISTS=$(docker run --rm -v $VOLUME:/certs alpine test -f "/certs/live/$DOMAIN/privkey.pem" && echo "yes" || echo "no")

if [ "$CERT_EXISTS" = "yes" ] && [ "$KEY_EXISTS" = "yes" ]; then
    echo "✓ fullchain.pem exists"
    echo "✓ privkey.pem exists"

    # Check if they are files or symlinks
    echo ""
    echo "File types:"
    docker run --rm -v $VOLUME:/certs alpine file "/certs/live/$DOMAIN/fullchain.pem"
    docker run --rm -v $VOLUME:/certs alpine file "/certs/live/$DOMAIN/privkey.pem"

    # If symlinks, check if they resolve
    echo ""
    echo "Checking symlink resolution (if applicable):"
    docker run --rm -v $VOLUME:/certs alpine sh -c "cat /certs/live/$DOMAIN/fullchain.pem | head -c 100 && echo '...'" 2>/dev/null && echo "✓ fullchain.pem is readable" || echo "✗ fullchain.pem cannot be read"
else
    echo "✗ Certificate files are missing!"
    [ "$CERT_EXISTS" = "no" ] && echo "  - fullchain.pem is missing"
    [ "$KEY_EXISTS" = "no" ] && echo "  - privkey.pem is missing"

    # Check archive directory
    echo ""
    echo "Checking archive directory:"
    docker run --rm -v $VOLUME:/certs alpine ls -la "/certs/archive/$DOMAIN/" 2>/dev/null || echo "  Archive directory not found"

    echo ""
    echo "Attempting to fix symlinks..."
    fix_symlinks
fi

echo ""
echo "=== Step 6: Verifying nginx can access certificates ==="
docker compose exec nginx test -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" 2>/dev/null && echo "✓ nginx can access fullchain.pem" || echo "✗ nginx cannot access fullchain.pem"
docker compose exec nginx test -f "/etc/letsencrypt/live/$DOMAIN/privkey.pem" 2>/dev/null && echo "✓ nginx can access privkey.pem" || echo "✗ nginx cannot access privkey.pem"

echo ""
echo "=== Diagnostic complete ==="
echo ""
echo "If certificates are missing or broken, you have two options:"
echo ""
echo "Option 1: Re-run setup to obtain new certificates"
echo "  ./setup.sh"
echo ""
echo "Option 2: Manually obtain a certificate"
echo "  docker run --rm -it \\"
echo "    -v letsencrypt:/etc/letsencrypt \\"
echo "    -v ./cloudflare.ini:/cloudflare.ini:ro \\"
echo "    certbot/dns-cloudflare certonly \\"
echo "    --dns-cloudflare \\"
echo "    --dns-cloudflare-credentials /cloudflare.ini \\"
echo "    -d $DOMAIN \\"
echo "    --agree-tos \\"
echo "    --non-interactive \\"
echo "    --email your@email.com"
echo ""
echo "After obtaining certificates, restart nginx:"
echo "  docker compose restart nginx"
