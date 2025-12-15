<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import { useDebugStore } from '@/stores/debug'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import {
  Cog6ToothIcon,
  PaintBrushIcon,
  ShieldCheckIcon,
  BellIcon,
  CircleStackIcon,
  UserIcon,
  KeyIcon,
  EyeIcon,
  EyeSlashIcon,
  CheckIcon,
  SunIcon,
  MoonIcon,
  BugAntIcon,
  Bars3Icon,
  ViewColumnsIcon,
} from '@heroicons/vue/24/outline'

const route = useRoute()
const themeStore = useThemeStore()
const authStore = useAuthStore()
const notificationStore = useNotificationStore()
const debugStore = useDebugStore()

const loading = ref(true)
const saving = ref(false)
const activeTab = ref(route.query.tab || 'appearance')

// Watch for tab query changes
watch(() => route.query.tab, (newTab) => {
  if (newTab) activeTab.value = newTab
})

// Password change
const passwordForm = ref({
  current: '',
  new: '',
  confirm: '',
})
const showPasswords = ref({
  current: false,
  new: false,
  confirm: false,
})
const changingPassword = ref(false)

// Debug mode - use store (local refs for backward compatibility in template)
const debugMode = computed(() => debugStore.isEnabled)
const debugModeLoading = computed(() => debugStore.loading)

// n8n API Key state
const n8nApiKey = ref('')
const n8nApiKeyMasked = ref('')
const n8nApiKeyIsSet = ref(false)
const n8nApiKeyLoading = ref(false)
const showN8nApiKey = ref(false)
const n8nApiKeyEditing = ref(false)

// Settings
const settings = ref({
  backup: {
    enabled: true,
    schedule: '02:00',
    retention_days: 30,
    include_workflows: true,
    include_credentials: true,
    nfs_enabled: false,
    nfs_path: '',
  },
  notifications: {
    backup_success: true,
    backup_failure: true,
    container_unhealthy: true,
    disk_space_warning: true,
    disk_space_threshold: 80,
  },
  security: {
    session_timeout: 60,
    max_login_attempts: 5,
    lockout_duration: 15,
  },
})

// No longer using theme presets - removed in favor of simpler light/dark toggle

const tabs = [
  { id: 'appearance', name: 'Appearance', icon: PaintBrushIcon },
  { id: 'backup', name: 'Backup', icon: CircleStackIcon },
  { id: 'notifications', name: 'System Notifications', icon: BellIcon },
  { id: 'security', name: 'Security', icon: ShieldCheckIcon },
  { id: 'account', name: 'Account', icon: UserIcon },
  { id: 'api-debug', name: 'n8n API / Debug', icon: BugAntIcon },
]

async function loadSettings() {
  loading.value = true
  try {
    const response = await api.settings.getAll()
    if (response.data) {
      settings.value = { ...settings.value, ...response.data }
    }

    // Load n8n API key status
    try {
      const apiKeyRes = await api.settings.getEnvVariable('N8N_API_KEY')
      n8nApiKeyIsSet.value = apiKeyRes.data.is_set
      n8nApiKeyMasked.value = apiKeyRes.data.masked_value || ''
    } catch (e) {
      console.error('Failed to load n8n API key status:', e)
    }
  } catch (error) {
    console.error('Failed to load settings:', error)
  } finally {
    loading.value = false
  }
}

async function saveSettings(section) {
  saving.value = true
  try {
    // Backend expects {value: data} format per SettingUpdate schema
    await api.settings.update(section, { value: settings.value[section] })
    notificationStore.success('Settings saved successfully')
  } catch (error) {
    console.error('Failed to save settings:', error)
    notificationStore.error('Failed to save settings')
  } finally {
    saving.value = false
  }
}

