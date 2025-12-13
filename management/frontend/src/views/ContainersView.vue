<script setup>
import { ref, onMounted, computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useContainerStore } from '@/stores/containers'
import { useNotificationStore } from '@/stores/notifications'
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
  CircleStackIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/vue/24/outline'

const router = useRouter()
const themeStore = useThemeStore()
const containerStore = useContainerStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const actionLoading = ref(null)
const logsDialog = ref({ open: false, container: null, logs: '', loading: false })
const actionDialog = ref({ open: false, container: null, action: '', loading: false })

// Filter
const filterStatus = ref('all')

const filteredContainers = computed(() => {
  if (filterStatus.value === 'all') return containerStore.containers
  return containerStore.containers.filter((c) => c.status === filterStatus.value)
})

// Stats
const stats = computed(() => ({
  total: containerStore.containers.length,
  running: containerStore.runningCount,
  stopped: containerStore.stoppedCount,
  unhealthy: containerStore.unhealthyCount,
}))

function getStatusIcon(status) {
  switch (status) {
    case 'running':
      return CheckCircleIcon
    case 'stopped':
      return XCircleIcon
    case 'unhealthy':
      return ExclamationTriangleIcon
    default:
      return ServerIcon
  }
}

function getStatusColor(status) {
  switch (status) {
    case 'running':
      return 'emerald'
    case 'stopped':
      return 'gray'
    case 'unhealthy':
      return 'red'
    default:
      return 'blue'
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
  // Navigate to System page with terminal tab and container pre-selected
  router.push({
    name: 'system',
    query: { tab: 'terminal', target: container.id }
  })
}

async function loadData() {
  loading.value = true
  try {
    await containerStore.fetchContainers()
  } catch (error) {
    notificationStore.error('Failed to load containers')
  } finally {
    loading.value = false
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
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
                <ServerIcon class="h-5 w-5 text-blue-500" />
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
                <p class="text-xl font-bold text-primary">{{ stats.running }}</p>
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
                <p class="text-xl font-bold text-primary">{{ stats.stopped }}</p>
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
                <p class="text-xl font-bold text-primary">{{ stats.unhealthy }}</p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Filters -->
      <Card :neon="true" :padding="false">
        <div class="p-4 flex items-center gap-4">
          <select v-model="filterStatus" class="select-field">
            <option value="all">All Statuses</option>
            <option value="running">Running</option>
            <option value="stopped">Stopped</option>
            <option value="unhealthy">Unhealthy</option>
          </select>
        </div>
      </Card>

      <!-- Container List -->
      <Card title="Docker Containers" :neon="true">
        <EmptyState
          v-if="filteredContainers.length === 0"
          :icon="ServerIcon"
          title="No containers found"
          description="No containers match your current filter."
        />

        <div v-else class="space-y-4">
          <div
            v-for="container in filteredContainers"
            :key="container.id"
            class="p-4 rounded-lg bg-surface-hover border border-[var(--color-border)]"
          >
            <div class="flex items-start justify-between">
              <div class="flex items-start gap-4">
                <div
                  :class="[
                    'p-3 rounded-lg',
                    `bg-${getStatusColor(container.status)}-100 dark:bg-${getStatusColor(container.status)}-500/20`
                  ]"
                >
                  <component
                    :is="getStatusIcon(container.status)"
                    :class="[
                      'h-6 w-6',
                      `text-${getStatusColor(container.status)}-500`
                    ]"
                  />
                </div>
                <div>
                  <div class="flex items-center gap-2">
                    <p class="font-semibold text-primary">{{ container.name }}</p>
                    <StatusBadge :status="container.status" size="sm" />
                  </div>
                  <p class="text-sm text-secondary mt-1">{{ container.image }}</p>

                  <!-- Container Details -->
                  <div class="flex items-center gap-4 mt-3 text-xs text-muted">
                    <div class="flex items-center gap-1">
                      <ClockIcon class="h-3.5 w-3.5" />
                      <span>{{ container.uptime || 'N/A' }}</span>
                    </div>
                    <div v-if="container.cpu_percent !== undefined" class="flex items-center gap-1">
                      <CpuChipIcon class="h-3.5 w-3.5" />
                      <span>{{ container.cpu_percent?.toFixed(1) }}% CPU</span>
                    </div>
                    <div v-if="container.memory_mb !== undefined" class="flex items-center gap-1">
                      <CircleStackIcon class="h-3.5 w-3.5" />
                      <span>{{ container.memory_mb?.toFixed(0) }} MB</span>
                    </div>
                  </div>

                  <!-- Ports -->
                  <div v-if="container.ports?.length" class="mt-2">
                    <p class="text-xs text-muted">
                      Ports:
                      <span
                        v-for="(port, i) in container.ports"
                        :key="i"
                        class="inline-block bg-surface px-1.5 py-0.5 rounded text-secondary ml-1"
                      >
                        {{ port }}
                      </span>
                    </p>
                  </div>
                </div>
              </div>

              <!-- Actions -->
              <div class="flex items-center gap-2">
                <button
                  v-if="container.status !== 'running'"
                  @click="performAction(container, 'start')"
                  class="btn-secondary p-2 text-emerald-500 hover:text-emerald-600"
                  title="Start"
                >
                  <PlayIcon class="h-4 w-4" />
                </button>
                <button
                  v-if="container.status === 'running'"
                  @click="performAction(container, 'stop')"
                  class="btn-secondary p-2 text-red-500 hover:text-red-600"
                  title="Stop"
                >
                  <StopIcon class="h-4 w-4" />
                </button>
                <button
                  @click="performAction(container, 'restart')"
                  class="btn-secondary p-2"
                  title="Restart"
                >
                  <ArrowPathIcon class="h-4 w-4" />
                </button>
                <button
                  @click="viewLogs(container)"
                  class="btn-secondary p-2"
                  title="View Logs"
                >
                  <DocumentTextIcon class="h-4 w-4" />
                </button>
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
          </div>
        </div>
      </Card>
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
                class="text-xs font-mono text-secondary whitespace-pre-wrap bg-gray-900 dark:bg-black p-4 rounded-lg overflow-auto"
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
