<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useBackupStore } from '@/stores/backups'
import { useNotificationStore } from '@/stores/notifications'
import Card from '@/components/common/Card.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import {
  FolderIcon,
  ClockIcon,
  TrashIcon,
  BellIcon,
  CheckCircleIcon,
  Cog6ToothIcon,
  ServerIcon,
  ArrowPathIcon,
  CheckIcon,
  XMarkIcon,
  ArrowLeftIcon,
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
      if (!form.value.primary_storage_path && storage.recommended_path) {
        form.value.primary_storage_path = storage.recommended_path
      }
      if (storage.has_nfs && storage.nfs_mounts.length > 0) {
        const nfsMount = storage.nfs_mounts[0]
        if (!form.value.nfs_storage_path) {
          form.value.nfs_storage_path = nfsMount.path
        }
      }
    }
  } catch (err) {
    notificationStore.error('Failed to load configuration')
  } finally {
    loading.value = false
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

function selectStoragePath(path) {
  form.value.primary_storage_path = path
  validatePath(path)
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

function goBack() {
  router.push('/backups')
}

onMounted(() => {
  loadConfiguration()
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
      <div v-if="activeTab === 'storage'" class="space-y-6">
        <!-- Detected Storage -->
        <Card title="Detected Storage Locations" subtitle="Automatically detected storage paths available on your system">
          <template #actions>
            <button
              @click="detectStorage"
              :disabled="detectingStorage"
              class="btn-secondary text-sm flex items-center gap-2"
            >
              <ArrowPathIcon :class="['h-4 w-4', detectingStorage ? 'animate-spin' : '']" />
              {{ detectingStorage ? 'Detecting...' : 'Refresh' }}
            </button>
          </template>

          <div v-if="storageDetection" class="space-y-4">
            <!-- NFS Mounts -->
            <div v-if="storageDetection.has_nfs">
              <div class="flex items-center gap-2 mb-3">
                <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400">
                  <ServerIcon class="h-3.5 w-3.5 mr-1" />
                  NFS Available
                </span>
              </div>
              <div class="space-y-2">
                <div
                  v-for="nfs in storageDetection.nfs_mounts"
                  :key="nfs.path"
                  :class="[
                    'flex items-center justify-between p-4 rounded-lg border transition-colors',
                    form.nfs_storage_path === nfs.path
                      ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  ]"
                >
                  <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-900/30">
                      <ServerIcon class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <div>
                      <p class="font-mono text-sm font-medium text-primary">{{ nfs.path }}</p>
                      <p class="text-xs text-secondary">
                        {{ nfs.source }} ({{ nfs.fs_type }})
                        <span v-if="nfs.free_space_gb" class="ml-2">• {{ nfs.free_space_gb }} GB free of {{ nfs.total_space_gb }} GB</span>
                      </p>
                    </div>
                  </div>
                  <button
                    v-if="nfs.is_writable"
                    @click="selectNfsPath(nfs.path)"
                    :class="[
                      'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                      form.nfs_storage_path === nfs.path
                        ? 'bg-emerald-500 text-white'
                        : 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400 dark:hover:bg-emerald-900/50'
                    ]"
                  >
                    {{ form.nfs_storage_path === nfs.path ? 'Selected' : 'Use NFS' }}
                  </button>
                  <span v-else class="text-sm text-red-500">Not writable</span>
                </div>
              </div>
            </div>

            <!-- Local Paths -->
            <div>
              <p class="text-sm font-medium text-secondary mb-3">Local Storage Paths</p>
              <div class="space-y-2">
                <div
                  v-for="local in storageDetection.local_paths"
                  :key="local.path"
                  :class="[
                    'flex items-center justify-between p-4 rounded-lg border transition-colors',
                    form.primary_storage_path === local.path
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  ]"
                >
                  <div class="flex items-center gap-3">
                    <div :class="[
                      'p-2 rounded-lg',
                      local.is_writable ? 'bg-blue-100 dark:bg-blue-900/30' : 'bg-gray-100 dark:bg-gray-800'
                    ]">
                      <FolderIcon :class="[
                        'h-5 w-5',
                        local.is_writable ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400'
                      ]" />
                    </div>
                    <div>
                      <p class="font-mono text-sm font-medium text-primary">{{ local.path }}</p>
                      <p class="text-xs text-secondary">
                        <span v-if="local.exists">
                          <span v-if="local.is_writable" class="text-emerald-600 dark:text-emerald-400">Writable</span>
                          <span v-else class="text-red-500">Not writable</span>
                          <span v-if="local.free_space_gb" class="ml-2">• {{ local.free_space_gb }} GB free</span>
                        </span>
                        <span v-else class="text-amber-600 dark:text-amber-400">Does not exist</span>
                      </p>
                    </div>
                  </div>
                  <button
                    v-if="local.is_writable"
                    @click="selectStoragePath(local.path)"
                    :class="[
                      'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                      form.primary_storage_path === local.path
                        ? 'bg-blue-500 text-white'
                        : 'bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:hover:bg-blue-900/50'
                    ]"
                  >
                    {{ form.primary_storage_path === local.path ? 'Selected' : 'Select' }}
                  </button>
                </div>
              </div>
            </div>

            <!-- Recommended -->
            <div v-if="storageDetection.recommended_path" class="p-4 rounded-lg bg-gradient-to-r from-blue-50 to-emerald-50 dark:from-blue-900/20 dark:to-emerald-900/20 border border-blue-200 dark:border-blue-800">
              <p class="text-sm font-medium text-blue-700 dark:text-blue-400">
                <CheckCircleIcon class="h-4 w-4 inline mr-1" />
                Recommended: <span class="font-mono">{{ storageDetection.recommended_path }}</span>
              </p>
            </div>
          </div>

          <div v-else class="text-center py-8 text-secondary">
            <FolderIcon class="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p>Click "Refresh" to detect available storage locations</p>
          </div>
        </Card>

        <!-- Manual Configuration -->
        <Card title="Storage Configuration" subtitle="Configure your primary and NFS storage paths">
          <div class="space-y-6">
            <div>
              <label class="block text-sm font-medium text-primary mb-2">Primary Storage Path</label>
              <div class="flex gap-3">
                <input
                  v-model="form.primary_storage_path"
                  type="text"
                  class="input-field flex-1 font-mono"
                  placeholder="/app/backups"
                />
                <button
                  @click="validatePath(form.primary_storage_path)"
                  :disabled="validatingPath"
                  class="btn-secondary px-4"
                >
                  {{ validatingPath ? 'Checking...' : 'Validate' }}
                </button>
              </div>

              <div v-if="pathValidation" class="mt-3 p-3 rounded-lg" :class="pathValidation.is_writable ? 'bg-emerald-50 dark:bg-emerald-900/20' : 'bg-red-50 dark:bg-red-900/20'">
                <div class="flex items-center gap-2">
                  <CheckCircleIcon v-if="pathValidation.is_writable" class="h-5 w-5 text-emerald-500" />
                  <XMarkIcon v-else class="h-5 w-5 text-red-500" />
                  <span :class="pathValidation.is_writable ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'">
                    {{ pathValidation.is_writable ? 'Path is valid and writable' : 'Path is not accessible or writable' }}
                  </span>
                </div>
                <p v-if="pathValidation.free_space_gb" class="mt-1 text-sm text-secondary">
                  Free space: {{ pathValidation.free_space_gb }} GB / {{ pathValidation.total_space_gb }} GB
                </p>
              </div>
            </div>

            <!-- NFS Toggle -->
            <div class="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-900">
              <div>
                <p class="font-medium text-primary">Enable NFS Storage</p>
                <p class="text-sm text-secondary">Store backups on network-attached storage</p>
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

            <div v-if="form.nfs_enabled" class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-primary mb-2">NFS Storage Path</label>
                <input
                  v-model="form.nfs_storage_path"
                  type="text"
                  class="input-field w-full font-mono"
                  placeholder="/mnt/backups"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-primary mb-2">Storage Preference</label>
                <select v-model="form.storage_preference" class="input-field w-full">
                  <option value="local">Local storage only</option>
                  <option value="nfs">NFS storage only</option>
                  <option value="both">Both (redundant copies)</option>
                </select>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Schedule Tab -->
      <div v-if="activeTab === 'schedule'" class="space-y-6">
        <Card title="Backup Schedule" subtitle="Configure automatic backup scheduling">
          <div class="space-y-6">
            <div class="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-900">
              <div>
                <p class="font-medium text-primary">Enable Scheduled Backups</p>
                <p class="text-sm text-secondary">Automatically run backups on a schedule</p>
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

            <div v-if="form.schedule_enabled" class="grid grid-cols-1 md:grid-cols-2 gap-6">
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
        </Card>

        <Card title="Backup Contents" subtitle="Choose what to include in backups">
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-primary mb-2">Default Backup Type</label>
              <select v-model="form.default_backup_type" class="input-field w-full">
                <option value="postgres_full">Full PostgreSQL Backup (n8n + management)</option>
                <option value="postgres_n8n">n8n Database Only</option>
                <option value="postgres_mgmt">Management Database Only</option>
              </select>
            </div>

            <div class="space-y-3 pt-4">
              <label class="flex items-center gap-3 cursor-pointer">
                <input v-model="form.include_n8n_config" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-blue-500" />
                <span class="text-sm text-primary">Include n8n configuration files (docker-compose.yaml, nginx.conf)</span>
              </label>
              <label class="flex items-center gap-3 cursor-pointer">
                <input v-model="form.include_ssl_certs" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-blue-500" />
                <span class="text-sm text-primary">Include SSL certificates</span>
              </label>
              <label class="flex items-center gap-3 cursor-pointer">
                <input v-model="form.include_env_files" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-blue-500" />
                <span class="text-sm text-primary">Include environment files (.env)</span>
              </label>
            </div>
          </div>
        </Card>
      </div>

      <!-- Retention Tab -->
      <div v-if="activeTab === 'retention'" class="space-y-6">
        <Card title="Retention Policy" subtitle="Configure automatic backup cleanup">
          <div class="space-y-6">
            <div class="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-900">
              <div>
                <p class="font-medium text-primary">Enable Automatic Cleanup</p>
                <p class="text-sm text-secondary">Automatically delete old backups based on retention rules</p>
              </div>
              <button
                @click="form.retention_enabled = !form.retention_enabled"
                :class="[
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                  form.retention_enabled ? 'bg-emerald-500' : 'bg-gray-300 dark:bg-gray-600'
                ]"
              >
                <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.retention_enabled ? 'translate-x-6' : 'translate-x-1']" />
              </button>
            </div>

            <div v-if="form.retention_enabled" class="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label class="block text-sm font-medium text-primary mb-2">Keep Backups For (days)</label>
                <input v-model.number="form.retention_days" type="number" min="1" max="365" class="input-field w-full" />
                <p class="mt-1 text-xs text-secondary">Delete backups older than this</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-primary mb-2">Maximum Backups</label>
                <input v-model.number="form.retention_count" type="number" min="1" max="100" class="input-field w-full" />
                <p class="mt-1 text-xs text-secondary">Maximum number of backups to keep</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-primary mb-2">Minimum Backups</label>
                <input v-model.number="form.retention_min_count" type="number" min="1" max="50" class="input-field w-full" />
                <p class="mt-1 text-xs text-secondary">Never delete below this count</p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Compression Tab -->
      <div v-if="activeTab === 'compression'" class="space-y-6">
        <Card title="Compression Settings" subtitle="Configure backup compression to save storage space">
          <div class="space-y-6">
            <div class="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-900">
              <div>
                <p class="font-medium text-primary">Enable Compression</p>
                <p class="text-sm text-secondary">Compress backups to reduce storage usage</p>
              </div>
              <button
                @click="form.compression_enabled = !form.compression_enabled"
                :class="[
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                  form.compression_enabled ? 'bg-emerald-500' : 'bg-gray-300 dark:bg-gray-600'
                ]"
              >
                <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.compression_enabled ? 'translate-x-6' : 'translate-x-1']" />
              </button>
            </div>

            <div v-if="form.compression_enabled" class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label class="block text-sm font-medium text-primary mb-2">Algorithm</label>
                <select v-model="form.compression_algorithm" class="input-field w-full">
                  <option value="gzip">Gzip (widely compatible)</option>
                  <option value="zstd">Zstandard (faster, better ratio)</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-primary mb-2">
                  Compression Level: {{ form.compression_level }}
                </label>
                <input
                  v-model.number="form.compression_level"
                  type="range"
                  min="1"
                  :max="compressionLevelMax"
                  class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
                />
                <div class="flex justify-between text-xs text-secondary mt-1">
                  <span>Faster (larger files)</span>
                  <span>Slower (smaller files)</span>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Notifications Tab -->
      <div v-if="activeTab === 'notifications'" class="space-y-6">
        <Card title="Backup Notifications" subtitle="Configure when to receive backup notifications">
          <div class="space-y-4">
            <div class="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-900">
              <div>
                <p class="font-medium text-primary">Notify on Success</p>
                <p class="text-sm text-secondary">Send notification when backup completes successfully</p>
              </div>
              <button
                @click="form.notify_on_success = !form.notify_on_success"
                :class="[
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                  form.notify_on_success ? 'bg-emerald-500' : 'bg-gray-300 dark:bg-gray-600'
                ]"
              >
                <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.notify_on_success ? 'translate-x-6' : 'translate-x-1']" />
              </button>
            </div>

            <div class="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-900">
              <div>
                <p class="font-medium text-primary">Notify on Failure</p>
                <p class="text-sm text-secondary">Send notification when backup fails</p>
              </div>
              <button
                @click="form.notify_on_failure = !form.notify_on_failure"
                :class="[
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                  form.notify_on_failure ? 'bg-emerald-500' : 'bg-gray-300 dark:bg-gray-600'
                ]"
              >
                <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.notify_on_failure ? 'translate-x-6' : 'translate-x-1']" />
              </button>
            </div>
          </div>
        </Card>
      </div>

      <!-- Verification Tab -->
      <div v-if="activeTab === 'verification'" class="space-y-6">
        <Card title="Backup Verification" subtitle="Configure automatic backup verification">
          <div class="space-y-4">
            <div class="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-900">
              <div>
                <p class="font-medium text-primary">Auto-verify Backups</p>
                <p class="text-sm text-secondary">Automatically verify backups on a schedule</p>
              </div>
              <button
                @click="form.auto_verify_enabled = !form.auto_verify_enabled"
                :class="[
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                  form.auto_verify_enabled ? 'bg-emerald-500' : 'bg-gray-300 dark:bg-gray-600'
                ]"
              >
                <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.auto_verify_enabled ? 'translate-x-6' : 'translate-x-1']" />
              </button>
            </div>

            <div class="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-900">
              <div>
                <p class="font-medium text-primary">Verify After Backup</p>
                <p class="text-sm text-secondary">Run verification immediately after each backup completes</p>
              </div>
              <button
                @click="form.verify_after_backup = !form.verify_after_backup"
                :class="[
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                  form.verify_after_backup ? 'bg-emerald-500' : 'bg-gray-300 dark:bg-gray-600'
                ]"
              >
                <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.verify_after_backup ? 'translate-x-6' : 'translate-x-1']" />
              </button>
            </div>
          </div>
        </Card>
      </div>
    </template>
  </div>
</template>
