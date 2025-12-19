<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
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
import ProgressModal from '@/components/backups/ProgressModal.vue'
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
  CloudIcon,
  FolderIcon,
  ArrowRightIcon,
  InformationCircleIcon,
  KeyIcon,
  ServerIcon,
  CubeIcon,
  DocumentIcon,
} from '@heroicons/vue/24/outline'

const router = useRouter()
const themeStore = useThemeStore()
const backupStore = useBackupStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const runningBackup = ref(false)
const deleteDialog = ref({ open: false, backup: null, loading: false })

// Progress Modal State
const progressModal = ref({
  show: false,
  type: 'backup', // 'backup' or 'verify'
  backupId: null,
  status: 'running' // 'running', 'success', 'failed'
})

// Get progress data for the active operation
const activeBackupProgress = computed(() => {
  if (!progressModal.value.backupId) return { progress: 0, progress_message: '' }
  const backup = backupStore.backups.find(b => b.id === progressModal.value.backupId)
  return backup || { progress: 0, progress_message: '' }
})

// Collapsible state
const sections = ref({
  history: false,  // Backup History collapsed by default
})

// Expanded backup IDs (which backup items are expanded)
const expandedBackups = ref(new Set())

// Which action is expanded for each backup (backupId -> 'verify'|'protect'|'restore'|'baremetal'|'delete'|null)
const expandedAction = ref({})

// Expanded workflow restore sections within backups
const expandedWorkflowRestore = ref(new Set())

// Expanded restore sections per backup (backupId -> 'workflows'|'config'|null)
const expandedRestoreSection = ref({})

// Expanded individual items for actions (backupId-itemId -> true)
const expandedRestoreItem = ref({})

// Workflows loaded for each backup
const backupWorkflows = ref({})
const loadingWorkflows = ref(new Set())

// Config files loaded for each backup
const backupConfigFiles = ref({})
const loadingConfigFiles = ref(new Set())

// Operation states
const verifyingBackup = ref(null)
const protectingBackup = ref(null)
const creatingBareMetal = ref(null)
const restoringWorkflow = ref(null)
const restoringConfig = ref(null)

// Mount state
const mountedBackup = ref(null)  // { backup_id, backup_info, workflows }
const mountingBackup = ref(null)  // backup_id being mounted
const unmountingBackup = ref(false)

// Polling for running backups/verifications
const pollingInterval = ref(null)
const POLL_INTERVAL_MS = 2000

// Check if any backup is in progress
const hasRunningOperations = computed(() => {
  return backupStore.backups.some(b => b.status === 'running') ||
         verifyingBackup.value !== null ||
         runningBackup.value
})

// Start/stop polling based on running operations
function startPolling() {
  if (pollingInterval.value) return
  pollingInterval.value = setInterval(async () => {
    if (hasRunningOperations.value) {
      await backupStore.fetchBackups()
    } else {
      stopPolling()
    }
  }, POLL_INTERVAL_MS)
}

function stopPolling() {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
}

// Watch for running operations to start/stop polling
watch(hasRunningOperations, (hasRunning) => {
  if (hasRunning) {
    startPolling()
  } else {
    stopPolling()
  }
})

// Backup schedule (would come from API)
const schedule = ref({
  enabled: true,
  time: '02:00',
  frequency: 'daily',
  retention_days: 30,
})

// Backup configuration
const backupConfig = ref(null)

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
    // Clear expanded action when collapsing backup
    delete expandedAction.value[backupId]
  } else {
    expandedBackups.value.add(backupId)
  }
}

