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
const expandedContainerConfigs = ref(new Set())
const showMaintenanceModal = ref(false)
const showQuietHoursModal = ref(false)
const showAddTargetModal = ref(false)
const selectedEventForTarget = ref(null)
const expandedRateLimiting = ref(false)
const expandedDailyDigest = ref(false)
const expandedHistoryItems = ref(new Set())

// Maintenance mode form state
const maintenanceDuration = ref('1h')
const maintenanceReason = ref('')

// Quiet hours form state
const quietHoursStart = ref('22:00')
const quietHoursEnd = ref('07:00')

// Add target form state
const newTargetEscalationTimeout = ref(30)

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

// Rate limit presets
const rateLimitPresets = [
  { value: 25, label: 'Low (25)' },
  { value: 50, label: 'Medium (50)' },
  { value: 100, label: 'Standard (100)' },
  { value: 200, label: 'High (200)' },
  { value: 500, label: 'Maximum (500)' },
]

// Get rate limit severity class based on value
const getRateLimitSeverityClass = (value) => {
  if (value <= 50) {
    return 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400'
  } else if (value <= 150) {
    return 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400'
  } else {
    return 'bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-400'
  }
}

// Category grouping
const categoryInfo = {
  backup: { label: 'Backup Events', icon: CircleStackIcon, color: 'emerald', description: 'Notifications for backup operations' },
  container: { label: 'Container Events', icon: CubeIcon, color: 'blue', description: 'Docker container health and status alerts' },
  system: { label: 'System Events', icon: CpuChipIcon, color: 'purple', description: 'Host system resource monitoring' },
  ssl: { label: 'SSL Certificate Events', icon: ShieldCheckIcon, color: 'amber', description: 'SSL/TLS certificate expiration monitoring' },
  security: { label: 'Security Events', icon: ShieldExclamationIcon, color: 'red', description: 'Security and access notifications' },
}

// SSL configuration status
const sslConfigured = ref(false)

// Computed
const eventsByCategory = computed(() => {
  const grouped = {}
  for (const event of events.value) {
    // Hide ssl category if SSL is not configured
    if (event.category === 'ssl' && !sslConfigured.value) {
      continue
    }
    if (!grouped[event.category]) {
      grouped[event.category] = []
    }
    grouped[event.category].push(event)
  }
  return grouped
})

// Helper function to check if event has targets
function eventHasTargets(event) {
  return event.targets && event.targets.length > 0
}

// An event is only truly "enabled" if it has targets
const enabledEventsCount = computed(() => {
  return events.value.filter(e => e.enabled && eventHasTargets(e)).length
})

const totalEventsCount = computed(() => events.value.length)

const hasNoTargets = computed(() => {
  return (event) => !eventHasTargets(event)
})

// Check if any container events have targets configured
const containerEventsHaveTargets = computed(() => {
  const containerEvents = events.value.filter(e => e.category === 'container')
  return containerEvents.some(e => eventHasTargets(e))
})

// Check if a specific category has any events with targets
function categoryHasTargets(category) {
  const categoryEvents = events.value.filter(e => e.category === category)
  return categoryEvents.some(e => eventHasTargets(e))
}

// Get container config status - returns 'monitoring', 'no_targets', or 'disabled'
function getContainerConfigStatus(config) {
  if (!config.enabled) return 'disabled'
  if (!containerEventsHaveTargets.value) return 'no_targets'
  return 'monitoring'
}

// Get channels available for adding (excluding already assigned to this event)
const availableChannelsForTarget = computed(() => {
  if (!selectedEventForTarget.value) return channels.value
  const usedChannelIds = (selectedEventForTarget.value.targets || [])
    .filter(t => t.target_type === 'channel')
    .map(t => t.channel_id)
  return channels.value.filter(c => !usedChannelIds.includes(c.id))
})

// Get groups available for adding (excluding already assigned to this event)
const availableGroupsForTarget = computed(() => {
  if (!selectedEventForTarget.value) return groups.value
  const usedGroupIds = (selectedEventForTarget.value.targets || [])
    .filter(t => t.target_type === 'group')
    .map(t => t.group_id)
  return groups.value.filter(g => !usedGroupIds.includes(g.id))
})

// Check if we're currently in quiet hours
const isInQuietHours = computed(() => {
  if (!globalSettings.value?.quiet_hours_enabled) return false

  const now = new Date()
  const currentTime = now.getHours() * 60 + now.getMinutes()

  const [startHour, startMin] = (globalSettings.value.quiet_hours_start || '22:00').split(':').map(Number)
  const [endHour, endMin] = (globalSettings.value.quiet_hours_end || '07:00').split(':').map(Number)

  const startMinutes = startHour * 60 + startMin
  const endMinutes = endHour * 60 + endMin

  // Handle overnight quiet hours (e.g., 22:00 - 07:00)
  if (startMinutes > endMinutes) {
    return currentTime >= startMinutes || currentTime < endMinutes
  }
  return currentTime >= startMinutes && currentTime < endMinutes
})

// Format maintenance end time for display
function formatMaintenanceTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = date - now

  if (diffMs <= 0) return 'Expired'

  const hours = Math.floor(diffMs / (1000 * 60 * 60))
  const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60))

  if (hours > 0) {
    return `${hours}h ${minutes}m remaining`
  }
  return `${minutes}m remaining`
}

// Format event type for display (e.g., 'container_unhealthy' -> 'Container Unhealthy')
function formatEventType(eventType) {
  if (!eventType) return ''
  return eventType
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

// Format relative time for display
function formatRelativeTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now - date

  const minutes = Math.floor(diffMs / (1000 * 60))
  const hours = Math.floor(diffMs / (1000 * 60 * 60))
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  })
}

// Get icon for event type
function getEventIcon(eventType) {
  const iconMapping = {
    container_unhealthy: XCircleIcon,
    container_healthy: CheckCircleIcon,
    container_restart: ArrowPathIcon,
    backup_completed: CheckCircleIcon,
    backup_failed: XCircleIcon,
    cpu_threshold: CpuChipIcon,
    memory_threshold: CpuChipIcon,
    disk_threshold: CircleStackIcon,
    security_alert: ShieldExclamationIcon,
  }
  return iconMapping[eventType] || BellIcon
}

// Methods
async function loadData() {
  loading.value = true
  try {
    await Promise.all([
      loadEvents(),
      loadGlobalSettings(),
      loadContainerConfigs(),
      loadChannelsAndGroups(),
      loadSslStatus(),
    ])
  } catch (error) {
    console.error('Failed to load system notifications data:', error)
    notificationStore.error('Failed to load notification settings')
  } finally {
    loading.value = false
  }
}

