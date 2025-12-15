<template>
  <div class="saved-messages">
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Saved Messages</h3>

    <!-- Messages List -->
    <div v-if="messages.length === 0" class="text-center py-12 text-gray-500 dark:text-gray-400">
      <BookmarkIcon class="w-12 h-12 mx-auto mb-3 opacity-50" />
      <p>No saved messages. Save messages from the composer to quickly re-send them.</p>
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="message in messages"
        :key="message.id"
        class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-1">
              <h4 class="font-medium text-gray-900 dark:text-white">{{ message.name }}</h4>
              <span class="px-2 py-0.5 rounded text-xs bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300">
                {{ message.topic }}
              </span>
              <span :class="[
                'px-2 py-0.5 rounded text-xs',
                getPriorityClass(message.priority)
              ]">
                {{ getPriorityLabel(message.priority) }}
              </span>
            </div>

            <p v-if="message.description" class="text-sm text-gray-600 dark:text-gray-400 mb-2">
              {{ message.description }}
            </p>

            <div v-if="message.title" class="text-sm font-medium text-gray-800 dark:text-gray-200 mb-1">
              {{ message.title }}
            </div>

            <p class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap line-clamp-3">
              {{ message.message }}
            </p>

            <div v-if="message.tags?.length" class="flex flex-wrap gap-1 mt-2">
              <span
                v-for="tag in message.tags"
                :key="tag"
                class="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-xs"
              >
                {{ tag }}
              </span>
            </div>

            <div class="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400 mt-2">
              <span>Used {{ message.use_count }} times</span>
              <span v-if="message.last_used">Last: {{ formatDate(message.last_used) }}</span>
              <span v-if="message.delay">Delay: {{ message.delay }}</span>
              <span v-if="message.email">Email: {{ message.email }}</span>
            </div>
          </div>

          <div class="flex flex-col gap-1 ml-4">
            <button
              @click="sendMessage(message)"
              :disabled="sendingId === message.id"
              class="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1"
            >
              <PaperAirplaneIcon class="w-4 h-4" />
              {{ sendingId === message.id ? 'Sending...' : 'Send' }}
            </button>
            <button
              @click="deleteMessage(message)"
              class="px-3 py-1.5 text-sm text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 rounded flex items-center gap-1"
            >
              <TrashIcon class="w-4 h-4" />
              Delete
            </button>
          </div>
        </div>

        <!-- Send Result -->
        <div v-if="results[message.id]" :class="[
          'mt-3 p-2 rounded text-sm',
          results[message.id].success
            ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
            : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'
        ]">
          {{ results[message.id].success ? 'Message sent!' : results[message.id].error }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  BookmarkIcon,
  PaperAirplaneIcon,
  TrashIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps({
  messages: { type: Array, default: () => [] },
})

const emit = defineEmits(['send', 'delete'])

// State
const sendingId = ref(null)
const results = ref({})

// Priority helpers
const priorityLabels = ['', 'Min', 'Low', 'Default', 'High', 'Urgent']
const priorityClasses = [
  '',
  'bg-gray-100 dark:bg-gray-600 text-gray-600 dark:text-gray-400',
  'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300',
  'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300',
  'bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-300',
  'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300',
]

function getPriorityLabel(priority) {
  return priorityLabels[priority] || 'Default'
}

function getPriorityClass(priority) {
  return priorityClasses[priority] || priorityClasses[3]
}

// Format date
function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString()
}

// Send message
async function sendMessage(message) {
  sendingId.value = message.id
  results.value[message.id] = null

  try {
    const result = await emit('send', message.id)
    results.value[message.id] = result

    // Clear result after 3 seconds
    setTimeout(() => {
      if (results.value[message.id] === result) {
        results.value[message.id] = null
      }
    }, 3000)
  } finally {
    sendingId.value = null
  }
}

// Delete message
async function deleteMessage(message) {
  if (!confirm(`Delete saved message "${message.name}"?`)) return

  const result = await emit('delete', message.id)
  if (!result?.success) {
    alert(result?.error || 'Failed to delete message')
  }
}
</script>
