<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/views/SystemView.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useThemeStore } from '../stores/theme'
import { useAuthStore } from '../stores/auth'
import { useNotificationStore } from '../stores/notifications'
import api, { systemApi, settingsApi } from '../services/api'
import { formatBytes, getProgressColor } from '../utils/formatters'
import { usePoll } from '../composables/usePoll'
import { POLLING } from '../config/constants'
import Card from '../components/common/Card.vue'
import LoadingSpinner from '../components/common/LoadingSpinner.vue'
import HeartbeatLoader from '../components/common/HeartbeatLoader.vue'
import DnaHelixLoader from '../components/common/DnaHelixLoader.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
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
  KeyIcon,
  Cog6ToothIcon,
  EyeIcon,
  EyeSlashIcon,
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
const router = useRouter()
const themeStore = useThemeStore()
const authStore = useAuthStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const activeTab = ref('health')

// Tab definitions - Overview tab moved to Dashboard
const tabs = [
  { id: 'health', name: 'Health', icon: SignalIcon, iconColor: 'text-emerald-500', bgActive: 'bg-emerald-500/15 dark:bg-emerald-500/20', textActive: 'text-emerald-700 dark:text-emerald-400', borderActive: 'border-emerald-500/30' },
  { id: 'network', name: 'Network', icon: GlobeAltIcon, iconColor: 'text-purple-500', bgActive: 'bg-purple-500/15 dark:bg-purple-500/20', textActive: 'text-purple-700 dark:text-purple-400', borderActive: 'border-purple-500/30' },
  { id: 'terminal', name: 'Terminal', icon: CommandLineIcon, iconColor: 'text-amber-500', bgActive: 'bg-amber-500/15 dark:bg-amber-500/20', textActive: 'text-amber-700 dark:text-amber-400', borderActive: 'border-amber-500/30' },
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
const allHealthMessages = [
  'Running health checks...',
  'Still here, just a moment...',
  'Poking the containers to see if they respond...',
  'Asking Docker nicely for information...',
  'Counting all the bits and bytes...',
  'Making sure nothing is on fire...',
  'Consulting the server spirits...',
  'Almost done, gathering the last pieces...',
  'Checking if SSL certificates are happy...',
  'Verifying databases are awake...',
  'Double-checking everything twice...',
  'Waking up the hamsters that power the servers...',
  'Bribing the load balancer with cookies...',
  'Teaching containers to play nice together...',
  'Performing ancient DevOps rituals...',
  'Asking nginx how it\'s feeling today...',
  'Making sure PostgreSQL had its coffee...',
  'Untangling the network spaghetti...',
  'Checking if anyone left the debug mode on...',
  'Politely requesting metrics from prometheus...',
  'Verifying no gremlins in the system...',
  'Inspecting the series of tubes...',
  'Ensuring electrons are flowing correctly...',
  'Checking under the hood for loose wires...',
]
// Shuffle and pick random messages for this session
const healthLoadingMessages = ref([])
const healthLoadingMessageIndex = ref(0)
let healthLoadingInterval = null

function shuffleMessages() {
  const shuffled = [...allHealthMessages].sort(() => Math.random() - 0.5)
  healthLoadingMessages.value = shuffled.slice(0, 12) // Pick 12 random ones
}

// Network loading messages
const allNetworkMessages = [
  'Scanning network interfaces...',
  'Counting all the IP addresses...',
  'Asking the router for directions...',
  'Mapping the series of tubes...',
  'Pinging all the things...',
  'Untangling the network cables...',
  'Checking if the internet is still there...',
  'Negotiating with DNS servers...',
  'Following the ethernet breadcrumbs...',
  'Waking up the network hamsters...',
  'Consulting the gateway oracle...',
  'Checking who\'s hogging the bandwidth...',
  'Making sure packets aren\'t getting lost...',
  'Verifying the subnet masks are on straight...',
  'Asking Tailscale how its day is going...',
  'Checking if Cloudflare is in a good mood...',
  'Inspecting the packet delivery routes...',
  'Making friends with the firewall...',
  'Ensuring no one\'s sniffing the packets...',
  'Teaching bytes to find their way home...',
  'Checking the wifi password is still secret...',
  'Measuring the speed of light through fiber...',
  'Confirming TCP and UDP are getting along...',
  'Asking the load balancer to share...',
]
const networkLoadingMessages = ref([])
const networkLoadingMessageIndex = ref(0)
let networkLoadingInterval = null

function shuffleNetworkMessages() {
  const shuffled = [...allNetworkMessages].sort(() => Math.random() - 0.5)
  networkLoadingMessages.value = shuffled.slice(0, 12)
}

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

// External services state
const externalServices = ref([])
const externalServicesLoading = ref(false)

// API Key editing state for Cloudflare and Tailscale
const cloudflareTokenModal = ref(false)
const cloudflareToken = ref('')
const cloudflareTokenLoading = ref(false)
const cloudflareTokenMasked = ref('')
const cloudflareTokenIsSet = ref(false)
const showCloudflareToken = ref(false)

const tailscaleKeyModal = ref(false)
const tailscaleKey = ref('')
const tailscaleKeyLoading = ref(false)
const tailscaleKeyMasked = ref('')
const tailscaleKeyIsSet = ref(false)
const showTailscaleKey = ref(false)

// Tailscale reset confirmation dialog
const tailscaleResetDialog = ref({
  open: false,
  loading: false,
  containerStatus: 'unknown',
  actionLabel: 'Restart'
})

// Container restart state
const restartDialog = ref({
  open: false,
  containerName: '',
  displayName: '',
  loading: false,
})

// SSL Certificate renewal state
const sslRenewModal = ref(false)
const sslRenewing = ref(false)
const sslRenewalResult = ref(null)

// Logs detail modal state
const logsDetailModal = ref(false)

function openLogsDetailModal() {
  // Only open if there are errors or warnings
  const logs = healthData.value.checks?.logs?.details
  if (logs && (logs.error_count > 0 || logs.warning_count > 0)) {
    logsDetailModal.value = true
  }
}

function hasLogsToShow() {
  const logs = healthData.value.checks?.logs?.details
  return logs && (logs.error_count > 0 || logs.warning_count > 0)
}

function navigateToContainer(containerName) {
  logsDetailModal.value = false
  router.push({ name: 'containers', query: { highlight: containerName } })
}

function formatLogTimestamp(timestamp) {
  if (!timestamp) return ''
  // Convert ISO timestamp to readable format
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return timestamp
  }
}

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
let pingInterval = null

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

async function loadData() {
  loading.value = true
  try {
    const [systemRes] = await Promise.all([
      systemApi.getInfo(),
    ])
    systemInfo.value = systemRes.data

    // Update chart data with real values
    cpuHistory.value.push(systemInfo.value.cpu?.usage || 0)
    cpuHistory.value.shift()
    memoryHistory.value.push(systemInfo.value.memory?.percent || 0)
    memoryHistory.value.shift()
  } catch (error) {
    console.error('System info load failed:', error)
    notificationStore.error('Failed to load system information')
  } finally {
    loading.value = false
  }
}

