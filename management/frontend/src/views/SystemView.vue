<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
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
  GlobeAltIcon,
  ShieldCheckIcon,
  CommandLineIcon,
  WifiIcon,
  LockClosedIcon,
  PlayIcon,
  StopIcon,
  XMarkIcon,
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
const authStore = useAuthStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const activeTab = ref('overview')

// Tab definitions
const tabs = [
  { id: 'overview', name: 'Overview', icon: CpuChipIcon },
  { id: 'network', name: 'Network', icon: GlobeAltIcon },
  { id: 'ssl', name: 'SSL', icon: ShieldCheckIcon },
  { id: 'terminal', name: 'Terminal', icon: CommandLineIcon },
]

// System info state
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

// Network info state
const networkInfo = ref({
  hostname: '',
  fqdn: '',
  interfaces: [],
  gateway: null,
  dns_servers: [],
})
const networkLoading = ref(false)

// SSL info state
const sslInfo = ref({
  configured: false,
  certificates: [],
  error: null,
})
const sslLoading = ref(false)

// Terminal state
const terminalTargets = ref([])
const selectedTarget = ref('')
const terminalConnected = ref(false)
const terminalConnecting = ref(false)
const terminalElement = ref(null)
let terminal = null
let fitAddon = null
let websocket = null

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

async function loadNetworkInfo() {
  networkLoading.value = true
  try {
    const response = await api.system.getNetwork()
    networkInfo.value = response.data
  } catch (error) {
    notificationStore.error('Failed to load network information')
  } finally {
    networkLoading.value = false
  }
}

async function loadSslInfo() {
  sslLoading.value = true
  try {
    const response = await api.system.getSsl()
    sslInfo.value = response.data
  } catch (error) {
    notificationStore.error('Failed to load SSL information')
  } finally {
    sslLoading.value = false
  }
}

async function loadTerminalTargets() {
  try {
    const response = await api.system.getTerminalTargets()
    terminalTargets.value = response.data.targets || []
    if (terminalTargets.value.length > 0 && !selectedTarget.value) {
      selectedTarget.value = terminalTargets.value[0].id
    }
  } catch (error) {
    console.error('Failed to load terminal targets:', error)
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

// Terminal functions
async function initTerminal() {
  if (terminal) return

  try {
    // Dynamically import xterm
    const { Terminal } = await import('xterm')
    const { FitAddon } = await import('xterm-addon-fit')

    // Import CSS
    await import('xterm/css/xterm.css')

    terminal = new Terminal({
      cursorBlink: true,
      theme: themeStore.isDark ? {
        background: '#1a1b26',
        foreground: '#a9b1d6',
        cursor: '#c0caf5',
        cursorAccent: '#1a1b26',
        selection: 'rgba(99, 117, 171, 0.3)',
        black: '#414868',
        red: '#f7768e',
        green: '#9ece6a',
        yellow: '#e0af68',
        blue: '#7aa2f7',
        magenta: '#bb9af7',
        cyan: '#7dcfff',
        white: '#c0caf5',
        brightBlack: '#414868',
        brightRed: '#f7768e',
        brightGreen: '#9ece6a',
        brightYellow: '#e0af68',
        brightBlue: '#7aa2f7',
        brightMagenta: '#bb9af7',
        brightCyan: '#7dcfff',
        brightWhite: '#c0caf5',
      } : {
        background: '#ffffff',
        foreground: '#24292e',
        cursor: '#24292e',
      },
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    })

    fitAddon = new FitAddon()
    terminal.loadAddon(fitAddon)

    await nextTick()
    if (terminalElement.value) {
      terminal.open(terminalElement.value)
      fitAddon.fit()
    }

    // Handle terminal input
    terminal.onData((data) => {
      if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'input', data }))
      }
    })

    // Handle resize
    const resizeObserver = new ResizeObserver(() => {
      if (fitAddon) {
        fitAddon.fit()
        if (websocket && websocket.readyState === WebSocket.OPEN) {
          websocket.send(JSON.stringify({
            type: 'resize',
            rows: terminal.rows,
            cols: terminal.cols,
          }))
        }
      }
    })
    if (terminalElement.value) {
      resizeObserver.observe(terminalElement.value)
    }

  } catch (error) {
    console.error('Failed to initialize terminal:', error)
    notificationStore.error('Failed to initialize terminal')
  }
}

