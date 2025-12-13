<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
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
  CloudIcon,
  LinkIcon,
  SunIcon,
  MoonIcon,
  ChevronDownIcon,
  HeartIcon,
  BoltIcon,
  DocumentTextIcon,
  ArchiveBoxIcon,
  ServerIcon,
  XCircleIcon,
  InformationCircleIcon,
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

const route = useRoute()
const themeStore = useThemeStore()
const authStore = useAuthStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const activeTab = ref('overview')

// Tab definitions
const tabs = [
  { id: 'health', name: 'Health', icon: SignalIcon },
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

// Health checks (comprehensive)
const healthData = ref({
  overall_status: 'loading',
  warnings: 0,
  errors: 0,
  checks: {},
  container_memory: {},
  ssl_certificates: [],
  docker_disk_usage_gb: 0,
})
const healthLoading = ref(false)
const healthLastUpdated = ref(null)

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

// Cloudflare Tunnel state
const cloudflareInfo = ref({
  installed: false,
  running: false,
  connected: false,
  error: null,
})

// Tailscale state
const tailscaleInfo = ref({
  installed: false,
  running: false,
  logged_in: false,
  tailscale_ip: null,
  hostname: null,
  peers: [],
  error: null,
})
const peersExpanded = ref(false)

// Terminal state
const terminalTargets = ref([])
const selectedTarget = ref('')
const terminalConnected = ref(false)
const terminalConnecting = ref(false)
const terminalElement = ref(null)
const terminalDarkMode = ref(true) // Terminal theme preference (default dark)
let terminal = null
let fitAddon = null
let websocket = null

// Terminal theme definitions - vibrant high-contrast GitHub-style colors
const terminalThemes = {
  dark: {
    background: '#0d1117',
    foreground: '#e6edf3',
    cursor: '#58a6ff',
    cursorAccent: '#0d1117',
    selection: 'rgba(56, 139, 253, 0.4)',
    black: '#484f58',
    red: '#ff7b72',
    green: '#3fb950',
    yellow: '#d29922',
    blue: '#58a6ff',
    magenta: '#bc8cff',
    cyan: '#39c5cf',
    white: '#e6edf3',
    brightBlack: '#6e7681',
    brightRed: '#ffa198',
    brightGreen: '#56d364',
    brightYellow: '#e3b341',
    brightBlue: '#79c0ff',
    brightMagenta: '#d2a8ff',
    brightCyan: '#56d4dd',
    brightWhite: '#ffffff',
  },
  light: {
    background: '#ffffff',
    foreground: '#24292e',
    cursor: '#24292e',
    cursorAccent: '#ffffff',
    selection: 'rgba(0, 0, 0, 0.15)',
    black: '#24292e',
    red: '#d73a49',
    green: '#22863a',
    yellow: '#b08800',
    blue: '#0366d6',
    magenta: '#6f42c1',
    cyan: '#1b7c83',
    white: '#6a737d',
    brightBlack: '#586069',
    brightRed: '#cb2431',
    brightGreen: '#28a745',
    brightYellow: '#dbab09',
    brightBlue: '#2188ff',
    brightMagenta: '#8a63d2',
    brightCyan: '#3192aa',
    brightWhite: '#959da5',
  },
}

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

async function loadHealthData() {
  healthLoading.value = true
  try {
    const response = await api.system.getHealthFull()
    healthData.value = response.data
    healthLastUpdated.value = new Date()
  } catch (error) {
    notificationStore.error('Failed to load health data')
    healthData.value.overall_status = 'error'
  } finally {
    healthLoading.value = false
  }
}

async function loadNetworkInfo() {
  networkLoading.value = true
  try {
    // Load network, cloudflare, and tailscale info in parallel
    const [networkRes, cloudflareRes, tailscaleRes] = await Promise.all([
      api.system.getNetwork(),
      api.system.getCloudflare().catch(() => ({ data: { error: 'Not available' } })),
      api.system.getTailscale().catch(() => ({ data: { error: 'Not available' } })),
    ])
    networkInfo.value = networkRes.data
    cloudflareInfo.value = cloudflareRes.data
    tailscaleInfo.value = tailscaleRes.data
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
      theme: terminalDarkMode.value ? terminalThemes.dark : terminalThemes.light,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      rows: 28,
      cols: 120,
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

function toggleTerminalTheme() {
  terminalDarkMode.value = !terminalDarkMode.value
  if (terminal) {
    terminal.options.theme = terminalDarkMode.value ? terminalThemes.dark : terminalThemes.light
  }
}

// Watch for tab changes
watch(activeTab, async (newTab) => {
  if (newTab === 'health' && healthData.value.overall_status === 'loading') {
    await loadHealthData()
  } else if (newTab === 'network' && networkInfo.value.interfaces.length === 0) {
    await loadNetworkInfo()
  } else if (newTab === 'ssl' && !sslInfo.value.configured && !sslInfo.value.error) {
    await loadSslInfo()
  } else if (newTab === 'terminal') {
    await loadTerminalTargets()
    await nextTick()
    await initTerminal()
  }
})

onMounted(async () => {
  await loadData()

  // Check for query params to set initial tab and target
  if (route.query.tab) {
    activeTab.value = route.query.tab

    // If going to health tab, load health data
    if (route.query.tab === 'health') {
      await loadHealthData()
    }

    // If going to terminal tab with a target, pre-select it
    if (route.query.tab === 'terminal' && route.query.target) {
      await loadTerminalTargets()
      // Find matching target by container ID (first 12 chars)
      const targetId = route.query.target.slice(0, 12)
      const matchingTarget = terminalTargets.value.find(t => t.id === targetId || t.id.startsWith(targetId))
      if (matchingTarget) {
        selectedTarget.value = matchingTarget.id
      }
    }
  }
})

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

    <!-- Health Tab -->
    <template v-if="activeTab === 'health'">
      <LoadingSpinner v-if="healthLoading" size="lg" text="Running health checks..." class="py-12" />

      <template v-else>
        <!-- Overall Status Banner -->
        <div
          :class="[
            'rounded-xl p-6 border-2 relative overflow-hidden',
            healthData.overall_status === 'healthy'
              ? 'bg-gradient-to-r from-emerald-500/10 to-emerald-500/5 border-emerald-500/50'
              : healthData.overall_status === 'warning'
                ? 'bg-gradient-to-r from-amber-500/10 to-amber-500/5 border-amber-500/50'
                : 'bg-gradient-to-r from-red-500/10 to-red-500/5 border-red-500/50'
          ]"
        >
          <!-- Animated pulse background for healthy status -->
          <div
            v-if="healthData.overall_status === 'healthy'"
            class="absolute inset-0 bg-emerald-500/5 animate-pulse"
          ></div>

          <div class="relative flex items-center justify-between">
            <div class="flex items-center gap-4">
              <div
                :class="[
                  'p-4 rounded-2xl',
                  healthData.overall_status === 'healthy'
                    ? 'bg-emerald-500/20'
                    : healthData.overall_status === 'warning'
                      ? 'bg-amber-500/20'
                      : 'bg-red-500/20'
                ]"
              >
                <HeartIcon
                  :class="[
                    'h-10 w-10',
                    healthData.overall_status === 'healthy'
                      ? 'text-emerald-500'
                      : healthData.overall_status === 'warning'
                        ? 'text-amber-500'
                        : 'text-red-500'
                  ]"
                />
              </div>
              <div>
                <h2 class="text-2xl font-bold text-primary">
                  System Health:
                  <span
                    :class="[
                      healthData.overall_status === 'healthy'
                        ? 'text-emerald-500'
                        : healthData.overall_status === 'warning'
                          ? 'text-amber-500'
                          : 'text-red-500'
                    ]"
                  >
                    {{ healthData.overall_status?.toUpperCase() || 'CHECKING' }}
                  </span>
                </h2>
                <p class="text-secondary mt-1">
                  {{ healthData.version }} •
                  Last updated: {{ healthLastUpdated ? new Date(healthLastUpdated).toLocaleTimeString() : 'Never' }}
                </p>
              </div>
            </div>

            <div class="flex items-center gap-6">
              <!-- Counters -->
              <div class="text-center">
                <p class="text-3xl font-bold text-emerald-500">{{ healthData.passed || 0 }}</p>
                <p class="text-xs text-muted uppercase tracking-wide">Passed</p>
              </div>
              <div class="text-center">
                <p class="text-3xl font-bold text-amber-500">{{ healthData.warnings || 0 }}</p>
                <p class="text-xs text-muted uppercase tracking-wide">Warnings</p>
              </div>
              <div class="text-center">
                <p class="text-3xl font-bold text-red-500">{{ healthData.errors || 0 }}</p>
                <p class="text-xs text-muted uppercase tracking-wide">Errors</p>
              </div>

              <button
                @click="loadHealthData"
                :disabled="healthLoading"
                class="btn-secondary flex items-center gap-2 ml-4"
              >
                <ArrowPathIcon :class="['h-4 w-4', healthLoading ? 'animate-spin' : '']" />
                Refresh
              </button>
            </div>
          </div>
        </div>

        <!-- Health Check Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-6">
          <!-- Docker Containers -->
          <Card :neon="true" :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
                  <ServerIcon class="h-5 w-5 text-blue-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">Docker Containers</h3>
                  <p class="text-xs text-muted">Container status and health</p>
                </div>
                <span
                  :class="[
                    'px-2 py-1 rounded-full text-xs font-medium',
                    healthData.checks?.docker?.status === 'ok'
                      ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                      : healthData.checks?.docker?.status === 'warning'
                        ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400'
                        : 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400'
                  ]"
                >
                  {{ healthData.checks?.docker?.status?.toUpperCase() || 'N/A' }}
                </span>
              </div>
              <div class="space-y-2">
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Running</span>
                  <span class="font-medium text-emerald-500">{{ healthData.checks?.docker?.details?.running || 0 }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Stopped</span>
                  <span class="font-medium text-gray-500">{{ healthData.checks?.docker?.details?.stopped || 0 }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Unhealthy</span>
                  <span :class="['font-medium', (healthData.checks?.docker?.details?.unhealthy || 0) > 0 ? 'text-red-500' : 'text-gray-500']">
                    {{ healthData.checks?.docker?.details?.unhealthy || 0 }}
                  </span>
                </div>
              </div>
              <!-- Unhealthy containers list -->
              <div v-if="healthData.checks?.docker?.details?.unhealthy_containers?.length" class="mt-3 pt-3 border-t border-[var(--color-border)]">
                <p class="text-xs text-red-500 font-medium mb-1">Unhealthy:</p>
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="name in healthData.checks?.docker?.details?.unhealthy_containers"
                    :key="name"
                    class="px-2 py-0.5 text-xs bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400 rounded"
                  >
                    {{ name }}
                  </span>
                </div>
              </div>
            </div>
          </Card>

          <!-- Services -->
          <Card :neon="true" :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-500/20">
                  <BoltIcon class="h-5 w-5 text-purple-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">Core Services</h3>
                  <p class="text-xs text-muted">n8n, Nginx, Management API</p>
                </div>
                <span
                  :class="[
                    'px-2 py-1 rounded-full text-xs font-medium',
                    healthData.checks?.services?.status === 'ok'
                      ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                      : 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400'
                  ]"
                >
                  {{ healthData.checks?.services?.status?.toUpperCase() || 'N/A' }}
                </span>
              </div>
              <div class="space-y-2">
                <div
                  v-for="(status, service) in healthData.checks?.services?.details"
                  :key="service"
                  class="flex justify-between items-center text-sm"
                >
                  <span class="text-secondary capitalize">{{ service.replace('_', ' ') }}</span>
                  <span
                    :class="[
                      'flex items-center gap-1 font-medium',
                      status === 'ok' ? 'text-emerald-500' : 'text-red-500'
                    ]"
                  >
                    <CheckCircleIcon v-if="status === 'ok'" class="h-4 w-4" />
                    <XCircleIcon v-else class="h-4 w-4" />
                    {{ status }}
                  </span>
                </div>
              </div>
            </div>
          </Card>

          <!-- Database -->
          <Card :neon="true" :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-amber-100 dark:bg-amber-500/20">
                  <CircleStackIcon class="h-5 w-5 text-amber-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">Database</h3>
                  <p class="text-xs text-muted">PostgreSQL health</p>
                </div>
                <span
                  :class="[
                    'px-2 py-1 rounded-full text-xs font-medium',
                    healthData.checks?.database?.status === 'ok'
                      ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                      : 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400'
                  ]"
                >
                  {{ healthData.checks?.database?.status?.toUpperCase() || 'N/A' }}
                </span>
              </div>
              <div class="space-y-2">
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Connection</span>
                  <span :class="['font-medium', healthData.checks?.database?.details?.connection === 'ok' ? 'text-emerald-500' : 'text-red-500']">
                    {{ healthData.checks?.database?.details?.connection || 'N/A' }}
                  </span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Queries</span>
                  <span :class="['font-medium', healthData.checks?.database?.details?.query === 'ok' ? 'text-emerald-500' : 'text-red-500']">
                    {{ healthData.checks?.database?.details?.query || 'N/A' }}
                  </span>
                </div>
                <div v-if="healthData.checks?.database?.details?.version" class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Version</span>
                  <span class="font-medium text-primary">{{ healthData.checks?.database?.details?.version }}</span>
                </div>
              </div>
            </div>
          </Card>

          <!-- System Resources -->
          <Card :neon="true" :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-cyan-100 dark:bg-cyan-500/20">
                  <CpuChipIcon class="h-5 w-5 text-cyan-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">System Resources</h3>
                  <p class="text-xs text-muted">CPU, Memory, Disk</p>
                </div>
                <span
                  :class="[
                    'px-2 py-1 rounded-full text-xs font-medium',
                    healthData.checks?.resources?.status === 'ok'
                      ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                      : healthData.checks?.resources?.status === 'warning'
                        ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400'
                        : 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400'
                  ]"
                >
                  {{ healthData.checks?.resources?.status?.toUpperCase() || 'N/A' }}
                </span>
              </div>
              <div class="space-y-3">
                <!-- Disk -->
                <div>
                  <div class="flex justify-between items-center text-sm mb-1">
                    <span class="text-secondary">Disk</span>
                    <span class="font-medium text-primary">{{ healthData.checks?.resources?.details?.disk_percent || 0 }}%</span>
                  </div>
                  <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      :class="[
                        'h-full rounded-full transition-all',
                        (healthData.checks?.resources?.details?.disk_percent || 0) >= 90 ? 'bg-red-500' :
                        (healthData.checks?.resources?.details?.disk_percent || 0) >= 75 ? 'bg-amber-500' : 'bg-cyan-500'
                      ]"
                      :style="{ width: `${healthData.checks?.resources?.details?.disk_percent || 0}%` }"
                    ></div>
                  </div>
                  <p class="text-xs text-muted mt-1">{{ healthData.checks?.resources?.details?.disk_free_gb?.toFixed(1) || 0 }} GB free</p>
                </div>
                <!-- Memory -->
                <div>
                  <div class="flex justify-between items-center text-sm mb-1">
                    <span class="text-secondary">Memory</span>
                    <span class="font-medium text-primary">{{ healthData.checks?.resources?.details?.memory_percent || 0 }}%</span>
                  </div>
                  <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      :class="[
                        'h-full rounded-full transition-all',
                        (healthData.checks?.resources?.details?.memory_percent || 0) >= 90 ? 'bg-red-500' :
                        (healthData.checks?.resources?.details?.memory_percent || 0) >= 75 ? 'bg-amber-500' : 'bg-purple-500'
                      ]"
                      :style="{ width: `${healthData.checks?.resources?.details?.memory_percent || 0}%` }"
                    ></div>
                  </div>
                </div>
                <!-- CPU -->
                <div>
                  <div class="flex justify-between items-center text-sm mb-1">
                    <span class="text-secondary">CPU</span>
                    <span class="font-medium text-primary">{{ healthData.checks?.resources?.details?.cpu_percent?.toFixed(1) || 0 }}%</span>
                  </div>
                  <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      :class="[
                        'h-full rounded-full transition-all',
                        (healthData.checks?.resources?.details?.cpu_percent || 0) >= 90 ? 'bg-red-500' :
                        (healthData.checks?.resources?.details?.cpu_percent || 0) >= 75 ? 'bg-amber-500' : 'bg-blue-500'
                      ]"
                      :style="{ width: `${healthData.checks?.resources?.details?.cpu_percent || 0}%` }"
                    ></div>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          <!-- SSL Certificates -->
          <Card :neon="true" :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-500/20">
                  <LockClosedIcon class="h-5 w-5 text-emerald-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">SSL Certificates</h3>
                  <p class="text-xs text-muted">Certificate validity</p>
                </div>
                <span
                  :class="[
                    'px-2 py-1 rounded-full text-xs font-medium',
                    healthData.checks?.ssl?.status === 'ok'
                      ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                      : healthData.checks?.ssl?.status === 'warning'
                        ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400'
                        : 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400'
                  ]"
                >
                  {{ healthData.checks?.ssl?.status?.toUpperCase() || 'N/A' }}
                </span>
              </div>
              <div v-if="healthData.ssl_certificates?.length" class="space-y-2">
                <div
                  v-for="cert in healthData.ssl_certificates"
                  :key="cert.domain"
                  class="flex justify-between items-center text-sm p-2 rounded bg-surface-hover"
                >
                  <span class="font-medium text-primary truncate max-w-[150px]" :title="cert.domain">{{ cert.domain }}</span>
                  <span
                    :class="[
                      'text-xs px-2 py-0.5 rounded',
                      cert.days_until_expiry > 30 ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400' :
                      cert.days_until_expiry > 7 ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400' :
                      'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400'
                    ]"
                  >
                    {{ cert.days_until_expiry }}d
                  </span>
                </div>
              </div>
              <div v-else class="text-sm text-muted">No certificates found</div>
            </div>
          </Card>

          <!-- Network -->
          <Card :neon="true" :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-500/20">
                  <GlobeAltIcon class="h-5 w-5 text-indigo-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">Network</h3>
                  <p class="text-xs text-muted">Connectivity status</p>
                </div>
                <span
                  :class="[
                    'px-2 py-1 rounded-full text-xs font-medium',
                    healthData.checks?.network?.status === 'ok'
                      ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                      : 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400'
                  ]"
                >
                  {{ healthData.checks?.network?.status?.toUpperCase() || 'N/A' }}
                </span>
              </div>
              <div class="space-y-2">
                <div
                  v-for="(status, target) in healthData.checks?.network?.details"
                  :key="target"
                  class="flex justify-between items-center text-sm"
                >
                  <span class="text-secondary capitalize">{{ target.replace('_', ' ') }}</span>
                  <span
                    :class="[
                      'flex items-center gap-1 font-medium',
                      status === 'ok' ? 'text-emerald-500' : 'text-red-500'
                    ]"
                  >
                    <CheckCircleIcon v-if="status === 'ok'" class="h-4 w-4" />
                    <XCircleIcon v-else class="h-4 w-4" />
                    {{ status }}
                  </span>
                </div>
              </div>
            </div>
          </Card>

          <!-- Backups -->
          <Card :neon="true" :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-teal-100 dark:bg-teal-500/20">
                  <ArchiveBoxIcon class="h-5 w-5 text-teal-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">Backups</h3>
                  <p class="text-xs text-muted">Backup status</p>
                </div>
                <span
                  :class="[
                    'px-2 py-1 rounded-full text-xs font-medium',
                    healthData.checks?.backups?.status === 'ok'
                      ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                      : healthData.checks?.backups?.status === 'warning'
                        ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400'
                        : 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400'
                  ]"
                >
                  {{ healthData.checks?.backups?.status?.toUpperCase() || 'N/A' }}
                </span>
              </div>
              <div class="space-y-2">
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Recent (24h)</span>
                  <span class="font-medium text-primary">{{ healthData.checks?.backups?.details?.recent_count || 0 }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Failed (24h)</span>
                  <span :class="['font-medium', (healthData.checks?.backups?.details?.failed_count || 0) > 0 ? 'text-red-500' : 'text-gray-500']">
                    {{ healthData.checks?.backups?.details?.failed_count || 0 }}
                  </span>
                </div>
                <div v-if="healthData.checks?.backups?.details?.last_backup" class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Last Backup</span>
                  <span class="font-medium text-primary text-xs">
                    {{ new Date(healthData.checks?.backups?.details?.last_backup).toLocaleString() }}
                  </span>
                </div>
              </div>
            </div>
          </Card>

          <!-- Recent Logs -->
          <Card :neon="true" :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-rose-100 dark:bg-rose-500/20">
                  <DocumentTextIcon class="h-5 w-5 text-rose-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">Recent Logs</h3>
                  <p class="text-xs text-muted">Error analysis</p>
                </div>
                <span
                  :class="[
                    'px-2 py-1 rounded-full text-xs font-medium',
                    healthData.checks?.logs?.status === 'ok'
                      ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                      : healthData.checks?.logs?.status === 'warning'
                        ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400'
                        : 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400'
                  ]"
                >
                  {{ healthData.checks?.logs?.status?.toUpperCase() || 'N/A' }}
                </span>
              </div>
              <div class="space-y-2">
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Errors (1h)</span>
                  <span :class="['font-medium', (healthData.checks?.logs?.details?.error_count || 0) > 10 ? 'text-red-500' : (healthData.checks?.logs?.details?.error_count || 0) > 0 ? 'text-amber-500' : 'text-gray-500']">
                    {{ healthData.checks?.logs?.details?.error_count || 0 }}
                  </span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Warnings (1h)</span>
                  <span class="font-medium text-amber-500">{{ healthData.checks?.logs?.details?.warning_count || 0 }}</span>
                </div>
              </div>
              <!-- Recent errors -->
              <div v-if="healthData.checks?.logs?.details?.recent_errors?.length" class="mt-3 pt-3 border-t border-[var(--color-border)]">
                <p class="text-xs text-muted mb-2">Recent Errors:</p>
                <div class="space-y-1 max-h-24 overflow-y-auto">
                  <div
                    v-for="(err, i) in healthData.checks?.logs?.details?.recent_errors?.slice(0, 3)"
                    :key="i"
                    class="text-xs text-red-500 dark:text-red-400 font-mono truncate"
                    :title="err"
                  >
                    {{ err }}
                  </div>
                </div>
              </div>
            </div>
          </Card>

          <!-- Docker Disk -->
          <Card :neon="true" :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-orange-100 dark:bg-orange-500/20">
                  <ServerStackIcon class="h-5 w-5 text-orange-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">Docker Storage</h3>
                  <p class="text-xs text-muted">Images, volumes, containers</p>
                </div>
              </div>
              <div class="text-center py-4">
                <p class="text-4xl font-bold text-primary">
                  {{ healthData.docker_disk_usage_gb?.toFixed(1) || '0.0' }}
                  <span class="text-lg text-muted">GB</span>
                </p>
                <p class="text-xs text-muted mt-1">Total Docker disk usage</p>
              </div>
            </div>
          </Card>
        </div>

        <!-- Container Memory Usage -->
        <Card v-if="healthData.container_memory && Object.keys(healthData.container_memory).length" title="Container Memory Usage" class="mt-6" :neon="true">
          <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
            <div
              v-for="(memory, name) in healthData.container_memory"
              :key="name"
              class="p-3 rounded-lg bg-surface-hover border border-[var(--color-border)]"
            >
              <p class="font-medium text-primary text-sm truncate" :title="name">{{ name }}</p>
              <p
                :class="[
                  'text-2xl font-bold mt-1',
                  memory > 500 ? 'text-red-500' : memory > 200 ? 'text-amber-500' : 'text-emerald-500'
                ]"
              >
                {{ memory?.toFixed(0) || 0 }}
                <span class="text-xs text-muted font-normal">MB</span>
              </p>
            </div>
          </div>
        </Card>
      </template>
    </template>

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

        <!-- VPN & Tunnel Services -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          <!-- Cloudflare Tunnel -->
          <Card title="Cloudflare Tunnel" :neon="true">
            <div v-if="cloudflareInfo.error && !cloudflareInfo.installed" class="flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-500/10 rounded-lg">
              <CloudIcon class="h-6 w-6 text-gray-400" />
              <p class="text-muted">{{ cloudflareInfo.error }}</p>
            </div>
            <template v-else>
              <div class="space-y-3">
                <!-- Status -->
                <div class="flex items-center justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Status</span>
                  <span :class="[
                    'flex items-center gap-2 font-medium',
                    cloudflareInfo.running ? 'text-emerald-500' : 'text-red-500'
                  ]">
                    <span :class="['w-2 h-2 rounded-full', cloudflareInfo.running ? 'bg-emerald-500' : 'bg-red-500']"></span>
                    {{ cloudflareInfo.running ? 'Running' : 'Stopped' }}
                  </span>
                </div>
                <div v-if="cloudflareInfo.version" class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Version</span>
                  <span class="font-medium text-primary">{{ cloudflareInfo.version }}</span>
                </div>
                <div v-if="cloudflareInfo.connected !== undefined" class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Connected</span>
                  <span :class="cloudflareInfo.connected ? 'text-emerald-500' : 'text-amber-500'">
                    {{ cloudflareInfo.connected ? 'Yes' : 'No' }}
                  </span>
                </div>
                <div v-if="cloudflareInfo.edge_locations?.length" class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Edge Locations</span>
                  <div class="flex flex-wrap gap-1 justify-end">
                    <span
                      v-for="loc in cloudflareInfo.edge_locations"
                      :key="loc"
                      class="px-2 py-0.5 text-xs rounded bg-orange-100 dark:bg-orange-500/20 text-orange-700 dark:text-orange-300 uppercase"
                    >
                      {{ loc }}
                    </span>
                  </div>
                </div>
                <div v-if="cloudflareInfo.tunnel_id" class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Tunnel ID</span>
                  <span class="font-mono text-xs text-primary truncate max-w-[180px]" :title="cloudflareInfo.tunnel_id">
                    {{ cloudflareInfo.tunnel_id.slice(0, 8) }}...
                  </span>
                </div>
                <div v-if="cloudflareInfo.connector_id" class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Connector ID</span>
                  <span class="font-mono text-xs text-primary truncate max-w-[180px]" :title="cloudflareInfo.connector_id">
                    {{ cloudflareInfo.connector_id.slice(0, 8) }}...
                  </span>
                </div>
                <div v-if="cloudflareInfo.connections_per_location && Object.keys(cloudflareInfo.connections_per_location).length" class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Connections</span>
                  <div class="flex flex-wrap gap-1 justify-end">
                    <span
                      v-for="(count, loc) in cloudflareInfo.connections_per_location"
                      :key="loc"
                      class="px-2 py-0.5 text-xs rounded bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 uppercase"
                    >
                      {{ loc }}: {{ count }}
                    </span>
                  </div>
                </div>

                <!-- Metrics Section -->
                <div v-if="cloudflareInfo.metrics && Object.keys(cloudflareInfo.metrics).length" class="pt-2">
                  <p class="text-xs text-muted uppercase tracking-wide mb-2">Traffic Metrics</p>
                  <div class="grid grid-cols-2 gap-3">
                    <div v-if="cloudflareInfo.metrics.total_requests !== undefined" class="bg-surface-hover rounded-lg p-3">
                      <p class="text-xs text-muted">Total Requests</p>
                      <p class="text-lg font-semibold text-primary">{{ cloudflareInfo.metrics.total_requests.toLocaleString() }}</p>
                    </div>
                    <div v-if="cloudflareInfo.metrics.ha_connections !== undefined" class="bg-surface-hover rounded-lg p-3">
                      <p class="text-xs text-muted">HA Connections</p>
                      <p class="text-lg font-semibold text-primary">{{ cloudflareInfo.metrics.ha_connections }}</p>
                    </div>
                    <div v-if="cloudflareInfo.metrics.active_streams !== undefined" class="bg-surface-hover rounded-lg p-3">
                      <p class="text-xs text-muted">Active Streams</p>
                      <p class="text-lg font-semibold text-primary">{{ cloudflareInfo.metrics.active_streams }}</p>
                    </div>
                    <div v-if="cloudflareInfo.metrics.request_errors !== undefined" class="bg-surface-hover rounded-lg p-3">
                      <p class="text-xs text-muted">Errors</p>
                      <p :class="['text-lg font-semibold', cloudflareInfo.metrics.request_errors > 0 ? 'text-red-500' : 'text-primary']">
                        {{ cloudflareInfo.metrics.request_errors }}
                      </p>
                    </div>
                  </div>

                  <!-- Response Codes -->
                  <div v-if="cloudflareInfo.metrics.response_codes" class="mt-3">
                    <p class="text-xs text-muted mb-2">Response Codes</p>
                    <div class="flex flex-wrap gap-2">
                      <span
                        v-for="(count, code) in cloudflareInfo.metrics.response_codes"
                        :key="code"
                        :class="[
                          'px-2 py-1 text-xs rounded font-mono',
                          code.startsWith('2') ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300' :
                          code.startsWith('3') ? 'bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300' :
                          code.startsWith('4') ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300' :
                          'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-300'
                        ]"
                      >
                        {{ code }}: {{ count.toLocaleString() }}
                      </span>
                    </div>
                  </div>
                </div>

                <!-- Error display -->
                <div v-if="cloudflareInfo.last_error" class="mt-3 p-3 bg-red-50 dark:bg-red-500/10 rounded-lg">
                  <p class="text-xs text-red-600 dark:text-red-400 font-mono break-all">{{ cloudflareInfo.last_error }}</p>
                </div>
              </div>
            </template>
          </Card>

          <!-- Tailscale -->
          <Card title="Tailscale VPN" :neon="true">
            <div v-if="tailscaleInfo.error && !tailscaleInfo.installed" class="flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-500/10 rounded-lg">
              <LinkIcon class="h-6 w-6 text-gray-400" />
              <p class="text-muted">{{ tailscaleInfo.error }}</p>
            </div>
            <template v-else>
              <div class="space-y-3">
                <div class="flex items-center justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Status</span>
                  <span :class="[
                    'flex items-center gap-2 font-medium',
                    tailscaleInfo.running && tailscaleInfo.logged_in ? 'text-emerald-500' : 'text-red-500'
                  ]">
                    <span :class="['w-2 h-2 rounded-full', tailscaleInfo.running && tailscaleInfo.logged_in ? 'bg-emerald-500' : 'bg-red-500']"></span>
                    {{ tailscaleInfo.running && tailscaleInfo.logged_in ? 'Connected' : tailscaleInfo.running ? 'Not Logged In' : 'Stopped' }}
                  </span>
                </div>
                <div v-if="tailscaleInfo.tailscale_ip" class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Tailscale IP</span>
                  <span class="font-medium text-primary font-mono">{{ tailscaleInfo.tailscale_ip }}</span>
                </div>
                <div v-if="tailscaleInfo.hostname" class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Hostname</span>
                  <span class="font-medium text-primary">{{ tailscaleInfo.hostname }}</span>
                </div>
                <div v-if="tailscaleInfo.dns_name" class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">DNS Name</span>
                  <span class="font-medium text-primary font-mono text-sm">{{ tailscaleInfo.dns_name }}</span>
                </div>
                <div v-if="tailscaleInfo.tailnet" class="flex justify-between py-2 border-b border-[var(--color-border)]">
                  <span class="text-secondary">Tailnet</span>
                  <span class="font-medium text-primary">{{ tailscaleInfo.tailnet }}</span>
                </div>
                <!-- Devices with expandable list -->
                <div v-if="tailscaleInfo.peers?.length" class="py-2">
                  <button
                    @click="peersExpanded = !peersExpanded"
                    class="w-full flex items-center justify-between hover:bg-surface-hover rounded-lg p-1 -m-1 transition-colors"
                  >
                    <span class="text-secondary">Devices</span>
                    <div class="flex items-center gap-2">
                      <span class="font-medium text-primary">
                        {{ tailscaleInfo.online_peers || 0 }} online / {{ tailscaleInfo.peer_count }} total
                      </span>
                      <ChevronDownIcon
                        :class="[
                          'h-4 w-4 text-secondary transition-transform duration-200',
                          peersExpanded ? 'rotate-180' : ''
                        ]"
                      />
                    </div>
                  </button>

                  <!-- Expandable Peer List -->
                  <div
                    v-show="peersExpanded"
                    class="mt-3 space-y-2 max-h-[250px] overflow-y-auto"
                  >
                    <div
                      v-for="peer in tailscaleInfo.peers"
                      :key="peer.id || peer.hostname"
                      :class="[
                        'flex items-center justify-between p-2 rounded-lg',
                        peer.is_self ? 'bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30' : 'bg-surface-hover'
                      ]"
                    >
                      <div class="flex items-center gap-2">
                        <span
                          :class="[
                            'w-2 h-2 rounded-full flex-shrink-0',
                            peer.online ? 'bg-emerald-500' : 'bg-gray-400'
                          ]"
                        ></span>
                        <div class="min-w-0">
                          <p class="font-medium text-primary text-sm truncate">
                            {{ peer.hostname }}
                            <span v-if="peer.is_self" class="text-xs text-blue-600 dark:text-blue-400 ml-1">(this device)</span>
                          </p>
                          <p class="text-xs text-muted font-mono truncate">{{ peer.ip }}</p>
                        </div>
                      </div>
                      <div class="text-right flex-shrink-0 ml-2">
                        <span
                          :class="[
                            'text-xs px-2 py-0.5 rounded',
                            peer.online
                              ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                              : 'bg-gray-100 dark:bg-gray-500/20 text-gray-600 dark:text-gray-400'
                          ]"
                        >
                          {{ peer.online ? 'online' : 'offline' }}
                        </span>
                        <p v-if="peer.os" class="text-xs text-muted mt-1">{{ peer.os }}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
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
      <div class="flex flex-col" style="height: calc(100vh - 200px); min-height: 500px;">
        <Card :neon="true" :padding="false" :flex="true" class="flex-1">
          <!-- Custom Header with Controls -->
          <template #header>
            <div class="flex items-center justify-between w-full px-4 py-2">
              <div class="flex items-center gap-3">
                <CommandLineIcon class="h-5 w-5 text-primary" />
                <div>
                  <h3 class="font-semibold text-primary text-sm">Web Terminal</h3>
                  <p class="text-xs text-muted">Connect to containers or host</p>
                </div>
              </div>

              <div class="flex items-center gap-2">
                <!-- Target Selector -->
                <select
                  v-model="selectedTarget"
                  :disabled="terminalConnected"
                  class="select-field text-sm py-1 min-w-[180px]"
                >
                  <option
                    v-for="target in terminalTargets"
                    :key="target.id"
                    :value="target.id"
                  >
                    {{ target.name }}
                    <template v-if="target.type === 'container'"> ({{ target.image?.split(':')[0] }})</template>
                    <template v-if="target.type === 'host'"> - Host</template>
                  </option>
                </select>

                <!-- Theme Toggle -->
                <button
                  @click="toggleTerminalTheme"
                  :class="[
                    'p-1.5 rounded-lg transition-colors',
                    terminalDarkMode
                      ? 'bg-gray-700 text-yellow-400 hover:bg-gray-600'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  ]"
                  :title="terminalDarkMode ? 'Switch to light theme' : 'Switch to dark theme'"
                >
                  <SunIcon v-if="terminalDarkMode" class="h-4 w-4" />
                  <MoonIcon v-else class="h-4 w-4" />
                </button>

                <!-- Connect/Disconnect Button -->
                <button
                  v-if="!terminalConnected"
                  @click="connectTerminal"
                  :disabled="terminalConnecting || !selectedTarget"
                  class="btn-primary flex items-center gap-1.5 text-sm py-1 px-3"
                >
                  <PlayIcon class="h-4 w-4" />
                  {{ terminalConnecting ? 'Connecting...' : 'Connect' }}
                </button>
                <button
                  v-else
                  @click="disconnectTerminal"
                  class="btn-secondary flex items-center gap-1.5 text-sm py-1 px-3 text-red-500 hover:bg-red-500/10"
                >
                  <StopIcon class="h-4 w-4" />
                  Disconnect
                </button>
              </div>
            </div>
          </template>

          <!-- Terminal Window - fills remaining space -->
          <div class="flex-1 p-3 pt-0 flex flex-col min-h-0">
            <div
              ref="terminalElement"
              :class="[
                'flex-1 rounded-lg overflow-hidden',
                terminalDarkMode ? 'bg-[#0d1117]' : 'bg-white'
              ]"
            >
              <div v-if="!terminal" class="flex items-center justify-center h-full text-muted">
                <CommandLineIcon class="h-8 w-8 mr-2" />
                Select a target and click Connect to start a terminal session
              </div>
            </div>

            <!-- Terminal Status Bar -->
            <div class="mt-2 text-xs text-muted flex items-center justify-between">
              <p class="flex items-center gap-2">
                <span :class="['w-2 h-2 rounded-full', terminalConnected ? 'bg-emerald-500' : 'bg-gray-400']"></span>
                {{ terminalConnected ? `Connected to ${terminalTargets.find(t => t.id === selectedTarget)?.name}` : 'Not connected' }}
              </p>
            </div>
          </div>
        </Card>
      </div>
    </template>
  </div>
</template>

<style>
/* Terminal styling - ensure xterm fills container */
.xterm {
  padding: 8px;
  height: 100% !important;
  width: 100% !important;
}
.xterm-screen {
  height: 100% !important;
  width: 100% !important;
}
.xterm-viewport {
  height: 100% !important;
  overflow-y: auto !important;
}
.xterm-rows {
  height: 100% !important;
}
</style>
