<script setup>
import { ref, shallowRef, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useContainerStore } from '@/stores/containers'
import Card from '@/components/common/Card.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { systemApi, containersApi } from '@/services/api'
import {
  ServerIcon,
  CpuChipIcon,
  CircleStackIcon,
  SignalIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  ComputerDesktopIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ChartBarIcon,
  Squares2X2Icon,
  RectangleGroupIcon,
  ViewColumnsIcon,
  SparklesIcon,
} from '@heroicons/vue/24/outline'
import { Line, Doughnut, Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
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
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const router = useRouter()
const themeStore = useThemeStore()
const containerStore = useContainerStore()

// Current dashboard variation (1-5)
const currentVariation = ref(1)
const loading = ref(true)
const hostMetricsAvailable = ref(false)
const error = ref(null)

// Host metrics from metrics agent
const hostMetrics = ref(null)

// Metrics history for charts (last 30 data points)
// Using shallowRef to prevent deep reactivity tracking which causes infinite loops with Chart.js
const metricsHistory = shallowRef({
  labels: [],
  cpu: [],
  memory: [],
  networkRx: [],
  networkTx: [],
})
const MAX_HISTORY_POINTS = 30

// Helper to update metrics history without triggering infinite reactivity loops
function updateMetricsHistory(newData) {
  const current = metricsHistory.value
  const labels = [...current.labels, newData.label].slice(-MAX_HISTORY_POINTS)
  const cpu = [...current.cpu, newData.cpu].slice(-MAX_HISTORY_POINTS)
  const memory = [...current.memory, newData.memory].slice(-MAX_HISTORY_POINTS)
  const networkRx = [...current.networkRx, newData.networkRx].slice(-MAX_HISTORY_POINTS)
  const networkTx = [...current.networkTx, newData.networkTx].slice(-MAX_HISTORY_POINTS)

  // Replace the entire object to trigger shallow reactivity
  metricsHistory.value = { labels, cpu, memory, networkRx, networkTx }
}

// Container health summary
const containerHealth = ref({
  total: 0,
  running: 0,
  stopped: 0,
  unhealthy: 0,
  healthy: 0,
})

let metricsInterval = null

// Format bytes to human readable
function formatBytes(bytes, decimals = 1) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i]
}

// Format uptime
function formatUptime(seconds) {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

// Get status color
function getStatusColor(percent, warning = 70, critical = 90) {
  if (percent >= critical) return 'red'
  if (percent >= warning) return 'amber'
  return 'emerald'
}

// Chart colors based on theme
const chartColors = computed(() => {
  if (themeStore.isNeon) {
    return {
      cpu: 'rgb(34, 211, 238)',      // cyan
      memory: 'rgb(168, 85, 247)',   // purple
      disk: 'rgb(52, 211, 153)',     // emerald
      network: 'rgb(251, 191, 36)',  // amber
      networkTx: 'rgb(244, 114, 182)', // pink
      grid: 'rgba(34, 211, 238, 0.1)',
    }
  }
  return {
    cpu: 'rgb(59, 130, 246)',      // blue
    memory: 'rgb(168, 85, 247)',   // purple
    disk: 'rgb(34, 197, 94)',      // green
    network: 'rgb(245, 158, 11)',  // amber
    networkTx: 'rgb(239, 68, 68)', // red
    grid: 'rgba(107, 114, 128, 0.1)',
  }
})

// Fetch host metrics from metrics agent
async function fetchHostMetrics() {
  try {
    // First check if metrics agent is available
    const healthRes = await systemApi.hostMetricsHealth()
    hostMetricsAvailable.value = healthRes.data?.available || false

    if (!hostMetricsAvailable.value) {
      // Fall back to container metrics
      await fetchContainerMetrics()
      return
    }

    // Get full metrics from host
    const metricsRes = await systemApi.hostMetrics(true)
    hostMetrics.value = metricsRes.data

    // Update metrics history using helper to avoid reactivity loops
    const now = new Date()
    const timeLabel = now.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })

    const cpu = hostMetrics.value.cpu || {}
    const memory = hostMetrics.value.memory || {}
    const network = hostMetrics.value.network || []

    // Calculate total network bandwidth
    const totalRx = network.reduce((sum, iface) => sum + (iface.bytes_recv || 0), 0)
    const totalTx = network.reduce((sum, iface) => sum + (iface.bytes_sent || 0), 0)

    updateMetricsHistory({
      label: timeLabel,
      cpu: Math.round(cpu.percent || 0),
      memory: Math.round(memory.percent || 0),
      networkRx: totalRx,
      networkTx: totalTx,
    })

    // Update container health from host metrics
    const containers = hostMetrics.value.containers || []
    containerHealth.value = {
      total: containers.length,
      running: containers.filter(c => c.status === 'running').length,
      stopped: containers.filter(c => c.status !== 'running').length,
      unhealthy: containers.filter(c => c.health === 'unhealthy').length,
      healthy: containers.filter(c => c.health === 'healthy').length,
    }

    error.value = null
  } catch (err) {
    console.error('Failed to fetch host metrics:', err)
    error.value = err.response?.data?.detail || err.message
    // Fall back to container metrics
    await fetchContainerMetrics()
  }
}

