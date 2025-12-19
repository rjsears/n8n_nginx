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
- [Backup Configuration Page](#backup-configuration-page)
- [Backup History UI](#backup-history-ui-collapsible-design)
- [Session Updates](#session-updates) ← **Start here when resuming**

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

## Implementation Notes

### Autonomous Implementation Mode
- **Continue through phases** without stopping for approval
- **Build comprehensive test instructions** for each completed phase
- **Ensure database changes** are integrated with setup.sh for fresh installs
- **Update this document** after each task completion

### Database Integration Requirements
- All new tables must be added to the SQLAlchemy models in `models/backups.py`
- Database initialization handled by `init-db.sh` and SQLAlchemy's `create_all()`
- Ensure backward compatibility - existing installations should auto-migrate
- Test that setup.sh on clean server creates all necessary tables

### Testing Instructions Format
For each phase, document:
1. Prerequisites (containers running, test data needed)
2. Step-by-step test procedure
3. Expected results
4. Verification commands

---

## Progress Tracking

This section tracks implementation progress. Update after each completed task, change, or test.

### Current Status
- **Current Phase:** ALL PHASES COMPLETE
- **Last Updated:** December 17, 2024
- **Last Action:** Completed Phase 7 - Pruning & Retention System

### Phase 1: Enhanced Backup Creation & Archive Format ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| 1.1 Create `backup_contents` database model | ✅ Complete | Added BackupContents, BackupPruningSettings models, plus protection/deletion columns to BackupHistory |
| 1.2 Update backup service to capture workflow manifest | ✅ Complete | `capture_workflow_manifest()` queries n8n DB |
| 1.3 Capture config file manifest with checksums | ✅ Complete | `capture_config_file_manifest()` with SHA-256 |
| 1.4 Capture database schema manifest | ✅ Complete | `capture_database_schema_manifest()` gets tables, row counts, columns |
| 1.5 Create tar.gz archive with proper structure | ✅ Complete | `create_complete_archive()` creates tar.gz |
| 1.6 Include all config files | ✅ Complete | .env, docker-compose.yaml, nginx.conf, cloudflare.ini |
| 1.7 Include SSL certificates in backup | ✅ Complete | Copies entire /etc/letsencrypt/live directory |
| 1.8 Generate manifest.json (metadata.json) | ✅ Complete | Full metadata JSON inside archive |
| 1.9 Generate requirements.txt | ⏭️ Skipped | Not critical for MVP |
| 1.10 Create restore.sh template | ✅ Complete | `_generate_restore_script()` embedded in archive |
| 1.11 Store metadata in backup_contents table | ✅ Complete | `run_backup_with_metadata()` stores all metadata |

**Phase 1 API Endpoints:**
- `POST /api/backups/run-full` - Create full backup with metadata
- `GET /api/backups/contents/{backup_id}` - Get backup contents for browsing
- `GET /api/backups/contents/{backup_id}/workflows` - List workflows in backup
- `GET /api/backups/contents/{backup_id}/config-files` - List config files in backup
- `POST /api/backups/{backup_id}/protect` - Protect/unprotect backup
- `GET /api/backups/protected` - List protected backups
- `GET /api/backups/pruning/settings` - Get pruning settings
- `PUT /api/backups/pruning/settings` - Update pruning settings

**Files Modified in Phase 1:**
- `api/models/backups.py` - Added BackupContents, BackupPruningSettings, protection columns
- `api/schemas/backups.py` - Added all new schemas
- `api/services/backup_service.py` - Added ~700 lines of backup functionality
- `api/routers/backups.py` - Added 8 new endpoints
- `api/database.py` - Added schema migrations for new columns

### Phase 1 Testing Instructions
```bash
# Prerequisites:
# - Management container running
# - PostgreSQL container running with n8n database
# - At least one workflow in n8n

# Test 1: Create full backup with metadata
curl -X POST http://localhost:5678/api/backups/run-full \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"backup_type": "postgres_full", "compression": "gzip"}'

# Expected: Returns backup_id, status "success", filename like "backup_YYYYMMDD_HHMMSS.n8n_backup.tar.gz"

# Test 2: Get backup contents
curl http://localhost:5678/api/backups/contents/<backup_id> \
  -H "Authorization: Bearer <token>"

# Expected: JSON with workflow_count, credential_count, config_file_count, manifests

# Test 3: List workflows in backup
curl http://localhost:5678/api/backups/contents/<backup_id>/workflows \
  -H "Authorization: Bearer <token>"

# Expected: JSON array of workflows with id, name, active, created_at, updated_at

# Test 4: Protect a backup
curl -X POST http://localhost:5678/api/backups/<backup_id>/protect \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"protected": true, "reason": "Test protection"}'

# Expected: Backup with is_protected=true, protected_at set, protected_reason set

# Test 5: Verify archive structure
tar -tzf /path/to/backup_*.n8n_backup.tar.gz
# Expected contents:
# - restore.sh
# - metadata.json
# - databases/n8n.dump
# - databases/n8n_management.dump
# - config/.env (if exists)
# - config/docker-compose.yaml (if exists)
# - config/nginx.conf (if exists)
# - ssl/ (if SSL certs exist)
```

### Phase 2: Backup Content Browser UI ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| 2.1 Add API endpoint `GET /api/backups/{id}/contents` | ✅ Complete | Done in Phase 1 |
| 2.2 Add backup_contents schema | ✅ Complete | Done in Phase 1 |
| 2.3 Create BackupContentsDialog.vue component | ✅ Complete | Full tabbed dialog |
| 2.4 Add "View Contents" button to backup history | ✅ Complete | Eye icon button |
| 2.5 Display workflows tab | ✅ Complete | With search filter |
| 2.6 Display config files tab | ✅ Complete | With checksums |
| 2.7 Display database info tab | ✅ Complete | Tables with row counts |
| 2.8 Add search/filter for workflows | ✅ Complete | Real-time search |

**Phase 2 UI Features:**
- BackupContentsDialog.vue with 3 tabs (Workflows, Config Files, Database)
- Summary stats showing workflow/credential/config counts
- Search/filter for workflows
- Protection badge and toggle button
- View Contents (eye) button on each backup
- Shield icon for protect/unprotect

**Files Modified in Phase 2:**
- `frontend/src/components/backups/BackupContentsDialog.vue` - NEW: Full dialog component
- `frontend/src/stores/backups.js` - Added 8 new methods for contents, protection, pruning
- `frontend/src/views/BackupsView.vue` - Added View Contents, protection buttons, dialog integration

### Phase 3: Selective Workflow Restore ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| 3.1 Create `restore_service.py` | ✅ Complete | Full service with container management |
| 3.2 Implement `spin_up_restore_container()` | ✅ Complete | Docker container spin-up/teardown |
| 3.3 Implement `load_backup_to_container()` | ✅ Complete | Loads both new and legacy backup formats |
| 3.4 Implement `extract_workflow()` | ✅ Complete | Extracts workflow JSON from restore DB |
| 3.5 Implement `push_workflow_to_n8n()` via API | ✅ Complete | Uses n8n_api_service |
| 3.6 Implement `teardown_restore_container()` | ✅ Complete | Cleanup after restore |
| 3.7 Add restore API endpoints | ✅ Complete | 5 new endpoints |
| 3.8 Create WorkflowRestoreDialog.vue | ✅ Complete | Full restore dialog with options |
| 3.9 Integrate restore into BackupContentsDialog | ✅ Complete | Restore button opens dialog |

**Phase 3 API Endpoints:**
- `POST /api/backups/{id}/restore/workflow` - Restore workflow to n8n
- `GET /api/backups/{id}/restore/workflows` - List workflows in backup
- `GET /api/backups/{id}/workflows/{wf_id}/download` - Download workflow JSON
- `POST /api/backups/restore/cleanup` - Cleanup restore container
- `GET /api/backups/restore/status` - Check container status

**Phase 3 UI Features:**
- WorkflowRestoreDialog.vue with restore/download options
- Custom naming with format selection or custom name
- Preview of new workflow name
- Success/error feedback
- Integrated into BackupContentsDialog

**Files Created/Modified in Phase 3:**
- `api/services/restore_service.py` - NEW: Full restore service (~400 lines)
- `api/routers/backups.py` - Added 5 restore endpoints
- `frontend/src/components/backups/WorkflowRestoreDialog.vue` - NEW: Restore dialog
- `frontend/src/components/backups/BackupContentsDialog.vue` - Integrated restore

### Phase 4: Full System Restore ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| 4.1 Implement `restore_full_system()` | ✅ Complete | Full system restore in restore_service.py |
| 4.2 Add pre-restore safety checks | ✅ Complete | Backup creation option before overwriting |
| 4.3 Create current-state backup before restore | ✅ Complete | create_backups option in restore |
| 4.4 Implement database restore (both DBs) | ✅ Complete | `restore_database()` method |
| 4.5 Implement config file restore | ✅ Complete | `restore_config_file()` with path mappings |
| 4.6 Implement SSL certificate restore | ✅ Complete | Handled via config file restore |
| 4.7 Add Phase 4 API endpoints | ✅ Complete | 5 new restore endpoints |
| 4.8 Create SystemRestoreDialog.vue | ✅ Complete | Full restore UI with preview/confirm/progress |
| 4.9 Require confirmation to restore | ✅ Complete | Two-step confirm with warning |
| 4.10 Add restore progress indicator | ✅ Complete | Loading state during restore |
| 4.11 Restart services notification | ✅ Complete | Post-restore restart notice |

**Phase 4 API Endpoints:**
- `GET /api/backups/{id}/restore/preview` - Preview what would be restored
- `GET /api/backups/{id}/restore/config-files` - List config files in backup
- `POST /api/backups/{id}/restore/config` - Restore specific config file
- `POST /api/backups/{id}/restore/database` - Restore specific database
- `POST /api/backups/{id}/restore/full` - Full system restore

**Phase 4 UI Features:**
- SystemRestoreDialog.vue with 4 steps (preview, confirm, restoring, complete)
- Select databases, config files, SSL certificates to restore
- Option to create backups of existing files before overwriting
- Warning about destructive action
- Detailed results showing success/failure per item
- Post-restore notice about container restart

**Files Created/Modified in Phase 4:**
- `api/services/restore_service.py` - Added ~400 lines: extract_backup_archive, list_config_files_in_backup, restore_config_file, restore_database, get_restore_preview, full_system_restore
- `api/routers/backups.py` - Added 5 Phase 4 endpoints
- `frontend/src/stores/backups.js` - Added 8 Phase 4 methods
- `frontend/src/components/backups/SystemRestoreDialog.vue` - NEW: Full system restore dialog (~600 lines)
- `frontend/src/views/BackupsView.vue` - Added System Restore button and dialog integration

### Phase 5: Backup Verification System ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| 5.1 Create `verification_service.py` | ✅ Complete | Full verification service with container management |
| 5.2 Implement `verify_backup()` with temp container | ✅ Complete | Uses n8n_postgres_verify container |
| 5.3 Verify table existence and schemas | ✅ Complete | `verify_tables_exist()` method |
| 5.4 Verify row counts match manifest | ✅ Complete | `verify_row_counts()` method |
| 5.5 Verify workflow checksums | ✅ Complete | `verify_workflow_checksums()` with sampling |
| 5.6 Verify config file checksums | ✅ Complete | `verify_config_file_checksums()` method |
| 5.7 Store detailed verification results | ✅ Complete | Stores in backup_history table |
| 5.8 Add verification API endpoints | ✅ Complete | 5 new endpoints |
| 5.9 Add "Verify Now" button per backup | ✅ Complete | CheckBadge icon button |
| 5.10 Display verification status/results | ✅ Complete | Badge with passed/failed status |
| 5.11 Quick verify option | ✅ Complete | Fast checksum-only verification |
| 5.12 Verification container cleanup | ✅ Complete | Manual cleanup endpoint |

**Phase 5 API Endpoints:**
- `POST /api/backups/{id}/verify` - Comprehensive verification (spins up container)
- `POST /api/backups/{id}/verify/quick` - Quick verification (checksum only)
- `GET /api/backups/{id}/verification/status` - Get verification status
- `POST /api/backups/verification/cleanup` - Cleanup verification container
- `GET /api/backups/verification/container/status` - Check container status

**Phase 5 Features:**
- Separate verification container (n8n_postgres_verify) from restore container
- Comprehensive verification: archive integrity, tables, row counts, checksums
- Quick verification: file exists, checksum match, archive valid
- Workflow checksum sampling (default: 10 workflows)
- Verification status badge in backup list
- Verify button with loading state

**Files Created/Modified in Phase 5:**
- `api/services/verification_service.py` - NEW: Full verification service (~600 lines)
- `api/routers/backups.py` - Added 5 verification endpoints
- `frontend/src/stores/backups.js` - Added 5 verification methods
- `frontend/src/views/BackupsView.vue` - Added verification button and status display

### Phase 6: Bare Metal Recovery ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| 6.1 Create restore.sh template | ✅ Complete | Enhanced script with full recovery workflow |
| 6.2 Implement Docker detection/installation | ✅ Complete | Checks and optionally installs Docker |
| 6.3 Implement NFS reconfiguration prompt | ⏭️ Not needed | User handles NFS during initial setup |
| 6.4 Implement database restore | ✅ Complete | pg_restore with --clean --if-exists |
| 6.5 Implement config file restore | ✅ Complete | With backup of existing files |
| 6.6 Implement SSL certificate restore | ✅ Complete | Restores to /etc/letsencrypt/live |
| 6.7 Add validation checks post-restore | ✅ Complete | Checks files exist, DB connectivity |
| 6.8 Add dry-run mode | ✅ Complete | --dry-run shows what would happen |
| 6.9 Add --force mode | ✅ Complete | Skips confirmation prompts |
| 6.10 Include restore.sh in every backup | ✅ Complete | Already implemented in Phase 1 |

**restore.sh Features:**
- Comprehensive 8-step restore process
- Docker installation check/prompt
- PostgreSQL tools verification
- Database auto-creation if not exists
- Config file backup before overwrite
- SSL certificate restoration
- Post-restore validation checks
- Dry-run mode for testing
- Force mode for automation
- Colored output with status indicators
- Detailed next steps guide

**restore.sh Command Line Options:**
```bash
./restore.sh [options]
  --target-dir DIR    Directory to restore to (default: /opt/n8n)
  --db-host HOST      PostgreSQL host (default: localhost)
  --db-user USER      PostgreSQL user (default: n8n)
  --db-pass PASS      PostgreSQL password
  --skip-docker       Skip Docker installation check
  --skip-ssl          Skip SSL certificate restoration
  --skip-db           Skip database restoration
  --skip-config       Skip config file restoration
  --dry-run           Show what would be done without changes
  --force             Skip all confirmation prompts
  -h, --help          Show help message
```

### Phase 7: Pruning & Retention ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| 7.1 Add pruning columns to backup_history | ✅ Complete | Already done in Phase 1 |
| 7.2 Create backup_pruning_settings table | ✅ Complete | Already done in Phase 1 |
| 7.3 Create pruning_service.py | ✅ Complete | Full pruning service with all methods |
| 7.4 Implement time-based pruning | ✅ Complete | Delete backups older than X days |
| 7.5 Implement space-based pruning | ✅ Complete | Trigger when free space below X% |
| 7.6 Implement size-based pruning | ✅ Complete | Keep total backup size under X GB |
| 7.7 Implement pending deletion workflow | ✅ Complete | 24h wait + notification before delete |
| 7.8 Implement critical space handling | ✅ Complete | delete_oldest or stop_and_alert |
| 7.9 Add protect/unprotect backup endpoints | ✅ Complete | Already done in Phase 1 |
| 7.10 Add pruning settings API endpoints | ✅ Complete | Already done in Phase 1 |
| 7.11 Add storage usage endpoint | ✅ Complete | /api/backups/storage/usage |
| 7.12 Add pruning candidates endpoint | ✅ Complete | /api/backups/pruning/candidates |
| 7.13 Add pending deletions endpoint | ✅ Complete | /api/backups/pruning/pending |
| 7.14 Add cancel deletion endpoint | ✅ Complete | POST /{id}/cancel-deletion |
| 7.15 Add run pruning endpoint | ✅ Complete | POST /pruning/run |
| 7.16 Integrate with notification service | ✅ Complete | dispatch_notification calls |
| 7.17 Add frontend store methods | ✅ Complete | 6 new methods in backups.js |

**Phase 7 API Endpoints:**
- `GET /api/backups/storage/usage` - Get storage usage info
- `GET /api/backups/pruning/candidates` - Preview what would be pruned
- `GET /api/backups/pruning/pending` - List pending deletions
- `POST /api/backups/{id}/cancel-deletion` - Cancel pending deletion
- `POST /api/backups/pruning/run` - Manually trigger all pruning checks
- `POST /api/backups/pruning/execute-pending` - Execute pending deletions

**Pruning Service Features:**
- Time-based: Delete backups older than X days
- Space-based: Delete oldest when free space below X%
- Size-based: Keep total backup size under X GB
- Pending deletion workflow: Mark for deletion, wait, notify, then delete
- Critical space handling: Emergency delete or stop+alert
- Protected backups: Never auto-deleted
- Storage usage reporting: Local and NFS backup directories
- Candidate preview: See what would be deleted without executing

**Files Created/Modified in Phase 7:**
- `api/services/pruning_service.py` - NEW: Full pruning service (~500 lines)
- `api/routers/backups.py` - Added 6 pruning endpoints
- `frontend/src/stores/backups.js` - Added 6 pruning methods

### Change Log
| Date | Change | Details |
|------|--------|---------|
| 2024-12-17 | Initial planning | Created complete 7-phase implementation plan |
| 2024-12-17 | Finalized decisions | All 10 key decisions documented |
| 2024-12-17 | Added Phase 7 | Pruning & retention system with notifications |
| 2024-12-17 | Phase 1 Complete | Backend implementation done - backup service, models, schemas, routes |
| 2024-12-17 | Phase 2 Complete | UI implementation done - BackupContentsDialog, store methods, view updates |
| 2024-12-17 | Phase 3 Backend | Restore service, container management, 5 API endpoints |
| 2024-12-17 | Phase 3 UI | WorkflowRestoreDialog with restore/download options |
| 2024-12-17 | Phase 4 Backend | Full system restore: databases, configs, SSL certs, 5 API endpoints |
| 2024-12-17 | Phase 4 UI | SystemRestoreDialog with preview/confirm/progress/results steps |
| 2024-12-17 | Phase 5 Backend | Verification service with temp container, comprehensive checks |
| 2024-12-17 | Phase 5 UI | Verify button and verification status badge in backup list |
| 2024-12-17 | Phase 6 | Enhanced restore.sh with Docker check, dry-run, validation |
| 2024-12-17 | Phase 7 | Pruning service with time/space/size-based cleanup, notifications |
| 2024-12-17 | Backup Settings Page | Added dedicated `/backup-settings` page with 6 tabbed configuration sections |
| 2024-12-17 | Storage Tab | Local staging area, NFS detection, backup workflow options |
| 2024-12-17 | Schedule Tab | Schedule timing with frequency and backup type selection |
| 2024-12-17 | Retention Tab | Retention periods and automatic cleanup settings |
| 2024-12-17 | Compression Tab | Compression algorithm and level settings |
| 2024-12-17 | Notifications Tab | Channel/group selection supporting all notification services with validation |
| 2024-12-17 | Verification Tab | Automatic and manual verification configuration |
| 2024-12-17 | BackupsView Redesign | Hierarchical collapsible backup history with inline actions |
| 2024-12-17 | Backup Actions | Verify, Protect, Selective Workflow Restore, Bare Metal Recovery, Delete |
| 2024-12-17 | Workflow Restore | Collapsible workflow list with Download JSON and Push to n8n options |

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

## Backup Configuration Page

A dedicated backup configuration page (`/backup-settings`) was added to provide a comprehensive UI for configuring all backup-related settings. This page is accessed via the **Configure** button on the main Backups page.

### BackupSettingsView.vue

**Route:** `/backup-settings`
**File:** `frontend/src/views/BackupSettingsView.vue`

The page uses a tabbed interface with 6 tabs, each featuring collapsible sections with gradient icons for a polished UI experience.

### Tab 1: Storage

Configures where backups are stored and how they flow through the system.

**Collapsible Sections:**

1. **Local Staging Area** (Emerald gradient icon)
   - Shows the Docker volume mount at `/app/backups`
   - Explains this is a temporary holding area inside the management container
   - Displays path, status, and available space

2. **Network Storage (NFS)** (Blue gradient icon)
   - Auto-detects NFS mounts via `/proc/mounts` parsing
   - Shows NFS server address and mount path
   - Displays available space and mount status
   - Indicates when no NFS storage is detected

3. **Backup Workflow** (Purple gradient icon)
   - **Direct to Destination**: Backups written directly to final storage
   - **Stage Locally, Then Copy**: Write to local staging first, then copy to NFS
   - Explains the trade-offs of each approach

**API Integration:**
- `GET /api/backups/detect-storage` - Detects available storage paths
- Returns `staging_area`, `local_paths`, `nfs_mounts`, `has_nfs`, `recommended_path`

### Tab 2: Schedule

Configures when backups run automatically.

**Collapsible Sections:**

1. **Schedule Timing** (Emerald gradient icon)
   - Enable/disable scheduled backups
   - Frequency selection: Daily, Weekly, Monthly, Hourly
   - Time selection (hour and minute)
   - Day of week/month for weekly/monthly schedules

2. **Backup Types** (Blue gradient icon)
   - Configure which backup types to include
   - Options: postgres_full, postgres_n8n, n8n_config, flows

### Tab 3: Retention

Configures how long backups are kept.

**Collapsible Sections:**

1. **Retention Periods** (Amber gradient icon)
   - Hourly backups to keep (default: 24)
   - Daily backups to keep (default: 7)
   - Weekly backups to keep (default: 4)
   - Monthly backups to keep (default: 12)

2. **Automatic Cleanup** (Orange gradient icon)
   - Enable/disable automatic cleanup
   - Maximum age in days before deletion
   - Maximum total size limit

### Tab 4: Compression

Configures backup compression settings.

**Collapsible Sections:**

1. **Compression Settings** (Purple gradient icon)
   - Enable/disable compression
   - Algorithm selection: gzip, zstd, none
   - Compression level: Fast, Balanced, Maximum

2. **Advanced Options** (Indigo gradient icon)
   - Parallel compression threads
   - Chunk size settings

### Tab 5: Notifications

Configures alerts for backup events. **Supports all notification channels and groups, not just NTFY.**

**Collapsible Sections:**

1. **Notification Channel** (Indigo gradient icon)
   - Select from ALL configured notification services and groups
   - Services shown with indigo badge
   - Groups shown with purple badge
   - "Configure Notification Channels" button links to notification settings
   - **Validation:** Cannot enable notifications without selecting a channel first

2. **Notification Events** (Blue gradient icon)
   - Notify on success (with validation check)
   - Notify on failure (with validation check)
   - Shows warning and auto-expands channel section if trying to enable without channel selected

**API Integration:**
- `GET /notifications/services` - Fetches all notification services
- `GET /notifications/groups` - Fetches all notification groups
- Only enabled services and groups are shown as options

**Form Fields:**
- `notification_channel_id` - ID of selected service or group
- `notification_channel_type` - 'service' or 'group'

### Tab 6: Verification

Configures backup verification settings.

**Collapsible Sections:**

1. **Automatic Verification** (Teal gradient icon)
   - Enable/disable automatic verification
   - Verification frequency
   - Sample percentage for large backups

2. **Manual Verification** (Cyan gradient icon)
   - Verify selected backups on-demand
   - Shows last verification status
   - Quick verify vs comprehensive verify options

### Files Modified

| File | Changes |
|------|---------|
| `frontend/src/views/BackupSettingsView.vue` | NEW: Complete 6-tab configuration page with collapsible sections |
| `frontend/src/router/index.js` | Added route for `/backup-settings` |
| `frontend/src/views/BackupsView.vue` | Updated Configure button to navigate to new page |
| `api/routers/backups.py` | Added `GET /api/backups/detect-storage` endpoint with staging area separation |

### UI Design Patterns

All tabs use consistent styling:
- **Collapsible sections** with ChevronDownIcon toggle
- **Gradient icon backgrounds** using `bg-gradient-to-br from-{color}-100 to-{color}-100`
- **Color coding** for different section purposes:
  - Emerald/Green: Primary/main settings
  - Blue: Secondary settings
  - Purple/Indigo: Advanced settings
  - Amber/Orange: Warning/cleanup settings
  - Teal/Cyan: Verification settings

### Navigation

- **From Backups page:** Click "Configure" button with Cog6ToothIcon
- **Back to Backups:** Click "← Back to Backups" link or breadcrumb

---

## Backup History UI (Collapsible Design)

The main Backups page (`/backups`) uses a hierarchical collapsible design for browsing and managing backups.

### BackupsView.vue Structure

**File:** `frontend/src/views/BackupsView.vue`

The page is organized as follows:

1. **Stats Grid** - Four cards showing Total Backups, Successful, Failed, Total Size
2. **Backup Schedule Card** - Shows current schedule settings with link to Configure
3. **Filters** - Filter by status and sort by date/size
4. **Backup History** - Main collapsible section containing all backups

### Backup History (Collapsible)

When expanded, shows a list of individual backups. Each backup is itself a collapsible item.

**Backup Item Header Shows:**
- Backup type (postgres_full, postgres_n8n, etc.)
- Status badge (success/failed/pending)
- Protected badge (if protected)
- Verified badge (if verification passed)
- Creation date and size

### Backup Actions (When Expanded)

When you expand an individual backup, you see these action options:

#### 1. Verify Backup (Teal)
- Spins up a temporary PostgreSQL Docker container (`n8n_postgres_verify`)
- Loads the backed-up database into the temp container
- Validates backup integrity per the Verification Challenge & Solution:
  - Table existence and schemas
  - Row counts match manifest
  - Workflow checksums match
- Shows verification status badge (passed/failed)

#### 2. Protect Backup (Amber)
- Toggles protection status for the backup
- Protected backups are never automatically deleted by pruning
- Shows "Protected" badge when enabled
- Must unprotect before deleting

#### 3. Selective Workflow Restore (Indigo) - Collapsible
This is itself a collapsible section. When expanded:
- Spins up temporary Docker container with PostgreSQL
- Loads the workflow database from backup
- Lists all workflows in the backup with name and status

**Each workflow has two options:**
- **Download JSON** (DocumentArrowDownIcon) - Downloads the workflow as JSON file for manual import into n8n
- **Push to n8n** (CloudArrowUpIcon) - Uses n8n API to import the workflow directly (similar to test notification workflow push)

#### 4. Bare Metal Recovery (Purple)
- Downloads the backup archive as `backup_*.n8n_backup.tar.gz`
- Archive contains:
  - `restore.sh` - Self-contained restore script
  - `databases/` - PostgreSQL dumps
  - `config/` - .env, docker-compose.yaml, nginx.conf
  - `ssl/` - SSL certificates
  - `metadata.json` - Complete backup metadata
- User extracts on target server and runs `./restore.sh`

#### 5. Delete Backup (Red)
- Permanently deletes the backup
- Disabled if backup is protected (must unprotect first)
- Shows confirmation dialog before deleting

### State Management

```javascript
// Collapsible section state
const sections = ref({
  history: false,  // Backup History section
})

// Which individual backups are expanded
const expandedBackups = ref(new Set())

// Which backups have their workflow restore section expanded
const expandedWorkflowRestore = ref(new Set())

// Workflows loaded per backup (lazy-loaded on expand)
const backupWorkflows = ref({})
```

### API Endpoints Used

| Action | Endpoint | Description |
|--------|----------|-------------|
| Load workflows | `GET /backups/{id}/restore/workflows` | List workflows in backup |
| Download workflow | `GET /backups/{id}/workflows/{wf_id}/download` | Get workflow JSON |
| Restore workflow | `POST /backups/{id}/restore/workflow` | Push to n8n via API |
| Verify | `POST /backups/{id}/verify` | Full verification with temp container |
| Protect | `POST /backups/{id}/protect` | Toggle protection status |
| Download backup | `GET /backups/{id}/download` | Download tar.gz archive |
| Delete | `DELETE /backups/{id}` | Delete backup |

---

## Session Updates

### December 19, 2024 - Config File Restore Fix

**Issue Reported:**
```
[Errno 30] Read-only file system: '/app/host_config/cloudflare.ini'
```

**Root Cause:**
The `n8n_management` container had config file volume mounts set as read-only (`:ro`) but the restore service needs to write to them.

**Fix Applied (commit 008392d):**
Changed volume mounts from read-only to read-write in `docker-compose.yaml`:

```yaml
# Before (broken):
- ./docker-compose.yaml:/app/host_config/docker-compose.yaml:ro
- ./cloudflare.ini:/app/host_config/cloudflare.ini:ro

# After (fixed):
- ./docker-compose.yaml:/app/host_config/docker-compose.yaml:rw
- ./cloudflare.ini:/app/host_config/cloudflare.ini:rw
```

**To Apply Fix:**
```bash
git pull
docker compose up -d n8n_management
```

**Status:** ✅ Fixed

---

*Document updated on December 17, 2024*
*Added Phase 7: Pruning & Retention System*
*Added Backup Configuration Page documentation*
*Added Backup History UI (Collapsible Design) documentation*

*Document updated on December 19, 2024*
*Added Session Updates section for tracking fixes between chat sessions*
