# Public Website Backup & Restore Plan

## Executive Summary

This document outlines the changes required to fully integrate public website files into the backup and restore system. The implementation ensures public website files can be:
- Included in backups automatically
- Viewed in "View Backup Contents"
- Selectively restored (individual files or all files)
- Downloaded for inspection
- Previewed in-browser (text-based files like HTML, CSS, JS)

**Key Requirement:** All functionality is conditional - only active when public website feature is installed.

---

## Current State

### What's Already Implemented

| Component | Status | Location |
|-----------|--------|----------|
| `include_public_website` config flag | Done | `models/backups.py:346` |
| `_is_public_website_installed()` detection | Done | `backup_service.py:1244` |
| `_backup_public_website_volume()` backup | Done | `backup_service.py:1248` |
| Metadata tracking in backup | Done | `backup_service.py:1143-1144` |
| Restore script with `--skip-public-website` | Done | `backup_service.py:2309` |

### What's Missing

| Component | Status | Required For |
|-----------|--------|--------------|
| `public_website_file_count` in BackupContents | Missing | View Backup Contents |
| `public_website_manifest` in BackupContents | Missing | View Backup Contents |
| `capture_public_website_manifest()` function | Missing | Backup creation |
| File-based mounting system for PW files | Missing | Selective Restore |
| Public website file listing endpoint (paginated) | Missing | Selective Restore UI |
| Public website file preview endpoint | Missing | File inspection |
| Public website file download endpoint | Missing | File inspection |
| Public website dry-run check endpoint | Missing | Overwrite warnings |
| Public website selective restore endpoint | Missing | Selective Restore |
| Frontend: Public Website tab in contents view | Missing | User interface |
| Frontend: File browser with pagination | Missing | User interface |
| Frontend: File preview modal | Missing | User interface |
| Frontend: Restore confirmation dialog | Missing | User interface |
| Configuration for volume names | Missing | Deployment flexibility |

---

## Architecture Overview

### Backup Flow (Enhanced)

```
+-------------------------------------------------------------------+
|                    run_backup_with_metadata()                      |
+-------------------------------------------------------------------+
                                |
                                v
+-------------------------------------------------------------------+
| 1. Backup databases (postgres_full/n8n/mgmt)                      |
| 2. Backup config files (.env, docker-compose.yaml, etc.)          |
| 3. Backup SSL certificates (/etc/letsencrypt)                     |
| 4. Backup public website volume (if installed & enabled)     <NEW |
| 5. Capture manifests:                                             |
|    - Workflow manifest                                            |
|    - Credential manifest                                          |
|    - Config file manifest                                         |
|    - Database schema manifest                                     |
|    - Public website manifest (if installed)                  <NEW |
| 6. Create archive with metadata.json                              |
| 7. Store BackupContents record with all manifests                 |
+-------------------------------------------------------------------+
```

### Backup Archive Structure (Enhanced)

```
backup_20260122_120000.tar.gz/
+-- databases/
|   +-- n8n.dump
|   +-- n8n_management.dump
+-- config/
|   +-- .env
|   +-- docker-compose.yaml
|   +-- nginx.conf
|   +-- nginx-public.conf          # If public website enabled
|   +-- nginx-router.conf          # If public website enabled
|   +-- filebrowser.db
|   +-- ...
+-- ssl/
|   +-- domain.com/
|       +-- cert.pem
|       +-- fullchain.pem
|       +-- privkey.pem
+-- public_website/                 # NEW: Only if public website installed
|   +-- index.html
|   +-- css/
|   |   +-- style.css
|   +-- js/
|   |   +-- app.js
|   +-- images/
|   |   +-- logo.png
|   +-- ...
+-- metadata.json
+-- restore.sh
```

### View Backup Contents Flow

```
+------------------+     GET /backups/{id}/contents     +------------------+
|                  | ---------------------------------> |                  |
|     Frontend     |                                    |    Backend API   |
|  (BackupView)    | <--------------------------------- |                  |
|                  |     BackupContentsResponse         |                  |
+------------------+     (includes public_website)      +------------------+
         |
         v
+--------------------------------------------------------------------------+
|  Tabs: [Workflows] [Credentials] [Config Files] [Database] [Public Web]  |
|                                                              ^            |
|                                                              |            |
|                                                         NEW TAB           |
+--------------------------------------------------------------------------+
```

### Selective Restore Flow (File-Based Mounting)

```
+------------------+                                    +------------------+
|                  |  POST /backups/{id}/mount-         |                  |
|     Frontend     |       public-website               |   RestoreService |
|                  | ---------------------------------> |                  |
|                  | <--------------------------------- |  (extracts       |
|                  |     {status, file_count}           |   archive to     |
|                  |                                    |   temp dir)      |
|                  |  GET /backups/{id}/restore/        |                  |
|                  |      public-website-files          |                  |
|                  |      ?page=1&search=...            |                  |
|                  | ---------------------------------> |  (lists files    |
|                  | <--------------------------------- |   with pagination|
|                  |     {files, pagination}            |   and filters)   |
|                  |                                    |                  |
|                  |  GET /backups/{id}/public-website/ |                  |
|                  |      {path}/preview                |                  |
|                  | ---------------------------------> |  (returns text   |
|                  | <--------------------------------- |   content for    |
|                  |     {content, syntax, truncated}   |   preview)       |
|                  |                                    |                  |
|  User selects    |  POST /backups/{id}/restore/       |                  |
|  files to        |       public-website               |                  |
|  restore         |       {dry_run: true}              |                  |
|                  | ---------------------------------> |  (checks what    |
|                  | <--------------------------------- |   would be       |
|                  |     {files_to_overwrite, ...}      |   overwritten)   |
|                  |                                    |                  |
|  User confirms   |  POST /backups/{id}/restore/       |                  |
|                  |       public-website               |                  |
|                  |       {file_paths, overwrite}      |                  |
|                  | ---------------------------------> |  (batch restores |
|                  | <--------------------------------- |   to volume)     |
|                  |     {restored, skipped, errors}    |                  |
+------------------+                                    +------------------+
```

---

## Implementation Details

### 0. Configuration Changes

**File:** `management/api/core/config.py`

Add configurable volume names and paths to support different deployment configurations:

```python
from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    # ... existing settings ...

    # Docker volume names (configurable via environment)
    PUBLIC_WEBSITE_VOLUME: str = "public_web_root"
    N8N_DATA_VOLUME: str = "n8n_data"
    POSTGRES_VOLUME: str = "n8n_postgres_data"

    # Public website feature detection
    PUBLIC_WEBSITE_INDICATOR_PATH: str = "/app/host_project/filebrowser.db"

    # Checksum configuration
    CHECKSUM_ALGORITHM: Literal["md5", "sha256"] = "sha256"
    CHECKSUM_SIZE_LIMIT: int = 10 * 1024 * 1024  # 10MB

    # Public website mount settings
    PW_MOUNT_IDLE_TIMEOUT: int = 300  # 5 minutes

    class Config:
        env_file = ".env"
        env_prefix = "N8N_MGMT_"


settings = Settings()
```

