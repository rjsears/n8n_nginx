# System Notifications Revamp - Implementation Plan

## Overview
Complete overhaul of the System Notifications feature to provide comprehensive event monitoring, intelligent alerting, and full control over notification routing.

---

## Phase 1: Database Schema & Models

### New Models Required

#### 1. `SystemNotificationEvent` - Event Type Configuration
```python
class SystemNotificationEvent(Base):
    __tablename__ = "system_notification_events"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), unique=True, nullable=False)  # e.g., 'backup_success', 'container_unhealthy'
    display_name = Column(String(100), nullable=False)
    description = Column(Text)
    icon = Column(String(50))  # Icon name for UI
    category = Column(String(50))  # 'backup', 'container', 'system', 'security'

    # Enable/disable
    enabled = Column(Boolean, default=True)

    # Severity (affects ntfy priority)
    severity = Column(String(20), default='warning')  # 'info', 'warning', 'critical'

    # Frequency settings
    frequency = Column(String(30), default='every_time')  # 'every_time', 'once_per_15m', 'once_per_hour', etc.

    # Rate limiting for "every_time" events
    cooldown_minutes = Column(Integer, default=5)

    # Flapping detection
    flapping_enabled = Column(Boolean, default=True)
    flapping_threshold_count = Column(Integer, default=3)  # Events in window
    flapping_threshold_minutes = Column(Integer, default=10)  # Window size
    flapping_summary_interval = Column(Integer, default=15)  # Minutes between summaries
    notify_on_recovery = Column(Boolean, default=True)

    # Thresholds (JSON for flexibility)
    thresholds = Column(JSONB)  # e.g., {"disk_percent": 90, "memory_percent": 85}

    # Escalation
    escalation_enabled = Column(Boolean, default=False)
    escalation_timeout_minutes = Column(Integer, default=30)

    # Daily digest
    include_in_digest = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
```

#### 2. `SystemNotificationTarget` - Event-to-Channel Mapping
```python
class SystemNotificationTarget(Base):
    __tablename__ = "system_notification_targets"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("system_notification_events.id"))

    # Target can be channel or group
    target_type = Column(String(20))  # 'channel', 'group'
    channel_id = Column(Integer, ForeignKey("notification_services.id"), nullable=True)
    group_id = Column(Integer, ForeignKey("notification_groups.id"), nullable=True)

    # Escalation level (1 = primary, 2 = escalation)
    escalation_level = Column(Integer, default=1)
```

#### 3. `SystemNotificationContainerConfig` - Per-Container Settings
```python
class SystemNotificationContainerConfig(Base):
    __tablename__ = "system_notification_container_configs"

    id = Column(Integer, primary_key=True)
    container_name = Column(String(100), nullable=False, unique=True)

    # Which events to monitor for this container
    monitor_unhealthy = Column(Boolean, default=True)
    monitor_restart = Column(Boolean, default=True)

    # Per-container channel override (optional)
    custom_targets = Column(JSONB)  # Array of channel/group ids
```

#### 4. `SystemNotificationState` - Runtime State Tracking
```python
class SystemNotificationState(Base):
    __tablename__ = "system_notification_state"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False)
    target_id = Column(String(100))  # e.g., container name for per-target tracking

    # Cooldown tracking
    last_sent_at = Column(DateTime(timezone=True))

    # Flapping tracking
    event_count_in_window = Column(Integer, default=0)
    window_start = Column(DateTime(timezone=True))
    is_flapping = Column(Boolean, default=False)
    flapping_started_at = Column(DateTime(timezone=True))
    last_summary_at = Column(DateTime(timezone=True))

    # Unique constraint
    __table_args__ = (UniqueConstraint('event_type', 'target_id'),)
```

#### 5. `SystemNotificationGlobalSettings` - Global Configuration
```python
class SystemNotificationGlobalSettings(Base):
    __tablename__ = "system_notification_global_settings"

    id = Column(Integer, primary_key=True)

    # Maintenance mode
    maintenance_mode = Column(Boolean, default=False)
    maintenance_until = Column(DateTime(timezone=True))

    # Quiet hours
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String(5))  # "22:00"
    quiet_hours_end = Column(String(5))    # "07:00"
    quiet_hours_reduce_priority = Column(Boolean, default=True)  # Reduce vs mute

    # Blackout hours
    blackout_enabled = Column(Boolean, default=False)
    blackout_start = Column(String(5))
    blackout_end = Column(String(5))

    # Global rate limit
    max_notifications_per_hour = Column(Integer, default=50)
    emergency_contact_id = Column(Integer, ForeignKey("notification_services.id"))

    # Daily digest
    digest_enabled = Column(Boolean, default=False)
    digest_time = Column(String(5), default="08:00")  # When to send
    digest_severity_levels = Column(JSONB)  # ["info", "warning"] - which to batch
```

