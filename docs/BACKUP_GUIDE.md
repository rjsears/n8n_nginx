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
6. [Selective Restore](#selective-restore)
7. [Backup Verification](#backup-verification)
8. [Best Practices](#best-practices)

### Other Documentation

- [API Reference](./API.md) - REST API documentation
- [Certbot Guide](./CERTBOT.md) - SSL certificate management
- [Cloudflare Guide](./CLOUDFLARE.md) - Cloudflare Tunnel setup
- [Environment Variables](./ENVIRONMENTAL_VARIABLES.md) - Complete .env configuration reference
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

## Pruning

Pruning is the deletion of old backups, applied on top of the [retention policy](#retention-policies) above, to keep storage usage under control. Four independent modes can be enabled together.

Every pruning path — scheduled or manual, including emergency deletion — keeps the newest
`retention_min_count` ("Safety Net", default 3, never less than 1) successful backups **of each backup type**.
They are never marked for deletion or deleted, and a pending deletion that would remove one of them is cancelled.

The automatic runs (hourly and after every backup) only execute due pending deletions, GFS retention and
time-based pruning. For the space-based, size-based and critical-space conditions they only log a warning and send
the `backup_critical_space` notification; backups are deleted for those reasons only when you trigger pruning
manually (`POST /api/backups/pruning/run`). There is no setting to make space/size deletion automatic, because low
disk space is often caused by something other than backups and automatic deletion could remove every backup.

### Time-Based Pruning

- Delete backups older than X days
- Respects the retention policy — backups a retention rule needs to keep are not deleted

### Space-Based Pruning

- Trigger when free space falls below X% (a configurable threshold)
- Automatic runs: alert only. Manual run: marks the oldest unprotected backups outside the Safety Net

### Size-Based Pruning

- Keep total backup storage under X GB
- Automatic runs: alert only. Manual run: marks the oldest unprotected backups outside the Safety Net
  until the total is under the limit

### Critical Space Handling

- Emergency threshold (default: 5% free space)
- Two response options for a manual run: delete the oldest backups outside the Safety Net immediately,
  or alert only. Automatic runs always alert only

### Configuring Pruning

**Via Management UI:**
1. Go to **Settings** → **Backups** → **Pruning**
2. Enable the pruning modes you want (time-based, space-based, size-based)
3. Set the threshold for each enabled mode
4. Configure the critical space handling behavior
5. Save

**Via API:**
See [Storage & Pruning](./API.md#storage-pruning) in the API Reference for the full `BackupPruningSettingsResponse` schema and the endpoints to preview pruning candidates, view pending deletions, or force a pruning pass.

!!! note

    Backups marked as protected (see [Per-row actions → Protect](manual/backups.md#row-actions) in the User Manual) are never removed by any pruning mode.

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

### In-app System Restore (n8n database, config files, certificates)

Available through the **System Restore** dialog and the API (`POST /api/backups/{id}/restore/full`,
`POST /api/backups/{id}/restore/database`).

- Databases are **not** selected by default. Only the **n8n** database can be restored here; the
  management database (`n8n_management`) is shown but cannot be selected, because the console itself runs
  on it — see [Restoring the management database](#restoring-the-management-database).
- A database restore requires typing `RESTORE` to confirm.
- Only one backup, restore, verification or pruning run can happen at a time. If one is already running
  the API answers **409 Conflict** and the UI shows the message; try again when it has finished.

What an in-app restore of the n8n database does:

1. Checks that the dump in the archive is readable (`pg_restore --list`). Nothing changes if it is not.
2. Takes a **safety dump** of the current n8n database (`pg_dump -Fc`) into
   `<backup storage>/pre_restore/n8n_pre_restore_<timestamp>.dump`.
3. Restores the backup into a temporary database `n8n_restore_tmp` with
   `pg_restore --exit-on-error --single-transaction --no-owner --no-acl`.
   If this fails, the temporary database is dropped and **n8n and its live database are untouched**.
4. Stops the n8n container, disconnects remaining sessions, renames the live database to
   `n8n_pre_restore_<timestamp>` and renames `n8n_restore_tmp` to `n8n`.
   If the rename fails, the previous database is put back.
5. Starts n8n again. This happens in all cases, including failures.

Any error is shown in the dialog with the PostgreSQL error text; a restore is never reported as successful
when a step failed. The result also lists the safety dump path and the name of the kept previous database.

**Rolling back / cleaning up.** The previous database is kept, so you can switch back instantly:

```bash
docker compose stop n8n
docker exec -it n8n_postgres psql -U n8n -d postgres \
  -c 'ALTER DATABASE n8n RENAME TO n8n_restored_bad' \
  -c 'ALTER DATABASE n8n_pre_restore_20260930_101500 RENAME TO n8n'
docker compose start n8n
```

Once you are happy with the restored data, drop the kept copy to reclaim space
(`DROP DATABASE n8n_pre_restore_<timestamp>;`) and delete the safety dump from `pre_restore/`.

**SSL certificates.** Backups include the complete `/etc/letsencrypt` tree (`archive/`, `live/`, `renewal/`,
`accounts/`, …) with its symlinks. Restoring replaces those entries as a whole, so the `live/` symlinks keep
pointing into `archive/` and certbot can keep renewing. Backups made before this change only contain plain
copies of `live/` files: they restore working certificates, but certbot cannot renew them — re-issue the
certificate before it expires.

### Restoring the management database

The management database cannot be restored while the management console is running on it. Use the
bare-metal procedure, which restores every database with only PostgreSQL running:

```bash
tar -xzf backup_<timestamp>.n8n_backup.tar.gz -C /root/n8n_restore
cd /root/n8n_restore
sudo ./restore.sh --target-dir /opt/n8n       # add --dry-run first to preview
```

If the stack in the target directory is running, `restore.sh` stops it (`docker compose down`, volumes are
kept) before it overwrites anything; it asks first unless `--force`/`--auto` is given, and `--dry-run` only
reports it. It then restores config files, certificates and volumes, starts **only** the `postgres` service,
waits until PostgreSQL accepts TCP connections on three consecutive checks (so the image's first-start init
script has finished), restores each database with `pg_restore --exit-on-error --single-transaction` (inside the
postgres container, so the client version always matches), makes `MGMT_DB_USER` the owner of the restored
`n8n_management` objects (the console's startup migrations need to own its tables), and starts the rest of the
stack only if every database restored cleanly. `MGMT_DB_USER` must contain only letters, digits and
underscores; otherwise the script refuses to run. Any failure stops the script and prints the failing line.

### Bare-metal restore with an older archive

Archives whose `metadata.json` has no `restore_script_version` (or one below `3.2.0`) contain a `restore.sh`
that cannot complete: it stops after copying the first config file, skips `.env`, and restores the databases
after n8n is already running while hiding errors. Use the current script instead:

1. Download it from **Backups** → a backup → **Bare Metal** → **Download latest restore.sh**
   (or `GET /api/backups/restore-script` with your API token).
2. Extract the old archive and copy the new script over the old one:
   ```bash
   tar -xzf backup_<timestamp>.n8n_backup.tar.gz -C /root/n8n_restore
   cp restore.sh /root/n8n_restore/restore.sh && chmod +x /root/n8n_restore/restore.sh
   cd /root/n8n_restore && sudo ./restore.sh --dry-run    # then without --dry-run
   ```

After upgrading the management console, **take a fresh full backup** so that your newest archive embeds the
fixed script and the full certificate tree.

### Manual database restore (command line)

**WARNING:** This replaces all current data in the database.

```bash
# 1. Stop n8n so nothing writes to the database
docker compose stop n8n

# 2. Copy the dump into the postgres container (pg_restore needs a seekable file)
docker cp n8n.dump n8n_postgres:/tmp/n8n.dump

# 3. Restore in a single transaction; any error aborts and leaves the database unchanged
docker exec n8n_postgres pg_restore -U n8n -d n8n \
  --clean --if-exists --no-owner --no-acl --exit-on-error --single-transaction \
  /tmp/n8n.dump
docker exec n8n_postgres rm /tmp/n8n.dump

# 4. Start n8n
docker compose start n8n

# 5. Verify n8n is working
curl https://your-domain.com/healthz
```

---

## Selective Restore

The Management UI supports selective restore, allowing you to restore individual items from a backup without performing a full database restore. This is useful for recovering specific workflows, credentials, or configuration files.

### How Selective Restore Works

1. **Mount** the backup - spins up a temporary PostgreSQL container and loads the backup
2. **Browse** the contents - view workflows, credentials, and config files
3. **Restore** individual items - download or restore specific items
4. **Unmount** when done - clean up the temporary container

### Mounting a Backup

**Via Management UI:**
1. Go to **Backups** → **History**
2. Find the backup you want to browse
3. Expand the backup and click **Mount Backup**
4. Wait for the backup to be mounted (may take 1-2 minutes)
5. Once mounted, three collapsible sections appear: **Workflows**, **Credentials**, and **Configuration Files**

**Via API:**
```bash
# Mount a backup
curl -X POST https://your-domain.com/management/api/backups/123/mount \
  -H "Authorization: Bearer $TOKEN"

# Check mount status
curl https://your-domain.com/management/api/backups/mount/status \
  -H "Authorization: Bearer $TOKEN"

# Unmount when done
curl -X POST https://your-domain.com/management/api/backups/123/unmount \
  -H "Authorization: Bearer $TOKEN"
```

### Restoring Workflows

Once a backup is mounted, you can restore individual workflows:

**Via Management UI:**
1. Expand the **Workflows** section
2. Click on a workflow to expand it
3. Choose an action:
   - **Download JSON** - Downloads the workflow as a JSON file for manual import
   - **Restore to n8n** - Restores directly to n8n with a new name (appends `_backup_YYYYMMDD`)

**Via API:**
```bash
# Restore a workflow to n8n
curl -X POST https://your-domain.com/management/api/backups/123/restore/workflow \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "abc123",
    "rename_format": "{name}_backup_{date}"
  }'

# Download workflow as JSON
curl -O -J https://your-domain.com/management/api/backups/123/workflows/abc123/download \
  -H "Authorization: Bearer $TOKEN"
```

### Restoring Credentials

Credentials can also be selectively restored from backups:

**Via Management UI:**
1. Expand the **Credentials** section
2. Click on a credential to expand it
3. Click **Download JSON** to download the credential

**Important Notes on Credentials:**
- Credential data is **encrypted** in the backup using n8n's encryption key
- If restoring to a different n8n instance, you may need to **reconfigure the credential values** after import
- Use the downloaded JSON as a reference for which credentials existed and their types
- For same-instance restores where the encryption key hasn't changed, the data may work directly

**Via API:**
```bash
# Download credential as JSON
curl -O -J https://your-domain.com/management/api/backups/123/credentials/456/download \
  -H "Authorization: Bearer $TOKEN"
```

### Restoring Configuration Files

Configuration files (`.env`, `nginx.conf`, SSL certificates, etc.) can be selectively restored:

**Via Management UI:**
1. Expand the **Configuration Files** section
2. Click on a file to expand it
3. Choose an action:
   - **Download** - Download the file for review or manual placement
   - **Restore File** - Restore directly to the system (existing file is backed up first)

**Via API:**
```bash
# List config files in backup
curl https://your-domain.com/management/api/backups/123/restore/config-files \
  -H "Authorization: Bearer $TOKEN"

# Download a config file
curl -O -J https://your-domain.com/management/api/backups/123/config-files/config/.env/download \
  -H "Authorization: Bearer $TOKEN"

# Restore a config file (backs up existing first)
curl -X POST https://your-domain.com/management/api/backups/123/restore/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "config_path": "config/.env",
    "create_backup": true
  }'
```

### Unmounting a Backup

Always unmount when you're done to free up resources:

**Via Management UI:**
- Click **Unmount Backup** button

**Via API:**
```bash
curl -X POST https://your-domain.com/management/api/backups/123/unmount \
  -H "Authorization: Bearer $TOKEN"
```

**Note:** The restore container is automatically cleaned up after unmounting. If you navigate away without unmounting, you can clean up manually via **Settings** → **Cleanup Restore Container**.

---

### Restore Individual Workflow (Legacy)

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

### Download Options

The Management UI provides two download options for each backup:

#### Download Backup (Data Only)

Downloads a complete backup archive containing all data but **without** the restore.sh script.

**Best for:**
- Archival storage
- Manual restoration
- Importing to different environments

**Includes:**
- All databases (pg_dump files)
- Configuration files (.env, nginx.conf, docker-compose.yaml)
- SSL certificates
- Backup metadata

**Via Management UI:**
1. Go to **Backups** → **History**
2. Find the backup
3. Click **Download Backup**

**Via API:**
```bash
curl -O -J https://your-domain.com/management/api/backups/download/123/data-only \
  -H "Authorization: Bearer $TOKEN"
```

#### Bare Metal (Full Recovery Archive)

Downloads a complete recovery archive including an embedded `restore.sh` script.

**Best for:**
- Disaster recovery
- Migration to new servers
- Complete system restoration

**Includes:**
- All databases (pg_dump files)
- Configuration files (.env, nginx.conf, docker-compose.yaml)
- SSL certificates
- Backup metadata
- **restore.sh** - Self-contained restore script

**Via Management UI:**
1. Go to **Backups** → **History**
2. Find the backup
3. Click **Bare Metal** button
4. Click **Download Recovery Archive**

**Via API:**
```bash
curl -O -J https://your-domain.com/management/api/backups/download/123 \
  -H "Authorization: Bearer $TOKEN"
```

**Using the Bare Metal Archive:**
```bash
# On the target server:
tar -xzf backup_file.tar.gz
cd backup_*/
chmod +x restore.sh
./restore.sh
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
