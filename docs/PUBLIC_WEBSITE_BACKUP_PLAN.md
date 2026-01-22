# Public Website Backup & Restore Plan

## Executive Summary

This document outlines the changes required to fully integrate public website files into the backup and restore system. The implementation ensures public website files can be:
- Included in backups automatically
- Viewed in "View Backup Contents"
- Selectively restored (individual files or all files)
- Downloaded for inspection

**Key Requirement:** All functionality is conditional - only active when public website feature is installed.

---

## Current State

### What's Already Implemented

| Component | Status | Location |
|-----------|--------|----------|
| `include_public_website` config flag | ✅ Done | `models/backups.py:346` |
| `_is_public_website_installed()` detection | ✅ Done | `backup_service.py:1244` |
| `_backup_public_website_volume()` backup | ✅ Done | `backup_service.py:1248` |
| Metadata tracking in backup | ✅ Done | `backup_service.py:1143-1144` |
| Restore script with `--skip-public-website` | ✅ Done | `backup_service.py:2309` |

### What's Missing

| Component | Status | Required For |
|-----------|--------|--------------|
| `public_website_file_count` in BackupContents | ❌ Missing | View Backup Contents |
| `public_website_manifest` in BackupContents | ❌ Missing | View Backup Contents |
| `capture_public_website_manifest()` function | ❌ Missing | Backup creation |
| Public website file listing endpoint | ❌ Missing | Selective Restore UI |
| Public website file download endpoint | ❌ Missing | File inspection |
| Public website selective restore endpoint | ❌ Missing | Selective Restore |
| Frontend: Public Website tab in contents view | ❌ Missing | User interface |
| Frontend: File browser for public website | ❌ Missing | User interface |

---

## Architecture Overview

### Backup Flow (Enhanced)

```
┌─────────────────────────────────────────────────────────────────┐
│                    run_backup_with_metadata()                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Backup databases (postgres_full/n8n/mgmt)                    │
│ 2. Backup config files (.env, docker-compose.yaml, etc.)        │
│ 3. Backup SSL certificates (/etc/letsencrypt)                   │
│ 4. Backup public website volume (if installed & enabled)  ◄─NEW │
│ 5. Capture manifests:                                           │
│    - Workflow manifest                                          │
│    - Credential manifest                                        │
│    - Config file manifest                                       │
│    - Database schema manifest                                   │
│    - Public website manifest (if installed)              ◄─NEW  │
│ 6. Create archive with metadata.json                            │
│ 7. Store BackupContents record with all manifests               │
└─────────────────────────────────────────────────────────────────┘
```

### Backup Archive Structure (Enhanced)

```
backup_20260122_120000.tar.gz/
├── databases/
│   ├── n8n.dump
│   └── n8n_management.dump
├── config/
│   ├── .env
│   ├── docker-compose.yaml
│   ├── nginx.conf
│   ├── nginx-public.conf          # If public website enabled
│   ├── nginx-router.conf          # If public website enabled
│   ├── filebrowser.db
│   └── ...
├── ssl/
│   └── domain.com/
│       ├── cert.pem
│       ├── fullchain.pem
│       └── privkey.pem
├── public_website/                 # NEW: Only if public website installed
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── app.js
│   ├── images/
│   │   └── logo.png
│   └── ...
├── metadata.json
└── restore.sh
```

### View Backup Contents Flow

