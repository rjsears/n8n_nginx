<script setup>
import { ref, watch, computed } from 'vue'
import { XMarkIcon, HashtagIcon } from '@heroicons/vue/24/outline'

const props = defineProps({
  open: Boolean,
  group: {
    type: Object,
    default: null,
  },
  channels: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['save', 'cancel', 'update:open'])

const loading = ref(false)

// Form data
const form = ref({
  name: '',
  slug: '',
  description: '',
  enabled: true,
  channel_ids: [],
})

// Generate slug from name
function generateSlug(name) {
  return name.toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/_+/g, '_')
}

// Auto-generate slug when name changes (only for new groups)
function onNameChange() {
  if (!props.group && !form.value.slug) {
    form.value.slug = generateSlug(form.value.name)
  }
}

// Reset form when dialog opens/closes
watch(() => props.open, (isOpen) => {
  if (isOpen) {
    loading.value = false

    if (props.group) {
      // Editing existing group
      form.value = {
        name: props.group.name || '',
        slug: props.group.slug || '',
        description: props.group.description || '',
        enabled: props.group.enabled ?? true,
        channel_ids: props.group.channels?.map(c => c.id) || [],
      }
    } else {
      // New group
      form.value = {
        name: '',
        slug: '',
        description: '',
        enabled: true,
        channel_ids: [],
      }
    }
  }
})

const isEditing = computed(() => !!props.group)

const dialogTitle = computed(() => isEditing.value ? 'Edit Notification Group' : 'Add Notification Group')

const isValid = computed(() => {
  return form.value.name.trim() && form.value.channel_ids.length > 0
})

// Get available channels (webhook enabled only for webhook routing)
const availableChannels = computed(() => {
  return props.channels || []
})

function toggleChannel(channelId) {
  const index = form.value.channel_ids.indexOf(channelId)
  if (index === -1) {
    form.value.channel_ids.push(channelId)
  } else {
    form.value.channel_ids.splice(index, 1)
  }
}

function isChannelSelected(channelId) {
  return form.value.channel_ids.includes(channelId)
}

function close() {
  emit('update:open', false)
  emit('cancel')
}

function save() {
  if (!isValid.value) return

  loading.value = true
  emit('save', {
    ...form.value,
    id: props.group?.id,
  })
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
        <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full border border-gray-400 dark:border-gray-700 max-h-[90vh] overflow-hidden flex flex-col">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-full bg-indigo-100 dark:bg-indigo-500/20">
                <HashtagIcon class="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
              </div>
              <h3 class="text-lg font-semibold text-gray-900 dark:text-white">{{ dialogTitle }}</h3>
            </div>
            <button
              @click="close"
              class="p-1 rounded-lg text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              <XMarkIcon class="h-5 w-5" />
            </button>
          </div>

          <!-- Content -->
          <div class="px-6 py-4 overflow-y-auto flex-1 bg-white dark:bg-gray-800">
            <form @submit.prevent="save" class="space-y-4">
              <!-- Name -->
              <div>
                <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                  Group Name *
                </label>
                <input
                  v-model="form.name"
                  @input="onNameChange"
                  type="text"
                  class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="e.g., DevOps Team"
                  required
                />
              </div>

              <!-- Slug -->
              <div>
                <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                  Slug (for targeting)
                </label>
                <div class="flex items-center gap-2">
                  <span class="text-sm text-gray-500 dark:text-gray-400 font-mono">group:</span>
                  <input
                    v-model="form.slug"
                    type="text"
                    class="flex-1 px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    placeholder="dev_ops"
                    pattern="^[a-z0-9_]+$"
                  />
                </div>
                <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Used in n8n webhooks to target this group. Lowercase letters, numbers, and underscores only.
                </p>
              </div>

              <!-- Description -->
              <div>
                <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                  Description (optional)
                </label>
                <textarea
                  v-model="form.description"
                  rows="2"
                  class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="e.g., Notifications for the DevOps team"
                />
              </div>

              <!-- Channels Selection -->
              <div>
                <label class="block text-sm font-medium text-gray-900 dark:text-white mb-2">
                  Channels * <span class="text-gray-500 dark:text-gray-400 font-normal">({{ form.channel_ids.length }} selected)</span>
                </label>

                <div v-if="availableChannels.length === 0" class="text-sm text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 rounded-lg p-4">
                  No channels available. Create channels first in the Channels tab.
                </div>

                <div v-else class="space-y-2 max-h-48 overflow-y-auto border border-gray-400 dark:border-gray-700 rounded-lg p-2">
                  <label
                    v-for="channel in availableChannels"
                    :key="channel.id"
                    class="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer transition-colors"
                    :class="{ 'bg-indigo-50 dark:bg-indigo-900/20': isChannelSelected(channel.id) }"
                  >
                    <input
                      type="checkbox"
                      :checked="isChannelSelected(channel.id)"
                      @change="toggleChannel(channel.id)"
                      class="w-4 h-4 text-indigo-600 bg-gray-100 border-gray-400 rounded focus:ring-indigo-500 dark:focus:ring-indigo-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"
                    />
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2">
                        <p class="text-sm font-medium text-gray-900 dark:text-white truncate">{{ channel.name }}</p>
                        <span
                          v-if="channel.webhook_enabled"
                          class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300"
                        >
                          Webhook
                        </span>
                      </div>
                      <p class="text-xs text-gray-500 dark:text-gray-400 truncate">
                        {{ channel.service_type }} • channel:{{ channel.slug }}
                      </p>
                    </div>
                  </label>
                </div>
                <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Select at least one channel to include in this group.
                </p>
              </div>

              <!-- Enabled Toggle -->
              <div class="flex items-center justify-between border-t border-gray-400 dark:border-gray-700 pt-4">
                <div>
                  <label class="text-sm font-medium text-gray-900 dark:text-white">Enabled</label>
                  <p class="text-xs text-gray-500 dark:text-gray-400">Group can be targeted for notifications</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    v-model="form.enabled"
                    class="sr-only peer"
                  />
                  <div
                    class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-400 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-indigo-500"
                  ></div>
                </label>
              </div>

              <!-- Target Info -->
              <div v-if="form.slug" class="bg-indigo-50 dark:bg-indigo-900/20 rounded-lg p-3 text-xs">
                <p class="text-indigo-700 dark:text-indigo-300">
                  <strong>Target this group:</strong> Use <code class="bg-indigo-100 dark:bg-indigo-800 px-1.5 py-0.5 rounded font-mono">"group:{{ form.slug }}"</code> in your webhook targets.
                </p>
              </div>
            </form>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-400 dark:border-gray-700 bg-white dark:bg-gray-800">
            <button
              @click="close"
              class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
              :disabled="loading"
            >
              Cancel
            </button>
            <button
              @click="save"
              class="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="loading || !isValid"
            >
              <span v-if="loading" class="flex items-center gap-2">
                <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Saving...
              </span>
              <span v-else>{{ isEditing ? 'Save Changes' : 'Create Group' }}</span>
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
