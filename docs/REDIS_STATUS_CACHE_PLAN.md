# Redis Status Cache Implementation

> **Status: ✅ IMPLEMENTED** (January 21, 2026)
>
> This feature has been fully implemented and merged. This document is retained for architectural reference.

## Overview

This document describes the `n8n_status` container that continuously polls system data and caches it in Redis, eliminating slow tab load times caused by container spawning and external API calls.

**Original Branch:** `feature/redis-status-cache`
**Merged to:** `refactor/frontend-optimization-v2`
**Implementation Date:** January 20-21, 2026

---

## Problem Statement

Several tabs in the management UI take 2-8 seconds to load because the backend:

1. **Spawns Docker containers** to collect host-level data (Network, Health tabs)
2. **Makes multiple Docker API calls** to get container stats (Containers view)
3. **Calls external APIs** (Cloudflare, Tailscale, NTFY)

### Current Architecture (Slow)

```
User clicks "Network" tab
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  API receives request                                        │
│  └─▶ Spawns Alpine container with host networking           │
│      └─▶ Runs: hostname, ip addr, ip route, cat resolv.conf │
│          └─▶ Parses output                                  │
│              └─▶ Cleans up container                        │
│                  └─▶ Returns response                       │
│                                                             │
│  Total time: 2-5 seconds                                    │
└─────────────────────────────────────────────────────────────┘
```

### Proposed Architecture (Fast)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Docker Compose Stack                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────┐    ┌──────────────────────┐                      │
│  │   n8n_status         │    │   n8n_redis          │                      │
│  │   (Python service)   │───▶│   (Redis 7.x)        │                      │
│  │   network_mode: host │    │   Port: 6379         │                      │
│  │   Poll every 5-30s   │    │   Persistence: RDB   │                      │
│  └──────────────────────┘    └──────────┬───────────┘                      │
│                                         │                                   │
│                                         │ reads (< 5ms)                     │
│                                         ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │   n8n_management (existing)                                          │  │
│  │   - API reads from Redis (fast)                                      │  │
│  │   - Fallback to direct collection if Redis unavailable               │  │
│  │   - "Force refresh" triggers immediate poll                          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

User clicks "Network" tab
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  API receives request                                        │
│  └─▶ Redis GET system:network                               │
│      └─▶ Returns cached JSON                                │
│                                                             │
│  Total time: < 50ms                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Tabs Analysis: What Would Benefit from Caching

### TIER 1: HIGH IMPACT - Container Spawning Operations

These are the slowest because they spawn Docker containers to collect data.

| Tab/View | Endpoint | Current Behavior | Est. Time | Redis Benefit |
|----------|----------|------------------|-----------|---------------|
| **System → Health** | `GET /api/system/health-full` | Spawns Alpine container with host networking, runs shell commands for CPU/memory/disk | 2-5s | **CRITICAL** |
| **System → Network** | `GET /api/system/network` | Spawns Alpine container, runs `ip addr`, `ip route`, reads `/etc/resolv.conf` | 2-5s | **CRITICAL** |
| **Dashboard** | `GET /api/system/live-metrics` | Spawns Alpine container for real-time CPU/memory | 2-5s | **CRITICAL** |

**Pros:**
- Eliminates container spawn overhead entirely (biggest win)
- Reduces Docker daemon load
- No more orphaned containers on timeout

**Cons:**
- Data is slightly stale (5-10 seconds)
- Need to handle status container failures gracefully

---

### TIER 2: HIGH IMPACT - Docker API Calls

These make multiple Docker API calls which can be slow.

| Tab/View | Endpoint | Current Behavior | Est. Time | Redis Benefit |
|----------|----------|------------------|-----------|---------------|
| **Containers View** | `GET /api/containers/` | Lists all containers via Docker API | 1-2s | **HIGH** |
| **Containers View** | `GET /api/containers/stats` | Gets CPU/memory/network for ALL running containers (parallel with 5s timeout each) | 3-8s | **CRITICAL** |
| **Containers View** | `GET /api/containers/health` | Health check on all project containers | 2-5s | **HIGH** |
| **Dashboard Cards** | Various container status | Same as above | 2-5s | **HIGH** |

**Pros:**
- Container stats are polled constantly - perfect for caching
- Reduces Docker socket API load significantly
- Dashboard loads instantly

