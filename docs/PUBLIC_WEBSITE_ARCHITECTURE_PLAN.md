# Public Website Architecture Refactor Plan

## Executive Summary

This document outlines the architectural changes required to properly support a public-facing website alongside the n8n management console. The new architecture uses **two separate nginx containers** with **Cloudflare Tunnel handling hostname-based routing**.

**Key Decision:** Public website feature requires Cloudflare Tunnel. This eliminates the ERR_ECH_FALLBACK_CERTIFICATE_INVALID issue and provides clean separation of concerns.

---

## Problem Statement

### Current Issue
When running two SSL server blocks in a single nginx instance (one for n8n/management, one for public website), users experience intermittent `ERR_ECH_FALLBACK_CERTIFICATE_INVALID` errors when accessing via internal DNS.

### Root Cause
- Two server blocks on port 443 with `default_server` directive
- SNI ambiguity when browser uses Encrypted Client Hello (ECH)
- Working configurations have single server block without `default_server`

### Current Architecture (Problematic)
```
                    ┌─────────────────────────────────────┐
                    │           n8n_nginx                 │
                    │         (single container)          │
Internet ──────────►│                                     │
                    │  server_block_1 (n8n01.domain.com)  │
                    │  server_block_2 (www.domain.com)    │
                    │         ⚠️ ECH CONFLICT ⚠️           │
                    └─────────────────────────────────────┘
```

---

## Proposed Architecture

### New Design: Dual Nginx Containers

```
                         Cloudflare Tunnel
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
     n8n01.domain.com                  www.domain.com
              │                                 │
              ▼                                 ▼
    ┌─────────────────┐              ┌─────────────────┐
    │   n8n_nginx     │              │ n8n_nginx_public│
    │                 │              │                 │
    │ - n8n editor    │              │ - Static files  │
    │ - Management    │              │ - /var/www/public│
    │ - Webhooks      │              │                 │
    │ - NTFY          │              │ Single server   │
    │ - Portainer     │              │ block, simple   │
    │ - Adminer       │              │ config          │
    │ - Dozzle        │              │                 │
    │ - File Browser  │              └─────────────────┘
    │                 │
    │ Single server   │
    │ block, all      │
    │ services        │
    └─────────────────┘
```

### Traffic Flow

1. **External traffic (via Cloudflare Tunnel):**
   - `n8n01.domain.com` → Tunnel routes to `n8n_nginx:443`
   - `www.domain.com` → Tunnel routes to `n8n_nginx_public:443`

2. **Internal traffic (Tailscale/VPN):**
   - `n8n01.domain.com` → Direct to `n8n_nginx:443`
   - `www.domain.com` → Through Cloudflare Tunnel only (public site)

### Key Benefits

| Benefit | Description |
|---------|-------------|
| **No ECH Issues** | Each nginx has single server block, no SNI ambiguity |
| **Security Isolation** | Public site completely separated from internal services |
| **Simpler Configs** | Each nginx.conf is straightforward and maintainable |
| **Clear Boundaries** | Public site can't accidentally expose internal routes |
| **Cloudflare Protection** | Public site gets DDoS protection, WAF, caching |

---

## Implementation Requirements

### 1. Setup Script Changes (`setup.sh`)

#### 1.1 Validation Logic
```bash
# If public website enabled without Cloudflare tunnel, show warning (not error)
if [ "$INSTALL_PUBLIC_WEBSITE" = "true" ] && [ "$INSTALL_CLOUDFLARE_TUNNEL" != "true" ]; then
    print_warning "Public Website enabled without Cloudflare Tunnel"
    # Explain that manual configuration will be needed
    # Offer to configure Cloudflare Tunnel now
    # Allow install to continue regardless - container will be created
    # but may not be accessible without additional manual configuration
fi
```

**Note:** This is a warning, not a blocking error. The install continues and the public website container is created. Without Cloudflare Tunnel, the user will need to manually configure DNS/proxy routing to access the public website.

#### 1.2 New Functions Required
- `generate_public_nginx_conf()` - Generate nginx.conf for public website container
- `generate_public_dockerfile()` - If needed, or use nginx:alpine directly
- Update `generate_docker_compose_v3()` - Add n8n_nginx_public service
- Update `configure_cloudflare_tunnel()` - Add public hostname guidance

#### 1.3 Remove from Main Nginx
- Remove public website server block from `generate_nginx_conf_v3()`
- Remove `default_server` directive (no longer needed with single block)
- Keep File Browser location (for managing public site files internally)

