<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/system/CacheStatusView.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { cacheApi } from '../../services/api'
import { useNotificationStore } from '../../stores/notifications'
import Card from '../common/Card.vue'
import HeartbeatLoader from '../common/HeartbeatLoader.vue'
import ConfirmDialog from '../common/ConfirmDialog.vue'
import {
  CircleStackIcon,
  ServerIcon,
  ClockIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  TrashIcon,
  KeyIcon,
  ChartBarIcon,
  BoltIcon,
  SignalIcon,
  CpuChipIcon,
  GlobeAltIcon,
  CloudIcon,
  WifiIcon,
  HeartIcon,
  FireIcon,
  DocumentTextIcon,
  EyeIcon,
} from '@heroicons/vue/24/outline'

const notificationStore = useNotificationStore()

// State
const loading = ref(true)
const refreshing = ref(false)
const cacheData = ref(null)
const selectedKey = ref(null)
const keyDetailModal = ref(false)
const keyDetailLoading = ref(false)
const keyDetailData = ref(null)
const deleteDialog = ref({ open: false, keyName: '', loading: false })
const flushDialog = ref({ open: false, loading: false })

// Loading messages
const loadingMessages = [
  'Connecting to Redis...',
  'Gathering cache statistics...',
  'Checking collector status...',
  'Counting all the cached bits...',
  'Inspecting key-value pairs...',
  'Almost done...',
]
const loadingMessageIndex = ref(0)
let loadingInterval = null

// Auto-refresh
let refreshTimer = null
const autoRefresh = ref(true)
const refreshInterval = 30000 // 30 seconds

// Computed
const redisConnected = computed(() => cacheData.value?.redis?.connected || false)
const collectorHealthy = computed(() => cacheData.value?.collector?.healthy || false)
const collectorAvailable = computed(() => cacheData.value?.collector?.available || false)

const hitRatePercent = computed(() => {
  return cacheData.value?.redis?.info?.hit_rate_percent || 0
})

const hitRateColor = computed(() => {
  const rate = hitRatePercent.value
  if (rate >= 80) return 'emerald'
  if (rate >= 50) return 'amber'
  return 'red'
})

const overallStatus = computed(() => {
  if (!redisConnected.value) return 'error'
  if (!collectorAvailable.value) return 'warning'
  if (!collectorHealthy.value) return 'warning'
  return 'healthy'
})

const categoryIcons = {
  'n8n_status': CircleStackIcon,
  'host_metrics': CpuChipIcon,
  'network': GlobeAltIcon,
  'containers': ServerIcon,
  'cloudflare': CloudIcon,
  'tailscale': WifiIcon,
  'ntfy': BoltIcon,
  'other': DocumentTextIcon,
}

const categoryColors = {
  'n8n_status': 'cyan',
  'host_metrics': 'purple',
  'network': 'blue',
  'containers': 'emerald',
  'cloudflare': 'orange',
  'tailscale': 'indigo',
  'ntfy': 'pink',
  'other': 'gray',
}

// Methods
async function loadCacheStatus() {
  loading.value = true
  loadingMessageIndex.value = 0

  loadingInterval = setInterval(() => {
    loadingMessageIndex.value = (loadingMessageIndex.value + 1) % loadingMessages.length
  }, 2000)

  try {
    const response = await cacheApi.getStatus()
    cacheData.value = response.data
  } catch (error) {
    notificationStore.error('Failed to load cache status')
    console.error('Cache status error:', error)
  } finally {
    loading.value = false
    clearInterval(loadingInterval)
  }
}

async function refreshCacheStatus() {
  if (refreshing.value) return
  refreshing.value = true

  try {
    const response = await cacheApi.getStatus()
    cacheData.value = response.data
  } catch (error) {
    notificationStore.error('Failed to refresh cache status')
  } finally {
    refreshing.value = false
  }
}

