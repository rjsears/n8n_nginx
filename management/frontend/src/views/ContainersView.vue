<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useContainerStore } from '@/stores/containers'
import { useNotificationStore } from '@/stores/notifications'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
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
} from '@heroicons/vue/24/outline'

const router = useRouter()
const themeStore = useThemeStore()
const containerStore = useContainerStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const containerStats = ref({})
const actionDialog = ref({ open: false, container: null, action: '', loading: false })
const logsDialog = ref({ open: false, container: null, logs: '', loading: false })

let statsInterval = null

// Filter
const filterStatus = ref('all')

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

const filteredContainers = computed(() => {
  if (filterStatus.value === 'all') return containersWithStats.value
  return containersWithStats.value.filter((c) => c.status === filterStatus.value)
})

// Stats
const stats = computed(() => ({
  total: containerStore.containers.length,
  running: containerStore.runningCount,
  stopped: containerStore.stoppedCount,
  unhealthy: containerStore.unhealthyCount,
}))

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
    query: { tab: 'terminal', target: container.id }
  })
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
  try {
    await Promise.all([
      containerStore.fetchContainers(),
      fetchStats(),
    ])
  } catch (error) {
    notificationStore.error('Failed to load containers')
  } finally {
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

    <LoadingSpinner v-if="loading" size="lg" text="Loading containers..." class="py-12" />

    <template v-else>
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
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-gray-100 dark:bg-gray-500/20">
                <XCircleIcon class="h-5 w-5 text-gray-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Stopped</p>
                <p class="text-xl font-bold text-gray-500">{{ stats.stopped }}</p>
              </div>
            </div>
          </div>
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
          <option value="all">All Containers</option>
          <option value="running">Running Only</option>
          <option value="exited">Stopped Only</option>
        </select>
        <p class="text-sm text-muted">
          Showing {{ filteredContainers.length }} of {{ containerStore.containers.length }} containers
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
          <div class="p-4 border-b border-[var(--color-border)]">
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
                  <div class="flex items-center gap-2">
                    <h3 class="font-semibold text-primary text-lg">{{ container.name }}</h3>
                    <StatusBadge :status="container.status" size="sm" />
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

          <!-- Actions Footer -->
          <div class="p-4 border-t border-[var(--color-border)] flex items-center justify-between">
            <div class="flex items-center gap-2">
              <!-- Start Button (when stopped) -->
              <button
                v-if="container.status !== 'running'"
                @click="performAction(container, 'start')"
                class="btn-secondary flex items-center gap-1.5 text-sm py-1.5 px-3 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-500/10"
                title="Start Container"
              >
                <PlayIcon class="h-4 w-4" />
                Start
              </button>

              <!-- Stop Button (when running) -->
              <button
                v-if="container.status === 'running'"
                @click="performAction(container, 'stop')"
                class="btn-secondary flex items-center gap-1.5 text-sm py-1.5 px-3 text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10"
                title="Stop Container"
              >
                <StopIcon class="h-4 w-4" />
                Stop
              </button>

              <!-- Restart Button -->
              <button
                @click="performAction(container, 'restart')"
                class="btn-secondary flex items-center gap-1.5 text-sm py-1.5 px-3"
                title="Restart Container"
              >
                <ArrowPathIcon class="h-4 w-4" />
                Restart
              </button>
            </div>

            <div class="flex items-center gap-2">
              <!-- Logs Button -->
              <button
                @click="viewLogs(container)"
                class="btn-secondary p-2"
                title="View Logs"
              >
                <DocumentTextIcon class="h-4 w-4" />
              </button>

              <!-- Terminal Button (only when running) -->
              <button
                v-if="container.status === 'running'"
                @click="openTerminal(container)"
                class="btn-secondary p-2 text-blue-500 hover:text-blue-600"
                title="Open Terminal"
              >
                <CommandLineIcon class="h-4 w-4" />
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
          <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] flex flex-col border border-gray-200 dark:border-gray-700">
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
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
