<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/ntfy/MessageHistory.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<template>
  <div class="message-history">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-white">Message History</h3>
      <button
        v-if="history.length > 0"
        @click="toggleAll"
        class="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
      >
        {{ allExpanded ? 'Collapse All' : 'Expand All' }}
      </button>
    </div>

    <!-- History List -->
    <div v-if="history.length === 0" class="text-center py-12 text-gray-500 dark:text-gray-400">
      <ClockIcon class="w-12 h-12 mx-auto mb-3 opacity-50" />
      <p>No message history yet. Messages you send will appear here.</p>
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="entry in history"
        :key="entry.id"
        class="bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-400 dark:border-gray-600 overflow-hidden"
      >
        <!-- Collapsed Header (Always Visible) -->
        <button
          @click="toggleEntry(entry.id)"
          class="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
        >
          <div class="flex items-center gap-2 flex-1 min-w-0">
            <ChevronRightIcon
              :class="[
                'w-4 h-4 flex-shrink-0 text-gray-400 transition-transform',
                expandedEntries[entry.id] ? 'rotate-90' : ''
              ]"
            />

            <!-- Status Badge -->
            <span :class="[
              'px-2 py-0.5 rounded text-xs font-medium flex-shrink-0',
              getStatusClass(entry.status)
            ]">
              {{ entry.status }}
            </span>

            <!-- Topic -->
            <span class="px-2 py-0.5 rounded text-xs bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300 flex-shrink-0">
              {{ entry.topic }}
            </span>

            <!-- Priority -->
            <span :class="[
              'px-2 py-0.5 rounded text-xs flex-shrink-0',
              getPriorityClass(entry.priority)
            ]">
              {{ getPriorityLabel(entry.priority) }}
            </span>

            <!-- Source -->
            <span class="px-2 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-600 text-gray-600 dark:text-gray-400 flex-shrink-0">
              {{ entry.source }}
            </span>

            <!-- Title Preview (truncated) -->
            <span class="text-sm text-gray-900 dark:text-white font-medium truncate ml-2">
              {{ entry.title || truncateMessage(entry.message) }}
            </span>
          </div>

          <!-- Timestamp -->
          <span class="text-xs text-gray-500 dark:text-gray-400 flex-shrink-0 ml-2">
            {{ formatDateTime(entry.created_at) }}
          </span>
        </button>

        <!-- Expanded Content -->
        <div v-if="expandedEntries[entry.id]" class="px-4 pb-4 pt-2 border-t border-gray-400 dark:border-gray-600">
          <!-- Title -->
          <div v-if="entry.title" class="font-medium text-gray-900 dark:text-white mb-2">
            {{ entry.title }}
          </div>

          <!-- Message -->
          <p class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap bg-white dark:bg-gray-800 rounded p-3 border border-gray-400 dark:border-gray-600">
            {{ entry.message }}
          </p>

          <!-- Tags -->
          <div v-if="entry.tags?.length" class="flex flex-wrap gap-1 mt-3">
            <span
              v-for="tag in entry.tags"
              :key="tag"
              class="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-xs"
            >
              {{ tag }}
            </span>
          </div>

          <!-- Error message -->
          <div v-if="entry.error_message" class="mt-3 p-2 bg-red-100 dark:bg-red-900/30 rounded text-sm text-red-700 dark:text-red-300">
            {{ entry.error_message }}
          </div>

          <!-- Metadata -->
          <div class="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400 mt-3">
            <span v-if="entry.sent_at">
              Sent: {{ formatDateTime(entry.sent_at) }}
            </span>
            <span v-if="entry.scheduled_for">
              Scheduled: {{ formatDateTime(entry.scheduled_for) }}
            </span>
            <span v-if="entry.response_id">
              ID: {{ entry.response_id }}
            </span>
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
import { ref, computed } from 'vue'
import { ClockIcon, ChevronRightIcon } from '@heroicons/vue/24/outline'

const props = defineProps({
  history: { type: Array, default: () => [] },
})

defineEmits(['load-more'])

// Expand/collapse state
const expandedEntries = ref({})

// Check if all entries are expanded
const allExpanded = computed(() => {
  if (props.history.length === 0) return false
  return props.history.every(entry => expandedEntries.value[entry.id])
})

// Toggle single entry
function toggleEntry(id) {
  expandedEntries.value[id] = !expandedEntries.value[id]
}

// Toggle all entries
function toggleAll() {
  const shouldExpand = !allExpanded.value
  props.history.forEach(entry => {
    expandedEntries.value[entry.id] = shouldExpand
  })
}

// Truncate message for preview
function truncateMessage(message, maxLength = 50) {
  if (!message) return ''
  if (message.length <= maxLength) return message
  return message.substring(0, maxLength) + '...'
}

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
