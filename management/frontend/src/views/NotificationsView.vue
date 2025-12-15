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
} from '@heroicons/vue/24/outline'

const route = useRoute()
const themeStore = useThemeStore()
const notificationStore = useNotificationStore()

// Main tab navigation (Channels vs Groups vs NTFY Push)
const mainTab = ref('channels')

// Main tabs configuration
const mainTabs = [
  { id: 'channels', name: 'Channels', icon: BellIcon },
  { id: 'groups', name: 'Groups', icon: HashtagIcon },
  { id: 'ntfy', name: 'NTFY Push', icon: MegaphoneIcon },
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
const channels = ref([])
const groups = ref([])
const history = ref([])
const webhookInfo = ref(null)
const showApiKey = ref(false)
const webhookExpanded = ref(false)
const historyExpanded = ref(false)
const expandedHistoryItems = ref(new Set())
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
const testingChannel = ref(null)
const n8nStatus = ref({ checking: false, configured: false, connected: false, error: null })
const creatingWorkflow = ref(false)

// Channel type icons
const channelIcons = {
  apprise: ChatBubbleLeftIcon,
  ntfy: BellIcon,
  email: EnvelopeIcon,
  webhook: GlobeAltIcon,
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
    notificationStore.success('API key regenerated. Remember to update your n8n credentials!')
    regenerateDialog.value.open = false
    showApiKey.value = true
  } catch (error) {
    notificationStore.error('Failed to regenerate API key: ' + (error.response?.data?.detail || 'Unknown error'))
  } finally {
    regenerateDialog.value.loading = false
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

async function createTestWorkflow() {
  creatingWorkflow.value = true
  try {
    const response = await notificationsApi.createTestWorkflow()
    if (response.data.success) {
      const workflowId = response.data.workflow_id
      notificationStore.success(`Test workflow created! ID: ${workflowId}. Open n8n to configure the credential and run it.`)
    } else {
      notificationStore.error('Failed to create workflow: ' + (response.data.error || 'Unknown error'))
    }
  } catch (error) {
    notificationStore.error('Failed to create workflow: ' + (error.response?.data?.detail || 'Unknown error'))
  } finally {
    creatingWorkflow.value = false
  }
}

function getWebhookUrl() {
  const baseUrl = window.location.origin
  return `${baseUrl}/api/notifications/webhook`
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
      notificationStore.success('Channel created')
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
    notificationStore.error('Failed to save group: ' + (error.response?.data?.detail || 'Unknown error'))
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

onMounted(loadData)

// ==================== NTFY Section ====================

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
    await api.ntfy.createTopic(topic)
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
            themeStore.isNeon ? 'neon-text-cyan' : 'text-primary'
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
          themeStore.isNeon ? 'neon-btn-cyan' : ''
        ]"
      >
        <PlusIcon class="h-4 w-4" />
        Add Channel
      </button>
    </div>

    <!-- Main Tab Navigation -->
    <div class="border-b border-gray-200 dark:border-gray-700">
      <nav class="flex -mb-px space-x-4">
        <button
          v-for="tab in mainTabs"
          :key="tab.id"
          @click="mainTab = tab.id"
          :class="[
            'flex items-center px-4 py-3 text-sm font-medium border-b-2 transition-colors',
            mainTab === tab.id
              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
          ]"
        >
          <component :is="tab.icon" class="w-5 h-5 mr-2" />
          {{ tab.name }}
        </button>
      </nav>
    </div>

    <!-- Channels Tab Content -->
    <template v-if="mainTab === 'channels'">
      <LoadingSpinner v-if="loading" size="lg" text="Loading notifications..." class="py-12" />

      <template v-else>
      <!-- Stats Grid -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card :neon="true" :padding="false">
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

        <Card :neon="true" :padding="false">
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

        <Card :neon="true" :padding="false">
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

        <Card :neon="true" :padding="false">
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

      <!-- Notification Channels -->
      <Card title="Notification Channels" subtitle="Configure where alerts are sent" :neon="true">
        <EmptyState
          v-if="channels.length === 0"
          :icon="BellIcon"
          title="No channels configured"
          description="Add a notification channel to start receiving alerts."
          action-text="Add Channel"
          @action="openAddDialog"
        />

        <div v-else class="space-y-3">
          <div
            v-for="channel in channels"
            :key="channel.id"
            class="flex items-center justify-between p-4 rounded-lg bg-surface-hover border border-gray-300 dark:border-black"
          >
            <div class="flex items-center gap-4">
              <div
                :class="[
                  'p-3 rounded-lg',
                  channel.enabled
                    ? 'bg-blue-100 dark:bg-blue-500/20'
                    : 'bg-gray-100 dark:bg-gray-500/20'
                ]"
              >
                <component
                  :is="channelIcons[channel.service_type] || BellIcon"
                  :class="[
                    'h-6 w-6',
                    channel.enabled ? 'text-blue-500' : 'text-gray-500'
                  ]"
                />
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <p class="font-medium text-primary">{{ channel.name }}</p>
                  <StatusBadge :status="channel.enabled ? 'active' : 'inactive'" size="sm" />
                  <span
                    v-if="channel.webhook_enabled"
                    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-300"
                  >
                    <LinkIcon class="h-3 w-3" />
                    Webhook
                  </span>
                </div>
                <p class="text-sm text-secondary mt-0.5 capitalize">{{ channel.service_type }}</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <button
                @click="testChannel(channel)"
                :disabled="testingChannel === channel.id"
                class="btn-secondary p-2"
                title="Test"
              >
                <PaperAirplaneIcon
                  :class="['h-4 w-4', testingChannel === channel.id && 'animate-pulse']"
                />
              </button>
              <button @click="openEditDialog(channel)" class="btn-secondary p-2" title="Edit">
                <PencilSquareIcon class="h-4 w-4" />
              </button>
              <button
                @click="openDeleteDialog(channel)"
                class="btn-secondary p-2 text-red-500 hover:text-red-600"
                title="Delete"
              >
                <TrashIcon class="h-4 w-4" />
              </button>
              <label class="relative inline-flex items-center cursor-pointer ml-2">
                <input
                  type="checkbox"
                  :checked="channel.enabled"
                  @change="toggleChannel(channel)"
                  class="sr-only peer"
                />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"
                ></div>
              </label>
            </div>
          </div>
        </div>
      </Card>

      <!-- Notification History (Collapsible) -->
      <Card :neon="true" :padding="false">
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
          <div v-if="historyExpanded" class="px-4 pb-4 border-t border-gray-200 dark:border-gray-700">
            <EmptyState
              v-if="history.length === 0"
              :icon="BellIcon"
              title="No notifications sent"
              description="Notifications will appear here once they are triggered."
              class="pt-4"
            />

            <div v-else class="space-y-2 pt-2">
              <div
                v-for="item in history.slice(0, 20)"
                :key="item.id"
                class="border border-gray-300 dark:border-black rounded-lg overflow-hidden"
              >
                <!-- Collapsed Header Row -->
                <div
                  @click="toggleHistoryItem(item.id)"
                  class="flex items-center gap-3 p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                >
                  <component
                    :is="expandedHistoryItems.has(item.id) ? ChevronDownIcon : ChevronRightIcon"
                    class="h-4 w-4 text-secondary flex-shrink-0"
                  />
                  <div class="flex-1 min-w-0 flex items-center gap-4">
                    <div class="flex-1 min-w-0">
                      <p class="text-sm font-medium text-primary truncate">
                        {{ item.event_data?.title || item.event_type }}
                      </p>
                      <p class="text-xs text-secondary truncate">
                        {{ item.service_name }} • {{ new Date(item.sent_at).toLocaleString() }}
                      </p>
                    </div>
                    <StatusBadge :status="item.status" size="sm" class="flex-shrink-0" />
                  </div>
                </div>

                <!-- Expanded Details -->
                <Transition name="collapse">
                  <div
                    v-if="expandedHistoryItems.has(item.id)"
                    class="px-4 pb-4 pt-2 border-t border-gray-300 dark:border-black bg-gray-50 dark:bg-gray-800/50"
                  >
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <!-- Left Column -->
                      <div class="space-y-3">
                        <div>
                          <label class="text-xs font-medium text-secondary uppercase tracking-wide">Event Type</label>
                          <p class="text-sm text-primary font-mono mt-1">{{ item.event_type }}</p>
                        </div>
                        <div>
                          <label class="text-xs font-medium text-secondary uppercase tracking-wide">Channel</label>
                          <p class="text-sm text-primary mt-1">{{ item.service_name }}</p>
                        </div>
                        <div>
                          <label class="text-xs font-medium text-secondary uppercase tracking-wide">Status</label>
                          <div class="mt-1">
                            <StatusBadge :status="item.status" size="sm" />
                          </div>
                        </div>
                        <div>
                          <label class="text-xs font-medium text-secondary uppercase tracking-wide">Sent At</label>
                          <p class="text-sm text-primary mt-1">{{ new Date(item.sent_at).toLocaleString() }}</p>
                        </div>
                        <div v-if="item.error_message">
                          <label class="text-xs font-medium text-red-500 uppercase tracking-wide">Error</label>
                          <p class="text-sm text-red-600 dark:text-red-400 mt-1">{{ item.error_message }}</p>
                        </div>
                      </div>

                      <!-- Right Column - Message Content -->
                      <div class="space-y-3">
                        <div v-if="item.event_data?.title">
                          <label class="text-xs font-medium text-secondary uppercase tracking-wide">Title</label>
                          <p class="text-sm text-primary mt-1">{{ item.event_data.title }}</p>
                        </div>
                        <div v-if="item.event_data?.message">
                          <label class="text-xs font-medium text-secondary uppercase tracking-wide">Message</label>
                          <p class="text-sm text-primary mt-1 whitespace-pre-wrap break-words">{{ item.event_data.message }}</p>
                        </div>
                        <div v-if="item.event_data?.priority">
                          <label class="text-xs font-medium text-secondary uppercase tracking-wide">Priority</label>
                          <p class="text-sm text-primary mt-1 capitalize">{{ item.event_data.priority }}</p>
                        </div>
                        <div v-if="item.severity">
                          <label class="text-xs font-medium text-secondary uppercase tracking-wide">Severity</label>
                          <p class="text-sm text-primary mt-1 capitalize">{{ item.severity }}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </Transition>
              </div>
            </div>
          </div>
        </Transition>
      </Card>

      <!-- n8n Webhook Integration (Collapsible) -->
      <Card v-if="webhookInfo" :neon="true" :padding="false">
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
          <div v-if="webhookExpanded" class="px-4 pb-4 space-y-4 border-t border-gray-200 dark:border-gray-700">
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
                  class="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white font-mono text-sm"
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
                    class="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white font-mono text-sm"
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

            <!-- Create Test Workflow -->
            <div class="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-2">
                  <Cog6ToothIcon class="h-5 w-5 text-secondary" />
                  <h4 class="font-medium text-primary">Create Test Workflow</h4>
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
                Automatically create a test workflow in n8n to verify webhook notifications are working.
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

              <button
                @click.stop="createTestWorkflow"
                :disabled="creatingWorkflow || !webhookInfo.has_key"
                :class="[
                  'inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                  webhookInfo.has_key
                    ? 'bg-green-600 hover:bg-green-700 text-white disabled:opacity-50'
                    : 'bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400 cursor-not-allowed'
                ]"
              >
                <PlayIcon class="h-4 w-4" />
                {{ creatingWorkflow ? 'Creating...' : 'Create Test Workflow in n8n' }}
              </button>

              <p v-if="!webhookInfo.has_key" class="text-xs text-yellow-600 dark:text-yellow-400 mt-2">
                Generate an API key above first before creating the test workflow.
              </p>
              <p v-else class="text-xs text-secondary mt-2">
                This will create a "Management Console - Test Notifications" workflow in n8n.
                After creation, open n8n to configure the Header Auth credential and run it.
              </p>
            </div>
          </div>
        </Transition>
      </Card>
      </template>
    </template>

    <!-- Groups Tab Content -->
    <template v-else-if="mainTab === 'groups'">
      <LoadingSpinner v-if="loading" size="lg" text="Loading groups..." class="py-12" />

      <template v-else>
        <!-- Groups Stats -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card :neon="true" :padding="false">
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

          <Card :neon="true" :padding="false">
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

          <Card :neon="true" :padding="false">
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

        <!-- Groups List -->
        <Card title="Notification Groups" subtitle="Group channels together for targeted notifications" :neon="true">
          <template #actions>
            <button
              @click="openAddGroupDialog"
              :class="[
                'btn-primary flex items-center gap-2',
                themeStore.isNeon ? 'neon-btn-cyan' : ''
              ]"
            >
              <PlusIcon class="h-4 w-4" />
              Add Group
            </button>
          </template>

          <EmptyState
            v-if="groups.length === 0"
            :icon="HashtagIcon"
            title="No groups configured"
            description="Create groups to organize channels and target notifications."
            action-text="Add Group"
            @action="openAddGroupDialog"
          />

          <div v-else class="space-y-4">
            <div
              v-for="group in groups"
              :key="group.id"
              class="p-4 rounded-lg bg-surface-hover border border-gray-300 dark:border-black"
            >
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-3">
                  <div
                    :class="[
                      'p-2 rounded-lg',
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
                  <div>
                    <div class="flex items-center gap-2">
                      <p class="font-medium text-primary">{{ group.name }}</p>
                      <StatusBadge :status="group.enabled ? 'active' : 'inactive'" size="sm" />
                    </div>
                    <p class="text-xs text-secondary mt-0.5">
                      <span class="font-mono">group:{{ group.slug }}</span>
                      <span class="mx-2">•</span>
                      {{ group.channel_count }} channel{{ group.channel_count !== 1 ? 's' : '' }}
                    </p>
                  </div>
                </div>
                <div class="flex items-center gap-2">
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
                  <label class="relative inline-flex items-center cursor-pointer ml-2">
                    <input
                      type="checkbox"
                      :checked="group.enabled"
                      @change="toggleGroup(group)"
                      class="sr-only peer"
                    />
                    <div
                      class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-indigo-500"
                    ></div>
                  </label>
                </div>
              </div>

              <!-- Group description if present -->
              <p v-if="group.description" class="text-sm text-secondary mb-3">{{ group.description }}</p>

              <!-- Channels in group -->
              <div v-if="group.channels && group.channels.length > 0" class="flex flex-wrap gap-2">
                <div
                  v-for="channel in group.channels"
                  :key="channel.id"
                  class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300"
                >
                  <component
                    :is="channelIcons[channel.service_type] || BellIcon"
                    class="h-3.5 w-3.5"
                  />
                  {{ channel.name }}
                  <span
                    v-if="channel.webhook_enabled"
                    class="w-1.5 h-1.5 rounded-full bg-green-500"
                    title="Webhook enabled"
                  ></span>
                </div>
              </div>
            </div>
          </div>
        </Card>

        <!-- How to Use Groups -->
        <Card title="How to Target Groups" subtitle="Use groups in your n8n webhooks" :neon="true">
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
      <LoadingSpinner v-if="ntfyLoading" size="lg" text="Loading NTFY..." class="py-12" />

      <template v-else>
        <!-- NTFY Stats Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card :neon="true" :padding="false">
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

          <Card :neon="true" :padding="false">
            <div class="p-4">
              <p class="text-sm text-secondary">Topics</p>
              <p class="text-xl font-bold text-primary">{{ ntfyStatus.topics_count || 0 }}</p>
            </div>
          </Card>

          <Card :neon="true" :padding="false">
            <div class="p-4">
              <p class="text-sm text-secondary">Templates</p>
              <p class="text-xl font-bold text-primary">{{ ntfyStatus.templates_count || 0 }}</p>
            </div>
          </Card>

          <Card :neon="true" :padding="false">
            <div class="p-4">
              <p class="text-sm text-secondary">Messages Today</p>
              <p class="text-xl font-bold text-primary">{{ ntfyStatus.messages_today || 0 }}</p>
            </div>
          </Card>
        </div>

        <!-- NTFY Sub-Tabs -->
        <Card :neon="true" :padding="false">
          <div class="border-b border-gray-200 dark:border-gray-700">
            <nav class="flex -mb-px overflow-x-auto">
              <button
                v-for="tab in ntfyTabs"
                :key="tab.id"
                @click="ntfyActiveTab = tab.id"
                :class="[
                  'px-6 py-4 text-sm font-medium border-b-2 whitespace-nowrap transition-colors',
                  ntfyActiveTab === tab.id
                    ? 'border-orange-500 text-orange-600 dark:text-orange-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
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
                @create="handleNtfyCreateTopic"
                @update="handleNtfyUpdateTopic"
                @delete="handleNtfyDeleteTopic"
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
</style>