function connectTerminal() {
  if (!selectedTarget.value || terminalConnecting.value) return

  terminalConnecting.value = true

  // Get auth token
  const token = localStorage.getItem('auth_token')
  if (!token) {
    notificationStore.error('Not authenticated')
    terminalConnecting.value = false
    return
  }

  // Build WebSocket URL
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const basePath = window.location.pathname.startsWith('/management') ? '/management' : ''
  const wsUrl = `${protocol}//${window.location.host}${basePath}/api/ws/terminal?target=${selectedTarget.value}&token=${token}`

  try {
    websocket = new WebSocket(wsUrl)

    websocket.onopen = () => {
      terminalConnecting.value = false
      terminalConnected.value = true
      terminal?.clear()
      terminal?.focus()
    }

    websocket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'output' && msg.data) {
          terminal?.write(msg.data)
        } else if (msg.type === 'error') {
          terminal?.writeln(`\r\n\x1b[31mError: ${msg.message}\x1b[0m`)
        } else if (msg.type === 'connected') {
          terminal?.writeln('\x1b[32mConnected\x1b[0m\r\n')
        } else if (msg.type === 'disconnected') {
          terminal?.writeln('\r\n\x1b[33mDisconnected\x1b[0m')
          terminalConnected.value = false
        }
      } catch (e) {
        // Raw output
        terminal?.write(event.data)
      }
    }

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error)
      terminalConnecting.value = false
      notificationStore.error('Terminal connection error')
    }

    websocket.onclose = () => {
      terminalConnecting.value = false
      terminalConnected.value = false
      terminal?.writeln('\r\n\x1b[33mConnection closed\x1b[0m')
    }

  } catch (error) {
    console.error('Failed to connect:', error)
    terminalConnecting.value = false
    notificationStore.error('Failed to connect to terminal')
  }
}

function disconnectTerminal() {
  if (websocket) {
    websocket.close()
    websocket = null
  }
  terminalConnected.value = false
}

// Watch for tab changes
watch(activeTab, async (newTab) => {
  if (newTab === 'network' && networkInfo.value.interfaces.length === 0) {
    await loadNetworkInfo()
  } else if (newTab === 'ssl' && !sslInfo.value.configured && !sslInfo.value.error) {
    await loadSslInfo()
  } else if (newTab === 'terminal') {
    await loadTerminalTargets()
    await nextTick()
    await initTerminal()
  }
})

onMounted(loadData)

