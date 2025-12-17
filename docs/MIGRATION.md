# Migration Guide: v2.0 to v3.0

## Overview

This guide covers upgrading from n8n_nginx v2.0 to v3.0, which adds the management console and related features.

---

## What Changes

### Added

| Component | Description |
|-----------|-------------|
| `n8n_management` container | Management console backend (FastAPI) |
| `n8n_management_frontend` | Management console frontend (Vue.js) |
| `n8n_adminer` container | Database admin UI (optional) |
| `n8n_dozzle` container | Container logs viewer (optional) |
| Management database | New PostgreSQL database for management data |
| Nginx management block | New server block for management port |

### Preserved

- All n8n workflows and credentials
- All n8n configuration
- Existing SSL certificates
- PostgreSQL data
- n8n encryption key
- DNS provider configuration

### Modified

| File | Changes |
|------|---------|
| `docker-compose.yaml` | New services added |
| `nginx.conf` | New port block for management |
| `.env` | New management variables added |
| `setup.sh` | Upgraded to v3.0 |

---

## Before You Begin

### Check Requirements

| Requirement | Minimum |
|-------------|---------|
| Docker | 20.10+ |
| Docker Compose | v2+ |
| Free disk space | 2GB |
| Expected downtime | 5-15 minutes |

### Backup Everything

The migration script creates automatic backups, but it's good practice to create your own:

```bash
# Navigate to your n8n directory
cd /path/to/n8n_nginx

# Backup docker-compose
cp docker-compose.yaml docker-compose.yaml.manual-backup

# Backup nginx config
cp nginx.conf nginx.conf.manual-backup

# Backup .env
cp .env .env.manual-backup

# Backup PostgreSQL
docker exec n8n_postgres pg_dump -U n8n -d n8n -F c > n8n_manual_backup.dump

# Backup SSL certificates (if not using Let's Encrypt volume)
sudo cp -r /etc/letsencrypt ./letsencrypt-backup
```

### Verify Current Installation

```bash
# Check current version
grep "VERSION" setup.sh

# Check services are running
docker compose ps

# Verify n8n is accessible
curl -s https://your-domain.com/healthz
```

---

## Migration Process

### Automatic Migration (Recommended)

Run the setup script:

```bash
./setup.sh
```

The script will:
1. Detect your v2.0 installation
2. Offer to upgrade to v3.0
3. Create pre-migration backups
4. Configure the management console
5. Start new services
6. Verify everything works

### What to Expect

```
================================================================================
                           n8n Setup Script v3.0
================================================================================

Detecting current installation...
✓ Version 2.0 detected

================================================================================
                        UPGRADE: v2.0 → v3.0
================================================================================

This upgrade will add:
  • Management console for backups and monitoring
  • Web-based administration interface
  • Automated backup scheduling
  • Multi-channel notifications

Your existing data will be preserved.

Upgrade from v2.0 to v3.0? [y/N]:
```

### Configuration Prompts

During migration, you'll be asked to configure:

#### 1. Management Port

```
Management Console Port Configuration
=====================================
The management console needs a port for HTTPS access.
This port will be used alongside port 443 for n8n.

Recommended port: 3333 (default)
Reserved ports (cannot use): 80, 443, 5432, 5678, 8080, 8443

Enter management port [3333]:
```

**Considerations:**
- Must be between 1024 and 65535
- Cannot conflict with existing services
- Must be accessible through your firewall

#### 2. Admin Credentials

```
Admin User Configuration
========================
Create the admin user for the management console.

Admin username [admin]:
Admin password (min 12 characters):
Confirm password:
Admin email [admin@your-domain.com]:
```

**Requirements:**
- Password minimum 12 characters
- Recommended: mix of letters, numbers, symbols

#### 3. NFS Storage (Optional)

```
Backup Storage Configuration
============================
Configure where backups will be stored.

Use NFS for backup storage? [y/N]:

If yes:
NFS Server [192.168.1.100]:
NFS Path [/backups]:
```

#### 4. Notifications (Optional)

```
Notification Configuration
==========================
Configure notification channels for alerts.

Configure notifications now? [y/N]:

Available channels:
  1) Slack
  2) Discord
  3) Email
  4) NTFY
  5) Skip for now
```

---

## Post-Migration

### Verify Services

```bash
# Check all containers are running
docker compose ps

# Expected output:
# NAME                STATUS
# n8n                 Up (healthy)
# n8n_postgres        Up (healthy)
# n8n_nginx           Up
# n8n_management      Up (healthy)
# n8n_certbot         Up

# Check n8n is accessible
curl -s https://your-domain.com/healthz
# Expected: {"status":"ok"}

# Check management console
curl -s https://your-domain.com:3333/api/health
# Expected: {"status":"healthy","version":"3.0.0"}
```

### Access Management Console

1. Open `https://your-domain.com:3333`
2. Log in with your admin credentials
3. Explore the dashboard

### Configure Backups

1. Go to **Backups** → **Schedules**
2. Click **Add Schedule**
3. Configure your first backup:
   - Name: "Daily n8n backup"
   - Type: postgres_n8n
   - Frequency: Daily
   - Time: 02:00
4. Click **Save**
5. Click **Run Now** to test

### Set Up Notifications

1. Go to **Notifications** → **Services**
2. Click **Add Service**
3. Configure your preferred channel
4. Click **Test** to verify
5. Go to **Notifications** → **Rules**
6. Create rules for important events:
   - `backup.failed` → your service (critical)
   - `container.unhealthy` → your service (high)

---

## Rollback

If something goes wrong, you can rollback within 30 days:

```bash
./setup.sh --rollback
```

This will:
1. Stop v3.0 services
2. Restore v2.0 configuration files
3. Remove management database
4. Start v2.0 services
5. Verify restoration