---

## Phase 2: API Endpoints

### New Router: `/api/system-notifications/`

```
GET    /events                    - List all event types with configs
GET    /events/{event_type}       - Get single event config
PUT    /events/{event_type}       - Update event config
POST   /events/{event_type}/test  - Send test notification

GET    /global-settings           - Get global settings
PUT    /global-settings           - Update global settings
POST   /global-settings/mute      - Quick mute (body: {hours: 4})

GET    /containers                - List container monitoring configs
PUT    /containers/{name}         - Update container config

GET    /history                   - Get notification history (paginated)
GET    /state                     - Get current notification states (flapping, etc.)
```

---

## Phase 3: Frontend - Settings View Revamp

### Component Structure

```
SettingsView.vue
└── Notifications Tab
    ├── GlobalNotificationSettings.vue
    │   ├── MaintenanceMode section
    │   ├── QuietHours section
    │   ├── BlackoutHours section
    │   ├── GlobalRateLimit section
    │   └── DailyDigest section
    │
    ├── NotificationEventList.vue
    │   └── NotificationEventItem.vue (collapsible, per event)
    │       ├── Enable/Disable toggle
    │       ├── Severity selector
    │       ├── Frequency selector
    │       ├── Rate limiting (if every_time)
    │       ├── Flapping detection settings
    │       ├── Threshold settings (if applicable)
    │       ├── Target channel/group multi-select
    │       ├── Escalation settings
    │       ├── Test button
    │       └── Last triggered info
    │
    ├── ContainerMonitoringConfig.vue (for container events)
    │   └── Per-container checkboxes with custom target override
    │
    └── NotificationHistoryList.vue
        └── Collapsible history items with full details
```

### UI Wireframe - Event Item Expanded

```
┌────────────────────────────────────────────────────────────────────────────┐
│ ▾ 🔔 Container Restart                                    ● Enabled  L1→L2│
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─ Basic Settings ──────────────────────────────────────────────────────┐ │
│  │  Severity: [⚠️ Warning ▼]                                            │ │
│  │  Frequency: [Every occurrence ▼]                                      │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ ⚡ Rate Limiting (appears when frequency = "Every occurrence") ──────┐ │
│  │                                                                       │ │
│  │  Cooldown: Don't resend for [5] [minutes ▼] after notification       │ │
│  │                                                                       │ │
│  │  ┌─ 🔄 Flapping Detection ─────────────────────────────────────────┐  │ │
│  │  │  [✓] Enable flapping detection                                  │  │ │
│  │  │                                                                 │  │ │
│  │  │  Trigger after [3] events in [10] minutes                      │  │ │
│  │  │                                                                 │  │ │
│  │  │  While flapping:                                               │  │ │
│  │  │    • Suppress individual alerts                                │  │ │
│  │  │    • Send summary every [15] minutes                           │  │ │
│  │  │                                                                 │  │ │
│  │  │  [✓] Notify when stable again                                  │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ 📤 Send To ──────────────────────────────────────────────────────────┐ │
│  │                                                                       │ │
│  │  L1 (Primary):                                                        │ │
│  │  ┌────────────────────────────────────────────────────────────────┐  │ │
│  │  │ [✓] channel:sms_twilio_rjs     [✓] group:devops_team         │  │ │
│  │  │ [ ] channel:ntfy_alerts        [ ] group:on_call             │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                       │ │
│  │  ┌─ 🚨 Escalation ────────────────────────────────────────────────┐  │ │
│  │  │  [✓] Enable escalation                                        │  │ │
│  │  │                                                                │  │ │
│  │  │  Escalate after [30] minutes if not resolved                  │  │ │
│  │  │                                                                │  │ │
│  │  │  ┌─────────────────────────────────────────────────────────┐  │  │ │
│  │  │  │        L1                    L2                         │  │  │ │
│  │  │  │  ┌──────────┐          ┌──────────┐                    │  │  │ │
│  │  │  │  │ DevOps   │ ──30m──▶ │ Sr. Eng  │                    │  │  │ │
│  │  │  │  │ Team     │          │ On-Call  │                    │  │  │ │
│  │  │  │  └──────────┘          └──────────┘                    │  │  │ │
│  │  │  └─────────────────────────────────────────────────────────┘  │  │ │
│  │  │                                                                │  │ │
│  │  │  L2 (Escalation):                                             │  │ │
│  │  │  [Select channel or group ▼]                                   │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ Info ────────────────────────────────────────────────────────────────┐ │
│  │  Last triggered: 2 hours ago (container: redis)                       │ │
│  │  Status: Normal (not flapping)                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  [🧪 Test Notification]                                    [Save Changes] │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### UI Wireframe - Container Unhealthy (Special)

```
┌────────────────────────────────────────────────────────────────────────────┐
│ ▾ 💔 Container Unhealthy                                  ● Enabled  L1→L2│
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ... (same basic/rate limiting settings as above) ...                      │
│                                                                            │
│  ┌─ 📦 Monitored Containers ─────────────────────────────────────────────┐ │
│  │                                                                       │ │
│  │  [Select All] [Select None]                                          │ │
│  │                                                                       │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │ │
│  │  │ Container          │ Monitor │ Custom Targets                   │ │ │
│  │  ├────────────────────┼─────────┼──────────────────────────────────┤ │ │
│  │  │ 🟢 n8n             │  [✓]    │ [Default ▼]                     │ │ │
│  │  │ 🟢 postgres        │  [✓]    │ [Default ▼]                     │ │ │
│  │  │ 🟢 redis           │  [✓]    │ [group:critical_alerts ▼]       │ │ │
│  │  │ 🟢 nginx           │  [ ]    │ -                               │ │ │
│  │  │ 🟢 management-api  │  [✓]    │ [Default ▼]                     │ │ │
│  │  └─────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                       │ │
│  │  💡 "Default" uses the targets configured in "Send To" above         │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 4: Container View Integration

