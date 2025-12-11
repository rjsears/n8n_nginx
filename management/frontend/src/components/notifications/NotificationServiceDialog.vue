<script setup>
import { ref, watch, computed } from 'vue'
import { XMarkIcon, BellIcon } from '@heroicons/vue/24/outline'

const props = defineProps({
  open: Boolean,
  service: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['save', 'cancel', 'update:open'])

const loading = ref(false)

// Form data
const form = ref({
  name: '',
  service_type: 'apprise',
  enabled: true,
  priority: 0,
  config: {
    url: '',
  },
})

// Service type options
const serviceTypes = [
  { id: 'apprise', name: 'Apprise', description: 'Universal notification library (Discord, Slack, Telegram, etc.)' },
  { id: 'ntfy', name: 'NTFY', description: 'Simple push notifications via ntfy.sh' },
  { id: 'webhook', name: 'Webhook', description: 'Custom HTTP webhook endpoint' },
]

// Reset form when dialog opens/closes
watch(() => props.open, (isOpen) => {
  if (isOpen) {
    if (props.service) {
      // Editing existing service
      form.value = {
        name: props.service.name || '',
        service_type: props.service.service_type || 'apprise',
        enabled: props.service.enabled ?? true,
        priority: props.service.priority || 0,
        config: { ...props.service.config } || { url: '' },
      }
    } else {
      // New service
      form.value = {
        name: '',
        service_type: 'apprise',
        enabled: true,
        priority: 0,
        config: { url: '' },
      }
    }
  }
})

// Reset config when service type changes
watch(() => form.value.service_type, (newType) => {
  if (newType === 'apprise') {
    form.value.config = { url: form.value.config.url || '' }
  } else if (newType === 'ntfy') {
    form.value.config = {
      server: form.value.config.server || 'https://ntfy.sh',
      topic: form.value.config.topic || '',
      token: form.value.config.token || '',
    }
  } else if (newType === 'webhook') {
    form.value.config = {
      url: form.value.config.url || '',
      method: form.value.config.method || 'POST',
      headers: form.value.config.headers || {},
    }
  }
})

const isEditing = computed(() => !!props.service)

const dialogTitle = computed(() => isEditing.value ? 'Edit Notification Channel' : 'Add Notification Channel')

const isValid = computed(() => {
  if (!form.value.name.trim()) return false

  if (form.value.service_type === 'apprise') {
    return !!form.value.config.url?.trim()
  } else if (form.value.service_type === 'ntfy') {
    return !!form.value.config.topic?.trim()
  } else if (form.value.service_type === 'webhook') {
    return !!form.value.config.url?.trim()
  }

  return false
})

function close() {
  emit('update:open', false)
  emit('cancel')
}

function save() {
  if (!isValid.value) return

  loading.value = true
  emit('save', {
    ...form.value,
    id: props.service?.id,
  })
}

// Apprise URL examples
const appriseExamples = [
  { name: 'Discord', url: 'discord://webhook_id/webhook_token' },
  { name: 'Slack', url: 'slack://token_a/token_b/token_c/#channel' },
  { name: 'Telegram', url: 'tgram://bot_token/chat_id' },
  { name: 'Pushover', url: 'pover://user_key@api_key' },
  { name: 'Email', url: 'mailto://user:pass@gmail.com?to=recipient@email.com' },
]
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
        <div class="relative bg-surface rounded-lg shadow-xl max-w-lg w-full border border-[var(--color-border)] max-h-[90vh] overflow-hidden flex flex-col">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-full bg-blue-100 dark:bg-blue-500/20">
                <BellIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 class="text-lg font-semibold text-primary">{{ dialogTitle }}</h3>
            </div>
            <button
              @click="close"
              class="p-1 rounded-lg text-secondary hover:text-primary hover:bg-surface-hover"
            >
              <XMarkIcon class="h-5 w-5" />
            </button>
          </div>

          <!-- Content -->
          <div class="px-6 py-4 overflow-y-auto flex-1">
            <form @submit.prevent="save" class="space-y-4">
              <!-- Name -->
              <div>
                <label class="block text-sm font-medium text-primary mb-1">
                  Channel Name *
                </label>
                <input
                  v-model="form.name"
                  type="text"
                  class="input-field w-full"
                  placeholder="e.g., Discord Alerts"
                  required
                />
              </div>

              <!-- Service Type -->
              <div>
                <label class="block text-sm font-medium text-primary mb-1">
                  Service Type *
                </label>
                <select
                  v-model="form.service_type"
                  class="input-field w-full"
                >
                  <option
                    v-for="type in serviceTypes"
                    :key="type.id"
                    :value="type.id"
                  >
                    {{ type.name }} - {{ type.description }}
                  </option>
                </select>
              </div>

              <!-- Apprise Config -->
              <template v-if="form.service_type === 'apprise'">
                <div>
                  <label class="block text-sm font-medium text-primary mb-1">
                    Apprise URL *
                  </label>
                  <input
                    v-model="form.config.url"
                    type="text"
                    class="input-field w-full font-mono text-sm"
                    placeholder="discord://webhook_id/webhook_token"
                    required
                  />
                  <p class="mt-1 text-xs text-secondary">
                    Enter your Apprise notification URL.
                    <a href="https://github.com/caronc/apprise/wiki" target="_blank" class="text-blue-500 hover:underline">
                      See documentation
                    </a>
                  </p>
                </div>

                <!-- Examples -->
                <div class="bg-surface-hover rounded-lg p-3">
                  <p class="text-xs font-medium text-secondary mb-2">URL Examples:</p>
                  <div class="space-y-1">
                    <div
                      v-for="example in appriseExamples"
                      :key="example.name"
                      class="text-xs font-mono text-muted"
                    >
                      <span class="text-primary">{{ example.name }}:</span> {{ example.url }}
                    </div>
                  </div>
                </div>
              </template>

              <!-- NTFY Config -->
              <template v-if="form.service_type === 'ntfy'">
                <div>
                  <label class="block text-sm font-medium text-primary mb-1">
                    Server
                  </label>
                  <input
                    v-model="form.config.server"
                    type="text"
                    class="input-field w-full"
                    placeholder="https://ntfy.sh"
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-primary mb-1">
                    Topic *
                  </label>
                  <input
                    v-model="form.config.topic"
                    type="text"
                    class="input-field w-full"
                    placeholder="my-n8n-alerts"
                    required
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-primary mb-1">
                    Access Token (optional)
                  </label>
                  <input
                    v-model="form.config.token"
                    type="password"
                    class="input-field w-full"
                    placeholder="tk_xxx..."
                  />
                </div>
              </template>

              <!-- Webhook Config -->
              <template v-if="form.service_type === 'webhook'">
                <div>
                  <label class="block text-sm font-medium text-primary mb-1">
                    Webhook URL *
                  </label>
                  <input
                    v-model="form.config.url"
                    type="url"
                    class="input-field w-full"
                    placeholder="https://your-server.com/webhook"
                    required
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-primary mb-1">
                    HTTP Method
                  </label>
                  <select
                    v-model="form.config.method"
                    class="input-field w-full"
                  >
                    <option value="POST">POST</option>
                    <option value="GET">GET</option>
                  </select>
                </div>
              </template>

              <!-- Enabled Toggle -->
              <div class="flex items-center justify-between">
                <div>
                  <label class="text-sm font-medium text-primary">Enabled</label>
                  <p class="text-xs text-secondary">Send notifications through this channel</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    v-model="form.enabled"
                    class="sr-only peer"
                  />
                  <div
                    class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"
                  ></div>
                </label>
              </div>
            </form>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-[var(--color-border)]">
            <button
              @click="close"
              class="btn-secondary"
              :disabled="loading"
            >
              Cancel
            </button>
            <button
              @click="save"
              class="btn-primary"
              :disabled="loading || !isValid"
            >
              <span v-if="loading" class="flex items-center gap-2">
                <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Saving...
              </span>
              <span v-else>{{ isEditing ? 'Save Changes' : 'Add Channel' }}</span>
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

.input-field {
  @apply px-3 py-2 rounded-lg border border-[var(--color-border)] bg-surface text-primary;
  @apply focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent;
}
</style>
