<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/settings/EnvironmentSettings.vue

Environment Configuration Settings Component
Manages .env file variables with health checks, backups, and warnings

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref, onMounted, computed } from 'vue'
import { useNotificationStore } from '@/stores/notifications'
import { useBackupStore } from '@/stores/backups'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import ProgressModal from '@/components/backup-ui/ProgressModal.vue'
import {
  ExclamationCircleIcon,
  CircleStackIcon,
  ShieldCheckIcon,
  Cog6ToothIcon,
  ServerIcon,
  CloudIcon,
  GlobeAltIcon,
  CubeIcon,
  BellIcon,
  CodeBracketIcon,
  PlusCircleIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  EyeIcon,
  EyeSlashIcon,
  PencilSquareIcon,
  TrashIcon,
  ArrowPathIcon,
  ShieldExclamationIcon,
  InformationCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  PlusIcon,
  BeakerIcon,
  ArchiveBoxIcon,
  ArrowUturnLeftIcon,
  ClockIcon,
  ArrowDownTrayIcon,
  QuestionMarkCircleIcon,
  DocumentTextIcon,
  XMarkIcon,
  PlayIcon,
} from '@heroicons/vue/24/outline'

const notificationStore = useNotificationStore()
const backupStore = useBackupStore()

// Backup Confirm Dialog - same as BackupsView
const backupConfirmDialog = ref({ open: false, verifyAfterBackup: false })

// Progress Modal State for backup operations
const progressModal = ref({
  show: false,
  type: 'backup', // 'backup' or 'verify'
  backupId: null,
  status: 'running' // 'running', 'success', 'failed'
})

// Get progress data for the active operation from backup store
const activeBackupProgress = computed(() => {
  if (!progressModal.value.backupId) return { progress: 0, progress_message: '' }
  const backup = backupStore.backups.find(b => b.id === progressModal.value.backupId)
  return backup || { progress: 0, progress_message: '' }
})

// State
const loading = ref(true)
const saving = ref(false)
const envGroups = ref([])
const lastModified = ref(null)
const expandedGroups = ref(new Set())
const editingVariable = ref(null)
const editValue = ref('')
const showPassword = ref(new Set())
const pendingChanges = ref({})
const healthCheckResults = ref(null)
const healthCheckLoading = ref(false)

// Confirmation gate - user must acknowledge warning before seeing settings
const hasAcknowledgedRisk = ref(false)
const acknowledgeLoading = ref(false)
const downloadingFullBackup = ref(false)
const fullBackupDownloaded = ref(false)
const showRecoveryInstructions = ref(false)

// Backups
const backups = ref([])
const showRestoreDialog = ref(false)
const selectedBackup = ref(null)
const restoring = ref(false)

// Add variable dialog
const showAddDialog = ref(false)
const newVarKey = ref('')
const newVarValue = ref('')

// Delete confirmation
const showDeleteConfirm = ref(false)
const variableToDelete = ref(null)

// Reload confirmation
const showReloadConfirm = ref(false)

// Container restart after save
const showRestartDialog = ref(false)
const affectedContainers = ref([])
const selectedContainersToRestart = ref([])
const restartingContainers = ref(false)
const lastSavedVariable = ref(null)

// Icon mapping
const iconMap = {
  ExclamationCircleIcon,
  CircleStackIcon,
  ShieldCheckIcon,
  Cog6ToothIcon,
  ServerIcon,
  CloudIcon,
  GlobeAltIcon,
  CubeIcon,
  BellIcon,
  CodeBracketIcon,
  PlusCircleIcon,
}

// Color classes for groups
const colorClasses = {
  red: {
    bg: 'bg-red-50 dark:bg-red-500/10',
    border: 'border-red-200 dark:border-red-500/30',
    icon: 'text-red-500',
    text: 'text-red-700 dark:text-red-400',
    headerBg: 'bg-red-100 dark:bg-red-500/20',
  },
  blue: {
    bg: 'bg-blue-50 dark:bg-blue-500/10',
    border: 'border-blue-200 dark:border-blue-500/30',
    icon: 'text-blue-500',
    text: 'text-blue-700 dark:text-blue-400',
    headerBg: 'bg-blue-100 dark:bg-blue-500/20',
  },
  amber: {
    bg: 'bg-amber-50 dark:bg-amber-500/10',
    border: 'border-amber-200 dark:border-amber-500/30',
    icon: 'text-amber-500',
    text: 'text-amber-700 dark:text-amber-400',
    headerBg: 'bg-amber-100 dark:bg-amber-500/20',
  },
  purple: {
    bg: 'bg-purple-50 dark:bg-purple-500/10',
    border: 'border-purple-200 dark:border-purple-500/30',
    icon: 'text-purple-500',
    text: 'text-purple-700 dark:text-purple-400',
    headerBg: 'bg-purple-100 dark:bg-purple-500/20',
  },
  emerald: {
    bg: 'bg-emerald-50 dark:bg-emerald-500/10',
    border: 'border-emerald-200 dark:border-emerald-500/30',
    icon: 'text-emerald-500',
    text: 'text-emerald-700 dark:text-emerald-400',
    headerBg: 'bg-emerald-100 dark:bg-emerald-500/20',
  },
  orange: {
    bg: 'bg-orange-50 dark:bg-orange-500/10',
    border: 'border-orange-200 dark:border-orange-500/30',
    icon: 'text-orange-500',
    text: 'text-orange-700 dark:text-orange-400',
    headerBg: 'bg-orange-100 dark:bg-orange-500/20',
  },
  indigo: {
    bg: 'bg-indigo-50 dark:bg-indigo-500/10',
    border: 'border-indigo-200 dark:border-indigo-500/30',
    icon: 'text-indigo-500',
    text: 'text-indigo-700 dark:text-indigo-400',
    headerBg: 'bg-indigo-100 dark:bg-indigo-500/20',
  },
  gray: {
    bg: 'bg-gray-50 dark:bg-gray-500/10',
    border: 'border-gray-200 dark:border-gray-500/30',
    icon: 'text-gray-500',
    text: 'text-gray-700 dark:text-gray-400',
    headerBg: 'bg-gray-100 dark:bg-gray-500/20',
  },
  cyan: {
    bg: 'bg-cyan-50 dark:bg-cyan-500/10',
    border: 'border-cyan-200 dark:border-cyan-500/30',
    icon: 'text-cyan-500',
    text: 'text-cyan-700 dark:text-cyan-400',
    headerBg: 'bg-cyan-100 dark:bg-cyan-500/20',
  },
  pink: {
    bg: 'bg-pink-50 dark:bg-pink-500/10',
    border: 'border-pink-200 dark:border-pink-500/30',
    icon: 'text-pink-500',
    text: 'text-pink-700 dark:text-pink-400',
    headerBg: 'bg-pink-100 dark:bg-pink-500/20',
  },
  slate: {
    bg: 'bg-slate-50 dark:bg-slate-500/10',
    border: 'border-slate-200 dark:border-slate-500/30',
    icon: 'text-slate-500',
    text: 'text-slate-700 dark:text-slate-400',
    headerBg: 'bg-slate-100 dark:bg-slate-500/20',
  },
}