Add notification indicator button to each container card:

```
┌─────────────────────────────────────────┐
│  🟢 n8n                                 │
│  Running • 2.5% CPU • 256MB RAM         │
│                                         │
│  [Logs] [Shell] [Restart]  [🔔]        │ ← Green if monitored
└─────────────────────────────────────────┘
```

- 🔔 (green) = Container is monitored for unhealthy/restart
- 🔕 (gray) = Container is not monitored
- Clicking navigates to Settings → System Notifications with container highlighted

---

## Phase 5: Notification History in Settings

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ▾ 📜 Recent System Notifications                              Last 7 days  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ▸ 🔴 Backup Failed                          Today, 3:45 PM      → DevOps │
│  ▸ 🟢 Container Restart (redis)              Today, 2:30 PM      → DevOps │
│  ▸ 🟢 Backup Success                         Today, 2:00 AM      → DevOps │
│  ▾ 🟡 Disk Space Low                         Yesterday, 11:00 PM → DevOps │
│    ┌────────────────────────────────────────────────────────────────────┐  │
│    │ Event: disk_space_low                                              │  │
│    │ Severity: Warning                                                  │  │
│    │ Triggered: Dec 14, 2025, 11:00:23 PM                              │  │
│    │                                                                    │  │
│    │ Details:                                                           │  │
│    │   Disk Usage: 92%                                                 │  │
│    │   Free Space: 8.2 GB                                              │  │
│    │   Threshold: 90%                                                  │  │
│    │                                                                    │  │
│    │ Sent To:                                                          │  │
│    │   ✓ group:devops_team (via channel:ntfy_alerts)                   │  │
│    │   ✓ channel:sms_twilio_rjs                                        │  │
│    │                                                                    │  │
│    │ Status: Sent successfully                                          │  │
│    └────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  [Load More...]                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 6: Backend Monitoring Service

### Event Types to Implement

| Event Type | Trigger Source | Threshold Support |
|------------|----------------|-------------------|
| `backup_success` | Backup service callback | No |
| `backup_failure` | Backup service callback | No |
| `disk_space_low` | Periodic check (5 min) | Yes (% or GB) |
| `container_unhealthy` | Docker health check polling | No |
| `container_restart` | Docker event stream | No |
| `high_memory` | Periodic check (1 min) | Yes (%) |
| `high_cpu` | Periodic check (1 min) | Yes (%) |
| `certificate_expiring` | Daily check | Yes (days) |
| `security_event` | Auth failure callback | No |
| `update_available` | Daily check | No |

### Monitoring Service Architecture

```python
class SystemNotificationMonitor:
    """Background service for system monitoring and notification dispatch."""

    async def start(self):
        """Start all monitoring tasks."""
        asyncio.create_task(self.monitor_disk_space())
        asyncio.create_task(self.monitor_containers())
        asyncio.create_task(self.monitor_resources())
        asyncio.create_task(self.check_certificates())
        asyncio.create_task(self.process_daily_digest())
        asyncio.create_task(self.check_escalations())

    async def trigger_event(self, event_type: str, target_id: str = None, data: dict = None):
        """
        Main entry point for triggering notifications.
        Handles cooldown, flapping detection, and routing.
        """
        # 1. Check if event is enabled
        # 2. Check maintenance/blackout
        # 3. Check cooldown
        # 4. Check/update flapping state
        # 5. Route to appropriate channels
        # 6. Update state and history
```

---

## Implementation Order

### Week 1: Foundation
1. [ ] Create new database models
2. [ ] Create Alembic migration
3. [ ] Seed default event configurations
4. [ ] Create API endpoints (CRUD)

