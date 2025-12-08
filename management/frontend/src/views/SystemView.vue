<script setup>
import { ref, onMounted, computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useNotificationStore } from '@/stores/notifications'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import {
  CpuChipIcon,
  CircleStackIcon,
  ServerStackIcon,
  ClockIcon,
  ArrowPathIcon,
  SignalIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
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

const themeStore = useThemeStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const systemInfo = ref({
  hostname: '',
  platform: '',
  architecture: '',
  kernel: '',
  uptime: '',
  cpu: {
    model: '',
    cores: 0,
    usage: 0,
  },
  memory: {
    total: 0,
    used: 0,
    free: 0,
    percent: 0,
  },
  disk: {
    total: 0,
    used: 0,
    free: 0,
    percent: 0,
  },
  network: {
    interfaces: [],
  },
  docker: {
    version: '',
    containers_running: 0,
    containers_total: 0,
    images: 0,
  },
})

// Health checks
const healthChecks = ref([])

// Chart colors based on theme
const chartColors = computed(() => {
  if (themeStore.isNeon) {
    return {
      cpu: 'rgb(34, 211, 238)',
      memory: 'rgb(244, 114, 182)',
      disk: 'rgb(52, 211, 153)',
      grid: 'rgba(34, 211, 238, 0.1)',
    }
  }
  return {
    cpu: 'rgb(59, 130, 246)',
    memory: 'rgb(168, 85, 247)',
    disk: 'rgb(34, 197, 94)',
    grid: 'rgba(107, 114, 128, 0.1)',
  }
})

// Mock historical data for charts
const cpuHistory = ref([45, 52, 48, 61, 55, 49, 47])
const memoryHistory = ref([62, 64, 63, 67, 65, 66, 68])

const cpuChartData = computed(() => ({
  labels: ['6m', '5m', '4m', '3m', '2m', '1m', 'Now'],
  datasets: [
    {
      label: 'CPU Usage %',
      data: cpuHistory.value,
      borderColor: chartColors.value.cpu,
      backgroundColor: `${chartColors.value.cpu.replace('rgb', 'rgba').replace(')', ', 0.1)')}`,
      fill: true,
      tension: 0.4,
    },
  ],
}))

const memoryChartData = computed(() => ({
  labels: ['6m', '5m', '4m', '3m', '2m', '1m', 'Now'],
  datasets: [
    {
      label: 'Memory Usage %',
      data: memoryHistory.value,
      borderColor: chartColors.value.memory,
      backgroundColor: `${chartColors.value.memory.replace('rgb', 'rgba').replace(')', ', 0.1)')}`,
      fill: true,
      tension: 0.4,
    },
  ],
}))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false,
    },
  },
  scales: {
    x: {
      grid: { color: chartColors.value.grid },
      ticks: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280' },
    },
    y: {
      grid: { color: chartColors.value.grid },
      ticks: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280' },
      min: 0,
      max: 100,
    },
  },
}))

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

function getProgressColor(percent) {
  if (percent >= 90) return 'bg-red-500'
  if (percent >= 75) return 'bg-amber-500'
  return themeStore.isNeon ? 'bg-cyan-400' : 'bg-blue-500'
}

async function loadData() {
  loading.value = true
  try {
    const [systemRes, healthRes] = await Promise.all([
      api.system.getInfo(),
      api.system.getHealth(),
    ])
    systemInfo.value = systemRes.data
    healthChecks.value = healthRes.data.checks || []

    // Update chart data with real values
    cpuHistory.value.push(systemInfo.value.cpu?.usage || 0)
    cpuHistory.value.shift()
    memoryHistory.value.push(systemInfo.value.memory?.percent || 0)
    memoryHistory.value.shift()
  } catch (error) {
    notificationStore.error('Failed to load system information')
  } finally {
    loading.value = false
  }
}

