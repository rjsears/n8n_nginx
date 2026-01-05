<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/backups/BackupSettingsDialog.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useBackupStore } from '@/stores/backups'
import { useNotificationStore } from '@/stores/notifications'
import {
  XMarkIcon,
  FolderIcon,
  ClockIcon,
  TrashIcon,
  BellIcon,
  CheckCircleIcon,
  Cog6ToothIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps({
  open: Boolean,
})

const emit = defineEmits(['close', 'saved'])

const backupStore = useBackupStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const saving = ref(false)
const activeTab = ref('storage')
const validatingPath = ref(false)
const pathValidation = ref(null)
const storageDetection = ref(null)
const detectingStorage = ref(false)

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
  { id: 'storage', label: 'Storage', icon: FolderIcon },
  { id: 'compression', label: 'Compression', icon: Cog6ToothIcon },
  { id: 'retention', label: 'Retention', icon: TrashIcon },
  { id: 'schedule', label: 'Schedule', icon: ClockIcon },
  { id: 'notifications', label: 'Notifications', icon: BellIcon },
  { id: 'verification', label: 'Verification', icon: CheckCircleIcon },
]

const compressionLevelMax = computed(() => {
  return form.value.compression_algorithm === 'zstd' ? 22 : 9
})

async function loadConfiguration() {
  loading.value = true
  try {
    // Load config and detect storage in parallel
    const [config, storage] = await Promise.all([
      backupStore.fetchConfiguration(),
      backupStore.detectStorageLocations()
    ])

    // Copy config to form
    Object.keys(form.value).forEach(key => {
      if (config[key] !== undefined) {
        form.value[key] = config[key]
      }
    })

    // Store detected storage info
    storageDetection.value = storage

    // If no primary path set and we have a recommended path, use it
    if (!form.value.primary_storage_path && storage.recommended_path) {
      form.value.primary_storage_path = storage.recommended_path
    }

    // Auto-detect NFS
    if (storage.has_nfs && storage.nfs_mounts.length > 0) {
      const nfsMount = storage.nfs_mounts[0]
      if (!form.value.nfs_storage_path) {
        form.value.nfs_storage_path = nfsMount.path
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
    emit('saved')
    emit('close')
  } catch (err) {
    notificationStore.error('Failed to save configuration')
  } finally {
    saving.value = false
  }
}

function close() {
  emit('close')
}

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    loadConfiguration()
    activeTab.value = 'storage'
    pathValidation.value = null
  }
})

