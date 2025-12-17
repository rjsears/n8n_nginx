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
  slug: '',
  service_type: 'apprise',
  enabled: true,
  webhook_enabled: false,
  priority: 0,
  config: {
    url: '',
  },
})

// Generate slug from name
function generateSlug(name) {
  return name.toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/_+/g, '_')
}

// Auto-generate slug when name changes (only for new services)
function onNameChange() {
  if (!props.service && !form.value.slug) {
    form.value.slug = generateSlug(form.value.name)
  }
}

// Service type options
const serviceTypes = [
  { id: 'apprise', name: 'Apprise', description: 'Universal notification library (Discord, Slack, Telegram, etc.)' },
  { id: 'ntfy', name: 'NTFY', description: 'Simple push notifications via ntfy.sh' },
  { id: 'email', name: 'Email', description: 'Direct SMTP email notifications' },
  { id: 'webhook', name: 'Webhook', description: 'Custom HTTP webhook endpoint' },
]

// Email provider presets
const emailPresets = [
  { id: 'gmail_relay', name: 'Gmail Relay (IP Whitelist)', description: 'For Google Workspace with IP whitelisting' },
  { id: 'gmail_app', name: 'Gmail (App Password)', description: 'Gmail with app-specific password' },
  { id: 'internal', name: 'Internal Mail Server', description: 'Local/internal SMTP server without auth' },
  { id: 'custom', name: 'Custom SMTP', description: 'Standard SMTP with authentication' },
]

// Apply email preset configurations
function applyEmailPreset(presetId) {
  const presets = {
    gmail_relay: {
      smtp_server: 'smtp-relay.gmail.com',
      smtp_port: 587,
      smtp_user: '',
      smtp_password: '',
      use_tls: true,
      use_starttls: true,
    },
    gmail_app: {
      smtp_server: 'smtp.gmail.com',
      smtp_port: 587,
      smtp_user: '',
      smtp_password: '',
      use_tls: true,
      use_starttls: true,
    },
    internal: {
      smtp_server: '',
      smtp_port: 25,
      smtp_user: '',
      smtp_password: '',
      use_tls: false,
      use_starttls: false,
    },
    custom: {
      smtp_server: '',
      smtp_port: 587,
      smtp_user: '',
      smtp_password: '',
      use_tls: true,
      use_starttls: true,
    },
  }

  const preset = presets[presetId] || presets.custom
  form.value.config = {
    ...form.value.config,
    ...preset,
    email_preset: presetId,
    // Preserve user-entered values
    from_email: form.value.config.from_email || '',
    to_emails: form.value.config.to_emails || '',
  }
}

