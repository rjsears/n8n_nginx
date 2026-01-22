<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/backup-ui/PublicWebsiteRestoreDialog.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useBackupStore } from '../../stores/backups'
import { useNotificationStore } from '../../stores/notifications'
import LoadingSpinner from '../common/LoadingSpinner.vue'
import {
  XMarkIcon,
  FolderIcon,
  DocumentIcon,
  MagnifyingGlassIcon,
  ArrowDownTrayIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  EyeIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps({
  open: Boolean,
  backup: Object,
})

const emit = defineEmits(['close', 'restored'])

const backupStore = useBackupStore()
const notificationStore = useNotificationStore()

// State
const loading = ref(false)
const mountStatus = ref(null)
const files = ref([])
const searchQuery = ref('')
const selectedFiles = ref([])
const checkResults = ref(null)
const restoreInProgress = ref(false)
const showPreview = ref(false)
const previewContent = ref(null)
const previewPath = ref('')

// Pagination
const currentPage = ref(1)
const pageSize = ref(50)
const totalFiles = ref(0)

// Mount files when dialog opens
watch(() => props.open, async (isOpen) => {
  if (isOpen && props.backup) {
    await mountFiles()
  } else {
    // Cleanup when closing
    selectedFiles.value = []
    checkResults.value = null
    searchQuery.value = ''
    currentPage.value = 1
    showPreview.value = false
    previewContent.value = null
  }
})

// Cleanup on unmount
onUnmounted(async () => {
  if (mountStatus.value?.mounted) {
    await backupStore.unmountPublicWebsiteFiles()
  }
})

async function mountFiles() {
  loading.value = true
  try {
    const result = await backupStore.mountPublicWebsiteFiles(props.backup.id)
    mountStatus.value = result
    if (result.status === 'success' || result.status === 'already_mounted') {
      await loadFiles()
    }
  } catch (err) {
    notificationStore.error('Failed to mount public website files')
    emit('close')
  } finally {
    loading.value = false
  }
}

async function loadFiles() {
  loading.value = true
  try {
    const result = await backupStore.listPublicWebsiteFiles(props.backup.id, {
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
      search: searchQuery.value || undefined,
    })
    files.value = result.files || []
    totalFiles.value = result.total
  } catch (err) {
    notificationStore.error('Failed to load files')
  } finally {
    loading.value = false
  }
}

// Computed
const totalPages = computed(() => Math.ceil(totalFiles.value / pageSize.value) || 1)

const hasSelectedFiles = computed(() => selectedFiles.value.length > 0)

const selectAllChecked = computed(() => {
  return files.value.length > 0 && files.value.every(f => selectedFiles.value.includes(f.path))
})

// Methods
function toggleSelectAll() {
  if (selectAllChecked.value) {
    // Deselect all visible files
    files.value.forEach(f => {
      const idx = selectedFiles.value.indexOf(f.path)
      if (idx > -1) selectedFiles.value.splice(idx, 1)
    })
  } else {
    // Select all visible files
    files.value.forEach(f => {
      if (!selectedFiles.value.includes(f.path)) {
        selectedFiles.value.push(f.path)
      }
    })
  }
}

function toggleFileSelection(file) {
  const idx = selectedFiles.value.indexOf(file.path)
  if (idx > -1) {
    selectedFiles.value.splice(idx, 1)
  } else {
    selectedFiles.value.push(file.path)
  }
}

async function searchFiles() {
  currentPage.value = 1
  await loadFiles()
}

async function goToPage(page) {
  currentPage.value = page
  await loadFiles()
}

async function previewFile(file) {
  try {
    const result = await backupStore.previewPublicWebsiteFile(props.backup.id, file.path)
    previewContent.value = result
    previewPath.value = file.path
    showPreview.value = true
  } catch (err) {
    notificationStore.error('Failed to preview file')
  }
}

function downloadFile(file) {
  const url = backupStore.getPublicWebsiteFileDownloadUrl(props.backup.id, file.path)
  window.open(url, '_blank')
}

async function checkRestore() {
  loading.value = true
  try {
    const result = await backupStore.checkPublicWebsiteRestore(props.backup.id)
    checkResults.value = result
  } catch (err) {
    notificationStore.error('Failed to check restore')
  } finally {
    loading.value = false
  }
}

async function performRestore() {
  if (!confirm('This will restore public website files to the live volume. Files with the same name will be overwritten. Continue?')) {
    return
  }

  restoreInProgress.value = true
  try {
    const filesToRestore = hasSelectedFiles.value ? selectedFiles.value : null
    const result = await backupStore.restorePublicWebsiteFiles(props.backup.id, filesToRestore)

    if (result.status === 'success') {
      notificationStore.success(`Restored ${result.restored_count} files successfully`)
      emit('restored', result)
    } else if (result.status === 'partial') {
      notificationStore.warning(`Restored ${result.restored_count}/${result.total_files} files. Some files failed.`)
    } else {
      notificationStore.error('Restore failed: ' + (result.error || 'Unknown error'))
    }
  } catch (err) {
    notificationStore.error('Failed to restore files')
  } finally {
    restoreInProgress.value = false
  }
}

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
        <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-5xl max-h-[85vh] flex flex-col border border-gray-400 dark:border-gray-700">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-full bg-green-100 dark:bg-green-500/20">
                <FolderIcon class="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <h2 class="text-lg font-semibold text-gray-900 dark:text-white">
                  Public Website Restore
                </h2>
                <p class="text-sm text-gray-500 dark:text-gray-400">
                  Restore public website files from backup
                </p>
              </div>
            </div>
            <button
              @click="close"
              class="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              <XMarkIcon class="w-5 h-5 text-gray-500 dark:text-gray-400" />
            </button>
          </div>

          <!-- Content -->
          <div class="flex-1 overflow-hidden flex flex-col p-6 gap-4">
            <!-- Loading -->
            <div v-if="loading && !files.length" class="flex items-center justify-center py-12">
              <LoadingSpinner />
              <span class="ml-3 text-gray-600 dark:text-gray-300">Loading files...</span>
            </div>

            <!-- Files List -->
            <template v-else>
              <!-- Search and Actions -->
              <div class="flex items-center justify-between gap-4">
                <div class="relative flex-1 max-w-md">
                  <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    v-model="searchQuery"
                    type="text"
                    placeholder="Search files..."
                    class="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
                    @keyup.enter="searchFiles"
                  />
                </div>
                <div class="flex items-center gap-2">
                  <button
                    @click="checkRestore"
                    :disabled="loading"
                    class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                  >
                    <ExclamationTriangleIcon class="w-4 h-4" />
                    Preview Changes
                  </button>
                  <button
                    @click="performRestore"
                    :disabled="restoreInProgress"
                    class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
                  >
                    <ArrowPathIcon v-if="restoreInProgress" class="w-4 h-4 animate-spin" />
                    <ArrowDownTrayIcon v-else class="w-4 h-4" />
                    {{ hasSelectedFiles ? `Restore Selected (${selectedFiles.length})` : 'Restore All' }}
                  </button>
                </div>
              </div>

              <!-- Check Results Preview -->
              <div v-if="checkResults" class="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
                <h4 class="font-medium text-yellow-800 dark:text-yellow-200 mb-2">Restore Preview</h4>
                <div class="grid grid-cols-3 gap-4 text-sm">
                  <div class="flex items-center gap-2">
                    <CheckCircleIcon class="w-5 h-5 text-green-500" />
                    <span class="text-gray-700 dark:text-gray-300">{{ checkResults.summary?.new_files || 0 }} new files</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <ExclamationTriangleIcon class="w-5 h-5 text-yellow-500" />
                    <span class="text-gray-700 dark:text-gray-300">{{ checkResults.summary?.overwrite_files || 0 }} will be overwritten</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <DocumentIcon class="w-5 h-5 text-gray-500" />
                    <span class="text-gray-700 dark:text-gray-300">{{ checkResults.summary?.unchanged_files || 0 }} unchanged</span>
                  </div>
                </div>
              </div>

              <!-- Files Table -->
              <div class="flex-1 overflow-auto border border-gray-200 dark:border-gray-700 rounded-lg">
                <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead class="bg-gray-50 dark:bg-gray-900 sticky top-0">
                    <tr>
                      <th class="w-12 px-4 py-3">
                        <input
                          type="checkbox"
                          :checked="selectAllChecked"
                          @change="toggleSelectAll"
                          class="rounded border-gray-300 dark:border-gray-600"
                        />
                      </th>
                      <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        File
                      </th>
                      <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Size
                      </th>
                      <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Modified
                      </th>
                      <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                    <tr
                      v-for="file in files"
                      :key="file.path"
                      class="hover:bg-gray-50 dark:hover:bg-gray-700/50"
                    >
                      <td class="px-4 py-3">
                        <input
                          type="checkbox"
                          :checked="selectedFiles.includes(file.path)"
                          @change="toggleFileSelection(file)"
                          class="rounded border-gray-300 dark:border-gray-600"
                        />
                      </td>
                      <td class="px-4 py-3">
                        <div class="flex items-center gap-2">
                          <DocumentIcon class="w-5 h-5 text-gray-400 flex-shrink-0" />
                          <span class="text-sm text-gray-900 dark:text-white truncate" :title="file.path">
                            {{ file.path }}
                          </span>
                        </div>
                      </td>
                      <td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                        {{ formatBytes(file.size) }}
                      </td>
                      <td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                        {{ formatDate(file.modified_at) }}
                      </td>
                      <td class="px-4 py-3 text-right">
                        <div class="flex items-center justify-end gap-2">
                          <button
                            @click="previewFile(file)"
                            class="p-1 text-gray-400 hover:text-blue-600 transition-colors"
                            title="Preview"
                          >
                            <EyeIcon class="w-5 h-5" />
                          </button>
                          <button
                            @click="downloadFile(file)"
                            class="p-1 text-gray-400 hover:text-green-600 transition-colors"
                            title="Download"
                          >
                            <ArrowDownTrayIcon class="w-5 h-5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                    <tr v-if="files.length === 0">
                      <td colspan="5" class="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                        No files found
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- Pagination -->
              <div v-if="totalPages > 1" class="flex items-center justify-between">
                <span class="text-sm text-gray-500 dark:text-gray-400">
                  Showing {{ (currentPage - 1) * pageSize + 1 }} - {{ Math.min(currentPage * pageSize, totalFiles) }} of {{ totalFiles }} files
                </span>
                <div class="flex items-center gap-2">
                  <button
                    @click="goToPage(currentPage - 1)"
                    :disabled="currentPage === 1"
                    class="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <span class="text-sm text-gray-600 dark:text-gray-300">
                    Page {{ currentPage }} of {{ totalPages }}
                  </span>
                  <button
                    @click="goToPage(currentPage + 1)"
                    :disabled="currentPage === totalPages"
                    class="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- Preview Modal -->
        <Transition name="modal">
          <div
            v-if="showPreview && previewContent"
            class="fixed inset-0 z-[110] flex items-center justify-center p-4"
          >
            <div class="absolute inset-0 bg-black/50" @click="showPreview = false" />
            <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] flex flex-col border border-gray-400 dark:border-gray-700">
              <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                <h3 class="font-medium text-gray-900 dark:text-white truncate">{{ previewPath }}</h3>
                <button @click="showPreview = false" class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                  <XMarkIcon class="w-5 h-5 text-gray-500" />
                </button>
              </div>
              <div class="flex-1 overflow-auto p-4">
                <pre v-if="previewContent.is_text" class="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono">{{ previewContent.content }}</pre>
                <div v-else class="text-center text-gray-500 dark:text-gray-400">
                  <p>Binary file ({{ previewContent.mime_type }})</p>
                  <p class="text-sm mt-2">Size: {{ formatBytes(previewContent.size) }}</p>
                </div>
              </div>
            </div>
          </div>
        </Transition>
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
</style>
