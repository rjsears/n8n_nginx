<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useBackupStore } from '@/stores/backups'
import { useNotificationStore } from '@/stores/notifications'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import {
  CircleStackIcon,
  PlayIcon,
  TrashIcon,
  ArrowDownTrayIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  CalendarIcon,
  Cog6ToothIcon,
  ChevronDownIcon,
  ShieldCheckIcon,
  CheckBadgeIcon,
  ArchiveBoxIcon,
  DocumentArrowDownIcon,
  ServerStackIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  CloudArrowUpIcon,
} from '@heroicons/vue/24/outline'

const router = useRouter()
const themeStore = useThemeStore()
const backupStore = useBackupStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const runningBackup = ref(false)
const deleteDialog = ref({ open: false, backup: null, loading: false })

// Collapsible state
const sections = ref({
  history: false,  // Backup History collapsed by default
})

// Expanded backup IDs (which backup items are expanded)
const expandedBackups = ref(new Set())

// Expanded workflow restore sections within backups
const expandedWorkflowRestore = ref(new Set())

// Workflows loaded for each backup
const backupWorkflows = ref({})
const loadingWorkflows = ref(new Set())

// Operation states
const verifyingBackup = ref(null)
const protectingBackup = ref(null)
const creatingBareMetal = ref(null)
const restoringWorkflow = ref(null)

// Backup schedule (would come from API)
const schedule = ref({
  enabled: true,
  time: '02:00',
  frequency: 'daily',
  retention_days: 30,
})

// Filter and sort
const filterStatus = ref('all')
const sortBy = ref('date')

const filteredBackups = computed(() => {
  let backups = [...backupStore.backups]

  // Filter by status
  if (filterStatus.value !== 'all') {
    backups = backups.filter((b) => b.status === filterStatus.value)
  }

  // Sort
  if (sortBy.value === 'date') {
    backups.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  } else if (sortBy.value === 'size') {
    backups.sort((a, b) => (b.file_size || 0) - (a.file_size || 0))
  }

  return backups
})

// Stats
const stats = computed(() => ({
  total: backupStore.backups.length,
  successful: backupStore.backups.filter((b) => b.status === 'success').length,
  failed: backupStore.backups.filter((b) => b.status === 'failed').length,
  totalSize: backupStore.backups.reduce((sum, b) => sum + (b.file_size || 0), 0),
}))

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

function toggleSection(section) {
  sections.value[section] = !sections.value[section]
}

function toggleBackup(backupId) {
  if (expandedBackups.value.has(backupId)) {
    expandedBackups.value.delete(backupId)
  } else {
    expandedBackups.value.add(backupId)
  }
}

function toggleWorkflowRestore(backupId) {
  if (expandedWorkflowRestore.value.has(backupId)) {
    expandedWorkflowRestore.value.delete(backupId)
  } else {
    expandedWorkflowRestore.value.add(backupId)
    // Load workflows if not already loaded
    if (!backupWorkflows.value[backupId]) {
      loadWorkflowsForBackup(backupId)
    }
  }
}

async function loadWorkflowsForBackup(backupId) {
  loadingWorkflows.value.add(backupId)
  try {
    const response = await api.get(`/backups/${backupId}/restore/workflows`)
    backupWorkflows.value[backupId] = response.data.workflows || []
  } catch (error) {
    console.error('Failed to load workflows:', error)
    notificationStore.error('Failed to load workflows from backup')
    backupWorkflows.value[backupId] = []
  } finally {
    loadingWorkflows.value.delete(backupId)
  }
}

async function runBackupNow() {
  runningBackup.value = true
  try {
    await backupStore.triggerBackup()
    notificationStore.success('Backup started successfully')
    await loadData()
  } catch (error) {
    notificationStore.error('Failed to start backup')
  } finally {
    runningBackup.value = false
  }
}

// === BACKUP ACTIONS ===

// Verify Backup
async function verifyBackup(backup) {
  verifyingBackup.value = backup.id
  try {
    const result = await backupStore.verifyBackup(backup.id)
    if (result.overall_status === 'passed') {
      notificationStore.success('Backup verification passed')
    } else if (result.overall_status === 'failed') {
      notificationStore.error('Backup verification failed')
    } else {
      notificationStore.warning('Backup verification completed with warnings')
    }
    await loadData()
  } catch (error) {
    notificationStore.error('Failed to verify backup')
  } finally {
    verifyingBackup.value = null
  }
}