**Cons:**
- Stats are inherently time-sensitive (CPU%, memory)
- Need frequent polling (5-10 seconds)

---

### TIER 3: MEDIUM IMPACT - External API Calls

These make HTTP calls to external services.

| Tab/View | Endpoint | Current Behavior | Est. Time | Redis Benefit |
|----------|----------|------------------|-----------|---------------|
| **System → Network** | `GET /api/system/cloudflare` | Calls Cloudflare API for tunnel status | 1-3s | **MEDIUM** |
| **System → Network** | `GET /api/system/tailscale` | Runs `tailscale status --json` | 1-3s | **MEDIUM** |
| **NTFY View** | `GET /api/ntfy/health` | HTTP request to NTFY server | 1-3s | **MEDIUM** |
| **NTFY View** | `GET /api/ntfy/status` | NTFY health + DB queries | 2-5s | **MEDIUM** |
| **Env Config** | `POST /api/env/health-check` | Multi-service health check (Postgres, CF, Tailscale) | 5-20s | **HIGH** |

**Pros:**
- External APIs can be slow/unreliable
- Reduces external API rate limiting concerns
- Consistent response times

**Cons:**
- Cloudflare/Tailscale status can change quickly
- May need "force refresh" option for users

---

### TIER 4: LOWER IMPACT - Database Queries

These are already reasonably fast but could still benefit.

| Tab/View | Endpoint | Current Behavior | Est. Time | Redis Benefit |
|----------|----------|------------------|-----------|---------------|
| **Flows View** | `GET /api/flows/list` | Direct n8n database query | 1-3s | **LOW** |
| **Flows View** | `GET /api/flows/stats` | DB aggregation queries | 1-2s | **LOW** |

**Pros:**
- Reduces n8n database load
- More consistent response times

**Cons:**
- Workflow changes need to invalidate cache
- Adds complexity for minimal gain

---

### NOT RECOMMENDED for Caching

| Tab/View | Endpoint | Reason |
|----------|----------|--------|
| **Backups** | Verify, Mount, Restore | User-initiated actions, not polling |
| **Terminal** | WebSocket | Real-time bidirectional, not cacheable |
| **Settings** | Most endpoints | Rarely accessed, config changes |
| **Notifications** | Test service | User-initiated action |

---

## Priority Order Summary

| Priority | Data Type | Poll Interval | Impact |
|----------|-----------|---------------|--------|
| **P0** | Host metrics (CPU, memory, disk) | 5s | Eliminates container spawning |
| **P0** | Network info (interfaces, gateway, DNS) | 30s | Eliminates container spawning |
| **P0** | Container stats (CPU%, memory%) | 5s | Eliminates slow Docker API calls |
| **P1** | Container list/health | 10s | Faster dashboard |
| **P1** | Cloudflare tunnel status | 15s | Faster network tab |
| **P1** | Tailscale status | 15s | Faster network tab |
| **P2** | NTFY health/status | 30s | Faster NTFY view |
| **P3** | Workflow stats | 60s | Marginal improvement |

---

## Implementation Phases

### PHASE 1: Infrastructure Setup

**Goal:** Add Redis and create the `n8n_status` container skeleton

#### 1.1 Add Redis to docker-compose.yaml

```yaml
n8n_redis:
  image: redis:7-alpine
  container_name: n8n_redis
  restart: unless-stopped
  command: redis-server --appendonly yes --maxmemory 128mb --maxmemory-policy allkeys-lru
  volumes:
    - n8n_redis_data:/data
  networks:
    - n8n_network
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 5s
    retries: 3
```

#### 1.2 Create n8n_status container structure

```
n8n_status/
├── Dockerfile
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point, scheduler
│   ├── config.py            # Configuration from env vars
│   ├── redis_client.py      # Redis connection management
│   └── collectors/
│       ├── __init__.py
│       ├── base.py          # Base collector class
│       ├── host_metrics.py  # CPU, memory, disk (P0)
│       ├── network.py       # Interfaces, gateway, DNS (P0)
│       ├── containers.py    # Docker stats/health (P0)
│       ├── cloudflare.py    # Tunnel status (P1)
│       ├── tailscale.py     # VPN status (P1)
│       └── ntfy.py          # NTFY health (P2)
└── docker-compose.yaml      # For standalone testing
```

