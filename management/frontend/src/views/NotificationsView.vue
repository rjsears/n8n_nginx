<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/views/NotificationsView.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useNotificationStore } from '@/stores/notifications'
import { notificationsApi, ntfyApi } from '@/services/api'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import NotificationServiceDialog from '@/components/notifications/NotificationServiceDialog.vue'
import NotificationGroupDialog from '@/components/notifications/NotificationGroupDialog.vue'
// NTFY Components
import MessageComposer from '@/components/ntfy/MessageComposer.vue'
import TemplateBuilder from '@/components/ntfy/TemplateBuilder.vue'
import TopicsManager from '@/components/ntfy/TopicsManager.vue'
import SavedMessages from '@/components/ntfy/SavedMessages.vue'
import MessageHistory from '@/components/ntfy/MessageHistory.vue'
import ServerSettings from '@/components/ntfy/ServerSettings.vue'
import IntegrationHub from '@/components/ntfy/IntegrationHub.vue'
import {
  BellIcon,
  BellAlertIcon,
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  PaperAirplaneIcon,
  CheckCircleIcon,
  XCircleIcon,
  EnvelopeIcon,
  ChatBubbleLeftIcon,
  GlobeAltIcon,
  LinkIcon,
  ClipboardDocumentIcon,
  EyeIcon,
  EyeSlashIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  KeyIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  PlayIcon,
  Cog6ToothIcon,
  ClockIcon,
  MegaphoneIcon,
  DocumentTextIcon,
  HashtagIcon,
  BookmarkIcon,
  CodeBracketIcon,
  SparklesIcon,
  InformationCircleIcon,
} from '@heroicons/vue/24/outline'

const route = useRoute()
const themeStore = useThemeStore()
const notificationStore = useNotificationStore()

// Main tab navigation (Channels vs Groups vs NTFY Push)
const mainTab = ref('channels')

// Main tabs configuration
const mainTabs = [
  { id: 'channels', name: 'Channels', icon: BellIcon, iconColor: 'text-blue-500', bgActive: 'bg-blue-500/15 dark:bg-blue-500/20', textActive: 'text-blue-700 dark:text-blue-400', borderActive: 'border-blue-500/30' },
  { id: 'groups', name: 'Groups', icon: HashtagIcon, iconColor: 'text-purple-500', bgActive: 'bg-purple-500/15 dark:bg-purple-500/20', textActive: 'text-purple-700 dark:text-purple-400', borderActive: 'border-purple-500/30' },
  { id: 'ntfy', name: 'NTFY Push', icon: MegaphoneIcon, iconColor: 'text-amber-500', bgActive: 'bg-amber-500/15 dark:bg-amber-500/20', textActive: 'text-amber-700 dark:text-amber-400', borderActive: 'border-amber-500/30' },
]

// Watch for query param to switch tabs
watch(() => route.query.tab, (newTab) => {
  if (newTab === 'ntfy') {
    mainTab.value = 'ntfy'
  } else if (newTab === 'channels') {
    mainTab.value = 'channels'
  } else if (newTab === 'groups') {
    mainTab.value = 'groups'
  }
}, { immediate: true })

const loading = ref(true)

// Notification loading messages
const allNotificationMessages = [
  'Ringing all the bells...',
  'Waking up the notification fairies...',
  'Checking who wants to be disturbed...',
  'Polishing the alert buttons...',
  'Asking Slack if it\'s still awake...',
  'Convincing emails they\'re important...',
  'Teaching webhooks new tricks...',
  'Counting all the notification channels...',
  'Making sure no alerts got lost...',
  'Checking if Discord is feeling chatty...',
  'Verifying the push notifications can push...',
  'Asking NTFY to ntfy us...',
  'Loading carrier pigeons as backup...',
  'Ensuring smoke signals are calibrated...',
  'Testing if anyone\'s listening...',
  'Warming up the alert sirens...',
  'Organizing the notification queue...',
  'Making sure webhooks are hooked...',
  'Preparing the royal trumpet fanfare...',
  'Checking the notification bat signal...',
  'Ensuring alerts don\'t go to spam...',
  'Bribing the notification gods...',
  'Tuning the alert frequencies...',
  'Loading the notification confetti...',
]
const notificationLoadingMessages = ref([])
const notificationLoadingMessageIndex = ref(0)
let notificationLoadingInterval = null

function shuffleNotificationMessages() {
  const shuffled = [...allNotificationMessages].sort(() => Math.random() - 0.5)
  notificationLoadingMessages.value = shuffled.slice(0, 12)
}

const channels = ref([])
const groups = ref([])
const history = ref([])
const webhookInfo = ref(null)
const showApiKey = ref(false)
const webhookExpanded = ref(false)
const historyExpanded = ref(false)
const channelsExpanded = ref(true)
const groupsExpanded = ref(true)
const expandedGroups = ref(new Set())
const expandedHistoryItems = ref(new Set())
const expandedHistoryGroups = ref(new Set())

// Computed property to group history items by notification event
// Each notification sent to a group becomes its own group entry
const groupedHistory = computed(() => {
  const result = []

  // Get the first 30 history items
  const items = history.value.slice(0, 30)

  // For batching notifications that went to the same group
  // We'll group items with the same group + event_type + similar timestamp
  const processedIds = new Set()

  for (let i = 0; i < items.length; i++) {
    const item = items[i]

    // Skip if already processed as part of a batch
    if (processedIds.has(item.id)) continue

    const targets = item.event_data?.targets || []
    const groupTarget = targets.find(t => t.startsWith('group:'))

    if (groupTarget) {
      const groupSlug = groupTarget.replace('group:', '')
      const group = groups.value.find(g => g.slug === groupSlug)
      const groupName = group?.name || groupSlug

      // Find other items that belong to the same notification event
      // (same group, same event_type, within 5 seconds)
      const itemTime = new Date(item.sent_at || item.created_at).getTime()
      const batchItems = [item]
      processedIds.add(item.id)

      // Look for related items (same group send)
      for (let j = i + 1; j < items.length; j++) {
        const other = items[j]
        if (processedIds.has(other.id)) continue

        const otherTargets = other.event_data?.targets || []
        const otherGroupTarget = otherTargets.find(t => t.startsWith('group:'))

        if (otherGroupTarget === groupTarget && other.event_type === item.event_type) {
          const otherTime = new Date(other.sent_at || other.created_at).getTime()
          // Within 5 seconds = same notification event
          if (Math.abs(otherTime - itemTime) < 5000) {
            batchItems.push(other)
            processedIds.add(other.id)
          }
        }
      }

      // Build channel entries from the actual batch items
      const channelEntries = batchItems.map(b => ({
        id: b.id,
        service_name: b.service_name,
        status: b.status,
        sent_at: b.sent_at || b.created_at,
        error_message: b.error_message,
        event_type: b.event_type,
        event_data: b.event_data,
        severity: b.severity,
      }))

      // Create a group entry for this notification event
      result.push({
        type: 'group',
        id: `group-${item.id}`,
        groupSlug,
        groupName,
        // Use the first item's data for the group header
        event_type: item.event_type,
        event_data: item.event_data,
        status: channelEntries.every(b => b.status === 'sent') ? 'sent' : 'failed',
        sent_at: item.sent_at || item.created_at,
        severity: item.severity,
        // Individual channel deliveries
        channels: channelEntries
      })
    } else {
      // Ungrouped item
      processedIds.add(item.id)
      result.push({
        type: 'single',
        id: item.id,
        ...item
      })
    }
  }

  return result
})

function toggleHistoryGroup(groupSlug) {
  if (expandedHistoryGroups.value.has(groupSlug)) {
    expandedHistoryGroups.value.delete(groupSlug)
  } else {
    expandedHistoryGroups.value.add(groupSlug)
  }
  expandedHistoryGroups.value = new Set(expandedHistoryGroups.value)
}

function toggleGroupExpanded(groupId) {
  if (expandedGroups.value.has(groupId)) {
    expandedGroups.value.delete(groupId)
  } else {
    expandedGroups.value.add(groupId)
  }
  expandedGroups.value = new Set(expandedGroups.value)
}

function getGroupMessageCount(group) {
  // Count messages sent to this group from history
  return history.value.filter(h =>
    h.event_data?.targets?.includes(`group:${group.slug}`)
  ).length
}
const generatingKey = ref(false)

// Groups dialog state
const groupDialog = ref({ open: false, group: null })
const deleteGroupDialog = ref({ open: false, group: null, loading: false })

// Toggle individual history item expansion
function toggleHistoryItem(itemId) {
  if (expandedHistoryItems.value.has(itemId)) {
    expandedHistoryItems.value.delete(itemId)
  } else {
    expandedHistoryItems.value.add(itemId)
  }
  // Force reactivity
  expandedHistoryItems.value = new Set(expandedHistoryItems.value)
}
const regenerateDialog = ref({ open: false, loading: false })
const deleteDialog = ref({ open: false, channel: null, loading: false })
const serviceDialog = ref({ open: false, service: null })
const ntfySuccessDialog = ref({ open: false, channel: null })
const testingChannel = ref(null)
const n8nStatus = ref({ checking: false, configured: false, connected: false, error: null })
const creatingWorkflow = ref(false)
const workflowCreationDialog = ref({ open: false })
const credentialStatus = ref({ exists: false, checking: false })
const creatingCredential = ref(false)
const regenerateSuccessDialog = ref({ open: false, updating: false })

// Channel type icons
const channelIcons = {
  apprise: ChatBubbleLeftIcon,
  ntfy: BellIcon,
  email: EnvelopeIcon,
  webhook: GlobeAltIcon,
}

// Check if an NTFY channel points to the local NTFY server
function isLocalNtfyChannel(channel) {
  if (channel.service_type !== 'ntfy') return false
  const server = channel.config?.server?.toLowerCase() || ''
  if (!server) return false

  // Local server patterns
  const localPatterns = [
    'n8n_ntfy',
    'ntfy:',
    'localhost',
    '127.0.0.1',
  ]

  // Check if URL starts with http://ntfy or https://ntfy (without .sh or other TLD)
  if (/^https?:\/\/ntfy[:/]/.test(server) || /^https?:\/\/ntfy$/.test(server)) {
    return true
  }

  return localPatterns.some(pattern => server.includes(pattern))
}

// Get the appropriate icon for a channel
function getChannelIcon(channel) {
  if (isLocalNtfyChannel(channel)) {
    return MegaphoneIcon  // Same icon as NTFY Push tab for local channels
  }
  return channelIcons[channel.service_type] || BellIcon
}

// Stats - with defensive array checks
const stats = computed(() => {
  const channelsList = Array.isArray(channels.value) ? channels.value : []
  const groupsList = Array.isArray(groups.value) ? groups.value : []
  const historyList = Array.isArray(history.value) ? history.value : []
  return {
    total: channelsList.length,
    active: channelsList.filter((c) => c.enabled).length,
    webhookEnabled: channelsList.filter((c) => c.webhook_enabled).length,
    groups: groupsList.length,
    sent: historyList.filter((h) => h.status === 'sent').length,
    failed: historyList.filter((h) => h.status === 'failed').length,
  }
})

