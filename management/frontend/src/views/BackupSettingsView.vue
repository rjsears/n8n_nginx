<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useBackupStore } from '@/stores/backups'
import { useNotificationStore } from '@/stores/notifications'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import {
  FolderIcon,
  ClockIcon,
  TrashIcon,
  BellIcon,
  CheckCircleIcon,
  ServerIcon,
  ArrowPathIcon,
  CheckIcon,
  XMarkIcon,
  ArrowLeftIcon,
  ChevronDownIcon,
  CloudIcon,
  CircleStackIcon,
  ArrowRightIcon,
  InformationCircleIcon,
  ExclamationTriangleIcon,
  CalendarIcon,
  Cog6ToothIcon,
  DocumentTextIcon,
  ShieldCheckIcon,
  PlayIcon,
  ArchiveBoxIcon,
} from '@heroicons/vue/24/outline'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const backupStore = useBackupStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const saving = ref(false)
const activeTab = ref(route.query.tab || 'storage')
const validatingPath = ref(false)
const pathValidation = ref(null)
const storageDetection = ref(null)
const detectingStorage = ref(false)

// Notification channels and groups for selection
const notificationServices = ref([])
const notificationGroups = ref([])
const loadingChannels = ref(false)

// Backups for manual verification
const availableBackups = ref([])
const loadingBackups = ref(false)
const selectedBackupId = ref(null)
const verifying = ref(false)
const verificationResult = ref(null)

// Collapsible sections state
const sections = ref({
  stagingArea: true,
  nfsStorage: true,
  backupWorkflow: true,
  localPaths: false,
  scheduleConfig: true,
  backupContents: true,
  retentionPolicy: true,
  compressionSettings: true,
  notifySettings: true,
  notifyChannels: true,
  autoVerify: true,
  manualVerify: true,
})

// Watch for tab query changes
watch(() => route.query.tab, (newTab) => {
  if (newTab) activeTab.value = newTab
})

// Form data
const form = ref({
  // Storage
  primary_storage_path: '/app/backups',
  nfs_storage_path: '',
  nfs_enabled: false,
  storage_preference: 'local',
  backup_workflow: 'direct',
  // Compression
  compression_enabled: true,
  compression_algorithm: 'gzip',
  compression_level: 6,
  // Retention
  retention_enabled: true,
  retention_days: 30,
  retention_count: 10,
  retention_min_count: 3,
  // Schedule
  schedule_enabled: true,
  schedule_frequency: 'daily',
  schedule_time: '02:00',
  schedule_day_of_week: null,
  schedule_day_of_month: null,
  // Backup Type
  default_backup_type: 'postgres_full',
  include_n8n_config: true,
  include_ssl_certs: true,
  include_env_files: true,
  // Notifications
  notify_on_success: false,
  notify_on_failure: true,
  notification_channel_id: null,
  notification_channel_type: null, // 'service' or 'group'
  // Verification
  auto_verify_enabled: false,
  verify_after_backup: false,
})

const tabs = [
  { id: 'storage', name: 'Storage', icon: FolderIcon, iconColor: 'text-blue-500', bgActive: 'bg-blue-500/15 dark:bg-blue-500/20', textActive: 'text-blue-700 dark:text-blue-400', borderActive: 'border-blue-500/30' },
  { id: 'schedule', name: 'Schedule', icon: ClockIcon, iconColor: 'text-emerald-500', bgActive: 'bg-emerald-500/15 dark:bg-emerald-500/20', textActive: 'text-emerald-700 dark:text-emerald-400', borderActive: 'border-emerald-500/30' },
  { id: 'retention', name: 'Retention', icon: TrashIcon, iconColor: 'text-amber-500', bgActive: 'bg-amber-500/15 dark:bg-amber-500/20', textActive: 'text-amber-700 dark:text-amber-400', borderActive: 'border-amber-500/30' },
  { id: 'compression', name: 'Compression', icon: ServerIcon, iconColor: 'text-purple-500', bgActive: 'bg-purple-500/15 dark:bg-purple-500/20', textActive: 'text-purple-700 dark:text-purple-400', borderActive: 'border-purple-500/30' },
  { id: 'notifications', name: 'Notifications', icon: BellIcon, iconColor: 'text-pink-500', bgActive: 'bg-pink-500/15 dark:bg-pink-500/20', textActive: 'text-pink-700 dark:text-pink-400', borderActive: 'border-pink-500/30' },
  { id: 'verification', name: 'Verification', icon: CheckCircleIcon, iconColor: 'text-cyan-500', bgActive: 'bg-cyan-500/15 dark:bg-cyan-500/20', textActive: 'text-cyan-700 dark:text-cyan-400', borderActive: 'border-cyan-500/30' },
]

const compressionLevelMax = computed(() => {
  return form.value.compression_algorithm === 'zstd' ? 22 : 9
})

const hasNfsConfigured = computed(() => {
  return storageDetection.value?.has_nfs ||
    (storageDetection.value?.environment?.nfs_mount_point &&
     storageDetection.value?.environment?.nfs_mount_point !== '')
})