**Environment Variable Support:**
```bash
# .env file (optional overrides)
N8N_MGMT_PUBLIC_WEBSITE_VOLUME=my_custom_volume_name
N8N_MGMT_CHECKSUM_ALGORITHM=sha256
```

---

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
    # Format: [{path, size, modified_at, checksum, checksum_algorithm, mime_type}, ...]
    public_website_manifest = Column(JSONB, nullable=True)

    verification_checksums = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # ... rest unchanged
```

**Migration Required:** Yes - Alembic migration to add new columns.

---

### 2. Backup Service Changes

**File:** `management/api/services/backup_service.py`

#### 2.1 Import Configuration

```python
from core.config import settings

# Use configured values instead of hardcoded constants
PUBLIC_WEBSITE_VOLUME = settings.PUBLIC_WEBSITE_VOLUME
PUBLIC_WEBSITE_INDICATOR = settings.PUBLIC_WEBSITE_INDICATOR_PATH
```

#### 2.2 Checksum Helper Function

```python
import hashlib
from typing import Optional

def calculate_file_checksum(file_path: str) -> Optional[str]:
    """
    Calculate checksum for a file using configured algorithm (SHA256 by default).

    Args:
        file_path: Path to the file

    Returns:
        Hex digest of the checksum, or None if file is too large
    """
    try:
        file_size = os.path.getsize(file_path)

        if file_size > settings.CHECKSUM_SIZE_LIMIT:
            return None

        if settings.CHECKSUM_ALGORITHM == "sha256":
            hasher = hashlib.sha256()
        else:
            hasher = hashlib.md5()

        with open(file_path, 'rb') as f:
            # Read in chunks for memory efficiency
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)

        return hasher.hexdigest()

    except Exception as e:
        logger.warning(f"Failed to calculate checksum for {file_path}: {e}")
        return None
```

#### 2.3 New Function: `capture_public_website_manifest()`

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
                "checksum": "sha256hash",  # only for files < 10MB
                "checksum_algorithm": "sha256",
                "mime_type": "text/html"
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

                    # Calculate checksum using configured algorithm
                    checksum = calculate_file_checksum(file_path)

                    # Determine MIME type for UI display
                    import mimetypes
                    mime_type, _ = mimetypes.guess_type(filename)

                    manifest.append({
                        "path": relative_path,
                        "size": stat.st_size,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                        "checksum": checksum,
                        "checksum_algorithm": settings.CHECKSUM_ALGORITHM if checksum else None,
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

#### 2.4 Update `run_backup_with_metadata()`

Add call to capture public website manifest after backing up files:

```python
# After backing up public website volume (around line 1144)
metadata["public_website_included"] = public_website_included
metadata["public_website_file_count"] = public_website_file_count

# NEW: Capture public website manifest if files were backed up
public_website_manifest = []
public_website_manifest_count = 0
if public_website_included and public_website_file_count > 0:
    await update_progress(56, "Capturing public website manifest")
    public_website_manifest_count, public_website_manifest = await self.capture_public_website_manifest(temp_dir)
    logger.info(f"Public website manifest: {public_website_manifest_count} files catalogued")
```

#### 2.5 Update BackupContents Creation

Update the code that creates the BackupContents record to include public website data:

```python
# When creating BackupContents record
backup_contents = BackupContents(
    backup_id=backup_history.id,
    workflow_count=workflow_count,
    credential_count=credential_count,
    config_file_count=len(config_files_manifest),
    public_website_file_count=public_website_manifest_count,  # NEW
    workflows_manifest=workflows_manifest,
    credentials_manifest=credentials_manifest,
    config_files_manifest=config_files_manifest,
    database_schema_manifest=database_schema_manifest,
    public_website_manifest=public_website_manifest if public_website_manifest else None,  # NEW
    verification_checksums=verification_checksums
)
```

---

### 3. Restore Service Changes

**File:** `management/api/services/restore_service.py`

#### 3.1 Module-Level State and Imports

**IMPORTANT:** The current restore service uses database-focused mounting (PostgreSQL container).
For public website files, we need a separate FILE-BASED mounting system that extracts
the archive to a temp directory.

```python
import asyncio
import tarfile
import shutil
import tempfile
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Tuple

from core.config import settings

# =========================================================================
# Public Website File-Based Mounting System
# =========================================================================
#
# Unlike database mounting (which uses a PostgreSQL container), public website
# mounting extracts the archive to a temp directory for file access.
# This is separate from the database restore container.

_mounted_pw_backup_id: Optional[int] = None
_mounted_pw_temp_dir: Optional[str] = None
_mounted_pw_file_list: Optional[List[Dict]] = None
_mounted_pw_timestamp: Optional[float] = None

# Lock to prevent race conditions during restore operations
_pw_restore_lock = asyncio.Lock()
```

#### 3.2 File-Based Mount Helper Functions

```python
def is_public_website_mounted(backup_id: int) -> bool:
    """
    Check if a backup's public website files are currently mounted (extracted).

    This is separate from database mounting - we extract the archive to a temp
    directory for file operations.
    """
    global _mounted_pw_backup_id, _mounted_pw_temp_dir

    if _mounted_pw_backup_id != backup_id:
        return False

    if _mounted_pw_temp_dir and os.path.exists(_mounted_pw_temp_dir):
        return True

    # State is stale, clean up
    _mounted_pw_backup_id = None
    _mounted_pw_temp_dir = None
    _mounted_pw_file_list = None
    _mounted_pw_timestamp = None
    return False


def get_pw_mount_dir() -> Optional[str]:
    """Get the current public website mount directory."""
    global _mounted_pw_temp_dir
    if _mounted_pw_temp_dir and os.path.exists(_mounted_pw_temp_dir):
        return _mounted_pw_temp_dir
    return None


def get_pw_mount_status() -> Dict:
    """Get current public website mount status."""
    global _mounted_pw_backup_id, _mounted_pw_temp_dir, _mounted_pw_file_list, _mounted_pw_timestamp

    if _mounted_pw_backup_id and _mounted_pw_temp_dir and os.path.exists(_mounted_pw_temp_dir):
        return {
            "mounted": True,
            "backup_id": _mounted_pw_backup_id,
            "file_count": len(_mounted_pw_file_list) if _mounted_pw_file_list else 0,
            "mounted_at": _mounted_pw_timestamp
        }

    return {"mounted": False, "backup_id": None, "file_count": 0}


@asynccontextmanager
async def pw_restore_lock(timeout: float = 30.0):
    """
    Acquire lock for public website restore operations.

    Prevents race conditions when multiple restore requests come in simultaneously.
    """
    try:
        await asyncio.wait_for(_pw_restore_lock.acquire(), timeout=timeout)
        yield
    except asyncio.TimeoutError:
        raise RuntimeError("Timeout waiting for public website restore lock. Another operation is in progress.")
    finally:
        if _pw_restore_lock.locked():
            _pw_restore_lock.release()
