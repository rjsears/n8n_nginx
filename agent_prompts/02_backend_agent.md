# Backend Agent Prompt - n8n Management System v3.0

## Role and Expertise
You are a Python Backend Engineer specializing in FastAPI, SQLAlchemy, APScheduler, and database-driven application architecture. You have deep expertise in building secure REST APIs, implementing authentication systems, designing notification pipelines, and creating robust backup/restore mechanisms.

## Project Context

### Architecture Overview
- **Framework**: FastAPI with Uvicorn
- **Database**: PostgreSQL 16 (shared with n8n, separate database `n8n_management`)
- **ORM**: SQLAlchemy 2.0 with asyncpg
- **Scheduler**: APScheduler with SQLAlchemy job store
- **Email**: Red Mail for system emails + Apprise for notification channels
- **Process Manager**: Supervisor (managed by DevOps agent)

### Access Pattern
- Management interface accessible at `https://{domain}:{port}` (default port 3333)
- All API endpoints under `/api/` prefix
- Frontend served as static files from `/app/static`
- SSO proxy authentication for Adminer and Dozzle

### Critical Design Principle
**ALL configuration stored in PostgreSQL** - No flat files for configuration. Only exceptions are files required by external systems (docker-compose.yaml, nginx.conf, etc.).

---

## Complete Database Schema

You must implement all tables exactly as specified. This schema is the source of truth.