onMounted(() => {
  if (props.open) {
    loadConfiguration()
  }
})
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center">
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/50" @click="close"></div>

      <!-- Dialog -->
      <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden m-4">
        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 class="text-xl font-semibold text-gray-900 dark:text-white">Backup Configuration</h2>
          <button @click="close" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <XMarkIcon class="h-6 w-6" />
          </button>
        </div>

        <!-- Loading State -->
        <div v-if="loading" class="p-12 text-center">
          <div class="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto"></div>
          <p class="mt-4 text-gray-500">Loading configuration...</p>
        </div>

        <!-- Content -->
        <div v-else class="flex h-[600px]">
          <!-- Sidebar Tabs -->
          <div class="w-48 bg-gray-50 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 p-2">
            <nav class="space-y-1">
              <button
                v-for="tab in tabs"
                :key="tab.id"
                @click="activeTab = tab.id"
                :class="[
                  'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left text-sm font-medium transition-colors',
                  activeTab === tab.id
                    ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
                ]"
              >
                <component :is="tab.icon" class="h-5 w-5" />
                {{ tab.label }}
              </button>
            </nav>
          </div>

          <!-- Tab Content -->
          <div class="flex-1 overflow-y-auto p-6">
            <!-- Storage Tab -->
            <div v-if="activeTab === 'storage'" class="space-y-6">
              <div>
                <div class="flex items-center justify-between mb-4">
                  <h3 class="text-lg font-medium text-gray-900 dark:text-white">Storage Settings</h3>
                  <button
                    @click="detectStorage"
                    :disabled="detectingStorage"
                    class="btn-secondary text-sm"
                  >
                    {{ detectingStorage ? 'Detecting...' : 'Refresh Detection' }}
                  </button>
                </div>

                <!-- Detected Storage Locations -->
                <div v-if="storageDetection" class="mb-6 p-4 bg-gray-50 dark:bg-gray-900 rounded-lg">
                  <h4 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Detected Storage Locations</h4>

                  <!-- NFS Mounts -->
                  <div v-if="storageDetection.has_nfs" class="mb-4">
                    <div class="flex items-center gap-2 mb-2">
                      <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                        NFS Available
                      </span>
                    </div>
                    <div class="space-y-2">
                      <div
                        v-for="nfs in storageDetection.nfs_mounts"
                        :key="nfs.path"
                        class="flex items-center justify-between p-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700"
                      >
                        <div>
                          <p class="text-sm font-mono text-gray-900 dark:text-white">{{ nfs.path }}</p>
                          <p class="text-xs text-gray-500">
                            {{ nfs.source }} ({{ nfs.fs_type }})
                            <span v-if="nfs.free_space_gb"> · {{ nfs.free_space_gb }} GB free</span>
                          </p>
                        </div>
                        <button
                          v-if="nfs.is_writable"
                          @click="selectNfsPath(nfs.path)"
                          class="btn-primary text-xs px-2 py-1"
                        >
                          Use NFS
                        </button>
                        <span v-else class="text-xs text-red-500">Not writable</span>
                      </div>
                    </div>
                  </div>

                  <!-- Local Paths -->
                  <div>
                    <p class="text-xs text-gray-500 mb-2">Local Paths:</p>
                    <div class="space-y-2">
                      <div
                        v-for="local in storageDetection.local_paths"
                        :key="local.path"
                        class="flex items-center justify-between p-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700"
                      >
                        <div>
                          <p class="text-sm font-mono text-gray-900 dark:text-white">{{ local.path }}</p>
                          <p class="text-xs text-gray-500">
                            <span v-if="local.exists">
                              <span v-if="local.is_writable" class="text-green-600">Writable</span>
                              <span v-else class="text-red-500">Not writable</span>
                              <span v-if="local.free_space_gb"> · {{ local.free_space_gb }} GB free</span>
                            </span>
                            <span v-else class="text-yellow-600">Does not exist</span>
                          </p>
                        </div>
                        <button
                          v-if="local.is_writable"
                          @click="selectStoragePath(local.path)"
                          class="btn-secondary text-xs px-2 py-1"
                        >
                          Select
                        </button>
                      </div>
                    </div>
                  </div>

                  <!-- Recommended -->
                  <div v-if="storageDetection.recommended_path" class="mt-3 p-2 bg-blue-50 dark:bg-blue-900/20 rounded">
                    <p class="text-xs text-blue-700 dark:text-blue-400">
                      Recommended: <span class="font-mono">{{ storageDetection.recommended_path }}</span>
                    </p>
                  </div>
                </div>

                <div class="space-y-4">
                  <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Primary Storage Path
                    </label>
                    <div class="flex gap-2">
                      <input
                        v-model="form.primary_storage_path"
                        type="text"
                        class="input-field flex-1"
                        placeholder="/app/backups"
                        @blur="validatePath(form.primary_storage_path)"
                      />
                      <button
                        @click="validatePath(form.primary_storage_path)"
                        :disabled="validatingPath"
                        class="btn-secondary px-4"
                      >
                        {{ validatingPath ? 'Checking...' : 'Validate' }}
                      </button>
                    </div>
                    <p class="mt-1 text-sm text-gray-500">Local directory for storing backups</p>
                  </div>

                  <!-- Path validation result -->
                  <div v-if="pathValidation" class="p-3 rounded-lg" :class="pathValidation.is_writable ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'">
                    <div class="flex items-center gap-2">
                      <CheckCircleIcon v-if="pathValidation.is_writable" class="h-5 w-5 text-green-500" />
                      <XMarkIcon v-else class="h-5 w-5 text-red-500" />
                      <span :class="pathValidation.is_writable ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'">
                        {{ pathValidation.is_writable ? 'Path is valid and writable' : 'Path is not accessible or writable' }}
                      </span>
                    </div>
                    <div v-if="pathValidation.free_space_gb" class="mt-2 text-sm text-gray-600 dark:text-gray-400">
                      Free space: {{ pathValidation.free_space_gb }} GB / {{ pathValidation.total_space_gb }} GB
                    </div>
                  </div>

                  <div class="flex items-center justify-between py-3">
                    <div>
                      <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Enable NFS Storage</label>
                      <p class="text-sm text-gray-500">Store backups on NFS mount</p>
                    </div>
                    <button
                      @click="form.nfs_enabled = !form.nfs_enabled"
                      :class="[
                        'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                        form.nfs_enabled ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                      ]"
                    >
                      <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.nfs_enabled ? 'translate-x-6' : 'translate-x-1']" />
                    </button>
                  </div>

                  <div v-if="form.nfs_enabled">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      NFS Storage Path
                    </label>
                    <input
                      v-model="form.nfs_storage_path"
                      type="text"
                      class="input-field w-full"
                      placeholder="/mnt/backups"
                    />
                  </div>

                  <div v-if="form.nfs_enabled">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Storage Preference
                    </label>
                    <select v-model="form.storage_preference" class="input-field w-full">
                      <option value="local">Local only</option>
                      <option value="nfs">NFS only</option>
                      <option value="both">Both (redundant)</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>

            <!-- Compression Tab -->
            <div v-if="activeTab === 'compression'" class="space-y-6">
              <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">Compression Settings</h3>

              <div class="flex items-center justify-between py-3">
                <div>
                  <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Enable Compression</label>
                  <p class="text-sm text-gray-500">Compress backups to save space</p>
                </div>
                <button
                  @click="form.compression_enabled = !form.compression_enabled"
                  :class="[
                    'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                    form.compression_enabled ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                  ]"
                >
                  <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.compression_enabled ? 'translate-x-6' : 'translate-x-1']" />
                </button>
              </div>

              <div v-if="form.compression_enabled" class="space-y-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Algorithm
                  </label>
                  <select v-model="form.compression_algorithm" class="input-field w-full">
                    <option value="gzip">Gzip (widely compatible)</option>
                    <option value="zstd">Zstandard (faster, better ratio)</option>
                  </select>
                </div>

                <div>
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Compression Level: {{ form.compression_level }}
                  </label>
                  <input
                    v-model.number="form.compression_level"
                    type="range"
                    min="1"
                    :max="compressionLevelMax"
                    class="w-full"
                  />
                  <div class="flex justify-between text-xs text-gray-500">
                    <span>Fast (larger)</span>
                    <span>Slow (smaller)</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Retention Tab -->
            <div v-if="activeTab === 'retention'" class="space-y-6">
              <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">Retention Settings</h3>

              <div class="flex items-center justify-between py-3">
                <div>
                  <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Enable Automatic Cleanup</label>
                  <p class="text-sm text-gray-500">Automatically delete old backups</p>
                </div>
                <button
                  @click="form.retention_enabled = !form.retention_enabled"
                  :class="[
                    'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                    form.retention_enabled ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                  ]"
                >
                  <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.retention_enabled ? 'translate-x-6' : 'translate-x-1']" />
                </button>
              </div>

              <div v-if="form.retention_enabled" class="space-y-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Keep Backups For (days)
                  </label>
                  <input
                    v-model.number="form.retention_days"
                    type="number"
                    min="1"
                    max="365"
                    class="input-field w-full"
                  />
                </div>

                <div>
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Maximum Backups to Keep
                  </label>
                  <input
                    v-model.number="form.retention_count"
                    type="number"
                    min="1"
                    max="100"
                    class="input-field w-full"
                  />
                </div>

                <div>
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Minimum Backups to Keep
                  </label>
                  <input
                    v-model.number="form.retention_min_count"
                    type="number"
                    min="1"
                    max="50"
                    class="input-field w-full"
                  />
                  <p class="mt-1 text-sm text-gray-500">Never delete below this number, even if older than retention period</p>
                </div>
              </div>
            </div>

            <!-- Schedule Tab -->
            <div v-if="activeTab === 'schedule'" class="space-y-6">
              <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">Schedule Settings</h3>

              <div class="flex items-center justify-between py-3">
                <div>
                  <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Enable Scheduled Backups</label>
                  <p class="text-sm text-gray-500">Run backups automatically</p>
                </div>
                <button
                  @click="form.schedule_enabled = !form.schedule_enabled"
                  :class="[
                    'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                    form.schedule_enabled ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                  ]"
                >
                  <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.schedule_enabled ? 'translate-x-6' : 'translate-x-1']" />
                </button>
              </div>

              <div v-if="form.schedule_enabled" class="space-y-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Frequency
                  </label>
                  <select v-model="form.schedule_frequency" class="input-field w-full">
                    <option value="hourly">Hourly</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>

                <div>
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Time
                  </label>
                  <input
                    v-model="form.schedule_time"
                    type="time"
                    class="input-field w-full"
                  />
                </div>

                <div v-if="form.schedule_frequency === 'weekly'">
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Day of Week
                  </label>
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
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Day of Month
                  </label>
                  <input
                    v-model.number="form.schedule_day_of_month"
                    type="number"
                    min="1"
                    max="31"
                    class="input-field w-full"
                  />
                </div>

                <div class="pt-4 border-t border-gray-200 dark:border-gray-700">
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Default Backup Type
                  </label>
                  <select v-model="form.default_backup_type" class="input-field w-full">
                    <option value="postgres_full">Full PostgreSQL Backup</option>
                    <option value="postgres_n8n">n8n Database Only</option>
                    <option value="postgres_mgmt">Management Database Only</option>
                  </select>
                </div>

                <div class="space-y-3">
                  <div class="flex items-center gap-3">
                    <input
                      v-model="form.include_n8n_config"
                      type="checkbox"
                      id="include_n8n_config"
                      class="h-4 w-4 rounded border-gray-300"
                    />
                    <label for="include_n8n_config" class="text-sm text-gray-700 dark:text-gray-300">
                      Include n8n configuration files
                    </label>
                  </div>
                  <div class="flex items-center gap-3">
                    <input
                      v-model="form.include_ssl_certs"
                      type="checkbox"
                      id="include_ssl_certs"
                      class="h-4 w-4 rounded border-gray-300"
                    />
                    <label for="include_ssl_certs" class="text-sm text-gray-700 dark:text-gray-300">
                      Include SSL certificates
                    </label>
                  </div>
                  <div class="flex items-center gap-3">
                    <input
                      v-model="form.include_env_files"
                      type="checkbox"
                      id="include_env_files"
                      class="h-4 w-4 rounded border-gray-300"
                    />
                    <label for="include_env_files" class="text-sm text-gray-700 dark:text-gray-300">
                      Include .env files
                    </label>
                  </div>
                </div>
              </div>
            </div>

            <!-- Notifications Tab -->
            <div v-if="activeTab === 'notifications'" class="space-y-6">
              <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">Notification Settings</h3>

              <div class="space-y-4">
                <div class="flex items-center justify-between py-3">
                  <div>
                    <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Notify on Success</label>
                    <p class="text-sm text-gray-500">Send notification when backup completes</p>
                  </div>
                  <button
                    @click="form.notify_on_success = !form.notify_on_success"
                    :class="[
                      'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                      form.notify_on_success ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                    ]"
                  >
                    <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.notify_on_success ? 'translate-x-6' : 'translate-x-1']" />
                  </button>
                </div>

                <div class="flex items-center justify-between py-3">
                  <div>
                    <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Notify on Failure</label>
                    <p class="text-sm text-gray-500">Send notification when backup fails</p>
                  </div>
                  <button
                    @click="form.notify_on_failure = !form.notify_on_failure"
                    :class="[
                      'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                      form.notify_on_failure ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                    ]"
                  >
                    <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.notify_on_failure ? 'translate-x-6' : 'translate-x-1']" />
                  </button>
                </div>
              </div>
            </div>

            <!-- Verification Tab -->
            <div v-if="activeTab === 'verification'" class="space-y-6">
              <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">Verification Settings</h3>

              <div class="space-y-4">
                <div class="flex items-center justify-between py-3">
                  <div>
                    <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Auto-verify Backups</label>
                    <p class="text-sm text-gray-500">Automatically verify backups on schedule</p>
                  </div>
                  <button
                    @click="form.auto_verify_enabled = !form.auto_verify_enabled"
                    :class="[
                      'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                      form.auto_verify_enabled ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                    ]"
                  >
                    <span :class="['inline-block h-4 w-4 transform rounded-full bg-white transition-transform', form.auto_verify_enabled ? 'translate-x-6' : 'translate-x-1']" />
                  </button>
                </div>

                <div class="flex items-center justify-between py-3">
                  <div>
                    <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Verify After Backup</label>
                    <p class="text-sm text-gray-500">Run verification immediately after each backup</p>
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
        </div>

        <!-- Footer -->
        <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <button @click="close" class="btn-secondary">
            Cancel
          </button>
          <button
            @click="save"
            :disabled="saving"
            class="btn-primary"
          >
            {{ saving ? 'Saving...' : 'Save Configuration' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