const nfsMounts = computed(() => {
  return storageDetection.value?.nfs_mounts || []
})

const stagingArea = computed(() => {
  return storageDetection.value?.staging_area || {
    path: '/app/backups',
    exists: true,
    is_writable: true,
  }
})

const availableLocalPaths = computed(() => {
  return storageDetection.value?.local_paths?.filter(p => p.exists && p.is_writable) || []
})

const verifiableBackups = computed(() => {
  return availableBackups.value.filter(b => b.status === 'success')
})

// Check if notifications can be enabled (requires channel selected)
const canEnableNotifications = computed(() => {
  return form.value.notification_channel_id !== null
})

// All available notification channels (services + groups)
const allNotificationChannels = computed(() => {
  const channels = []
  // Add services
  notificationServices.value.forEach(s => {
    channels.push({
      id: s.id,
      type: 'service',
      name: s.name,
      description: s.service_type ? `${s.service_type.toUpperCase()} Channel` : 'Channel',
      enabled: s.enabled,
      icon: 'service'
    })
  })
  // Add groups
  notificationGroups.value.forEach(g => {
    channels.push({
      id: g.id,
      type: 'group',
      name: g.name,
      description: g.description || `${g.services?.length || 0} services`,
      enabled: g.enabled,
      icon: 'group'
    })
  })
  return channels
})

async function loadConfiguration() {
  loading.value = true
  try {
    const [config, storage] = await Promise.all([
      backupStore.fetchConfiguration(),
      backupStore.detectStorageLocations().catch(() => null)
    ])

    Object.keys(form.value).forEach(key => {
      if (config[key] !== undefined) {
        form.value[key] = config[key]
      }
    })

    if (storage) {
      storageDetection.value = storage
      if (storage.has_nfs && storage.nfs_mounts.length > 0) {
        const nfsMount = storage.nfs_mounts[0]
        if (!form.value.nfs_storage_path) {
          form.value.nfs_storage_path = nfsMount.path
        }
        sections.value.nfsStorage = true
      }
    }
  } catch (err) {
    notificationStore.error('Failed to load configuration')
  } finally {
    loading.value = false
  }
}

async function loadNotificationChannels() {
  loadingChannels.value = true
  try {
    const [servicesRes, groupsRes] = await Promise.all([
      api.get('/notifications/services'),
      api.get('/notifications/groups')
    ])
    notificationServices.value = servicesRes.data.filter(s => s.enabled)
    notificationGroups.value = groupsRes.data.filter(g => g.enabled)
  } catch (err) {
    console.error('Failed to load notification channels:', err)
  } finally {
    loadingChannels.value = false
  }
}

async function loadBackups() {
  loadingBackups.value = true
  try {
    await backupStore.fetchBackups()
    availableBackups.value = backupStore.backups || []
  } catch (err) {
    console.error('Failed to load backups:', err)
  } finally {
    loadingBackups.value = false
  }
}

async function detectStorage() {
  detectingStorage.value = true
  try {
    storageDetection.value = await backupStore.detectStorageLocations()
  } catch (err) {
    notificationStore.error('Failed to detect storage locations')
  } finally {
    detectingStorage.value = false
  }
}

function selectNfsPath(path) {
  form.value.nfs_storage_path = path
  form.value.nfs_enabled = true
}

async function validatePath(path) {
  if (!path) {
    pathValidation.value = null
    return
  }
  validatingPath.value = true
  try {
    pathValidation.value = await backupStore.validateStoragePath(path)
  } catch (err) {
    pathValidation.value = { error: true, message: 'Failed to validate path' }
  } finally {
    validatingPath.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await backupStore.updateConfiguration(form.value)
    notificationStore.success('Backup configuration saved')
  } catch (err) {
    notificationStore.error('Failed to save configuration')
  } finally {
    saving.value = false
  }
}

async function runManualVerification() {
  if (!selectedBackupId.value) {
    notificationStore.warning('Please select a backup to verify')
    return
  }

  verifying.value = true
  verificationResult.value = null
  try {
    const result = await backupStore.verifyBackup(selectedBackupId.value)
    verificationResult.value = result
    if (result.overall_status === 'passed') {
      notificationStore.success('Backup verification passed!')
    } else if (result.overall_status === 'failed') {
      notificationStore.error('Backup verification failed')
    } else {
      notificationStore.warning('Backup verification completed with warnings')
    }
    await loadBackups()
  } catch (err) {
    notificationStore.error('Failed to verify backup')
    verificationResult.value = { error: true, message: err.message }
  } finally {
    verifying.value = false
  }
}

function goBack() {
  router.push('/backups')
}

function toggleSection(section) {
  sections.value[section] = !sections.value[section]
}

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

function selectNotificationChannel(channel) {
  form.value.notification_channel_id = channel.id
  form.value.notification_channel_type = channel.type
}

function clearNotificationChannel() {
  form.value.notification_channel_id = null
  form.value.notification_channel_type = null
  // Disable notifications if no channel selected
  form.value.notify_on_success = false
  form.value.notify_on_failure = false
}

