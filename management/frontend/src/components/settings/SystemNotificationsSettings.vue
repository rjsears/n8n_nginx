<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useNotificationStore } from '@/stores/notifications'
import { useThemeStore } from '@/stores/theme'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import {
  BellIcon,
  BellAlertIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  Cog6ToothIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  PauseCircleIcon,
  PlayCircleIcon,
  CubeIcon,
  ArrowPathIcon,
  ShieldCheckIcon,
  CircleStackIcon,
  CpuChipIcon,
  HeartIcon,
  FireIcon,
  ArrowDownTrayIcon,
  ShieldExclamationIcon,
  PlusIcon,
  TrashIcon,
  AdjustmentsHorizontalIcon,
  InformationCircleIcon,
  CalendarDaysIcon,
  MoonIcon,
  SunIcon,
  EnvelopeIcon,
  DocumentTextIcon,
  QuestionMarkCircleIcon,
} from '@heroicons/vue/24/outline'

const notificationStore = useNotificationStore()
const themeStore = useThemeStore()

const loading = ref(true)
const saving = ref(false)

// Data
const events = ref([])
const globalSettings = ref(null)
const containerConfigs = ref([])
const history = ref([])
const channels = ref([])
const groups = ref([])

// UI State
const activeSection = ref('events') // 'events', 'containers', 'history', 'global'
const expandedCategories = ref(new Set())
const expandedEvents = ref(new Set())
const expandedContainers = ref(new Set())
const showMaintenanceModal = ref(false)
const showAddTargetModal = ref(false)
const selectedEventForTarget = ref(null)

// Icon mapping
const iconMap = {
  CheckCircleIcon,
  XCircleIcon,
  CircleStackIcon,
  HeartIcon,
  ArrowPathIcon,
  CpuChipIcon,
  FireIcon,
  ShieldCheckIcon,
  ShieldExclamationIcon,
  ArrowDownTrayIcon,
}

// Frequency options with descriptions
const frequencyOptions = [
  { value: 'every_time', label: 'Every Time', description: 'Send notification each time this event occurs' },
  { value: 'once_per_15m', label: 'Once per 15 minutes', description: 'Maximum one notification per 15 minute window' },
  { value: 'once_per_30m', label: 'Once per 30 minutes', description: 'Maximum one notification per 30 minute window' },
  { value: 'once_per_hour', label: 'Once per hour', description: 'Maximum one notification per hour' },
  { value: 'once_per_4h', label: 'Once per 4 hours', description: 'Maximum one notification every 4 hours' },
  { value: 'once_per_12h', label: 'Once per 12 hours', description: 'Maximum one notification every 12 hours' },
  { value: 'once_per_day', label: 'Once per day', description: 'Maximum one notification per day' },
  { value: 'once_per_week', label: 'Once per week', description: 'Maximum one notification per week' },
]

// Severity options with descriptions
const severityOptions = [
  { value: 'info', label: 'Info', color: 'blue', description: 'Informational - no action required' },
  { value: 'warning', label: 'Warning', color: 'amber', description: 'Attention needed - not critical' },
  { value: 'critical', label: 'Critical', color: 'red', description: 'Immediate action required' },
]

// Category grouping
const categoryInfo = {
  backup: { label: 'Backup Events', icon: CircleStackIcon, color: 'emerald', description: 'Notifications for backup operations' },
  container: { label: 'Container Events', icon: CubeIcon, color: 'blue', description: 'Docker container health and status alerts' },
  system: { label: 'System Events', icon: CpuChipIcon, color: 'purple', description: 'Host system resource monitoring' },
  security: { label: 'Security Events', icon: ShieldCheckIcon, color: 'red', description: 'Security and access notifications' },
}

// Computed
const eventsByCategory = computed(() => {
  const grouped = {}
  for (const event of events.value) {
    if (!grouped[event.category]) {
      grouped[event.category] = []
    }
    grouped[event.category].push(event)
  }
  return grouped
})

const enabledEventsCount = computed(() => {
  return events.value.filter(e => e.enabled).length
})

const totalEventsCount = computed(() => events.value.length)

const hasNoTargets = computed(() => {
  return (event) => !event.targets || event.targets.length === 0
})

// Methods
async function loadData() {
  loading.value = true
  try {
    await Promise.all([
      loadEvents(),
      loadGlobalSettings(),
      loadContainerConfigs(),
      loadChannelsAndGroups(),
    ])
  } catch (error) {
    console.error('Failed to load system notifications data:', error)
    notificationStore.error('Failed to load notification settings')
  } finally {
    loading.value = false
  }
}

async function loadEvents() {
  try {
    const response = await api.get('/system-notifications/events')
    events.value = response.data
  } catch (error) {
    console.error('Failed to load events:', error)
    events.value = []
  }
}

async function loadGlobalSettings() {
  try {
    const response = await api.get('/system-notifications/global-settings')
    globalSettings.value = response.data
  } catch (error) {
    console.error('Failed to load global settings:', error)
    globalSettings.value = null
  }
}

async function loadContainerConfigs() {
  try {
    const response = await api.get('/system-notifications/container-configs')
    containerConfigs.value = response.data
  } catch (error) {
    console.error('Failed to load container configs:', error)
    containerConfigs.value = []
  }
}

async function loadChannelsAndGroups() {
  try {
    const [channelsRes, groupsRes] = await Promise.all([
      api.get('/notifications/services'),
      api.get('/notifications/groups'),
    ])
    channels.value = channelsRes.data
    groups.value = groupsRes.data
  } catch (error) {
    console.error('Failed to load channels/groups:', error)
    channels.value = []
    groups.value = []
  }
}

async function loadHistory() {
  try {
    const response = await api.get('/system-notifications/history', {
      params: { limit: 100 }
    })
    history.value = response.data.items || []
  } catch (error) {
    console.error('Failed to load history:', error)
    history.value = []
  }
}

function toggleCategory(category) {
  if (expandedCategories.value.has(category)) {
    expandedCategories.value.delete(category)
  } else {
    expandedCategories.value.add(category)
  }
  expandedCategories.value = new Set(expandedCategories.value)
}

function toggleEvent(eventId) {
  if (expandedEvents.value.has(eventId)) {
    expandedEvents.value.delete(eventId)
  } else {
    expandedEvents.value.add(eventId)
  }
  expandedEvents.value = new Set(expandedEvents.value)
}