### Week 2: Frontend - Global & Events
5. [ ] Build GlobalNotificationSettings component
6. [ ] Build NotificationEventItem component (collapsible)
7. [ ] Implement channel/group multi-select
8. [ ] Implement escalation UI with visual diagram

### Week 3: Frontend - Special Cases & History
9. [ ] Build container monitoring UI
10. [ ] Implement notification history list
11. [ ] Add test notification functionality
12. [ ] Container view notification button

### Week 4: Backend Monitoring
13. [ ] Implement notification state tracking
14. [ ] Implement flapping detection logic
15. [ ] Build monitoring service tasks
16. [ ] Implement escalation checker
17. [ ] Implement daily digest

---

## Default Event Configurations

```python
DEFAULT_EVENTS = [
    {
        "event_type": "backup_success",
        "display_name": "Backup Success",
        "category": "backup",
        "icon": "CheckCircleIcon",
        "severity": "info",
        "frequency": "every_time",
        "cooldown_minutes": 0,
        "flapping_enabled": False,
    },
    {
        "event_type": "backup_failure",
        "display_name": "Backup Failure",
        "category": "backup",
        "icon": "XCircleIcon",
        "severity": "critical",
        "frequency": "every_time",
        "cooldown_minutes": 60,
        "flapping_enabled": True,
        "flapping_threshold_count": 2,
        "flapping_threshold_minutes": 60,
    },
    {
        "event_type": "disk_space_low",
        "display_name": "Disk Space Low",
        "category": "system",
        "icon": "CircleStackIcon",
        "severity": "warning",
        "frequency": "once_per_4h",
        "thresholds": {"percent": 90},
    },
    {
        "event_type": "container_unhealthy",
        "display_name": "Container Unhealthy",
        "category": "container",
        "icon": "HeartIcon",
        "severity": "critical",
        "frequency": "every_time",
        "cooldown_minutes": 15,
        "flapping_enabled": True,
    },
    {
        "event_type": "container_restart",
        "display_name": "Container Restart",
        "category": "container",
        "icon": "ArrowPathIcon",
        "severity": "warning",
        "frequency": "every_time",
        "cooldown_minutes": 5,
        "flapping_enabled": True,
        "flapping_threshold_count": 3,
        "flapping_threshold_minutes": 10,
    },
    {
        "event_type": "high_memory",
        "display_name": "High Memory Usage",
        "category": "system",
        "icon": "CpuChipIcon",
        "severity": "warning",
        "frequency": "once_per_hour",
        "thresholds": {"percent": 90},
    },
    {
        "event_type": "high_cpu",
        "display_name": "High CPU Usage",
        "category": "system",
        "icon": "FireIcon",
        "severity": "warning",
        "frequency": "once_per_hour",
        "thresholds": {"percent": 90, "duration_minutes": 5},
    },
    {
        "event_type": "certificate_expiring",
        "display_name": "Certificate Expiring",
        "category": "security",
        "icon": "ShieldCheckIcon",
        "severity": "warning",
        "frequency": "once_per_day",
        "thresholds": {"days": 14},
    },
    {
        "event_type": "security_event",
        "display_name": "Security Event",
        "category": "security",
        "icon": "ShieldExclamationIcon",
        "severity": "critical",
        "frequency": "every_time",
        "cooldown_minutes": 1,
        "flapping_enabled": True,
        "flapping_threshold_count": 5,
        "flapping_threshold_minutes": 5,
    },
]
```

---

## Questions Resolved

1. ✅ Daily digest timing - Configurable (default 8:00 AM)
2. ✅ Escalation - Two levels, configurable timeout
3. ✅ History storage - Unlimited (future DB maintenance feature)
4. ✅ Container button behavior - Navigate + auto-expand/highlight
5. ✅ Per-container channels - Supported with "Default" or custom override
6. ✅ Hysteresis - Cooldown + flapping detection for all "every time" events

---

## Files to Create/Modify

### New Files
- `api/models/system_notifications.py`
- `api/routers/system_notifications.py`
- `api/services/system_notification_service.py`
- `api/services/system_notification_monitor.py`
- `frontend/src/components/settings/GlobalNotificationSettings.vue`
- `frontend/src/components/settings/NotificationEventItem.vue`
- `frontend/src/components/settings/ContainerMonitoringConfig.vue`
- `frontend/src/components/settings/NotificationHistoryList.vue`

### Modified Files
- `api/models/__init__.py` - Import new models
- `api/routers/__init__.py` - Register new router
- `api/main.py` - Start monitoring service
- `frontend/src/views/SettingsView.vue` - Replace notifications tab
- `frontend/src/views/ContainersView.vue` - Add notification button
- `frontend/src/services/api.js` - Add new API methods
