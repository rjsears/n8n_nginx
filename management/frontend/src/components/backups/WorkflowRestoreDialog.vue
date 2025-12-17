<script setup>
import { ref, computed, watch } from 'vue'
import { useBackupStore } from '@/stores/backups'
import { useNotificationStore } from '@/stores/notifications'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import {
  XMarkIcon,
  ArrowPathIcon,
  ArrowDownTrayIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps({
  open: Boolean,
  backup: Object,
  workflow: Object,
})

const emit = defineEmits(['close', 'restored'])

const backupStore = useBackupStore()
const notificationStore = useNotificationStore()

const restoreMode = ref('n8n') // 'n8n' or 'download'
const renameFormat = ref('{name}_backup_{date}')
const customName = ref('')
const useCustomName = ref(false)
const loading = ref(false)
const result = ref(null)

// Reset state when dialog opens
watch(() => props.open, (isOpen) => {
  if (isOpen) {
    restoreMode.value = 'n8n'
    renameFormat.value = '{name}_backup_{date}'
    customName.value = props.workflow?.name ? `${props.workflow.name}_restored` : ''
    useCustomName.value = false
    loading.value = false
    result.value = null
  }
})

// Preview of the new workflow name
const previewName = computed(() => {
  if (useCustomName.value && customName.value) {
    return customName.value
  }
  if (!props.workflow || !props.backup) return ''

  const backupDate = new Date(props.backup.created_at).toISOString().slice(0, 10).replace(/-/g, '')
  return renameFormat.value
    .replace('{name}', props.workflow.name)
    .replace('{date}', backupDate)
    .replace('{id}', props.workflow.id.slice(0, 8))
})

async function handleRestore() {
  if (!props.backup || !props.workflow) return

  loading.value = true
  result.value = null

  try {
    if (restoreMode.value === 'n8n') {
      // Restore to n8n
      const format = useCustomName.value ? customName.value : renameFormat.value
      const response = await fetch(`/api/backups/${props.backup.id}/restore/workflow`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          workflow_id: props.workflow.id,
          rename_format: useCustomName.value ? customName.value : renameFormat.value,
        }),
      })

      const data = await response.json()

      if (data.status === 'success') {
        result.value = { success: true, data }
        notificationStore.success(`Workflow restored as "${data.new_name}"`)
        emit('restored', data)
      } else {
        result.value = { success: false, error: data.error || 'Restore failed' }
        notificationStore.error(data.error || 'Failed to restore workflow')
      }
    } else {
      // Download as JSON
      const response = await fetch(
        `/api/backups/${props.backup.id}/workflows/${props.workflow.id}/download`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
          },
        }
      )

      if (response.ok) {
        const data = await response.json()
        // Create download
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${props.workflow.name}.json`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)

        result.value = { success: true, downloaded: true }
        notificationStore.success('Workflow downloaded')
      } else {
        const errorData = await response.json()
        result.value = { success: false, error: errorData.detail || 'Download failed' }
        notificationStore.error('Failed to download workflow')
      }
    }
  } catch (err) {
    result.value = { success: false, error: err.message }
    notificationStore.error(`Error: ${err.message}`)
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
        <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-lg border border-gray-400 dark:border-gray-700">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-full bg-blue-100 dark:bg-blue-500/20">
                <ArrowPathIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h3 class="text-lg font-semibold text-primary">Restore Workflow</h3>
                <p class="text-sm text-secondary" v-if="workflow">
                  {{ workflow.name }}
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

          <!-- Content -->
          <div class="p-6 space-y-4">
            <!-- Success Result -->
            <div v-if="result?.success" class="p-4 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30">
              <div class="flex items-center gap-3">
                <CheckCircleIcon class="h-6 w-6 text-emerald-500" />
                <div>
                  <p class="font-medium text-emerald-800 dark:text-emerald-300">
                    {{ result.downloaded ? 'Download Complete!' : 'Restore Complete!' }}
                  </p>
                  <p v-if="result.data?.new_name" class="text-sm text-emerald-700 dark:text-emerald-400">
                    Workflow created as "{{ result.data.new_name }}"
                  </p>
                </div>
              </div>
            </div>

            <!-- Error Result -->
            <div v-else-if="result?.success === false" class="p-4 rounded-lg bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30">
              <div class="flex items-center gap-3">
                <ExclamationTriangleIcon class="h-6 w-6 text-red-500" />
                <div>
                  <p class="font-medium text-red-800 dark:text-red-300">Restore Failed</p>
                  <p class="text-sm text-red-700 dark:text-red-400">{{ result.error }}</p>
                </div>
              </div>
            </div>

            <!-- Restore Options -->
            <template v-if="!result">
              <!-- Mode Selection -->
              <div>
                <label class="block text-sm font-medium text-primary mb-2">Restore Method</label>
                <div class="grid grid-cols-2 gap-3">
                  <button
                    @click="restoreMode = 'n8n'"
                    :class="[
                      'p-3 rounded-lg border-2 text-left transition-colors',
                      restoreMode === 'n8n'
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-500/10'
                        : 'border-gray-300 dark:border-gray-600 hover:border-gray-400'
                    ]"
                  >
                    <div class="flex items-center gap-2 mb-1">
                      <ArrowPathIcon class="h-5 w-5 text-blue-500" />
                      <span class="font-medium text-primary">Restore to n8n</span>
                    </div>
                    <p class="text-xs text-secondary">Import directly into running n8n</p>
                  </button>

                  <button
                    @click="restoreMode = 'download'"
                    :class="[
                      'p-3 rounded-lg border-2 text-left transition-colors',
                      restoreMode === 'download'
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-500/10'
                        : 'border-gray-300 dark:border-gray-600 hover:border-gray-400'
                    ]"
                  >
                    <div class="flex items-center gap-2 mb-1">
                      <ArrowDownTrayIcon class="h-5 w-5 text-purple-500" />
                      <span class="font-medium text-primary">Download JSON</span>
                    </div>
                    <p class="text-xs text-secondary">Save workflow as JSON file</p>
                  </button>
                </div>
              </div>

              <!-- Naming Options (only for n8n restore) -->
              <div v-if="restoreMode === 'n8n'" class="space-y-3">
                <label class="block text-sm font-medium text-primary">New Workflow Name</label>

                <div class="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="useCustomName"
                    v-model="useCustomName"
                    class="rounded border-gray-300"
                  />
                  <label for="useCustomName" class="text-sm text-secondary">Use custom name</label>
                </div>

                <div v-if="useCustomName">
                  <input
                    v-model="customName"
                    type="text"
                    placeholder="Enter custom name"
                    class="input-field"
                  />
                </div>

                <div v-else>
                  <select v-model="renameFormat" class="select-field">
                    <option value="{name}_backup_{date}">{name}_backup_{date}</option>
                    <option value="{name}_restored">{name}_restored</option>
                    <option value="Restored_{name}"">Restored_{name}</option>
                    <option value="{name}_{id}">{name}_{id}</option>
                  </select>
                </div>

                <!-- Preview -->
                <div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-700">
                  <p class="text-xs text-secondary mb-1">Preview:</p>
                  <p class="font-mono text-sm text-primary">{{ previewName }}</p>
                </div>
              </div>

              <!-- Info -->
              <div class="p-3 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30">
                <p class="text-sm text-amber-800 dark:text-amber-300">
                  <strong>Note:</strong>
                  <span v-if="restoreMode === 'n8n'">
                    The workflow will be created as inactive. You'll need to configure any credentials and activate it manually.
                  </span>
                  <span v-else>
                    The JSON file can be imported into any n8n instance using the Import feature.
                  </span>
                </p>
              </div>
            </template>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-400 dark:border-gray-700">
            <button @click="close" class="btn-secondary">
              {{ result ? 'Close' : 'Cancel' }}
            </button>
            <button
              v-if="!result"
              @click="handleRestore"
              :disabled="loading"
              class="btn-primary flex items-center gap-2"
            >
              <template v-if="loading">
                <LoadingSpinner size="sm" />
                {{ restoreMode === 'n8n' ? 'Restoring...' : 'Downloading...' }}
              </template>
              <template v-else>
                <component :is="restoreMode === 'n8n' ? ArrowPathIcon : ArrowDownTrayIcon" class="h-4 w-4" />
                {{ restoreMode === 'n8n' ? 'Restore to n8n' : 'Download JSON' }}
              </template>
            </button>
          </div>
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
</style>