### 2. Docker Compose Changes

#### 2.1 New Service: `n8n_nginx_public`
```yaml
# ===========================================================================
# Public Website Nginx (separate from main nginx)
# ===========================================================================
n8n_nginx_public:
  image: nginx:alpine
  container_name: n8n_nginx_public
  restart: unless-stopped
  volumes:
    - ./nginx-public.conf:/etc/nginx/nginx.conf:ro
    - public_web_root:/var/www/public:ro
    - letsencrypt:/etc/letsencrypt:ro
  networks:
    - n8n_network
  # No external ports - accessed via Cloudflare Tunnel only
```

#### 2.2 Update Main Nginx Service
- Remove `default_server` from listen directive
- Remove public website server block
- Keep all internal services

#### 2.3 Volume Sharing
- `public_web_root` volume shared between:
  - `n8n_nginx` (via File Browser for management)
  - `n8n_nginx_public` (for serving static files)

#### 2.4 Public Website Initialization

The `initialize_public_website()` function must correctly copy the default `index.html` to the shared volume.

**Current Issue (to be fixed):**
Docker Compose prefixes volume names with the project name (e.g., `n8n_nginx_public_web_root` instead of `public_web_root`). The function must use the correct prefixed volume name.

**Updated Function Logic:**
```bash
initialize_public_website() {
    print_info "Initializing public website..."

    # Get the docker compose project name (defaults to directory name)
    local project_name=$(basename "${SCRIPT_DIR}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/_/g')
    local volume_name="${project_name}_public_web_root"

    # Check if index.html already exists
    local has_index=$($DOCKER_SUDO docker run --rm -v "${volume_name}:/data:ro" alpine sh -c '[ -f /data/index.html ] && echo "yes" || echo "no"' 2>/dev/null)

    if [ "$has_index" = "yes" ]; then
        print_info "Public website already has content, skipping initialization"
        return 0
    fi

    # Copy default index.html to volume
    # ... (create default landing page content)

    # Set proper permissions
    $DOCKER_SUDO docker run --rm -v "${volume_name}:/data" alpine chmod -R 755 /data

    print_success "Public website initialized with default landing page"
}
```

**Key Requirements:**
1. Use correct volume name with project prefix
2. Copy `public_index.html` (or generate default) to volume
3. Set proper permissions (755) for nginx to read
4. Run AFTER docker compose creates the volume
5. Verify file exists in volume before considering success

**Alternative Approach - Use Running Container:**
Instead of mounting the volume directly, copy through the running `n8n_nginx_public` container:
```bash
# Copy via running container (more reliable)
docker cp public_index.html n8n_nginx_public:/var/www/public/index.html
docker exec n8n_nginx_public chmod 644 /var/www/public/index.html
```

### 3. Nginx Configuration Files

#### 3.1 Main Nginx (`nginx.conf`) - Updated
```nginx
events {
    worker_connections 1024;
}

http {
    resolver 127.0.0.11 valid=30s ipv6=off;
    resolver_timeout 5s;

    client_max_body_size 50M;
    client_body_buffer_size 10M;

    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;
    send_timeout 600s;

    upstream n8n {
        server n8n:5678;
    }

    upstream management {
        server n8n_management:80;
    }

    geo $access_level {
        default          "external";
        127.0.0.1/32     "internal";
        10.0.0.0/8       "internal";
        172.16.0.0/12    "internal";
        192.168.0.0/16   "internal";
        100.64.0.0/10    "internal";
    }

    # Single server block - NO default_server needed
    server {
        listen 443 ssl;
        http2 on;
        server_name ${N8N_DOMAIN};

        ssl_certificate /etc/letsencrypt/live/${SSL_CERT_DOMAIN}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${SSL_CERT_DOMAIN}/privkey.pem;

        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers '...';
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        # All existing locations...
        # /webhook/ - public
        # / - internal (n8n)
        # /management/ - internal
        # /portainer/ - internal
        # /adminer/ - internal
        # /dozzle/ - internal
        # /ntfy/ - public
        # /files/ - internal (File Browser)
    }

    # NO second server block for public website
}
```

