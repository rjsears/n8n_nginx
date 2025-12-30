<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/views/FlowsView.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref, onMounted, computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useNotificationStore } from '@/stores/notifications'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
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
const workflowsExpanded = ref(true)
const expandedWorkflows = ref(new Set())
const expandedSuccessExecutions = ref(new Set())
const expandedFailedExecutions = ref(new Set())

function toggleWorkflowExpanded(workflowId) {
  if (expandedWorkflows.value.has(workflowId)) {
    expandedWorkflows.value.delete(workflowId)
  } else {
    expandedWorkflows.value.add(workflowId)
  }
  expandedWorkflows.value = new Set(expandedWorkflows.value)
}

function toggleSuccessExecutions(workflowId) {
  if (expandedSuccessExecutions.value.has(workflowId)) {
    expandedSuccessExecutions.value.delete(workflowId)
  } else {
    expandedSuccessExecutions.value.add(workflowId)
  }
  expandedSuccessExecutions.value = new Set(expandedSuccessExecutions.value)
}

function toggleFailedExecutions(workflowId) {
  if (expandedFailedExecutions.value.has(workflowId)) {
    expandedFailedExecutions.value.delete(workflowId)
  } else {
    expandedFailedExecutions.value.add(workflowId)
  }
  expandedFailedExecutions.value = new Set(expandedFailedExecutions.value)
}

function getWorkflowSuccessExecutions(workflowId) {
  return executions.value
    .filter(e => e.workflowId === workflowId && e.status === 'success')
    .slice(0, 5)
}

