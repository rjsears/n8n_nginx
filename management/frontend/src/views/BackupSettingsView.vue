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


// Collapsible sections state - all start collapsed
const sections = ref({
  backupDestination: false,
  backupWorkflow: false,
  stagingArea: false,
  localPaths: false,
  scheduleConfig: false,
  backupContents: false,
  retentionPolicy: false,
  compressionSettings: false,
  notifySettings: false,
  notifyChannels: false,
})

// Computed properties for time picker
const scheduleHour = computed({
  get: () => {
    const [h] = (form.value.schedule_time || '00:00').split(':')
    return parseInt(h, 10)
  },
  set: (val) => {
    const [, m] = (form.value.schedule_time || '00:00').split(':')
    form.value.schedule_time = `${String(val).padStart(2, '0')}:${m}`
  }
})

const scheduleMinute = computed({
  get: () => {
    const [, m] = (form.value.schedule_time || '00:00').split(':')
    return parseInt(m, 10)
  },
  set: (val) => {
    const [h] = (form.value.schedule_time || '00:00').split(':')
    form.value.schedule_time = `${h}:${String(val).padStart(2, '0')}`
  }
})

const formattedTime = computed(() => {
  const h = scheduleHour.value
  const m = scheduleMinute.value
  const period = h >= 12 ? 'PM' : 'AM'
  const displayHour = h === 0 ? 12 : h > 12 ? h - 12 : h
  return `${displayHour}:${String(m).padStart(2, '0')} ${period}`
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
  // Retention - Tiered GFS (Grandfather-Father-Son) strategy
  retention_enabled: true,
  retention_daily_count: 7,    // Keep daily backups for X days
  retention_weekly_count: 4,   // Keep weekly backups for X weeks
  retention_monthly_count: 6,  // Keep monthly backups for X months
  retention_min_count: 3,      // Minimum backups to always keep
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
  notification_channel_id: null, // Single channel ID
  // Verification
  auto_verify_enabled: false,
  verify_frequency: 1, // Verify every Nth backup (1 = every backup)
})

const tabs = [
  { id: 'storage', name: 'Storage', icon: FolderIcon, iconColor: 'text-blue-500', bgActive: 'bg-blue-500/15 dark:bg-blue-500/20', textActive: 'text-blue-700 dark:text-blue-400', borderActive: 'border-blue-500/30' },
  { id: 'schedule', name: 'Schedule', icon: ClockIcon, iconColor: 'text-emerald-500', bgActive: 'bg-emerald-500/15 dark:bg-emerald-500/20', textActive: 'text-emerald-700 dark:text-emerald-400', borderActive: 'border-emerald-500/30' },
  { id: 'retention', name: 'Retention', icon: TrashIcon, iconColor: 'text-amber-500', bgActive: 'bg-amber-500/15 dark:bg-amber-500/20', textActive: 'text-amber-700 dark:text-amber-400', borderActive: 'border-amber-500/30' },
  { id: 'compression', name: 'Compression', icon: ServerIcon, iconColor: 'text-purple-500', bgActive: 'bg-purple-500/15 dark:bg-purple-500/20', textActive: 'text-purple-700 dark:text-purple-400', borderActive: 'border-purple-500/30' },
  { id: 'verification', name: 'Verification', icon: ShieldCheckIcon, iconColor: 'text-cyan-500', bgActive: 'bg-cyan-500/15 dark:bg-cyan-500/20', textActive: 'text-cyan-700 dark:text-cyan-400', borderActive: 'border-cyan-500/30' },
  { id: 'notifications', name: 'Notifications', icon: BellIcon, iconColor: 'text-pink-500', bgActive: 'bg-pink-500/15 dark:bg-pink-500/20', textActive: 'text-pink-700 dark:text-pink-400', borderActive: 'border-pink-500/30' },
]

const compressionLevelMax = computed(() => {
  return form.value.compression_algorithm === 'zstd' ? 22 : 9
})