async function updateEvent(event, field, value) {
  // Prevent enabling if no targets
  if (field === 'enabled' && value === true && hasNoTargets.value(event)) {
    notificationStore.warning('Add at least one notification target before enabling')
    return
  }

  try {
    const updateData = { [field]: value }
    await api.put(`/system-notifications/events/${event.id}`, updateData)

    // Update local state
    const idx = events.value.findIndex(e => e.id === event.id)
    if (idx !== -1) {
      events.value[idx] = { ...events.value[idx], [field]: value }
    }

    // Better toast messages based on field
    const fieldMessages = {
      enabled: value ? `Enabled notifications for "${event.display_name}"` : `Disabled notifications for "${event.display_name}"`,
      frequency: `Frequency updated for "${event.display_name}"`,
      severity: `Severity changed to ${value} for "${event.display_name}"`,
      cooldown_minutes: `Cooldown updated for "${event.display_name}"`,
      flapping_enabled: value ? `Flapping detection enabled for "${event.display_name}"` : `Flapping detection disabled for "${event.display_name}"`,
      escalation_enabled: value ? `Escalation enabled for "${event.display_name}"` : `Escalation disabled for "${event.display_name}"`,
    }
    notificationStore.success(fieldMessages[field] || `Settings saved for "${event.display_name}"`)
  } catch (error) {
    console.error('Failed to update event:', error)
    notificationStore.error(`Failed to save changes for "${event.display_name}"`)
  }
}

async function updateGlobalSettings(updates) {
  saving.value = true
  try {
    const response = await api.put('/system-notifications/global-settings', updates)
    globalSettings.value = response.data
    notificationStore.success('Global settings saved successfully')
  } catch (error) {
    console.error('Failed to update global settings:', error)
    notificationStore.error('Failed to save global settings')
  } finally {
    saving.value = false
  }
}

async function toggleMaintenanceMode() {
  if (globalSettings.value?.maintenance_mode) {
    // Disable maintenance mode
    await updateGlobalSettings({ maintenance_mode: false, maintenance_until: null, maintenance_reason: null })
  } else {
    // Show modal to enable with options
    showMaintenanceModal.value = true
  }
}

async function enableMaintenanceMode(until, reason) {
  await updateGlobalSettings({
    maintenance_mode: true,
    maintenance_until: until,
    maintenance_reason: reason,
  })
  showMaintenanceModal.value = false
}

function openAddTargetModal(event) {
  selectedEventForTarget.value = event
  showAddTargetModal.value = true
}

async function addTarget(eventId, targetType, targetId, level) {
  try {
    const data = {
      target_type: targetType,
      escalation_level: level,
    }
    if (targetType === 'channel') {
      data.channel_id = targetId
    } else {
      data.group_id = targetId
    }

    await api.post(`/system-notifications/events/${eventId}/targets`, data)
    await loadEvents()
    notificationStore.success('Notification target added successfully')
    showAddTargetModal.value = false
  } catch (error) {
    console.error('Failed to add target:', error)
    notificationStore.error(error.response?.data?.detail || 'Failed to add notification target')
  }
}

async function removeTarget(eventId, targetId) {
  try {
    await api.delete(`/system-notifications/events/${eventId}/targets/${targetId}`)
    await loadEvents()
    notificationStore.success('Notification target removed')
  } catch (error) {
    console.error('Failed to remove target:', error)
    notificationStore.error('Failed to remove notification target')
  }
}

function getSeverityColor(severity) {
  switch (severity) {
    case 'info': return 'blue'
    case 'warning': return 'amber'
    case 'critical': return 'red'
    default: return 'gray'
  }
}

function getFrequencyLabel(value) {
  return frequencyOptions.find(o => o.value === value)?.label || value
}

function getIcon(iconName) {
  return iconMap[iconName] || BellIcon
}

function formatDate(dateStr) {
  if (!dateStr) return 'Never'
  return new Date(dateStr).toLocaleString()
}

function getCategoryEventCounts(category) {
  const categoryEvents = eventsByCategory.value[category] || []
  const enabled = categoryEvents.filter(e => e.enabled).length
  return { enabled, total: categoryEvents.length }
}

