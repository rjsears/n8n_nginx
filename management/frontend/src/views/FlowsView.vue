<script setup>
import { ref, onMounted, computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useNotificationStore } from '@/stores/notifications'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import {
  BoltIcon,
  PlayIcon,
  StopIcon,
  ArrowPathIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  InformationCircleIcon,
  RocketLaunchIcon,
  ArrowDownTrayIcon,
  ArrowTopRightOnSquareIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/vue/24/outline'

const themeStore = useThemeStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const workflows = ref([])
const executions = ref([])
const searchQuery = ref('')
const filterActive = ref('all')
const actionLoading = ref(null)
const n8nUrl = ref('/n8n') // Default, will be loaded from API
const executionsExpanded = ref(false)

// Confirm dialog state
const showActivateConfirm = ref(false)
const pendingToggleWorkflow = ref(null)

// Stats
const stats = computed(() => ({
  total: workflows.value.length,
  active: workflows.value.filter((w) => w.active).length,
  inactive: workflows.value.filter((w) => !w.active).length,
  executions: executions.value.length,
}))

// Filtered workflows
const filteredWorkflows = computed(() => {
  let result = [...workflows.value]

  // Search filter
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter((w) =>
      w.name.toLowerCase().includes(query) ||
      w.id.toString().includes(query)
    )
  }

  // Active filter
  if (filterActive.value === 'active') {
    result = result.filter((w) => w.active)
  } else if (filterActive.value === 'inactive') {
    result = result.filter((w) => !w.active)
  }

  return result
})

// Execution stats by status
const executionStats = computed(() => {
  const stats = {
    success: 0,
    error: 0,
    waiting: 0,
    running: 0,
  }
  executions.value.forEach((e) => {
    if (stats[e.status] !== undefined) {
      stats[e.status]++
    }
  })
  return stats
})

async function loadData() {
  loading.value = true
  try {
    const [workflowsRes, executionsRes, n8nUrlRes] = await Promise.all([
      api.flows.getWorkflows(),
      api.flows.getExecutions(),
      api.flows.getN8nUrl(),
    ])
    workflows.value = workflowsRes.data
    executions.value = executionsRes.data
    n8nUrl.value = n8nUrlRes.data.url
  } catch (error) {
    const detail = error.response?.data?.detail || 'Unknown error'
    notificationStore.error(`Failed to load workflow data: ${detail}`)
    console.error('Flows load error:', error.response?.data || error)
  } finally {
    loading.value = false
  }
}

function toggleWorkflow(workflow) {
  const targetState = !workflow.active
  // If activating, show confirmation dialog first
  if (targetState) {
    pendingToggleWorkflow.value = workflow
    showActivateConfirm.value = true
  } else {
    // Deactivating doesn't need confirmation
    doToggleWorkflow(workflow, targetState)
  }
}

async function doToggleWorkflow(workflow, targetState) {
  actionLoading.value = workflow.id
  try {
    await api.flows.toggleWorkflow(workflow.id, targetState)
    // Reload workflows to verify the actual state changed
    const workflowsRes = await api.flows.getWorkflows()
    workflows.value = workflowsRes.data
    // Find the updated workflow and check if state actually changed
    const updated = workflows.value.find(w => w.id === workflow.id)
    if (updated && updated.active === targetState) {
      notificationStore.success(`Workflow ${targetState ? 'activated' : 'deactivated'}`)
    } else {
      notificationStore.warning(`Workflow toggle requested, but state may not have changed. Check n8n for errors.`)
    }
  } catch (error) {
    const detail = error.response?.data?.detail || error.message || 'Unknown error'
    notificationStore.error(`Failed to toggle workflow: ${detail}`)
    console.error('Toggle workflow error:', error.response?.data || error)
  } finally {
    actionLoading.value = null
  }
}

function confirmActivate() {
  if (pendingToggleWorkflow.value) {
    doToggleWorkflow(pendingToggleWorkflow.value, true)
  }
  showActivateConfirm.value = false
  pendingToggleWorkflow.value = null
}

async function executeWorkflow(workflow) {
  actionLoading.value = workflow.id
  try {
    await api.flows.executeWorkflow(workflow.id)
    notificationStore.success('Workflow execution started')
    // Reload executions
    const executionsRes = await api.flows.getExecutions()
    executions.value = executionsRes.data
  } catch (error) {
    const detail = error.response?.data?.detail || error.message || 'Unknown error'
    notificationStore.error(`Failed to execute workflow: ${detail}`)
    console.error('Execute workflow error:', error.response?.data || error)
  } finally {
    actionLoading.value = null
  }
}

