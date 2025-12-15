<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
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
  ComputerDesktopIcon,
  SparklesIcon,
  GlobeAltIcon,
  PlusIcon,
  TrashIcon,
  ArrowPathIcon,
} from '@heroicons/vue/24/outline'

const themeStore = useThemeStore()
const authStore = useAuthStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const saving = ref(false)
const activeTab = ref('appearance')

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

// Access Control
const accessControl = ref({
  enabled: false,
  ip_ranges: [],
  nginx_config_path: '',
  last_updated: null,
})
const accessControlLoading = ref(false)
const reloadingNginx = ref(false)
const addingIpRange = ref(false)
const newIpRange = ref({
  cidr: '',
  description: '',
  access_level: 'internal',
})
const defaultIpRanges = ref([])
const deleteConfirmDialog = ref(null)
const ipRangeToDelete = ref(null)

// Theme presets
const themePresets = [
  {
    id: 'modern_light',
    name: 'Modern Light',
    description: 'Clean, minimal design with light colors',
    icon: SunIcon,
    preview: 'bg-white border-gray-200',
  },
  {
    id: 'modern_dark',
    name: 'Modern Dark',
    description: 'Sleek dark theme for reduced eye strain',
    icon: MoonIcon,
    preview: 'bg-gray-900 border-gray-700',
  },
  {
    id: 'dashboard_light',
    name: 'Dashboard Light',
    description: 'Sidebar layout with light theme',
    icon: ComputerDesktopIcon,
    preview: 'bg-gray-50 border-gray-200',
  },
  {
    id: 'dashboard_dark_neon',
    name: 'Cyberpunk Neon',
    description: 'Dark theme with neon glow effects',
    icon: SparklesIcon,
    preview: 'bg-gray-950 border-cyan-500',
  },
]

const tabs = [
  { id: 'appearance', name: 'Appearance', icon: PaintBrushIcon },
  { id: 'backup', name: 'Backup', icon: CircleStackIcon },
  { id: 'notifications', name: 'Notifications', icon: BellIcon },
  { id: 'security', name: 'Security', icon: ShieldCheckIcon },
  { id: 'access-control', name: 'Access Control', icon: GlobeAltIcon },
  { id: 'account', name: 'Account', icon: UserIcon },
]

