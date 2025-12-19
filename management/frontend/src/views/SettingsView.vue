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
import SystemNotificationsSettings from '@/components/settings/SystemNotificationsSettings.vue'
import {
  Cog6ToothIcon,
  PaintBrushIcon,
  ShieldCheckIcon,
  BellIcon,
  BellAlertIcon,
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
  GlobeAltIcon,
  PlusIcon,
  TrashIcon,
  ArrowPathIcon,
  LockClosedIcon,
  LockOpenIcon,
  CubeIcon,
  DocumentTextIcon,
  ChartBarIcon,
  FireIcon,
  HeartIcon,
  BoltIcon,
  LinkIcon,
  BeakerIcon,
  ServerIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  PencilIcon,
  XMarkIcon,
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

// Access Control state
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
const showDeleteConfirm = ref(false)
const ipRangeToDelete = ref(null)
const cloudflareInstalled = ref(false)
const cloudflareRunning = ref(false)

// External Routes state
const externalRoutes = ref({
  routes: [],
  domain: null,
  last_updated: null,
})
const externalRoutesLoading = ref(false)
const addingExternalRoute = ref(false)
const newExternalRoute = ref({
  path: '',
  description: '',
  upstream: 'n8n',
  upstream_port: null,
  is_public: true,
})
const showDeleteRouteConfirm = ref(false)
const routeToDelete = ref(null)

// IP Range editing state
const editingIpRangeIndex = ref(null)
const editingIpRangeDescription = ref('')
const savingIpRangeDescription = ref(false)

// Collapsible state for sections and individual items
const routesSectionExpanded = ref(false)
const ipRangesSectionExpanded = ref(false)
const expandedRoutes = ref(new Set())
const expandedIpRanges = ref(new Set())

function toggleRoutesSection() {
  routesSectionExpanded.value = !routesSectionExpanded.value
}

function toggleIpRangesSection() {
  ipRangesSectionExpanded.value = !ipRangesSectionExpanded.value
}

function toggleRouteExpanded(index) {
  if (expandedRoutes.value.has(index)) {
    expandedRoutes.value.delete(index)
  } else {
    expandedRoutes.value.add(index)
  }
  // Force reactivity
  expandedRoutes.value = new Set(expandedRoutes.value)
}

function toggleIpRangeExpanded(index) {
  if (expandedIpRanges.value.has(index)) {
    expandedIpRanges.value.delete(index)
  } else {
    expandedIpRanges.value.add(index)
  }
  // Force reactivity
  expandedIpRanges.value = new Set(expandedIpRanges.value)
}

function expandAllRoutes() {
  externalRoutes.value.routes.forEach((_, index) => expandedRoutes.value.add(index))
  expandedRoutes.value = new Set(expandedRoutes.value)
}

function collapseAllRoutes() {
  expandedRoutes.value.clear()
  expandedRoutes.value = new Set(expandedRoutes.value)
}

function expandAllIpRanges() {
  accessControl.value.ip_ranges.forEach((_, index) => expandedIpRanges.value.add(index))
  expandedIpRanges.value = new Set(expandedIpRanges.value)
}

function collapseAllIpRanges() {
  expandedIpRanges.value.clear()
  expandedIpRanges.value = new Set(expandedIpRanges.value)
}

// Filter out already-configured ranges from the defaults list
const availableDefaultRanges = computed(() => {
  const configuredCidrs = accessControl.value.ip_ranges.map(r => r.cidr)
  return defaultIpRanges.value.filter(d => !configuredCidrs.includes(d.cidr))
})

// No longer using theme presets - removed in favor of simpler light/dark toggle

const tabs = [
  { id: 'appearance', name: 'Appearance', icon: PaintBrushIcon, iconColor: 'text-pink-500', bgActive: 'bg-pink-500/15 dark:bg-pink-500/20', textActive: 'text-pink-700 dark:text-pink-400', borderActive: 'border-pink-500/30' },
  { id: 'notifications', name: 'System Notifications', icon: BellIcon, iconColor: 'text-amber-500', bgActive: 'bg-amber-500/15 dark:bg-amber-500/20', textActive: 'text-amber-700 dark:text-amber-400', borderActive: 'border-amber-500/30' },
  { id: 'security', name: 'Security', icon: ShieldCheckIcon, iconColor: 'text-red-500', bgActive: 'bg-red-500/15 dark:bg-red-500/20', textActive: 'text-red-700 dark:text-red-400', borderActive: 'border-red-500/30' },
  { id: 'access-control', name: 'Access Control', icon: GlobeAltIcon, iconColor: 'text-blue-500', bgActive: 'bg-blue-500/15 dark:bg-blue-500/20', textActive: 'text-blue-700 dark:text-blue-400', borderActive: 'border-blue-500/30' },
  { id: 'account', name: 'Account', icon: UserIcon, iconColor: 'text-purple-500', bgActive: 'bg-purple-500/15 dark:bg-purple-500/20', textActive: 'text-purple-700 dark:text-purple-400', borderActive: 'border-purple-500/30' },
  { id: 'api-debug', name: 'n8n API / Debug', icon: BugAntIcon, iconColor: 'text-cyan-500', bgActive: 'bg-cyan-500/15 dark:bg-cyan-500/20', textActive: 'text-cyan-700 dark:text-cyan-400', borderActive: 'border-cyan-500/30' },
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

// Access Control functions
async function loadAccessControl() {
  accessControlLoading.value = true
  try {
    // Load defaults first - this should always work
    try {
      const defaultsResponse = await api.settings.getDefaultIpRanges()
      defaultIpRanges.value = defaultsResponse.data
    } catch (e) {
      console.error('Failed to load default IP ranges:', e)
    }

    // Load current config - may fail if nginx config doesn't exist
    try {
      const configResponse = await api.settings.getAccessControl()
      accessControl.value = configResponse.data
    } catch (e) {
      console.error('Failed to load access control config:', e)
      // Set defaults if config load fails
      accessControl.value = {
        enabled: false,
        ip_ranges: [],
        nginx_config_path: '',
        last_updated: null,
      }
    }

    // Check if Cloudflare tunnel is installed/running
    try {
      const cfResponse = await api.system.cloudflare()
      cloudflareInstalled.value = cfResponse.data?.installed || false
      cloudflareRunning.value = cfResponse.data?.running || false
    } catch (e) {
      cloudflareInstalled.value = false
      cloudflareRunning.value = false
    }

    // Also load external routes
    loadExternalRoutes()
  } catch (error) {
    console.error('Failed to load access control:', error)
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
  showDeleteConfirm.value = true
}

async function deleteIpRange() {
  if (!ipRangeToDelete.value) return

  try {
    await api.settings.deleteIpRange(ipRangeToDelete.value.cidr)
    notificationStore.success(`IP range ${ipRangeToDelete.value.cidr} deleted`)
    ipRangeToDelete.value = null
    showDeleteConfirm.value = false
    await loadAccessControl()
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to delete IP range')
    showDeleteConfirm.value = false
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
  const exists = accessControl.value.ip_ranges.some(r => r.cidr === defaultRange.cidr)
  if (exists) {
    notificationStore.warning(`${defaultRange.cidr} is already configured`)
    return
  }
  newIpRange.value = {
    cidr: defaultRange.cidr,
    description: defaultRange.description,
    access_level: defaultRange.access_level,
  }
}

function startEditIpRangeDescription(index, currentDescription) {
  editingIpRangeIndex.value = index
  editingIpRangeDescription.value = currentDescription || ''
}

function cancelEditIpRangeDescription() {
  editingIpRangeIndex.value = null
  editingIpRangeDescription.value = ''
}

async function saveIpRangeDescription(cidr) {
  savingIpRangeDescription.value = true
  try {
    await api.settings.updateIpRange(cidr, editingIpRangeDescription.value)
    notificationStore.success('Description updated successfully')
    editingIpRangeIndex.value = null
    editingIpRangeDescription.value = ''
    await loadAccessControl()
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to update description')
  } finally {
    savingIpRangeDescription.value = false
  }
}

// External Routes functions
async function loadExternalRoutes() {
  externalRoutesLoading.value = true
  try {
    const response = await api.settings.getExternalRoutes()
    externalRoutes.value = response.data
  } catch (error) {
    console.error('Failed to load external routes:', error)
    externalRoutes.value = { routes: [], domain: null, last_updated: null }
  } finally {
    externalRoutesLoading.value = false
  }
}

async function addExternalRoute() {
  if (!newExternalRoute.value.path) {
    notificationStore.error('Please enter a path')
    return
  }

  // Validate upstream port if provided
  if (newExternalRoute.value.upstream_port && (newExternalRoute.value.upstream_port < 1 || newExternalRoute.value.upstream_port > 65535)) {
    notificationStore.error('Port must be between 1 and 65535')
    return
  }

  addingExternalRoute.value = true
  try {
    await api.settings.addExternalRoute(newExternalRoute.value)
    const accessType = newExternalRoute.value.is_public ? 'public' : 'restricted'
    notificationStore.success(`External route ${newExternalRoute.value.path} added (${accessType}). Reload nginx to apply.`)
    newExternalRoute.value = { path: '', description: '', upstream: 'n8n', upstream_port: null, is_public: true }
    await loadExternalRoutes()
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to add external route')
  } finally {
    addingExternalRoute.value = false
  }
}

function confirmDeleteRoute(route) {
  routeToDelete.value = route
  showDeleteRouteConfirm.value = true
}

async function deleteExternalRoute() {
  if (!routeToDelete.value) return

  try {
    await api.settings.deleteExternalRoute(routeToDelete.value.path)
    notificationStore.success(`External route ${routeToDelete.value.path} removed. Reload nginx to apply.`)
    routeToDelete.value = null
    showDeleteRouteConfirm.value = false
    await loadExternalRoutes()
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to delete external route')
    showDeleteRouteConfirm.value = false
  }
}

// Icon mapping for routes
const iconMap = {
  'webhook': BoltIcon,
  'flask': BeakerIcon,
  'cube': CubeIcon,
  'database': CircleStackIcon,
  'document-text': DocumentTextIcon,
  'chart-bar': ChartBarIcon,
  'fire': FireIcon,
  'cog': Cog6ToothIcon,
  'heart': HeartIcon,
  'bolt': BoltIcon,
  'link': LinkIcon,
  'server': ServerIcon,
  'bell': BellAlertIcon,
}

// Color mapping for background
const colorBgMap = {
  'green': 'rgba(34, 197, 94, 0.15)',
  'amber': 'rgba(245, 158, 11, 0.15)',
  'blue': 'rgba(59, 130, 246, 0.15)',
  'purple': 'rgba(168, 85, 247, 0.15)',
  'emerald': 'rgba(16, 185, 129, 0.15)',
  'orange': 'rgba(249, 115, 22, 0.15)',
  'red': 'rgba(239, 68, 68, 0.15)',
  'cyan': 'rgba(6, 182, 212, 0.15)',
  'rose': 'rgba(244, 63, 94, 0.15)',
  'gray': 'rgba(107, 114, 128, 0.15)',
}

// Color mapping for icon
const colorIconMap = {
  'green': '#22c55e',
  'amber': '#f59e0b',
  'blue': '#3b82f6',
  'purple': '#a855f7',
  'emerald': '#10b981',
  'orange': '#f97316',
  'red': '#ef4444',
  'cyan': '#06b6d4',
  'rose': '#f43f5e',
  'gray': '#6b7280',
}

function getRouteIcon(iconName) {
  return iconMap[iconName] || LinkIcon
}

function getRouteIconBg(color) {
  return colorBgMap[color] || colorBgMap['gray']
}

function getRouteIconColor(color) {
  return colorIconMap[color] || colorIconMap['gray']
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    notificationStore.success('URL copied to clipboard')
  }).catch(() => {
    notificationStore.error('Failed to copy to clipboard')
  })
}

onMounted(async () => {
  await loadSettings()
})

// Watch for tab changes to load access control data
watch(activeTab, (newTab) => {
  if (newTab === 'access-control' && defaultIpRanges.value.length === 0) {
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
      <!-- Tabs - Matching style with colored icons -->
      <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-400 dark:border-gray-700 p-1.5 flex gap-1.5 overflow-x-auto">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="[
            'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap border',
            activeTab === tab.id
              ? `${tab.bgActive} ${tab.textActive} ${tab.borderActive}`
              : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700/50 border-transparent'
          ]"
        >
          <component :is="tab.icon" :class="['h-4 w-4', activeTab === tab.id ? '' : tab.iconColor]" />
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
                  : 'border-gray-400 hover:border-gray-400'
              ]"
              @click="selectTheme('light')"
            >
              <!-- Preview Area -->
              <div class="bg-white p-4 border-b border-gray-400">
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
                  <div class="flex items-center gap-2 bg-white rounded-lg p-1 border border-gray-400">
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
                  : 'border-gray-400 hover:border-gray-400'
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

      <!-- Notifications Tab -->
      <div v-if="activeTab === 'notifications'">
        <SystemNotificationsSettings />
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

      <!-- Access Control Tab -->
      <div v-if="activeTab === 'access-control'" class="space-y-6">
        <LoadingSpinner v-if="accessControlLoading" size="lg" text="Loading access control..." class="py-12" />

        <template v-else>
          <!-- External Access Info (show if Cloudflare tunnel is configured) -->
          <div
            v-if="cloudflareInstalled"
            :class="[
              'rounded-lg p-4 border',
              cloudflareRunning
                ? 'bg-green-50 dark:bg-green-500/10 border-green-200 dark:border-green-500/30'
                : 'bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/30'
            ]"
          >
            <div class="flex gap-3">
              <GlobeAltIcon :class="['h-5 w-5 flex-shrink-0 mt-0.5', cloudflareRunning ? 'text-green-500' : 'text-red-500']" />
              <div>
                <p :class="['font-medium', cloudflareRunning ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400']">
                  External Access via Cloudflare Tunnel
                  <span v-if="!cloudflareRunning" class="ml-2 text-xs font-normal px-2 py-0.5 bg-red-100 dark:bg-red-500/20 rounded">
                    DOWN
                  </span>
                </p>
                <p v-if="cloudflareRunning" class="text-sm text-green-600 dark:text-green-300 mt-1">
                  External users access your services through Cloudflare Tunnel. Traffic arrives from the internal Docker network,
                  bypassing IP-based restrictions. The IP ranges below control direct network access only.
                </p>
                <p v-else class="text-sm text-red-600 dark:text-red-300 mt-1">
                  Cloudflare Tunnel is configured but currently not running. External access may be unavailable.
                  Check the System page for tunnel status.
                </p>
              </div>
            </div>
          </div>

          <!-- Nginx Routes Section - Collapsible Card -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-400 dark:border-gray-700 shadow-sm hover:shadow-md transition-all overflow-hidden">
            <!-- Section Header (clickable) -->
            <div
              @click="toggleRoutesSection"
              class="flex items-center gap-4 p-5 cursor-pointer"
            >
              <!-- Icon -->
              <div class="flex-shrink-0 w-12 h-12 rounded-full bg-emerald-50 dark:bg-emerald-500/10 flex items-center justify-center">
                <ServerIcon class="h-6 w-6 text-emerald-500" />
              </div>

              <!-- Title and Description -->
              <div class="flex-1 min-w-0">
                <p class="font-semibold text-gray-900 dark:text-white text-lg">Nginx Routes</p>
                <p class="text-sm text-gray-500 dark:text-gray-400">All configured routes and their access levels</p>
              </div>

              <!-- Count Badge -->
              <span class="flex-shrink-0 px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
                {{ externalRoutes.routes.length }} routes
              </span>

              <!-- Chevron -->
              <ChevronRightIcon
                :class="[
                  'h-5 w-5 text-gray-400 transition-transform duration-200',
                  routesSectionExpanded ? 'rotate-90' : ''
                ]"
              />
            </div>

            <!-- Expanded Content -->
            <Transition name="section-expand">
              <div v-if="routesSectionExpanded" class="border-t border-gray-100 dark:border-gray-700">
                <div class="p-5">
                  <LoadingSpinner v-if="externalRoutesLoading" size="sm" text="Loading routes..." class="py-4" />

                  <template v-else>
                    <!-- Domain Info -->
                    <div v-if="externalRoutes.domain" class="mb-4 p-3 rounded-lg bg-gradient-to-r from-blue-50 to-cyan-50 dark:from-blue-900/20 dark:to-cyan-900/20 border border-blue-200 dark:border-blue-800">
                      <div class="flex items-center gap-2">
                        <GlobeAltIcon class="h-5 w-5 text-blue-500" />
                        <span class="text-sm text-secondary">Domain:</span>
                        <span class="font-mono text-primary font-medium">{{ externalRoutes.domain }}</span>
                      </div>
                    </div>

                    <!-- Legend -->
                    <div class="flex flex-wrap gap-4 mb-4 text-xs">
                      <div class="flex items-center gap-1.5">
                        <span class="w-2 h-2 rounded-full bg-green-500"></span>
                        <span class="text-secondary">Public (No Auth)</span>
                      </div>
                      <div class="flex items-center gap-1.5">
                        <span class="w-2 h-2 rounded-full bg-amber-500"></span>
                        <span class="text-secondary">SSO Protected</span>
                      </div>
                      <div class="flex items-center gap-1.5">
                        <span class="w-2 h-2 rounded-full bg-red-500"></span>
                        <span class="text-secondary">IP Restricted</span>
                      </div>
                    </div>

                    <div v-if="externalRoutes.routes.length === 0" class="text-center py-6 text-secondary">
                      No routes found in nginx configuration.
                    </div>

                    <!-- Routes List -->
                    <div v-else class="space-y-2 mb-4">
                      <div
                        v-for="(route, index) in externalRoutes.routes"
                        :key="index"
                        class="bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-400 dark:border-gray-700 overflow-hidden"
                      >
                        <!-- Route Header -->
                        <div
                          @click="toggleRouteExpanded(index)"
                          class="flex items-center gap-3 p-3 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                        >
                          <!-- Icon -->
                          <div
                            class="flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center"
                            :style="{ backgroundColor: getRouteIconBg(route.color) }"
                          >
                            <component
                              :is="getRouteIcon(route.icon)"
                              class="h-4 w-4"
                              :style="{ color: getRouteIconColor(route.color) }"
                            />
                          </div>

                          <!-- Path -->
                          <div class="flex-1 min-w-0 flex items-center gap-2">
                            <p class="font-medium text-gray-900 dark:text-white font-mono text-sm">{{ route.path }}</p>
                            <span
                              v-if="route.protected"
                              class="text-xs px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded"
                            >
                              System
                            </span>
                          </div>

                          <!-- Status Badge -->
                          <span
                            :class="[
                              'flex-shrink-0 px-2 py-0.5 rounded-full text-xs font-medium',
                              route.is_public
                                ? 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400'
                                : route.has_auth
                                  ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400'
                                  : 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400'
                            ]"
                          >
                            {{ route.is_public ? 'Public' : route.has_auth ? 'SSO' : 'Restricted' }}
                          </span>

                          <!-- Chevron -->
                          <ChevronRightIcon
                            :class="[
                              'h-4 w-4 text-gray-400 transition-transform duration-200',
                              expandedRoutes.has(index) ? 'rotate-90' : ''
                            ]"
                          />
                        </div>

                        <!-- Route Details -->
                        <Transition name="expand">
                          <div v-if="expandedRoutes.has(index)" class="px-3 pb-3 pt-1 border-t border-gray-400 dark:border-gray-700 bg-white dark:bg-gray-800">
                            <div class="space-y-2 text-sm">
                              <p class="text-gray-600 dark:text-gray-300">{{ route.description }}</p>

                              <div v-if="externalRoutes.domain" class="flex items-center gap-2 flex-wrap">
                                <span class="text-gray-500 dark:text-gray-400">URL:</span>
                                <code class="text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded font-mono text-xs">
                                  https://{{ externalRoutes.domain }}{{ route.path }}
                                </code>
                                <button
                                  @click.stop="copyToClipboard(`https://${externalRoutes.domain}${route.path}`)"
                                  class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded transition-colors"
                                  title="Copy URL"
                                >
                                  <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                  </svg>
                                </button>
                              </div>

                              <div class="flex items-center gap-2">
                                <span class="text-gray-500 dark:text-gray-400">Upstream:</span>
                                <span class="font-mono text-gray-900 dark:text-white">
                                  {{ route.proxy_target }}{{ route.proxy_port ? `:${route.proxy_port}` : '' }}
                                </span>
                              </div>

                              <div v-if="route.manageable && !route.protected" class="pt-1">
                                <button
                                  @click.stop="confirmDeleteRoute(route)"
                                  class="text-xs text-red-500 hover:text-red-600 flex items-center gap-1"
                                >
                                  <TrashIcon class="h-3 w-3" />
                                  Remove route
                                </button>
                              </div>
                            </div>
                          </div>
                        </Transition>
                      </div>
                    </div>

                    <!-- Add Route Form -->
                    <div class="border-t border-gray-400 dark:border-gray-700 pt-4 mt-4">
                      <div class="flex items-center gap-2 mb-3">
                        <PlusIcon class="h-5 w-5 text-green-500" />
                        <p class="text-sm font-medium text-primary">Add New Route</p>
                      </div>
                      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        <div>
                          <label class="block text-sm text-secondary mb-1.5">Path *</label>
                          <input
                            type="text"
                            v-model="newExternalRoute.path"
                            placeholder="/ntfy/, /myservice/"
                            class="input-field w-full font-mono"
                            @click.stop
                          />
                          <p class="text-xs text-muted mt-1">Any path except /api, /admin, /config</p>
                        </div>
                        <div>
                          <label class="block text-sm text-secondary mb-1.5">Upstream Server</label>
                          <input
                            type="text"
                            v-model="newExternalRoute.upstream"
                            placeholder="n8n"
                            class="input-field w-full font-mono"
                            @click.stop
                          />
                          <p class="text-xs text-muted mt-1">Service name (e.g., n8n, n8n_ntfy)</p>
                        </div>
                        <div>
                          <label class="block text-sm text-secondary mb-1.5">Upstream Port</label>
                          <input
                            type="number"
                            v-model.number="newExternalRoute.upstream_port"
                            placeholder="Optional (e.g., 8085)"
                            class="input-field w-full font-mono"
                            min="1"
                            max="65535"
                            @click.stop
                          />
                          <p class="text-xs text-muted mt-1">Leave empty to use upstream name</p>
                        </div>
                        <div class="md:col-span-2 lg:col-span-2">
                          <label class="block text-sm text-secondary mb-1.5">Description</label>
                          <input
                            type="text"
                            v-model="newExternalRoute.description"
                            placeholder="NTFY push notification server"
                            class="input-field w-full"
                            @click.stop
                          />
                        </div>
                        <div>
                          <label class="block text-sm text-secondary mb-1.5">Access Level</label>
                          <div class="flex gap-4 mt-2">
                            <label class="flex items-center gap-2 cursor-pointer">
                              <input
                                type="radio"
                                v-model="newExternalRoute.is_public"
                                :value="true"
                                class="w-4 h-4 text-green-500 focus:ring-green-500"
                                @click.stop
                              />
                              <span class="text-sm text-primary flex items-center gap-1">
                                <LockOpenIcon class="h-4 w-4 text-green-500" />
                                Public
                              </span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer">
                              <input
                                type="radio"
                                v-model="newExternalRoute.is_public"
                                :value="false"
                                class="w-4 h-4 text-red-500 focus:ring-red-500"
                                @click.stop
                              />
                              <span class="text-sm text-primary flex items-center gap-1">
                                <LockClosedIcon class="h-4 w-4 text-red-500" />
                                Restricted (IP check)
                              </span>
                            </label>
                          </div>
                        </div>
                      </div>
                      <div class="flex justify-end mt-4">
                        <button
                          @click.stop="addExternalRoute"
                          :disabled="addingExternalRoute || !newExternalRoute.path"
                          class="btn-primary flex items-center gap-2"
                        >
                          <PlusIcon class="h-4 w-4" />
                          {{ addingExternalRoute ? 'Adding...' : 'Add Route' }}
                        </button>
                      </div>
                    </div>
                  </template>
                </div>
              </div>
            </Transition>
          </div>

          <!-- Configured IP Ranges - Collapsible Card -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-400 dark:border-gray-700 shadow-sm hover:shadow-md transition-all overflow-hidden">
            <!-- Section Header (clickable) -->
            <div
              @click="toggleIpRangesSection"
              class="flex items-center gap-4 p-5 cursor-pointer"
            >
              <!-- Icon -->
              <div class="flex-shrink-0 w-12 h-12 rounded-full bg-blue-50 dark:bg-blue-500/10 flex items-center justify-center">
                <GlobeAltIcon class="h-6 w-6 text-blue-500" />
              </div>

              <!-- Title and Description -->
              <div class="flex-1 min-w-0">
                <p class="font-semibold text-gray-900 dark:text-white text-lg">IP Ranges (Direct Access)</p>
                <p class="text-sm text-gray-500 dark:text-gray-400">Networks allowed to bypass IP restrictions</p>
              </div>

              <!-- Status Badge -->
              <span
                :class="[
                  'flex-shrink-0 px-3 py-1 rounded-full text-xs font-medium',
                  accessControl.enabled
                    ? 'bg-green-50 text-green-600 dark:bg-green-500/10 dark:text-green-400'
                    : 'bg-gray-50 text-gray-600 dark:bg-gray-500/10 dark:text-gray-400'
                ]"
              >
                {{ accessControl.enabled ? 'Active' : 'Not Configured' }}
              </span>

              <!-- Count Badge -->
              <span class="flex-shrink-0 px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                {{ accessControl.ip_ranges.length }} ranges
              </span>

              <!-- Chevron -->
              <ChevronRightIcon
                :class="[
                  'h-5 w-5 text-gray-400 transition-transform duration-200',
                  ipRangesSectionExpanded ? 'rotate-90' : ''
                ]"
              />
            </div>

            <!-- Expanded Content -->
            <Transition name="section-expand">
              <div v-if="ipRangesSectionExpanded" class="border-t border-gray-100 dark:border-gray-700">
                <div class="p-5">
                  <!-- Status Info and Reload Button -->
                  <div class="flex items-center justify-between mb-4 pb-4 border-b border-gray-400 dark:border-gray-700">
                    <div class="text-sm text-gray-500 dark:text-gray-400">
                      <span v-if="accessControl.last_updated">
                        Last updated: {{ new Date(accessControl.last_updated).toLocaleString() }}
                      </span>
                      <span v-else>Configuration not yet saved</span>
                    </div>
                    <button
                      @click.stop="reloadNginx"
                      :disabled="reloadingNginx"
                      class="btn-secondary text-sm flex items-center gap-2"
                    >
                      <ArrowPathIcon :class="['h-4 w-4', reloadingNginx && 'animate-spin']" />
                      {{ reloadingNginx ? 'Reloading...' : 'Reload Nginx' }}
                    </button>
                  </div>

                  <div v-if="accessControl.ip_ranges.length === 0" class="text-center py-6 text-secondary">
                    No IP ranges configured. Add ranges below or use defaults.
                  </div>

                  <!-- IP Ranges List -->
                  <div v-else class="space-y-2 mb-4">
                    <div
                      v-for="(range, index) in accessControl.ip_ranges"
                      :key="index"
                      class="bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-400 dark:border-gray-700 overflow-hidden"
                    >
                      <!-- Range Header -->
                      <div
                        @click="toggleIpRangeExpanded(index)"
                        class="flex items-center gap-3 p-3 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                      >
                        <!-- Icon -->
                        <div
                          :class="[
                            'flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center',
                            range.protected
                              ? 'bg-gray-200 dark:bg-gray-700'
                              : range.access_level === 'external'
                                ? 'bg-purple-100 dark:bg-purple-500/20'
                                : 'bg-blue-100 dark:bg-blue-500/20'
                          ]"
                        >
                          <GlobeAltIcon
                            :class="[
                              'h-4 w-4',
                              range.protected
                                ? 'text-gray-500'
                                : range.access_level === 'external'
                                  ? 'text-purple-500'
                                  : 'text-blue-500'
                            ]"
                          />
                        </div>

                        <!-- CIDR -->
                        <div class="flex-1 min-w-0 flex items-center gap-2">
                          <p class="font-medium text-gray-900 dark:text-white font-mono text-sm">{{ range.cidr }}</p>
                          <span
                            v-if="range.protected"
                            class="text-xs px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded"
                          >
                            System
                          </span>
                        </div>

                        <!-- Status Badge -->
                        <span
                          :class="[
                            'flex-shrink-0 px-2 py-0.5 rounded-full text-xs font-medium',
                            range.access_level === 'external'
                              ? 'bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-400'
                              : 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400'
                          ]"
                        >
                          {{ range.access_level === 'external' ? 'External' : 'Internal' }}
                        </span>

                        <!-- Delete button (inline for non-protected) -->
                        <button
                          v-if="!range.protected"
                          @click.stop="confirmDeleteIpRange(range)"
                          class="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors"
                          title="Delete IP range"
                        >
                          <TrashIcon class="h-4 w-4" />
                        </button>
                        <LockClosedIcon v-else class="h-4 w-4 text-gray-400" />

                        <!-- Chevron -->
                        <ChevronRightIcon
                          :class="[
                            'h-4 w-4 text-gray-400 transition-transform duration-200',
                            expandedIpRanges.has(index) ? 'rotate-90' : ''
                          ]"
                        />
                      </div>

                      <!-- Range Details -->
                      <Transition name="expand">
                        <div v-if="expandedIpRanges.has(index)" class="px-3 pb-3 pt-1 border-t border-gray-400 dark:border-gray-700 bg-white dark:bg-gray-800">
                          <div class="space-y-2 text-sm">
                            <!-- Description with edit capability -->
                            <div v-if="editingIpRangeIndex === index" class="space-y-2">
                              <label class="block text-xs text-gray-500 dark:text-gray-400">Description</label>
                              <input
                                type="text"
                                v-model="editingIpRangeDescription"
                                class="input-field w-full text-sm"
                                placeholder="Enter description..."
                                @click.stop
                                @keyup.enter="saveIpRangeDescription(range.cidr)"
                                @keyup.escape="cancelEditIpRangeDescription"
                              />
                              <div class="flex items-center gap-2">
                                <button
                                  @click.stop="saveIpRangeDescription(range.cidr)"
                                  :disabled="savingIpRangeDescription"
                                  class="text-xs px-2 py-1 rounded bg-blue-500 hover:bg-blue-600 text-white flex items-center gap-1"
                                >
                                  <CheckIcon class="h-3 w-3" />
                                  {{ savingIpRangeDescription ? 'Saving...' : 'Save' }}
                                </button>
                                <button
                                  @click.stop="cancelEditIpRangeDescription"
                                  :disabled="savingIpRangeDescription"
                                  class="text-xs px-2 py-1 rounded bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 flex items-center gap-1"
                                >
                                  <XMarkIcon class="h-3 w-3" />
                                  Cancel
                                </button>
                              </div>
                            </div>
                            <div v-else class="flex items-start justify-between gap-2">
                              <p class="text-gray-600 dark:text-gray-300 flex-1">
                                {{ range.description || 'No description provided' }}
                              </p>
                              <button
                                @click.stop="startEditIpRangeDescription(index, range.description)"
                                class="p-1 text-gray-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-500/10 rounded transition-colors flex-shrink-0"
                                title="Edit description"
                              >
                                <PencilIcon class="h-4 w-4" />
                              </button>
                            </div>
                            <div class="flex items-center gap-2">
                              <span class="text-gray-500 dark:text-gray-400">Type:</span>
                              <span class="text-gray-900 dark:text-white">
                                {{ range.access_level === 'external' ? 'External network' : 'Internal/trusted network' }}
                              </span>
                            </div>
                            <div v-if="range.protected" class="flex items-center gap-2 text-amber-600 dark:text-amber-400">
                              <LockClosedIcon class="h-4 w-4" />
                              <span>System protected - required for functionality</span>
                            </div>
                          </div>
                        </div>
                      </Transition>
                    </div>
                  </div>

                  <!-- Add IP Range Form -->
                  <div class="border-t border-gray-400 dark:border-gray-700 pt-4 mt-4">
                    <div class="flex items-center gap-2 mb-3">
                      <PlusIcon class="h-5 w-5 text-blue-500" />
                      <p class="text-sm font-medium text-primary">Add New IP Range</p>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <label class="block text-sm text-secondary mb-1.5">CIDR Address</label>
                        <input
                          type="text"
                          v-model="newIpRange.cidr"
                          placeholder="e.g., 192.168.1.0/24"
                          class="input-field w-full font-mono"
                          @click.stop
                        />
                      </div>
                      <div>
                        <label class="block text-sm text-secondary mb-1.5">Description</label>
                        <input
                          type="text"
                          v-model="newIpRange.description"
                          placeholder="e.g., Home Network"
                          class="input-field w-full"
                          @click.stop
                        />
                      </div>
                      <div>
                        <label class="block text-sm text-secondary mb-1.5">Access Level</label>
                        <select v-model="newIpRange.access_level" class="select-field w-full" @click.stop>
                          <option value="internal">Internal</option>
                          <option value="external">External</option>
                        </select>
                      </div>
                    </div>
                    <div class="flex justify-end mt-4">
                      <button
                        @click.stop="addIpRange"
                        :disabled="addingIpRange || !newIpRange.cidr"
                        class="btn-primary flex items-center gap-2"
                      >
                        <PlusIcon class="h-4 w-4" />
                        {{ addingIpRange ? 'Adding...' : 'Add IP Range' }}
                      </button>
                    </div>
                  </div>

                  <!-- Quick Add Common Networks -->
                  <div v-if="availableDefaultRanges.length > 0" class="border-t border-gray-400 dark:border-gray-700 pt-4 mt-4">
                    <div class="flex items-center gap-2 mb-3">
                      <BoltIcon class="h-5 w-5 text-amber-500" />
                      <p class="text-sm font-medium text-primary">Quick Add Common Networks</p>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                      <button
                        v-for="defaultRange in availableDefaultRanges"
                        :key="defaultRange.cidr"
                        @click.stop="addDefaultRange(defaultRange)"
                        class="flex items-center justify-between p-3 rounded-lg border text-left transition-colors border-gray-400 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600 hover:bg-blue-50 dark:hover:bg-blue-500/10"
                      >
                        <div>
                          <p class="font-mono text-gray-900 dark:text-white text-sm">{{ defaultRange.cidr }}</p>
                          <p class="text-xs text-gray-500 dark:text-gray-400">{{ defaultRange.description }}</p>
                        </div>
                        <PlusIcon class="h-5 w-5 text-gray-400" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </Transition>
          </div>
        </template>

        <!-- Delete IP Range Confirmation Dialog -->
        <ConfirmDialog
          v-model:open="showDeleteConfirm"
          title="Delete IP Range"
          :message="`Are you sure you want to delete ${ipRangeToDelete?.cidr}? This will remove access for this network range.`"
          confirm-text="Delete"
          :danger="true"
          @confirm="deleteIpRange"
        />

        <!-- Delete External Route Confirmation Dialog -->
        <ConfirmDialog
          v-model:open="showDeleteRouteConfirm"
          title="Remove External Route"
          :message="`Are you sure you want to remove ${routeToDelete?.path}? This path will no longer be publicly accessible.`"
          confirm-text="Remove"
          :danger="true"
          @confirm="deleteExternalRoute"
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
                      'after:bg-white after:border-gray-400 after:border after:rounded-full',
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

              <div v-else class="mt-4 p-3 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-400 dark:border-gray-700">
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

<style scoped>
/* Section expand/collapse transitions (for main collapsible cards) */
.section-expand-enter-active,
.section-expand-leave-active {
  transition: all 0.3s ease-out;
  overflow: hidden;
}

.section-expand-enter-from,
.section-expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.section-expand-enter-to,
.section-expand-leave-from {
  opacity: 1;
  max-height: 2000px;
}

/* Item expand/collapse transitions (for individual items) */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease-out;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 200px;
}
</style>