const hasNfsConfigured = computed(() => {
  return storageDetection.value?.has_nfs ||
    storageDetection.value?.environment?.nfs_configured ||
    (storageDetection.value?.environment?.nfs_server &&
     storageDetection.value?.environment?.nfs_server !== '')
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

// Check if notifications can be enabled (requires a channel to be selected)
const canEnableNotifications = computed(() => {
  return form.value.notification_channel_id !== null
})

// Get the selected channel info for display
const selectedChannel = computed(() => {
  if (!form.value.notification_channel_id) return null
  return notificationServices.value.find(s => s.id === form.value.notification_channel_id)
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

function selectStorageDestination(destination) {
  form.value.storage_preference = destination
  if (destination === 'nfs') {
    form.value.nfs_enabled = true
    // If no NFS path selected yet and there are mounts, select the first one
    if (!form.value.nfs_storage_path && nfsMounts.value.length > 0) {
      form.value.nfs_storage_path = nfsMounts.value[0].path
    }
  } else {
    form.value.nfs_enabled = false
  }
}

function selectNfsMount(path) {
  form.value.storage_preference = 'nfs'
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

function goBack() {
  router.push('/backups')
}

function toggleSection(section) {
  sections.value[section] = !sections.value[section]
}

function selectNotificationChannel(channelId) {
  // Toggle: if same channel, deselect; otherwise select the new one
  if (form.value.notification_channel_id === channelId) {
    form.value.notification_channel_id = null
    form.value.notify_on_success = false
    form.value.notify_on_failure = false
  } else {
    form.value.notification_channel_id = channelId
  }
}

function clearNotificationChannel() {
  form.value.notification_channel_id = null
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

    <!-- Cool Loading Animation -->
    <div v-if="loading" class="py-16 flex flex-col items-center justify-center">
      <div class="relative flex items-center gap-8">
        <!-- Source Drive -->
        <div class="relative">
          <div class="w-16 h-20 rounded-lg bg-gradient-to-br from-blue-100 to-blue-200 dark:from-blue-900/40 dark:to-blue-800/40 border-2 border-blue-300 dark:border-blue-700 flex items-center justify-center shadow-lg">
            <CircleStackIcon class="h-8 w-8 text-blue-600 dark:text-blue-400" />
          </div>
          <div class="absolute -bottom-1 left-1/2 transform -translate-x-1/2 w-12 h-1.5 bg-blue-300 dark:bg-blue-700 rounded-full"></div>
        </div>

        <!-- Animated Files -->
        <div class="relative w-24 h-8 overflow-hidden">
          <div class="file-animation absolute flex items-center gap-1">
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
            <FolderIcon class="h-8 w-8 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div class="absolute -bottom-1 left-1/2 transform -translate-x-1/2 w-12 h-1.5 bg-emerald-300 dark:bg-emerald-700 rounded-full"></div>
        </div>
      </div>
      <p class="mt-6 text-sm font-medium text-secondary">Loading backup configuration...</p>
      <p class="mt-1 text-xs text-muted">Detecting storage locations</p>
    </div>

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

      <!-- Storage Tab - 3-Step Configuration Flow -->
      <div v-if="activeTab === 'storage'" class="space-y-4">
        <!-- Important Backup Notice -->
        <div class="p-4 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/50">
          <div class="flex gap-3">
            <div class="flex-shrink-0">
              <div class="p-2 rounded-lg bg-amber-100 dark:bg-amber-800/50">
                <ExclamationTriangleIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
            </div>
            <div>
              <h4 class="font-semibold text-amber-800 dark:text-amber-300 mb-1">Important Backup Information</h4>
              <p class="text-sm text-amber-700 dark:text-amber-400">
                This backup system only backs up <span class="font-semibold">N8N workflows</span> and <span class="font-semibold">N8N Management configuration files</span>.
                It does <span class="font-semibold">NOT</span> backup any other data, additional containers, or configuration files you may have added to the system.
              </p>
            </div>
          </div>
        </div>

        <!-- Introduction -->
        <div class="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-xl border border-blue-200 dark:border-blue-800 p-4">
          <div class="flex items-start gap-3">
            <InformationCircleIcon class="h-5 w-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
            <div class="text-sm">
              <p class="font-medium text-blue-800 dark:text-blue-300">Storage Configuration</p>
              <p class="text-blue-700 dark:text-blue-400 mt-1">
                Configure where your backups will be stored. Follow the steps below to set up your backup destination.
              </p>
            </div>
          </div>
        </div>

        <!-- STEP 1: Backup Destination -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <button
            @click="toggleSection('backupDestination')"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="flex items-center justify-center w-8 h-8 rounded-full bg-blue-500 text-white font-bold text-sm">
                1
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Backup Destination</h3>
                <p class="text-sm text-secondary">Choose where backups will be stored</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span :class="[
                'px-2.5 py-1 rounded-full text-xs font-medium',
                form.storage_preference === 'nfs'
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400'
                  : 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400'
              ]">
                {{ form.storage_preference === 'nfs' ? 'Network Storage' : 'Local Storage' }}
              </span>
              <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.backupDestination ? 'rotate-180' : '']" />
            </div>
          </button>

          <div v-if="sections.backupDestination" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <div class="mt-4 space-y-3">
              <!-- Local Storage Option -->
              <label
                :class="[
                  'flex items-start gap-4 p-4 rounded-lg border-2 cursor-pointer transition-all',
                  form.storage_preference === 'local'
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-blue-300'
                ]"
                @click="selectStorageDestination('local')"
              >
                <input type="radio" v-model="form.storage_preference" value="local" class="mt-1 h-4 w-4 text-blue-500" />
                <div class="flex-1">
                  <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/40">
                      <CircleStackIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
                    </div>
                    <div>
                      <p class="font-medium text-primary">Local Storage</p>
                      <p class="text-sm text-secondary mt-0.5">Store backups on the local Docker volume</p>
                    </div>
                  </div>
                  <div v-if="stagingArea" class="mt-3 ml-11 p-3 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                    <div class="flex items-center gap-2">
                      <FolderIcon class="h-4 w-4 text-blue-500" />
                      <code class="text-xs font-mono text-primary">{{ stagingArea.path }}</code>
                      <span v-if="stagingArea.free_space_gb" class="px-1.5 py-0.5 rounded text-xs bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                        {{ stagingArea.free_space_gb }} GB free
                      </span>
                      <span v-else-if="detectingStorage" class="px-1.5 py-0.5 rounded text-xs bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 flex items-center gap-1">
                        <ArrowPathIcon class="h-3 w-3 animate-spin" />
                        Checking...
                      </span>
                      <span v-else class="px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                        Unknown
                      </span>
                    </div>
                  </div>
                </div>
              </label>

              <!-- Network Storage Option (NFS) -->
              <label
                :class="[
                  'flex items-start gap-4 p-4 rounded-lg border-2 transition-all',
                  hasNfsConfigured ? 'cursor-pointer' : 'cursor-not-allowed opacity-60',
                  form.storage_preference === 'nfs'
                    ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-emerald-300'
                ]"
                @click="hasNfsConfigured && selectStorageDestination('nfs')"
              >
                <input type="radio" v-model="form.storage_preference" value="nfs" :disabled="!hasNfsConfigured" class="mt-1 h-4 w-4 text-emerald-500" />
                <div class="flex-1">
                  <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-900/40">
                      <CloudIcon class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <div>
                      <p class="font-medium text-primary">Network Storage (NFS)</p>
                      <p class="text-sm text-secondary mt-0.5">
                        <span v-if="hasNfsConfigured">Store backups on remote NFS server</span>
                        <span v-else class="text-amber-600 dark:text-amber-400">No NFS storage detected</span>
                      </p>
                    </div>
                  </div>

                  <!-- Show detected NFS mounts -->
                  <div v-if="nfsMounts.length > 0" class="mt-3 ml-11 space-y-2">
                    <div
                      v-for="nfs in nfsMounts"
                      :key="nfs.path"
                      :class="[
                        'p-3 rounded-lg border transition-all',
                        form.nfs_storage_path === nfs.path && form.storage_preference === 'nfs'
                          ? 'bg-emerald-100 dark:bg-emerald-900/40 border-emerald-300 dark:border-emerald-700'
                          : 'bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700'
                      ]"
                      @click.stop="selectNfsMount(nfs.path)"
                    >
                      <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                          <ServerIcon class="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                          <code class="text-xs font-mono text-primary">{{ nfs.path }}</code>
                        </div>
                        <div class="flex items-center gap-2">
                          <span v-if="nfs.free_space_gb" class="text-xs text-emerald-600 dark:text-emerald-400">
                            {{ nfs.free_space_gb }} GB free
                          </span>
                          <div v-if="form.nfs_storage_path === nfs.path && form.storage_preference === 'nfs'" class="p-1 rounded-full bg-emerald-500">
                            <CheckIcon class="h-3 w-3 text-white" />
                          </div>
                        </div>
                      </div>
                      <p class="text-xs text-secondary mt-1 ml-6">
                        {{ nfs.source }} ({{ nfs.fs_type }})
                        <span v-if="nfs.host_mount" class="text-gray-400"> → {{ nfs.host_mount }}</span>
                      </p>
                    </div>
                  </div>

                  <!-- NFS configured via env but not mounted -->
                  <div v-else-if="storageDetection?.environment?.nfs_configured" class="mt-3 ml-11 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
                    <div class="flex items-start gap-2">
                      <ExclamationTriangleIcon class="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                      <div class="text-xs">
                        <p class="font-medium text-amber-800 dark:text-amber-300">NFS Mount Issue</p>
                        <p class="text-amber-700 dark:text-amber-400 mt-0.5">
                          NFS is configured (<code class="px-1 py-0.5 rounded bg-amber-100 dark:bg-amber-900/50 font-mono">{{ storageDetection?.environment?.nfs_server }}:{{ storageDetection?.environment?.nfs_path }}</code>)
                          but the mount point is not accessible. Check that NFS is mounted on the host at
                          <code class="px-1 py-0.5 rounded bg-amber-100 dark:bg-amber-900/50 font-mono">{{ storageDetection?.environment?.nfs_local_mount || '/opt/n8n_backups' }}</code>
                          and verify with <code class="px-1 py-0.5 rounded bg-amber-100 dark:bg-amber-900/50 font-mono">mount | grep nfs</code>.
                        </p>
                      </div>
                    </div>
                  </div>

                  <!-- No NFS detected message -->
                  <div v-else class="mt-3 ml-11 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
                    <div class="flex items-start gap-2">
                      <ExclamationTriangleIcon class="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                      <div class="text-xs">
                        <p class="font-medium text-amber-800 dark:text-amber-300">NFS Not Configured</p>
                        <p class="text-amber-700 dark:text-amber-400 mt-0.5">
                          To use NFS storage, configure it during setup or mount an NFS share at
                          <code class="px-1 py-0.5 rounded bg-amber-100 dark:bg-amber-900/50 font-mono">{{ storageDetection?.environment?.nfs_mount_point || '/mnt/backups' }}</code>
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </label>
            </div>
          </div>
        </div>

        <!-- STEP 2: Backup Workflow (only if NFS selected) -->
        <Transition name="slide-fade">
          <div v-if="form.storage_preference === 'nfs'" class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
            <button
              @click="toggleSection('backupWorkflow')"
              class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
            >
              <div class="flex items-center gap-3">
                <div class="flex items-center justify-center w-8 h-8 rounded-full bg-indigo-500 text-white font-bold text-sm">
                  2
                </div>
                <div class="text-left">
                  <h3 class="font-semibold text-primary">Backup Workflow</h3>
                  <p class="text-sm text-secondary">How backups are transferred to NFS</p>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <span :class="[
                  'px-2.5 py-1 rounded-full text-xs font-medium',
                  form.backup_workflow === 'stage_then_copy'
                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400'
                    : 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-400'
                ]">
                  {{ form.backup_workflow === 'stage_then_copy' ? 'Stage & Copy' : 'Direct' }}
                </span>
                <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.backupWorkflow ? 'rotate-180' : '']" />
              </div>
            </button>

            <div v-if="sections.backupWorkflow" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
              <div class="mt-4 space-y-3">
                <!-- Direct to NFS Option -->
                <label
                  :class="[
                    'flex items-start gap-4 p-4 rounded-lg border-2 cursor-pointer transition-all',
                    form.backup_workflow === 'direct'
                      ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-indigo-300'
                  ]"
                >
                  <input type="radio" v-model="form.backup_workflow" value="direct" class="mt-1 h-4 w-4 text-indigo-500" />
                  <div class="flex-1">
                    <div class="flex items-center gap-2">
                      <p class="font-medium text-primary">Direct to NFS</p>
                    </div>
                    <p class="text-sm text-secondary mt-1">Write backups directly to NFS. Faster, but may be incomplete if network issues occur during backup.</p>
                    <div class="mt-2 flex items-center gap-4 text-xs">
                      <span class="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                        <CheckIcon class="h-3 w-3" /> Faster
                      </span>
                      <span class="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                        <ExclamationTriangleIcon class="h-3 w-3" /> Network-dependent
                      </span>
                    </div>
                  </div>
                </label>

                <!-- Stage Locally, Then Copy Option -->
                <label
                  :class="[
                    'flex items-start gap-4 p-4 rounded-lg border-2 cursor-pointer transition-all',
                    form.backup_workflow === 'stage_then_copy'
                      ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-emerald-300'
                  ]"
                >
                  <input type="radio" v-model="form.backup_workflow" value="stage_then_copy" class="mt-1 h-4 w-4 text-emerald-500" />
                  <div class="flex-1">
                    <div class="flex items-center gap-2">
                      <p class="font-medium text-primary">Stage Locally, Then Copy</p>
                      <span class="px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400">Recommended</span>
                    </div>
                    <p class="text-sm text-secondary mt-1">Create backup locally first, verify integrity, then copy to NFS. Ensures backup completes successfully before transfer.</p>
                    <div class="mt-2 flex items-center gap-4 text-xs">
                      <span class="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                        <CheckIcon class="h-3 w-3" /> Reliable
                      </span>
                      <span class="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                        <CheckIcon class="h-3 w-3" /> Verified
                      </span>
                      <span class="flex items-center gap-1 text-blue-600 dark:text-blue-400">
                        <CircleStackIcon class="h-3 w-3" /> Uses staging area
                      </span>
                    </div>
                  </div>
                </label>
              </div>
            </div>
          </div>
        </Transition>

        <!-- STEP 3: Local Staging Area (only if Stage & Copy workflow selected) -->
        <Transition name="slide-fade">
          <div v-if="form.storage_preference === 'nfs' && form.backup_workflow === 'stage_then_copy'" class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
            <button
              @click="toggleSection('stagingArea')"
              class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
            >
              <div class="flex items-center gap-3">
                <div class="flex items-center justify-center w-8 h-8 rounded-full bg-amber-500 text-white font-bold text-sm">
                  3
                </div>
                <div class="text-left">
                  <h3 class="font-semibold text-primary">Local Staging Area</h3>
                  <p class="text-sm text-secondary">Temporary storage for backup creation</p>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <span v-if="stagingArea?.is_writable" class="px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400">
                  Ready
                </span>
                <span v-else class="px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
                  Not Available
                </span>
                <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.stagingArea ? 'rotate-180' : '']" />
              </div>
            </button>

            <div v-if="sections.stagingArea" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
              <div class="mt-4 p-4 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
                <div class="flex items-start gap-3">
                  <InformationCircleIcon class="h-5 w-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                  <div class="text-sm">
                    <p class="font-medium text-amber-800 dark:text-amber-300">How Staging Works</p>
                    <p class="text-amber-700 dark:text-amber-400 mt-1">
                      Backups are created in the staging area first, verified for integrity, then copied to the final NFS destination.
                      The local copy is removed after successful transfer.
                    </p>
                  </div>
                </div>
              </div>

              <div class="mt-4 p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg bg-amber-100 dark:bg-amber-900/40">
                      <FolderIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
                    </div>
                    <div>
                      <p class="font-mono text-sm font-medium text-primary">{{ stagingArea?.path || '/app/backups' }}</p>
                      <p class="text-xs text-secondary mt-0.5">
                        <span v-if="stagingArea?.is_writable" class="text-emerald-600 dark:text-emerald-400">Available</span>
                        <span v-else class="text-red-500">Not writable</span>
                        <span v-if="stagingArea?.free_space_gb" class="ml-2">{{ stagingArea.free_space_gb }} GB free</span>
                      </p>
                    </div>
                  </div>
                  <span class="px-3 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
                    Staging
                  </span>
                </div>
              </div>

              <!-- Workflow Visualization -->
              <div class="mt-4 p-4 rounded-lg bg-gradient-to-r from-blue-50 via-amber-50 to-emerald-50 dark:from-blue-900/10 dark:via-amber-900/10 dark:to-emerald-900/10 border border-gray-200 dark:border-gray-700">
                <p class="text-xs font-medium text-secondary mb-3">Backup Flow</p>
                <div class="flex items-center justify-between gap-2">
                  <div class="flex flex-col items-center gap-1">
                    <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/40">
                      <CircleStackIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
                    </div>
                    <span class="text-xs text-secondary">Database</span>
                  </div>
                  <ArrowRightIcon class="h-4 w-4 text-gray-400 flex-shrink-0" />
                  <div class="flex flex-col items-center gap-1">
                    <div class="p-2 rounded-lg bg-amber-100 dark:bg-amber-900/40">
                      <FolderIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
                    </div>
                    <span class="text-xs text-secondary">Staging</span>
                  </div>
                  <ArrowRightIcon class="h-4 w-4 text-gray-400 flex-shrink-0" />
                  <div class="flex flex-col items-center gap-1">
                    <div class="p-2 rounded-lg bg-cyan-100 dark:bg-cyan-900/40">
                      <ShieldCheckIcon class="h-5 w-5 text-cyan-600 dark:text-cyan-400" />
                    </div>
                    <span class="text-xs text-secondary">Verify</span>
                  </div>
                  <ArrowRightIcon class="h-4 w-4 text-gray-400 flex-shrink-0" />
                  <div class="flex flex-col items-center gap-1">
                    <div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-900/40">
                      <CloudIcon class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <span class="text-xs text-secondary">NFS</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Transition>

        <!-- Summary Card -->
        <div class="bg-gradient-to-r from-gray-50 to-slate-50 dark:from-gray-800/50 dark:to-slate-800/50 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <h4 class="font-semibold text-primary mb-3 flex items-center gap-2">
            <InformationCircleIcon class="h-4 w-4 text-gray-400" />
            Configuration Summary
          </h4>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <!-- Destination -->
            <div :class="[
              'p-3 rounded-lg border',
              form.storage_preference === 'nfs'
                ? 'bg-emerald-50/50 dark:bg-emerald-900/10 border-emerald-200 dark:border-emerald-800/50'
                : 'bg-blue-50/50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800/50'
            ]">
              <div class="flex items-center gap-2 mb-1">
                <component
                  :is="form.storage_preference === 'nfs' ? CloudIcon : CircleStackIcon"
                  :class="[
                    'h-4 w-4',
                    form.storage_preference === 'nfs' ? 'text-emerald-500' : 'text-blue-500'
                  ]"
                />
                <p :class="[
                  'text-xs font-medium uppercase tracking-wide',
                  form.storage_preference === 'nfs' ? 'text-emerald-600 dark:text-emerald-400' : 'text-blue-600 dark:text-blue-400'
                ]">Destination</p>
              </div>
              <p class="text-sm font-medium text-primary">
                {{ form.storage_preference === 'nfs' ? 'Network Storage (NFS)' : 'Local Storage' }}
              </p>
              <p v-if="form.storage_preference === 'nfs' && form.nfs_storage_path" class="text-xs text-secondary mt-0.5 font-mono truncate">
                {{ form.nfs_storage_path }}
              </p>
              <p v-else-if="form.storage_preference === 'local' && stagingArea?.path" class="text-xs text-secondary mt-0.5 font-mono truncate">
                {{ stagingArea.path }}
              </p>
            </div>
            <!-- Workflow -->
            <div :class="[
              'p-3 rounded-lg border',
              form.storage_preference === 'nfs'
                ? (form.backup_workflow === 'stage_then_copy'
                    ? 'bg-indigo-50/50 dark:bg-indigo-900/10 border-indigo-200 dark:border-indigo-800/50'
                    : 'bg-purple-50/50 dark:bg-purple-900/10 border-purple-200 dark:border-purple-800/50')
                : 'bg-blue-50/50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800/50'
            ]">
              <div class="flex items-center gap-2 mb-1">
                <ArrowRightIcon :class="[
                  'h-4 w-4',
                  form.storage_preference === 'nfs'
                    ? (form.backup_workflow === 'stage_then_copy' ? 'text-indigo-500' : 'text-purple-500')
                    : 'text-blue-500'
                ]" />
                <p :class="[
                  'text-xs font-medium uppercase tracking-wide',
                  form.storage_preference === 'nfs'
                    ? (form.backup_workflow === 'stage_then_copy' ? 'text-indigo-600 dark:text-indigo-400' : 'text-purple-600 dark:text-purple-400')
                    : 'text-blue-600 dark:text-blue-400'
                ]">Workflow</p>
              </div>
              <p class="text-sm font-medium text-primary">
                <span v-if="form.storage_preference === 'local'">Direct to Local</span>
                <span v-else-if="form.backup_workflow === 'stage_then_copy'">Stage & Copy</span>
                <span v-else>Direct to NFS</span>
              </p>
            </div>
            <!-- Staging -->
            <div :class="[
              'p-3 rounded-lg border',
              form.storage_preference === 'nfs' && form.backup_workflow === 'stage_then_copy'
                ? 'bg-amber-50/50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800/50'
                : 'bg-gray-50/50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700'
            ]">
              <div class="flex items-center gap-2 mb-1">
                <FolderIcon :class="[
                  'h-4 w-4',
                  form.storage_preference === 'nfs' && form.backup_workflow === 'stage_then_copy'
                    ? 'text-amber-500'
                    : 'text-gray-400'
                ]" />
                <p :class="[
                  'text-xs font-medium uppercase tracking-wide',
                  form.storage_preference === 'nfs' && form.backup_workflow === 'stage_then_copy'
                    ? 'text-amber-600 dark:text-amber-400'
                    : 'text-gray-500 dark:text-gray-400'
                ]">Staging</p>
              </div>
              <p class="text-sm font-medium text-primary">
                <span v-if="form.storage_preference === 'nfs' && form.backup_workflow === 'stage_then_copy'">
                  Enabled
                </span>
                <span v-else class="text-secondary">Not Used</span>
              </p>
              <p v-if="form.storage_preference === 'nfs' && form.backup_workflow === 'stage_then_copy' && stagingArea?.path" class="text-xs text-secondary mt-0.5 font-mono truncate">
                {{ stagingArea.path }}
              </p>
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
                <p class="text-sm text-secondary">
                  <span v-if="form.schedule_enabled">
                    {{ form.schedule_frequency.charAt(0).toUpperCase() + form.schedule_frequency.slice(1) }} at {{ formattedTime }}
                  </span>
                  <span v-else>Disabled</span>
                </p>
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

            <div v-if="form.schedule_enabled" class="mt-4 space-y-4">
              <!-- Frequency Selection - Colored Boxes -->
              <div>
                <label class="block text-sm font-medium text-primary mb-3">Frequency</label>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <button
                    type="button"
                    @click="form.schedule_frequency = 'hourly'"
                    :class="[
                      'p-3 rounded-lg border-2 transition-all text-center',
                      form.schedule_frequency === 'hourly'
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                        : 'border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700'
                    ]"
                  >
                    <ClockIcon :class="['h-5 w-5 mx-auto mb-1', form.schedule_frequency === 'hourly' ? 'text-blue-500' : 'text-gray-400']" />
                    <p :class="['text-sm font-medium', form.schedule_frequency === 'hourly' ? 'text-blue-700 dark:text-blue-300' : 'text-primary']">Hourly</p>
                  </button>
                  <button
                    type="button"
                    @click="form.schedule_frequency = 'daily'"
                    :class="[
                      'p-3 rounded-lg border-2 transition-all text-center',
                      form.schedule_frequency === 'daily'
                        ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/30'
                        : 'border-gray-200 dark:border-gray-700 hover:border-emerald-300 dark:hover:border-emerald-700'
                    ]"
                  >
                    <CalendarIcon :class="['h-5 w-5 mx-auto mb-1', form.schedule_frequency === 'daily' ? 'text-emerald-500' : 'text-gray-400']" />
                    <p :class="['text-sm font-medium', form.schedule_frequency === 'daily' ? 'text-emerald-700 dark:text-emerald-300' : 'text-primary']">Daily</p>
                  </button>
                  <button
                    type="button"
                    @click="form.schedule_frequency = 'weekly'"
                    :class="[
                      'p-3 rounded-lg border-2 transition-all text-center',
                      form.schedule_frequency === 'weekly'
                        ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/30'
                        : 'border-gray-200 dark:border-gray-700 hover:border-purple-300 dark:hover:border-purple-700'
                    ]"
                  >
                    <CalendarIcon :class="['h-5 w-5 mx-auto mb-1', form.schedule_frequency === 'weekly' ? 'text-purple-500' : 'text-gray-400']" />
                    <p :class="['text-sm font-medium', form.schedule_frequency === 'weekly' ? 'text-purple-700 dark:text-purple-300' : 'text-primary']">Weekly</p>
                  </button>
                  <button
                    type="button"
                    @click="form.schedule_frequency = 'monthly'"
                    :class="[
                      'p-3 rounded-lg border-2 transition-all text-center',
                      form.schedule_frequency === 'monthly'
                        ? 'border-amber-500 bg-amber-50 dark:bg-amber-900/30'
                        : 'border-gray-200 dark:border-gray-700 hover:border-amber-300 dark:hover:border-amber-700'
                    ]"
                  >
                    <CalendarIcon :class="['h-5 w-5 mx-auto mb-1', form.schedule_frequency === 'monthly' ? 'text-amber-500' : 'text-gray-400']" />
                    <p :class="['text-sm font-medium', form.schedule_frequency === 'monthly' ? 'text-amber-700 dark:text-amber-300' : 'text-primary']">Monthly</p>
                  </button>
                </div>
              </div>

              <!-- Time Selection - Simple Hour/Minute -->
              <div>
                <label class="block text-sm font-medium text-primary mb-3">Time</label>
                <div class="flex items-center gap-4 p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                  <ClockIcon class="h-5 w-5 text-emerald-500" />
                  <div class="flex items-center gap-2">
                    <!-- Hour -->
                    <div class="flex items-center gap-1">
                      <button
                        type="button"
                        @click="scheduleHour = (scheduleHour - 1 + 24) % 24"
                        class="p-1.5 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
                      >
                        <ChevronDownIcon class="h-4 w-4 text-gray-600 dark:text-gray-300 rotate-90" />
                      </button>
                      <div class="w-16 text-center py-2 px-3 rounded-lg bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 font-mono text-lg font-semibold text-primary">
                        {{ String(scheduleHour).padStart(2, '0') }}
                      </div>
                      <button
                        type="button"
                        @click="scheduleHour = (scheduleHour + 1) % 24"
                        class="p-1.5 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
                      >
                        <ChevronDownIcon class="h-4 w-4 text-gray-600 dark:text-gray-300 -rotate-90" />
                      </button>
                    </div>
                    <span class="text-2xl font-bold text-gray-400">:</span>
                    <!-- Minute -->
                    <div class="flex items-center gap-1">
                      <button
                        type="button"
                        @click="scheduleMinute = (scheduleMinute - 5 + 60) % 60"
                        class="p-1.5 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
                      >
                        <ChevronDownIcon class="h-4 w-4 text-gray-600 dark:text-gray-300 rotate-90" />
                      </button>
                      <div class="w-16 text-center py-2 px-3 rounded-lg bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 font-mono text-lg font-semibold text-primary">
                        {{ String(scheduleMinute).padStart(2, '0') }}
                      </div>
                      <button
                        type="button"
                        @click="scheduleMinute = (scheduleMinute + 5) % 60"
                        class="p-1.5 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
                      >
                        <ChevronDownIcon class="h-4 w-4 text-gray-600 dark:text-gray-300 -rotate-90" />
                      </button>
                    </div>
                  </div>
                  <span class="text-sm text-secondary ml-2">({{ formattedTime }})</span>
                </div>
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
      <div v-if="activeTab === 'retention'" class="space-y-6">
        <!-- Header Banner -->
        <div class="relative overflow-hidden rounded-xl bg-gradient-to-br from-amber-500 via-orange-500 to-red-500 p-6 text-white shadow-lg">
          <div class="absolute inset-0 bg-black/10"></div>
          <div class="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-white/10 blur-2xl"></div>
          <div class="absolute -bottom-8 -left-8 h-32 w-32 rounded-full bg-white/10 blur-2xl"></div>
          <div class="relative flex items-center gap-4">
            <div class="flex h-14 w-14 items-center justify-center rounded-full bg-white/20 backdrop-blur-sm">
              <svg class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <div>
              <h2 class="text-2xl font-bold">Tiered Retention Policy</h2>
              <p class="text-white/80">Grandfather-Father-Son backup retention strategy</p>
            </div>
          </div>
        </div>

        <!-- Enable Toggle Card -->
        <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
          <div class="flex items-center justify-between p-5">
            <div class="flex items-center gap-4">
              <div class="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 text-white shadow-lg shadow-orange-500/25">
                <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <div>
                <h3 class="font-semibold text-gray-900 dark:text-white text-lg">Automatic Retention</h3>
                <p class="text-sm text-gray-500 dark:text-gray-400">Intelligently rotate backups using the GFS retention strategy</p>
              </div>
            </div>
            <button
              @click="form.retention_enabled = !form.retention_enabled"
              :class="[
                'relative inline-flex h-7 w-14 items-center rounded-full transition-all duration-300',
                form.retention_enabled
                  ? 'bg-gradient-to-r from-amber-500 to-orange-500 shadow-lg shadow-orange-500/25'
                  : 'bg-gray-300 dark:bg-gray-600'
              ]"
            >
              <span :class="['inline-block h-5 w-5 transform rounded-full bg-white shadow-md transition-transform duration-300', form.retention_enabled ? 'translate-x-8' : 'translate-x-1']" />
            </button>
          </div>
        </div>

        <!-- Tiered Retention Cards -->
        <div v-if="form.retention_enabled" class="space-y-4">
          <!-- GFS Explanation -->
          <div class="bg-gradient-to-r from-blue-50 to-cyan-50 dark:from-blue-900/20 dark:to-cyan-900/20 rounded-xl border border-blue-200 dark:border-blue-800 p-5">
            <div class="flex gap-4">
              <div class="flex-shrink-0">
                <div class="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-500/20">
                  <svg class="h-5 w-5 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
              <div>
                <h4 class="font-semibold text-blue-900 dark:text-blue-100">How Tiered Retention Works</h4>
                <p class="mt-1 text-sm text-blue-700 dark:text-blue-300">
                  The GFS (Grandfather-Father-Son) strategy keeps recent backups at higher frequency while retaining older backups at lower frequency.
                  This gives you quick recovery options for recent data while maintaining long-term archives efficiently.
                </p>
              </div>
            </div>
          </div>

          <!-- Retention Tiers Grid -->
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <!-- Daily Tier (Son) -->
            <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden transition-all hover:shadow-md hover:border-emerald-300 dark:hover:border-emerald-600">
              <div class="bg-gradient-to-r from-emerald-500 to-teal-500 p-4">
                <div class="flex items-center gap-3">
                  <div class="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 backdrop-blur-sm">
                    <svg class="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                  </div>
                  <div>
                    <h3 class="font-bold text-white text-lg">Daily</h3>
                    <p class="text-white/80 text-xs">Son backups</p>
                  </div>
                </div>
              </div>
              <div class="px-5 pt-4 pb-3 min-h-[88px]">
                <p class="text-sm text-gray-500 dark:text-gray-400">
                  Keep one backup per day for the most recent period. Ideal for quick recovery from recent changes.
                </p>
              </div>
              <div class="border-t border-gray-100 dark:border-gray-700 px-5 pt-3 pb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Keep for</label>
                <div class="flex items-center gap-3">
                  <input
                    v-model.number="form.retention_daily_count"
                    type="number"
                    min="1"
                    max="30"
                    class="flex-1 px-4 py-3 text-center font-mono text-lg border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                  />
                  <span class="text-sm font-medium text-gray-600 dark:text-gray-400 w-16">days</span>
                </div>
                <p class="text-xs text-gray-500 dark:text-gray-500 mt-2">
                  Keeps {{ form.retention_daily_count }} daily backup{{ form.retention_daily_count !== 1 ? 's' : '' }}
                </p>
              </div>
            </div>

            <!-- Weekly Tier (Father) -->
            <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden transition-all hover:shadow-md hover:border-blue-300 dark:hover:border-blue-600">
              <div class="bg-gradient-to-r from-blue-500 to-indigo-500 p-4">
                <div class="flex items-center gap-3">
                  <div class="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 backdrop-blur-sm">
                    <svg class="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <div>
                    <h3 class="font-bold text-white text-lg">Weekly</h3>
                    <p class="text-white/80 text-xs">Father backups</p>
                  </div>
                </div>
              </div>
              <div class="px-5 pt-4 pb-3 min-h-[88px]">
                <p class="text-sm text-gray-500 dark:text-gray-400">
                  Keep one backup per week for medium-term retention. Great for recovering from issues discovered later.
                </p>
              </div>
              <div class="border-t border-gray-100 dark:border-gray-700 px-5 pt-3 pb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Keep for</label>
                <div class="flex items-center gap-3">
                  <input
                    v-model.number="form.retention_weekly_count"
                    type="number"
                    min="1"
                    max="52"
                    class="flex-1 px-4 py-3 text-center font-mono text-lg border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <span class="text-sm font-medium text-gray-600 dark:text-gray-400 w-16">weeks</span>
                </div>
                <p class="text-xs text-gray-500 dark:text-gray-500 mt-2">
                  Keeps {{ form.retention_weekly_count }} weekly backup{{ form.retention_weekly_count !== 1 ? 's' : '' }}
                </p>
              </div>
            </div>

            <!-- Monthly Tier (Grandfather) -->
            <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden transition-all hover:shadow-md hover:border-purple-300 dark:hover:border-purple-600">
              <div class="bg-gradient-to-r from-purple-500 to-pink-500 p-4">
                <div class="flex items-center gap-3">
                  <div class="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 backdrop-blur-sm">
                    <svg class="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                  </div>
                  <div>
                    <h3 class="font-bold text-white text-lg">Monthly</h3>
                    <p class="text-white/80 text-xs">Grandfather backups</p>
                  </div>
                </div>
              </div>
              <div class="px-5 pt-4 pb-3 min-h-[88px]">
                <p class="text-sm text-gray-500 dark:text-gray-400">
                  Keep one backup per month for long-term archives. Essential for compliance and historical recovery.
                </p>
              </div>
              <div class="border-t border-gray-100 dark:border-gray-700 px-5 pt-3 pb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Keep for</label>
                <div class="flex items-center gap-3">
                  <input
                    v-model.number="form.retention_monthly_count"
                    type="number"
                    min="1"
                    max="24"
                    class="flex-1 px-4 py-3 text-center font-mono text-lg border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                  <span class="text-sm font-medium text-gray-600 dark:text-gray-400 w-16">months</span>
                </div>
                <p class="text-xs text-gray-500 dark:text-gray-500 mt-2">
                  Keeps {{ form.retention_monthly_count }} monthly backup{{ form.retention_monthly_count !== 1 ? 's' : '' }}
                </p>
              </div>
            </div>
          </div>

          <!-- Safety Net Card -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
            <div class="flex items-start gap-4 p-5">
              <div class="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-red-400 to-rose-600 text-white shadow-lg shadow-red-500/25">
                <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div class="flex-1">
                <h3 class="font-semibold text-gray-900 dark:text-white">Safety Net</h3>
                <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Always keep at least this many backups, regardless of age. This prevents accidental deletion of all backups.
                </p>
                <div class="mt-4 flex items-center gap-4">
                  <input
                    v-model.number="form.retention_min_count"
                    type="number"
                    min="1"
                    max="50"
                    class="w-24 px-4 py-2 text-center font-mono border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  />
                  <span class="text-sm text-gray-500 dark:text-gray-400">minimum backups always kept</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Retention Summary -->
          <div class="bg-gradient-to-r from-gray-50 to-slate-50 dark:from-gray-800 dark:to-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
            <h4 class="font-semibold text-gray-900 dark:text-white mb-3">Retention Summary</h4>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div class="text-center p-3 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800">
                <p class="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{{ form.retention_daily_count }}</p>
                <p class="text-xs text-emerald-700 dark:text-emerald-300">Daily</p>
              </div>
              <div class="text-center p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
                <p class="text-2xl font-bold text-blue-600 dark:text-blue-400">{{ form.retention_weekly_count }}</p>
                <p class="text-xs text-blue-700 dark:text-blue-300">Weekly</p>
              </div>
              <div class="text-center p-3 rounded-lg bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800">
                <p class="text-2xl font-bold text-purple-600 dark:text-purple-400">{{ form.retention_monthly_count }}</p>
                <p class="text-xs text-purple-700 dark:text-purple-300">Monthly</p>
              </div>
              <div class="text-center p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
                <p class="text-2xl font-bold text-amber-600 dark:text-amber-400">{{ form.retention_daily_count + form.retention_weekly_count + form.retention_monthly_count }}</p>
                <p class="text-xs text-amber-700 dark:text-amber-300">Max Total</p>
              </div>
            </div>
            <p class="mt-3 text-sm text-gray-500 dark:text-gray-400">
              With daily backups, you'll have up to <strong>{{ form.retention_daily_count + form.retention_weekly_count + form.retention_monthly_count }}</strong> backups,
              spanning approximately <strong>{{ Math.max(form.retention_daily_count, form.retention_weekly_count * 7, form.retention_monthly_count * 30) }}</strong> days of history.
            </p>
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

      <!-- Verification Tab -->
      <div v-if="activeTab === 'verification'" class="space-y-4">
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <!-- Header -->
          <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-cyan-100 dark:bg-cyan-500/20">
                <ShieldCheckIcon class="h-5 w-5 text-cyan-600 dark:text-cyan-400" />
              </div>
              <div>
                <h3 class="font-semibold text-primary">Auto-Verification</h3>
                <p class="text-sm text-secondary">Automatically verify backups after they complete</p>
              </div>
            </div>
          </div>

          <div class="p-6 space-y-6">
            <!-- Enable Toggle -->
            <div class="flex items-center justify-between p-4 bg-cyan-50 dark:bg-cyan-900/20 rounded-lg border border-cyan-200 dark:border-cyan-800">
              <div>
                <p class="font-medium text-cyan-800 dark:text-cyan-300">Enable Auto-Verification</p>
                <p class="text-sm text-cyan-700 dark:text-cyan-400">Automatically verify backup integrity after each backup completes</p>
              </div>
              <button
                type="button"
                @click="form.auto_verify_enabled = !form.auto_verify_enabled"
                :class="[
                  'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2',
                  form.auto_verify_enabled ? 'bg-cyan-500' : 'bg-gray-300 dark:bg-gray-600'
                ]"
              >
                <span :class="['inline-block h-5 w-5 transform rounded-full bg-white transition-transform', form.auto_verify_enabled ? 'translate-x-5' : 'translate-x-0']" />
              </button>
            </div>

            <!-- Frequency Setting -->
            <div v-if="form.auto_verify_enabled" class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-primary mb-2">Verification Frequency</label>
                <p class="text-sm text-secondary mb-3">Choose how often backups should be verified</p>

                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <button
                    type="button"
                    @click="form.verify_frequency = 1"
                    :class="[
                      'p-4 rounded-lg border-2 transition-all text-center',
                      form.verify_frequency === 1
                        ? 'border-cyan-500 bg-cyan-50 dark:bg-cyan-900/30'
                        : 'border-gray-200 dark:border-gray-700 hover:border-cyan-300 dark:hover:border-cyan-700'
                    ]"
                  >
                    <div :class="['text-2xl font-bold mb-1', form.verify_frequency === 1 ? 'text-cyan-600 dark:text-cyan-400' : 'text-gray-700 dark:text-gray-300']">1</div>
                    <div :class="['text-xs', form.verify_frequency === 1 ? 'text-cyan-700 dark:text-cyan-400' : 'text-secondary']">Every backup</div>
                  </button>

                  <button
                    type="button"
                    @click="form.verify_frequency = 3"
                    :class="[
                      'p-4 rounded-lg border-2 transition-all text-center',
                      form.verify_frequency === 3
                        ? 'border-cyan-500 bg-cyan-50 dark:bg-cyan-900/30'
                        : 'border-gray-200 dark:border-gray-700 hover:border-cyan-300 dark:hover:border-cyan-700'
                    ]"
                  >
                    <div :class="['text-2xl font-bold mb-1', form.verify_frequency === 3 ? 'text-cyan-600 dark:text-cyan-400' : 'text-gray-700 dark:text-gray-300']">3</div>
                    <div :class="['text-xs', form.verify_frequency === 3 ? 'text-cyan-700 dark:text-cyan-400' : 'text-secondary']">Every 3rd</div>
                  </button>

                  <button
                    type="button"
                    @click="form.verify_frequency = 5"
                    :class="[
                      'p-4 rounded-lg border-2 transition-all text-center',
                      form.verify_frequency === 5
                        ? 'border-cyan-500 bg-cyan-50 dark:bg-cyan-900/30'
                        : 'border-gray-200 dark:border-gray-700 hover:border-cyan-300 dark:hover:border-cyan-700'
                    ]"
                  >
                    <div :class="['text-2xl font-bold mb-1', form.verify_frequency === 5 ? 'text-cyan-600 dark:text-cyan-400' : 'text-gray-700 dark:text-gray-300']">5</div>
                    <div :class="['text-xs', form.verify_frequency === 5 ? 'text-cyan-700 dark:text-cyan-400' : 'text-secondary']">Every 5th</div>
                  </button>

                  <button
                    type="button"
                    @click="form.verify_frequency = 10"
                    :class="[
                      'p-4 rounded-lg border-2 transition-all text-center',
                      form.verify_frequency === 10
                        ? 'border-cyan-500 bg-cyan-50 dark:bg-cyan-900/30'
                        : 'border-gray-200 dark:border-gray-700 hover:border-cyan-300 dark:hover:border-cyan-700'
                    ]"
                  >
                    <div :class="['text-2xl font-bold mb-1', form.verify_frequency === 10 ? 'text-cyan-600 dark:text-cyan-400' : 'text-gray-700 dark:text-gray-300']">10</div>
                    <div :class="['text-xs', form.verify_frequency === 10 ? 'text-cyan-700 dark:text-cyan-400' : 'text-secondary']">Every 10th</div>
                  </button>
                </div>

                <!-- Custom frequency input -->
                <div class="mt-4">
                  <label class="block text-sm font-medium text-primary mb-1">Or enter a custom frequency</label>
                  <div class="flex items-center gap-2">
                    <span class="text-secondary">Verify every</span>
                    <input
                      v-model.number="form.verify_frequency"
                      type="number"
                      min="1"
                      max="100"
                      class="w-20 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-primary text-center"
                    />
                    <span class="text-secondary">backup(s)</span>
                  </div>
                </div>
              </div>

              <!-- Info Box -->
              <div class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                <div class="flex gap-3">
                  <InformationCircleIcon class="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
                  <div class="text-sm">
                    <p class="font-medium text-blue-800 dark:text-blue-300 mb-1">What does verification do?</p>
                    <ul class="text-blue-700 dark:text-blue-400 space-y-1">
                      <li>Validates archive integrity (checks for corruption)</li>
                      <li>Verifies database dump can be read by PostgreSQL</li>
                      <li>Confirms checksums match expected values</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>

            <!-- Disabled state info -->
            <div v-else class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <p class="text-sm text-secondary">
                When disabled, backups will not be automatically verified. You can still manually verify any backup from the Backup History page.
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Notifications Tab -->
      <div v-if="activeTab === 'notifications'" class="space-y-4">
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div class="text-center py-8">
            <div class="mx-auto w-16 h-16 rounded-full bg-gradient-to-br from-pink-100 to-rose-100 dark:from-pink-900/30 dark:to-rose-900/30 flex items-center justify-center mb-4">
              <BellIcon class="h-8 w-8 text-pink-600 dark:text-pink-400" />
            </div>
            <h3 class="text-lg font-semibold text-primary mb-2">Backup Notifications</h3>
            <p class="text-secondary mb-6 max-w-md mx-auto">
              Configure when and how you receive notifications about backup events like successful completions or failures.
            </p>
            <button
              @click="router.push('/settings?tab=notifications&section=backup')"
              class="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white rounded-lg font-medium transition-all shadow-lg shadow-pink-500/25"
            >
              <Cog6ToothIcon class="h-5 w-5" />
              Open System Notifications
              <ArrowRightIcon class="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* Slide-fade transition for conditional sections */
.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}
.slide-fade-leave-active {
  transition: all 0.2s ease-in;
}
.slide-fade-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}
.slide-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* File transfer animation */
.file-animation {
  animation: moveFiles 1.5s ease-in-out infinite;
}

@keyframes moveFiles {
  0% {
    transform: translateX(-100%);
    opacity: 0;
  }
  20% {
    opacity: 1;
  }
  80% {
    opacity: 1;
  }
  100% {
    transform: translateX(100%);
    opacity: 0;
  }
}

/* Time picker scrollbar */
.scrollbar-thin {
  scrollbar-width: thin;
  scrollbar-color: #d1d5db transparent;
}
.scrollbar-thin::-webkit-scrollbar {
  width: 6px;
}
.scrollbar-thin::-webkit-scrollbar-track {
  background: transparent;
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background-color: #d1d5db;
  border-radius: 3px;
}
.dark .scrollbar-thin {
  scrollbar-color: #4b5563 transparent;
}
.dark .scrollbar-thin::-webkit-scrollbar-thumb {
  background-color: #4b5563;
}
</style>