// Reset form when dialog opens/closes
watch(() => props.open, (isOpen) => {
  if (isOpen) {
    // Reset loading state when dialog opens
    loading.value = false

    if (props.service) {
      // Editing existing service
      form.value = {
        name: props.service.name || '',
        slug: props.service.slug || '',
        service_type: props.service.service_type || 'apprise',
        enabled: props.service.enabled ?? true,
        webhook_enabled: props.service.webhook_enabled ?? false,
        priority: props.service.priority || 0,
        config: { ...props.service.config } || { url: '' },
      }
    } else {
      // New service
      form.value = {
        name: '',
        slug: '',
        service_type: 'apprise',
        enabled: true,
        webhook_enabled: false,
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
  } else if (newType === 'email') {
    form.value.config = {
      email_preset: form.value.config.email_preset || 'custom',
      smtp_server: form.value.config.smtp_server || '',
      smtp_port: form.value.config.smtp_port || 587,
      smtp_user: form.value.config.smtp_user || '',
      smtp_password: form.value.config.smtp_password || '',
      use_tls: form.value.config.use_tls ?? true,
      use_starttls: form.value.config.use_starttls ?? true,
      from_email: form.value.config.from_email || '',
      to_emails: form.value.config.to_emails || '',
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
  } else if (form.value.service_type === 'email') {
    return !!form.value.config.smtp_server?.trim() &&
           !!form.value.config.from_email?.trim() &&
           !!form.value.config.to_emails?.trim()
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
        <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full border border-gray-400 dark:border-gray-700 max-h-[90vh] overflow-hidden flex flex-col">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-full bg-blue-100 dark:bg-blue-500/20">
                <BellIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
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
                  Channel Name *
                </label>
                <input
                  v-model="form.name"
                  @input="onNameChange"
                  type="text"
                  class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Discord Alerts"
                  required
                />
              </div>

              <!-- Slug -->
              <div>
                <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                  Slug (for targeting)
                </label>
                <div class="flex items-center gap-2">
                  <span class="text-sm text-gray-500 dark:text-gray-400 font-mono">channel:</span>
                  <input
                    v-model="form.slug"
                    type="text"
                    class="flex-1 px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="discord_alerts"
                    pattern="^[a-z0-9_]+$"
                  />
                </div>
                <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Used in n8n webhooks to target this channel. Lowercase letters, numbers, and underscores only.
                </p>
              </div>

              <!-- Service Type -->
              <div>
                <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                  Service Type *
                </label>
                <select
                  v-model="form.service_type"
                  class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                  <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                    Apprise URL *
                  </label>
                  <input
                    v-model="form.config.url"
                    type="text"
                    class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="discord://webhook_id/webhook_token"
                    required
                  />
                  <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    Enter your Apprise notification URL.
                    <a href="https://github.com/caronc/apprise/wiki" target="_blank" class="text-blue-500 hover:underline">
                      See documentation
                    </a>
                  </p>
                </div>

                <!-- Examples -->
                <div class="bg-gray-100 dark:bg-gray-700 rounded-lg p-3">
                  <p class="text-xs font-medium text-gray-600 dark:text-gray-300 mb-2">URL Examples:</p>
                  <div class="space-y-1">
                    <div
                      v-for="example in appriseExamples"
                      :key="example.name"
                      class="text-xs font-mono text-gray-500 dark:text-gray-400"
                    >
                      <span class="text-gray-900 dark:text-white">{{ example.name }}:</span> {{ example.url }}
                    </div>
                  </div>
                </div>
              </template>

              <!-- NTFY Config -->
              <template v-if="form.service_type === 'ntfy'">
                <div>
                  <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                    Server
                  </label>
                  <input
                    v-model="form.config.server"
                    type="text"
                    class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="https://ntfy.sh"
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                    Topic *
                  </label>
                  <input
                    v-model="form.config.topic"
                    type="text"
                    class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="my-n8n-alerts"
                    required
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                    Access Token (optional)
                  </label>
                  <input
                    v-model="form.config.token"
                    type="password"
                    class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="tk_xxx..."
                  />
                </div>
              </template>

              <!-- Email Config -->
              <template v-if="form.service_type === 'email'">
                <!-- Provider Preset -->
                <div>
                  <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                    Email Provider
                  </label>
                  <select
                    v-model="form.config.email_preset"
                    @change="applyEmailPreset(form.config.email_preset)"
                    class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option
                      v-for="preset in emailPresets"
                      :key="preset.id"
                      :value="preset.id"
                    >
                      {{ preset.name }}
                    </option>
                  </select>
                  <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {{ emailPresets.find(p => p.id === form.config.email_preset)?.description }}
                  </p>
                </div>

                <!-- SMTP Server & Port -->
                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                      SMTP Server *
                    </label>
                    <input
                      v-model="form.config.smtp_server"
                      type="text"
                      class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      :placeholder="form.config.email_preset === 'internal' ? 'mail.internal.local' : 'smtp.example.com'"
                      required
                    />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                      Port
                    </label>
                    <input
                      v-model="form.config.smtp_port"
                      type="number"
                      class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>

                <!-- Authentication (shown for custom and gmail_app) -->
                <template v-if="form.config.email_preset === 'custom' || form.config.email_preset === 'gmail_app'">
                  <div class="grid grid-cols-2 gap-4">
                    <div>
                      <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                        {{ form.config.email_preset === 'gmail_app' ? 'Gmail Address' : 'Username' }}
                      </label>
                      <input
                        v-model="form.config.smtp_user"
                        type="text"
                        class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                        :placeholder="form.config.email_preset === 'gmail_app' ? 'user@gmail.com' : 'user@example.com'"
                      />
                    </div>
                    <div>
                      <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                        {{ form.config.email_preset === 'gmail_app' ? 'App Password' : 'Password' }}
                      </label>
                      <input
                        v-model="form.config.smtp_password"
                        type="password"
                        class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="••••••••"
                      />
                    </div>
                  </div>
                  <p v-if="form.config.email_preset === 'gmail_app'" class="text-xs text-gray-500 dark:text-gray-400 -mt-2">
                    Generate an app password at <a href="https://myaccount.google.com/apppasswords" target="_blank" class="text-blue-500 hover:underline">Google Account Settings</a>
                  </p>
                </template>

                <!-- Gmail Relay Note -->
                <div v-if="form.config.email_preset === 'gmail_relay'" class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
                  <p class="text-xs text-blue-700 dark:text-blue-300">
                    <strong>Gmail Relay:</strong> Requires your server's IP to be whitelisted in Google Workspace Admin Console under Apps → Google Workspace → Gmail → Routing → SMTP relay service.
                  </p>
                </div>

                <!-- Internal Server Note -->
                <div v-if="form.config.email_preset === 'internal'" class="bg-amber-50 dark:bg-amber-900/20 rounded-lg p-3">
                  <p class="text-xs text-amber-700 dark:text-amber-300">
                    <strong>Internal Server:</strong> No authentication required. Ensure your mail server accepts connections from this host.
                  </p>
                </div>

                <!-- From Email -->
                <div>
                  <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                    From Email *
                  </label>
                  <input
                    v-model="form.config.from_email"
                    type="email"
                    class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="n8n-alerts@yourdomain.com"
                    required
                  />
                </div>

                <!-- To Emails -->
                <div>
                  <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                    To Emails *
                  </label>
                  <input
                    v-model="form.config.to_emails"
                    type="text"
                    class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="admin@example.com, ops@example.com"
                    required
                  />
                  <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    Comma-separated list of recipient addresses
                  </p>
                </div>

                <!-- TLS Toggle (only for custom) -->
                <div v-if="form.config.email_preset === 'custom'" class="flex items-center justify-between">
                  <div>
                    <label class="text-sm font-medium text-gray-900 dark:text-white">Use STARTTLS</label>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Enable TLS encryption (recommended)</p>
                  </div>
                  <label class="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      v-model="form.config.use_starttls"
                      class="sr-only peer"
                    />
                    <div
                      class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-400 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"
                    ></div>
                  </label>
                </div>
              </template>

              <!-- Webhook Config -->
              <template v-if="form.service_type === 'webhook'">
                <div>
                  <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                    Webhook URL *
                  </label>
                  <input
                    v-model="form.config.url"
                    type="url"
                    class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="https://your-server.com/webhook"
                    required
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                    HTTP Method
                  </label>
                  <select
                    v-model="form.config.method"
                    class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="POST">POST</option>
                    <option value="GET">GET</option>
                  </select>
                </div>
              </template>

              <!-- Enabled Toggle -->
              <div class="flex items-center justify-between">
                <div>
                  <label class="text-sm font-medium text-gray-900 dark:text-white">Enabled</label>
                  <p class="text-xs text-gray-500 dark:text-gray-400">Send notifications through this channel</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    v-model="form.enabled"
                    class="sr-only peer"
                  />
                  <div
                    class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-400 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"
                  ></div>
                </label>
              </div>

              <!-- Webhook Enabled Toggle -->
              <div class="flex items-center justify-between border-t border-gray-400 dark:border-gray-700 pt-4">
                <div>
                  <label class="text-sm font-medium text-gray-900 dark:text-white">n8n Webhook Routing</label>
                  <p class="text-xs text-gray-500 dark:text-gray-400">Receive notifications from n8n workflows via webhook</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    v-model="form.webhook_enabled"
                    class="sr-only peer"
                  />
                  <div
                    class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-400 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-green-500"
                  ></div>
                </label>
              </div>

              <!-- Webhook Info -->
              <div v-if="form.webhook_enabled" class="bg-green-50 dark:bg-green-900/20 rounded-lg p-3 text-xs space-y-2">
                <p class="text-green-700 dark:text-green-300">
                  <strong>Webhook Enabled:</strong> This channel can receive notifications via the webhook endpoint.
                </p>
                <div v-if="form.slug" class="bg-white dark:bg-gray-800 rounded p-2 font-mono text-gray-700 dark:text-gray-300">
                  Target with: <span class="text-green-600 dark:text-green-400">"channel:{{ form.slug }}"</span>
                </div>
                <p class="text-green-600 dark:text-green-400">
                  Or use <span class="font-mono">"all"</span> to send to all webhook-enabled channels.
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
              class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
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
</style>
