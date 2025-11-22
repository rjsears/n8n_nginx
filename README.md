# n8n with HTTPS using Docker, Nginx & Let's Encrypt

**Version:** 1.0.0  
**Release Date:** November 22, 2025

![Last Commit](https://img.shields.io/github/last-commit/rjsears/n8n_nginx)
![Issues](https://img.shields.io/github/issues/rjsears/n8n_nginx)
![License](https://img.shields.io/badge/license-MIT-green)
![Contributors](https://img.shields.io/github/contributors/rjsears/n8n_nginx)
![Release](https://img.shields.io/github/v/release/rjsears/n8n_nginx)

A production-ready deployment of n8n workflow automation with HTTPS, automated SSL certificate management, and PostgreSQL with pgvector for AI/RAG workflows. Uses DNS-01 challenge for certificate validation - no port 80/443 internet exposure required!

---

## Table of Contents

- [What This Deploys](#what-this-deploys)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [DNS Provider Setup](#dns-provider-setup)
  - [Cloudflare Setup](#cloudflare-setup)
  - [Other DNS Providers](#other-dns-providers)
- [Installation](#installation)
  - [Step 1: Clone Repository](#step-1-clone-repository)
  - [Step 2: Configure DNS Credentials](#step-2-configure-dns-credentials)
  - [Step 3: Edit Configuration](#step-3-edit-configuration)
  - [Step 4: Run Setup](#step-4-run-setup)
- [SSL Certificate Auto-Renewal](#ssl-certificate-auto-renewal)
- [Accessing n8n](#accessing-n8n)
- [Docker Commands Reference](#docker-commands-reference)
- [Troubleshooting](#troubleshooting)
- [Architecture](#architecture)
- [Security Notes](#security-notes)
- [Contributing](#contributing)
- [License](#license)

---

## What This Deploys

This setup deploys a complete, production-ready n8n automation platform with:

- **n8n** - Workflow automation tool (latest version)
- **PostgreSQL 16** - Database with pgvector extension for AI embeddings
- **Nginx** - Reverse proxy handling SSL/TLS termination
- **Certbot** - Automated SSL certificate management via Let's Encrypt
- **Docker Compose** - Container orchestration

All running on **port 443 (HTTPS)** with valid SSL certificates that automatically renew.

---

## Features

- **One-Command Setup** - Fully automated installation  
- **Valid SSL Certificates** - Let's Encrypt with auto-renewal  
- **DNS-01 Challenge** - No port 80/443 internet exposure needed  
- **Multiple DNS Providers** - Cloudflare, Route53, Google DNS, and more  
- **PostgreSQL + pgvector** - Ready for AI/RAG workflows  
- **Auto-Renewal** - Certificates check and renew every 12 hours  
- **Production Ready** - Proper security headers, timeouts, and configurations  
- **Easy Maintenance** - Simple docker-compose commands  

---

## Prerequisites

### Required

- **Docker** and **Docker Compose** installed
- **Domain name** with DNS managed by a supported provider
- **DNS API access** (API token/credentials from your DNS provider)
- **Server/VPS** with at least:
  - 2 CPU cores
  - 2GB RAM
  - 10GB disk space
  - Internet access to reach DNS provider API

### Supported Operating Systems

- **Linux:** Ubuntu 20.04+, Debian 11+, CentOS 8+, or any distribution with Docker support
- **macOS:** macOS 10.15+ with Docker Desktop
- **Windows:** Windows 10/11 with Docker Desktop (WSL2 backend)

---

## DNS Provider Setup

This setup uses **DNS-01 challenge** for certificate validation, which means you need API access to your DNS provider. This allows certificate generation without exposing ports 80/443 to the internet.

### Cloudflare Setup

**Most Popular Choice** - Free tier available, excellent API

1. **Log in to Cloudflare Dashboard**
   - Go to https://dash.cloudflare.com

2. **Create API Token**
   - Click on your profile → **API Tokens**
   - Click **Create Token**
   - Use **Edit zone DNS** template
   - Configure:
     - **Permissions:** Zone → DNS → Edit
     - **Zone Resources:** Include → Specific zone → `yourdomain.com`
   - Click **Continue to summary** → **Create Token**
   - **Copy the token** (you won't see it again!)

3. **Token Format**
   ```
   Example: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
   ```

**Cloudflare Configuration File:**
```ini
# cloudflare.ini
dns_cloudflare_api_token = YOUR_TOKEN_HERE
```

---

### Other DNS Providers

#### AWS Route53

**Requirements:** AWS account with Route53 hosted zone

**Setup:**
1. Go to IAM → Users → Create User
2. Attach policy: `AmazonRoute53FullAccess` (or create custom policy)
3. Create access key

**Configuration File:**
```ini
# route53.ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
```

**Docker Image:** `certbot/dns-route53`

**Setup Command:**
```bash
docker run --rm \
  -v $(pwd)/route53.ini:/root/.aws/credentials:ro \
  -v letsencrypt:/etc/letsencrypt \
  certbot/dns-route53 \
  certonly --dns-route53 \
  -d n8n.yourdomain.com
```

---

#### Google Cloud DNS

**Requirements:** Google Cloud project with Cloud DNS API enabled

**Setup:**
1. Go to IAM & Admin → Service Accounts
2. Create service account with **DNS Administrator** role
3. Create and download JSON key

**Configuration File:**
```json
# google.json
{
  "type": "service_account",
  "project_id": "your-project",
  "private_key_id": "...",
  "private_key": "...",
  ...
}
```

**Docker Image:** `certbot/dns-google`

**Setup Command:**
```bash
docker run --rm \
  -v $(pwd)/google.json:/google.json:ro \
  -v letsencrypt:/etc/letsencrypt \
  certbot/dns-google \
  certonly --dns-google \
  --dns-google-credentials /google.json \
  -d n8n.yourdomain.com
```

---

#### DigitalOcean DNS

**Requirements:** DigitalOcean account with domain in DO DNS

**Setup:**
1. Go to API → Tokens/Keys
2. Generate New Token (read + write access)

**Configuration File:**
```ini
# digitalocean.ini
dns_digitalocean_token = YOUR_TOKEN_HERE
```

**Docker Image:** `certbot/dns-digitalocean`

---

#### Namecheap, GoDaddy, Other Providers

For other providers, check the **Certbot DNS Plugins** list:
https://eff-certbot.readthedocs.io/en/stable/using.html#dns-plugins

Most providers have community-supported plugins available.

---

## Installation

### Step 1: Clone Repository

```bash
# SSH to your server
ssh user@your-server-ip

# Clone the repository
git clone https://github.com/rjsears/n8n_nginx.git
cd n8n_nginx
```

---

### Step 2: Configure DNS Credentials

#### For Cloudflare:

```bash
# Copy example file
cp cloudflare.ini.example cloudflare.ini

# Edit and add your API token
nano cloudflare.ini
```

Update with your token:
```ini
dns_cloudflare_api_token = your_actual_token_here
```

Set secure permissions:
```bash
chmod 600 cloudflare.ini
```

#### For Other DNS Providers:

Follow the provider-specific setup above, then **edit `setup.sh`** to change:
- Docker image (line ~80): `certbot/dns-cloudflare` → `certbot/dns-route53` (or your provider)
- Credentials file mount (line ~81): `/cloudflare.ini` → `/your-provider.ini`
- Certbot flags (line ~86): `--dns-cloudflare` → `--dns-route53` (or your provider)

---

### Step 3: Edit Configuration

#### Update docker-compose.yaml

```bash
nano docker-compose.yaml
```

**Change these values:**

1. **Line 10 & 25** - PostgreSQL password:
   ```yaml
   - POSTGRES_PASSWORD=your_secure_password_here
   ```

2. **Line 52** - n8n encryption key (generate with `openssl rand -base64 32`):
   ```yaml
   - N8N_ENCRYPTION_KEY=your_generated_encryption_key
   ```

3. **Lines 36-38** - Your domain:
   ```yaml
   - N8N_HOST=n8n.yourdomain.com
   - WEBHOOK_URL=https://n8n.yourdomain.com
   - N8N_EDITOR_BASE_URL=https://n8n.yourdomain.com
   ```

**Save and close** (Ctrl+X, Y, Enter)

---

### Step 4: Run Setup

```bash
# Make setup script executable
chmod +x setup.sh

# Run setup (takes 3-5 minutes)
./setup.sh
```

**What the setup script does:**

1. Validates configuration files
2. Checks port 443 availability
3. Creates external Docker volume for certificates
4. Starts PostgreSQL database
5. Requests SSL certificate from Let's Encrypt via DNS-01 challenge
6. Copies certificates to Docker volume
7. Starts all services (nginx, n8n, certbot)

**Expected Output:**
```
=== n8n HTTPS Setup with Let's Encrypt + Cloudflare ===

Step 1: Checking configuration...
✓ Port 443 is available
✓ Configuration looks good

Step 2: Creating external letsencrypt volume...
✓ Volume created

Step 3: Starting PostgreSQL...
✓ PostgreSQL is running

Step 4: Obtaining SSL certificate from Let's Encrypt...
✓ SSL certificate obtained successfully!

Step 5: Copying certificates to Docker volume...
✓ Certificates copied to Docker volume

Step 6: Starting all services...

=== Setup Complete! ===

Your n8n instance should now be accessible at:
https://n8n.yourdomain.com
```

---

## SSL Certificate Auto-Renewal

### How It Works

The **certbot container** handles automatic certificate renewal:

```yaml
certbot:
  image: certbot/dns-cloudflare:latest
  entrypoint: /bin/sh -c "trap exit TERM; while :; do 
    certbot renew --dns-cloudflare --dns-cloudflare-credentials /cloudflare.ini 
    --deploy-hook 'docker exec n8n_nginx nginx -s reload' || true; 
    sleep 12h & wait $${!}; 
  done;"
```

**Process:**

1. **Every 12 hours**, certbot checks if certificates need renewal
2. Let's Encrypt certificates are valid for **90 days**
3. Certbot attempts renewal at **30 days before expiration**
4. Uses **DNS-01 challenge** via your DNS provider API
5. Creates temporary TXT record in your DNS
6. Let's Encrypt validates the TXT record
7. New certificate issued and saved
8. **Nginx automatically reloads** to use new certificate (via deploy-hook)
9. Process repeats every 12 hours

**Key Features:**

- **Fully Automatic** - No manual intervention needed
- **Nginx Reload** - Deploy hook automatically reloads nginx after renewal
- **Docker Socket Access** - Certbot can control nginx container
- **Error Handling** - `|| true` prevents container restart on failed checks
- **Background Process** - Runs continuously without blocking

**Verify Auto-Renewal:**

```bash
# Check when certificates expire
docker run --rm \
  -v letsencrypt:/etc/letsencrypt \
  certbot/dns-cloudflare:latest \
  certificates

# Test renewal process (dry-run, doesn't actually renew)
docker exec n8n_certbot certbot renew --dry-run \
  --dns-cloudflare \
  --dns-cloudflare-credentials /cloudflare.ini

# View certbot logs
docker logs n8n_certbot
```

**Expected Log Output:**

```
Cert not yet due for renewal
```

Or when renewal happens (~30 days before expiration):

```
Renewing certificate for n8n.yourdomain.com
Successfully renewed certificate n8n.yourdomain.com
Running deploy-hook command: docker exec n8n_nginx nginx -s reload
```

---

## Accessing n8n

### Initial Access

1. Open your browser to: `https://n8n.yourdomain.com`
2. You'll see the n8n setup page
3. Create your **owner account** (first user = admin)
4. Start building workflows!

### Valid SSL Certificate

Your browser will show:
- Green padlock (valid HTTPS)
- Certificate issued by Let's Encrypt
- Valid for 90 days (auto-renews at 60 days)

---

## Docker Commands Reference

### Starting and Stopping

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart n8n
docker-compose restart nginx

# Stop and remove everything (including data!)
docker-compose down -v
```

### Viewing Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f n8n
docker-compose logs -f nginx
docker-compose logs -f certbot
docker-compose logs -f postgres

# Last 50 lines
docker-compose logs --tail=50 n8n
```

### Checking Status

```bash
# Check all container status
docker-compose ps

# Check specific container
docker ps | grep n8n

# Check resource usage
docker stats
```

### Updating n8n

```bash
# Pull latest n8n image
docker-compose pull n8n

# Recreate container with new image
docker-compose up -d n8n

# Verify version
docker exec n8n n8n --version
```

### Database Operations

```bash
# Connect to PostgreSQL
docker exec -it n8n_postgres psql -U n8n -d n8n

# Backup database
docker exec n8n_postgres pg_dump -U n8n -d n8n -F c -f /tmp/backup.dump
docker cp n8n_postgres:/tmp/backup.dump ./backup-$(date +%Y%m%d).dump

# Check database size
docker exec n8n_postgres psql -U n8n -d n8n \
  -c "SELECT pg_size_pretty(pg_database_size('n8n'));"
```

### Certificate Management

```bash
# Check certificate expiration
docker run --rm \
  -v letsencrypt:/etc/letsencrypt \
  certbot/dns-cloudflare:latest \
  certificates

# Force certificate renewal (use carefully)
docker exec n8n_certbot certbot renew --force-renewal \
  --dns-cloudflare \
  --dns-cloudflare-credentials /cloudflare.ini
```

---

## Troubleshooting

### n8n Not Accessible

**Symptom:** Can't reach https://n8n.yourdomain.com

**Solutions:**

```bash
# 1. Check all containers are running
docker-compose ps
# All should show "Up"

# 2. Check port 443 is listening
netstat -tulpn | grep :443
# Should show docker-proxy

# 3. Check nginx logs
docker logs n8n_nginx
# Look for errors

# 4. Test from server itself
curl -I https://n8n.yourdomain.com
# Should return HTTP/2 200

# 5. Check DNS resolution
nslookup n8n.yourdomain.com
# Should resolve to your server IP
```

---

### Certificate Errors

**Symptom:** Browser shows SSL error or "Certificate not valid"

**Solutions:**

```bash
# 1. Check if certificates exist
docker run --rm -v letsencrypt:/certs alpine ls -la /certs/live/n8n.yourdomain.com/
# Should show cert.pem, privkey.pem, etc.

# 2. Check nginx can read certificates
docker exec n8n_nginx cat /etc/letsencrypt/live/n8n.yourdomain.com/fullchain.pem | head -5
# Should show certificate

# 3. Verify certificate details
openssl s_client -connect n8n.yourdomain.com:443 -servername n8n.yourdomain.com
# Should show Let's Encrypt certificate

# 4. Re-run setup if certificates missing
docker-compose down
./setup.sh
```

---

### 502 Bad Gateway

**Symptom:** Nginx returns 502 error

**Solutions:**

```bash
# 1. Check n8n is running
docker-compose ps n8n
# Should show "Up"

# 2. Check n8n logs
docker logs n8n
# Look for errors

# 3. Verify n8n port
docker logs n8n | grep "port"
# Should say: "n8n ready on ::, port 5678"

# 4. Test connection from nginx
docker exec n8n_nginx wget -O- http://n8n:5678 2>&1 | head -20
# Should return HTML

# 5. Restart n8n
docker-compose restart n8n
```

---

### Database Connection Issues

**Symptom:** n8n can't connect to database

**Solutions:**

```bash
# 1. Check PostgreSQL is healthy
docker-compose ps postgres
# Should show "Up (healthy)"

# 2. Check PostgreSQL logs
docker logs n8n_postgres

# 3. Test database connection
docker exec n8n_postgres psql -U n8n -d n8n -c "SELECT version();"
# Should show PostgreSQL version

# 4. Verify credentials match in docker-compose.yaml
grep POSTGRES_PASSWORD docker-compose.yaml
# Lines 10 and 25 should match
```

---

### Port Already in Use

**Symptom:** Setup fails with "port 443 already in use"

**Solutions:**

```bash
# 1. Find what's using port 443
sudo lsof -i :443
# or
sudo netstat -tulpn | grep :443

# 2. Stop the conflicting service
sudo systemctl stop nginx  # if system nginx
# or
sudo systemctl stop apache2  # if apache

# 3. Re-run setup
./setup.sh
```

---

### Certbot DNS Validation Fails

**Symptom:** Certificate request fails with DNS validation error

**Solutions:**

```bash
# 1. Verify DNS provider API token
# - Check token hasn't expired
# - Verify token has correct permissions
# - Test token manually via provider's API

# 2. Check DNS propagation
nslookup -type=TXT _acme-challenge.n8n.yourdomain.com
# Should show TXT record during validation

# 3. Increase propagation time
# Edit setup.sh line ~86:
--dns-cloudflare-propagation-seconds 120  # Was 60

# 4. Check certbot logs
docker logs n8n_certbot
```

---

### Container Keeps Restarting

**Symptom:** Container in constant restart loop

**Solutions:**

```bash
# 1. Check which container is restarting
docker-compose ps

# 2. View last 50 log lines
docker-compose logs --tail=50 CONTAINER_NAME

# 3. Common fixes:

# If nginx restarting: Check nginx.conf syntax
docker run --rm -v $(pwd)/nginx.conf:/etc/nginx/nginx.conf:ro nginx:alpine nginx -t

# If n8n restarting: Check environment variables
docker-compose config | grep -A20 "n8n:"

# If postgres restarting: Check volume permissions
docker volume inspect postgres_data

# 4. Start in debug mode (run interactively)
docker run -it --rm \
  -v letsencrypt:/etc/letsencrypt:ro \
  -v $(pwd)/nginx.conf:/etc/nginx/nginx.conf:ro \
  nginx:alpine sh
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Internet / Users                     │
└─────────────────────────────────────────────────────────┘
                            │
                            │ HTTPS (443)
                            ▼
┌─────────────────────────────────────────────────────────┐
│                     nginx:alpine                        │
│  - SSL/TLS Termination                                  │
│  - Reverse Proxy                                        │
│  - Security Headers                                     │
│  - Port: 443 → n8n:5678                                 │
└─────────────────────────────────────────────────────────┘
                            │
                            │ HTTP (internal)
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    n8n:latest                           │
│  - Workflow Automation                                  │
│  - Webhooks                                             │
│  - Port: 5678 (internal)                                │
└─────────────────────────────────────────────────────────┘
                            │
                            │ PostgreSQL Protocol
                            ▼
┌─────────────────────────────────────────────────────────┐
│              pgvector/pgvector:pg16                     │
│  - Database Storage                                     │
│  - Vector Embeddings (pgvector)                         │
│  - Port: 5432 (internal)                                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│           certbot/dns-cloudflare:latest                 │
│  - SSL Certificate Management                           │
│  - Auto-renewal every 12 hours                          │
│  - DNS-01 Challenge                                     │
└─────────────────────────────────────────────────────────┘
                            │
                            │ DNS API
                            ▼
┌─────────────────────────────────────────────────────────┐
│                 DNS Provider (Cloudflare)               │
│  - TXT Record Creation/Deletion                         │
│  - Domain Management                                    │
└─────────────────────────────────────────────────────────┘
                            │
                            │ Validation
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    Let's Encrypt                        │
│  - Certificate Authority                                │
│  - Issues SSL Certificates                              │
└─────────────────────────────────────────────────────────┘
```

### Network Flow

1. **User Request** → `https://n8n.yourdomain.com`
2. **Nginx** receives on port 443, terminates SSL
3. **Nginx** proxies to `n8n:5678` (HTTP internally)
4. **n8n** processes request, queries database if needed
5. **n8n** returns response → Nginx → User (HTTPS)

### Certificate Renewal Flow

1. **Certbot** wakes every 12 hours
2. Checks if certificates expire in ≤30 days
3. If renewal needed:
   - Contacts DNS provider API
   - Creates `_acme-challenge.n8n.yourdomain.com` TXT record
   - Let's Encrypt validates TXT record
   - Issues new certificate
   - Certbot saves to volume
   - Executes deploy-hook: reloads nginx
4. Returns to sleep for 12 hours

---

## Security Notes

### Credentials Security

- **Never commit** `cloudflare.ini` or credentials files to version control
- Store encryption keys securely (password manager)
- Use strong, unique passwords for PostgreSQL
- Rotate credentials periodically

### Network Security

- All internal communication (n8n ↔ postgres) is within Docker network
- Only port 443 exposed to internet
- No port 80 exposure required (DNS-01 challenge)
- Nginx handles SSL/TLS termination with modern ciphers

### SSL/TLS Configuration

- TLS 1.2 and 1.3 only
- Strong cipher suites (ECDHE, AES-GCM)
- Security headers configured (X-Frame-Options, CSP, etc.)
- HSTS ready (can be enabled in nginx.conf)

### Backup Strategy

**Critical Data:**
- PostgreSQL database (workflows, credentials, executions)
- n8n encryption key (needed to decrypt credentials)
- SSL certificates (can be regenerated but good to backup)

**Recommended Backup Schedule:**
```bash
# Daily PostgreSQL backup
0 2 * * * cd /path/to/n8n_nginx && docker exec n8n_postgres pg_dump -U n8n -d n8n -F c > backups/n8n-$(date +\%Y\%m\%d).dump

# Weekly full backup (database + n8n data)
0 3 * * 0 cd /path/to/n8n_nginx && docker run --rm -v n8n_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/n8n-data-$(date +\%Y\%m\%d).tar.gz -C /data .
```

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/n8n_nginx.git
cd n8n_nginx

# Create feature branch
git checkout -b feature/your-feature-name

# Make changes, test thoroughly

# Commit with descriptive message
git commit -m "Add: description of your changes"

# Push and create PR
git push origin feature/your-feature-name
```

### Reporting Issues

When reporting issues, please include:
- Operating system and version
- Docker and Docker Compose versions
- DNS provider being used
- Full error messages and logs
- Steps to reproduce

---

## License

MIT License - See LICENSE file for details

---

## Acknowledgments

- [n8n.io](https://n8n.io) - Workflow automation platform
- [Let's Encrypt](https://letsencrypt.org) - Free SSL certificates
- [Certbot](https://certbot.eff.org) - SSL automation tool
- [PostgreSQL](https://www.postgresql.org) - Database
- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity search
- [Nginx](https://nginx.org) - Web server and reverse proxy

---

## Support

- **Issues:** [GitHub Issues](https://github.com/rjsears/n8n_nginx/issues)
- **Discussions:** [GitHub Discussions](https://github.com/rjsears/n8n_nginx/discussions)
- **n8n Community:** [n8n.io/community](https://n8n.io/community)

---

## Acknowledgments
* **My Amazing and loving family!** My family puts up with all my coding and automation projects and encouraged me in everything. Without them, my projects would not be possible.
* **My brother James**, who is a continual source of inspiration to me and others. Everyone should have a brother as awesome as mine!
