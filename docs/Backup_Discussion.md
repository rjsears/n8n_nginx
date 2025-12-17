# Backup System Implementation Discussion

**Date:** December 17, 2024
**Branch:** test_branch → claude/implement-backup-guide-WMboR

---

## Table of Contents

- [Initial Review of BACKUP_GUIDE.md](#initial-review-of-backup_guidemd)
- [Current Implementation Status](#current-implementation-status)
- [User's Expanded Vision](#users-expanded-vision)
- [Verification Challenge & Solution](#verification-challenge--solution)
- [New Database Schema](#new-database-schema)
- [Revised Implementation Plan](#revised-implementation-plan)
- [Finalized Decisions](#finalized-decisions)
- [NFS Configuration](#nfs-configuration-from-setupsh-analysis)
- [Final Implementation Plan](#final-implementation-plan)
- [Pruning & Retention Decisions](#pruning--retention-decisions)
- [Progress Tracking](#progress-tracking)

---

## Initial Review of BACKUP_GUIDE.md

### Summary of BACKUP_GUIDE.md

#### Backup Types
| Type | Purpose |
|------|---------|
| `postgres_full` | Complete backup of all PostgreSQL databases (n8n + management) |
| `postgres_n8n` | Just n8n database (workflows, credentials, executions) |
| `n8n_config` | Configuration files and environment settings |
| `flows` | Individual workflow exports as JSON |

#### Key Features
1. **Scheduling** - Via Management UI or API (hourly, daily, weekly, monthly)
2. **Storage Options** - Local (`/app/backups`) or NFS remote storage
3. **Retention Policies** - Configurable (default: 24 hourly, 7 daily, 4 weekly, 12 monthly)
4. **Backup Verification** - Creates temp container to test restore viability
5. **Restoration** - Full database restore or individual workflow recovery
6. **API Endpoints** - Full REST API for programmatic backup management

#### Implementation Requirements
This implies building:
- A **management service/container** with API endpoints
- **Database tables** for backup history, schedules, and settings
- **Management UI** for scheduling, viewing, and restoring backups
- **NFS integration** for remote storage
- **Verification system** using temporary PostgreSQL containers
- **Notification integration** for backup failure alerts

---

## Current Implementation Status

### What's Already Implemented ✅

| Component | Status | Details |
|-----------|--------|---------|
| **Database Models** | Complete | BackupSchedule, BackupHistory, RetentionPolicy, VerificationSchedule |
| **Backup Creation** | 95% | pg_dump works for postgres_full/n8n/mgmt |
| **Scheduling** | Complete | APScheduler with cron triggers |
| **Compression** | 50% | gzip works; zstd defined but not implemented |
| **Retention (count-based)** | Complete | Enforces hourly/daily/weekly/monthly limits |
| **Basic Verification** | 25% | Checksum-only validation |
| **Frontend UI** | 85% | Schedule management, history view, manual backup |
| **NFS Setup** | Complete | setup.sh handles NFS configuration |
| **Docker Integration** | Complete | Volume mounts at `/app/backups` and `/mnt/backups` |

### What's Missing ❌

| Feature | Priority | Complexity |
|---------|----------|------------|
| **Database Restore** | HIGH | Medium |
| **Full Verification** (temp container) | HIGH | High |
| **Individual Flow Restore** | HIGH | Medium |
| **n8n_config Backup** | MEDIUM | Low |
| **flows Backup Type** | MEDIUM | Medium |
| **NFS Configuration UI** | LOW | Low |
| **Storage Limit Enforcement** | LOW | Low |
| **zstd Compression** | LOW | Low |

### Technology Stack

#### Backend
| Component | Technology | Details |
|-----------|-----------|---------|
| Web Framework | FastAPI | Async, OpenAPI docs at /api/docs |
| ORM | SQLAlchemy 2.0 | Async with asyncpg driver |
| Database | PostgreSQL | Two databases (management + n8n) |
| Job Scheduler | APScheduler | AsyncIOScheduler with cron triggers |
| Validation | Pydantic v2 | Request/response validation |
| Data Compression | gzip, zstd | Defined; gzip implemented |
| Checksums | hashlib | SHA-256 for file integrity |
| Process Execution | subprocess | For pg_dump commands |
| Notifications | Custom service | Event-based notification system |

#### Frontend
| Component | Technology | Details |
|-----------|-----------|---------|
| Framework | Vue 3 | Composition API |
| State Management | Pinia | Reactive store system |
| UI Component Library | Custom | Card, Badge, Dialog, etc. |
| Icons | Heroicons | 24px outline icons |
| Styling | Tailwind CSS | Utility-first CSS |
| Theme Support | Custom store | Light/dark/neon modes |

#### Database Schema (Existing)
```
Tables:
├── backup_schedules (40 cols)
├── backup_history (33 cols with 4 indexes)
├── retention_policies (7 cols)
├── verification_schedule (8 cols)
├── migration_state (11 cols)
└── apscheduler_jobs (3 cols)
```

---

## User's Expanded Vision

### Full System Backups
Not just databases, but everything needed for bare metal recovery:
- All PostgreSQL databases (n8n + management)
- .env files
- docker-compose.yaml
- nginx.conf
- SSL certificates
- Everything needed to rebuild from scratch

### Selective Workflow Restore
Using a temporary PostgreSQL container:
1. Spin up `n8n_postgres_restore` container
2. Load the backup into it
3. Display all workflows in that backup
4. Allow selecting specific workflow(s)
5. Push to running n8n via API (with renamed name like `workflow_backup_timestamp`)
6. Tear down the restore container when done

### Bare Metal Recovery
Two methods:
- Via SSH to a new server
- By placing backup file next to setup.sh, which detects it and offers full restore

### Backup Verification
- Spin up temp container
- Mount backup files
- Verify backup data matches server data
- Challenge: data changes between backup and verification
- Need ideas on how to handle this

### Backup Metadata Tables
New database tables to track:
- Date/time of backup
- Size of backup
- Name of every workflow in that backup
- Name of every config file backed up
- This allows browsing backup contents without loading the backup

### UI for Backup Browsing
- Click on a backup in the list
- Opens menu showing everything in the backup (without loading it)
- Select workflows to restore
- Choose: file download OR restore to running n8n (renamed)
- Spin up temp container, extract workflow, do the action
- Ask if they need more files
- Tear down when done

---

## Verification Challenge & Solution

### The Core Challenge
- Data changes between backup time and verification time
- We can't compare "backup data = current data" because that's not the goal
- The real question is: "Is this backup restorable and complete?"

### Key Insight
We're testing **Backup Integrity**, not **Data Currency**.

The question isn't "Does this backup match current production?" (impossible - data changes)

The question is: **"If I need to restore this backup, will it work and contain what it claims?"**

### Proposed Verification Approach

#### At Backup Time - Capture Snapshot Metadata:
```json
{
  "backup_metadata": {
    "timestamp": "2024-12-17T02:00:00Z",
    "databases": {
      "n8n": {
        "tables": ["workflows", "credentials", "execution_data", "..."],
        "row_counts": {"workflows": 47, "credentials": 12, "..."},
        "workflow_ids": ["uuid1", "uuid2", "uuid3", "..."],
        "workflow_checksums": {"uuid1": "sha256_of_workflow_json", "..."}
      },
      "n8n_management": {
        "tables": ["..."],
        "row_counts": {"..."}
      }
    },
    "config_files": [
      {"name": ".env", "checksum": "sha256:abc123...", "size": 2048},
      {"name": "nginx.conf", "checksum": "sha256:def456...", "size": 4096},
      {"name": "docker-compose.yaml", "checksum": "sha256:ghi789...", "size": 8192}
    ],
    "total_size": 52428800,
    "compression": "gzip",
    "pg_version": "16.1"
  }
}
```

#### At Verification Time:
1. Spin up `n8n_postgres_restore` container
2. Restore the backup into it
3. Verify against stored metadata:
   - ✅ All tables exist with correct schemas
   - ✅ Row counts match what was recorded at backup time
   - ✅ All workflow_ids are present
   - ✅ Workflow checksums match (proves data integrity)
   - ✅ Config file checksums match
4. **The Ultimate Test:** Query a workflow and verify JSON structure is valid
5. Tear down container

#### What This Proves:
- The backup file is not corrupt
- The backup is restorable (pg_restore succeeds)
- The backup contains exactly what it claimed to contain when created
- No data loss during backup/compression/transfer

#### What This Does NOT Prove (and shouldn't):
- That the backup matches current production (impossible due to time)

---

## New Database Schema

```sql
-- Stores metadata for each backup (for browsing without loading)
CREATE TABLE backup_contents (
    id SERIAL PRIMARY KEY,
    backup_id INTEGER REFERENCES backup_history(id) ON DELETE CASCADE,

    -- Quick lookup data
    workflow_count INTEGER,
    credential_count INTEGER,
    config_file_count INTEGER,

    -- JSON blobs for detailed contents
    workflows_manifest JSONB,      -- [{id, name, active, created_at, updated_at, checksum}, ...]
    credentials_manifest JSONB,    -- [{id, name, type}, ...]  (no sensitive data!)
    config_files_manifest JSONB,   -- [{name, path, size, checksum}, ...]
    database_schema_manifest JSONB, -- [{table, row_count, columns}, ...]

    -- Verification data
    verification_checksums JSONB,  -- {workflow_id: checksum, ...}

    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX idx_backup_contents_backup_id ON backup_contents(backup_id);
```

This allows:
- **Instant browsing** of backup contents without loading
- **Selective restore** - click a workflow, see its name, decide to restore
- **Verification** - compare checksums at any time

---

## Revised Implementation Plan

### Phase 1: Enhanced Backup Creation
*Capture comprehensive metadata at backup time*

| # | Task | Description |
|---|------|-------------|
| 1.1 | Create `backup_contents` table | New database model for backup metadata |
| 1.2 | Implement full system backup | Include .env, docker-compose.yaml, nginx.conf, SSL certs |
| 1.3 | Capture workflow manifest at backup time | Store workflow IDs, names, checksums |
| 1.4 | Capture config file manifest | Store filenames, paths, sizes, checksums |
| 1.5 | Capture database schema manifest | Tables, row counts, column info |
| 1.6 | Store all metadata in backup_contents table | Enables browsing without loading |

**Test:** Create backup, verify metadata captured correctly

---

### Phase 2: Backup Content Browser UI
*Browse backups without loading them*

| # | Task | Description |
|---|------|-------------|
| 2.1 | Add API endpoint `GET /api/backups/{id}/contents` | Return backup_contents data |
| 2.2 | Create BackupContentsDialog.vue component | Modal showing backup contents |
| 2.3 | Add "View Contents" button to backup history | Opens the dialog |
| 2.4 | Display workflows list with name, status, date | Searchable/filterable |
| 2.5 | Display config files list with name, size | Checkmark for verified |
| 2.6 | Add "Restore" button per item | Triggers restore flow |

**Test:** Click backup → see all workflows without loading

---

### Phase 3: Selective Workflow Restore
*Spin up temp container, extract specific workflow*

| # | Task | Description |
|---|------|-------------|
| 3.1 | Implement `spin_up_restore_container()` | Create/start n8n_postgres_restore |
| 3.2 | Implement `load_backup_to_restore_container()` | pg_restore to temp container |
| 3.3 | Implement `extract_workflow_from_restore()` | Query temp DB for workflow JSON |
| 3.4 | Implement `push_workflow_to_n8n()` | Use n8n API to import (renamed) |
| 3.5 | Implement `teardown_restore_container()` | Clean up temp container |
| 3.6 | Add restore dialog with options | "Download as file" vs "Restore to n8n" |
| 3.7 | Handle workflow renaming | `{name}_restored_{timestamp}` |
| 3.8 | Check n8n API availability | Disable "Restore to n8n" if API down |

**Test:** Select workflow from old backup → restore to running n8n

---

### Phase 4: Full System Restore
*Bare metal recovery capability*

| # | Task | Description |
|---|------|-------------|
| 4.1 | Implement `restore_full_system()` | Databases + all config files |
| 4.2 | Add restore safety checks | Stop n8n, backup current state first |
| 4.3 | Implement config file restore | .env, nginx.conf, docker-compose.yaml |
| 4.4 | Implement SSL certificate restore | Let's Encrypt certs |
| 4.5 | Add `POST /api/backups/restore/full/{id}` endpoint | Full system restore |
| 4.6 | Add full restore UI with confirmation | Type "RESTORE" to confirm |
| 4.7 | Implement setup.sh backup detection | Check for backup files on startup |
| 4.8 | Add bare metal restore flow to setup.sh | Offer restore if backup found |

**Test:** Take backup → destroy system → restore from backup

---

### Phase 5: Backup Verification System
*Prove backups are restorable*

| # | Task | Description |
|---|------|-------------|
| 5.1 | Implement scheduled verification | "every N backups" option |
| 5.2 | Spin up temp container for verification | n8n_postgres_verify |
| 5.3 | Restore backup to temp container | Full pg_restore |
| 5.4 | Verify table existence and schemas | Compare to manifest |
| 5.5 | Verify row counts match manifest | Exact match required |
| 5.6 | Verify workflow checksums | Sample or all workflows |
| 5.7 | Verify config file checksums | All config files |
| 5.8 | Store verification results | Pass/fail with details |
| 5.9 | Add verification UI | Show last verification status per backup |
| 5.10 | Send notifications on verification failure | Alert immediately |

**Test:** Create backup → verify → corrupt backup file → verify → should fail

---

### Phase 6: Remote Restore (Future)
*SSH-based restore to new server*

| # | Task | Description |
|---|------|-------------|
| 6.1 | Design SSH restore architecture | How to securely connect |
| 6.2 | Implement SSH connection service | Store credentials securely |
| 6.3 | Implement remote file transfer | SCP backup to new server |
| 6.4 | Implement remote restore execution | Run setup.sh --restore remotely |
| 6.5 | Add remote restore UI | Server address, credentials, status |

**Note:** This phase is more complex and could be a later addition

---

## Verification Schedule Options

For the "every N backups" feature:

```python
verification_schedule = {
    "mode": "every_n",  # or "daily", "weekly", "manual"
    "every_n_backups": 5,  # verify every 5th backup
    # OR
    "mode": "percentage",
    "percentage": 20  # verify 20% of backups randomly
}
```

---

## Finalized Decisions

### 1. Restore Container Strategy
**Decision:** Spin up on-demand (saves resources)
- Containers are quick to spin up
- No resources wasted when not in use
- Clean state for each restore operation

### 2. Config File Storage
**Decision:** Both approaches
- **In tar.gz bundle:** Actual files for bare metal restore
- **In database (JSONB):** Metadata for quick browsing without extracting
- Best of both worlds: speed for browsing, completeness for restore

### 3. Workflow Rename Format
**Decision:** `{name}_backup_{backup_date}`
- Example: "My Workflow_backup_20241215"
- Users will likely rename immediately anyway
- Clear indication of which backup it came from

### 4. Verification Frequency
**Decision:** User-configurable + Manual button
- Let user choose frequency (every N backups, daily, weekly, etc.)
- Always provide a "Verify Now" button for any backup
- No forced default - user decides based on their needs

### 5. Bare Metal Recovery
**Decision:** Self-contained backup with embedded restore.sh

**Naming Convention:**
```
backup_yyyymmddhhmmss.n8n_backup.tar.gz
```
Example: `backup_20241217143022.n8n_backup.tar.gz`

**Backup Archive Contents:**
```
backup_20241217143022.n8n_backup.tar.gz
├── restore.sh                    # Self-contained restore script
├── requirements.txt              # System packages that were installed
├── manifest.json                 # Complete backup metadata
├── databases/
│   ├── n8n.dump                 # n8n database (pg_dump format)
│   └── n8n_management.dump      # Management database
├── config/
│   ├── .env                     # Environment variables
│   ├── docker-compose.yaml      # Docker configuration
│   ├── nginx.conf               # Nginx configuration
│   └── cloudflare.ini           # DNS credentials (if applicable)
├── ssl/
│   ├── fullchain.pem            # SSL certificate
│   └── privkey.pem              # SSL private key
└── metadata/
    ├── workflows.json           # Workflow manifest for browsing
    ├── credentials.json         # Credential manifest (no secrets)
    └── system_info.json         # Original system information
```

**restore.sh Capabilities:**
- Detects if Docker is installed, installs if needed
- Detects if NFS was configured, offers to reconfigure
- Restores all databases
- Restores all config files
- Restores SSL certificates
- Validates restoration
- Starts all services

**Bare Metal Recovery Process:**
1. SCP backup file to new server
2. Extract: `tar -xzf backup_20241217143022.n8n_backup.tar.gz`
3. Run: `./restore.sh`
4. Script handles everything (Docker, databases, configs, SSL)

---

## NFS Configuration (From setup.sh Analysis)

### Key Points from setup.sh

1. **NFS Variables**:
   - `NFS_SERVER` - The NFS server address/hostname
   - `NFS_PATH` - The NFS export path
   - `NFS_CONFIGURED` - Boolean flag

2. **NFS Configuration Process**:
   - Prompts user: "Configure NFS for backup storage?"
   - Checks if `showmount` exists, offers to install NFS client
   - Tests connectivity to NFS server
   - Discovers accessible NFS exports
   - Tests actual NFS mount
   - Saves configuration to state file

3. **Docker Volume Configuration**:
   ```yaml
   nfs_backups:
     driver: local
     driver_opts:
       type: nfs
       o: addr=${NFS_SERVER},rw,nolock,soft
       device: ":${NFS_PATH}"
   ```

4. **Mount Points**:
   - Local staging: `/app/backups` (mgmt_backup_staging volume)
   - NFS storage: `/mnt/backups` (nfs_backups volume)

---

## Final Implementation Plan

Based on the finalized decisions, here is the approved implementation order:

### Phase 1: Enhanced Backup Creation & Archive Format
*Create complete, self-contained backup archives*

| # | Task | Files to Modify/Create |
|---|------|------------------------|
| 1.1 | Create `backup_contents` database model | `models/backups.py` |
| 1.2 | Update backup service to capture workflow manifest | `services/backup_service.py` |
| 1.3 | Capture config file manifest with checksums | `services/backup_service.py` |
| 1.4 | Capture database schema manifest | `services/backup_service.py` |
| 1.5 | Create tar.gz archive with proper structure | `services/backup_service.py` |
| 1.6 | Include all config files (.env, nginx.conf, docker-compose.yaml) | `services/backup_service.py` |
| 1.7 | Include SSL certificates in backup | `services/backup_service.py` |
| 1.8 | Generate manifest.json with complete metadata | `services/backup_service.py` |
| 1.9 | Generate requirements.txt (system packages) | `services/backup_service.py` |
| 1.10 | Create restore.sh template for bare metal | `templates/restore.sh` |
| 1.11 | Store metadata in backup_contents table | `services/backup_service.py` |

**Deliverable:** Complete backup archive in format `backup_yyyymmddhhmmss.n8n_backup.tar.gz`

---

### Phase 2: Backup Content Browser UI
*Browse backup contents without loading*

| # | Task | Files to Modify/Create |
|---|------|------------------------|
| 2.1 | Add `GET /api/backups/{id}/contents` endpoint | `routers/backups.py` |
| 2.2 | Add backup_contents schema | `schemas/backups.py` |
| 2.3 | Create BackupContentsDialog.vue component | `components/backups/BackupContentsDialog.vue` |
| 2.4 | Add "View Contents" button to backup history | `views/BackupsView.vue` |
| 2.5 | Display workflows tab (name, active, created date) | `components/backups/BackupContentsDialog.vue` |
| 2.6 | Display config files tab (name, size, checksum) | `components/backups/BackupContentsDialog.vue` |
| 2.7 | Display database info tab (tables, row counts) | `components/backups/BackupContentsDialog.vue` |
| 2.8 | Add search/filter for workflows | `components/backups/BackupContentsDialog.vue` |

**Deliverable:** Click any backup → see complete contents instantly

---

### Phase 3: Selective Workflow Restore
*Extract and restore individual workflows*

| # | Task | Files to Modify/Create |
|---|------|------------------------|
| 3.1 | Create `restore_service.py` for restore operations | `services/restore_service.py` |
| 3.2 | Implement `spin_up_restore_container()` | `services/restore_service.py` |
| 3.3 | Implement `load_backup_to_container()` | `services/restore_service.py` |
| 3.4 | Implement `extract_workflow()` | `services/restore_service.py` |
| 3.5 | Implement `push_workflow_to_n8n()` via API | `services/restore_service.py` |
| 3.6 | Implement `teardown_restore_container()` | `services/restore_service.py` |
| 3.7 | Add `POST /api/backups/{id}/restore/workflow` endpoint | `routers/backups.py` |
| 3.8 | Add `GET /api/backups/{id}/workflows/{workflow_id}/download` | `routers/backups.py` |
| 3.9 | Create WorkflowRestoreDialog.vue | `components/backups/WorkflowRestoreDialog.vue` |
| 3.10 | Add restore options (download file vs restore to n8n) | `components/backups/WorkflowRestoreDialog.vue` |
| 3.11 | Implement workflow renaming `{name}_backup_{date}` | `services/restore_service.py` |
| 3.12 | Check n8n API availability before restore | `services/restore_service.py` |

**Deliverable:** Select workflow from backup → restore to n8n or download as file

---

### Phase 4: Full System Restore (via Management UI)
*Restore entire system from backup*

| # | Task | Files to Modify/Create |
|---|------|------------------------|
| 4.1 | Implement `restore_full_system()` | `services/restore_service.py` |
| 4.2 | Add pre-restore safety checks | `services/restore_service.py` |
| 4.3 | Create current-state backup before restore | `services/restore_service.py` |
| 4.4 | Implement database restore (both DBs) | `services/restore_service.py` |
| 4.5 | Implement config file restore | `services/restore_service.py` |
| 4.6 | Implement SSL certificate restore | `services/restore_service.py` |
| 4.7 | Add `POST /api/backups/{id}/restore/full` endpoint | `routers/backups.py` |
| 4.8 | Create FullRestoreDialog.vue with confirmation | `components/backups/FullRestoreDialog.vue` |
| 4.9 | Require typing "RESTORE" to confirm | `components/backups/FullRestoreDialog.vue` |
| 4.10 | Add restore progress indicator | `components/backups/FullRestoreDialog.vue` |
| 4.11 | Restart services after restore | `services/restore_service.py` |

**Deliverable:** Full system restore from management console

---

### Phase 5: Backup Verification System
*Prove backups are restorable*

| # | Task | Files to Modify/Create |
|---|------|------------------------|
| 5.1 | Create `verification_service.py` | `services/verification_service.py` |
| 5.2 | Implement `verify_backup()` with temp container | `services/verification_service.py` |
| 5.3 | Verify table existence and schemas | `services/verification_service.py` |
| 5.4 | Verify row counts match manifest | `services/verification_service.py` |
| 5.5 | Verify workflow checksums | `services/verification_service.py` |
| 5.6 | Verify config file checksums | `services/verification_service.py` |
| 5.7 | Store detailed verification results | `services/verification_service.py` |
| 5.8 | Add `POST /api/backups/{id}/verify` endpoint | `routers/backups.py` |
| 5.9 | Add verification schedule settings UI | `views/SettingsView.vue` |
| 5.10 | Add "Verify Now" button per backup | `views/BackupsView.vue` |
| 5.11 | Display verification status/results | `views/BackupsView.vue` |
| 5.12 | Send notification on verification failure | `services/verification_service.py` |
| 5.13 | Implement scheduled verification (every N backups) | `tasks/scheduler.py` |

**Deliverable:** Verification system with UI and notifications

---

### Phase 6: Bare Metal Recovery (restore.sh)
*Self-contained restore for new servers*

| # | Task | Files to Modify/Create |
|---|------|------------------------|
| 6.1 | Create restore.sh template | `templates/restore.sh.template` |
| 6.2 | Implement Docker detection/installation in restore.sh | `templates/restore.sh.template` |
| 6.3 | Implement NFS reconfiguration prompt | `templates/restore.sh.template` |
| 6.4 | Implement database restore in restore.sh | `templates/restore.sh.template` |
| 6.5 | Implement config file restore | `templates/restore.sh.template` |
| 6.6 | Implement SSL certificate restore | `templates/restore.sh.template` |
| 6.7 | Add validation checks post-restore | `templates/restore.sh.template` |
| 6.8 | Generate requirements.txt at backup time | `services/backup_service.py` |
| 6.9 | Generate system_info.json at backup time | `services/backup_service.py` |
| 6.10 | Include restore.sh in every backup archive | `services/backup_service.py` |

**Deliverable:** Any backup can be extracted on new server and `./restore.sh` handles everything

---

### Phase 7: Backup Pruning & Retention System
*Automatic cleanup with pre-deletion notifications*

| # | Task | Files to Modify/Create |
|---|------|------------------------|
| 7.1 | Add pruning columns to backup_history (protected, deletion_status, scheduled_deletion_at) | `models/backups.py` |
| 7.2 | Create `backup_pruning_settings` table | `models/backups.py` |
| 7.3 | Create `pruning_service.py` | `services/pruning_service.py` |
| 7.4 | Implement time-based pruning (delete older than X days) | `services/pruning_service.py` |
| 7.5 | Implement space-based pruning (delete when below X% free) | `services/pruning_service.py` |
| 7.6 | Implement size-based pruning (keep under X GB total) | `services/pruning_service.py` |
| 7.7 | Implement pending deletion workflow (24h wait + notification) | `services/pruning_service.py` |
| 7.8 | Implement critical space handling (delete immediately OR stop + emergency notify) | `services/pruning_service.py` |
| 7.9 | Add protect/unprotect backup endpoints | `routers/backups.py` |
| 7.10 | Add pruning settings API endpoints | `routers/backups.py` |
| 7.11 | Add scheduler task for pruning checks (hourly) | `tasks/scheduler.py` |
| 7.12 | Add scheduler task for pending deletion execution | `tasks/scheduler.py` |
| 7.13 | Integrate with notification service | `services/pruning_service.py` |
| 7.14 | Add pruning settings UI | `views/SettingsView.vue` |
| 7.15 | Add protect/pending status to backup history UI | `views/BackupsView.vue` |
| 7.16 | Add cancel pending deletion button | `views/BackupsView.vue` |
| 7.17 | Add storage usage display | `views/BackupsView.vue` |

**Deliverable:** Automatic backup cleanup with notifications and protected backups

---

## Pruning & Retention Decisions

### 6. Manual vs Automatic Deletion
**Decision:** Different behavior based on deletion type

| Deletion Type | Behavior |
|---------------|----------|
| **Manual** (user clicks delete) | Confirmation dialog → Immediate delete (no notification) |
| **Automatic** (pruning rules) | If "Notify before deletion" enabled: wait configured hours, send notification, then delete |

### 7. Critical Space Handling
**Decision:** User-configurable emergency behavior

```
┌─────────────────────────────────────────────────────────────────┐
│ Critical Space Settings                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Critical space threshold: [5] %                                 │
│                                                                  │
│  When storage is critically low:                                 │
│  ○ Delete oldest backups as necessary to complete new backup    │
│  ○ Stop all backups and send emergency notification             │
│      └─► Emergency channel: [#alerts ▼] (required)              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8. Deletion Priority
**Decision:** Oldest first
- Older backups deleted before newer ones
- Larger backups are typically newer, so they're preserved
- Simple, predictable behavior

### 9. Protected Backups
**Decision:** Users can protect specific backups

| Feature | Description |
|---------|-------------|
| **Protect button** | Lock icon on each backup in history |
| **Protected status** | Shield badge shown on protected backups |
| **Automatic deletion** | Protected backups are NEVER auto-deleted |
| **Manual deletion** | Protected backups require unprotect first |
| **Use cases** | Known-good backup, milestone backup, pre-upgrade backup |

### Pruning Settings UI

```
┌─────────────────────────────────────────────────────────────────┐
│ Backup Retention & Pruning                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Automatic Pruning Rules:                                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ☑ Delete backups older than [90] days                      │ │
│  │ ☑ Delete oldest when free space below [10] %               │ │
│  │ ☑ Keep maximum total backup size of [100] GB               │ │
│  │ ☐ Keep only [7] daily, [4] weekly, [12] monthly            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Pre-Deletion Notifications:                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ☑ Notify before automatic deletion                         │ │
│  │   Hours before deletion: [24 ▼]                            │ │
│  │   Notification channel:  [#backup-alerts ▼] (required)     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Critical Space Handling:                                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Critical threshold: [5] % free space                       │ │
│  │                                                             │ │
│  │ When critically low:                                        │ │
│  │ ● Delete oldest (unprotected) to make room for new backup  │ │
│  │ ○ Stop backups & send emergency alert to [#alerts ▼]       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│                                              [Save Settings]    │
└─────────────────────────────────────────────────────────────────┘
```

### Backup History with Protection & Pending Status

```
┌─────────────────────────────────────────────────────────────────┐
│ Backup History                                    Storage: 45/100GB │
├─────────────────────────────────────────────────────────────────┤
│ ⚠️ 2 backups pending deletion (click to cancel)                  │
├─────────────────────────────────────────────────────────────────┤
│ │ Date         │ Size   │ Status      │ Protected │ Actions    │
│ ├──────────────┼────────┼─────────────┼───────────┼────────────│
│ │ 12/17 02:00  │ 52 MB  │ ✓ Verified  │ 🛡️        │ [👁][⬇][🔓]│
│ │ 12/16 02:00  │ 51 MB  │ ✓ Verified  │           │ [👁][⬇][🗑]│
│ │ 12/15 02:00  │ 50 MB  │ ⏳ Del 18h  │           │ [👁][⬇][❌]│
│ │ 09/15 02:00  │ 48 MB  │ ⏳ Del 18h  │           │ [👁][⬇][❌]│
│ │ 09/14 02:00  │ 47 MB  │ ✓ Verified  │ 🛡️        │ [👁][⬇][🔓]│
└─────────────────────────────────────────────────────────────────┘

Legend:
  🛡️ = Protected (click 🔓 to unprotect)
  ⏳ Del Xh = Pending deletion in X hours (click ❌ to cancel)
  [👁] = View contents  [⬇] = Download  [🗑] = Delete  [🔓] = Unprotect
```

---

## Progress Tracking

This section tracks implementation progress. Update after each completed task, change, or test.

### Current Status
- **Current Phase:** Not started
- **Last Updated:** December 17, 2024
- **Last Action:** Planning complete, awaiting Phase 1 start

### Phase 1: Enhanced Backup Creation & Archive Format
| Task | Status | Notes |
|------|--------|-------|
| 1.1 Create `backup_contents` database model | ⬜ Pending | |
| 1.2 Update backup service to capture workflow manifest | ⬜ Pending | |
| 1.3 Capture config file manifest with checksums | ⬜ Pending | |
| 1.4 Capture database schema manifest | ⬜ Pending | |
| 1.5 Create tar.gz archive with proper structure | ⬜ Pending | |
| 1.6 Include all config files | ⬜ Pending | |
| 1.7 Include SSL certificates in backup | ⬜ Pending | |
| 1.8 Generate manifest.json | ⬜ Pending | |
| 1.9 Generate requirements.txt | ⬜ Pending | |
| 1.10 Create restore.sh template | ⬜ Pending | |
| 1.11 Store metadata in backup_contents table | ⬜ Pending | |

### Phase 2: Backup Content Browser UI
| Task | Status | Notes |
|------|--------|-------|
| 2.1-2.8 | ⬜ Pending | Not started |

### Phase 3: Selective Workflow Restore
| Task | Status | Notes |
|------|--------|-------|
| 3.1-3.12 | ⬜ Pending | Not started |

### Phase 4: Full System Restore
| Task | Status | Notes |
|------|--------|-------|
| 4.1-4.11 | ⬜ Pending | Not started |

### Phase 5: Backup Verification System
| Task | Status | Notes |
|------|--------|-------|
| 5.1-5.13 | ⬜ Pending | Not started |

### Phase 6: Bare Metal Recovery
| Task | Status | Notes |
|------|--------|-------|
| 6.1-6.10 | ⬜ Pending | Not started |

### Phase 7: Pruning & Retention
| Task | Status | Notes |
|------|--------|-------|
| 7.1-7.17 | ⬜ Pending | Not started |

### Change Log
| Date | Change | Details |
|------|--------|---------|
| 2024-12-17 | Initial planning | Created complete 7-phase implementation plan |
| 2024-12-17 | Finalized decisions | All 10 key decisions documented |
| 2024-12-17 | Added Phase 7 | Pruning & retention system with notifications |

### Testing Notes
*(Record test results, issues found, and resolutions here)*

### Issues & Resolutions
*(Track any blockers or problems encountered)*

---

## Summary

| Phase | Focus | Key Deliverable |
|-------|-------|-----------------|
| 1 | Enhanced Backup Creation | Complete tar.gz archives with all files |
| 2 | Content Browser UI | Browse backups without loading |
| 3 | Selective Workflow Restore | Restore individual workflows |
| 4 | Full System Restore | Restore entire system from UI |
| 5 | Verification System | Prove backups are valid |
| 6 | Bare Metal Recovery | restore.sh for new servers |
| 7 | Pruning & Retention | Automatic cleanup with notifications |

---

*Document updated on December 17, 2024*
*Added Phase 7: Pruning & Retention System*
*Ready to begin Phase 1 implementation*