```
┌──────────────────┐     GET /backups/{id}/contents     ┌──────────────────┐
│                  │ ─────────────────────────────────► │                  │
│     Frontend     │                                    │    Backend API   │
│  (BackupView)    │ ◄───────────────────────────────── │                  │
│                  │     BackupContentsResponse         │                  │
└──────────────────┘     (includes public_website)      └──────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Tabs: [Workflows] [Credentials] [Config Files] [Database] [Public Web] │
│                                                              ▲           │
│                                                              │           │
│                                                         NEW TAB          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Selective Restore Flow

```
┌──────────────────┐                                    ┌──────────────────┐
│                  │  POST /backups/{id}/mount          │                  │
│     Frontend     │ ─────────────────────────────────► │   RestoreService │
│                  │                                    │                  │
│                  │  GET /backups/{id}/restore/        │                  │
│                  │      public-website-files          │                  │
│                  │ ─────────────────────────────────► │  (lists files    │
│                  │ ◄───────────────────────────────── │   from mounted   │
│                  │     [{path, size, modified}, ...]  │   backup)        │
│                  │                                    │                  │
│  User selects    │  POST /backups/{id}/restore/       │                  │
│  files to        │       public-website               │                  │
│  restore         │ ─────────────────────────────────► │  (restores to    │
│                  │ ◄───────────────────────────────── │   volume)        │
│                  │     {restored: [...], errors: []}  │                  │
└──────────────────┘                                    └──────────────────┘
```

---

## Implementation Details

### 1. Database Model Changes

**File:** `management/api/models/backups.py`

```python
class BackupContents(Base):
    """
    Stores metadata for each backup for browsing without loading.
    """
    __tablename__ = "backup_contents"

    id = Column(Integer, primary_key=True)
    backup_id = Column(Integer, ForeignKey("backup_history.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Existing counts
    workflow_count = Column(Integer, default=0)
    credential_count = Column(Integer, default=0)
    config_file_count = Column(Integer, default=0)

    # NEW: Public website count
    public_website_file_count = Column(Integer, default=0)

    # Existing manifests
    workflows_manifest = Column(JSONB, nullable=True)
    credentials_manifest = Column(JSONB, nullable=True)
    config_files_manifest = Column(JSONB, nullable=True)
    database_schema_manifest = Column(JSONB, nullable=True)

    # NEW: Public website manifest
    # Format: [{path: "index.html", size: 1234, modified_at: "...", checksum: "..."}, ...]
    public_website_manifest = Column(JSONB, nullable=True)

    verification_checksums = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # ... rest unchanged
```

**Migration Required:** Yes - Alembic migration to add new columns.

---

### 2. Backup Service Changes

**File:** `management/api/services/backup_service.py`

#### 2.1 New Function: `capture_public_website_manifest()`

```python
async def capture_public_website_manifest(self, temp_dir: str) -> Tuple[int, List[Dict]]:
    """
    Capture manifest of public website files from the backup.
    Only called if public website is installed and was included in backup.

    Returns:
        Tuple of (file_count, manifest_list)
        manifest_list: [{path, size, modified_at, checksum}, ...]
    """
    public_website_dir = os.path.join(temp_dir, "public_website")

    if not os.path.exists(public_website_dir):
        logger.info("No public website directory in backup")
        return 0, []

    manifest = []
    file_count = 0

    for root, dirs, files in os.walk(public_website_dir):
        for filename in files:
            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, public_website_dir)

            try:
                stat = os.stat(file_path)

                # Calculate checksum for smaller files (< 10MB)
                checksum = None
                if stat.st_size < 10 * 1024 * 1024:
                    import hashlib
                    with open(file_path, 'rb') as f:
                        checksum = hashlib.md5(f.read()).hexdigest()

                manifest.append({
                    "path": relative_path,
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                    "checksum": checksum,
                    "is_directory": False
                })
                file_count += 1

            except Exception as e:
                logger.warning(f"Error capturing manifest for {relative_path}: {e}")

    # Sort by path for consistent ordering
    manifest.sort(key=lambda x: x["path"])

    logger.info(f"Captured public website manifest: {file_count} files")
    return file_count, manifest
```

#### 2.2 Update `run_backup_with_metadata()`

Add call to capture public website manifest after backing up files:

```python
# After backing up public website volume (around line 1144)
public_website_manifest = []
public_website_file_count_manifest = 0

if public_website_included:
    await update_progress(56, "Capturing public website manifest")
    public_website_file_count_manifest, public_website_manifest = await self.capture_public_website_manifest(temp_dir)
```

#### 2.3 Update BackupContents Creation

Update the code that creates the BackupContents record to include public website data:

```python
# When creating BackupContents record
backup_contents = BackupContents(
    backup_id=backup_history.id,
    workflow_count=workflow_count,
    credential_count=credential_count,
    config_file_count=len(config_files_manifest),
    public_website_file_count=public_website_file_count_manifest,  # NEW
    workflows_manifest=workflows_manifest,
    credentials_manifest=credentials_manifest,
    config_files_manifest=config_files_manifest,
    database_schema_manifest=database_schema_manifest,
    public_website_manifest=public_website_manifest,  # NEW
    verification_checksums=verification_checksums
)
```

---

### 3. Restore Service Changes

**File:** `management/api/services/restore_service.py`

#### 3.1 New Function: `list_public_website_files()`

```python
async def list_public_website_files(self, backup_id: int) -> List[Dict]:
    """
    List public website files from a mounted backup.

    Returns list of files with path, size, modified_at.
    Requires backup to be mounted first.
    """
    if not self._is_backup_mounted(backup_id):
        raise ValueError(f"Backup {backup_id} is not mounted. Mount it first.")

    public_website_dir = os.path.join(self.mount_dir, "public_website")

    if not os.path.exists(public_website_dir):
        return []

    files = []
    for root, dirs, filenames in os.walk(public_website_dir):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, public_website_dir)
            stat = os.stat(file_path)

            files.append({
                "path": relative_path,
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
            })

    return sorted(files, key=lambda x: x["path"])
```

#### 3.2 New Function: `download_public_website_file()`

```python
async def download_public_website_file(self, backup_id: int, file_path: str) -> Tuple[bytes, str]:
    """
    Download a specific public website file from mounted backup.

    Args:
        backup_id: The backup ID (must be mounted)
        file_path: Relative path within public_website directory

    Returns:
        Tuple of (file_content, filename)
    """
    if not self._is_backup_mounted(backup_id):
        raise ValueError(f"Backup {backup_id} is not mounted. Mount it first.")

    # Security: Prevent path traversal
    safe_path = os.path.normpath(file_path)
    if safe_path.startswith('..') or safe_path.startswith('/'):
        raise ValueError("Invalid file path")

    full_path = os.path.join(self.mount_dir, "public_website", safe_path)

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not os.path.isfile(full_path):
        raise ValueError(f"Not a file: {file_path}")

    with open(full_path, 'rb') as f:
        content = f.read()

    return content, os.path.basename(file_path)