async function changePassword() {
  if (passwordForm.value.new !== passwordForm.value.confirm) {
    notificationStore.error('New passwords do not match')
    return
  }

  if (passwordForm.value.new.length < 8) {
    notificationStore.error('Password must be at least 8 characters')
    return
  }

  changingPassword.value = true
  try {
    await api.auth.changePassword({
      current_password: passwordForm.value.current,
      new_password: passwordForm.value.new,
    })
    notificationStore.success('Password changed successfully')
    passwordForm.value = { current: '', new: '', confirm: '' }
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to change password')
  } finally {
    changingPassword.value = false
  }
}

// Theme selection with notification feedback
function selectTheme(mode) {
  themeStore.setColorMode(mode)
  notificationStore.success(`Theme changed to ${mode === 'dark' ? 'Dark' : 'Light'} mode`)
}

async function toggleDebugMode() {
  const success = await debugStore.toggleDebugMode()
  if (success) {
    notificationStore.success(`Debug mode ${debugStore.isEnabled ? 'enabled' : 'disabled'}`)
  } else {
    notificationStore.error('Failed to update debug mode')
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

onMounted(async () => {
  await loadSettings()
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
        Settings
      </h1>
      <p class="text-secondary mt-1">Configure your management console</p>
    </div>

    <LoadingSpinner v-if="loading" size="lg" text="Loading settings..." class="py-12" />

    <template v-else>
      <!-- Tabs -->
      <div class="flex gap-1 p-1 bg-surface-hover rounded-lg overflow-x-auto">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="[
            'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all whitespace-nowrap',
            activeTab === tab.id
              ? themeStore.isNeon
                ? 'bg-cyan-500/20 text-cyan-400'
                : 'bg-surface text-primary shadow-sm'
              : 'text-secondary hover:text-primary'
          ]"
        >
          <component :is="tab.icon" class="h-4 w-4" />
          {{ tab.name }}
        </button>
      </div>

      <!-- Appearance Tab -->
      <div v-if="activeTab === 'appearance'" class="space-y-6">
        <Card title="Theme" subtitle="Choose your preferred color scheme and navigation layout">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Modern Light Theme Card -->
            <div
              :class="[
                'relative rounded-xl border-2 overflow-hidden transition-all cursor-pointer',
                !themeStore.isDark
                  ? 'border-blue-500 ring-2 ring-blue-500/20'
                  : 'border-gray-200 hover:border-gray-300'
              ]"
              @click="selectTheme('light')"
            >
              <!-- Preview Area -->
              <div class="bg-white p-4 border-b border-gray-200">
                <div class="flex items-center gap-3 mb-3">
                  <div class="w-10 h-10 rounded-full bg-gradient-to-br from-yellow-300 to-orange-400 flex items-center justify-center">
                    <SunIcon class="h-6 w-6 text-white" />
                  </div>
                  <div>
                    <p class="font-semibold text-gray-900">Modern Light</p>
                    <p class="text-xs text-gray-500">Clean and bright interface</p>
                  </div>
                  <CheckIcon
                    v-if="!themeStore.isDark"
                    class="h-6 w-6 text-blue-500 ml-auto"
                  />
                </div>
                <!-- Mini preview -->
                <div class="bg-gray-50 rounded-lg p-2 space-y-1">
                  <div class="h-2 w-3/4 bg-gray-200 rounded"></div>
                  <div class="h-2 w-1/2 bg-gray-200 rounded"></div>
                  <div class="h-2 w-2/3 bg-gray-200 rounded"></div>
                </div>
              </div>
              <!-- Layout Toggle -->
              <div class="bg-gray-50 p-3" @click.stop>
                <div class="flex items-center justify-between">
                  <span class="text-sm font-medium text-gray-700">Navigation</span>
                  <div class="flex items-center gap-2 bg-white rounded-lg p-1 border border-gray-200">
                    <button
                      @click="themeStore.setLayoutMode('horizontal')"
                      :class="[
                        'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all',
                        themeStore.layout === 'horizontal'
                          ? 'bg-blue-500 text-white'
                          : 'text-gray-600 hover:bg-gray-100'
                      ]"
                    >
                      <Bars3Icon class="h-4 w-4" />
                      Top
                    </button>
                    <button
                      @click="themeStore.setLayoutMode('sidebar')"
                      :class="[
                        'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all',
                        themeStore.layout === 'sidebar'
                          ? 'bg-blue-500 text-white'
                          : 'text-gray-600 hover:bg-gray-100'
                      ]"
                    >
                      <ViewColumnsIcon class="h-4 w-4" />
                      Side
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Modern Dark Theme Card -->
            <div
              :class="[
                'relative rounded-xl border-2 overflow-hidden transition-all cursor-pointer',
                themeStore.isDark
                  ? 'border-blue-500 ring-2 ring-blue-500/20'
                  : 'border-gray-200 hover:border-gray-300'
              ]"
              @click="selectTheme('dark')"
            >
              <!-- Preview Area -->
              <div class="bg-slate-900 p-4 border-b border-slate-700">
                <div class="flex items-center gap-3 mb-3">
                  <div class="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                    <MoonIcon class="h-6 w-6 text-white" />
                  </div>
                  <div>
                    <p class="font-semibold text-white">Modern Dark</p>
                    <p class="text-xs text-slate-400">Easy on the eyes at night</p>
                  </div>
                  <CheckIcon
                    v-if="themeStore.isDark"
                    class="h-6 w-6 text-blue-400 ml-auto"
                  />
                </div>
                <!-- Mini preview -->
                <div class="bg-slate-800 rounded-lg p-2 space-y-1">
                  <div class="h-2 w-3/4 bg-slate-700 rounded"></div>
                  <div class="h-2 w-1/2 bg-slate-700 rounded"></div>
                  <div class="h-2 w-2/3 bg-slate-700 rounded"></div>
                </div>
              </div>
              <!-- Layout Toggle -->
              <div class="bg-slate-800 p-3" @click.stop>
                <div class="flex items-center justify-between">
                  <span class="text-sm font-medium text-slate-300">Navigation</span>
                  <div class="flex items-center gap-2 bg-slate-900 rounded-lg p-1 border border-slate-700">
                    <button
                      @click="themeStore.setLayoutMode('horizontal')"
                      :class="[
                        'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all',
                        themeStore.layout === 'horizontal'
                          ? 'bg-blue-500 text-white'
                          : 'text-slate-400 hover:bg-slate-800'
                      ]"
                    >
                      <Bars3Icon class="h-4 w-4" />
                      Top
                    </button>
                    <button
                      @click="themeStore.setLayoutMode('sidebar')"
                      :class="[
                        'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all',
                        themeStore.layout === 'sidebar'
                          ? 'bg-blue-500 text-white'
                          : 'text-slate-400 hover:bg-slate-800'
                      ]"
                    >
                      <ViewColumnsIcon class="h-4 w-4" />
                      Side
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Backup Tab -->
      <div v-if="activeTab === 'backup'" class="space-y-6">
        <Card title="Backup Configuration" :neon="true">
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Automatic Backups</p>
                <p class="text-sm text-secondary">Enable scheduled backups</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="settings.backup.enabled" class="sr-only peer" />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"
                ></div>
              </label>
            </div>

            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Backup Time</p>
                <p class="text-sm text-secondary">Daily backup schedule</p>
              </div>
              <input
                type="time"
                v-model="settings.backup.schedule"
                class="input-field w-32"
              />
            </div>

            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Retention Period</p>
                <p class="text-sm text-secondary">Days to keep backups</p>
              </div>
              <input
                type="number"
                v-model="settings.backup.retention_days"
                min="1"
                max="365"
                class="input-field w-24"
              />
            </div>

            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Include Workflows</p>
                <p class="text-sm text-secondary">Back up n8n workflows</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="settings.backup.include_workflows" class="sr-only peer" />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"
                ></div>
              </label>
            </div>

            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Include Credentials</p>
                <p class="text-sm text-secondary">Back up encrypted credentials</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="settings.backup.include_credentials" class="sr-only peer" />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"
                ></div>
              </label>
            </div>
          </div>

          <template #footer>
            <div class="flex justify-end">
              <button
                @click="saveSettings('backup')"
                :disabled="saving"
                class="btn-primary"
              >
                {{ saving ? 'Saving...' : 'Save Changes' }}
              </button>
            </div>
          </template>
        </Card>

        <Card title="NFS Storage" subtitle="Remote backup storage configuration" :neon="true">
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Enable NFS</p>
                <p class="text-sm text-secondary">Store backups on NFS share</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="settings.backup.nfs_enabled" class="sr-only peer" />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"
                ></div>
              </label>
            </div>

            <div v-if="settings.backup.nfs_enabled">
              <label class="block text-sm font-medium text-primary mb-1.5">NFS Path</label>
              <input
                type="text"
                v-model="settings.backup.nfs_path"
                placeholder="server:/path/to/share"
                class="input-field w-full"
              />
            </div>
          </div>
        </Card>
      </div>

      <!-- Notifications Tab -->
      <div v-if="activeTab === 'notifications'" class="space-y-6">
        <Card title="Notification Events" subtitle="Choose which events trigger notifications" :neon="true">
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Backup Success</p>
                <p class="text-sm text-secondary">Notify when backups complete successfully</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="settings.notifications.backup_success" class="sr-only peer" />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"
                ></div>
              </label>
            </div>

            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Backup Failure</p>
                <p class="text-sm text-secondary">Notify when backups fail</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="settings.notifications.backup_failure" class="sr-only peer" />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"
                ></div>
              </label>
            </div>

            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Container Unhealthy</p>
                <p class="text-sm text-secondary">Notify when a container becomes unhealthy</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="settings.notifications.container_unhealthy" class="sr-only peer" />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"
                ></div>
              </label>
            </div>

            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Disk Space Warning</p>
                <p class="text-sm text-secondary">Notify when disk space is low</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="settings.notifications.disk_space_warning" class="sr-only peer" />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"
                ></div>
              </label>
            </div>

            <div v-if="settings.notifications.disk_space_warning" class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Disk Space Threshold</p>
                <p class="text-sm text-secondary">Warning at this usage percentage</p>
              </div>
              <div class="flex items-center gap-2">
                <input
                  type="number"
                  v-model="settings.notifications.disk_space_threshold"
                  min="50"
                  max="99"
                  class="input-field w-20"
                />
                <span class="text-secondary">%</span>
              </div>
            </div>
          </div>

          <template #footer>
            <div class="flex justify-end">
              <button
                @click="saveSettings('notifications')"
                :disabled="saving"
                class="btn-primary"
              >
                {{ saving ? 'Saving...' : 'Save Changes' }}
              </button>
            </div>
          </template>
        </Card>
      </div>

      <!-- Security Tab -->
      <div v-if="activeTab === 'security'" class="space-y-6">
        <Card title="Session Settings" :neon="true">
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <div class="flex-1">
                <p class="font-medium text-primary">Session Timeout</p>
                <p class="text-sm text-secondary">Minutes of inactivity before logout</p>
              </div>
              <div class="flex items-center gap-2 w-40 justify-end">
                <input
                  type="number"
                  v-model="settings.security.session_timeout"
                  min="5"
                  max="480"
                  class="input-field w-20 text-right"
                />
                <span class="text-secondary w-16">min</span>
              </div>
            </div>

            <div class="flex items-center justify-between">
              <div class="flex-1">
                <p class="font-medium text-primary">Max Login Attempts</p>
                <p class="text-sm text-secondary">Failed attempts before lockout</p>
              </div>
              <div class="flex items-center gap-2 w-40 justify-end">
                <input
                  type="number"
                  v-model="settings.security.max_login_attempts"
                  min="3"
                  max="10"
                  class="input-field w-20 text-right"
                />
                <span class="text-secondary w-16">attempts</span>
              </div>
            </div>

            <div class="flex items-center justify-between">
              <div class="flex-1">
                <p class="font-medium text-primary">Lockout Duration</p>
                <p class="text-sm text-secondary">Minutes to wait after lockout</p>
              </div>
              <div class="flex items-center gap-2 w-40 justify-end">
                <input
                  type="number"
                  v-model="settings.security.lockout_duration"
                  min="5"
                  max="60"
                  class="input-field w-20 text-right"
                />
                <span class="text-secondary w-16">min</span>
              </div>
            </div>
          </div>

          <template #footer>
            <div class="flex justify-end">
              <button
                @click="saveSettings('security')"
                :disabled="saving"
                class="btn-primary"
              >
                {{ saving ? 'Saving...' : 'Save Changes' }}
              </button>
            </div>
          </template>
        </Card>
      </div>

      <!-- Account Tab -->
      <div v-if="activeTab === 'account'" class="space-y-6">
        <Card title="Account Information" :neon="true">
          <div class="space-y-4">
            <div class="flex items-center gap-4">
              <div class="p-4 rounded-full bg-blue-100 dark:bg-blue-500/20">
                <UserIcon class="h-8 w-8 text-blue-500" />
              </div>
              <div>
                <p class="font-medium text-primary text-lg">{{ authStore.user?.username || 'Admin' }}</p>
                <p class="text-sm text-secondary">Administrator</p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Change Password" :neon="true">
          <form @submit.prevent="changePassword" class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-primary mb-1.5">Current Password</label>
              <div class="relative">
                <KeyIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted" />
                <input
                  v-model="passwordForm.current"
                  :type="showPasswords.current ? 'text' : 'password'"
                  placeholder="Enter current password"
                  class="input-field pl-10 pr-10 w-full"
                  required
                />
                <button
                  type="button"
                  @click="showPasswords.current = !showPasswords.current"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-secondary"
                >
                  <EyeSlashIcon v-if="showPasswords.current" class="h-5 w-5" />
                  <EyeIcon v-else class="h-5 w-5" />
                </button>
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-primary mb-1.5">New Password</label>
              <div class="relative">
                <KeyIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted" />
                <input
                  v-model="passwordForm.new"
                  :type="showPasswords.new ? 'text' : 'password'"
                  placeholder="Enter new password"
                  class="input-field pl-10 pr-10 w-full"
                  required
                  minlength="8"
                />
                <button
                  type="button"
                  @click="showPasswords.new = !showPasswords.new"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-secondary"
                >
                  <EyeSlashIcon v-if="showPasswords.new" class="h-5 w-5" />
                  <EyeIcon v-else class="h-5 w-5" />
                </button>
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-primary mb-1.5">Confirm New Password</label>
              <div class="relative">
                <KeyIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted" />
                <input
                  v-model="passwordForm.confirm"
                  :type="showPasswords.confirm ? 'text' : 'password'"
                  placeholder="Confirm new password"
                  class="input-field pl-10 pr-10 w-full"
                  required
                />
                <button
                  type="button"
                  @click="showPasswords.confirm = !showPasswords.confirm"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-secondary"
                >
                  <EyeSlashIcon v-if="showPasswords.confirm" class="h-5 w-5" />
                  <EyeIcon v-else class="h-5 w-5" />
                </button>
              </div>
            </div>

            <div class="pt-2">
              <button
                type="submit"
                :disabled="changingPassword"
                class="btn-primary"
              >
                {{ changingPassword ? 'Changing...' : 'Change Password' }}
              </button>
            </div>
          </form>
        </Card>
      </div>

      <!-- n8n API / Debug Tab -->
      <div v-if="activeTab === 'api-debug'" class="space-y-6">
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
      </div>
    </template>
  </div>
</template>
