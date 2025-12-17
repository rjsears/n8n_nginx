<script setup>
import { ref, computed, watch } from 'vue'
import { useBackupStore } from '@/stores/backups'
import { useNotificationStore } from '@/stores/notifications'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
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

// Tabs configuration
const tabs = [
  { id: 'workflows', label: 'Workflows', icon: CircleStackIcon },
  { id: 'config', label: 'Config Files', icon: Cog6ToothIcon },
  { id: 'database', label: 'Database', icon: TableCellsIcon },
]

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
              <div class="grid grid-cols-3 gap-4">
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