#### 1.3 Add n8n_status to main docker-compose.yaml

```yaml
n8n_status:
  build:
    context: ./n8n_status
    dockerfile: Dockerfile
  container_name: n8n_status
  restart: unless-stopped
  network_mode: host  # Required for host network visibility
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
    - /proc:/host/proc:ro
    - /etc/resolv.conf:/host/resolv.conf:ro
  environment:
    - REDIS_HOST=127.0.0.1  # localhost because host network mode
    - REDIS_PORT=6379
    - POLL_INTERVAL_METRICS=5
    - POLL_INTERVAL_NETWORK=30
    - POLL_INTERVAL_CONTAINERS=5
    - POLL_INTERVAL_EXTERNAL=15
  depends_on:
    n8n_redis:
      condition: service_healthy
```

**Deliverables:**
- [x] Redis container added and working
- [x] n8n_status container structure created
- [x] Basic health check endpoint in n8n_status
- [x] Containers start and communicate

---

### PHASE 2: Core Collectors (P0)

**Goal:** Implement the highest-impact collectors

#### 2.1 Host Metrics Collector

```python
# collectors/host_metrics.py
class HostMetricsCollector(BaseCollector):
    """Collect CPU, memory, disk from /proc"""

    key = "system:host_metrics"
    interval = 5  # seconds

    def collect(self) -> dict:
        return {
            "cpu_percent": self._get_cpu_percent(),
            "memory": self._get_memory_info(),
            "disk": self._get_disk_info(),
            "load_average": os.getloadavg(),
            "collected_at": datetime.utcnow().isoformat(),
        }
```

#### 2.2 Network Info Collector

```python
# collectors/network.py
class NetworkCollector(BaseCollector):
    """Collect network interfaces, gateway, DNS"""

    key = "system:network"
    interval = 30  # seconds

    def collect(self) -> dict:
        return {
            "hostname": socket.gethostname(),
            "fqdn": socket.getfqdn(),
            "interfaces": self._get_interfaces(),
            "gateway": self._get_default_gateway(),
            "dns_servers": self._get_dns_servers(),
            "collected_at": datetime.utcnow().isoformat(),
        }
```

#### 2.3 Container Stats Collector

```python
# collectors/containers.py
class ContainerCollector(BaseCollector):
    """Collect Docker container stats and health"""

    key_list = "containers:list"
    key_stats = "containers:stats"
    key_health = "containers:health"
    interval = 5  # seconds

    def collect(self) -> dict:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        # ... collect stats for each
```

**Deliverables:**
- [x] Host metrics collector working
- [x] Network info collector working
- [x] Container stats collector working
- [x] Data visible in Redis (`redis-cli GET system:host_metrics`)

---

### PHASE 3: API Integration

**Goal:** Modify existing API endpoints to read from Redis

#### 3.1 Add Redis client to n8n_management

```python
# api/services/redis_service.py
import redis.asyncio as redis

class RedisService:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )

    async def get_cached(self, key: str) -> Optional[dict]:
        """Get cached data, return None if not available"""
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None

    async def is_healthy(self) -> bool:
        """Check Redis connection"""
        try:
            await self.client.ping()
            return True
        except:
            return False
```

#### 3.2 Update API endpoints with cache-first pattern

```python
# Example: routers/system.py

@router.get("/network")
async def get_network_info(
    force_refresh: bool = False,
    redis: RedisService = Depends(get_redis),
):
    # Try cache first (unless force refresh)
    if not force_refresh:
        cached = await redis.get_cached("system:network")
        if cached:
            return {**cached["data"], "source": "cache", "cached_at": cached["collected_at"]}

    # Fallback to direct collection (existing code)
    return await _collect_network_info_direct()
```

#### 3.3 Update environment config

```python
# api/config.py
class Settings:
    redis_host: str = os.getenv("REDIS_HOST", "n8n_redis")
    redis_port: int = int(os.getenv("REDIS_PORT", 6379))
    redis_enabled: bool = os.getenv("REDIS_ENABLED", "true").lower() == "true"
```

**Deliverables:**
- [x] RedisService created and tested
- [x] `/api/system/network` reads from cache
- [x] `/api/system/health-full` reads from cache
- [x] `/api/containers/stats` reads from cache
- [x] Graceful fallback when Redis unavailable

---

### PHASE 4: External Service Collectors (P1)

