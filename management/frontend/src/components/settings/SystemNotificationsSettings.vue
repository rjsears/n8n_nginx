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

// Frequency options
const frequencyOptions = [
  { value: 'every_time', label: 'Every Time' },
  { value: 'once_per_15m', label: 'Once per 15 minutes' },
  { value: 'once_per_30m', label: 'Once per 30 minutes' },
  { value: 'once_per_hour', label: 'Once per hour' },
  { value: 'once_per_4h', label: 'Once per 4 hours' },
  { value: 'once_per_12h', label: 'Once per 12 hours' },
  { value: 'once_per_day', label: 'Once per day' },
  { value: 'once_per_week', label: 'Once per week' },
]

// Severity options
const severityOptions = [
  { value: 'info', label: 'Info', color: 'blue' },
  { value: 'warning', label: 'Warning', color: 'amber' },
  { value: 'critical', label: 'Critical', color: 'red' },
]

// Category grouping
const categoryInfo = {
  backup: { label: 'Backup Events', icon: CircleStackIcon, color: 'emerald' },
  container: { label: 'Container Events', icon: CubeIcon, color: 'blue' },
  system: { label: 'System Events', icon: CpuChipIcon, color: 'purple' },
  security: { label: 'Security Events', icon: ShieldCheckIcon, color: 'red' },
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
    notificationStore.error('Failed to load system notifications')
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

function toggleEvent(eventId) {
  if (expandedEvents.value.has(eventId)) {
    expandedEvents.value.delete(eventId)
  } else {
    expandedEvents.value.add(eventId)
  }
  expandedEvents.value = new Set(expandedEvents.value)
}

async function updateEvent(event, field, value) {
  try {
    const updateData = { [field]: value }
    await api.put(`/system-notifications/events/${event.id}`, updateData)

    // Update local state
    const idx = events.value.findIndex(e => e.id === event.id)
    if (idx !== -1) {
      events.value[idx] = { ...events.value[idx], [field]: value }
    }

    notificationStore.success(`Updated ${event.display_name}`)
  } catch (error) {
    console.error('Failed to update event:', error)
    notificationStore.error('Failed to update event')
  }
}

async function updateGlobalSettings(updates) {
  saving.value = true
  try {
    const response = await api.put('/system-notifications/global-settings', updates)
    globalSettings.value = response.data
    notificationStore.success('Global settings updated')
  } catch (error) {
    console.error('Failed to update global settings:', error)
    notificationStore.error('Failed to update settings')
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
    notificationStore.success('Target added')
    showAddTargetModal.value = false
  } catch (error) {
    console.error('Failed to add target:', error)
    notificationStore.error(error.response?.data?.detail || 'Failed to add target')
  }
}

async function removeTarget(eventId, targetId) {
  try {
    await api.delete(`/system-notifications/events/${eventId}/targets/${targetId}`)
    await loadEvents()
    notificationStore.success('Target removed')
  } catch (error) {
    console.error('Failed to remove target:', error)
    notificationStore.error('Failed to remove target')
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
      <div class="bg-surface rounded-lg p-4 border border-[var(--color-border)]">
        <div class="flex items-center gap-3">
          <div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-500/20">
            <BellIcon class="h-5 w-5 text-emerald-500" />
          </div>
          <div>
            <p class="text-2xl font-bold text-primary">{{ enabledEventsCount }}/{{ totalEventsCount }}</p>
            <p class="text-xs text-secondary">Events Enabled</p>
          </div>
        </div>
      </div>

      <!-- Maintenance Mode -->
      <div
        :class="[
          'rounded-lg p-4 border cursor-pointer transition-all',
          globalSettings?.maintenance_mode
            ? 'bg-amber-50 dark:bg-amber-500/10 border-amber-300 dark:border-amber-500/30'
            : 'bg-surface border-[var(--color-border)] hover:border-gray-300 dark:hover:border-gray-600'
        ]"
        @click="toggleMaintenanceMode"
      >
        <div class="flex items-center gap-3">
          <div :class="[
            'p-2 rounded-lg',
            globalSettings?.maintenance_mode ? 'bg-amber-200 dark:bg-amber-500/30' : 'bg-gray-100 dark:bg-gray-700'
          ]">
            <PauseCircleIcon :class="['h-5 w-5', globalSettings?.maintenance_mode ? 'text-amber-600' : 'text-gray-500']" />
          </div>
          <div>
            <p :class="['font-semibold', globalSettings?.maintenance_mode ? 'text-amber-700 dark:text-amber-400' : 'text-primary']">
              {{ globalSettings?.maintenance_mode ? 'ON' : 'OFF' }}
            </p>
            <p class="text-xs text-secondary">Maintenance Mode</p>
          </div>
        </div>
      </div>

      <!-- Quiet Hours -->
      <div
        :class="[
          'rounded-lg p-4 border',
          globalSettings?.quiet_hours_enabled
            ? 'bg-indigo-50 dark:bg-indigo-500/10 border-indigo-300 dark:border-indigo-500/30'
            : 'bg-surface border-[var(--color-border)]'
        ]"
      >
        <div class="flex items-center gap-3">
          <div :class="[
            'p-2 rounded-lg',
            globalSettings?.quiet_hours_enabled ? 'bg-indigo-200 dark:bg-indigo-500/30' : 'bg-gray-100 dark:bg-gray-700'
          ]">
            <MoonIcon :class="['h-5 w-5', globalSettings?.quiet_hours_enabled ? 'text-indigo-600' : 'text-gray-500']" />
          </div>
          <div>
            <p v-if="globalSettings?.quiet_hours_enabled" class="font-semibold text-indigo-700 dark:text-indigo-400">
              {{ globalSettings.quiet_hours_start }} - {{ globalSettings.quiet_hours_end }}
            </p>
            <p v-else class="font-semibold text-primary">Disabled</p>
            <p class="text-xs text-secondary">Quiet Hours</p>
          </div>
        </div>
      </div>

      <!-- Rate Limit Status -->
      <div class="bg-surface rounded-lg p-4 border border-[var(--color-border)]">
        <div class="flex items-center gap-3">
          <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
            <ClockIcon class="h-5 w-5 text-blue-500" />
          </div>
          <div>
            <p class="text-2xl font-bold text-primary">
              {{ globalSettings?.notifications_this_hour || 0 }}/{{ globalSettings?.max_notifications_per_hour || 50 }}
            </p>
            <p class="text-xs text-secondary">This Hour</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Section Tabs -->
    <div class="flex gap-1 p-1 bg-surface-hover rounded-lg overflow-x-auto">
      <button
        v-for="section in [
          { id: 'events', label: 'Notification Events', icon: BellAlertIcon },
          { id: 'global', label: 'Global Settings', icon: Cog6ToothIcon },
          { id: 'containers', label: 'Container Config', icon: CubeIcon },
          { id: 'history', label: 'History', icon: DocumentTextIcon },
        ]"
        :key="section.id"
        @click="activeSection = section.id"
        :class="[
          'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all whitespace-nowrap',
          activeSection === section.id
            ? 'bg-surface text-primary shadow-sm'
            : 'text-secondary hover:text-primary'
        ]"
      >
        <component :is="section.icon" class="h-4 w-4" />
        {{ section.label }}
      </button>
    </div>

    <LoadingSpinner v-if="loading" size="lg" text="Loading notification settings..." class="py-12" />

    <template v-else>
      <!-- Events Section -->
      <div v-if="activeSection === 'events'" class="space-y-4">
        <div v-for="(categoryEvents, category) in eventsByCategory" :key="category" class="space-y-2">
          <!-- Category Header -->
          <div class="flex items-center gap-2 px-2 py-1">
            <component
              :is="categoryInfo[category]?.icon || BellIcon"
              :class="['h-5 w-5', `text-${categoryInfo[category]?.color || 'gray'}-500`]"
            />
            <h3 class="font-semibold text-primary">{{ categoryInfo[category]?.label || category }}</h3>
            <span class="text-xs text-secondary">({{ categoryEvents.length }})</span>
          </div>

          <!-- Event Cards -->
          <div class="space-y-2">
            <div
              v-for="event in categoryEvents"
              :key="event.id"
              class="bg-surface rounded-lg border border-[var(--color-border)] overflow-hidden"
            >
              <!-- Event Header -->
              <div
                @click="toggleEvent(event.id)"
                class="flex items-center gap-3 p-4 cursor-pointer hover:bg-surface-hover transition-colors"
              >
                <!-- Icon -->
                <div
                  :class="[
                    'flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center',
                    event.enabled ? `bg-${getSeverityColor(event.severity)}-100 dark:bg-${getSeverityColor(event.severity)}-500/20` : 'bg-gray-100 dark:bg-gray-700'
                  ]"
                >
                  <component
                    :is="getIcon(event.icon)"
                    :class="[
                      'h-5 w-5',
                      event.enabled ? `text-${getSeverityColor(event.severity)}-500` : 'text-gray-400'
                    ]"
                  />
                </div>

                <!-- Event Info -->
                <div class="flex-1 min-w-0">
                  <p :class="['font-medium', event.enabled ? 'text-primary' : 'text-secondary']">
                    {{ event.display_name }}
                  </p>
                  <p class="text-xs text-secondary truncate">{{ event.description }}</p>
                </div>

                <!-- Quick Stats -->
                <div class="flex items-center gap-3">
                  <!-- Targets Count -->
                  <span class="text-xs text-secondary">
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
                  <label class="relative inline-flex items-center cursor-pointer" @click.stop>
                    <input
                      type="checkbox"
                      :checked="event.enabled"
                      @change="updateEvent(event, 'enabled', $event.target.checked)"
                      class="sr-only peer"
                    />
                    <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-emerald-500"></div>
                  </label>

                  <!-- Chevron -->
                  <ChevronRightIcon
                    :class="[
                      'h-5 w-5 text-gray-400 transition-transform duration-200',
                      expandedEvents.has(event.id) ? 'rotate-90' : ''
                    ]"
                  />
                </div>
              </div>

              <!-- Expanded Content -->
              <Transition name="expand">
                <div v-if="expandedEvents.has(event.id)" class="border-t border-[var(--color-border)] bg-surface-hover">
                  <div class="p-4 space-y-4">
                    <!-- Frequency & Rate Limiting -->
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <label class="block text-xs font-medium text-secondary mb-1">Frequency</label>
                        <select
                          :value="event.frequency"
                          @change="updateEvent(event, 'frequency', $event.target.value)"
                          class="select-field w-full text-sm"
                        >
                          <option v-for="opt in frequencyOptions" :key="opt.value" :value="opt.value">
                            {{ opt.label }}
                          </option>
                        </select>
                      </div>
                      <div>
                        <label class="block text-xs font-medium text-secondary mb-1">Severity</label>
                        <select
                          :value="event.severity"
                          @change="updateEvent(event, 'severity', $event.target.value)"
                          class="select-field w-full text-sm"
                        >
                          <option v-for="opt in severityOptions" :key="opt.value" :value="opt.value">
                            {{ opt.label }}
                          </option>
                        </select>
                      </div>
                      <div v-if="event.frequency === 'every_time'">
                        <label class="block text-xs font-medium text-secondary mb-1">Cooldown (minutes)</label>
                        <input
                          type="number"
                          :value="event.cooldown_minutes"
                          @change="updateEvent(event, 'cooldown_minutes', parseInt($event.target.value))"
                          min="0"
                          class="input-field w-full text-sm"
                        />
                      </div>
                    </div>

                    <!-- Flapping Detection (for every_time events) -->
                    <div v-if="event.frequency === 'every_time'" class="p-3 rounded-lg bg-surface border border-[var(--color-border)]">
                      <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-2">
                          <ArrowPathIcon class="h-4 w-4 text-amber-500" />
                          <span class="text-sm font-medium text-primary">Flapping Detection</span>
                        </div>
                        <label class="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            :checked="event.flapping_enabled"
                            @change="updateEvent(event, 'flapping_enabled', $event.target.checked)"
                            class="sr-only peer"
                          />
                          <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-amber-500"></div>
                        </label>
                      </div>
                      <div v-if="event.flapping_enabled" class="grid grid-cols-3 gap-3 text-xs">
                        <div>
                          <label class="block text-secondary mb-1">Threshold Count</label>
                          <input
                            type="number"
                            :value="event.flapping_threshold_count"
                            @change="updateEvent(event, 'flapping_threshold_count', parseInt($event.target.value))"
                            min="2"
                            class="input-field w-full text-sm"
                          />
                        </div>
                        <div>
                          <label class="block text-secondary mb-1">Window (minutes)</label>
                          <input
                            type="number"
                            :value="event.flapping_threshold_minutes"
                            @change="updateEvent(event, 'flapping_threshold_minutes', parseInt($event.target.value))"
                            min="1"
                            class="input-field w-full text-sm"
                          />
                        </div>
                        <div>
                          <label class="block text-secondary mb-1">Summary Interval</label>
                          <input
                            type="number"
                            :value="event.flapping_summary_interval"
                            @change="updateEvent(event, 'flapping_summary_interval', parseInt($event.target.value))"
                            min="1"
                            class="input-field w-full text-sm"
                          />
                        </div>
                      </div>
                    </div>

                    <!-- Targets -->
                    <div class="space-y-2">
                      <div class="flex items-center justify-between">
                        <span class="text-sm font-medium text-primary">Notification Targets</span>
                        <button
                          @click="openAddTargetModal(event)"
                          class="flex items-center gap-1 px-2 py-1 text-xs text-blue-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-500/10 rounded transition-colors"
                        >
                          <PlusIcon class="h-4 w-4" />
                          Add Target
                        </button>
                      </div>

                      <div v-if="!event.targets || event.targets.length === 0" class="text-sm text-secondary italic p-2">
                        No targets configured. Add channels or groups to receive notifications.
                      </div>

                      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-2">
                        <!-- L1 Targets -->
                        <div class="space-y-1">
                          <p class="text-xs font-medium text-secondary uppercase tracking-wide">L1 (Primary)</p>
                          <div v-for="target in event.targets.filter(t => t.escalation_level === 1)" :key="target.id"
                            class="flex items-center justify-between p-2 rounded bg-surface border border-[var(--color-border)]"
                          >
                            <div class="flex items-center gap-2">
                              <span :class="[
                                'w-2 h-2 rounded-full',
                                target.target_type === 'channel' ? 'bg-blue-500' : 'bg-purple-500'
                              ]"></span>
                              <span class="text-sm text-primary">
                                {{ target.target_type === 'channel' ? target.channel_name : target.group_name }}
                              </span>
                              <span class="text-xs text-secondary">
                                ({{ target.target_type }})
                              </span>
                            </div>
                            <button
                              @click="removeTarget(event.id, target.id)"
                              class="p-1 text-gray-400 hover:text-red-500 rounded transition-colors"
                            >
                              <TrashIcon class="h-4 w-4" />
                            </button>
                          </div>
                          <div v-if="!event.targets.some(t => t.escalation_level === 1)" class="text-xs text-secondary italic p-2">
                            No L1 targets
                          </div>
                        </div>

                        <!-- L2 Targets -->
                        <div class="space-y-1">
                          <p class="text-xs font-medium text-secondary uppercase tracking-wide">L2 (Escalation)</p>
                          <div v-for="target in event.targets.filter(t => t.escalation_level === 2)" :key="target.id"
                            class="flex items-center justify-between p-2 rounded bg-surface border border-[var(--color-border)]"
                          >
                            <div class="flex items-center gap-2">
                              <span :class="[
                                'w-2 h-2 rounded-full',
                                target.target_type === 'channel' ? 'bg-blue-500' : 'bg-purple-500'
                              ]"></span>
                              <span class="text-sm text-primary">
                                {{ target.target_type === 'channel' ? target.channel_name : target.group_name }}
                              </span>
                              <span class="text-xs text-secondary">
                                ({{ target.target_type }})
                              </span>
                            </div>
                            <button
                              @click="removeTarget(event.id, target.id)"
                              class="p-1 text-gray-400 hover:text-red-500 rounded transition-colors"
                            >
                              <TrashIcon class="h-4 w-4" />
                            </button>
                          </div>
                          <div v-if="!event.targets.some(t => t.escalation_level === 2)" class="text-xs text-secondary italic p-2">
                            No L2 targets
                          </div>
                        </div>
                      </div>

                      <!-- Escalation Settings -->
                      <div v-if="event.targets?.some(t => t.escalation_level === 2)" class="flex items-center gap-4 pt-2 border-t border-[var(--color-border)]">
                        <label class="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            :checked="event.escalation_enabled"
                            @change="updateEvent(event, 'escalation_enabled', $event.target.checked)"
                            class="w-4 h-4 rounded border-gray-300 text-blue-500 focus:ring-blue-500"
                          />
                          <span class="text-sm text-primary">Enable L2 Escalation</span>
                        </label>
                        <div v-if="event.escalation_enabled" class="flex items-center gap-2">
                          <span class="text-sm text-secondary">after</span>
                          <input
                            type="number"
                            :value="event.escalation_timeout_minutes"
                            @change="updateEvent(event, 'escalation_timeout_minutes', parseInt($event.target.value))"
                            min="1"
                            class="input-field w-16 text-sm"
                          />
                          <span class="text-sm text-secondary">minutes</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </Transition>
            </div>
          </div>
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
              Add a channel or group to receive notifications for "{{ selectedEventForTarget?.display_name }}"
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
                  <option :value="1">L1 - Primary</option>
                  <option :value="2">L2 - Escalation</option>
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
.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease-out;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 1000px;
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
