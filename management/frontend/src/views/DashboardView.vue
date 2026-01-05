<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/views/DashboardView.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import Card from '@/components/common/Card.vue'
import SystemMetricsLoader from '@/components/common/SystemMetricsLoader.vue'
import { systemApi } from '@/services/api'
import {
  ServerIcon,
  CpuChipIcon,
  CircleStackIcon,
  ServerStackIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
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

// Format bytes per second to human readable rate
function formatRate(bytesPerSec) {
  if (!bytesPerSec || bytesPerSec === 0) return '0 B/s'
  const k = 1024
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s']
  const i = Math.floor(Math.log(bytesPerSec) / Math.log(k))
  return parseFloat((bytesPerSec / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
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

// Get color for progress bar based on percent
function getProgressColor(percent) {
  if (percent >= 90) return 'bg-red-500'
  if (percent >= 70) return 'bg-amber-500'
  return 'bg-emerald-500'
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
const containerHealth = computed(() => latest.value.containers || {})
const networkRates = computed(() => metricsData.value?.network_rates || {})

// CPU chart data (blue)
const cpuChartData = computed(() => {
  const hist = history.value
  if (!hist.length) {
    return {
      labels: ['--:--'],
      datasets: [{
        label: 'CPU %',
        data: [0],
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        borderWidth: 2,
      }],
    }
  }

  return {
    labels: hist.map(h => h.time),
    datasets: [{
      label: 'CPU %',
      data: hist.map(h => h.cpu || 0),
      borderColor: 'rgb(59, 130, 246)',
      backgroundColor: 'rgba(59, 130, 246, 0.1)',
      fill: true,
      tension: 0.4,
      pointRadius: 0,
      borderWidth: 2,
    }],
  }
})

// Memory chart data (purple)
const memoryChartData = computed(() => {
  const hist = history.value
  if (!hist.length) {
    return {
      labels: ['--:--'],
      datasets: [{
        label: 'Memory %',
        data: [0],
        borderColor: 'rgb(168, 85, 247)',
        backgroundColor: 'rgba(168, 85, 247, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        borderWidth: 2,
      }],
    }
  }

  return {
    labels: hist.map(h => h.time),
    datasets: [{
      label: 'Memory %',
      data: hist.map(h => h.memory || 0),
      borderColor: 'rgb(168, 85, 247)',
      backgroundColor: 'rgba(168, 85, 247, 0.1)',
      fill: true,
      tension: 0.4,
      pointRadius: 0,
      borderWidth: 2,
    }],
  }
})

// Network RX chart data (teal) - showing rate in MB/s
const networkRxChartData = computed(() => {
  const hist = history.value
  if (!hist.length) {
    return {
      labels: ['--:--'],
      datasets: [{
        label: 'Download',
        data: [0],
        borderColor: 'rgb(20, 184, 166)',
        backgroundColor: 'rgba(20, 184, 166, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        borderWidth: 2,
      }],
    }
  }

  // Convert to KB/s for display (better visibility for small values)
  return {
    labels: hist.map(h => h.time),
    datasets: [{
      label: 'Download (KB/s)',
      data: hist.map(h => ((h.network_rx_rate || 0) / 1024).toFixed(1)),
      borderColor: 'rgb(20, 184, 166)',
      backgroundColor: 'rgba(20, 184, 166, 0.1)',
      fill: true,
      tension: 0.4,
      pointRadius: 0,
      borderWidth: 2,
    }],
  }
})

// Network TX chart data (teal) - showing rate in KB/s
const networkTxChartData = computed(() => {
  const hist = history.value
  if (!hist.length) {
    return {
      labels: ['--:--'],
      datasets: [{
        label: 'Upload',
        data: [0],
        borderColor: 'rgb(20, 184, 166)',
        backgroundColor: 'rgba(20, 184, 166, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        borderWidth: 2,
      }],
    }
  }

  // Convert to KB/s for display (better visibility for small values)
  return {
    labels: hist.map(h => h.time),
    datasets: [{
      label: 'Upload (KB/s)',
      data: hist.map(h => ((h.network_tx_rate || 0) / 1024).toFixed(1)),
      borderColor: 'rgb(20, 184, 166)',
      backgroundColor: 'rgba(20, 184, 166, 0.1)',
      fill: true,
      tension: 0.4,
      pointRadius: 0,
      borderWidth: 2,
    }],
  }
})

// Chart options for percentage-based charts (CPU, Memory)
const percentChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { intersect: false, mode: 'index' },
  plugins: {
    legend: { display: false },
  },
  scales: {
    x: {
      grid: { color: themeStore.colorMode === 'dark' ? 'rgba(75, 85, 99, 0.3)' : 'rgba(107, 114, 128, 0.1)' },
      ticks: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280', maxTicksLimit: 8 },
    },
    y: {
      grid: { color: themeStore.colorMode === 'dark' ? 'rgba(75, 85, 99, 0.3)' : 'rgba(107, 114, 128, 0.1)' },
      ticks: {
        color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280',
        callback: (value) => value + '%',
      },
      min: 0,
      max: 100,
    },
  },
}))

// Chart options for network rate charts (dynamic scale)
const networkChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { intersect: false, mode: 'index' },
  plugins: {
    legend: { display: false },
  },
  scales: {
    x: {
      grid: { color: themeStore.colorMode === 'dark' ? 'rgba(75, 85, 99, 0.3)' : 'rgba(107, 114, 128, 0.1)' },
      ticks: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280', maxTicksLimit: 8 },
    },
    y: {
      grid: { color: themeStore.colorMode === 'dark' ? 'rgba(75, 85, 99, 0.3)' : 'rgba(107, 114, 128, 0.1)' },
      ticks: {
        color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280',
        callback: (value) => value + ' KB/s',
      },
      min: 0,
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
        System Overview
      </h1>
      <p class="text-secondary mt-1">
        Real-time system monitoring
        <span v-if="!metricsAvailable && !loading" class="text-amber-500 text-xs ml-2">
          (Waiting for metrics collection...)
        </span>
      </p>
    </div>

    <SystemMetricsLoader v-if="loading" />

    <!-- Error State -->
    <Card v-else-if="error && !metricsAvailable" class="border-red-300 dark:border-red-900">
      <div class="flex items-center gap-3 text-red-500">
        <ExclamationTriangleIcon class="h-6 w-6" />
        <div>
          <p class="font-medium">Metrics Unavailable</p>
          <p class="text-sm text-secondary">{{ error }}</p>
          <p class="text-xs text-muted mt-1">
            Metrics are collected every minute by the scheduler. Please wait for the first collection cycle.
          </p>
        </div>
      </div>
    </Card>

    <!-- Dashboard Content -->
    <template v-else>
      <!-- Quick Stats Row (Overview style) -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <!-- CPU -->
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
                <CpuChipIcon class="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">CPU Usage</p>
                <p class="text-xl font-bold text-primary">{{ (cpuMetrics.percent || 0).toFixed(1) }}%</p>
              </div>
            </div>
            <div class="mt-3 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all', getProgressColor(cpuMetrics.percent || 0)]"
                :style="{ width: `${cpuMetrics.percent || 0}%` }"
              />
            </div>
          </div>
        </Card>

        <!-- Memory -->
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-500/20">
                <CircleStackIcon class="h-5 w-5 text-purple-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Memory Usage</p>
                <p class="text-xl font-bold text-primary">{{ (memoryMetrics.percent || 0).toFixed(1) }}%</p>
              </div>
            </div>
            <div class="mt-3 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all', getProgressColor(memoryMetrics.percent || 0)]"
                :style="{ width: `${memoryMetrics.percent || 0}%` }"
              />
            </div>
          </div>
        </Card>

        <!-- Disk -->
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-500/20">
                <ServerStackIcon class="h-5 w-5 text-emerald-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Disk Usage</p>
                <p class="text-xl font-bold text-primary">{{ (diskMetrics.percent || 0).toFixed(1) }}%</p>
              </div>
            </div>
            <div class="mt-3 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all', getProgressColor(diskMetrics.percent || 0)]"
                :style="{ width: `${diskMetrics.percent || 0}%` }"
              />
            </div>
          </div>
        </Card>

        <!-- Uptime -->
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-amber-100 dark:bg-amber-500/20">
                <ClockIcon class="h-5 w-5 text-amber-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Uptime</p>
                <p class="text-xl font-bold text-primary">{{ formatUptime(systemInfo.uptime_seconds) }}</p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Charts Row - CPU & Memory -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="CPU History" subtitle="Last hour" :neon="true">
          <div class="h-48">
            <Line
              v-if="history.length > 0"
              :data="cpuChartData"
              :options="percentChartOptions"
            />
            <div v-else class="h-full flex items-center justify-center text-muted">
              <p>Collecting data...</p>
            </div>
          </div>
        </Card>

        <Card title="Memory History" subtitle="Last hour" :neon="true">
          <div class="h-48">
            <Line
              v-if="history.length > 0"
              :data="memoryChartData"
              :options="percentChartOptions"
            />
            <div v-else class="h-full flex items-center justify-center text-muted">
              <p>Collecting data...</p>
            </div>
          </div>
        </Card>
      </div>

      <!-- Containers & Network Row -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Containers Tile - Indigo -->
        <Card :neon="true" :padding="false">
          <div class="p-6">
            <div class="flex items-start justify-between mb-4">
              <div>
                <p class="text-sm font-medium text-secondary uppercase tracking-wider">Docker Containers</p>
                <p class="text-4xl font-black mt-2 text-indigo-500">
                  {{ containerHealth.total || 0 }}
                </p>
                <p class="text-sm text-muted mt-1">{{ containerHealth.running || 0 }} running</p>
              </div>
              <div class="p-3 rounded-2xl bg-indigo-100 dark:bg-indigo-500/20">
                <ServerIcon class="h-8 w-8 text-indigo-500" />
              </div>
            </div>
            <div class="grid grid-cols-4 gap-2 pt-4 border-t border-gray-400 dark:border-gray-700">
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

        <!-- Network I/O Current Rates -->
        <Card :neon="true" :padding="false">
          <div class="p-6">
            <p class="text-sm font-medium text-secondary uppercase tracking-wider mb-4">Network I/O</p>
            <div class="grid grid-cols-2 gap-4">
              <!-- Download Rate -->
              <div class="text-center p-4 bg-teal-50 dark:bg-teal-900/20 rounded-xl">
                <ArrowTrendingDownIcon class="h-6 w-6 text-teal-500 mx-auto mb-2" />
                <p class="text-2xl font-bold text-teal-500">{{ formatRate(networkRates.rx_bytes_per_sec || 0) }}</p>
                <p class="text-xs text-muted">Download</p>
              </div>
              <!-- Upload Rate -->
              <div class="text-center p-4 bg-teal-50 dark:bg-teal-900/20 rounded-xl">
                <ArrowTrendingUpIcon class="h-6 w-6 text-teal-500 mx-auto mb-2" />
                <p class="text-2xl font-bold text-teal-500">{{ formatRate(networkRates.tx_bytes_per_sec || 0) }}</p>
                <p class="text-xs text-muted">Upload</p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Network History Charts -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Download History" subtitle="Last hour" :neon="true">
          <div class="h-40">
            <Line
              v-if="history.length > 0"
              :data="networkRxChartData"
              :options="networkChartOptions"
            />
            <div v-else class="h-full flex items-center justify-center text-muted">
              <p>Collecting data...</p>
            </div>
          </div>
        </Card>

        <Card title="Upload History" subtitle="Last hour" :neon="true">
          <div class="h-40">
            <Line
              v-if="history.length > 0"
              :data="networkTxChartData"
              :options="networkChartOptions"
            />
            <div v-else class="h-full flex items-center justify-center text-muted">
              <p>Collecting data...</p>
            </div>
          </div>
        </Card>
      </div>
    </template>
  </div>
</template>
