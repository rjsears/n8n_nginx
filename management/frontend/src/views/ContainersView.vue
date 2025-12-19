<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useContainerStore } from '@/stores/containers'
import { useNotificationStore } from '@/stores/notifications'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import ContainerStackLoader from '@/components/common/ContainerStackLoader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { useRouter } from 'vue-router'
import {
  ServerIcon,
  PlayIcon,
  StopIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  CommandLineIcon,
  CpuChipIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  SignalIcon,
  ArrowDownTrayIcon,
  ArrowUpTrayIcon,
  Square3Stack3DIcon,
  HeartIcon,
  BellIcon,
  BellSlashIcon,
  TrashIcon,
} from '@heroicons/vue/24/outline'

const router = useRouter()
const themeStore = useThemeStore()
const containerStore = useContainerStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const containerStats = ref({})
const actionDialog = ref({ open: false, container: null, action: '', loading: false })
const logsDialog = ref({ open: false, container: null, logs: '', loading: false })
const notifyDialog = ref({
  open: false,
  container: null,
  loading: false,
  saving: false,
  config: {
    enabled: true,
    notify_on_stop: true,
    notify_on_unhealthy: true,
    notify_on_restart: true,
    notify_on_high_cpu: false,
    cpu_threshold: 80,
    notify_on_high_memory: false,
    memory_threshold: 80,
  }
})
const containerConfigs = ref({})  // Cache of container notification configs
const hasContainerEventTargets = ref(false)  // Track if any container events have targets configured

// Stopped containers popup
const stoppedContainersDialog = ref({ open: false })
const removeConfirmDialog = ref({ open: false, container: null, loading: false })

let statsInterval = null

// Funny loading messages for containers
const allContainerMessages = [
  'Waking up the containers...',
  'Asking Docker who\'s home...',
  'Counting all the little boxes...',
  'Unpacking the shipping containers...',
  'Checking if anyone escaped...',
  'Herding the container cats...',
  'Making sure no one\'s sleeping on the job...',
  'Peeking inside each container...',
  'Taking attendance...',
  'Shaking the containers to see what rattles...',
  'Knocking on container doors...',
  'Interrogating the Docker daemon...',
  'Playing hide and seek with containers...',
  'Convincing containers to share their secrets...',
  'Measuring how much RAM each container stole...',
  'Checking who ate all the CPU...',
  'Translating from container-speak...',
  'Sorting containers by how well they behave...',
  'Asking nicely for container stats...',
  'Bribbing containers with more memory...',
  'Checking if nginx is still angry...',
  'Verifying PostgreSQL had its morning coffee...',
  'Making sure n8n workflows aren\'t plotting...',
  'Inspecting the container cargo...',
]
const containerLoadingMessages = ref([])
const containerLoadingMessageIndex = ref(0)
let containerLoadingInterval = null

function shuffleContainerMessages() {
  const shuffled = [...allContainerMessages].sort(() => Math.random() - 0.5)
  containerLoadingMessages.value = shuffled.slice(0, 12)
}

// Filters
const filterStatus = ref('all')
const containerTypeFilter = ref('all')  // 'all', 'n8n', 'non-n8n'

// Merge containers with their stats
const containersWithStats = computed(() => {
  return containerStore.containers.map(container => {
    const stats = containerStats.value[container.name] || {}
    return {
      ...container,
      cpu_percent: stats.cpu_percent || 0,
      memory_usage: stats.memory_usage || 0,
      memory_limit: stats.memory_limit || 0,
      memory_percent: stats.memory_percent || 0,
      memory_mb: stats.memory_usage ? Math.round(stats.memory_usage / (1024 * 1024)) : 0,
      network_rx: stats.network_rx || 0,
      network_tx: stats.network_tx || 0,
    }
  })
})

// Check if there are any non-project containers
const hasNonProjectContainers = computed(() => {
  return containersWithStats.value.some(c => !c.is_project)
})

// Filter containers by type first, then by status
const filteredContainers = computed(() => {
  let filtered = containersWithStats.value

  // Filter by container type
  if (containerTypeFilter.value === 'n8n') {
    filtered = filtered.filter(c => c.is_project)
  } else if (containerTypeFilter.value === 'non-n8n') {
    filtered = filtered.filter(c => !c.is_project)
  }

  // Then filter by status
  if (filterStatus.value === 'running') {
    filtered = filtered.filter(c => c.status === 'running')
  } else if (filterStatus.value === 'stopped') {
    // "Stopped" means any non-running status (exited, created, dead, paused, etc.)
    filtered = filtered.filter(c => c.status !== 'running')
  }

  return filtered
})

// Stats - always show ALL containers (no filtering)
const stats = computed(() => {
  const all = containersWithStats.value
  return {
    total: all.length,
    running: all.filter(c => c.status === 'running').length,
    stopped: all.filter(c => c.status !== 'running').length,
    unhealthy: all.filter(c => c.health === 'unhealthy').length,
  }
})