// Fallback to fetch from container API
async function fetchContainerMetrics() {
  try {
    const [metricsRes, infoRes, containersRes] = await Promise.all([
      systemApi.metrics(),
      systemApi.info(),
      containerStore.fetchContainers(),
    ])

    // Build a pseudo host metrics object from container data
    hostMetrics.value = {
      system: {
        hostname: infoRes.data.hostname,
        platform: infoRes.data.platform,
        platform_version: infoRes.data.platform_release,
        uptime_seconds: infoRes.data.uptime_seconds,
      },
      cpu: {
        percent: metricsRes.data.cpu.percent,
        core_count: metricsRes.data.cpu.count,
        load_avg_1m: 0,
        load_avg_5m: 0,
        load_avg_15m: 0,
      },
      memory: {
        total_bytes: metricsRes.data.memory.total_bytes,
        used_bytes: metricsRes.data.memory.used_bytes,
        available_bytes: metricsRes.data.memory.available_bytes,
        percent: metricsRes.data.memory.percent,
        swap_total_bytes: 0,
        swap_used_bytes: 0,
        swap_percent: 0,
      },
      disks: [{
        mount_point: '/',
        total_bytes: metricsRes.data.disk.total_bytes,
        used_bytes: metricsRes.data.disk.used_bytes,
        free_bytes: metricsRes.data.disk.free_bytes,
        percent: metricsRes.data.disk.percent,
      }],
      network: [{
        name: 'eth0',
        bytes_recv: metricsRes.data.network?.bytes_recv || 0,
        bytes_sent: metricsRes.data.network?.bytes_sent || 0,
      }],
      containers: containerStore.containers.map(c => ({
        name: c.name,
        status: c.status,
        health: c.health_status || 'none',
        image: c.image,
      })),
    }

    // Update container health
    containerHealth.value = {
      total: containerStore.containers.length,
      running: containerStore.runningCount,
      stopped: containerStore.containers.length - containerStore.runningCount,
      unhealthy: containerStore.containers.filter(c => c.health_status === 'unhealthy').length,
      healthy: containerStore.containers.filter(c => c.health_status === 'healthy').length,
    }

    // Update history using helper to avoid reactivity loops
    const now = new Date()
    const timeLabel = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })

    updateMetricsHistory({
      label: timeLabel,
      cpu: Math.round(metricsRes.data.cpu.percent),
      memory: Math.round(metricsRes.data.memory.percent),
      networkRx: metricsRes.data.network?.bytes_recv || 0,
      networkTx: metricsRes.data.network?.bytes_sent || 0,
    })
  } catch (err) {
    console.error('Failed to fetch container metrics:', err)
    error.value = err.response?.data?.detail || err.message
  }
}

// Load all data
async function loadData() {
  loading.value = true
  await fetchHostMetrics()
  loading.value = false
}

// Navigate to containers view with filter
function navigateToContainers(filter = null) {
  router.push({ name: 'containers', query: filter ? { status: filter } : {} })
}

onMounted(() => {
  loadData()
  // Update every 30 seconds
  metricsInterval = setInterval(fetchHostMetrics, 30000)
})

onUnmounted(() => {
  if (metricsInterval) {
    clearInterval(metricsInterval)
  }
})

// Computed properties for display
const systemInfo = computed(() => hostMetrics.value?.system || {})
const cpuMetrics = computed(() => hostMetrics.value?.cpu || {})
const memoryMetrics = computed(() => hostMetrics.value?.memory || {})
const diskMetrics = computed(() => hostMetrics.value?.disks || [])
const networkMetrics = computed(() => hostMetrics.value?.network || [])

// Primary disk (usually /)
const primaryDisk = computed(() => diskMetrics.value.find(d => d.mount_point === '/') || diskMetrics.value[0] || {})

// Total network bytes
const totalNetwork = computed(() => {
  const rx = networkMetrics.value.reduce((sum, iface) => sum + (iface.bytes_recv || 0), 0)
  const tx = networkMetrics.value.reduce((sum, iface) => sum + (iface.bytes_sent || 0), 0)
  return { rx, tx }
})

// Chart data for CPU/Memory history
const resourceChartData = computed(() => ({
  labels: metricsHistory.value.labels.length > 0 ? metricsHistory.value.labels : ['--:--'],
  datasets: [
    {
      label: 'CPU %',
      data: metricsHistory.value.cpu.length > 0 ? metricsHistory.value.cpu : [0],
      borderColor: chartColors.value.cpu,
      backgroundColor: chartColors.value.cpu.replace('rgb', 'rgba').replace(')', ', 0.1)'),
      fill: true,
      tension: 0.4,
      pointRadius: 2,
    },
    {
      label: 'Memory %',
      data: metricsHistory.value.memory.length > 0 ? metricsHistory.value.memory : [0],
      borderColor: chartColors.value.memory,
      backgroundColor: chartColors.value.memory.replace('rgb', 'rgba').replace(')', ', 0.1)'),
      fill: true,
      tension: 0.4,
      pointRadius: 2,
    },
  ],
}))

const resourceChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { intersect: false, mode: 'index' },
  plugins: {
    legend: { position: 'top', labels: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280', boxWidth: 12 } },
  },
  scales: {
    x: { grid: { color: chartColors.value.grid }, ticks: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280', maxTicksLimit: 8 } },
    y: { grid: { color: chartColors.value.grid }, ticks: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280' }, min: 0, max: 100 },
  },
}))

// Disk usage bar chart
const diskChartData = computed(() => ({
  labels: diskMetrics.value.map(d => d.mount_point),
  datasets: [{
    label: 'Used %',
    data: diskMetrics.value.map(d => d.percent),
    backgroundColor: diskMetrics.value.map(d => {
      const status = getStatusColor(d.percent, 70, 90)
      if (status === 'red') return 'rgba(239, 68, 68, 0.8)'
      if (status === 'amber') return 'rgba(245, 158, 11, 0.8)'
      return 'rgba(34, 197, 94, 0.8)'
    }),
    borderRadius: 4,
  }],
}))

const diskChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  indexAxis: 'y',
  plugins: { legend: { display: false } },
  scales: {
    x: { grid: { color: chartColors.value.grid }, ticks: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280' }, min: 0, max: 100 },
    y: { grid: { display: false }, ticks: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280' } },
  },
}))

// Dashboard variation items for switcher
const variations = [
  { id: 1, name: 'Command Center', icon: Squares2X2Icon },
  { id: 2, name: 'Metrics Focus', icon: ChartBarIcon },
  { id: 3, name: 'Compact', icon: RectangleGroupIcon },
  { id: 4, name: 'Grid Tiles', icon: ViewColumnsIcon },
  { id: 5, name: 'Minimal', icon: SparklesIcon },
]
</script>