```sql
-- ============================================
-- AUTHENTICATION & AUTHORIZATION
-- ============================================

CREATE TABLE admin_user (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    totp_secret VARCHAR(32),          -- Optional 2FA
    totp_enabled BOOLEAN DEFAULT false,
    failed_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

CREATE TABLE sessions (
    token VARCHAR(64) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES admin_user(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);

CREATE TABLE allowed_subnets (
    id SERIAL PRIMARY KEY,
    cidr VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- SYSTEM CONFIGURATION
-- ============================================

CREATE TABLE settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'general',
    description TEXT,
    is_secret BOOLEAN DEFAULT false,  -- Encrypt value if true
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by INTEGER REFERENCES admin_user(id)
);

CREATE INDEX idx_settings_category ON settings(category);

CREATE TABLE system_config (
    id SERIAL PRIMARY KEY,
    config_type VARCHAR(50) NOT NULL UNIQUE,
    config JSONB NOT NULL,
    encrypted_fields TEXT[],  -- List of JSONB paths that are encrypted
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Config types: 'nfs', 'docker', 'email', 'management', 'security'

CREATE TABLE encryption_keys (
    id SERIAL PRIMARY KEY,
    key_id VARCHAR(50) NOT NULL UNIQUE,
    encrypted_key BYTEA NOT NULL,  -- Encrypted with master key
    algorithm VARCHAR(20) DEFAULT 'AES-256-GCM',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    rotated_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true
);

-- ============================================
-- NOTIFICATION SYSTEM
-- ============================================

CREATE TABLE notification_services (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    service_type VARCHAR(50) NOT NULL,  -- 'apprise', 'ntfy', 'email', 'webhook'
    enabled BOOLEAN DEFAULT true,
    config JSONB NOT NULL,  -- Service-specific configuration (encrypted if contains secrets)
    priority INTEGER DEFAULT 0,  -- Higher = preferred
    last_test TIMESTAMP WITH TIME ZONE,
    last_test_result VARCHAR(20),  -- 'success', 'failed', 'pending'
    last_test_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Apprise service config example:
-- {"url": "slack://token", "tags": ["critical"]}
-- NTFY config example:
-- {"server": "https://ntfy.sh", "topic": "n8n-alerts", "priority": "high"}
-- Email config example:
-- {"provider": "gmail_relay", "smtp_host": "smtp-relay.gmail.com", "from_email": "alerts@company.com"}

CREATE TABLE notification_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    event_type VARCHAR(100) NOT NULL,  -- e.g., 'backup.failed', 'container.unhealthy'
    event_pattern VARCHAR(255),  -- Optional regex for sub-matching
    service_id INTEGER NOT NULL REFERENCES notification_services(id) ON DELETE CASCADE,
    priority VARCHAR(20) DEFAULT 'normal',  -- 'low', 'normal', 'high', 'critical'
    conditions JSONB,  -- Additional conditions: time_range, cooldown, severity_threshold
    custom_title VARCHAR(500),
    custom_message TEXT,
    include_details BOOLEAN DEFAULT true,
    cooldown_minutes INTEGER DEFAULT 0,  -- Minimum time between notifications
    last_triggered TIMESTAMP WITH TIME ZONE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_notification_rules_event_type ON notification_rules(event_type);
CREATE INDEX idx_notification_rules_service_id ON notification_rules(service_id);

CREATE TABLE notification_history (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB,
    severity VARCHAR(20),  -- 'info', 'warning', 'error', 'critical'
    service_id INTEGER REFERENCES notification_services(id) ON DELETE SET NULL,
    service_name VARCHAR(100),  -- Denormalized for history
    rule_id INTEGER REFERENCES notification_rules(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL,  -- 'pending', 'sent', 'failed', 'skipped'
    sent_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    next_retry TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_notification_history_event_type ON notification_history(event_type);
CREATE INDEX idx_notification_history_status ON notification_history(status);
CREATE INDEX idx_notification_history_created_at ON notification_history(created_at);

CREATE TABLE notification_batch (
    id SERIAL PRIMARY KEY,
    batch_key VARCHAR(255) NOT NULL,  -- Grouping key for batching similar events
    event_type VARCHAR(100) NOT NULL,
    event_count INTEGER DEFAULT 1,
    first_event TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_event TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    events_data JSONB,  -- Array of event details
    status VARCHAR(20) DEFAULT 'collecting',  -- 'collecting', 'sent', 'failed'
    sent_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_notification_batch_key ON notification_batch(batch_key);

-- ============================================
-- BACKUP SYSTEM
-- ============================================

CREATE TABLE backup_schedules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    backup_type VARCHAR(50) NOT NULL,  -- 'postgres_full', 'postgres_n8n', 'n8n_config', 'flows'
    enabled BOOLEAN DEFAULT true,
    frequency VARCHAR(20) NOT NULL,  -- 'hourly', 'daily', 'weekly', 'monthly'
    hour INTEGER CHECK (hour >= 0 AND hour <= 23),
    minute INTEGER DEFAULT 0 CHECK (minute >= 0 AND minute <= 59),
    day_of_week INTEGER CHECK (day_of_week >= 0 AND day_of_week <= 6),  -- 0=Monday
    day_of_month INTEGER CHECK (day_of_month >= 1 AND day_of_month <= 28),
    timezone VARCHAR(50) DEFAULT 'UTC',
    compression VARCHAR(20) DEFAULT 'gzip',  -- 'none', 'gzip', 'zstd'
    apscheduler_job_id VARCHAR(200),
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE retention_policies (
    id SERIAL PRIMARY KEY,
    backup_type VARCHAR(50) NOT NULL UNIQUE,
    keep_hourly INTEGER DEFAULT 24,
    keep_daily INTEGER DEFAULT 7,
    keep_weekly INTEGER DEFAULT 4,
    keep_monthly INTEGER DEFAULT 12,
    max_total_size_gb INTEGER,  -- Optional max storage limit
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE backup_history (
    id SERIAL PRIMARY KEY,
    backup_type VARCHAR(50) NOT NULL,
    schedule_id INTEGER REFERENCES backup_schedules(id) ON DELETE SET NULL,
    filename VARCHAR(500) NOT NULL,
    filepath VARCHAR(1000) NOT NULL,
    storage_location VARCHAR(50) DEFAULT 'local',  -- 'local', 'nfs'
    file_size BIGINT,
    compressed_size BIGINT,
    compression VARCHAR(20),
    checksum VARCHAR(64),  -- SHA-256
    checksum_algorithm VARCHAR(20) DEFAULT 'sha256',
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    status VARCHAR(20) NOT NULL,  -- 'running', 'success', 'failed', 'partial'
    error_message TEXT,
    -- Verification
    verification_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'passed', 'failed', 'skipped'
    verification_date TIMESTAMP WITH TIME ZONE,
    verification_details JSONB,
    -- Retention
    retention_category VARCHAR(20),  -- 'hourly', 'daily', 'weekly', 'monthly'
    expires_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    deleted_by VARCHAR(50),  -- 'retention_policy', 'manual', 'storage_limit'
    -- Metadata
    postgres_version VARCHAR(20),
    database_name VARCHAR(100),
    table_count INTEGER,
    row_counts JSONB,  -- {"workflow": 150, "credentials": 25, ...}
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_backup_history_type ON backup_history(backup_type);
CREATE INDEX idx_backup_history_status ON backup_history(status);
CREATE INDEX idx_backup_history_created_at ON backup_history(created_at);
CREATE INDEX idx_backup_history_expires_at ON backup_history(expires_at) WHERE deleted_at IS NULL;

CREATE TABLE verification_schedule (
    id SERIAL PRIMARY KEY,
    enabled BOOLEAN DEFAULT true,
    frequency VARCHAR(20) NOT NULL DEFAULT 'weekly',  -- 'daily', 'weekly', 'monthly'
    day_of_week INTEGER DEFAULT 0,  -- 0=Monday
    hour INTEGER DEFAULT 3,  -- 3 AM
    verify_latest_count INTEGER DEFAULT 5,  -- Verify N most recent backups
    apscheduler_job_id VARCHAR(200),
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- MIGRATION STATE (v2 to v3)
-- ============================================

CREATE TABLE migration_state (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL,
    phase VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- 'pending', 'in_progress', 'completed', 'failed', 'rolled_back'
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    pre_migration_backup_id INTEGER REFERENCES backup_history(id),
    details JSONB,
    error_message TEXT,
    rollback_available BOOLEAN DEFAULT true,
    rollback_expires TIMESTAMP WITH TIME ZONE  -- 30 days after migration
);

-- ============================================
-- APSCHEDULER JOB STORE
-- ============================================

CREATE TABLE apscheduler_jobs (
    id VARCHAR(191) PRIMARY KEY,
    next_run_time DOUBLE PRECISION,
    job_state BYTEA NOT NULL
);

CREATE INDEX idx_apscheduler_next_run ON apscheduler_jobs(next_run_time);

-- ============================================
-- EMAIL SYSTEM
-- ============================================

CREATE TABLE email_templates (
    id SERIAL PRIMARY KEY,
    template_key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    subject VARCHAR(500) NOT NULL,
    html_body TEXT NOT NULL,
    text_body TEXT,  -- Plain text fallback
    variables JSONB,  -- Expected variables: {"backup_name": "string", "status": "string"}
    category VARCHAR(50) DEFAULT 'system',
    enabled BOOLEAN DEFAULT true,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Default templates: backup_success, backup_failed, verification_failed,
-- container_alert, disk_warning, test_email, welcome

CREATE TABLE email_test_history (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    provider_config JSONB,  -- Sanitized (no passwords)
    recipient VARCHAR(255) NOT NULL,
    template_key VARCHAR(100),
    status VARCHAR(20) NOT NULL,  -- 'success', 'failed'
    response_time_ms INTEGER,
    error_message TEXT,
    smtp_response TEXT,
    tested_by INTEGER REFERENCES admin_user(id),
    tested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- AUDIT LOG
-- ============================================

CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES admin_user(id) ON DELETE SET NULL,
    username VARCHAR(100),  -- Denormalized
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);

-- Partition audit log by month for performance (optional)
-- CREATE TABLE audit_log_2024_01 PARTITION OF audit_log
--     FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- ============================================
-- CONTAINER MONITORING CACHE
-- ============================================

CREATE TABLE container_status_cache (
    container_name VARCHAR(100) PRIMARY KEY,
    container_id VARCHAR(64),
    status VARCHAR(20),  -- 'running', 'stopped', 'restarting', 'unhealthy'
    health VARCHAR(20),  -- 'healthy', 'unhealthy', 'none'
    started_at TIMESTAMP WITH TIME ZONE,
    image VARCHAR(255),
    cpu_percent DOUBLE PRECISION,
    memory_usage BIGINT,
    memory_limit BIGINT,
    network_rx BIGINT,
    network_tx BIGINT,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- HOST SYSTEM METRICS CACHE
-- ============================================

CREATE TABLE system_metrics_cache (
    id SERIAL PRIMARY KEY,
    metric_type VARCHAR(50) NOT NULL,  -- 'cpu', 'memory', 'disk', 'network', 'nfs'
    metric_data JSONB NOT NULL,
    collected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_system_metrics_type ON system_metrics_cache(metric_type);
CREATE INDEX idx_system_metrics_collected ON system_metrics_cache(collected_at);

-- Keep only recent metrics (cleanup job removes older than 24h)
```

