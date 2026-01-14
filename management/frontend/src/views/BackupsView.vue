<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/views/BackupsView.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useThemeStore } from '../stores/theme'
import { useBackupStore } from '../stores/backups'
import { useNotificationStore } from '../stores/notifications'
import api from '../services/api'
import {
  formatBytes,
  formatDate,
  formatScheduleTime,
  formatScheduleTimeFromSchedule
} from '../utils/formatters'
import { usePoll } from '../composables/usePoll'
import { POLLING, TIMEOUTS, PAGINATION } from '../config/constants'
import Card from '../components/common/Card.vue'
import StatusBadge from '../components/common/StatusBadge.vue'
import LoadingSpinner from '../components/common/LoadingSpinner.vue'
import BackupScanLoader from '../components/common/BackupScanLoader.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import ProgressModal from '../components/backup-ui/ProgressModal.vue'
import BackupContents from '../components/backup-ui/BackupContents.vue'
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
  ExclamationTriangleIcon,
  EyeIcon,
  HashtagIcon,
  ClipboardDocumentListIcon,
} from '@heroicons/vue/24/outline'

const router = useRouter()
const themeStore = useThemeStore()
const backupStore = useBackupStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const runningBackup = ref(false)
const deleteDialog = ref({ open: false, backup: null, loading: false })
const protectedDeleteDialog = ref({ open: false, backup: null, loading: false })
const unprotectDialog = ref({ open: false, backup: null, loading: false })
const backupConfirmDialog = ref({ open: false, verifyAfterBackup: false })

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

// Credentials loaded for each backup
const backupCredentials = ref({})
const loadingCredentials = ref(new Set())

// Config files loaded for each backup
const backupConfigFiles = ref({})
const loadingConfigFiles = ref(new Set())

// Operation states
const verifyingBackup = ref(null)
const protectingBackup = ref(null)
const creatingBareMetal = ref(null)
const downloadingBackup = ref(null)
const restoringWorkflow = ref(null)
const restoringConfig = ref(null)

// Backup contents viewer
const backupContents = ref({})  // backupId -> contents data
const loadingContents = ref(new Set())
const contentsActiveTab = ref({})  // backupId -> 'workflows' | 'credentials' | 'config'

// Mount state
const mountedBackup = ref(null)  // { backup_id, backup_info, workflows }
const mountingBackup = ref(null)  // backup_id being mounted
const unmountingBackup = ref(false)

// Check if any backup is in progress
const hasRunningOperations = computed(() => {
  return backupStore.backups.some(b => b.status === 'running') ||
         verifyingBackup.value !== null ||
         runningBackup.value
})

const { start: startPolling, stop: stopPolling } = usePoll(async () => {
  if (hasRunningOperations.value) {
    await backupStore.fetchBackups()
  } else {
    stopPolling()
  }
}, POLLING.BACKUP_OPERATIONS, false)

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

// Backup schedules
const backupSchedules = ref([])

// Computed: primary schedule (first enabled schedule or first schedule)
const primarySchedule = computed(() => {
  if (!backupSchedules.value || backupSchedules.value.length === 0) {
    return null
  }
  // Prefer enabled schedules
  const enabled = backupSchedules.value.find(s => s.enabled)
  return enabled || backupSchedules.value[0]
})

// Filter and sort
const filterStatus = ref('all')
const sortBy = ref('date')
const dateFrom = ref('')
const dateTo = ref('')

// Page size options
const pageSizeOptions = PAGINATION.PAGE_SIZE_OPTIONS

const filteredBackups = computed(() => {
  let backups = [...backupStore.backups]

  // Sort (server already sorts by date desc, but we can re-sort by size locally)
  if (sortBy.value === 'size') {
    backups.sort((a, b) => (b.file_size || 0) - (a.file_size || 0))
  }

  return backups
})

// Stats - use totalBackups from store for accurate total count
const stats = computed(() => ({
  total: backupStore.totalBackups,
  successful: backupStore.backups.filter((b) => b.status === 'success').length,
  failed: backupStore.backups.filter((b) => b.status === 'failed').length,
  totalSize: backupStore.backups.reduce((sum, b) => sum + (b.file_size || 0), 0),
}))

// Apply filters to server
async function applyFilters() {
  const filters = {}
  if (filterStatus.value !== 'all') {
    filters.status = filterStatus.value
  }
  if (dateFrom.value) {
    filters.startDate = dateFrom.value
  }
  if (dateTo.value) {
    filters.endDate = dateTo.value
  }
  await backupStore.setFilters(filters)
}

// Clear all filters
async function clearAllFilters() {
  filterStatus.value = 'all'
  dateFrom.value = ''
  dateTo.value = ''
  await backupStore.clearFilters()
}

