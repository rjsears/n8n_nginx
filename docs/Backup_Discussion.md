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
- [Open Questions](#open-questions)

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

## Open Questions

### 1. Restore Container Strategy
Should we keep `n8n_postgres_restore` running constantly (faster restores) or spin up on-demand (saves resources)?

### 2. Config File Storage
Should we store config files:
- Inside the PostgreSQL backup (as a separate table with BYTEA)
- As separate files alongside the .dump file in a .tar.gz bundle
- Both (database for quick browsing, files for actual restore)

### 3. Workflow Rename Format
What naming convention for restored workflows?
- `{name}_restored_{timestamp}` (e.g., "My Workflow_restored_20241217_1430")
- `{name}_backup_{backup_date}` (e.g., "My Workflow_backup_20241215")
- User-specified during restore

### 4. Verification Frequency Default
What should be the default?
- Every backup (safest, most resource intensive)
- Every 5th backup
- Weekly regardless of backup count
- Manual only

### 5. Bare Metal Detection
In setup.sh, what file pattern should trigger restore offer?
- `*.n8n_backup.tar.gz`
- Any `.tar.gz` in the directory
- A specific `restore_me.tar.gz` filename

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

## Next Steps

1. User to review this document and answer open questions
2. Finalize phase priorities and any modifications
3. Begin implementation starting with Phase 1

---

*Document generated from implementation discussion on December 17, 2024*
