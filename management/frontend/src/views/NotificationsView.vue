<script setup>
import { ref, onMounted, computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useNotificationStore } from '@/stores/notifications'
import { notificationsApi } from '@/services/api'
import Card from '@/components/common/Card.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import NotificationServiceDialog from '@/components/notifications/NotificationServiceDialog.vue'
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
} from '@heroicons/vue/24/outline'

const themeStore = useThemeStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const channels = ref([])
const history = ref([])
const webhookInfo = ref(null)
const showApiKey = ref(false)
const webhookExpanded = ref(false)
const deleteDialog = ref({ open: false, channel: null, loading: false })
const serviceDialog = ref({ open: false, service: null })
const testingChannel = ref(null)

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
  const historyList = Array.isArray(history.value) ? history.value : []
  return {
    total: channelsList.length,
    active: channelsList.filter((c) => c.enabled).length,
    webhookEnabled: channelsList.filter((c) => c.webhook_enabled).length,
    sent: historyList.filter((h) => h.status === 'sent').length,
    failed: historyList.filter((h) => h.status === 'failed').length,
  }
})

async function loadData() {
  loading.value = true
  try {
    const [servicesRes, historyRes, webhookRes] = await Promise.all([
      notificationsApi.getServices(),
      notificationsApi.getHistory(),
      notificationsApi.getWebhookInfo(),
    ])
    // Ensure we always have arrays
    channels.value = Array.isArray(servicesRes.data) ? servicesRes.data : []
    history.value = Array.isArray(historyRes.data) ? historyRes.data : []
    webhookInfo.value = webhookRes.data
  } catch (error) {
    console.error('Failed to load notification data:', error)
    notificationStore.error('Failed to load notification data')
    // Reset to empty arrays on error
    channels.value = []
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
        <p class="text-secondary mt-1">Configure notification channels and view history</p>
      </div>
      <button
        v-if="!loading && channels.length > 0"
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
            class="flex items-center justify-between p-4 rounded-lg bg-surface-hover border border-[var(--color-border)]"
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

      <!-- Notification History -->
      <Card title="Recent Notifications" subtitle="Last 20 notifications" :neon="true">
        <EmptyState
          v-if="history.length === 0"
          :icon="BellIcon"
          title="No notifications sent"
          description="Notifications will appear here once they are triggered."
        />

        <div v-else class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-[var(--color-border)]">
                <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Event</th>
                <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Channel</th>
                <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Status</th>
                <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Time</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in history.slice(0, 20)"
                :key="item.id"
                class="border-b border-[var(--color-border)] last:border-0"
              >
                <td class="py-3 px-4">
                  <span class="font-medium text-primary">{{ item.event_type }}</span>
                </td>
                <td class="py-3 px-4 text-sm text-secondary">
                  {{ item.service_name }}
                </td>
                <td class="py-3 px-4">
                  <StatusBadge :status="item.status" size="sm" />
                </td>
                <td class="py-3 px-4 text-sm text-secondary">
                  {{ new Date(item.sent_at).toLocaleString() }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
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
              </div>
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
  "priority": "normal"
}</pre>
              </div>
            </div>
          </div>
        </Transition>
      </Card>
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

    <!-- Add/Edit Service Dialog -->
    <NotificationServiceDialog
      :open="serviceDialog.open"
      :service="serviceDialog.service"
      @save="handleServiceSave"
      @cancel="serviceDialog.open = false"
      @update:open="(val) => serviceDialog.open = val"
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
  max-height: 500px;
}
</style>
