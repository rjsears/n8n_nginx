<script setup>
import { ref, onMounted } from 'vue'
import { useNotificationStore } from '@/stores/notifications'
import { useThemeStore } from '@/stores/theme'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import {
  KeyIcon,
  BugAntIcon,
  EyeIcon,
  EyeSlashIcon,
} from '@heroicons/vue/24/outline'

const themeStore = useThemeStore()
const notificationStore = useNotificationStore()

const loading = ref(true)

// Debug mode state
const debugMode = ref(false)
const debugModeLoading = ref(false)

// n8n API Key state
const n8nApiKey = ref('')
const n8nApiKeyMasked = ref('')
const n8nApiKeyIsSet = ref(false)
const n8nApiKeyLoading = ref(false)
const showN8nApiKey = ref(false)
const n8nApiKeyEditing = ref(false)

async function loadSettings() {
  loading.value = true
  try {
    // Load debug mode
    const debugRes = await api.settings.getDebugMode()
    debugMode.value = debugRes.data.enabled

    // Load n8n API key status
    const apiKeyRes = await api.settings.getEnvVariable('N8N_API_KEY')
    n8nApiKeyIsSet.value = apiKeyRes.data.is_set
    n8nApiKeyMasked.value = apiKeyRes.data.masked_value || ''
  } catch (error) {
    console.error('Failed to load settings:', error)
    notificationStore.error('Failed to load settings')
  } finally {
    loading.value = false
  }
}

async function toggleDebugMode() {
  debugModeLoading.value = true
  try {
    const newValue = !debugMode.value
    await api.settings.setDebugMode(newValue)
    debugMode.value = newValue
    notificationStore.success(`Debug mode ${newValue ? 'enabled' : 'disabled'}`)
  } catch (error) {
    console.error('Failed to update debug mode:', error)
    notificationStore.error('Failed to update debug mode')
  } finally {
    debugModeLoading.value = false
  }
}

function startEditN8nApiKey() {
  n8nApiKeyEditing.value = true
  n8nApiKey.value = ''
}

function cancelEditN8nApiKey() {
  n8nApiKeyEditing.value = false
  n8nApiKey.value = ''
}

async function saveN8nApiKey() {
  if (!n8nApiKey.value.trim()) {
    notificationStore.error('API key cannot be empty')
    return
  }

  n8nApiKeyLoading.value = true
  try {
    await api.settings.updateEnvVariable('N8N_API_KEY', n8nApiKey.value.trim())
    n8nApiKeyIsSet.value = true
    n8nApiKeyMasked.value = n8nApiKey.value.length > 8
      ? `${n8nApiKey.value.slice(0, 4)}...${n8nApiKey.value.slice(-4)}`
      : '*'.repeat(n8nApiKey.value.length)
    n8nApiKeyEditing.value = false
    n8nApiKey.value = ''
    notificationStore.success('n8n API key updated successfully')
  } catch (error) {
    console.error('Failed to update API key:', error)
    notificationStore.error('Failed to update n8n API key')
  } finally {
    n8nApiKeyLoading.value = false
  }
}