// Get list of stopped containers
const stoppedContainers = computed(() => {
  return containersWithStats.value.filter(c => c.status !== 'running')
})

// Open stopped containers popup
function openStoppedContainersDialog() {
  if (stats.value.stopped > 0) {
    stoppedContainersDialog.value.open = true
  }
}

// Prompt to remove a container
function promptRemoveContainer(container) {
  removeConfirmDialog.value = { open: true, container, loading: false }
}

// Confirm and remove container
async function confirmRemoveContainer() {
  const container = removeConfirmDialog.value.container
  if (!container) return

  removeConfirmDialog.value.loading = true
  try {
    await containerStore.removeContainer(container.name)
    notificationStore.success(`Container ${container.name} removed successfully`)
    removeConfirmDialog.value.open = false
    // If no more stopped containers, close the stopped dialog too
    if (stoppedContainers.value.length <= 1) {
      stoppedContainersDialog.value.open = false
    }
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || `Failed to remove ${container.name}`)
  } finally {
    removeConfirmDialog.value.loading = false
  }
}

function getStatusIcon(container) {
  if (container.health === 'unhealthy') return ExclamationTriangleIcon
  if (container.status === 'running') return CheckCircleIcon
  if (container.status === 'exited' || container.status === 'stopped') return XCircleIcon
  return ServerIcon
}

function getStatusColor(container) {
  if (container.health === 'unhealthy') return 'red'
  if (container.status === 'running') return 'emerald'
  if (container.status === 'exited' || container.status === 'stopped') return 'gray'
  return 'blue'
}

function getMemoryColor(memoryMb) {
  if (memoryMb > 500) return 'text-red-500'
  if (memoryMb > 200) return 'text-amber-500'
  return 'text-emerald-500'
}

