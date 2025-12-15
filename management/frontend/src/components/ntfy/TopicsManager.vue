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

    <div v-else class="space-y-3">
      <div
        v-for="topic in topics"
        :key="topic.id"
        class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-3 mb-1">
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
            </div>
            <p v-if="topic.description" class="text-sm text-gray-600 dark:text-gray-400 mb-2">
              {{ topic.description }}
            </p>
            <div class="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
              <span>Access: {{ topic.access_level }}</span>
              <span>Messages: {{ topic.message_count }}</span>
              <span v-if="topic.last_message_at">
                Last: {{ formatDate(topic.last_message_at) }}
              </span>
            </div>
            <div v-if="topic.default_tags?.length" class="flex gap-1 mt-2">
              <span
                v-for="tag in topic.default_tags"
                :key="tag"
                class="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-xs"
              >
                {{ tag }}
              </span>
            </div>
          </div>
          <div class="flex gap-2">
            <button
              @click="openEditor(topic)"
              class="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
            >
              <PencilIcon class="w-4 h-4" />
            </button>
            <button
              @click="deleteTopic(topic)"
              class="p-2 text-red-500 hover:text-red-700 hover:bg-red-100 dark:hover:bg-red-900/30 rounded"
            >
              <TrashIcon class="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Topic Editor Modal -->
    <div v-if="showEditor" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-lg">
        <div class="flex justify-between items-center p-4 border-b border-gray-200 dark:border-gray-700">
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
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
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
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
            />
          </div>

          <!-- Access Level -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Access Level
            </label>
            <select
              v-model="editorForm.access_level"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
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
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
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
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
            />
          </div>

          <!-- Options -->
          <div class="space-y-2">
            <div class="flex items-center">
              <input
                id="requires_auth"
                v-model="editorForm.requires_auth"
                type="checkbox"
                class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
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
                class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label for="enabled" class="ml-2 text-sm text-gray-700 dark:text-gray-300">
                Topic enabled
              </label>
            </div>
          </div>
        </form>

        <div class="flex justify-end gap-2 p-4 border-t border-gray-200 dark:border-gray-700">
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
} from '@heroicons/vue/24/outline'

const props = defineProps({
  topics: { type: Array, default: () => [] },
  onCreate: { type: Function, required: true },
  onUpdate: { type: Function, required: true },
  onDelete: { type: Function, required: true },
  onSync: { type: Function, required: true },
})

// State
const showEditor = ref(false)
const editingTopic = ref(null)
const saving = ref(false)
const syncing = ref(false)
const syncMessage = ref('')
const syncSuccess = ref(false)

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
    if (editingTopic.value) {
      result = await props.onUpdate(editingTopic.value.id, data)
    } else {
      result = await props.onCreate(data)
    }

    if (result?.success) {
      closeEditor()
    } else {
      alert(result?.error || 'Failed to save topic')
    }
  } finally {
    saving.value = false
  }
}

// Delete topic
async function deleteTopic(topic) {
  if (!confirm(`Delete topic "${topic.name}"? This cannot be undone.`)) return

  const result = await props.onDelete(topic.id)
  if (!result?.success) {
    alert(result?.error || 'Failed to delete topic')
  }
}

// Sync topics to notification channels
async function syncChannels() {
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