async function loadSettings() {
  loading.value = true
  try {
    const response = await api.settings.getAll()
    if (response.data) {
      settings.value = { ...settings.value, ...response.data }
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
    await api.settings.update(section, settings.value[section])
    notificationStore.success('Settings saved successfully')
  } catch (error) {
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

function applyThemePreset(presetId) {
  themeStore.applyPreset(presetId)
  notificationStore.success('Theme applied')
}

// Access Control functions
async function loadAccessControl() {
  accessControlLoading.value = true
  try {
    const [configResponse, defaultsResponse] = await Promise.all([
      api.settings.getAccessControl(),
      api.settings.getDefaultIpRanges(),
    ])
    accessControl.value = configResponse.data
    defaultIpRanges.value = defaultsResponse.data
  } catch (error) {
    console.error('Failed to load access control:', error)
    notificationStore.error('Failed to load access control configuration')
  } finally {
    accessControlLoading.value = false
  }
}

async function addIpRange() {
  if (!newIpRange.value.cidr) {
    notificationStore.error('Please enter a CIDR address')
    return
  }

  addingIpRange.value = true
  try {
    await api.settings.addIpRange(newIpRange.value)
    notificationStore.success(`IP range ${newIpRange.value.cidr} added`)
    newIpRange.value = { cidr: '', description: '', access_level: 'internal' }
    await loadAccessControl()
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to add IP range')
  } finally {
    addingIpRange.value = false
  }
}

function confirmDeleteIpRange(ipRange) {
  ipRangeToDelete.value = ipRange
  deleteConfirmDialog.value?.open()
}

async function deleteIpRange() {
  if (!ipRangeToDelete.value) return

  try {
    await api.settings.deleteIpRange(ipRangeToDelete.value.cidr)
    notificationStore.success(`IP range ${ipRangeToDelete.value.cidr} deleted`)
    ipRangeToDelete.value = null
    await loadAccessControl()
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to delete IP range')
  }
}

async function reloadNginx() {
  reloadingNginx.value = true
  try {
    await api.settings.reloadNginx()
    notificationStore.success('Nginx reloaded successfully')
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to reload nginx')
  } finally {
    reloadingNginx.value = false
  }
}

function addDefaultRange(defaultRange) {
  // Check if already exists
  const exists = accessControl.value.ip_ranges.some(r => r.cidr === defaultRange.cidr)
  if (exists) {
    notificationStore.warning(`${defaultRange.cidr} is already configured`)
    return
  }

  // Pre-fill the form with default values
  newIpRange.value = {
    cidr: defaultRange.cidr,
    description: defaultRange.description,
    access_level: defaultRange.access_level,
  }
}

onMounted(loadSettings)

// Watch for tab changes to load access control data
watch(activeTab, (newTab) => {
  if (newTab === 'access-control' && accessControl.value.ip_ranges.length === 0) {
    loadAccessControl()
  }
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
        <Card title="Theme Presets" subtitle="Choose your preferred look and feel" :neon="true">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <button
              v-for="preset in themePresets"
              :key="preset.id"
              @click="applyThemePreset(preset.id)"
              :class="[
                'relative flex items-start gap-4 p-4 rounded-lg border-2 transition-all text-left',
                themeStore.currentPreset === preset.id
                  ? themeStore.isNeon
                    ? 'border-cyan-500 bg-cyan-500/10'
                    : 'border-blue-500 bg-blue-500/10'
                  : 'border-[var(--color-border)] hover:border-blue-300 dark:hover:border-blue-700'
              ]"
            >
              <div
                :class="[
                  'w-12 h-12 rounded-lg border-2 flex items-center justify-center',
                  preset.preview
                ]"
              >
                <component :is="preset.icon" class="h-6 w-6" />
              </div>
              <div class="flex-1">
                <p class="font-medium text-primary">{{ preset.name }}</p>
                <p class="text-sm text-secondary mt-0.5">{{ preset.description }}</p>
              </div>
              <CheckIcon
                v-if="themeStore.currentPreset === preset.id"
                :class="[
                  'h-5 w-5 absolute top-4 right-4',
                  themeStore.isNeon ? 'text-cyan-400' : 'text-blue-500'
                ]"
              />
            </button>
          </div>
        </Card>

        <Card title="Layout Options" :neon="true">
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Layout Style</p>
                <p class="text-sm text-secondary">Choose navigation layout</p>
              </div>
              <select v-model="themeStore.layout" class="select-field w-48">
                <option value="horizontal">Horizontal (Top Nav)</option>
                <option value="sidebar">Sidebar (Side Nav)</option>
              </select>
            </div>
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Color Mode</p>
                <p class="text-sm text-secondary">Light or dark appearance</p>
              </div>
              <select v-model="themeStore.colorMode" class="select-field w-48">
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </div>
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Neon Effects</p>
                <p class="text-sm text-secondary">Enable glowing neon effects (dark mode)</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  v-model="themeStore.neonEffects"
                  :disabled="themeStore.colorMode === 'light'"
                  class="sr-only peer"
                />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-cyan-500 peer-disabled:opacity-50"
                ></div>
              </label>
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
              <div>
                <p class="font-medium text-primary">Session Timeout</p>
                <p class="text-sm text-secondary">Minutes of inactivity before logout</p>
              </div>
              <div class="flex items-center gap-2">
                <input
                  type="number"
                  v-model="settings.security.session_timeout"
                  min="5"
                  max="480"
                  class="input-field w-24"
                />
                <span class="text-secondary">min</span>
              </div>
            </div>

            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Max Login Attempts</p>
                <p class="text-sm text-secondary">Failed attempts before lockout</p>
              </div>
              <input
                type="number"
                v-model="settings.security.max_login_attempts"
                min="3"
                max="10"
                class="input-field w-24"
              />
            </div>

            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Lockout Duration</p>
                <p class="text-sm text-secondary">Minutes to wait after lockout</p>
              </div>
              <div class="flex items-center gap-2">
                <input
                  type="number"
                  v-model="settings.security.lockout_duration"
                  min="5"
                  max="60"
                  class="input-field w-24"
                />
                <span class="text-secondary">min</span>
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

      <!-- Access Control Tab -->
      <div v-if="activeTab === 'access-control'" class="space-y-6">
        <LoadingSpinner v-if="accessControlLoading" size="lg" text="Loading access control..." class="py-12" />

        <template v-else>
          <!-- Status Card -->
          <Card title="Access Control Status" :neon="true">
            <div class="space-y-4">
              <div class="flex items-center justify-between">
                <div>
                  <p class="font-medium text-primary">Status</p>
                  <p class="text-sm text-secondary">IP-based access control via nginx geo block</p>
                </div>
                <span
                  :class="[
                    'px-3 py-1 rounded-full text-sm font-medium',
                    accessControl.enabled
                      ? 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400'
                      : 'bg-gray-100 text-gray-700 dark:bg-gray-500/20 dark:text-gray-400'
                  ]"
                >
                  {{ accessControl.enabled ? 'Enabled' : 'Not Configured' }}
                </span>
              </div>

              <div v-if="accessControl.last_updated" class="flex items-center justify-between">
                <div>
                  <p class="font-medium text-primary">Last Updated</p>
                  <p class="text-sm text-secondary">Configuration file modification time</p>
                </div>
                <span class="text-secondary text-sm">
                  {{ new Date(accessControl.last_updated).toLocaleString() }}
                </span>
              </div>
            </div>

            <template #footer>
              <div class="flex justify-end">
                <button
                  @click="reloadNginx"
                  :disabled="reloadingNginx"
                  class="btn-primary flex items-center gap-2"
                >
                  <ArrowPathIcon :class="['h-4 w-4', reloadingNginx && 'animate-spin']" />
                  {{ reloadingNginx ? 'Reloading...' : 'Reload Nginx' }}
                </button>
              </div>
            </template>
          </Card>

          <!-- Current IP Ranges -->
          <Card title="Configured IP Ranges" subtitle="Internal networks with privileged access" :neon="true">
            <div v-if="accessControl.ip_ranges.length === 0" class="text-center py-8 text-secondary">
              No IP ranges configured. Add ranges below or use defaults.
            </div>

            <div v-else class="space-y-2">
              <div
                v-for="(range, index) in accessControl.ip_ranges"
                :key="index"
                class="flex items-center justify-between p-3 rounded-lg bg-surface-hover"
              >
                <div class="flex-1">
                  <p class="font-mono text-primary">{{ range.cidr }}</p>
                  <p v-if="range.description" class="text-sm text-secondary">{{ range.description }}</p>
                </div>
                <div class="flex items-center gap-3">
                  <span
                    :class="[
                      'px-2 py-0.5 rounded text-xs font-medium',
                      range.access_level === 'internal'
                        ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400'
                        : 'bg-gray-100 text-gray-700 dark:bg-gray-500/20 dark:text-gray-400'
                    ]"
                  >
                    {{ range.access_level }}
                  </span>
                  <button
                    @click="confirmDeleteIpRange(range)"
                    class="p-1.5 text-red-500 hover:bg-red-100 dark:hover:bg-red-500/20 rounded"
                    title="Delete IP range"
                  >
                    <TrashIcon class="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          </Card>

          <!-- Add IP Range -->
          <Card title="Add IP Range" subtitle="Add a new IP range for internal access" :neon="true">
            <div class="space-y-4">
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label class="block text-sm font-medium text-primary mb-1.5">CIDR Address</label>
                  <input
                    type="text"
                    v-model="newIpRange.cidr"
                    placeholder="e.g., 192.168.1.0/24"
                    class="input-field w-full font-mono"
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-primary mb-1.5">Description</label>
                  <input
                    type="text"
                    v-model="newIpRange.description"
                    placeholder="e.g., Home Network"
                    class="input-field w-full"
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-primary mb-1.5">Access Level</label>
                  <select v-model="newIpRange.access_level" class="select-field w-full">
                    <option value="internal">Internal</option>
                    <option value="external">External</option>
                  </select>
                </div>
              </div>
            </div>

            <template #footer>
              <div class="flex justify-end">
                <button
                  @click="addIpRange"
                  :disabled="addingIpRange || !newIpRange.cidr"
                  class="btn-primary flex items-center gap-2"
                >
                  <PlusIcon class="h-4 w-4" />
                  {{ addingIpRange ? 'Adding...' : 'Add IP Range' }}
                </button>
              </div>
            </template>
          </Card>

          <!-- Default Ranges -->
          <Card title="Common Networks" subtitle="Quick-add common internal network ranges" :neon="true">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <button
                v-for="defaultRange in defaultIpRanges"
                :key="defaultRange.cidr"
                @click="addDefaultRange(defaultRange)"
                :class="[
                  'flex items-center justify-between p-3 rounded-lg border text-left transition-colors',
                  accessControl.ip_ranges.some(r => r.cidr === defaultRange.cidr)
                    ? 'border-green-500 bg-green-50 dark:bg-green-500/10'
                    : 'border-[var(--color-border)] hover:border-blue-300 dark:hover:border-blue-700 hover:bg-surface-hover'
                ]"
              >
                <div>
                  <p class="font-mono text-primary text-sm">{{ defaultRange.cidr }}</p>
                  <p class="text-xs text-secondary">{{ defaultRange.description }}</p>
                </div>
                <CheckIcon
                  v-if="accessControl.ip_ranges.some(r => r.cidr === defaultRange.cidr)"
                  class="h-5 w-5 text-green-500"
                />
                <PlusIcon v-else class="h-5 w-5 text-muted" />
              </button>
            </div>
          </Card>
        </template>

        <!-- Delete Confirmation Dialog -->
        <ConfirmDialog
          ref="deleteConfirmDialog"
          title="Delete IP Range"
          :message="`Are you sure you want to delete ${ipRangeToDelete?.cidr}? This will remove access for this network range.`"
          confirm-text="Delete"
          confirm-class="btn-danger"
          @confirm="deleteIpRange"
        />
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
    </template>
  </div>
</template>