onMounted(() => {
  loadSettings()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div>
      <h1
        :class="[
          'text-2xl font-bold',
          themeStore.isNeon ? 'neon-text-cyan' : 'text-primary'
        ]"
      >
        n8n API & Debug
      </h1>
      <p class="text-secondary mt-1">Configure n8n API integration and debug settings</p>
    </div>

    <LoadingSpinner v-if="loading" size="lg" text="Loading settings..." class="py-12" />

    <template v-else>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- n8n API Key Card -->
        <Card :neon="true" :padding="false">
          <template #header>
            <div class="flex items-center gap-2 px-4 py-3">
              <KeyIcon class="h-5 w-5 text-blue-500" />
              <h3 class="font-semibold text-primary">n8n API Key</h3>
            </div>
          </template>
          <div class="p-4">
            <p class="text-sm text-secondary mb-4">
              The n8n API key enables communication with your n8n instance for workflow management
              and notifications. Generate this key in n8n under
              <span class="font-medium">Settings &rarr; API</span>.
            </p>

            <div class="flex items-center justify-between mb-3 py-2 border-b border-[var(--color-border)]">
              <span class="text-sm text-secondary">Status</span>
              <span
                :class="[
                  'flex items-center gap-2 text-sm font-medium',
                  n8nApiKeyIsSet ? 'text-emerald-500' : 'text-amber-500'
                ]"
              >
                <span :class="['w-2 h-2 rounded-full', n8nApiKeyIsSet ? 'bg-emerald-500' : 'bg-amber-500']"></span>
                {{ n8nApiKeyIsSet ? 'Configured' : 'Not Set' }}
              </span>
            </div>

            <div v-if="n8nApiKeyIsSet && !n8nApiKeyEditing" class="flex items-center justify-between mb-4 py-2 border-b border-[var(--color-border)]">
              <span class="text-sm text-secondary">Current Key</span>
              <span class="font-mono text-sm text-primary">{{ n8nApiKeyMasked }}</span>
            </div>

            <!-- Edit Form -->
            <div v-if="n8nApiKeyEditing" class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-primary mb-1.5">New API Key</label>
                <div class="relative">
                  <KeyIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted" />
                  <input
                    v-model="n8nApiKey"
                    :type="showN8nApiKey ? 'text' : 'password'"
                    placeholder="Enter your n8n API key"
                    class="input-field pl-10 pr-10 w-full"
                  />
                  <button
                    type="button"
                    @click="showN8nApiKey = !showN8nApiKey"
                    class="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-secondary"
                  >
                    <EyeSlashIcon v-if="showN8nApiKey" class="h-5 w-5" />
                    <EyeIcon v-else class="h-5 w-5" />
                  </button>
                </div>
              </div>
              <div class="flex gap-3">
                <button
                  @click="saveN8nApiKey"
                  :disabled="n8nApiKeyLoading || !n8nApiKey.trim()"
                  class="btn-primary"
                >
                  {{ n8nApiKeyLoading ? 'Saving...' : 'Save Key' }}
                </button>
                <button
                  @click="cancelEditN8nApiKey"
                  :disabled="n8nApiKeyLoading"
                  class="btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </div>

            <!-- Edit Button -->
            <button
              v-if="!n8nApiKeyEditing"
              @click="startEditN8nApiKey"
              :class="[
                'w-full py-2 rounded-lg font-medium transition-all',
                n8nApiKeyIsSet
                  ? 'bg-emerald-500 hover:bg-emerald-600 text-white'
                  : 'btn-primary'
              ]"
            >
              {{ n8nApiKeyIsSet ? 'Update API Key' : 'Set API Key' }}
            </button>
          </div>
        </Card>

        <!-- Debug Mode Card -->
        <Card :neon="true" :padding="false">
          <template #header>
            <div class="flex items-center gap-2 px-4 py-3">
              <BugAntIcon class="h-5 w-5 text-amber-500" />
              <h3 class="font-semibold text-primary">Debug Mode</h3>
            </div>
          </template>
          <div class="p-4">
            <p class="text-sm text-secondary mb-4">
              Enable debug mode to show detailed error messages and verbose logging.
              Useful for troubleshooting issues with the management console.
            </p>

            <div class="flex items-center justify-between py-3 border-y border-[var(--color-border)]">
              <div>
                <p class="font-medium text-primary">Enable Debug Mode</p>
                <p class="text-sm text-secondary">
                  Shows detailed errors in the browser console
                </p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  :checked="debugMode"
                  @change="toggleDebugMode"
                  :disabled="debugModeLoading"
                  class="sr-only peer"
                />
                <div
                  :class="[
                    'w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700',
                    'peer-checked:after:translate-x-full peer-checked:after:border-white',
                    `after:content-[''] after:absolute after:top-[2px] after:left-[2px]`,
                    'after:bg-white after:border-gray-300 after:border after:rounded-full',
                    'after:h-5 after:w-5 after:transition-all dark:border-gray-600',
                    'peer-checked:bg-amber-500',
                    debugModeLoading ? 'opacity-50' : ''
                  ]"
                ></div>
              </label>
            </div>

            <div v-if="debugMode" class="mt-4 p-3 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30">
              <p class="text-sm text-amber-700 dark:text-amber-400">
                Debug mode is active. Check the browser developer console (F12) for detailed logs.
              </p>
            </div>

            <div v-else class="mt-4 p-3 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
              <p class="text-sm text-secondary">
                Debug mode is disabled. Enable it when troubleshooting issues.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </template>
  </div>
</template>
