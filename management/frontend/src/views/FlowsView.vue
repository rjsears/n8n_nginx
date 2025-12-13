<script setup>
import { ref, onMounted, computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useNotificationStore } from '@/stores/notifications'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
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
} from '@heroicons/vue/24/outline'

const themeStore = useThemeStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const workflows = ref([])
const executions = ref([])
const searchQuery = ref('')
const filterActive = ref('all')
const actionLoading = ref(null)

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
    const [workflowsRes, executionsRes] = await Promise.all([
      api.flows.getWorkflows(),
      api.flows.getExecutions(),
    ])
    workflows.value = workflowsRes.data
    executions.value = executionsRes.data
  } catch (error) {
    const detail = error.response?.data?.detail || 'Unknown error'
    notificationStore.error(`Failed to load workflow data: ${detail}`)
    console.error('Flows load error:', error.response?.data || error)
  } finally {
    loading.value = false
  }
}

async function toggleWorkflow(workflow) {
  actionLoading.value = workflow.id
  const targetState = !workflow.active
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

      <!-- Execution Stats -->
      <Card title="Execution Summary" subtitle="Recent execution status breakdown" :neon="true">
        <div class="flex items-center gap-8">
          <div class="flex items-center gap-2">
            <div class="w-3 h-3 rounded-full bg-emerald-500"></div>
            <span class="text-sm text-secondary">Success: {{ executionStats.success }}</span>
          </div>
          <div class="flex items-center gap-2">
            <div class="w-3 h-3 rounded-full bg-red-500"></div>
            <span class="text-sm text-secondary">Error: {{ executionStats.error }}</span>
          </div>
          <div class="flex items-center gap-2">
            <div class="w-3 h-3 rounded-full bg-amber-500"></div>
            <span class="text-sm text-secondary">Waiting: {{ executionStats.waiting }}</span>
          </div>
          <div class="flex items-center gap-2">
            <div class="w-3 h-3 rounded-full bg-blue-500"></div>
            <span class="text-sm text-secondary">Running: {{ executionStats.running }}</span>
          </div>
        </div>
      </Card>

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
            class="flex items-center justify-between p-4 rounded-lg bg-surface-hover border border-[var(--color-border)]"
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
                @click="executeWorkflow(workflow)"
                :disabled="actionLoading === workflow.id"
                class="btn-secondary p-2"
                title="Execute Now"
              >
                <PlayIcon class="h-4 w-4" />
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

      <!-- Recent Executions -->
      <Card title="Recent Executions" subtitle="Last 20 workflow executions" :neon="true">
        <EmptyState
          v-if="executions.length === 0"
          :icon="ClockIcon"
          title="No executions"
          description="No workflow executions have been recorded yet."
        />

        <div v-else class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-[var(--color-border)]">
                <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Workflow</th>
                <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Status</th>
                <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Duration</th>
                <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Started</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="execution in executions.slice(0, 20)"
                :key="execution.id"
                class="border-b border-[var(--color-border)] last:border-0"
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
              </tr>
            </tbody>
          </table>
        </div>
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
  </div>
</template>