// Watch for section changes to load data
watch(activeSection, (newSection) => {
  if (newSection === 'history' && history.value.length === 0) {
    loadHistory()
  }
})

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Quick Stats / Status Bar -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <!-- Events Enabled -->
      <div class="relative overflow-hidden rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 p-5 shadow-lg shadow-emerald-500/20">
        <div class="absolute top-0 right-0 -mt-4 -mr-4 h-24 w-24 rounded-full bg-white/10"></div>
        <div class="relative">
          <div class="flex items-center gap-3">
            <div class="p-2 rounded-xl bg-white/20 backdrop-blur">
              <BellIcon class="h-6 w-6 text-white" />
            </div>
            <div>
              <p class="text-3xl font-bold text-white">{{ enabledEventsCount }}<span class="text-lg text-white/70">/{{ totalEventsCount }}</span></p>
              <p class="text-sm text-white/80 font-medium">Events Enabled</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Maintenance Mode -->
      <div
        :class="[
          'relative overflow-hidden rounded-2xl p-5 cursor-pointer transition-all shadow-lg',
          globalSettings?.maintenance_mode
            ? 'bg-gradient-to-br from-amber-500 to-orange-600 shadow-amber-500/20'
            : 'bg-gradient-to-br from-gray-400 to-gray-500 dark:from-gray-600 dark:to-gray-700 shadow-gray-500/20 hover:from-gray-500 hover:to-gray-600'
        ]"
        @click="toggleMaintenanceMode"
      >
        <div class="absolute top-0 right-0 -mt-4 -mr-4 h-24 w-24 rounded-full bg-white/10"></div>
        <div class="relative flex items-center gap-3">
          <div class="p-2 rounded-xl bg-white/20 backdrop-blur">
            <PauseCircleIcon class="h-6 w-6 text-white" />
          </div>
          <div>
            <p class="text-2xl font-bold text-white">{{ globalSettings?.maintenance_mode ? 'ACTIVE' : 'OFF' }}</p>
            <p class="text-sm text-white/80 font-medium">Maintenance Mode</p>
          </div>
        </div>
      </div>

      <!-- Quiet Hours -->
      <div
        :class="[
          'relative overflow-hidden rounded-2xl p-5 shadow-lg',
          globalSettings?.quiet_hours_enabled
            ? 'bg-gradient-to-br from-indigo-500 to-purple-600 shadow-indigo-500/20'
            : 'bg-gradient-to-br from-slate-400 to-slate-500 dark:from-slate-600 dark:to-slate-700 shadow-slate-500/20'
        ]"
      >
        <div class="absolute top-0 right-0 -mt-4 -mr-4 h-24 w-24 rounded-full bg-white/10"></div>
        <div class="relative flex items-center gap-3">
          <div class="p-2 rounded-xl bg-white/20 backdrop-blur">
            <MoonIcon class="h-6 w-6 text-white" />
          </div>
          <div>
            <p v-if="globalSettings?.quiet_hours_enabled" class="text-xl font-bold text-white">
              {{ globalSettings.quiet_hours_start }} - {{ globalSettings.quiet_hours_end }}
            </p>
            <p v-else class="text-2xl font-bold text-white">OFF</p>
            <p class="text-sm text-white/80 font-medium">Quiet Hours</p>
          </div>
        </div>
      </div>

      <!-- Rate Limit Status -->
      <div class="relative overflow-hidden rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-600 p-5 shadow-lg shadow-blue-500/20">
        <div class="absolute top-0 right-0 -mt-4 -mr-4 h-24 w-24 rounded-full bg-white/10"></div>
        <div class="relative flex items-center gap-3">
          <div class="p-2 rounded-xl bg-white/20 backdrop-blur">
            <ClockIcon class="h-6 w-6 text-white" />
          </div>
          <div>
            <p class="text-3xl font-bold text-white">
              {{ globalSettings?.notifications_this_hour || 0 }}<span class="text-lg text-white/70">/{{ globalSettings?.max_notifications_per_hour || 50 }}</span>
            </p>
            <p class="text-sm text-white/80 font-medium">This Hour</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Section Tabs -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-2 flex gap-2 overflow-x-auto">
      <button
        v-for="(section, idx) in [
          { id: 'events', label: 'Notification Events', icon: BellAlertIcon, color: 'from-emerald-500 to-teal-500' },
          { id: 'global', label: 'Global Settings', icon: Cog6ToothIcon, color: 'from-blue-500 to-indigo-500' },
          { id: 'containers', label: 'Container Config', icon: CubeIcon, color: 'from-purple-500 to-pink-500' },
          { id: 'history', label: 'History', icon: DocumentTextIcon, color: 'from-amber-500 to-orange-500' },
        ]"
        :key="section.id"
        @click="activeSection = section.id"
        :class="[
          'flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold transition-all whitespace-nowrap',
          activeSection === section.id
            ? `bg-gradient-to-r ${section.color} text-white shadow-lg`
            : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
        ]"
      >
        <component :is="section.icon" class="h-5 w-5" />
        {{ section.label }}
      </button>
    </div>

    <LoadingSpinner v-if="loading" size="lg" text="Loading notification settings..." class="py-12" />

    <template v-else>
      <!-- Events Section -->
      <div v-if="activeSection === 'events'" class="space-y-4">
        <!-- Collapsible Category Cards -->
        <div
          v-for="(categoryEvents, category) in eventsByCategory"
          :key="category"
          class="bg-white dark:bg-gray-800 rounded-2xl shadow-lg overflow-hidden"
        >
          <!-- Category Header (Clickable) - Gradient based on category -->
          <div
            @click="toggleCategory(category)"
            :class="[
              'flex items-center justify-between p-5 cursor-pointer transition-all',
              expandedCategories.has(category)
                ? category === 'backup' ? 'bg-gradient-to-r from-emerald-500 to-teal-500'
                  : category === 'container' ? 'bg-gradient-to-r from-blue-500 to-indigo-500'
                  : category === 'security' ? 'bg-gradient-to-r from-red-500 to-rose-600'
                  : 'bg-gradient-to-r from-purple-500 to-pink-500'
                : 'bg-gradient-to-r from-gray-100 to-gray-50 dark:from-gray-700 dark:to-gray-800 hover:from-gray-200 hover:to-gray-100 dark:hover:from-gray-600 dark:hover:to-gray-700'
            ]"
          >
            <div class="flex items-center gap-4">
              <div :class="[
                'p-3 rounded-xl',
                expandedCategories.has(category) ? 'bg-white/20' : 'bg-white dark:bg-gray-600 shadow-sm'
              ]">
                <component
                  :is="categoryInfo[category]?.icon || BellIcon"
                  :class="[
                    'h-6 w-6',
                    expandedCategories.has(category)
                      ? 'text-white'
                      : category === 'backup' ? 'text-emerald-500'
                        : category === 'container' ? 'text-blue-500'
                        : category === 'security' ? 'text-red-500'
                        : 'text-purple-500'
                  ]"
                />
              </div>
              <div>
                <h3 :class="['font-bold text-lg', expandedCategories.has(category) ? 'text-white' : 'text-primary']">
                  {{ categoryInfo[category]?.label || category }}
                </h3>
                <p :class="['text-sm', expandedCategories.has(category) ? 'text-white/80' : 'text-secondary']">
                  {{ categoryInfo[category]?.description }}
                </p>
              </div>
            </div>
            <div class="flex items-center gap-4">
              <div :class="[
                'px-4 py-2 rounded-full font-semibold text-sm',
                expandedCategories.has(category)
                  ? 'bg-white/20 text-white'
                  : category === 'backup' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400'
                    : category === 'container' ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400'
                    : category === 'security' ? 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400'
                    : 'bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-400'
              ]">
                {{ getCategoryEventCounts(category).enabled }}/{{ getCategoryEventCounts(category).total }} enabled
              </div>
              <div :class="[
                'p-2 rounded-lg',
                expandedCategories.has(category) ? 'bg-white/20' : 'bg-gray-100 dark:bg-gray-600'
              ]">
                <ChevronDownIcon v-if="expandedCategories.has(category)" :class="['h-5 w-5', expandedCategories.has(category) ? 'text-white' : 'text-secondary']" />
                <ChevronRightIcon v-else class="h-5 w-5 text-secondary" />
              </div>
            </div>
          </div>

          <!-- Category Content (Collapsible) -->
          <Transition name="collapse">
            <div v-if="expandedCategories.has(category)" class="border-t border-gray-200 dark:border-gray-700">
              <div class="p-4 space-y-3">
                <!-- Event Rows -->
                <div
                  v-for="event in categoryEvents"
                  :key="event.id"
                  class="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden"
                >
                  <!-- Event Header Row -->
                  <div
                    @click="toggleEvent(event.id)"
                    class="flex items-center gap-3 p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                  >
                    <component
                      :is="expandedEvents.has(event.id) ? ChevronDownIcon : ChevronRightIcon"
                      class="h-4 w-4 text-secondary flex-shrink-0"
                    />

                    <!-- Icon -->
                    <div
                      :class="[
                        'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
                        event.enabled ? `bg-${getSeverityColor(event.severity)}-100 dark:bg-${getSeverityColor(event.severity)}-500/20` : 'bg-gray-100 dark:bg-gray-700'
                      ]"
                    >
                      <component
                        :is="getIcon(event.icon)"
                        :class="[
                          'h-4 w-4',
                          event.enabled ? `text-${getSeverityColor(event.severity)}-500` : 'text-gray-400'
                        ]"
                      />
                    </div>

                    <!-- Event Info -->
                    <div class="flex-1 min-w-0">
                      <p :class="['font-medium text-sm', event.enabled ? 'text-primary' : 'text-secondary']">
                        {{ event.display_name }}
                      </p>
                      <p class="text-xs text-secondary truncate">{{ event.description }}</p>
                    </div>

                    <!-- Quick Info -->
                    <div class="flex items-center gap-3" @click.stop>
                      <!-- Targets Warning -->
                      <span v-if="hasNoTargets(event)" class="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
                        <ExclamationTriangleIcon class="h-3.5 w-3.5" />
                        No targets
                      </span>
                      <span v-else class="text-xs text-secondary">
                        {{ event.targets?.length || 0 }} target{{ event.targets?.length !== 1 ? 's' : '' }}
                      </span>

                      <!-- Severity Badge -->
                      <span
                        :class="[
                          'px-2 py-0.5 rounded-full text-xs font-medium',
                          event.severity === 'critical' ? 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400' :
                          event.severity === 'warning' ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400' :
                          'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400'
                        ]"
                      >
                        {{ event.severity }}
                      </span>

                      <!-- Enable Toggle -->
                      <div class="relative group">
                        <label
                          :class="[
                            'relative inline-flex items-center',
                            hasNoTargets(event) ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'
                          ]"
                          :title="hasNoTargets(event) ? 'Add notification targets first' : (event.enabled ? 'Disable notifications' : 'Enable notifications')"
                        >
                          <input
                            type="checkbox"
                            :checked="event.enabled"
                            @change="updateEvent(event, 'enabled', $event.target.checked)"
                            :disabled="hasNoTargets(event) && !event.enabled"
                            class="sr-only peer"
                          />
                          <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-emerald-500 peer-disabled:cursor-not-allowed"></div>
                        </label>
                      </div>
                    </div>
                  </div>

                  <!-- Expanded Settings Panel - Different layout per category -->
                  <Transition name="collapse">
                    <div v-if="expandedEvents.has(event.id)" class="border-t border-gray-200 dark:border-gray-700">

                      <!-- ==================== BACKUP LAYOUT (Style 1: Gradient Cards) ==================== -->
                      <div v-if="event.category === 'backup'" class="bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 p-6">
                        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                          <!-- Frequency Card -->
                          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-lg overflow-hidden">
                            <div class="bg-gradient-to-r from-emerald-500 to-teal-500 px-4 py-3">
                              <h4 class="text-white font-semibold flex items-center gap-2">
                                <ClockIcon class="h-5 w-5" />
                                Frequency
                              </h4>
                            </div>
                            <div class="p-4 space-y-4">
                              <p class="text-xs text-secondary">How often should we notify you?</p>
                              <div class="space-y-2">
                                <label
                                  v-for="opt in frequencyOptions.slice(0, 4)"
                                  :key="opt.value"
                                  class="flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all"
                                  :class="event.frequency === opt.value ? 'bg-emerald-100 dark:bg-emerald-500/20 ring-2 ring-emerald-500' : 'hover:bg-gray-50 dark:hover:bg-gray-700'"
                                >
                                  <input
                                    type="radio"
                                    :checked="event.frequency === opt.value"
                                    @change="updateEvent(event, 'frequency', opt.value)"
                                    class="w-4 h-4 text-emerald-500 focus:ring-emerald-500"
                                  />
                                  <span class="text-sm font-medium text-primary">{{ opt.label }}</span>
                                </label>
                              </div>
                              <select
                                v-if="!['every_time', 'once_per_15m', 'once_per_30m', 'once_per_hour'].includes(event.frequency)"
                                :value="event.frequency"
                                @change="updateEvent(event, 'frequency', $event.target.value)"
                                class="select-field w-full text-sm mt-2"
                              >
                                <option v-for="opt in frequencyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                              </select>
                            </div>
                          </div>

                          <!-- Severity Card -->
                          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-lg overflow-hidden">
                            <div class="bg-gradient-to-r from-teal-500 to-cyan-500 px-4 py-3">
                              <h4 class="text-white font-semibold flex items-center gap-2">
                                <ExclamationTriangleIcon class="h-5 w-5" />
                                Priority Level
                              </h4>
                            </div>
                            <div class="p-4 space-y-3">
                              <p class="text-xs text-secondary">Set the urgency of this alert</p>
                              <div class="flex gap-2">
                                <button
                                  v-for="sev in severityOptions"
                                  :key="sev.value"
                                  @click="updateEvent(event, 'severity', sev.value)"
                                  :class="[
                                    'flex-1 py-3 px-4 rounded-xl font-medium text-sm transition-all',
                                    event.severity === sev.value
                                      ? sev.value === 'critical' ? 'bg-red-500 text-white shadow-lg shadow-red-500/30'
                                        : sev.value === 'warning' ? 'bg-amber-500 text-white shadow-lg shadow-amber-500/30'
                                        : 'bg-blue-500 text-white shadow-lg shadow-blue-500/30'
                                      : 'bg-gray-100 dark:bg-gray-700 text-secondary hover:bg-gray-200 dark:hover:bg-gray-600'
                                  ]"
                                >
                                  {{ sev.label }}
                                </button>
                              </div>
                              <p class="text-xs text-center text-secondary mt-2">
                                {{ severityOptions.find(s => s.value === event.severity)?.description }}
                              </p>
                            </div>
                          </div>

                          <!-- Targets Card -->
                          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-lg overflow-hidden">
                            <div class="bg-gradient-to-r from-cyan-500 to-blue-500 px-4 py-3 flex items-center justify-between">
                              <h4 class="text-white font-semibold flex items-center gap-2">
                                <BellIcon class="h-5 w-5" />
                                Send To
                              </h4>
                              <button
                                @click="openAddTargetModal(event)"
                                class="p-1.5 bg-white/20 hover:bg-white/30 rounded-lg transition-colors"
                              >
                                <PlusIcon class="h-4 w-4 text-white" />
                              </button>
                            </div>
                            <div class="p-4">
                              <div v-if="hasNoTargets(event)" class="text-center py-6">
                                <div class="w-12 h-12 mx-auto rounded-full bg-amber-100 dark:bg-amber-500/20 flex items-center justify-center mb-3">
                                  <ExclamationTriangleIcon class="h-6 w-6 text-amber-500" />
                                </div>
                                <p class="text-sm font-medium text-primary">No targets yet</p>
                                <p class="text-xs text-secondary mt-1">Add a channel or group to enable</p>
                              </div>
                              <div v-else class="space-y-2">
                                <div
                                  v-for="target in event.targets"
                                  :key="target.id"
                                  class="flex items-center justify-between p-3 rounded-xl bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-700 dark:to-gray-700/50"
                                >
                                  <div class="flex items-center gap-2">
                                    <div :class="['w-8 h-8 rounded-full flex items-center justify-center', target.target_type === 'channel' ? 'bg-blue-100 dark:bg-blue-500/20' : 'bg-purple-100 dark:bg-purple-500/20']">
                                      <BellIcon :class="['h-4 w-4', target.target_type === 'channel' ? 'text-blue-500' : 'text-purple-500']" />
                                    </div>
                                    <div>
                                      <p class="text-sm font-medium text-primary">{{ target.channel_name || target.group_name }}</p>
                                      <p class="text-xs text-secondary">L{{ target.escalation_level }} · {{ target.target_type }}</p>
                                    </div>
                                  </div>
                                  <button @click="removeTarget(event.id, target.id)" class="p-2 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10">
                                    <TrashIcon class="h-4 w-4" />
                                  </button>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>

                      <!-- ==================== CONTAINER LAYOUT (Style 2: Horizontal Compact) ==================== -->
                      <div v-else-if="event.category === 'container'" class="bg-gradient-to-r from-blue-50 via-indigo-50 to-purple-50 dark:from-blue-900/10 dark:via-indigo-900/10 dark:to-purple-900/10 p-6">
                        <!-- Top Row: Main Controls -->
                        <div class="flex flex-wrap items-center gap-4 mb-6">
                          <!-- Severity Pills -->
                          <div class="flex items-center gap-2">
                            <span class="text-xs font-semibold text-secondary uppercase">Severity:</span>
                            <div class="inline-flex rounded-full p-1 bg-white dark:bg-gray-800 shadow-sm">
                              <button
                                v-for="sev in severityOptions"
                                :key="sev.value"
                                @click="updateEvent(event, 'severity', sev.value)"
                                :class="[
                                  'px-4 py-1.5 rounded-full text-xs font-semibold transition-all',
                                  event.severity === sev.value
                                    ? sev.value === 'critical' ? 'bg-red-500 text-white'
                                      : sev.value === 'warning' ? 'bg-amber-500 text-white'
                                      : 'bg-blue-500 text-white'
                                    : 'text-secondary hover:bg-gray-100 dark:hover:bg-gray-700'
                                ]"
                              >
                                {{ sev.label }}
                              </button>
                            </div>
                          </div>

                          <!-- Frequency Dropdown -->
                          <div class="flex items-center gap-2">
                            <span class="text-xs font-semibold text-secondary uppercase">Frequency:</span>
                            <div class="relative">
                              <select
                                :value="event.frequency"
                                @change="updateEvent(event, 'frequency', $event.target.value)"
                                class="appearance-none bg-white dark:bg-gray-800 border-0 rounded-full px-4 py-2 pr-8 text-sm font-medium shadow-sm focus:ring-2 focus:ring-blue-500"
                              >
                                <option v-for="opt in frequencyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                              </select>
                              <ChevronDownIcon class="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                            </div>
                          </div>

                          <!-- Cooldown Slider (if every_time) -->
                          <div v-if="event.frequency === 'every_time'" class="flex items-center gap-3 bg-white dark:bg-gray-800 rounded-full px-4 py-2 shadow-sm">
                            <span class="text-xs font-semibold text-secondary uppercase whitespace-nowrap">Cooldown:</span>
                            <input
                              type="range"
                              :value="event.cooldown_minutes"
                              @input="updateEvent(event, 'cooldown_minutes', parseInt($event.target.value))"
                              min="0"
                              max="120"
                              step="5"
                              class="w-24 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
                            />
                            <span class="text-sm font-bold text-blue-600 w-12">{{ event.cooldown_minutes }}m</span>
                          </div>
                        </div>

                        <!-- Bottom Row: Targets -->
                        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-4">
                          <div class="flex items-center justify-between mb-4">
                            <h4 class="font-semibold text-primary flex items-center gap-2">
                              <BellIcon class="h-5 w-5 text-blue-500" />
                              Notification Targets
                            </h4>
                            <button
                              @click="openAddTargetModal(event)"
                              class="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-500 to-indigo-500 text-white text-sm font-medium rounded-xl hover:shadow-lg hover:shadow-blue-500/30 transition-all"
                            >
                              <PlusIcon class="h-4 w-4" />
                              Add Target
                            </button>
                          </div>

                          <div v-if="hasNoTargets(event)" class="flex items-center gap-4 p-4 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20">
                            <ExclamationTriangleIcon class="h-8 w-8 text-amber-500" />
                            <div>
                              <p class="font-medium text-amber-700 dark:text-amber-400">No notification targets configured</p>
                              <p class="text-sm text-amber-600 dark:text-amber-500">Add at least one channel or group to receive alerts</p>
                            </div>
                          </div>

                          <div v-else class="flex flex-wrap gap-3">
                            <div
                              v-for="target in event.targets"
                              :key="target.id"
                              class="group flex items-center gap-2 pl-4 pr-2 py-2 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-500/10 dark:to-indigo-500/10 border border-blue-200 dark:border-blue-500/20"
                            >
                              <span :class="['px-2 py-0.5 rounded-full text-xs font-bold', target.escalation_level === 1 ? 'bg-blue-500 text-white' : 'bg-purple-500 text-white']">
                                L{{ target.escalation_level }}
                              </span>
                              <span class="font-medium text-primary">{{ target.channel_name || target.group_name }}</span>
                              <button @click="removeTarget(event.id, target.id)" class="p-1 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-100 dark:hover:bg-red-500/20 opacity-0 group-hover:opacity-100 transition-all">
                                <XCircleIcon class="h-5 w-5" />
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>

                      <!-- ==================== SECURITY LAYOUT (Style 3: Dark/Serious) ==================== -->
                      <div v-else-if="event.category === 'security'" class="bg-gradient-to-br from-gray-900 to-red-900/80 dark:from-gray-900 dark:to-red-950 p-6">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                          <!-- Left: Settings -->
                          <div class="space-y-4">
                            <!-- Severity - Prominent -->
                            <div class="bg-black/30 backdrop-blur rounded-xl p-4 border border-red-500/30">
                              <h4 class="text-red-400 font-semibold text-sm uppercase tracking-wider mb-4 flex items-center gap-2">
                                <ShieldExclamationIcon class="h-5 w-5" />
                                Alert Severity
                              </h4>
                              <div class="grid grid-cols-3 gap-3">
                                <button
                                  v-for="sev in severityOptions"
                                  :key="sev.value"
                                  @click="updateEvent(event, 'severity', sev.value)"
                                  :class="[
                                    'p-4 rounded-xl border-2 transition-all text-center',
                                    event.severity === sev.value
                                      ? sev.value === 'critical' ? 'border-red-500 bg-red-500/20 shadow-lg shadow-red-500/20'
                                        : sev.value === 'warning' ? 'border-amber-500 bg-amber-500/20 shadow-lg shadow-amber-500/20'
                                        : 'border-blue-500 bg-blue-500/20 shadow-lg shadow-blue-500/20'
                                      : 'border-gray-600 bg-gray-800/50 hover:border-gray-500'
                                  ]"
                                >
                                  <div :class="[
                                    'text-2xl font-bold mb-1',
                                    event.severity === sev.value
                                      ? sev.value === 'critical' ? 'text-red-400' : sev.value === 'warning' ? 'text-amber-400' : 'text-blue-400'
                                      : 'text-gray-400'
                                  ]">
                                    {{ sev.value === 'critical' ? '!' : sev.value === 'warning' ? '⚠' : 'i' }}
                                  </div>
                                  <p :class="['text-sm font-semibold', event.severity === sev.value ? 'text-white' : 'text-gray-400']">{{ sev.label }}</p>
                                </button>
                              </div>
                            </div>

                            <!-- Frequency -->
                            <div class="bg-black/30 backdrop-blur rounded-xl p-4 border border-gray-700">
                              <h4 class="text-gray-300 font-semibold text-sm uppercase tracking-wider mb-3 flex items-center gap-2">
                                <ClockIcon class="h-5 w-5 text-gray-500" />
                                Notification Frequency
                              </h4>
                              <select
                                :value="event.frequency"
                                @change="updateEvent(event, 'frequency', $event.target.value)"
                                class="w-full bg-gray-800 border border-gray-600 text-white rounded-lg px-4 py-3 focus:border-red-500 focus:ring-red-500"
                              >
                                <option v-for="opt in frequencyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                              </select>
                            </div>
                          </div>

                          <!-- Right: Targets -->
                          <div class="bg-black/30 backdrop-blur rounded-xl p-4 border border-gray-700">
                            <div class="flex items-center justify-between mb-4">
                              <h4 class="text-gray-300 font-semibold text-sm uppercase tracking-wider flex items-center gap-2">
                                <BellIcon class="h-5 w-5 text-red-400" />
                                Alert Recipients
                              </h4>
                              <button
                                @click="openAddTargetModal(event)"
                                class="flex items-center gap-2 px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white text-sm font-medium rounded-lg transition-colors"
                              >
                                <PlusIcon class="h-4 w-4" />
                                Add
                              </button>
                            </div>

                            <div v-if="hasNoTargets(event)" class="text-center py-8">
                              <ShieldExclamationIcon class="h-12 w-12 mx-auto text-red-500/50 mb-3" />
                              <p class="text-gray-400 font-medium">No recipients configured</p>
                              <p class="text-gray-500 text-sm">Security alerts need at least one target</p>
                            </div>

                            <div v-else class="space-y-2">
                              <div
                                v-for="target in event.targets"
                                :key="target.id"
                                class="flex items-center justify-between p-3 rounded-lg bg-gray-800/50 border border-gray-700 hover:border-red-500/50 transition-colors"
                              >
                                <div class="flex items-center gap-3">
                                  <span :class="['w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold', target.escalation_level === 1 ? 'bg-red-500' : 'bg-orange-500']">
                                    L{{ target.escalation_level }}
                                  </span>
                                  <div>
                                    <p class="font-medium text-white">{{ target.channel_name || target.group_name }}</p>
                                    <p class="text-xs text-gray-500">{{ target.target_type }}</p>
                                  </div>
                                </div>
                                <button @click="removeTarget(event.id, target.id)" class="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors">
                                  <TrashIcon class="h-5 w-5" />
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>

                      <!-- ==================== SYSTEM LAYOUT (Style 4: Clean Minimal) ==================== -->
                      <div v-else class="bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-900/10 dark:to-pink-900/10 p-6">
                        <div class="max-w-4xl mx-auto">
                          <!-- Single Row Settings -->
                          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl overflow-hidden">
                            <!-- Header -->
                            <div class="bg-gradient-to-r from-purple-500 to-pink-500 px-6 py-4">
                              <h4 class="text-white font-semibold flex items-center gap-2">
                                <CpuChipIcon class="h-5 w-5" />
                                {{ event.display_name }} Configuration
                              </h4>
                            </div>

                            <div class="p-6">
                              <!-- Settings Row -->
                              <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
                                <!-- Severity -->
                                <div>
                                  <label class="block text-sm font-semibold text-primary mb-3">Alert Priority</label>
                                  <div class="space-y-2">
                                    <label
                                      v-for="sev in severityOptions"
                                      :key="sev.value"
                                      :class="[
                                        'flex items-center gap-3 p-3 rounded-xl border-2 cursor-pointer transition-all',
                                        event.severity === sev.value
                                          ? sev.value === 'critical' ? 'border-red-500 bg-red-50 dark:bg-red-500/10'
                                            : sev.value === 'warning' ? 'border-amber-500 bg-amber-50 dark:bg-amber-500/10'
                                            : 'border-blue-500 bg-blue-50 dark:bg-blue-500/10'
                                          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                                      ]"
                                    >
                                      <input
                                        type="radio"
                                        :checked="event.severity === sev.value"
                                        @change="updateEvent(event, 'severity', sev.value)"
                                        :class="[
                                          'w-4 h-4',
                                          sev.value === 'critical' ? 'text-red-500 focus:ring-red-500'
                                            : sev.value === 'warning' ? 'text-amber-500 focus:ring-amber-500'
                                            : 'text-blue-500 focus:ring-blue-500'
                                        ]"
                                      />
                                      <div>
                                        <p class="font-medium text-primary">{{ sev.label }}</p>
                                        <p class="text-xs text-secondary">{{ sev.description }}</p>
                                      </div>
                                    </label>
                                  </div>
                                </div>

                                <!-- Frequency -->
                                <div>
                                  <label class="block text-sm font-semibold text-primary mb-3">Notification Rate</label>
                                  <select
                                    :value="event.frequency"
                                    @change="updateEvent(event, 'frequency', $event.target.value)"
                                    class="w-full bg-gray-50 dark:bg-gray-700 border-2 border-gray-200 dark:border-gray-600 rounded-xl px-4 py-3 text-primary focus:border-purple-500 focus:ring-purple-500"
                                  >
                                    <option v-for="opt in frequencyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                                  </select>
                                  <p class="text-xs text-secondary mt-2">{{ frequencyOptions.find(f => f.value === event.frequency)?.description }}</p>
                                </div>

                                <!-- Cooldown (if applicable) -->
                                <div v-if="event.frequency === 'every_time'">
                                  <label class="block text-sm font-semibold text-primary mb-3">Cooldown Period</label>
                                  <div class="bg-gray-50 dark:bg-gray-700 rounded-xl p-4 border-2 border-gray-200 dark:border-gray-600">
                                    <input
                                      type="range"
                                      :value="event.cooldown_minutes"
                                      @input="updateEvent(event, 'cooldown_minutes', parseInt($event.target.value))"
                                      min="0"
                                      max="120"
                                      step="5"
                                      class="w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-lg appearance-none cursor-pointer accent-purple-500"
                                    />
                                    <div class="flex justify-between mt-2">
                                      <span class="text-xs text-secondary">0 min</span>
                                      <span class="text-lg font-bold text-purple-600">{{ event.cooldown_minutes }} min</span>
                                      <span class="text-xs text-secondary">120 min</span>
                                    </div>
                                  </div>
                                </div>
                              </div>

                              <!-- Targets Section -->
                              <div class="border-t border-gray-200 dark:border-gray-700 pt-6">
                                <div class="flex items-center justify-between mb-4">
                                  <div>
                                    <h5 class="font-semibold text-primary">Notification Targets</h5>
                                    <p class="text-sm text-secondary">Where should these alerts be sent?</p>
                                  </div>
                                  <button
                                    @click="openAddTargetModal(event)"
                                    class="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white text-sm font-medium rounded-xl hover:shadow-lg hover:shadow-purple-500/30 transition-all"
                                  >
                                    <PlusIcon class="h-4 w-4" />
                                    Add Target
                                  </button>
                                </div>

                                <div v-if="hasNoTargets(event)" class="bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-500/10 dark:to-orange-500/10 rounded-xl p-6 border border-amber-200 dark:border-amber-500/20">
                                  <div class="flex items-center gap-4">
                                    <div class="w-12 h-12 rounded-xl bg-amber-100 dark:bg-amber-500/20 flex items-center justify-center">
                                      <ExclamationTriangleIcon class="h-6 w-6 text-amber-500" />
                                    </div>
                                    <div>
                                      <p class="font-medium text-amber-700 dark:text-amber-400">No notification targets configured</p>
                                      <p class="text-sm text-amber-600 dark:text-amber-500">Add at least one channel or group to receive notifications</p>
                                    </div>
                                  </div>
                                </div>

                                <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                  <div
                                    v-for="target in event.targets"
                                    :key="target.id"
                                    class="flex items-center justify-between p-4 rounded-xl bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-700 hover:border-purple-300 dark:hover:border-purple-500/50 transition-colors"
                                  >
                                    <div class="flex items-center gap-3">
                                      <div :class="[
                                        'w-10 h-10 rounded-xl flex items-center justify-center font-bold text-white',
                                        target.escalation_level === 1 ? 'bg-gradient-to-br from-purple-500 to-pink-500' : 'bg-gradient-to-br from-orange-500 to-red-500'
                                      ]">
                                        L{{ target.escalation_level }}
                                      </div>
                                      <div>
                                        <p class="font-medium text-primary">{{ target.channel_name || target.group_name }}</p>
                                        <p class="text-xs text-secondary">{{ target.target_type === 'channel' ? 'Channel' : 'Group' }}</p>
                                      </div>
                                    </div>
                                    <button @click="removeTarget(event.id, target.id)" class="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors">
                                      <TrashIcon class="h-5 w-5" />
                                    </button>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>

                    </div>
                  </Transition>
                </div>
              </div>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Global Settings Section -->
      <div v-if="activeSection === 'global'" class="space-y-6">
        <Card title="Maintenance Mode" subtitle="Temporarily pause all notifications">
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Enable Maintenance Mode</p>
                <p class="text-sm text-secondary">All notifications will be suppressed</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  :checked="globalSettings?.maintenance_mode"
                  @change="toggleMaintenanceMode"
                  class="sr-only peer"
                />
                <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-amber-500"></div>
              </label>
            </div>

            <div v-if="globalSettings?.maintenance_mode" class="p-3 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30">
              <p class="text-sm text-amber-700 dark:text-amber-400">
                <span class="font-medium">Maintenance mode is active.</span>
                <span v-if="globalSettings.maintenance_until"> Until: {{ formatDate(globalSettings.maintenance_until) }}</span>
                <span v-if="globalSettings.maintenance_reason"> - {{ globalSettings.maintenance_reason }}</span>
              </p>
            </div>
          </div>
        </Card>

        <Card title="Quiet Hours" subtitle="Reduce notification priority during specified hours">
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Enable Quiet Hours</p>
                <p class="text-sm text-secondary">Notifications will have reduced priority</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  :checked="globalSettings?.quiet_hours_enabled"
                  @change="updateGlobalSettings({ quiet_hours_enabled: $event.target.checked })"
                  class="sr-only peer"
                />
                <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-indigo-500"></div>
              </label>
            </div>

            <div v-if="globalSettings?.quiet_hours_enabled" class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-primary mb-1">Start Time</label>
                <input
                  type="time"
                  :value="globalSettings?.quiet_hours_start"
                  @change="updateGlobalSettings({ quiet_hours_start: $event.target.value })"
                  class="input-field w-full"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-primary mb-1">End Time</label>
                <input
                  type="time"
                  :value="globalSettings?.quiet_hours_end"
                  @change="updateGlobalSettings({ quiet_hours_end: $event.target.value })"
                  class="input-field w-full"
                />
              </div>
            </div>
          </div>
        </Card>

        <Card title="Rate Limiting" subtitle="Prevent notification storms">
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Max Notifications Per Hour</p>
                <p class="text-sm text-secondary">Limit total notifications sent per hour</p>
              </div>
              <input
                type="number"
                :value="globalSettings?.max_notifications_per_hour"
                @change="updateGlobalSettings({ max_notifications_per_hour: parseInt($event.target.value) })"
                min="1"
                max="1000"
                class="input-field w-24"
              />
            </div>

            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Emergency Contact</p>
                <p class="text-sm text-secondary">Channel to notify if rate limit is exceeded</p>
              </div>
              <select
                :value="globalSettings?.emergency_contact_id || ''"
                @change="updateGlobalSettings({ emergency_contact_id: $event.target.value ? parseInt($event.target.value) : null })"
                class="select-field w-48"
              >
                <option value="">None</option>
                <option v-for="channel in channels" :key="channel.id" :value="channel.id">
                  {{ channel.name }}
                </option>
              </select>
            </div>
          </div>
        </Card>

        <Card title="Daily Digest" subtitle="Batch low-priority notifications into a daily summary">
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-primary">Enable Daily Digest</p>
                <p class="text-sm text-secondary">Info-level events will be batched</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  :checked="globalSettings?.digest_enabled"
                  @change="updateGlobalSettings({ digest_enabled: $event.target.checked })"
                  class="sr-only peer"
                />
                <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"></div>
              </label>
            </div>

            <div v-if="globalSettings?.digest_enabled">
              <label class="block text-sm font-medium text-primary mb-1">Digest Time</label>
              <input
                type="time"
                :value="globalSettings?.digest_time"
                @change="updateGlobalSettings({ digest_time: $event.target.value })"
                class="input-field w-32"
              />
            </div>
          </div>
        </Card>
      </div>

      <!-- Container Config Section -->
      <div v-if="activeSection === 'containers'" class="space-y-4">
        <div class="p-4 rounded-lg bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30">
          <div class="flex gap-3">
            <InformationCircleIcon class="h-5 w-5 text-blue-500 flex-shrink-0" />
            <div class="text-sm text-blue-700 dark:text-blue-400">
              <p class="font-medium">Per-Container Configuration</p>
              <p class="mt-1">Configure which containers should be monitored and optionally override their notification targets. Containers without custom configuration will use the default event targets.</p>
            </div>
          </div>
        </div>

        <div v-if="containerConfigs.length === 0" class="text-center py-8 text-secondary">
          <CubeIcon class="h-12 w-12 mx-auto mb-3 text-gray-300" />
          <p>No container-specific configurations yet.</p>
          <p class="text-sm">Container configs will appear here when customized from the Containers view.</p>
        </div>

        <div v-else class="space-y-2">
          <div v-for="config in containerConfigs" :key="config.id"
            class="bg-surface rounded-lg border border-[var(--color-border)] p-4"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <CubeIcon class="h-5 w-5 text-blue-500" />
                <span class="font-medium text-primary">{{ config.container_name }}</span>
              </div>
              <div class="flex items-center gap-4 text-sm">
                <label class="flex items-center gap-2">
                  <input
                    type="checkbox"
                    :checked="config.monitor_unhealthy"
                    class="w-4 h-4 rounded border-gray-300 text-blue-500"
                  />
                  <span class="text-secondary">Unhealthy</span>
                </label>
                <label class="flex items-center gap-2">
                  <input
                    type="checkbox"
                    :checked="config.monitor_restart"
                    class="w-4 h-4 rounded border-gray-300 text-blue-500"
                  />
                  <span class="text-secondary">Restarts</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- History Section -->
      <div v-if="activeSection === 'history'" class="space-y-4">
        <div v-if="history.length === 0" class="text-center py-8 text-secondary">
          <DocumentTextIcon class="h-12 w-12 mx-auto mb-3 text-gray-300" />
          <p>No notification history yet.</p>
        </div>

        <div v-else class="space-y-2">
          <div v-for="entry in history" :key="entry.id"
            class="bg-surface rounded-lg border border-[var(--color-border)] p-4"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <span :class="[
                  'w-2 h-2 rounded-full',
                  entry.status === 'sent' ? 'bg-green-500' :
                  entry.status === 'suppressed' ? 'bg-amber-500' :
                  entry.status === 'failed' ? 'bg-red-500' : 'bg-gray-500'
                ]"></span>
                <span class="font-medium text-primary">{{ entry.event_type }}</span>
                <span v-if="entry.target_label" class="text-sm text-secondary">- {{ entry.target_label }}</span>
              </div>
              <div class="flex items-center gap-3 text-sm">
                <span :class="[
                  'px-2 py-0.5 rounded-full text-xs font-medium',
                  entry.status === 'sent' ? 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400' :
                  entry.status === 'suppressed' ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400' :
                  entry.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400' :
                  'bg-gray-100 text-gray-700 dark:bg-gray-500/20 dark:text-gray-400'
                ]">
                  {{ entry.status }}
                </span>
                <span class="text-secondary">{{ formatDate(entry.triggered_at) }}</span>
              </div>
            </div>
            <div v-if="entry.suppression_reason" class="mt-2 text-sm text-secondary">
              Reason: {{ entry.suppression_reason }}
            </div>
            <div v-if="entry.error_message" class="mt-2 text-sm text-red-500">
              Error: {{ entry.error_message }}
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Add Target Modal -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showAddTargetModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div class="bg-surface rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 class="text-lg font-semibold text-primary">Add Notification Target</h3>
            <p class="text-sm text-secondary">
              Choose where to send notifications for "{{ selectedEventForTarget?.display_name }}"
            </p>

            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-primary mb-2">Target Type</label>
                <div class="flex gap-4">
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="radio" v-model="newTargetType" value="channel" class="w-4 h-4" />
                    <span class="text-sm">Channel</span>
                  </label>
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="radio" v-model="newTargetType" value="group" class="w-4 h-4" />
                    <span class="text-sm">Group</span>
                  </label>
                </div>
              </div>

              <div v-if="newTargetType === 'channel'">
                <label class="block text-sm font-medium text-primary mb-1">Select Channel</label>
                <select v-model="newTargetId" class="select-field w-full">
                  <option value="">Choose a channel...</option>
                  <option v-for="channel in channels" :key="channel.id" :value="channel.id">
                    {{ channel.name }} ({{ channel.service_type }})
                  </option>
                </select>
              </div>

              <div v-if="newTargetType === 'group'">
                <label class="block text-sm font-medium text-primary mb-1">Select Group</label>
                <select v-model="newTargetId" class="select-field w-full">
                  <option value="">Choose a group...</option>
                  <option v-for="group in groups" :key="group.id" :value="group.id">
                    {{ group.name }} ({{ group.channel_count }} channels)
                  </option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-primary mb-1">Escalation Level</label>
                <select v-model="newTargetLevel" class="select-field w-full">
                  <option :value="1">L1 - Primary (receives immediately)</option>
                  <option :value="2">L2 - Escalation (receives if L1 unacknowledged)</option>
                </select>
              </div>
            </div>

            <div class="flex justify-end gap-3 pt-4">
              <button @click="showAddTargetModal = false" class="btn-secondary">
                Cancel
              </button>
              <button
                @click="addTarget(selectedEventForTarget.id, newTargetType, newTargetId, newTargetLevel)"
                :disabled="!newTargetId"
                class="btn-primary"
              >
                Add Target
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script>
// Additional script for modal state
export default {
  data() {
    return {
      newTargetType: 'channel',
      newTargetId: '',
      newTargetLevel: 1,
    }
  },
  watch: {
    showAddTargetModal(val) {
      if (val) {
        this.newTargetType = 'channel'
        this.newTargetId = ''
        this.newTargetLevel = 1
      }
    }
  }
}
</script>

<style scoped>
.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
}
.collapse-enter-to,
.collapse-leave-from {
  opacity: 1;
  max-height: 2000px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