<template>
  <div class="space-y-6">
    <!-- Dashboard Variation Switcher -->
    <div class="flex items-center justify-between flex-wrap gap-4">
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
          <span v-if="!hostMetricsAvailable" class="text-amber-500 text-xs ml-2">(Fallback mode - metrics agent unavailable)</span>
        </p>
      </div>

      <!-- Variation Switcher -->
      <div class="flex items-center gap-1 bg-surface border border-gray-300 dark:border-gray-700 rounded-lg p-1">
        <button
          v-for="v in variations"
          :key="v.id"
          @click="currentVariation = v.id"
          :class="[
            'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all',
            currentVariation === v.id
              ? 'bg-blue-500 text-white shadow-sm'
              : 'text-secondary hover:text-primary hover:bg-gray-100 dark:hover:bg-gray-800'
          ]"
          :title="v.name"
        >
          <component :is="v.icon" class="h-4 w-4" />
          <span class="hidden sm:inline">{{ v.name }}</span>
        </button>
      </div>
    </div>

    <LoadingSpinner v-if="loading" size="lg" text="Loading host metrics..." class="py-12" />

    <!-- Error State -->
    <Card v-else-if="error && !hostMetrics" class="border-red-300 dark:border-red-900">
      <div class="flex items-center gap-3 text-red-500">
        <ExclamationTriangleIcon class="h-6 w-6" />
        <div>
          <p class="font-medium">Failed to load metrics</p>
          <p class="text-sm text-secondary">{{ error }}</p>
        </div>
      </div>
    </Card>

    <!-- Variation 1: Command Center -->
    <template v-else-if="currentVariation === 1">
      <!-- System Info Banner -->
      <Card :neon="true" :padding="false">
        <div class="px-6 py-4 flex flex-wrap items-center justify-between gap-4">
          <div class="flex items-center gap-4">
            <div class="p-3 rounded-lg bg-blue-100 dark:bg-blue-500/20">
              <ComputerDesktopIcon class="h-8 w-8 text-blue-500" />
            </div>
            <div>
              <h2 :class="['text-xl font-bold', themeStore.isNeon ? 'neon-text-cyan' : 'text-primary']">
                {{ systemInfo.hostname || 'Docker Host' }}
              </h2>
              <p class="text-sm text-secondary">
                {{ systemInfo.platform }} {{ systemInfo.platform_version }}
              </p>
            </div>
          </div>
          <div class="flex items-center gap-6 text-sm">
            <div class="text-center">
              <p class="text-muted">Uptime</p>
              <p class="font-semibold text-primary">{{ formatUptime(systemInfo.uptime_seconds || 0) }}</p>
            </div>
            <div class="text-center">
              <p class="text-muted">CPU Cores</p>
              <p class="font-semibold text-primary">{{ cpuMetrics.core_count || '-' }}</p>
            </div>
            <div class="text-center">
              <p class="text-muted">Total RAM</p>
              <p class="font-semibold text-primary">{{ formatBytes(memoryMetrics.total_bytes || 0, 0) }}</p>
            </div>
          </div>
        </div>
      </Card>

      <!-- Main Metrics Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- CPU Gauge Card -->
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-start justify-between mb-4">
              <div>
                <p class="text-sm text-secondary">CPU Usage</p>
                <p :class="['text-3xl font-bold', `text-${getStatusColor(cpuMetrics.percent || 0)}-500`]">
                  {{ Math.round(cpuMetrics.percent || 0) }}%
                </p>
              </div>
              <div :class="['p-2 rounded-lg', `bg-${getStatusColor(cpuMetrics.percent || 0)}-100 dark:bg-${getStatusColor(cpuMetrics.percent || 0)}-500/20`]">
                <CpuChipIcon :class="['h-5 w-5', `text-${getStatusColor(cpuMetrics.percent || 0)}-500`]" />
              </div>
            </div>
            <!-- Progress bar -->
            <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all duration-500', `bg-${getStatusColor(cpuMetrics.percent || 0)}-500`]"
                :style="{ width: `${cpuMetrics.percent || 0}%` }"
              />
            </div>
            <div class="mt-2 flex justify-between text-xs text-muted">
              <span>Load: {{ (cpuMetrics.load_avg_1m || 0).toFixed(2) }}</span>
              <span>{{ cpuMetrics.core_count || 0 }} cores</span>
            </div>
          </div>
        </Card>

        <!-- Memory Gauge Card -->
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-start justify-between mb-4">
              <div>
                <p class="text-sm text-secondary">Memory Usage</p>
                <p :class="['text-3xl font-bold', `text-${getStatusColor(memoryMetrics.percent || 0)}-500`]">
                  {{ Math.round(memoryMetrics.percent || 0) }}%
                </p>
              </div>
              <div :class="['p-2 rounded-lg', `bg-${getStatusColor(memoryMetrics.percent || 0)}-100 dark:bg-${getStatusColor(memoryMetrics.percent || 0)}-500/20`]">
                <CircleStackIcon :class="['h-5 w-5', `text-${getStatusColor(memoryMetrics.percent || 0)}-500`]" />
              </div>
            </div>
            <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all duration-500', `bg-${getStatusColor(memoryMetrics.percent || 0)}-500`]"
                :style="{ width: `${memoryMetrics.percent || 0}%` }"
              />
            </div>
            <div class="mt-2 flex justify-between text-xs text-muted">
              <span>{{ formatBytes(memoryMetrics.used_bytes || 0) }} used</span>
              <span>{{ formatBytes(memoryMetrics.total_bytes || 0) }} total</span>
            </div>
          </div>
        </Card>

        <!-- Disk Gauge Card -->
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-start justify-between mb-4">
              <div>
                <p class="text-sm text-secondary">Disk Usage ({{ primaryDisk.mount_point || '/' }})</p>
                <p :class="['text-3xl font-bold', `text-${getStatusColor(primaryDisk.percent || 0)}-500`]">
                  {{ Math.round(primaryDisk.percent || 0) }}%
                </p>
              </div>
              <div :class="['p-2 rounded-lg', `bg-${getStatusColor(primaryDisk.percent || 0)}-100 dark:bg-${getStatusColor(primaryDisk.percent || 0)}-500/20`]">
                <ChartBarIcon :class="['h-5 w-5', `text-${getStatusColor(primaryDisk.percent || 0)}-500`]" />
              </div>
            </div>
            <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all duration-500', `bg-${getStatusColor(primaryDisk.percent || 0)}-500`]"
                :style="{ width: `${primaryDisk.percent || 0}%` }"
              />
            </div>
            <div class="mt-2 flex justify-between text-xs text-muted">
              <span>{{ formatBytes(primaryDisk.free_bytes || 0) }} free</span>
              <span>{{ formatBytes(primaryDisk.total_bytes || 0) }} total</span>
            </div>
          </div>
        </Card>

        <!-- Network Card -->
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-start justify-between mb-4">
              <div>
                <p class="text-sm text-secondary">Network I/O</p>
                <p :class="['text-2xl font-bold', themeStore.isNeon ? 'neon-text-cyan' : 'text-primary']">
                  {{ networkMetrics.length }} interfaces
                </p>
              </div>
              <div class="p-2 rounded-lg bg-amber-100 dark:bg-amber-500/20">
                <SignalIcon class="h-5 w-5 text-amber-500" />
              </div>
            </div>
            <div class="space-y-2">
              <div class="flex justify-between text-sm">
                <span class="flex items-center gap-1 text-emerald-500">
                  <ArrowTrendingDownIcon class="h-4 w-4" /> RX
                </span>
                <span class="text-primary">{{ formatBytes(totalNetwork.rx) }}</span>
              </div>
              <div class="flex justify-between text-sm">
                <span class="flex items-center gap-1 text-blue-500">
                  <ArrowTrendingUpIcon class="h-4 w-4" /> TX
                </span>
                <span class="text-primary">{{ formatBytes(totalNetwork.tx) }}</span>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Container Health Summary -->
      <Card title="Container Health" subtitle="Quick container status overview" :neon="true">
        <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
          <button
            @click="navigateToContainers()"
            class="p-4 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors text-center"
          >
            <p class="text-3xl font-bold text-primary">{{ containerHealth.total }}</p>
            <p class="text-sm text-muted">Total</p>
          </button>
          <button
            @click="navigateToContainers('running')"
            class="p-4 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 transition-colors text-center"
          >
            <p class="text-3xl font-bold text-emerald-500">{{ containerHealth.running }}</p>
            <p class="text-sm text-emerald-600 dark:text-emerald-400">Running</p>
          </button>
          <button
            @click="navigateToContainers('stopped')"
            class="p-4 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors text-center"
          >
            <p class="text-3xl font-bold text-gray-500">{{ containerHealth.stopped }}</p>
            <p class="text-sm text-gray-600 dark:text-gray-400">Stopped</p>
          </button>
          <button
            @click="navigateToContainers('healthy')"
            class="p-4 rounded-lg bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors text-center"
          >
            <p class="text-3xl font-bold text-blue-500">{{ containerHealth.healthy }}</p>
            <p class="text-sm text-blue-600 dark:text-blue-400">Healthy</p>
          </button>
          <button
            @click="navigateToContainers('unhealthy')"
            :class="[
              'p-4 rounded-lg transition-colors text-center',
              containerHealth.unhealthy > 0
                ? 'bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/40 animate-pulse'
                : 'bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700'
            ]"
          >
            <p :class="['text-3xl font-bold', containerHealth.unhealthy > 0 ? 'text-red-500' : 'text-gray-400']">
              {{ containerHealth.unhealthy }}
            </p>
            <p :class="['text-sm', containerHealth.unhealthy > 0 ? 'text-red-600 dark:text-red-400' : 'text-gray-500']">
              Unhealthy
            </p>
          </button>
        </div>
      </Card>

      <!-- Resource Usage Chart -->
      <Card title="Resource Usage History" subtitle="CPU and Memory over time" :neon="true">
        <div class="h-64">
          <Line :data="resourceChartData" :options="resourceChartOptions" />
        </div>
      </Card>
    </template>

    <!-- Variation 2: Metrics Focus -->
    <template v-else-if="currentVariation === 2">
      <!-- Two-column layout: Charts left, Stats right -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Charts Column (2/3) -->
        <div class="lg:col-span-2 space-y-6">
          <!-- CPU & Memory Chart -->
          <Card title="CPU & Memory Usage" subtitle="Real-time monitoring" :neon="true">
            <div class="h-72">
              <Line :data="resourceChartData" :options="resourceChartOptions" />
            </div>
          </Card>

          <!-- Disk Usage Chart -->
          <Card title="Disk Usage by Mount Point" subtitle="All mounted filesystems" :neon="true">
            <div class="h-48">
              <Bar :data="diskChartData" :options="diskChartOptions" />
            </div>
          </Card>
        </div>

        <!-- Stats Column (1/3) -->
        <div class="space-y-4">
          <!-- System Summary -->
          <Card title="System Summary" :neon="true" :padding="false">
            <div class="divide-y divide-gray-200 dark:divide-gray-700">
              <div class="px-4 py-3 flex justify-between">
                <span class="text-secondary">Hostname</span>
                <span class="font-medium text-primary">{{ systemInfo.hostname || '-' }}</span>
              </div>
              <div class="px-4 py-3 flex justify-between">
                <span class="text-secondary">Platform</span>
                <span class="font-medium text-primary">{{ systemInfo.platform || '-' }}</span>
              </div>
              <div class="px-4 py-3 flex justify-between">
                <span class="text-secondary">Uptime</span>
                <span class="font-medium text-primary">{{ formatUptime(systemInfo.uptime_seconds || 0) }}</span>
              </div>
              <div class="px-4 py-3 flex justify-between">
                <span class="text-secondary">CPU Cores</span>
                <span class="font-medium text-primary">{{ cpuMetrics.core_count || '-' }}</span>
              </div>
              <div class="px-4 py-3 flex justify-between">
                <span class="text-secondary">Total Memory</span>
                <span class="font-medium text-primary">{{ formatBytes(memoryMetrics.total_bytes || 0, 0) }}</span>
              </div>
              <div class="px-4 py-3 flex justify-between">
                <span class="text-secondary">Load Avg (1/5/15m)</span>
                <span class="font-medium text-primary text-xs">
                  {{ (cpuMetrics.load_avg_1m || 0).toFixed(2) }} /
                  {{ (cpuMetrics.load_avg_5m || 0).toFixed(2) }} /
                  {{ (cpuMetrics.load_avg_15m || 0).toFixed(2) }}
                </span>
              </div>
            </div>
          </Card>

          <!-- Current Values -->
          <Card title="Current Metrics" :neon="true" :padding="false">
            <div class="divide-y divide-gray-200 dark:divide-gray-700">
              <div class="px-4 py-3">
                <div class="flex justify-between mb-1">
                  <span class="text-secondary">CPU</span>
                  <span :class="[`text-${getStatusColor(cpuMetrics.percent || 0)}-500`, 'font-bold']">
                    {{ Math.round(cpuMetrics.percent || 0) }}%
                  </span>
                </div>
                <div class="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full">
                  <div
                    :class="['h-full rounded-full', `bg-${getStatusColor(cpuMetrics.percent || 0)}-500`]"
                    :style="{ width: `${cpuMetrics.percent || 0}%` }"
                  />
                </div>
              </div>
              <div class="px-4 py-3">
                <div class="flex justify-between mb-1">
                  <span class="text-secondary">Memory</span>
                  <span :class="[`text-${getStatusColor(memoryMetrics.percent || 0)}-500`, 'font-bold']">
                    {{ Math.round(memoryMetrics.percent || 0) }}%
                  </span>
                </div>
                <div class="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full">
                  <div
                    :class="['h-full rounded-full', `bg-${getStatusColor(memoryMetrics.percent || 0)}-500`]"
                    :style="{ width: `${memoryMetrics.percent || 0}%` }"
                  />
                </div>
              </div>
              <div class="px-4 py-3">
                <div class="flex justify-between mb-1">
                  <span class="text-secondary">Disk (/)</span>
                  <span :class="[`text-${getStatusColor(primaryDisk.percent || 0)}-500`, 'font-bold']">
                    {{ Math.round(primaryDisk.percent || 0) }}%
                  </span>
                </div>
                <div class="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full">
                  <div
                    :class="['h-full rounded-full', `bg-${getStatusColor(primaryDisk.percent || 0)}-500`]"
                    :style="{ width: `${primaryDisk.percent || 0}%` }"
                  />
                </div>
              </div>
            </div>
          </Card>

          <!-- Container Summary -->
          <Card title="Containers" :neon="true" :padding="false">
            <div class="p-4">
              <div class="flex items-center justify-center gap-4">
                <button
                  @click="navigateToContainers('running')"
                  class="text-center hover:opacity-80 transition-opacity"
                >
                  <div class="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
                    <span class="text-2xl font-bold text-emerald-500">{{ containerHealth.running }}</span>
                  </div>
                  <p class="text-xs text-muted mt-1">Running</p>
                </button>
                <button
                  @click="navigateToContainers('unhealthy')"
                  class="text-center hover:opacity-80 transition-opacity"
                >
                  <div :class="['w-16 h-16 rounded-full flex items-center justify-center', containerHealth.unhealthy > 0 ? 'bg-red-100 dark:bg-red-900/30 animate-pulse' : 'bg-gray-100 dark:bg-gray-800']">
                    <span :class="['text-2xl font-bold', containerHealth.unhealthy > 0 ? 'text-red-500' : 'text-gray-400']">
                      {{ containerHealth.unhealthy }}
                    </span>
                  </div>
                  <p class="text-xs text-muted mt-1">Unhealthy</p>
                </button>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </template>

    <!-- Variation 3: Compact Overview -->
    <template v-else-if="currentVariation === 3">
      <!-- Compact header with system info -->
      <Card :neon="true" :padding="false">
        <div class="px-4 py-3 flex items-center justify-between gap-4 flex-wrap">
          <div class="flex items-center gap-3">
            <ComputerDesktopIcon class="h-6 w-6 text-blue-500" />
            <span class="font-semibold text-primary">{{ systemInfo.hostname || 'Docker Host' }}</span>
            <span class="text-sm text-muted">{{ systemInfo.platform }} | Up {{ formatUptime(systemInfo.uptime_seconds || 0) }}</span>
          </div>
          <div class="flex items-center gap-4">
            <button @click="navigateToContainers()" class="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 text-sm hover:bg-emerald-200 dark:hover:bg-emerald-900/50 transition-colors">
              <ServerIcon class="h-4 w-4" />
              {{ containerHealth.running }}/{{ containerHealth.total }} containers
            </button>
            <button
              v-if="containerHealth.unhealthy > 0"
              @click="navigateToContainers('unhealthy')"
              class="flex items-center gap-2 px-3 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 text-sm hover:bg-red-200 dark:hover:bg-red-900/50 transition-colors animate-pulse"
            >
              <ExclamationTriangleIcon class="h-4 w-4" />
              {{ containerHealth.unhealthy }} unhealthy
            </button>
          </div>
        </div>
      </Card>

      <!-- Compact metrics grid -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center justify-between mb-2">
              <span class="text-sm text-secondary">CPU</span>
              <CpuChipIcon :class="['h-4 w-4', `text-${getStatusColor(cpuMetrics.percent || 0)}-500`]" />
            </div>
            <div class="flex items-baseline gap-1">
              <span :class="['text-2xl font-bold', `text-${getStatusColor(cpuMetrics.percent || 0)}-500`]">
                {{ Math.round(cpuMetrics.percent || 0) }}
              </span>
              <span class="text-sm text-muted">%</span>
            </div>
            <div class="h-1 bg-gray-200 dark:bg-gray-700 rounded-full mt-2">
              <div
                :class="['h-full rounded-full', `bg-${getStatusColor(cpuMetrics.percent || 0)}-500`]"
                :style="{ width: `${cpuMetrics.percent || 0}%` }"
              />
            </div>
          </div>
        </Card>

        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center justify-between mb-2">
              <span class="text-sm text-secondary">Memory</span>
              <CircleStackIcon :class="['h-4 w-4', `text-${getStatusColor(memoryMetrics.percent || 0)}-500`]" />
            </div>
            <div class="flex items-baseline gap-1">
              <span :class="['text-2xl font-bold', `text-${getStatusColor(memoryMetrics.percent || 0)}-500`]">
                {{ Math.round(memoryMetrics.percent || 0) }}
              </span>
              <span class="text-sm text-muted">%</span>
            </div>
            <div class="h-1 bg-gray-200 dark:bg-gray-700 rounded-full mt-2">
              <div
                :class="['h-full rounded-full', `bg-${getStatusColor(memoryMetrics.percent || 0)}-500`]"
                :style="{ width: `${memoryMetrics.percent || 0}%` }"
              />
            </div>
          </div>
        </Card>

        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center justify-between mb-2">
              <span class="text-sm text-secondary">Disk</span>
              <ChartBarIcon :class="['h-4 w-4', `text-${getStatusColor(primaryDisk.percent || 0)}-500`]" />
            </div>
            <div class="flex items-baseline gap-1">
              <span :class="['text-2xl font-bold', `text-${getStatusColor(primaryDisk.percent || 0)}-500`]">
                {{ Math.round(primaryDisk.percent || 0) }}
              </span>
              <span class="text-sm text-muted">%</span>
            </div>
            <div class="h-1 bg-gray-200 dark:bg-gray-700 rounded-full mt-2">
              <div
                :class="['h-full rounded-full', `bg-${getStatusColor(primaryDisk.percent || 0)}-500`]"
                :style="{ width: `${primaryDisk.percent || 0}%` }"
              />
            </div>
          </div>
        </Card>

        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center justify-between mb-2">
              <span class="text-sm text-secondary">Network</span>
              <SignalIcon class="h-4 w-4 text-amber-500" />
            </div>
            <div class="text-xs space-y-1">
              <div class="flex justify-between">
                <span class="text-emerald-500">RX</span>
                <span class="text-primary">{{ formatBytes(totalNetwork.rx) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-blue-500">TX</span>
                <span class="text-primary">{{ formatBytes(totalNetwork.tx) }}</span>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Compact Chart -->
      <Card title="Resource Trend" :neon="true">
        <div class="h-48">
          <Line :data="resourceChartData" :options="resourceChartOptions" />
        </div>
      </Card>

      <!-- Disk breakdown -->
      <Card title="Storage" subtitle="All mount points" :neon="true" v-if="diskMetrics.length > 1">
        <div class="space-y-3">
          <div v-for="disk in diskMetrics" :key="disk.mount_point" class="flex items-center gap-4">
            <span class="w-24 text-sm text-secondary truncate">{{ disk.mount_point }}</span>
            <div class="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full">
              <div
                :class="['h-full rounded-full', `bg-${getStatusColor(disk.percent)}-500`]"
                :style="{ width: `${disk.percent}%` }"
              />
            </div>
            <span :class="['text-sm font-medium w-12 text-right', `text-${getStatusColor(disk.percent)}-500`]">
              {{ Math.round(disk.percent) }}%
            </span>
          </div>
        </div>
      </Card>
    </template>

    <!-- Variation 4: Grid Tiles -->
    <template v-else-if="currentVariation === 4">
      <!-- Large Tile Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- CPU Tile -->
        <Card :neon="true" :padding="false">
          <div class="p-6">
            <div class="flex items-start justify-between">
              <div>
                <p class="text-sm font-medium text-secondary uppercase tracking-wider">CPU Usage</p>
                <p :class="['text-5xl font-black mt-2', `text-${getStatusColor(cpuMetrics.percent || 0)}-500`]">
                  {{ Math.round(cpuMetrics.percent || 0) }}<span class="text-2xl">%</span>
                </p>
                <p class="text-sm text-muted mt-2">{{ cpuMetrics.core_count || 0 }} cores @ {{ (cpuMetrics.frequency_mhz || 0).toFixed(0) }} MHz</p>
              </div>
              <div :class="['p-4 rounded-2xl', `bg-${getStatusColor(cpuMetrics.percent || 0)}-100 dark:bg-${getStatusColor(cpuMetrics.percent || 0)}-500/20`]">
                <CpuChipIcon :class="['h-10 w-10', `text-${getStatusColor(cpuMetrics.percent || 0)}-500`]" />
              </div>
            </div>
            <div class="mt-6 h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all duration-700', `bg-${getStatusColor(cpuMetrics.percent || 0)}-500`]"
                :style="{ width: `${cpuMetrics.percent || 0}%` }"
              />
            </div>
            <div class="mt-3 flex justify-between text-sm text-muted">
              <span>Load: {{ (cpuMetrics.load_avg_1m || 0).toFixed(2) }} / {{ (cpuMetrics.load_avg_5m || 0).toFixed(2) }} / {{ (cpuMetrics.load_avg_15m || 0).toFixed(2) }}</span>
            </div>
          </div>
        </Card>

        <!-- Memory Tile -->
        <Card :neon="true" :padding="false">
          <div class="p-6">
            <div class="flex items-start justify-between">
              <div>
                <p class="text-sm font-medium text-secondary uppercase tracking-wider">Memory Usage</p>
                <p :class="['text-5xl font-black mt-2', `text-${getStatusColor(memoryMetrics.percent || 0)}-500`]">
                  {{ Math.round(memoryMetrics.percent || 0) }}<span class="text-2xl">%</span>
                </p>
                <p class="text-sm text-muted mt-2">{{ formatBytes(memoryMetrics.used_bytes || 0) }} / {{ formatBytes(memoryMetrics.total_bytes || 0) }}</p>
              </div>
              <div :class="['p-4 rounded-2xl', `bg-${getStatusColor(memoryMetrics.percent || 0)}-100 dark:bg-${getStatusColor(memoryMetrics.percent || 0)}-500/20`]">
                <CircleStackIcon :class="['h-10 w-10', `text-${getStatusColor(memoryMetrics.percent || 0)}-500`]" />
              </div>
            </div>
            <div class="mt-6 h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all duration-700', `bg-${getStatusColor(memoryMetrics.percent || 0)}-500`]"
                :style="{ width: `${memoryMetrics.percent || 0}%` }"
              />
            </div>
            <div class="mt-3 flex justify-between text-sm text-muted">
              <span>Swap: {{ formatBytes(memoryMetrics.swap_used_bytes || 0) }} / {{ formatBytes(memoryMetrics.swap_total_bytes || 0) }}</span>
              <span v-if="memoryMetrics.swap_percent">{{ memoryMetrics.swap_percent.toFixed(1) }}%</span>
            </div>
          </div>
        </Card>

        <!-- Disk Tile -->
        <Card :neon="true" :padding="false">
          <div class="p-6">
            <div class="flex items-start justify-between">
              <div>
                <p class="text-sm font-medium text-secondary uppercase tracking-wider">Disk Usage</p>
                <p :class="['text-5xl font-black mt-2', `text-${getStatusColor(primaryDisk.percent || 0)}-500`]">
                  {{ Math.round(primaryDisk.percent || 0) }}<span class="text-2xl">%</span>
                </p>
                <p class="text-sm text-muted mt-2">{{ formatBytes(primaryDisk.free_bytes || 0) }} free</p>
              </div>
              <div :class="['p-4 rounded-2xl', `bg-${getStatusColor(primaryDisk.percent || 0)}-100 dark:bg-${getStatusColor(primaryDisk.percent || 0)}-500/20`]">
                <ChartBarIcon :class="['h-10 w-10', `text-${getStatusColor(primaryDisk.percent || 0)}-500`]" />
              </div>
            </div>
            <div class="mt-6 space-y-2">
              <div v-for="disk in diskMetrics.slice(0, 3)" :key="disk.mount_point">
                <div class="flex justify-between text-xs mb-1">
                  <span class="text-muted">{{ disk.mount_point }}</span>
                  <span :class="`text-${getStatusColor(disk.percent)}-500`">{{ disk.percent.toFixed(0) }}%</span>
                </div>
                <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full">
                  <div
                    :class="['h-full rounded-full', `bg-${getStatusColor(disk.percent)}-500`]"
                    :style="{ width: `${disk.percent}%` }"
                  />
                </div>
              </div>
            </div>
          </div>
        </Card>

        <!-- Containers Tile -->
        <Card :neon="true" :padding="false">
          <div class="p-6">
            <div class="flex items-start justify-between">
              <div>
                <p class="text-sm font-medium text-secondary uppercase tracking-wider">Containers</p>
                <p class="text-5xl font-black mt-2 text-blue-500">
                  {{ containerHealth.total }}
                </p>
                <p class="text-sm text-muted mt-2">{{ containerHealth.running }} running</p>
              </div>
              <div class="p-4 rounded-2xl bg-blue-100 dark:bg-blue-500/20">
                <ServerIcon class="h-10 w-10 text-blue-500" />
              </div>
            </div>
            <div class="mt-6 grid grid-cols-4 gap-2">
              <button @click="navigateToContainers('running')" class="text-center p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                <p class="text-lg font-bold text-emerald-500">{{ containerHealth.running }}</p>
                <p class="text-xs text-muted">Running</p>
              </button>
              <button @click="navigateToContainers('stopped')" class="text-center p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                <p class="text-lg font-bold text-gray-500">{{ containerHealth.stopped }}</p>
                <p class="text-xs text-muted">Stopped</p>
              </button>
              <button @click="navigateToContainers('healthy')" class="text-center p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                <p class="text-lg font-bold text-blue-500">{{ containerHealth.healthy }}</p>
                <p class="text-xs text-muted">Healthy</p>
              </button>
              <button
                @click="navigateToContainers('unhealthy')"
                :class="['text-center p-2 rounded-lg transition-colors', containerHealth.unhealthy > 0 ? 'bg-red-50 dark:bg-red-900/20 animate-pulse' : 'hover:bg-gray-100 dark:hover:bg-gray-800']"
              >
                <p :class="['text-lg font-bold', containerHealth.unhealthy > 0 ? 'text-red-500' : 'text-gray-400']">
                  {{ containerHealth.unhealthy }}
                </p>
                <p class="text-xs text-muted">Unhealthy</p>
              </button>
            </div>
          </div>
        </Card>
      </div>

      <!-- Network + System Info Row -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Network Tile -->
        <Card :neon="true" :padding="false">
          <div class="p-6">
            <p class="text-sm font-medium text-secondary uppercase tracking-wider mb-4">Network I/O</p>
            <div class="grid grid-cols-2 gap-4">
              <div class="text-center p-4 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl">
                <ArrowTrendingDownIcon class="h-6 w-6 text-emerald-500 mx-auto mb-2" />
                <p class="text-2xl font-bold text-emerald-500">{{ formatBytes(totalNetwork.rx) }}</p>
                <p class="text-xs text-muted">Received</p>
              </div>
              <div class="text-center p-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                <ArrowTrendingUpIcon class="h-6 w-6 text-blue-500 mx-auto mb-2" />
                <p class="text-2xl font-bold text-blue-500">{{ formatBytes(totalNetwork.tx) }}</p>
                <p class="text-xs text-muted">Transmitted</p>
              </div>
            </div>
            <p class="text-xs text-muted text-center mt-4">{{ networkMetrics.length }} network interface(s)</p>
          </div>
        </Card>

        <!-- System Info Tile -->
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
                <span class="font-medium text-primary">{{ formatUptime(systemInfo.uptime_seconds || 0) }}</span>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Chart -->
      <Card title="Resource History" :neon="true">
        <div class="h-64">
          <Line :data="resourceChartData" :options="resourceChartOptions" />
        </div>
      </Card>
    </template>

    <!-- Variation 5: Minimal Modern -->
    <template v-else-if="currentVariation === 5">
      <!-- Minimal header -->
      <div class="text-center pb-4">
        <p class="text-muted text-sm">{{ systemInfo.hostname || 'Docker Host' }} | {{ systemInfo.platform }}</p>
        <p class="text-xs text-muted">Up {{ formatUptime(systemInfo.uptime_seconds || 0) }}</p>
      </div>

      <!-- Centered Metrics -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-8 max-w-4xl mx-auto">
        <!-- CPU -->
        <div class="text-center">
          <div class="relative w-24 h-24 mx-auto">
            <svg class="w-24 h-24 transform -rotate-90">
              <circle cx="48" cy="48" r="40" stroke-width="8" fill="none" class="stroke-gray-200 dark:stroke-gray-700" />
              <circle
                cx="48" cy="48" r="40" stroke-width="8" fill="none"
                :class="[`stroke-${getStatusColor(cpuMetrics.percent || 0)}-500`]"
                stroke-linecap="round"
                :stroke-dasharray="251.2"
                :stroke-dashoffset="251.2 - (251.2 * (cpuMetrics.percent || 0) / 100)"
                style="transition: stroke-dashoffset 0.5s ease"
              />
            </svg>
            <div class="absolute inset-0 flex items-center justify-center">
              <span :class="['text-xl font-bold', `text-${getStatusColor(cpuMetrics.percent || 0)}-500`]">
                {{ Math.round(cpuMetrics.percent || 0) }}%
              </span>
            </div>
          </div>
          <p class="text-sm text-muted mt-2">CPU</p>
        </div>

        <!-- Memory -->
        <div class="text-center">
          <div class="relative w-24 h-24 mx-auto">
            <svg class="w-24 h-24 transform -rotate-90">
              <circle cx="48" cy="48" r="40" stroke-width="8" fill="none" class="stroke-gray-200 dark:stroke-gray-700" />
              <circle
                cx="48" cy="48" r="40" stroke-width="8" fill="none"
                :class="[`stroke-${getStatusColor(memoryMetrics.percent || 0)}-500`]"
                stroke-linecap="round"
                :stroke-dasharray="251.2"
                :stroke-dashoffset="251.2 - (251.2 * (memoryMetrics.percent || 0) / 100)"
                style="transition: stroke-dashoffset 0.5s ease"
              />
            </svg>
            <div class="absolute inset-0 flex items-center justify-center">
              <span :class="['text-xl font-bold', `text-${getStatusColor(memoryMetrics.percent || 0)}-500`]">
                {{ Math.round(memoryMetrics.percent || 0) }}%
              </span>
            </div>
          </div>
          <p class="text-sm text-muted mt-2">Memory</p>
        </div>

        <!-- Disk -->
        <div class="text-center">
          <div class="relative w-24 h-24 mx-auto">
            <svg class="w-24 h-24 transform -rotate-90">
              <circle cx="48" cy="48" r="40" stroke-width="8" fill="none" class="stroke-gray-200 dark:stroke-gray-700" />
              <circle
                cx="48" cy="48" r="40" stroke-width="8" fill="none"
                :class="[`stroke-${getStatusColor(primaryDisk.percent || 0)}-500`]"
                stroke-linecap="round"
                :stroke-dasharray="251.2"
                :stroke-dashoffset="251.2 - (251.2 * (primaryDisk.percent || 0) / 100)"
                style="transition: stroke-dashoffset 0.5s ease"
              />
            </svg>
            <div class="absolute inset-0 flex items-center justify-center">
              <span :class="['text-xl font-bold', `text-${getStatusColor(primaryDisk.percent || 0)}-500`]">
                {{ Math.round(primaryDisk.percent || 0) }}%
              </span>
            </div>
          </div>
          <p class="text-sm text-muted mt-2">Disk</p>
        </div>

        <!-- Containers -->
        <div class="text-center">
          <div class="relative w-24 h-24 mx-auto">
            <svg class="w-24 h-24 transform -rotate-90">
              <circle cx="48" cy="48" r="40" stroke-width="8" fill="none" class="stroke-gray-200 dark:stroke-gray-700" />
              <circle
                cx="48" cy="48" r="40" stroke-width="8" fill="none"
                :class="containerHealth.unhealthy > 0 ? 'stroke-red-500' : 'stroke-emerald-500'"
                stroke-linecap="round"
                :stroke-dasharray="251.2"
                :stroke-dashoffset="containerHealth.total > 0 ? 251.2 - (251.2 * containerHealth.running / containerHealth.total) : 251.2"
                style="transition: stroke-dashoffset 0.5s ease"
              />
            </svg>
            <div class="absolute inset-0 flex items-center justify-center">
              <span :class="['text-xl font-bold', containerHealth.unhealthy > 0 ? 'text-red-500' : 'text-emerald-500']">
                {{ containerHealth.running }}/{{ containerHealth.total }}
              </span>
            </div>
          </div>
          <p class="text-sm text-muted mt-2">Containers</p>
        </div>
      </div>

      <!-- Alert banner if unhealthy containers -->
      <button
        v-if="containerHealth.unhealthy > 0"
        @click="navigateToContainers('unhealthy')"
        class="w-full max-w-md mx-auto mt-8 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl flex items-center justify-center gap-3 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors animate-pulse"
      >
        <ExclamationTriangleIcon class="h-5 w-5" />
        <span class="font-medium">{{ containerHealth.unhealthy }} unhealthy container(s) - Click to view</span>
      </button>

      <!-- Minimal chart -->
      <Card class="mt-8 max-w-4xl mx-auto" :neon="true">
        <div class="h-48">
          <Line :data="resourceChartData" :options="resourceChartOptions" />
        </div>
      </Card>

      <!-- Quick stats -->
      <div class="max-w-2xl mx-auto mt-8 grid grid-cols-2 md:grid-cols-4 gap-4 text-center text-sm">
        <div>
          <p class="text-muted">Network RX</p>
          <p class="font-semibold text-primary">{{ formatBytes(totalNetwork.rx) }}</p>
        </div>
        <div>
          <p class="text-muted">Network TX</p>
          <p class="font-semibold text-primary">{{ formatBytes(totalNetwork.tx) }}</p>
        </div>
        <div>
          <p class="text-muted">CPU Cores</p>
          <p class="font-semibold text-primary">{{ cpuMetrics.core_count || '-' }}</p>
        </div>
        <div>
          <p class="text-muted">Total RAM</p>
          <p class="font-semibold text-primary">{{ formatBytes(memoryMetrics.total_bytes || 0, 0) }}</p>
        </div>
      </div>
    </template>
  </div>
</template>