// Delete Backup
function openDeleteDialog(backup) {
  deleteDialog.value = { open: true, backup, loading: false }
}

async function confirmDelete() {
  if (!deleteDialog.value.backup) return

  deleteDialog.value.loading = true
  try {
    await backupStore.deleteBackup(deleteDialog.value.backup.id)
    notificationStore.success('Backup deleted')
    deleteDialog.value.open = false
    // Remove from expanded state
    expandedBackups.value.delete(deleteDialog.value.backup.id)
  } catch (error) {
    notificationStore.error('Failed to delete backup')
  } finally {
    deleteDialog.value.loading = false
  }
}

// Protect Backup
async function toggleProtection(backup) {
  protectingBackup.value = backup.id
  try {
    const newProtected = !backup.is_protected
    await backupStore.protectBackup(backup.id, newProtected, newProtected ? 'Protected via UI' : null)
    notificationStore.success(newProtected ? 'Backup protected' : 'Backup unprotected')
    await loadData()
  } catch (error) {
    notificationStore.error('Failed to update backup protection')
  } finally {
    protectingBackup.value = null
  }
}

// Download Workflow JSON
async function downloadWorkflow(backup, workflow) {
  try {
    const response = await api.get(`/backups/${backup.id}/workflows/${workflow.id}/download`)
    const blob = new Blob([JSON.stringify(response.data.workflow, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${workflow.name || 'workflow'}_${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    notificationStore.success(`Downloaded workflow: ${workflow.name}`)
  } catch (error) {
    notificationStore.error('Failed to download workflow')
  }
}

// Restore Workflow to n8n via API
async function restoreWorkflowToN8n(backup, workflow) {
  restoringWorkflow.value = `${backup.id}-${workflow.id}`
  try {
    const response = await api.post(`/backups/${backup.id}/restore/workflow`, {
      workflow_id: workflow.id,
      rename_format: 'backup_date',
    })
    if (response.data.success) {
      notificationStore.success(`Restored workflow: ${response.data.new_name}`)
    } else {
      notificationStore.error(response.data.error || 'Failed to restore workflow')
    }
  } catch (error) {
    notificationStore.error('Failed to restore workflow to n8n')
  } finally {
    restoringWorkflow.value = null
  }
}

// Bare Metal Recovery - Create tar.gz
async function createBareMetalRecovery(backup) {
  creatingBareMetal.value = backup.id
  try {
    // Download the backup file (which already includes restore.sh)
    const response = await api.get(`/backups/${backup.id}/download`, {
      responseType: 'blob'
    })

    // Create download link
    const blob = new Blob([response.data], { type: 'application/gzip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = backup.filename || `backup_${backup.id}.n8n_backup.tar.gz`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    notificationStore.success('Bare metal recovery archive downloaded. Extract and run ./restore.sh on target server.')
  } catch (error) {
    notificationStore.error('Failed to download bare metal recovery archive')
  } finally {
    creatingBareMetal.value = null
  }
}

async function loadData() {
  loading.value = true
  try {
    await backupStore.fetchBackups()
  } catch (error) {
    notificationStore.error('Failed to load backups')
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
          Backups
        </h1>
        <p class="text-secondary mt-1">Manage database and workflow backups</p>
      </div>
      <div class="flex items-center gap-3">
        <button
          @click="router.push('/backup-settings')"
          class="btn-secondary flex items-center gap-2"
        >
          <Cog6ToothIcon class="h-4 w-4" />
          Configure
        </button>
        <button
          @click="runBackupNow"
          :disabled="runningBackup"
          :class="[
            'btn-primary flex items-center gap-2',
            themeStore.isNeon ? 'neon-btn-cyan' : ''
          ]"
        >
          <PlayIcon class="h-4 w-4" />
          {{ runningBackup ? 'Running...' : 'Backup Now' }}
        </button>
      </div>
    </div>

    <LoadingSpinner v-if="loading" size="lg" text="Loading backups..." class="py-12" />

    <template v-else>
      <!-- Stats Grid -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
                <CircleStackIcon class="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Total Backups</p>
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
                <p class="text-sm text-secondary">Successful</p>
                <p class="text-xl font-bold text-primary">{{ stats.successful }}</p>
              </div>
            </div>
          </div>
        </Card>

        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-red-100 dark:bg-red-500/20">
                <XCircleIcon class="h-5 w-5 text-red-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Failed</p>
                <p class="text-xl font-bold text-primary">{{ stats.failed }}</p>
              </div>
            </div>
          </div>
        </Card>

        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-500/20">
                <ArrowDownTrayIcon class="h-5 w-5 text-purple-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Total Size</p>
                <p class="text-xl font-bold text-primary">{{ formatBytes(stats.totalSize) }}</p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Schedule Card -->
      <Card :neon="true" :padding="false">
        <div class="p-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-gradient-to-br from-indigo-100 to-indigo-100 dark:from-indigo-500/20 dark:to-indigo-500/20">
                <CalendarIcon class="h-5 w-5 text-indigo-500" />
              </div>
              <div>
                <h3 class="font-semibold text-primary">Backup Schedule</h3>
                <p class="text-sm text-secondary">
                  {{ schedule.frequency }} at {{ schedule.time }} • {{ schedule.retention_days }} day retention
                </p>
              </div>
            </div>
            <StatusBadge :status="schedule.enabled ? 'enabled' : 'disabled'" />
          </div>
        </div>
      </Card>

      <!-- Backup History - Collapsible Section -->
      <Card :neon="true" :padding="false">
        <!-- Section Header (Collapsible) -->
        <button
          @click="toggleSection('history')"
          class="w-full p-4 flex items-center justify-between hover:bg-surface-hover transition-colors rounded-t-lg"
        >
          <div class="flex items-center gap-3">
            <div class="p-2 rounded-lg bg-gradient-to-br from-cyan-100 to-cyan-100 dark:from-cyan-500/20 dark:to-cyan-500/20">
              <ArchiveBoxIcon class="h-5 w-5 text-cyan-600 dark:text-cyan-400" />
            </div>
            <div class="text-left">
              <h3 class="font-semibold text-primary">Backup History</h3>
              <p class="text-sm text-secondary">{{ filteredBackups.length }} backup(s) available</p>
            </div>
          </div>
          <ChevronDownIcon
            :class="[
              'h-5 w-5 text-muted transition-transform duration-200',
              sections.history ? 'rotate-180' : ''
            ]"
          />
        </button>

        <!-- Section Content -->
        <div v-show="sections.history" class="border-t border-gray-200 dark:border-gray-700">
          <!-- Filters (inside Backup History) -->
          <div class="p-4 flex items-center gap-4 bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
            <select v-model="filterStatus" class="select-field">
              <option value="all">All Statuses</option>
              <option value="success">Successful</option>
              <option value="failed">Failed</option>
              <option value="running">Running</option>
              <option value="pending">Pending</option>
            </select>
            <select v-model="sortBy" class="select-field">
              <option value="date">Sort by Date</option>
              <option value="size">Sort by Size</option>
            </select>
          </div>

          <EmptyState
            v-if="filteredBackups.length === 0"
            :icon="CircleStackIcon"
            title="No backups found"
            description="No backups match your current filters."
            class="py-8"
          />

          <div v-else class="divide-y divide-gray-200 dark:divide-gray-700">
            <!-- Individual Backup Items (Collapsible) -->
            <div v-for="backup in filteredBackups" :key="backup.id">
              <!-- Backup Header (Click to expand) -->
              <button
                @click="toggleBackup(backup.id)"
                class="w-full p-4 flex items-center justify-between hover:bg-surface-hover transition-colors"
              >
                <div class="flex items-center gap-4">
                  <div
                    :class="[
                      'p-2 rounded-lg',
                      backup.status === 'success'
                        ? 'bg-emerald-100 dark:bg-emerald-500/20'
                        : backup.status === 'failed'
                        ? 'bg-red-100 dark:bg-red-500/20'
                        : 'bg-amber-100 dark:bg-amber-500/20'
                    ]"
                  >
                    <CircleStackIcon
                      :class="[
                        'h-5 w-5',
                        backup.status === 'success'
                          ? 'text-emerald-500'
                          : backup.status === 'failed'
                          ? 'text-red-500'
                          : 'text-amber-500'
                      ]"
                    />
                  </div>
                  <div class="text-left">
                    <div class="flex items-center gap-2">
                      <p class="font-medium text-primary">{{ backup.backup_type }} Backup</p>
                      <StatusBadge :status="backup.status" size="sm" />
                      <span
                        v-if="backup.is_protected"
                        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-400"
                      >
                        <ShieldCheckIcon class="h-3 w-3" />
                        Protected
                      </span>
                      <span
                        v-if="backup.verification_status === 'passed'"
                        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-400"
                      >
                        <CheckBadgeIcon class="h-3 w-3" />
                        Verified
                      </span>
                    </div>
                    <p class="text-sm text-secondary mt-0.5">
                      {{ new Date(backup.created_at).toLocaleString() }} • {{ formatBytes(backup.file_size) }}
                    </p>
                  </div>
                </div>
                <ChevronDownIcon
                  :class="[
                    'h-5 w-5 text-muted transition-transform duration-200',
                    expandedBackups.has(backup.id) ? 'rotate-180' : ''
                  ]"
                />
              </button>

              <!-- Backup Actions (Expanded Content) -->
              <div
                v-show="expandedBackups.has(backup.id)"
                class="bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700"
              >
                <div class="p-4 space-y-2">
                  <!-- Verify Action -->
                  <button
                    v-if="backup.status === 'success'"
                    @click="verifyBackup(backup)"
                    :disabled="verifyingBackup === backup.id"
                    class="w-full flex items-center gap-3 p-3 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-teal-300 dark:hover:border-teal-500 hover:bg-teal-50 dark:hover:bg-teal-500/10 transition-colors"
                  >
                    <div class="p-2 rounded-lg bg-gradient-to-br from-teal-100 to-teal-100 dark:from-teal-500/20 dark:to-teal-500/20">
                      <CheckBadgeIcon v-if="verifyingBackup !== backup.id" class="h-5 w-5 text-teal-600 dark:text-teal-400" />
                      <LoadingSpinner v-else size="sm" />
                    </div>
                    <div class="text-left flex-1">
                      <p class="font-medium text-primary">Verify Backup</p>
                      <p class="text-sm text-secondary">Spin up temp container and validate backup integrity</p>
                    </div>
                    <span
                      v-if="backup.verification_status"
                      :class="[
                        'text-xs px-2 py-1 rounded-full',
                        backup.verification_status === 'passed' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400' :
                        backup.verification_status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400' :
                        'bg-gray-100 text-gray-700 dark:bg-gray-500/20 dark:text-gray-400'
                      ]"
                    >
                      {{ backup.verification_status }}
                    </span>
                  </button>

                  <!-- Protect Action -->
                  <button
                    v-if="backup.status === 'success'"
                    @click="toggleProtection(backup)"
                    :disabled="protectingBackup === backup.id"
                    class="w-full flex items-center gap-3 p-3 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-amber-300 dark:hover:border-amber-500 hover:bg-amber-50 dark:hover:bg-amber-500/10 transition-colors"
                  >
                    <div class="p-2 rounded-lg bg-gradient-to-br from-amber-100 to-amber-100 dark:from-amber-500/20 dark:to-amber-500/20">
                      <ShieldCheckIcon v-if="protectingBackup !== backup.id" class="h-5 w-5 text-amber-600 dark:text-amber-400" />
                      <LoadingSpinner v-else size="sm" />
                    </div>
                    <div class="text-left flex-1">
                      <p class="font-medium text-primary">{{ backup.is_protected ? 'Unprotect' : 'Protect' }} Backup</p>
                      <p class="text-sm text-secondary">{{ backup.is_protected ? 'Remove protection from automated pruning' : 'Protect from automated pruning' }}</p>
                    </div>
                    <span
                      v-if="backup.is_protected"
                      class="text-xs px-2 py-1 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400"
                    >
                      Protected
                    </span>
                  </button>

                  <!-- Selective Workflow Restore - Collapsible -->
                  <div v-if="backup.status === 'success'" class="rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 overflow-hidden">
                    <button
                      @click="toggleWorkflowRestore(backup.id)"
                      class="w-full flex items-center gap-3 p-3 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-colors"
                    >
                      <div class="p-2 rounded-lg bg-gradient-to-br from-indigo-100 to-indigo-100 dark:from-indigo-500/20 dark:to-indigo-500/20">
                        <ArrowPathIcon class="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                      </div>
                      <div class="text-left flex-1">
                        <p class="font-medium text-primary">Selective Workflow Restore</p>
                        <p class="text-sm text-secondary">Download or push individual workflows to n8n</p>
                      </div>
                      <ChevronDownIcon
                        :class="[
                          'h-5 w-5 text-muted transition-transform duration-200',
                          expandedWorkflowRestore.has(backup.id) ? 'rotate-180' : ''
                        ]"
                      />
                    </button>

                    <!-- Workflow List -->
                    <div
                      v-show="expandedWorkflowRestore.has(backup.id)"
                      class="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50"
                    >
                      <div v-if="loadingWorkflows.has(backup.id)" class="p-4 text-center">
                        <LoadingSpinner size="sm" text="Loading workflows..." />
                      </div>
                      <div v-else-if="!backupWorkflows[backup.id] || backupWorkflows[backup.id].length === 0" class="p-4 text-center text-secondary">
                        No workflows found in this backup
                      </div>
                      <div v-else class="divide-y divide-gray-200 dark:divide-gray-700">
                        <div
                          v-for="workflow in backupWorkflows[backup.id]"
                          :key="workflow.id"
                          class="p-3 flex items-center justify-between hover:bg-white dark:hover:bg-gray-800"
                        >
                          <div class="flex items-center gap-3">
                            <DocumentTextIcon class="h-5 w-5 text-indigo-500" />
                            <div>
                              <p class="font-medium text-primary">{{ workflow.name }}</p>
                              <p class="text-xs text-secondary">
                                {{ workflow.active ? 'Active' : 'Inactive' }}
                                <span v-if="workflow.updated_at"> • Updated {{ new Date(workflow.updated_at).toLocaleDateString() }}</span>
                              </p>
                            </div>
                          </div>
                          <div class="flex items-center gap-2">
                            <!-- Download JSON -->
                            <button
                              @click.stop="downloadWorkflow(backup, workflow)"
                              class="btn-secondary p-2 text-blue-500 hover:text-blue-600"
                              title="Download JSON"
                            >
                              <DocumentArrowDownIcon class="h-4 w-4" />
                            </button>
                            <!-- Push to n8n -->
                            <button
                              @click.stop="restoreWorkflowToN8n(backup, workflow)"
                              :disabled="restoringWorkflow === `${backup.id}-${workflow.id}`"
                              class="btn-secondary p-2 text-emerald-500 hover:text-emerald-600"
                              title="Push to n8n via API"
                            >
                              <LoadingSpinner v-if="restoringWorkflow === `${backup.id}-${workflow.id}`" size="sm" />
                              <CloudArrowUpIcon v-else class="h-4 w-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Bare Metal Recovery -->
                  <button
                    v-if="backup.status === 'success'"
                    @click="createBareMetalRecovery(backup)"
                    :disabled="creatingBareMetal === backup.id"
                    class="w-full flex items-center gap-3 p-3 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-purple-300 dark:hover:border-purple-500 hover:bg-purple-50 dark:hover:bg-purple-500/10 transition-colors"
                  >
                    <div class="p-2 rounded-lg bg-gradient-to-br from-purple-100 to-purple-100 dark:from-purple-500/20 dark:to-purple-500/20">
                      <ServerStackIcon v-if="creatingBareMetal !== backup.id" class="h-5 w-5 text-purple-600 dark:text-purple-400" />
                      <LoadingSpinner v-else size="sm" />
                    </div>
                    <div class="text-left flex-1">
                      <p class="font-medium text-primary">Bare Metal Recovery</p>
                      <p class="text-sm text-secondary">Download tar.gz with restore.sh for full server recovery</p>
                    </div>
                  </button>

                  <!-- Delete Action - Always visible for all backups -->
                  <button
                    @click="openDeleteDialog(backup)"
                    :disabled="backup.is_protected"
                    :class="[
                      'w-full flex items-center gap-3 p-3 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 transition-colors',
                      backup.is_protected
                        ? 'opacity-50 cursor-not-allowed'
                        : 'hover:border-red-300 dark:hover:border-red-500 hover:bg-red-50 dark:hover:bg-red-500/10'
                    ]"
                  >
                    <div class="p-2 rounded-lg bg-gradient-to-br from-red-100 to-red-100 dark:from-red-500/20 dark:to-red-500/20">
                      <TrashIcon class="h-5 w-5 text-red-600 dark:text-red-400" />
                    </div>
                    <div class="text-left flex-1">
                      <p class="font-medium text-primary">
                        {{ backup.status === 'running' ? 'Cancel & Delete' : 'Delete Backup' }}
                      </p>
                      <p class="text-sm text-secondary">
                        {{ backup.is_protected ? 'Unprotect first to delete' :
                           backup.status === 'running' ? 'Cancel this stuck backup and delete the record' :
                           'Permanently delete this backup' }}
                      </p>
                    </div>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </template>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="deleteDialog.open"
      title="Delete Backup"
      message="Are you sure you want to delete this backup? This action cannot be undone."
      confirm-text="Delete"
      :danger="true"
      :loading="deleteDialog.loading"
      @confirm="confirmDelete"
      @cancel="deleteDialog.open = false"
    />
  </div>
</template>
