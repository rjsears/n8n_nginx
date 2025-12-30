<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/ntfy/TopicsManager.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<template>
  <div class="topics-manager">
    <div class="flex justify-between items-center mb-4">
      <div>
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white">Topics</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          Topics are automatically available as notification channels
        </p>
      </div>
      <div class="flex gap-2">
        <button
          v-if="topics.length > 0"
          @click="syncChannels"
          :disabled="syncing"
          class="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 flex items-center gap-2 disabled:opacity-50"
          title="Sync existing topics to notification channels"
        >
          <ArrowPathIcon :class="['w-5 h-5', syncing ? 'animate-spin' : '']" />
          {{ syncing ? 'Syncing...' : 'Sync Channels' }}
        </button>
        <button
          @click="openEditor(null)"
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
        >
          <PlusIcon class="w-5 h-5" />
          New Topic
        </button>
      </div>
    </div>

    <!-- Sync Result Message -->
    <div v-if="syncMessage" :class="[
      'mb-4 p-3 rounded-lg text-sm',
      syncSuccess
        ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
        : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'
    ]">
      {{ syncMessage }}
    </div>

    <!-- Topics List -->
    <div v-if="topics.length === 0" class="text-center py-12 text-gray-500 dark:text-gray-400">
      <HashtagIcon class="w-12 h-12 mx-auto mb-3 opacity-50" />
      <p>No topics configured. Create topics to organize your notifications.</p>
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="topic in topics"
        :key="topic.id"
        class="bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-400 dark:border-gray-600 overflow-hidden"
      >
        <!-- Collapsed Header -->
        <div class="flex items-center">
          <button
            @click="toggleTopic(topic.id)"
            class="flex-1 px-4 py-3 flex items-center gap-2 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
          >
            <ChevronRightIcon
              :class="[
                'w-4 h-4 flex-shrink-0 text-gray-400 transition-transform',
                expandedTopics[topic.id] ? 'rotate-90' : ''
              ]"
            />
            <h4 class="font-medium text-gray-900 dark:text-white">{{ topic.name }}</h4>
            <span :class="[
              'px-2 py-0.5 rounded text-xs',
              topic.enabled
                ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
                : 'bg-gray-100 dark:bg-gray-600 text-gray-600 dark:text-gray-400'
            ]">
              {{ topic.enabled ? 'Active' : 'Disabled' }}
            </span>
            <span v-if="topic.requires_auth" class="px-2 py-0.5 rounded text-xs bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">
              Auth Required
            </span>
            <span class="text-xs text-gray-500 dark:text-gray-400 ml-auto">
              {{ topic.message_count }} messages
            </span>
          </button>
          <div class="flex gap-1 pr-2">
            <button
              @click.stop="openEditor(topic)"
              class="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
            >
              <PencilIcon class="w-4 h-4" />
            </button>
            <button
              @click.stop="deleteTopic(topic)"
              class="p-2 text-red-500 hover:text-red-700 hover:bg-red-100 dark:hover:bg-red-900/30 rounded"
            >
              <TrashIcon class="w-4 h-4" />
            </button>
          </div>
        </div>

        <!-- Expanded Content -->
        <div v-if="expandedTopics[topic.id]" class="px-4 pb-4 pt-2 border-t border-gray-400 dark:border-gray-600">
          <p v-if="topic.description" class="text-sm text-gray-600 dark:text-gray-400 mb-3">
            {{ topic.description }}
          </p>
          <div class="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span class="text-gray-500 dark:text-gray-400">Access Level:</span>
              <span class="ml-2 text-gray-900 dark:text-white">{{ topic.access_level }}</span>
            </div>
            <div>
              <span class="text-gray-500 dark:text-gray-400">Default Priority:</span>
              <span class="ml-2 text-gray-900 dark:text-white">{{ getPriorityLabel(topic.default_priority) }}</span>
            </div>
            <div>
              <span class="text-gray-500 dark:text-gray-400">Messages Sent:</span>
              <span class="ml-2 text-gray-900 dark:text-white">{{ topic.message_count }}</span>
            </div>
            <div v-if="topic.last_message_at">
              <span class="text-gray-500 dark:text-gray-400">Last Message:</span>
              <span class="ml-2 text-gray-900 dark:text-white">{{ formatDate(topic.last_message_at) }}</span>
            </div>
          </div>
          <div v-if="topic.default_tags?.length" class="flex flex-wrap gap-1 mt-3">
            <span class="text-xs text-gray-500 dark:text-gray-400 mr-1">Default Tags:</span>
            <span
              v-for="tag in topic.default_tags"
              :key="tag"
              class="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-xs"
            >
              {{ tag }}
            </span>
          </div>
          <div class="mt-3 pt-3 border-t border-gray-400 dark:border-gray-600 text-xs text-gray-500 dark:text-gray-400">
            Notification Channel: <code class="bg-gray-200 dark:bg-gray-600 px-1 rounded">ntfy_{{ topic.name.toLowerCase().replace(/[^a-z0-9]+/g, '_') }}</code>
          </div>
        </div>
      </div>
    </div>

    <!-- Topic Editor Modal -->
    <div v-if="showEditor" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-lg">
        <div class="flex justify-between items-center p-4 border-b border-gray-400 dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
            {{ editingTopic ? 'Edit Topic' : 'Create Topic' }}
          </h3>
          <button @click="closeEditor" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <XMarkIcon class="w-6 h-6" />
          </button>
        </div>

        <form @submit.prevent="saveTopic" class="p-4 space-y-4">
          <!-- Name -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Topic Name <span class="text-red-500">*</span>
            </label>
            <input
              v-model="editorForm.name"
              type="text"
              placeholder="my-topic"
              class="w-full rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
              :disabled="editingTopic"
              required
            />
            <p v-if="!editingTopic" class="mt-1 text-xs text-gray-500">
              Topic names cannot be changed after creation
            </p>
          </div>

          <!-- Description -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Description
            </label>
            <input
              v-model="editorForm.description"
              type="text"
              placeholder="What this topic is for..."
              class="w-full rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
            />
          </div>

          <!-- Access Level -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Access Level
            </label>
            <select
              v-model="editorForm.access_level"
              class="w-full rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
            >
              <option value="read-write">Read & Write</option>
              <option value="read-only">Read Only</option>
              <option value="write-only">Write Only</option>
            </select>
          </div>

          <!-- Default Priority -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Default Priority
            </label>
            <select
              v-model="editorForm.default_priority"
              class="w-full rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
            >
              <option :value="1">Min</option>
              <option :value="2">Low</option>
              <option :value="3">Default</option>
              <option :value="4">High</option>
              <option :value="5">Urgent</option>
            </select>
          </div>

          <!-- Default Tags -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Default Tags
            </label>
            <input
              v-model="tagsInput"
              type="text"
              placeholder="server, alerts (comma-separated)"
              class="w-full rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
            />
          </div>

          <!-- Options -->
          <div class="space-y-2">
            <div class="flex items-center">
              <input
                id="requires_auth"
                v-model="editorForm.requires_auth"
                type="checkbox"
                class="rounded border-gray-400 text-blue-600 focus:ring-blue-500"
              />
              <label for="requires_auth" class="ml-2 text-sm text-gray-700 dark:text-gray-300">
                Require authentication
              </label>
            </div>
            <div v-if="editingTopic" class="flex items-center">
              <input
                id="enabled"
                v-model="editorForm.enabled"
                type="checkbox"
                class="rounded border-gray-400 text-blue-600 focus:ring-blue-500"
              />
              <label for="enabled" class="ml-2 text-sm text-gray-700 dark:text-gray-300">
                Topic enabled
              </label>
            </div>
          </div>
        </form>

        <div class="flex justify-end gap-2 p-4 border-t border-gray-400 dark:border-gray-700">
          <button
            @click="closeEditor"
            type="button"
            class="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            Cancel
          </button>
          <button
            @click="saveTopic"
            :disabled="saving"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {{ saving ? 'Saving...' : (editingTopic ? 'Update' : 'Create') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="deleteDialog.open"
      title="Delete Topic"
      :message="`Are you sure you want to delete the topic '${deleteDialog.topic?.name}'? This cannot be undone.`"
      confirm-text="Delete"
      :loading="deleteDialog.loading"
      :error="deleteDialog.error"
      variant="danger"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />

    <!-- Topic Created Success Dialog -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="successDialog.open"
          class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          @click.self="successDialog.open = false"
        >
          <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-lg w-full p-6">
            <!-- Header -->
            <div class="flex items-center gap-3 mb-4">
              <div class="p-2 rounded-lg bg-green-100 dark:bg-green-500/20">
                <CheckCircleIcon class="h-6 w-6 text-green-500" />
              </div>
              <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
                NTFY Topic Created!
              </h3>
            </div>

            <!-- Content -->
            <div class="space-y-4">
              <p class="text-sm text-gray-600 dark:text-gray-300">
                Your NTFY topic has been created successfully. Here's how to use it:
              </p>

              <!-- Topic Info -->
              <div class="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
                <div class="flex items-center gap-2 mb-2">
                  <MegaphoneIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
                  <span class="font-semibold text-amber-800 dark:text-amber-300">Subscribe to Topic</span>
                </div>
                <p class="text-sm text-amber-700 dark:text-amber-400 mb-2">
                  In your NTFY app or browser, subscribe to:
                </p>
                <code class="block px-3 py-2 bg-amber-100 dark:bg-amber-900/40 rounded text-amber-900 dark:text-amber-200 font-mono text-sm">
                  {{ successDialog.topic?.name }}
                </code>
              </div>

              <!-- Slug Info -->
              <div class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                <div class="flex items-center gap-2 mb-2">
                  <LinkIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  <span class="font-semibold text-blue-800 dark:text-blue-300">Send via n8n Webhook</span>
                </div>
                <p class="text-sm text-blue-700 dark:text-blue-400 mb-2">
                  To send notifications from n8n workflows, use this channel slug:
                </p>
                <code class="block px-3 py-2 bg-blue-100 dark:bg-blue-900/40 rounded text-blue-900 dark:text-blue-200 font-mono text-sm">
                  channel:ntfy_{{ successDialog.topic?.name?.toLowerCase().replace(/[^a-z0-9]+/g, '_') }}
                </code>
              </div>

              <!-- Note -->
              <p class="text-xs text-gray-500 dark:text-gray-400">
                <strong>Note:</strong> The topic is what you subscribe to in the NTFY app. The channel slug is used in n8n webhook payloads to route messages to this topic.
              </p>
            </div>

            <!-- Footer -->
            <div class="mt-6 flex justify-end">
              <button
                @click="successDialog.open = false"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
              >
                Got it!
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  PlusIcon,
  HashtagIcon,
  PencilIcon,
  TrashIcon,
  XMarkIcon,
  ArrowPathIcon,
  ChevronRightIcon,
  CheckCircleIcon,
  LinkIcon,
  MegaphoneIcon,
} from '@heroicons/vue/24/outline'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const props = defineProps({
  topics: { type: Array, default: () => [] },
  onCreate: { type: Function, required: true },
  onUpdate: { type: Function, required: true },
  onDelete: { type: Function, required: true },
  onSync: { type: Function, default: null },
})

// State
const showEditor = ref(false)
const editingTopic = ref(null)
const saving = ref(false)
const syncing = ref(false)
const syncMessage = ref('')
const syncSuccess = ref(false)
const expandedTopics = ref({})
const deleteDialog = ref({ open: false, topic: null, loading: false, error: null })
const successDialog = ref({ open: false, topic: null })

// Toggle topic expand/collapse
function toggleTopic(id) {
  expandedTopics.value[id] = !expandedTopics.value[id]
}

// Priority label helper
const priorityLabels = ['', 'Min', 'Low', 'Default', 'High', 'Urgent']
function getPriorityLabel(priority) {
  return priorityLabels[priority] || 'Default'
}

const editorForm = ref({
  name: '',
  description: '',
  access_level: 'read-write',
  requires_auth: false,
  default_priority: 3,
  enabled: true,
})

const tagsInput = ref('')

// Format date
function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString()
}