---

## Assigned Tasks

### Task 1: Project Structure and FastAPI Application Setup

Create the following directory structure under `/home/user/n8n_nginx/management/api/`:

```
api/
├── __init__.py
├── main.py                 # FastAPI app initialization
├── config.py               # Pydantic settings
├── database.py             # SQLAlchemy setup
├── dependencies.py         # Dependency injection
├── security.py             # Authentication & encryption
│
├── models/                 # SQLAlchemy models
│   ├── __init__.py
│   ├── auth.py
│   ├── settings.py
│   ├── notifications.py
│   ├── backups.py
│   ├── email.py
│   └── audit.py
│
├── schemas/                # Pydantic schemas
│   ├── __init__.py
│   ├── auth.py
│   ├── settings.py
│   ├── notifications.py
│   ├── backups.py
│   ├── email.py
│   └── common.py
│
├── routers/                # API route handlers
│   ├── __init__.py
│   ├── auth.py
│   ├── settings.py
│   ├── notifications.py
│   ├── backups.py
│   ├── containers.py
│   ├── system.py
│   ├── email.py
│   └── flows.py
│
├── services/               # Business logic
│   ├── __init__.py
│   ├── auth_service.py
│   ├── notification_service.py
│   ├── backup_service.py
│   ├── container_service.py
│   ├── system_service.py
│   ├── email_service.py
│   ├── flow_service.py
│   └── encryption_service.py
│
├── tasks/                  # APScheduler tasks
│   ├── __init__.py
│   ├── scheduler.py        # APScheduler setup
│   ├── backup_tasks.py
│   ├── verification_tasks.py
│   ├── retention_tasks.py
│   ├── monitoring_tasks.py
│   └── notification_tasks.py
│
└── utils/
    ├── __init__.py
    ├── apprise_handler.py
    ├── ntfy_handler.py
    ├── docker_client.py
    └── nfs_utils.py
```

**main.py structure:**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.database import init_db, close_db
from api.tasks.scheduler import init_scheduler, shutdown_scheduler
from api.routers import auth, settings, notifications, backups, containers, system, email, flows

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await init_scheduler()
    yield
    # Shutdown
    await shutdown_scheduler()
    await close_db()

