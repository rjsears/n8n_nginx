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


// Collapsible sections state
const sections = ref({
  backupDestination: true,
  backupWorkflow: true,
  stagingArea: true,
  localPaths: false,
  scheduleConfig: true,
  backupContents: true,
  retentionPolicy: true,
  compressionSettings: true,
  notifySettings: true,
  notifyChannels: true,
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
  notification_channel_ids: [], // Array of {id, type} for multi-select
})

const tabs = [
  { id: 'storage', name: 'Storage', icon: FolderIcon, iconColor: 'text-blue-500', bgActive: 'bg-blue-500/15 dark:bg-blue-500/20', textActive: 'text-blue-700 dark:text-blue-400', borderActive: 'border-blue-500/30' },
  { id: 'schedule', name: 'Schedule', icon: ClockIcon, iconColor: 'text-emerald-500', bgActive: 'bg-emerald-500/15 dark:bg-emerald-500/20', textActive: 'text-emerald-700 dark:text-emerald-400', borderActive: 'border-emerald-500/30' },
  { id: 'retention', name: 'Retention', icon: TrashIcon, iconColor: 'text-amber-500', bgActive: 'bg-amber-500/15 dark:bg-amber-500/20', textActive: 'text-amber-700 dark:text-amber-400', borderActive: 'border-amber-500/30' },
  { id: 'compression', name: 'Compression', icon: ServerIcon, iconColor: 'text-purple-500', bgActive: 'bg-purple-500/15 dark:bg-purple-500/20', textActive: 'text-purple-700 dark:text-purple-400', borderActive: 'border-purple-500/30' },
  { id: 'notifications', name: 'Notifications', icon: BellIcon, iconColor: 'text-pink-500', bgActive: 'bg-pink-500/15 dark:bg-pink-500/20', textActive: 'text-pink-700 dark:text-pink-400', borderActive: 'border-pink-500/30' },
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

// Check if notifications can be enabled (requires at least one channel selected)
const canEnableNotifications = computed(() => {
  return form.value.notification_channel_ids.length > 0
})

// Selected channel count for display
const selectedChannelCount = computed(() => {
  return form.value.notification_channel_ids.length
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

function isChannelSelected(channel) {
  return form.value.notification_channel_ids.some(
    c => c.id === channel.id && c.type === channel.type
  )
}

function toggleNotificationChannel(channel) {
  const index = form.value.notification_channel_ids.findIndex(
    c => c.id === channel.id && c.type === channel.type
  )
  if (index > -1) {
    // Remove if already selected
    form.value.notification_channel_ids.splice(index, 1)
  } else {
    // Add if not selected
    form.value.notification_channel_ids.push({ id: channel.id, type: channel.type })
  }

  // Disable notifications if no channels selected
  if (form.value.notification_channel_ids.length === 0) {
    form.value.notify_on_success = false
    form.value.notify_on_failure = false
  }
}

function clearAllNotificationChannels() {
  form.value.notification_channel_ids = []
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

      <!-- Storage Tab - 3-Step Configuration Flow -->
      <div v-if="activeTab === 'storage'" class="space-y-4">
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
                      <FolderIcon class="h-4 w-4 text-gray-500" />
                      <code class="text-xs font-mono text-primary">{{ stagingArea.path }}</code>
                      <span v-if="stagingArea.is_writable" class="px-1.5 py-0.5 rounded text-xs bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                        {{ stagingArea.free_space_gb }} GB free
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
                      <p class="text-xs text-secondary mt-1 ml-6">{{ nfs.source }} ({{ nfs.fs_type }})</p>
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
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <h4 class="font-semibold text-primary mb-3">Configuration Summary</h4>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
              <p class="text-xs font-medium text-secondary uppercase tracking-wide">Destination</p>
              <p class="text-sm font-medium text-primary mt-1">
                {{ form.storage_preference === 'nfs' ? 'Network Storage (NFS)' : 'Local Storage' }}
              </p>
              <p v-if="form.storage_preference === 'nfs' && form.nfs_storage_path" class="text-xs text-secondary mt-0.5 font-mono">
                {{ form.nfs_storage_path }}
              </p>
            </div>
            <div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
              <p class="text-xs font-medium text-secondary uppercase tracking-wide">Workflow</p>
              <p class="text-sm font-medium text-primary mt-1">
                <span v-if="form.storage_preference === 'local'">Direct to Local</span>
                <span v-else-if="form.backup_workflow === 'stage_then_copy'">Stage & Copy</span>
                <span v-else>Direct to NFS</span>
              </p>
            </div>
            <div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
              <p class="text-xs font-medium text-secondary uppercase tracking-wide">Staging</p>
              <p class="text-sm font-medium text-primary mt-1">
                <span v-if="form.storage_preference === 'nfs' && form.backup_workflow === 'stage_then_copy'">
                  Enabled
                </span>
                <span v-else class="text-secondary">Not Used</span>
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
        <!-- Channel Selection (Multi-select) -->
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
                <h3 class="font-semibold text-primary">Notification Channels</h3>
                <p class="text-sm text-secondary">Select channels to receive backup notifications</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span v-if="selectedChannelCount > 0" class="px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-400">
                {{ selectedChannelCount }} selected
              </span>
              <span v-else class="px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
                None selected
              </span>
              <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.notifyChannels ? 'rotate-180' : '']" />
            </div>
          </button>

          <div v-if="sections.notifyChannels" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <!-- Configure Notifications Button -->
            <div class="mt-4 flex items-center justify-between">
              <p class="text-sm text-secondary">Select one or more channels to receive notifications</p>
              <button
                @click="router.push('/notifications')"
                class="btn-secondary text-sm flex items-center gap-2"
              >
                <Cog6ToothIcon class="h-4 w-4" />
                Manage Channels
              </button>
            </div>

            <div v-if="loadingChannels" class="mt-4 flex justify-center py-8">
              <LoadingSpinner text="Loading notification channels..." />
            </div>

            <div v-else-if="allNotificationChannels.length > 0" class="mt-4 space-y-4">
              <!-- Services (Checkboxes) -->
              <div v-if="notificationServices.length > 0">
                <p class="text-xs font-medium text-muted uppercase tracking-wide mb-2">Channels</p>
                <div class="space-y-2">
                  <label
                    v-for="channel in allNotificationChannels.filter(c => c.type === 'service')"
                    :key="`service-${channel.id}`"
                    :class="[
                      'flex items-center gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all',
                      isChannelSelected(channel)
                        ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20'
                        : 'border-gray-200 dark:border-gray-700 hover:border-indigo-300'
                    ]"
                  >
                    <input
                      type="checkbox"
                      :checked="isChannelSelected(channel)"
                      @change="toggleNotificationChannel(channel)"
                      class="h-4 w-4 rounded border-gray-300 text-indigo-500 focus:ring-indigo-500"
                    />
                    <div class="flex items-center gap-3 flex-1">
                      <div class="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900/40">
                        <BellIcon class="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                      </div>
                      <div>
                        <p class="font-medium text-primary">{{ channel.name }}</p>
                        <p class="text-xs text-secondary">{{ channel.description }}</p>
                      </div>
                    </div>
                  </label>
                </div>
              </div>

              <!-- Groups (Checkboxes) -->
              <div v-if="notificationGroups.length > 0">
                <p class="text-xs font-medium text-muted uppercase tracking-wide mb-2">Groups</p>
                <div class="space-y-2">
                  <label
                    v-for="channel in allNotificationChannels.filter(c => c.type === 'group')"
                    :key="`group-${channel.id}`"
                    :class="[
                      'flex items-center gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all',
                      isChannelSelected(channel)
                        ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                        : 'border-gray-200 dark:border-gray-700 hover:border-purple-300'
                    ]"
                  >
                    <input
                      type="checkbox"
                      :checked="isChannelSelected(channel)"
                      @change="toggleNotificationChannel(channel)"
                      class="h-4 w-4 rounded border-gray-300 text-purple-500 focus:ring-purple-500"
                    />
                    <div class="flex items-center gap-3 flex-1">
                      <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-900/40">
                        <FolderIcon class="h-5 w-5 text-purple-600 dark:text-purple-400" />
                      </div>
                      <div>
                        <p class="font-medium text-primary">{{ channel.name }}</p>
                        <p class="text-xs text-secondary">{{ channel.description }}</p>
                      </div>
                    </div>
                  </label>
                </div>
              </div>

              <button
                v-if="selectedChannelCount > 0"
                @click="clearAllNotificationChannels"
                class="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              >
                Clear all selections
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

        <!-- Notification Triggers -->
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
              <span v-if="!canEnableNotifications" class="text-xs text-amber-600 dark:text-amber-400">Select channels first</span>
              <ChevronDownIcon :class="['h-5 w-5 text-gray-400 transition-transform', sections.notifySettings ? 'rotate-180' : '']" />
            </div>
          </button>

          <div v-if="sections.notifySettings" class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
            <div v-if="!canEnableNotifications" class="mt-4 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
              <p class="text-sm text-amber-700 dark:text-amber-400">
                Please select at least one notification channel above before enabling notifications.
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
</style>
