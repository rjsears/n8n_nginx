<script setup>
import { ref, onMounted, computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useNotificationStore } from '@/stores/notifications'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
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
} from '@heroicons/vue/24/outline'

const themeStore = useThemeStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const channels = ref([])
const history = ref([])
const deleteDialog = ref({ open: false, channel: null, loading: false })
const testingChannel = ref(null)

// Channel type icons
const channelIcons = {
  apprise: ChatBubbleLeftIcon,
  ntfy: BellIcon,
  email: EnvelopeIcon,
  webhook: GlobeAltIcon,
}

// Stats
const stats = computed(() => ({
  total: channels.value.length,
  active: channels.value.filter((c) => c.enabled).length,
  sent: history.value.filter((h) => h.status === 'sent').length,
  failed: history.value.filter((h) => h.status === 'failed').length,
}))

async function loadData() {
  loading.value = true
  try {
    const [channelsRes, historyRes] = await Promise.all([
      api.notifications.getChannels(),
      api.notifications.getHistory(),
    ])
    channels.value = channelsRes.data
    history.value = historyRes.data
  } catch (error) {
    notificationStore.error('Failed to load notification data')
  } finally {
    loading.value = false
  }
}

async function testChannel(channel) {
  testingChannel.value = channel.id
  try {
    await api.notifications.testChannel(channel.id)
    notificationStore.success('Test notification sent!')
  } catch (error) {
    notificationStore.error('Test failed: ' + (error.response?.data?.detail || 'Unknown error'))
  } finally {
    testingChannel.value = null
  }
}

async function toggleChannel(channel) {
  try {
    await api.notifications.updateChannel(channel.id, { enabled: !channel.enabled })
    channel.enabled = !channel.enabled
    notificationStore.success(`Channel ${channel.enabled ? 'enabled' : 'disabled'}`)
  } catch (error) {
    notificationStore.error('Failed to update channel')
  }
}

function openDeleteDialog(channel) {
  deleteDialog.value = { open: true, channel, loading: false }
}

async function confirmDelete() {
  if (!deleteDialog.value.channel) return

  deleteDialog.value.loading = true
  try {
    await api.notifications.deleteChannel(deleteDialog.value.channel.id)
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

        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-red-100 dark:bg-red-500/20">
                <XCircleIcon class="h-5 w-5 text-red-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Failed</p>
                <p class="text-xl font-bold text-primary">{{ stats.failed }}</p>
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
          @action="() => {}"
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
                  :is="channelIcons[channel.type] || BellIcon"
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
                </div>
                <p class="text-sm text-secondary mt-0.5 capitalize">{{ channel.type }}</p>
                <p class="text-xs text-muted mt-0.5">
                  Events: {{ channel.events?.join(', ') || 'All' }}
                </p>
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
              <button class="btn-secondary p-2" title="Edit">
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
                  {{ item.channel_name }}
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
  </div>
</template>