// Watch filter changes and apply them
watch([filterStatus], async () => {
  await applyFilters()
})

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
    // For 'contents' action, load the backup contents metadata
    if (action === 'contents') {
      loadBackupContents(backupId)
    }
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
    const response = await api.post(`/backups/${backupId}/mount`, {}, { timeout: TIMEOUTS.MOUNT_BACKUP }) // 10 minute timeout
    if (response.data.status === 'success') {
      mountedBackup.value = {
        backup_id: backupId,
        backup_info: response.data.backup_info,
        workflows: response.data.workflows || [],
        credentials: response.data.credentials || []
      }
      // Store workflows and credentials for this backup
      backupWorkflows.value[backupId] = response.data.workflows || []
      backupCredentials.value[backupId] = response.data.credentials || []
      const workflowCount = response.data.workflows?.length || 0
      const credentialCount = response.data.credentials?.length || 0
      notificationStore.success(`Backup mounted with ${workflowCount} workflows and ${credentialCount} credentials`)
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
    delete backupCredentials.value[backupId]
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

// Load backup contents metadata (for viewing without mounting)
async function loadBackupContents(backupId) {
  if (backupContents.value[backupId]) return // Already loaded

  loadingContents.value.add(backupId)
  try {
    const response = await api.get(`/backups/contents/${backupId}`)
    backupContents.value[backupId] = response.data
    // Set default tab
    if (!contentsActiveTab.value[backupId]) {
      contentsActiveTab.value[backupId] = 'workflows'
    }
  } catch (error) {
    console.error('Failed to load backup contents:', error)
    notificationStore.error('Failed to load backup contents. This backup may not have metadata stored.')
    backupContents.value[backupId] = null
  } finally {
    loadingContents.value.delete(backupId)
  }
}

// Set active tab for backup contents viewer
function setContentsTab(backupId, tab) {
  contentsActiveTab.value[backupId] = tab
}

function promptBackupNow() {
  backupConfirmDialog.value.open = true
}

async function runBackupNow() {
  const shouldVerify = backupConfirmDialog.value.verifyAfterBackup
  backupConfirmDialog.value.open = false
  runningBackup.value = true

  // Show progress modal
  progressModal.value = {
    show: true,
    type: 'backup',
    backupId: null,
    status: 'running'
  }

  try {
    // Always skip backend auto-verification for manual backups
    // Frontend handles verification separately when user selects "Verify after backup"
    const result = await backupStore.triggerBackup(true)
    // Set the backup ID so we can track progress
    if (result && result.backup_id) {
      progressModal.value.backupId = result.backup_id
    }

    // Poll for completion
    await pollForCompletion('backup')

    // If backup succeeded and verify option was selected, run verification
    if (shouldVerify && progressModal.value.status === 'success' && progressModal.value.backupId) {
      notificationStore.success('Backup completed. Starting verification...')

      // Brief pause to show backup success before switching to verify
      await new Promise(resolve => setTimeout(resolve, 1000))

      // Switch to verify mode
      progressModal.value.type = 'verify'
      progressModal.value.status = 'running'

      // Start polling for progress updates
      pollForProgress()

      // Call the verification API
      const verifyResult = await backupStore.verifyBackup(progressModal.value.backupId)

      // Update modal status based on result
      if (verifyResult.overall_status === 'passed') {
        progressModal.value.status = 'success'
        notificationStore.success('Backup and verification completed successfully')
      } else if (verifyResult.overall_status === 'failed' || verifyResult.error || verifyResult.errors?.length > 0) {
        progressModal.value.status = 'failed'
        const errorMsg = verifyResult.error || verifyResult.errors?.join(', ') || 'Verification failed'
        notificationStore.error(`Verification failed: ${errorMsg}`)
      } else if (verifyResult.warnings?.length > 0) {
        progressModal.value.status = 'success'
        const warnMsg = verifyResult.warnings.join(', ')
        notificationStore.warning(`Verification completed with warnings: ${warnMsg}`)
      } else {
        progressModal.value.status = 'failed'
        notificationStore.error('Verification failed: Unknown status')
      }

      // Final refresh
      await backupStore.fetchBackups()
    }

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
    } else if (result.overall_status === 'failed' || result.error || result.errors?.length > 0) {
      progressModal.value.status = 'failed'
      const errorMsg = result.error || result.errors?.join(', ') || 'Verification failed'
      notificationStore.error(`Backup verification failed: ${errorMsg}`)
    } else if (result.warnings?.length > 0) {
      progressModal.value.status = 'success' // Treat warnings-only as success
      const warnMsg = result.warnings.join(', ')
      notificationStore.warning(`Backup verification completed with warnings: ${warnMsg}`)
    } else {
      // Unknown status - treat as failure to be safe
      progressModal.value.status = 'failed'
      notificationStore.error('Backup verification failed: Unknown status')
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
  // If backup is protected, show the protected delete warning instead
  if (backup.is_protected) {
    protectedDeleteDialog.value = { open: true, backup, loading: false }
  } else {
    deleteDialog.value = { open: true, backup, loading: false }
  }
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

// Unprotect and Delete - for protected backups
async function unprotectAndDelete() {
  if (!protectedDeleteDialog.value.backup) return

  protectedDeleteDialog.value.loading = true
  try {
    // First unprotect the backup
    await backupStore.protectBackup(protectedDeleteDialog.value.backup.id, false, null)
    // Close the protected dialog
    protectedDeleteDialog.value.open = false
    // Now open the normal delete dialog
    deleteDialog.value = { open: true, backup: protectedDeleteDialog.value.backup, loading: false }
  } catch (error) {
    notificationStore.error('Failed to unprotect backup')
  } finally {
    protectedDeleteDialog.value.loading = false
  }
}

// Protect Backup
async function protectBackup(backup) {
  protectingBackup.value = backup.id
  try {
    await backupStore.protectBackup(backup.id, true, 'Protected via UI')
    notificationStore.success('Backup protected')
    await loadData()
    // Close the action panel
    expandedAction.value[backup.id] = null
  } catch (error) {
    notificationStore.error('Failed to protect backup')
  } finally {
    protectingBackup.value = null
  }
}

// Open unprotect confirmation dialog
function openUnprotectDialog(backup) {
  unprotectDialog.value = { open: true, backup, loading: false }
}

// Confirm unprotect
async function confirmUnprotect() {
  if (!unprotectDialog.value.backup) return

  unprotectDialog.value.loading = true
  try {
    await backupStore.protectBackup(unprotectDialog.value.backup.id, false, null)
    notificationStore.success('Backup unprotected - now eligible for automatic pruning')
    unprotectDialog.value.open = false
    await loadData()
    // Close the action panel
    expandedAction.value[unprotectDialog.value.backup.id] = null
  } catch (error) {
    notificationStore.error('Failed to unprotect backup')
  } finally {
    unprotectDialog.value.loading = false
  }
}

// Download Workflow JSON
async function downloadWorkflow(backup, workflow) {
  try {
    const response = await api.get(`/backups/${backup.id}/workflows/${workflow.id}/download`)
    const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' })
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

// Download Credential JSON
async function downloadCredential(backup, credential) {
  try {
    const response = await api.get(`/backups/${backup.id}/credentials/${credential.id}/download`)
    const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${credential.name || 'credential'}_${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    notificationStore.success(`Downloaded credential: ${credential.name}`)
  } catch (error) {
    notificationStore.error('Failed to download credential')
  }
}

// Restore Workflow to n8n via API
async function restoreWorkflowToN8n(backup, workflow) {
  restoringWorkflow.value = `${backup.id}-${workflow.id}`
  try {
    const response = await api.post(`/backups/${backup.id}/restore/workflow`, {
      workflow_id: workflow.id,
      rename_format: '{name}_backup_{date}',
    }, { timeout: TIMEOUTS.LONG_RUNNING }) // 5 minute timeout
    if (response.data.status === 'success') {
      notificationStore.success(`Restored workflow: ${response.data.new_name}`)
    } else {
      notificationStore.error(response.data.error || 'Failed to restore workflow')
    }
  } catch (error) {
    const errorMsg = error.response?.data?.detail || error.response?.data?.error || 'Failed to restore workflow to n8n'
    notificationStore.error(errorMsg)
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
    }, { timeout: TIMEOUTS.LONG_RUNNING }) // 5 minute timeout
    if (response.data.status === 'success') {
      notificationStore.success(`Restored ${configFile.name}. Original backed up to ${response.data.backup_created || 'backup file'}`)
    } else {
      notificationStore.error(response.data.error || 'Failed to restore config file')
    }
  } catch (error) {
    const errorMsg = error.response?.data?.detail || error.response?.data?.error || 'Failed to restore config file'
    notificationStore.error(errorMsg)
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
    // Extract just the filename (handles SSL files like "domain.com/fullchain.pem")
    // Browsers can't create files with "/" in the name
    const filename = configFile.name.includes('/')
      ? configFile.name.split('/').pop()
      : configFile.name
    a.download = filename
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

// Bare Metal Recovery - Download complete archive with restore.sh
async function createBareMetalRecovery(backup) {
  creatingBareMetal.value = backup.id
  try {
    // Download the backup file (which already includes restore.sh)
    const response = await api.get(`/backups/download/${backup.id}`, {
      responseType: 'blob',
      timeout: TIMEOUTS.LONG_RUNNING // 5 minutes
    })

    // Create download link - same method as EnvironmentSettings
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
    console.error('Download error:', error)
    const errorMsg = error.response?.data?.detail || error.message || 'Unknown error'
    notificationStore.error(`Failed to download recovery archive: ${errorMsg}`)
  } finally {
    creatingBareMetal.value = null
  }
}

// Download Backup Data Only (without restore scripts)
async function downloadBackupData(backup) {
  downloadingBackup.value = backup.id
  try {
    // Download data-only archive (excludes restore.sh)
    // Use 5-minute timeout for large backup files
    const response = await api.get(`/backups/download/${backup.id}/data-only`, {
      responseType: 'blob',
      timeout: TIMEOUTS.LONG_RUNNING // 5 minutes
    })

    // Create download link
    const blob = new Blob([response.data], { type: 'application/gzip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    // Generate filename without restore script indicator
    const filename = backup.filename?.replace('.n8n_backup.tar.gz', '.data.tar.gz') ||
                     backup.filename?.replace('.tar.gz', '.data.tar.gz') ||
                     `backup_${backup.id}.data.tar.gz`
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    notificationStore.success('Backup data downloaded successfully.')
  } catch (error) {
    const errorMsg = error.response?.data?.detail || error.message || 'Unknown error'
    notificationStore.error(`Failed to download backup: ${errorMsg}`)
  } finally {
    downloadingBackup.value = null
  }
}

async function loadData() {
  loading.value = true
  try {
    await backupStore.fetchBackups()
    // Fetch backup configuration and schedules
    try {
      backupConfig.value = await backupStore.fetchConfiguration()
    } catch (err) {
      console.error('Failed to fetch backup configuration:', err)
    }
    try {
      await backupStore.fetchSchedules()
      backupSchedules.value = backupStore.schedules
    } catch (err) {
      console.error('Failed to fetch backup schedules:', err)
    }
    // Check if a backup is already mounted (e.g., from previous session)
    try {
      const mountStatus = await api.get('/backups/mount/status')
      if (mountStatus.data.mounted && mountStatus.data.backup_id) {
        mountedBackup.value = {
          backup_id: mountStatus.data.backup_id,
          backup_info: mountStatus.data.backup_info,
          workflows: mountStatus.data.workflows || [],
          credentials: mountStatus.data.credentials || []
        }
        // Store workflows and credentials for the mounted backup
        if (mountStatus.data.workflows) {
          backupWorkflows.value[mountStatus.data.backup_id] = mountStatus.data.workflows
        }
        if (mountStatus.data.credentials) {
          backupCredentials.value[mountStatus.data.backup_id] = mountStatus.data.credentials
        }
      }
    } catch (err) {
      console.error('Failed to check mount status:', err)
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
            'text-primary'
          ]"
        >
          Backups
        </h1>
        <p class="text-secondary mt-1">Manage database and workflow backups</p>
      </div>
      <div class="flex items-center gap-3">
        <!-- Unmount Button - Shows when a backup is mounted -->
        <button
          v-if="mountedBackup"
          @click="unmountBackup()"
          :disabled="unmountingBackup"
          class="flex items-center gap-2 px-4 py-2 bg-amber-100 dark:bg-amber-500/20 border border-amber-400 dark:border-amber-500 text-amber-700 dark:text-amber-300 rounded-lg hover:bg-amber-200 dark:hover:bg-amber-500/30 transition-colors font-medium"
        >
          <LoadingSpinner v-if="unmountingBackup" size="sm" />
          <XCircleIcon v-else class="h-4 w-4" />
          {{ unmountingBackup ? 'Unmounting...' : 'Unmount Backup' }}
        </button>
        <button
          @click="router.push('/backup-settings')"
          class="btn-secondary flex items-center gap-2"
        >
          <Cog6ToothIcon class="h-4 w-4" />
          Configure
        </button>
        <button
          @click="promptBackupNow"
          :disabled="runningBackup"
          :class="[
            'btn-primary flex items-center gap-2',
            ''
          ]"
        >
          <PlayIcon class="h-4 w-4" />
          {{ runningBackup ? 'Running...' : 'Backup Now' }}
        </button>
      </div>
    </div>

    <!-- Cool Backup Loading Animation -->
    <div v-if="loading" class="py-16 flex flex-col items-center justify-center">
      <div class="relative flex items-center gap-8">
        <!-- Source Database -->
        <div class="relative">
          <div class="w-16 h-20 rounded-lg bg-gradient-to-br from-blue-100 to-blue-200 dark:from-blue-900/40 dark:to-blue-800/40 border-2 border-blue-300 dark:border-blue-700 flex items-center justify-center shadow-lg">
            <CircleStackIcon class="h-8 w-8 text-blue-600 dark:text-blue-400" />
          </div>
          <div class="absolute -bottom-1 left-1/2 transform -translate-x-1/2 w-12 h-1.5 bg-blue-300 dark:bg-blue-700 rounded-full"></div>
        </div>

        <!-- Animated Files -->
        <div class="relative w-24 h-8 overflow-hidden">
          <div class="backup-file-animation absolute flex items-center gap-1">
            <DocumentTextIcon class="h-5 w-5 text-emerald-500" />
            <DocumentTextIcon class="h-4 w-4 text-blue-500" />
            <DocumentTextIcon class="h-5 w-5 text-purple-500" />
          </div>
          <div class="absolute inset-0 flex items-center justify-center">
            <div class="w-full h-0.5 bg-gradient-to-r from-blue-300 via-emerald-300 to-blue-300 dark:from-blue-700 dark:via-emerald-700 dark:to-blue-700 opacity-50"></div>
          </div>
        </div>

        <!-- Destination Drive -->
        <div class="relative">
          <div class="w-16 h-20 rounded-lg bg-gradient-to-br from-emerald-100 to-emerald-200 dark:from-emerald-900/40 dark:to-emerald-800/40 border-2 border-emerald-300 dark:border-emerald-700 flex items-center justify-center shadow-lg animate-pulse">
            <ArchiveBoxIcon class="h-8 w-8 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div class="absolute -bottom-1 left-1/2 transform -translate-x-1/2 w-12 h-1.5 bg-emerald-300 dark:bg-emerald-700 rounded-full"></div>
        </div>
      </div>
      <p class="mt-6 text-sm font-medium text-secondary">Loading backups...</p>
      <p class="mt-1 text-xs text-muted">Fetching backup history</p>
    </div>

    <template v-else>
      <!-- Stats Grid -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card :padding="false">
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

        <Card :padding="false">
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

        <Card :padding="false">
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

        <Card :padding="false">
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
      <Card v-if="backupConfig" :padding="false" class="mt-4">
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
              <p v-if="backupConfig.storage_preference === 'nfs' && backupConfig.backup_workflow === 'stage_then_copy' && backupConfig.primary_storage_path" class="text-xs text-secondary mt-0.5 font-mono truncate">
                {{ backupConfig.primary_storage_path }}
              </p>
            </div>
          </div>
        </button>
      </Card>

      <!-- Schedule Card (Clickable - navigates to schedule settings) -->
      <Card :padding="false">
        <button
          @click="router.push('/backup-settings?tab=schedule')"
          class="w-full text-left hover:bg-surface-hover transition-colors rounded-lg"
        >
          <div class="p-4 flex items-center justify-between gap-4">
            <!-- Left: Icon and Schedule Info -->
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-gradient-to-br from-indigo-100 to-indigo-100 dark:from-indigo-500/20 dark:to-indigo-500/20">
                <CalendarIcon class="h-5 w-5 text-indigo-500" />
              </div>
              <div>
                <h3 class="font-semibold text-primary">Backup Schedule</h3>
                <p v-if="primarySchedule" class="text-sm text-secondary">
                  {{ primarySchedule.frequency }} at {{ formatScheduleTimeFromSchedule(primarySchedule) }}
                </p>
                <p v-else class="text-sm text-secondary">
                  No schedule configured
                </p>
              </div>
            </div>

            <!-- Center: Compact Retention Bars -->
            <div class="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/50">
              <span class="text-xs font-medium text-gray-500 dark:text-gray-400 mr-1">Retention Policy</span>
              <div class="bg-gradient-to-r from-emerald-500 to-teal-500 px-2.5 py-1 rounded text-xs font-semibold text-white">
                Daily {{ backupConfig?.retention_daily_count || 7 }}
              </div>
              <div class="bg-gradient-to-r from-blue-500 to-indigo-500 px-2.5 py-1 rounded text-xs font-semibold text-white">
                Weekly {{ backupConfig?.retention_weekly_count || 4 }}
              </div>
              <div class="bg-gradient-to-r from-purple-500 to-pink-500 px-2.5 py-1 rounded text-xs font-semibold text-white">
                Monthly {{ backupConfig?.retention_monthly_count || 6 }}
              </div>
            </div>

            <!-- Right: Status Badge -->
            <StatusBadge :status="primarySchedule?.enabled ? 'enabled' : 'disabled'" />
          </div>
        </button>
      </Card>

      <!-- Backup History - Collapsible Section -->
      <Card :padding="false">
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
              <p class="text-sm text-secondary">{{ backupStore.totalBackups }} backup(s) available</p>
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
          <div class="p-4 flex flex-wrap items-center gap-4 bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
            <!-- Status Filter -->
            <select v-model="filterStatus" class="select-field">
              <option value="all">All Statuses</option>
              <option value="success">Successful</option>
              <option value="failed">Failed</option>
              <option value="running">Running</option>
              <option value="pending">Pending</option>
            </select>

            <!-- Date Range Filter -->
            <div class="flex items-center gap-2">
              <label class="text-sm text-secondary">From:</label>
              <input
                v-model="dateFrom"
                type="date"
                class="input-field text-sm py-1.5"
                @change="applyFilters"
              />
            </div>
            <div class="flex items-center gap-2">
              <label class="text-sm text-secondary">To:</label>
              <input
                v-model="dateTo"
                type="date"
                class="input-field text-sm py-1.5"
                @change="applyFilters"
              />
            </div>

            <!-- Clear Filters Button -->
            <button
              v-if="filterStatus !== 'all' || dateFrom || dateTo"
              @click="clearAllFilters"
              class="text-sm text-blue-600 dark:text-blue-400 hover:underline"
            >
              Clear filters
            </button>

            <!-- Spacer -->
            <div class="flex-1"></div>

            <!-- Page Size Selector -->
            <div class="flex items-center gap-2">
              <label class="text-sm text-secondary">Show:</label>
              <select
                :value="backupStore.pagination.limit"
                @change="backupStore.setPageSize(Number($event.target.value))"
                class="select-field text-sm py-1.5"
              >
                <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}</option>
              </select>
            </div>

            <!-- Sort -->
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

                  <!-- View Backup Contents Button -->
                  <button
                    v-if="backup.status === 'success'"
                    @click="toggleAction(backup.id, 'contents')"
                    :class="[
                      'flex items-center gap-2 px-4 py-2 rounded-lg border transition-all',
                      expandedAction[backup.id] === 'contents'
                        ? 'bg-cyan-100 dark:bg-cyan-500/20 border-cyan-400 dark:border-cyan-500 text-cyan-700 dark:text-cyan-300'
                        : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:border-cyan-300 dark:hover:border-cyan-500 hover:bg-cyan-50 dark:hover:bg-cyan-500/10'
                    ]"
                  >
                    <EyeIcon class="h-5 w-5 text-cyan-600 dark:text-cyan-400" />
                    <span class="font-medium">View Backup Contents</span>
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

                  <!-- Download Backup Button (data only, no restore scripts) -->
                  <button
                    v-if="backup.status === 'success'"
                    @click="downloadBackupData(backup)"
                    :disabled="downloadingBackup === backup.id"
                    class="flex items-center gap-2 px-4 py-2 rounded-lg border transition-all bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:border-sky-300 dark:hover:border-sky-500 hover:bg-sky-50 dark:hover:bg-sky-500/10"
                  >
                    <LoadingSpinner v-if="downloadingBackup === backup.id" size="sm" />
                    <ArrowDownTrayIcon v-else class="h-5 w-5 text-sky-600 dark:text-sky-400" />
                    <span class="font-medium">{{ downloadingBackup === backup.id ? 'Downloading...' : 'Download Backup' }}</span>
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
                    @click="backup.is_protected ? openDeleteDialog(backup) : toggleAction(backup.id, 'delete')"
                    :class="[
                      'flex items-center gap-2 px-4 py-2 rounded-lg border transition-all',
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
                        {{ backup.is_protected ? 'Remove Backup Protection' : 'Protect Backup' }}
                      </h4>
                      <!-- Protect Mode -->
                      <template v-if="!backup.is_protected">
                        <p class="text-sm text-secondary mb-4">
                          Protected backups are never automatically deleted by retention policies or pruning.
                          They also cannot be manually deleted until protection is removed.
                        </p>
                        <button
                          @click="protectBackup(backup)"
                          :disabled="protectingBackup === backup.id"
                          class="btn-primary bg-amber-600 hover:bg-amber-700 flex items-center gap-2"
                        >
                          <LoadingSpinner v-if="protectingBackup === backup.id" size="sm" />
                          <ShieldCheckIcon v-else class="h-4 w-4" />
                          {{ protectingBackup === backup.id ? 'Protecting...' : 'Protect This Backup' }}
                        </button>
                      </template>
                      <!-- Unprotect Mode -->
                      <template v-else>
                        <div class="p-3 mb-4 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700">
                          <div class="flex gap-2">
                            <ExclamationTriangleIcon class="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                            <div class="text-sm text-amber-700 dark:text-amber-400">
                              <p class="font-medium">Warning: Removing protection</p>
                              <p class="mt-1">This backup will become eligible for automatic pruning based on your retention policy settings.</p>
                            </div>
                          </div>
                        </div>
                        <button
                          @click="openUnprotectDialog(backup)"
                          :disabled="protectingBackup === backup.id"
                          class="btn-secondary text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-600 hover:bg-amber-50 dark:hover:bg-amber-900/30 flex items-center gap-2"
                        >
                          <ShieldCheckIcon class="h-4 w-4" />
                          Remove Protection
                        </button>
                      </template>
                    </div>
                  </div>

                  <!-- View Backup Contents Panel -->
                  <div v-if="expandedAction[backup.id] === 'contents'" class="p-4">
                    <BackupContents
                      :backup="backup"
                      :contents="backupContents[backup.id]"
                      :loading="loadingContents.has(backup.id)"
                      :active-tab="contentsActiveTab[backup.id] || 'workflows'"
                      @update:active-tab="(tab) => setContentsTab(backup.id, tab)"
                    />
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
                                      <span :class="workflow.archived ? 'text-amber-600 dark:text-amber-400' : ''">
                                        {{ workflow.archived ? 'Archived' : (workflow.active ? 'Active' : 'Inactive') }}
                                      </span>
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

                    <!-- Credentials Section (Collapsible) -->
                    <div class="bg-white dark:bg-gray-800 rounded-lg border border-amber-200 dark:border-amber-700 overflow-hidden">
                      <!-- Section Header (Clickable) -->
                      <button
                        @click="toggleRestoreSection(backup.id, 'credentials')"
                        class="w-full p-4 flex items-center justify-between hover:bg-amber-50 dark:hover:bg-amber-900/20 transition-colors"
                      >
                        <div class="flex items-center gap-2">
                          <KeyIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
                          <span class="font-semibold text-primary">Credentials</span>
                          <span v-if="backupCredentials[backup.id]" class="text-xs text-secondary bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded-full">
                            {{ backupCredentials[backup.id].length }}
                          </span>
                        </div>
                        <ChevronDownIcon
                          :class="[
                            'h-5 w-5 text-gray-400 transition-transform duration-200',
                            expandedRestoreSection[backup.id] === 'credentials' ? 'rotate-180' : ''
                          ]"
                        />
                      </button>

                      <!-- Section Content -->
                      <div v-if="expandedRestoreSection[backup.id] === 'credentials'" class="border-t border-amber-100 dark:border-amber-800">
                        <p class="text-sm text-secondary px-4 py-2 bg-amber-50/50 dark:bg-amber-900/10">
                          Click a credential to download. <span class="text-amber-600 dark:text-amber-400 font-medium">Note: Credential data is encrypted and may need reconfiguration after import.</span>
                        </p>

                        <!-- Credentials List -->
                        <div v-if="!backupCredentials[backup.id] || backupCredentials[backup.id].length === 0" class="py-4 text-center text-secondary">
                          No credentials found in this backup
                        </div>
                        <div v-else class="max-h-64 overflow-y-auto">
                          <div
                            v-for="credential in backupCredentials[backup.id]"
                            :key="credential.id"
                            class="border-b border-gray-100 dark:border-gray-700 last:border-b-0"
                          >
                            <!-- Credential Item (Clickable) -->
                            <button
                              @click="toggleRestoreItem(backup.id, `cred-${credential.id}`)"
                              class="w-full p-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                            >
                              <div class="flex items-center gap-3">
                                <KeyIcon class="h-5 w-5 text-amber-500" />
                                <div class="text-left">
                                  <p class="font-medium text-primary">{{ credential.name }}</p>
                                  <p class="text-xs text-secondary">
                                    {{ credential.type }}
                                    <span v-if="credential.updated_at"> • {{ new Date(credential.updated_at).toLocaleDateString() }}</span>
                                  </p>
                                </div>
                              </div>
                              <ChevronDownIcon
                                :class="[
                                  'h-4 w-4 text-gray-400 transition-transform duration-200',
                                  isRestoreItemExpanded(backup.id, `cred-${credential.id}`) ? 'rotate-180' : ''
                                ]"
                              />
                            </button>

                            <!-- Credential Actions (Expanded) -->
                            <div
                              v-if="isRestoreItemExpanded(backup.id, `cred-${credential.id}`)"
                              class="px-4 py-3 bg-amber-50 dark:bg-amber-900/20 flex items-center gap-3"
                            >
                              <button
                                @click.stop="downloadCredential(backup, credential)"
                                class="btn-secondary px-4 py-2 text-sm flex items-center gap-2 border border-blue-300 dark:border-blue-600 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/30"
                                title="Download as JSON file"
                              >
                                <DocumentArrowDownIcon class="h-4 w-4 text-blue-600" />
                                <span>Download JSON</span>
                              </button>
                              <span class="text-xs text-secondary italic">
                                Import manually via n8n CLI or reconfigure after restore
                              </span>
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
                      <!-- Protected Backup Warning -->
                      <template v-if="backup.is_protected">
                        <h4 class="font-semibold text-primary flex items-center gap-2 mb-2">
                          <ShieldCheckIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
                          Protected Backup
                        </h4>
                        <div class="p-3 mb-4 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700">
                          <div class="flex gap-2">
                            <ExclamationTriangleIcon class="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                            <div class="text-sm text-amber-700 dark:text-amber-400">
                              <p class="font-medium">This backup is protected</p>
                              <p class="mt-1">Protected backups cannot be deleted. You must first remove protection before this backup can be deleted.</p>
                            </div>
                          </div>
                        </div>
                        <button
                          @click="openDeleteDialog(backup)"
                          class="btn-danger flex items-center gap-2"
                        >
                          <TrashIcon class="h-4 w-4" />
                          Delete Protected Backup...
                        </button>
                      </template>
                      <!-- Normal Delete -->
                      <template v-else>
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
                          class="btn-danger flex items-center gap-2"
                        >
                          <TrashIcon class="h-4 w-4" />
                          Delete Permanently
                        </button>
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Pagination Controls -->
          <div
            v-if="backupStore.totalBackups > 0"
            class="p-4 flex items-center justify-between border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50"
          >
            <div class="text-sm text-secondary">
              Showing {{ backupStore.pagination.offset + 1 }} - {{ Math.min(backupStore.pagination.offset + filteredBackups.length, backupStore.totalBackups) }} of {{ backupStore.totalBackups }} backups
            </div>
            <div class="flex items-center gap-2">
              <!-- First Page -->
              <button
                @click="backupStore.goToPage(1)"
                :disabled="!backupStore.hasPrevPage"
                class="px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                title="First page"
              >
                ««
              </button>
              <!-- Previous Page -->
              <button
                @click="backupStore.prevPage"
                :disabled="!backupStore.hasPrevPage"
                class="px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                Previous
              </button>
              <!-- Page Info -->
              <span class="px-3 py-1.5 text-sm text-secondary">
                Page {{ backupStore.currentPage }} of {{ backupStore.totalPages }}
              </span>
              <!-- Next Page -->
              <button
                @click="backupStore.nextPage"
                :disabled="!backupStore.hasNextPage"
                class="px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                Next
              </button>
              <!-- Last Page -->
              <button
                @click="backupStore.goToPage(backupStore.totalPages)"
                :disabled="!backupStore.hasNextPage"
                class="px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                title="Last page"
              >
                »»
              </button>
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

    <!-- Protected Backup Delete Warning Dialog (Skull and Crossbones) -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="protectedDeleteDialog.open"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/50" @click="protectedDeleteDialog.open = false" />
          <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-md w-full border-2 border-red-500 dark:border-red-600">
            <!-- Header with skull icon -->
            <div class="px-6 py-5 bg-red-50 dark:bg-red-900/30 rounded-t-lg border-b border-red-200 dark:border-red-700">
              <div class="flex items-center justify-center mb-3">
                <div class="p-4 rounded-full bg-red-100 dark:bg-red-800/50">
                  <!-- Skull and Crossbones SVG -->
                  <svg class="h-12 w-12 text-red-600 dark:text-red-400" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h1v1c0 .55.45 1 1 1h2c.55 0 1-.45 1-1v-1h1c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7zM9 11c-.83 0-1.5-.67-1.5-1.5S8.17 8 9 8s1.5.67 1.5 1.5S9.83 11 9 11zm6 0c-.83 0-1.5-.67-1.5-1.5S14.17 8 15 8s1.5.67 1.5 1.5S15.83 11 15 11z"/>
                    <path d="M4 21l2-2M20 21l-2-2M4 21l-1 1M20 21l1 1M6 19l-2-2M18 19l2-2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                </div>
              </div>
              <h3 class="text-xl font-bold text-red-800 dark:text-red-300 text-center">
                Delete Protected Backup
              </h3>
            </div>

            <!-- Content -->
            <div class="px-6 py-5 bg-white dark:bg-gray-800">
              <div class="p-4 mb-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700">
                <div class="flex gap-3">
                  <ExclamationTriangleIcon class="h-6 w-6 text-red-600 flex-shrink-0" />
                  <div class="text-sm text-red-700 dark:text-red-400">
                    <p class="font-bold">Warning: Protected Backup</p>
                    <p class="mt-2">You are attempting to delete a <span class="font-semibold">protected backup</span>. This backup was marked as protected to prevent accidental deletion.</p>
                  </div>
                </div>
              </div>

              <p class="text-gray-600 dark:text-gray-400 text-sm">
                To delete this backup, you must first remove its protection. This action will:
              </p>
              <ul class="mt-2 space-y-1 text-sm text-gray-600 dark:text-gray-400">
                <li class="flex items-center gap-2">
                  <span class="text-red-500">•</span>
                  Remove protection from this backup
                </li>
                <li class="flex items-center gap-2">
                  <span class="text-red-500">•</span>
                  Proceed to the delete confirmation
                </li>
              </ul>
            </div>

            <!-- Footer -->
            <div class="px-6 py-4 bg-gray-50 dark:bg-gray-700/50 rounded-b-lg flex justify-end gap-3">
              <button
                @click="protectedDeleteDialog.open = false"
                class="btn-secondary"
              >
                Cancel
              </button>
              <button
                @click="unprotectAndDelete"
                :disabled="protectedDeleteDialog.loading"
                class="btn-danger flex items-center gap-2"
              >
                <LoadingSpinner v-if="protectedDeleteDialog.loading" size="sm" />
                <TrashIcon v-else class="h-4 w-4" />
                {{ protectedDeleteDialog.loading ? 'Processing...' : 'Unprotect and Delete' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Unprotect Confirmation Dialog -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="unprotectDialog.open"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/50" @click="unprotectDialog.open = false" />
          <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-md w-full border border-amber-400 dark:border-amber-500">
            <!-- Header -->
            <div class="px-6 py-5 bg-amber-50 dark:bg-amber-900/30 rounded-t-lg border-b border-amber-200 dark:border-amber-700">
              <div class="flex items-center justify-center mb-3">
                <div class="p-4 rounded-full bg-amber-100 dark:bg-amber-800/50">
                  <ShieldCheckIcon class="h-10 w-10 text-amber-600 dark:text-amber-400" />
                </div>
              </div>
              <h3 class="text-xl font-bold text-amber-800 dark:text-amber-300 text-center">
                Remove Backup Protection
              </h3>
            </div>

            <!-- Content -->
            <div class="px-6 py-5 bg-white dark:bg-gray-800">
              <div class="p-4 mb-4 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700">
                <div class="flex gap-3">
                  <ExclamationTriangleIcon class="h-6 w-6 text-amber-600 flex-shrink-0" />
                  <div class="text-sm text-amber-700 dark:text-amber-400">
                    <p class="font-bold">Warning: Removing Protection</p>
                    <p class="mt-2">Once protection is removed, this backup will become eligible for automatic pruning based on your retention policy settings.</p>
                  </div>
                </div>
              </div>

              <p class="text-gray-600 dark:text-gray-400 text-sm text-center">
                Are you sure you want to remove protection from this backup?
              </p>
            </div>

            <!-- Footer -->
            <div class="px-6 py-4 bg-gray-50 dark:bg-gray-700/50 rounded-b-lg flex justify-end gap-3">
              <button
                @click="unprotectDialog.open = false"
                class="btn-secondary"
              >
                Cancel
              </button>
              <button
                @click="confirmUnprotect"
                :disabled="unprotectDialog.loading"
                class="px-4 py-2 rounded-lg font-medium bg-amber-600 hover:bg-amber-700 text-white flex items-center gap-2 transition-colors"
              >
                <LoadingSpinner v-if="unprotectDialog.loading" size="sm" />
                <ShieldCheckIcon v-else class="h-4 w-4" />
                {{ unprotectDialog.loading ? 'Processing...' : 'Remove Protection' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Backup Confirmation Dialog -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="backupConfirmDialog.open"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/50" @click="backupConfirmDialog.open = false" />
          <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-md w-full border border-amber-400 dark:border-amber-500">
            <!-- Header with warning icon -->
            <div class="px-6 py-5 bg-amber-50 dark:bg-amber-900/30 rounded-t-lg border-b border-amber-200 dark:border-amber-700">
              <div class="flex items-center justify-center mb-3">
                <div class="p-4 rounded-full bg-amber-100 dark:bg-amber-800/50">
                  <!-- Warning Triangle with Exclamation -->
                  <svg class="h-12 w-12" viewBox="0 0 24 24" fill="none">
                    <path d="M12 2L1 21h22L12 2z" fill="#FCD34D" stroke="#F59E0B" stroke-width="1.5"/>
                    <path d="M12 9v5" stroke="#DC2626" stroke-width="2.5" stroke-linecap="round"/>
                    <circle cx="12" cy="17" r="1.25" fill="#DC2626"/>
                  </svg>
                </div>
              </div>
              <h3 class="text-xl font-bold text-amber-800 dark:text-amber-300 text-center">
                Backup Notice
              </h3>
            </div>

            <!-- Content -->
            <div class="px-6 py-5 bg-white dark:bg-gray-800">
              <p class="text-gray-700 dark:text-gray-300 text-center">
                This backup system only backs up:
              </p>
              <ul class="mt-3 space-y-2 text-sm">
                <li class="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                  <CheckCircleIcon class="h-5 w-5 text-emerald-500 flex-shrink-0" />
                  <span><span class="font-semibold text-gray-800 dark:text-gray-200">N8N Workflows</span> and credentials</span>
                </li>
                <li class="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                  <CheckCircleIcon class="h-5 w-5 text-emerald-500 flex-shrink-0" />
                  <span><span class="font-semibold text-gray-800 dark:text-gray-200">N8N Management</span> configuration files</span>
                </li>
              </ul>
              <div class="mt-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700">
                <p class="text-sm text-red-700 dark:text-red-400 flex items-start gap-2">
                  <XCircleIcon class="h-5 w-5 flex-shrink-0 mt-0.5" />
                  <span>Does <span class="font-bold">NOT</span> backup other data, additional containers, or custom configuration files you may have added.</span>
                </p>
              </div>

              <!-- Verify After Backup Toggle -->
              <div class="mt-4 p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700">
                <label class="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    v-model="backupConfirmDialog.verifyAfterBackup"
                    class="w-5 h-5 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500 dark:bg-gray-700"
                  />
                  <div class="flex-1">
                    <span class="text-sm font-medium text-blue-800 dark:text-blue-300">Verify after backup</span>
                    <p class="text-xs text-blue-600 dark:text-blue-400 mt-0.5">
                      Automatically run verification to ensure backup integrity
                    </p>
                  </div>
                  <ShieldCheckIcon class="h-5 w-5 text-blue-500 flex-shrink-0" />
                </label>
              </div>
            </div>

            <!-- Actions -->
            <div class="px-6 py-4 bg-gray-50 dark:bg-gray-900/50 rounded-b-lg flex gap-3">
              <button
                @click="backupConfirmDialog.open = false"
                class="flex-1 btn-secondary"
              >
                Cancel
              </button>
              <button
                @click="runBackupNow"
                class="flex-1 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-medium transition-colors flex items-center justify-center gap-2"
              >
                <PlayIcon class="h-4 w-4" />
                {{ backupConfirmDialog.verifyAfterBackup ? 'Backup & Verify' : 'Start Backup' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

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

<style scoped>
/* Backup file animation */
.backup-file-animation {
  animation: moveBackupFiles 1.8s ease-in-out infinite;
}

@keyframes moveBackupFiles {
  0% {
    transform: translateX(-120%);
    opacity: 0;
  }
  15% {
    opacity: 1;
  }
  85% {
    opacity: 1;
  }
  100% {
    transform: translateX(120%);
    opacity: 0;
  }
}
</style>