#### 3.2 Public Nginx (`nginx-public.conf`) - New File
```nginx
events {
    worker_connections 256;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    server {
        listen 443 ssl;
        http2 on;
        server_name ${PUBLIC_WEBSITE_DOMAIN};

        ssl_certificate /etc/letsencrypt/live/${SSL_CERT_DOMAIN}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${SSL_CERT_DOMAIN}/privkey.pem;

        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;

        root /var/www/public;
        index index.html;

        # Security headers
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "DENY" always;
        add_header X-XSS-Protection "1; mode=block" always;

        location / {
            try_files $uri $uri/ =404;
        }

        # Health check for Cloudflare Tunnel
        location /healthz {
            access_log off;
            return 200 "healthy\n";
        }

        # Block common attack paths
        location ~ /\. {
            deny all;
        }
    }
}
```

### 4. Cloudflare Tunnel Configuration

#### 4.1 Required Public Hostnames
Users must configure two hostnames in Cloudflare Zero Trust dashboard:

| Hostname | Service | URL |
|----------|---------|-----|
| `n8n01.domain.com` | HTTP | `https://n8n_nginx:443` |
| `www.domain.com` | HTTP | `https://n8n_nginx_public:443` |

#### 4.2 Setup Script Guidance
After tunnel configuration, display:
```
═══════════════════════════════════════════════════════════════
 CLOUDFLARE TUNNEL CONFIGURATION REQUIRED
═══════════════════════════════════════════════════════════════

You have enabled the Public Website feature. Please add BOTH
hostnames in Cloudflare Zero Trust:

1. Visit: https://one.dash.cloudflare.com
2. Go to: Networks → Tunnels → [Your Tunnel] → Configure
3. Add Public Hostnames:

   Hostname: n8n01.domain.com
   Service:  HTTPS://n8n_nginx:443

   Hostname: www.domain.com
   Service:  HTTPS://n8n_nginx_public:443

Note: Enable "No TLS Verify" for both if using self-signed certs.
═══════════════════════════════════════════════════════════════
```

### 5. File Browser Integration

File Browser remains on the main nginx (internal access only) and writes to `public_web_root` volume, which is read by `n8n_nginx_public`.

```
┌─────────────────┐         ┌──────────────────┐
│   n8n_nginx     │         │ n8n_nginx_public │
│                 │         │                  │
│  /files/ ───────┼────┐    │                  │
│  (File Browser) │    │    │  /var/www/public │
└─────────────────┘    │    │        ▲         │
                       │    └────────┼─────────┘
                       │             │
                       ▼             │
              ┌────────────────┐     │
              │ public_web_root│─────┘
              │    (volume)    │
              └────────────────┘
```

---

## Documentation Updates Required

### 1. README.md
- [ ] Update architecture diagram
- [ ] Add public website section explaining Cloudflare requirement
- [ ] Update feature list
- [ ] Add FAQ entry about why Cloudflare is required

### 2. docs/CLOUDFLARE.md
- [ ] Add section on configuring multiple hostnames
- [ ] Add public website hostname configuration steps
- [ ] Update tunnel configuration examples

### 3. docs/TROUBLESHOOTING.md
- [ ] Remove ERR_ECH_FALLBACK_CERTIFICATE_INVALID section (no longer applicable)
- [ ] Add new section on public website routing issues
- [ ] Add Cloudflare tunnel debugging for dual hostnames

### 4. docs/ENVIRONMENTAL_VARIABLES.md
- [ ] Add `PUBLIC_NGINX_CONTAINER` variable
- [ ] Document that `INSTALL_PUBLIC_WEBSITE` requires `INSTALL_CLOUDFLARE_TUNNEL`

### 5. docs/CHANGELOG.md
- [ ] Document architectural change in next version
- [ ] Note breaking change: public website now requires Cloudflare Tunnel

### 6. New Documentation
- [ ] Create `docs/PUBLIC_WEBSITE.md` with:
  - Architecture explanation
  - Setup instructions
  - Cloudflare configuration guide
  - File management via File Browser
  - Custom domain setup

---

## Migration Path

### For Existing Users with Public Website

1. **Backup current configuration**
2. **Enable Cloudflare Tunnel** (if not already)
3. **Re-run setup.sh** or manually:
   - Add `n8n_nginx_public` container
   - Update main nginx.conf (remove public server block)
   - Create nginx-public.conf
   - Configure Cloudflare tunnel hostnames
4. **Restart stack**

### For New Installations

No migration needed - setup.sh handles everything automatically when both features are enabled.

---

## Testing Plan

### 1. Fresh Installation Tests
- [ ] Install with public website + Cloudflare tunnel → Should work
- [ ] Install with public website WITHOUT Cloudflare tunnel → Should error with clear message
- [ ] Install without public website → Should work (single nginx, no changes)