async function loadSslStatus() {
  try {
    // Check if SSL is configured via the health endpoint (quick mode)
    const response = await api.get('/system/health/full?quick=true')
    sslConfigured.value = response.data.ssl_configured || false
  } catch (error) {
    console.error('Failed to load SSL status:', error)
    sslConfigured.value = false
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
    // Initialize quiet hours form with current values
    if (response.data) {
      quietHoursStart.value = response.data.quiet_hours_start || '22:00'
      quietHoursEnd.value = response.data.quiet_hours_end || '07:00'
    }
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

function toggleContainerConfig(configId) {
  if (expandedContainerConfigs.value.has(configId)) {
    expandedContainerConfigs.value.delete(configId)
  } else {
    expandedContainerConfigs.value.add(configId)
  }
  expandedContainerConfigs.value = new Set(expandedContainerConfigs.value)
}

function getContainerConfigSummary(config) {
  const monitors = []
  if (config.monitor_stopped) monitors.push('Stopped')
  if (config.monitor_unhealthy) monitors.push('Unhealthy')
  if (config.monitor_restart) monitors.push('Restarts')
  if (config.monitor_high_cpu) monitors.push(`CPU >${config.cpu_threshold}%`)
  if (config.monitor_high_memory) monitors.push(`Memory >${config.memory_threshold}%`)

  if (monitors.length === 0) return 'No events monitored'
  return monitors.join(' • ')
}

async function updateContainerConfig(config, updates) {
  // Warn if enabling without targets configured
  if (updates.enabled === true && !containerEventsHaveTargets.value) {
    notificationStore.warning('No notification targets configured for container events. Go to Notification Events → Container Events to add targets.')
  }

  try {
    const response = await api.put(`/system-notifications/container-configs/${config.container_name}`, {
      ...config,
      ...updates
    })
    // Update local state
    const index = containerConfigs.value.findIndex(c => c.id === config.id)
    if (index !== -1) {
      containerConfigs.value[index] = response.data
    }
    notificationStore.success('Container config updated')
  } catch (error) {
    console.error('Failed to update container config:', error)
    notificationStore.error('Failed to update config')
  }
}

async function deleteContainerConfig(config) {
  if (!confirm(`Remove custom notification settings for ${config.container_name}? This will revert to default settings.`)) {
    return
  }

  try {
    await api.delete(`/system-notifications/container-configs/${config.container_name}`)
    containerConfigs.value = containerConfigs.value.filter(c => c.id !== config.id)
    expandedContainerConfigs.value.delete(config.id)
    notificationStore.success('Container config removed')
  } catch (error) {
    console.error('Failed to delete container config:', error)
    notificationStore.error('Failed to remove config')
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

function toggleHistoryItem(entryId) {
  if (expandedHistoryItems.value.has(entryId)) {
    expandedHistoryItems.value.delete(entryId)
  } else {
    expandedHistoryItems.value.add(entryId)
  }
  expandedHistoryItems.value = new Set(expandedHistoryItems.value)
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

async function updateEventThreshold(event, key, value) {
  try {
    // Merge with existing thresholds
    const updatedThresholds = { ...(event.thresholds || {}), [key]: value }
    await api.put(`/system-notifications/events/${event.id}`, { thresholds: updatedThresholds })

    // Update local state
    const idx = events.value.findIndex(e => e.id === event.id)
    if (idx !== -1) {
      events.value[idx] = { ...events.value[idx], thresholds: updatedThresholds }
    }

    notificationStore.success(`Threshold updated for "${event.display_name}"`)
  } catch (error) {
    console.error('Failed to update threshold:', error)
    notificationStore.error(`Failed to update threshold for "${event.display_name}"`)
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

async function enableMaintenanceMode() {
  // Calculate the end time based on duration
  let until = null
  if (maintenanceDuration.value !== 'indefinite') {
    const now = new Date()
    const durationMap = {
      '1h': 60,
      '2h': 120,
      '4h': 240,
      '8h': 480,
      '12h': 720,
      '24h': 1440,
    }
    const minutes = durationMap[maintenanceDuration.value] || 60
    until = new Date(now.getTime() + minutes * 60 * 1000).toISOString()
  }

  await updateGlobalSettings({
    maintenance_mode: true,
    maintenance_until: until,
    maintenance_reason: maintenanceReason.value || null,
  })

  // Reset form
  maintenanceDuration.value = '1h'
  maintenanceReason.value = ''
  showMaintenanceModal.value = false
}

async function saveQuietHours() {
  await updateGlobalSettings({
    quiet_hours_enabled: true,
    quiet_hours_start: quietHoursStart.value,
    quiet_hours_end: quietHoursEnd.value,
  })
  showQuietHoursModal.value = false
}

async function disableQuietHours() {
  await updateGlobalSettings({
    quiet_hours_enabled: false,
  })
  showQuietHoursModal.value = false
}

function openAddTargetModal(event) {
  selectedEventForTarget.value = event
  showAddTargetModal.value = true
}

async function addTarget(eventId, targetType, targetId, level, escalationTimeout = 30) {
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

    // Include escalation timeout for L2 targets
    if (level === 2) {
      data.escalation_timeout_minutes = escalationTimeout
    }

    await api.post(`/system-notifications/events/${eventId}/targets`, data)
    await loadEvents()
    notificationStore.success('Notification target added successfully')
    showAddTargetModal.value = false

    // Reset form
    newTargetEscalationTimeout.value = 30
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

// State for "Apply to All" modal
const showApplyToAllModal = ref(false)
const applyToAllCategory = ref(null)
const applyToAllTargetType = ref('channel')
const applyToAllTargetId = ref(null)
const applyToAllLevel = ref(1)
const applyingToAll = ref(false)

function openApplyToAllModal(category) {
  applyToAllCategory.value = category
  applyToAllTargetType.value = 'channel'
  applyToAllTargetId.value = null
  applyToAllLevel.value = 1
  showApplyToAllModal.value = true
}

async function applyTargetToAllEvents() {
  if (!applyToAllCategory.value || !applyToAllTargetId.value) {
    notificationStore.error('Please select a target')
    return
  }

  applyingToAll.value = true
  const categoryEvents = events.value.filter(e => e.category === applyToAllCategory.value)
  let successCount = 0
  let skipCount = 0

  try {
    for (const event of categoryEvents) {
      // Check if this target is already added to this event
      const existingTarget = event.targets?.find(t =>
        t.target_type === applyToAllTargetType.value &&
        (applyToAllTargetType.value === 'channel'
          ? t.channel_id === applyToAllTargetId.value
          : t.group_id === applyToAllTargetId.value) &&
        t.escalation_level === applyToAllLevel.value
      )

      if (existingTarget) {
        skipCount++
        continue
      }

      try {
        const data = {
          target_type: applyToAllTargetType.value,
          escalation_level: applyToAllLevel.value,
        }
        if (applyToAllTargetType.value === 'channel') {
          data.channel_id = applyToAllTargetId.value
        } else {
          data.group_id = applyToAllTargetId.value
        }

        await api.post(`/system-notifications/events/${event.id}/targets`, data)
        successCount++
      } catch (error) {
        console.error(`Failed to add target to event ${event.id}:`, error)
      }
    }

    await loadEvents()

    if (successCount > 0) {
      notificationStore.success(`Target added to ${successCount} event(s)${skipCount > 0 ? ` (${skipCount} already had it)` : ''}`)
    } else if (skipCount > 0) {
      notificationStore.info(`All ${skipCount} events already have this target`)
    }

    showApplyToAllModal.value = false
  } catch (error) {
    console.error('Failed to apply targets:', error)
    notificationStore.error('Failed to apply targets to all events')
  } finally {
    applyingToAll.value = false
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
  // Only count as enabled if event is enabled AND has targets
  const enabled = categoryEvents.filter(e => e.enabled && eventHasTargets(e)).length
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
    <!-- Quick Stats / Status Bar - Buttons on left, info on right -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <!-- Maintenance Mode Button -->
      <div
        :class="[
          'rounded-lg p-4 border cursor-pointer transition-all',
          globalSettings?.maintenance_mode
            ? 'bg-green-50 dark:bg-green-500/10 border-green-400 dark:border-green-500/40 ring-2 ring-green-400/50'
            : 'bg-surface border-[var(--color-border)] hover:border-amber-300 dark:hover:border-amber-500/50 hover:bg-amber-50/50 dark:hover:bg-amber-500/5'
        ]"
        @click="toggleMaintenanceMode"
      >
        <div class="flex items-center gap-3">
          <div :class="[
            'p-2 rounded-lg',
            globalSettings?.maintenance_mode ? 'bg-green-200 dark:bg-green-500/30' : 'bg-amber-100 dark:bg-amber-500/20'
          ]">
            <PauseCircleIcon :class="['h-5 w-5', globalSettings?.maintenance_mode ? 'text-green-600' : 'text-amber-500']" />
          </div>
          <div>
            <p :class="['font-semibold', globalSettings?.maintenance_mode ? 'text-green-700 dark:text-green-400' : 'text-primary']">
              {{ globalSettings?.maintenance_mode ? 'ACTIVE' : 'Maintenance' }}
            </p>
            <p v-if="globalSettings?.maintenance_mode && globalSettings.maintenance_until" class="text-xs text-green-600 dark:text-green-400">
              Until {{ formatMaintenanceTime(globalSettings.maintenance_until) }}
            </p>
            <p v-else class="text-xs text-secondary">Click to enable</p>
          </div>
        </div>
      </div>

      <!-- Quiet Hours Button -->
      <div
        :class="[
          'rounded-lg p-4 border cursor-pointer transition-all',
          isInQuietHours
            ? 'bg-indigo-900 dark:bg-indigo-950 border-indigo-500 dark:border-indigo-400/50 ring-2 ring-indigo-400/50'
            : globalSettings?.quiet_hours_enabled
              ? 'bg-indigo-50 dark:bg-indigo-500/10 border-indigo-300 dark:border-indigo-500/30'
              : 'bg-surface border-[var(--color-border)] hover:border-indigo-300 dark:hover:border-indigo-500/50 hover:bg-indigo-50/50 dark:hover:bg-indigo-500/5'
        ]"
        @click="showQuietHoursModal = true"
      >
        <div class="flex items-center gap-3">
          <div :class="[
            'p-2 rounded-lg relative',
            isInQuietHours ? 'bg-indigo-800 dark:bg-indigo-800' : globalSettings?.quiet_hours_enabled ? 'bg-indigo-200 dark:bg-indigo-500/30' : 'bg-indigo-100 dark:bg-indigo-500/20'
          ]">
            <MoonIcon :class="['h-5 w-5', isInQuietHours ? 'text-yellow-300' : globalSettings?.quiet_hours_enabled ? 'text-indigo-600' : 'text-indigo-400']" />
            <!-- Stars decoration when in quiet hours -->
            <span v-if="isInQuietHours" class="absolute -top-1 -right-1 text-yellow-300 text-xs">✦</span>
            <span v-if="isInQuietHours" class="absolute -bottom-0.5 -left-0.5 text-yellow-200 text-[10px]">✧</span>
          </div>
          <div>
            <p v-if="isInQuietHours" class="font-semibold text-indigo-100">
              Quiet Mode Active
            </p>
            <p v-else-if="globalSettings?.quiet_hours_enabled" class="font-semibold text-indigo-700 dark:text-indigo-400">
              {{ globalSettings.quiet_hours_start }} - {{ globalSettings.quiet_hours_end }}
            </p>
            <p v-else class="font-semibold text-primary">Quiet Hours</p>
            <p :class="['text-xs', isInQuietHours ? 'text-indigo-300' : 'text-secondary']">
              {{ isInQuietHours ? 'Non-critical muted' : globalSettings?.quiet_hours_enabled ? 'Scheduled' : 'Click to configure' }}
            </p>
          </div>
        </div>
      </div>

      <!-- Events Enabled Info -->
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

      <!-- Rate Limit Status Info -->
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

    <!-- Section Tabs - Lighter, more translucent with colored icons when inactive -->
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-400 dark:border-gray-700 p-1.5 flex gap-1.5 overflow-x-auto">
      <button
        v-for="(section, idx) in [
          { id: 'events', label: 'Notification Events', icon: BellAlertIcon, iconColor: 'text-emerald-500', bgActive: 'bg-emerald-500/15 dark:bg-emerald-500/20', textActive: 'text-emerald-700 dark:text-emerald-400', borderActive: 'border-emerald-500/30' },
          { id: 'global', label: 'Global Settings', icon: Cog6ToothIcon, iconColor: 'text-blue-500', bgActive: 'bg-blue-500/15 dark:bg-blue-500/20', textActive: 'text-blue-700 dark:text-blue-400', borderActive: 'border-blue-500/30' },
          { id: 'containers', label: 'Container Config', icon: CubeIcon, iconColor: 'text-purple-500', bgActive: 'bg-purple-500/15 dark:bg-purple-500/20', textActive: 'text-purple-700 dark:text-purple-400', borderActive: 'border-purple-500/30' },
          { id: 'history', label: 'History', icon: DocumentTextIcon, iconColor: 'text-amber-500', bgActive: 'bg-amber-500/15 dark:bg-amber-500/20', textActive: 'text-amber-700 dark:text-amber-400', borderActive: 'border-amber-500/30' },
        ]"
        :key="section.id"
        @click="activeSection = section.id"
        :class="[
          'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap border',
          activeSection === section.id
            ? `${section.bgActive} ${section.textActive} ${section.borderActive}`
            : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700/50 border-transparent'
        ]"
      >
        <component :is="section.icon" :class="['h-5 w-5', activeSection === section.id ? '' : section.iconColor]" />
        {{ section.label }}
      </button>
    </div>

    <!-- Skeleton Loader for Events Section -->
    <div v-if="loading" class="space-y-4">
      <!-- Skeleton for Category Cards -->
      <div v-for="i in 4" :key="i" class="rounded-2xl shadow-lg overflow-hidden bg-white dark:bg-gray-800">
        <!-- Skeleton Header -->
        <div class="flex items-center justify-between p-5 bg-gray-50 dark:bg-gray-800/50">
          <div class="flex items-center gap-4">
            <div class="p-3 rounded-xl bg-gray-200 dark:bg-gray-700 animate-pulse">
              <div class="h-6 w-6"></div>
            </div>
            <div class="space-y-2">
              <div class="h-5 w-32 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
              <div class="h-3 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <div class="h-6 w-16 bg-gray-200 dark:bg-gray-700 rounded-full animate-pulse"></div>
            <div class="h-5 w-5 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
          </div>
        </div>
      </div>
    </div>

    <template v-else>
      <!-- Events Section -->
      <div v-if="activeSection === 'events'" class="space-y-4">
        <!-- Maintenance Mode Banner -->
        <div v-if="globalSettings?.maintenance_mode" class="bg-green-50 dark:bg-green-500/10 border-2 border-green-400 dark:border-green-500/50 rounded-xl p-4 flex items-center gap-4">
          <div class="p-3 rounded-xl bg-green-200 dark:bg-green-500/30">
            <PauseCircleIcon class="h-8 w-8 text-green-600 dark:text-green-400" />
          </div>
          <div class="flex-1">
            <h3 class="font-bold text-green-700 dark:text-green-400 text-lg">Maintenance Mode Active</h3>
            <p class="text-sm text-green-600 dark:text-green-300">
              All system notifications are completely disabled. No alerts will be sent or stored.
              <span v-if="globalSettings.maintenance_until" class="font-medium">
                ({{ formatMaintenanceTime(globalSettings.maintenance_until) }})
              </span>
            </p>
          </div>
          <button
            @click="toggleMaintenanceMode"
            class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors"
          >
            End Maintenance
          </button>
        </div>

        <!-- Collapsible Category Cards -->
        <div
          v-for="(categoryEvents, category) in eventsByCategory"
          :key="category"
          :class="[
            'rounded-2xl shadow-lg overflow-hidden transition-all',
            globalSettings?.maintenance_mode
              ? 'bg-gray-100 dark:bg-gray-800/50 opacity-60 pointer-events-none'
              : 'bg-white dark:bg-gray-800'
          ]"
        >
          <!-- Category Header (Clickable) - Lighter, more translucent -->
          <div
            @click="!globalSettings?.maintenance_mode && toggleCategory(category)"
            :class="[
              'flex items-center justify-between p-5 transition-all',
              globalSettings?.maintenance_mode
                ? 'cursor-not-allowed'
                : 'cursor-pointer',
              globalSettings?.maintenance_mode
                ? ''
                : expandedCategories.has(category)
                    ? (category === 'backup' ? 'bg-emerald-50 dark:bg-emerald-500/10 border-b border-emerald-200 dark:border-emerald-500/20'
                        : category === 'container' ? 'bg-blue-50 dark:bg-blue-500/10 border-b border-blue-200 dark:border-blue-500/20'
                        : category === 'security' ? 'bg-red-50 dark:bg-red-500/10 border-b border-red-200 dark:border-red-500/20'
                        : category === 'ssl' ? 'bg-amber-50 dark:bg-amber-500/10 border-b border-amber-200 dark:border-amber-500/20'
                        : 'bg-purple-50 dark:bg-purple-500/10 border-b border-purple-200 dark:border-purple-500/20')
                    : 'hover:bg-gray-50 dark:hover:bg-gray-700/50'
            ]"
          >
            <div class="flex items-center gap-4">
              <div :class="[
                'p-3 rounded-xl',
                expandedCategories.has(category)
                  ? category === 'backup' ? 'bg-emerald-100 dark:bg-emerald-500/20'
                    : category === 'container' ? 'bg-blue-100 dark:bg-blue-500/20'
                    : category === 'security' ? 'bg-red-100 dark:bg-red-500/20'
                    : category === 'ssl' ? 'bg-amber-100 dark:bg-amber-500/20'
                    : 'bg-purple-100 dark:bg-purple-500/20'
                  : 'bg-gray-100 dark:bg-gray-700'
              ]">
                <component
                  :is="categoryInfo[category]?.icon || BellIcon"
                  :class="[
                    'h-6 w-6',
                    category === 'backup' ? 'text-emerald-500'
                      : category === 'container' ? 'text-blue-500'
                      : category === 'security' ? 'text-red-500'
                      : category === 'ssl' ? 'text-amber-500'
                      : 'text-purple-500'
                  ]"
                />
              </div>
              <div>
                <h3 :class="[
                  'font-bold text-lg',
                  expandedCategories.has(category)
                    ? category === 'backup' ? 'text-emerald-700 dark:text-emerald-400'
                      : category === 'container' ? 'text-blue-700 dark:text-blue-400'
                      : category === 'security' ? 'text-red-700 dark:text-red-400'
                      : category === 'ssl' ? 'text-amber-700 dark:text-amber-400'
                      : 'text-purple-700 dark:text-purple-400'
                    : 'text-primary'
                ]">
                  {{ categoryInfo[category]?.label || category }}
                </h3>
                <p class="text-sm text-secondary">
                  {{ categoryInfo[category]?.description }}
                </p>
              </div>
            </div>
            <div class="flex items-center gap-4">
              <div :class="[
                'px-4 py-2 rounded-full font-semibold text-sm',
                category === 'backup' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400'
                  : category === 'container' ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400'
                  : category === 'security' ? 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400'
                  : category === 'ssl' ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400'
                  : 'bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-400'
              ]">
                {{ getCategoryEventCounts(category).enabled }}/{{ getCategoryEventCounts(category).total }} enabled
              </div>
              <div class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700">
                <ChevronDownIcon v-if="expandedCategories.has(category)" class="h-5 w-5 text-secondary" />
                <ChevronRightIcon v-else class="h-5 w-5 text-secondary" />
              </div>
            </div>
          </div>

          <!-- Category Content (Collapsible) -->
          <Transition name="collapse">
            <div v-if="expandedCategories.has(category)" class="border-t border-gray-400 dark:border-gray-700">
              <div class="p-4 space-y-3">
                <!-- Quick Action: Apply Target to All Events -->
                <div class="flex items-center justify-between p-3 rounded-xl bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600">
                  <div class="flex items-center gap-3">
                    <div :class="[
                      'p-2 rounded-lg',
                      category === 'backup' ? 'bg-emerald-100 dark:bg-emerald-500/20'
                        : category === 'container' ? 'bg-blue-100 dark:bg-blue-500/20'
                        : category === 'security' ? 'bg-red-100 dark:bg-red-500/20'
                        : category === 'ssl' ? 'bg-amber-100 dark:bg-amber-500/20'
                        : 'bg-purple-100 dark:bg-purple-500/20'
                    ]">
                      <BellAlertIcon :class="[
                        'h-5 w-5',
                        category === 'backup' ? 'text-emerald-500'
                          : category === 'container' ? 'text-blue-500'
                          : category === 'security' ? 'text-red-500'
                          : category === 'ssl' ? 'text-amber-500'
                          : 'text-purple-500'
                      ]" />
                    </div>
                    <div>
                      <p class="text-sm font-medium text-primary">Quick Setup</p>
                      <p class="text-xs text-secondary">Add the same target to all events in this category</p>
                    </div>
                  </div>
                  <button
                    @click.stop="openApplyToAllModal(category)"
                    :class="[
                      'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all',
                      category === 'backup' ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200 dark:bg-emerald-500/20 dark:text-emerald-400 dark:hover:bg-emerald-500/30'
                        : category === 'container' ? 'bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-500/20 dark:text-blue-400 dark:hover:bg-blue-500/30'
                        : category === 'security' ? 'bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-500/20 dark:text-red-400 dark:hover:bg-red-500/30'
                        : category === 'ssl' ? 'bg-amber-100 text-amber-700 hover:bg-amber-200 dark:bg-amber-500/20 dark:text-amber-400 dark:hover:bg-amber-500/30'
                        : 'bg-purple-100 text-purple-700 hover:bg-purple-200 dark:bg-purple-500/20 dark:text-purple-400 dark:hover:bg-purple-500/30'
                    ]"
                  >
                    <PlusIcon class="h-4 w-4" />
                    Apply to All Events
                  </button>
                </div>

                <!-- Event Rows -->
                <div
                  v-for="event in categoryEvents"
                  :key="event.id"
                  class="rounded-lg border border-gray-400 dark:border-gray-700 overflow-hidden"
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
                          <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-400 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-emerald-500 peer-disabled:cursor-not-allowed"></div>
                        </label>
                      </div>
                    </div>
                  </div>

                  <!-- Expanded Settings Panel - Unified layout for all categories -->
                  <Transition name="collapse">
                    <div v-if="expandedEvents.has(event.id)" class="border-t border-gray-400 dark:border-gray-700">
                      <!-- Unified Clean Layout - No background color -->
                      <div class="p-6">
                        <div class="max-w-4xl mx-auto">
                          <!-- Settings Card -->
                          <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden border border-gray-400 dark:border-gray-700">
                            <!-- Header - Subtle colored top border only -->
                            <div :class="[
                              'px-6 py-4 border-b border-gray-400 dark:border-gray-700',
                              event.category === 'backup' ? 'border-t-4 border-t-emerald-400'
                                : event.category === 'container' ? 'border-t-4 border-t-blue-400'
                                : event.category === 'security' ? 'border-t-4 border-t-red-400'
                                : event.category === 'ssl' ? 'border-t-4 border-t-amber-400'
                                : 'border-t-4 border-t-purple-400'
                            ]">
                              <h4 class="font-semibold flex items-center gap-2 text-primary">
                                <component
                                  :is="categoryInfo[event.category]?.icon || BellIcon"
                                  :class="[
                                    'h-5 w-5',
                                    event.category === 'backup' ? 'text-emerald-500'
                                      : event.category === 'container' ? 'text-blue-500'
                                      : event.category === 'security' ? 'text-red-500'
                                      : event.category === 'ssl' ? 'text-amber-500'
                                      : 'text-purple-500'
                                  ]"
                                />
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
                                          ? sev.value === 'critical' ? 'border-red-400 bg-red-50 dark:bg-red-500/10'
                                            : sev.value === 'warning' ? 'border-amber-400 bg-amber-50 dark:bg-amber-500/10'
                                            : 'border-blue-400 bg-blue-50 dark:bg-blue-500/10'
                                          : 'border-gray-400 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-600'
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
                                    :class="[
                                      'w-full bg-gray-50 dark:bg-gray-700 border-2 rounded-xl px-4 py-3 text-primary',
                                      event.category === 'backup' ? 'border-gray-400 dark:border-gray-600 focus:border-emerald-400 focus:ring-emerald-400'
                                        : event.category === 'container' ? 'border-gray-400 dark:border-gray-600 focus:border-blue-400 focus:ring-blue-400'
                                        : event.category === 'security' ? 'border-gray-400 dark:border-gray-600 focus:border-red-400 focus:ring-red-400'
                                        : event.category === 'ssl' ? 'border-gray-400 dark:border-gray-600 focus:border-amber-400 focus:ring-amber-400'
                                        : 'border-gray-400 dark:border-gray-600 focus:border-purple-400 focus:ring-purple-400'
                                    ]"
                                  >
                                    <option v-for="opt in frequencyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                                  </select>
                                  <p class="text-xs text-secondary mt-2">{{ frequencyOptions.find(f => f.value === event.frequency)?.description }}</p>
                                </div>

                                <!-- Cooldown (if applicable) -->
                                <div v-if="event.frequency === 'every_time'">
                                  <label class="block text-sm font-semibold text-primary mb-2">Cooldown Period</label>
                                  <div class="bg-gray-50 dark:bg-gray-700 rounded-xl p-4 border border-gray-400 dark:border-gray-600">
                                    <input
                                      type="range"
                                      :value="event.cooldown_minutes"
                                      @input="updateEvent(event, 'cooldown_minutes', parseInt($event.target.value))"
                                      min="0"
                                      max="120"
                                      step="5"
                                      :class="[
                                        'w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-lg appearance-none cursor-pointer',
                                        event.category === 'backup' ? 'accent-emerald-500'
                                          : event.category === 'container' ? 'accent-blue-500'
                                          : event.category === 'security' ? 'accent-red-500'
                                          : event.category === 'ssl' ? 'accent-amber-500'
                                          : 'accent-purple-500'
                                      ]"
                                    />
                                    <div class="flex justify-between mt-2">
                                      <span class="text-xs text-secondary">0 min</span>
                                      <span :class="[
                                        'text-lg font-bold',
                                        event.category === 'backup' ? 'text-emerald-600 dark:text-emerald-400'
                                          : event.category === 'container' ? 'text-blue-600 dark:text-blue-400'
                                          : event.category === 'security' ? 'text-red-600 dark:text-red-400'
                                          : event.category === 'ssl' ? 'text-amber-600 dark:text-amber-400'
                                          : 'text-purple-600 dark:text-purple-400'
                                      ]">{{ event.cooldown_minutes }} min</span>
                                      <span class="text-xs text-secondary">120 min</span>
                                    </div>
                                  </div>
                                  <p class="text-xs text-secondary mt-2">Minimum time between duplicate notifications. Prevents alert fatigue from repeated events.</p>
                                </div>

                                <!-- Certificate Expiration Threshold (SSL events only) -->
                                <div v-if="event.event_type === 'certificate_expiring'">
                                  <label class="block text-sm font-semibold text-primary mb-2">Days Before Expiration</label>
                                  <div class="bg-amber-50 dark:bg-amber-500/10 rounded-xl p-4 border border-amber-200 dark:border-amber-500/20">
                                    <div class="flex items-center justify-between mb-3">
                                      <span class="text-sm text-amber-700 dark:text-amber-300">Alert when certificate expires in:</span>
                                      <span class="text-2xl font-bold text-amber-600 dark:text-amber-400">{{ event.thresholds?.days || 14 }} days</span>
                                    </div>
                                    <input
                                      type="range"
                                      :value="event.thresholds?.days || 14"
                                      @input="updateEventThreshold(event, 'days', parseInt($event.target.value))"
                                      min="3"
                                      max="60"
                                      step="1"
                                      class="w-full h-2 bg-amber-200 dark:bg-amber-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
                                    />
                                    <div class="flex justify-between mt-2 text-xs text-amber-600 dark:text-amber-400">
                                      <span>3 days</span>
                                      <span>60 days</span>
                                    </div>
                                  </div>
                                  <p class="text-xs text-secondary mt-2">How many days before expiration to start sending notifications.</p>
                                </div>
                              </div>

                              <!-- Targets Section -->
                              <div class="border-t border-gray-400 dark:border-gray-700 pt-6">
                                <div class="flex items-center justify-between mb-4">
                                  <div>
                                    <h5 class="font-semibold text-primary">Notification Targets</h5>
                                    <p class="text-sm text-secondary">Where should these alerts be sent?</p>
                                  </div>
                                  <button
                                    @click="openAddTargetModal(event)"
                                    :class="[
                                      'flex items-center gap-2 px-4 py-2 text-white text-sm font-medium rounded-xl transition-all',
                                      event.category === 'backup' ? 'bg-emerald-500 hover:bg-emerald-600'
                                        : event.category === 'container' ? 'bg-blue-500 hover:bg-blue-600'
                                        : event.category === 'security' ? 'bg-red-500 hover:bg-red-600'
                                        : event.category === 'ssl' ? 'bg-amber-500 hover:bg-amber-600'
                                        : 'bg-purple-500 hover:bg-purple-600'
                                    ]"
                                  >
                                    <PlusIcon class="h-4 w-4" />
                                    Add Target
                                  </button>
                                </div>

                                <div v-if="hasNoTargets(event)" class="bg-amber-50 dark:bg-amber-500/10 rounded-xl p-6 border border-amber-200 dark:border-amber-500/20">
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
                                    class="flex items-center justify-between p-4 rounded-xl border border-gray-400 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-600 bg-gray-50 dark:bg-gray-700/50 transition-colors"
                                  >
                                    <div class="flex items-center gap-3">
                                      <div :class="[
                                        'w-10 h-10 rounded-xl flex items-center justify-center font-bold text-white',
                                        target.escalation_level === 1
                                          ? event.category === 'backup' ? 'bg-emerald-500'
                                            : event.category === 'container' ? 'bg-blue-500'
                                            : event.category === 'security' ? 'bg-red-500'
                                            : event.category === 'ssl' ? 'bg-amber-500'
                                            : 'bg-purple-500'
                                          : 'bg-orange-500'
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
      <div v-if="activeSection === 'global'" class="space-y-4">
        <!-- Rate Limiting Card -->
        <div class="bg-surface rounded-xl border border-[var(--color-border)] overflow-hidden">
          <button
            @click="expandedRateLimiting = !expandedRateLimiting"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-rose-100 dark:bg-rose-500/20">
                <FireIcon class="h-5 w-5 text-rose-600 dark:text-rose-400" />
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Rate Limiting</h3>
                <p class="text-sm text-secondary">Prevent notification storms</p>
              </div>
            </div>
            <div class="flex items-center gap-3">
              <span :class="[
                'px-2.5 py-1 rounded-full text-xs font-semibold',
                getRateLimitSeverityClass(globalSettings?.max_notifications_per_hour || 100)
              ]">
                {{ globalSettings?.max_notifications_per_hour || 100 }}/hour
              </span>
              <ChevronDownIcon
                :class="['h-5 w-5 text-gray-400 transition-transform duration-200', expandedRateLimiting ? 'rotate-180' : '']"
              />
            </div>
          </button>

          <Transition name="collapse">
            <div v-if="expandedRateLimiting" class="border-t border-[var(--color-border)]">
              <div class="p-5 space-y-6 bg-gray-50/50 dark:bg-gray-800/30">
                <!-- Visual Rate Limit Gauge -->
                <div class="space-y-3">
                  <div class="flex items-center justify-between">
                    <p class="font-medium text-primary">Maximum Notifications Per Hour</p>
                    <div class="flex items-center gap-2">
                      <input
                        type="number"
                        :value="globalSettings?.max_notifications_per_hour"
                        @change="updateGlobalSettings({ max_notifications_per_hour: Math.max(1, Math.min(1000, parseInt($event.target.value) || 100)) })"
                        min="1"
                        max="1000"
                        class="input-field w-20 text-center font-semibold"
                      />
                      <span class="text-sm text-secondary">/hour</span>
                    </div>
                  </div>

                  <!-- Slider with gradient background -->
                  <div class="relative pt-1">
                    <input
                      type="range"
                      :value="globalSettings?.max_notifications_per_hour || 100"
                      @input="updateGlobalSettings({ max_notifications_per_hour: parseInt($event.target.value) })"
                      min="10"
                      max="500"
                      step="10"
                      class="w-full h-2 rounded-full appearance-none cursor-pointer bg-gradient-to-r from-green-400 via-yellow-400 to-rose-500 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-gray-300 [&::-webkit-slider-thumb]:cursor-pointer [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:shadow-md [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-gray-300 [&::-moz-range-thumb]:cursor-pointer"
                    />
                    <div class="flex justify-between text-xs text-secondary mt-1">
                      <span>10</span>
                      <span>100</span>
                      <span>250</span>
                      <span>500</span>
                    </div>
                  </div>

                  <!-- Preset Buttons -->
                  <div class="flex flex-wrap gap-2 pt-2">
                    <span class="text-xs text-secondary mr-1 self-center">Presets:</span>
                    <button
                      v-for="preset in rateLimitPresets"
                      :key="preset.value"
                      @click="updateGlobalSettings({ max_notifications_per_hour: preset.value })"
                      :class="[
                        'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                        globalSettings?.max_notifications_per_hour === preset.value
                          ? 'bg-rose-500 text-white shadow-sm'
                          : 'bg-white dark:bg-gray-700 text-secondary hover:bg-gray-100 dark:hover:bg-gray-600 border border-[var(--color-border)]'
                      ]"
                    >
                      {{ preset.label }}
                    </button>
                  </div>
                </div>

                <!-- Divider -->
                <div class="border-t border-[var(--color-border)]"></div>

                <!-- Emergency Contact -->
                <div class="space-y-3">
                  <div class="flex items-start gap-3">
                    <div class="p-2 rounded-lg bg-amber-100 dark:bg-amber-500/20 mt-0.5">
                      <ExclamationTriangleIcon class="h-4 w-4 text-amber-600 dark:text-amber-400" />
                    </div>
                    <div class="flex-1">
                      <p class="font-medium text-primary">Emergency Contact</p>
                      <p class="text-sm text-secondary mt-0.5">When the rate limit is exceeded, this channel will receive an alert</p>
                    </div>
                  </div>
                  <select
                    :value="globalSettings?.emergency_contact_id || ''"
                    @change="updateGlobalSettings({ emergency_contact_id: $event.target.value ? parseInt($event.target.value) : null })"
                    class="select-field w-full"
                  >
                    <option value="">No emergency contact configured</option>
                    <option v-for="channel in channels" :key="channel.id" :value="channel.id">
                      {{ channel.name }}
                    </option>
                  </select>
                </div>

                <!-- Info Box -->
                <div class="rounded-lg bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 p-3">
                  <div class="flex gap-2">
                    <InformationCircleIcon class="h-5 w-5 text-blue-500 flex-shrink-0" />
                    <div class="text-sm text-blue-700 dark:text-blue-400">
                      <p class="font-medium">How rate limiting works</p>
                      <p class="mt-1 text-blue-600 dark:text-blue-300">When the hourly limit is reached, additional notifications are queued and delivered when the limit resets. Lower limits help prevent notification fatigue during high-activity periods.</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </Transition>
        </div>

        <!-- Daily Digest Card -->
        <div class="bg-surface rounded-xl border border-[var(--color-border)] overflow-hidden">
          <button
            @click="expandedDailyDigest = !expandedDailyDigest"
            class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
                <EnvelopeIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div class="text-left">
                <h3 class="font-semibold text-primary">Daily Digest</h3>
                <p class="text-sm text-secondary">Batch low-priority notifications into a daily summary</p>
              </div>
            </div>
            <div class="flex items-center gap-3">
              <span :class="[
                'px-2 py-0.5 rounded-full text-xs font-medium',
                globalSettings?.digest_enabled
                  ? 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400'
                  : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
              ]">
                {{ globalSettings?.digest_enabled ? 'Enabled' : 'Disabled' }}
              </span>
              <ChevronDownIcon
                :class="['h-5 w-5 text-gray-400 transition-transform duration-200', expandedDailyDigest ? 'rotate-180' : '']"
              />
            </div>
          </button>

          <Transition name="collapse">
            <div v-if="expandedDailyDigest" class="border-t border-[var(--color-border)]">
              <div class="p-4 space-y-4 bg-gray-50/50 dark:bg-gray-800/30">
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
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-400 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"></div>
                  </label>
                </div>

                <div v-if="globalSettings?.digest_enabled" class="flex items-center justify-between">
                  <div>
                    <p class="font-medium text-primary">Digest Time</p>
                    <p class="text-sm text-secondary">When to send the daily summary</p>
                  </div>
                  <div class="flex items-center gap-2">
                    <ClockIcon class="h-4 w-4 text-gray-400" />
                    <input
                      type="time"
                      :value="globalSettings?.digest_time"
                      @change="updateGlobalSettings({ digest_time: $event.target.value })"
                      class="input-field w-32"
                    />
                  </div>
                </div>

                <div class="pt-2 border-t border-[var(--color-border)]">
                  <p class="text-xs text-secondary">
                    <InformationCircleIcon class="inline h-4 w-4 mr-1" />
                    Info-level events will be collected and sent as a single digest email at the specified time.
                  </p>
                </div>
              </div>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Container Config Section -->
      <div v-if="activeSection === 'containers'" class="space-y-4">
        <!-- Info Banner -->
        <div class="p-4 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-500/10 dark:to-indigo-500/10 border border-blue-200 dark:border-blue-500/30">
          <div class="flex gap-3">
            <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
              <CubeIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div class="text-sm">
              <p class="font-semibold text-blue-800 dark:text-blue-300">Per-Container Notification Settings</p>
              <p class="mt-1 text-blue-700 dark:text-blue-400">Customize monitoring and alert thresholds for individual containers. Changes here sync with the container's Alerts settings.</p>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="containerConfigs.length === 0" class="text-center py-12">
          <div class="inline-flex p-4 rounded-full bg-gray-100 dark:bg-gray-800 mb-4">
            <CubeIcon class="h-12 w-12 text-gray-400" />
          </div>
          <p class="text-lg font-medium text-primary">No Container Configurations</p>
          <p class="text-sm text-secondary mt-1 max-w-md mx-auto">
            Container configs will appear here when you customize notification settings from the Containers view.
          </p>
          <router-link to="/containers" class="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors">
            <CubeIcon class="h-4 w-4" />
            Go to Containers
          </router-link>
        </div>

        <!-- Container Cards -->
        <div v-else class="space-y-3">
          <div v-for="config in containerConfigs" :key="config.id"
            class="bg-surface rounded-2xl border border-[var(--color-border)] overflow-hidden shadow-sm hover:shadow-md transition-shadow"
          >
            <!-- Card Header - Clickable -->
            <button
              @click="toggleContainerConfig(config.id)"
              class="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
            >
              <div class="flex items-center gap-4">
                <div :class="[
                  'p-3 rounded-xl',
                  config.enabled ? 'bg-blue-100 dark:bg-blue-500/20' : 'bg-gray-100 dark:bg-gray-700'
                ]">
                  <CubeIcon :class="[
                    'h-6 w-6',
                    config.enabled ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400'
                  ]" />
                </div>
                <div class="text-left">
                  <h3 class="font-semibold text-primary">{{ config.container_name }}</h3>
                  <p class="text-sm text-secondary">
                    {{ getContainerConfigSummary(config) }}
                  </p>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <!-- Status Badge -->
                <span :class="[
                  'px-3 py-1 rounded-full text-xs font-semibold',
                  getContainerConfigStatus(config) === 'monitoring'
                    ? 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400'
                    : getContainerConfigStatus(config) === 'no_targets'
                      ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400'
                      : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                ]">
                  {{ getContainerConfigStatus(config) === 'monitoring' ? 'Monitoring' : getContainerConfigStatus(config) === 'no_targets' ? 'No Targets' : 'Disabled' }}
                </span>
                <ChevronDownIcon
                  :class="['h-5 w-5 text-gray-400 transition-transform duration-200', expandedContainerConfigs.has(config.id) ? 'rotate-180' : '']"
                />
              </div>
            </button>

            <!-- Expanded Content -->
            <Transition name="collapse">
              <div v-if="expandedContainerConfigs.has(config.id)" class="border-t border-[var(--color-border)]">
                <div class="p-5 bg-gray-50/50 dark:bg-gray-800/30 space-y-6">
                  <!-- Master Toggle -->
                  <div class="flex items-center justify-between p-4 rounded-xl bg-white dark:bg-gray-800 border border-[var(--color-border)]">
                    <div class="flex items-center gap-3">
                      <div class="p-2 rounded-lg bg-green-100 dark:bg-green-500/20">
                        <BellIcon class="h-5 w-5 text-green-600 dark:text-green-400" />
                      </div>
                      <div>
                        <p class="font-medium text-primary">Enable Notifications</p>
                        <p class="text-sm text-secondary">Master switch for all alerts on this container</p>
                      </div>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        :checked="config.enabled"
                        @change="updateContainerConfig(config, { enabled: $event.target.checked })"
                        class="sr-only peer"
                      />
                      <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-400 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-green-500"></div>
                    </label>
                  </div>

                  <!-- Warning: No Targets Configured -->
                  <div v-if="!containerEventsHaveTargets" class="p-4 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30">
                    <div class="flex items-start gap-3">
                      <ExclamationTriangleIcon class="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                      <div>
                        <p class="font-medium text-amber-800 dark:text-amber-300">No Notification Targets Configured</p>
                        <p class="text-sm text-amber-700 dark:text-amber-400 mt-1">
                          Notifications are enabled but won't be sent because no targets are configured for container events.
                        </p>
                        <button
                          @click="activeSection = 'events'; expandedCategories.add('container')"
                          class="mt-2 text-sm font-medium text-amber-700 dark:text-amber-300 hover:underline flex items-center gap-1"
                        >
                          Configure targets in Container Events
                          <ChevronRightIcon class="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>

                  <!-- Status Events Section -->
                  <div :class="[!config.enabled && 'opacity-50 pointer-events-none']">
                    <h4 class="text-sm font-semibold text-primary mb-3 flex items-center gap-2">
                      <HeartIcon class="h-4 w-4 text-rose-500" />
                      Status Events
                    </h4>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <!-- Stopped -->
                      <label class="flex items-center gap-3 p-3 rounded-xl bg-white dark:bg-gray-800 border border-[var(--color-border)] cursor-pointer hover:border-blue-300 dark:hover:border-blue-500 transition-colors">
                        <input
                          type="checkbox"
                          :checked="config.monitor_stopped"
                          @change="updateContainerConfig(config, { monitor_stopped: $event.target.checked })"
                          class="w-4 h-4 rounded border-gray-400 text-blue-500 focus:ring-blue-500"
                        />
                        <div>
                          <p class="text-sm font-medium text-primary">Stopped</p>
                          <p class="text-xs text-secondary">Container exits</p>
                        </div>
                      </label>

                      <!-- Unhealthy -->
                      <label class="flex items-center gap-3 p-3 rounded-xl bg-white dark:bg-gray-800 border border-[var(--color-border)] cursor-pointer hover:border-blue-300 dark:hover:border-blue-500 transition-colors">
                        <input
                          type="checkbox"
                          :checked="config.monitor_unhealthy"
                          @change="updateContainerConfig(config, { monitor_unhealthy: $event.target.checked })"
                          class="w-4 h-4 rounded border-gray-400 text-blue-500 focus:ring-blue-500"
                        />
                        <div>
                          <p class="text-sm font-medium text-primary">Unhealthy</p>
                          <p class="text-xs text-secondary">Health check fails</p>
                        </div>
                      </label>

                      <!-- Restart -->
                      <label class="flex items-center gap-3 p-3 rounded-xl bg-white dark:bg-gray-800 border border-[var(--color-border)] cursor-pointer hover:border-blue-300 dark:hover:border-blue-500 transition-colors">
                        <input
                          type="checkbox"
                          :checked="config.monitor_restart"
                          @change="updateContainerConfig(config, { monitor_restart: $event.target.checked })"
                          class="w-4 h-4 rounded border-gray-400 text-blue-500 focus:ring-blue-500"
                        />
                        <div>
                          <p class="text-sm font-medium text-primary">Restarts</p>
                          <p class="text-xs text-secondary">Auto-restarts</p>
                        </div>
                      </label>
                    </div>
                  </div>

                  <!-- Resource Thresholds Section -->
                  <div :class="[!config.enabled && 'opacity-50 pointer-events-none']">
                    <h4 class="text-sm font-semibold text-primary mb-3 flex items-center gap-2">
                      <CpuChipIcon class="h-4 w-4 text-purple-500" />
                      Resource Thresholds
                    </h4>
                    <div class="space-y-4">
                      <!-- CPU Threshold -->
                      <div class="p-4 rounded-xl bg-white dark:bg-gray-800 border border-[var(--color-border)]">
                        <div class="flex items-center justify-between mb-3">
                          <label class="flex items-center gap-3 cursor-pointer">
                            <input
                              type="checkbox"
                              :checked="config.monitor_high_cpu"
                              @change="updateContainerConfig(config, { monitor_high_cpu: $event.target.checked })"
                              class="w-4 h-4 rounded border-gray-400 text-purple-500 focus:ring-purple-500"
                            />
                            <div>
                              <p class="text-sm font-medium text-primary">High CPU Usage</p>
                              <p class="text-xs text-secondary">Alert when CPU exceeds threshold</p>
                            </div>
                          </label>
                          <span class="text-lg font-bold text-purple-600 dark:text-purple-400">
                            {{ config.cpu_threshold }}%
                          </span>
                        </div>
                        <div v-if="config.monitor_high_cpu" class="mt-2">
                          <input
                            type="range"
                            :value="config.cpu_threshold"
                            @input="updateContainerConfig(config, { cpu_threshold: parseInt($event.target.value) })"
                            min="50"
                            max="100"
                            step="5"
                            class="w-full h-2 rounded-full appearance-none cursor-pointer bg-gradient-to-r from-green-400 via-yellow-400 to-red-500 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-purple-400 [&::-webkit-slider-thumb]:cursor-pointer"
                          />
                          <div class="flex justify-between text-xs text-secondary mt-1">
                            <span>50%</span>
                            <span>75%</span>
                            <span>100%</span>
                          </div>
                        </div>
                      </div>

                      <!-- Memory Threshold -->
                      <div class="p-4 rounded-xl bg-white dark:bg-gray-800 border border-[var(--color-border)]">
                        <div class="flex items-center justify-between mb-3">
                          <label class="flex items-center gap-3 cursor-pointer">
                            <input
                              type="checkbox"
                              :checked="config.monitor_high_memory"
                              @change="updateContainerConfig(config, { monitor_high_memory: $event.target.checked })"
                              class="w-4 h-4 rounded border-gray-400 text-amber-500 focus:ring-amber-500"
                            />
                            <div>
                              <p class="text-sm font-medium text-primary">High Memory Usage</p>
                              <p class="text-xs text-secondary">Alert when memory exceeds threshold</p>
                            </div>
                          </label>
                          <span class="text-lg font-bold text-amber-600 dark:text-amber-400">
                            {{ config.memory_threshold }}%
                          </span>
                        </div>
                        <div v-if="config.monitor_high_memory" class="mt-2">
                          <input
                            type="range"
                            :value="config.memory_threshold"
                            @input="updateContainerConfig(config, { memory_threshold: parseInt($event.target.value) })"
                            min="50"
                            max="100"
                            step="5"
                            class="w-full h-2 rounded-full appearance-none cursor-pointer bg-gradient-to-r from-green-400 via-yellow-400 to-red-500 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-amber-400 [&::-webkit-slider-thumb]:cursor-pointer"
                          />
                          <div class="flex justify-between text-xs text-secondary mt-1">
                            <span>50%</span>
                            <span>75%</span>
                            <span>100%</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Delete Config Button -->
                  <div class="pt-4 border-t border-[var(--color-border)] flex justify-end">
                    <button
                      @click="deleteContainerConfig(config)"
                      class="flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors"
                    >
                      <TrashIcon class="h-4 w-4" />
                      Remove Custom Config
                    </button>
                  </div>
                </div>
              </div>
            </Transition>
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
            class="bg-surface rounded-xl border border-[var(--color-border)] overflow-hidden"
          >
            <!-- Collapsed header row - clickable -->
            <button
              @click="toggleHistoryItem(entry.id)"
              class="w-full flex items-center justify-between p-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
            >
              <div class="flex items-center gap-3">
                <div :class="[
                  'p-1.5 rounded-lg',
                  entry.status === 'sent' ? 'bg-green-100 dark:bg-green-500/20' :
                  entry.status === 'suppressed' ? 'bg-amber-100 dark:bg-amber-500/20' :
                  entry.status === 'failed' ? 'bg-red-100 dark:bg-red-500/20' : 'bg-gray-100 dark:bg-gray-700'
                ]">
                  <component
                    :is="getEventIcon(entry.event_type)"
                    :class="[
                      'h-4 w-4',
                      entry.status === 'sent' ? 'text-green-600 dark:text-green-400' :
                      entry.status === 'suppressed' ? 'text-amber-600 dark:text-amber-400' :
                      entry.status === 'failed' ? 'text-red-600 dark:text-red-400' : 'text-gray-600 dark:text-gray-400'
                    ]"
                  />
                </div>
                <div class="text-left">
                  <span class="font-medium text-primary">{{ formatEventType(entry.event_type) }}</span>
                  <span v-if="entry.container_name" class="text-sm text-secondary ml-2">
                    <CubeIcon class="h-3 w-3 inline" /> {{ entry.container_name }}
                  </span>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-xs text-secondary hidden sm:inline">{{ entry.target_label }}</span>
                <span :class="[
                  'px-2 py-0.5 rounded-full text-xs font-medium',
                  entry.status === 'sent' ? 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400' :
                  entry.status === 'suppressed' ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400' :
                  entry.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400' :
                  'bg-gray-100 text-gray-700 dark:bg-gray-500/20 dark:text-gray-400'
                ]">
                  {{ entry.status }}
                </span>
                <span class="text-xs text-secondary">{{ formatRelativeTime(entry.triggered_at) }}</span>
                <ChevronDownIcon
                  :class="['h-4 w-4 text-gray-400 transition-transform duration-200', expandedHistoryItems.has(entry.id) ? 'rotate-180' : '']"
                />
              </div>
            </button>

            <!-- Expanded details -->
            <Transition name="collapse">
              <div v-if="expandedHistoryItems.has(entry.id)" class="border-t border-[var(--color-border)]">
                <div class="p-4 space-y-3 bg-gray-50/50 dark:bg-gray-800/30">
                  <!-- Target and Time -->
                  <div class="flex items-center justify-between text-sm">
                    <div v-if="entry.target_label" class="flex items-center gap-2 text-secondary">
                      <BellIcon class="h-4 w-4" />
                      <span>Sent to: {{ entry.target_label }}</span>
                    </div>
                    <div class="flex items-center gap-1 text-secondary">
                      <ClockIcon class="h-4 w-4" />
                      <span>{{ formatDate(entry.triggered_at) }}</span>
                    </div>
                  </div>

                  <!-- Event details -->
                  <div v-if="entry.details" class="text-sm text-primary bg-white dark:bg-gray-800 rounded-lg p-3 border border-[var(--color-border)]">
                    {{ entry.details }}
                  </div>

                  <!-- Suppression reason -->
                  <div v-if="entry.suppression_reason" class="flex items-start gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30">
                    <ExclamationTriangleIcon class="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
                    <div class="text-sm text-amber-700 dark:text-amber-400">
                      <span class="font-medium">Suppressed:</span> {{ entry.suppression_reason }}
                    </div>
                  </div>

                  <!-- Error message -->
                  <div v-if="entry.error_message" class="flex items-start gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30">
                    <XCircleIcon class="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
                    <div class="text-sm text-red-700 dark:text-red-400">
                      <span class="font-medium">Error:</span> {{ entry.error_message }}
                    </div>
                  </div>
                </div>
              </div>
            </Transition>
          </div>
        </div>
      </div>
    </template>

    <!-- Add Target Modal -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showAddTargetModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full p-6 space-y-4 border border-gray-400 dark:border-gray-700">
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
                <select v-model="newTargetId" class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-primary focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                  <option value="">Choose a channel...</option>
                  <option v-for="channel in availableChannelsForTarget" :key="channel.id" :value="channel.id">
                    {{ channel.name }} ({{ channel.service_type }})
                  </option>
                </select>
                <p v-if="availableChannelsForTarget.length === 0" class="text-xs text-amber-600 dark:text-amber-400 mt-1">
                  All channels are already assigned to this event
                </p>
              </div>

              <div v-if="newTargetType === 'group'">
                <label class="block text-sm font-medium text-primary mb-1">Select Group</label>
                <select v-model="newTargetId" class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-primary focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                  <option value="">Choose a group...</option>
                  <option v-for="group in availableGroupsForTarget" :key="group.id" :value="group.id">
                    {{ group.name }} ({{ group.channel_count }} channels)
                  </option>
                </select>
                <p v-if="availableGroupsForTarget.length === 0" class="text-xs text-amber-600 dark:text-amber-400 mt-1">
                  All groups are already assigned to this event
                </p>
              </div>

              <div>
                <label class="block text-sm font-medium text-primary mb-1">Escalation Level</label>
                <select v-model="newTargetLevel" class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-primary focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                  <option :value="1">L1 - Primary (receives immediately)</option>
                  <option :value="2">L2 - Escalation (receives after timeout)</option>
                </select>
              </div>

              <!-- Escalation Timeout (only shown for L2) -->
              <div v-if="newTargetLevel === 2" class="bg-blue-50 dark:bg-blue-500/10 rounded-lg p-4 border border-blue-200 dark:border-blue-500/30">
                <label class="block text-sm font-medium text-blue-700 dark:text-blue-300 mb-2">
                  Escalation Timeout
                </label>
                <p class="text-xs text-blue-600 dark:text-blue-400 mb-3">
                  Time to wait before escalating to L2 if L1 hasn't acknowledged
                </p>
                <div class="grid grid-cols-4 gap-2">
                  <button
                    v-for="mins in [15, 30, 45, 60]"
                    :key="mins"
                    @click="newTargetEscalationTimeout = mins"
                    :class="[
                      'px-2 py-1.5 rounded-lg text-sm font-medium border transition-all',
                      newTargetEscalationTimeout === mins
                        ? 'bg-blue-100 dark:bg-blue-500/20 border-blue-400 text-blue-700 dark:text-blue-300'
                        : 'bg-white dark:bg-gray-700 border-gray-400 dark:border-gray-600 text-secondary hover:bg-gray-50 dark:hover:bg-gray-600'
                    ]"
                  >
                    {{ mins }}m
                  </button>
                </div>
                <div class="grid grid-cols-3 gap-2 mt-2">
                  <button
                    v-for="mins in [90, 120, 180]"
                    :key="mins"
                    @click="newTargetEscalationTimeout = mins"
                    :class="[
                      'px-2 py-1.5 rounded-lg text-sm font-medium border transition-all',
                      newTargetEscalationTimeout === mins
                        ? 'bg-blue-100 dark:bg-blue-500/20 border-blue-400 text-blue-700 dark:text-blue-300'
                        : 'bg-white dark:bg-gray-700 border-gray-400 dark:border-gray-600 text-secondary hover:bg-gray-50 dark:hover:bg-gray-600'
                    ]"
                  >
                    {{ mins >= 60 ? `${mins/60}h` : `${mins}m` }}
                  </button>
                </div>
              </div>
            </div>

            <div class="flex justify-end gap-3 pt-4">
              <button @click="showAddTargetModal = false" class="btn-secondary">
                Cancel
              </button>
              <button
                @click="addTarget(selectedEventForTarget.id, newTargetType, newTargetId, newTargetLevel, newTargetEscalationTimeout)"
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

    <!-- Apply to All Events Modal -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showApplyToAllModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full p-6 space-y-5 border border-gray-400 dark:border-gray-700">
            <div class="flex items-center gap-3">
              <div :class="[
                'p-3 rounded-xl',
                applyToAllCategory === 'backup' ? 'bg-emerald-100 dark:bg-emerald-500/20'
                  : applyToAllCategory === 'container' ? 'bg-blue-100 dark:bg-blue-500/20'
                  : applyToAllCategory === 'security' ? 'bg-red-100 dark:bg-red-500/20'
                  : applyToAllCategory === 'ssl' ? 'bg-amber-100 dark:bg-amber-500/20'
                  : 'bg-purple-100 dark:bg-purple-500/20'
              ]">
                <BellAlertIcon :class="[
                  'h-6 w-6',
                  applyToAllCategory === 'backup' ? 'text-emerald-600'
                    : applyToAllCategory === 'container' ? 'text-blue-600'
                    : applyToAllCategory === 'security' ? 'text-red-600'
                    : applyToAllCategory === 'ssl' ? 'text-amber-600'
                    : 'text-purple-600'
                ]" />
              </div>
              <div>
                <h3 class="text-lg font-semibold text-primary">Apply Target to All Events</h3>
                <p class="text-sm text-secondary">{{ categoryInfo[applyToAllCategory]?.label }}</p>
              </div>
            </div>

            <div class="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4">
              <p class="text-sm text-blue-800 dark:text-blue-300">
                This will add the selected notification target to <strong>all events</strong> in this category. Events that already have this target will be skipped.
              </p>
            </div>

            <div class="space-y-4">
              <!-- Target Type Selection -->
              <div>
                <label class="block text-sm font-medium text-primary mb-2">Target Type</label>
                <div class="grid grid-cols-2 gap-2">
                  <button
                    @click="applyToAllTargetType = 'channel'; applyToAllTargetId = null"
                    :class="[
                      'p-3 rounded-lg text-sm font-medium border transition-all',
                      applyToAllTargetType === 'channel'
                        ? 'bg-blue-100 dark:bg-blue-500/20 border-blue-400 text-blue-700 dark:text-blue-300'
                        : 'bg-white dark:bg-gray-700 border-gray-400 dark:border-gray-600 text-secondary hover:bg-gray-50 dark:hover:bg-gray-600'
                    ]"
                  >
                    Channel
                  </button>
                  <button
                    @click="applyToAllTargetType = 'group'; applyToAllTargetId = null"
                    :class="[
                      'p-3 rounded-lg text-sm font-medium border transition-all',
                      applyToAllTargetType === 'group'
                        ? 'bg-blue-100 dark:bg-blue-500/20 border-blue-400 text-blue-700 dark:text-blue-300'
                        : 'bg-white dark:bg-gray-700 border-gray-400 dark:border-gray-600 text-secondary hover:bg-gray-50 dark:hover:bg-gray-600'
                    ]"
                  >
                    Group
                  </button>
                </div>
              </div>

              <!-- Channel/Group Selection -->
              <div>
                <label class="block text-sm font-medium text-primary mb-2">
                  Select {{ applyToAllTargetType === 'channel' ? 'Channel' : 'Group' }}
                </label>
                <select
                  v-model="applyToAllTargetId"
                  class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-primary"
                >
                  <option :value="null" disabled>Choose a {{ applyToAllTargetType }}</option>
                  <template v-if="applyToAllTargetType === 'channel'">
                    <option v-for="channel in channels" :key="channel.id" :value="channel.id">
                      {{ channel.name }} ({{ channel.service_type }})
                    </option>
                  </template>
                  <template v-else>
                    <option v-for="group in groups" :key="group.id" :value="group.id">
                      {{ group.name }} ({{ group.channels?.length || 0 }} channels)
                    </option>
                  </template>
                </select>
                <p v-if="applyToAllTargetType === 'channel' && channels.length === 0" class="mt-2 text-sm text-amber-600 dark:text-amber-400">
                  No notification channels configured. Add channels in Notifications settings first.
                </p>
                <p v-if="applyToAllTargetType === 'group' && groups.length === 0" class="mt-2 text-sm text-amber-600 dark:text-amber-400">
                  No notification groups configured. Create groups in Notifications settings first.
                </p>
              </div>

              <!-- Escalation Level -->
              <div>
                <label class="block text-sm font-medium text-primary mb-2">Escalation Level</label>
                <div class="grid grid-cols-2 gap-2">
                  <button
                    @click="applyToAllLevel = 1"
                    :class="[
                      'p-3 rounded-lg text-sm font-medium border transition-all',
                      applyToAllLevel === 1
                        ? 'bg-green-100 dark:bg-green-500/20 border-green-400 text-green-700 dark:text-green-300'
                        : 'bg-white dark:bg-gray-700 border-gray-400 dark:border-gray-600 text-secondary hover:bg-gray-50 dark:hover:bg-gray-600'
                    ]"
                  >
                    <span class="font-bold">L1</span> - Primary
                  </button>
                  <button
                    @click="applyToAllLevel = 2"
                    :class="[
                      'p-3 rounded-lg text-sm font-medium border transition-all',
                      applyToAllLevel === 2
                        ? 'bg-orange-100 dark:bg-orange-500/20 border-orange-400 text-orange-700 dark:text-orange-300'
                        : 'bg-white dark:bg-gray-700 border-gray-400 dark:border-gray-600 text-secondary hover:bg-gray-50 dark:hover:bg-gray-600'
                    ]"
                  >
                    <span class="font-bold">L2</span> - Escalation
                  </button>
                </div>
              </div>
            </div>

            <div class="flex justify-end gap-3 pt-4">
              <button @click="showApplyToAllModal = false" class="btn-secondary">
                Cancel
              </button>
              <button
                @click="applyTargetToAllEvents"
                :disabled="!applyToAllTargetId || applyingToAll"
                :class="[
                  'btn-primary flex items-center gap-2',
                  applyToAllCategory === 'backup' ? '!bg-emerald-500 hover:!bg-emerald-600'
                    : applyToAllCategory === 'container' ? '!bg-blue-500 hover:!bg-blue-600'
                    : applyToAllCategory === 'security' ? '!bg-red-500 hover:!bg-red-600'
                    : applyToAllCategory === 'ssl' ? '!bg-amber-500 hover:!bg-amber-600'
                    : '!bg-purple-500 hover:!bg-purple-600'
                ]"
              >
                <ArrowPathIcon v-if="applyingToAll" class="h-4 w-4 animate-spin" />
                {{ applyingToAll ? 'Applying...' : 'Apply to All Events' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Maintenance Mode Modal -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showMaintenanceModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full p-6 space-y-5 border border-gray-400 dark:border-gray-700">
            <div class="flex items-center gap-3">
              <div class="p-3 rounded-xl bg-amber-100 dark:bg-amber-500/20">
                <PauseCircleIcon class="h-6 w-6 text-amber-600" />
              </div>
              <div>
                <h3 class="text-lg font-semibold text-primary">Enable Maintenance Mode</h3>
                <p class="text-sm text-secondary">All system notifications will be paused</p>
              </div>
            </div>

            <div class="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg p-4">
              <p class="text-sm text-amber-800 dark:text-amber-300">
                <strong>All notifications disabled:</strong> While maintenance mode is active, ALL system notifications are completely stopped. No alerts will be sent, queued, or stored. Use this when performing intentional maintenance that may generate unwanted alerts. This will not affect any n8n webhook generated notifications.
              </p>
            </div>

            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-primary mb-2">Duration</label>
                <div class="grid grid-cols-4 gap-2">
                  <button
                    v-for="opt in [
                      { value: '1h', label: '1 Hour' },
                      { value: '2h', label: '2 Hours' },
                      { value: '4h', label: '4 Hours' },
                      { value: '8h', label: '8 Hours' },
                    ]"
                    :key="opt.value"
                    @click="maintenanceDuration = opt.value"
                    :class="[
                      'px-3 py-2 rounded-lg text-sm font-medium border transition-all',
                      maintenanceDuration === opt.value
                        ? 'bg-amber-100 dark:bg-amber-500/20 border-amber-400 text-amber-700 dark:text-amber-300'
                        : 'bg-gray-50 dark:bg-gray-700 border-gray-400 dark:border-gray-600 text-secondary hover:bg-gray-100 dark:hover:bg-gray-600'
                    ]"
                  >
                    {{ opt.label }}
                  </button>
                </div>
                <div class="grid grid-cols-3 gap-2 mt-2">
                  <button
                    v-for="opt in [
                      { value: '12h', label: '12 Hours' },
                      { value: '24h', label: '24 Hours' },
                      { value: 'indefinite', label: 'Until I disable' },
                    ]"
                    :key="opt.value"
                    @click="maintenanceDuration = opt.value"
                    :class="[
                      'px-3 py-2 rounded-lg text-sm font-medium border transition-all',
                      maintenanceDuration === opt.value
                        ? 'bg-amber-100 dark:bg-amber-500/20 border-amber-400 text-amber-700 dark:text-amber-300'
                        : 'bg-gray-50 dark:bg-gray-700 border-gray-400 dark:border-gray-600 text-secondary hover:bg-gray-100 dark:hover:bg-gray-600'
                    ]"
                  >
                    {{ opt.label }}
                  </button>
                </div>
              </div>

              <div>
                <label class="block text-sm font-medium text-primary mb-1">Reason (optional)</label>
                <input
                  v-model="maintenanceReason"
                  type="text"
                  placeholder="e.g., Server maintenance, Upgrade in progress..."
                  class="w-full px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 text-primary focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                />
              </div>
            </div>

            <div class="flex justify-end gap-3 pt-2">
              <button @click="showMaintenanceModal = false" class="btn-secondary">
                Cancel
              </button>
              <button @click="enableMaintenanceMode" class="px-4 py-2 rounded-lg font-medium bg-amber-500 hover:bg-amber-600 text-white transition-colors">
                Enable Maintenance Mode
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Quiet Hours Modal -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showQuietHoursModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div class="bg-gradient-to-b from-indigo-950 to-slate-900 rounded-xl shadow-xl max-w-md w-full p-6 space-y-5 border border-indigo-500/30">
            <!-- Starry header -->
            <div class="relative">
              <div class="flex items-center gap-3">
                <div class="p-3 rounded-xl bg-indigo-800/50 relative">
                  <MoonIcon class="h-6 w-6 text-yellow-300" />
                  <span class="absolute -top-1 -right-1 text-yellow-300 text-sm animate-pulse">✦</span>
                </div>
                <div>
                  <h3 class="text-lg font-semibold text-indigo-100">Quiet Hours</h3>
                  <p class="text-sm text-indigo-300">Schedule a time for reduced notifications</p>
                </div>
              </div>
              <!-- Decorative stars -->
              <span class="absolute top-0 right-4 text-indigo-400/50 text-xs">✧</span>
              <span class="absolute top-2 right-12 text-indigo-300/40 text-[10px]">✦</span>
              <span class="absolute -top-1 right-20 text-indigo-400/30 text-sm">✧</span>
            </div>

            <div class="bg-indigo-800/30 border border-indigo-500/30 rounded-lg p-4">
              <p class="text-sm text-indigo-200">
                During quiet hours, <strong class="text-indigo-100">non-critical notifications</strong> will be suppressed. Critical alerts will still come through.
              </p>
            </div>

            <div class="space-y-4">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-indigo-200 mb-2">
                    <SunIcon class="h-4 w-4 inline mr-1 text-orange-400" />
                    Start Time
                  </label>
                  <input
                    v-model="quietHoursStart"
                    type="time"
                    class="w-full px-3 py-2.5 rounded-lg border border-indigo-500/50 bg-indigo-900/50 text-indigo-100 focus:ring-2 focus:ring-indigo-400 focus:border-indigo-400"
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-indigo-200 mb-2">
                    <MoonIcon class="h-4 w-4 inline mr-1 text-yellow-300" />
                    End Time
                  </label>
                  <input
                    v-model="quietHoursEnd"
                    type="time"
                    class="w-full px-3 py-2.5 rounded-lg border border-indigo-500/50 bg-indigo-900/50 text-indigo-100 focus:ring-2 focus:ring-indigo-400 focus:border-indigo-400"
                  />
                </div>
              </div>

              <!-- Quick presets -->
              <div>
                <label class="block text-xs font-medium text-indigo-400 mb-2">Quick Presets</label>
                <div class="flex flex-wrap gap-2">
                  <button
                    @click="quietHoursStart = '22:00'; quietHoursEnd = '07:00'"
                    class="px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-800/50 border border-indigo-500/30 text-indigo-200 hover:bg-indigo-700/50 transition-colors"
                  >
                    Night (10pm - 7am)
                  </button>
                  <button
                    @click="quietHoursStart = '23:00'; quietHoursEnd = '06:00'"
                    class="px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-800/50 border border-indigo-500/30 text-indigo-200 hover:bg-indigo-700/50 transition-colors"
                  >
                    Late Night (11pm - 6am)
                  </button>
                  <button
                    @click="quietHoursStart = '00:00'; quietHoursEnd = '08:00'"
                    class="px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-800/50 border border-indigo-500/30 text-indigo-200 hover:bg-indigo-700/50 transition-colors"
                  >
                    Midnight (12am - 8am)
                  </button>
                </div>
              </div>
            </div>

            <div class="flex justify-between items-center pt-2">
              <button
                v-if="globalSettings?.quiet_hours_enabled"
                @click="disableQuietHours"
                class="px-4 py-2 rounded-lg font-medium text-red-400 hover:bg-red-500/20 transition-colors"
              >
                Disable Quiet Hours
              </button>
              <div v-else></div>
              <div class="flex gap-3">
                <button @click="showQuietHoursModal = false" class="px-4 py-2 rounded-lg font-medium text-indigo-300 hover:bg-indigo-800/50 transition-colors">
                  Cancel
                </button>
                <button @click="saveQuietHours" class="px-4 py-2 rounded-lg font-medium bg-indigo-500 hover:bg-indigo-400 text-white transition-colors">
                  {{ globalSettings?.quiet_hours_enabled ? 'Update' : 'Enable' }} Quiet Hours
                </button>
              </div>
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