// Open editor
function openEditor(topic) {
  editingTopic.value = topic

  if (topic) {
    editorForm.value = {
      name: topic.name,
      description: topic.description || '',
      access_level: topic.access_level,
      requires_auth: topic.requires_auth,
      default_priority: topic.default_priority,
      enabled: topic.enabled,
    }
    tagsInput.value = (topic.default_tags || []).join(', ')
  } else {
    editorForm.value = {
      name: '',
      description: '',
      access_level: 'read-write',
      requires_auth: false,
      default_priority: 3,
      enabled: true,
    }
    tagsInput.value = ''
  }

  showEditor.value = true
}

// Close editor
function closeEditor() {
  showEditor.value = false
  editingTopic.value = null
}

// Save topic
async function saveTopic() {
  saving.value = true

  try {
    const data = {
      ...editorForm.value,
      default_tags: tagsInput.value.split(',').map(t => t.trim()).filter(t => t),
    }

    let result
    const isCreating = !editingTopic.value
    if (editingTopic.value) {
      result = await props.onUpdate(editingTopic.value.id, data)
    } else {
      result = await props.onCreate(data)
    }

    if (result?.success) {
      closeEditor()
      // Show success dialog for new topics
      if (isCreating && result.topic) {
        successDialog.value = { open: true, topic: result.topic }
      }
    } else {
      alert(result?.error || 'Failed to save topic')
    }
  } finally {
    saving.value = false
  }
}

