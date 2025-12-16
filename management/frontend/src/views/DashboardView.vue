<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import Card from '@/components/common/Card.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { systemApi } from '@/services/api'
import {
  ServerIcon,
  CpuChipIcon,
  CircleStackIcon,
  ExclamationTriangleIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ChartBarIcon,
} from '@heroicons/vue/24/outline'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const router = useRouter()
const themeStore = useThemeStore()

const loading = ref(true)
const error = ref(null)
const metricsAvailable = ref(false)

// Metrics data from the cached SQL endpoint
const metricsData = ref(null)

let refreshInterval = null

// Format bytes to human readable
function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i]
}

// Format uptime
function formatUptime(seconds) {
  if (!seconds) return '0m'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

// Check if value is in warning/critical range
function isWarning(percent) {
  return percent >= 70 && percent < 90
}

function isCritical(percent) {
  return percent >= 90
}

// Fetch metrics from the cached SQL endpoint
async function fetchMetrics() {
  try {
    const response = await systemApi.hostMetricsCached(60)
    metricsData.value = response.data
    metricsAvailable.value = response.data.available
    error.value = response.data.available ? null : response.data.error
  } catch (err) {
    console.error('Failed to fetch cached metrics:', err)
    error.value = err.response?.data?.detail || err.message
    metricsAvailable.value = false
  }
}

// Load all data
async function loadData() {
  loading.value = true
  await fetchMetrics()
  loading.value = false
}

// Navigate to containers view with filter
function navigateToContainers(filter = null) {
  router.push({ name: 'containers', query: filter ? { status: filter } : {} })
}

onMounted(() => {
  loadData()
  // Refresh every 30 seconds (data is updated every minute in the database)
  refreshInterval = setInterval(fetchMetrics, 30000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})

// Computed properties for easy access
const latest = computed(() => metricsData.value?.latest || {})
const history = computed(() => metricsData.value?.history || [])
const systemInfo = computed(() => latest.value.system || {})
const cpuMetrics = computed(() => latest.value.cpu || {})
const memoryMetrics = computed(() => latest.value.memory || {})
const diskMetrics = computed(() => latest.value.disk || {})
const disksDetail = computed(() => latest.value.disks || [])
const networkMetrics = computed(() => latest.value.network || {})
const containerHealth = computed(() => latest.value.containers || {})

// Chart data from SQL history with distinct colors
const resourceChartData = computed(() => {
  const hist = history.value
  if (!hist.length) {
    return {
      labels: ['--:--'],
      datasets: [
        { label: 'CPU %', data: [0], borderColor: 'rgb(59, 130, 246)', backgroundColor: 'transparent', tension: 0.4, pointRadius: 0 },
        { label: 'Memory %', data: [0], borderColor: 'rgb(168, 85, 247)', backgroundColor: 'transparent', tension: 0.4, pointRadius: 0 },
      ],
    }
  }

  return {
    labels: hist.map(h => h.time),
    datasets: [
      {
        label: 'CPU %',
        data: hist.map(h => h.cpu || 0),
        borderColor: 'rgb(59, 130, 246)',  // Blue
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        borderWidth: 2,
      },
      {
        label: 'Memory %',
        data: hist.map(h => h.memory || 0),
        borderColor: 'rgb(168, 85, 247)',  // Purple
        backgroundColor: 'rgba(168, 85, 247, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        borderWidth: 2,
      },
    ],
  }
})

const resourceChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { intersect: false, mode: 'index' },
  plugins: {
    legend: { position: 'top', labels: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280', boxWidth: 12 } },
  },
  scales: {
    x: {
      grid: { color: themeStore.colorMode === 'dark' ? 'rgba(75, 85, 99, 0.3)' : 'rgba(107, 114, 128, 0.1)' },
      ticks: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280', maxTicksLimit: 10 },
    },
    y: {
      grid: { color: themeStore.colorMode === 'dark' ? 'rgba(75, 85, 99, 0.3)' : 'rgba(107, 114, 128, 0.1)' },
      ticks: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280' },
      min: 0,
      max: 100,
    },
  },
}))
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <h1
        :class="[
          'text-2xl font-bold',
          themeStore.isNeon ? 'neon-text-cyan' : 'text-primary'
        ]"
      >
        Host Dashboard
      </h1>
      <p class="text-secondary mt-1">
        Real-time host system metrics
        <span v-if="!metricsAvailable && !loading" class="text-amber-500 text-xs ml-2">
          (Waiting for metrics collection...)
        </span>
      </p>
    </div>

    <LoadingSpinner v-if="loading" size="lg" text="Loading host metrics..." class="py-12" />

    <!-- Error State -->
    <Card v-else-if="error && !metricsAvailable" class="border-red-300 dark:border-red-900">
      <div class="flex items-center gap-3 text-red-500">
        <ExclamationTriangleIcon class="h-6 w-6" />
        <div>
          <p class="font-medium">Metrics Unavailable</p>
          <p class="text-sm text-secondary">{{ error }}</p>
          <p class="text-xs text-muted mt-1">
            Metrics are collected every minute. Please ensure the metrics-agent is running and METRICS_AGENT_ENABLED=true.
          </p>
        </div>
      </div>
    </Card>

    <!-- Grid Tiles Layout -->
    <template v-else>
      <!-- Large Tile Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- CPU Tile - Blue -->
        <Card :neon="true" :padding="false">
          <div class="p-6">
            <div class="flex items-start justify-between">
              <div>
                <p class="text-sm font-medium text-secondary uppercase tracking-wider">CPU Usage</p>
                <p :class="['text-5xl font-black mt-2', isCritical(cpuMetrics.percent || 0) ? 'text-red-500' : isWarning(cpuMetrics.percent || 0) ? 'text-amber-500' : 'text-blue-500']">
                  {{ Math.round(cpuMetrics.percent || 0) }}<span class="text-2xl">%</span>
                </p>
                <p class="text-sm text-muted mt-2">{{ cpuMetrics.core_count || 0 }} cores</p>
              </div>
              <div class="p-4 rounded-2xl bg-blue-100 dark:bg-blue-500/20">
                <CpuChipIcon class="h-10 w-10 text-blue-500" />
              </div>
            </div>
            <div class="mt-6 h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all duration-700', isCritical(cpuMetrics.percent || 0) ? 'bg-red-500' : isWarning(cpuMetrics.percent || 0) ? 'bg-amber-500' : 'bg-blue-500']"
                :style="{ width: `${cpuMetrics.percent || 0}%` }"
              />
            </div>
            <div class="mt-3 flex justify-between text-sm text-muted">
              <span>Load: {{ (cpuMetrics.load_avg_1m || 0).toFixed(2) }} / {{ (cpuMetrics.load_avg_5m || 0).toFixed(2) }} / {{ (cpuMetrics.load_avg_15m || 0).toFixed(2) }}</span>
            </div>
          </div>
        </Card>

        <!-- Memory Tile - Purple -->
        <Card :neon="true" :padding="false">
          <div class="p-6">
            <div class="flex items-start justify-between">
              <div>
                <p class="text-sm font-medium text-secondary uppercase tracking-wider">Memory Usage</p>
                <p :class="['text-5xl font-black mt-2', isCritical(memoryMetrics.percent || 0) ? 'text-red-500' : isWarning(memoryMetrics.percent || 0) ? 'text-amber-500' : 'text-purple-500']">
                  {{ Math.round(memoryMetrics.percent || 0) }}<span class="text-2xl">%</span>
                </p>
                <p class="text-sm text-muted mt-2">{{ formatBytes(memoryMetrics.used_bytes || 0) }} / {{ formatBytes(memoryMetrics.total_bytes || 0) }}</p>
              </div>
              <div class="p-4 rounded-2xl bg-purple-100 dark:bg-purple-500/20">
                <CircleStackIcon class="h-10 w-10 text-purple-500" />
              </div>
            </div>
            <div class="mt-6 h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all duration-700', isCritical(memoryMetrics.percent || 0) ? 'bg-red-500' : isWarning(memoryMetrics.percent || 0) ? 'bg-amber-500' : 'bg-purple-500']"
                :style="{ width: `${memoryMetrics.percent || 0}%` }"
              />
            </div>
            <div class="mt-3 flex justify-between text-sm text-muted">
              <span>Swap: {{ formatBytes(memoryMetrics.swap_used_bytes || 0) }} / {{ formatBytes(memoryMetrics.swap_total_bytes || 0) }}</span>
              <span v-if="memoryMetrics.swap_percent">{{ (memoryMetrics.swap_percent || 0).toFixed(1) }}%</span>
            </div>
          </div>
        </Card>

        <!-- Disk Tile - Amber/Orange -->
        <Card :neon="true" :padding="false">
          <div class="p-6">
            <div class="flex items-start justify-between">
              <div>
                <p class="text-sm font-medium text-secondary uppercase tracking-wider">Disk Usage</p>
                <p :class="['text-5xl font-black mt-2', isCritical(diskMetrics.percent || 0) ? 'text-red-500' : isWarning(diskMetrics.percent || 0) ? 'text-red-400' : 'text-amber-500']">
                  {{ Math.round(diskMetrics.percent || 0) }}<span class="text-2xl">%</span>
                </p>
                <p class="text-sm text-muted mt-2">{{ formatBytes(diskMetrics.free_bytes || 0) }} free</p>
              </div>
              <div class="p-4 rounded-2xl bg-amber-100 dark:bg-amber-500/20">
                <ChartBarIcon class="h-10 w-10 text-amber-500" />
              </div>
            </div>
            <div class="mt-6 space-y-2">
              <div v-for="disk in disksDetail.slice(0, 3)" :key="disk.mount_point">
                <div class="flex justify-between text-xs mb-1">
                  <span class="text-muted">{{ disk.mount_point }}</span>
                  <span :class="isCritical(disk.percent || 0) ? 'text-red-500' : isWarning(disk.percent || 0) ? 'text-red-400' : 'text-amber-500'">{{ (disk.percent || 0).toFixed(0) }}%</span>
                </div>
                <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full">
                  <div
                    :class="['h-full rounded-full', isCritical(disk.percent || 0) ? 'bg-red-500' : isWarning(disk.percent || 0) ? 'bg-red-400' : 'bg-amber-500']"
                    :style="{ width: `${disk.percent || 0}%` }"
                  />
                </div>
              </div>
            </div>
          </div>
        </Card>

        <!-- Containers Tile - Indigo -->
        <Card :neon="true" :padding="false">
          <div class="p-6">
            <div class="flex items-start justify-between">
              <div>
                <p class="text-sm font-medium text-secondary uppercase tracking-wider">Containers</p>
                <p class="text-5xl font-black mt-2 text-indigo-500">
                  {{ containerHealth.total || 0 }}
                </p>
                <p class="text-sm text-muted mt-2">{{ containerHealth.running || 0 }} running</p>
              </div>
              <div class="p-4 rounded-2xl bg-indigo-100 dark:bg-indigo-500/20">
                <ServerIcon class="h-10 w-10 text-indigo-500" />
              </div>
            </div>
            <div class="mt-6 grid grid-cols-4 gap-2">
              <button @click="navigateToContainers('running')" class="text-center p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                <p class="text-lg font-bold text-emerald-500">{{ containerHealth.running || 0 }}</p>
                <p class="text-xs text-muted">Running</p>
              </button>
              <button @click="navigateToContainers('stopped')" class="text-center p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                <p class="text-lg font-bold text-slate-500">{{ containerHealth.stopped || 0 }}</p>
                <p class="text-xs text-muted">Stopped</p>
              </button>
              <button @click="navigateToContainers('healthy')" class="text-center p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                <p class="text-lg font-bold text-teal-500">{{ containerHealth.healthy || 0 }}</p>
                <p class="text-xs text-muted">Healthy</p>
              </button>
              <button
                @click="navigateToContainers('unhealthy')"
                :class="['text-center p-2 rounded-lg transition-colors', (containerHealth.unhealthy || 0) > 0 ? 'bg-red-50 dark:bg-red-900/20 animate-pulse' : 'hover:bg-gray-100 dark:hover:bg-gray-800']"
              >
                <p :class="['text-lg font-bold', (containerHealth.unhealthy || 0) > 0 ? 'text-red-500' : 'text-gray-400']">
                  {{ containerHealth.unhealthy || 0 }}
                </p>
                <p class="text-xs text-muted">Unhealthy</p>
              </button>
            </div>
          </div>
        </Card>
      </div>

      <!-- Network + System Info Row -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Network Tile - Teal/Rose -->
        <Card :neon="true" :padding="false">
          <div class="p-6">
            <p class="text-sm font-medium text-secondary uppercase tracking-wider mb-4">Network I/O</p>
            <div class="grid grid-cols-2 gap-4">
              <div class="text-center p-4 bg-teal-50 dark:bg-teal-900/20 rounded-xl">
                <ArrowTrendingDownIcon class="h-6 w-6 text-teal-500 mx-auto mb-2" />
                <p class="text-2xl font-bold text-teal-500">{{ formatBytes(networkMetrics.rx_bytes || 0) }}</p>
                <p class="text-xs text-muted">Received</p>
              </div>
              <div class="text-center p-4 bg-rose-50 dark:bg-rose-900/20 rounded-xl">
                <ArrowTrendingUpIcon class="h-6 w-6 text-rose-500 mx-auto mb-2" />
                <p class="text-2xl font-bold text-rose-500">{{ formatBytes(networkMetrics.tx_bytes || 0) }}</p>
                <p class="text-xs text-muted">Transmitted</p>
              </div>
            </div>
          </div>
        </Card>

        <!-- System Info Tile - Slate -->
        <Card :neon="true" :padding="false">
          <div class="p-6">
            <p class="text-sm font-medium text-secondary uppercase tracking-wider mb-4">System Info</p>
            <div class="space-y-3">
              <div class="flex justify-between">
                <span class="text-muted">Hostname</span>
                <span class="font-medium text-primary">{{ systemInfo.hostname || '-' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-muted">Platform</span>
                <span class="font-medium text-primary">{{ systemInfo.platform || '-' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-muted">Uptime</span>
                <span class="font-medium text-primary">{{ formatUptime(systemInfo.uptime_seconds) }}</span>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Chart - Blue/Purple to match CPU/Memory -->
      <Card title="Resource History (Last Hour)" :neon="true">
        <div class="h-64">
          <Line
            v-if="history.length > 0"
            :data="resourceChartData"
            :options="resourceChartOptions"
          />
          <div v-else class="h-full flex items-center justify-center text-muted">
            <p>Collecting historical data... Charts will appear after a few minutes.</p>
          </div>
        </div>
      </Card>
    </template>
  </div>
</template>
