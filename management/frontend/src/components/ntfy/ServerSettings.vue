<template>
  <div class="server-settings">
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Server Settings</h3>

    <form @submit.prevent="saveSettings" class="space-y-6">
      <!-- Connection Settings -->
      <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600">
        <h4 class="font-medium text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <GlobeAltIcon class="w-5 h-5" />
          Connection
        </h4>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Base URL
            </label>
            <input
              v-model="form.base_url"
              type="url"
              placeholder="https://ntfy.example.com"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
            />
            <p class="mt-1 text-xs text-gray-500">Your NTFY server URL (leave empty for default)</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Upstream Base URL
            </label>
            <input
              v-model="form.upstream_base_url"
              type="url"
              placeholder="https://ntfy.sh"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
            />
            <p class="mt-1 text-xs text-gray-500">Upstream server for federation</p>
          </div>
        </div>
      </div>

      <!-- Access Control -->
      <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600">
        <h4 class="font-medium text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <ShieldCheckIcon class="w-5 h-5" />
          Access Control
        </h4>

        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Default Access
            </label>
            <select
              v-model="form.default_access"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
            >
              <option value="read-write">Read & Write</option>
              <option value="read-only">Read Only</option>
              <option value="write-only">Write Only</option>
              <option value="deny-all">Deny All</option>
            </select>
          </div>

          <div class="flex items-center gap-6">
            <div class="flex items-center">
              <input
                id="enable_login"
                v-model="form.enable_login"
                type="checkbox"
                class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label for="enable_login" class="ml-2 text-sm text-gray-700 dark:text-gray-300">
                Enable login
              </label>
            </div>
            <div class="flex items-center">
              <input
                id="enable_signup"
                v-model="form.enable_signup"
                type="checkbox"
                class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label for="enable_signup" class="ml-2 text-sm text-gray-700 dark:text-gray-300">
                Enable signup
              </label>
            </div>
          </div>
        </div>
      </div>

      <!-- Cache & Attachments -->
      <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600">
        <h4 class="font-medium text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <CircleStackIcon class="w-5 h-5" />
          Cache & Attachments
        </h4>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Cache Duration
            </label>
            <input
              v-model="form.cache_duration"
              type="text"
              placeholder="24h"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Attachment Expiry
            </label>
            <input
              v-model="form.attachment_expiry_duration"
              type="text"
              placeholder="24h"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Total Attachment Size Limit
            </label>
            <input
              v-model="form.attachment_total_size_limit"
              type="text"
              placeholder="100M"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Per-File Size Limit
            </label>
            <input
              v-model="form.attachment_file_size_limit"
              type="text"
              placeholder="15M"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
            />
          </div>
        </div>
      </div>

      <!-- Rate Limiting -->
      <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600">
        <h4 class="font-medium text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <ClockIcon class="w-5 h-5" />
          Rate Limiting
        </h4>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Daily Message Limit per Visitor
          </label>
          <input
            v-model.number="form.visitor_message_daily_limit"
            type="number"
            min="0"
            placeholder="0 = unlimited"
            class="w-full md:w-1/2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
          />
          <p class="mt-1 text-xs text-gray-500">Set to 0 for unlimited</p>
        </div>
      </div>

      <!-- SMTP Settings -->
      <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600">
        <h4 class="font-medium text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <EnvelopeIcon class="w-5 h-5" />
          SMTP Email Settings
          <span v-if="config.smtp_configured" class="px-2 py-0.5 rounded text-xs bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
            Configured
          </span>
        </h4>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              SMTP Server Address
            </label>
            <input
              v-model="form.smtp_sender_addr"
              type="text"
              placeholder="smtp.gmail.com:587"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              From Address
            </label>
            <input
              v-model="form.smtp_sender_from"
              type="email"
              placeholder="noreply@example.com"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Username
            </label>
            <input
              v-model="form.smtp_sender_user"
              type="text"
              placeholder="(optional for IP-whitelisted servers)"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Password
            </label>
            <input
              v-model="form.smtp_sender_pass"
              type="password"
              placeholder="(optional for IP-whitelisted servers)"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
            />
          </div>
        </div>

        <p class="mt-2 text-xs text-gray-500">
          For IP-whitelisted SMTP servers (like business Gmail), you can leave username and password empty.
        </p>
      </div>

      <!-- Status Info -->
      <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600">
        <h4 class="font-medium text-gray-900 dark:text-white mb-4">Server Status</h4>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span class="text-gray-500 dark:text-gray-400">Health Status:</span>
            <span :class="[
              'ml-2 font-medium',
              config.health_status === 'healthy'
                ? 'text-green-600 dark:text-green-400'
                : 'text-red-600 dark:text-red-400'
            ]">
              {{ config.health_status || 'Unknown' }}
            </span>
          </div>

          <div>
            <span class="text-gray-500 dark:text-gray-400">Last Check:</span>
            <span class="ml-2 text-gray-900 dark:text-white">
              {{ config.last_health_check ? formatDate(config.last_health_check) : 'Never' }}
            </span>
          </div>

          <div>
            <span class="text-gray-500 dark:text-gray-400">SMTP:</span>
            <span :class="[
              'ml-2 font-medium',
              config.smtp_configured ? 'text-green-600 dark:text-green-400' : 'text-gray-500'
            ]">
              {{ config.smtp_configured ? 'Configured' : 'Not configured' }}
            </span>
          </div>

          <div>
            <span class="text-gray-500 dark:text-gray-400">Web Push:</span>
            <span :class="[
              'ml-2 font-medium',
              config.web_push_configured ? 'text-green-600 dark:text-green-400' : 'text-gray-500'
            ]">
              {{ config.web_push_configured ? 'Configured' : 'Not configured' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Save Button -->
      <div class="flex justify-end gap-3">
        <button
          type="button"
          @click="resetForm"
          class="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
        >
          Reset
        </button>
        <button
          type="submit"
          :disabled="saving"
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {{ saving ? 'Saving...' : 'Save Settings' }}
        </button>
      </div>

      <!-- Result Message -->
      <div v-if="resultMessage" :class="[
        'p-3 rounded-lg text-sm',
        resultSuccess ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300' : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'
      ]">
        {{ resultMessage }}
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import {
  GlobeAltIcon,
  ShieldCheckIcon,
  CircleStackIcon,
  ClockIcon,
  EnvelopeIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps({
  config: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['update'])

// State
const saving = ref(false)
const resultMessage = ref('')
const resultSuccess = ref(false)

const form = ref({
  base_url: '',
  upstream_base_url: 'https://ntfy.sh',
  default_access: 'read-write',
  enable_login: true,
  enable_signup: false,
  cache_duration: '24h',
  attachment_total_size_limit: '100M',
  attachment_file_size_limit: '15M',
  attachment_expiry_duration: '24h',
  visitor_message_daily_limit: 0,
  smtp_sender_addr: '',
  smtp_sender_user: '',
  smtp_sender_pass: '',
  smtp_sender_from: '',
})

// Initialize form from config
function initForm() {
  form.value = {
    base_url: props.config.base_url || '',
    upstream_base_url: props.config.upstream_base_url || 'https://ntfy.sh',
    default_access: props.config.default_access || 'read-write',
    enable_login: props.config.enable_login ?? true,
    enable_signup: props.config.enable_signup ?? false,
    cache_duration: props.config.cache_duration || '24h',
    attachment_total_size_limit: props.config.attachment_total_size_limit || '100M',
    attachment_file_size_limit: props.config.attachment_file_size_limit || '15M',
    attachment_expiry_duration: props.config.attachment_expiry_duration || '24h',
    visitor_message_daily_limit: props.config.visitor_message_daily_limit || 0,
    smtp_sender_addr: '',
    smtp_sender_user: '',
    smtp_sender_pass: '',
    smtp_sender_from: '',
  }
}

// Watch for config changes
watch(() => props.config, initForm, { immediate: true })

// Format date
function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString()
}

// Reset form
function resetForm() {
  initForm()
  resultMessage.value = ''
}

// Save settings
async function saveSettings() {
  saving.value = true
  resultMessage.value = ''

  try {
    const result = await emit('update', form.value)

    if (result?.success) {
      resultSuccess.value = true
      resultMessage.value = 'Settings saved successfully!'
    } else {
      resultSuccess.value = false
      resultMessage.value = result?.error || 'Failed to save settings'
    }
  } catch (error) {
    resultSuccess.value = false
    resultMessage.value = error.message || 'Failed to save settings'
  } finally {
    saving.value = false
  }
}
</script>