```

#### 3.3 New Function: `mount_public_website_files()`

```python
async def mount_public_website_files(self, backup_id: int) -> Dict:
    """
    Mount (extract) public website files from a backup for browsing/restore.

    Unlike database mounting which uses a PostgreSQL container, this extracts
    the public_website directory from the backup archive to a temp directory.

    The extracted files remain available until unmount_public_website_files()
    is called or the idle timeout is reached.

    Args:
        backup_id: The backup ID to mount

    Returns:
        Dict with status, backup_id, file_count

    Raises:
        ValueError: If backup not found or has no public website files
        FileNotFoundError: If backup file doesn't exist
    """
    global _mounted_pw_backup_id, _mounted_pw_temp_dir, _mounted_pw_file_list, _mounted_pw_timestamp

    # Check if public website feature is installed
    if not os.path.exists(settings.PUBLIC_WEBSITE_INDICATOR_PATH):
        raise ValueError("Public website feature is not installed")

    # Already mounted?
    if is_public_website_mounted(backup_id):
        return {
            "status": "already_mounted",
            "backup_id": backup_id,
            "file_count": len(_mounted_pw_file_list) if _mounted_pw_file_list else 0
        }

    # Unmount any existing
    await self.unmount_public_website_files()

    # Get backup and extract
    backup = await self._get_backup_by_id(backup_id)
    if not backup:
        raise ValueError(f"Backup {backup_id} not found")

    backup_file = backup.backup_file_path
    if not os.path.exists(backup_file):
        raise FileNotFoundError(f"Backup file not found: {backup_file}")

    temp_dir = tempfile.mkdtemp(prefix=f"pw_mount_{backup_id}_")

    try:
        # Extract only public_website directory from archive
        with tarfile.open(backup_file, 'r:gz') as tar:
            members = [m for m in tar.getmembers()
                      if m.name.startswith('public_website/')]

            if not members:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise ValueError("No public website files in this backup")

            tar.extractall(temp_dir, members=members)

        # Build file list
        pw_dir = os.path.join(temp_dir, "public_website")
        file_list = []

        for root, dirs, filenames in os.walk(pw_dir):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for filename in filenames:
                if filename.startswith('.'):
                    continue

                file_path = os.path.join(root, filename)
                relative_path = os.path.relpath(file_path, pw_dir)

                try:
                    stat = os.stat(file_path)

                    import mimetypes
                    mime_type, _ = mimetypes.guess_type(filename)

                    file_list.append({
                        "path": relative_path,
                        "size": stat.st_size,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                        "mime_type": mime_type or "application/octet-stream"
                    })
                except Exception as e:
                    logger.warning(f"Error getting stats for {relative_path}: {e}")

        file_list.sort(key=lambda x: x["path"])

        # Update global state
        _mounted_pw_backup_id = backup_id
        _mounted_pw_temp_dir = temp_dir
        _mounted_pw_file_list = file_list
        _mounted_pw_timestamp = datetime.now(UTC).timestamp()

        logger.info(f"Mounted public website files from backup {backup_id}: {len(file_list)} files")

        return {
            "status": "mounted",
            "backup_id": backup_id,
            "file_count": len(file_list)
        }

    except Exception as e:
        # Cleanup on failure
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


async def unmount_public_website_files(self) -> Dict:
    """
    Unmount (cleanup) any mounted public website files.

    Removes the temp directory and clears mount state.
    """
    global _mounted_pw_backup_id, _mounted_pw_temp_dir, _mounted_pw_file_list, _mounted_pw_timestamp

    backup_id = _mounted_pw_backup_id

    if _mounted_pw_temp_dir and os.path.exists(_mounted_pw_temp_dir):
        shutil.rmtree(_mounted_pw_temp_dir, ignore_errors=True)
        logger.info(f"Unmounted public website files from backup {backup_id}")

    _mounted_pw_backup_id = None
    _mounted_pw_temp_dir = None
    _mounted_pw_file_list = None
    _mounted_pw_timestamp = None

    return {"status": "unmounted", "backup_id": backup_id}
```

#### 3.4 New Function: `list_public_website_files()` (with Pagination)

```python
async def list_public_website_files(
    self,
    backup_id: int,
    page: int = 1,
    page_size: int = 50,
    search: Optional[str] = None,
    file_type: Optional[str] = None,
    sort_by: str = "path",
    sort_order: str = "asc"
) -> Dict:
    """
    List public website files from a mounted backup with pagination and filtering.

    Args:
        backup_id: The backup ID (must be mounted)
        page: Page number (1-indexed)
        page_size: Items per page (10-500)
        search: Filter by filename (case-insensitive)
        file_type: Filter by extension (e.g., 'html', 'css', 'png,jpg,gif')
        sort_by: Sort field ('path', 'size', 'modified_at')
        sort_order: Sort direction ('asc', 'desc')

    Returns:
        Dict with files array and pagination info

    Raises:
        ValueError: If backup is not mounted
    """
    if not is_public_website_mounted(backup_id):
        raise ValueError(f"Backup {backup_id} public website files are not mounted. Call mount_public_website_files() first.")

    # Start with cached file list
    all_files = _mounted_pw_file_list.copy()

    # Apply search filter
    if search:
        search_lower = search.lower()
        all_files = [f for f in all_files if search_lower in f["path"].lower()]

    # Apply file type filter (supports comma-separated extensions)
    if file_type:
        extensions = [f".{ext.strip().lower()}" for ext in file_type.split(',')]
        all_files = [f for f in all_files
                    if any(f["path"].lower().endswith(ext) for ext in extensions)]

    # Sort
    reverse = sort_order == "desc"
    if sort_by == "size":
        all_files.sort(key=lambda x: x["size"], reverse=reverse)
    elif sort_by == "modified_at":
        all_files.sort(key=lambda x: x["modified_at"], reverse=reverse)
    else:  # path
        all_files.sort(key=lambda x: x["path"], reverse=reverse)

    # Paginate
    total_count = len(all_files)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))  # Clamp to valid range

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_files = all_files[start_idx:end_idx]

    return {
        "files": page_files,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }
```

#### 3.5 New Function: `preview_public_website_file()`

```python
# MIME types that can be previewed in-browser
PREVIEWABLE_MIME_TYPES = {
    'text/html': 'html',
    'text/css': 'css',
    'text/javascript': 'javascript',
    'application/javascript': 'javascript',
    'application/json': 'json',
    'text/plain': 'text',
    'text/markdown': 'markdown',
    'text/xml': 'xml',
    'application/xml': 'xml',
    'image/svg+xml': 'xml',
    'text/yaml': 'yaml',
    'application/x-yaml': 'yaml',
}


