<template>
  <div class="message-history">
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Message History</h3>

    <!-- History List -->
    <div v-if="history.length === 0" class="text-center py-12 text-gray-500 dark:text-gray-400">
      <ClockIcon class="w-12 h-12 mx-auto mb-3 opacity-50" />
      <p>No message history yet. Messages you send will appear here.</p>
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="entry in history"
        :key="entry.id"
        class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-2">
              <!-- Status Badge -->
              <span :class="[
                'px-2 py-0.5 rounded text-xs font-medium',
                getStatusClass(entry.status)
              ]">
                {{ entry.status }}
              </span>

              <!-- Topic -->
              <span class="px-2 py-0.5 rounded text-xs bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300">
                {{ entry.topic }}
              </span>

              <!-- Priority -->
              <span :class="[
                'px-2 py-0.5 rounded text-xs',
                getPriorityClass(entry.priority)
              ]">
                {{ getPriorityLabel(entry.priority) }}
              </span>

              <!-- Source -->
              <span class="px-2 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-600 text-gray-600 dark:text-gray-400">
                {{ entry.source }}
              </span>
            </div>

            <!-- Title -->
            <div v-if="entry.title" class="font-medium text-gray-900 dark:text-white mb-1">
              {{ entry.title }}
            </div>

            <!-- Message -->
            <p class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
              {{ entry.message }}
            </p>

            <!-- Tags -->
            <div v-if="entry.tags?.length" class="flex flex-wrap gap-1 mt-2">
              <span
                v-for="tag in entry.tags"
                :key="tag"
                class="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-xs"
              >
                {{ tag }}
              </span>
            </div>

            <!-- Error message -->
            <div v-if="entry.error_message" class="mt-2 p-2 bg-red-100 dark:bg-red-900/30 rounded text-sm text-red-700 dark:text-red-300">
              {{ entry.error_message }}
            </div>

            <!-- Metadata -->
            <div class="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400 mt-2">
              <span>{{ formatDateTime(entry.created_at) }}</span>
              <span v-if="entry.sent_at && entry.sent_at !== entry.created_at">
                Sent: {{ formatDateTime(entry.sent_at) }}
              </span>
              <span v-if="entry.scheduled_for">
                Scheduled: {{ formatDateTime(entry.scheduled_for) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Load More Button -->
      <div class="text-center pt-4">
        <button
          @click="$emit('load-more')"
          class="px-4 py-2 text-sm text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg"
        >
          Load More
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ClockIcon } from '@heroicons/vue/24/outline'

const props = defineProps({
  history: { type: Array, default: () => [] },
})

defineEmits(['load-more'])

// Status classes
function getStatusClass(status) {
  switch (status) {
    case 'sent':
      return 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
    case 'scheduled':
      return 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300'
    case 'failed':
      return 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'
    default:
      return 'bg-gray-100 dark:bg-gray-600 text-gray-600 dark:text-gray-400'
  }
}

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

// Format date/time
function formatDateTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString()
}
</script>
