#!/bin/bash

# n8n HTTPS Setup Script with Let's Encrypt + DNS Provider
# Automated SSL certificate setup and deployment
#
# Version 1.0.0
# Richard J. Sears
# richardjsears@gmail.com
# November 22, 2025


set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== n8n HTTPS Setup with Let's Encrypt ===${NC}"
echo ""

# Check if cloudflare.ini exists
if [ ! -f "cloudflare.ini" ]; then
    echo -e "${RED}Error: cloudflare.ini not found!${NC}"
    echo ""
    echo "Please create cloudflare.ini from the example:"
    echo "  1. cp cloudflare.ini.example cloudflare.ini"
    echo "  2. Edit cloudflare.ini and add your Cloudflare API token"
    echo ""
    echo "For other DNS providers, see README.md for configuration"
    exit 1
fi

# Check if API token is set
if grep -q "YOUR_CLOUDFLARE_API_TOKEN_HERE" cloudflare.ini; then
    echo -e "${RED}Error: Cloudflare API token not configured!${NC}"
    echo ""
    echo "Please edit cloudflare.ini and replace YOUR_CLOUDFLARE_API_TOKEN_HERE"
    echo "with your actual Cloudflare API token"
    exit 1
fi

# Set correct permissions on cloudflare.ini
chmod 600 cloudflare.ini

echo -e "${YELLOW}Step 1: Checking configuration...${NC}"

# Check if port 443 is available
if netstat -tulpn 2>/dev/null | grep -q ':443 ' || ss -tulpn 2>/dev/null | grep -q ':443 '; then
    echo -e "${YELLOW}Warning: Port 443 appears to be in use${NC}"
    echo "This setup requires port 443 for HTTPS access."
    echo ""
    netstat -tulpn 2>/dev/null | grep ':443 ' || ss -tulpn 2>/dev/null | grep ':443 '
    echo ""
    read -p "Continue anyway? The container may fail to start. (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓ Port 443 is available${NC}"
fi
echo ""

# Check if docker-compose.yaml has been configured
if grep -q "change_this_to_random_secure_key_min_10_chars" docker-compose.yaml; then
    echo -e "${YELLOW}Warning: Please update N8N_ENCRYPTION_KEY in docker-compose.yaml${NC}"
    echo "Generate one with: openssl rand -base64 32"
    echo ""
    read -p "Press Enter to continue anyway, or Ctrl+C to exit and fix it..."
fi

if grep -q "n8n.yourdomain.com" docker-compose.yaml; then
    echo -e "${YELLOW}Warning: Domain still set to n8n.yourdomain.com in docker-compose.yaml${NC}"
    echo "Please update lines 36-38 with your actual domain"
    echo ""
    read -p "Press Enter to continue anyway, or Ctrl+C to exit and fix it..."
fi

echo -e "${GREEN}✓ Configuration looks good${NC}"
echo ""

echo -e "${YELLOW}Step 2: Creating external letsencrypt volume...${NC}"
# Create the external letsencrypt volume that docker-compose will use
docker volume create letsencrypt || echo "Volume already exists"
echo -e "${GREEN}✓ Volume created${NC}"
echo ""

echo -e "${YELLOW}Step 3: Starting PostgreSQL...${NC}"
docker-compose up -d postgres

echo "Waiting for PostgreSQL to be ready..."
sleep 10
echo -e "${GREEN}✓ PostgreSQL is running${NC}"
echo ""

# Extract domain from docker-compose.yaml
DOMAIN=$(grep "N8N_HOST=" docker-compose.yaml | head -1 | cut -d'=' -f2)

echo -e "${YELLOW}Step 4: Obtaining SSL certificate from Let's Encrypt...${NC}"
echo "Domain: $DOMAIN"
echo "This will use DNS-01 challenge (no ports 80/443 exposure required)"
echo ""

# Run certbot to get certificate and save to local directory first
docker run --rm \
    -v "$(pwd)/letsencrypt-temp:/etc/letsencrypt" \
    -v "$(pwd)/cloudflare.ini:/cloudflare.ini:ro" \
    certbot/dns-cloudflare:latest \
    certonly \
    --dns-cloudflare \
    --dns-cloudflare-credentials /cloudflare.ini \
    --dns-cloudflare-propagation-seconds 60 \
    -d $DOMAIN \
    --agree-tos \
    --non-interactive \
    --email admin@$(echo $DOMAIN | cut -d'.' -f2-)

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ SSL certificate obtained successfully!${NC}"
    echo ""
else
    echo ""
    echo -e "${RED}✗ Failed to obtain SSL certificate${NC}"
    echo "Please check:"
    echo "  - Your DNS provider API token has correct permissions"
    echo "  - The domain $DOMAIN is in your DNS provider account"
    echo "  - DNS is properly configured and propagated"
    exit 1
fi

echo -e "${YELLOW}Step 5: Copying certificates to Docker volume...${NC}"
# Copy certificates from temp directory to the external volume
# Use -L to follow symlinks and copy actual files
docker run --rm \
    -v "$(pwd)/letsencrypt-temp:/source:ro" \
    -v letsencrypt:/dest \
    alpine \
    sh -c "cp -rL /source/* /dest/"

echo -e "${GREEN}✓ Certificates copied to Docker volume${NC}"

# Clean up temp directory
rm -rf letsencrypt-temp

echo ""

echo -e "${YELLOW}Step 6: Starting all services...${NC}"
docker-compose up -d

echo ""
echo -e "${GREEN}=== Setup Complete! ===${NC}"
echo ""
echo "Your n8n instance should now be accessible at:"
echo -e "${GREEN}https://$DOMAIN${NC}"
echo ""
echo "Check the status with:"
echo "  docker-compose ps"
echo ""
echo "View logs with:"
echo "  docker-compose logs -f n8n"
echo ""
echo -e "${YELLOW}Note: Certificates will auto-renew every 12 hours via the certbot container${NC}"
echo ""
echo "Create your owner account and start automating! 🚀"