function getWorkflowFailedExecutions(workflowId) {
  return executions.value
    .filter(e => e.workflowId === workflowId && e.status === 'error')
    .slice(0, 5)
}

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

    <!-- Workflow Loading Animation -->
    <div v-if="loading" class="py-16 flex flex-col items-center justify-center">
      <div class="relative flex items-center gap-4">
        <!-- Trigger Node -->
        <div class="workflow-node">
          <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-amber-100 to-amber-200 dark:from-amber-900/40 dark:to-amber-800/40 border-2 border-amber-300 dark:border-amber-700 flex items-center justify-center shadow-lg">
            <BoltIcon class="h-6 w-6 text-amber-600 dark:text-amber-400" />
          </div>
        </div>

        <!-- Connection Line 1 -->
        <div class="relative w-12 h-1">
          <div class="absolute inset-0 bg-gradient-to-r from-amber-300 to-blue-300 dark:from-amber-700 dark:to-blue-700 rounded-full opacity-50"></div>
          <div class="workflow-data-pulse absolute h-2 w-2 bg-emerald-500 rounded-full top-1/2 -translate-y-1/2"></div>
        </div>

        <!-- Process Node -->
        <div class="workflow-node animation-delay-1">
          <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-blue-100 to-blue-200 dark:from-blue-900/40 dark:to-blue-800/40 border-2 border-blue-300 dark:border-blue-700 flex items-center justify-center shadow-lg">
            <PlayIcon class="h-6 w-6 text-blue-600 dark:text-blue-400" />
          </div>
        </div>

        <!-- Connection Line 2 -->
        <div class="relative w-12 h-1">
          <div class="absolute inset-0 bg-gradient-to-r from-blue-300 to-emerald-300 dark:from-blue-700 dark:to-emerald-700 rounded-full opacity-50"></div>
          <div class="workflow-data-pulse animation-delay-2 absolute h-2 w-2 bg-emerald-500 rounded-full top-1/2 -translate-y-1/2"></div>
        </div>

        <!-- Output Node -->
        <div class="workflow-node animation-delay-2">
          <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-emerald-100 to-emerald-200 dark:from-emerald-900/40 dark:to-emerald-800/40 border-2 border-emerald-300 dark:border-emerald-700 flex items-center justify-center shadow-lg">
            <CheckCircleIcon class="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
          </div>
        </div>
      </div>
      <p class="mt-6 text-sm font-medium text-secondary">Loading workflows...</p>
      <p class="mt-1 text-xs text-muted">Fetching workflow data from n8n</p>
    </div>

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

      <!-- Workflows List (Collapsible) -->
      <Card :neon="true" :padding="false">
        <!-- Collapsible Header -->
        <div
          @click="workflowsExpanded = !workflowsExpanded"
          class="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
        >
          <div class="flex items-center gap-3">
            <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
              <BoltIcon class="h-5 w-5 text-blue-500" />
            </div>
            <div>
              <h3 class="font-semibold text-primary">Workflows</h3>
              <p class="text-sm text-muted">Manage n8n workflows</p>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <div class="flex items-center gap-2">
              <span class="text-xs px-2 py-1 rounded-full bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300">
                {{ stats.active }} active
              </span>
              <span class="text-xs px-2 py-1 rounded-full bg-gray-100 dark:bg-gray-500/20 text-gray-700 dark:text-gray-300">
                {{ stats.total }} total
              </span>
            </div>
            <ChevronDownIcon v-if="workflowsExpanded" class="h-5 w-5 text-secondary" />
            <ChevronRightIcon v-else class="h-5 w-5 text-secondary" />
          </div>
        </div>

        <!-- Collapsible Content -->
        <Transition name="collapse">
          <div v-if="workflowsExpanded" class="px-4 pb-4 border-t border-gray-400 dark:border-gray-700">
            <EmptyState
              v-if="filteredWorkflows.length === 0"
              :icon="BoltIcon"
              title="No workflows found"
              description="No workflows match your current search or filter criteria."
              class="pt-4"
            />

            <div v-else class="pt-2">
              <!-- Header Row -->
              <div class="grid grid-cols-[20px_36px_minmax(200px,1fr)_80px_100px_50px] gap-3 px-3 py-2 text-xs font-medium text-secondary uppercase tracking-wide border-b border-gray-400 dark:border-gray-700">
                <div></div>
                <div></div>
                <div>Name</div>
                <div class="text-center">Status</div>
                <div class="text-center">ID</div>
                <div class="text-center">Toggle</div>
              </div>
              <!-- Workflow Rows -->
              <div class="space-y-1 pt-1">
                <div
                  v-for="workflow in filteredWorkflows"
                  :key="workflow.id"
                  class="rounded-lg bg-surface-hover border border-gray-400 dark:border-black overflow-hidden"
                >
                  <!-- Workflow Row (Single line, clickable to expand) -->
                  <div
                    @click="toggleWorkflowExpanded(workflow.id)"
                    class="grid grid-cols-[20px_36px_minmax(200px,1fr)_80px_100px_50px] gap-3 px-3 py-2 items-center cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors"
                  >
                    <component
                      :is="expandedWorkflows.has(workflow.id) ? ChevronDownIcon : ChevronRightIcon"
                      class="h-4 w-4 text-secondary"
                    />
                    <div
                      :class="[
                        'p-1.5 rounded-lg',
                        workflow.active
                          ? 'bg-emerald-100 dark:bg-emerald-500/20'
                          : 'bg-gray-100 dark:bg-gray-500/20'
                      ]"
                    >
                      <BoltIcon
                        :class="[
                          'h-4 w-4',
                          workflow.active ? 'text-emerald-500' : 'text-gray-500'
                        ]"
                      />
                    </div>
                    <p class="font-medium text-sm text-primary truncate">{{ workflow.name }}</p>
                    <div class="flex justify-center">
                      <StatusBadge :status="workflow.active ? 'active' : 'inactive'" size="sm" />
                    </div>
                    <p class="text-xs text-secondary text-center font-mono">{{ workflow.id }}</p>
                    <!-- Quick toggle -->
                    <div class="flex justify-center" @click.stop>
                      <label class="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          :checked="workflow.active"
                          @change="toggleWorkflow(workflow)"
                          :disabled="actionLoading === workflow.id"
                          class="sr-only peer"
                        />
                        <div
                          class="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-400 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-emerald-500"
                        ></div>
                      </label>
                    </div>
                  </div>

                  <!-- Expanded Workflow Details -->
                  <Transition name="collapse">
                    <div
                      v-if="expandedWorkflows.has(workflow.id)"
                      class="px-4 pb-4 pt-3 border-t border-gray-400 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50"
                    >
                    <!-- Workflow Info -->
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                      <div>
                        <label class="text-xs font-medium text-secondary uppercase tracking-wide">Workflow ID</label>
                        <p class="text-sm text-primary font-mono mt-1">{{ workflow.id }}</p>
                      </div>
                      <div v-if="workflow.triggerCount">
                        <label class="text-xs font-medium text-secondary uppercase tracking-wide">Triggers</label>
                        <p class="text-sm text-primary mt-1">{{ workflow.triggerCount }}</p>
                      </div>
                      <div v-if="workflow.nodeCount">
                        <label class="text-xs font-medium text-secondary uppercase tracking-wide">Nodes</label>
                        <p class="text-sm text-primary mt-1">{{ workflow.nodeCount }}</p>
                      </div>
                      <div v-if="workflow.updatedAt">
                        <label class="text-xs font-medium text-secondary uppercase tracking-wide">Last Updated</label>
                        <p class="text-sm text-primary mt-1">{{ new Date(workflow.updatedAt).toLocaleString() }}</p>
                      </div>
                    </div>

                    <!-- Action Buttons (Bigger) -->
                    <div class="flex flex-wrap items-center gap-3">
                      <button
                        @click="openWorkflowInN8n(workflow)"
                        class="btn-secondary px-4 py-2.5 flex items-center gap-2"
                      >
                        <ArrowTopRightOnSquareIcon class="h-5 w-5" />
                        <span class="font-medium">Open in n8n</span>
                      </button>
                      <button
                        @click="downloadWorkflow(workflow)"
                        :disabled="actionLoading === workflow.id"
                        class="btn-secondary px-4 py-2.5 flex items-center gap-2"
                      >
                        <ArrowDownTrayIcon class="h-5 w-5" />
                        <span class="font-medium">Download</span>
                      </button>
                      <button
                        @click="executeWorkflow(workflow)"
                        :disabled="actionLoading === workflow.id"
                        class="btn-secondary px-4 py-2.5 flex items-center gap-2 text-blue-600 hover:text-blue-700 dark:text-blue-400"
                      >
                        <RocketLaunchIcon class="h-5 w-5" />
                        <span class="font-medium">Execute Now</span>
                      </button>
                      <button
                        @click="toggleWorkflow(workflow)"
                        :disabled="actionLoading === workflow.id"
                        :class="[
                          'btn-secondary px-4 py-2.5 flex items-center gap-2',
                          workflow.active
                            ? 'text-amber-600 hover:text-amber-700 dark:text-amber-400'
                            : 'text-emerald-600 hover:text-emerald-700 dark:text-emerald-400'
                        ]"
                      >
                        <StopIcon v-if="workflow.active" class="h-5 w-5" />
                        <PlayIcon v-else class="h-5 w-5" />
                        <span class="font-medium">{{ workflow.active ? 'Deactivate' : 'Activate' }}</span>
                      </button>
                    </div>

                    <!-- Workflow Executions -->
                    <div class="mt-4 space-y-2">
                      <!-- Last 5 Successful Executions -->
                      <div class="rounded-lg border border-emerald-200 dark:border-emerald-800 overflow-hidden">
                        <div
                          @click.stop="toggleSuccessExecutions(workflow.id)"
                          class="flex items-center justify-between px-3 py-2 cursor-pointer bg-emerald-50 dark:bg-emerald-900/20 hover:bg-emerald-100 dark:hover:bg-emerald-900/30 transition-colors"
                        >
                          <div class="flex items-center gap-2">
                            <component
                              :is="expandedSuccessExecutions.has(workflow.id) ? ChevronDownIcon : ChevronRightIcon"
                              class="h-4 w-4 text-emerald-600 dark:text-emerald-400"
                            />
                            <CheckCircleIcon class="h-4 w-4 text-emerald-500" />
                            <span class="text-sm font-medium text-emerald-700 dark:text-emerald-300">Last 5 Successful Executions</span>
                          </div>
                          <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-500/30 text-emerald-700 dark:text-emerald-300">
                            {{ getWorkflowSuccessExecutions(workflow.id).length }}
                          </span>
                        </div>
                        <Transition name="collapse">
                          <div v-if="expandedSuccessExecutions.has(workflow.id)" class="border-t border-emerald-200 dark:border-emerald-800">
                            <div v-if="getWorkflowSuccessExecutions(workflow.id).length === 0" class="px-3 py-3 text-sm text-secondary italic">
                              No successful executions found
                            </div>
                            <div v-else class="divide-y divide-emerald-100 dark:divide-emerald-800/50">
                              <div
                                v-for="exec in getWorkflowSuccessExecutions(workflow.id)"
                                :key="exec.id"
                                class="flex items-center justify-between px-3 py-2 bg-white dark:bg-gray-800/30"
                              >
                                <div class="flex-1 min-w-0">
                                  <p class="text-sm text-primary">
                                    {{ new Date(exec.startedAt).toLocaleString() }}
                                  </p>
                                  <p class="text-xs text-secondary">
                                    Duration: {{ formatDuration(exec.executionTime) }}
                                  </p>
                                </div>
                                <button
                                  @click.stop="openExecutionInN8n(exec)"
                                  class="btn-secondary p-1.5 text-emerald-600 hover:text-emerald-700 dark:text-emerald-400"
                                  title="View in n8n"
                                >
                                  <ArrowTopRightOnSquareIcon class="h-4 w-4" />
                                </button>
                              </div>
                            </div>
                          </div>
                        </Transition>
                      </div>

                      <!-- Last 5 Failed Executions -->
                      <div class="rounded-lg border border-red-200 dark:border-red-800 overflow-hidden">
                        <div
                          @click.stop="toggleFailedExecutions(workflow.id)"
                          class="flex items-center justify-between px-3 py-2 cursor-pointer bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
                        >
                          <div class="flex items-center gap-2">
                            <component
                              :is="expandedFailedExecutions.has(workflow.id) ? ChevronDownIcon : ChevronRightIcon"
                              class="h-4 w-4 text-red-600 dark:text-red-400"
                            />
                            <XCircleIcon class="h-4 w-4 text-red-500" />
                            <span class="text-sm font-medium text-red-700 dark:text-red-300">Last 5 Failed Executions</span>
                          </div>
                          <span class="text-xs px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-500/30 text-red-700 dark:text-red-300">
                            {{ getWorkflowFailedExecutions(workflow.id).length }}
                          </span>
                        </div>
                        <Transition name="collapse">
                          <div v-if="expandedFailedExecutions.has(workflow.id)" class="border-t border-red-200 dark:border-red-800">
                            <div v-if="getWorkflowFailedExecutions(workflow.id).length === 0" class="px-3 py-3 text-sm text-secondary italic">
                              No failed executions found
                            </div>
                            <div v-else class="divide-y divide-red-100 dark:divide-red-800/50">
                              <div
                                v-for="exec in getWorkflowFailedExecutions(workflow.id)"
                                :key="exec.id"
                                class="flex items-center justify-between px-3 py-2 bg-white dark:bg-gray-800/30"
                              >
                                <div class="flex-1 min-w-0">
                                  <p class="text-sm text-primary">
                                    {{ new Date(exec.startedAt).toLocaleString() }}
                                  </p>
                                  <p class="text-xs text-secondary">
                                    Duration: {{ formatDuration(exec.executionTime) }}
                                  </p>
                                </div>
                                <button
                                  @click.stop="openExecutionInN8n(exec)"
                                  class="btn-secondary p-1.5 text-red-600 hover:text-red-700 dark:text-red-400"
                                  title="View in n8n"
                                >
                                  <ArrowTopRightOnSquareIcon class="h-4 w-4" />
                                </button>
                              </div>
                            </div>
                          </div>
                        </Transition>
                      </div>
                    </div>
                    </div>
                  </Transition>
                </div>
              </div>
            </div>
          </div>
        </Transition>
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
          <div v-if="executionsExpanded" class="border-t border-gray-400 dark:border-black">
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
                  <tr class="border-b border-gray-400 dark:border-black bg-gray-50 dark:bg-gray-800/50">
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
                    class="border-b border-gray-400 dark:border-black last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/30"
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

/* Workflow loading animation */
.workflow-node {
  animation: nodePulse 2s ease-in-out infinite;
}

.workflow-node.animation-delay-1 {
  animation-delay: 0.3s;
}

.workflow-node.animation-delay-2 {
  animation-delay: 0.6s;
}

@keyframes nodePulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.05);
    opacity: 1;
  }
}

.workflow-data-pulse {
  animation: dataPulse 1.5s ease-in-out infinite;
}

.workflow-data-pulse.animation-delay-2 {
  animation-delay: 0.5s;
}

@keyframes dataPulse {
  0% {
    left: 0;
    opacity: 0;
  }
  20% {
    opacity: 1;
  }
  80% {
    opacity: 1;
  }
  100% {
    left: calc(100% - 8px);
    opacity: 0;
  }
}
</style>
