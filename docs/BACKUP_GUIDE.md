# Backup and Restore Guide

## Overview

The n8n Management System provides comprehensive backup capabilities for:

- PostgreSQL databases (n8n workflows, credentials, and management data)
- n8n configuration files
- Individual workflow exports

---

## Table of Contents

1. [Backup Types](#backup-types)
2. [Scheduling Backups](#scheduling-backups)
3. [Manual Backups](#manual-backups)
4. [Backup Storage](#backup-storage)
5. [Restore Procedures](#restore-procedures)
6. [Backup Verification](#backup-verification)
7. [Best Practices](#best-practices)

### Other Documentation

- [API Reference](./API.md) - REST API documentation
- [Certbot Guide](./CERTBOT.md) - SSL certificate management
- [Cloudflare Guide](./CLOUDFLARE.md) - Cloudflare Tunnel setup
- [Migration Guide](./MIGRATION.md) - Upgrading from v2.0 to v3.0
- [Notifications Guide](./NOTIFICATIONS.md) - Alert and notification setup
- [Tailscale Guide](./TAILSCALE.md) - Tailscale VPN integration
- [Troubleshooting](./TROUBLESHOOTING.md) - Common issues and solutions

---

## Backup Types

### postgres_full

Complete backup of all PostgreSQL databases including n8n and management databases.

**Best for:** Disaster recovery, full system migration

**Includes:**
- n8n database (workflows, credentials, executions)
- Management database (settings, backup history, notification rules)
- All PostgreSQL roles and permissions

### postgres_n8n

Backup of only the n8n database (workflows, credentials, executions).

**Best for:** Regular scheduled backups, quick recovery of n8n data

**Includes:**
- All n8n workflows
- Credentials (encrypted)
- Execution history
- Tags and workflow settings

### n8n_config

Backup of n8n configuration files and environment settings.

**Best for:** Configuration management, environment replication

**Includes:**
- Environment variables
- Custom node configurations
- SSL certificates (optional)

### flows

Export of individual workflows as JSON files.

**Best for:** Workflow versioning, sharing workflows, selective restore

---

## Scheduling Backups

### Via Management Interface

1. Navigate to **Backups** → **Schedules**
2. Click **Add Schedule**
3. Configure:
   - **Name**: Descriptive name (e.g., "Daily n8n backup")
   - **Type**: Select backup type
   - **Frequency**: Hourly, Daily, Weekly, or Monthly
   - **Time**: When to run (for non-hourly)
   - **Enabled**: Toggle on/off
4. Click **Save**

### Recommended Schedule

| Backup Type | Frequency | Retention | Rationale |
|-------------|-----------|-----------|-----------|
| postgres_n8n | Daily at 2:00 AM | 7 daily, 4 weekly, 12 monthly | Balance of protection and storage |
| postgres_full | Weekly (Sunday 3:00 AM) | 4 weekly, 12 monthly | Full recovery capability |
| n8n_config | After changes | 10 versions | Track configuration changes |

### Via API

```bash
curl -X POST https://your-domain.com/management/api/backups/schedules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily n8n backup",
    "backup_type": "postgres_n8n",
    "frequency": "daily",
    "hour": 2,
    "minute": 0,
    "enabled": true
  }'
```

---

## Storage Options

### Local Storage

Backups stored in the management container's volume at `/app/backups`.

**Pros:**
- Simple setup
- Fast backup/restore
- No network dependency

**Cons:**
- Lost if host fails
- Limited by host disk space

**Configuration:**
Default - no additional configuration needed.

### NFS Storage

Backups stored on remote NFS server.

**Pros:**
- Centralized storage
- Survives host failures
- Scalable capacity

**Cons:**
- Network dependency
- Slightly slower

**Configuration during setup:**
```bash
./setup.sh
# Select "Configure NFS for backup storage"
# Enter NFS server: 192.168.1.100
# Enter NFS path: /backups/n8n
```

**Via Management UI:**
1. Go to **Settings** → **Storage**
2. Enable NFS
3. Enter server address and path
4. Click **Test Connection**
5. Save

**Manual NFS mount test:**
```bash
# Test NFS connectivity
showmount -e your-nfs-server

# Test mount
docker exec n8n_management mount -t nfs your-nfs-server:/path /mnt/test
```

---

## Retention Policies

Configure how long backups are kept:

| Category | Default | Description |
|----------|---------|-------------|
| Hourly | 24 | Keep last 24 hourly backups |
| Daily | 7 | Keep last 7 daily backups |
| Weekly | 4 | Keep last 4 weekly backups |
| Monthly | 12 | Keep last 12 monthly backups |

### How Retention Works

1. Each backup is tagged with its schedule frequency
2. Retention policy runs after each successful backup
3. Oldest backups exceeding the retention count are deleted
4. Backups are categorized based on creation time:
   - First backup of each month = monthly
   - First backup of each week = weekly
   - First backup of each day = daily

### Configuring Retention

**Via Management UI:**
1. Go to **Settings** → **Backups**
2. Adjust retention values
3. Save

**Via API:**
```bash
curl -X PUT https://your-domain.com/management/api/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "backup_retention": {
      "hourly": 24,
      "daily": 7,
      "weekly": 4,
      "monthly": 12
    }
  }'
```

---

## Backup Verification

Verification ensures backups can actually be restored.

### How It Works

1. Creates temporary PostgreSQL container
2. Restores backup to temporary container
3. Validates data integrity:
   - Table existence
   - Row counts comparison
   - Checksum verification (if enabled)
4. Cleans up temporary container

### Enabling Automatic Verification

**Via Management UI:**
1. Go to **Settings** → **Backups** → **Verification Schedule**
2. Configure:
   - **Enabled**: On
   - **Frequency**: Daily, Weekly, or Monthly
   - **Day**: Day to run (for weekly/monthly)
   - **Time**: Hour to run
   - **Count**: Number of recent backups to verify
3. Save

### Manual Verification

**Via Management UI:**
1. Go to **Backups** → **History**
2. Find the backup to verify
3. Click **⋮** → **Verify**
4. Wait for verification to complete
5. Check verification status

**Via API:**
```bash
curl -X POST https://your-domain.com/management/api/backups/verify/123 \
  -H "Authorization: Bearer $TOKEN"
```

### Verification States

| Status | Meaning |
|--------|---------|
| `passed` | Backup verified successfully |
| `failed` | Verification failed - backup may be corrupt |
| `pending` | Verification not yet run |
| `running` | Verification in progress |

---

## Restoring Data

### Full Database Restore

**WARNING:** This will replace all current data.

**Via Command Line:**

```bash
# 1. Stop n8n container
docker compose stop n8n

# 2. Download backup file (if using management UI)
# Or locate backup in /app/backups/

# 3. Restore database
docker exec -i n8n_postgres pg_restore \
  -U n8n -d n8n --clean --if-exists \
  < backup_file.dump

# 4. Start n8n
docker compose start n8n

# 5. Verify n8n is working
curl https://your-domain.com/healthz
```

### Restore from Management UI

1. Go to **Backups** → **History**
2. Find the backup to restore
3. Click **⋮** → **Restore**
4. Confirm the restore operation
5. Wait for restore to complete

### Restore Individual Workflow

Use the management interface for safe workflow restoration:

1. Go to **Flows** → **Restore from Backup**
2. Select the backup containing your workflow
3. Browse available workflows
4. Choose the workflow to restore
5. Select conflict action:
   - **Rename**: Add timestamp suffix if name exists
   - **Overwrite**: Replace existing workflow
   - **Skip**: Don't restore if exists
6. Click **Restore**

### Restore via CLI

```bash
# List flows in a backup
docker exec n8n_management python -c "
from api.services.flow_service import FlowService
import asyncio
flows = asyncio.run(FlowService.list_flows_from_backup(BACKUP_ID))
for f in flows:
    print(f'{f.id}: {f.name}')
"

# Restore specific flow
docker exec n8n_management python -c "
from api.services.flow_service import FlowService
import asyncio
result = asyncio.run(FlowService.restore_flow(BACKUP_ID, 'FLOW_ID', 'rename'))
print(result)
"
```

---

## Manual Backup Commands

### Create Manual Backup

**Via Management UI:**
1. Go to **Backups**
2. Click **Create Backup**
3. Select backup type
4. Click **Start**

**Via API:**
```bash
curl -X POST https://your-domain.com/management/api/backups/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"backup_type": "postgres_n8n"}'
```

**Via Docker:**
```bash
# PostgreSQL dump
docker exec n8n_postgres pg_dump -U n8n -d n8n -F c \
  > backup_$(date +%Y%m%d_%H%M%S).dump

# With compression
docker exec n8n_postgres pg_dump -U n8n -d n8n -F c | gzip \
  > backup_$(date +%Y%m%d_%H%M%S).dump.gz
```

### Download Backup

**Via Management UI:**
1. Go to **Backups** → **History**
2. Find the backup
3. Click **⋮** → **Download**

**Via API:**
```bash
curl -O -J https://your-domain.com/management/api/backups/download/123 \
  -H "Authorization: Bearer $TOKEN"
```

---

## Troubleshooting

### Backup Fails with "Connection refused"

**Cause:** PostgreSQL is not running or not accessible.

**Solution:**
```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check PostgreSQL is ready
docker exec n8n_postgres pg_isready -U n8n

# Check PostgreSQL logs
docker logs n8n_postgres --tail 50
```

### Backup Fails with "No space left"

**Cause:** Disk is full.

**Solutions:**
1. Check disk usage:
   ```bash
   df -h
   docker system df
   ```

2. Prune old backups:
   - Via UI: **Backups** → select old backups → **Delete**
   - Or reduce retention settings

3. Clean Docker:
   ```bash
   docker system prune -f
   ```

4. Consider NFS storage for larger capacity

### NFS Mount Fails

**Cause:** Network or permission issues.

**Solutions:**

1. Verify NFS server is reachable:
   ```bash
   ping your-nfs-server
   showmount -e your-nfs-server
   ```

2. Check firewall allows NFS (ports 111, 2049):
   ```bash
   nc -zv your-nfs-server 2049
   ```

3. Verify export permissions on NFS server:
   ```bash
   # On NFS server
   cat /etc/exports
   # Should include your client IP with rw permissions
   ```

4. Test manual mount:
   ```bash
   docker exec n8n_management mount -t nfs \
     your-nfs-server:/path /mnt/test
   ```

### Verification Fails

**Possible Causes:**
- Backup file corrupt
- Insufficient disk space for temp container
- Docker resource limits

**Solutions:**

1. Check backup file integrity:
   ```bash
   # For gzip compressed
   gunzip -t backup_file.dump.gz

   # For pg_dump format
   docker exec n8n_postgres pg_restore --list backup_file.dump
   ```

2. Check available disk space:
   ```bash
   df -h
   ```

3. Check Docker can create containers:
   ```bash
   docker run --rm hello-world
   ```

4. Review verification error details in Management UI

### Restore Fails

**Solutions:**

1. Check target database is accessible:
   ```bash
   docker exec n8n_postgres psql -U n8n -d n8n -c "SELECT 1"
   ```

2. Stop n8n before restore:
   ```bash
   docker compose stop n8n
   ```

3. Try restore with verbose output:
   ```bash
   docker exec -i n8n_postgres pg_restore \
     -U n8n -d n8n --verbose --clean --if-exists \
     < backup_file.dump
   ```

---

## Best Practices

### 1. Test Restores Regularly

Don't wait for an emergency. Schedule quarterly restore tests:
1. Restore to a test environment
2. Verify workflows work correctly
3. Document any issues found

### 2. Use NFS for Production

Local backups alone are risky:
- Same disk as data = single point of failure
- Configure NFS or other remote storage
- Consider cloud storage for critical workloads

### 3. Enable Verification

Catch problems before you need the backup:
- Enable weekly verification at minimum
- Review verification results regularly
- Investigate any failures immediately

### 4. Monitor Notifications

Set up alerts for backup failures:
- Create notification rule for `backup.failed`
- Use multiple notification channels
- Test notifications work

### 5. Document Your Schedule

Know what's backed up and when:
- Export backup schedule configuration
- Document recovery procedures
- Keep recovery runbook updated

### 6. Keep Multiple Copies

Retention policies help, but consider:
- Off-site copies for disaster recovery
- Cloud storage for geographic redundancy
- Encrypted copies for sensitive data

### 7. Secure Your Backups

Backups contain sensitive data:
- Restrict NFS access to management server only
- Use encrypted storage where possible
- Audit access to backup files