```

#### 3.3 New Function: `restore_public_website_files()`

```python
async def restore_public_website_files(
    self,
    backup_id: int,
    file_paths: Optional[List[str]] = None,
    overwrite: bool = False
) -> Dict:
    """
    Restore public website files from mounted backup to the public_web_root volume.

    Args:
        backup_id: The backup ID (must be mounted)
        file_paths: Optional list of specific files to restore. If None, restore all.
        overwrite: Whether to overwrite existing files

    Returns:
        Dict with restored files list and any errors
    """
    if not self._is_backup_mounted(backup_id):
        raise ValueError(f"Backup {backup_id} is not mounted. Mount it first.")

    source_dir = os.path.join(self.mount_dir, "public_website")

    if not os.path.exists(source_dir):
        raise ValueError("No public website files in this backup")

    restored = []
    errors = []

    # Get list of files to restore
    if file_paths is None:
        # Restore all files
        files_to_restore = []
        for root, dirs, filenames in os.walk(source_dir):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, source_dir)
                files_to_restore.append(relative_path)
    else:
        files_to_restore = file_paths

    # Use docker to copy files to the public_web_root volume
    for file_path in files_to_restore:
        try:
            # Security check
            safe_path = os.path.normpath(file_path)
            if safe_path.startswith('..') or safe_path.startswith('/'):
                errors.append({"path": file_path, "error": "Invalid path"})
                continue

            source_file = os.path.join(source_dir, safe_path)

            if not os.path.exists(source_file):
                errors.append({"path": file_path, "error": "File not found in backup"})
                continue

            # Create temp container to copy file to volume
            dest_dir = os.path.dirname(safe_path)

            # Ensure destination directory exists in volume
            if dest_dir:
                subprocess.run([
                    "docker", "run", "--rm",
                    "-v", "public_web_root:/dest",
                    "alpine",
                    "mkdir", "-p", f"/dest/{dest_dir}"
                ], check=True, capture_output=True)

            # Copy file to volume
            subprocess.run([
                "docker", "run", "--rm",
                "-v", f"{source_dir}:/source:ro",
                "-v", "public_web_root:/dest",
                "alpine",
                "cp", f"/source/{safe_path}", f"/dest/{safe_path}"
            ], check=True, capture_output=True)

            restored.append(file_path)

        except Exception as e:
            errors.append({"path": file_path, "error": str(e)})

    return {
        "restored": restored,
        "restored_count": len(restored),
        "errors": errors,
        "error_count": len(errors)
    }
