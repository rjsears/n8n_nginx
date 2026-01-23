<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/backups/BackupContentsDialog.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref, computed, watch } from 'vue'
import { useBackupStore } from '../../stores/backups'
import { useNotificationStore } from '../../stores/notifications'
import LoadingSpinner from '../common/LoadingSpinner.vue'
import StatusBadge from '../common/StatusBadge.vue'
import WorkflowRestoreDialog from './WorkflowRestoreDialog.vue'
import {
  XMarkIcon,
  CircleStackIcon,
  DocumentTextIcon,
  Cog6ToothIcon,
  TableCellsIcon,
  MagnifyingGlassIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowDownTrayIcon,
  ArrowPathIcon,
  ShieldCheckIcon,
  GlobeAltIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps({
  open: Boolean,
  backup: Object,
})

const emit = defineEmits(['close', 'restore-workflow'])

const backupStore = useBackupStore()
const notificationStore = useNotificationStore()

const loading = ref(false)
const contents = ref(null)
const activeTab = ref('workflows')
const searchQuery = ref('')
const restoreDialog = ref({ open: false, workflow: null })

// Base tabs configuration
const baseTabs = [
  { id: 'workflows', label: 'Workflows', icon: CircleStackIcon },
  { id: 'config', label: 'Config Files', icon: Cog6ToothIcon },
  { id: 'database', label: 'Database', icon: TableCellsIcon },
]

// Computed tabs - includes Public Website tab if available
const tabs = computed(() => {
  const allTabs = [...baseTabs]
  // Add Public Website tab if feature is available and backup has files
  if (contents.value?.public_website_available && contents.value?.public_website_file_count > 0) {
    allTabs.push({ id: 'publicwebsite', label: 'Public Website', icon: GlobeAltIcon })
  }
  return allTabs
})

// Public website restore state
const selectedPublicWebsiteFiles = ref([])
const publicWebsiteRestoring = ref(false)
const selectAllPublicWebsite = computed({
  get() {
    const manifest = contents.value?.public_website_manifest || []
    return manifest.length > 0 && selectedPublicWebsiteFiles.value.length === manifest.length
  },
  set(value) {
    if (value) {
      selectedPublicWebsiteFiles.value = (contents.value?.public_website_manifest || []).map(f => f.path)
    } else {
      selectedPublicWebsiteFiles.value = []
    }
  }
})

// Load contents when dialog opens
watch(() => props.open, async (isOpen) => {
  if (isOpen && props.backup) {
    await loadContents()
  } else {
    contents.value = null
    activeTab.value = 'workflows'
    searchQuery.value = ''
  }
})

async function loadContents() {
  loading.value = true
  try {
    contents.value = await backupStore.fetchBackupContents(props.backup.id)
  } catch (err) {
    notificationStore.error('Failed to load backup contents')
    emit('close')
  } finally {
    loading.value = false
  }
}

// Filtered workflows based on search
const filteredWorkflows = computed(() => {
  if (!contents.value?.workflows_manifest) return []
  if (!searchQuery.value) return contents.value.workflows_manifest

  const query = searchQuery.value.toLowerCase()
  return contents.value.workflows_manifest.filter(w =>
    w.name.toLowerCase().includes(query)
  )
})

// Format file size
function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

// Format date
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

// Handle restore workflow request
function requestRestoreWorkflow(workflow) {
  restoreDialog.value = { open: true, workflow }
}

function closeRestoreDialog() {
  restoreDialog.value = { open: false, workflow: null }
}

function handleRestored(data) {
  closeRestoreDialog()
  notificationStore.success(`Workflow "${data.new_name}" restored successfully`)
  emit('restore-workflow', { backup: props.backup, ...data })
}

function close() {
  emit('close')
}

// Public website file operations
async function downloadPublicWebsiteFile(filePath) {
  try {
    const response = await backupStore.downloadPublicWebsiteFile(props.backup.id, filePath)
    // Create download link
    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filePath.split('/').pop()
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (err) {
    notificationStore.error(`Failed to download ${filePath}`)
  }
}

async function restorePublicWebsiteFiles(filePaths = null, overwrite = false) {
  publicWebsiteRestoring.value = true
  try {
    const result = await backupStore.restorePublicWebsiteFiles(props.backup.id, filePaths, overwrite)
    if (result.status === 'success') {
      notificationStore.success(`Restored ${result.restored_count} public website files`)
    } else if (result.status === 'partial') {
      notificationStore.warning(`Restored ${result.restored_count} files, ${result.error_count} errors`)
    } else {
      notificationStore.error('Failed to restore public website files')
    }
    selectedPublicWebsiteFiles.value = []
  } catch (err) {
    notificationStore.error('Failed to restore public website files')
  } finally {
    publicWebsiteRestoring.value = false
  }
}

function restoreSelectedPublicWebsiteFiles() {
  if (selectedPublicWebsiteFiles.value.length === 0) return
  restorePublicWebsiteFiles(selectedPublicWebsiteFiles.value, false)
}

function restoreAllPublicWebsiteFiles() {
  restorePublicWebsiteFiles(null, false)
}

// Get file extension icon/color
function getFileTypeColor(mimeType) {
  if (!mimeType) return 'bg-gray-100 dark:bg-gray-600/20 text-gray-500'
  if (mimeType.startsWith('text/html')) return 'bg-orange-100 dark:bg-orange-500/20 text-orange-500'
  if (mimeType.startsWith('text/css')) return 'bg-blue-100 dark:bg-blue-500/20 text-blue-500'
  if (mimeType.includes('javascript')) return 'bg-yellow-100 dark:bg-yellow-500/20 text-yellow-600'
  if (mimeType.startsWith('image/')) return 'bg-purple-100 dark:bg-purple-500/20 text-purple-500'
  if (mimeType.includes('json')) return 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-500'
  return 'bg-gray-100 dark:bg-gray-600/20 text-gray-500'
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
        <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl max-h-[85vh] flex flex-col border border-gray-400 dark:border-gray-700">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-full bg-blue-100 dark:bg-blue-500/20">
                <CircleStackIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h3 class="text-lg font-semibold text-primary">Backup Contents</h3>
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
          <div v-if="loading" class="flex-1 flex items-center justify-center py-12">
            <LoadingSpinner text="Loading backup contents..." />
          </div>

          <!-- Content -->
          <template v-else-if="contents">
            <!-- Summary Stats -->
            <div class="px-6 py-4 bg-gray-50 dark:bg-gray-750 border-b border-gray-400 dark:border-gray-700">
              <div :class="[
                'grid gap-4',
                contents.public_website_available && contents.public_website_file_count > 0
                  ? 'grid-cols-4'
                  : 'grid-cols-3'
              ]">
                <div class="text-center">
                  <p class="text-2xl font-bold text-primary">{{ contents.workflow_count }}</p>
                  <p class="text-sm text-secondary">Workflows</p>
                </div>
                <div class="text-center">
                  <p class="text-2xl font-bold text-primary">{{ contents.credential_count }}</p>
                  <p class="text-sm text-secondary">Credentials</p>
                </div>
                <div class="text-center">
                  <p class="text-2xl font-bold text-primary">{{ contents.config_file_count }}</p>
                  <p class="text-sm text-secondary">Config Files</p>
                </div>
                <div v-if="contents.public_website_available && contents.public_website_file_count > 0" class="text-center">
                  <p class="text-2xl font-bold text-primary">{{ contents.public_website_file_count }}</p>
                  <p class="text-sm text-secondary">Website Files</p>
                </div>
              </div>
            </div>

            <!-- Tabs -->
            <div class="border-b border-gray-400 dark:border-gray-700">
              <nav class="flex px-6" aria-label="Tabs">
                <button
                  v-for="tab in tabs"
                  :key="tab.id"
                  @click="activeTab = tab.id"
                  :class="[
                    'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                      : 'border-transparent text-secondary hover:text-primary hover:border-gray-300'
                  ]"
                >
                  <component :is="tab.icon" class="h-4 w-4" />
                  {{ tab.label }}
                </button>
              </nav>
            </div>

            <!-- Tab Content -->
            <div class="flex-1 overflow-y-auto p-6">
              <!-- Workflows Tab -->
              <div v-if="activeTab === 'workflows'" class="space-y-4">
                <!-- Search -->
                <div class="relative">
                  <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
                  <input
                    v-model="searchQuery"
                    type="text"
                    placeholder="Search workflows..."
                    class="input-field pl-10"
                  />
                </div>

                <!-- Workflow List -->
                <div v-if="filteredWorkflows.length === 0" class="text-center py-8 text-secondary">
                  <CircleStackIcon class="h-12 w-12 mx-auto mb-2 text-muted" />
                  <p>No workflows found</p>
                </div>

                <div v-else class="space-y-2">
                  <div
                    v-for="workflow in filteredWorkflows"
                    :key="workflow.id"
                    class="flex items-center justify-between p-3 rounded-lg bg-surface-hover border border-gray-300 dark:border-gray-600"
                  >
                    <div class="flex items-center gap-3">
                      <div :class="[
                        'p-2 rounded-lg',
                        workflow.active ? 'bg-emerald-100 dark:bg-emerald-500/20' : 'bg-gray-100 dark:bg-gray-600/20'
                      ]">
                        <CircleStackIcon :class="[
                          'h-5 w-5',
                          workflow.active ? 'text-emerald-500' : 'text-gray-400'
                        ]" />
                      </div>
                      <div>
                        <p class="font-medium text-primary">{{ workflow.name }}</p>
                        <p class="text-xs text-secondary">
                          {{ workflow.node_count || '?' }} nodes
                          <span v-if="workflow.updated_at"> &bull; Updated {{ formatDate(workflow.updated_at) }}</span>
                        </p>
                      </div>
                    </div>
                    <div class="flex items-center gap-2">
                      <StatusBadge :status="workflow.active ? 'active' : 'inactive'" size="sm" />
                      <button
                        @click="requestRestoreWorkflow(workflow)"
                        class="btn-secondary p-2 text-sm"
                        title="Restore this workflow"
                      >
                        <ArrowPathIcon class="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Config Files Tab -->
              <div v-else-if="activeTab === 'config'" class="space-y-4">
                <div v-if="!contents.config_files_manifest?.length" class="text-center py-8 text-secondary">
                  <DocumentTextIcon class="h-12 w-12 mx-auto mb-2 text-muted" />
                  <p>No config files in this backup</p>
                </div>

                <div v-else class="space-y-2">
                  <div
                    v-for="file in contents.config_files_manifest"
                    :key="file.path"
                    class="flex items-center justify-between p-3 rounded-lg bg-surface-hover border border-gray-300 dark:border-gray-600"
                  >
                    <div class="flex items-center gap-3">
                      <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-500/20">
                        <DocumentTextIcon class="h-5 w-5 text-purple-500" />
                      </div>
                      <div>
                        <p class="font-medium text-primary">{{ file.name }}</p>
                        <p class="text-xs text-secondary">
                          {{ formatBytes(file.size) }}
                          <span v-if="file.modified_at"> &bull; Modified {{ formatDate(file.modified_at) }}</span>
                        </p>
                      </div>
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="text-xs text-muted font-mono" title="SHA-256 checksum">
                        {{ file.checksum?.substring(0, 8) }}...
                      </span>
                      <CheckCircleIcon class="h-4 w-4 text-emerald-500" title="Checksum verified" />
                    </div>
                  </div>
                </div>
              </div>

              <!-- Database Tab -->
              <div v-else-if="activeTab === 'database'" class="space-y-4">
                <div v-if="!contents.database_schema_manifest?.length" class="text-center py-8 text-secondary">
                  <TableCellsIcon class="h-12 w-12 mx-auto mb-2 text-muted" />
                  <p>No database schema information available</p>
                </div>

                <div v-else>
                  <div
                    v-for="db in contents.database_schema_manifest"
                    :key="db.database"
                    class="mb-6"
                  >
                    <h4 class="text-lg font-semibold text-primary mb-3 flex items-center gap-2">
                      <TableCellsIcon class="h-5 w-5" />
                      {{ db.database }}
                      <span class="text-sm font-normal text-secondary">
                        ({{ db.tables?.length || 0 }} tables, {{ db.total_rows?.toLocaleString() || 0 }} rows)
                      </span>
                    </h4>

                    <div class="bg-surface-hover rounded-lg border border-gray-300 dark:border-gray-600 overflow-hidden">
                      <table class="w-full text-sm">
                        <thead class="bg-gray-100 dark:bg-gray-700">
                          <tr>
                            <th class="px-4 py-2 text-left font-medium text-secondary">Table</th>
                            <th class="px-4 py-2 text-right font-medium text-secondary">Rows</th>
                            <th class="px-4 py-2 text-right font-medium text-secondary">Columns</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr
                            v-for="table in db.tables"
                            :key="table.name"
                            class="border-t border-gray-200 dark:border-gray-600"
                          >
                            <td class="px-4 py-2 font-mono text-primary">{{ table.name }}</td>
                            <td class="px-4 py-2 text-right text-secondary">{{ table.row_count?.toLocaleString() }}</td>
                            <td class="px-4 py-2 text-right text-secondary">{{ table.columns?.length || '?' }}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Public Website Tab -->
              <div v-else-if="activeTab === 'publicwebsite'" class="space-y-4">
                <!-- Actions Bar -->
                <div class="flex items-center justify-between">
                  <div class="text-sm text-secondary">
                    <span v-if="selectedPublicWebsiteFiles.length > 0">
                      {{ selectedPublicWebsiteFiles.length }} file(s) selected
                    </span>
                    <span v-else>
                      {{ contents.public_website_file_count }} files in backup
                    </span>
                  </div>
                  <div class="flex items-center gap-2">
                    <button
                      @click="restoreSelectedPublicWebsiteFiles"
                      :disabled="selectedPublicWebsiteFiles.length === 0 || publicWebsiteRestoring"
                      class="btn-secondary text-sm"
                    >
                      <ArrowPathIcon class="h-4 w-4 mr-1" />
                      Restore Selected
                    </button>
                    <button
                      @click="restoreAllPublicWebsiteFiles"
                      :disabled="publicWebsiteRestoring"
                      class="btn-primary text-sm"
                    >
                      <ArrowPathIcon class="h-4 w-4 mr-1" />
                      Restore All
                    </button>
                  </div>
                </div>

                <!-- File List -->
                <div v-if="!contents.public_website_manifest?.length" class="text-center py-8 text-secondary">
                  <GlobeAltIcon class="h-12 w-12 mx-auto mb-2 text-muted" />
                  <p>No public website files in this backup</p>
                </div>

                <div v-else class="bg-surface-hover rounded-lg border border-gray-300 dark:border-gray-600 overflow-hidden">
                  <table class="w-full text-sm">
                    <thead class="bg-gray-100 dark:bg-gray-700">
                      <tr>
                        <th class="px-4 py-2 text-left w-10">
                          <input
                            type="checkbox"
                            v-model="selectAllPublicWebsite"
                            class="rounded border-gray-300 dark:border-gray-600"
                          />
                        </th>
                        <th class="px-4 py-2 text-left font-medium text-secondary">File Path</th>
                        <th class="px-4 py-2 text-right font-medium text-secondary">Size</th>
                        <th class="px-4 py-2 text-right font-medium text-secondary">Modified</th>
                        <th class="px-4 py-2 text-center font-medium text-secondary w-24">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="file in contents.public_website_manifest"
                        :key="file.path"
                        class="border-t border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                      >
                        <td class="px-4 py-2">
                          <input
                            type="checkbox"
                            :value="file.path"
                            v-model="selectedPublicWebsiteFiles"
                            class="rounded border-gray-300 dark:border-gray-600"
                          />
                        </td>
                        <td class="px-4 py-2">
                          <div class="flex items-center gap-2">
                            <div :class="['p-1 rounded', getFileTypeColor(file.mime_type)]">
                              <DocumentTextIcon class="h-4 w-4" />
                            </div>
                            <span class="font-mono text-primary text-xs">{{ file.path }}</span>
                          </div>
                        </td>
                        <td class="px-4 py-2 text-right text-secondary">{{ formatBytes(file.size) }}</td>
                        <td class="px-4 py-2 text-right text-secondary text-xs">
                          {{ file.modified_at ? formatDate(file.modified_at) : 'N/A' }}
                        </td>
                        <td class="px-4 py-2 text-center">
                          <div class="flex items-center justify-center gap-1">
                            <button
                              @click="downloadPublicWebsiteFile(file.path)"
                              class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
                              title="Download file"
                            >
                              <ArrowDownTrayIcon class="h-4 w-4 text-secondary" />
                            </button>
                            <button
                              @click="restorePublicWebsiteFiles([file.path], false)"
                              :disabled="publicWebsiteRestoring"
                              class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
                              title="Restore file"
                            >
                              <ArrowPathIcon class="h-4 w-4 text-secondary" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </template>

          <!-- No Contents Available -->
          <div v-else class="flex-1 flex items-center justify-center py-12">
            <div class="text-center">
              <XCircleIcon class="h-12 w-12 mx-auto mb-3 text-amber-500" />
              <p class="text-primary font-medium">No contents available</p>
              <p class="text-secondary text-sm mt-1">
                This backup may not have metadata stored.
              </p>
            </div>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-400 dark:border-gray-700">
            <button @click="close" class="btn-secondary">
              Close
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Workflow Restore Dialog -->
    <WorkflowRestoreDialog
      :open="restoreDialog.open"
      :backup="backup"
      :workflow="restoreDialog.workflow"
      @close="closeRestoreDialog"
      @restored="handleRestored"
    />
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
</style>