async function loadData() {
  loading.value = true

  // Shuffle messages and start cycling
  shuffleNotificationMessages()
  notificationLoadingMessageIndex.value = 0
  if (notificationLoadingInterval) clearInterval(notificationLoadingInterval)
  notificationLoadingInterval = setInterval(() => {
    notificationLoadingMessageIndex.value = (notificationLoadingMessageIndex.value + 1) % notificationLoadingMessages.value.length
  }, 2000)

  try {
    const [servicesRes, groupsRes, historyRes, webhookRes] = await Promise.all([
      notificationsApi.getServices(),
      notificationsApi.getGroups(),
      notificationsApi.getHistory(),
      notificationsApi.getWebhookInfo(),
    ])
    // Ensure we always have arrays
    channels.value = Array.isArray(servicesRes.data) ? servicesRes.data : []
    groups.value = Array.isArray(groupsRes.data) ? groupsRes.data : []

    // Use regular notification history only - it already has all channel delivery records
    // with proper message content. System notifications create both SystemNotificationHistory
    // AND regular NotificationHistory records, so we don't need to merge them.
    history.value = Array.isArray(historyRes.data) ? historyRes.data : []
    webhookInfo.value = webhookRes.data
  } catch (error) {
    console.error('Failed to load notification data:', error)
    notificationStore.error('Failed to load notification data')
    // Reset to empty arrays on error
    channels.value = []
    groups.value = []
    history.value = []
  } finally {
    if (notificationLoadingInterval) clearInterval(notificationLoadingInterval)
    loading.value = false
  }
}

function copyToClipboard(text, name) {
  navigator.clipboard.writeText(text).then(() => {
    notificationStore.success(`${name} copied to clipboard`)
  }).catch(() => {
    notificationStore.error('Failed to copy to clipboard')
  })
}

async function generateApiKey() {
  generatingKey.value = true
  try {
    const response = await notificationsApi.generateWebhookKey()
    webhookInfo.value = {
      ...webhookInfo.value,
      api_key: response.data.api_key,
      has_key: true,
    }
    notificationStore.success('API key generated successfully')
    // Auto-expand to show the new key
    webhookExpanded.value = true
    showApiKey.value = true
  } catch (error) {
    notificationStore.error('Failed to generate API key: ' + (error.response?.data?.detail || 'Unknown error'))
  } finally {
    generatingKey.value = false
  }
}

function openRegenerateDialog() {
  regenerateDialog.value = { open: true, loading: false }
}

async function confirmRegenerateKey() {
  regenerateDialog.value.loading = true
  try {
    const response = await notificationsApi.regenerateWebhookKey()
    webhookInfo.value = {
      ...webhookInfo.value,
      api_key: response.data.api_key,
      has_key: true,
    }
    regenerateDialog.value.open = false
    showApiKey.value = true
    // Show the success dialog with option to update n8n credential
    regenerateSuccessDialog.value.open = true
  } catch (error) {
    notificationStore.error('Failed to regenerate API key: ' + (error.response?.data?.detail || 'Unknown error'))
  } finally {
    regenerateDialog.value.loading = false
  }
}

async function updateN8nCredentialAfterRegenerate() {
  regenerateSuccessDialog.value.updating = true
  try {
    const response = await notificationsApi.createOrUpdateCredential()
    if (response.data.success) {
      notificationStore.success('n8n credential updated successfully!')
      regenerateSuccessDialog.value.open = false
    } else {
      notificationStore.error('Failed to update credential: ' + (response.data.message || 'Unknown error'))
    }
  } catch (error) {
    notificationStore.error('Failed to update credential: ' + (error.response?.data?.detail || 'Unknown error'))
  } finally {
    regenerateSuccessDialog.value.updating = false
  }
}

async function checkN8nStatus() {
  n8nStatus.value.checking = true
  n8nStatus.value.error = null
  try {
    const response = await notificationsApi.getN8nStatus()
    n8nStatus.value.configured = response.data.configured
    n8nStatus.value.connected = response.data.connected
    if (!response.data.configured) {
      n8nStatus.value.error = 'N8N_API_KEY not configured in environment'
    } else if (!response.data.connected) {
      n8nStatus.value.error = response.data.error || 'Cannot connect to n8n API'
    }
  } catch (error) {
    n8nStatus.value.configured = false
    n8nStatus.value.connected = false
    n8nStatus.value.error = error.response?.data?.detail || 'Failed to check n8n status'
  } finally {
    n8nStatus.value.checking = false
  }
}

async function createTestWorkflow(workflowType = 'broadcast') {
  creatingWorkflow.value = workflowType
  try {
    const response = await notificationsApi.createTestWorkflow(workflowType)
    if (response.data.success) {
      const workflowName = response.data.workflow_name
      const credentialCreated = response.data.credential_id
      if (credentialCreated) {
        notificationStore.success(`${workflowName} created with auto-configured credential! Ready to test.`)
      } else {
        notificationStore.success(`${workflowName} created! Open n8n to configure the credential and run it.`)
      }
    } else {
      notificationStore.error('Failed to create workflow: ' + (response.data.error || 'Unknown error'))
    }
  } catch (error) {
    notificationStore.error('Failed to create workflow: ' + (error.response?.data?.detail || 'Unknown error'))
  } finally {
    creatingWorkflow.value = false
  }
}

function showWorkflowCreationDialog() {
  workflowCreationDialog.value.open = true
}

async function createAllTestWorkflows() {
  workflowCreationDialog.value.open = false
  creatingWorkflow.value = 'all'
  try {
    const response = await notificationsApi.createAllTestWorkflows()
    if (response.data.success) {
      const count = response.data.workflows_created?.length || 0
      const credentialsProvisioned = response.data.credentials_provisioned
      if (credentialsProvisioned) {
        notificationStore.success(`Created ${count} test workflow(s) with auto-configured credentials! Ready to test in n8n.`)
      } else {
        notificationStore.success(`Created ${count} test workflow(s) in n8n! Open n8n to configure credentials and run them.`)
      }
      if (response.data.errors?.length > 0) {
        notificationStore.warning('Some workflows had errors: ' + response.data.errors.join(', '))
      }
    } else {
      notificationStore.error('Failed to create workflows: ' + (response.data.message || 'Unknown error'))
    }
  } catch (error) {
    notificationStore.error('Failed to create workflows: ' + (error.response?.data?.detail || 'Unknown error'))
  } finally {
    creatingWorkflow.value = false
  }
}

async function checkCredentialStatus() {
  credentialStatus.value.checking = true
  try {
    const response = await notificationsApi.getCredentialStatus()
    credentialStatus.value.exists = response.data.exists
    credentialStatus.value.configured = response.data.configured
  } catch (error) {
    console.error('Failed to check credential status:', error)
  } finally {
    credentialStatus.value.checking = false
  }
}

async function createOrUpdateCredential() {
  creatingCredential.value = true
  try {
    const response = await notificationsApi.createOrUpdateCredential()
    if (response.data.success) {
      const action = response.data.action
      notificationStore.success(`Credential ${action} successfully in n8n!`)
      credentialStatus.value.exists = true
    } else {
      notificationStore.error('Failed to manage credential: ' + (response.data.message || 'Unknown error'))
    }
  } catch (error) {
    notificationStore.error('Failed to manage credential: ' + (error.response?.data?.detail || 'Unknown error'))
  } finally {
    creatingCredential.value = false
  }
}

function getWebhookUrl() {
  const baseUrl = window.location.origin
  return `${baseUrl}/management/api/notifications/webhook`
}

async function testChannel(channel) {
  testingChannel.value = channel.id
  try {
    await notificationsApi.testService(channel.id)
    notificationStore.success('Test notification sent!')
  } catch (error) {
    notificationStore.error('Test failed: ' + (error.response?.data?.detail || 'Unknown error'))
  } finally {
    testingChannel.value = null
  }
}

async function toggleChannel(channel) {
  try {
    await notificationsApi.updateService(channel.id, { enabled: !channel.enabled })
    channel.enabled = !channel.enabled
    notificationStore.success(`Channel ${channel.enabled ? 'enabled' : 'disabled'}`)
  } catch (error) {
    notificationStore.error('Failed to update channel')
  }
}

function openDeleteDialog(channel) {
  deleteDialog.value = { open: true, channel, loading: false }
}

function openAddDialog() {
  serviceDialog.value = { open: true, service: null }
}

function openEditDialog(channel) {
  serviceDialog.value = { open: true, service: channel }
}

async function handleServiceSave(formData) {
  try {
    if (formData.id) {
      // Update existing service
      const response = await notificationsApi.updateService(formData.id, {
        name: formData.name,
        slug: formData.slug,
        service_type: formData.service_type,
        enabled: formData.enabled,
        webhook_enabled: formData.webhook_enabled,
        priority: formData.priority,
        config: formData.config,
      })
      const index = channels.value.findIndex(c => c.id === formData.id)
      if (index !== -1) {
        channels.value[index] = response.data
      }
      notificationStore.success('Channel updated')
    } else {
      // Create new service
      const response = await notificationsApi.createService({
        name: formData.name,
        slug: formData.slug,
        service_type: formData.service_type,
        enabled: formData.enabled,
        webhook_enabled: formData.webhook_enabled,
        priority: formData.priority,
        config: formData.config,
      })
      channels.value.push(response.data)

      // Show success info dialog for local NTFY channels
      if (formData.service_type === 'ntfy' && isLocalNtfyChannel(response.data)) {
        ntfySuccessDialog.value = { open: true, channel: response.data }
      } else {
        notificationStore.success('Channel created')
      }
    }
    serviceDialog.value.open = false
  } catch (error) {
    notificationStore.error('Failed to save channel: ' + (error.response?.data?.detail || 'Unknown error'))
  }
}

// Group management functions
function openAddGroupDialog() {
  groupDialog.value = { open: true, group: null }
}

function openEditGroupDialog(group) {
  groupDialog.value = { open: true, group }
}

function openDeleteGroupDialog(group) {
  deleteGroupDialog.value = { open: true, group, loading: false }
}

async function handleGroupSave(formData) {
  try {
    if (formData.id) {
      // Update existing group
      const response = await notificationsApi.updateGroup(formData.id, {
        name: formData.name,
        slug: formData.slug,
        description: formData.description,
        enabled: formData.enabled,
        channel_ids: formData.channel_ids,
      })
      const index = groups.value.findIndex(g => g.id === formData.id)
      if (index !== -1) {
        groups.value[index] = response.data
      }
      notificationStore.success('Group updated')
    } else {
      // Create new group
      const response = await notificationsApi.createGroup({
        name: formData.name,
        slug: formData.slug,
        description: formData.description,
        enabled: formData.enabled,
        channel_ids: formData.channel_ids,
      })
      groups.value.push(response.data)
      notificationStore.success('Group created')
    }
    groupDialog.value.open = false
  } catch (error) {
    console.error('Group save error:', error)
    const errorMsg = error.response?.data?.detail || error.message || 'Unknown error'
    notificationStore.error('Failed to save group: ' + errorMsg)
    // Store form data and reopen dialog to preserve user input
    const savedFormData = { ...formData }
    groupDialog.value.open = false
    setTimeout(() => {
      groupDialog.value = { open: true, group: savedFormData.id ? savedFormData : null }
    }, 100)
  }
}