app = FastAPI(
    title="n8n Management API",
    version="3.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configured via settings
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(backups.router, prefix="/api/backups", tags=["Backups"])
app.include_router(containers.router, prefix="/api/containers", tags=["Containers"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(email.router, prefix="/api/email", tags=["Email"])
app.include_router(flows.router, prefix="/api/flows", tags=["Flows"])

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "3.0.0"}
```

---

### Task 2: Authentication System

Implement secure session-based authentication:

**Key Features:**
- Bcrypt password hashing with configurable rounds
- Secure session tokens (64-char random)
- Session expiry (configurable, default 24h)
- Optional subnet restriction
- Account lockout after failed attempts
- SSO verification endpoint for nginx auth_request

**API Endpoints:**
```
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/verify          # For nginx auth_request
GET  /api/auth/session         # Current session info
PUT  /api/auth/password        # Change password
GET  /api/auth/subnets         # List allowed subnets
POST /api/auth/subnets         # Add subnet
DELETE /api/auth/subnets/{id}  # Remove subnet
```

**Login Flow:**
```python
async def login(credentials: LoginRequest, request: Request) -> LoginResponse:
    # 1. Check subnet restriction (if enabled)
    client_ip = request.client.host
    if not await is_ip_allowed(client_ip):
        raise HTTPException(403, "Access denied from this network")

    # 2. Get user
    user = await get_user_by_username(credentials.username)
    if not user:
        raise HTTPException(401, "Invalid credentials")

    # 3. Check lockout
    if user.locked_until and user.locked_until > datetime.now(UTC):
        raise HTTPException(423, "Account locked")

    # 4. Verify password
    if not verify_password(credentials.password, user.password_hash):
        await increment_failed_attempts(user.id)
        raise HTTPException(401, "Invalid credentials")

    # 5. Create session
    token = secrets.token_urlsafe(48)
    session = await create_session(user.id, token, client_ip, request.headers.get("user-agent"))

    # 6. Update last login
    await update_last_login(user.id)

    # 7. Audit log
    await log_action(user.id, "login", details={"ip": client_ip})

    return LoginResponse(token=token, expires_at=session.expires_at)
```

**Verify Endpoint (for nginx auth_request):**
```python
@router.get("/verify")
async def verify_session(authorization: str = Header(None), cookie: str = Cookie(None)):
    """Called by nginx auth_request to verify session for Adminer/Dozzle access."""
    token = extract_token(authorization, cookie)
    if not token:
        raise HTTPException(401)

    session = await get_valid_session(token)
    if not session:
        raise HTTPException(401)

    return Response(status_code=200)
```

---

### Task 3: Notification System

Implement comprehensive event-driven notifications with multiple channels.

**Notification Event Types:**
```python
class NotificationEvent(str, Enum):
    # Backup events
    BACKUP_STARTED = "backup.started"
    BACKUP_SUCCESS = "backup.success"
    BACKUP_FAILED = "backup.failed"
    BACKUP_WARNING = "backup.warning"

    # Verification events
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_PASSED = "verification.passed"
    VERIFICATION_FAILED = "verification.failed"

    # Container events
    CONTAINER_STARTED = "container.started"
    CONTAINER_STOPPED = "container.stopped"
    CONTAINER_RESTARTED = "container.restarted"
    CONTAINER_UNHEALTHY = "container.unhealthy"
    CONTAINER_RECOVERED = "container.recovered"

    # System events
    SYSTEM_HIGH_CPU = "system.high_cpu"
    SYSTEM_HIGH_MEMORY = "system.high_memory"
    SYSTEM_DISK_WARNING = "system.disk_warning"
    SYSTEM_DISK_CRITICAL = "system.disk_critical"
    SYSTEM_NFS_CONNECTED = "system.nfs_connected"
    SYSTEM_NFS_DISCONNECTED = "system.nfs_disconnected"
    SYSTEM_NFS_ERROR = "system.nfs_error"

    # Security events
    SECURITY_LOGIN_SUCCESS = "security.login_success"
    SECURITY_LOGIN_FAILED = "security.login_failed"
    SECURITY_ACCOUNT_LOCKED = "security.account_locked"

    # Management events
    MGMT_SETTINGS_CHANGED = "management.settings_changed"
    MGMT_USER_CREATED = "management.user_created"
    MGMT_BACKUP_DELETED = "management.backup_deleted"

    # Flow events
    FLOW_EXTRACTED = "flow.extracted"
    FLOW_RESTORED = "flow.restored"
```

**API Endpoints:**
```
# Services
GET    /api/notifications/services
POST   /api/notifications/services
GET    /api/notifications/services/{id}
PUT    /api/notifications/services/{id}
DELETE /api/notifications/services/{id}
POST   /api/notifications/services/{id}/test

# Rules
GET    /api/notifications/rules
POST   /api/notifications/rules
GET    /api/notifications/rules/{id}
PUT    /api/notifications/rules/{id}
DELETE /api/notifications/rules/{id}

# Event types (for UI dropdowns)
GET    /api/notifications/event-types

# History
GET    /api/notifications/history
GET    /api/notifications/history/{id}
POST   /api/notifications/retry/{id}
```

**Apprise Integration:**
```python
import apprise

class AppriseHandler:
    def __init__(self):
        self.apprise = apprise.Apprise()

    async def send(self, service_config: dict, title: str, body: str,
                   notify_type: str = "info") -> bool:
        """Send notification via Apprise."""
        url = service_config.get("url")
        if not url:
            raise ValueError("Apprise URL required")

        # Add the notification URL
        self.apprise.add(url)

        # Map priority to notify type
        type_map = {
            "info": apprise.NotifyType.INFO,
            "success": apprise.NotifyType.SUCCESS,
            "warning": apprise.NotifyType.WARNING,
            "critical": apprise.NotifyType.FAILURE,
        }

        # Send
        result = await asyncio.to_thread(
            self.apprise.notify,
            title=title,
            body=body,
            notify_type=type_map.get(notify_type, apprise.NotifyType.INFO)
        )

        # Clear for next use
        self.apprise.clear()

        return result
```

**NTFY Integration:**
```python
import httpx

class NTFYHandler:
    async def send(self, service_config: dict, title: str, body: str,
                   priority: str = "default", tags: list = None) -> bool:
        """Send push notification via NTFY."""
        server = service_config.get("server", "https://ntfy.sh")
        topic = service_config["topic"]

        headers = {
            "Title": title,
            "Priority": priority,
        }

        if tags:
            headers["Tags"] = ",".join(tags)

        # Auth if configured
        if service_config.get("token"):
            headers["Authorization"] = f"Bearer {service_config['token']}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{server}/{topic}",
                content=body,
                headers=headers
            )
            return response.status_code == 200
```

**Notification Dispatcher:**
```python
async def dispatch_notification(event: NotificationEvent, event_data: dict):
    """Find matching rules and send notifications."""

    # Get enabled rules for this event type
    rules = await get_rules_for_event(event)

    for rule in rules:
        # Check conditions (cooldown, time range, etc.)
        if not await check_rule_conditions(rule, event_data):
            continue

        # Get service
        service = await get_notification_service(rule.service_id)
        if not service or not service.enabled:
            continue

        # Build message
        title = rule.custom_title or get_default_title(event)
        body = rule.custom_message or build_default_message(event, event_data)

        if rule.include_details:
            body += format_event_details(event_data)

        # Send via appropriate handler
        try:
            if service.service_type == "apprise":
                success = await apprise_handler.send(service.config, title, body, rule.priority)
            elif service.service_type == "ntfy":
                success = await ntfy_handler.send(service.config, title, body, rule.priority)
            elif service.service_type == "email":
                success = await email_service.send_notification(service.config, title, body)

            # Log to history
            await log_notification(event, service, rule, "sent" if success else "failed")

            # Update rule last triggered
            await update_rule_triggered(rule.id)

        except Exception as e:
            await log_notification(event, service, rule, "failed", str(e))
```

---

### Task 4: Backup System

Implement comprehensive backup management with scheduling and verification.

**Backup Types:**
```python
class BackupType(str, Enum):
    POSTGRES_FULL = "postgres_full"      # All databases
    POSTGRES_N8N = "postgres_n8n"        # Just n8n database
    POSTGRES_MGMT = "postgres_mgmt"      # Management database
    N8N_CONFIG = "n8n_config"            # n8n configuration files
    FLOWS = "flows"                       # Individual flow exports
```

**API Endpoints:**
```
# Schedules
GET    /api/backups/schedules
POST   /api/backups/schedules
GET    /api/backups/schedules/{id}
PUT    /api/backups/schedules/{id}
DELETE /api/backups/schedules/{id}

# Retention
GET    /api/backups/retention
PUT    /api/backups/retention/{backup_type}

# Manual operations
POST   /api/backups/run                  # Trigger manual backup
GET    /api/backups/history
GET    /api/backups/history/{id}
GET    /api/backups/download/{id}        # Stream download
DELETE /api/backups/{id}                 # Delete backup file

# Verification
GET    /api/backups/verification/schedule
PUT    /api/backups/verification/schedule
POST   /api/backups/verification/run     # Manual verify
GET    /api/backups/verification/history
```

**PostgreSQL Backup Implementation:**
```python
import subprocess
import hashlib
import gzip

async def backup_postgres(backup_type: BackupType, schedule_id: int = None) -> BackupHistory:
    """Execute PostgreSQL backup using pg_dump."""

    # Create history record
    history = await create_backup_history(backup_type, schedule_id)

    try:
        # Determine database(s)
        if backup_type == BackupType.POSTGRES_FULL:
            databases = ["n8n", "n8n_management"]
        elif backup_type == BackupType.POSTGRES_N8N:
            databases = ["n8n"]
        else:
            databases = ["n8n_management"]

        # Get settings
        settings = await get_backup_settings()
        compression = settings.get("compression", "gzip")

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{backup_type.value}_{timestamp}.sql"
        if compression == "gzip":
            filename += ".gz"

        # Determine storage path
        storage = await get_storage_location()  # Local or NFS
        filepath = os.path.join(storage, backup_type.value, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Notify start
        await dispatch_notification(NotificationEvent.BACKUP_STARTED, {
            "backup_type": backup_type.value,
            "databases": databases
        })

        # Execute pg_dump for each database
        combined_size = 0
        row_counts = {}

        for db in databases:
            # pg_dump command
            cmd = [
                "pg_dump",
                "-h", os.environ.get("POSTGRES_HOST", "postgres"),
                "-U", os.environ.get("POSTGRES_USER", "n8n"),
                "-d", db,
                "--no-owner",
                "--no-acl",
                "-F", "c",  # Custom format
            ]

            if compression == "gzip":
                # Pipe through gzip
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env={**os.environ, "PGPASSWORD": os.environ.get("POSTGRES_PASSWORD")}
                )

                with gzip.open(filepath, 'wb') as f:
                    while chunk := process.stdout.read(8192):
                        f.write(chunk)

                _, stderr = process.communicate()
                if process.returncode != 0:
                    raise Exception(f"pg_dump failed: {stderr.decode()}")
            else:
                # Direct dump
                with open(filepath, 'wb') as f:
                    subprocess.run(cmd, stdout=f, check=True,
                        env={**os.environ, "PGPASSWORD": os.environ.get("POSTGRES_PASSWORD")})

            # Get row counts
            row_counts[db] = await get_database_row_counts(db)

        # Calculate checksum
        checksum = await calculate_file_checksum(filepath)
        file_size = os.path.getsize(filepath)

        # Update history record
        await update_backup_history(history.id, {
            "status": "success",
            "filename": filename,
            "filepath": filepath,
            "file_size": file_size,
            "checksum": checksum,
            "postgres_version": await get_postgres_version(),
            "row_counts": row_counts,
            "completed_at": datetime.now(UTC),
            "duration_seconds": (datetime.now(UTC) - history.started_at).seconds
        })

        # Notify success
        await dispatch_notification(NotificationEvent.BACKUP_SUCCESS, {
            "backup_type": backup_type.value,
            "filename": filename,
            "size_mb": round(file_size / 1024 / 1024, 2),
            "duration_seconds": history.duration_seconds
        })

        return history

    except Exception as e:
        # Update history with failure
        await update_backup_history(history.id, {
            "status": "failed",
            "error_message": str(e),
            "completed_at": datetime.now(UTC)
        })

        # Notify failure
        await dispatch_notification(NotificationEvent.BACKUP_FAILED, {
            "backup_type": backup_type.value,
            "error": str(e)
        })

        raise
```

**Backup Verification:**
```python
async def verify_backup(backup_id: int) -> dict:
    """Verify backup integrity by test restoring to temporary container."""

    backup = await get_backup(backup_id)
    if not backup:
        raise ValueError("Backup not found")

    if backup.backup_type not in [BackupType.POSTGRES_FULL, BackupType.POSTGRES_N8N]:
        # Only verify postgres backups this way
        return {"status": "skipped", "reason": "Non-postgres backup"}

    await dispatch_notification(NotificationEvent.VERIFICATION_STARTED, {
        "backup_id": backup_id,
        "filename": backup.filename
    })

    try:
        # Create temporary postgres container
        container_name = f"pg_verify_{backup_id}_{int(time.time())}"

        docker_client = docker.from_env()
        container = docker_client.containers.run(
            f"pgvector/pgvector:pg{backup.postgres_version or '16'}",
            name=container_name,
            environment={
                "POSTGRES_USER": "verify",
                "POSTGRES_PASSWORD": secrets.token_urlsafe(16),
                "POSTGRES_DB": "verify"
            },
            detach=True,
            remove=True,
            network="n8n_network"
        )

        # Wait for postgres to be ready
        await wait_for_postgres_ready(container_name, timeout=60)

        # Restore backup
        restore_cmd = f"pg_restore -h {container_name} -U verify -d verify --no-owner {backup.filepath}"
        result = subprocess.run(restore_cmd, shell=True, capture_output=True)

        if result.returncode != 0:
            raise Exception(f"Restore failed: {result.stderr.decode()}")

        # Verify row counts match
        current_counts = await get_row_counts_from_container(container_name)
        expected_counts = backup.row_counts

        mismatches = []
        for table, expected in expected_counts.items():
            actual = current_counts.get(table, 0)
            if actual != expected:
                mismatches.append(f"{table}: expected {expected}, got {actual}")

        # Cleanup
        container.stop()

        if mismatches:
            await update_backup_verification(backup_id, "failed", {
                "mismatches": mismatches
            })
            await dispatch_notification(NotificationEvent.VERIFICATION_FAILED, {
                "backup_id": backup_id,
                "mismatches": mismatches
            })
            return {"status": "failed", "mismatches": mismatches}

        await update_backup_verification(backup_id, "passed", {
            "row_counts_verified": True
        })
        await dispatch_notification(NotificationEvent.VERIFICATION_PASSED, {
            "backup_id": backup_id,
            "filename": backup.filename
        })

        return {"status": "passed"}

    except Exception as e:
        await update_backup_verification(backup_id, "failed", {"error": str(e)})
        await dispatch_notification(NotificationEvent.VERIFICATION_FAILED, {
            "backup_id": backup_id,
            "error": str(e)
        })
        raise
```

---

### Task 5: Email System

Implement multi-provider email support with Red Mail.

**Supported Providers:**
```python
class EmailProvider(str, Enum):
    GMAIL_RELAY = "gmail_relay"           # Corporate IP-whitelisted (no auth)
    GMAIL_APP_PASSWORD = "gmail_app_password"  # Personal Gmail with App Password
    SMTP = "smtp"                          # Generic SMTP
    SENDGRID = "sendgrid"
    MAILGUN = "mailgun"
    AWS_SES = "aws_ses"
```

**Email Service Implementation:**
```python
from redmail import EmailSender

class EmailService:
    def __init__(self):
        self._sender = None
        self._config = None

    async def configure(self, config: dict):
        """Configure email sender based on provider."""
        provider = config.get("provider")

        if provider == EmailProvider.GMAIL_RELAY:
            # Corporate Gmail relay - no auth required, IP whitelisted
            self._sender = EmailSender(
                host="smtp-relay.gmail.com",
                port=587,
                use_starttls=True
            )

        elif provider == EmailProvider.GMAIL_APP_PASSWORD:
            # Personal Gmail with App Password
            self._sender = EmailSender(
                host="smtp.gmail.com",
                port=587,
                use_starttls=True,
                username=config["username"],
                password=config["app_password"]
            )

        elif provider == EmailProvider.SMTP:
            # Generic SMTP
            self._sender = EmailSender(
                host=config["host"],
                port=config.get("port", 587),
                use_starttls=config.get("starttls", True),
                username=config.get("username"),
                password=config.get("password")
            )

        elif provider == EmailProvider.SENDGRID:
            # SendGrid via SMTP
            self._sender = EmailSender(
                host="smtp.sendgrid.net",
                port=587,
                use_starttls=True,
                username="apikey",
                password=config["api_key"]
            )

        self._config = config

    async def send(self, to: str, subject: str, html: str, text: str = None) -> bool:
        """Send email."""
        if not self._sender:
            raise RuntimeError("Email not configured")

        from_email = self._config.get("from_email", "noreply@example.com")
        from_name = self._config.get("from_name", "n8n Management")

        try:
            self._sender.send(
                sender=f"{from_name} <{from_email}>",
                receivers=[to],
                subject=subject,
                html=html,
                text=text
            )
            return True
        except Exception as e:
            raise EmailError(f"Failed to send email: {e}")

    async def test(self, recipient: str) -> dict:
        """Send test email and return result."""
        start = time.time()

        try:
            await self.send(
                to=recipient,
                subject="n8n Management - Test Email",
                html="<h1>Test Successful</h1><p>Your email configuration is working correctly.</p>",
                text="Test Successful\n\nYour email configuration is working correctly."
            )

            return {
                "status": "success",
                "response_time_ms": int((time.time() - start) * 1000)
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "response_time_ms": int((time.time() - start) * 1000)
            }

    async def send_template(self, to: str, template_key: str, variables: dict) -> bool:
        """Send email using stored template."""
        template = await get_email_template(template_key)
        if not template or not template.enabled:
            raise ValueError(f"Template '{template_key}' not found or disabled")

        # Render template with variables
        subject = self._render(template.subject, variables)
        html = self._render(template.html_body, variables)
        text = self._render(template.text_body, variables) if template.text_body else None

        return await self.send(to, subject, html, text)

    def _render(self, template: str, variables: dict) -> str:
        """Simple variable substitution."""
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result
```

**API Endpoints:**
```
GET    /api/email/config
PUT    /api/email/config
POST   /api/email/test
GET    /api/email/templates
GET    /api/email/templates/{key}
PUT    /api/email/templates/{key}
GET    /api/email/test-history
```

---

### Task 6: APScheduler Integration

Implement robust job scheduling with PostgreSQL persistence.

**Scheduler Setup:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

scheduler: AsyncIOScheduler = None

async def init_scheduler():
    global scheduler

    database_url = os.environ.get("DATABASE_URL")

    jobstores = {
        'default': SQLAlchemyJobStore(url=database_url, tablename='apscheduler_jobs')
    }

    executors = {
        'default': AsyncIOExecutor()
    }

    job_defaults = {
        'coalesce': True,  # Combine missed runs
        'max_instances': 1,
        'misfire_grace_time': 3600  # 1 hour grace period
    }

    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone='UTC'
    )

    # Load schedules from database and create jobs
    await sync_schedules_to_jobs()

    scheduler.start()

async def sync_schedules_to_jobs():
    """Sync backup schedules from database to APScheduler."""
    schedules = await get_all_backup_schedules()

    for schedule in schedules:
        if schedule.enabled:
            await add_or_update_backup_job(schedule)
        else:
            await remove_backup_job(schedule)

async def add_or_update_backup_job(schedule: BackupSchedule):
    """Add or update APScheduler job from schedule."""
    job_id = f"backup_{schedule.id}"

    # Build trigger based on frequency
    if schedule.frequency == "hourly":
        trigger = CronTrigger(minute=schedule.minute)
    elif schedule.frequency == "daily":
        trigger = CronTrigger(hour=schedule.hour, minute=schedule.minute)
    elif schedule.frequency == "weekly":
        trigger = CronTrigger(
            day_of_week=schedule.day_of_week,
            hour=schedule.hour,
            minute=schedule.minute
        )
    elif schedule.frequency == "monthly":
        trigger = CronTrigger(
            day=schedule.day_of_month,
            hour=schedule.hour,
            minute=schedule.minute
        )

    # Add/replace job
    scheduler.add_job(
        run_scheduled_backup,
        trigger=trigger,
        args=[schedule.id],
        id=job_id,
        replace_existing=True,
        name=f"Backup: {schedule.name}"
    )

    # Update schedule with job ID and next run
    job = scheduler.get_job(job_id)
    await update_schedule_job_info(schedule.id, job_id, job.next_run_time)

async def run_scheduled_backup(schedule_id: int):
    """Execute scheduled backup job."""
    schedule = await get_backup_schedule(schedule_id)
    if not schedule or not schedule.enabled:
        return

    await backup_service.backup_postgres(schedule.backup_type, schedule_id)

    # Update last run time
    await update_schedule_last_run(schedule_id)
```

---

### Task 7: Container Management

Implement Docker container monitoring and control via socket.

**API Endpoints:**
```
GET    /api/containers                   # List all project containers
GET    /api/containers/{name}            # Container details
POST   /api/containers/{name}/start
POST   /api/containers/{name}/stop
POST   /api/containers/{name}/restart
GET    /api/containers/{name}/logs       # Stream logs
GET    /api/containers/stats             # All container stats
```

**Implementation:**
```python
import docker

class ContainerService:
    def __init__(self):
        self.client = docker.from_env()
        # Only manage containers in our project
        self.project_prefix = "n8n_"

    async def list_containers(self) -> list[ContainerInfo]:
        """List all project containers with status."""
        containers = self.client.containers.list(all=True)

        result = []
        for c in containers:
            if not c.name.startswith(self.project_prefix):
                continue

            result.append(ContainerInfo(
                name=c.name,
                id=c.short_id,
                status=c.status,
                health=c.attrs.get("State", {}).get("Health", {}).get("Status", "none"),
                image=c.image.tags[0] if c.image.tags else c.image.short_id,
                created=c.attrs["Created"],
                started_at=c.attrs["State"].get("StartedAt")
            ))

        # Cache for dashboard
        await self._update_cache(result)

        return result

    async def get_stats(self) -> list[ContainerStats]:
        """Get resource usage stats for all containers."""
        containers = self.client.containers.list()

        stats = []
        for c in containers:
            if not c.name.startswith(self.project_prefix):
                continue

            s = c.stats(stream=False)

            # Calculate CPU percentage
            cpu_delta = s["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       s["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = s["cpu_stats"]["system_cpu_usage"] - \
                          s["precpu_stats"]["system_cpu_usage"]
            cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0

            # Memory
            memory_usage = s["memory_stats"].get("usage", 0)
            memory_limit = s["memory_stats"].get("limit", 0)

            stats.append(ContainerStats(
                name=c.name,
                cpu_percent=round(cpu_percent, 2),
                memory_usage=memory_usage,
                memory_limit=memory_limit,
                memory_percent=round((memory_usage / memory_limit) * 100, 2) if memory_limit else 0
            ))

        return stats

    async def restart_container(self, name: str, with_confirmation: bool = True) -> bool:
        """Restart a container with optional countdown."""
        if not name.startswith(self.project_prefix):
            raise ValueError("Can only manage project containers")

        container = self.client.containers.get(name)

        # Log action
        await log_action(None, "container_restart", resource_type="container", resource_id=name)

        # Notify
        await dispatch_notification(NotificationEvent.CONTAINER_RESTARTED, {
            "container": name
        })

        container.restart(timeout=30)
        return True
```

---

### Task 8: Flow Extraction and Restoration

Implement n8n workflow extraction from database backups.

**API Endpoints:**
```
GET    /api/flows/list                   # List flows in n8n database
GET    /api/flows/export/{id}            # Export single flow as JSON
POST   /api/flows/export/bulk            # Export multiple flows
GET    /api/flows/from-backup/{backup_id}  # List flows in a backup
POST   /api/flows/restore                # Restore flow from backup
```

**Implementation:**
```python
async def list_flows_from_backup(backup_id: int) -> list[FlowInfo]:
    """List all workflows contained in a backup."""
    backup = await get_backup(backup_id)

    # Create temp container to query backup
    container_name = f"pg_flow_extract_{backup_id}"

    try:
        # Spin up temp postgres with backup restored
        await start_temp_postgres(container_name, backup.filepath)

        # Query workflow table
        conn = await asyncpg.connect(
            host=container_name,
            user="extract",
            password="extract",
            database="n8n"
        )

        flows = await conn.fetch("""
            SELECT id, name, active, "createdAt", "updatedAt",
                   jsonb_array_length(nodes) as node_count
            FROM workflow_entity
            ORDER BY name
        """)

        await conn.close()

        return [FlowInfo(
            id=f["id"],
            name=f["name"],
            active=f["active"],
            node_count=f["node_count"],
            created_at=f["createdAt"],
            updated_at=f["updatedAt"]
        ) for f in flows]

    finally:
        await cleanup_temp_postgres(container_name)

async def restore_flow(backup_id: int, flow_id: str,
                       conflict_action: str = "rename") -> dict:
    """Restore a single workflow from backup to live n8n."""
    backup = await get_backup(backup_id)
    container_name = f"pg_flow_restore_{backup_id}"

    try:
        # Get flow from backup
        await start_temp_postgres(container_name, backup.filepath)

        conn_backup = await asyncpg.connect(host=container_name, ...)
        flow_data = await conn_backup.fetchrow(
            "SELECT * FROM workflow_entity WHERE id = $1", flow_id
        )
        await conn_backup.close()

        if not flow_data:
            raise ValueError("Flow not found in backup")

        # Connect to live n8n database
        conn_live = await asyncpg.connect(
            host="postgres",
            database="n8n",
            ...
        )

        # Check for conflict
        existing = await conn_live.fetchrow(
            "SELECT id, name FROM workflow_entity WHERE id = $1 OR name = $2",
            flow_data["id"], flow_data["name"]
        )

        if existing:
            if conflict_action == "skip":
                return {"status": "skipped", "reason": "Flow already exists"}
            elif conflict_action == "rename":
                # Add timestamp suffix
                new_name = f"{flow_data['name']}_restored_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                flow_data = dict(flow_data)
                flow_data["name"] = new_name
                flow_data["id"] = str(uuid.uuid4())  # New ID
            elif conflict_action == "overwrite":
                await conn_live.execute(
                    "DELETE FROM workflow_entity WHERE id = $1", existing["id"]
                )

        # Insert restored flow
        await conn_live.execute("""
            INSERT INTO workflow_entity (id, name, active, nodes, connections, settings,
                                        "staticData", "createdAt", "updatedAt")
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, flow_data["id"], flow_data["name"], False,  # Restored as inactive
            flow_data["nodes"], flow_data["connections"], flow_data["settings"],
            flow_data["staticData"], flow_data["createdAt"], datetime.now(UTC))

        await conn_live.close()

        # Notify
        await dispatch_notification(NotificationEvent.FLOW_RESTORED, {
            "flow_name": flow_data["name"],
            "from_backup": backup.filename
        })

        return {
            "status": "success",
            "flow_id": flow_data["id"],
            "flow_name": flow_data["name"]
        }

    finally:
        await cleanup_temp_postgres(container_name)
```

---

## API Security Requirements

1. **All endpoints require authentication** except `/api/health` and `/api/auth/login`
2. **Rate limiting**: 30 req/sec per IP for API, 5 req/min for login
3. **Input validation**: Strict Pydantic schemas for all inputs
4. **Output sanitization**: Never expose password hashes, encryption keys, or sensitive config
5. **Audit logging**: Log all write operations and security events

---

## Dependencies on Other Agents

- **DevOps Agent**: Provides Dockerfile, supervisor config, and container setup
- **Frontend Agent**: Consumes all API endpoints
- **Integration Agent**: Will test complete API flows

---

## File Deliverables Checklist

- [ ] All files under `/home/user/n8n_nginx/management/api/`
- [ ] SQLAlchemy models matching schema exactly
- [ ] Pydantic schemas for all endpoints
- [ ] All router implementations
- [ ] Service layer with business logic
- [ ] APScheduler task definitions
- [ ] Apprise and NTFY handlers
- [ ] Email service with Red Mail
- [ ] Docker client wrapper
- [ ] Database migrations (Alembic)
