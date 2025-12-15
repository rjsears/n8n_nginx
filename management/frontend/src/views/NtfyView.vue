<template>
  <div class="ntfy-view">
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">NTFY Push Notifications</h1>
        <p class="text-gray-600 dark:text-gray-400 mt-1">Send push notifications to phones and desktops</p>
      </div>
      <div class="flex items-center gap-3">
        <!-- Health Status Badge -->
        <div
          :class="[
            'px-3 py-1.5 rounded-full text-sm font-medium flex items-center gap-2',
            health.healthy
              ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
              : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
          ]"
        >
          <span :class="['w-2 h-2 rounded-full', health.healthy ? 'bg-green-500' : 'bg-red-500']"></span>
          {{ health.healthy ? 'Connected' : 'Disconnected' }}
        </div>
      </div>
    </div>

    <!-- Stats Cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="text-sm text-gray-500 dark:text-gray-400">Topics</div>
        <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ status.topics_count || 0 }}</div>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="text-sm text-gray-500 dark:text-gray-400">Templates</div>
        <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ status.templates_count || 0 }}</div>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="text-sm text-gray-500 dark:text-gray-400">Messages Today</div>
        <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ status.messages_today || 0 }}</div>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="text-sm text-gray-500 dark:text-gray-400">Last Message</div>
        <div class="text-lg font-medium text-gray-900 dark:text-white">
          {{ status.last_message_at ? formatTime(status.last_message_at) : 'Never' }}
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
      <div class="border-b border-gray-200 dark:border-gray-700">
        <nav class="flex -mb-px overflow-x-auto">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            @click="activeTab = tab.id"
            :class="[
              'px-6 py-4 text-sm font-medium border-b-2 whitespace-nowrap transition-colors',
              activeTab === tab.id
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
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
        <div v-if="activeTab === 'composer'" class="space-y-6">
          <MessageComposer
            :topics="topics"
            :emoji-categories="emojiCategories"
            @send="handleSendMessage"
            @save="handleSaveMessage"
          />
        </div>

        <!-- Templates Tab -->
        <div v-else-if="activeTab === 'templates'" class="space-y-6">
          <TemplateBuilder
            :templates="templates"
            @create="handleCreateTemplate"
            @update="handleUpdateTemplate"
            @delete="handleDeleteTemplate"
            @preview="handlePreviewTemplate"
          />
        </div>

        <!-- Topics Tab -->
        <div v-else-if="activeTab === 'topics'" class="space-y-6">
          <TopicsManager
            :topics="topics"
            @create="handleCreateTopic"
            @update="handleUpdateTopic"
            @delete="handleDeleteTopic"
          />
        </div>

        <!-- Saved Messages Tab -->
        <div v-else-if="activeTab === 'saved'" class="space-y-6">
          <SavedMessages
            :messages="savedMessages"
            @send="handleSendSavedMessage"
            @delete="handleDeleteSavedMessage"
          />
        </div>

        <!-- History Tab -->
        <div v-else-if="activeTab === 'history'" class="space-y-6">
          <MessageHistory :history="history" @load-more="loadMoreHistory" />
        </div>

        <!-- Settings Tab -->
        <div v-else-if="activeTab === 'settings'" class="space-y-6">
          <ServerSettings :config="serverConfig" @update="handleUpdateConfig" />
        </div>

        <!-- Integration Hub Tab -->
        <div v-else-if="activeTab === 'integrations'" class="space-y-6">
          <IntegrationHub :examples="integrationExamples" :topics="topics" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '@/services/api'
import {
  PaperAirplaneIcon,
  DocumentTextIcon,
  HashtagIcon,
  BookmarkIcon,
  ClockIcon,
  Cog6ToothIcon,
  CodeBracketIcon,
} from '@heroicons/vue/24/outline'

// Import sub-components
import MessageComposer from '@/components/ntfy/MessageComposer.vue'
import TemplateBuilder from '@/components/ntfy/TemplateBuilder.vue'
import TopicsManager from '@/components/ntfy/TopicsManager.vue'
import SavedMessages from '@/components/ntfy/SavedMessages.vue'
import MessageHistory from '@/components/ntfy/MessageHistory.vue'
import ServerSettings from '@/components/ntfy/ServerSettings.vue'
import IntegrationHub from '@/components/ntfy/IntegrationHub.vue'

// State
const loading = ref(true)
const health = ref({ healthy: false, status: 'unknown' })
const status = ref({})
const activeTab = ref('composer')

// Data
const topics = ref([])
const templates = ref([])
const savedMessages = ref([])
const history = ref([])
const serverConfig = ref({})
const emojiCategories = ref({})
const integrationExamples = ref([])