async function loadHealthData() {
  healthLoading.value = true
  healthLoadingMessageIndex.value = 0
  shuffleMessages() // Randomize messages each time

  // Start rotating messages every 2 seconds
  healthLoadingInterval = setInterval(() => {
    healthLoadingMessageIndex.value = (healthLoadingMessageIndex.value + 1) % healthLoadingMessages.value.length
  }, 2000)

  try {
    const response = await systemApi.getHealthFull()
    healthData.value = response.data
    healthLastUpdated.value = new Date()
  } catch (error) {
    console.error('Health data load failed:', error)
    notificationStore.error('Failed to load health data')
    healthData.value.overall_status = 'error'
  } finally {
    // Stop rotating messages
    if (healthLoadingInterval) {
      clearInterval(healthLoadingInterval)
      healthLoadingInterval = null
    }
    healthLoading.value = false
  }
}

// Start polling for system info
usePoll(loadData, POLLING.DASHBOARD_METRICS, false)
// Poll health data every minute
usePoll(loadHealthData, 60000, false)

async function loadNetworkInfo() {
  networkLoading.value = true

  // Shuffle messages and start cycling
  shuffleNetworkMessages()
  networkLoadingMessageIndex.value = 0
  if (networkLoadingInterval) clearInterval(networkLoadingInterval)
  networkLoadingInterval = setInterval(() => {
    networkLoadingMessageIndex.value = (networkLoadingMessageIndex.value + 1) % networkLoadingMessages.value.length
  }, 2000)

  try {
    // Load network, cloudflare, and tailscale info in parallel
    const [networkRes, cloudflareRes, tailscaleRes] = await Promise.all([
      systemApi.getNetwork(),
      systemApi.getCloudflare().catch(() => ({ data: { error: 'Not available' } })),
      systemApi.getTailscale().catch(() => ({ data: { error: 'Not available' } })),
    ])
    networkInfo.value = networkRes.data
    cloudflareInfo.value = cloudflareRes.data
    tailscaleInfo.value = tailscaleRes.data
  } catch (error) {
    console.error('Network info load failed:', error.response?.data || error.message)
    const detail = error.response?.data?.detail
    notificationStore.error(detail ? `Network error: ${detail}` : 'Failed to load network information')
  } finally {
    if (networkLoadingInterval) clearInterval(networkLoadingInterval)
    networkLoading.value = false
  }
}

async function loadSslInfo() {
  sslLoading.value = true
  try {
    const response = await systemApi.getSsl()
    sslInfo.value = response.data
  } catch (error) {
    console.error('SSL info load failed:', error.response?.data || error.message)
    const detail = error.response?.data?.detail
    notificationStore.error(detail ? `SSL error: ${detail}` : 'Failed to load SSL information')
  } finally {
    sslLoading.value = false
  }
}

async function loadTerminalTargets() {
  try {
    const response = await systemApi.getTerminalTargets()
    terminalTargets.value = response.data.targets || []
    if (terminalTargets.value.length > 0 && !selectedTarget.value) {
      selectedTarget.value = terminalTargets.value[0].id
    }
  } catch (error) {
    console.error('Failed to load terminal targets:', error)
  }
}

async function loadExternalServices() {
  externalServicesLoading.value = true
  try {
    const response = await systemApi.getExternalServices()
    // Build URLs using current origin + path from nginx.conf
    const origin = window.location.origin
    externalServices.value = (response.data.services || []).map(service => ({
      ...service,
      url: `${origin}${service.path}`,
    }))
  } catch (error) {
    console.error('Failed to load external services:', error)
    externalServices.value = []
  } finally {
    externalServicesLoading.value = false
  }
}

async function runHealthCheck() {
  try {
    const response = await systemApi.getHealth()
    healthChecks.value = response.data.checks || []
    notificationStore.success('Health check completed')
  } catch (error) {
    notificationStore.error('Health check failed')
  }
}

// Cloudflare Token Management
async function loadCloudflareTokenStatus() {
  try {
    const response = await settingsApi.getEnvVariable('CLOUDFLARE_TUNNEL_TOKEN')
    cloudflareTokenIsSet.value = response.data.is_set
    cloudflareTokenMasked.value = response.data.masked_value || ''
  } catch (error) {
    console.error('Failed to load Cloudflare token status:', error)
  }
}

function openCloudflareTokenModal() {
  cloudflareToken.value = ''
  showCloudflareToken.value = false
  cloudflareTokenModal.value = true
}

function closeCloudflareTokenModal() {
  cloudflareTokenModal.value = false
  cloudflareToken.value = ''
  showCloudflareToken.value = false
}

async function saveCloudflareToken() {
  if (!cloudflareToken.value.trim()) {
    notificationStore.error('Token cannot be empty')
    return
  }

  cloudflareTokenLoading.value = true
  try {
    const response = await settingsApi.updateEnvVariable('CLOUDFLARE_TUNNEL_TOKEN', cloudflareToken.value.trim())
    cloudflareTokenIsSet.value = true
    cloudflareTokenMasked.value = response.data.masked_value || ''
    cloudflareTokenModal.value = false
    cloudflareToken.value = ''
    showCloudflareToken.value = false

    if (response.data.requires_restart) {
      notificationStore.success('Cloudflare token saved. Restart the container to apply changes.')
    } else {
      notificationStore.success('Cloudflare token saved successfully')
    }
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to save token')
  } finally {
    cloudflareTokenLoading.value = false
  }
}

// Tailscale Key Management
async function loadTailscaleKeyStatus() {
  try {
    const response = await settingsApi.getEnvVariable('TAILSCALE_AUTH_KEY')
    tailscaleKeyIsSet.value = response.data.is_set
    tailscaleKeyMasked.value = response.data.masked_value || ''
  } catch (error) {
    console.error('Failed to load Tailscale key status:', error)
  }
}

function openTailscaleKeyModal() {
  tailscaleKey.value = ''
  showTailscaleKey.value = false
  tailscaleKeyModal.value = true
}

function closeTailscaleKeyModal() {
  tailscaleKeyModal.value = false
  tailscaleKey.value = ''
  showTailscaleKey.value = false
}

async function saveTailscaleKey() {
  if (!tailscaleKey.value.trim()) {
    notificationStore.error('Auth key cannot be empty')
    return
  }

  tailscaleKeyLoading.value = true
  try {
    const response = await settingsApi.updateEnvVariable('TAILSCALE_AUTH_KEY', tailscaleKey.value.trim())
    tailscaleKeyIsSet.value = true
    tailscaleKeyMasked.value = response.data.masked_value || ''
    tailscaleKeyModal.value = false
    tailscaleKey.value = ''
    showTailscaleKey.value = false

    // Get container status to determine button label
    try {
      const statusRes = await settingsApi.getTailscaleStatus()
      tailscaleResetDialog.value.containerStatus = statusRes.data.status
      tailscaleResetDialog.value.actionLabel = statusRes.data.action_label || 'Restart'
    } catch {
      tailscaleResetDialog.value.actionLabel = 'Start'
    }

    // Show confirmation dialog for container restart
    tailscaleResetDialog.value.open = true
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to save auth key')
  } finally {
    tailscaleKeyLoading.value = false
  }
}

async function confirmTailscaleReset() {
  tailscaleResetDialog.value.loading = true
  try {
    await settingsApi.resetTailscale()
    notificationStore.success('Tailscale container restarted with new auth key')
    tailscaleResetDialog.value.open = false

    // Reload Tailscale info after a delay
    setTimeout(() => loadNetworkInfo(), 5000)
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to reset Tailscale container')
  } finally {
    tailscaleResetDialog.value.loading = false
  }
}

function cancelTailscaleReset() {
  tailscaleResetDialog.value.open = false
  notificationStore.info('Auth key saved but container not restarted. You can restart it manually later.')
}

