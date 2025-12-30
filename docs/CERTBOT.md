# SSL Certificates with Certbot & Let's Encrypt

## Overview

This guide explains why SSL certificates are essential for the n8n Management Suite, even when using Tailscale or Cloudflare Tunnel. Understanding the "why" helps you make informed decisions about your security architecture.

---

## Table of Contents

1. [Why SSL Certificates Are Required](#why-ssl-certificates-are-required)
2. [The Hairpinning Alternative](#the-hairpinning-alternative)
3. [How DNS-01 Challenge Works](#how-dns-01-challenge-works)
4. [Supported DNS Providers](#supported-dns-providers)
5. [Configuration During Setup](#configuration-during-setup)
6. [How Certificates Are Used](#how-certificates-are-used)
7. [Automatic Renewal](#automatic-renewal)
8. [Manual Certificate Management](#manual-certificate-management)
9. [Troubleshooting](#troubleshooting)

---

## Why SSL Certificates Are Required

### The Short Answer

Even with Tailscale or Cloudflare Tunnel providing encrypted transport, **you still need valid SSL certificates on nginx** for your services to work correctly. This is primarily due to **CORS (Cross-Origin Resource Sharing)** requirements and browser security policies.

### The Technical Explanation

#### 1. CORS and Browser Security

Modern browsers enforce strict security policies:

```
[Browser] → [Cloudflare Tunnel] → [Your Server]
                HTTPS                  ???
```

When you access `https://n8n.yourdomain.com`:

1. Your browser connects to Cloudflare (HTTPS)
2. Cloudflare terminates SSL and proxies to your origin server
3. **Your origin server must also speak HTTPS** for the full chain to work

Without valid SSL on your origin:
- n8n webhooks may fail silently
- The Management Console API calls may be blocked
- WebSocket connections (used for real-time updates) will fail
- Browsers will show mixed-content warnings

#### 2. n8n Webhook Requirements

n8n requires HTTPS for production webhooks:

```
[External Service] → [Your Domain] → [n8n]
                       HTTPS           ↓
                                    Webhook processed
```

If the SSL chain is broken, webhook payloads may:
- Be rejected by n8n
- Fail CORS preflight checks
- Timeout during SSL handshake

#### 3. Management Console Communication

The Management Console frontend makes API calls to its backend:

```
Frontend (Browser)  →  /management/api/*  →  FastAPI Backend
       ↓                     ↓                    ↓
   JavaScript            nginx proxy          Python API
```

Browsers require:
- Same-origin policy compliance
- Valid SSL certificates
- Proper CORS headers

Without valid SSL, these internal API calls fail with cryptic errors.

### What Happens Without Valid SSL?

| Symptom | Root Cause |
|---------|------------|
| Webhooks not triggering | CORS preflight fails |
| "Mixed content" warnings | HTTP/HTTPS mismatch |
| API calls returning 0 bytes | Browser blocks insecure request |
| WebSocket disconnects | WSS requires valid cert |
| "NET::ERR_CERT_AUTHORITY_INVALID" | Self-signed cert rejected |
| Management Console blank screen | JavaScript API calls blocked |

---

## The Hairpinning Alternative

### What is Hairpinning?

If you really don't want to set up local SSL certificates, there's an alternative called "hairpinning" or "NAT loopback":

```
                    ┌──────────────────────────────────────┐
                    │           Your Network               │
                    │                                      │
[Internal Device]   │    ──────────────────────────────────┼───────┐
     │              │                                      │       │
     └──────────────┼──→ Router ──→ Internet ──→ Cloudflare        │
                    │        ↑                      │              │
                    │        └──────────────────────┼──────────────┘
                    │                               ↓
                    │                         [Your Server]
                    └──────────────────────────────────────┘
```

With hairpinning:
1. Internal device makes request to `https://n8n.yourdomain.com`
2. Traffic exits your network to the internet
3. Reaches Cloudflare Tunnel
4. Returns through Cloudflare to your server
5. Response makes the reverse trip

### Why Hairpinning is Inefficient

| Issue | Impact |
|-------|--------|
| **Latency** | Every request takes a round-trip to Cloudflare |
| **Bandwidth** | Uses your internet upload/download for internal traffic |
| **Reliability** | Depends on internet connectivity for local access |
| **Speed** | 10-100x slower than local communication |
| **Data caps** | May consume metered bandwidth unnecessarily |

### Example Latency Comparison

| Access Method | Typical Latency |
|--------------|-----------------|
| Direct local (with SSL) | 1-5ms |
| Hairpinning via Cloudflare | 50-200ms |
| Via Tailscale (encrypted) | 5-20ms |

### When Hairpinning Might Be Acceptable

- Very low-traffic internal use
- No latency-sensitive operations
- Unlimited internet bandwidth
- Highly reliable internet connection
- Temporary/testing setup

### The Recommended Approach

Use **local SSL certificates** from Let's Encrypt:
- Fast local access (1-5ms)
- No internet dependency for internal traffic
- Zero cost (Let's Encrypt is free)
- Automatic renewal
- Proper CORS compliance

---

## How DNS-01 Challenge Works

### Why DNS-01?

The n8n Management Suite uses **DNS-01 challenge** rather than HTTP-01 because:

1. **No port 80 exposure required** - Your firewall can block all inbound traffic
2. **Works behind NAT** - No port forwarding needed
3. **Wildcard certificates** - Can issue `*.yourdomain.com` if needed
4. **More secure** - No web server exposure during validation

### The DNS-01 Process

```
┌─────────────────────────────────────────────────────────────────┐
│                    DNS-01 Challenge Flow                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Certbot requests certificate for n8n.example.com            │
│     ↓                                                           │
│  2. Let's Encrypt says: "Prove you control the domain"          │
│     ↓                                                           │
│  3. Certbot creates TXT record:                                 │
│     _acme-challenge.n8n.example.com → [random-token]            │
│     ↓                                                           │
│  4. Let's Encrypt queries DNS for the TXT record                │
│     ↓                                                           │
│  5. If found and matches → Certificate issued!                  │
│     ↓                                                           │
│  6. Certbot removes the TXT record                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### DNS Propagation

After Certbot creates the TXT record, it waits for DNS propagation:

| Provider | Typical Wait Time |
|----------|-------------------|
| Cloudflare | 60 seconds |
| Route53 | 60 seconds |
| Google Cloud DNS | 120 seconds |
| DigitalOcean | 60 seconds |

The setup configures appropriate propagation delays automatically.

---

## Supported DNS Providers

### Cloudflare (Recommended)

**Why Cloudflare is recommended:**
- Fast DNS propagation
- Easy API token generation
- Free tier available
- Same provider as Cloudflare Tunnel (if using)

**Setup during installation:**
```
  DNS Provider Selection:
    1. Cloudflare
    2. AWS Route 53
    3. Google Cloud DNS
    4. DigitalOcean
    5. Other (Manual DNS)

  Enter choice [1]: 1

  Cloudflare API Token: [paste your token]
```

**API Token Requirements:**

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/profile/api-tokens)
2. Click **Create Token**
3. Use the **Edit zone DNS** template, or create custom with:
   - **Zone:DNS:Edit** permission
   - **Zone:Zone:Read** permission
4. Limit to your specific zone (domain) for security

**Credentials file created:** `cloudflare.ini`
```ini
dns_cloudflare_api_token = your-api-token-here
```

### AWS Route 53

**Setup:**
```
  AWS Access Key ID: AKIA...
  AWS Secret Access Key: [hidden]
```

**IAM Policy Required:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "route53:ListHostedZones",
        "route53:GetChange"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "route53:ChangeResourceRecordSets"
      ],
      "Resource": "arn:aws:route53:::hostedzone/YOUR_ZONE_ID"
    }
  ]
}
```

**Credentials file created:** `route53.ini`
```ini
[default]
aws_access_key_id = AKIA...
aws_secret_access_key = your-secret-key
```

### Google Cloud DNS

**Setup:**
```
  Path to Google Cloud service account JSON: /path/to/credentials.json
```

**Service Account Requirements:**
1. Create service account in Google Cloud Console
2. Grant **DNS Administrator** role
3. Create and download JSON key file
4. Provide path during setup

**Credentials file created:** `google.json` (copied from your file)

### DigitalOcean

**Setup:**
```
  DigitalOcean API Token: dop_v1_...
```

**Token Requirements:**
1. Go to [DigitalOcean API Tokens](https://cloud.digitalocean.com/account/api/tokens)
2. Generate new token with **Write** scope
3. Token needs access to DNS management

**Credentials file created:** `digitalocean.ini`
```ini
dns_digitalocean_token = dop_v1_your-token-here
```

### Manual DNS (Other Providers)

For DNS providers without Certbot plugins:

```
  ⚠️ Manual DNS configuration selected
  You'll need to manually add TXT records during certificate issuance
```

**Manual process:**
1. Certbot will display the required TXT record
2. You add it to your DNS provider's control panel
3. Wait for propagation
4. Press Enter to continue validation
5. Remove the TXT record after completion

**Use manual mode for:**
- GoDaddy
- Namecheap
- Hover
- Other providers without API plugins

---

## Configuration During Setup

### Interactive Setup Flow

When running `./setup.sh`, the DNS configuration happens early:

```
╔══════════════════════════════════════════════════════════════╗
║              DNS Provider for SSL Certificates               ║
╚══════════════════════════════════════════════════════════════╝

  Select your DNS provider for Let's Encrypt DNS-01 challenge:

    1. Cloudflare (recommended)
    2. AWS Route 53
    3. Google Cloud DNS
    4. DigitalOcean
    5. Other (Manual DNS)

  Enter choice [1]:
```

### Pre-configured Setup

If using a config file, set these variables:

```bash
# In your config file
DNS_PROVIDER=cloudflare
CLOUDFLARE_API_TOKEN=your-api-token

# Or for Route53
DNS_PROVIDER=route53
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=your-secret-key

# Or for Google Cloud DNS
DNS_PROVIDER=google
GOOGLE_CREDENTIALS_FILE=/path/to/credentials.json

# Or for DigitalOcean
DNS_PROVIDER=digitalocean
DIGITALOCEAN_TOKEN=dop_v1_...
```

### Environment Variables Set by Setup

After configuration, these variables are set in your `.env`:

| Variable | Example | Purpose |
|----------|---------|---------|
| `DNS_PROVIDER` | `cloudflare` | Which DNS provider plugin to use |
| `DNS_CERTBOT_IMAGE` | `certbot/dns-cloudflare:latest` | Docker image for Certbot |
| `DNS_CERTBOT_FLAGS` | `--dns-cloudflare ...` | CLI flags for certificate issuance |
| `DNS_CREDENTIALS_FILE` | `cloudflare.ini` | Path to credentials file |

---

## How Certificates Are Used

### Certificate Storage

Certificates are stored in the `letsencrypt` Docker volume:

```
letsencrypt/
├── live/
│   └── n8n.yourdomain.com/
│       ├── fullchain.pem    # Certificate + intermediate certs
│       ├── privkey.pem      # Private key
│       ├── cert.pem         # Just the certificate
│       └── chain.pem        # Intermediate certificates
├── archive/                  # All versions of certs
├── renewal/                  # Renewal configuration
└── accounts/                 # Let's Encrypt account info
```

### nginx Configuration

The certificates are mounted into the nginx container:

```yaml
# docker-compose.yaml
nginx:
  volumes:
    - letsencrypt:/etc/letsencrypt:ro
```

And referenced in nginx.conf:

```nginx
server {
    listen 443 ssl http2;
    server_name n8n.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/n8n.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/n8n.yourdomain.com/privkey.pem;

    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:...;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
}
```

### Shared Certificate

The same certificate is used for all services:
- n8n (main application)
- Management Console (`/management`)
- Adminer (`/adminer`)
- Portainer (`/portainer`)
- Dozzle (`/dozzle`)

This simplifies management - one certificate covers everything.

---

## Automatic Renewal

### How Renewal Works

The Certbot container runs continuously and checks for renewal:

```yaml
# docker-compose.yaml
certbot:
  image: ${DNS_CERTBOT_IMAGE:-certbot/certbot:latest}
  entrypoint: /bin/sh -c "trap exit TERM; while :; do certbot renew ... --deploy-hook 'docker exec n8n_nginx nginx -s reload'; sleep 12h & wait $${!}; done;"
```

**Process:**
1. Every 12 hours, Certbot checks if renewal is needed
2. Certificates are renewed when less than 30 days remain
3. After renewal, nginx is reloaded to pick up new certs
4. No downtime - nginx gracefully reloads

### Renewal Timeline

```
Certificate Issued          Renewal Window Opens       Expires
       │                           │                      │
       ├───────────── 60 days ─────┼─────── 30 days ──────┤
       │                           │                      │
       │                           └── Certbot renews ────┘
       │                               (any check in this window)
```

### Verifying Renewal Configuration

```bash
# Check Certbot container is running
docker ps | grep certbot

# View renewal configuration
docker exec n8n_certbot cat /etc/letsencrypt/renewal/n8n.yourdomain.com.conf

# Test renewal (dry run)
docker exec n8n_certbot certbot renew --dry-run
```

---

## Manual Certificate Management

### Force Renewal

From the Management Console:
1. Go to **System** → **SSL/TLS**
2. Click **Force Renewal**

Or via command line:
```bash
docker exec n8n_certbot certbot renew --force-renewal
docker exec n8n_nginx nginx -s reload
```

### View Certificate Details

```bash
# Check certificate expiration
docker exec n8n_nginx openssl x509 -in /etc/letsencrypt/live/n8n.yourdomain.com/fullchain.pem -noout -dates

# View full certificate info
docker exec n8n_nginx openssl x509 -in /etc/letsencrypt/live/n8n.yourdomain.com/fullchain.pem -noout -text
```

### Replace with Custom Certificate

If you have certificates from another CA:

1. Stop nginx:
   ```bash
   docker compose stop nginx
   ```

2. Copy certificates into the volume:
   ```bash
   # Create directory structure
   docker run --rm -v letsencrypt:/etc/letsencrypt alpine mkdir -p /etc/letsencrypt/live/n8n.yourdomain.com

   # Copy certificate files
   docker cp fullchain.pem n8n_certbot:/etc/letsencrypt/live/n8n.yourdomain.com/
   docker cp privkey.pem n8n_certbot:/etc/letsencrypt/live/n8n.yourdomain.com/
   ```

3. Start nginx:
   ```bash
   docker compose start nginx
   ```

---

## Troubleshooting

### Certificate Issuance Failed

**Check Certbot logs:**
```bash
docker logs n8n_certbot
```

**Common issues:**

| Error | Cause | Solution |
|-------|-------|----------|
| `DNS problem: NXDOMAIN` | Domain doesn't exist in DNS | Verify domain is configured |
| `Invalid API token` | Wrong credentials | Regenerate API token |
| `Rate limited` | Too many requests | Wait 1 hour, check rate limits |
| `CAA record issue` | CAA DNS record blocks Let's Encrypt | Add `0 issue "letsencrypt.org"` |
| `Timeout during connect` | Network issues | Check internet connectivity |

### Certificate Not Updating in nginx

```bash
# Reload nginx manually
docker exec n8n_nginx nginx -s reload

# Or restart nginx container
docker compose restart nginx

# Verify certificate is current
curl -v https://n8n.yourdomain.com 2>&1 | grep "expire date"
```

### Mixed Content Warnings

If you see mixed content warnings:

1. Ensure all services use HTTPS internally
2. Check nginx proxy settings use `https://` for upstream
3. Clear browser cache and retry

### CORS Errors in Console

```
Access to fetch at 'https://...' from origin 'https://...' has been blocked by CORS policy
```

**Solutions:**
1. Verify SSL certificate is valid (not self-signed)
2. Check certificate matches the domain being accessed
3. Ensure nginx is properly configured with correct server_name

### Rate Limits

Let's Encrypt has rate limits:

| Limit | Value | Reset |
|-------|-------|-------|
| Certificates per domain | 50/week | Rolling 7 days |
| Failed validations | 5/hour | 1 hour |
| Duplicate certificates | 5/week | Rolling 7 days |

**If rate limited:**
1. Wait for the limit to reset
2. Use staging environment for testing:
   ```bash
   certbot certonly --staging ...
   ```

### Verify Certificate Chain

```bash
# Check the full chain is valid
docker exec n8n_nginx openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt /etc/letsencrypt/live/n8n.yourdomain.com/fullchain.pem

# Test SSL configuration
curl -I https://n8n.yourdomain.com

# External SSL test
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=n8n.yourdomain.com
```

---

## Quick Reference

### Commands

```bash
# View certificate expiration
docker exec n8n_nginx openssl x509 -in /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem -noout -enddate

# Force certificate renewal
docker exec n8n_certbot certbot renew --force-renewal

# Test renewal (dry run)
docker exec n8n_certbot certbot renew --dry-run

# Reload nginx after renewal
docker exec n8n_nginx nginx -s reload

# View Certbot logs
docker logs n8n_certbot

# Check certificate from outside
echo | openssl s_client -connect YOUR_DOMAIN:443 2>/dev/null | openssl x509 -noout -dates
```

### File Locations

| File | Location | Purpose |
|------|----------|---------|
| Credentials | `./cloudflare.ini` (or similar) | DNS API credentials |
| Certificate | `letsencrypt:/etc/letsencrypt/live/DOMAIN/fullchain.pem` | SSL certificate |
| Private key | `letsencrypt:/etc/letsencrypt/live/DOMAIN/privkey.pem` | SSL private key |
| Renewal config | `letsencrypt:/etc/letsencrypt/renewal/DOMAIN.conf` | Certbot renewal settings |

### Environment Variables

| Variable | Example | Purpose |
|----------|---------|---------|
| `DNS_PROVIDER` | `cloudflare` | DNS provider selection |
| `DNS_CERTBOT_IMAGE` | `certbot/dns-cloudflare:latest` | Certbot Docker image |
| `DNS_CERTBOT_FLAGS` | `--dns-cloudflare --dns-cloudflare-credentials /credentials.ini` | Certbot CLI flags |
| `DNS_CREDENTIALS_FILE` | `cloudflare.ini` | Credentials file name |

---

## Related Documentation

- [README.md](../README.md) - Main documentation
- [CLOUDFLARE.md](./CLOUDFLARE.md) - Cloudflare Tunnel setup
- [TAILSCALE.md](./TAILSCALE.md) - Tailscale VPN setup
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - General troubleshooting