// Computed
const hasPendingChanges = computed(() => Object.keys(pendingChanges.value).length > 0)
const hasBackups = computed(() => backups.value.length > 0)

// Methods
async function loadEnvConfig() {
  loading.value = true
  try {
    const response = await api.get('/env-config')
    envGroups.value = response.data.groups
    lastModified.value = response.data.last_modified
  } catch (error) {
    console.error('Failed to load environment config:', error)
    notificationStore.error('Failed to load environment configuration')
  } finally {
    loading.value = false
  }
}

async function loadBackups() {
  try {
    const response = await api.get('/env-config/backups')
    backups.value = response.data.backups || []
  } catch (error) {
    console.error('Failed to load backups:', error)
  }
}

function toggleGroup(groupKey) {
  if (expandedGroups.value.has(groupKey)) {
    expandedGroups.value.delete(groupKey)
  } else {
    expandedGroups.value.add(groupKey)
  }
}

function getIcon(iconName) {
  return iconMap[iconName] || Cog6ToothIcon
}

function getColorClass(color, type) {
  return colorClasses[color]?.[type] || colorClasses.gray[type]
}

function startEditing(variable) {
  editingVariable.value = variable.key
  editValue.value = variable.sensitive ? '' : variable.value
}

function cancelEditing() {
  editingVariable.value = null
  editValue.value = ''
}

async function saveVariable(variable) {
  if (!editValue.value && variable.required) {
    notificationStore.error('This field is required')
    return
  }

  saving.value = true
  try {
    await api.put(`/env-config/${variable.key}`, {
      key: variable.key,
      value: editValue.value,
    })
    notificationStore.success(`${variable.label} updated successfully`)
    editingVariable.value = null
    editValue.value = ''
    lastSavedVariable.value = variable.key

    // Check which containers are affected
    await checkAffectedContainers(variable.key)

    await loadEnvConfig()
  } catch (error) {
    console.error('Failed to save variable:', error)
    notificationStore.error(error.response?.data?.detail || 'Failed to save variable')
  } finally {
    saving.value = false
  }
}

async function checkAffectedContainers(variableKey) {
  try {
    const response = await api.get(`/env-config/affected-containers/${variableKey}`)
    if (response.data.affected_containers && response.data.affected_containers.length > 0) {
      affectedContainers.value = response.data.affected_containers.map(name => ({
        name,
        displayName: response.data.container_display_names[name] || name,
      }))
      selectedContainersToRestart.value = [...response.data.affected_containers]
      showRestartDialog.value = true
    }
  } catch (error) {
    console.error('Failed to check affected containers:', error)
  }
}

async function restartSelectedContainers() {
  if (selectedContainersToRestart.value.length === 0) {
    showRestartDialog.value = false
    return
  }

  restartingContainers.value = true
  try {
    const response = await api.post('/env-config/restart-containers', {
      containers: selectedContainersToRestart.value,
    })

    if (response.data.status === 'success') {
      notificationStore.success(response.data.message)
    } else {
      notificationStore.warning(response.data.message)
    }

    showRestartDialog.value = false
  } catch (error) {
    console.error('Failed to restart containers:', error)
    notificationStore.error('Failed to restart containers')
  } finally {
    restartingContainers.value = false
  }
}

function toggleContainerSelection(containerName) {
  const idx = selectedContainersToRestart.value.indexOf(containerName)
  if (idx >= 0) {
    selectedContainersToRestart.value.splice(idx, 1)
  } else {
    selectedContainersToRestart.value.push(containerName)
  }
}

function togglePasswordVisibility(key) {
  if (showPassword.value.has(key)) {
    showPassword.value.delete(key)
  } else {
    showPassword.value.add(key)
  }
}

function getDisplayValue(variable) {
  if (variable.sensitive) {
    if (showPassword.value.has(variable.key)) {
      return variable.value || '********'
    }
    return '********'
  }
  return variable.value || variable.default || ''
}

async function runHealthCheck() {
  healthCheckLoading.value = true
  healthCheckResults.value = null
  try {
    const response = await api.post('/env-config/health-check', pendingChanges.value)
    healthCheckResults.value = response.data
    if (response.data.overall_success) {
      notificationStore.success('All health checks passed')
    } else {
      notificationStore.warning('Some health checks failed')
    }
  } catch (error) {
    console.error('Health check failed:', error)
    notificationStore.error('Failed to run health checks')
  } finally {
    healthCheckLoading.value = false
  }
}

function openAddDialog() {
  newVarKey.value = ''
  newVarValue.value = ''
  showAddDialog.value = true
}

async function addVariable() {
  if (!newVarKey.value) {
    notificationStore.error('Variable name is required')
    return
  }

  if (!/^[A-Z][A-Z0-9_]*$/.test(newVarKey.value)) {
    notificationStore.error('Variable name must be uppercase and start with a letter (e.g., MY_VARIABLE)')
    return
  }

  saving.value = true
  try {
    await api.post('/env-config', {
      key: newVarKey.value,
      value: newVarValue.value,
    })
    notificationStore.success(`Variable ${newVarKey.value} added successfully`)
    showAddDialog.value = false
    newVarKey.value = ''
    newVarValue.value = ''
    await loadEnvConfig()
  } catch (error) {
    console.error('Failed to add variable:', error)
    notificationStore.error(error.response?.data?.detail || 'Failed to add variable')
  } finally {
    saving.value = false
  }
}

function confirmDelete(variable) {
  variableToDelete.value = variable
  showDeleteConfirm.value = true
}

async function deleteVariable() {
  if (!variableToDelete.value) return

  saving.value = true
  try {
    await api.delete(`/env-config/${variableToDelete.value.key}`)
    notificationStore.success(`Variable ${variableToDelete.value.key} deleted`)
    showDeleteConfirm.value = false
    variableToDelete.value = null
    await loadEnvConfig()
  } catch (error) {
    console.error('Failed to delete variable:', error)
    notificationStore.error(error.response?.data?.detail || 'Failed to delete variable')
  } finally {
    saving.value = false
  }
}

async function reloadEnvVariables() {
  saving.value = true
  try {
    const response = await api.post('/env-config/reload')
    notificationStore.success(response.data.message)
    showReloadConfirm.value = false
    await loadEnvConfig()
  } catch (error) {
    console.error('Failed to reload variables:', error)
    notificationStore.error('Failed to reload environment variables')
  } finally {
    saving.value = false
  }
}

function formatDate(isoString) {
  if (!isoString) return 'Unknown'
  return new Date(isoString).toLocaleString()
}