onUnmounted(() => {
  disconnectTerminal()
  if (terminal) {
    terminal.dispose()
    terminal = null
  }
})
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
        <p class="text-secondary mt-1">Server health, network, and terminal access</p>
      </div>
      <button
        @click="loadData"
        class="btn-secondary flex items-center gap-2"
      >
        <ArrowPathIcon class="h-4 w-4" />
        Refresh
      </button>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 p-1 bg-surface-hover rounded-lg overflow-x-auto">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="activeTab = tab.id"
        :class="[
          'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all whitespace-nowrap',
          activeTab === tab.id
            ? themeStore.isNeon
              ? 'bg-cyan-500/20 text-cyan-400'
              : 'bg-surface text-primary shadow-sm'
            : 'text-secondary hover:text-primary'
        ]"
      >
        <component :is="tab.icon" class="h-4 w-4" />
        {{ tab.name }}
      </button>
    </div>

    <LoadingSpinner v-if="loading && activeTab === 'overview'" size="lg" text="Loading system info..." class="py-12" />

    <!-- Overview Tab -->
    <template v-if="activeTab === 'overview' && !loading">
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

    <!-- Network Tab -->
    <template v-if="activeTab === 'network'">
      <LoadingSpinner v-if="networkLoading" size="lg" text="Loading network info..." class="py-12" />

      <template v-else>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- Basic Network Info -->
          <Card title="Network Configuration" :neon="true">
            <div class="space-y-3">
              <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
                <span class="text-secondary">Hostname</span>
                <span class="font-medium text-primary">{{ networkInfo.hostname || 'N/A' }}</span>
              </div>
              <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
                <span class="text-secondary">FQDN</span>
                <span class="font-medium text-primary">{{ networkInfo.fqdn || 'N/A' }}</span>
              </div>
              <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
                <span class="text-secondary">Default Gateway</span>
                <span class="font-medium text-primary font-mono">{{ networkInfo.gateway || 'N/A' }}</span>
              </div>
              <div class="flex justify-between py-2">
                <span class="text-secondary">DNS Servers</span>
                <div class="text-right">
                  <span
                    v-for="(dns, i) in networkInfo.dns_servers"
                    :key="i"
                    class="font-medium text-primary font-mono block"
                  >
                    {{ dns }}
                  </span>
                  <span v-if="!networkInfo.dns_servers?.length" class="text-muted">None configured</span>
                </div>
              </div>
            </div>
          </Card>

          <!-- Network Interfaces -->
          <Card title="Network Interfaces" :neon="true">
            <div class="space-y-4">
              <div
                v-for="iface in networkInfo.interfaces"
                :key="iface.name"
                class="p-3 rounded-lg bg-surface-hover"
              >
                <div class="flex items-center gap-2 mb-2">
                  <WifiIcon class="h-4 w-4 text-blue-500" />
                  <span class="font-medium text-primary">{{ iface.name }}</span>
                </div>
                <div class="space-y-1 text-sm">
                  <div
                    v-for="addr in iface.addresses"
                    :key="addr.address"
                    class="flex justify-between"
                  >
                    <span class="text-secondary">{{ addr.type.toUpperCase() }}</span>
                    <span class="font-mono text-primary">{{ addr.address }}</span>
                  </div>
                  <div
                    v-for="addr in iface.addresses.filter(a => a.netmask)"
                    :key="'mask-' + addr.address"
                    class="flex justify-between"
                  >
                    <span class="text-secondary">Netmask</span>
                    <span class="font-mono text-muted">{{ addr.netmask }}</span>
                  </div>
                </div>
              </div>
              <div v-if="!networkInfo.interfaces?.length" class="text-center py-4 text-muted">
                No network interfaces found
              </div>
            </div>
          </Card>
        </div>
      </template>
    </template>

    <!-- SSL Tab -->
    <template v-if="activeTab === 'ssl'">
      <LoadingSpinner v-if="sslLoading" size="lg" text="Loading SSL info..." class="py-12" />

      <template v-else>
        <Card v-if="sslInfo.error" title="SSL Status" :neon="true">
          <div class="flex items-center gap-3 p-4 bg-amber-50 dark:bg-amber-500/10 rounded-lg">
            <ExclamationTriangleIcon class="h-6 w-6 text-amber-500" />
            <p class="text-amber-700 dark:text-amber-400">{{ sslInfo.error }}</p>
          </div>
        </Card>

        <Card v-else-if="!sslInfo.configured" title="SSL Status" :neon="true">
          <div class="flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-500/10 rounded-lg">
            <LockClosedIcon class="h-6 w-6 text-gray-400" />
            <p class="text-muted">No SSL certificates found. Certificates are typically managed by the nginx container.</p>
          </div>
        </Card>

        <div v-else class="space-y-6">
          <Card
            v-for="cert in sslInfo.certificates"
            :key="cert.domain"
            :title="cert.domain"
            :subtitle="cert.type"
            :neon="true"
          >
            <div class="space-y-4">
              <!-- Status Banner -->
              <div
                :class="[
                  'flex items-center gap-3 p-4 rounded-lg',
                  cert.status === 'valid'
                    ? cert.warning
                      ? 'bg-amber-50 dark:bg-amber-500/10'
                      : 'bg-emerald-50 dark:bg-emerald-500/10'
                    : 'bg-red-50 dark:bg-red-500/10'
                ]"
              >
                <CheckCircleIcon
                  v-if="cert.status === 'valid' && !cert.warning"
                  class="h-6 w-6 text-emerald-500"
                />
                <ExclamationTriangleIcon
                  v-else-if="cert.warning || cert.status !== 'valid'"
                  :class="['h-6 w-6', cert.status === 'valid' ? 'text-amber-500' : 'text-red-500']"
                />
                <div>
                  <p :class="[
                    'font-medium',
                    cert.status === 'valid'
                      ? cert.warning ? 'text-amber-700 dark:text-amber-400' : 'text-emerald-700 dark:text-emerald-400'
                      : 'text-red-700 dark:text-red-400'
                  ]">
                    {{ cert.days_until_expiry }} days until expiry
                  </p>
                  <p v-if="cert.warning" class="text-sm text-amber-600 dark:text-amber-500">
                    {{ cert.warning }}
                  </p>
                </div>
              </div>

              <!-- Certificate Details -->
              <div class="space-y-3">
                <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Subject</span>
                  <span class="font-medium text-primary text-right max-w-[300px] truncate">
                    {{ cert.subject }}
                  </span>
                </div>
                <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Issuer</span>
                  <span class="font-medium text-primary text-right max-w-[300px] truncate">
                    {{ cert.issuer }}
                  </span>
                </div>
                <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Valid From</span>
                  <span class="font-medium text-primary">{{ cert.valid_from }}</span>
                </div>
                <div class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Valid Until</span>
                  <span class="font-medium text-primary">{{ cert.valid_until }}</span>
                </div>
                <div v-if="cert.san?.length" class="py-2">
                  <span class="text-secondary block mb-2">Subject Alternative Names</span>
                  <div class="flex flex-wrap gap-2">
                    <span
                      v-for="san in cert.san"
                      :key="san"
                      class="px-2 py-1 text-xs font-mono rounded bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300"
                    >
                      {{ san }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </template>
    </template>

    <!-- Terminal Tab -->
    <template v-if="activeTab === 'terminal'">
      <Card title="Web Terminal" subtitle="Connect to containers or host system" :neon="true">
        <!-- Terminal Controls -->
        <div class="flex items-center gap-4 mb-4">
          <div class="flex-1">
            <label class="block text-sm font-medium text-secondary mb-1">Connect To</label>
            <select
              v-model="selectedTarget"
              :disabled="terminalConnected"
              class="select-field w-full"
            >
              <option
                v-for="target in terminalTargets"
                :key="target.id"
                :value="target.id"
              >
                {{ target.name }}
                <template v-if="target.type === 'container'"> ({{ target.image }})</template>
                <template v-if="target.type === 'host'"> - Docker Host</template>
              </option>
            </select>
          </div>
          <div class="pt-6">
            <button
              v-if="!terminalConnected"
              @click="connectTerminal"
              :disabled="terminalConnecting || !selectedTarget"
              class="btn-primary flex items-center gap-2"
            >
              <PlayIcon class="h-4 w-4" />
              {{ terminalConnecting ? 'Connecting...' : 'Connect' }}
            </button>
            <button
              v-else
              @click="disconnectTerminal"
              class="btn-secondary flex items-center gap-2 text-red-500 hover:bg-red-500/10"
            >
              <StopIcon class="h-4 w-4" />
              Disconnect
            </button>
          </div>
        </div>

        <!-- Terminal Window -->
        <div
          ref="terminalElement"
          :class="[
            'rounded-lg overflow-hidden',
            themeStore.isDark ? 'bg-[#1a1b26]' : 'bg-white',
            'min-h-[400px] h-[500px]'
          ]"
        >
          <div v-if="!terminal" class="flex items-center justify-center h-full text-muted">
            <CommandLineIcon class="h-8 w-8 mr-2" />
            Select a target and click Connect to start a terminal session
          </div>
        </div>

        <!-- Terminal Info -->
        <div class="mt-4 text-xs text-muted">
          <p v-if="terminalConnected" class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
            Connected to {{ terminalTargets.find(t => t.id === selectedTarget)?.name }}
          </p>
          <p v-else class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-gray-400"></span>
            Not connected
          </p>
        </div>
      </Card>
    </template>
  </div>
</template>

<style>
/* Terminal styling */
.xterm {
  padding: 8px;
}
.xterm-viewport {
  overflow-y: auto !important;
}
</style>