async function confirmDeleteGroup() {
  if (!deleteGroupDialog.value.group) return

  deleteGroupDialog.value.loading = true
  try {
    await notificationsApi.deleteGroup(deleteGroupDialog.value.group.id)
    groups.value = groups.value.filter((g) => g.id !== deleteGroupDialog.value.group.id)
    notificationStore.success('Group deleted')
    deleteGroupDialog.value.open = false
  } catch (error) {
    notificationStore.error('Failed to delete group')
  } finally {
    deleteGroupDialog.value.loading = false
  }
}

async function toggleGroup(group) {
  try {
    await notificationsApi.updateGroup(group.id, { enabled: !group.enabled })
    group.enabled = !group.enabled
    notificationStore.success(`Group ${group.enabled ? 'enabled' : 'disabled'}`)
  } catch (error) {
    notificationStore.error('Failed to update group')
  }
}

async function confirmDelete() {
  if (!deleteDialog.value.channel) return

  deleteDialog.value.loading = true
  try {
    await notificationsApi.deleteService(deleteDialog.value.channel.id)
    channels.value = channels.value.filter((c) => c.id !== deleteDialog.value.channel.id)
    notificationStore.success('Channel deleted')
    deleteDialog.value.open = false
  } catch (error) {
    notificationStore.error('Failed to delete channel')
  } finally {
    deleteDialog.value.loading = false
  }
}

onMounted(() => {
  loadData()
  checkN8nStatus()
})

// ==================== NTFY Section ====================

// NTFY Loading messages
const allNtfyMessages = [
  'Waking up NTFY...',
  'Poking the push notification service...',
  'Asking NTFY if it\'s home...',
  'Loading the notification launcher...',
  'Checking NTFY\'s pulse...',
  'Convincing NTFY to share its secrets...',
  'Warming up the push engines...',
  'Making sure NTFY had its coffee...',
  'Counting all the topics...',
  'Teaching notifications to fly...',
  'Calibrating the alert catapult...',
  'Checking the notification fuel levels...',
  'Asking topics what they\'re about...',
  'Loading the emoji arsenal...',
  'Preparing the message templates...',
  'Ensuring notifications are properly caffeinated...',
]
const ntfyLoadingMessages = ref([])
const ntfyLoadingMessageIndex = ref(0)
let ntfyLoadingInterval = null

function shuffleNtfyMessages() {
  const shuffled = [...allNtfyMessages].sort(() => Math.random() - 0.5)
  ntfyLoadingMessages.value = shuffled.slice(0, 12)
}

// NTFY State
const ntfyLoading = ref(true)
const ntfyHealth = ref({ healthy: false, status: 'unknown' })
const ntfyStatus = ref({})
const ntfyActiveTab = ref('composer')

// NTFY Data
const ntfyTopics = ref([])
const ntfyTemplates = ref([])
const ntfySavedMessages = ref([])
const ntfyHistory = ref([])
const ntfyServerConfig = ref({})
const ntfyEmojiCategories = ref({})
const ntfyIntegrationExamples = ref([])

// NTFY Tabs configuration
const ntfyTabs = [
  { id: 'composer', name: 'Compose', icon: PaperAirplaneIcon },
  { id: 'templates', name: 'Templates', icon: DocumentTextIcon },
  { id: 'topics', name: 'Topics', icon: HashtagIcon },
  { id: 'saved', name: 'Saved', icon: BookmarkIcon },
  { id: 'history', name: 'History', icon: ClockIcon },
  { id: 'settings', name: 'Settings', icon: Cog6ToothIcon },
  { id: 'integrations', name: 'Integrations', icon: CodeBracketIcon },
]

// NTFY Formatters
function formatNtfyTime(dateStr) {
  if (!dateStr) return 'Never'
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date

  if (diff < 60000) return 'Just now'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
  return date.toLocaleDateString()
}

// NTFY Load data
async function loadNtfyData() {
  ntfyLoading.value = true

  // Shuffle messages and start cycling
  shuffleNtfyMessages()
  ntfyLoadingMessageIndex.value = 0
  if (ntfyLoadingInterval) clearInterval(ntfyLoadingInterval)
  ntfyLoadingInterval = setInterval(() => {
    ntfyLoadingMessageIndex.value = (ntfyLoadingMessageIndex.value + 1) % ntfyLoadingMessages.value.length
  }, 2000)

  try {
    // Load health and status in parallel
    const [healthRes, statusRes] = await Promise.all([
      api.ntfy.health(),
      api.ntfy.status(),
    ])
    ntfyHealth.value = healthRes.data
    ntfyStatus.value = statusRes.data

    // Load other data
    const [topicsRes, templatesRes, savedRes, historyRes, configRes, emojisRes, examplesRes] = await Promise.all([
      api.ntfy.getTopics(),
      api.ntfy.getTemplates(),
      api.ntfy.getSavedMessages(),
      api.ntfy.getHistory({ limit: 50 }),
      api.ntfy.getConfig(),
      api.ntfy.getEmojiCategories(),
      api.ntfy.getExamples(),
    ])

    ntfyTopics.value = topicsRes.data || []
    ntfyTemplates.value = templatesRes.data || []
    ntfySavedMessages.value = savedRes.data || []
    ntfyHistory.value = historyRes.data || []
    ntfyServerConfig.value = configRes.data || {}
    ntfyEmojiCategories.value = emojisRes.data || {}
    ntfyIntegrationExamples.value = examplesRes.data || []
  } catch (error) {
    console.error('Failed to load NTFY data:', error)
  } finally {
    if (ntfyLoadingInterval) clearInterval(ntfyLoadingInterval)
    ntfyLoading.value = false
  }
}

// Watch for tab change to load NTFY data
watch(mainTab, (newTab) => {
  if (newTab === 'ntfy' && ntfyLoading.value) {
    loadNtfyData()
  }
})