function toggleAction(backupId, action) {
  // Toggle the action panel - if same action is clicked, close it
  if (expandedAction.value[backupId] === action) {
    expandedAction.value[backupId] = null
  } else {
    expandedAction.value[backupId] = action
    // Note: For 'restore' action, we no longer auto-load workflows/config
    // User must click "Mount Backup" first to load the data
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

// Toggle restore section (workflows or config files)
function toggleRestoreSection(backupId, section) {
  if (expandedRestoreSection.value[backupId] === section) {
    expandedRestoreSection.value[backupId] = null
  } else {
    expandedRestoreSection.value[backupId] = section
  }
}

// Toggle individual item expansion (for showing action buttons)
function toggleRestoreItem(backupId, itemId) {
  const key = `${backupId}-${itemId}`
  if (expandedRestoreItem.value[key]) {
    delete expandedRestoreItem.value[key]
  } else {
    // Close other expanded items for this backup
    Object.keys(expandedRestoreItem.value).forEach(k => {
      if (k.startsWith(`${backupId}-`)) {
        delete expandedRestoreItem.value[k]
      }
    })
    expandedRestoreItem.value[key] = true
  }
}

// Check if an item is expanded
function isRestoreItemExpanded(backupId, itemId) {
  return !!expandedRestoreItem.value[`${backupId}-${itemId}`]
}

// Mount a backup for restore operations
async function mountBackup(backupId) {
  mountingBackup.value = backupId
  try {
    const response = await api.post(`/backups/${backupId}/mount`)
    if (response.data.status === 'success') {
      mountedBackup.value = {
        backup_id: backupId,
        backup_info: response.data.backup_info,
        workflows: response.data.workflows || []
      }
      // Store workflows for this backup
      backupWorkflows.value[backupId] = response.data.workflows || []
      notificationStore.success(`Backup mounted with ${response.data.workflows?.length || 0} workflows`)
      // Also load config files
      await loadConfigFilesForBackup(backupId)
    } else {
      notificationStore.error(response.data.error || 'Failed to mount backup')
    }
  } catch (error) {
    console.error('Failed to mount backup:', error)
    notificationStore.error('Failed to mount backup: ' + (error.response?.data?.detail || error.message))
  } finally {
    mountingBackup.value = null
  }
}

// Unmount the currently mounted backup
async function unmountBackup() {
  if (!mountedBackup.value) return

  unmountingBackup.value = true
  const backupId = mountedBackup.value.backup_id
  try {
    await api.post(`/backups/${backupId}/unmount`)
    mountedBackup.value = null
    // Clear the loaded data
    delete backupWorkflows.value[backupId]
    delete backupConfigFiles.value[backupId]
    notificationStore.success('Backup unmounted')
  } catch (error) {
    console.error('Failed to unmount backup:', error)
    notificationStore.error('Failed to unmount backup')
  } finally {
    unmountingBackup.value = false
  }
}

// Check if a specific backup is mounted
function isBackupMounted(backupId) {
  return mountedBackup.value?.backup_id === backupId
}

async function loadWorkflowsForBackup(backupId) {
  // If backup is mounted, workflows are already loaded
  if (isBackupMounted(backupId) && backupWorkflows.value[backupId]) {
    return
  }
  // Otherwise, they need to mount first
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

async function loadConfigFilesForBackup(backupId) {
  loadingConfigFiles.value.add(backupId)
  try {
    const response = await api.get(`/backups/${backupId}/restore/config-files`)
    backupConfigFiles.value[backupId] = response.data.config_files || []
  } catch (error) {
    console.error('Failed to load config files:', error)
    notificationStore.error('Failed to load config files from backup')
    backupConfigFiles.value[backupId] = []
  } finally {
    loadingConfigFiles.value.delete(backupId)
  }
}

async function runBackupNow() {
  runningBackup.value = true

  // Show progress modal
  progressModal.value = {
    show: true,
    type: 'backup',
    backupId: null,
    status: 'running'
  }

  try {
    const result = await backupStore.triggerBackup()
    // Set the backup ID so we can track progress
    if (result && result.backup_id) {
      progressModal.value.backupId = result.backup_id
    }

    // Poll for completion
    await pollForCompletion('backup')

  } catch (error) {
    progressModal.value.status = 'failed'
    notificationStore.error('Failed to start backup: ' + (error.message || 'Unknown error'))
  } finally {
    runningBackup.value = false
  }
}

// Poll for backup/verification completion
async function pollForCompletion(type) {
  const maxAttempts = 300 // 5 minutes max
  let attempts = 0

  while (attempts < maxAttempts) {
    await new Promise(resolve => setTimeout(resolve, 1000)) // Wait 1 second
    await backupStore.fetchBackups()

    const backup = backupStore.backups.find(b => b.id === progressModal.value.backupId)
    if (!backup) {
      attempts++
      continue
    }

    // Update modal with latest status
    if (backup.status === 'success') {
      progressModal.value.status = 'success'
      if (type === 'backup') {
        notificationStore.success('Backup completed successfully')
      }
      return
    } else if (backup.status === 'failed') {
      progressModal.value.status = 'failed'
      if (type === 'backup') {
        notificationStore.error('Backup failed: ' + (backup.error_message || 'Unknown error'))
      }
      return
    }

    // For verification, check verification_status
    if (type === 'verify') {
      if (backup.verification_status === 'passed') {
        progressModal.value.status = 'success'
        notificationStore.success('Backup verification passed')
        return
      } else if (backup.verification_status === 'failed') {
        progressModal.value.status = 'failed'
        notificationStore.error('Backup verification failed')
        return
      }
    }

    attempts++
  }

  // Timeout
  progressModal.value.status = 'failed'
  notificationStore.error('Operation timed out')
}

function closeProgressModal() {
  progressModal.value.show = false
  progressModal.value.backupId = null
  loadData() // Refresh the list
}

// === BACKUP ACTIONS ===

// Verify Backup
async function verifyBackup(backup) {
  verifyingBackup.value = backup.id

  // Reset progress in local store to avoid showing stale data
  const index = backupStore.history.findIndex(b => b.id === backup.id)
  if (index > -1) {
    backupStore.history[index] = {
      ...backupStore.history[index],
      progress: 0,
      progress_message: 'Starting verification...'
    }
  }

  // Show progress modal
  progressModal.value = {
    show: true,
    type: 'verify',
    backupId: backup.id,
    status: 'running'
  }

  // Start polling for progress updates in background (don't await - runs independently)
  pollForProgress()

  try {
    // Call the verification API (this may block until complete)
    const result = await backupStore.verifyBackup(backup.id)

    // Update modal status based on result (this also stops polling)
    if (result.overall_status === 'passed') {
      progressModal.value.status = 'success'
      notificationStore.success('Backup verification passed')
    } else if (result.overall_status === 'failed') {
      progressModal.value.status = 'failed'
      const errorMsg = result.error || result.errors?.join(', ') || 'Unknown error'
      notificationStore.error(`Backup verification failed: ${errorMsg}`)
    } else {
      progressModal.value.status = 'success' // Treat warnings as success
      const warnMsg = result.warnings?.join(', ') || ''
      notificationStore.warning(`Backup verification completed with warnings${warnMsg ? ': ' + warnMsg : ''}`)
    }

    // Final refresh to get latest data
    await backupStore.fetchBackups()
  } catch (error) {
    progressModal.value.status = 'failed'
    notificationStore.error('Failed to verify backup: ' + (error.message || 'Unknown error'))
  } finally {
    verifyingBackup.value = null
  }
}

// Poll for progress updates during long-running operations
async function pollForProgress() {
  while (progressModal.value.status === 'running' && progressModal.value.show) {
    await new Promise(resolve => setTimeout(resolve, 1000))
    try {
      await backupStore.fetchBackups()
    } catch (e) {
      // Ignore polling errors
    }
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
      rename_format: '{name}_backup_{date}',
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

// Restore Config File to system
async function restoreConfigFile(backup, configFile) {
  restoringConfig.value = `${backup.id}-${configFile.path}`
  try {
    const response = await api.post(`/backups/${backup.id}/restore/config`, {
      config_path: configFile.path,
      create_backup: true,
    })
    if (response.data.status === 'success') {
      notificationStore.success(`Restored ${configFile.name}. Original backed up to ${response.data.backup_created || 'backup file'}`)
    } else {
      notificationStore.error(response.data.error || 'Failed to restore config file')
    }
  } catch (error) {
    notificationStore.error('Failed to restore config file')
  } finally {
    restoringConfig.value = null
  }
}

// Download config file from backup
async function downloadConfigFile(backup, configFile) {
  try {
    // Download the specific config file from the backup archive
    const response = await api.get(`/backups/${backup.id}/config-files/${configFile.path}/download`, {
      responseType: 'blob'
    })

    // Create download link
    const blob = new Blob([response.data], { type: 'application/octet-stream' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = configFile.name
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    notificationStore.success(`Downloaded ${configFile.name}`)
  } catch (error) {
    console.error('Failed to download config file:', error)
    notificationStore.error(`Failed to download ${configFile.name}`)
  }
}

// Get icon component for config file type
function getConfigFileIcon(configFile) {
  if (configFile.is_ssl) return 'ShieldCheckIcon'
  if (configFile.name.endsWith('.env')) return 'KeyIcon'
  if (configFile.name.includes('nginx')) return 'ServerIcon'
  if (configFile.name.includes('docker')) return 'CubeIcon'
  return 'DocumentIcon'
}

// Format file size
function formatFileSize(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
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
    // Fetch backup configuration
    try {
      backupConfig.value = await backupStore.fetchConfiguration()
    } catch (err) {
      console.error('Failed to fetch backup configuration:', err)
    }
  } catch (error) {
    notificationStore.error('Failed to load backups')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
onUnmounted(stopPolling)
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

      <!-- Backup Configuration Summary Card (Clickable - navigates to storage settings) -->
      <Card v-if="backupConfig" :neon="true" :padding="false" class="mt-4">
        <button
          @click="router.push('/backup-settings?tab=storage')"
          class="w-full p-4 text-left hover:bg-surface-hover transition-colors rounded-lg"
        >
          <h4 class="font-semibold text-primary mb-3 flex items-center gap-2">
            <InformationCircleIcon class="h-4 w-4 text-gray-400" />
            Backup Configuration Summary
          </h4>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <!-- Destination -->
            <div :class="[
              'p-3 rounded-lg border',
              backupConfig.storage_preference === 'nfs'
                ? 'bg-emerald-50/50 dark:bg-emerald-900/10 border-emerald-200 dark:border-emerald-800/50'
                : 'bg-blue-50/50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800/50'
            ]">
              <div class="flex items-center gap-2 mb-1">
                <component
                  :is="backupConfig.storage_preference === 'nfs' ? CloudIcon : CircleStackIcon"
                  :class="[
                    'h-4 w-4',
                    backupConfig.storage_preference === 'nfs' ? 'text-emerald-500' : 'text-blue-500'
                  ]"
                />
                <p :class="[
                  'text-xs font-medium uppercase tracking-wide',
                  backupConfig.storage_preference === 'nfs' ? 'text-emerald-600 dark:text-emerald-400' : 'text-blue-600 dark:text-blue-400'
                ]">Destination</p>
              </div>
              <p class="text-sm font-medium text-primary">
                {{ backupConfig.storage_preference === 'nfs' ? 'Network Storage (NFS)' : 'Local Storage' }}
              </p>
              <p v-if="backupConfig.storage_preference === 'nfs' && backupConfig.nfs_storage_path" class="text-xs text-secondary mt-0.5 font-mono truncate">
                {{ backupConfig.nfs_storage_path }}
              </p>
            </div>
            <!-- Workflow -->
            <div :class="[
              'p-3 rounded-lg border',
              backupConfig.storage_preference === 'nfs'
                ? (backupConfig.backup_workflow === 'stage_then_copy'
                    ? 'bg-indigo-50/50 dark:bg-indigo-900/10 border-indigo-200 dark:border-indigo-800/50'
                    : 'bg-purple-50/50 dark:bg-purple-900/10 border-purple-200 dark:border-purple-800/50')
                : 'bg-blue-50/50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800/50'
            ]">
              <div class="flex items-center gap-2 mb-1">
                <ArrowRightIcon :class="[
                  'h-4 w-4',
                  backupConfig.storage_preference === 'nfs'
                    ? (backupConfig.backup_workflow === 'stage_then_copy' ? 'text-indigo-500' : 'text-purple-500')
                    : 'text-blue-500'
                ]" />
                <p :class="[
                  'text-xs font-medium uppercase tracking-wide',
                  backupConfig.storage_preference === 'nfs'
                    ? (backupConfig.backup_workflow === 'stage_then_copy' ? 'text-indigo-600 dark:text-indigo-400' : 'text-purple-600 dark:text-purple-400')
                    : 'text-blue-600 dark:text-blue-400'
                ]">Workflow</p>
              </div>
              <p class="text-sm font-medium text-primary">
                <span v-if="backupConfig.storage_preference === 'local'">Direct to Local</span>
                <span v-else-if="backupConfig.backup_workflow === 'stage_then_copy'">Stage & Copy</span>
                <span v-else>Direct to NFS</span>
              </p>
            </div>
            <!-- Staging -->
            <div :class="[
              'p-3 rounded-lg border',
              backupConfig.storage_preference === 'nfs' && backupConfig.backup_workflow === 'stage_then_copy'
                ? 'bg-amber-50/50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800/50'
                : 'bg-gray-50/50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700'
            ]">
              <div class="flex items-center gap-2 mb-1">
                <FolderIcon :class="[
                  'h-4 w-4',
                  backupConfig.storage_preference === 'nfs' && backupConfig.backup_workflow === 'stage_then_copy'
                    ? 'text-amber-500'
                    : 'text-gray-400'
                ]" />
                <p :class="[
                  'text-xs font-medium uppercase tracking-wide',
                  backupConfig.storage_preference === 'nfs' && backupConfig.backup_workflow === 'stage_then_copy'
                    ? 'text-amber-600 dark:text-amber-400'
                    : 'text-gray-500 dark:text-gray-400'
                ]">Staging</p>
              </div>
              <p class="text-sm font-medium text-primary">
                {{ backupConfig.storage_preference === 'nfs' && backupConfig.backup_workflow === 'stage_then_copy' ? 'Enabled' : 'Disabled' }}
              </p>
            </div>
          </div>
        </button>
      </Card>

      <!-- Schedule Card (Clickable - navigates to schedule settings) -->
      <Card :neon="true" :padding="false">
        <button
          @click="router.push('/backup-settings?tab=schedule')"
          class="w-full p-4 text-left hover:bg-surface-hover transition-colors rounded-lg"
        >
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
        </button>
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
                    <!-- Progress Bar for Running Backups -->
                    <div v-if="backup.status === 'running' && backup.progress !== undefined" class="mt-2 w-64">
                      <div class="flex items-center justify-between text-xs text-secondary mb-1">
                        <span>{{ backup.progress_message || 'In progress...' }}</span>
                        <span>{{ backup.progress }}%</span>
                      </div>
                      <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                        <div
                          class="bg-blue-500 h-2 rounded-full transition-all duration-300"
                          :style="{ width: `${backup.progress}%` }"
                        ></div>
                      </div>
                    </div>
                    <p v-else class="text-sm text-secondary mt-0.5">
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
                <!-- Action Button Bar -->
                <div class="p-4 flex flex-wrap items-center gap-2">
                  <!-- Verify Button -->
                  <button
                    v-if="backup.status === 'success'"
                    @click="toggleAction(backup.id, 'verify')"
                    :class="[
                      'flex items-center gap-2 px-4 py-2 rounded-lg border transition-all',
                      expandedAction[backup.id] === 'verify'
                        ? 'bg-teal-100 dark:bg-teal-500/20 border-teal-400 dark:border-teal-500 text-teal-700 dark:text-teal-300'
                        : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:border-teal-300 dark:hover:border-teal-500 hover:bg-teal-50 dark:hover:bg-teal-500/10'
                    ]"
                  >
                    <CheckBadgeIcon class="h-5 w-5 text-teal-600 dark:text-teal-400" />
                    <span class="font-medium">Verify</span>
                  </button>

                  <!-- Protect Button -->
                  <button
                    v-if="backup.status === 'success'"
                    @click="toggleAction(backup.id, 'protect')"
                    :class="[
                      'flex items-center gap-2 px-4 py-2 rounded-lg border transition-all',
                      expandedAction[backup.id] === 'protect'
                        ? 'bg-amber-100 dark:bg-amber-500/20 border-amber-400 dark:border-amber-500 text-amber-700 dark:text-amber-300'
                        : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:border-amber-300 dark:hover:border-amber-500 hover:bg-amber-50 dark:hover:bg-amber-500/10'
                    ]"
                  >
                    <ShieldCheckIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
                    <span class="font-medium">{{ backup.is_protected ? 'Unprotect' : 'Protect' }}</span>
                  </button>

                  <!-- Selective Restore Button -->
                  <button
                    v-if="backup.status === 'success'"
                    @click="toggleAction(backup.id, 'restore')"
                    :class="[
                      'flex items-center gap-2 px-4 py-2 rounded-lg border transition-all',
                      expandedAction[backup.id] === 'restore'
                        ? 'bg-indigo-100 dark:bg-indigo-500/20 border-indigo-400 dark:border-indigo-500 text-indigo-700 dark:text-indigo-300'
                        : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:border-indigo-300 dark:hover:border-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-500/10'
                    ]"
                  >
                    <ArrowPathIcon class="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                    <span class="font-medium">Selective Restore</span>
                  </button>

                  <!-- Bare Metal Button -->
                  <button
                    v-if="backup.status === 'success'"
                    @click="toggleAction(backup.id, 'baremetal')"
                    :class="[
                      'flex items-center gap-2 px-4 py-2 rounded-lg border transition-all',
                      expandedAction[backup.id] === 'baremetal'
                        ? 'bg-purple-100 dark:bg-purple-500/20 border-purple-400 dark:border-purple-500 text-purple-700 dark:text-purple-300'
                        : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:border-purple-300 dark:hover:border-purple-500 hover:bg-purple-50 dark:hover:bg-purple-500/10'
                    ]"
                  >
                    <ServerStackIcon class="h-5 w-5 text-purple-600 dark:text-purple-400" />
                    <span class="font-medium">Bare Metal</span>
                  </button>

                  <!-- Delete Button - Always visible -->
                  <button
                    @click="toggleAction(backup.id, 'delete')"
                    :disabled="backup.is_protected"
                    :class="[
                      'flex items-center gap-2 px-4 py-2 rounded-lg border transition-all',
                      backup.is_protected ? 'opacity-50 cursor-not-allowed' :
                      expandedAction[backup.id] === 'delete'
                        ? 'bg-red-100 dark:bg-red-500/20 border-red-400 dark:border-red-500 text-red-700 dark:text-red-300'
                        : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:border-red-300 dark:hover:border-red-500 hover:bg-red-50 dark:hover:bg-red-500/10'
                    ]"
                  >
                    <TrashIcon class="h-5 w-5 text-red-600 dark:text-red-400" />
                    <span class="font-medium">Delete</span>
                  </button>
                </div>

                <!-- Action Panels -->
                <div v-if="expandedAction[backup.id]" class="border-t border-gray-200 dark:border-gray-700">
                  <!-- Verify Panel -->
                  <div v-if="expandedAction[backup.id] === 'verify'" class="p-4">
                    <div class="bg-white dark:bg-gray-800 rounded-lg border border-teal-200 dark:border-teal-700 p-4">
                      <h4 class="font-semibold text-primary flex items-center gap-2 mb-2">
                        <CheckBadgeIcon class="h-5 w-5 text-teal-600 dark:text-teal-400" />
                        Verify Backup Integrity
                      </h4>
                      <p class="text-sm text-secondary mb-4">
                        Spins up a temporary PostgreSQL container, loads the backup, and validates all database tables, row counts, and workflow checksums.
                      </p>
                      <div class="flex items-center gap-3">
                        <button
                          @click="verifyBackup(backup)"
                          :disabled="verifyingBackup === backup.id"
                          class="btn-primary bg-teal-600 hover:bg-teal-700 flex items-center gap-2"
                        >
                          <LoadingSpinner v-if="verifyingBackup === backup.id" size="sm" />
                          <CheckBadgeIcon v-else class="h-4 w-4" />
                          {{ verifyingBackup === backup.id ? 'Verifying...' : 'Start Verification' }}
                        </button>
                        <span
                          v-if="backup.verification_status && !['pending', 'running'].includes(backup.verification_status)"
                          :class="[
                            'text-sm px-3 py-1 rounded-full',
                            backup.verification_status === 'passed' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400' :
                            'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400'
                          ]"
                        >
                          Last result: {{ backup.verification_status }}
                        </span>
                      </div>
                      <!-- Verification Progress Bar -->
                      <div v-if="verifyingBackup === backup.id && backup.progress !== undefined" class="mt-4">
                        <div class="flex items-center justify-between text-xs text-secondary mb-1">
                          <span>{{ backup.progress_message || 'Verifying...' }}</span>
                          <span>{{ backup.progress }}%</span>
                        </div>
                        <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                          <div
                            class="bg-teal-500 h-2 rounded-full transition-all duration-300"
                            :style="{ width: `${backup.progress}%` }"
                          ></div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Protect Panel -->
                  <div v-if="expandedAction[backup.id] === 'protect'" class="p-4">
                    <div class="bg-white dark:bg-gray-800 rounded-lg border border-amber-200 dark:border-amber-700 p-4">
                      <h4 class="font-semibold text-primary flex items-center gap-2 mb-2">
                        <ShieldCheckIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
                        {{ backup.is_protected ? 'Backup Protection' : 'Protect Backup' }}
                      </h4>
                      <p class="text-sm text-secondary mb-4">
                        {{ backup.is_protected
                          ? 'This backup is protected from automatic pruning and cannot be deleted until unprotected.'
                          : 'Protected backups are never automatically deleted by retention policies or pruning.'
                        }}
                      </p>
                      <button
                        @click="toggleProtection(backup)"
                        :disabled="protectingBackup === backup.id"
                        :class="[
                          'flex items-center gap-2',
                          backup.is_protected ? 'btn-secondary' : 'btn-primary bg-amber-600 hover:bg-amber-700'
                        ]"
                      >
                        <LoadingSpinner v-if="protectingBackup === backup.id" size="sm" />
                        <ShieldCheckIcon v-else class="h-4 w-4" />
                        {{ protectingBackup === backup.id ? 'Processing...' : (backup.is_protected ? 'Remove Protection' : 'Protect This Backup') }}
                      </button>
                    </div>
                  </div>

                  <!-- Selective Restore Panel -->
                  <div v-if="expandedAction[backup.id] === 'restore'" class="p-4 space-y-4">
                    <!-- Mount Required Message (if not mounted) -->
                    <div v-if="!isBackupMounted(backup.id)" class="bg-white dark:bg-gray-800 rounded-lg border border-indigo-200 dark:border-indigo-700 p-6">
                      <div class="flex items-start gap-4">
                        <div class="flex-shrink-0">
                          <ArchiveBoxIcon class="h-10 w-10 text-indigo-500" />
                        </div>
                        <div class="flex-1">
                          <h4 class="font-semibold text-primary text-lg mb-2">Mount Backup for Restore</h4>
                          <p class="text-secondary mb-4">
                            To browse and restore individual items, the backup archive must first be mounted.
                            This will extract and load the backup data into a temporary container.
                          </p>
                          <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-3 mb-4">
                            <p class="text-sm text-amber-800 dark:text-amber-200 flex items-start gap-2">
                              <InformationCircleIcon class="h-5 w-5 flex-shrink-0 mt-0.5" />
                              <span><strong>Important:</strong> Please keep the backup mounted until you have completed all restore operations. Click "Unmount" when finished to free up resources.</span>
                            </p>
                          </div>
                          <button
                            @click="mountBackup(backup.id)"
                            :disabled="mountingBackup === backup.id"
                            class="btn-primary bg-indigo-600 hover:bg-indigo-700 flex items-center gap-2 px-6 py-2.5"
                          >
                            <LoadingSpinner v-if="mountingBackup === backup.id" size="sm" />
                            <ArchiveBoxIcon v-else class="h-5 w-5" />
                            {{ mountingBackup === backup.id ? 'Mounting Backup...' : 'Mount Backup' }}
                          </button>
                        </div>
                      </div>
                    </div>

                    <!-- Mounted State - Show Unmount + Content -->
                    <template v-else>
                      <!-- Mounted Status Bar -->
                      <div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 rounded-lg p-3 flex items-center justify-between">
                        <div class="flex items-center gap-3">
                          <CheckCircleIcon class="h-5 w-5 text-green-600 dark:text-green-400" />
                          <span class="text-green-800 dark:text-green-200 font-medium">
                            Backup Mounted
                            <span class="text-green-600 dark:text-green-400 font-normal ml-2">
                              ({{ backupWorkflows[backup.id]?.length || 0 }} workflows available)
                            </span>
                          </span>
                        </div>
                        <button
                          @click="unmountBackup()"
                          :disabled="unmountingBackup"
                          class="px-4 py-1.5 bg-white dark:bg-gray-800 border border-green-300 dark:border-green-600 rounded-lg text-green-700 dark:text-green-300 hover:bg-green-100 dark:hover:bg-green-900/30 text-sm font-medium flex items-center gap-2"
                        >
                          <LoadingSpinner v-if="unmountingBackup" size="sm" />
                          <XCircleIcon v-else class="h-4 w-4" />
                          {{ unmountingBackup ? 'Unmounting...' : 'Unmount Backup' }}
                        </button>
                      </div>

                      <!-- Workflows Section (Collapsible) -->
                      <div class="bg-white dark:bg-gray-800 rounded-lg border border-indigo-200 dark:border-indigo-700 overflow-hidden">
                        <!-- Section Header (Clickable) -->
                        <button
                          @click="toggleRestoreSection(backup.id, 'workflows')"
                          class="w-full p-4 flex items-center justify-between hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors"
                        >
                          <div class="flex items-center gap-2">
                            <DocumentTextIcon class="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                            <span class="font-semibold text-primary">Workflows</span>
                            <span v-if="backupWorkflows[backup.id]" class="text-xs text-secondary bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded-full">
                              {{ backupWorkflows[backup.id].length }}
                            </span>
                          </div>
                          <ChevronDownIcon
                            :class="[
                              'h-5 w-5 text-gray-400 transition-transform duration-200',
                              expandedRestoreSection[backup.id] === 'workflows' ? 'rotate-180' : ''
                            ]"
                          />
                        </button>

                        <!-- Section Content -->
                        <div v-if="expandedRestoreSection[backup.id] === 'workflows'" class="border-t border-indigo-100 dark:border-indigo-800">
                          <p class="text-sm text-secondary px-4 py-2 bg-indigo-50/50 dark:bg-indigo-900/10">
                            Click a workflow to see restore options.
                          </p>

                          <!-- Workflow List -->
                          <div v-if="!backupWorkflows[backup.id] || backupWorkflows[backup.id].length === 0" class="py-4 text-center text-secondary">
                            No workflows found in this backup
                          </div>
                          <div v-else class="max-h-64 overflow-y-auto">
                            <div
                              v-for="workflow in backupWorkflows[backup.id]"
                              :key="workflow.id"
                              class="border-b border-gray-100 dark:border-gray-700 last:border-b-0"
                            >
                              <!-- Workflow Item (Clickable) -->
                              <button
                                @click="toggleRestoreItem(backup.id, `wf-${workflow.id}`)"
                                class="w-full p-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                              >
                                <div class="flex items-center gap-3">
                                  <DocumentTextIcon class="h-5 w-5 text-indigo-500" />
                                  <div class="text-left">
                                    <p class="font-medium text-primary">{{ workflow.name }}</p>
                                    <p class="text-xs text-secondary">
                                      {{ workflow.active ? 'Active' : 'Inactive' }}
                                      <span v-if="workflow.updated_at"> • {{ new Date(workflow.updated_at).toLocaleDateString() }}</span>
                                    </p>
                                  </div>
                                </div>
                                <ChevronDownIcon
                                  :class="[
                                    'h-4 w-4 text-gray-400 transition-transform duration-200',
                                    isRestoreItemExpanded(backup.id, `wf-${workflow.id}`) ? 'rotate-180' : ''
                                  ]"
                                />
                              </button>

                              <!-- Workflow Actions (Expanded) -->
                              <div
                                v-if="isRestoreItemExpanded(backup.id, `wf-${workflow.id}`)"
                                class="px-4 py-3 bg-indigo-50 dark:bg-indigo-900/20 flex items-center gap-3"
                              >
                                <button
                                  @click.stop="downloadWorkflow(backup, workflow)"
                                  class="btn-secondary px-4 py-2 text-sm flex items-center gap-2 border border-blue-300 dark:border-blue-600 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/30"
                                  title="Download as JSON file"
                                >
                                  <DocumentArrowDownIcon class="h-4 w-4 text-blue-600" />
                                  <span>Download JSON</span>
                                </button>
                                <button
                                  @click.stop="restoreWorkflowToN8n(backup, workflow)"
                                  :disabled="restoringWorkflow === `${backup.id}-${workflow.id}`"
                                  class="btn-primary px-4 py-2 text-sm flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 rounded-lg text-white"
                                  title="Restore to n8n with new name"
                                >
                                  <LoadingSpinner v-if="restoringWorkflow === `${backup.id}-${workflow.id}`" size="sm" />
                                  <CloudArrowUpIcon v-else class="h-4 w-4" />
                                  <span>Restore to n8n</span>
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>

                    <!-- Config Files Section (Collapsible) -->
                    <div class="bg-white dark:bg-gray-800 rounded-lg border border-emerald-200 dark:border-emerald-700 overflow-hidden">
                      <!-- Section Header (Clickable) -->
                      <button
                        @click="toggleRestoreSection(backup.id, 'config')"
                        class="w-full p-4 flex items-center justify-between hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors"
                      >
                        <div class="flex items-center gap-2">
                          <Cog6ToothIcon class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                          <span class="font-semibold text-primary">Configuration Files</span>
                          <span v-if="backupConfigFiles[backup.id]" class="text-xs text-secondary bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded-full">
                            {{ backupConfigFiles[backup.id].length }}
                          </span>
                        </div>
                        <ChevronDownIcon
                          :class="[
                            'h-5 w-5 text-gray-400 transition-transform duration-200',
                            expandedRestoreSection[backup.id] === 'config' ? 'rotate-180' : ''
                          ]"
                        />
                      </button>

                      <!-- Section Content -->
                      <div v-if="expandedRestoreSection[backup.id] === 'config'" class="border-t border-emerald-100 dark:border-emerald-800">
                        <p class="text-sm text-secondary px-4 py-2 bg-emerald-50/50 dark:bg-emerald-900/10">
                          Click a file to see restore options. <span class="text-amber-600 dark:text-amber-400 font-medium">Restoring will backup existing files first.</span>
                        </p>

                        <!-- Config Files List -->
                        <div v-if="loadingConfigFiles.has(backup.id)" class="py-4 text-center">
                          <LoadingSpinner size="sm" text="Loading config files..." />
                        </div>
                        <div v-else-if="!backupConfigFiles[backup.id] || backupConfigFiles[backup.id].length === 0" class="py-4 text-center text-secondary">
                          No configuration files found in this backup
                        </div>
                        <div v-else class="max-h-64 overflow-y-auto">
                          <div
                            v-for="configFile in backupConfigFiles[backup.id]"
                            :key="configFile.path"
                            class="border-b border-gray-100 dark:border-gray-700 last:border-b-0"
                          >
                            <!-- Config File Item (Clickable) -->
                            <button
                              @click="toggleRestoreItem(backup.id, `cfg-${configFile.path}`)"
                              class="w-full p-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                            >
                              <div class="flex items-center gap-3">
                                <component
                                  :is="configFile.is_ssl ? ShieldCheckIcon : (configFile.name.endsWith('.env') ? KeyIcon : (configFile.name.includes('nginx') ? ServerIcon : (configFile.name.includes('docker') ? CubeIcon : DocumentIcon)))"
                                  :class="[
                                    'h-5 w-5',
                                    configFile.is_ssl ? 'text-green-500' : 'text-emerald-500'
                                  ]"
                                />
                                <div class="text-left">
                                  <p class="font-medium text-primary">{{ configFile.name }}</p>
                                  <p class="text-xs text-secondary">
                                    {{ formatFileSize(configFile.size) }}
                                    <span v-if="configFile.is_ssl" class="ml-1 text-green-600 dark:text-green-400">SSL Certificate</span>
                                  </p>
                                </div>
                              </div>
                              <ChevronDownIcon
                                :class="[
                                  'h-4 w-4 text-gray-400 transition-transform duration-200',
                                  isRestoreItemExpanded(backup.id, `cfg-${configFile.path}`) ? 'rotate-180' : ''
                                ]"
                              />
                            </button>

                            <!-- Config File Actions (Expanded) -->
                            <div
                              v-if="isRestoreItemExpanded(backup.id, `cfg-${configFile.path}`)"
                              class="px-4 py-3 bg-emerald-50 dark:bg-emerald-900/20 flex items-center gap-3"
                            >
                              <button
                                @click.stop="downloadConfigFile(backup, configFile)"
                                class="btn-secondary px-4 py-2 text-sm flex items-center gap-2 border border-blue-300 dark:border-blue-600 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/30"
                                title="Download file"
                              >
                                <DocumentArrowDownIcon class="h-4 w-4 text-blue-600" />
                                <span>Download</span>
                              </button>
                              <button
                                @click.stop="restoreConfigFile(backup, configFile)"
                                :disabled="restoringConfig === `${backup.id}-${configFile.path}`"
                                class="btn-primary px-4 py-2 text-sm flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-white"
                                title="Restore to system (backs up existing file first)"
                              >
                                <LoadingSpinner v-if="restoringConfig === `${backup.id}-${configFile.path}`" size="sm" />
                                <ArrowPathIcon v-else class="h-4 w-4" />
                                <span>Restore File</span>
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                    </template>
                  </div>

                  <!-- Bare Metal Panel -->
                  <div v-if="expandedAction[backup.id] === 'baremetal'" class="p-4">
                    <div class="bg-white dark:bg-gray-800 rounded-lg border border-purple-200 dark:border-purple-700 p-4">
                      <h4 class="font-semibold text-primary flex items-center gap-2 mb-2">
                        <ServerStackIcon class="h-5 w-5 text-purple-600 dark:text-purple-400" />
                        Bare Metal Recovery
                      </h4>
                      <p class="text-sm text-secondary mb-4">
                        Downloads a complete recovery archive containing databases, configuration files, SSL certificates, and a self-contained <code class="bg-gray-100 dark:bg-gray-700 px-1 rounded">restore.sh</code> script. Extract on any server and run the script to fully restore your n8n installation.
                      </p>
                      <button
                        @click="createBareMetalRecovery(backup)"
                        :disabled="creatingBareMetal === backup.id"
                        class="btn-primary bg-purple-600 hover:bg-purple-700 flex items-center gap-2"
                      >
                        <LoadingSpinner v-if="creatingBareMetal === backup.id" size="sm" />
                        <ArrowDownTrayIcon v-else class="h-4 w-4" />
                        {{ creatingBareMetal === backup.id ? 'Preparing...' : 'Download Recovery Archive' }}
                      </button>
                    </div>
                  </div>

                  <!-- Delete Panel -->
                  <div v-if="expandedAction[backup.id] === 'delete'" class="p-4">
                    <div class="bg-white dark:bg-gray-800 rounded-lg border border-red-200 dark:border-red-700 p-4">
                      <h4 class="font-semibold text-primary flex items-center gap-2 mb-2">
                        <TrashIcon class="h-5 w-5 text-red-600 dark:text-red-400" />
                        {{ backup.status === 'running' ? 'Cancel & Delete Backup' : 'Delete Backup' }}
                      </h4>
                      <p class="text-sm text-secondary mb-4">
                        {{ backup.status === 'running'
                          ? 'This backup appears to be stuck. Deleting will cancel the backup operation and remove the record.'
                          : 'This action cannot be undone. The backup file and all associated data will be permanently deleted.'
                        }}
                      </p>
                      <button
                        @click="openDeleteDialog(backup)"
                        :disabled="backup.is_protected"
                        class="btn-danger flex items-center gap-2"
                      >
                        <TrashIcon class="h-4 w-4" />
                        {{ backup.is_protected ? 'Unprotect First' : 'Delete Permanently' }}
                      </button>
                      <p v-if="backup.is_protected" class="text-xs text-amber-600 dark:text-amber-400 mt-2">
                        This backup is protected. Remove protection before deleting.
                      </p>
                    </div>
                  </div>
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

    <!-- Progress Modal -->
    <ProgressModal
      :show="progressModal.show"
      :type="progressModal.type"
      :progress="activeBackupProgress.progress || 0"
      :progress-message="activeBackupProgress.progress_message || ''"
      :status="progressModal.status"
      @close="closeProgressModal"
    />
  </div>
</template>