async function downloadWorkflow(workflow) {
  actionLoading.value = workflow.id
  try {
    const response = await api.flows.export(workflow.id)
    const data = response.data

    // Create blob and download
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    // Sanitize filename
    const safeName = workflow.name.replace(/[^a-z0-9]/gi, '_').toLowerCase()
    link.download = `${safeName}_workflow.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    notificationStore.success(`Workflow "${workflow.name}" downloaded`)
  } catch (error) {
    const detail = error.response?.data?.detail || error.message || 'Unknown error'
    notificationStore.error(`Failed to download workflow: ${detail}`)
    console.error('Download workflow error:', error.response?.data || error)
  } finally {
    actionLoading.value = null
  }
}

function openExecutionInN8n(execution) {
  // n8n execution URL format: /workflow/{workflowId}/executions/{executionId}
  const url = `${n8nUrl.value}/workflow/${execution.workflowId}/executions/${execution.id}`
  window.open(url, '_blank', 'noopener,noreferrer')
}

function openWorkflowInN8n(workflow) {
  // n8n workflow URL format: /workflow/{workflowId}
  const url = `${n8nUrl.value}/workflow/${workflow.id}`
  window.open(url, '_blank', 'noopener,noreferrer')
}

function formatDuration(ms) {
  if (!ms) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
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
          Workflows
        </h1>
        <p class="text-secondary mt-1">Monitor and manage n8n workflows</p>
      </div>
      <button
        @click="loadData"
        class="btn-secondary flex items-center gap-2"
      >
        <ArrowPathIcon class="h-4 w-4" />
        Refresh
      </button>
    </div>

    <LoadingSpinner v-if="loading" size="lg" text="Loading workflows..." class="py-12" />

    <template v-else>
      <!-- Stats Grid -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
                <BoltIcon class="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Total Workflows</p>
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
                <p class="text-sm text-secondary">Active</p>
                <p class="text-xl font-bold text-primary">{{ stats.active }}</p>
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
                <p class="text-sm text-secondary">Inactive</p>
                <p class="text-xl font-bold text-primary">{{ stats.inactive }}</p>
              </div>
            </div>
          </div>
        </Card>

        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-500/20">
                <ClockIcon class="h-5 w-5 text-purple-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Executions</p>
                <p class="text-xl font-bold text-primary">{{ stats.executions }}</p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Search and Filters -->
      <Card :neon="true" :padding="false">
        <div class="p-4 flex items-center gap-4">
          <div class="relative flex-1 max-w-md">
            <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search workflows..."
              class="input-field pl-10"
            />
          </div>
          <select v-model="filterActive" class="select-field">
            <option value="all">All Workflows</option>
            <option value="active">Active Only</option>
            <option value="inactive">Inactive Only</option>
          </select>
        </div>
      </Card>

      <!-- Workflows List -->
      <Card title="Workflows" :neon="true">
        <EmptyState
          v-if="filteredWorkflows.length === 0"
          :icon="BoltIcon"
          title="No workflows found"
          description="No workflows match your current search or filter criteria."
        />

        <div v-else class="space-y-3">
          <div
            v-for="workflow in filteredWorkflows"
            :key="workflow.id"
            class="flex items-center justify-between p-4 rounded-lg bg-surface-hover border border-gray-300 dark:border-slate-500"
          >
            <div class="flex items-center gap-4">
              <div
                :class="[
                  'p-3 rounded-lg',
                  workflow.active
                    ? 'bg-emerald-100 dark:bg-emerald-500/20'
                    : 'bg-gray-100 dark:bg-gray-500/20'
                ]"
              >
                <BoltIcon
                  :class="[
                    'h-6 w-6',
                    workflow.active ? 'text-emerald-500' : 'text-gray-500'
                  ]"
                />
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <p class="font-medium text-primary">{{ workflow.name }}</p>
                  <StatusBadge :status="workflow.active ? 'active' : 'inactive'" size="sm" />
                </div>
                <p class="text-sm text-secondary mt-0.5">
                  ID: {{ workflow.id }}
                </p>
                <div class="flex items-center gap-4 mt-1 text-xs text-muted">
                  <span v-if="workflow.triggerCount">
                    {{ workflow.triggerCount }} trigger{{ workflow.triggerCount !== 1 ? 's' : '' }}
                  </span>
                  <span v-if="workflow.nodeCount">
                    {{ workflow.nodeCount }} node{{ workflow.nodeCount !== 1 ? 's' : '' }}
                  </span>
                  <span v-if="workflow.updatedAt">
                    Updated {{ new Date(workflow.updatedAt).toLocaleDateString() }}
                  </span>
                </div>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <button
                @click="openWorkflowInN8n(workflow)"
                class="btn-secondary p-2"
                title="Open in n8n"
              >
                <ArrowTopRightOnSquareIcon class="h-4 w-4" />
              </button>
              <button
                @click="downloadWorkflow(workflow)"
                :disabled="actionLoading === workflow.id"
                class="btn-secondary p-2"
                title="Download Workflow"
              >
                <ArrowDownTrayIcon class="h-4 w-4" />
              </button>
              <button
                @click="executeWorkflow(workflow)"
                :disabled="actionLoading === workflow.id"
                class="btn-secondary p-2"
                title="Execute Now"
              >
                <RocketLaunchIcon class="h-4 w-4" />
              </button>
              <button
                @click="toggleWorkflow(workflow)"
                :disabled="actionLoading === workflow.id"
                :class="[
                  'btn-secondary p-2',
                  workflow.active ? 'text-amber-500 hover:text-amber-600' : 'text-emerald-500 hover:text-emerald-600'
                ]"
                :title="workflow.active ? 'Deactivate' : 'Activate'"
              >
                <StopIcon v-if="workflow.active" class="h-4 w-4" />
                <PlayIcon v-else class="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </Card>

      <!-- Recent Executions (Collapsible) -->
      <Card :neon="true" :padding="false">
        <!-- Collapsible Header -->
        <div
          @click="executionsExpanded = !executionsExpanded"
          class="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
        >
          <div class="flex items-center gap-3">
            <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-500/20">
              <ClockIcon class="h-5 w-5 text-purple-500" />
            </div>
            <div>
              <h3 class="font-semibold text-primary">Recent Executions</h3>
              <p class="text-sm text-muted">Last 20 workflow executions</p>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <div class="flex items-center gap-2">
              <span class="text-xs px-2 py-1 rounded-full bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300">
                {{ executionStats.success }} success
              </span>
              <span v-if="executionStats.error > 0" class="text-xs px-2 py-1 rounded-full bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-300">
                {{ executionStats.error }} error
              </span>
              <span class="text-xs px-2 py-1 rounded-full bg-gray-100 dark:bg-gray-500/20 text-gray-700 dark:text-gray-300">
                {{ executions.length }} total
              </span>
            </div>
            <ChevronDownIcon v-if="executionsExpanded" class="h-5 w-5 text-secondary" />
            <ChevronRightIcon v-else class="h-5 w-5 text-secondary" />
          </div>
        </div>

        <!-- Collapsible Content -->
        <Transition name="collapse">
          <div v-if="executionsExpanded" class="border-t border-gray-300 dark:border-slate-500">
            <EmptyState
              v-if="executions.length === 0"
              :icon="ClockIcon"
              title="No executions"
              description="No workflow executions have been recorded yet."
              class="py-8"
            />

            <div v-else class="overflow-x-auto">
              <table class="w-full">
                <thead>
                  <tr class="border-b border-gray-300 dark:border-slate-500 bg-gray-50 dark:bg-gray-800/50">
                    <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Workflow</th>
                    <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Status</th>
                    <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Duration</th>
                    <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Started</th>
                    <th class="text-right py-3 px-4 text-sm font-medium text-secondary">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="execution in executions.slice(0, 20)"
                    :key="execution.id"
                    class="border-b border-gray-300 dark:border-slate-500 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/30"
                  >
                    <td class="py-3 px-4">
                      <span class="font-medium text-primary">{{ execution.workflowName }}</span>
                    </td>
                    <td class="py-3 px-4">
                      <StatusBadge
                        :status="execution.status === 'success' ? 'success' : execution.status === 'error' ? 'failed' : execution.status"
                        size="sm"
                      />
                    </td>
                    <td class="py-3 px-4 text-sm text-secondary">
                      {{ formatDuration(execution.executionTime) }}
                    </td>
                    <td class="py-3 px-4 text-sm text-secondary">
                      {{ new Date(execution.startedAt).toLocaleString() }}
                    </td>
                    <td class="py-3 px-4 text-right">
                      <button
                        @click="openExecutionInN8n(execution)"
                        class="btn-secondary p-1.5"
                        title="View in n8n"
                      >
                        <ArrowTopRightOnSquareIcon class="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </Transition>
      </Card>

      <!-- API Notice -->
      <div class="flex items-start gap-3 p-4 rounded-lg bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30">
        <InformationCircleIcon class="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
        <div class="text-sm">
          <p class="font-medium text-blue-800 dark:text-blue-300">n8n API Integration</p>
          <p class="text-blue-700 dark:text-blue-400 mt-1">
            Activate/deactivate and execute functions require <strong>N8N_API_KEY</strong> to be configured.
            The execute feature may not work for all workflow types &mdash; workflows with webhook triggers
            should be triggered via their webhook URL instead.
          </p>
          <p class="text-amber-600 dark:text-amber-400 mt-2">
            <strong>Note:</strong> The API may allow activating misconfigured workflows that the n8n UI would reject.
            Always verify workflow configuration in n8n before activating via this console.
          </p>
        </div>
      </div>
    </template>

    <!-- Activation Confirmation Dialog -->
    <ConfirmDialog
      :open="showActivateConfirm"
      title="Activate Workflow?"
      :message="`Are you sure you want to activate '${pendingToggleWorkflow?.name}'?\n\nWarning: The n8n API may allow activating workflows that have configuration issues. The n8n UI validates workflows before activation, but this API call bypasses that validation.\n\nAlways verify your workflow configuration in n8n before activating via this console.`"
      confirm-text="Activate"
      @confirm="confirmActivate"
      @cancel="showActivateConfirm = false; pendingToggleWorkflow = null"
    />
  </div>
</template>

<style scoped>
.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
}
.collapse-enter-to,
.collapse-leave-from {
  opacity: 1;
  max-height: 800px;
}
</style>