// Tabs configuration
const tabs = [
  { id: 'composer', name: 'Compose', icon: PaperAirplaneIcon },
  { id: 'templates', name: 'Templates', icon: DocumentTextIcon },
  { id: 'topics', name: 'Topics', icon: HashtagIcon },
  { id: 'saved', name: 'Saved', icon: BookmarkIcon },
  { id: 'history', name: 'History', icon: ClockIcon },
  { id: 'settings', name: 'Settings', icon: Cog6ToothIcon },
  { id: 'integrations', name: 'Integrations', icon: CodeBracketIcon },
]

// Formatters
function formatTime(dateStr) {
  if (!dateStr) return 'Never'
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date

  if (diff < 60000) return 'Just now'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
  return date.toLocaleDateString()
}

// Load data
async function loadData() {
  loading.value = true
  try {
    // Load health and status in parallel
    const [healthRes, statusRes] = await Promise.all([
      api.ntfy.health(),
      api.ntfy.status(),
    ])
    health.value = healthRes.data
    status.value = statusRes.data

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

    topics.value = topicsRes.data || []
    templates.value = templatesRes.data || []
    savedMessages.value = savedRes.data || []
    history.value = historyRes.data || []
    serverConfig.value = configRes.data || {}
    emojiCategories.value = emojisRes.data || {}
    integrationExamples.value = examplesRes.data || []
  } catch (error) {
    console.error('Failed to load NTFY data:', error)
  } finally {
    loading.value = false
  }
}

// Message handlers
async function handleSendMessage(message) {
  try {
    const res = await api.ntfy.send(message)
    if (res.data.success) {
      // Refresh history
      const historyRes = await api.ntfy.getHistory({ limit: 50 })
      history.value = historyRes.data || []
      // Refresh status
      const statusRes = await api.ntfy.status()
      status.value = statusRes.data
      return { success: true }
    }
    return { success: false, error: res.data.error }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handleSaveMessage(message) {
  try {
    await api.ntfy.createSavedMessage(message)
    const savedRes = await api.ntfy.getSavedMessages()
    savedMessages.value = savedRes.data || []
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

// Template handlers
async function handleCreateTemplate(template) {
  try {
    await api.ntfy.createTemplate(template)
    const res = await api.ntfy.getTemplates()
    templates.value = res.data || []
    // Refresh status
    const statusRes = await api.ntfy.status()
    status.value = statusRes.data
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handleUpdateTemplate(id, template) {
  try {
    await api.ntfy.updateTemplate(id, template)
    const res = await api.ntfy.getTemplates()
    templates.value = res.data || []
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handleDeleteTemplate(id) {
  try {
    await api.ntfy.deleteTemplate(id)
    const res = await api.ntfy.getTemplates()
    templates.value = res.data || []
    // Refresh status
    const statusRes = await api.ntfy.status()
    status.value = statusRes.data
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handlePreviewTemplate(data) {
  try {
    const res = await api.ntfy.previewTemplate(data)
    return res.data
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

// Topic handlers
async function handleCreateTopic(topic) {
  try {
    await api.ntfy.createTopic(topic)
    const res = await api.ntfy.getTopics()
    topics.value = res.data || []
    // Refresh status
    const statusRes = await api.ntfy.status()
    status.value = statusRes.data
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handleUpdateTopic(id, topic) {
  try {
    await api.ntfy.updateTopic(id, topic)
    const res = await api.ntfy.getTopics()
    topics.value = res.data || []
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handleDeleteTopic(id) {
  try {
    await api.ntfy.deleteTopic(id)
    const res = await api.ntfy.getTopics()
    topics.value = res.data || []
    // Refresh status
    const statusRes = await api.ntfy.status()
    status.value = statusRes.data
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

// Saved message handlers
async function handleSendSavedMessage(id) {
  try {
    const res = await api.ntfy.sendSavedMessage(id)
    if (res.data.success) {
      // Refresh history
      const historyRes = await api.ntfy.getHistory({ limit: 50 })
      history.value = historyRes.data || []
      // Refresh status
      const statusRes = await api.ntfy.status()
      status.value = statusRes.data
      return { success: true }
    }
    return { success: false, error: res.data.error }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function handleDeleteSavedMessage(id) {
  try {
    await api.ntfy.deleteSavedMessage(id)
    const res = await api.ntfy.getSavedMessages()
    savedMessages.value = res.data || []
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

// History handlers
async function loadMoreHistory() {
  try {
    const res = await api.ntfy.getHistory({ limit: 50, offset: history.value.length })
    history.value = [...history.value, ...(res.data || [])]
  } catch (error) {
    console.error('Failed to load more history:', error)
  }
}

// Config handler
async function handleUpdateConfig(config) {
  try {
    await api.ntfy.updateConfig(config)
    const res = await api.ntfy.getConfig()
    serverConfig.value = res.data || {}
    return { success: true }
  } catch (error) {
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

// Initialize
onMounted(() => {
  loadData()
})
</script>

<style scoped>
.ntfy-view {
  @apply max-w-7xl mx-auto;
}
</style>
