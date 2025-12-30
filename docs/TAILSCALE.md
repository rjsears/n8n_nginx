# Tailscale Integration Guide

## Overview

Tailscale provides secure, zero-config VPN access to your n8n installation and Docker host from anywhere in the world. This guide covers everything from creating an account to understanding why specific configurations are needed.

---

## Table of Contents

1. [What is Tailscale?](#what-is-tailscale)
2. [Creating a Tailscale Account](#creating-a-tailscale-account)
3. [Generating Auth Keys](#generating-auth-keys)
4. [Understanding Subnet Routing](#understanding-subnet-routing)
5. [Configuration in n8n Management](#configuration-in-n8n-management)
6. [Approving Routes in Admin Console](#approving-routes-in-admin-console)
7. [Tailscale Serve (HTTPS Proxy)](#tailscale-serve-https-proxy)
8. [Accessing Services via Tailscale](#accessing-services-via-tailscale)
9. [Security Best Practices](#security-best-practices)
10. [Troubleshooting](#troubleshooting)

---

## What is Tailscale?

Tailscale is a VPN service built on WireGuard that creates a secure mesh network (called a "tailnet") between your devices. Unlike traditional VPNs:

- **No port forwarding required** - Works behind NAT and firewalls
- **Zero configuration** - Devices automatically find each other
- **End-to-end encrypted** - Traffic is encrypted device-to-device
- **Magic DNS** - Access devices by name (e.g., `n8n-tailscale.your-tailnet.ts.net`)

### Why Use Tailscale with n8n?

1. **Remote Access** - Access your n8n instance and management console from anywhere
2. **SSH to Docker Host** - Manage your server without exposing SSH to the internet
3. **No Public Ports** - Keep your infrastructure completely private
4. **Multiple Devices** - Access from laptop, phone, tablet - all secure

---

## Creating a Tailscale Account

### Step 1: Sign Up

1. Visit [https://tailscale.com](https://tailscale.com)
2. Click **Get Started** or **Sign Up**
3. Choose a sign-in method:
   - **Google** (recommended for personal use)
   - **Microsoft** (recommended for organizations)
   - **GitHub** (great for developers)
   - **Apple** (iOS users)
   - **Email + password** (custom domains only)

### Step 2: Create Your Tailnet

After signing up, Tailscale automatically creates a tailnet for you:

- Your tailnet name is based on your email domain or a generated name
- Example: `your-email.gmail.com` becomes `your-email.ts.net`
- You can customize this later in **Settings** > **General**

### Step 3: Install Tailscale on Your First Device

To manage your tailnet, install Tailscale on at least one device:

**macOS:**
```bash
brew install tailscale
```

**Windows:**
Download from [https://tailscale.com/download/windows](https://tailscale.com/download/windows)

**Linux (Ubuntu/Debian):**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

**iOS/Android:**
Install from App Store or Google Play Store

### Step 4: Connect Your Device

```bash
sudo tailscale up
```

This opens a browser for authentication. After authenticating, your device is part of your tailnet.

---

## Generating Auth Keys

Auth keys allow the n8n Tailscale container to join your tailnet automatically without interactive login.

### Step 1: Access the Admin Console

1. Visit [https://login.tailscale.com/admin/settings/keys](https://login.tailscale.com/admin/settings/keys)
2. Or navigate: **Tailscale Admin Console** > **Settings** > **Keys**

### Step 2: Generate an Auth Key

1. Click **Generate auth key**
2. Configure the key settings:

| Setting | Recommended Value | Explanation |
|---------|-------------------|-------------|
| **Description** | `n8n Docker` | Helps identify the key's purpose |
| **Reusable** | ✅ Enabled | Allows container restarts without new keys |
| **Ephemeral** | ❌ Disabled | Node persists in admin console |
| **Pre-approved** | ✅ Enabled | Skip manual device approval |
| **Tags** | Optional | For ACL management |
| **Expiration** | 90 days or never | Your preference |

3. Click **Generate key**
4. **Copy the key immediately** - it's only shown once!

The key looks like: `tskey-auth-kBWxxxxxCNTRL-xxxxxxxxxxxxxxxxx`

### Step 3: Store the Key Securely

Add to your n8n `.env` file:
```env
TAILSCALE_AUTH_KEY=tskey-auth-kBWxxxxxCNTRL-xxxxxxxxxxxxxxxxx
```

> ⚠️ **Security Note**: Never commit auth keys to version control. Add `.env` to `.gitignore`.

---

## Understanding Subnet Routing

### What is Subnet Routing?

Subnet routing allows devices on your Tailscale network to access IPs that aren't directly running Tailscale. In our case:

- The **Tailscale container** runs inside Docker
- Your **Docker host** has a local IP (e.g., `192.168.1.10`)
- Other Tailscale devices need to reach the Docker host

### Why We Use /32 Routing

The n8n setup advertises a `/32` route (single IP) rather than a full subnet:

```
TS_ROUTES=192.168.1.10/32
```

**Why /32 specifically?**

| Route Type | Example | What It Exposes |
|------------|---------|-----------------|
| `/32` | `192.168.1.10/32` | Only your Docker host IP |
| `/24` | `192.168.1.0/24` | Your entire local network (254 hosts) |
| `/16` | `192.168.0.0/16` | 65,534 hosts |

**Benefits of /32:**

1. **Minimal Exposure** - Only your Docker host is accessible, not your entire LAN
2. **Precise Control** - You know exactly what's reachable
3. **Security** - Other devices on your network aren't exposed
4. **Simplicity** - No complex ACL rules needed

### What Can You Access via the /32 Route?

With the Docker host IP routed (`192.168.1.10/32`), you gain the ability to SSH directly to your Docker host from anywhere on your Tailscale network. However, for web services, **we recommend using Tailscale Serve** (Magic DNS) which provides a cleaner experience without port numbers.

**SSH Access (via Tailscale):**
```bash
ssh user@n8n-tailscale.your-tailnet.ts.net
```

**Web Services (via Tailscale Serve - recommended):**

All web services are accessed through nginx reverse proxy with path-based routing - no ports to remember:

| Service | URL |
|---------|-----|
| **n8n** | `https://n8n-tailscale.your-tailnet.ts.net` |
| **Management Console** | `https://n8n-tailscale.your-tailnet.ts.net/management` |
| **Adminer** (optional) | `https://n8n-tailscale.your-tailnet.ts.net/adminer` |
| **Portainer** (optional) | `https://n8n-tailscale.your-tailnet.ts.net/portainer` |
| **Dozzle** (optional) | `https://n8n-tailscale.your-tailnet.ts.net/dozzle` |

> **Note**: This system is specifically designed to eliminate port requirements. All services are routed through nginx on standard HTTPS (443), with paths determining which service you access.

### When to Use Larger Subnets

You might want `/24` or larger if:

- You need to access multiple servers on your LAN
- You're setting up a full site-to-site VPN
- You have IoT devices you want to access remotely

To enable a full subnet:
```env
TAILSCALE_HOST_IP=192.168.1.0/24
```

> ⚠️ **Warning**: Larger subnets require careful ACL configuration to prevent unintended access.

---

## Configuration in n8n Management

### Required Environment Variables

Add these to your `.env` file:

```env
# Tailscale auth key (from admin console)
TAILSCALE_AUTH_KEY=tskey-auth-xxxxxxxxxxxxx

# Your Docker host's LOCAL IP address
# This is the IP on your LAN, not a public IP
TAILSCALE_HOST_IP=192.168.1.10
```

### Finding Your Docker Host IP

**Linux:**
```bash
# Get the primary interface IP
ip route get 1 | awk '{print $7}'

# Or list all interfaces
ip -4 addr show | grep inet
```

**macOS:**
```bash
ipconfig getifaddr en0
```

**Windows (PowerShell):**
```powershell
(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Ethernet").IPAddress
```

### Docker Compose Configuration

The Tailscale container is configured in `docker-compose.yml`:

```yaml
n8n_tailscale:
  image: tailscale/tailscale:stable
  container_name: n8n_tailscale
  hostname: n8n-tailscale
  environment:
    - TS_AUTHKEY=${TAILSCALE_AUTH_KEY}
    - TS_ROUTES=${TAILSCALE_HOST_IP}/32
    - TS_AUTH_ONCE=true
    - TS_SERVE_CONFIG=/config/tailscale-serve.json
  volumes:
    - tailscale_data:/var/lib/tailscale
    - ./tailscale-serve.json:/config/tailscale-serve.json:ro
  cap_add:
    - NET_ADMIN
    - SYS_MODULE
  devices:
    - /dev/net/tun
  restart: unless-stopped
```

### Key Configuration Options

| Variable | Purpose |
|----------|---------|
| `TS_AUTHKEY` | Authenticates to your tailnet |
| `TS_ROUTES` | IP(s) to advertise for subnet routing |
| `TS_AUTH_ONCE` | Prevents re-auth on restart (requires reusable key) |
| `TS_SERVE_CONFIG` | Enables HTTPS proxy via Tailscale Serve |

---

## Approving Routes in Admin Console

After the container starts, you **must** approve the advertised routes.

### Step 1: Access Machines List

1. Visit [https://login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines)
2. Find **n8n-tailscale** in the list (your container's hostname)

### Step 2: Approve Subnet Routes

1. Click on the **n8n-tailscale** machine
2. Scroll to the **Subnets** section
3. You'll see: `192.168.1.10/32` (Pending approval)
4. Click **Approve**

### Step 3: Verify Route Status

After approval, the status should show:
- ✅ `192.168.1.10/32` (Approved)

### Step 4: Enable Serve (If Prompted)

If using Tailscale Serve, you may need to:
1. Scroll to **Serve** section
2. Toggle to **Enable**

### Why Approval is Required

This is a security feature:
- Prevents rogue devices from advertising routes
- Ensures only authorized routes are enabled
- Gives administrators control over network topology

---

## Tailscale Serve (HTTPS Proxy)

Tailscale Serve creates an HTTPS endpoint on your tailnet that proxies to your n8n instance.

### How It Works

```
[Your Device]
    → https://n8n-tailscale.your-tailnet.ts.net (Tailscale encrypted)
    → [Tailscale Container]
    → https://your-domain.com:443 (proxied to nginx)
    → [n8n]
```

### Benefits

1. **Valid HTTPS** - Tailscale provides automatic certificates
2. **Magic DNS** - Easy-to-remember URL
3. **No Port Exposure** - Works without any open ports
4. **Encrypted** - End-to-end via WireGuard

### Configuration File

The `tailscale-serve.json` file configures the proxy:

```json
{
  "TCP": {
    "443": {
      "HTTPS": true
    }
  },
  "Web": {
    "${TS_CERT_DOMAIN}:443": {
      "Handlers": {
        "/": {
          "Proxy": "https://your-domain.com:443"
        }
      }
    }
  }
}
```

Replace `your-domain.com` with your actual domain.

### Verifying Serve Status

```bash
docker exec n8n_tailscale tailscale serve status
```

Expected output:
```
https://n8n-tailscale.your-tailnet.ts.net (Tailscale Serve)
|-- / proxy https://your-domain.com:443
```

---

## Accessing Services via Tailscale

### Recommended: Magic DNS with Path-Based Routing

The n8n Management Suite uses nginx reverse proxy to eliminate port requirements. All services are accessed via paths on a single URL:

| Service | URL |
|---------|-----|
| **n8n** | `https://n8n-tailscale.your-tailnet.ts.net` |
| **Management Console** | `https://n8n-tailscale.your-tailnet.ts.net/management` |
| **Adminer** (optional) | `https://n8n-tailscale.your-tailnet.ts.net/adminer` |
| **Portainer** (optional) | `https://n8n-tailscale.your-tailnet.ts.net/portainer` |
| **Dozzle** (optional) | `https://n8n-tailscale.your-tailnet.ts.net/dozzle` |

**Benefits:**
- No ports to remember
- Single URL for all services
- Automatic HTTPS certificate from Tailscale
- Works from any Tailscale-connected device

### SSH Access to Docker Host

SSH to your Docker host using the Tailscale Magic DNS name:

```bash
# SSH to Docker host via Tailscale
ssh user@n8n-tailscale.your-tailnet.ts.net
```

This works from anywhere in the world as long as you're connected to your Tailscale network.

> **Note about the Tailscale Container**: The SSH connection above connects to your **Docker host**, not the Tailscale container itself. If you need shell access to the Tailscale container:
>
> 1. **Easiest**: Use the **Terminal** button in the Management Console's Container view - no extra configuration needed
> 2. **Alternative**: Enable [Tailscale SSH](https://tailscale.com/kb/1193/tailscale-ssh) on the container (see below)

### Tailscale SSH (Optional Advanced Feature)

Tailscale offers its own SSH server that provides passwordless, key-less SSH authentication using your Tailscale identity. This is separate from traditional SSH and provides additional security features.

**To enable Tailscale SSH on the container:**

1. Enter the container:
   ```bash
   docker exec -it n8n_tailscale sh
   ```

2. Enable Tailscale SSH:
   ```bash
   tailscale set --ssh
   ```

3. Configure ACLs in the [Tailscale Admin Console](https://login.tailscale.com/admin/acls) to permit SSH access:
   ```json
   "ssh": [
     {
       "action": "accept",
       "src": ["autogroup:member"],
       "dst": ["tag:n8n"],
       "users": ["root", "autogroup:nonroot"]
     }
   ]
   ```

**Benefits of Tailscale SSH:**
- No SSH keys to manage
- Authentication via your identity provider
- Session recording (optional)
- Check mode for re-authentication on sensitive connections

**For most users**: The Management Console's built-in Terminal feature is the simplest way to access containers without any additional configuration.

For more details, see the [Tailscale SSH documentation](https://tailscale.com/kb/1193/tailscale-ssh).

### Finding the Tailscale IP

Access via the container's Tailscale IP:

```bash
# Find the Tailscale IP
docker exec n8n_tailscale tailscale ip

# Output: 100.x.x.x
```

---

## Security Best Practices

### 1. Use Reusable, Pre-approved Keys

This prevents the container from losing access after restarts while maintaining security:
```
Reusable: ✅ Yes
Pre-approved: ✅ Yes
Ephemeral: ❌ No
```

### 2. Set Key Expiration

For production, use keys that expire and rotate them periodically:
- 90 days is a good balance
- Set calendar reminders to rotate keys

### 3. Use Access Control Lists (ACLs)

Configure ACLs to restrict who can access what:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["group:admins"],
      "dst": ["tag:n8n:*"]
    }
  ],
  "tagOwners": {
    "tag:n8n": ["autogroup:admin"]
  }
}
```

### 4. Restrict Management Console to Tailscale

In the n8n Management Console:
1. Go to **Settings** > **Security**
2. Set allowed IPs to only include Tailscale range:
   ```
   100.64.0.0/10
   ```
3. This makes the management console only accessible via Tailscale

### 5. Monitor Access Logs

Regularly check:
- Tailscale Admin Console for connected devices
- Management Console logs for access attempts

---

## Troubleshooting

### Container Won't Start

**Check auth key validity:**
```bash
docker logs n8n_tailscale 2>&1 | grep -i auth
```

Common issues:
- Key expired
- Key already used (if not reusable)
- Network connectivity issues

### Routes Not Working

**Verify route is advertised:**
```bash
docker exec n8n_tailscale tailscale status
```

Look for:
```
# Subnet routes:
192.168.1.10/32 (pending)  # Needs approval
192.168.1.10/32            # Approved and active
```

**Check admin console:**
- Routes may need manual approval
- Visit [Machines page](https://login.tailscale.com/admin/machines)

### Can't Access Docker Host

1. **Verify TAILSCALE_HOST_IP is correct:**
   ```bash
   grep TAILSCALE_HOST_IP .env
   ```

2. **Ping the host from another Tailscale device:**
   ```bash
   ping 192.168.1.10
   ```

3. **Check route approval:**
   - Must be approved in admin console

### Serve Not Working

**Check serve status:**
```bash
docker exec n8n_tailscale tailscale serve status
```

**Verify serve.json configuration:**
```bash
docker exec n8n_tailscale cat /config/tailscale-serve.json
```

**Check for errors:**
```bash
docker logs n8n_tailscale 2>&1 | grep -i serve
```

### Connection Timeout

1. **Ensure Tailscale is running on your device:**
   ```bash
   tailscale status
   ```

2. **Check if route is enabled:**
   The route must show as active, not pending

3. **Verify no firewall blocking:**
   ```bash
   # On Docker host
   sudo iptables -L | grep -i tailscale
   ```

### Need to Re-authenticate

If using `TS_AUTH_ONCE=true` but auth is lost:

1. Generate a new auth key
2. Update `.env` with the new key
3. Restart the container:
   ```bash
   docker compose restart n8n_tailscale
   ```

---

## Quick Reference

### Commands

```bash
# Check Tailscale status
docker exec n8n_tailscale tailscale status

# Get Tailscale IP
docker exec n8n_tailscale tailscale ip

# Check serve status
docker exec n8n_tailscale tailscale serve status

# View container logs
docker logs n8n_tailscale

# Restart Tailscale container
docker compose restart n8n_tailscale
```

### URLs

| Resource | URL |
|----------|-----|
| Admin Console | https://login.tailscale.com/admin |
| Generate Auth Keys | https://login.tailscale.com/admin/settings/keys |
| Machine List | https://login.tailscale.com/admin/machines |
| ACL Editor | https://login.tailscale.com/admin/acls |

### Environment Variables

| Variable | Example | Purpose |
|----------|---------|---------|
| `TAILSCALE_AUTH_KEY` | `tskey-auth-xxx` | Authentication |
| `TAILSCALE_HOST_IP` | `192.168.1.10` | Subnet route IP |

---

## Related Documentation

- [README.md](../README.md) - Main documentation
- [SECURITY.md](./SECURITY.md) - Security configuration
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - General troubleshooting