async def preview_public_website_file(
    self,
    backup_id: int,
    file_path: str,
    max_size: int = 100000
) -> Dict:
    """
    Preview a text-based file from a mounted backup.

    Only supports text-based file types (HTML, CSS, JS, JSON, etc.).
    Binary files should use download_public_website_file() instead.

    Args:
        backup_id: The backup ID (must be mounted)
        file_path: Relative path within public_website directory
        max_size: Maximum bytes to return (default 100KB, max 500KB)

    Returns:
        Dict with content, truncated flag, mime_type, and syntax hint

    Raises:
        ValueError: If backup not mounted, invalid path, or non-text file
        FileNotFoundError: If file doesn't exist
    """
    if not is_public_website_mounted(backup_id):
        raise ValueError(f"Backup {backup_id} public website files are not mounted.")

    # Security: Prevent path traversal
    safe_path = os.path.normpath(file_path)
    if safe_path.startswith('..') or safe_path.startswith('/'):
        raise ValueError(f"Invalid file path: {file_path}")

    mount_dir = get_pw_mount_dir()
    full_path = os.path.join(mount_dir, "public_website", safe_path)

    # Verify path is still within public_website directory
    expected_base = os.path.join(mount_dir, "public_website")
    if not os.path.abspath(full_path).startswith(os.path.abspath(expected_base)):
        raise ValueError(f"Path traversal attempt detected: {file_path}")

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not os.path.isfile(full_path):
        raise ValueError(f"Not a file: {file_path}")

    # Check MIME type
    import mimetypes
    mime_type, _ = mimetypes.guess_type(file_path)

    if mime_type not in PREVIEWABLE_MIME_TYPES:
        raise ValueError(f"File type '{mime_type}' is not previewable. Use download instead.")

    # Read file
    file_size = os.path.getsize(full_path)
    max_size = min(max_size, 500000)  # Cap at 500KB

    with open(full_path, 'rb') as f:
        content = f.read(max_size + 1)  # Read one extra to check truncation

    truncated = len(content) > max_size
    if truncated:
        content = content[:max_size]

    # Decode as text
    try:
        text_content = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text_content = content.decode('latin-1')
        except UnicodeDecodeError:
            raise ValueError("File contains binary content that cannot be previewed")

    return {
        "file_path": file_path,
        "content": text_content,
        "size": file_size,
        "truncated": truncated,
        "mime_type": mime_type,
        "syntax": PREVIEWABLE_MIME_TYPES.get(mime_type, 'text')
    }
```

#### 3.6 New Function: `download_public_website_file()`

```python
async def download_public_website_file(
    self,
    backup_id: int,
    file_path: str
) -> Tuple[bytes, str]:
    """
    Download a specific public website file from a mounted backup.

    Args:
        backup_id: The backup ID (must be mounted)
        file_path: Relative path within public_website directory

    Returns:
        Tuple of (file_content_bytes, filename)

    Raises:
        ValueError: If backup not mounted or invalid path
        FileNotFoundError: If file doesn't exist
    """
    if not is_public_website_mounted(backup_id):
        raise ValueError(f"Backup {backup_id} public website files are not mounted.")

    # Security: Prevent path traversal
    safe_path = os.path.normpath(file_path)
    if safe_path.startswith('..') or safe_path.startswith('/'):
        raise ValueError(f"Invalid file path: {file_path}")

    mount_dir = get_pw_mount_dir()
    full_path = os.path.join(mount_dir, "public_website", safe_path)

    # Verify path is still within public_website directory
    expected_base = os.path.join(mount_dir, "public_website")
    if not os.path.abspath(full_path).startswith(os.path.abspath(expected_base)):
        raise ValueError(f"Path traversal attempt detected: {file_path}")

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not os.path.isfile(full_path):
        raise ValueError(f"Not a file: {file_path}")

    with open(full_path, 'rb') as f:
        content = f.read()

    return content, os.path.basename(file_path)