```

---

### 4. API Router Changes

**File:** `management/api/routers/backups.py`

#### 4.1 New Endpoint: List Public Website Files

```python
@router.get("/backups/{backup_id}/restore/public-website-files")
async def list_public_website_files(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List public website files available for restore from a mounted backup.

    Requires:
    - Public website feature to be installed
    - Backup to be mounted
    """
    # Check if public website is installed
    if not backup_service._is_public_website_installed():
        raise HTTPException(
            status_code=400,
            detail="Public website feature is not installed"
        )

    try:
        files = await restore_service.list_public_website_files(backup_id)
        return {
            "backup_id": backup_id,
            "file_count": len(files),
            "files": files
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

#### 4.2 New Endpoint: Download Public Website File

```python
@router.get("/backups/{backup_id}/public-website/{file_path:path}/download")
async def download_public_website_file(
    backup_id: int,
    file_path: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Download a specific public website file from a mounted backup.

    Requires:
    - Public website feature to be installed
    - Backup to be mounted
    """
    if not backup_service._is_public_website_installed():
        raise HTTPException(
            status_code=400,
            detail="Public website feature is not installed"
        )

    try:
        content, filename = await restore_service.download_public_website_file(backup_id, file_path)

        # Determine content type
        import mimetypes
        content_type, _ = mimetypes.guess_type(filename)
        if content_type is None:
            content_type = "application/octet-stream"

        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

#### 4.3 New Endpoint: Restore Public Website Files

```python
class PublicWebsiteRestoreRequest(BaseModel):
    file_paths: Optional[List[str]] = None  # None = restore all
    overwrite: bool = False

@router.post("/backups/{backup_id}/restore/public-website")
async def restore_public_website_files(
    backup_id: int,
    request: PublicWebsiteRestoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Restore public website files from a mounted backup.

    If file_paths is empty/null, restores ALL public website files.

    Requires:
    - Public website feature to be installed
    - Backup to be mounted
    """
    if not backup_service._is_public_website_installed():
        raise HTTPException(
            status_code=400,
            detail="Public website feature is not installed"
        )

    try:
        result = await restore_service.restore_public_website_files(
            backup_id,
            file_paths=request.file_paths,
            overwrite=request.overwrite
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

#### 4.4 Update BackupContentsResponse Schema

```python
class BackupContentsResponse(BaseModel):
    backup_id: int
    workflow_count: int
    credential_count: int
    config_file_count: int
    public_website_file_count: int = 0  # NEW

    # Include flag for conditional UI rendering
    public_website_available: bool = False  # NEW

    workflows_manifest: Optional[List[Dict]] = None
    credentials_manifest: Optional[List[Dict]] = None
    config_files_manifest: Optional[List[Dict]] = None
    database_schema_manifest: Optional[List[Dict]] = None
    public_website_manifest: Optional[List[Dict]] = None  # NEW
```

---

### 5. Frontend Changes

**File:** `management/frontend/src/views/BackupContentsView.vue` (or similar)

#### 5.1 Add Public Website Tab

```vue
<template>
  <div class="backup-contents">
    <Tabs>
      <Tab name="Workflows" :count="contents.workflow_count">
        <!-- existing -->
      </Tab>
      <Tab name="Credentials" :count="contents.credential_count">
        <!-- existing -->
      </Tab>
      <Tab name="Config Files" :count="contents.config_file_count">
        <!-- existing -->
      </Tab>
      <Tab name="Database">
        <!-- existing -->
      </Tab>

      <!-- NEW: Public Website Tab - only show if available -->
      <Tab
        v-if="contents.public_website_available"
        name="Public Website"
        :count="contents.public_website_file_count"
      >
        <PublicWebsiteFiles
          :backup-id="backupId"
          :manifest="contents.public_website_manifest"
        />
      </Tab>
    </Tabs>
  </div>
</template>
```

#### 5.2 New Component: PublicWebsiteFiles.vue

```vue
<template>
  <div class="public-website-files">
    <div class="header">
      <h3>Public Website Files</h3>
      <div class="actions">
        <button @click="restoreAll" :disabled="!isMounted">
          Restore All Files
        </button>
        <button @click="restoreSelected" :disabled="!selectedFiles.length || !isMounted">
          Restore Selected ({{ selectedFiles.length }})
        </button>
      </div>
    </div>

    <div v-if="!isMounted" class="mount-notice">
      <p>Mount the backup to enable restore functionality.</p>
      <button @click="mountBackup">Mount Backup</button>
    </div>

    <table class="file-table">
      <thead>
        <tr>
          <th><input type="checkbox" v-model="selectAll" /></th>
          <th>File Path</th>
          <th>Size</th>
          <th>Modified</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="file in manifest" :key="file.path">
          <td><input type="checkbox" v-model="selectedFiles" :value="file.path" /></td>
          <td>{{ file.path }}</td>
          <td>{{ formatSize(file.size) }}</td>
          <td>{{ formatDate(file.modified_at) }}</td>
          <td>
            <button @click="downloadFile(file.path)" :disabled="!isMounted">
              Download
            </button>
            <button @click="restoreFile(file.path)" :disabled="!isMounted">
              Restore
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
export default {
  props: {
    backupId: Number,
    manifest: Array
  },

  data() {
    return {
      selectedFiles: [],
      isMounted: false
    }
  },

  methods: {
    async downloadFile(path) {
      const response = await fetch(
        `/api/backups/${this.backupId}/public-website/${encodeURIComponent(path)}/download`
      );
      // Handle download...
    },

    async restoreFile(path) {
      await fetch(`/api/backups/${this.backupId}/restore/public-website`, {
        method: 'POST',
        body: JSON.stringify({ file_paths: [path] })
      });
      // Handle response...
    },

    async restoreSelected() {
      await fetch(`/api/backups/${this.backupId}/restore/public-website`, {
        method: 'POST',
        body: JSON.stringify({ file_paths: this.selectedFiles })
      });
    },

    async restoreAll() {
      await fetch(`/api/backups/${this.backupId}/restore/public-website`, {
        method: 'POST',
        body: JSON.stringify({ file_paths: null })  // null = all files
      });
    }
  }
}
</script>
```

---

### 6. Conditional Checks

All public website functionality must be conditional. The checks should be:

#### 6.1 Backend Check Function

```python
# In backup_service.py - already exists
def _is_public_website_installed(self) -> bool:
    """Check if public website feature is installed by looking for filebrowser.db."""
    return os.path.exists(PUBLIC_WEBSITE_INDICATOR)
```

#### 6.2 API Response Flag

Include in all relevant responses:
```python
"public_website_available": backup_service._is_public_website_installed()
```

#### 6.3 Frontend Conditional Rendering

```vue
<!-- Only show tab if public website is available AND has files -->
<Tab
  v-if="contents.public_website_available && contents.public_website_file_count > 0"
  name="Public Website"
>
```

---

## Database Migration

### Alembic Migration Script

```python
"""Add public website fields to backup_contents

Revision ID: xxxx
Revises: previous_revision
Create Date: 2026-01-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

def upgrade():
    op.add_column('backup_contents',
        sa.Column('public_website_file_count', sa.Integer(), default=0, nullable=True)
    )
    op.add_column('backup_contents',
        sa.Column('public_website_manifest', JSONB(), nullable=True)
    )

def downgrade():
    op.drop_column('backup_contents', 'public_website_manifest')
    op.drop_column('backup_contents', 'public_website_file_count')
```

---

## Testing Plan

### 1. Unit Tests

- [ ] `capture_public_website_manifest()` correctly captures files
- [ ] `list_public_website_files()` returns correct file list
- [ ] `download_public_website_file()` returns file content
- [ ] `restore_public_website_files()` restores files correctly
- [ ] Path traversal attacks are blocked

### 2. Integration Tests

- [ ] Backup with public website enabled includes files
- [ ] Backup without public website has empty manifest
- [ ] View Backup Contents shows public website tab when available
- [ ] Selective restore works for individual files
- [ ] Restore all works correctly
- [ ] Download file works for all file types

### 3. Conditional Behavior Tests

- [ ] API returns 400 if public website not installed
- [ ] Frontend hides tab if public website not installed
- [ ] Manifest is empty for backups before public website was enabled

---

## Implementation Order

### Phase 1: Database & Model
1. Create Alembic migration
2. Update BackupContents model
3. Update Pydantic schemas

### Phase 2: Backup Service
4. Add `capture_public_website_manifest()`
5. Update `run_backup_with_metadata()` to call new function
6. Update BackupContents creation

### Phase 3: Restore Service
7. Add `list_public_website_files()`
8. Add `download_public_website_file()`
9. Add `restore_public_website_files()`

### Phase 4: API Endpoints
10. Add list files endpoint
11. Add download file endpoint
12. Add restore files endpoint
13. Update BackupContentsResponse schema

### Phase 5: Frontend
14. Add Public Website tab to backup contents view
15. Create PublicWebsiteFiles component
16. Add conditional rendering logic

### Phase 6: Testing
17. Write unit tests
18. Write integration tests
19. Manual testing

---

## Files to Modify

| File | Changes |
|------|---------|
| `management/api/models/backups.py` | Add `public_website_file_count`, `public_website_manifest` columns |
| `management/api/schemas/backups.py` | Update response schemas |
| `management/api/services/backup_service.py` | Add manifest capture, update backup flow |
| `management/api/services/restore_service.py` | Add list, download, restore functions |
| `management/api/routers/backups.py` | Add 3 new endpoints |
| `management/frontend/src/views/BackupContentsView.vue` | Add Public Website tab |
| `management/frontend/src/components/PublicWebsiteFiles.vue` | NEW component |
| `alembic/versions/xxx_add_public_website_backup.py` | NEW migration |

---

## Security Considerations

1. **Path Traversal Prevention**
   - All file paths must be sanitized
   - Use `os.path.normpath()` and check for `..`
   - Validate paths don't escape backup directory

2. **File Size Limits**
   - Consider limiting individual file download size
   - Consider limiting total restore size

3. **Permission Checks**
   - All endpoints require authenticated user
   - Consider adding admin-only restriction for restore

---

---

## Behavior Matrix: With vs Without Public Website

### Backup Creation

| Scenario | Public Website Installed | `include_public_website` Config | Result |
|----------|--------------------------|--------------------------------|--------|
| A | No | N/A | No public website backup, no manifest |
| B | Yes | false | No public website backup, no manifest |
| C | Yes | true | Full backup of public_web_root volume + manifest |

**Detection Logic:**
```python
# In backup_service.py
PUBLIC_WEBSITE_INDICATOR = "/app/host_project/filebrowser.db"
PUBLIC_WEBSITE_VOLUME = "public_web_root"

def _is_public_website_installed(self) -> bool:
    """
    Check if public website feature is installed.
    Looks for filebrowser.db which is created when public website is enabled.
    """
    return os.path.exists(PUBLIC_WEBSITE_INDICATOR)
```

### Backup Contents (metadata.json)

**Without Public Website:**
```json
{
  "backup_type": "manual",
  "created_at": "2026-01-22T12:00:00Z",
  "databases": ["n8n", "n8n_management"],
  "config_files_count": 8,
  "ssl_included": true,
  "public_website_included": false,
  "public_website_file_count": 0
}
```

**With Public Website:**
```json
{
  "backup_type": "manual",
  "created_at": "2026-01-22T12:00:00Z",
  "databases": ["n8n", "n8n_management"],
  "config_files_count": 10,
  "ssl_included": true,
  "public_website_included": true,
  "public_website_file_count": 47
}
```

### BackupContents Database Record

**Without Public Website:**
```sql
INSERT INTO backup_contents (
  backup_id, workflow_count, credential_count, config_file_count,
  public_website_file_count, workflows_manifest, credentials_manifest,
  config_files_manifest, database_schema_manifest, public_website_manifest
) VALUES (
  123, 15, 5, 8,
  0,  -- no public website files
  '[...]', '[...]', '[...]', '[...]',
  NULL  -- no manifest
);
```

**With Public Website:**
```sql
INSERT INTO backup_contents (
  backup_id, workflow_count, credential_count, config_file_count,
  public_website_file_count, workflows_manifest, credentials_manifest,
  config_files_manifest, database_schema_manifest, public_website_manifest
) VALUES (
  123, 15, 5, 10,
  47,  -- includes public website files
  '[...]', '[...]', '[...]', '[...]',
  '[{"path": "index.html", "size": 2048, ...}, ...]'  -- file manifest
);
```

### API Response: GET /backups/{id}/contents

**Without Public Website Installed:**
```json
{
  "backup_id": 123,
  "workflow_count": 15,
  "credential_count": 5,
  "config_file_count": 8,
  "public_website_file_count": 0,
  "public_website_available": false,
  "workflows_manifest": [...],
  "credentials_manifest": [...],
  "config_files_manifest": [...],
  "database_schema_manifest": [...],
  "public_website_manifest": null
}
```

**With Public Website Installed:**
```json
{
  "backup_id": 123,
  "workflow_count": 15,
  "credential_count": 5,
  "config_file_count": 10,
  "public_website_file_count": 47,
  "public_website_available": true,
  "workflows_manifest": [...],
  "credentials_manifest": [...],
  "config_files_manifest": [...],
  "database_schema_manifest": [...],
  "public_website_manifest": [
    {"path": "index.html", "size": 2048, "modified_at": "2026-01-20T10:00:00Z", "checksum": "abc123"},
    {"path": "css/style.css", "size": 5120, "modified_at": "2026-01-20T10:00:00Z", "checksum": "def456"},
    {"path": "images/logo.png", "size": 102400, "modified_at": "2026-01-20T10:00:00Z", "checksum": "ghi789"}
  ]
}
```

### Frontend Display

**Without Public Website:**
```
┌─────────────────────────────────────────────────────────────────┐
│  Backup Contents - Backup #123                                  │
├─────────────────────────────────────────────────────────────────┤
│  [Workflows (15)] [Credentials (5)] [Config (8)] [Database]     │
│                                                                 │
│  ← No Public Website tab shown                                  │
└─────────────────────────────────────────────────────────────────┘
```

**With Public Website:**
```
┌─────────────────────────────────────────────────────────────────┐
│  Backup Contents - Backup #123                                  │
├─────────────────────────────────────────────────────────────────┤
│  [Workflows (15)] [Credentials (5)] [Config (10)] [Database]    │
│  [Public Website (47)]  ← NEW TAB                               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Public Website Files                    [Restore All]   │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ ☐ index.html              2 KB    Jan 20, 2026         │   │
│  │ ☐ css/style.css           5 KB    Jan 20, 2026         │   │
│  │ ☐ images/logo.png       100 KB    Jan 20, 2026         │   │
│  │ ☐ js/app.js              12 KB    Jan 20, 2026         │   │
│  │ ...                                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Complete Code Changes

### File 1: `management/api/models/backups.py`

**Lines to modify:** Around line 234-251

**Current code:**
```python
class BackupContents(Base):
    # ... existing fields ...
    workflow_count = Column(Integer, default=0)
    credential_count = Column(Integer, default=0)
    config_file_count = Column(Integer, default=0)

    workflows_manifest = Column(JSONB, nullable=True)
    credentials_manifest = Column(JSONB, nullable=True)
    config_files_manifest = Column(JSONB, nullable=True)
    database_schema_manifest = Column(JSONB, nullable=True)
    verification_checksums = Column(JSONB, nullable=True)
```

**New code:**
```python
class BackupContents(Base):
    # ... existing fields ...
    workflow_count = Column(Integer, default=0)
    credential_count = Column(Integer, default=0)
    config_file_count = Column(Integer, default=0)
    public_website_file_count = Column(Integer, default=0)  # NEW

    workflows_manifest = Column(JSONB, nullable=True)
    credentials_manifest = Column(JSONB, nullable=True)
    config_files_manifest = Column(JSONB, nullable=True)
    database_schema_manifest = Column(JSONB, nullable=True)
    public_website_manifest = Column(JSONB, nullable=True)  # NEW
    verification_checksums = Column(JSONB, nullable=True)
```

---

### File 2: `management/api/services/backup_service.py`

**Addition 1:** New function after `capture_config_file_manifest()` (~line 1230)

```python
async def capture_public_website_manifest(self, temp_dir: str) -> Tuple[int, List[Dict]]:
    """
    Capture manifest of public website files from the backup.

    This function scans the public_website directory in the backup temp folder
    and creates a manifest of all files with their metadata.

    Only called if:
    1. Public website feature is installed (_is_public_website_installed() returns True)
    2. Public website was successfully backed up (public_website_included is True)

    Args:
        temp_dir: Path to the temporary backup directory

    Returns:
        Tuple of (file_count, manifest_list)
        manifest_list format: [
            {
                "path": "relative/path/to/file.ext",
                "size": 1234,  # bytes
                "modified_at": "2026-01-22T12:00:00Z",
                "checksum": "md5hash"  # only for files < 10MB
            },
            ...
        ]
    """
    public_website_dir = os.path.join(temp_dir, "public_website")

    if not os.path.exists(public_website_dir):
        logger.info("No public website directory in backup - skipping manifest capture")
        return 0, []

    manifest = []
    file_count = 0

    try:
        for root, dirs, files in os.walk(public_website_dir):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for filename in files:
                # Skip hidden files
                if filename.startswith('.'):
                    continue

                file_path = os.path.join(root, filename)
                relative_path = os.path.relpath(file_path, public_website_dir)

                try:
                    stat = os.stat(file_path)

                    # Calculate MD5 checksum for files under 10MB
                    checksum = None
                    if stat.st_size < 10 * 1024 * 1024:  # 10MB
                        import hashlib
                        with open(file_path, 'rb') as f:
                            checksum = hashlib.md5(f.read()).hexdigest()

                    # Determine file type for UI display
                    import mimetypes
                    mime_type, _ = mimetypes.guess_type(filename)

                    manifest.append({
                        "path": relative_path,
                        "size": stat.st_size,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                        "checksum": checksum,
                        "mime_type": mime_type or "application/octet-stream"
                    })
                    file_count += 1

                except Exception as e:
                    logger.warning(f"Error capturing manifest for {relative_path}: {e}")
                    continue

        # Sort by path for consistent ordering
        manifest.sort(key=lambda x: x["path"])
        logger.info(f"Captured public website manifest: {file_count} files")

    except Exception as e:
        logger.error(f"Error walking public website directory: {e}")
        return 0, []

    return file_count, manifest
```

**Addition 2:** Update `run_backup_with_metadata()` (~line 1146)

Find this section:
```python
metadata["public_website_included"] = public_website_included
metadata["public_website_file_count"] = public_website_file_count
```

Add after it:
```python
# Capture public website manifest if files were backed up
public_website_manifest = []
public_website_manifest_count = 0
if public_website_included and public_website_file_count > 0:
    await update_progress(56, "Capturing public website manifest")
    public_website_manifest_count, public_website_manifest = await self.capture_public_website_manifest(temp_dir)
    logger.info(f"Public website manifest: {public_website_manifest_count} files catalogued")
```

**Addition 3:** Update BackupContents creation (~line 1200)

Find where BackupContents is created and add:
```python
public_website_file_count=public_website_manifest_count,
public_website_manifest=public_website_manifest if public_website_manifest else None,
```

---

### File 3: `management/api/services/restore_service.py`

**Addition:** Three new methods at end of class

```python
# =========================================================================
# Public Website Restore Methods
# =========================================================================

async def list_public_website_files(self, backup_id: int) -> List[Dict]:
    """
    List public website files from a mounted backup.

    Prerequisites:
    - Public website feature must be installed on the system
    - Backup must be mounted via mount_backup()

    Args:
        backup_id: The backup ID to list files from

    Returns:
        List of file dictionaries with path, size, modified_at

    Raises:
        ValueError: If backup is not mounted or public website not installed
    """
    # Check if public website is installed
    if not os.path.exists("/app/host_project/filebrowser.db"):
        raise ValueError("Public website feature is not installed")

    # Check if backup is mounted
    if not self._is_backup_mounted(backup_id):
        raise ValueError(f"Backup {backup_id} is not mounted. Call mount_backup() first.")

    public_website_dir = os.path.join(self.mount_dir, "public_website")

    if not os.path.exists(public_website_dir):
        logger.info(f"No public website directory in backup {backup_id}")
        return []

    files = []
    for root, dirs, filenames in os.walk(public_website_dir):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        for filename in filenames:
            if filename.startswith('.'):
                continue

            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, public_website_dir)

            try:
                stat = os.stat(file_path)
                files.append({
                    "path": relative_path,
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
                })
            except Exception as e:
                logger.warning(f"Error getting stats for {relative_path}: {e}")

    return sorted(files, key=lambda x: x["path"])


async def download_public_website_file(self, backup_id: int, file_path: str) -> Tuple[bytes, str]:
    """
    Download a specific public website file from a mounted backup.

    Prerequisites:
    - Public website feature must be installed on the system
    - Backup must be mounted via mount_backup()

    Args:
        backup_id: The backup ID
        file_path: Relative path within public_website directory (e.g., "images/logo.png")

    Returns:
        Tuple of (file_content_bytes, filename)

    Raises:
        ValueError: If backup not mounted, invalid path, or public website not installed
        FileNotFoundError: If file doesn't exist in backup
    """
    # Check if public website is installed
    if not os.path.exists("/app/host_project/filebrowser.db"):
        raise ValueError("Public website feature is not installed")

    # Check if backup is mounted
    if not self._is_backup_mounted(backup_id):
        raise ValueError(f"Backup {backup_id} is not mounted. Call mount_backup() first.")

    # Security: Prevent path traversal attacks
    safe_path = os.path.normpath(file_path)
    if safe_path.startswith('..') or safe_path.startswith('/'):
        raise ValueError(f"Invalid file path: {file_path}")

    full_path = os.path.join(self.mount_dir, "public_website", safe_path)

    # Verify path is still within public_website directory
    if not full_path.startswith(os.path.join(self.mount_dir, "public_website")):
        raise ValueError(f"Path traversal attempt detected: {file_path}")

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"File not found in backup: {file_path}")

    if not os.path.isfile(full_path):
        raise ValueError(f"Not a file: {file_path}")

    with open(full_path, 'rb') as f:
        content = f.read()

    return content, os.path.basename(file_path)


async def restore_public_website_files(
    self,
    backup_id: int,
    file_paths: Optional[List[str]] = None,
    overwrite: bool = False
) -> Dict:
    """
    Restore public website files from a mounted backup to the live public_web_root volume.

    Prerequisites:
    - Public website feature must be installed on the system
    - Backup must be mounted via mount_backup()

    Args:
        backup_id: The backup ID (must be mounted)
        file_paths: Optional list of specific file paths to restore.
                   If None or empty, ALL files are restored.
        overwrite: If True, overwrite existing files. If False, skip existing files.

    Returns:
        Dictionary with results:
        {
            "restored": ["file1.html", "css/style.css", ...],
            "restored_count": 15,
            "skipped": ["existing_file.html", ...],  # only if overwrite=False
            "skipped_count": 2,
            "errors": [{"path": "bad_file.txt", "error": "Permission denied"}],
            "error_count": 1
        }

    Raises:
        ValueError: If backup not mounted or public website not installed
    """
    # Check if public website is installed
    if not os.path.exists("/app/host_project/filebrowser.db"):
        raise ValueError("Public website feature is not installed")

    # Check if backup is mounted
    if not self._is_backup_mounted(backup_id):
        raise ValueError(f"Backup {backup_id} is not mounted. Call mount_backup() first.")

    source_dir = os.path.join(self.mount_dir, "public_website")

    if not os.path.exists(source_dir):
        raise ValueError("No public website files in this backup")

    restored = []
    skipped = []
    errors = []

    # Build list of files to restore
    if not file_paths:
        # Restore all files
        files_to_restore = []
        for root, dirs, filenames in os.walk(source_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in filenames:
                if not filename.startswith('.'):
                    full_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(full_path, source_dir)
                    files_to_restore.append(relative_path)
    else:
        files_to_restore = file_paths

    logger.info(f"Restoring {len(files_to_restore)} public website files from backup {backup_id}")

    for file_path in files_to_restore:
        try:
            # Security: Prevent path traversal
            safe_path = os.path.normpath(file_path)
            if safe_path.startswith('..') or safe_path.startswith('/'):
                errors.append({"path": file_path, "error": "Invalid path - path traversal attempt"})
                continue

            source_file = os.path.join(source_dir, safe_path)

            if not os.path.exists(source_file):
                errors.append({"path": file_path, "error": "File not found in backup"})
                continue

            # Check if file exists in destination (if not overwriting)
            if not overwrite:
                check_result = subprocess.run([
                    "docker", "run", "--rm",
                    "-v", "public_web_root:/dest:ro",
                    "alpine",
                    "test", "-f", f"/dest/{safe_path}"
                ], capture_output=True)

                if check_result.returncode == 0:
                    skipped.append(file_path)
                    continue

            # Ensure destination directory exists
            dest_dir = os.path.dirname(safe_path)
            if dest_dir:
                subprocess.run([
                    "docker", "run", "--rm",
                    "-v", "public_web_root:/dest",
                    "alpine",
                    "mkdir", "-p", f"/dest/{dest_dir}"
                ], check=True, capture_output=True)

            # Copy file to volume
            # We mount source directory and copy the specific file
            subprocess.run([
                "docker", "run", "--rm",
                "-v", f"{source_dir}:/source:ro",
                "-v", "public_web_root:/dest",
                "alpine",
                "cp", f"/source/{safe_path}", f"/dest/{safe_path}"
            ], check=True, capture_output=True)

            restored.append(file_path)
            logger.debug(f"Restored: {file_path}")

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            errors.append({"path": file_path, "error": error_msg})
            logger.error(f"Failed to restore {file_path}: {error_msg}")

        except Exception as e:
            errors.append({"path": file_path, "error": str(e)})
            logger.error(f"Failed to restore {file_path}: {e}")

    result = {
        "restored": restored,
        "restored_count": len(restored),
        "skipped": skipped,
        "skipped_count": len(skipped),
        "errors": errors,
        "error_count": len(errors)
    }

    logger.info(f"Public website restore complete: {len(restored)} restored, {len(skipped)} skipped, {len(errors)} errors")
    return result
```

---

### File 4: `management/api/routers/backups.py`

**Addition:** New endpoints (add near other restore endpoints, ~line 1100)

```python
# =========================================================================
# Public Website Restore Endpoints
# =========================================================================

@router.get("/backups/{backup_id}/restore/public-website-files",
            summary="List public website files in backup",
            response_description="List of files available for restore")
async def list_public_website_files_endpoint(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all public website files available in a mounted backup.

    **Prerequisites:**
    - Public website feature must be installed
    - Backup must be mounted first (POST /backups/{id}/mount)

    **Returns:**
    - file_count: Total number of files
    - files: Array of file objects with path, size, modified_at
    """
    try:
        files = await restore_service.list_public_website_files(backup_id)
        return {
            "backup_id": backup_id,
            "public_website_installed": True,
            "file_count": len(files),
            "files": files
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing public website files: {e}")
        raise HTTPException(status_code=500, detail="Failed to list public website files")


@router.get("/backups/{backup_id}/public-website/{file_path:path}/download",
            summary="Download a public website file from backup",
            response_description="File content")
async def download_public_website_file_endpoint(
    backup_id: int,
    file_path: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Download a specific file from the public website backup.

    **Prerequisites:**
    - Public website feature must be installed
    - Backup must be mounted first

    **Path parameter:**
    - file_path: Relative path to file (e.g., "css/style.css" or "images/logo.png")
    """
    try:
        content, filename = await restore_service.download_public_website_file(backup_id, file_path)

        # Determine content type
        import mimetypes
        content_type, _ = mimetypes.guess_type(filename)
        if content_type is None:
            content_type = "application/octet-stream"

        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(content))
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error downloading public website file: {e}")
        raise HTTPException(status_code=500, detail="Failed to download file")


class PublicWebsiteRestoreRequest(BaseModel):
    """Request schema for restoring public website files."""
    file_paths: Optional[List[str]] = Field(
        default=None,
        description="List of file paths to restore. If null/empty, ALL files are restored."
    )
    overwrite: bool = Field(
        default=False,
        description="If true, overwrite existing files. If false, skip existing files."
    )


@router.post("/backups/{backup_id}/restore/public-website",
             summary="Restore public website files from backup",
             response_description="Restore operation results")
async def restore_public_website_files_endpoint(
    backup_id: int,
    request: PublicWebsiteRestoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Restore public website files from a mounted backup to the live volume.

    **Prerequisites:**
    - Public website feature must be installed
    - Backup must be mounted first

    **Request body:**
    - file_paths: List of specific files to restore, or null to restore ALL files
    - overwrite: Whether to overwrite existing files (default: false)

    **Returns:**
    - restored: List of successfully restored file paths
    - restored_count: Number of files restored
    - skipped: List of files skipped (if overwrite=false and file exists)
    - skipped_count: Number of files skipped
    - errors: List of errors encountered
    - error_count: Number of errors
    """
    try:
        result = await restore_service.restore_public_website_files(
            backup_id,
            file_paths=request.file_paths,
            overwrite=request.overwrite
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error restoring public website files: {e}")
        raise HTTPException(status_code=500, detail="Failed to restore public website files")
```

**Update:** Modify BackupContentsResponse schema (in schemas/backups.py or inline)

```python
class BackupContentsResponse(BaseModel):
    backup_id: int
    workflow_count: int = 0
    credential_count: int = 0
    config_file_count: int = 0
    public_website_file_count: int = 0  # NEW

    # Flag indicating if public website feature is currently installed
    # Used by frontend to show/hide public website tab
    public_website_available: bool = False  # NEW

    workflows_manifest: Optional[List[Dict]] = None
    credentials_manifest: Optional[List[Dict]] = None
    config_files_manifest: Optional[List[Dict]] = None
    database_schema_manifest: Optional[List[Dict]] = None
    public_website_manifest: Optional[List[Dict]] = None  # NEW

    class Config:
        from_attributes = True
```

**Update:** Modify get_backup_contents endpoint to include public_website_available flag

```python
@router.get("/backups/contents/{backup_id}")
async def get_backup_contents(...):
    # ... existing code ...

    # Add this to the response:
    response["public_website_available"] = backup_service._is_public_website_installed()

    return response
```

---

### File 5: Frontend Changes

**File:** `management/frontend/src/views/BackupsView.vue` or similar

The frontend needs to:

1. **Check `public_website_available` flag** from API response
2. **Conditionally render Public Website tab** only if flag is true AND file_count > 0
3. **Provide file browser interface** for viewing and selecting files
4. **Support actions:** Download individual file, Restore selected, Restore all

See Section 5 (Frontend Changes) above for component structure.

---

## Summary of All Changes

| File | Type | Changes |
|------|------|---------|
| `models/backups.py` | Model | Add 2 columns to BackupContents |
| `services/backup_service.py` | Service | Add `capture_public_website_manifest()`, update backup flow |
| `services/restore_service.py` | Service | Add 3 new methods for list/download/restore |
| `routers/backups.py` | API | Add 3 new endpoints, update response schema |
| `schemas/backups.py` | Schema | Update BackupContentsResponse |
| Frontend | Vue | Add Public Website tab and file browser component |
| Alembic | Migration | Add 2 columns to backup_contents table |

**Total new endpoints:** 3
**Total new service methods:** 4
**Total new model columns:** 2
**Estimated lines of code:** ~500

---

*Document Version: 1.1*
*Created: January 22, 2026*
*Last Updated: January 22, 2026*
*Status: PENDING REVIEW*