// Delete topic - open confirmation dialog
function deleteTopic(topic) {
  deleteDialog.value = { open: true, topic, loading: false, error: null }
}

// Confirm delete
async function confirmDelete() {
  if (!deleteDialog.value.topic) return

  deleteDialog.value.loading = true
  deleteDialog.value.error = null

  try {
    const result = await props.onDelete(deleteDialog.value.topic.id)
    if (result?.success) {
      deleteDialog.value = { open: false, topic: null, loading: false, error: null }
    } else {
      deleteDialog.value.error = result?.error || 'Failed to delete topic'
      deleteDialog.value.loading = false
    }
  } catch (error) {
    deleteDialog.value.error = error.message || 'Failed to delete topic'
    deleteDialog.value.loading = false
  }
}

// Cancel delete
function cancelDelete() {
  deleteDialog.value = { open: false, topic: null, loading: false, error: null }
}

// Sync topics to notification channels
async function syncChannels() {
  if (typeof props.onSync !== 'function') {
    syncSuccess.value = false
    syncMessage.value = 'Sync function not available'
    return
  }

  syncing.value = true
  syncMessage.value = ''

  try {
    const result = await props.onSync()
    if (result?.success) {
      syncSuccess.value = true
      syncMessage.value = result.message || `Synced ${result.synced} topics to notification channels`
    } else {
      syncSuccess.value = false
      syncMessage.value = result?.error || 'Failed to sync topics'
    }

    // Clear message after 5 seconds
    setTimeout(() => {
      syncMessage.value = ''
    }, 5000)
  } catch (error) {
    syncSuccess.value = false
    syncMessage.value = error.message || 'Failed to sync topics'
  } finally {
    syncing.value = false
  }
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