function formatBackupDate(isoString) {
  if (!isoString) return 'Unknown'
  const date = new Date(isoString)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

function formatContainerName(name) {
  // Remove n8n_ prefix and format nicely
  return name
    .replace(/^n8n_/, '')
    .replace(/_/g, ' ')
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function formatContainerStatus(status) {
  const statusMap = {
    running: 'Running',
    exited: 'Stopped',
    paused: 'Paused',
    restarting: 'Restarting',
    not_found: 'Not Installed',
    created: 'Created',
  }
  return statusMap[status] || status
}

function getCheckTitle(checkType) {
  const titles = {
    containers: 'Container Status',
    postgres_connection: 'Database Connection',
    domain_resolution: 'Domain Resolution',
    required_variables: 'Required Variables',
    cloudflare_tunnel: 'Cloudflare Tunnel',
    tailscale: 'Tailscale VPN',
  }
  return titles[checkType] || checkType
}

function getCheckBgClass(check) {
  if (check.success) {
    return 'bg-emerald-50 dark:bg-emerald-500/5 border-emerald-200 dark:border-emerald-500/20'
  }
  return 'bg-red-50 dark:bg-red-500/5 border-red-200 dark:border-red-500/20'
}

function getCheckHeaderClass(check) {
  if (check.success) {
    return 'bg-emerald-100 dark:bg-emerald-500/10'
  }
  return 'bg-red-100 dark:bg-red-500/10'
}

function getCategoryTextColor(color) {
  const colors = {
    blue: 'text-blue-600 dark:text-blue-400',
    purple: 'text-purple-600 dark:text-purple-400',
    emerald: 'text-emerald-600 dark:text-emerald-400',
    amber: 'text-amber-600 dark:text-amber-400',
    red: 'text-red-600 dark:text-red-400',
  }
  return colors[color] || 'text-gray-600 dark:text-gray-400'
}

function getContainerStatusClass(container) {
  if (container.status === 'running') {
    return 'bg-white dark:bg-gray-700 border-emerald-200 dark:border-emerald-500/30'
  }
  if (container.status === 'not_found' && !container.required) {
    return 'bg-gray-50 dark:bg-gray-700/50 border-gray-200 dark:border-gray-600'
  }
  if (container.status === 'not_found' && container.required) {
    return 'bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/30'
  }
  return 'bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/30'
}

function getContainerIconColor(container) {
  if (container.status === 'running') {
    return 'text-emerald-500'
  }
  if (container.status === 'not_found' && !container.required) {
    return 'text-gray-400'
  }
  if (container.status === 'not_found' && container.required) {
    return 'text-red-500'
  }
  return 'text-amber-500'
}

function getContainerStatusTextColor(container) {
  if (container.status === 'running') {
    return 'text-emerald-600 dark:text-emerald-400'
  }
  if (container.status === 'not_found' && !container.required) {
    return 'text-gray-500 dark:text-gray-400'
  }
  if (container.status === 'not_found' && container.required) {
    return 'text-red-600 dark:text-red-400'
  }
  return 'text-amber-600 dark:text-amber-400'
}

// Open the backup confirm dialog (same flow as BackupsView)
function promptFullBackup() {
  backupConfirmDialog.value.open = true
}

// Run backup with optional verification - IDENTICAL to BackupsView.runBackupNow
async function runFullBackup() {
  const shouldVerify = backupConfirmDialog.value.verifyAfterBackup
  backupConfirmDialog.value.open = false
  downloadingFullBackup.value = true

  // Show progress modal
  progressModal.value = {
    show: true,
    type: 'backup',
    backupId: null,
    status: 'running'
  }

  try {
    // Use the backup store - same as BackupsView
    // Always skip backend auto-verification for manual backups
    const result = await backupStore.triggerBackup(true)

    // Set the backup ID so we can track progress
    if (result && result.backup_id) {
      progressModal.value.backupId = result.backup_id
    }

    // Poll for completion - same as BackupsView
    await pollForCompletion()

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
    downloadingFullBackup.value = false
  }
}

// Poll for backup completion - same as BackupsView
async function pollForCompletion() {
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

    if (backup.status === 'success') {
      progressModal.value.status = 'success'
      return
    } else if (backup.status === 'failed') {
      progressModal.value.status = 'failed'
      notificationStore.error('Backup failed: ' + (backup.error_message || 'Unknown error'))
      return
    }
    // Still running, continue polling
    attempts++
  }

  // Timeout
  progressModal.value.status = 'failed'
  notificationStore.error('Backup timed out after 5 minutes')
}

// Poll for progress updates during backup operations
async function pollForProgress() {
  while (progressModal.value.status === 'running' && progressModal.value.show) {
    await new Promise(resolve => setTimeout(resolve, 1000))
    try {
      await backupStore.fetchBackups()
    } catch (e) {
      console.error('Poll error:', e)
    }
  }
}

// Close progress modal and download backup if successful
async function closeProgressModal() {
  const backupId = progressModal.value.backupId
  const wasSuccess = progressModal.value.status === 'success'

  // If backup was successful, download the file
  if (wasSuccess && backupId) {
    try {
      const backup = backupStore.backups.find(b => b.id === backupId)

      // Download the complete backup (with restore.sh for bare metal recovery)
      const downloadResponse = await api.get(`/backups/download/${backupId}`, {
        responseType: 'blob',
        timeout: 300000 // 5 minutes
      })

      // Create download link
      const blob = new Blob([downloadResponse.data], { type: 'application/gzip' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const filename = backup?.filename || `n8n_full_backup_${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}.tar.gz`
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      fullBackupDownloaded.value = true
      notificationStore.success('Full backup downloaded successfully. You can now safely proceed.')
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message || 'Unknown error'
      notificationStore.error(`Failed to download backup: ${errorMsg}`)
    }
  }

  // Close the modal
  progressModal.value.show = false
  progressModal.value.backupId = null
}

function downloadRecoveryInstructions() {
  const instructions = `================================================================================
n8n Management Console - Environment File Recovery Instructions
================================================================================

If you have made changes to environment variables that have caused the system
to become unusable and you cannot access the Management Console, follow these
steps to restore your .env file from a backup.

IMPORTANT: These instructions assume you have SSH access to the Docker host.

================================================================================
RECOVERY STEPS
================================================================================

1. SSH to the Docker host that runs your n8n system:

   ssh user@your-docker-host

2. Navigate to the n8n installation directory:

   cd /root/n8n_nginx
   (or wherever you installed n8n_nginx)

3. List available .env backups:

   ls -la env_backups/

   You will see files like:
   .env_backup_20260104123456
   .env_backup_20260104120000
   ...

4. View the current (broken) .env file to understand what changed:

   cat .env

5. View a backup to compare:

   cat env_backups/.env_backup_YYYYMMDDHHMMSS

6. Copy the backup file to restore your .env:

   cp env_backups/.env_backup_YYYYMMDDHHMMSS .env

   Replace YYYYMMDDHHMMSS with the timestamp of the backup you want to restore.
   Usually you want the most recent backup before you made changes.

7. Stop all containers:

   docker compose down

8. Start all containers with the restored configuration:

   docker compose up -d

9. Verify the system is working:

   docker compose ps

   All containers should show as "Up" or "healthy".

10. Access the Management Console to verify everything works:

    https://your-domain.com/management

================================================================================
BARE METAL RECOVERY (Complete System Failure)
================================================================================

If you have downloaded a Bare Metal backup archive, you can use it to restore
the entire system:

1. Transfer the backup archive to the server:

   scp backup_file.tar.gz user@your-docker-host:/tmp/

2. Extract the archive:

   cd /tmp
   tar -xzf backup_file.tar.gz

3. Run the restore script:

   cd backup_*/
   chmod +x restore.sh
   ./restore.sh

4. Follow the on-screen prompts to restore databases and configuration.

================================================================================
GETTING HELP
================================================================================

If you continue to have issues:

1. Check container logs:
   docker compose logs -f

2. Check individual container:
   docker logs n8n_management --tail 100

3. Review the .env file for syntax errors:
   - No spaces around = signs
   - Quotes around values with special characters
   - No trailing whitespace

4. Verify Docker is running:
   docker info

================================================================================
PREVENTION
================================================================================

To avoid this situation in the future:

1. Always download a Full Backup before making environment changes
2. Test changes one at a time
3. Keep the backup archive in a safe location (not on the same server)
4. Document any changes you make

================================================================================
Generated by n8n Management Console
================================================================================
`

  // Create and download the text file
  const blob = new Blob([instructions], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'how_to_restore_broken_env_file.txt'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)

  notificationStore.success('Recovery instructions downloaded')
}

async function acknowledgeRisk() {
  acknowledgeLoading.value = true
  try {
    // Create a backup before allowing access
    await api.post('/env-config/backup')
    notificationStore.success('Backup created before entering Environment settings')
    hasAcknowledgedRisk.value = true
    await loadBackups()
  } catch (error) {
    console.error('Failed to create backup:', error)
    // Still allow access even if backup fails
    hasAcknowledgedRisk.value = true
    notificationStore.warning('Could not create backup, but you may proceed')
  } finally {
    acknowledgeLoading.value = false
  }
}

function openRestoreDialog() {
  selectedBackup.value = null
  showRestoreDialog.value = true
}

async function restoreBackup() {
  if (!selectedBackup.value) {
    notificationStore.error('Please select a backup to restore')
    return
  }

  restoring.value = true
  try {
    const response = await api.post('/env-config/restore', {
      filename: selectedBackup.value,
    })
    notificationStore.success(response.data.message)
    showRestoreDialog.value = false
    selectedBackup.value = null
    await loadEnvConfig()
    await loadBackups()
  } catch (error) {
    console.error('Failed to restore backup:', error)
    notificationStore.error(error.response?.data?.detail || 'Failed to restore backup')
  } finally {
    restoring.value = false
  }
}

onMounted(() => {
  loadEnvConfig()
  loadBackups()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Confirmation Gate - Show warning card if not acknowledged -->
    <div v-if="!hasAcknowledgedRisk" class="flex justify-center">
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow-2xl border-2 border-red-500 dark:border-red-600 overflow-hidden max-w-md w-full">
        <!-- Header with skull icon -->
        <div class="px-6 py-5 bg-red-50 dark:bg-red-900/30 border-b border-red-200 dark:border-red-800">
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
            Advanced Configuration Warning
          </p>
        </div>

        <!-- Content -->
        <div class="px-6 py-5 bg-white dark:bg-gray-800">
          <p class="text-gray-700 dark:text-gray-300 text-center">
            This is an <strong>ADVANCED</strong> configuration area. Changes to these variables are not typically required.
          </p>

          <!-- Warning Box -->
          <div class="mt-4 p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
            <p class="text-red-700 dark:text-red-400 text-center font-bold mb-2">
              Changes to these variables could cause system failure, loss of access, or data corruption and loss!
            </p>
            <p class="text-red-600 dark:text-red-300 text-center text-sm">
              These settings control the core functionality of the n8n management system, its supporting containers, and local and remote access. Incorrect values here can lead to partial or complete system failure.
            </p>
          </div>

          <p class="text-sm text-gray-500 dark:text-gray-400 text-center mt-4 font-medium">
            Continue to Environment Settings?
          </p>
        </div>

        <!-- Recommended Action - Download Full Backup -->
        <div class="mx-6 mb-4 p-4 bg-blue-50 dark:bg-blue-500/10 rounded-lg border border-blue-200 dark:border-blue-500/20">
          <div class="text-center">
            <div class="flex items-center justify-center gap-2 mb-1">
              <ArrowDownTrayIcon class="h-5 w-5 text-blue-600" />
              <p class="text-blue-800 dark:text-blue-300 text-sm font-semibold">
                Recommended: Download a Full Backup First
              </p>
            </div>
            <p class="text-blue-700 dark:text-blue-400 text-xs mb-3">
              Create and download a complete backup archive before making any changes. This backup includes all databases, configuration files, and a restore script for disaster recovery.
            </p>
            <button
              @click="promptFullBackup"
              :class="[
                'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
                fullBackupDownloaded
                  ? 'bg-emerald-500 text-white cursor-default'
                  : 'bg-blue-500 hover:bg-blue-600 text-white'
              ]"
            >
              <CheckCircleIcon v-if="fullBackupDownloaded" class="h-4 w-4" />
              <ArrowDownTrayIcon v-else class="h-4 w-4" />
              {{ fullBackupDownloaded ? 'Backup Downloaded!' : 'Download Full Backup' }}
            </button>
          </div>
        </div>

        <!-- Recovery Help Section -->
        <div class="mx-6 mb-4 p-4 bg-amber-50 dark:bg-amber-500/10 rounded-lg border border-amber-200 dark:border-amber-500/20">
          <div class="text-center">
            <div class="flex items-center justify-center gap-2 mb-1">
              <QuestionMarkCircleIcon class="h-5 w-5 text-amber-600" />
              <p class="text-amber-800 dark:text-amber-300 text-sm font-semibold">
                What if I break the system?
              </p>
            </div>
            <p class="text-amber-700 dark:text-amber-400 text-xs mb-3">
              If changes cause the Management Console to become inaccessible, you can recover via SSH. Download these instructions now so you have them if needed.
            </p>
            <button
              @click="showRecoveryInstructions = true"
              class="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all bg-amber-500 hover:bg-amber-600 text-white"
            >
              <QuestionMarkCircleIcon class="h-4 w-4" />
              How to Recover
            </button>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="px-6 py-4 bg-gray-50 dark:bg-gray-900/50 flex gap-3">
          <button
            @click="$router.back()"
            class="flex-1 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white font-medium transition-colors"
          >
            Back to Safety
          </button>
          <button
            @click="acknowledgeRisk"
            class="flex-1 px-4 py-2 rounded-lg font-medium transition-colors flex items-center justify-center gap-2 bg-red-500 hover:bg-red-600 text-white"
          >
            <ShieldExclamationIcon class="h-4 w-4" />
            I understand the risks, Continue
          </button>
        </div>
      </div>
    </div>

    <!-- Main Content - Only show after acknowledgement -->
    <template v-if="hasAcknowledgedRisk">
      <!-- Action Bar -->
      <div class="flex items-center justify-between bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-400 dark:border-gray-700">
        <div class="flex items-center gap-4">
          <button
            @click="runHealthCheck"
            :disabled="healthCheckLoading"
            class="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            <BeakerIcon v-if="!healthCheckLoading" class="h-5 w-5" />
            <LoadingSpinner v-else size="sm" />
            Validate Configuration
          </button>
          <button
            @click="showReloadConfirm = true"
            class="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors"
          >
            <ArrowPathIcon class="h-5 w-5" />
            Reload Variables
          </button>
          <button
            v-if="hasBackups"
            @click="openRestoreDialog"
            class="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg font-medium transition-colors"
          >
            <ArrowUturnLeftIcon class="h-5 w-5" />
            Restore Previous .env
          </button>
        </div>
        <div class="flex items-center gap-4">
          <button
            @click="openAddDialog"
            class="flex items-center gap-2 px-4 py-2 bg-purple-500 hover:bg-purple-600 text-white rounded-lg font-medium transition-colors"
          >
            <PlusIcon class="h-5 w-5" />
            Add Custom Variable
          </button>
          <div v-if="lastModified" class="text-sm text-secondary">
            Last modified: {{ formatDate(lastModified) }}
          </div>
        </div>
      </div>

      <!-- Health Check Results -->
      <Transition name="fade">
        <div v-if="healthCheckResults" class="bg-white dark:bg-gray-800 rounded-xl border border-gray-400 dark:border-gray-700 overflow-hidden">
          <div class="px-4 py-3 border-b border-gray-400 dark:border-gray-700 flex items-center justify-between">
            <div class="flex items-center gap-3">
              <component
                :is="healthCheckResults.overall_success ? CheckCircleIcon : XCircleIcon"
                :class="[
                  'h-6 w-6',
                  healthCheckResults.overall_success ? 'text-emerald-500' : 'text-red-500'
                ]"
              />
              <h3 class="font-semibold text-primary">
                System Health Check - {{ healthCheckResults.overall_success ? 'All Passed' : 'Issues Found' }}
              </h3>
            </div>
            <button
              @click="healthCheckResults = null"
              class="text-secondary hover:text-primary"
            >
              <XCircleIcon class="h-5 w-5" />
            </button>
          </div>
          <div class="p-4 space-y-4">
            <div
              v-for="check in healthCheckResults.checks"
              :key="check.check_type"
              :class="[
                'rounded-lg overflow-hidden border',
                getCheckBgClass(check)
              ]"
            >
              <!-- Check Header -->
              <div :class="['px-4 py-3 flex items-center gap-3', getCheckHeaderClass(check)]">
                <component
                  :is="check.success ? CheckCircleIcon : XCircleIcon"
                  :class="['h-5 w-5 flex-shrink-0', check.success ? 'text-emerald-600' : 'text-red-600']"
                />
                <div class="flex-1">
                  <p class="font-medium text-gray-900 dark:text-white">{{ getCheckTitle(check.check_type) }}</p>
                  <p class="text-sm text-gray-600 dark:text-gray-300">{{ check.message }}</p>
                </div>
              </div>

              <!-- Containers - Categorized display -->
              <div v-if="check.check_type === 'containers' && check.details?.categories" class="p-4 space-y-4">
                <div
                  v-for="(category, catKey) in check.details.categories"
                  :key="catKey"
                  class="space-y-2"
                >
                  <h4 :class="['text-sm font-semibold', getCategoryTextColor(category.color)]">
                    {{ category.label }}
                  </h4>
                  <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                    <div
                      v-for="container in category.containers"
                      :key="container.name"
                      :class="[
                        'flex items-center gap-2 px-3 py-2 rounded-lg border',
                        getContainerStatusClass(container)
                      ]"
                    >
                      <CubeIcon :class="['h-4 w-4', getContainerIconColor(container)]" />
                      <div class="flex-1 min-w-0">
                        <span class="text-sm font-medium text-primary truncate block">{{ container.display }}</span>
                        <span :class="['text-xs', getContainerStatusTextColor(container)]">
                          {{ formatContainerStatus(container.status) }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- PostgreSQL Connection Details -->
              <div v-else-if="check.check_type === 'postgres_connection' && check.details" class="px-4 pb-3">
                <div class="flex flex-wrap gap-4 text-sm">
                  <div v-if="check.details.host" class="flex items-center gap-2">
                    <ServerIcon class="h-4 w-4 text-secondary" />
                    <span class="text-secondary">Host:</span>
                    <span class="font-mono text-primary">{{ check.details.host }}</span>
                  </div>
                  <div v-if="check.details.user" class="flex items-center gap-2">
                    <span class="text-secondary">User:</span>
                    <span class="font-mono text-primary">{{ check.details.user }}</span>
                  </div>
                  <div v-if="check.details.database" class="flex items-center gap-2">
                    <CircleStackIcon class="h-4 w-4 text-secondary" />
                    <span class="text-secondary">Database:</span>
                    <span class="font-mono text-primary">{{ check.details.database }}</span>
                  </div>
                </div>
                <p v-if="check.details.error" class="text-xs text-red-600 dark:text-red-400 mt-2 font-mono">
                  {{ check.details.error }}
                </p>
              </div>

              <!-- Domain Resolution Details -->
              <div v-else-if="check.check_type === 'domain_resolution' && check.details" class="px-4 pb-3">
                <div class="flex flex-wrap gap-4 text-sm">
                  <div v-if="check.details.domain" class="flex items-center gap-2">
                    <GlobeAltIcon class="h-4 w-4 text-secondary" />
                    <span class="text-secondary">Domain:</span>
                    <span class="font-mono text-primary">{{ check.details.domain }}</span>
                  </div>
                  <div v-if="check.details.ip" class="flex items-center gap-2">
                    <span class="text-secondary">Resolves to:</span>
                    <span class="font-mono text-primary">{{ check.details.ip }}</span>
                  </div>
                </div>
                <p v-if="check.details.error" class="text-xs text-red-600 dark:text-red-400 mt-2">
                  {{ check.details.error }}
                </p>
              </div>

              <!-- Required Variables - Missing list -->
              <div v-else-if="check.check_type === 'required_variables' && check.details?.missing" class="px-4 pb-3">
                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="varName in check.details.missing"
                    :key="varName"
                    class="px-2 py-1 bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400 rounded font-mono text-xs"
                  >
                    {{ varName }}
                  </span>
                </div>
              </div>

              <!-- Cloudflare Tunnel Details -->
              <div v-else-if="check.check_type === 'cloudflare_tunnel' && check.details?.installed" class="px-4 pb-3">
                <div class="flex flex-wrap gap-4 text-sm">
                  <div class="flex items-center gap-2">
                    <CloudIcon class="h-4 w-4 text-orange-500" />
                    <span class="text-secondary">Container:</span>
                    <span class="font-mono text-primary">{{ check.details.container }}</span>
                  </div>
                  <div v-if="check.details.connected !== undefined" class="flex items-center gap-2">
                    <span class="text-secondary">Connected:</span>
                    <span :class="check.details.connected ? 'text-emerald-600' : 'text-amber-600'">
                      {{ check.details.connected ? 'Yes' : 'Checking...' }}
                    </span>
                  </div>
                  <div v-if="check.details.metrics?.ha_connections" class="flex items-center gap-2">
                    <span class="text-secondary">HA Connections:</span>
                    <span class="font-mono text-primary">{{ check.details.metrics.ha_connections }}</span>
                  </div>
                </div>
              </div>

              <!-- Tailscale Details -->
              <div v-else-if="check.check_type === 'tailscale' && check.details?.installed" class="px-4 pb-3">
                <div class="flex flex-wrap gap-4 text-sm">
                  <div v-if="check.details.tailscale_ip" class="flex items-center gap-2">
                    <ServerIcon class="h-4 w-4 text-blue-500" />
                    <span class="text-secondary">Tailscale IP:</span>
                    <span class="font-mono text-primary">{{ check.details.tailscale_ip }}</span>
                  </div>
                  <div v-if="check.details.tailnet" class="flex items-center gap-2">
                    <span class="text-secondary">Tailnet:</span>
                    <span class="font-mono text-primary">{{ check.details.tailnet }}</span>
                  </div>
                  <div v-if="check.details.peer_count !== undefined" class="flex items-center gap-2">
                    <span class="text-secondary">Peers:</span>
                    <span class="font-mono text-primary">{{ check.details.peer_count }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Warnings -->
            <div v-if="healthCheckResults.warnings?.length > 0" class="mt-4 p-3 bg-amber-50 dark:bg-amber-500/10 rounded-lg border border-amber-200 dark:border-amber-500/30">
              <h4 class="font-medium text-amber-700 dark:text-amber-400 mb-2">Warnings</h4>
              <ul class="space-y-2">
                <li
                  v-for="(warning, idx) in healthCheckResults.warnings"
                  :key="idx"
                  class="flex items-start gap-2 text-sm text-amber-600 dark:text-amber-400"
                >
                  <ExclamationTriangleIcon class="h-4 w-4 flex-shrink-0 mt-0.5" />
                  {{ warning }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Loading State -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <LoadingSpinner />
      </div>

      <!-- Variable Groups -->
      <div v-else class="space-y-4">
        <div
          v-for="group in envGroups"
          :key="group.key"
          class="bg-white dark:bg-gray-800 rounded-xl border border-gray-400 dark:border-gray-700 overflow-hidden"
        >
          <!-- Group Header - Icon on far left, click to expand -->
          <button
            @click="toggleGroup(group.key)"
            class="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
          >
            <!-- Icon container on far left -->
            <div :class="['p-2 rounded-lg', getColorClass(group.color, 'headerBg')]">
              <component
                :is="getIcon(group.icon)"
                :class="['h-5 w-5', getColorClass(group.color, 'icon')]"
              />
            </div>
            <div class="flex-1 text-left">
              <h3 :class="['font-semibold', getColorClass(group.color, 'text')]">
                {{ group.label }}
              </h3>
              <p class="text-xs text-secondary">{{ group.description }}</p>
            </div>
            <span class="text-sm text-secondary">
              {{ group.variables.length }} variable{{ group.variables.length !== 1 ? 's' : '' }}
            </span>
          </button>

          <!-- Group Variables -->
          <Transition name="collapse">
            <div v-if="expandedGroups.has(group.key)" class="divide-y divide-gray-200 dark:divide-gray-700 border-t border-gray-200 dark:border-gray-700">
              <div
                v-for="variable in group.variables"
                :key="variable.key"
                class="px-4 py-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
              >
                <div class="flex items-start justify-between gap-4">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1">
                      <span class="font-mono text-sm font-medium text-primary">{{ variable.key }}</span>
                      <span v-if="variable.required" class="text-xs px-1.5 py-0.5 bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 rounded">
                        Required
                      </span>
                      <span v-if="variable.sensitive" class="text-xs px-1.5 py-0.5 bg-amber-100 dark:bg-amber-500/20 text-amber-600 dark:text-amber-400 rounded">
                        Sensitive
                      </span>
                      <span v-if="variable.is_custom" class="text-xs px-1.5 py-0.5 bg-purple-100 dark:bg-purple-500/20 text-purple-600 dark:text-purple-400 rounded">
                        Custom
                      </span>
                      <span v-if="!variable.editable" class="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-500/20 text-gray-600 dark:text-gray-400 rounded">
                        Read-only
                      </span>
                    </div>
                    <p class="text-sm text-secondary mb-2">{{ variable.description }}</p>

                    <!-- Warning message -->
                    <div v-if="variable.warning" class="flex items-start gap-2 p-2 bg-red-50 dark:bg-red-500/10 rounded-lg mb-2">
                      <ExclamationTriangleIcon class="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
                      <span class="text-xs text-red-600 dark:text-red-400">{{ variable.warning }}</span>
                    </div>

                    <!-- Value Display / Edit -->
                    <div v-if="editingVariable === variable.key" class="flex items-center gap-2">
                      <input
                        v-model="editValue"
                        :type="variable.type === 'password' && !showPassword.has(variable.key) ? 'password' : 'text'"
                        :placeholder="variable.sensitive ? 'Enter new value' : variable.default || ''"
                        class="flex-1 px-3 py-2 border border-gray-400 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-primary font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                      <button
                        v-if="variable.type === 'password'"
                        @click="togglePasswordVisibility(variable.key)"
                        class="p-2 text-secondary hover:text-primary"
                      >
                        <EyeSlashIcon v-if="showPassword.has(variable.key)" class="h-5 w-5" />
                        <EyeIcon v-else class="h-5 w-5" />
                      </button>
                      <button
                        @click="saveVariable(variable)"
                        :disabled="saving"
                        class="px-3 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                      >
                        Save
                      </button>
                      <button
                        @click="cancelEditing"
                        class="px-3 py-2 bg-gray-200 dark:bg-gray-600 hover:bg-gray-300 dark:hover:bg-gray-500 text-primary rounded-lg text-sm font-medium transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                    <div v-else class="flex items-center gap-2">
                      <div class="flex-1 px-3 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg font-mono text-sm text-primary">
                        {{ getDisplayValue(variable) || '(not set)' }}
                      </div>
                      <button
                        v-if="variable.sensitive && variable.value"
                        @click="togglePasswordVisibility(variable.key)"
                        class="p-2 text-secondary hover:text-primary"
                      >
                        <EyeSlashIcon v-if="showPassword.has(variable.key)" class="h-5 w-5" />
                        <EyeIcon v-else class="h-5 w-5" />
                      </button>
                    </div>
                  </div>

                  <!-- Actions -->
                  <div class="flex items-center gap-2">
                    <button
                      v-if="variable.editable && editingVariable !== variable.key"
                      @click="startEditing(variable)"
                      class="p-2 text-blue-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-500/10 rounded-lg transition-colors"
                      title="Edit"
                    >
                      <PencilSquareIcon class="h-5 w-5" />
                    </button>
                    <button
                      v-if="variable.is_custom"
                      @click="confirmDelete(variable)"
                      class="p-2 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors"
                      title="Delete"
                    >
                      <TrashIcon class="h-5 w-5" />
                    </button>
                  </div>
                </div>
              </div>

              <!-- Empty state for custom group -->
              <div v-if="group.key === 'custom' && group.variables.length === 0" class="px-4 py-8 text-center">
                <PlusCircleIcon class="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
                <p class="text-secondary">No custom variables defined</p>
                <button
                  @click="openAddDialog"
                  class="mt-3 text-purple-500 hover:text-purple-600 text-sm font-medium"
                >
                  Add your first custom variable
                </button>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </template>

    <!-- Add Variable Dialog -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="showAddDialog"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/50" @click="showAddDialog = false" />
          <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full border border-gray-400 dark:border-gray-700">
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-full bg-purple-100 dark:bg-purple-500/20">
                  <PlusCircleIcon class="h-5 w-5 text-purple-600 dark:text-purple-400" />
                </div>
                <h3 class="text-lg font-semibold text-primary">Add Custom Variable</h3>
              </div>
              <button @click="showAddDialog = false" class="p-1 rounded-lg text-secondary hover:text-primary hover:bg-surface-hover">
                <XCircleIcon class="h-5 w-5" />
              </button>
            </div>
            <div class="px-6 py-4 space-y-4">
              <div>
                <label class="block text-sm font-medium text-primary mb-1">Variable Name</label>
                <input
                  v-model="newVarKey"
                  type="text"
                  placeholder="MY_CUSTOM_VARIABLE"
                  class="w-full px-3 py-2 border border-gray-400 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-primary font-mono focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
                <p class="text-xs text-secondary mt-1">Must be uppercase, start with a letter, and contain only letters, numbers, and underscores</p>
              </div>
              <div>
                <label class="block text-sm font-medium text-primary mb-1">Value</label>
                <input
                  v-model="newVarValue"
                  type="text"
                  placeholder="Enter value"
                  class="w-full px-3 py-2 border border-gray-400 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-primary focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
            </div>
            <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-400 dark:border-gray-700">
              <button @click="showAddDialog = false" class="btn-secondary">Cancel</button>
              <button @click="addVariable" :disabled="saving" class="btn-primary">
                <span v-if="saving" class="flex items-center gap-2">
                  <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Adding...
                </span>
                <span v-else>Add Variable</span>
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Restore Backup Dialog -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="showRestoreDialog"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/50" @click="showRestoreDialog = false" />
          <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full border border-gray-400 dark:border-gray-700">
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-full bg-amber-100 dark:bg-amber-500/20">
                  <ArrowUturnLeftIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
                </div>
                <h3 class="text-lg font-semibold text-primary">Restore Previous .env File</h3>
              </div>
              <button @click="showRestoreDialog = false" class="p-1 rounded-lg text-secondary hover:text-primary hover:bg-surface-hover">
                <XCircleIcon class="h-5 w-5" />
              </button>
            </div>

            <!-- Warning -->
            <div class="px-6 py-4 bg-amber-50 dark:bg-amber-500/10 border-b border-amber-200 dark:border-amber-500/30">
              <div class="flex items-start gap-3">
                <ExclamationTriangleIcon class="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                <div class="text-sm text-amber-700 dark:text-amber-400">
                  <p class="font-medium mb-1">Restoring a backup may cause problems!</p>
                  <p>Restoring will replace the current .env file. A backup of the current file will be made automatically. You may need to restart containers for changes to take effect.</p>
                </div>
              </div>
            </div>

            <div class="px-6 py-4">
              <label class="block text-sm font-medium text-primary mb-3">Select a backup to restore:</label>
              <div class="space-y-2 max-h-64 overflow-y-auto">
                <label
                  v-for="backup in backups"
                  :key="backup.filename"
                  :class="[
                    'flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                    selectedBackup === backup.filename
                      ? 'border-amber-500 bg-amber-50 dark:bg-amber-500/10'
                      : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                  ]"
                >
                  <input
                    type="radio"
                    :value="backup.filename"
                    v-model="selectedBackup"
                    class="text-amber-500 focus:ring-amber-500"
                  />
                  <div class="flex-1">
                    <div class="flex items-center gap-2">
                      <ArchiveBoxIcon class="h-4 w-4 text-secondary" />
                      <span class="font-mono text-sm text-primary">{{ backup.filename }}</span>
                    </div>
                    <div class="flex items-center gap-2 mt-1 text-xs text-secondary">
                      <ClockIcon class="h-3 w-3" />
                      {{ formatBackupDate(backup.created_at) }}
                      <span class="text-gray-400">•</span>
                      {{ (backup.size / 1024).toFixed(1) }} KB
                    </div>
                  </div>
                </label>
              </div>
              <p v-if="backups.length === 0" class="text-center text-secondary py-4">No backups available</p>
            </div>

            <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-400 dark:border-gray-700">
              <button @click="showRestoreDialog = false" class="btn-secondary">Cancel</button>
              <button
                @click="restoreBackup"
                :disabled="!selectedBackup || restoring"
                class="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                <LoadingSpinner v-if="restoring" size="sm" />
                <ArrowUturnLeftIcon v-else class="h-4 w-4" />
                {{ restoring ? 'Restoring...' : 'Restore' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Container Restart Dialog -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="showRestartDialog"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/50" @click="showRestartDialog = false" />
          <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full border border-gray-400 dark:border-gray-700">
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-full bg-blue-100 dark:bg-blue-500/20">
                  <ArrowPathIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <h3 class="text-lg font-semibold text-primary">Restart Affected Containers</h3>
              </div>
              <button @click="showRestartDialog = false" class="p-1 rounded-lg text-secondary hover:text-primary hover:bg-surface-hover">
                <XCircleIcon class="h-5 w-5" />
              </button>
            </div>

            <div class="px-6 py-4">
              <div class="flex items-start gap-3 mb-4 p-3 bg-blue-50 dark:bg-blue-500/10 rounded-lg">
                <InformationCircleIcon class="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div class="text-sm text-blue-700 dark:text-blue-400">
                  <p>The following containers use the <strong>{{ lastSavedVariable }}</strong> variable and need to be restarted for changes to take effect.</p>
                </div>
              </div>

              <label class="block text-sm font-medium text-primary mb-3">Select containers to restart:</label>
              <div class="space-y-2">
                <label
                  v-for="container in affectedContainers"
                  :key="container.name"
                  :class="[
                    'flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                    selectedContainersToRestart.includes(container.name)
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-500/10'
                      : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                  ]"
                >
                  <input
                    type="checkbox"
                    :checked="selectedContainersToRestart.includes(container.name)"
                    @change="toggleContainerSelection(container.name)"
                    class="text-blue-500 focus:ring-blue-500 rounded"
                  />
                  <div class="flex items-center gap-2">
                    <CubeIcon class="h-4 w-4 text-secondary" />
                    <span class="font-medium text-primary">{{ container.displayName }}</span>
                    <span class="text-xs text-secondary font-mono">({{ container.name }})</span>
                  </div>
                </label>
              </div>
            </div>

            <div class="flex items-center justify-between px-6 py-4 border-t border-gray-400 dark:border-gray-700">
              <button
                @click="showRestartDialog = false"
                class="text-secondary hover:text-primary text-sm"
              >
                Skip for now
              </button>
              <button
                @click="restartSelectedContainers"
                :disabled="selectedContainersToRestart.length === 0 || restartingContainers"
                class="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                <LoadingSpinner v-if="restartingContainers" size="sm" />
                <ArrowPathIcon v-else class="h-4 w-4" />
                {{ restartingContainers ? 'Restarting...' : `Restart ${selectedContainersToRestart.length} Container${selectedContainersToRestart.length !== 1 ? 's' : ''}` }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Delete Confirmation -->
    <ConfirmDialog
      :open="showDeleteConfirm"
      title="Delete Variable"
      :message="`Are you sure you want to delete '${variableToDelete?.key}'? This action cannot be undone.`"
      confirm-text="Delete"
      cancel-text="Cancel"
      :danger="true"
      @confirm="deleteVariable"
      @cancel="showDeleteConfirm = false; variableToDelete = null"
    />

    <!-- Reload Confirmation -->
    <ConfirmDialog
      :open="showReloadConfirm"
      title="Reload Environment Variables"
      message="This will reload environment variables into the current process. Note: Container restarts may be required for all changes to take full effect."
      confirm-text="Reload"
      cancel-text="Cancel"
      @confirm="reloadEnvVariables"
      @cancel="showReloadConfirm = false"
    />

    <!-- Recovery Instructions Modal -->
    <Transition name="modal">
      <div v-if="showRecoveryInstructions" class="fixed inset-0 z-50 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <!-- Backdrop -->
          <div class="fixed inset-0 bg-black/50" @click="showRecoveryInstructions = false"></div>

          <!-- Modal Content -->
          <div class="relative bg-white dark:bg-gray-800 rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
            <!-- Header -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-amber-50 dark:bg-amber-500/10">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-full bg-amber-100 dark:bg-amber-500/20 flex items-center justify-center">
                  <QuestionMarkCircleIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                  <h3 class="text-lg font-bold text-gray-900 dark:text-white">How to Recover from a Broken Configuration</h3>
                  <p class="text-sm text-amber-600 dark:text-amber-400">Emergency recovery instructions for SSH access</p>
                </div>
              </div>
              <button
                @click="showRecoveryInstructions = false"
                class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                <XMarkIcon class="h-5 w-5 text-gray-500" />
              </button>
            </div>

            <!-- Instructions Content -->
            <div class="p-6 overflow-y-auto max-h-[60vh]">
              <!-- Important Notice -->
              <div class="mb-6 p-4 bg-red-50 dark:bg-red-500/10 rounded-xl border border-red-200 dark:border-red-500/20">
                <div class="flex items-start gap-3">
                  <!-- Warning Triangle Icon -->
                  <div class="flex-shrink-0 mt-0.5">
                    <svg class="h-6 w-6" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M12 2L1 21h22L12 2z" fill="#FBBF24" stroke="#DC2626" stroke-width="1.5" stroke-linejoin="round"/>
                      <path d="M12 9v5" stroke="#DC2626" stroke-width="2" stroke-linecap="round"/>
                      <circle cx="12" cy="17" r="1" fill="#DC2626"/>
                    </svg>
                  </div>
                  <div>
                    <p class="text-red-700 dark:text-red-300 text-sm font-semibold">
                      Save these instructions NOW before making changes!
                    </p>
                    <p class="text-red-600/80 dark:text-red-400/70 text-sm mt-1">
                      If the Management Console becomes inaccessible, you won't be able to view this page.
                    </p>
                  </div>
                </div>
              </div>

              <!-- Steps -->
              <div class="space-y-4">
                <h4 class="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <span class="w-6 h-6 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center font-bold">1</span>
                  SSH to your Docker host
                </h4>
                <div class="ml-8 p-3 bg-gray-100 dark:bg-gray-900 rounded-lg font-mono text-sm text-gray-800 dark:text-gray-200">
                  ssh user@your-docker-host
                </div>

                <h4 class="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <span class="w-6 h-6 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center font-bold">2</span>
                  Navigate to the n8n installation directory
                </h4>
                <div class="ml-8 p-3 bg-gray-100 dark:bg-gray-900 rounded-lg font-mono text-sm text-gray-800 dark:text-gray-200">
                  cd /root/n8n_nginx
                </div>

                <h4 class="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <span class="w-6 h-6 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center font-bold">3</span>
                  List available backups and find the most recent one
                </h4>
                <div class="ml-8 p-3 bg-gray-100 dark:bg-gray-900 rounded-lg font-mono text-sm text-gray-800 dark:text-gray-200">
                  ls -la env_backups/
                </div>

                <h4 class="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <span class="w-6 h-6 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center font-bold">4</span>
                  Restore the backup (replace timestamp with actual backup filename)
                </h4>
                <div class="ml-8 p-3 bg-gray-100 dark:bg-gray-900 rounded-lg font-mono text-sm text-gray-800 dark:text-gray-200">
                  cp env_backups/.env_backup_YYYYMMDDHHMMSS .env
                </div>

                <h4 class="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <span class="w-6 h-6 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center font-bold">5</span>
                  Restart all containers
                </h4>
                <div class="ml-8 p-3 bg-gray-100 dark:bg-gray-900 rounded-lg font-mono text-sm text-gray-800 dark:text-gray-200">
                  docker compose down && docker compose up -d
                </div>

                <h4 class="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <span class="w-6 h-6 rounded-full bg-emerald-500 text-white text-xs flex items-center justify-center font-bold">✓</span>
                  Verify containers are running
                </h4>
                <div class="ml-8 p-3 bg-gray-100 dark:bg-gray-900 rounded-lg font-mono text-sm text-gray-800 dark:text-gray-200">
                  docker compose ps
                </div>
              </div>

              <!-- Bare Metal Section -->
              <div class="mt-6 p-4 bg-purple-50 dark:bg-purple-500/10 rounded-xl border border-purple-200 dark:border-purple-500/20">
                <h4 class="font-semibold text-purple-700 dark:text-purple-300 mb-2">Complete System Failure?</h4>
                <p class="text-purple-600/80 dark:text-purple-400/70 text-sm mb-2">
                  If you downloaded a Bare Metal backup archive, you can restore the entire system:
                </p>
                <div class="p-3 bg-gray-100 dark:bg-gray-900 rounded-lg font-mono text-sm text-gray-800 dark:text-gray-200">
                  <div>tar -xzf backup_file.tar.gz</div>
                  <div>cd backup_*/</div>
                  <div>chmod +x restore.sh</div>
                  <div>./restore.sh</div>
                </div>
              </div>
            </div>

            <!-- Footer -->
            <div class="flex items-center justify-between px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
              <button
                @click="downloadRecoveryInstructions"
                class="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors"
              >
                <DocumentTextIcon class="h-4 w-4" />
                Download These Instructions
              </button>
              <button
                @click="showRecoveryInstructions = false"
                class="px-4 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600 rounded-lg font-medium transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Backup Confirm Dialog - same as BackupsView -->
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
                @click="runFullBackup"
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

    <!-- Backup Progress Modal -->
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
.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.3s ease;
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
  max-height: 2000px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