**Goal:** Add collectors for external services

#### 4.1 Cloudflare Tunnel Collector

```python
# collectors/cloudflare.py
class CloudflareCollector(BaseCollector):
    key = "system:cloudflare"
    interval = 15

    def collect(self) -> dict:
        # Check cloudflared container logs/status
        # Return tunnel health, connected status
```

#### 4.2 Tailscale Collector

```python
# collectors/tailscale.py
class TailscaleCollector(BaseCollector):
    key = "system:tailscale"
    interval = 15

    def collect(self) -> dict:
        # Run tailscale status --json
        # Return connection status, IP, peers
```

#### 4.3 NTFY Health Collector

```python
# collectors/ntfy.py
class NtfyCollector(BaseCollector):
    key = "services:ntfy"
    interval = 30

    def collect(self) -> dict:
        # HTTP request to NTFY health endpoint
        # Return server status, version
```

**Deliverables:**
- [x] Cloudflare collector working
- [x] Tailscale collector working
- [x] NTFY collector working
- [x] API endpoints updated to use cache

---

### PHASE 5: Frontend Updates

**Goal:** Update frontend to leverage cached data and show freshness

#### 5.1 Add cache metadata to responses

```typescript
// types/api.ts
interface CachedResponse<T> {
  data: T;
  source: 'cache' | 'direct';
  cached_at?: string;
  age_seconds?: number;
}
```

#### 5.2 Update SystemView to show data freshness

```vue
<!-- Show when data was last updated -->
<div class="text-xs text-gray-500" v-if="networkInfo.cached_at">
  Last updated: {{ formatRelativeTime(networkInfo.cached_at) }}
</div>
```

#### 5.3 Add force refresh button

```vue
<button @click="loadNetworkInfo(true)" title="Force refresh">
  <ArrowPathIcon class="h-4 w-4" />
</button>
```

**Deliverables:**
- [x] API responses include cache metadata
- [x] UI shows "last updated" timestamps
- [x] Force refresh buttons work
- [x] Loading states remain appropriate

---

### PHASE 6: Monitoring & Reliability

**Goal:** Ensure the system is observable and reliable

#### 6.1 Add health endpoint to n8n_status

```python
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "collectors": {
            name: {
                "last_run": collector.last_run,
                "last_error": collector.last_error,
                "run_count": collector.run_count,
            }
            for name, collector in collectors.items()
        },
        "redis_connected": redis_client.is_connected(),
    }
```

#### 6.2 Add Redis connection to management health check

```python
# Include Redis status in /api/health
{
    "redis": {
        "connected": true,
        "keys_count": 12,
        "memory_used": "1.2MB",
    }
}
```

#### 6.3 Graceful degradation

- If Redis is down → fall back to direct collection
- If n8n_status is down → fall back to direct collection
- Log warnings but don't fail requests

**Deliverables:**
- [x] n8n_status has /health endpoint
- [x] Management API reports Redis status
- [x] Graceful fallback tested
- [x] Logging/alerting in place

---

## Testing Strategy

### Unit Tests

| Component | Test Cases |
|-----------|------------|
| **Host Metrics Collector** | Parse /proc/stat, /proc/meminfo correctly; Handle missing files; Handle malformed data |
| **Network Collector** | Parse interface list; Extract gateway from route table; Parse resolv.conf |
| **Container Collector** | Handle empty container list; Handle containers without stats; Handle Docker connection failure |
| **Redis Service** | Connection handling; JSON serialization; TTL behavior; Reconnection logic |

### Integration Tests

| Test | Description | Pass Criteria |
|------|-------------|---------------|
| **Redis Write/Read** | n8n_status writes data, management API reads it | Data matches, latency < 10ms |
| **Cache Miss Fallback** | Stop n8n_status, API should fall back to direct collection | API still responds (slower) |
| **Redis Down Fallback** | Stop Redis, API should fall back to direct collection | API still responds (slower) |
| **Force Refresh** | API with `force_refresh=true` bypasses cache | Fresh data returned |
| **Data Freshness** | Check `cached_at` timestamp accuracy | Timestamps within expected range |

### Performance Tests