function getCpuColor(cpuPercent) {
  if (cpuPercent > 80) return 'text-red-500'
  if (cpuPercent > 50) return 'text-amber-500'
  return 'text-emerald-500'
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function getHealthBadgeClass(health) {
  switch (health) {
    case 'healthy':
      return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400'
    case 'unhealthy':
      return 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400'
    case 'starting':
      return 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400'
    default:
      return 'bg-gray-100 text-gray-600 dark:bg-gray-500/20 dark:text-gray-400'
  }
}

async function performAction(container, action) {
  actionDialog.value = { open: true, container, action, loading: false }
}

async function confirmAction() {
  const { container, action } = actionDialog.value
  if (!container || !action) return

  actionDialog.value.loading = true
  try {
    switch (action) {
      case 'start':
        await containerStore.startContainer(container.name)
        notificationStore.success(`Container ${container.name} started`)
        break
      case 'stop':
        await containerStore.stopContainer(container.name)
        notificationStore.success(`Container ${container.name} stopped`)
        break
      case 'restart':
        await containerStore.restartContainer(container.name)
        notificationStore.success(`Container ${container.name} restarted`)
        break
    }
    actionDialog.value.open = false
    // Refresh data
    await loadData()
  } catch (error) {
    notificationStore.error(`Failed to ${action} container`)
  } finally {
    actionDialog.value.loading = false
  }
}

async function viewLogs(container) {
  logsDialog.value = { open: true, container, logs: '', loading: true }
  try {
    const logs = await containerStore.getContainerLogs(container.name)
    logsDialog.value.logs = logs
  } catch (error) {
    notificationStore.error('Failed to fetch logs')
  } finally {
    logsDialog.value.loading = false
  }
}

function openTerminal(container) {
  router.push({
    name: 'system',
    query: { tab: 'terminal', target: container.id, autoconnect: 'true' }
  })
}

async function openNotifySettings(container) {
  notifyDialog.value = {
    open: true,
    container,
    loading: true,
    saving: false,
    config: {
      enabled: true,
      notify_on_stop: true,
      notify_on_unhealthy: true,
      notify_on_restart: true,
      notify_on_high_cpu: false,
      cpu_threshold: 80,
      notify_on_high_memory: false,
      memory_threshold: 80,
    }
  }

  try {
    // Try to load existing config for this container
    const response = await api.get(`/system-notifications/container-configs/${container.name}`)
    if (response.data) {
      notifyDialog.value.config = {
        enabled: response.data.enabled ?? true,
        notify_on_stop: response.data.notify_on_stop ?? true,
        notify_on_unhealthy: response.data.notify_on_unhealthy ?? true,
        notify_on_restart: response.data.notify_on_restart ?? true,
        notify_on_high_cpu: response.data.notify_on_high_cpu ?? false,
        cpu_threshold: response.data.cpu_threshold ?? 80,
        notify_on_high_memory: response.data.notify_on_high_memory ?? false,
        memory_threshold: response.data.memory_threshold ?? 80,
      }
    }
  } catch (error) {
    // No existing config, use defaults
    console.log('No existing notification config for container:', container.name)
  } finally {
    notifyDialog.value.loading = false
  }
}

async function saveNotifySettings() {
  if (!notifyDialog.value.container) return

  notifyDialog.value.saving = true
  try {
    await api.put(`/system-notifications/container-configs/${notifyDialog.value.container.name}`, {
      container_name: notifyDialog.value.container.name,
      ...notifyDialog.value.config
    })
    notificationStore.success(`Notification settings saved for ${notifyDialog.value.container.name}`)
    // Cache the config
    containerConfigs.value[notifyDialog.value.container.name] = { ...notifyDialog.value.config }
    notifyDialog.value.open = false
  } catch (error) {
    notificationStore.error('Failed to save notification settings')
  } finally {
    notifyDialog.value.saving = false
  }
}

function hasNotificationConfig(containerName) {
  return containerConfigs.value[containerName]?.enabled ?? false
}

async function loadContainerConfigs() {
  try {
    const response = await api.get('/system-notifications/container-configs')
    if (response.data) {
      for (const config of response.data) {
        containerConfigs.value[config.container_name] = config
      }
    }
  } catch (error) {
    console.error('Failed to load container notification configs:', error)
  }
}

async function checkContainerEventTargets() {
  try {
    // Check if any container events have notification targets configured
    const response = await api.get('/system-notifications/events')
    const containerEvents = response.data.filter(e => e.category === 'container')
    hasContainerEventTargets.value = containerEvents.some(e => e.targets && e.targets.length > 0)
  } catch (error) {
    console.error('Failed to check container event targets:', error)
    hasContainerEventTargets.value = false
  }
}

async function fetchStats() {
  try {
    const response = await api.get('/containers/stats')
    const statsMap = {}
    for (const stat of response.data) {
      statsMap[stat.name] = stat
    }
    containerStats.value = statsMap
  } catch (error) {
    console.error('Failed to fetch container stats:', error)
  }
}

async function loadData() {
  loading.value = true
  containerLoadingMessageIndex.value = 0
  shuffleContainerMessages()

  // Start rotating messages every 3.5 seconds
  containerLoadingInterval = setInterval(() => {
    containerLoadingMessageIndex.value = (containerLoadingMessageIndex.value + 1) % containerLoadingMessages.value.length
  }, 3500)

  try {
    await Promise.all([
      containerStore.fetchContainers(),
      fetchStats(),
      loadContainerConfigs(),
      checkContainerEventTargets(),
    ])
  } catch (error) {
    notificationStore.error('Failed to load containers')
  } finally {
    // Stop rotating messages
    if (containerLoadingInterval) {
      clearInterval(containerLoadingInterval)
      containerLoadingInterval = null
    }
    loading.value = false
  }
}

onMounted(() => {
  loadData()
  // Refresh stats every 30 seconds
  statsInterval = setInterval(fetchStats, 30000)
})

onUnmounted(() => {
  if (statsInterval) {
    clearInterval(statsInterval)
  }
  if (containerLoadingInterval) {
    clearInterval(containerLoadingInterval)
    containerLoadingInterval = null
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
          Containers
        </h1>
        <p class="text-secondary mt-1">Manage Docker containers</p>
      </div>
      <button
        @click="loadData"
        class="btn-secondary flex items-center gap-2"
      >
        <ArrowPathIcon class="h-4 w-4" />
        Refresh
      </button>
    </div>

    <ContainerStackLoader v-if="loading" :text="containerLoadingMessages[containerLoadingMessageIndex]" class="py-16 mt-8" />

    <template v-else>
      <!-- Container Type Filter Buttons (only shown if non-n8n containers exist) -->
      <div v-if="hasNonProjectContainers" class="flex items-center gap-3">
        <button
          @click="containerTypeFilter = 'n8n'"
          :class="[
            'px-4 py-2 rounded-lg font-medium transition-all duration-200 flex items-center gap-2',
            containerTypeFilter === 'n8n'
              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/25'
              : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200 dark:bg-indigo-500/20 dark:text-indigo-400 dark:hover:bg-indigo-500/30'
          ]"
        >
          <Square3Stack3DIcon class="h-4 w-4" />
          N8N Containers
        </button>
        <button
          @click="containerTypeFilter = 'non-n8n'"
          :class="[
            'px-4 py-2 rounded-lg font-medium transition-all duration-200 flex items-center gap-2',
            containerTypeFilter === 'non-n8n'
              ? 'bg-amber-600 text-white shadow-lg shadow-amber-500/25'
              : 'bg-amber-100 text-amber-700 hover:bg-amber-200 dark:bg-amber-500/20 dark:text-amber-400 dark:hover:bg-amber-500/30'
          ]"
        >
          <ServerIcon class="h-4 w-4" />
          Non-N8N Containers
        </button>
        <button
          @click="containerTypeFilter = 'all'"
          :class="[
            'px-4 py-2 rounded-lg font-medium transition-all duration-200 flex items-center gap-2',
            containerTypeFilter === 'all'
              ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/25'
              : 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200 dark:bg-emerald-500/20 dark:text-emerald-400 dark:hover:bg-emerald-500/30'
          ]"
        >
          <CheckCircleIcon class="h-4 w-4" />
          All Containers
        </button>
      </div>

      <!-- Stats Grid -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
                <Square3Stack3DIcon class="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Total</p>
                <p class="text-xl font-bold text-primary">{{ stats.total }}</p>
              </div>
            </div>
          </div>
        </Card>

        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-500/20">
                <CheckCircleIcon class="h-5 w-5 text-emerald-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Running</p>
                <p class="text-xl font-bold text-emerald-500">{{ stats.running }}</p>
              </div>
            </div>
          </div>
        </Card>

        <Card :neon="true" :padding="false">
          <button
            @click="openStoppedContainersDialog"
            :disabled="stats.stopped === 0"
            :class="[
              'w-full p-4 text-left transition-colors rounded-lg',
              stats.stopped > 0 ? 'hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer' : 'cursor-default'
            ]"
          >
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-gray-100 dark:bg-gray-500/20">
                <XCircleIcon class="h-5 w-5 text-gray-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Stopped</p>
                <p class="text-xl font-bold text-gray-500">{{ stats.stopped }}</p>
              </div>
              <div v-if="stats.stopped > 0" class="ml-auto text-xs text-gray-400">
                Click to manage
              </div>
            </div>
          </button>
        </Card>

        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-red-100 dark:bg-red-500/20">
                <ExclamationTriangleIcon class="h-5 w-5 text-red-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Unhealthy</p>
                <p class="text-xl font-bold text-red-500">{{ stats.unhealthy }}</p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Filters -->
      <div class="flex items-center gap-4">
        <select v-model="filterStatus" class="select-field">
          <option value="all">All Statuses</option>
          <option value="running">Running Only</option>
          <option value="stopped">Stopped Only</option>
        </select>
        <p class="text-sm text-muted">
          Showing {{ filteredContainers.length }} of {{ containerStore.containers.length }} containers
          <span v-if="containerTypeFilter !== 'all'" class="font-medium">
            ({{ containerTypeFilter === 'n8n' ? 'N8N only' : 'Non-N8N only' }})
          </span>
        </p>
      </div>

      <!-- Container Cards Grid -->
      <EmptyState
        v-if="filteredContainers.length === 0"
        :icon="ServerIcon"
        title="No containers found"
        description="No containers match your current filter."
      />

      <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          v-for="container in filteredContainers"
          :key="container.id"
          :neon="true"
          :padding="false"
        >
          <!-- Card Header -->
          <div class="p-4 border-b border-gray-400 dark:border-black">
            <div class="flex items-start justify-between">
              <div class="flex items-center gap-3">
                <div
                  :class="[
                    'p-3 rounded-lg',
                    `bg-${getStatusColor(container)}-100 dark:bg-${getStatusColor(container)}-500/20`
                  ]"
                >
                  <component
                    :is="getStatusIcon(container)"
                    :class="['h-6 w-6', `text-${getStatusColor(container)}-500`]"
                  />
                </div>
                <div>
                  <div class="flex items-center gap-2 flex-wrap">
                    <h3 class="font-semibold text-primary text-lg">{{ container.name }}</h3>
                    <StatusBadge :status="container.status" size="sm" />
                    <span
                      v-if="hasNonProjectContainers"
                      :class="[
                        'px-1.5 py-0.5 text-xs font-medium rounded',
                        container.is_project
                          ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-400'
                          : 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400'
                      ]"
                    >
                      {{ container.is_project ? 'N8N' : 'External' }}
                    </span>
                  </div>
                  <p class="text-sm text-muted mt-0.5 font-mono">{{ container.image }}</p>
                </div>
              </div>

              <!-- Health Badge -->
              <span
                v-if="container.health && container.health !== 'none'"
                :class="['px-2 py-1 text-xs font-medium rounded-full flex items-center gap-1', getHealthBadgeClass(container.health)]"
              >
                <HeartIcon class="h-3 w-3" />
                {{ container.health }}
              </span>
            </div>
          </div>

          <!-- Stats Grid -->
          <div class="p-4 grid grid-cols-2 md:grid-cols-4 gap-4">
            <!-- Uptime -->
            <div class="text-center p-3 rounded-lg bg-surface-hover">
              <ClockIcon class="h-5 w-5 mx-auto text-blue-500 mb-1" />
              <p class="text-xs text-muted">Uptime</p>
              <p class="font-semibold text-primary">{{ container.uptime || '-' }}</p>
            </div>

            <!-- CPU -->
            <div class="text-center p-3 rounded-lg bg-surface-hover">
              <CpuChipIcon class="h-5 w-5 mx-auto text-purple-500 mb-1" />
              <p class="text-xs text-muted">CPU</p>
              <p :class="['font-semibold', getCpuColor(container.cpu_percent)]">
                {{ container.status === 'running' ? container.cpu_percent.toFixed(1) + '%' : '-' }}
              </p>
            </div>

            <!-- Memory -->
            <div class="text-center p-3 rounded-lg bg-surface-hover">
              <ServerIcon class="h-5 w-5 mx-auto text-amber-500 mb-1" />
              <p class="text-xs text-muted">Memory</p>
              <p :class="['font-semibold', getMemoryColor(container.memory_mb)]">
                {{ container.status === 'running' ? container.memory_mb + ' MB' : '-' }}
              </p>
            </div>

            <!-- Network -->
            <div class="text-center p-3 rounded-lg bg-surface-hover">
              <SignalIcon class="h-5 w-5 mx-auto text-cyan-500 mb-1" />
              <p class="text-xs text-muted">Network</p>
              <p class="font-semibold text-primary text-xs">
                <span v-if="container.status === 'running'" class="flex items-center justify-center gap-1">
                  <ArrowDownTrayIcon class="h-3 w-3 text-emerald-500" />
                  {{ formatBytes(container.network_rx) }}
                </span>
                <span v-else>-</span>
              </p>
            </div>
          </div>

          <!-- Memory Bar (only for running containers) -->
          <div v-if="container.status === 'running' && container.memory_limit > 0" class="px-4 pb-2">
            <div class="flex items-center justify-between text-xs text-muted mb-1">
              <span>Memory Usage</span>
              <span>{{ container.memory_percent.toFixed(1) }}%</span>
            </div>
            <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                :class="[
                  'h-full rounded-full transition-all duration-500',
                  container.memory_percent > 80 ? 'bg-red-500' :
                  container.memory_percent > 60 ? 'bg-amber-500' : 'bg-emerald-500'
                ]"
                :style="{ width: `${Math.min(container.memory_percent, 100)}%` }"
              ></div>
            </div>
          </div>

          <!-- Actions Footer - Evenly distributed buttons -->
          <div class="p-4 border-t border-gray-400 dark:border-black">
            <div class="flex items-center justify-center gap-3 flex-wrap">
              <!-- Start Button (when stopped) -->
              <button
                v-if="container.status !== 'running'"
                @click="performAction(container, 'start')"
                class="flex-1 min-w-[100px] max-w-[140px] btn-secondary flex items-center justify-center gap-2 text-sm py-2 px-4 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30"
                title="Start Container"
              >
                <PlayIcon class="h-4 w-4" />
                Start
              </button>

              <!-- Stop Button (when running) -->
              <button
                v-if="container.status === 'running'"
                @click="performAction(container, 'stop')"
                class="flex-1 min-w-[100px] max-w-[140px] btn-secondary flex items-center justify-center gap-2 text-sm py-2 px-4 text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10 border border-red-200 dark:border-red-500/30"
                title="Stop Container"
              >
                <StopIcon class="h-4 w-4" />
                Stop
              </button>

              <!-- Restart Button -->
              <button
                @click="performAction(container, 'restart')"
                class="flex-1 min-w-[100px] max-w-[140px] btn-secondary flex items-center justify-center gap-2 text-sm py-2 px-4 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30"
                title="Restart Container"
              >
                <ArrowPathIcon class="h-4 w-4" />
                Restart
              </button>

              <!-- Notification Settings Button -->
              <button
                @click="openNotifySettings(container)"
                :class="[
                  'flex-1 min-w-[100px] max-w-[140px] btn-secondary flex items-center justify-center gap-2 text-sm py-2 px-4 border',
                  hasNotificationConfig(container.name)
                    ? 'text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-500/10 border-amber-200 dark:border-amber-500/30'
                    : 'text-gray-500 hover:text-gray-700 border-gray-400 dark:border-gray-600'
                ]"
                :title="hasNotificationConfig(container.name) ? 'Notifications enabled - Click to configure' : 'Configure notifications'"
              >
                <BellIcon v-if="hasNotificationConfig(container.name)" class="h-4 w-4" />
                <BellSlashIcon v-else class="h-4 w-4" />
                Alerts
              </button>

              <!-- Logs Button -->
              <button
                @click="viewLogs(container)"
                class="flex-1 min-w-[100px] max-w-[140px] btn-secondary flex items-center justify-center gap-2 text-sm py-2 px-4 text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-500/10 border border-purple-200 dark:border-purple-500/30"
                title="View Logs"
              >
                <DocumentTextIcon class="h-4 w-4" />
                Logs
              </button>

              <!-- Terminal Button (only when running) -->
              <button
                v-if="container.status === 'running'"
                @click="openTerminal(container)"
                class="flex-1 min-w-[100px] max-w-[140px] btn-secondary flex items-center justify-center gap-2 text-sm py-2 px-4 text-cyan-600 hover:bg-cyan-50 dark:hover:bg-cyan-500/10 border border-cyan-200 dark:border-cyan-500/30"
                title="Open Terminal"
              >
                <CommandLineIcon class="h-4 w-4" />
                Terminal
              </button>
            </div>
          </div>
        </Card>
      </div>
    </template>

    <!-- Action Confirmation Dialog -->
    <ConfirmDialog
      :open="actionDialog.open"
      :title="`${actionDialog.action?.charAt(0).toUpperCase()}${actionDialog.action?.slice(1)} Container`"
      :message="`Are you sure you want to ${actionDialog.action} ${actionDialog.container?.name}?`"
      :confirm-text="actionDialog.action?.charAt(0).toUpperCase() + actionDialog.action?.slice(1)"
      :danger="actionDialog.action === 'stop'"
      :loading="actionDialog.loading"
      @confirm="confirmAction"
      @cancel="actionDialog.open = false"
    />

    <!-- Logs Dialog -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="logsDialog.open"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/50" @click="logsDialog.open = false" />
          <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] flex flex-col border border-gray-400 dark:border-gray-700">
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700 bg-white dark:bg-gray-800">
              <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
                Logs: {{ logsDialog.container?.name }}
              </h3>
              <button
                @click="logsDialog.open = false"
                class="p-1 rounded-lg text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                ×
              </button>
            </div>
            <div class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-800">
              <LoadingSpinner v-if="logsDialog.loading" text="Loading logs..." />
              <pre
                v-else
                class="text-xs font-mono text-gray-200 whitespace-pre-wrap bg-gray-900 dark:bg-black p-4 rounded-lg overflow-auto"
              >{{ logsDialog.logs || 'No logs available' }}</pre>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Notification Settings Dialog -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="notifyDialog.open"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/50" @click="notifyDialog.open = false" />
          <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full max-h-[80vh] flex flex-col border border-gray-400 dark:border-gray-700">
            <!-- Header -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-lg bg-amber-100 dark:bg-amber-500/20">
                  <BellIcon class="h-5 w-5 text-amber-500" />
                </div>
                <div>
                  <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
                    Notification Settings
                  </h3>
                  <p class="text-sm text-gray-500 dark:text-gray-400">
                    {{ notifyDialog.container?.name }}
                  </p>
                </div>
              </div>
              <button
                @click="notifyDialog.open = false"
                class="p-1 rounded-lg text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                ×
              </button>
            </div>

            <!-- Content -->
            <div class="flex-1 overflow-auto p-6">
              <LoadingSpinner v-if="notifyDialog.loading" text="Loading settings..." />

              <div v-else class="space-y-6">
                <!-- Warning: No targets configured -->
                <div v-if="!hasContainerEventTargets" class="p-4 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30">
                  <div class="flex gap-3">
                    <ExclamationTriangleIcon class="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p class="font-medium text-amber-700 dark:text-amber-400">No notification targets configured</p>
                      <p class="text-sm text-amber-600 dark:text-amber-500 mt-1">
                        Container events won't be sent until you configure notification targets.
                      </p>
                      <router-link
                        to="/settings?section=notifications&tab=events"
                        class="inline-flex items-center gap-1 text-sm font-medium text-amber-700 dark:text-amber-400 hover:underline mt-2"
                        @click="notifyDialog.open = false"
                      >
                        Configure in Settings → Notifications
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                        </svg>
                      </router-link>
                    </div>
                  </div>
                </div>

                <!-- Enable/Disable Toggle -->
                <div class="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-700/50">
                  <div>
                    <p class="font-medium text-gray-900 dark:text-white">Enable Notifications</p>
                    <p class="text-sm text-gray-500 dark:text-gray-400">Receive alerts for this container</p>
                  </div>
                  <label :class="['relative inline-flex items-center', !hasContainerEventTargets ? 'cursor-not-allowed opacity-50' : 'cursor-pointer']">
                    <input
                      type="checkbox"
                      v-model="notifyDialog.config.enabled"
                      :disabled="!hasContainerEventTargets && !notifyDialog.config.enabled"
                      class="sr-only peer"
                      @change="!hasContainerEventTargets && notifyDialog.config.enabled && notificationStore.warning('Configure notification targets first in Settings → Notifications')"
                    >
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-600 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-400 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-500 peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                <!-- Status Events -->
                <div :class="['space-y-3', !notifyDialog.config.enabled && 'opacity-50 pointer-events-none']">
                  <h4 class="font-medium text-gray-900 dark:text-white text-sm">Status Events</h4>

                  <label class="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer">
                    <input type="checkbox" v-model="notifyDialog.config.notify_on_stop" class="form-checkbox h-4 w-4 text-blue-600 rounded">
                    <div>
                      <p class="text-sm font-medium text-gray-900 dark:text-white">Container Stopped</p>
                      <p class="text-xs text-gray-500 dark:text-gray-400">Alert when container stops unexpectedly</p>
                    </div>
                  </label>

                  <label class="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer">
                    <input type="checkbox" v-model="notifyDialog.config.notify_on_unhealthy" class="form-checkbox h-4 w-4 text-blue-600 rounded">
                    <div>
                      <p class="text-sm font-medium text-gray-900 dark:text-white">Health Check Failed</p>
                      <p class="text-xs text-gray-500 dark:text-gray-400">Alert when container becomes unhealthy</p>
                    </div>
                  </label>

                  <label class="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer">
                    <input type="checkbox" v-model="notifyDialog.config.notify_on_restart" class="form-checkbox h-4 w-4 text-blue-600 rounded">
                    <div>
                      <p class="text-sm font-medium text-gray-900 dark:text-white">Container Restarted</p>
                      <p class="text-xs text-gray-500 dark:text-gray-400">Alert when container restarts automatically</p>
                    </div>
                  </label>
                </div>

                <!-- Resource Thresholds -->
                <div :class="['space-y-3', !notifyDialog.config.enabled && 'opacity-50 pointer-events-none']">
                  <h4 class="font-medium text-gray-900 dark:text-white text-sm">Resource Thresholds</h4>

                  <div class="p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <label class="flex items-center gap-3 cursor-pointer">
                      <input type="checkbox" v-model="notifyDialog.config.notify_on_high_cpu" class="form-checkbox h-4 w-4 text-blue-600 rounded">
                      <div class="flex-1">
                        <p class="text-sm font-medium text-gray-900 dark:text-white">High CPU Usage</p>
                        <p class="text-xs text-gray-500 dark:text-gray-400">Alert when CPU exceeds threshold</p>
                      </div>
                    </label>
                    <div v-if="notifyDialog.config.notify_on_high_cpu" class="mt-3 ml-7">
                      <div class="flex items-center gap-2">
                        <input
                          type="range"
                          v-model.number="notifyDialog.config.cpu_threshold"
                          min="50"
                          max="100"
                          step="5"
                          class="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
                        >
                        <span class="text-sm font-medium text-gray-900 dark:text-white w-12 text-right">
                          {{ notifyDialog.config.cpu_threshold }}%
                        </span>
                      </div>
                    </div>
                  </div>

                  <div class="p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <label class="flex items-center gap-3 cursor-pointer">
                      <input type="checkbox" v-model="notifyDialog.config.notify_on_high_memory" class="form-checkbox h-4 w-4 text-blue-600 rounded">
                      <div class="flex-1">
                        <p class="text-sm font-medium text-gray-900 dark:text-white">High Memory Usage</p>
                        <p class="text-xs text-gray-500 dark:text-gray-400">Alert when memory exceeds threshold</p>
                      </div>
                    </label>
                    <div v-if="notifyDialog.config.notify_on_high_memory" class="mt-3 ml-7">
                      <div class="flex items-center gap-2">
                        <input
                          type="range"
                          v-model.number="notifyDialog.config.memory_threshold"
                          min="50"
                          max="100"
                          step="5"
                          class="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
                        >
                        <span class="text-sm font-medium text-gray-900 dark:text-white w-12 text-right">
                          {{ notifyDialog.config.memory_threshold }}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Footer -->
            <div class="px-6 py-4 border-t border-gray-400 dark:border-gray-700 space-y-4">
              <!-- Info about targets -->
              <div v-if="hasContainerEventTargets" class="text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
                <p class="font-medium mb-1">ℹ️ These settings control which events to monitor for this container.</p>
                <p>Notification targets (where alerts are sent) are configured in Settings → Notifications → Container Events.</p>
              </div>

              <div class="flex items-center justify-end gap-3">
                <button
                  @click="notifyDialog.open = false"
                  class="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  @click="saveNotifySettings"
                  :disabled="notifyDialog.saving"
                  class="btn-primary flex items-center gap-2"
                >
                  <span v-if="notifyDialog.saving">Saving...</span>
                  <span v-else>Save Settings</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Stopped Containers Dialog -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="stoppedContainersDialog.open"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/50" @click="stoppedContainersDialog.open = false" />
          <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full max-h-[80vh] flex flex-col border border-gray-400 dark:border-gray-700">
            <!-- Header -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700 bg-white dark:bg-gray-800 rounded-t-lg">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700">
                  <XCircleIcon class="h-5 w-5 text-gray-500" />
                </div>
                <div>
                  <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
                    Stopped Containers
                  </h3>
                  <p class="text-sm text-gray-500 dark:text-gray-400">
                    {{ stoppedContainers.length }} container{{ stoppedContainers.length !== 1 ? 's' : '' }} stopped
                  </p>
                </div>
              </div>
              <button
                @click="stoppedContainersDialog.open = false"
                class="p-1 rounded-lg text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                ×
              </button>
            </div>

            <!-- Content -->
            <div class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-800">
              <div v-if="stoppedContainers.length === 0" class="text-center py-8 text-gray-500">
                No stopped containers
              </div>
              <div v-else class="space-y-3">
                <div
                  v-for="container in stoppedContainers"
                  :key="container.id"
                  class="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600"
                >
                  <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg bg-gray-200 dark:bg-gray-600">
                      <ServerIcon class="h-5 w-5 text-gray-500 dark:text-gray-400" />
                    </div>
                    <div>
                      <p class="font-medium text-gray-900 dark:text-white">{{ container.name }}</p>
                      <p class="text-xs text-gray-500 dark:text-gray-400 font-mono">{{ container.image }}</p>
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <button
                      @click="performAction(container, 'start')"
                      class="p-2 rounded-lg text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 transition-colors"
                      title="Start container"
                    >
                      <PlayIcon class="h-5 w-5" />
                    </button>
                    <button
                      @click="promptRemoveContainer(container)"
                      class="p-2 rounded-lg text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
                      title="Remove container"
                    >
                      <TrashIcon class="h-5 w-5" />
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Footer -->
            <div class="px-6 py-4 border-t border-gray-400 dark:border-gray-700 bg-white dark:bg-gray-800 rounded-b-lg">
              <button
                @click="stoppedContainersDialog.open = false"
                class="w-full btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Remove Container Confirmation Dialog (Skull and Crossbones) -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="removeConfirmDialog.open"
          class="fixed inset-0 z-[110] flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/60" @click="removeConfirmDialog.open = false" />
          <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-md w-full border-2 border-red-500 dark:border-red-600">
            <!-- Header with skull -->
            <div class="px-6 py-5 bg-red-50 dark:bg-red-900/30 rounded-t-lg border-b border-red-200 dark:border-red-800">
              <div class="flex items-center justify-center mb-3">
                <div class="p-4 rounded-full bg-red-100 dark:bg-red-900/50">
                  <!-- Skull and Crossbones SVG -->
                  <svg class="h-12 w-12 text-red-600 dark:text-red-400" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7zm-2 15v-1h4v1h-4zm5.55-5.46l-.55.39V14h-6v-2.07l-.55-.39C7.51 10.85 7 9.47 7 8c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.47-.51 2.85-1.45 3.54zM9 9c.55 0 1-.45 1-1s-.45-1-1-1-1 .45-1 1 .45 1 1 1zm6 0c.55 0 1-.45 1-1s-.45-1-1-1-1 .45-1 1 .45 1 1 1zm-7 9h8l-1 3h-6l-1-3z"/>
                  </svg>
                </div>
              </div>
              <h3 class="text-xl font-bold text-red-700 dark:text-red-400 text-center">
                Danger Zone
              </h3>
              <p class="text-sm text-red-600 dark:text-red-500 text-center mt-1">
                This action cannot be undone!
              </p>
            </div>

            <!-- Content -->
            <div class="px-6 py-5 bg-white dark:bg-gray-800">
              <p class="text-gray-700 dark:text-gray-300 text-center">
                Are you sure you want to permanently remove the container
                <span class="font-bold text-gray-900 dark:text-white">{{ removeConfirmDialog.container?.name }}</span>?
              </p>
              <p class="text-sm text-gray-500 dark:text-gray-400 text-center mt-2">
                All container data will be lost forever.
              </p>
            </div>

            <!-- Actions -->
            <div class="px-6 py-4 bg-gray-50 dark:bg-gray-900/50 rounded-b-lg flex gap-3">
              <button
                @click="removeConfirmDialog.open = false"
                :disabled="removeConfirmDialog.loading"
                class="flex-1 btn-secondary"
              >
                Cancel
              </button>
              <button
                @click="confirmRemoveContainer"
                :disabled="removeConfirmDialog.loading"
                class="flex-1 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium transition-colors flex items-center justify-center gap-2"
              >
                <LoadingSpinner v-if="removeConfirmDialog.loading" size="sm" />
                <TrashIcon v-else class="h-4 w-4" />
                {{ removeConfirmDialog.loading ? 'Removing...' : 'Remove Forever' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