async function viewKeyDetail(keyName) {
  selectedKey.value = keyName
  keyDetailModal.value = true
  keyDetailLoading.value = true
  keyDetailData.value = null

  try {
    const response = await cacheApi.getKey(keyName)
    keyDetailData.value = response.data
  } catch (error) {
    notificationStore.error('Failed to load key details')
    keyDetailModal.value = false
  } finally {
    keyDetailLoading.value = false
  }
}

function openDeleteDialog(keyName) {
  deleteDialog.value = { open: true, keyName, loading: false }
}

async function confirmDelete() {
  deleteDialog.value.loading = true
  try {
    await cacheApi.deleteKey(deleteDialog.value.keyName)
    notificationStore.success(`Key "${deleteDialog.value.keyName}" deleted`)
    deleteDialog.value.open = false
    keyDetailModal.value = false
    await refreshCacheStatus()
  } catch (error) {
    notificationStore.error('Failed to delete key')
  } finally {
    deleteDialog.value.loading = false
  }
}

function openFlushDialog() {
  flushDialog.value = { open: true, loading: false }
}

async function confirmFlush() {
  flushDialog.value.loading = true
  try {
    await cacheApi.flushCache()
    notificationStore.success('Cache flushed successfully')
    flushDialog.value.open = false
    await refreshCacheStatus()
  } catch (error) {
    notificationStore.error('Failed to flush cache')
  } finally {
    flushDialog.value.loading = false
  }
}

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function formatUptime(seconds) {
  if (!seconds) return '0s'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m ${Math.floor(seconds % 60)}s`
}

function formatTTL(ttl) {
  if (ttl === null || ttl === undefined) return 'No expiry'
  if (ttl <= 0) return 'Expired'
  return formatUptime(ttl)
}

function getCollectorIcon(name) {
  const icons = {
    'host_metrics': CpuChipIcon,
    'network': GlobeAltIcon,
    'containers': ServerIcon,
    'cloudflare': CloudIcon,
    'tailscale': WifiIcon,
    'ntfy': BoltIcon,
  }
  return icons[name] || CircleStackIcon
}

function setupAutoRefresh() {
  if (refreshTimer) clearInterval(refreshTimer)
  if (autoRefresh.value) {
    refreshTimer = setInterval(refreshCacheStatus, refreshInterval)
  }
}

onMounted(() => {
  loadCacheStatus()
  setupAutoRefresh()
})

onUnmounted(() => {
  if (loadingInterval) clearInterval(loadingInterval)
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <div>
    <!-- Loading State -->
    <HeartbeatLoader
      v-if="loading"
      :text="loadingMessages[loadingMessageIndex]"
      color="cyan"
      class="py-16"
    />

    <template v-else>
      <!-- Overall Status Banner -->
      <div
        :class="[
          'rounded-xl p-6 border-2 relative overflow-hidden',
          overallStatus === 'healthy'
            ? 'bg-gradient-to-r from-cyan-500/10 to-cyan-500/5 border-cyan-500/50'
            : overallStatus === 'warning'
              ? 'bg-gradient-to-r from-amber-500/10 to-amber-500/5 border-amber-500/50'
              : 'bg-gradient-to-r from-red-500/10 to-red-500/5 border-red-500/50'
        ]"
      >
        <!-- Animated pulse background -->
        <div
          v-if="overallStatus === 'healthy'"
          class="absolute inset-0 bg-cyan-500/5 animate-pulse"
        ></div>

        <div class="relative flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div
              :class="[
                'p-4 rounded-2xl',
                overallStatus === 'healthy'
                  ? 'bg-cyan-500/20'
                  : overallStatus === 'warning'
                    ? 'bg-amber-500/20'
                    : 'bg-red-500/20'
              ]"
            >
              <CircleStackIcon
                :class="[
                  'h-10 w-10',
                  overallStatus === 'healthy'
                    ? 'text-cyan-500'
                    : overallStatus === 'warning'
                      ? 'text-amber-500'
                      : 'text-red-500'
                ]"
              />
            </div>
            <div>
              <h2 class="text-2xl font-bold text-primary">
                Cache Status:
                <span
                  :class="[
                    overallStatus === 'healthy'
                      ? 'text-cyan-500'
                      : overallStatus === 'warning'
                        ? 'text-amber-500'
                        : 'text-red-500'
                  ]"
                >
                  {{ overallStatus.toUpperCase() }}
                </span>
              </h2>
              <p class="text-secondary mt-1">
                Redis {{ cacheData?.redis?.info?.version || 'N/A' }} •
                {{ cacheData?.cached_data?.total_keys || 0 }} cached keys
              </p>
            </div>
          </div>

          <div class="flex items-center gap-6">
            <!-- Hit Rate Gauge -->
            <div class="text-center">
              <div class="relative w-16 h-16">
                <svg class="w-16 h-16 transform -rotate-90">
                  <circle
                    cx="32"
                    cy="32"
                    r="28"
                    stroke="currentColor"
                    stroke-width="4"
                    fill="none"
                    class="text-gray-200 dark:text-gray-700"
                  />
                  <circle
                    cx="32"
                    cy="32"
                    r="28"
                    stroke="currentColor"
                    stroke-width="4"
                    fill="none"
                    :stroke-dasharray="`${hitRatePercent * 1.76} 176`"
                    stroke-linecap="round"
                    :class="[
                      hitRateColor === 'emerald' ? 'text-emerald-500' :
                      hitRateColor === 'amber' ? 'text-amber-500' : 'text-red-500'
                    ]"
                  />
                </svg>
                <div class="absolute inset-0 flex items-center justify-center">
                  <span class="text-sm font-bold text-primary">{{ hitRatePercent }}%</span>
                </div>
              </div>
              <p class="text-xs text-muted mt-1">Hit Rate</p>
            </div>

            <!-- Counters -->
            <div class="text-center">
              <p class="text-3xl font-bold text-cyan-500">{{ cacheData?.cached_data?.total_keys || 0 }}</p>
              <p class="text-xs text-muted uppercase tracking-wide">Keys</p>
            </div>
            <div class="text-center">
              <p class="text-3xl font-bold text-purple-500">{{ Object.keys(cacheData?.collector?.collectors || {}).length }}</p>
              <p class="text-xs text-muted uppercase tracking-wide">Collectors</p>
            </div>

            <div class="flex gap-2">
              <button
                @click="refreshCacheStatus"
                :disabled="refreshing"
                class="btn-secondary flex items-center gap-2"
              >
                <ArrowPathIcon :class="['h-4 w-4', refreshing ? 'animate-spin' : '']" />
                Refresh
              </button>
              <button
                @click="openFlushDialog"
                class="btn-secondary flex items-center gap-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10"
              >
                <TrashIcon class="h-4 w-4" />
                Flush
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Status Cards Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-6">
        <!-- Redis Connection Card -->
        <Card :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3 mb-4">
              <div class="p-2 rounded-lg bg-red-100 dark:bg-red-500/20">
                <FireIcon class="h-5 w-5 text-red-500" />
              </div>
              <div class="flex-1">
                <h3 class="font-semibold text-primary">Redis Server</h3>
                <p class="text-xs text-muted">{{ cacheData?.redis?.host }}:{{ cacheData?.redis?.port }}</p>
              </div>
              <span
                :class="[
                  'px-2 py-1 rounded-full text-xs font-medium',
                  redisConnected
                    ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                    : 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400'
                ]"
              >
                {{ redisConnected ? 'CONNECTED' : 'DISCONNECTED' }}
              </span>
            </div>

            <div class="space-y-2">
              <div class="flex justify-between items-center text-sm">
                <span class="text-secondary">Version</span>
                <span class="font-medium text-primary">{{ cacheData?.redis?.info?.version || 'N/A' }}</span>
              </div>
              <div class="flex justify-between items-center text-sm">
                <span class="text-secondary">Uptime</span>
                <span class="font-medium text-primary">{{ formatUptime(cacheData?.redis?.info?.uptime_seconds) }}</span>
              </div>
              <div class="flex justify-between items-center text-sm">
                <span class="text-secondary">Memory Used</span>
                <span class="font-medium text-primary">{{ cacheData?.redis?.info?.used_memory_human || 'N/A' }}</span>
              </div>
              <div class="flex justify-between items-center text-sm">
                <span class="text-secondary">Clients</span>
                <span class="font-medium text-primary">{{ cacheData?.redis?.info?.connected_clients || 0 }}</span>
              </div>
              <div class="flex justify-between items-center text-sm">
                <span class="text-secondary">Commands</span>
                <span class="font-medium text-primary">{{ (cacheData?.redis?.info?.total_commands_processed || 0).toLocaleString() }}</span>
              </div>
            </div>

            <!-- Hit Rate Bar -->
            <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <div class="flex justify-between items-center text-sm mb-2">
                <span class="text-secondary">Cache Hit Rate</span>
                <span :class="['font-medium', hitRateColor === 'emerald' ? 'text-emerald-500' : hitRateColor === 'amber' ? 'text-amber-500' : 'text-red-500']">
                  {{ hitRatePercent }}%
                </span>
              </div>
              <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  :class="[
                    'h-full rounded-full transition-all duration-500',
                    hitRateColor === 'emerald' ? 'bg-emerald-500' :
                    hitRateColor === 'amber' ? 'bg-amber-500' : 'bg-red-500'
                  ]"
                  :style="{ width: `${hitRatePercent}%` }"
                ></div>
              </div>
              <div class="flex justify-between text-xs text-muted mt-1">
                <span>Hits: {{ (cacheData?.redis?.info?.keyspace_hits || 0).toLocaleString() }}</span>
                <span>Misses: {{ (cacheData?.redis?.info?.keyspace_misses || 0).toLocaleString() }}</span>
              </div>
            </div>
          </div>
        </Card>

        <!-- Status Collector Card -->
        <Card :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3 mb-4">
              <div class="p-2 rounded-lg bg-cyan-100 dark:bg-cyan-500/20">
                <ServerIcon class="h-5 w-5 text-cyan-500" />
              </div>
              <div class="flex-1">
                <h3 class="font-semibold text-primary">Status Collector</h3>
                <p class="text-xs text-muted">n8n_status service</p>
              </div>
              <span
                :class="[
                  'px-2 py-1 rounded-full text-xs font-medium',
                  collectorHealthy
                    ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                    : collectorAvailable
                      ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400'
                      : 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400'
                ]"
              >
                {{ collectorHealthy ? 'HEALTHY' : collectorAvailable ? 'DEGRADED' : 'OFFLINE' }}
              </span>
            </div>

            <div class="space-y-2">
              <div class="flex justify-between items-center text-sm">
                <span class="text-secondary">Uptime</span>
                <span class="font-medium text-primary">{{ formatUptime(cacheData?.collector?.uptime_seconds) }}</span>
              </div>
              <div class="flex justify-between items-center text-sm">
                <span class="text-secondary">Scheduler</span>
                <span :class="['font-medium', cacheData?.collector?.scheduler?.running ? 'text-emerald-500' : 'text-red-500']">
                  {{ cacheData?.collector?.scheduler?.running ? 'Running' : 'Stopped' }}
                </span>
              </div>
              <div class="flex justify-between items-center text-sm">
                <span class="text-secondary">Scheduled Jobs</span>
                <span class="font-medium text-primary">{{ cacheData?.collector?.scheduler?.jobs || 0 }}</span>
              </div>
              <div class="flex justify-between items-center text-sm">
                <span class="text-secondary">Redis Connected</span>
                <span :class="['font-medium', cacheData?.collector?.redis_connected ? 'text-emerald-500' : 'text-red-500']">
                  {{ cacheData?.collector?.redis_connected ? 'Yes' : 'No' }}
                </span>
              </div>
            </div>

            <div v-if="cacheData?.collector?.error" class="mt-3 p-2 bg-red-50 dark:bg-red-500/10 rounded-lg">
              <p class="text-xs text-red-600 dark:text-red-400">{{ cacheData?.collector?.error }}</p>
            </div>
          </div>
        </Card>

        <!-- Collectors Status Card -->
        <Card :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3 mb-4">
              <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-500/20">
                <ChartBarIcon class="h-5 w-5 text-purple-500" />
              </div>
              <div class="flex-1">
                <h3 class="font-semibold text-primary">Data Collectors</h3>
                <p class="text-xs text-muted">Individual collector status</p>
              </div>
            </div>

            <div class="space-y-2">
              <div
                v-for="(status, name) in cacheData?.collector?.collectors"
                :key="name"
                class="flex items-center justify-between text-sm py-1"
              >
                <div class="flex items-center gap-2">
                  <component
                    :is="getCollectorIcon(name)"
                    class="h-4 w-4 text-secondary"
                  />
                  <span class="text-secondary capitalize">{{ name.replace('_', ' ') }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <span
                    v-if="status.last_error"
                    class="text-red-500"
                    :title="status.last_error"
                  >
                    <ExclamationTriangleIcon class="h-4 w-4" />
                  </span>
                  <span
                    :class="[
                      'flex items-center gap-1 font-medium text-xs',
                      !status.last_error ? 'text-emerald-500' : 'text-amber-500'
                    ]"
                  >
                    <CheckCircleIcon v-if="!status.last_error" class="h-3 w-3" />
                    {{ status.last_run ? 'OK' : 'Pending' }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Cached Keys Section -->
      <div class="mt-6">
        <Card :padding="false">
          <div class="p-4 border-b border-gray-200 dark:border-gray-700">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-lg bg-amber-100 dark:bg-amber-500/20">
                  <KeyIcon class="h-5 w-5 text-amber-500" />
                </div>
                <div>
                  <h3 class="font-semibold text-primary">Cached Keys</h3>
                  <p class="text-xs text-muted">{{ cacheData?.cached_data?.total_keys || 0 }} total keys in cache</p>
                </div>
              </div>

              <!-- Category Badges -->
              <div class="flex gap-2">
                <span
                  v-for="(data, category) in cacheData?.cached_data?.categories"
                  :key="category"
                  :class="[
                    'px-2 py-1 rounded-full text-xs font-medium',
                    `bg-${categoryColors[category] || 'gray'}-100 dark:bg-${categoryColors[category] || 'gray'}-500/20`,
                    `text-${categoryColors[category] || 'gray'}-700 dark:text-${categoryColors[category] || 'gray'}-400`
                  ]"
                >
                  {{ category }}: {{ data.count }}
                </span>
              </div>
            </div>
          </div>

          <div class="divide-y divide-gray-200 dark:divide-gray-700">
            <div
              v-for="key in cacheData?.cached_data?.keys"
              :key="key.key"
              class="p-4 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors cursor-pointer"
              @click="viewKeyDetail(key.key)"
            >
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                  <component
                    :is="categoryIcons[key.category] || DocumentTextIcon"
                    :class="[
                      'h-5 w-5',
                      `text-${categoryColors[key.category] || 'gray'}-500`
                    ]"
                  />
                  <div>
                    <p class="font-medium text-primary">{{ key.key }}</p>
                    <div class="flex items-center gap-3 text-xs text-muted mt-1">
                      <span>Type: {{ key.type }}</span>
                      <span v-if="key.size_bytes">Size: {{ formatBytes(key.size_bytes) }}</span>
                      <span v-if="key.preview?.collected_at">
                        Updated: {{ new Date(key.preview.collected_at).toLocaleTimeString() }}
                      </span>
                    </div>
                  </div>
                </div>
                <div class="flex items-center gap-4">
                  <div class="text-right">
                    <span
                      :class="[
                        'px-2 py-1 rounded text-xs font-medium',
                        key.ttl === null
                          ? 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                          : key.ttl > 60
                            ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                            : 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400'
                      ]"
                    >
                      {{ formatTTL(key.ttl) }}
                    </span>
                  </div>
                  <EyeIcon class="h-5 w-5 text-secondary" />
                </div>
              </div>

              <!-- Data Fields Preview -->
              <div v-if="key.preview?.data_fields?.length" class="mt-2 flex flex-wrap gap-1">
                <span
                  v-for="field in key.preview.data_fields"
                  :key="field"
                  class="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded"
                >
                  {{ field }}
                </span>
              </div>
            </div>

            <div v-if="!cacheData?.cached_data?.keys?.length" class="p-8 text-center">
              <CircleStackIcon class="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
              <p class="text-secondary">No cached keys found</p>
            </div>
          </div>
        </Card>
      </div>
    </template>

    <!-- Key Detail Modal -->
    <Teleport to="body">
      <div
        v-if="keyDetailModal"
        class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
        @click.self="keyDetailModal = false"
      >
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-3xl w-full max-h-[80vh] overflow-hidden">
          <div class="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <div class="flex items-center gap-3">
              <KeyIcon class="h-5 w-5 text-amber-500" />
              <h3 class="font-semibold text-primary">{{ selectedKey }}</h3>
            </div>
            <div class="flex items-center gap-2">
              <button
                @click="openDeleteDialog(selectedKey)"
                class="btn-secondary text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10"
              >
                <TrashIcon class="h-4 w-4" />
              </button>
              <button
                @click="keyDetailModal = false"
                class="btn-secondary"
              >
                Close
              </button>
            </div>
          </div>

          <div class="p-4 overflow-auto max-h-[60vh]">
            <HeartbeatLoader v-if="keyDetailLoading" text="Loading key data..." color="amber" class="py-8" />

            <template v-else-if="keyDetailData">
              <div class="grid grid-cols-3 gap-4 mb-4">
                <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
                  <p class="text-xs text-muted uppercase">Type</p>
                  <p class="font-medium text-primary">{{ keyDetailData.type }}</p>
                </div>
                <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
                  <p class="text-xs text-muted uppercase">TTL</p>
                  <p class="font-medium text-primary">{{ formatTTL(keyDetailData.ttl) }}</p>
                </div>
                <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
                  <p class="text-xs text-muted uppercase">Key</p>
                  <p class="font-medium text-primary truncate" :title="keyDetailData.key">{{ keyDetailData.key }}</p>
                </div>
              </div>

              <div class="bg-gray-900 rounded-lg p-4 overflow-auto">
                <pre class="text-sm text-green-400 whitespace-pre-wrap break-words">{{ JSON.stringify(keyDetailData.value, null, 2) }}</pre>
              </div>
            </template>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="deleteDialog.open"
      title="Delete Cache Key"
      :message="`Are you sure you want to delete the key '${deleteDialog.keyName}'?`"
      confirm-text="Delete"
      :loading="deleteDialog.loading"
      danger
      @confirm="confirmDelete"
      @cancel="deleteDialog.open = false"
    />

    <!-- Flush Confirmation Dialog -->
    <ConfirmDialog
      :open="flushDialog.open"
      title="Flush All Cache"
      message="Are you sure you want to delete ALL cached keys? This will force the status collector to repopulate the cache."
      confirm-text="Flush All"
      :loading="flushDialog.loading"
      danger
      @confirm="confirmFlush"
      @cancel="flushDialog.open = false"
    />
  </div>
</template>