### Manual Rollback

If the automatic rollback fails:

```bash
# Stop all services
docker compose down

# Restore backup files
cp docker-compose.yaml.v2.backup docker-compose.yaml
cp nginx.conf.v2.backup nginx.conf
cp .env.v2.backup .env

# Remove v3.0 volumes (optional)
docker volume rm n8n_management_data

# Start v2.0 services
docker compose up -d

# Verify
docker compose ps
curl -s https://your-domain.com/healthz
```

### Restore Database (if needed)

```bash
# Stop n8n
docker compose stop n8n

# Restore from backup
docker exec -i n8n_postgres pg_restore \
  -U n8n -d n8n --clean --if-exists \
  < n8n_manual_backup.dump

# Start n8n
docker compose start n8n
```

---

## Troubleshooting

### Migration Fails at Database Step

**Error:** "Could not create database"

**Solution:**
```bash
# Check PostgreSQL is running
docker compose ps postgres

# Try creating database manually
docker exec n8n_postgres psql -U n8n -c "CREATE DATABASE n8n_management;"

# Retry migration
./setup.sh
```

### Management Container Won't Start

**Error:** Container exits immediately

**Solutions:**

1. Check logs:
   ```bash
   docker logs n8n_management
   ```

2. Common issues:
   - **Port conflict**: Change `MGMT_PORT` in `.env`
   - **Database connection**: Verify PostgreSQL is healthy
   - **Missing environment variables**: Check `.env` file

3. Verify database:
   ```bash
   docker exec n8n_postgres psql -U n8n -c "\l" | grep n8n_management
   ```

### Can't Access Management Console

**Problem:** Browser shows connection refused or timeout

**Solutions:**

1. Check firewall:
   ```bash
   # UFW
   sudo ufw allow 3333/tcp

   # firewalld
   sudo firewall-cmd --add-port=3333/tcp --permanent
   sudo firewall-cmd --reload
   ```

2. Verify nginx config:
   ```bash
   docker exec n8n_nginx nginx -t
   ```

3. Check SSL certificate covers the domain:
   ```bash
   docker exec n8n_nginx ls -la /etc/letsencrypt/live/your-domain.com/
   ```

4. Test from server:
   ```bash
   curl -k https://localhost:3333/api/health
   ```

### n8n Stops Working After Migration

**Solutions:**

1. Check n8n logs:
   ```bash
   docker logs n8n --tail 100
   ```

2. Verify database connection:
   ```bash
   docker exec n8n_postgres pg_isready -U n8n
   ```

3. Check n8n can reach database:
   ```bash
   docker exec n8n ping -c 1 n8n_postgres
   ```

4. If needed, rollback:
   ```bash
   ./setup.sh --rollback
   ```

### Certificate Issues

**Problem:** SSL errors after migration

**Solutions:**

1. Check certificate exists:
   ```bash
   docker exec n8n_nginx ls -la /etc/letsencrypt/live/your-domain.com/
   ```

2. Verify certificate is valid:
   ```bash
   echo | openssl s_client -connect your-domain.com:443 2>/dev/null | \
     openssl x509 -noout -dates
   ```

3. Force certificate renewal:
   ```bash
   docker exec n8n_certbot certbot renew --force-renewal
   docker compose restart nginx
   ```

### Database Connection Errors

**Error:** "Connection refused" or "Database does not exist"

**Solutions:**

1. Check PostgreSQL is running:
   ```bash
   docker compose ps postgres
   docker exec n8n_postgres pg_isready -U n8n
   ```

2. Verify databases exist:
   ```bash
   docker exec n8n_postgres psql -U n8n -c "\l"
   ```

3. Check connection from management container:
   ```bash
   docker exec n8n_management pg_isready -h postgres -U n8n
   ```

---

## FAQ

**Q: How long does migration take?**

A: Typically 5-10 minutes, depending on database size. Most time is spent on:
- Creating backups (1-2 min)
- Stopping/starting services (1 min)
- Database preparation (1-2 min)
- Verification (1 min)

**Q: Is there downtime?**

A: Yes, n8n is briefly stopped during migration (usually under 2 minutes). Running workflows will be interrupted and resumed when n8n starts again.

**Q: Can I migrate without optional features?**

A: Yes, you can skip during setup:
- NFS storage → use local backups
- Notifications → configure later via UI
- Adminer → skip database UI
- Dozzle → skip log viewer

**Q: What if I want to add features later?**

A: Run `./setup.sh` again. It will detect v3.0 and offer to add optional features or reconfigure existing ones.

**Q: How long can I rollback?**

A: Rollback is available for 30 days after migration. After that, backup files may be cleaned up by retention policies.

**Q: Will my workflows continue running?**

A: Yes, all workflows and their schedules are preserved. Active executions will resume after n8n restarts.

**Q: Do I need to update DNS?**

A: No, unless you want to access management on a different subdomain. By default, it uses the same domain with a different port.

**Q: Can I use a different port later?**

A: Yes, edit `MGMT_PORT` in `.env` and run:
```bash
docker compose up -d
```

**Q: Is the management console secure?**

A: Yes, it uses:
- HTTPS with same SSL certificate as n8n
- Session-based JWT authentication
- Password requirements (min 12 chars)
- Optional subnet restrictions

---

## Getting Help

If you encounter issues not covered here:

1. **Check logs:**
   ```bash
   docker compose logs > migration-logs.txt
   ```

2. **Check GitHub Issues:**
   https://github.com/rjsears/n8n_nginx/issues

3. **Create new issue with:**
   - Operating system and version
   - Docker and Docker Compose versions
   - Full error messages
   - Contents of migration-logs.txt