// NTFY Message handlers
async function handleNtfySendMessage(message) {
  try {
    const res = await api.ntfy.send(message)
    if (res.data.success) {
      // Refresh history
      const historyRes = await api.ntfy.getHistory({ limit: 50 })
      ntfyHistory.value = historyRes.data || []
      // Refresh status
      const statusRes = await api.ntfy.status()
      ntfyStatus.value = statusRes.data
      return { success: true }
    }
    return { success: false, error: res.data.error }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handleNtfySaveMessage(message) {
  try {
    await api.ntfy.createSavedMessage(message)
    const savedRes = await api.ntfy.getSavedMessages()
    ntfySavedMessages.value = savedRes.data || []
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

// NTFY Template handlers
async function handleNtfyCreateTemplate(template) {
  try {
    await api.ntfy.createTemplate(template)
    const res = await api.ntfy.getTemplates()
    ntfyTemplates.value = res.data || []
    // Refresh status
    const statusRes = await api.ntfy.status()
    ntfyStatus.value = statusRes.data
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handleNtfyUpdateTemplate(id, template) {
  try {
    await api.ntfy.updateTemplate(id, template)
    const res = await api.ntfy.getTemplates()
    ntfyTemplates.value = res.data || []
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handleNtfyDeleteTemplate(id) {
  try {
    await api.ntfy.deleteTemplate(id)
    const res = await api.ntfy.getTemplates()
    ntfyTemplates.value = res.data || []
    // Refresh status
    const statusRes = await api.ntfy.status()
    ntfyStatus.value = statusRes.data
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handleNtfyPreviewTemplate(data) {
  try {
    const res = await api.ntfy.previewTemplate(data)
    return res.data
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

// NTFY Topic handlers
async function handleNtfyCreateTopic(topic) {
  try {
    const createRes = await api.ntfy.createTopic(topic)
    const createdTopic = createRes.data
    const res = await api.ntfy.getTopics()
    ntfyTopics.value = res.data || []
    // Refresh status
    const statusRes = await api.ntfy.status()
    ntfyStatus.value = statusRes.data
    return { success: true, topic: createdTopic }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handleNtfyUpdateTopic(id, topic) {
  try {
    await api.ntfy.updateTopic(id, topic)
    const res = await api.ntfy.getTopics()
    ntfyTopics.value = res.data || []
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handleNtfyDeleteTopic(id) {
  try {
    await api.ntfy.deleteTopic(id)
    const res = await api.ntfy.getTopics()
    ntfyTopics.value = res.data || []
    // Refresh status
    const statusRes = await api.ntfy.status()
    ntfyStatus.value = statusRes.data
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

// NTFY Sync topics <-> channels (bidirectional)
async function handleNtfySyncTopics() {
  try {
    // Sync in both directions
    const [topicsToChannels, channelsToTopics] = await Promise.all([
      api.ntfy.syncTopicsToChannels(),
      api.ntfy.syncChannelsToTopics()
    ])

    // Refresh data to show changes
    await Promise.all([loadData(), loadNtfyData()])

    return {
      success: true,
      topicsToChannels: topicsToChannels.data,
      channelsToTopics: channelsToTopics.data,
      message: `Synced ${topicsToChannels.data.synced || 0} topics to channels, ${channelsToTopics.data.synced || 0} channels to topics`
    }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

// NTFY Saved message handlers
async function handleNtfySendSavedMessage(id) {
  try {
    const res = await api.ntfy.sendSavedMessage(id)
    if (res.data.success) {
      // Refresh history
      const historyRes = await api.ntfy.getHistory({ limit: 50 })
      ntfyHistory.value = historyRes.data || []
      // Refresh status
      const statusRes = await api.ntfy.status()
      ntfyStatus.value = statusRes.data
      return { success: true }
    }
    return { success: false, error: res.data.error }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handleNtfyDeleteSavedMessage(id) {
  try {
    await api.ntfy.deleteSavedMessage(id)
    const res = await api.ntfy.getSavedMessages()
    ntfySavedMessages.value = res.data || []
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

// NTFY History handlers
async function loadMoreNtfyHistory() {
  try {
    const res = await api.ntfy.getHistory({ limit: 50, offset: ntfyHistory.value.length })
    ntfyHistory.value = [...ntfyHistory.value, ...(res.data || [])]
  } catch (error) {
    console.error('Failed to load more history:', error)
  }
}

// NTFY Config handler
async function handleNtfyUpdateConfig(config) {
  try {
    await api.ntfy.updateConfig(config)
    const res = await api.ntfy.getConfig()
    ntfyServerConfig.value = res.data || {}
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1
          :class="[
            'text-2xl font-bold',
            'text-primary'
          ]"
        >
          Notifications
        </h1>
        <p class="text-secondary mt-1">Configure notification channels and push notifications</p>
      </div>
      <button
        v-if="mainTab === 'channels' && !loading && channels.length > 0"
        @click="openAddDialog"
        :class="[
          'btn-primary flex items-center gap-2',
          ''
        ]"
      >
        <PlusIcon class="h-4 w-4" />
        Add Channel
      </button>
    </div>

    <!-- Main Tab Navigation -->
    <div class="flex flex-wrap gap-2 pb-4 border-b border-gray-400 dark:border-gray-700">
      <button
        v-for="tab in mainTabs"
        :key="tab.id"
        @click="mainTab = tab.id"
        :class="[
          'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap border',
          mainTab === tab.id
            ? `${tab.bgActive} ${tab.textActive} ${tab.borderActive}`
            : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700/50 border-transparent'
        ]"
      >
        <component :is="tab.icon" :class="['h-4 w-4', mainTab === tab.id ? '' : tab.iconColor]" />
        {{ tab.name }}
      </button>
    </div>

    <!-- Channels Tab Content -->
    <template v-if="mainTab === 'channels'">
      <!-- Notification Loading Animation -->
      <div v-if="loading" class="py-16 flex flex-col items-center justify-center">
        <div class="relative">
          <!-- Bell with ring animation -->
          <div class="notification-bell">
            <BellIcon class="h-12 w-12 text-blue-500" />
          </div>
          <!-- Notification waves -->
          <div class="absolute -top-1 -right-1">
            <div class="notification-wave w-4 h-4 rounded-full bg-emerald-400"></div>
            <div class="notification-wave animation-delay-1 w-4 h-4 rounded-full bg-emerald-400 absolute top-0 left-0"></div>
          </div>
        </div>
        <p class="mt-6 text-sm font-medium text-secondary">{{ notificationLoadingMessages[notificationLoadingMessageIndex] || 'Loading notifications...' }}</p>
        <p class="mt-1 text-xs text-muted">Fetching notification channels</p>
      </div>

      <template v-else>
      <!-- Stats Grid -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
                <BellIcon class="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Total Channels</p>
                <p class="text-xl font-bold text-primary">{{ stats.total }}</p>
              </div>
            </div>
          </div>
        </Card>

        <Card :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-500/20">
                <CheckCircleIcon class="h-5 w-5 text-emerald-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Active</p>
                <p class="text-xl font-bold text-primary">{{ stats.active }}</p>
              </div>
            </div>
          </div>
        </Card>

        <Card :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-green-100 dark:bg-green-500/20">
                <LinkIcon class="h-5 w-5 text-green-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Webhook Enabled</p>
                <p class="text-xl font-bold text-primary">{{ stats.webhookEnabled }}</p>
              </div>
            </div>
          </div>
        </Card>

        <Card :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-500/20">
                <PaperAirplaneIcon class="h-5 w-5 text-purple-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Sent</p>
                <p class="text-xl font-bold text-primary">{{ stats.sent }}</p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Notification Channels (Collapsible) -->
      <Card :padding="false">
        <div
          @click="channelsExpanded = !channelsExpanded"
          class="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
        >
          <div class="flex items-center gap-3">
            <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
              <BellIcon class="h-5 w-5 text-blue-500" />
            </div>
            <div>
              <h3 class="font-semibold text-primary">Notification Channels</h3>
              <p class="text-sm text-secondary">Configure where alerts are sent</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs px-2 py-1 rounded-full bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300">
              {{ channels.length }} channel{{ channels.length !== 1 ? 's' : '' }}
            </span>
            <ChevronDownIcon v-if="channelsExpanded" class="h-5 w-5 text-secondary" />
            <ChevronRightIcon v-else class="h-5 w-5 text-secondary" />
          </div>
        </div>

        <Transition name="collapse">
          <div v-if="channelsExpanded" class="px-4 pb-4 border-t border-gray-400 dark:border-gray-700">
            <EmptyState
              v-if="channels.length === 0"
              :icon="BellIcon"
              title="No channels configured"
              description="Add a notification channel to start receiving alerts."
              action-text="Add Channel"
              @action="openAddDialog"
              class="pt-4"
            />

            <div v-else class="space-y-2 pt-2">
              <!-- Header row - fixed widths, STATUS aligns under Webhook Enabled stat box -->
              <div class="grid grid-cols-[44px_292px_280px_70px_90px_55px_1fr] gap-3 p-3 border border-transparent text-xs font-medium text-secondary uppercase tracking-wide">
                <div></div>
                <div>Name</div>
                <div>Channel Slug</div>
                <div class="w-full text-center">Status</div>
                <div class="w-full text-center">Webhook</div>
                <div class="w-full text-center">Type</div>
                <div class="w-full text-right pr-[85px]">Actions</div>
              </div>
              <div
                v-for="channel in channels"
                :key="channel.id"
                class="grid grid-cols-[44px_292px_280px_70px_90px_55px_1fr] gap-3 items-center p-3 rounded-lg bg-surface-hover border border-gray-400 dark:border-black"
              >
                <!-- Icon -->
                <div
                  :class="[
                    'p-2 rounded-lg flex-shrink-0',
                    isLocalNtfyChannel(channel)
                      ? (channel.enabled ? 'bg-amber-100 dark:bg-amber-500/20' : 'bg-gray-100 dark:bg-gray-500/20')
                      : (channel.enabled ? 'bg-blue-100 dark:bg-blue-500/20' : 'bg-gray-100 dark:bg-gray-500/20')
                  ]"
                >
                  <component
                    :is="getChannelIcon(channel)"
                    :class="[
                      'h-5 w-5',
                      isLocalNtfyChannel(channel)
                        ? (channel.enabled ? 'text-amber-500' : 'text-gray-500')
                        : (channel.enabled ? 'text-blue-500' : 'text-gray-500')
                    ]"
                  />
                </div>
                <!-- Name -->
                <p class="font-medium text-primary truncate">{{ channel.name }}</p>
                <!-- Slug -->
                <code class="text-xs text-secondary font-mono bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded truncate">channel:{{ channel.slug }}</code>
                <!-- Status -->
                <div class="w-full text-center">
                  <StatusBadge :status="channel.enabled ? 'active' : 'inactive'" size="sm" class="inline-flex" />
                </div>
                <!-- Webhook -->
                <div class="w-full text-center">
                  <span
                    v-if="channel.webhook_enabled"
                    :class="[
                      'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
                      channel.enabled
                        ? 'bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-300'
                        : 'bg-gray-100 dark:bg-gray-500/20 text-gray-500 dark:text-gray-400'
                    ]"
                  >
                    <LinkIcon class="h-3 w-3" />
                    Webhook
                  </span>
                  <span v-else class="text-xs text-gray-400">-</span>
                </div>
                <!-- Type -->
                <div class="w-full text-center">
                  <span v-if="isLocalNtfyChannel(channel)" class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300">
                    <MegaphoneIcon class="h-3 w-3" />
                    Local
                  </span>
                  <span v-else class="text-xs text-secondary capitalize">{{ channel.service_type }}</span>
                </div>
                <!-- Actions -->
                <div class="w-full flex items-center gap-1 justify-end">
                  <button
                    @click.stop="testChannel(channel)"
                    :disabled="testingChannel === channel.id"
                    class="btn-secondary p-2"
                    title="Test"
                  >
                    <PaperAirplaneIcon
                      :class="['h-4 w-4', testingChannel === channel.id && 'animate-pulse']"
                    />
                  </button>
                  <button @click.stop="openEditDialog(channel)" class="btn-secondary p-2" title="Edit">
                    <PencilSquareIcon class="h-4 w-4" />
                  </button>
                  <button
                    @click.stop="openDeleteDialog(channel)"
                    class="btn-secondary p-2 text-red-500 hover:text-red-600"
                    title="Delete"
                  >
                    <TrashIcon class="h-4 w-4" />
                  </button>
                  <label class="relative inline-flex items-center cursor-pointer ml-1">
                    <input
                      type="checkbox"
                      :checked="channel.enabled"
                      @change.stop="toggleChannel(channel)"
                      class="sr-only peer"
                    />
                    <div
                      class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-400 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"
                    ></div>
                  </label>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </Card>

      <!-- Notification History (Collapsible) -->
      <Card :padding="false">
        <div
          @click="historyExpanded = !historyExpanded"
          class="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
        >
          <div class="flex items-center gap-3">
            <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-500/20">
              <ClockIcon class="h-5 w-5 text-purple-500" />
            </div>
            <div>
              <h3 class="font-semibold text-primary">Recent Notifications</h3>
              <p class="text-sm text-secondary">Last 20 notifications sent</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs px-2 py-1 rounded-full bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-300">
              {{ history.length }} total
            </span>
            <ChevronDownIcon v-if="historyExpanded" class="h-5 w-5 text-secondary" />
            <ChevronRightIcon v-else class="h-5 w-5 text-secondary" />
          </div>
        </div>

        <Transition name="collapse">
          <div v-if="historyExpanded" class="px-4 pb-4 border-t border-gray-400 dark:border-gray-700">
            <EmptyState
              v-if="history.length === 0"
              :icon="BellIcon"
              title="No notifications sent"
              description="Notifications will appear here once they are triggered."
              class="pt-4"
            />

            <div v-else class="space-y-3 pt-2">
              <!-- Iterate through all history entries (groups and singles) -->
              <template v-for="entry in groupedHistory" :key="entry.id">

                <!-- Group Entry (notification sent to a group) -->
                <div
                  v-if="entry.type === 'group'"
                  class="border border-indigo-200 dark:border-indigo-800 rounded-lg overflow-hidden"
                >
                  <!-- Group Header -->
                  <div
                    @click="toggleHistoryGroup(entry.id)"
                    class="flex items-center gap-3 p-3 cursor-pointer bg-indigo-50 dark:bg-indigo-900/30 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 transition-colors"
                  >
                    <component
                      :is="expandedHistoryGroups.has(entry.id) ? ChevronDownIcon : ChevronRightIcon"
                      class="h-4 w-4 text-indigo-500 flex-shrink-0"
                    />
                    <div class="p-1.5 rounded-lg bg-indigo-100 dark:bg-indigo-500/20 flex-shrink-0">
                      <HashtagIcon class="h-4 w-4 text-indigo-500" />
                    </div>
                    <div class="flex-1 min-w-0">
                      <p class="text-sm font-medium text-indigo-700 dark:text-indigo-300">
                        {{ entry.event_data?.title || entry.event_type }} → {{ entry.groupName }}
                      </p>
                      <p class="text-xs text-indigo-600/70 dark:text-indigo-400/70">
                        {{ new Date(entry.sent_at).toLocaleString() }}
                      </p>
                    </div>
                    <StatusBadge :status="entry.status" size="sm" class="flex-shrink-0" />
                    <span class="text-xs px-2 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-500/30 text-indigo-700 dark:text-indigo-300 flex-shrink-0">
                      {{ entry.channels.length }} channel{{ entry.channels.length !== 1 ? 's' : '' }}
                    </span>
                  </div>

                  <!-- Group Expanded Content - Shows channel entries exactly like standalone messages -->
                  <Transition name="collapse">
                    <div v-if="expandedHistoryGroups.has(entry.id)" class="border-t border-indigo-200 dark:border-indigo-800 p-2 space-y-2 bg-white dark:bg-gray-800/50">
                      <!-- Each channel as a full expandable entry (same as standalone) -->
                      <div
                        v-for="channel in entry.channels"
                        :key="channel.id"
                        class="border border-gray-400 dark:border-black rounded-lg overflow-hidden"
                      >
                        <!-- Channel Header (same layout as standalone) -->
                        <div
                          @click="toggleHistoryItem(channel.id)"
                          class="flex items-center gap-3 p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                        >
                          <component
                            :is="expandedHistoryItems.has(channel.id) ? ChevronDownIcon : ChevronRightIcon"
                            class="h-4 w-4 text-secondary flex-shrink-0"
                          />
                          <div class="flex-1 min-w-0 flex items-center gap-4">
                            <div class="flex-1 min-w-0">
                              <p class="text-sm font-medium text-primary truncate">
                                {{ channel.event_data?.title || channel.event_type }}
                              </p>
                              <p class="text-xs text-secondary truncate">
                                {{ channel.service_name }} • {{ new Date(channel.sent_at).toLocaleString() }}
                              </p>
                            </div>
                            <StatusBadge :status="channel.status" size="sm" class="flex-shrink-0" />
                          </div>
                        </div>

                        <!-- Channel Expanded Details (same layout as standalone) -->
                        <Transition name="collapse">
                          <div
                            v-if="expandedHistoryItems.has(channel.id)"
                            class="px-4 pb-4 pt-2 border-t border-gray-400 dark:border-black bg-gray-50 dark:bg-gray-800/50"
                          >
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <!-- Left Column -->
                              <div class="space-y-3">
                                <div>
                                  <label class="text-xs font-medium text-secondary uppercase tracking-wide">Event Type</label>
                                  <p class="text-sm text-primary font-mono mt-1">{{ channel.event_type }}</p>
                                </div>
                                <div>
                                  <label class="text-xs font-medium text-secondary uppercase tracking-wide">Channel</label>
                                  <p class="text-sm text-primary mt-1">{{ channel.service_name }}</p>
                                </div>
                                <div>
                                  <label class="text-xs font-medium text-secondary uppercase tracking-wide">Status</label>
                                  <div class="mt-1">
                                    <StatusBadge :status="channel.status" size="sm" />
                                  </div>
                                </div>
                                <div>
                                  <label class="text-xs font-medium text-secondary uppercase tracking-wide">Sent At</label>
                                  <p class="text-sm text-primary mt-1">{{ new Date(channel.sent_at).toLocaleString() }}</p>
                                </div>
                                <div v-if="channel.error_message">
                                  <label class="text-xs font-medium text-red-500 uppercase tracking-wide">Error</label>
                                  <p class="text-sm text-red-600 dark:text-red-400 mt-1">{{ channel.error_message }}</p>
                                </div>
                              </div>

                              <!-- Right Column - Message Content -->
                              <div class="space-y-3">
                                <div v-if="channel.event_data?.title">
                                  <label class="text-xs font-medium text-secondary uppercase tracking-wide">Title</label>
                                  <p class="text-sm text-primary mt-1">{{ channel.event_data.title }}</p>
                                </div>
                                <div v-if="channel.event_data?.message">
                                  <label class="text-xs font-medium text-secondary uppercase tracking-wide">Message</label>
                                  <p class="text-sm text-primary mt-1 whitespace-pre-wrap break-words">{{ channel.event_data.message }}</p>
                                </div>
                                <div v-if="channel.event_data?.priority">
                                  <label class="text-xs font-medium text-secondary uppercase tracking-wide">Priority</label>
                                  <p class="text-sm text-primary mt-1 capitalize">{{ channel.event_data.priority }}</p>
                                </div>
                                <div v-if="channel.severity">
                                  <label class="text-xs font-medium text-secondary uppercase tracking-wide">Severity</label>
                                  <p class="text-sm text-primary mt-1 capitalize">{{ channel.severity }}</p>
                                </div>
                              </div>
                            </div>
                          </div>
                        </Transition>
                      </div>
                    </div>
                  </Transition>
                </div>

                <!-- Single Entry (notification not sent to a group) -->
                <div
                  v-else
                  class="border border-gray-400 dark:border-black rounded-lg overflow-hidden"
                >
                  <!-- Collapsed Header Row -->
                  <div
                    @click="toggleHistoryItem(entry.id)"
                    class="flex items-center gap-3 p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                  >
                    <component
                      :is="expandedHistoryItems.has(entry.id) ? ChevronDownIcon : ChevronRightIcon"
                      class="h-4 w-4 text-secondary flex-shrink-0"
                    />
                    <div class="flex-1 min-w-0 flex items-center gap-4">
                      <div class="flex-1 min-w-0">
                        <p class="text-sm font-medium text-primary truncate">
                          {{ entry.event_data?.title || entry.event_type }}
                        </p>
                        <p class="text-xs text-secondary truncate">
                          {{ entry.service_name }} • {{ new Date(entry.sent_at || entry.created_at).toLocaleString() }}
                        </p>
                      </div>
                      <StatusBadge :status="entry.status" size="sm" class="flex-shrink-0" />
                    </div>
                  </div>

                  <!-- Expanded Details -->
                  <Transition name="collapse">
                    <div
                      v-if="expandedHistoryItems.has(entry.id)"
                      class="px-4 pb-4 pt-2 border-t border-gray-400 dark:border-black bg-gray-50 dark:bg-gray-800/50"
                    >
                      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <!-- Left Column -->
                        <div class="space-y-3">
                          <div>
                            <label class="text-xs font-medium text-secondary uppercase tracking-wide">Event Type</label>
                            <p class="text-sm text-primary font-mono mt-1">{{ entry.event_type }}</p>
                          </div>
                          <div>
                            <label class="text-xs font-medium text-secondary uppercase tracking-wide">Channel</label>
                            <p class="text-sm text-primary mt-1">{{ entry.service_name }}</p>
                          </div>
                          <div>
                            <label class="text-xs font-medium text-secondary uppercase tracking-wide">Status</label>
                            <div class="mt-1">
                              <StatusBadge :status="entry.status" size="sm" />
                            </div>
                          </div>
                          <div>
                            <label class="text-xs font-medium text-secondary uppercase tracking-wide">Sent At</label>
                            <p class="text-sm text-primary mt-1">{{ new Date(entry.sent_at || entry.created_at).toLocaleString() }}</p>
                          </div>
                          <div v-if="entry.error_message">
                            <label class="text-xs font-medium text-red-500 uppercase tracking-wide">Error</label>
                            <p class="text-sm text-red-600 dark:text-red-400 mt-1">{{ entry.error_message }}</p>
                          </div>
                        </div>

                        <!-- Right Column - Message Content -->
                        <div class="space-y-3">
                          <div v-if="entry.event_data?.title">
                            <label class="text-xs font-medium text-secondary uppercase tracking-wide">Title</label>
                            <p class="text-sm text-primary mt-1">{{ entry.event_data.title }}</p>
                          </div>
                          <div v-if="entry.event_data?.message">
                            <label class="text-xs font-medium text-secondary uppercase tracking-wide">Message</label>
                            <p class="text-sm text-primary mt-1 whitespace-pre-wrap break-words">{{ entry.event_data.message }}</p>
                          </div>
                          <div v-if="entry.event_data?.priority">
                            <label class="text-xs font-medium text-secondary uppercase tracking-wide">Priority</label>
                            <p class="text-sm text-primary mt-1 capitalize">{{ entry.event_data.priority }}</p>
                          </div>
                          <div v-if="entry.severity">
                            <label class="text-xs font-medium text-secondary uppercase tracking-wide">Severity</label>
                            <p class="text-sm text-primary mt-1 capitalize">{{ entry.severity }}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </Transition>
                </div>

              </template>
            </div>
          </div>
        </Transition>
      </Card>

      <!-- n8n Webhook Integration (Collapsible) -->
      <Card v-if="webhookInfo" :padding="false">
        <div
          @click="webhookExpanded = !webhookExpanded"
          class="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
        >
          <div class="flex items-center gap-3">
            <div class="p-2 rounded-lg bg-green-100 dark:bg-green-500/20">
              <LinkIcon class="h-5 w-5 text-green-500" />
            </div>
            <div>
              <h3 class="font-semibold text-primary">n8n Webhook Integration</h3>
              <p class="text-sm text-secondary">Send notifications from n8n workflows</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs px-2 py-1 rounded-full bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-300">
              {{ stats.webhookEnabled }} channel{{ stats.webhookEnabled !== 1 ? 's' : '' }} enabled
            </span>
            <ChevronDownIcon v-if="webhookExpanded" class="h-5 w-5 text-secondary" />
            <ChevronRightIcon v-else class="h-5 w-5 text-secondary" />
          </div>
        </div>

        <Transition name="collapse">
          <div v-if="webhookExpanded" class="px-4 pb-4 space-y-4 border-t border-gray-400 dark:border-gray-700">
            <p class="text-sm text-secondary pt-4">
              Use this webhook endpoint in your n8n workflows to send notifications through all channels with "n8n Webhook Routing" enabled.
            </p>

            <!-- Webhook URL -->
            <div>
              <label class="block text-sm font-medium text-primary mb-1">Webhook URL</label>
              <div class="flex items-center gap-2">
                <input
                  type="text"
                  :value="getWebhookUrl()"
                  readonly
                  class="flex-1 px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white font-mono text-sm"
                />
                <button
                  @click.stop="copyToClipboard(getWebhookUrl(), 'Webhook URL')"
                  class="btn-secondary p-2"
                  title="Copy URL"
                >
                  <ClipboardDocumentIcon class="h-5 w-5" />
                </button>
              </div>
            </div>

            <!-- API Key -->
            <div>
              <label class="block text-sm font-medium text-primary mb-1">API Key</label>

              <!-- No API Key - Generate Button -->
              <div v-if="!webhookInfo.has_key" class="bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-4">
                <div class="flex items-start gap-3">
                  <KeyIcon class="h-5 w-5 text-yellow-600 dark:text-yellow-400 mt-0.5" />
                  <div class="flex-1">
                    <p class="text-sm text-yellow-700 dark:text-yellow-300 mb-3">
                      No API key configured. Generate one to enable webhook notifications from n8n.
                    </p>
                    <button
                      @click.stop="generateApiKey"
                      :disabled="generatingKey"
                      class="inline-flex items-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white text-sm font-medium rounded-lg disabled:opacity-50"
                    >
                      <KeyIcon class="h-4 w-4" />
                      {{ generatingKey ? 'Generating...' : 'Generate API Key' }}
                    </button>
                  </div>
                </div>
              </div>

              <!-- Has API Key - Show with Regenerate -->
              <template v-else>
                <div class="flex items-center gap-2">
                  <input
                    :type="showApiKey ? 'text' : 'password'"
                    :value="webhookInfo.api_key"
                    readonly
                    class="flex-1 px-3 py-2 rounded-lg border border-gray-400 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white font-mono text-sm"
                  />
                  <button
                    @click.stop="showApiKey = !showApiKey"
                    class="btn-secondary p-2"
                    :title="showApiKey ? 'Hide API Key' : 'Show API Key'"
                  >
                    <EyeSlashIcon v-if="showApiKey" class="h-5 w-5" />
                    <EyeIcon v-else class="h-5 w-5" />
                  </button>
                  <button
                    @click.stop="copyToClipboard(webhookInfo.api_key, 'API Key')"
                    class="btn-secondary p-2"
                    title="Copy API Key"
                  >
                    <ClipboardDocumentIcon class="h-5 w-5" />
                  </button>
                  <button
                    @click.stop="openRegenerateDialog"
                    class="btn-secondary p-2 text-orange-500 hover:text-orange-600"
                    title="Regenerate API Key"
                  >
                    <ArrowPathIcon class="h-5 w-5" />
                  </button>
                </div>
                <p class="text-xs text-secondary mt-1">
                  Click the refresh icon to regenerate if your key is compromised.
                </p>
              </template>
            </div>

            <!-- n8n Credential Tip -->
            <div class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
              <p class="text-xs text-blue-700 dark:text-blue-300">
                <strong>Tip:</strong> In n8n, create a "Header Auth" credential with Name: <code class="bg-blue-100 dark:bg-blue-800 px-1 rounded">X-API-Key</code> and Value: your API key above.
                Then attach this credential to your HTTP Request node for secure, reusable authentication.
              </p>
            </div>

            <!-- Usage Example -->
            <div class="bg-gray-100 dark:bg-gray-700 rounded-lg p-4">
              <p class="text-xs font-medium text-secondary mb-2">n8n HTTP Request Node:</p>
              <div class="text-xs font-mono text-gray-600 dark:text-gray-300 space-y-1">
                <p><strong>Method:</strong> POST</p>
                <p><strong>URL:</strong> {{ getWebhookUrl() }}</p>
                <p><strong>Authentication:</strong> Header Auth (create credential with X-API-Key)</p>
                <p><strong>Body Content Type:</strong> JSON</p>
                <p><strong>Body:</strong></p>
                <pre class="mt-1 overflow-x-auto whitespace-pre-wrap">{
  "title": "Alert Title",
  "message": "Your notification message",
  "priority": "normal",
  "targets": ["all"]
}</pre>
              </div>
            </div>

            <!-- Targeting Examples -->
            <div class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
              <p class="text-xs font-medium text-blue-700 dark:text-blue-300 mb-2">Target Examples:</p>
              <div class="text-xs font-mono text-blue-600 dark:text-blue-400 space-y-2">
                <div>
                  <p class="text-blue-700 dark:text-blue-300 mb-1">All channels:</p>
                  <code class="bg-blue-100 dark:bg-blue-800 px-2 py-1 rounded">"targets": ["all"]</code>
                </div>
                <div>
                  <p class="text-blue-700 dark:text-blue-300 mb-1">Specific channel:</p>
                  <code class="bg-blue-100 dark:bg-blue-800 px-2 py-1 rounded">"targets": ["channel:devops_slack"]</code>
                </div>
                <div>
                  <p class="text-blue-700 dark:text-blue-300 mb-1">Group:</p>
                  <code class="bg-blue-100 dark:bg-blue-800 px-2 py-1 rounded">"targets": ["group:dev_ops"]</code>
                </div>
                <div>
                  <p class="text-blue-700 dark:text-blue-300 mb-1">Multiple targets:</p>
                  <code class="bg-blue-100 dark:bg-blue-800 px-2 py-1 rounded">"targets": ["channel:ceo_phone", "group:management"]</code>
                </div>
              </div>
            </div>

            <!-- Create Test Workflows -->
            <div class="border-t border-gray-400 dark:border-gray-700 pt-4 mt-4">
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-2">
                  <Cog6ToothIcon class="h-5 w-5 text-secondary" />
                  <h4 class="font-medium text-primary">Create Test Workflows</h4>
                </div>
                <button
                  @click.stop="checkN8nStatus"
                  :disabled="n8nStatus.checking"
                  class="text-xs text-blue-500 hover:text-blue-600 flex items-center gap-1"
                >
                  <ArrowPathIcon :class="['h-3 w-3', n8nStatus.checking && 'animate-spin']" />
                  {{ n8nStatus.checking ? 'Checking...' : 'Check n8n API' }}
                </button>
              </div>

              <p class="text-sm text-secondary mb-3">
                Create test workflows in n8n to verify targeted notifications are working.
              </p>

              <!-- n8n Status -->
              <div v-if="n8nStatus.error" class="bg-red-50 dark:bg-red-900/20 rounded-lg p-3 mb-3">
                <div class="flex items-start gap-2">
                  <XCircleIcon class="h-5 w-5 text-red-500 mt-0.5" />
                  <div>
                    <p class="text-sm font-medium text-red-700 dark:text-red-300">n8n API not available</p>
                    <p class="text-xs text-red-600 dark:text-red-400 mt-1">{{ n8nStatus.error }}</p>
                    <div class="text-xs text-red-600 dark:text-red-400 mt-2 space-y-1">
                      <p class="font-medium">To enable n8n API integration:</p>
                      <ol class="list-decimal list-inside space-y-0.5 ml-1">
                        <li>Generate an API key in n8n: Settings → API</li>
                        <li>Add <code class="bg-red-100 dark:bg-red-800 px-1 rounded">N8N_API_KEY=your_key</code> to your <code class="bg-red-100 dark:bg-red-800 px-1 rounded">.env</code> file</li>
                        <li>Restart the management container: <code class="bg-red-100 dark:bg-red-800 px-1 rounded">docker compose up -d n8n_management</code></li>
                      </ol>
                    </div>
                  </div>
                </div>
              </div>

              <div v-else-if="n8nStatus.connected" class="bg-green-50 dark:bg-green-900/20 rounded-lg p-3 mb-3">
                <div class="flex items-center gap-2">
                  <CheckCircleIcon class="h-5 w-5 text-green-500" />
                  <p class="text-sm text-green-700 dark:text-green-300">n8n API connected</p>
                </div>
              </div>

              <p v-if="!webhookInfo.has_key" class="text-xs text-yellow-600 dark:text-yellow-400 mb-3">
                Generate an API key above first before creating test workflows.
              </p>

              <!-- Workflow Type Buttons -->
              <div class="space-y-3">
                <!-- Create All Button -->
                <button
                  @click.stop="showWorkflowCreationDialog"
                  :disabled="creatingWorkflow || !webhookInfo.has_key"
                  :class="[
                    'w-full inline-flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium rounded-lg transition-colors',
                    webhookInfo.has_key
                      ? 'bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-50'
                      : 'bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400 cursor-not-allowed'
                  ]"
                >
                  <SparklesIcon class="h-4 w-4" />
                  {{ creatingWorkflow === 'all' ? 'Creating All...' : 'Create Test Workflows' }}
                </button>
                <p class="text-xs text-secondary text-center">Create workflows with auto-configured credentials</p>

                <!-- Credential Only Button -->
                <button
                  @click.stop="createOrUpdateCredential"
                  :disabled="creatingCredential || !webhookInfo.has_key || !n8nStatus.connected"
                  :class="[
                    'w-full inline-flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-lg transition-colors border',
                    webhookInfo.has_key && n8nStatus.connected
                      ? 'border-amber-400 dark:border-amber-500 bg-amber-50 dark:bg-amber-900/20 hover:bg-amber-100 dark:hover:bg-amber-900/30 text-amber-700 dark:text-amber-300 disabled:opacity-50'
                      : 'border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                  ]"
                >
                  <KeyIcon class="h-3.5 w-3.5" />
                  {{ creatingCredential ? 'Updating...' : 'Create/Update n8n Credential' }}
                </button>
                <p class="text-xs text-muted text-center">
                  Update credential if you regenerated your API key
                </p>
              </div>

              <p class="text-xs text-secondary mt-3">
                Credentials are auto-configured when creating workflows.
                For channel/group workflows, edit the JSON body in n8n to specify your target slug.
              </p>
            </div>
          </div>
        </Transition>
      </Card>
      </template>
    </template>

    <!-- Groups Tab Content -->
    <template v-else-if="mainTab === 'groups'">
      <!-- Groups Loading Animation -->
      <div v-if="loading" class="py-16 flex flex-col items-center justify-center">
        <div class="relative">
          <div class="notification-bell">
            <HashtagIcon class="h-12 w-12 text-indigo-500" />
          </div>
          <div class="absolute -top-1 -right-1">
            <div class="notification-wave w-4 h-4 rounded-full bg-indigo-400"></div>
            <div class="notification-wave animation-delay-1 w-4 h-4 rounded-full bg-indigo-400 absolute top-0 left-0"></div>
          </div>
        </div>
        <p class="mt-6 text-sm font-medium text-secondary">{{ notificationLoadingMessages[notificationLoadingMessageIndex] || 'Loading groups...' }}</p>
        <p class="mt-1 text-xs text-muted">Fetching notification groups</p>
      </div>

      <template v-else>
        <!-- Groups Stats -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-500/20">
                  <HashtagIcon class="h-5 w-5 text-indigo-500" />
                </div>
                <div>
                  <p class="text-sm text-secondary">Total Groups</p>
                  <p class="text-xl font-bold text-primary">{{ stats.groups }}</p>
                </div>
              </div>
            </div>
          </Card>

          <Card :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
                  <BellIcon class="h-5 w-5 text-blue-500" />
                </div>
                <div>
                  <p class="text-sm text-secondary">Total Channels</p>
                  <p class="text-xl font-bold text-primary">{{ stats.total }}</p>
                </div>
              </div>
            </div>
          </Card>

          <Card :padding="false">
            <div class="p-4">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-lg bg-green-100 dark:bg-green-500/20">
                  <LinkIcon class="h-5 w-5 text-green-500" />
                </div>
                <div>
                  <p class="text-sm text-secondary">Webhook Enabled</p>
                  <p class="text-xl font-bold text-primary">{{ stats.webhookEnabled }}</p>
                </div>
              </div>
            </div>
          </Card>
        </div>

        <!-- Groups List (Collapsible) -->
        <Card :padding="false">
          <div
            @click="groupsExpanded = !groupsExpanded"
            class="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-full bg-indigo-100 dark:bg-indigo-500/20">
                <HashtagIcon class="h-5 w-5 text-indigo-500" />
              </div>
              <div>
                <h3 class="font-semibold text-primary">Notification Groups</h3>
                <p class="text-sm text-secondary">Group channels together for targeted notifications</p>
              </div>
            </div>
            <div class="flex items-center gap-3">
              <button
                @click.stop="openAddGroupDialog"
                :class="[
                  'btn-primary flex items-center gap-2',
                  ''
                ]"
              >
                <PlusIcon class="h-4 w-4" />
                Add Group
              </button>
              <span class="text-sm font-medium text-indigo-500">{{ groups.length }} group{{ groups.length !== 1 ? 's' : '' }}</span>
              <ChevronDownIcon v-if="groupsExpanded" class="h-5 w-5 text-secondary" />
              <ChevronRightIcon v-else class="h-5 w-5 text-secondary" />
            </div>
          </div>
          <Transition name="collapse">
            <div v-if="groupsExpanded" class="px-4 pb-4 border-t border-gray-400 dark:border-gray-700">
              <EmptyState
                v-if="groups.length === 0"
                :icon="HashtagIcon"
                title="No groups configured"
                description="Create groups to organize channels and target notifications."
                action-text="Add Group"
                @action="openAddGroupDialog"
                class="pt-4"
              />

              <div v-else class="space-y-2 pt-2">
                <div
                  v-for="group in groups"
                  :key="group.id"
                  class="rounded-lg bg-surface-hover border border-gray-400 dark:border-black overflow-hidden"
                >
                  <!-- Group Header (Clickable to expand) -->
                  <div
                    @click="toggleGroupExpanded(group.id)"
                    class="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors"
                  >
                    <div class="flex items-center gap-3 flex-1 min-w-0">
                      <component
                        :is="expandedGroups.has(group.id) ? ChevronDownIcon : ChevronRightIcon"
                        class="h-4 w-4 text-secondary flex-shrink-0"
                      />
                      <div
                        :class="[
                          'p-2 rounded-lg flex-shrink-0',
                          group.enabled
                            ? 'bg-indigo-100 dark:bg-indigo-500/20'
                            : 'bg-gray-100 dark:bg-gray-500/20'
                        ]"
                      >
                        <HashtagIcon
                          :class="[
                            'h-5 w-5',
                            group.enabled ? 'text-indigo-500' : 'text-gray-500'
                          ]"
                        />
                      </div>
                      <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2">
                          <p class="font-medium text-primary truncate">{{ group.name }}</p>
                          <StatusBadge :status="group.enabled ? 'active' : 'inactive'" size="sm" class="flex-shrink-0" />
                        </div>
                        <p class="text-xs text-secondary mt-0.5">
                          {{ group.channels?.length || 0 }} channel{{ (group.channels?.length || 0) !== 1 ? 's' : '' }}
                          <span class="mx-1">•</span>
                          {{ getGroupMessageCount(group) }} message{{ getGroupMessageCount(group) !== 1 ? 's' : '' }} sent
                        </p>
                      </div>
                    </div>
                    <!-- Group Slug (centered) -->
                    <div class="flex-1 flex justify-center">
                      <div class="text-center">
                        <span class="text-xs font-medium text-secondary uppercase tracking-wide">Group Slug</span>
                        <code class="block text-sm text-primary font-mono bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded mt-0.5">group:{{ group.slug }}</code>
                      </div>
                    </div>
                    <div class="flex items-center gap-1 flex-shrink-0" @click.stop>
                      <button @click="openEditGroupDialog(group)" class="btn-secondary p-2" title="Edit">
                        <PencilSquareIcon class="h-4 w-4" />
                      </button>
                      <button
                        @click="openDeleteGroupDialog(group)"
                        class="btn-secondary p-2 text-red-500 hover:text-red-600"
                        title="Delete"
                      >
                        <TrashIcon class="h-4 w-4" />
                      </button>
                      <label class="relative inline-flex items-center cursor-pointer ml-1">
                        <input
                          type="checkbox"
                          :checked="group.enabled"
                          @change="toggleGroup(group)"
                          class="sr-only peer"
                        />
                        <div
                          class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-400 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-indigo-500"
                        ></div>
                      </label>
                    </div>
                  </div>

                  <!-- Expanded Group Details -->
                  <Transition name="collapse">
                    <div
                      v-if="expandedGroups.has(group.id)"
                      class="px-4 pb-4 pt-2 border-t border-gray-400 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50"
                    >
                      <!-- Group description if present -->
                      <p v-if="group.description" class="text-sm text-secondary mb-3">{{ group.description }}</p>

                      <!-- Channels in group -->
                      <div v-if="group.channels && group.channels.length > 0">
                        <p class="text-xs font-medium text-secondary uppercase tracking-wide mb-2">Channels in this group</p>
                        <div class="rounded-lg border border-gray-400 dark:border-gray-700 overflow-hidden">
                          <!-- Header row -->
                          <div class="grid grid-cols-[28px_minmax(140px,1.5fr)_minmax(180px,2fr)_70px_70px] gap-2 px-3 py-2 bg-gray-100 dark:bg-gray-700 text-xs font-medium text-secondary uppercase tracking-wide">
                            <div></div>
                            <div>Name</div>
                            <div>Direct Channel Slug</div>
                            <div class="text-center">Webhook</div>
                            <div class="text-center">Type</div>
                          </div>
                          <!-- Channel rows -->
                          <div
                            v-for="channel in group.channels"
                            :key="channel.id"
                            class="grid grid-cols-[28px_minmax(140px,1.5fr)_minmax(180px,2fr)_70px_70px] gap-2 px-3 py-2 items-center bg-white dark:bg-gray-800/50 border-t border-gray-400 dark:border-gray-700"
                          >
                            <component
                              :is="getChannelIcon(channel)"
                              :class="['h-4 w-4', isLocalNtfyChannel(channel) ? 'text-amber-500' : 'text-gray-500']"
                            />
                            <span class="font-medium text-sm text-primary truncate">{{ channel.name }}</span>
                            <code class="text-xs text-secondary font-mono bg-gray-100 dark:bg-gray-600 px-1.5 py-0.5 rounded truncate">channel:{{ channel.slug }}</code>
                            <div class="flex justify-center">
                              <span
                                v-if="channel.webhook_enabled"
                                class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-medium bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-300"
                              >
                                <LinkIcon class="h-3 w-3" />
                              </span>
                              <span v-else class="text-xs text-gray-400">-</span>
                            </div>
                            <span v-if="isLocalNtfyChannel(channel)" class="inline-flex items-center justify-center gap-0.5 px-1 py-0.5 rounded text-xs font-medium bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300">
                              <MegaphoneIcon class="h-2.5 w-2.5" />
                              Local
                            </span>
                            <span v-else class="text-xs text-secondary capitalize text-center">{{ channel.service_type }}</span>
                          </div>
                        </div>
                      </div>
                      <div v-else class="text-sm text-secondary italic">No channels in this group</div>

                      <!-- Usage example -->
                      <div class="mt-3 p-3 bg-indigo-50 dark:bg-indigo-900/20 rounded-lg">
                        <p class="text-xs text-indigo-700 dark:text-indigo-300">
                          <strong>Target this group:</strong> Use <code class="bg-indigo-100 dark:bg-indigo-800 px-1.5 py-0.5 rounded font-mono">"group:{{ group.slug }}"</code> in your webhook targets.
                        </p>
                      </div>
                    </div>
                  </Transition>
                </div>
              </div>
            </div>
          </Transition>
        </Card>

        <!-- How to Use Groups -->
        <Card title="How to Target Groups" subtitle="Use groups in your n8n webhooks">
          <div class="space-y-4">
            <p class="text-sm text-secondary">
              When sending notifications from n8n, use the <code class="bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded text-sm font-mono">targets</code> field to specify which groups or channels should receive the notification.
            </p>

            <div class="bg-gray-100 dark:bg-gray-700 rounded-lg p-4">
              <p class="text-xs font-medium text-secondary mb-2">Example: Send to a specific group</p>
              <pre class="text-xs font-mono text-gray-600 dark:text-gray-300 overflow-x-auto whitespace-pre-wrap">{
  "title": "DevOps Alert",
  "message": "Deployment failed on production",
  "priority": "high",
  "targets": ["group:dev_ops"]
}</pre>
            </div>

            <div class="bg-gray-100 dark:bg-gray-700 rounded-lg p-4">
              <p class="text-xs font-medium text-secondary mb-2">Example: Send to multiple targets</p>
              <pre class="text-xs font-mono text-gray-600 dark:text-gray-300 overflow-x-auto whitespace-pre-wrap">{
  "title": "Critical Alert",
  "message": "Database connection lost",
  "priority": "critical",
  "targets": ["group:dev_ops", "channel:ceo_phone"]
}</pre>
            </div>
          </div>
        </Card>
      </template>
    </template>

    <!-- NTFY Push Tab Content -->
    <template v-else-if="mainTab === 'ntfy'">
      <!-- NTFY Loading Animation -->
      <div v-if="ntfyLoading" class="py-16 flex flex-col items-center justify-center">
        <div class="relative">
          <div class="notification-bell">
            <BellAlertIcon class="h-12 w-12 text-rose-500" />
          </div>
          <div class="absolute -top-1 -right-1">
            <div class="notification-wave w-4 h-4 rounded-full bg-rose-400"></div>
            <div class="notification-wave animation-delay-1 w-4 h-4 rounded-full bg-rose-400 absolute top-0 left-0"></div>
          </div>
        </div>
        <p class="mt-6 text-sm font-medium text-secondary">{{ ntfyLoadingMessages[ntfyLoadingMessageIndex] || 'Loading NTFY...' }}</p>
        <p class="mt-1 text-xs text-muted">Fetching push notification service</p>
      </div>

      <template v-else>
        <!-- NTFY Stats Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card :padding="false">
            <div class="p-4">
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-sm text-secondary">Status</p>
                  <p class="text-xl font-bold" :class="ntfyHealth.healthy ? 'text-green-500' : 'text-red-500'">
                    {{ ntfyHealth.healthy ? 'Connected' : 'Disconnected' }}
                  </p>
                </div>
                <div :class="['w-3 h-3 rounded-full', ntfyHealth.healthy ? 'bg-green-500' : 'bg-red-500']"></div>
              </div>
            </div>
          </Card>

          <Card :padding="false">
            <div class="p-4">
              <p class="text-sm text-secondary">Topics</p>
              <p class="text-xl font-bold text-primary">{{ ntfyStatus.topics_count || 0 }}</p>
            </div>
          </Card>

          <Card :padding="false">
            <div class="p-4">
              <p class="text-sm text-secondary">Templates</p>
              <p class="text-xl font-bold text-primary">{{ ntfyStatus.templates_count || 0 }}</p>
            </div>
          </Card>

          <Card :padding="false">
            <div class="p-4">
              <p class="text-sm text-secondary">Messages Today</p>
              <p class="text-xl font-bold text-primary">{{ ntfyStatus.messages_today || 0 }}</p>
            </div>
          </Card>
        </div>

        <!-- NTFY Sub-Tabs -->
        <Card :padding="false">
          <div class="border-b border-gray-400 dark:border-gray-700">
            <nav class="flex -mb-px overflow-x-auto">
              <button
                v-for="tab in ntfyTabs"
                :key="tab.id"
                @click="ntfyActiveTab = tab.id"
                :class="[
                  'px-6 py-4 text-sm font-medium border-b-2 whitespace-nowrap transition-colors',
                  ntfyActiveTab === tab.id
                    ? 'border-orange-500 text-orange-600 dark:text-orange-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-400 dark:text-gray-400 dark:hover:text-gray-300'
                ]"
              >
                <component :is="tab.icon" class="w-5 h-5 inline-block mr-2 -mt-0.5" />
                {{ tab.name }}
              </button>
            </nav>
          </div>

          <div class="p-6">
            <!-- Message Composer Tab -->
            <div v-if="ntfyActiveTab === 'composer'" class="space-y-6">
              <MessageComposer
                :topics="ntfyTopics"
                :emoji-categories="ntfyEmojiCategories"
                @send="handleNtfySendMessage"
                @save="handleNtfySaveMessage"
              />
            </div>

            <!-- Templates Tab -->
            <div v-else-if="ntfyActiveTab === 'templates'" class="space-y-6">
              <TemplateBuilder
                :templates="ntfyTemplates"
                @create="handleNtfyCreateTemplate"
                @update="handleNtfyUpdateTemplate"
                @delete="handleNtfyDeleteTemplate"
                @preview="handleNtfyPreviewTemplate"
              />
            </div>

            <!-- Topics Tab -->
            <div v-else-if="ntfyActiveTab === 'topics'" class="space-y-6">
              <TopicsManager
                :topics="ntfyTopics"
                :on-create="handleNtfyCreateTopic"
                :on-update="handleNtfyUpdateTopic"
                :on-delete="handleNtfyDeleteTopic"
                :on-sync="handleNtfySyncTopics"
              />
            </div>

            <!-- Saved Messages Tab -->
            <div v-else-if="ntfyActiveTab === 'saved'" class="space-y-6">
              <SavedMessages
                :messages="ntfySavedMessages"
                @send="handleNtfySendSavedMessage"
                @delete="handleNtfyDeleteSavedMessage"
              />
            </div>

            <!-- History Tab -->
            <div v-else-if="ntfyActiveTab === 'history'" class="space-y-6">
              <MessageHistory :history="ntfyHistory" @load-more="loadMoreNtfyHistory" />
            </div>

            <!-- Settings Tab -->
            <div v-else-if="ntfyActiveTab === 'settings'" class="space-y-6">
              <ServerSettings :config="ntfyServerConfig" @update="handleNtfyUpdateConfig" />
            </div>

            <!-- Integration Hub Tab -->
            <div v-else-if="ntfyActiveTab === 'integrations'" class="space-y-6">
              <IntegrationHub :examples="ntfyIntegrationExamples" :topics="ntfyTopics" />
            </div>
          </div>
        </Card>
      </template>
    </template>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="deleteDialog.open"
      title="Delete Channel"
      message="Are you sure you want to delete this notification channel? You will stop receiving alerts through this channel."
      confirm-text="Delete"
      :danger="true"
      :loading="deleteDialog.loading"
      @confirm="confirmDelete"
      @cancel="deleteDialog.open = false"
    />

    <!-- Regenerate API Key Confirmation Dialog -->
    <ConfirmDialog
      :open="regenerateDialog.open"
      title="Regenerate API Key"
      message="This will invalidate the current API key. Any n8n workflows using the old key will stop working until you update their credentials with the new key. Are you sure?"
      confirm-text="Regenerate"
      :danger="true"
      :loading="regenerateDialog.loading"
      @confirm="confirmRegenerateKey"
      @cancel="regenerateDialog.open = false"
    />

    <!-- Add/Edit Service Dialog -->
    <NotificationServiceDialog
      :open="serviceDialog.open"
      :service="serviceDialog.service"
      @save="handleServiceSave"
      @cancel="serviceDialog.open = false"
      @update:open="(val) => serviceDialog.open = val"
    />

    <!-- Add/Edit Group Dialog -->
    <NotificationGroupDialog
      :open="groupDialog.open"
      :group="groupDialog.group"
      :channels="channels"
      @save="handleGroupSave"
      @cancel="groupDialog.open = false"
      @update:open="(val) => groupDialog.open = val"
    />

    <!-- Delete Group Confirmation Dialog -->
    <ConfirmDialog
      :open="deleteGroupDialog.open"
      title="Delete Group"
      message="Are you sure you want to delete this notification group? The channels in this group will not be deleted."
      confirm-text="Delete"
      :danger="true"
      :loading="deleteGroupDialog.loading"
      @confirm="confirmDeleteGroup"
      @cancel="deleteGroupDialog.open = false"
    />

    <!-- API Key Regenerated Success Dialog -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="regenerateSuccessDialog.open"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50"
          @click.self="regenerateSuccessDialog.open = false"
        >
          <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full border border-gray-200 dark:border-gray-700">
            <!-- Header -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-lg bg-green-100 dark:bg-green-500/20">
                  <CheckCircleIcon class="h-6 w-6 text-green-500" />
                </div>
                <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
                  API Key Regenerated
                </h3>
              </div>
              <button
                @click="regenerateSuccessDialog.open = false"
                class="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                <XCircleIcon class="h-5 w-5" />
              </button>
            </div>

            <!-- Content -->
            <div class="px-6 py-5 space-y-4">
              <p class="text-sm text-gray-600 dark:text-gray-300">
                Your webhook API key has been regenerated successfully.
              </p>

              <!-- Warning -->
              <div class="flex items-start gap-3 p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
                <ExclamationTriangleIcon class="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                <div class="text-sm text-amber-700 dark:text-amber-300">
                  <p class="font-medium mb-1">Update Required</p>
                  <p>
                    Any n8n workflows using the old API key will stop working.
                    You need to update the "Management Webhook API Key" credential in n8n.
                  </p>
                </div>
              </div>

              <p class="text-sm text-gray-500 dark:text-gray-400">
                Click the button below to automatically update your n8n credential with the new API key.
              </p>
            </div>

            <!-- Footer -->
            <div class="flex flex-col gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 rounded-b-xl">
              <button
                v-if="n8nStatus.connected"
                @click="updateN8nCredentialAfterRegenerate"
                :disabled="regenerateSuccessDialog.updating"
                class="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <KeyIcon v-if="!regenerateSuccessDialog.updating" class="h-4 w-4" />
                <svg v-else class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {{ regenerateSuccessDialog.updating ? 'Updating Credential...' : 'Update n8n Credential Now' }}
              </button>
              <p v-else class="text-xs text-center text-amber-600 dark:text-amber-400">
                n8n API is not connected. Please update the credential manually in n8n.
              </p>
              <button
                @click="regenerateSuccessDialog.open = false"
                class="w-full px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600"
              >
                {{ n8nStatus.connected ? 'I\'ll Update Manually' : 'Close' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Workflow Creation Info Dialog -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="workflowCreationDialog.open"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50"
          @click.self="workflowCreationDialog.open = false"
        >
          <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-xl w-full border border-gray-200 dark:border-gray-700">
            <!-- Header -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-500/20">
                  <SparklesIcon class="h-6 w-6 text-indigo-500" />
                </div>
                <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
                  Create Test Workflows
                </h3>
              </div>
              <button
                @click="workflowCreationDialog.open = false"
                class="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                <XCircleIcon class="h-5 w-5" />
              </button>
            </div>

            <!-- Content -->
            <div class="px-6 py-5 space-y-4">
              <!-- Info Message -->
              <div class="flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                <InformationCircleIcon class="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
                <div class="text-sm text-blue-700 dark:text-blue-300">
                  <p class="font-medium mb-1">Automatic Credential Setup</p>
                  <p>
                    This will create test workflows in n8n and automatically configure the Header Auth
                    credential with your API key. Just open n8n, configure the target, and run!
                  </p>
                </div>
              </div>

              <!-- Workflow Types -->
              <p class="text-sm font-medium text-gray-700 dark:text-gray-300">
                The following test workflows will be created:
              </p>

              <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <!-- Broadcast -->
                <div class="flex flex-col items-center gap-2 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                  <span class="text-2xl">📢</span>
                  <span class="font-medium text-blue-700 dark:text-blue-300">Broadcast</span>
                  <span class="text-xs text-blue-600 dark:text-blue-400 text-center">
                    Send to all webhook-enabled channels
                  </span>
                </div>

                <!-- Channel -->
                <div class="flex flex-col items-center gap-2 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                  <span class="text-2xl">🎯</span>
                  <span class="font-medium text-green-700 dark:text-green-300">Channel</span>
                  <span class="text-xs text-green-600 dark:text-green-400 text-center">
                    Target a specific channel by slug
                  </span>
                </div>

                <!-- Group -->
                <div class="flex flex-col items-center gap-2 p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
                  <span class="text-2xl">👥</span>
                  <span class="font-medium text-purple-700 dark:text-purple-300">Group</span>
                  <span class="text-xs text-purple-600 dark:text-purple-400 text-center">
                    Target a channel group by slug
                  </span>
                </div>
              </div>

              <!-- Note -->
              <p class="text-xs text-gray-500 dark:text-gray-400">
                For channel/group workflows, you'll need to edit the JSON body in n8n to specify
                your target slug. Find slugs in the Channels or Groups tab.
              </p>
            </div>

            <!-- Footer -->
            <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 rounded-b-xl">
              <button
                @click="workflowCreationDialog.open = false"
                class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600"
              >
                Cancel
              </button>
              <button
                @click="createAllTestWorkflows"
                :disabled="creatingWorkflow"
                class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <SparklesIcon v-if="!creatingWorkflow" class="h-4 w-4" />
                <svg v-else class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {{ creatingWorkflow ? 'Creating...' : 'Create All Workflows' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- NTFY Channel Created Success Dialog -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="ntfySuccessDialog.open"
          class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          @click.self="ntfySuccessDialog.open = false"
        >
          <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-lg w-full p-6">
            <!-- Header -->
            <div class="flex items-center gap-3 mb-4">
              <div class="p-2 rounded-lg bg-green-100 dark:bg-green-500/20">
                <CheckCircleIcon class="h-6 w-6 text-green-500" />
              </div>
              <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
                NTFY Channel Created!
              </h3>
            </div>

            <!-- Content -->
            <div class="space-y-4">
              <p class="text-sm text-gray-600 dark:text-gray-300">
                Your local NTFY channel has been created successfully. Here's how to use it:
              </p>

              <!-- Topic Info -->
              <div class="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
                <div class="flex items-center gap-2 mb-2">
                  <MegaphoneIcon class="h-5 w-5 text-amber-600 dark:text-amber-400" />
                  <span class="font-semibold text-amber-800 dark:text-amber-300">Subscribe to Topic</span>
                </div>
                <p class="text-sm text-amber-700 dark:text-amber-400 mb-2">
                  In your NTFY app or browser, subscribe to:
                </p>
                <code class="block px-3 py-2 bg-amber-100 dark:bg-amber-900/40 rounded text-amber-900 dark:text-amber-200 font-mono text-sm">
                  {{ ntfySuccessDialog.channel?.config?.topic }}
                </code>
              </div>

              <!-- Slug Info -->
              <div class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                <div class="flex items-center gap-2 mb-2">
                  <LinkIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  <span class="font-semibold text-blue-800 dark:text-blue-300">Send via n8n Webhook</span>
                </div>
                <p class="text-sm text-blue-700 dark:text-blue-400 mb-2">
                  To send notifications from n8n workflows, use this channel slug:
                </p>
                <code class="block px-3 py-2 bg-blue-100 dark:bg-blue-900/40 rounded text-blue-900 dark:text-blue-200 font-mono text-sm">
                  channel:{{ ntfySuccessDialog.channel?.slug }}
                </code>
              </div>

              <!-- Note -->
              <p class="text-xs text-gray-500 dark:text-gray-400">
                <strong>Note:</strong> The topic is what you subscribe to in the NTFY app. The channel slug is used in n8n webhook payloads to route messages to this channel.
              </p>
            </div>

            <!-- Footer -->
            <div class="mt-6 flex justify-end">
              <button
                @click="ntfySuccessDialog.open = false"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
              >
                Got it!
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

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
  max-height: 800px;
}

/* Notification loading animation */
.notification-bell {
  animation: bellSwing 1s ease-in-out infinite;
  transform-origin: top center;
}

@keyframes bellSwing {
  0%, 100% {
    transform: rotate(0deg);
  }
  25% {
    transform: rotate(15deg);
  }
  75% {
    transform: rotate(-15deg);
  }
}

.notification-wave {
  animation: waveExpand 1.5s ease-out infinite;
}

.notification-wave.animation-delay-1 {
  animation-delay: 0.5s;
}

@keyframes waveExpand {
  0% {
    transform: scale(1);
    opacity: 1;
  }
  100% {
    transform: scale(2.5);
    opacity: 0;
  }
}
</style>