// Container Restart
function openRestartDialog(containerName, displayName) {
  restartDialog.value = {
    open: true,
    containerName,
    displayName,
    loading: false,
  }
}

async function confirmRestart() {
  const { containerName, displayName } = restartDialog.value
  if (!containerName) return

  restartDialog.value.loading = true
  try {
    await settingsApi.restartContainer(containerName, 'Manual restart from System page')
    notificationStore.success(`${displayName} restarted successfully`)

    // Reload the relevant info after restart
    if (containerName === 'n8n_cloudflared' || containerName === 'n8n_tailscale') {
      setTimeout(() => loadNetworkInfo(), 3000)
    }
    restartDialog.value.open = false
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || `Failed to restart ${displayName}`)
  } finally {
    restartDialog.value.loading = false
  }
}

// SSL Certificate Renewal
function openSslRenewModal() {
  sslRenewalResult.value = null
  sslRenewModal.value = true
}

function closeSslRenewModal() {
  sslRenewModal.value = false
  sslRenewalResult.value = null
}

async function forceRenewSslCertificate() {
  sslRenewing.value = true
  sslRenewalResult.value = null

  try {
    const response = await systemApi.sslRenew()
    sslRenewalResult.value = response.data

    if (response.data.success) {
      notificationStore.success('SSL certificate renewed successfully')
      // Reload health data to show updated certificate info
      setTimeout(() => loadHealthData(), 2000)
    } else {
      notificationStore.error(response.data.message || 'Certificate renewal failed')
    }
  } catch (error) {
    sslRenewalResult.value = {
      success: false,
      message: error.response?.data?.detail || 'Failed to renew certificate',
    }
    notificationStore.error(error.response?.data?.detail || 'Failed to renew certificate')
  } finally {
    sslRenewing.value = false
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
      rows: 35,
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

      // Start ping interval (30s)
      if (pingInterval) clearInterval(pingInterval)
      pingInterval = setInterval(() => {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
          websocket.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30000)
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
        } else if (msg.type === 'pong') {
          // Pong received, connection is alive
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
      if (pingInterval) {
        clearInterval(pingInterval)
        pingInterval = null
      }
    }

    websocket.onclose = () => {
      terminalConnecting.value = false
      terminalConnected.value = false
      terminal?.writeln('\r\n\x1b[33mConnection closed\x1b[0m')
      if (pingInterval) {
        clearInterval(pingInterval)
        pingInterval = null
      }
    }

  } catch (error) {
    console.error('Failed to connect:', error)
    terminalConnecting.value = false
    notificationStore.error('Failed to connect to terminal')
  }
}