| Test | Baseline (Current) | Target (With Cache) | How to Measure |
|------|-------------------|---------------------|----------------|
| **System → Network tab load** | 2-5 seconds | < 100ms | Browser DevTools Network tab |
| **System → Health tab load** | 2-5 seconds | < 100ms | Browser DevTools Network tab |
| **Containers page load** | 3-8 seconds | < 100ms | Browser DevTools Network tab |
| **Dashboard initial load** | 3-5 seconds | < 200ms | Browser DevTools Network tab |
| **API `/api/containers/stats`** | 3000-8000ms | < 50ms | `curl -w "%{time_total}"` |

### Manual Testing Checklist

```
PHASE 1 - Infrastructure
[ ] Redis container starts and is healthy
[ ] n8n_status container starts and is healthy
[ ] redis-cli PING returns PONG
[ ] n8n_status /health endpoint responds

PHASE 2 - Core Collectors
[ ] redis-cli GET system:host_metrics returns valid JSON
[ ] redis-cli GET system:network returns valid JSON
[ ] redis-cli GET containers:stats returns valid JSON
[ ] Data refreshes at expected intervals

PHASE 3 - API Integration
[ ] GET /api/system/network returns cached data
[ ] Response includes "source": "cache"
[ ] Response includes "cached_at" timestamp
[ ] force_refresh=true bypasses cache
[ ] Stopping Redis → API still works (slower)

PHASE 4 - External Collectors
[ ] redis-cli GET system:cloudflare returns valid JSON
[ ] redis-cli GET system:tailscale returns valid JSON
[ ] redis-cli GET services:ntfy returns valid JSON

PHASE 5 - Frontend
[ ] Network tab loads instantly
[ ] Health tab loads instantly
[ ] Containers page loads instantly
[ ] "Last updated" timestamp shows correctly
[ ] Force refresh button works
[ ] Data updates when refreshed

PHASE 6 - Reliability
[ ] Stop n8n_status → API falls back gracefully
[ ] Stop Redis → API falls back gracefully
[ ] Restart n8n_status → Collection resumes
[ ] Restart Redis → Connection re-establishes
```

### Load Testing (Optional)

```bash
# Test concurrent requests with cache
ab -n 1000 -c 50 http://localhost:5679/management/api/system/network

# Expected results with cache:
# Requests per second: > 500
# Time per request: < 20ms (mean)

# Compare to current (without cache):
# Requests per second: < 5
# Time per request: > 2000ms (mean)
```

---

## Expected Impact

| Tab | Current Load Time | After Implementation |
|-----|------------------|---------------------|
| System → Health | 2-5 seconds | < 100ms |
| System → Network | 2-5 seconds | < 100ms |
| Containers | 3-8 seconds | < 100ms |
| Dashboard | 3-5 seconds | < 200ms |

## Resource Requirements

### New Containers

| Container | Image | Memory | CPU | Purpose |
|-----------|-------|--------|-----|---------|
| n8n_redis | redis:7-alpine | ~30MB | Minimal | Cache storage |
| n8n_status | python:3.11-slim | ~50MB | Minimal | Data collection |

### Redis Keys

| Key | Update Interval | TTL | Size (est.) |
|-----|-----------------|-----|-------------|
| `system:host_metrics` | 5s | 30s | ~500 bytes |
| `system:network` | 30s | 120s | ~2KB |
| `containers:list` | 10s | 60s | ~5KB |
| `containers:stats` | 5s | 30s | ~10KB |
| `containers:health` | 10s | 60s | ~1KB |
| `system:cloudflare` | 15s | 60s | ~500 bytes |
| `system:tailscale` | 15s | 60s | ~1KB |
| `services:ntfy` | 30s | 120s | ~500 bytes |

**Total Redis memory usage:** < 50KB (well within 128MB limit)

---

## Rollback Plan

If issues arise after deployment:

1. **Disable cache in API**: Set `REDIS_ENABLED=false` in n8n_management environment
2. **Stop n8n_status**: `docker stop n8n_status`
3. **API automatically falls back** to direct collection (current behavior)

No data loss risk - Redis only contains ephemeral cache data.

---

## Future Enhancements

1. **WebSocket push**: Instead of polling from frontend, push updates via WebSocket when data changes
2. **Cache invalidation API**: Allow manual cache invalidation for specific keys
3. **Metrics dashboard**: Show n8n_status collector performance in the UI
4. **Alert on stale data**: Notify if data hasn't been updated in expected timeframe