function tryEnableNotification(type) {
  if (!canEnableNotifications.value) {
    notificationStore.warning('Please select a notification channel first')
    sections.value.notifyChannels = true
    return
  }
  if (type === 'success') {
    form.value.notify_on_success = !form.value.notify_on_success
  } else {
    form.value.notify_on_failure = !form.value.notify_on_failure
  }
}

onMounted(() => {
  loadConfiguration()
  loadNotificationChannels()
  loadBackups()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-4">
        <button
          @click="goBack"
          class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          <ArrowLeftIcon class="h-5 w-5 text-gray-500" />
        </button>
        <div>
          <h1
            :class="[
              'text-2xl font-bold',
              themeStore.isNeon ? 'neon-text-cyan' : 'text-primary'
            ]"
          >
            Backup Configuration
          </h1>
          <p class="text-secondary mt-1">Configure backup storage, schedule, and retention policies</p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <button
          @click="detectStorage"
          :disabled="detectingStorage"
          class="btn-secondary flex items-center gap-2"
        >
          <ArrowPathIcon :class="['h-4 w-4', detectingStorage ? 'animate-spin' : '']" />
          {{ detectingStorage ? 'Detecting...' : 'Detect Storage' }}
        </button>
        <button
          @click="save"
          :disabled="saving"
          :class="[
            'btn-primary flex items-center gap-2',
            themeStore.isNeon ? 'neon-btn-cyan' : ''
          ]"
        >
          <CheckIcon v-if="!saving" class="h-4 w-4" />
          <ArrowPathIcon v-else class="h-4 w-4 animate-spin" />
          {{ saving ? 'Saving...' : 'Save Configuration' }}
        </button>
      </div>
    </div>

    <LoadingSpinner v-if="loading" size="lg" text="Loading configuration..." class="py-12" />

    <template v-else>
      <!-- Tabs -->
      <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-1.5 flex gap-1.5 overflow-x-auto">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="[
            'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap border',
            activeTab === tab.id
              ? `${tab.bgActive} ${tab.textActive} ${tab.borderActive}`
              : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700/50 border-transparent'
          ]"
        >
          <component :is="tab.icon" :class="['h-4 w-4', activeTab === tab.id ? '' : tab.iconColor]" />
          {{ tab.name }}
        </button>
      </div>

      <!-- Storage Tab -->
      <div v-if="activeTab === 'storage'" class="space-y-4">
        <!-- Staging Area Section -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <button
            @click="toggleSection('stagingArea')"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2.5 rounded-xl bg-gradient-to-br from-amber-100 to-orange-100 dark:from-amber-900/30 dark:to-orange-900/30">
                <CircleStackIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Local Staging Area</h3>
                <p class="text-sm text-secondary">Temporary storage for backup creation</p>
              </div>
            </div>
            <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.stagingArea ? 'rotate-180' : '']" />
          </button>

          <div v-if="sections.stagingArea" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <div class="mt-4 p-4 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
              <div class="flex items-start gap-3">
                <InformationCircleIcon class="h-5 w-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                <div class="text-sm">
                  <p class="font-medium text-amber-800 dark:text-amber-300">About the Staging Area</p>
                  <p class="text-amber-700 dark:text-amber-400 mt-1">
                    The staging area (<code class="px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/50 font-mono text-xs">{{ stagingArea.path }}</code>)
                    is a local Docker volume used to temporarily store backups during creation.
                  </p>
                </div>
              </div>
            </div>

            <div class="mt-4 flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
              <div class="flex items-center gap-3">
                <FolderIcon class="h-5 w-5 text-amber-500" />
                <div>
                  <p class="font-mono text-sm font-medium text-primary">{{ stagingArea.path }}</p>
                  <p class="text-xs text-secondary">
                    <span v-if="stagingArea.is_writable" class="text-emerald-600 dark:text-emerald-400">Available</span>
                    <span v-else class="text-red-500">Not writable</span>
                    <span v-if="stagingArea.free_space_gb" class="ml-2">{{ stagingArea.free_space_gb }} GB free</span>
                  </p>
                </div>
              </div>
              <span class="px-3 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
                Staging
              </span>
            </div>
          </div>
        </div>

        <!-- NFS Storage Section -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <button
            @click="toggleSection('nfsStorage')"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2.5 rounded-xl bg-gradient-to-br from-emerald-100 to-teal-100 dark:from-emerald-900/30 dark:to-teal-900/30">
                <CloudIcon class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Network Storage (NFS)</h3>
                <p class="text-sm text-secondary">
                  <span v-if="hasNfsConfigured" class="text-emerald-600 dark:text-emerald-400">{{ nfsMounts.length }} NFS mount(s) detected</span>
                  <span v-else>No NFS storage detected</span>
                </p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span v-if="form.nfs_enabled" class="px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400">
                Enabled
              </span>
              <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.nfsStorage ? 'rotate-180' : '']" />
            </div>
          </button>

          <div v-if="sections.nfsStorage" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <div v-if="nfsMounts.length > 0" class="mt-4 space-y-3">
              <p class="text-sm font-medium text-secondary">Detected NFS Mounts</p>
              <div
                v-for="nfs in nfsMounts"
                :key="nfs.path"
                :class="[
                  'p-4 rounded-lg border-2 transition-all cursor-pointer',
                  form.nfs_storage_path === nfs.path
                    ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-emerald-300 dark:hover:border-emerald-700'
                ]"
                @click="selectNfsPath(nfs.path)"
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-900/40">
                      <ServerIcon class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <div>
                      <p class="font-mono text-sm font-medium text-primary">{{ nfs.path }}</p>
                      <p class="text-xs text-secondary mt-0.5">
                        <span class="font-medium">{{ nfs.source }}</span>
                        <span class="mx-1">|</span>
                        {{ nfs.fs_type }}
                        <span v-if="nfs.free_space_gb" class="ml-2 text-emerald-600 dark:text-emerald-400">
                          {{ nfs.free_space_gb }} GB free
                        </span>
                      </p>
                    </div>
                  </div>
                  <div v-if="form.nfs_storage_path === nfs.path" class="p-1.5 rounded-full bg-emerald-500">
                    <CheckIcon class="h-4 w-4 text-white" />
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="mt-4 p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
              <div class="flex items-start gap-3">
                <ExclamationTriangleIcon class="h-5 w-5 text-gray-400 flex-shrink-0 mt-0.5" />
                <div class="text-sm">
                  <p class="font-medium text-primary">No NFS Storage Detected</p>
                  <p class="text-secondary mt-1">
                    Check that the NFS share is properly mounted at <code class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 font-mono text-xs">{{ storageDetection?.environment?.nfs_mount_point || '/mnt/backups' }}</code>
                  </p>
                </div>
              </div>
            </div>

            <div class="mt-4">
              <label class="block text-sm font-medium text-primary mb-2">Custom NFS Path</label>
              <div class="flex gap-3">
                <input
                  v-model="form.nfs_storage_path"
                  type="text"
                  class="input-field flex-1 font-mono"
                  placeholder="/mnt/backups"
                />
                <button
                  @click="validatePath(form.nfs_storage_path)"
                  :disabled="validatingPath || !form.nfs_storage_path"
                  class="btn-secondary px-4"
                >
                  {{ validatingPath ? 'Checking...' : 'Validate' }}
                </button>
              </div>
            </div>

            <div class="mt-4 flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
              <div>
                <p class="font-medium text-primary">Enable NFS Storage</p>
                <p class="text-sm text-secondary">Store final backups on NFS network storage</p>
              </div>
              <button
                @click="form.nfs_enabled = !form.nfs_enabled"
                :class="[
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                  form.nfs_enabled ? 'bg-emerald-500' : 'bg-gray-300 dark:bg-gray-600'
                ]"
              >
                <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.nfs_enabled ? 'translate-x-6' : 'translate-x-1']" />
              </button>
            </div>
          </div>
        </div>

        <!-- Backup Workflow Section -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <button
            @click="toggleSection('backupWorkflow')"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2.5 rounded-xl bg-gradient-to-br from-blue-100 to-indigo-100 dark:from-blue-900/30 dark:to-indigo-900/30">
                <ArrowRightIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Backup Workflow</h3>
                <p class="text-sm text-secondary">How backups are created and stored</p>
              </div>
            </div>
            <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.backupWorkflow ? 'rotate-180' : '']" />
          </button>

          <div v-if="sections.backupWorkflow" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <div class="mt-4 space-y-3">
              <label
                :class="[
                  'flex items-start gap-4 p-4 rounded-lg border-2 cursor-pointer transition-all',
                  form.backup_workflow === 'direct'
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-blue-300'
                ]"
              >
                <input type="radio" v-model="form.backup_workflow" value="direct" class="mt-1 h-4 w-4 text-blue-500" />
                <div class="flex-1">
                  <p class="font-medium text-primary">Direct to Destination</p>
                  <p class="text-sm text-secondary mt-1">Faster but less safe if network issues occur</p>
                </div>
              </label>

              <label
                :class="[
                  'flex items-start gap-4 p-4 rounded-lg border-2 cursor-pointer transition-all',
                  form.backup_workflow === 'stage_then_copy'
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-blue-300'
                ]"
              >
                <input type="radio" v-model="form.backup_workflow" value="stage_then_copy" class="mt-1 h-4 w-4 text-blue-500" />
                <div class="flex-1">
                  <div class="flex items-center gap-2">
                    <p class="font-medium text-primary">Stage Locally, Then Copy</p>
                    <span class="px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400">Recommended</span>
                  </div>
                  <p class="text-sm text-secondary mt-1">Safer - verify locally before copying to NFS</p>
                </div>
              </label>
            </div>

            <div v-if="form.nfs_enabled" class="mt-4">
              <label class="block text-sm font-medium text-primary mb-2">Final Storage Location</label>
              <select v-model="form.storage_preference" class="input-field w-full">
                <option value="nfs">NFS only</option>
                <option value="local">Local only</option>
                <option value="both">Both (redundant)</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <!-- Schedule Tab -->
      <div v-if="activeTab === 'schedule'" class="space-y-4">
        <!-- Schedule Configuration -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <button
            @click="toggleSection('scheduleConfig')"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2.5 rounded-xl bg-gradient-to-br from-emerald-100 to-teal-100 dark:from-emerald-900/30 dark:to-teal-900/30">
                <CalendarIcon class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Backup Schedule</h3>
                <p class="text-sm text-secondary">Configure automatic backup timing</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span v-if="form.schedule_enabled" class="px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400">
                Active
              </span>
              <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.scheduleConfig ? 'rotate-180' : '']" />
            </div>
          </button>

          <div v-if="sections.scheduleConfig" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <div class="mt-4 flex items-center justify-between p-4 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800">
              <div>
                <p class="font-medium text-emerald-800 dark:text-emerald-300">Enable Scheduled Backups</p>
                <p class="text-sm text-emerald-700 dark:text-emerald-400">Automatically run backups on a schedule</p>
              </div>
              <button
                @click="form.schedule_enabled = !form.schedule_enabled"
                :class="[
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                  form.schedule_enabled ? 'bg-emerald-500' : 'bg-gray-300 dark:bg-gray-600'
                ]"
              >
                <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.schedule_enabled ? 'translate-x-6' : 'translate-x-1']" />
              </button>
            </div>

            <div v-if="form.schedule_enabled" class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-primary mb-2">Frequency</label>
                <select v-model="form.schedule_frequency" class="input-field w-full">
                  <option value="hourly">Hourly</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-primary mb-2">Time</label>
                <input v-model="form.schedule_time" type="time" class="input-field w-full" />
              </div>

              <div v-if="form.schedule_frequency === 'weekly'">
                <label class="block text-sm font-medium text-primary mb-2">Day of Week</label>
                <select v-model="form.schedule_day_of_week" class="input-field w-full">
                  <option :value="0">Monday</option>
                  <option :value="1">Tuesday</option>
                  <option :value="2">Wednesday</option>
                  <option :value="3">Thursday</option>
                  <option :value="4">Friday</option>
                  <option :value="5">Saturday</option>
                  <option :value="6">Sunday</option>
                </select>
              </div>

              <div v-if="form.schedule_frequency === 'monthly'">
                <label class="block text-sm font-medium text-primary mb-2">Day of Month</label>
                <input v-model.number="form.schedule_day_of_month" type="number" min="1" max="31" class="input-field w-full" />
              </div>
            </div>
          </div>
        </div>

        <!-- Backup Contents -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <button
            @click="toggleSection('backupContents')"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2.5 rounded-xl bg-gradient-to-br from-blue-100 to-indigo-100 dark:from-blue-900/30 dark:to-indigo-900/30">
                <DocumentTextIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Backup Contents</h3>
                <p class="text-sm text-secondary">What to include in backups</p>
              </div>
            </div>
            <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.backupContents ? 'rotate-180' : '']" />
          </button>

          <div v-if="sections.backupContents" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <div class="mt-4">
              <label class="block text-sm font-medium text-primary mb-2">Default Backup Type</label>
              <select v-model="form.default_backup_type" class="input-field w-full">
                <option value="postgres_full">Full PostgreSQL Backup (n8n + management)</option>
                <option value="postgres_n8n">n8n Database Only</option>
                <option value="postgres_mgmt">Management Database Only</option>
              </select>
            </div>

            <div class="mt-4 space-y-3">
              <label class="flex items-center gap-3 cursor-pointer p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/30">
                <input v-model="form.include_n8n_config" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-blue-500" />
                <span class="text-sm text-primary">Include n8n configuration files</span>
              </label>
              <label class="flex items-center gap-3 cursor-pointer p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/30">
                <input v-model="form.include_ssl_certs" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-blue-500" />
                <span class="text-sm text-primary">Include SSL certificates</span>
              </label>
              <label class="flex items-center gap-3 cursor-pointer p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/30">
                <input v-model="form.include_env_files" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-blue-500" />
                <span class="text-sm text-primary">Include environment files (.env)</span>
              </label>
            </div>
          </div>
        </div>
      </div>

      <!-- Retention Tab -->
      <div v-if="activeTab === 'retention'" class="space-y-4">
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <button
            @click="toggleSection('retentionPolicy')"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2.5 rounded-xl bg-gradient-to-br from-amber-100 to-orange-100 dark:from-amber-900/30 dark:to-orange-900/30">
                <TrashIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Retention Policy</h3>
                <p class="text-sm text-secondary">Automatic backup cleanup rules</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span v-if="form.retention_enabled" class="px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
                Active
              </span>
              <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.retentionPolicy ? 'rotate-180' : '']" />
            </div>
          </button>

          <div v-if="sections.retentionPolicy" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <div class="mt-4 flex items-center justify-between p-4 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
              <div>
                <p class="font-medium text-amber-800 dark:text-amber-300">Enable Automatic Cleanup</p>
                <p class="text-sm text-amber-700 dark:text-amber-400">Delete old backups based on retention rules</p>
              </div>
              <button
                @click="form.retention_enabled = !form.retention_enabled"
                :class="[
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                  form.retention_enabled ? 'bg-amber-500' : 'bg-gray-300 dark:bg-gray-600'
                ]"
              >
                <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.retention_enabled ? 'translate-x-6' : 'translate-x-1']" />
              </button>
            </div>

            <div v-if="form.retention_enabled" class="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div class="p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                <label class="block text-sm font-medium text-primary mb-2">Keep For (days)</label>
                <input v-model.number="form.retention_days" type="number" min="1" max="365" class="input-field w-full" />
                <p class="mt-1 text-xs text-secondary">Delete backups older than this</p>
              </div>

              <div class="p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                <label class="block text-sm font-medium text-primary mb-2">Max Backups</label>
                <input v-model.number="form.retention_count" type="number" min="1" max="100" class="input-field w-full" />
                <p class="mt-1 text-xs text-secondary">Maximum number to keep</p>
              </div>

              <div class="p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                <label class="block text-sm font-medium text-primary mb-2">Min Backups</label>
                <input v-model.number="form.retention_min_count" type="number" min="1" max="50" class="input-field w-full" />
                <p class="mt-1 text-xs text-secondary">Never delete below this</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Compression Tab -->
      <div v-if="activeTab === 'compression'" class="space-y-4">
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <button
            @click="toggleSection('compressionSettings')"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2.5 rounded-xl bg-gradient-to-br from-purple-100 to-pink-100 dark:from-purple-900/30 dark:to-pink-900/30">
                <ArchiveBoxIcon class="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Compression Settings</h3>
                <p class="text-sm text-secondary">Reduce backup file sizes</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span v-if="form.compression_enabled" class="px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400">
                Active
              </span>
              <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.compressionSettings ? 'rotate-180' : '']" />
            </div>
          </button>

          <div v-if="sections.compressionSettings" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <div class="mt-4 flex items-center justify-between p-4 rounded-lg bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800">
              <div>
                <p class="font-medium text-purple-800 dark:text-purple-300">Enable Compression</p>
                <p class="text-sm text-purple-700 dark:text-purple-400">Compress backups to save storage space</p>
              </div>
              <button
                @click="form.compression_enabled = !form.compression_enabled"
                :class="[
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                  form.compression_enabled ? 'bg-purple-500' : 'bg-gray-300 dark:bg-gray-600'
                ]"
              >
                <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.compression_enabled ? 'translate-x-6' : 'translate-x-1']" />
              </button>
            </div>

            <div v-if="form.compression_enabled" class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                <label class="block text-sm font-medium text-primary mb-2">Algorithm</label>
                <select v-model="form.compression_algorithm" class="input-field w-full">
                  <option value="gzip">Gzip (widely compatible)</option>
                  <option value="zstd">Zstandard (faster, better ratio)</option>
                </select>
              </div>

              <div class="p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                <label class="block text-sm font-medium text-primary mb-2">Level: {{ form.compression_level }}</label>
                <input
                  v-model.number="form.compression_level"
                  type="range"
                  min="1"
                  :max="compressionLevelMax"
                  class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
                />
                <div class="flex justify-between text-xs text-secondary mt-1">
                  <span>Faster</span>
                  <span>Smaller</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Notifications Tab -->
      <div v-if="activeTab === 'notifications'" class="space-y-4">
        <!-- Channel Selection First (Required) -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <button
            @click="toggleSection('notifyChannels')"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2.5 rounded-xl bg-gradient-to-br from-indigo-100 to-purple-100 dark:from-indigo-900/30 dark:to-purple-900/30">
                <ServerIcon class="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Notification Channel</h3>
                <p class="text-sm text-secondary">Select where to send backup notifications</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span v-if="form.notification_channel_id" class="px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-400">
                Selected
              </span>
              <span v-else class="px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
                Required
              </span>
              <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.notifyChannels ? 'rotate-180' : '']" />
            </div>
          </button>

          <div v-if="sections.notifyChannels" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <!-- Configure Notifications Button -->
            <div class="mt-4 flex justify-end">
              <button
                @click="router.push('/notifications')"
                class="btn-secondary text-sm flex items-center gap-2"
              >
                <Cog6ToothIcon class="h-4 w-4" />
                Configure Notification Channels
              </button>
            </div>

            <div v-if="loadingChannels" class="mt-4 flex justify-center py-8">
              <LoadingSpinner text="Loading notification channels..." />
            </div>

            <div v-else-if="allNotificationChannels.length > 0" class="mt-4 space-y-3">
              <p class="text-sm font-medium text-secondary">Select a channel or group to receive backup notifications</p>

              <!-- Services -->
              <div v-if="notificationServices.length > 0">
                <p class="text-xs font-medium text-muted uppercase tracking-wide mb-2">Channels</p>
                <div class="space-y-2">
                  <div
                    v-for="channel in allNotificationChannels.filter(c => c.type === 'service')"
                    :key="`service-${channel.id}`"
                    :class="[
                      'p-4 rounded-lg border-2 cursor-pointer transition-all',
                      form.notification_channel_id === channel.id && form.notification_channel_type === 'service'
                        ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20'
                        : 'border-gray-200 dark:border-gray-700 hover:border-indigo-300'
                    ]"
                    @click="selectNotificationChannel(channel)"
                  >
                    <div class="flex items-center justify-between">
                      <div class="flex items-center gap-3">
                        <div class="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900/40">
                          <BellIcon class="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                        </div>
                        <div>
                          <p class="font-medium text-primary">{{ channel.name }}</p>
                          <p class="text-xs text-secondary">{{ channel.description }}</p>
                        </div>
                      </div>
                      <div v-if="form.notification_channel_id === channel.id && form.notification_channel_type === 'service'" class="p-1.5 rounded-full bg-indigo-500">
                        <CheckIcon class="h-4 w-4 text-white" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Groups -->
              <div v-if="notificationGroups.length > 0" class="mt-4">
                <p class="text-xs font-medium text-muted uppercase tracking-wide mb-2">Groups</p>
                <div class="space-y-2">
                  <div
                    v-for="channel in allNotificationChannels.filter(c => c.type === 'group')"
                    :key="`group-${channel.id}`"
                    :class="[
                      'p-4 rounded-lg border-2 cursor-pointer transition-all',
                      form.notification_channel_id === channel.id && form.notification_channel_type === 'group'
                        ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                        : 'border-gray-200 dark:border-gray-700 hover:border-purple-300'
                    ]"
                    @click="selectNotificationChannel(channel)"
                  >
                    <div class="flex items-center justify-between">
                      <div class="flex items-center gap-3">
                        <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-900/40">
                          <FolderIcon class="h-5 w-5 text-purple-600 dark:text-purple-400" />
                        </div>
                        <div>
                          <p class="font-medium text-primary">{{ channel.name }}</p>
                          <p class="text-xs text-secondary">{{ channel.description }}</p>
                        </div>
                      </div>
                      <div v-if="form.notification_channel_id === channel.id && form.notification_channel_type === 'group'" class="p-1.5 rounded-full bg-purple-500">
                        <CheckIcon class="h-4 w-4 text-white" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <button
                v-if="form.notification_channel_id"
                @click="clearNotificationChannel"
                class="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              >
                Clear selection
              </button>
            </div>

            <div v-else class="mt-4 p-4 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
              <div class="flex items-start gap-3">
                <ExclamationTriangleIcon class="h-5 w-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                <div class="text-sm">
                  <p class="font-medium text-amber-800 dark:text-amber-300">No Notification Channels Configured</p>
                  <p class="text-amber-700 dark:text-amber-400 mt-1">
                    You need to configure at least one notification channel (NTFY, email, etc.) before enabling backup notifications.
                  </p>
                  <button
                    @click="router.push('/notifications')"
                    class="mt-3 btn-primary text-sm"
                  >
                    Configure Notifications
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Notification Triggers (only show if channel selected) -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <button
            @click="toggleSection('notifySettings')"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2.5 rounded-xl bg-gradient-to-br from-pink-100 to-rose-100 dark:from-pink-900/30 dark:to-rose-900/30">
                <BellIcon class="h-5 w-5 text-pink-600 dark:text-pink-400" />
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Notification Triggers</h3>
                <p class="text-sm text-secondary">When to send backup notifications</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span v-if="!canEnableNotifications" class="text-xs text-amber-600 dark:text-amber-400">Select channel first</span>
              <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.notifySettings ? 'rotate-180' : '']" />
            </div>
          </button>

          <div v-if="sections.notifySettings" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <div v-if="!canEnableNotifications" class="mt-4 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
              <p class="text-sm text-amber-700 dark:text-amber-400">
                Please select a notification channel above before enabling notifications.
              </p>
            </div>

            <div class="mt-4 space-y-3" :class="{ 'opacity-50 pointer-events-none': !canEnableNotifications }">
              <div class="flex items-center justify-between p-4 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800">
                <div class="flex items-center gap-3">
                  <CheckCircleIcon class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                  <div>
                    <p class="font-medium text-emerald-800 dark:text-emerald-300">Notify on Success</p>
                    <p class="text-sm text-emerald-700 dark:text-emerald-400">When backup completes successfully</p>
                  </div>
                </div>
                <button
                  @click="tryEnableNotification('success')"
                  :class="[
                    'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                    form.notify_on_success ? 'bg-emerald-500' : 'bg-gray-300 dark:bg-gray-600'
                  ]"
                >
                  <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.notify_on_success ? 'translate-x-6' : 'translate-x-1']" />
                </button>
              </div>

              <div class="flex items-center justify-between p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                <div class="flex items-center gap-3">
                  <XMarkIcon class="h-5 w-5 text-red-600 dark:text-red-400" />
                  <div>
                    <p class="font-medium text-red-800 dark:text-red-300">Notify on Failure</p>
                    <p class="text-sm text-red-700 dark:text-red-400">When backup fails</p>
                  </div>
                </div>
                <button
                  @click="tryEnableNotification('failure')"
                  :class="[
                    'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                    form.notify_on_failure ? 'bg-red-500' : 'bg-gray-300 dark:bg-gray-600'
                  ]"
                >
                  <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.notify_on_failure ? 'translate-x-6' : 'translate-x-1']" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Verification Tab -->
      <div v-if="activeTab === 'verification'" class="space-y-4">
        <!-- Auto Verification -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <button
            @click="toggleSection('autoVerify')"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2.5 rounded-xl bg-gradient-to-br from-cyan-100 to-blue-100 dark:from-cyan-900/30 dark:to-blue-900/30">
                <ShieldCheckIcon class="h-5 w-5 text-cyan-600 dark:text-cyan-400" />
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Automatic Verification</h3>
                <p class="text-sm text-secondary">Auto-verify backups after creation</p>
              </div>
            </div>
            <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.autoVerify ? 'rotate-180' : '']" />
          </button>

          <div v-if="sections.autoVerify" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <div class="mt-4 space-y-3">
              <div class="flex items-center justify-between p-4 rounded-lg bg-cyan-50 dark:bg-cyan-900/20 border border-cyan-200 dark:border-cyan-800">
                <div>
                  <p class="font-medium text-cyan-800 dark:text-cyan-300">Auto-verify Backups</p>
                  <p class="text-sm text-cyan-700 dark:text-cyan-400">Automatically verify backups on a schedule</p>
                </div>
                <button
                  @click="form.auto_verify_enabled = !form.auto_verify_enabled"
                  :class="[
                    'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                    form.auto_verify_enabled ? 'bg-cyan-500' : 'bg-gray-300 dark:bg-gray-600'
                  ]"
                >
                  <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.auto_verify_enabled ? 'translate-x-6' : 'translate-x-1']" />
                </button>
              </div>

              <div class="flex items-center justify-between p-4 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
                <div>
                  <p class="font-medium text-blue-800 dark:text-blue-300">Verify After Backup</p>
                  <p class="text-sm text-blue-700 dark:text-blue-400">Run verification immediately after each backup</p>
                </div>
                <button
                  @click="form.verify_after_backup = !form.verify_after_backup"
                  :class="[
                    'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                    form.verify_after_backup ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                  ]"
                >
                  <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.verify_after_backup ? 'translate-x-6' : 'translate-x-1']" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Manual Verification -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <button
            @click="toggleSection('manualVerify')"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2.5 rounded-xl bg-gradient-to-br from-emerald-100 to-teal-100 dark:from-emerald-900/30 dark:to-teal-900/30">
                <PlayIcon class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Manual Verification</h3>
                <p class="text-sm text-secondary">Verify a specific backup now</p>
              </div>
            </div>
            <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.manualVerify ? 'rotate-180' : '']" />
          </button>

          <div v-if="sections.manualVerify" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <div v-if="loadingBackups" class="mt-4 flex justify-center py-8">
              <LoadingSpinner text="Loading backups..." />
            </div>

            <div v-else-if="verifiableBackups.length > 0" class="mt-4 space-y-4">
              <div>
                <label class="block text-sm font-medium text-primary mb-2">Select Backup to Verify</label>
                <select v-model="selectedBackupId" class="input-field w-full">
                  <option :value="null">-- Select a backup --</option>
                  <option v-for="backup in verifiableBackups" :key="backup.id" :value="backup.id">
                    {{ formatDate(backup.created_at) }} - {{ backup.type }} ({{ formatBytes(backup.size_bytes) }})
                    <span v-if="backup.verification_status">- {{ backup.verification_status }}</span>
                  </option>
                </select>
              </div>

              <button
                @click="runManualVerification"
                :disabled="!selectedBackupId || verifying"
                class="btn-primary w-full flex items-center justify-center gap-2"
              >
                <ArrowPathIcon v-if="verifying" class="h-4 w-4 animate-spin" />
                <ShieldCheckIcon v-else class="h-4 w-4" />
                {{ verifying ? 'Verifying...' : 'Run Verification' }}
              </button>

              <div v-if="verificationResult && !verificationResult.error" class="p-4 rounded-lg" :class="verificationResult.overall_status === 'passed' ? 'bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800' : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'">
                <div class="flex items-center gap-2 mb-2">
                  <CheckCircleIcon v-if="verificationResult.overall_status === 'passed'" class="h-5 w-5 text-emerald-500" />
                  <XMarkIcon v-else class="h-5 w-5 text-red-500" />
                  <span class="font-medium" :class="verificationResult.overall_status === 'passed' ? 'text-emerald-800 dark:text-emerald-300' : 'text-red-800 dark:text-red-300'">
                    Verification {{ verificationResult.overall_status }}
                  </span>
                </div>
                <div v-if="verificationResult.checks" class="text-sm text-secondary">
                  <p v-for="(check, key) in verificationResult.checks" :key="key">
                    {{ key }}: {{ check.status }}
                  </p>
                </div>
              </div>
            </div>

            <div v-else class="mt-4 p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
              <div class="flex items-start gap-3">
                <InformationCircleIcon class="h-5 w-5 text-gray-400 flex-shrink-0 mt-0.5" />
                <div class="text-sm">
                  <p class="font-medium text-primary">No Backups Available</p>
                  <p class="text-secondary mt-1">Create a backup first to verify it.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