async function runHealthCheck() {
  try {
    const response = await api.system.getHealth()
    healthChecks.value = response.data.checks || []
    notificationStore.success('Health check completed')
  } catch (error) {
    notificationStore.error('Health check failed')
  }
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1
          :class="[
            'text-2xl font-bold',
            themeStore.isNeon ? 'neon-text-cyan' : 'text-primary'
          ]"
        >
          System
        </h1>
        <p class="text-secondary mt-1">Server health and resource monitoring</p>
      </div>
      <button
        @click="loadData"
        class="btn-secondary flex items-center gap-2"
      >
        <ArrowPathIcon class="h-4 w-4" />
        Refresh
      </button>
    </div>

    <LoadingSpinner v-if="loading" size="lg" text="Loading system info..." class="py-12" />

    <template v-else>
      <!-- Quick Stats -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
                <CpuChipIcon class="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">CPU Usage</p>
                <p class="text-xl font-bold text-primary">{{ systemInfo.cpu?.usage?.toFixed(1) || 0 }}%</p>
              </div>
            </div>
            <div class="mt-3 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all', getProgressColor(systemInfo.cpu?.usage || 0)]"
                :style="{ width: `${systemInfo.cpu?.usage || 0}%` }"
              ></div>
            </div>
          </div>
        </Card>

        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-500/20">
                <CircleStackIcon class="h-5 w-5 text-purple-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Memory Usage</p>
                <p class="text-xl font-bold text-primary">{{ systemInfo.memory?.percent?.toFixed(1) || 0 }}%</p>
              </div>
            </div>
            <div class="mt-3 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all', getProgressColor(systemInfo.memory?.percent || 0)]"
                :style="{ width: `${systemInfo.memory?.percent || 0}%` }"
              ></div>
            </div>
          </div>
        </Card>

        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-500/20">
                <ServerStackIcon class="h-5 w-5 text-emerald-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Disk Usage</p>
                <p class="text-xl font-bold text-primary">{{ systemInfo.disk?.percent?.toFixed(1) || 0 }}%</p>
              </div>
            </div>
            <div class="mt-3 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all', getProgressColor(systemInfo.disk?.percent || 0)]"
                :style="{ width: `${systemInfo.disk?.percent || 0}%` }"
              ></div>
            </div>
          </div>
        </Card>

        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-amber-100 dark:bg-amber-500/20">
                <ClockIcon class="h-5 w-5 text-amber-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Uptime</p>
                <p class="text-xl font-bold text-primary">{{ systemInfo.uptime || 'N/A' }}</p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Charts -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="CPU History" subtitle="Last 7 minutes" :neon="true">
          <div class="h-48">
            <Line :data="cpuChartData" :options="chartOptions" />
          </div>
        </Card>

        <Card title="Memory History" subtitle="Last 7 minutes" :neon="true">
          <div class="h-48">
            <Line :data="memoryChartData" :options="chartOptions" />
          </div>
        </Card>
      </div>

      <!-- System Details -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Server Info -->
        <Card title="Server Information" :neon="true">
          <div class="space-y-3">
            <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
              <span class="text-secondary">Hostname</span>
              <span class="font-medium text-primary">{{ systemInfo.hostname || 'N/A' }}</span>
            </div>
            <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
              <span class="text-secondary">Platform</span>
              <span class="font-medium text-primary">{{ systemInfo.platform || 'N/A' }}</span>
            </div>
            <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
              <span class="text-secondary">Architecture</span>
              <span class="font-medium text-primary">{{ systemInfo.architecture || 'N/A' }}</span>
            </div>
            <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
              <span class="text-secondary">Kernel</span>
              <span class="font-medium text-primary">{{ systemInfo.kernel || 'N/A' }}</span>
            </div>
            <div class="flex justify-between py-2">
              <span class="text-secondary">CPU Model</span>
              <span class="font-medium text-primary text-right max-w-[200px] truncate">
                {{ systemInfo.cpu?.model || 'N/A' }}
              </span>
            </div>
          </div>
        </Card>

        <!-- Docker Info -->
        <Card title="Docker Information" :neon="true">
          <div class="space-y-3">
            <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
              <span class="text-secondary">Docker Version</span>
              <span class="font-medium text-primary">{{ systemInfo.docker?.version || 'N/A' }}</span>
            </div>
            <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
              <span class="text-secondary">Running Containers</span>
              <span class="font-medium text-primary">{{ systemInfo.docker?.containers_running || 0 }}</span>
            </div>
            <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
              <span class="text-secondary">Total Containers</span>
              <span class="font-medium text-primary">{{ systemInfo.docker?.containers_total || 0 }}</span>
            </div>
            <div class="flex justify-between py-2">
              <span class="text-secondary">Images</span>
              <span class="font-medium text-primary">{{ systemInfo.docker?.images || 0 }}</span>
            </div>
          </div>
        </Card>
      </div>

      <!-- Resource Details -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Memory Details -->
        <Card title="Memory Details" :neon="true">
          <div class="space-y-3">
            <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
              <span class="text-secondary">Total</span>
              <span class="font-medium text-primary">{{ formatBytes(systemInfo.memory?.total) }}</span>
            </div>
            <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
              <span class="text-secondary">Used</span>
              <span class="font-medium text-primary">{{ formatBytes(systemInfo.memory?.used) }}</span>
            </div>
            <div class="flex justify-between py-2">
              <span class="text-secondary">Free</span>
              <span class="font-medium text-primary">{{ formatBytes(systemInfo.memory?.free) }}</span>
            </div>
          </div>
        </Card>

        <!-- Disk Details -->
        <Card title="Disk Details" :neon="true">
          <div class="space-y-3">
            <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
              <span class="text-secondary">Total</span>
              <span class="font-medium text-primary">{{ formatBytes(systemInfo.disk?.total) }}</span>
            </div>
            <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
              <span class="text-secondary">Used</span>
              <span class="font-medium text-primary">{{ formatBytes(systemInfo.disk?.used) }}</span>
            </div>
            <div class="flex justify-between py-2">
              <span class="text-secondary">Free</span>
              <span class="font-medium text-primary">{{ formatBytes(systemInfo.disk?.free) }}</span>
            </div>
          </div>
        </Card>
      </div>

      <!-- Health Checks -->
      <Card title="Health Checks" :neon="true">
        <template #actions>
          <button @click="runHealthCheck" class="btn-secondary text-sm flex items-center gap-1">
            <SignalIcon class="h-4 w-4" />
            Run Check
          </button>
        </template>

        <div class="space-y-3">
          <div
            v-for="check in healthChecks"
            :key="check.name"
            class="flex items-center justify-between p-3 rounded-lg bg-surface-hover"
          >
            <div class="flex items-center gap-3">
              <div
                :class="[
                  'p-2 rounded-lg',
                  check.status === 'healthy'
                    ? 'bg-emerald-100 dark:bg-emerald-500/20'
                    : 'bg-red-100 dark:bg-red-500/20'
                ]"
              >
                <CheckCircleIcon
                  v-if="check.status === 'healthy'"
                  class="h-5 w-5 text-emerald-500"
                />
                <ExclamationTriangleIcon v-else class="h-5 w-5 text-red-500" />
              </div>
              <div>
                <p class="font-medium text-primary">{{ check.name }}</p>
                <p class="text-xs text-muted">{{ check.message || 'OK' }}</p>
              </div>
            </div>
            <span
              :class="[
                'text-sm font-medium',
                check.status === 'healthy' ? 'text-emerald-500' : 'text-red-500'
              ]"
            >
              {{ check.status }}
            </span>
          </div>
        </div>
      </Card>
    </template>
  </div>
</template>