```

#### 3.7 New Function: `check_public_website_restore()` (Dry Run)

```python
async def check_public_website_restore(
    self,
    backup_id: int,
    file_paths: Optional[List[str]] = None
) -> Dict:
    """
    Dry-run check for restore operation.

    Returns information about what would happen without making changes.
    Used to warn users about files that would be overwritten.

    Args:
        backup_id: The backup ID (must be mounted)
        file_paths: Optional list of specific files. If None, checks all files.

    Returns:
        Dict with files_to_restore, files_to_overwrite, new_files lists
    """
    if not is_public_website_mounted(backup_id):
        raise ValueError(f"Backup {backup_id} is not mounted")

    mount_dir = get_pw_mount_dir()
    source_dir = os.path.join(mount_dir, "public_website")

    # Get files to check
    if not file_paths:
        file_paths = []
        for root, dirs, filenames in os.walk(source_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in filenames:
                if not filename.startswith('.'):
                    full_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(full_path, source_dir)
                    file_paths.append(relative_path)

    files_to_restore = []
    files_to_overwrite = []
    new_files = []

    for file_path in file_paths:
        safe_path = os.path.normpath(file_path)
        if safe_path.startswith('..') or safe_path.startswith('/'):
            continue

        source_file = os.path.join(source_dir, safe_path)
        if not os.path.exists(source_file):
            continue

        files_to_restore.append(file_path)

        # Check if file exists in destination volume
        check_result = subprocess.run([
            "docker", "run", "--rm",
            "-v", f"{settings.PUBLIC_WEBSITE_VOLUME}:/dest:ro",
            "alpine",
            "test", "-f", f"/dest/{safe_path}"
        ], capture_output=True)

        if check_result.returncode == 0:
            files_to_overwrite.append(file_path)
        else:
            new_files.append(file_path)

    return {
        "files_to_restore": files_to_restore,
        "files_to_overwrite": files_to_overwrite,
        "new_files": new_files,
        "total_count": len(files_to_restore),
        "overwrite_count": len(files_to_overwrite),
        "new_count": len(new_files)
    }
```

#### 3.8 New Function: `restore_public_website_files()` (Batched with Locking)

```python
async def restore_public_website_files(
    self,
    backup_id: int,
    file_paths: Optional[List[str]] = None,
    overwrite: bool = False
) -> Dict:
    """
    Restore public website files from mounted backup to the live volume.

    Uses batched Docker operations for performance and locking to prevent
    race conditions from concurrent restore requests.

    Args:
        backup_id: The backup ID (must be mounted)
        file_paths: Optional list of specific files. If None, restores all files.
        overwrite: If True, overwrite existing files. If False, skip existing.

    Returns:
        Dict with restored, skipped, and errors lists

    Raises:
        ValueError: If backup not mounted
        RuntimeError: If lock timeout or batch restore fails
    """
    async with pw_restore_lock():
        return await self._restore_pw_files_batched(backup_id, file_paths, overwrite)


async def _restore_pw_files_batched(
    self,
    backup_id: int,
    file_paths: Optional[List[str]],
    overwrite: bool
) -> Dict:
    """
    Internal batched restore implementation.

    Instead of running a Docker container per file, we:
    1. Create a shell script with all copy commands
    2. Run a single Docker container that executes the script

    This dramatically improves performance for large restores.
    """
    if not is_public_website_mounted(backup_id):
        raise ValueError(f"Backup {backup_id} is not mounted")

    mount_dir = get_pw_mount_dir()
    source_dir = os.path.join(mount_dir, "public_website")

    # Build list of files to restore
    if not file_paths:
        file_paths = []
        for root, dirs, filenames in os.walk(source_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in filenames:
                if not filename.startswith('.'):
                    full_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(full_path, source_dir)
                    file_paths.append(relative_path)

    # Validate files and categorize
    valid_files = []
    errors = []

    for file_path in file_paths:
        safe_path = os.path.normpath(file_path)
        if safe_path.startswith('..') or safe_path.startswith('/'):
            errors.append({"path": file_path, "error": "Invalid path - path traversal attempt"})
            continue

        source_file = os.path.join(source_dir, safe_path)
        if not os.path.exists(source_file):
            errors.append({"path": file_path, "error": "File not found in backup"})
            continue

        valid_files.append(safe_path)

    if not valid_files:
        return {
            "restored": [],
            "restored_count": 0,
            "skipped": [],
            "skipped_count": 0,
            "errors": errors,
            "error_count": len(errors)
        }

    logger.info(f"Restoring {len(valid_files)} public website files from backup {backup_id}")

    # Create batch restore script
    script_lines = [
        "#!/bin/sh",
        "set -e",  # Exit on error
        ""
    ]

    # Collect all directories that need to be created
    dirs_needed = set()
    for file_path in valid_files:
        dir_path = os.path.dirname(file_path)
        if dir_path:
            dirs_needed.add(dir_path)

    # Add mkdir commands (sorted for consistent ordering)
    for dir_path in sorted(dirs_needed):
        script_lines.append(f'mkdir -p "/dest/{dir_path}"')

    script_lines.append("")

    # Add copy commands with optional overwrite check
    for file_path in valid_files:
        if not overwrite:
            # Check if file exists before copying
            script_lines.append(f'if [ ! -f "/dest/{file_path}" ]; then')
            script_lines.append(f'  cp "/source/{file_path}" "/dest/{file_path}"')
            script_lines.append(f'  echo "RESTORED:{file_path}"')
            script_lines.append('else')
            script_lines.append(f'  echo "SKIPPED:{file_path}"')
            script_lines.append('fi')
        else:
            # Overwrite mode - just copy
            script_lines.append(f'cp "/source/{file_path}" "/dest/{file_path}"')
            script_lines.append(f'echo "RESTORED:{file_path}"')

    script_content = "\n".join(script_lines)

    # Write script to temp file in mount directory
    script_file = os.path.join(mount_dir, "restore_batch.sh")
    with open(script_file, 'w') as f:
        f.write(script_content)
    os.chmod(script_file, 0o755)

    try:
        # Run single Docker container with batch script
        # Key: source_dir is a host path (bind mount), volume is a named Docker volume
        result = subprocess.run([
            "docker", "run", "--rm",
            "-v", f"{source_dir}:/source:ro",                    # Host bind mount (read-only)
            "-v", f"{settings.PUBLIC_WEBSITE_VOLUME}:/dest",     # Named Docker volume
            "-v", f"{script_file}:/restore.sh:ro",               # Script file
            "alpine",
            "/bin/sh", "/restore.sh"
        ], capture_output=True, text=True, timeout=300)  # 5 minute timeout

        # Check for errors
        if result.returncode != 0:
            logger.error(f"Batch restore failed: {result.stderr}")
            raise RuntimeError(f"Batch restore failed: {result.stderr}")

        # Parse output to determine results
        restored = []
        skipped = []

        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if line.startswith("RESTORED:"):
                restored.append(line[9:])
            elif line.startswith("SKIPPED:"):
                skipped.append(line[8:])

        logger.info(f"Public website restore complete: {len(restored)} restored, {len(skipped)} skipped, {len(errors)} errors")

        return {
            "restored": restored,
            "restored_count": len(restored),
            "skipped": skipped,
            "skipped_count": len(skipped),
            "errors": errors,
            "error_count": len(errors)
        }

    except subprocess.TimeoutExpired:
        logger.error("Batch restore timed out after 5 minutes")
        raise RuntimeError("Restore operation timed out")

    except subprocess.CalledProcessError as e:
        logger.error(f"Batch restore failed: {e.stderr}")
        raise RuntimeError(f"Batch restore failed: {e.stderr}")

    finally:
        # Cleanup script file
        if os.path.exists(script_file):
            os.remove(script_file)
```

---

### 4. API Router Changes

**File:** `management/api/routers/backups.py`

#### 4.1 Import Updates

```python
from fastapi import Query
from fastapi.responses import Response
from typing import Optional, List
from pydantic import BaseModel, Field

from core.config import settings
```

#### 4.2 Request/Response Schemas

```python
# =========================================================================
# Public Website Schemas
# =========================================================================

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
    dry_run: bool = Field(
        default=False,
        description="If true, only check what would be overwritten without making changes."
    )


class BackupContentsResponse(BaseModel):
    """Response schema for backup contents."""
    backup_id: int
    workflow_count: int = 0
    credential_count: int = 0
    config_file_count: int = 0
    public_website_file_count: int = 0

    # Flag indicating if public website feature is currently installed
    public_website_available: bool = False

    workflows_manifest: Optional[List[Dict]] = None
    credentials_manifest: Optional[List[Dict]] = None
    config_files_manifest: Optional[List[Dict]] = None
    database_schema_manifest: Optional[List[Dict]] = None
    public_website_manifest: Optional[List[Dict]] = None

    class Config:
        from_attributes = True
```

#### 4.3 New Endpoint: Mount Public Website Files

```python
@router.post("/backups/{backup_id}/mount-public-website",
             summary="Mount public website files from backup",
             response_description="Mount status")
async def mount_public_website_endpoint(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Mount (extract) public website files from a backup for browsing and restore.

    This extracts the public_website directory from the backup archive to a
    temporary directory. The files remain mounted until explicitly unmounted
    or the idle timeout is reached.

    **Prerequisites:**
    - Public website feature must be installed

    **Returns:**
    - status: 'mounted' or 'already_mounted'
    - backup_id: The mounted backup ID
    - file_count: Number of files available
    """
    try:
        result = await restore_service.mount_public_website_files(backup_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error mounting public website files: {e}")
        raise HTTPException(status_code=500, detail="Failed to mount public website files")


@router.post("/backups/unmount-public-website",
             summary="Unmount public website files")
async def unmount_public_website_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Unmount any currently mounted public website files."""
    result = await restore_service.unmount_public_website_files()
    return result


@router.get("/backups/public-website-mount-status",
            summary="Get public website mount status")
async def get_pw_mount_status_endpoint(
    current_user: User = Depends(get_current_active_user)
):
    """Get current public website mount status."""
    return get_pw_mount_status()
```

#### 4.4 New Endpoint: List Public Website Files (Paginated)

```python
@router.get("/backups/{backup_id}/restore/public-website-files",
            summary="List public website files in backup",
            response_description="Paginated list of files")
async def list_public_website_files_endpoint(
    backup_id: int,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=50, ge=10, le=500, description="Items per page"),
    search: Optional[str] = Query(default=None, description="Filter by filename (case-insensitive)"),
    file_type: Optional[str] = Query(default=None, description="Filter by extension (e.g., 'html', 'css', 'png,jpg,gif')"),
    sort_by: str = Query(default="path", enum=["path", "size", "modified_at"], description="Sort field"),
    sort_order: str = Query(default="asc", enum=["asc", "desc"], description="Sort direction"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List public website files from a mounted backup with pagination, search, and filtering.

    **Prerequisites:**
    - Public website feature must be installed
    - Backup must be mounted first (POST /backups/{id}/mount-public-website)

    **Query Parameters:**
    - page: Page number (default: 1)
    - page_size: Items per page (default: 50, max: 500)
    - search: Filter by filename substring
    - file_type: Filter by extension (comma-separated for multiple)
    - sort_by: Sort field (path, size, modified_at)
    - sort_order: Sort direction (asc, desc)

    **Returns:**
    - files: Array of file objects
    - pagination: Page info (page, page_size, total_count, total_pages, has_next, has_prev)
    """
    # Check if public website is installed
    if not os.path.exists(settings.PUBLIC_WEBSITE_INDICATOR_PATH):
        raise HTTPException(
            status_code=400,
            detail="Public website feature is not installed"
        )

    try:
        result = await restore_service.list_public_website_files(
            backup_id,
            page=page,
            page_size=page_size,
            search=search,
            file_type=file_type,
            sort_by=sort_by,
            sort_order=sort_order
        )

        return {
            "backup_id": backup_id,
            "public_website_installed": True,
            **result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing public website files: {e}")
        raise HTTPException(status_code=500, detail="Failed to list public website files")
```

#### 4.5 New Endpoint: Preview Public Website File

```python
@router.get("/backups/{backup_id}/public-website/{file_path:path}/preview",
            summary="Preview a text file from backup",
            response_description="File content for preview")
async def preview_public_website_file_endpoint(
    backup_id: int,
    file_path: str,
    max_size: int = Query(default=100000, le=500000, description="Max bytes to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Preview a text-based file from the backup without downloading.

    **Supported file types:** HTML, CSS, JS, JSON, TXT, MD, XML, SVG, YAML

    **Prerequisites:**
    - Public website feature must be installed
    - Backup must be mounted first

    **Returns:**
    - file_path: The requested file path
    - content: File content (may be truncated)
    - size: Original file size in bytes
    - truncated: Whether content was truncated
    - mime_type: Detected MIME type
    - syntax: Suggested syntax highlighting language
    """
    if not os.path.exists(settings.PUBLIC_WEBSITE_INDICATOR_PATH):
        raise HTTPException(status_code=400, detail="Public website feature is not installed")

    try:
        result = await restore_service.preview_public_website_file(
            backup_id, file_path, max_size
        )
        return result

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error previewing public website file: {e}")
        raise HTTPException(status_code=500, detail="Failed to preview file")
```

#### 4.6 New Endpoint: Download Public Website File

```python
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
    if not os.path.exists(settings.PUBLIC_WEBSITE_INDICATOR_PATH):
        raise HTTPException(status_code=400, detail="Public website feature is not installed")

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
```

#### 4.7 New Endpoint: Restore Public Website Files

```python
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
    - dry_run: If true, only check what would be affected without making changes

    **Dry run response:**
    - files_to_restore: All files that would be restored
    - files_to_overwrite: Files that exist and would be overwritten
    - new_files: Files that don't exist and would be created

    **Restore response:**
    - restored: List of successfully restored file paths
    - restored_count: Number of files restored
    - skipped: List of files skipped (if overwrite=false and file exists)
    - skipped_count: Number of files skipped
    - errors: List of errors encountered
    - error_count: Number of errors
    """
    if not os.path.exists(settings.PUBLIC_WEBSITE_INDICATOR_PATH):
        raise HTTPException(status_code=400, detail="Public website feature is not installed")

    try:
        if request.dry_run:
            # Dry run - just check what would happen
            result = await restore_service.check_public_website_restore(
                backup_id,
                file_paths=request.file_paths
            )
            return {
                "dry_run": True,
                **result
            }

        # Actual restore
        result = await restore_service.restore_public_website_files(
            backup_id,
            file_paths=request.file_paths,
            overwrite=request.overwrite
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error restoring public website files: {e}")
        raise HTTPException(status_code=500, detail="Failed to restore public website files")
```

#### 4.8 Update get_backup_contents Endpoint

```python
@router.get("/backups/contents/{backup_id}")
async def get_backup_contents(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get detailed contents of a backup."""
    # ... existing code to fetch backup_contents ...

    # Add public website availability flag
    response = {
        "backup_id": backup_id,
        "workflow_count": backup_contents.workflow_count,
        "credential_count": backup_contents.credential_count,
        "config_file_count": backup_contents.config_file_count,
        "public_website_file_count": backup_contents.public_website_file_count or 0,
        "public_website_available": os.path.exists(settings.PUBLIC_WEBSITE_INDICATOR_PATH),
        "workflows_manifest": backup_contents.workflows_manifest,
        "credentials_manifest": backup_contents.credentials_manifest,
        "config_files_manifest": backup_contents.config_files_manifest,
        "database_schema_manifest": backup_contents.database_schema_manifest,
        "public_website_manifest": backup_contents.public_website_manifest,
    }

    return response
```

---

### 5. Frontend Changes

#### 5.1 Directory Structure

```
management/frontend/src/
+-- components/
|   +-- backup-ui/
|       +-- BackupContents.vue              # MODIFY: Add Public Website tab
|       +-- BackupContentsDialog.vue        # MODIFY: Add Public Website tab
|       +-- PublicWebsiteFilesTab.vue       # NEW: File browser with pagination
|       +-- PublicWebsitePreview.vue        # NEW: File preview modal
|       +-- PublicWebsiteRestoreConfirm.vue # NEW: Restore confirmation dialog
|       +-- WorkflowRestoreDialog.vue       # EXISTING (reference)
+-- stores/
|   +-- backups.js                          # MODIFY: Add PW store actions
+-- api/
    +-- backups.js                          # MODIFY: Add PW API calls
```

#### 5.2 Store Updates: backups.js

Add to `useBackupStore` in `management/frontend/src/stores/backups.js`:

```javascript
// =========================================================================
// Public Website Actions
// =========================================================================

async function getPublicWebsiteMountStatus() {
  const response = await api.get('/backups/public-website-mount-status')
  return response.data
}

async function mountPublicWebsiteFiles(backupId) {
  const response = await api.post(`/backups/${backupId}/mount-public-website`)
  return response.data
}

async function unmountPublicWebsiteFiles() {
  const response = await api.post('/backups/unmount-public-website')
  return response.data
}

async function listPublicWebsiteFiles(backupId, params = {}) {
  const response = await api.get(`/backups/${backupId}/restore/public-website-files`, { params })
  return response.data
}

async function previewPublicWebsiteFile(backupId, filePath) {
  const response = await api.get(`/backups/${backupId}/public-website/${encodeURIComponent(filePath)}/preview`)
  return response.data
}

async function downloadPublicWebsiteFile(backupId, filePath) {
  const response = await api.get(
    `/backups/${backupId}/public-website/${encodeURIComponent(filePath)}/download`,
    { responseType: 'blob' }
  )

  // Trigger download
  const filename = filePath.split('/').pop()
  const url = window.URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

async function checkPublicWebsiteRestore(backupId, filePaths = null) {
  const response = await api.post(`/backups/${backupId}/restore/public-website`, {
    file_paths: filePaths,
    dry_run: true
  })
  return response.data
}

async function restorePublicWebsiteFiles(backupId, filePaths = null, overwrite = false) {
  const response = await api.post(`/backups/${backupId}/restore/public-website`, {
    file_paths: filePaths,
    overwrite: overwrite,
    dry_run: false
  })
  return response.data
}

// Export all new actions
return {
  // ... existing exports ...
  getPublicWebsiteMountStatus,
  mountPublicWebsiteFiles,
  unmountPublicWebsiteFiles,
  listPublicWebsiteFiles,
  previewPublicWebsiteFile,
  downloadPublicWebsiteFile,
  checkPublicWebsiteRestore,
  restorePublicWebsiteFiles
}
```

#### 5.3 Component Implementation Notes

See the detailed Vue component implementations in the separate frontend specification document. Key components:

1. **PublicWebsiteFilesTab.vue** - Main file browser with:
   - Mount status banner
   - Search and filter controls
   - Paginated DataTable
   - File actions (preview, download, restore)

2. **PublicWebsitePreview.vue** - Modal for previewing text files with:
   - Syntax highlighting
   - Truncation warning
   - Download button

3. **PublicWebsiteRestoreConfirm.vue** - Confirmation dialog with:
   - Dry-run results display
   - Overwrite warnings
   - File count summaries

---

### 6. Database Migration

#### Alembic Migration Script

```python
"""Add public website fields to backup_contents

Revision ID: add_public_website_backup
Revises: [previous_revision]
Create Date: 2026-01-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = 'add_public_website_backup'
down_revision = '[previous_revision]'  # Replace with actual
branch_labels = None
depends_on = None


def upgrade():
    # Add public_website_file_count column
    op.add_column(
        'backup_contents',
        sa.Column('public_website_file_count', sa.Integer(), nullable=True, default=0)
    )

    # Add public_website_manifest column (JSONB for PostgreSQL)
    op.add_column(
        'backup_contents',
        sa.Column('public_website_manifest', JSONB(), nullable=True)
    )

    # Set default value for existing rows
    op.execute("UPDATE backup_contents SET public_website_file_count = 0 WHERE public_website_file_count IS NULL")


def downgrade():
    op.drop_column('backup_contents', 'public_website_manifest')
    op.drop_column('backup_contents', 'public_website_file_count')
```

---

## Conditional Checks Summary

All public website functionality is conditional based on feature installation:

| Check Location | Method | Purpose |
|----------------|--------|---------|
| Backup Service | `_is_public_website_installed()` | Gate backup of PW volume |
| Restore Service | `os.path.exists(settings.PUBLIC_WEBSITE_INDICATOR_PATH)` | Gate mount/restore operations |
| API Endpoints | Same check at start of each endpoint | Return 400 if not installed |
| API Response | `public_website_available` flag | Tell frontend to show/hide tab |
| Frontend | `v-if="contents.public_website_available"` | Conditionally render tab |

---

## Testing Plan

### 1. Unit Tests

- [ ] `calculate_file_checksum()` returns correct SHA256 hash
- [ ] `capture_public_website_manifest()` correctly captures files with checksums
- [ ] `mount_public_website_files()` extracts archive to temp dir
- [ ] `unmount_public_website_files()` cleans up temp dir
- [ ] `list_public_website_files()` pagination works correctly
- [ ] `list_public_website_files()` search filter works
- [ ] `list_public_website_files()` file type filter works
- [ ] `preview_public_website_file()` returns text content
- [ ] `preview_public_website_file()` rejects binary files
- [ ] `download_public_website_file()` returns file content
- [ ] `check_public_website_restore()` correctly identifies overwrites
- [ ] `restore_public_website_files()` batch restore works
- [ ] Path traversal attacks are blocked in all file operations
- [ ] Race condition lock prevents concurrent restores

### 2. Integration Tests

- [ ] Backup with public website enabled includes files in archive
- [ ] Backup without public website has empty manifest
- [ ] Mount endpoint extracts files correctly
- [ ] List endpoint returns paginated results
- [ ] Preview endpoint works for HTML/CSS/JS files
- [ ] Download endpoint returns correct file with headers
- [ ] Dry-run endpoint correctly identifies existing files
- [ ] Restore endpoint copies files to volume
- [ ] Restore with overwrite=false skips existing files
- [ ] Restore with overwrite=true overwrites files

### 3. Frontend Tests

- [ ] Public Website tab shows only when `public_website_available` is true
- [ ] File table renders correctly with pagination
- [ ] Search filter updates results
- [ ] File type dropdown filters correctly
- [ ] Sort options work correctly
- [ ] Preview modal shows file content
- [ ] Preview modal shows truncation warning for large files
- [ ] Download button triggers file download
- [ ] Restore confirmation shows overwrite warnings
- [ ] Restore completes and shows success toast

### 4. Conditional Behavior Tests

- [ ] API returns 400 if public website not installed
- [ ] Frontend hides tab if `public_website_available` is false
- [ ] Manifest is empty/null for backups created before PW was enabled
- [ ] Old backups without PW files show empty state gracefully

---

## Implementation Order

### Phase 1: Configuration & Database
1. Add settings to `core/config.py`
2. Create Alembic migration
3. Update `BackupContents` model
4. Update Pydantic response schemas

### Phase 2: Backup Service
5. Add `calculate_file_checksum()` helper
6. Add `capture_public_website_manifest()` function
7. Update `run_backup_with_metadata()` to call new function
8. Update `BackupContents` creation to include new fields

### Phase 3: Restore Service
9. Add module-level mount state variables
10. Add `is_public_website_mounted()` helper
11. Add `mount_public_website_files()` method
12. Add `unmount_public_website_files()` method
13. Add `list_public_website_files()` with pagination
14. Add `preview_public_website_file()` method
15. Add `download_public_website_file()` method
16. Add `check_public_website_restore()` dry-run method
17. Add `restore_public_website_files()` with batching and locking

### Phase 4: API Endpoints
18. Add mount/unmount endpoints
19. Add list files endpoint with pagination params
20. Add preview endpoint
21. Add download endpoint
22. Add restore endpoint with dry_run support
23. Update `get_backup_contents` to include availability flag

### Phase 5: Frontend
24. Create `PublicWebsiteFilesTab.vue` component
25. Create `PublicWebsitePreview.vue` component
26. Create `PublicWebsiteRestoreConfirm.vue` component
27. Update `BackupContentsDialog.vue` to include new tab
28. Add store actions for all new API calls

### Phase 6: Testing
29. Write unit tests for all new service methods
30. Write integration tests for API endpoints
31. Manual E2E testing
32. Edge case testing (empty backups, large files, etc.)

---

## Files to Modify Summary

| File | Type | Changes |
|------|------|---------|
| `management/api/core/config.py` | Config | Add volume names, checksum settings |
| `management/api/models/backups.py` | Model | Add 2 columns to BackupContents |
| `management/api/schemas/backups.py` | Schema | Update BackupContentsResponse |
| `management/api/services/backup_service.py` | Service | Add checksum helper, manifest capture |
| `management/api/services/restore_service.py` | Service | Add 8 new methods for mount/list/preview/download/restore |
| `management/api/routers/backups.py` | API | Add 7 new endpoints |
| `management/frontend/src/stores/backups.js` | Store | Add 8 new actions |
| `management/frontend/src/components/backup-ui/BackupContentsDialog.vue` | Component | Add Public Website tab |
| `management/frontend/src/components/backup-ui/PublicWebsiteFilesTab.vue` | Component | NEW - File browser |
| `management/frontend/src/components/backup-ui/PublicWebsitePreview.vue` | Component | NEW - Preview modal |
| `management/frontend/src/components/backup-ui/PublicWebsiteRestoreConfirm.vue` | Component | NEW - Confirm dialog |
| `alembic/versions/xxx_add_public_website_backup.py` | Migration | NEW - Add columns |

---

## Security Considerations

1. **Path Traversal Prevention**
   - All file paths sanitized with `os.path.normpath()`
   - Check for `..` and absolute paths
   - Verify resolved path stays within expected directory using `os.path.abspath()`

2. **File Size Limits**
   - Preview limited to 500KB max
   - Checksum calculation limited to 10MB files
   - Restore timeout of 5 minutes

3. **Permission Checks**
   - All endpoints require authenticated user
   - Consider adding admin-only restriction for restore operations

4. **Race Condition Prevention**
   - Asyncio lock prevents concurrent restore operations
   - Batch processing ensures atomic operations

5. **Resource Cleanup**
   - Temp directories cleaned up in `finally` blocks
   - Mount state cleared on errors
   - Consider idle timeout for auto-unmount

---

## API Endpoint Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/backups/{id}/mount-public-website` | Mount PW files from backup |
| POST | `/backups/unmount-public-website` | Unmount current PW files |
| GET | `/backups/public-website-mount-status` | Get mount status |
| GET | `/backups/{id}/restore/public-website-files` | List files (paginated) |
| GET | `/backups/{id}/public-website/{path}/preview` | Preview text file |
| GET | `/backups/{id}/public-website/{path}/download` | Download file |
| POST | `/backups/{id}/restore/public-website` | Restore files (with dry_run option) |

---

*Document Version: 2.1*
*Created: January 22, 2026*
*Last Updated: January 22, 2026*
*Status: IMPLEMENTED - Pending Integration Testing*

---

## Changelog

### v2.0 (January 22, 2026)
- **Fixed:** Docker volume copy bug - now uses host bind mount for source directory
- **Added:** File-based mounting system separate from database mounting
- **Added:** Asyncio lock to prevent race conditions during restore
- **Added:** Batch processing for restore operations (single Docker container)
- **Changed:** Checksum algorithm from MD5 to SHA256 (configurable)
- **Added:** Configuration file support for volume names and paths
- **Added:** File preview endpoint for text-based files
- **Added:** Dry-run endpoint for restore operation warnings
- **Added:** Pagination, search, and filtering for file listing
- **Added:** Frontend restore confirmation dialog with overwrite warnings
- **Added:** Frontend file preview modal with syntax highlighting
- **Specified:** Exact frontend component locations and structure

### v1.0 (January 22, 2026)
- Initial draft

---

## Implementation Checklist

The following items have been implemented:

### Phase 1: Configuration & Database
- [x] Add settings to `management/api/config.py`:
  - `public_website_volume` (default: "public_web_root")
  - `public_website_checksum_algorithm` (default: "sha256")
  - `public_website_batch_size` (default: 100)
  - `public_website_mount_dir` (default: "/tmp/public_website_restore")
- [x] Create schema migration in `management/api/database.py`:
  - `backup_contents.public_website_file_count` (INTEGER)
  - `backup_contents.public_website_manifest` (JSONB)
- [x] Update `BackupContents` model in `management/api/models/backups.py`
- [x] Update Pydantic schemas in `management/api/schemas/backups.py`:
  - Add `PublicWebsiteFileManifestItem` schema
  - Add fields to `BackupContentsResponse`

### Phase 2: Backup Service
- [x] Add `calculate_file_checksum()` helper function with configurable algorithm
- [x] Update `PUBLIC_WEBSITE_VOLUME` to use settings instead of hardcoded value
- [x] Add `capture_public_website_manifest()` method
- [x] Update `create_complete_archive()` to capture public website manifest
- [x] Update `run_backup_with_metadata()` to store public website metadata

### Phase 3: Restore Service
- [x] Add module-level state variables for public website mounting
- [x] Add `get_public_website_mount_status()` helper function
- [x] Add `mount_public_website_files()` method
- [x] Add `unmount_public_website_files()` method
- [x] Add `is_public_website_mounted()` method
- [x] Add `list_public_website_files()` with pagination and search
- [x] Add `preview_public_website_file()` method
- [x] Add `get_public_website_file_path()` for downloads
- [x] Add `check_public_website_restore()` dry-run method
- [x] Add `restore_public_website_files()` with asyncio lock and batching

### Phase 4: API Endpoints
- [x] POST `/restore/{backup_id}/public-website/mount`
- [x] POST `/restore/public-website/unmount`
- [x] GET `/restore/public-website/status`
- [x] GET `/restore/{backup_id}/public-website/files`
- [x] GET `/restore/{backup_id}/public-website/preview`
- [x] GET `/restore/{backup_id}/public-website/download`
- [x] POST `/restore/{backup_id}/public-website/check`
- [x] POST `/restore/{backup_id}/public-website/restore`

### Phase 5: Frontend
- [x] Add store actions in `management/frontend/src/stores/backups.js`:
  - `publicWebsiteMountStatus`, `publicWebsiteFiles`, `publicWebsitePagination` state
  - `mountPublicWebsiteFiles()`, `unmountPublicWebsiteFiles()`
  - `fetchPublicWebsiteMountStatus()`, `listPublicWebsiteFiles()`
  - `previewPublicWebsiteFile()`, `getPublicWebsiteFileDownloadUrl()`
  - `checkPublicWebsiteRestore()`, `restorePublicWebsiteFiles()`
- [x] Create `PublicWebsiteRestoreDialog.vue` component

### Remaining Work
- [ ] Integration testing with live Docker environment
- [ ] Add component to backup details view for easy access
- [ ] Add documentation for users