### 2. Functionality Tests
- [ ] Access n8n via Cloudflare tunnel → Works
- [ ] Access management console via tunnel → Works
- [ ] Access public website via tunnel → Works
- [ ] Access n8n via Tailscale/internal → Works
- [ ] Access management via Tailscale/internal → Works
- [ ] File Browser can upload files → Files appear on public site

### 3. Security Tests
- [ ] Public nginx cannot access internal services
- [ ] Internal services not exposed on public nginx
- [ ] Access controls work correctly on main nginx

### 4. ECH Test
- [ ] No ERR_ECH_FALLBACK_CERTIFICATE_INVALID errors
- [ ] Works on Chrome, Firefox, Safari
- [ ] Works via internal DNS and Cloudflare tunnel

---

## Implementation Order

### Phase 1: Core Changes
1. Update `setup.sh` validation logic
2. Create `generate_public_nginx_conf()` function
3. Update `generate_docker_compose_v3()` for new container
4. Update `generate_nginx_conf_v3()` to remove public server block

### Phase 2: Cloudflare Integration
5. Update `configure_cloudflare_tunnel()` with dual hostname guidance
6. Update final summary output

### Phase 3: Documentation
7. Update README.md
8. Update CLOUDFLARE.md
9. Create PUBLIC_WEBSITE.md
10. Update TROUBLESHOOTING.md
11. Update ENVIRONMENTAL_VARIABLES.md
12. Update CHANGELOG.md

### Phase 4: Testing
13. Test fresh installations (all scenarios)
14. Test migrations
15. ECH verification

---

## Files to Modify

| File | Changes |
|------|---------|
| `setup.sh` | Add validation, new nginx config generator, update docker-compose generator |
| `docker-compose.yaml` (template) | Add n8n_nginx_public service |
| `README.md` | Architecture update, public website section |
| `docs/CLOUDFLARE.md` | Dual hostname configuration |
| `docs/PUBLIC_WEBSITE.md` | NEW - complete guide |
| `docs/TROUBLESHOOTING.md` | Update ECH section |
| `docs/ENVIRONMENTAL_VARIABLES.md` | New variables |
| `docs/CHANGELOG.md` | Document changes |

---

## Rollback Plan

If issues arise, users can:
1. Disable public website feature (`INSTALL_PUBLIC_WEBSITE=false`)
2. Re-run setup.sh
3. System returns to single-nginx architecture

---

## Implementation Progress

| Task | Status | Notes |
|------|--------|-------|
| **Phase 1: Core Changes** | | |
| 1. Update `setup.sh` validation logic | ✅ Complete | Added validation in both interactive and preconfig modes |
| 2. Create `generate_public_nginx_conf()` function | ✅ Complete | Generates nginx-public.conf for public website container |
| 3. Update `generate_docker_compose_v3()` for new container | ✅ Complete | Added n8n_nginx_public service |
| 4. Update `generate_nginx_conf_v3()` to remove public server block | ✅ Complete | Removed public server block, removed default_server |
| **Phase 2: Cloudflare Integration** | | |
| 5. Update `configure_cloudflare_tunnel()` with dual hostname guidance | ✅ Complete | Updated final summary with both hostname instructions |
| 6. Update final summary output | ✅ Complete | Merged with task 5 |
| **Phase 3: Management Console** | | |
| 7. Add health check for `n8n_nginx_public` container | ✅ Complete | Added to system.py health checks |

**Legend:** ⬜ Pending | ⏳ In Progress | ✅ Complete

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Port exposure** | Tunnel only (no external ports) | Cleaner, more secure - public site accessed exclusively via Cloudflare Tunnel |
| **Health checks** | Yes, monitor in management console | Add public nginx health status to System > Health page |
| **Container naming** | `n8n_nginx_public` | Consistent with existing pattern (n8n_nginx, n8n_postgres, etc.) |

---

## Estimated Effort

| Task | Complexity | Priority |
|------|------------|----------|
| setup.sh changes | High | P0 |
| nginx-public.conf template | Low | P0 |
| docker-compose updates | Medium | P0 |
| Cloudflare guidance updates | Low | P0 |
| Documentation updates | Medium | P1 |
| Testing | Medium | P1 |

---

*Document Version: 1.2*
*Created: January 2026*
*Last Updated: January 21, 2026*
*Status: IMPLEMENTATION COMPLETE - PR #330*