function disconnectTerminal() {
  terminalConnected.value = false
  terminalConnecting.value = false
  if (pingInterval) {
    clearInterval(pingInterval)
    pingInterval = null
  }
  if (websocket) {
    try {
      websocket.close()
    } catch (e) {
      console.error('Error closing websocket:', e)
    }
    websocket = null
  }
  terminal?.writeln('\r\n\x1b[33mDisconnected\x1b[0m')
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
  } else if (newTab === 'network') {
    if (networkInfo.value.interfaces.length === 0) {
      await loadNetworkInfo()
    }
    if (externalServices.value.length === 0) {
      await loadExternalServices()
    }
    // Load token statuses
    await Promise.all([
      loadCloudflareTokenStatus(),
      loadTailscaleKeyStatus(),
    ])
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
  }

  // Always load health data if we're on the health tab (default or via query param)
  if (activeTab.value === 'health') {
    await loadHealthData()
  }

  // If going to terminal tab with a target, pre-select it and optionally auto-connect
  if (activeTab.value === 'terminal' && route.query.target) {
    await loadTerminalTargets()
    // Find matching target by container ID (first 12 chars)
    const targetId = route.query.target.slice(0, 12)
    const matchingTarget = terminalTargets.value.find(t => t.id === targetId || t.id.startsWith(targetId))
    if (matchingTarget) {
      selectedTarget.value = matchingTarget.id
      // Auto-connect if requested
      if (route.query.autoconnect === 'true') {
        // Wait for DOM to render, then initialize terminal properly before connecting
        await nextTick()
        await initTerminal()
        // Give terminal time to fully initialize and render
        await new Promise(resolve => setTimeout(resolve, 200))
        if (!terminalConnected.value && selectedTarget.value && terminal) {
          connectTerminal()
        }
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
  // Clean up health loading message interval
  if (healthLoadingInterval) {
    clearInterval(healthLoadingInterval)
    healthLoadingInterval = null
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
            'text-primary'
          ]"
        >
          System
        </h1>
        <p class="text-secondary mt-1">Server health, network, and terminal access</p>
      </div>
    </div>

    <!-- Tabs -->
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-400 dark:border-gray-700 p-1.5 flex gap-1.5 overflow-x-auto">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="activeTab = tab.id"
        :class="[
          'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap border',
          activeTab === tab.id
            ? `${tab.bgActive} ${tab.textActive} ${tab.borderActive}`
            : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700/50 border-transparent'
        ]"
      >
        <component :is="tab.icon" :class="['h-4 w-4', activeTab === tab.id ? '' : tab.iconColor]" />
        {{ tab.name }}
      </button>
    </div>

    <!-- Health Tab -->
    <template v-if="activeTab === 'health'">
      <HeartbeatLoader v-if="healthLoading" :text="healthLoadingMessages[healthLoadingMessageIndex]" color="emerald" class="py-16 mt-8" />

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
          <Card :padding="false">
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
              <div v-if="healthData.checks?.docker?.details?.unhealthy_containers?.length" class="mt-3 pt-3 border-t border-gray-400 dark:border-black">
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
          <Card :padding="false">
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

          <!-- n8n Database -->
          <Card :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-amber-100 dark:bg-amber-500/20">
                  <CircleStackIcon class="h-5 w-5 text-amber-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">n8n Database</h3>
                  <p class="text-xs text-muted">Main workflow database</p>
                </div>
                <span
                  :class="[
                    'px-2 py-1 rounded-full text-xs font-medium',
                    healthData.checks?.database?.details?.n8n_db === 'ok'
                      ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                      : 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400'
                  ]"
                >
                  {{ healthData.checks?.database?.details?.n8n_db === 'ok' ? 'OK' : 'ERROR' }}
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
                  <span class="text-secondary">Database</span>
                  <span :class="['font-medium', healthData.checks?.database?.details?.n8n_db === 'ok' ? 'text-emerald-500' : 'text-red-500']">
                    {{ healthData.checks?.database?.details?.n8n_db || 'N/A' }}
                  </span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Version</span>
                  <span class="font-medium text-primary">PostgreSQL {{ healthData.checks?.database?.details?.version || 'N/A' }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">User</span>
                  <span class="font-medium text-primary">{{ healthData.checks?.database?.details?.user || 'N/A' }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Name</span>
                  <span class="font-medium text-primary">n8n</span>
                </div>
              </div>
            </div>
          </Card>

          <!-- Host System Resources -->
          <Card :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-cyan-100 dark:bg-cyan-500/20">
                  <CpuChipIcon class="h-5 w-5 text-cyan-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">Host System Resources</h3>
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
          <Card :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-500/20">
                  <LockClosedIcon class="h-5 w-5 text-emerald-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">SSL Certificates</h3>
                  <p class="text-xs text-muted">Certificate validity</p>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    @click="openSslRenewModal"
                    :class="[
                      'px-3 py-1.5 rounded-full text-xs font-medium transition-all shadow-sm flex items-center gap-1.5',
                      healthData.checks?.ssl?.status === 'ok'
                        ? 'bg-emerald-500 hover:bg-emerald-600 text-white'
                        : 'bg-amber-500 hover:bg-amber-600 text-white'
                    ]"
                  >
                    <ArrowPathIcon class="h-3.5 w-3.5" />
                    Force Renew
                  </button>
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
              </div>
              <!-- Show certificates from array if available -->
              <div v-if="healthData.ssl_certificates?.length" class="space-y-2">
                <div
                  v-for="cert in healthData.ssl_certificates"
                  :key="cert.domain"
                  class="p-3 rounded-lg bg-surface-hover"
                >
                  <div class="flex justify-between items-center text-sm mb-2">
                    <span class="text-secondary">Domain</span>
                    <span class="font-medium text-primary">{{ cert.domain }}</span>
                  </div>
                  <div class="flex justify-between items-center text-sm mb-2">
                    <span class="text-secondary">Valid For</span>
                    <span
                      :class="[
                        'font-medium',
                        cert.days_until_expiry > 30 ? 'text-emerald-500' :
                        cert.days_until_expiry > 7 ? 'text-amber-500' : 'text-red-500'
                      ]"
                    >
                      {{ cert.days_until_expiry }} days
                    </span>
                  </div>
                  <div class="flex justify-between items-center text-sm">
                    <span class="text-secondary">Expires</span>
                    <span class="font-medium text-primary text-xs">{{ cert.expires }}</span>
                  </div>
                </div>
              </div>
              <!-- Fallback: show from ssl details if no certificates array but domain exists -->
              <div v-else-if="healthData.checks?.ssl?.details?.domain" class="space-y-2">
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Domain</span>
                  <span class="font-medium text-primary">{{ healthData.checks?.ssl?.details?.domain }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Valid For</span>
                  <span
                    :class="[
                      'font-medium',
                      (healthData.checks?.ssl?.details?.days_until_expiry || 0) > 30 ? 'text-emerald-500' :
                      (healthData.checks?.ssl?.details?.days_until_expiry || 0) > 7 ? 'text-amber-500' : 'text-red-500'
                    ]"
                  >
                    {{ healthData.checks?.ssl?.details?.days_until_expiry || 0 }} days
                  </span>
                </div>
              </div>
              <!-- No SSL data at all -->
              <div v-else class="text-sm text-muted">
                {{ healthData.checks?.ssl?.details?.message || healthData.checks?.ssl?.details?.error || 'No certificates found' }}
              </div>
            </div>
          </Card>

          <!-- Management Database -->
          <Card :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-500/20">
                  <CircleStackIcon class="h-5 w-5 text-indigo-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">Management DB</h3>
                  <p class="text-xs text-muted">Console database</p>
                </div>
                <span
                  :class="[
                    'px-2 py-1 rounded-full text-xs font-medium',
                    healthData.checks?.database?.details?.management_db === 'ok'
                      ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                      : healthData.checks?.database?.details?.management_db === 'warning'
                        ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400'
                        : 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400'
                  ]"
                >
                  {{ healthData.checks?.database?.details?.management_db === 'ok' ? 'OK' : healthData.checks?.database?.details?.management_db === 'warning' ? 'WARN' : 'ERROR' }}
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
                  <span class="text-secondary">Database</span>
                  <span :class="['font-medium', healthData.checks?.database?.details?.management_db === 'ok' ? 'text-emerald-500' : healthData.checks?.database?.details?.management_db === 'warning' ? 'text-amber-500' : 'text-red-500']">
                    {{ healthData.checks?.database?.details?.management_db || 'N/A' }}
                  </span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Version</span>
                  <span class="font-medium text-primary">PostgreSQL {{ healthData.checks?.database?.details?.version || 'N/A' }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">User</span>
                  <span class="font-medium text-primary">{{ healthData.checks?.database?.details?.user || 'N/A' }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Name</span>
                  <span class="font-medium text-primary">n8n_management</span>
                </div>
              </div>
            </div>
          </Card>

          <!-- Backups -->
          <Card :padding="false">
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
                <div class="flex justify-between items-center text-sm">
                  <span class="text-secondary">Total Size</span>
                  <span class="font-medium text-primary">
                    {{ healthData.checks?.backups?.details?.total_size_display || '0 B' }}
                  </span>
                </div>
              </div>
            </div>
          </Card>

          <!-- Recent Logs (Clickable when has errors/warnings) -->
          <Card
           
            :padding="false"
            :class="{ 'cursor-pointer hover:ring-2 hover:ring-rose-500/50 transition-all': hasLogsToShow() }"
            @click="openLogsDetailModal"
          >
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 rounded-lg bg-rose-100 dark:bg-rose-500/20">
                  <DocumentTextIcon class="h-5 w-5 text-rose-500" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-primary">Recent Logs</h3>
                  <p class="text-xs text-muted">
                    Error analysis
                    <span v-if="hasLogsToShow()" class="text-rose-500 ml-1">(click for details)</span>
                  </p>
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
              <!-- Per-container breakdown (summary) -->
              <div v-if="Object.keys(healthData.checks?.logs?.details?.by_container || {}).length" class="mt-3 pt-3 border-t border-gray-400 dark:border-black">
                <p class="text-xs text-muted mb-2">By Container:</p>
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="(stats, name) in healthData.checks?.logs?.details?.by_container"
                    :key="name"
                    :class="[
                      'px-2 py-0.5 text-xs rounded-full',
                      stats.error_count > 0 ? 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400' : 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400'
                    ]"
                  >
                    {{ name.replace('n8n_', '') }}: {{ stats.error_count }}
                  </span>
                </div>
              </div>
            </div>
          </Card>

          <!-- Docker Disk -->
          <Card :padding="false">
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

      </template>
    </template>

    <!-- Network Tab -->
    <template v-if="activeTab === 'network'">
      <DnaHelixLoader v-if="networkLoading" :text="networkLoadingMessages[networkLoadingMessageIndex] || 'Scanning network interfaces...'" class="py-16 mt-8" />

      <template v-else>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- External Services -->
          <Card title="External Services">
            <div v-if="externalServices.length > 0" class="grid grid-cols-1 gap-3">
              <a
                v-for="service in externalServices"
                :key="service.name"
                :href="service.url"
                target="_blank"
                rel="noopener noreferrer"
                class="group block p-4 bg-surface rounded-lg border border-gray-400 dark:border-black hover:border-blue-500 hover:shadow-md transition-all"
              >
                <div class="flex items-center gap-3">
                  <div :class="['p-2 rounded-lg', service.color || 'bg-blue-100 dark:bg-blue-500/20']">
                    <LinkIcon :class="['h-5 w-5', service.iconColor || 'text-blue-500']" />
                  </div>
                  <div class="flex-1 min-w-0">
                    <h4 class="font-semibold text-primary group-hover:text-blue-500 transition-colors">{{ service.name }}</h4>
                    <p class="text-xs text-muted">{{ service.description }}</p>
                  </div>
                  <div class="flex items-center gap-2">
                    <span
                      :class="[
                        'w-2 h-2 rounded-full',
                        service.running ? 'bg-emerald-500' : 'bg-gray-400'
                      ]"
                    ></span>
                    <svg class="h-4 w-4 text-gray-400 group-hover:text-blue-500 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </div>
                </div>
              </a>
            </div>
            <div v-else class="text-center py-4 text-muted">
              No external services configured in nginx
            </div>
          </Card>

          <!-- Network Configuration (with hostname in header) -->
          <Card :padding="false">
            <template #header>
              <div class="flex items-center justify-between w-full px-4 py-3">
                <h3 class="font-semibold text-primary">Network Configuration</h3>
                <span class="px-3 py-1 bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300 rounded-full text-sm font-mono">
                  {{ networkInfo.hostname || 'unknown' }}
                </span>
              </div>
            </template>
            <div class="p-4 space-y-4">
              <!-- Gateway & DNS -->
              <div class="space-y-2">
                <div class="flex justify-between py-2 border-b border-gray-400 dark:border-black">
                  <span class="text-secondary">Default Gateway</span>
                  <span class="font-medium text-primary font-mono">{{ networkInfo.gateway || 'N/A' }}</span>
                </div>
                <div class="flex justify-between py-2 border-b border-gray-400 dark:border-black">
                  <span class="text-secondary">DNS Servers</span>
                  <div class="text-right">
                    <span
                      v-for="(dns, i) in networkInfo.dns_servers"
                      :key="i"
                      class="font-medium text-primary font-mono block"
                    >
                      {{ dns }}
                    </span>
                    <span v-if="!networkInfo.dns_servers?.length" class="text-muted">None</span>
                  </div>
                </div>
              </div>

              <!-- Network Interfaces -->
              <div class="space-y-3">
                <h4 class="text-sm font-medium text-secondary">Interfaces</h4>
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
                  </div>
                </div>
                <div v-if="!networkInfo.interfaces?.length" class="text-center py-4 text-muted">
                  No network interfaces found
                </div>
              </div>
            </div>
          </Card>
        </div>

        <!-- VPN & Tunnel Services -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          <!-- Cloudflare Tunnel -->
          <Card :padding="false">
            <template #header>
              <div class="flex items-center justify-between w-full px-4 py-3">
                <div class="flex items-center gap-2">
                  <CloudIcon class="h-5 w-5 text-orange-500" />
                  <h3 class="font-semibold text-primary">Cloudflare Tunnel</h3>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    @click="openCloudflareTokenModal"
                    :class="[
                      'px-3 py-1.5 rounded-full text-xs font-medium transition-all shadow-sm flex items-center gap-1.5',
                      cloudflareInfo.running
                        ? 'bg-emerald-500 hover:bg-emerald-600 text-white'
                        : 'bg-gray-300 dark:bg-gray-600 hover:bg-gray-400 dark:hover:bg-gray-500 text-gray-700 dark:text-gray-300'
                    ]"
                  >
                    <KeyIcon class="h-3.5 w-3.5" />
                    API Key
                  </button>
                  <button
                    v-if="cloudflareInfo.running"
                    @click="openRestartDialog('n8n_cloudflared', 'Cloudflare Tunnel')"
                    class="btn-secondary flex items-center gap-1.5 text-xs py-1 px-2"
                    title="Restart Container"
                  >
                    <ArrowPathIcon class="h-3.5 w-3.5" />
                    Restart
                  </button>
                </div>
              </div>
            </template>
            <div class="p-4">
            <div v-if="cloudflareInfo.error && !cloudflareInfo.installed" class="flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-500/10 rounded-lg">
              <CloudIcon class="h-6 w-6 text-gray-400" />
              <p class="text-muted">{{ cloudflareInfo.error }}</p>
            </div>
            <template v-else>
              <div class="space-y-3">
                <!-- Status -->
                <div class="flex items-center justify-between py-2 border-b border-gray-400 dark:border-black">
                  <span class="text-secondary">Status</span>
                  <span :class="[
                    'flex items-center gap-2 font-medium',
                    cloudflareInfo.running ? 'text-emerald-500' : 'text-red-500'
                  ]">
                    <span :class="['w-2 h-2 rounded-full', cloudflareInfo.running ? 'bg-emerald-500' : 'bg-red-500']"></span>
                    {{ cloudflareInfo.running ? 'Running' : 'Stopped' }}
                  </span>
                </div>
                <div v-if="cloudflareInfo.version" class="flex justify-between py-2 border-b border-gray-400 dark:border-black">
                  <span class="text-secondary">Version</span>
                  <span class="font-medium text-primary">{{ cloudflareInfo.version }}</span>
                </div>
                <div v-if="cloudflareInfo.connected !== undefined" class="flex justify-between py-2 border-b border-gray-400 dark:border-black">
                  <span class="text-secondary">Connected</span>
                  <span :class="cloudflareInfo.connected ? 'text-emerald-500' : 'text-amber-500'">
                    {{ cloudflareInfo.connected ? 'Yes' : 'No' }}
                  </span>
                </div>
                <div v-if="cloudflareInfo.edge_locations?.length" class="flex justify-between py-2 border-b border-gray-400 dark:border-black">
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
                <div v-if="cloudflareInfo.tunnel_id" class="flex justify-between py-2 border-b border-gray-400 dark:border-black">
                  <span class="text-secondary">Tunnel ID</span>
                  <span class="font-mono text-xs text-primary truncate max-w-[180px]" :title="cloudflareInfo.tunnel_id">
                    {{ cloudflareInfo.tunnel_id.slice(0, 8) }}...
                  </span>
                </div>
                <div v-if="cloudflareInfo.connector_id" class="flex justify-between py-2 border-b border-gray-400 dark:border-black">
                  <span class="text-secondary">Connector ID</span>
                  <span class="font-mono text-xs text-primary truncate max-w-[180px]" :title="cloudflareInfo.connector_id">
                    {{ cloudflareInfo.connector_id.slice(0, 8) }}...
                  </span>
                </div>
                <div v-if="cloudflareInfo.connections_per_location && Object.keys(cloudflareInfo.connections_per_location).length" class="flex justify-between py-2 border-b border-gray-400 dark:border-black">
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
            </div>
          </Card>

          <!-- Tailscale -->
          <Card :padding="false">
            <template #header>
              <div class="flex items-center justify-between w-full px-4 py-3">
                <div class="flex items-center gap-2">
                  <LinkIcon class="h-5 w-5 text-blue-500" />
                  <h3 class="font-semibold text-primary">Tailscale VPN</h3>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    @click="openTailscaleKeyModal"
                    :class="[
                      'px-3 py-1.5 rounded-full text-xs font-medium transition-all shadow-sm flex items-center gap-1.5',
                      tailscaleInfo.running && tailscaleInfo.logged_in
                        ? 'bg-emerald-500 hover:bg-emerald-600 text-white'
                        : 'bg-gray-300 dark:bg-gray-600 hover:bg-gray-400 dark:hover:bg-gray-500 text-gray-700 dark:text-gray-300'
                    ]"
                  >
                    <KeyIcon class="h-3.5 w-3.5" />
                    API Key
                  </button>
                  <button
                    v-if="tailscaleInfo.running"
                    @click="openRestartDialog('n8n_tailscale', 'Tailscale VPN')"
                    class="btn-secondary flex items-center gap-1.5 text-xs py-1 px-2"
                    title="Restart Container"
                  >
                    <ArrowPathIcon class="h-3.5 w-3.5" />
                    Restart
                  </button>
                </div>
              </div>
            </template>
            <div class="p-4">
            <div v-if="tailscaleInfo.error && !tailscaleInfo.installed" class="flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-500/10 rounded-lg">
              <LinkIcon class="h-6 w-6 text-gray-400" />
              <p class="text-muted">{{ tailscaleInfo.error }}</p>
            </div>
            <template v-else>
              <div class="space-y-3">
                <div class="flex items-center justify-between py-2 border-b border-gray-400 dark:border-black">
                  <span class="text-secondary">Status</span>
                  <span :class="[
                    'flex items-center gap-2 font-medium',
                    tailscaleInfo.running && tailscaleInfo.logged_in ? 'text-emerald-500' : 'text-red-500'
                  ]">
                    <span :class="['w-2 h-2 rounded-full', tailscaleInfo.running && tailscaleInfo.logged_in ? 'bg-emerald-500' : 'bg-red-500']"></span>
                    {{ tailscaleInfo.running && tailscaleInfo.logged_in ? 'Connected' : tailscaleInfo.running ? 'Not Logged In' : 'Stopped' }}
                  </span>
                </div>
                <div v-if="tailscaleInfo.tailscale_ip" class="flex justify-between py-2 border-b border-gray-400 dark:border-black">
                  <span class="text-secondary">Tailscale IP</span>
                  <span class="font-medium text-primary font-mono">{{ tailscaleInfo.tailscale_ip }}</span>
                </div>
                <div v-if="tailscaleInfo.hostname" class="flex justify-between py-2 border-b border-gray-400 dark:border-black">
                  <span class="text-secondary">Hostname</span>
                  <span class="font-medium text-primary">{{ tailscaleInfo.hostname }}</span>
                </div>
                <div v-if="tailscaleInfo.dns_name" class="flex justify-between py-2 border-b border-gray-400 dark:border-black">
                  <span class="text-secondary">DNS Name</span>
                  <span class="font-medium text-primary font-mono text-sm">{{ tailscaleInfo.dns_name }}</span>
                </div>
                <div v-if="tailscaleInfo.tailnet" class="flex justify-between py-2 border-b border-gray-400 dark:border-black">
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
            </div>
          </Card>
        </div>
      </template>
    </template>

    <!-- Terminal Tab -->
    <template v-if="activeTab === 'terminal'">
      <Card :padding="false">
        <!-- Header: Title LEFT | Dropdown CENTER | Buttons RIGHT -->
        <template #header>
          <div class="flex items-center w-full px-4 py-3">
            <!-- Left: Title -->
            <div class="flex items-center gap-2 flex-shrink-0">
              <CommandLineIcon class="h-5 w-5 text-primary" />
              <h3 class="font-semibold text-primary">Web Terminal</h3>
            </div>

            <!-- Center: Dropdown (with flex-1 spacers on each side) -->
            <div class="flex-1 flex justify-center items-center gap-2">
              <div class="relative">
                <select
                  v-model="selectedTarget"
                  :disabled="terminalConnected || terminalConnecting"
                  :class="[
                    'select-field text-sm py-1.5 min-w-[220px] bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white',
                    (terminalConnected || terminalConnecting) ? 'opacity-50 cursor-not-allowed' : ''
                  ]"
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
              </div>
              <button
                @click="loadTerminalTargets"
                :disabled="terminalConnected || terminalConnecting"
                class="p-1.5 rounded-lg text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title="Refresh targets"
              >
                <ArrowPathIcon class="h-4 w-4" />
              </button>
            </div>

            <!-- Right: Theme Toggle + Connect Button -->
            <div class="flex items-center gap-2 flex-shrink-0">
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

              <button
                v-if="!terminalConnected"
                @click="connectTerminal"
                :disabled="terminalConnecting || !selectedTarget"
                class="btn-primary flex items-center gap-1.5 text-sm py-1.5 px-4"
              >
                <PlayIcon class="h-4 w-4" />
                {{ terminalConnecting ? 'Connecting...' : 'Connect' }}
              </button>
              <button
                v-else
                @click="disconnectTerminal"
                class="btn-secondary flex items-center gap-1.5 text-sm py-1.5 px-4 text-red-500 hover:bg-red-500/10"
              >
                <StopIcon class="h-4 w-4" />
                Disconnect
              </button>
            </div>
          </div>
        </template>

        <!-- Terminal Window - INLINE STYLE for guaranteed height -->
        <div class="p-4">
          <div
            ref="terminalElement"
            :class="['rounded-lg overflow-hidden', terminalDarkMode ? 'bg-[#0d1117]' : 'bg-white']"
            style="height: 62vh; min-height: 450px;"
          >
            <div v-if="!terminal" class="flex items-center justify-center h-full text-muted">
              <CommandLineIcon class="h-8 w-8 mr-2" />
              Select a target and click Connect to start a terminal session
            </div>
          </div>

          <!-- Terminal Status Bar -->
          <div class="mt-3 text-xs text-muted flex items-center">
            <span :class="['w-2 h-2 rounded-full mr-2', terminalConnected ? 'bg-emerald-500' : 'bg-gray-400']"></span>
            {{ terminalConnected ? `Connected to ${terminalTargets.find(t => t.id === selectedTarget)?.name}` : 'Not connected' }}
          </div>
        </div>
      </Card>
    </template>

    <!-- Cloudflare Token Modal -->
    <Teleport to="body">
      <div
        v-if="cloudflareTokenModal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" @click="closeCloudflareTokenModal"></div>
        <div class="relative bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-md w-full p-6 border border-gray-400 dark:border-gray-700">
          <div class="flex items-center gap-3 mb-4">
            <div class="p-2 rounded-lg bg-orange-100 dark:bg-orange-500/20">
              <CloudIcon class="h-6 w-6 text-orange-500" />
            </div>
            <div>
              <h3 class="text-lg font-semibold text-primary">Cloudflare Tunnel Token</h3>
              <p class="text-sm text-muted">Update your tunnel authentication token</p>
            </div>
          </div>

          <!-- Current Status -->
          <div class="mb-4 p-3 rounded-lg bg-surface-hover">
            <div class="flex items-center justify-between">
              <span class="text-secondary text-sm">Current Status</span>
              <span
                :class="[
                  'flex items-center gap-2 text-sm font-medium',
                  cloudflareTokenIsSet ? 'text-emerald-500' : 'text-amber-500'
                ]"
              >
                <span :class="['w-2 h-2 rounded-full', cloudflareTokenIsSet ? 'bg-emerald-500' : 'bg-amber-500']"></span>
                {{ cloudflareTokenIsSet ? 'Configured' : 'Not Set' }}
              </span>
            </div>
            <div v-if="cloudflareTokenIsSet" class="mt-2 flex items-center justify-between">
              <span class="text-secondary text-sm">Current Token</span>
              <span class="font-mono text-sm text-primary">{{ cloudflareTokenMasked }}</span>
            </div>
          </div>

          <!-- Input -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-primary mb-1.5">New Token</label>
            <div class="relative">
              <KeyIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted" />
              <input
                v-model="cloudflareToken"
                :type="showCloudflareToken ? 'text' : 'password'"
                placeholder="Enter Cloudflare tunnel token"
                class="input-field pl-10 pr-10 w-full"
              />
              <button
                type="button"
                @click="showCloudflareToken = !showCloudflareToken"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-secondary"
              >
                <EyeSlashIcon v-if="showCloudflareToken" class="h-5 w-5" />
                <EyeIcon v-else class="h-5 w-5" />
              </button>
            </div>
          </div>

          <!-- Info -->
          <div class="mb-6 p-3 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30">
            <p class="text-sm text-amber-700 dark:text-amber-400">
              After saving, you'll need to restart the Cloudflare container for changes to take effect.
            </p>
          </div>

          <!-- Actions -->
          <div class="flex gap-3 justify-end">
            <button @click="closeCloudflareTokenModal" class="btn-secondary">Cancel</button>
            <button
              @click="saveCloudflareToken"
              :disabled="cloudflareTokenLoading || !cloudflareToken.trim()"
              class="btn-primary"
            >
              {{ cloudflareTokenLoading ? 'Saving...' : 'Save Token' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Tailscale Auth Key Modal -->
    <Teleport to="body">
      <div
        v-if="tailscaleKeyModal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" @click="closeTailscaleKeyModal"></div>
        <div class="relative bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-md w-full p-6 border border-gray-400 dark:border-gray-700">
          <div class="flex items-center gap-3 mb-4">
            <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
              <LinkIcon class="h-6 w-6 text-blue-500" />
            </div>
            <div>
              <h3 class="text-lg font-semibold text-primary">Tailscale Auth Key</h3>
              <p class="text-sm text-muted">Update your Tailscale authentication key</p>
            </div>
          </div>

          <!-- Current Status -->
          <div class="mb-4 p-3 rounded-lg bg-surface-hover">
            <div class="flex items-center justify-between">
              <span class="text-secondary text-sm">Current Status</span>
              <span
                :class="[
                  'flex items-center gap-2 text-sm font-medium',
                  tailscaleKeyIsSet ? 'text-emerald-500' : 'text-amber-500'
                ]"
              >
                <span :class="['w-2 h-2 rounded-full', tailscaleKeyIsSet ? 'bg-emerald-500' : 'bg-amber-500']"></span>
                {{ tailscaleKeyIsSet ? 'Configured' : 'Not Set' }}
              </span>
            </div>
            <div v-if="tailscaleKeyIsSet" class="mt-2 flex items-center justify-between">
              <span class="text-secondary text-sm">Current Key</span>
              <span class="font-mono text-sm text-primary">{{ tailscaleKeyMasked }}</span>
            </div>
          </div>

          <!-- Input -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-primary mb-1.5">New Auth Key</label>
            <div class="relative">
              <KeyIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted" />
              <input
                v-model="tailscaleKey"
                :type="showTailscaleKey ? 'text' : 'password'"
                placeholder="Enter Tailscale auth key"
                class="input-field pl-10 pr-10 w-full"
              />
              <button
                type="button"
                @click="showTailscaleKey = !showTailscaleKey"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-secondary"
              >
                <EyeSlashIcon v-if="showTailscaleKey" class="h-5 w-5" />
                <EyeIcon v-else class="h-5 w-5" />
              </button>
            </div>
          </div>

          <!-- Info -->
          <div class="mb-6 p-3 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30">
            <p class="text-sm text-amber-700 dark:text-amber-400">
              After saving, you'll need to restart the Tailscale container for changes to take effect.
            </p>
          </div>

          <!-- Actions -->
          <div class="flex gap-3 justify-end">
            <button @click="closeTailscaleKeyModal" class="btn-secondary">Cancel</button>
            <button
              @click="saveTailscaleKey"
              :disabled="tailscaleKeyLoading || !tailscaleKey.trim()"
              class="btn-primary"
            >
              {{ tailscaleKeyLoading ? 'Saving...' : 'Save Key' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Tailscale Reset Confirmation Modal -->
    <Teleport to="body">
      <div
        v-if="tailscaleResetDialog.open"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" @click="!tailscaleResetDialog.loading && cancelTailscaleReset()"></div>
        <div class="relative bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-md w-full p-6 border border-gray-400 dark:border-gray-700">
          <div class="flex items-center gap-3 mb-4">
            <div class="p-2 rounded-lg bg-amber-100 dark:bg-amber-500/20">
              <ExclamationTriangleIcon class="h-6 w-6 text-amber-500" />
            </div>
            <div>
              <h3 class="text-lg font-semibold text-primary">Container Restart Required</h3>
              <p class="text-sm text-muted">The new auth key requires a container restart</p>
            </div>
          </div>

          <div class="mb-6 p-4 rounded-lg bg-surface-hover">
            <p class="text-sm text-secondary mb-3">
              To apply the new Tailscale auth key, the container must be restarted with fresh authentication state.
            </p>
            <p class="text-sm text-secondary">
              This will:
            </p>
            <ul class="text-sm text-secondary mt-2 ml-4 list-disc space-y-1">
              <li>Stop the Tailscale container</li>
              <li>Clear saved authentication data</li>
              <li>Start container with the new key</li>
            </ul>
          </div>

          <div class="flex justify-end gap-3">
            <button
              @click="cancelTailscaleReset"
              :disabled="tailscaleResetDialog.loading"
              class="btn-secondary"
            >
              Later
            </button>
            <button
              @click="confirmTailscaleReset"
              :disabled="tailscaleResetDialog.loading"
              class="btn-primary"
            >
              <ArrowPathIcon v-if="tailscaleResetDialog.loading" class="h-4 w-4 animate-spin mr-2" />
              {{ tailscaleResetDialog.loading ? 'Restarting...' : tailscaleResetDialog.actionLabel + ' Container' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- SSL Certificate Renewal Modal -->
    <Teleport to="body">
      <div
        v-if="sslRenewModal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" @click="!sslRenewing && closeSslRenewModal()"></div>
        <div class="relative bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-lg w-full p-6 border border-gray-400 dark:border-gray-700">
          <div class="flex items-center gap-3 mb-4">
            <div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-500/20">
              <LockClosedIcon class="h-6 w-6 text-emerald-500" />
            </div>
            <div>
              <h3 class="text-lg font-semibold text-primary">Force Renew SSL Certificate</h3>
              <p class="text-sm text-muted">Request new certificate from Let's Encrypt</p>
            </div>
          </div>

          <!-- Current Certificate Info -->
          <div v-if="!sslRenewalResult" class="space-y-4">
            <div class="p-4 rounded-lg bg-surface-hover">
              <h4 class="text-sm font-medium text-primary mb-3">Current Certificate</h4>
              <div v-if="healthData.ssl_certificates?.length" class="space-y-2">
                <div
                  v-for="cert in healthData.ssl_certificates"
                  :key="cert.domain"
                  class="text-sm"
                >
                  <div class="flex justify-between mb-1">
                    <span class="text-secondary">Domain</span>
                    <span class="font-medium text-primary">{{ cert.domain }}</span>
                  </div>
                  <div class="flex justify-between mb-1">
                    <span class="text-secondary">Expires In</span>
                    <span
                      :class="[
                        'font-medium',
                        cert.days_until_expiry > 30 ? 'text-emerald-500' :
                        cert.days_until_expiry > 7 ? 'text-amber-500' : 'text-red-500'
                      ]"
                    >
                      {{ cert.days_until_expiry }} days
                    </span>
                  </div>
                  <div class="flex justify-between">
                    <span class="text-secondary">Expiry Date</span>
                    <span class="font-medium text-primary text-xs">{{ cert.expires }}</span>
                  </div>
                </div>
              </div>
              <div v-else-if="healthData.checks?.ssl?.details?.days_until_expiry" class="text-sm">
                <div class="flex justify-between mb-1">
                  <span class="text-secondary">Domain</span>
                  <span class="font-medium text-primary">{{ healthData.checks?.ssl?.details?.domain || 'N/A' }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-secondary">Expires In</span>
                  <span
                    :class="[
                      'font-medium',
                      (healthData.checks?.ssl?.details?.days_until_expiry || 0) > 30 ? 'text-emerald-500' :
                      (healthData.checks?.ssl?.details?.days_until_expiry || 0) > 7 ? 'text-amber-500' : 'text-red-500'
                    ]"
                  >
                    {{ healthData.checks?.ssl?.details?.days_until_expiry || 0 }} days
                  </span>
                </div>
              </div>
              <div v-else class="text-sm text-muted">
                No certificate information available
              </div>
            </div>

            <!-- Warning -->
            <div class="p-3 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30">
              <div class="flex gap-2">
                <ExclamationTriangleIcon class="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                <div class="text-sm text-amber-700 dark:text-amber-400">
                  <p class="font-medium mb-1">Important:</p>
                  <ul class="list-disc list-inside space-y-1 text-xs">
                    <li>This will request a new certificate from Let's Encrypt</li>
                    <li>Let's Encrypt has rate limits (5 certificates per domain per week)</li>
                    <li>Nginx will be automatically reloaded after renewal</li>
                    <li>This may take 30-60 seconds to complete</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          <!-- Renewal Result -->
          <div v-else class="space-y-4">
            <div
              :class="[
                'p-4 rounded-lg',
                sslRenewalResult.success
                  ? 'bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30'
                  : 'bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30'
              ]"
            >
              <div class="flex items-center gap-2 mb-2">
                <CheckCircleIcon v-if="sslRenewalResult.success" class="h-5 w-5 text-emerald-500" />
                <XCircleIcon v-else class="h-5 w-5 text-red-500" />
                <span
                  :class="[
                    'font-medium',
                    sslRenewalResult.success ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'
                  ]"
                >
                  {{ sslRenewalResult.success ? 'Renewal Successful' : 'Renewal Failed' }}
                </span>
              </div>
              <p class="text-sm text-secondary">{{ sslRenewalResult.message }}</p>
              <div v-if="sslRenewalResult.nginx_reloaded" class="mt-2 text-xs text-emerald-600 dark:text-emerald-400">
                Nginx has been reloaded to apply the new certificate.
              </div>
            </div>

            <!-- Detailed Output (collapsible) -->
            <details v-if="sslRenewalResult.renewal_output" class="group">
              <summary class="cursor-pointer text-sm text-secondary hover:text-primary flex items-center gap-1">
                <ChevronDownIcon class="h-4 w-4 transition-transform group-open:rotate-180" />
                View detailed output
              </summary>
              <pre class="mt-2 p-3 rounded-lg bg-gray-900 text-gray-100 text-xs overflow-auto max-h-48 font-mono">{{ sslRenewalResult.renewal_output }}</pre>
            </details>
          </div>

          <!-- Actions -->
          <div class="flex gap-3 justify-end mt-6">
            <button
              @click="closeSslRenewModal"
              :disabled="sslRenewing"
              class="btn-secondary"
            >
              {{ sslRenewalResult ? 'Close' : 'Cancel' }}
            </button>
            <button
              v-if="!sslRenewalResult"
              @click="forceRenewSslCertificate"
              :disabled="sslRenewing"
              class="btn-primary flex items-center gap-2"
            >
              <ArrowPathIcon v-if="sslRenewing" class="h-4 w-4 animate-spin" />
              {{ sslRenewing ? 'Renewing...' : 'Force Renew' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Container Restart Confirmation Dialog -->
    <ConfirmDialog
      :open="restartDialog.open"
      title="Restart Container"
      :message="`Are you sure you want to restart ${restartDialog.displayName}? This may cause a brief service interruption.`"
      confirm-text="Restart"
      :loading="restartDialog.loading"
      @confirm="confirmRestart"
      @cancel="restartDialog.open = false"
    />

    <!-- Logs Detail Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="logsDetailModal"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/60" @click="logsDetailModal = false" />
          <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col">
            <!-- Header -->
            <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-lg bg-rose-100 dark:bg-rose-500/20">
                  <DocumentTextIcon class="h-5 w-5 text-rose-500" />
                </div>
                <div>
                  <h3 class="text-lg font-semibold text-primary">Log Analysis Details</h3>
                  <p class="text-sm text-muted">Errors and warnings from the last hour</p>
                </div>
              </div>
              <button
                @click="logsDetailModal = false"
                class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                <XMarkIcon class="h-5 w-5 text-gray-500" />
              </button>
            </div>

            <!-- Content -->
            <div class="flex-1 overflow-y-auto p-6 space-y-6">
              <!-- Per-Container Breakdown -->
              <div v-if="Object.keys(healthData.checks?.logs?.details?.by_container || {}).length">
                <h4 class="text-sm font-semibold text-primary mb-3">Errors by Container</h4>
                <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <button
                    v-for="(stats, containerName) in healthData.checks?.logs?.details?.by_container"
                    :key="containerName"
                    @click="navigateToContainer(containerName)"
                    :class="[
                      'p-3 rounded-lg text-left transition-all hover:scale-[1.02]',
                      stats.error_count > 0
                        ? 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 hover:bg-red-100 dark:hover:bg-red-900/30'
                        : 'bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 hover:bg-amber-100 dark:hover:bg-amber-900/30'
                    ]"
                  >
                    <div class="flex items-center justify-between">
                      <span class="font-medium text-primary text-sm">{{ containerName }}</span>
                      <LinkIcon class="h-3 w-3 text-muted" />
                    </div>
                    <div class="mt-1 flex items-center gap-2 text-xs">
                      <span :class="stats.error_count > 0 ? 'text-red-600 dark:text-red-400' : 'text-gray-500'">
                        {{ stats.error_count }} errors
                      </span>
                      <span class="text-amber-600 dark:text-amber-400">
                        {{ stats.warning_count }} warnings
                      </span>
                    </div>
                  </button>
                </div>
                <p class="text-xs text-muted mt-2">Click a container to view its logs</p>
              </div>

              <!-- Recent Errors List -->
              <div v-if="healthData.checks?.logs?.details?.recent_errors?.length">
                <h4 class="text-sm font-semibold text-primary mb-3">Recent Errors</h4>
                <div class="space-y-2 max-h-80 overflow-y-auto">
                  <div
                    v-for="(err, i) in healthData.checks?.logs?.details?.recent_errors"
                    :key="i"
                    class="p-3 rounded-lg bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700"
                  >
                    <div class="flex items-center gap-2 mb-1">
                      <button
                        @click="navigateToContainer(err.container)"
                        class="px-2 py-0.5 text-xs font-medium rounded bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-400 hover:bg-rose-200 dark:hover:bg-rose-500/30 transition-colors"
                      >
                        {{ err.container }}
                      </button>
                      <span class="text-xs text-muted">{{ formatLogTimestamp(err.timestamp) }}</span>
                    </div>
                    <p class="text-sm text-gray-700 dark:text-gray-300 font-mono break-all">
                      {{ err.message }}
                    </p>
                  </div>
                </div>
              </div>

              <!-- No errors state -->
              <div v-if="!healthData.checks?.logs?.details?.recent_errors?.length && !Object.keys(healthData.checks?.logs?.details?.by_container || {}).length" class="text-center py-8">
                <CheckCircleIcon class="h-12 w-12 text-emerald-500 mx-auto mb-3" />
                <p class="text-primary font-medium">No errors or warnings in the last hour</p>
                <p class="text-sm text-muted mt-1">All containers are running smoothly</p>
              </div>
            </div>

            <!-- Footer -->
            <div class="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
              <button
                @click="logsDetailModal = false"
                class="btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style>
/* Terminal xterm styling */
.xterm {
  padding: 12px;
  height: 100% !important;
}
.xterm-viewport {
  overflow-y: auto !important;
}
</style>
