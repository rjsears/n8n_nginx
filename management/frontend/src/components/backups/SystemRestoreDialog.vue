<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/backups/SystemRestoreDialog.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref, computed, watch } from 'vue'
import { useBackupStore } from '@/stores/backups'
import { useNotificationStore } from '@/stores/notifications'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import {
  XMarkIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  CircleStackIcon,
  DocumentTextIcon,
  ShieldCheckIcon,
  TableCellsIcon,
  Cog6ToothIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps({
  open: Boolean,
  backup: Object,
})

const emit = defineEmits(['close', 'restored'])

const backupStore = useBackupStore()
const notificationStore = useNotificationStore()

// State
const step = ref('preview') // 'preview', 'confirm', 'restoring', 'complete'
const loading = ref(false)
const preview = ref(null)

// Restore options
const restoreOptions = ref({
  databases: true,
  configs: true,
  ssl: true,
  createBackups: true,
  selectedDatabases: [],
  selectedConfigs: [],
})

// Results
const restoreResult = ref(null)

// Reset state when dialog opens
watch(() => props.open, async (isOpen) => {
  if (isOpen && props.backup) {
    step.value = 'preview'
    loading.value = true
    preview.value = null
    restoreResult.value = null
    restoreOptions.value = {
      databases: true,
      configs: true,
      ssl: true,
      createBackups: true,
      selectedDatabases: [],
      selectedConfigs: [],
    }

    try {
      preview.value = await backupStore.fetchRestorePreview(props.backup.id)
      // Pre-select all items
      if (preview.value.databases) {
        restoreOptions.value.selectedDatabases = preview.value.databases.map(d => d.name)
      }
      if (preview.value.config_files) {
        restoreOptions.value.selectedConfigs = preview.value.config_files.map(c => c.name)
      }
    } catch (err) {
      notificationStore.error('Failed to load restore preview')
      emit('close')
    } finally {
      loading.value = false
    }
  }
})

// Computed
const canRestore = computed(() => {
  if (!preview.value) return false
  const hasDatabase = restoreOptions.value.databases && restoreOptions.value.selectedDatabases.length > 0
  const hasConfig = restoreOptions.value.configs && restoreOptions.value.selectedConfigs.length > 0
  const hasSsl = restoreOptions.value.ssl && preview.value.ssl_certificates?.length > 0
  return hasDatabase || hasConfig || hasSsl
})

const restoreSummary = computed(() => {
  const items = []
  if (restoreOptions.value.databases && restoreOptions.value.selectedDatabases.length > 0) {
    items.push(`${restoreOptions.value.selectedDatabases.length} database(s)`)
  }
  if (restoreOptions.value.configs && restoreOptions.value.selectedConfigs.length > 0) {
    items.push(`${restoreOptions.value.selectedConfigs.length} config file(s)`)
  }
  if (restoreOptions.value.ssl && preview.value?.ssl_certificates?.length > 0) {
    items.push(`${preview.value.ssl_certificates.length} SSL certificate(s)`)
  }
  return items.join(', ') || 'Nothing selected'
})

// Methods
function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

function formatDate(dateStr) {
  if (!dateStr) return 'N/A'
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function toggleDatabase(dbName) {
  const idx = restoreOptions.value.selectedDatabases.indexOf(dbName)
  if (idx > -1) {
    restoreOptions.value.selectedDatabases.splice(idx, 1)
  } else {
    restoreOptions.value.selectedDatabases.push(dbName)
  }
}

function toggleConfig(configName) {
  const idx = restoreOptions.value.selectedConfigs.indexOf(configName)
  if (idx > -1) {
    restoreOptions.value.selectedConfigs.splice(idx, 1)
  } else {
    restoreOptions.value.selectedConfigs.push(configName)
  }
}

function proceedToConfirm() {
  step.value = 'confirm'
}

function backToPreview() {
  step.value = 'preview'
}

async function performRestore() {
  step.value = 'restoring'
  loading.value = true

  try {
    restoreResult.value = await backupStore.fullSystemRestore(props.backup.id, {
      restoreDatabases: restoreOptions.value.databases,
      restoreConfigs: restoreOptions.value.configs,
      restoreSsl: restoreOptions.value.ssl,
      databaseNames: restoreOptions.value.selectedDatabases,
      configFiles: restoreOptions.value.selectedConfigs,
      createBackups: restoreOptions.value.createBackups,
    })

    step.value = 'complete'

    if (restoreResult.value.status === 'success') {
      notificationStore.success('System restore completed successfully')
    } else if (restoreResult.value.status === 'partial') {
      notificationStore.warning('System restore completed with some warnings')
    } else {
      notificationStore.error('System restore failed')
    }

    emit('restored', restoreResult.value)
  } catch (err) {
    restoreResult.value = {
      status: 'failed',
      error: err.message || 'Unknown error',
    }
    step.value = 'complete'
    notificationStore.error('System restore failed')
  } finally {
    loading.value = false
  }
}

function close() {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open"
        class="fixed inset-0 z-[100] flex items-center justify-center p-4"
      >
        <!-- Backdrop -->
        <div
          class="absolute inset-0 bg-black/50"
          @click="close"
        />

        <!-- Dialog -->
        <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col border border-gray-400 dark:border-gray-700">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-full bg-amber-100 dark:bg-amber-500/20">
                <ArrowPathIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <h3 class="text-lg font-semibold text-primary">System Restore</h3>
                <p class="text-sm text-secondary" v-if="backup">
                  {{ backup.filename }} &bull; {{ formatDate(backup.created_at) }}
                </p>
              </div>
            </div>
            <button
              @click="close"
              class="p-1 rounded-lg text-secondary hover:text-primary hover:bg-surface-hover"
            >
              <XMarkIcon class="h-5 w-5" />
            </button>
          </div>

          <!-- Loading State -->
          <div v-if="loading && step === 'preview'" class="flex-1 flex items-center justify-center py-12">
            <LoadingSpinner text="Loading restore preview..." />
          </div>

          <!-- Preview Step -->
          <template v-else-if="step === 'preview' && preview">
            <div class="flex-1 overflow-y-auto p-6 space-y-6">
              <!-- Summary Stats -->
              <div class="grid grid-cols-4 gap-4">
                <div class="text-center p-3 rounded-lg bg-blue-50 dark:bg-blue-500/10">
                  <p class="text-2xl font-bold text-blue-600 dark:text-blue-400">
                    {{ preview.databases?.length || 0 }}
                  </p>
                  <p class="text-xs text-secondary">Databases</p>
                </div>
                <div class="text-center p-3 rounded-lg bg-purple-50 dark:bg-purple-500/10">
                  <p class="text-2xl font-bold text-purple-600 dark:text-purple-400">
                    {{ preview.config_files?.length || 0 }}
                  </p>
                  <p class="text-xs text-secondary">Config Files</p>
                </div>
                <div class="text-center p-3 rounded-lg bg-emerald-50 dark:bg-emerald-500/10">
                  <p class="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                    {{ preview.ssl_certificates?.length || 0 }}
                  </p>
                  <p class="text-xs text-secondary">SSL Certs</p>
                </div>
                <div class="text-center p-3 rounded-lg bg-gray-50 dark:bg-gray-700">
                  <p class="text-2xl font-bold text-primary">
                    {{ preview.workflow_count || 0 }}
                  </p>
                  <p class="text-xs text-secondary">Workflows</p>
                </div>
              </div>

              <!-- Databases Section -->
              <div v-if="preview.databases?.length > 0">
                <div class="flex items-center gap-2 mb-3">
                  <input
                    type="checkbox"
                    id="restoreDatabases"
                    v-model="restoreOptions.databases"
                    class="rounded border-gray-300"
                  />
                  <label for="restoreDatabases" class="flex items-center gap-2 font-medium text-primary">
                    <TableCellsIcon class="h-5 w-5 text-blue-500" />
                    Databases
                  </label>
                </div>

                <div v-if="restoreOptions.databases" class="ml-6 space-y-2">
                  <div
                    v-for="db in preview.databases"
                    :key="db.name"
                    class="flex items-center justify-between p-3 rounded-lg bg-surface-hover border border-gray-200 dark:border-gray-600"
                  >
                    <label class="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        :checked="restoreOptions.selectedDatabases.includes(db.name)"
                        @change="toggleDatabase(db.name)"
                        class="rounded border-gray-300"
                      />
                      <div>
                        <p class="font-medium text-primary">{{ db.name }}</p>
                        <p class="text-xs text-secondary">{{ formatBytes(db.size) }}</p>
                      </div>
                    </label>
                  </div>
                </div>
              </div>

              <!-- Config Files Section -->
              <div v-if="preview.config_files?.length > 0">
                <div class="flex items-center gap-2 mb-3">
                  <input
                    type="checkbox"
                    id="restoreConfigs"
                    v-model="restoreOptions.configs"
                    class="rounded border-gray-300"
                  />
                  <label for="restoreConfigs" class="flex items-center gap-2 font-medium text-primary">
                    <Cog6ToothIcon class="h-5 w-5 text-purple-500" />
                    Config Files
                  </label>
                </div>

                <div v-if="restoreOptions.configs" class="ml-6 space-y-2">
                  <div
                    v-for="config in preview.config_files"
                    :key="config.name"
                    class="flex items-center justify-between p-3 rounded-lg bg-surface-hover border border-gray-200 dark:border-gray-600"
                  >
                    <label class="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        :checked="restoreOptions.selectedConfigs.includes(config.name)"
                        @change="toggleConfig(config.name)"
                        class="rounded border-gray-300"
                      />
                      <div>
                        <p class="font-medium text-primary">{{ config.name }}</p>
                        <p class="text-xs text-secondary">{{ formatBytes(config.size) }}</p>
                      </div>
                    </label>
                  </div>
                </div>
              </div>

              <!-- SSL Certificates Section -->
              <div v-if="preview.ssl_certificates?.length > 0">
                <div class="flex items-center gap-2 mb-3">
                  <input
                    type="checkbox"
                    id="restoreSsl"
                    v-model="restoreOptions.ssl"
                    class="rounded border-gray-300"
                  />
                  <label for="restoreSsl" class="flex items-center gap-2 font-medium text-primary">
                    <ShieldCheckIcon class="h-5 w-5 text-emerald-500" />
                    SSL Certificates
                  </label>
                </div>

                <div v-if="restoreOptions.ssl" class="ml-6 space-y-2">
                  <div
                    v-for="ssl in preview.ssl_certificates"
                    :key="ssl.domain"
                    class="flex items-center justify-between p-3 rounded-lg bg-surface-hover border border-gray-200 dark:border-gray-600"
                  >
                    <div class="flex items-center gap-3">
                      <ShieldCheckIcon class="h-5 w-5 text-emerald-500" />
                      <div>
                        <p class="font-medium text-primary">{{ ssl.domain }}</p>
                        <p class="text-xs text-secondary">
                          {{ ssl.certificates?.length || 0 }} certificate files
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Create Backups Option -->
              <div class="flex items-center gap-2 p-3 rounded-lg bg-gray-50 dark:bg-gray-700">
                <input
                  type="checkbox"
                  id="createBackups"
                  v-model="restoreOptions.createBackups"
                  class="rounded border-gray-300"
                />
                <label for="createBackups" class="text-sm text-primary">
                  Create backups of existing files before overwriting
                </label>
              </div>
            </div>

            <!-- Preview Footer -->
            <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-400 dark:border-gray-700">
              <button @click="close" class="btn-secondary">
                Cancel
              </button>
              <button
                @click="proceedToConfirm"
                :disabled="!canRestore"
                class="btn-primary"
              >
                Continue to Restore
              </button>
            </div>
          </template>

          <!-- Confirm Step -->
          <template v-else-if="step === 'confirm'">
            <div class="flex-1 p-6 space-y-4">
              <!-- Warning -->
              <div class="p-4 rounded-lg bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30">
                <div class="flex gap-3">
                  <ExclamationTriangleIcon class="h-6 w-6 text-red-500 flex-shrink-0" />
                  <div>
                    <h4 class="font-semibold text-red-800 dark:text-red-300">Warning: Destructive Action</h4>
                    <p class="text-sm text-red-700 dark:text-red-400 mt-1">
                      This will <strong>overwrite</strong> existing data with data from the backup.
                      This action cannot be undone (unless you have backups enabled).
                    </p>
                  </div>
                </div>
              </div>

              <!-- Summary -->
              <div class="p-4 rounded-lg bg-gray-50 dark:bg-gray-700">
                <h4 class="font-medium text-primary mb-3">You are about to restore:</h4>
                <p class="text-secondary">{{ restoreSummary }}</p>

                <div v-if="restoreOptions.createBackups" class="mt-3 text-sm text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                  <CheckCircleIcon class="h-4 w-4" />
                  Existing files will be backed up before overwriting
                </div>
              </div>

              <!-- Confirmation -->
              <p class="text-sm text-secondary">
                Are you sure you want to proceed with the system restore?
              </p>
            </div>

            <!-- Confirm Footer -->
            <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-400 dark:border-gray-700">
              <button @click="backToPreview" class="btn-secondary">
                Back
              </button>
              <button
                @click="performRestore"
                class="btn-danger flex items-center gap-2"
              >
                <ArrowPathIcon class="h-4 w-4" />
                Restore Now
              </button>
            </div>
          </template>

          <!-- Restoring Step -->
          <template v-else-if="step === 'restoring'">
            <div class="flex-1 flex items-center justify-center py-12">
              <div class="text-center">
                <LoadingSpinner size="lg" />
                <p class="mt-4 text-lg font-medium text-primary">Restoring System...</p>
                <p class="text-sm text-secondary mt-2">
                  This may take a few minutes. Do not close this window.
                </p>
              </div>
            </div>
          </template>

          <!-- Complete Step -->
          <template v-else-if="step === 'complete' && restoreResult">
            <div class="flex-1 overflow-y-auto p-6 space-y-4">
              <!-- Status Banner -->
              <div
                :class="[
                  'p-4 rounded-lg border',
                  restoreResult.status === 'success' ? 'bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/30' :
                  restoreResult.status === 'partial' ? 'bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/30' :
                  'bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/30'
                ]"
              >
                <div class="flex gap-3">
                  <component
                    :is="restoreResult.status === 'success' ? CheckCircleIcon : ExclamationTriangleIcon"
                    :class="[
                      'h-6 w-6 flex-shrink-0',
                      restoreResult.status === 'success' ? 'text-emerald-500' :
                      restoreResult.status === 'partial' ? 'text-amber-500' :
                      'text-red-500'
                    ]"
                  />
                  <div>
                    <h4 :class="[
                      'font-semibold',
                      restoreResult.status === 'success' ? 'text-emerald-800 dark:text-emerald-300' :
                      restoreResult.status === 'partial' ? 'text-amber-800 dark:text-amber-300' :
                      'text-red-800 dark:text-red-300'
                    ]">
                      {{
                        restoreResult.status === 'success' ? 'Restore Completed Successfully' :
                        restoreResult.status === 'partial' ? 'Restore Completed with Warnings' :
                        'Restore Failed'
                      }}
                    </h4>
                    <p v-if="restoreResult.message" class="text-sm mt-1 text-secondary">
                      {{ restoreResult.message }}
                    </p>
                    <p v-if="restoreResult.error" class="text-sm mt-1 text-red-600 dark:text-red-400">
                      {{ restoreResult.error }}
                    </p>
                  </div>
                </div>
              </div>

              <!-- Database Results -->
              <div v-if="restoreResult.databases?.length > 0">
                <h4 class="font-medium text-primary mb-2 flex items-center gap-2">
                  <TableCellsIcon class="h-4 w-4 text-blue-500" />
                  Databases
                </h4>
                <div class="space-y-2">
                  <div
                    v-for="db in restoreResult.databases"
                    :key="db.database"
                    class="flex items-center justify-between p-2 rounded bg-surface-hover"
                  >
                    <span class="text-sm text-primary">{{ db.database }}</span>
                    <span :class="[
                      'text-xs px-2 py-0.5 rounded-full',
                      db.status === 'success' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400' :
                      db.status === 'partial' ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400' :
                      'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400'
                    ]">
                      {{ db.status }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Config Results -->
              <div v-if="restoreResult.config_files?.length > 0">
                <h4 class="font-medium text-primary mb-2 flex items-center gap-2">
                  <Cog6ToothIcon class="h-4 w-4 text-purple-500" />
                  Config Files
                </h4>
                <div class="space-y-2">
                  <div
                    v-for="config in restoreResult.config_files"
                    :key="config.config_path"
                    class="flex items-center justify-between p-2 rounded bg-surface-hover"
                  >
                    <span class="text-sm text-primary">{{ config.config_path }}</span>
                    <span :class="[
                      'text-xs px-2 py-0.5 rounded-full',
                      config.status === 'success' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400' :
                      'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400'
                    ]">
                      {{ config.status }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- SSL Results -->
              <div v-if="restoreResult.ssl_certificates?.length > 0">
                <h4 class="font-medium text-primary mb-2 flex items-center gap-2">
                  <ShieldCheckIcon class="h-4 w-4 text-emerald-500" />
                  SSL Certificates
                </h4>
                <div class="space-y-2">
                  <div
                    v-for="ssl in restoreResult.ssl_certificates"
                    :key="ssl.config_path"
                    class="flex items-center justify-between p-2 rounded bg-surface-hover"
                  >
                    <span class="text-sm text-primary">{{ ssl.config_path }}</span>
                    <span :class="[
                      'text-xs px-2 py-0.5 rounded-full',
                      ssl.status === 'success' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400' :
                      'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400'
                    ]">
                      {{ ssl.status }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Errors -->
              <div v-if="restoreResult.errors?.length > 0">
                <h4 class="font-medium text-red-600 dark:text-red-400 mb-2">Errors</h4>
                <ul class="text-sm text-red-600 dark:text-red-400 list-disc list-inside">
                  <li v-for="(err, idx) in restoreResult.errors" :key="idx">{{ err }}</li>
                </ul>
              </div>

              <!-- Warnings -->
              <div v-if="restoreResult.warnings?.length > 0">
                <h4 class="font-medium text-amber-600 dark:text-amber-400 mb-2">Warnings</h4>
                <ul class="text-sm text-amber-600 dark:text-amber-400 list-disc list-inside">
                  <li v-for="(warn, idx) in restoreResult.warnings" :key="idx">{{ warn }}</li>
                </ul>
              </div>

              <!-- Restart Notice -->
              <div v-if="restoreResult.status === 'success' || restoreResult.status === 'partial'" class="p-3 rounded-lg bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30">
                <p class="text-sm text-blue-800 dark:text-blue-300">
                  <strong>Note:</strong> You may need to restart your Docker containers for all changes to take effect.
                </p>
              </div>
            </div>

            <!-- Complete Footer -->
            <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-400 dark:border-gray-700">
              <button @click="close" class="btn-primary">
                Close
              </button>
            </div>
          </template>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.btn-danger {
  @apply px-4 py-2 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed;
}
</style>
