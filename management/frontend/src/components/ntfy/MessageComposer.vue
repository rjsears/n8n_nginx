<template>
  <div class="message-composer">
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Compose Message</h3>

    <form @submit.prevent="sendMessage" class="space-y-6">
      <!-- Topic Selection -->
      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Topic <span class="text-red-500">*</span>
        </label>
        <div class="flex gap-2">
          <select
            v-model="form.topic"
            class="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select a topic...</option>
            <option v-for="topic in topics" :key="topic.id" :value="topic.name">
              {{ topic.name }}
            </option>
          </select>
          <input
            v-model="customTopic"
            type="text"
            placeholder="Or enter custom topic"
            class="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            @input="form.topic = customTopic"
          />
        </div>
      </div>

      <!-- Title -->
      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Title
        </label>
        <input
          v-model="form.title"
          type="text"
          placeholder="Notification title (optional)"
          class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <!-- Message -->
      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Message <span class="text-red-500">*</span>
        </label>
        <textarea
          v-model="form.message"
          rows="4"
          placeholder="Your notification message..."
          class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          required
        ></textarea>
        <div class="flex items-center mt-1">
          <input
            id="markdown"
            v-model="form.markdown"
            type="checkbox"
            class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <label for="markdown" class="ml-2 text-sm text-gray-600 dark:text-gray-400">
            Enable Markdown formatting
          </label>
        </div>
      </div>

      <!-- Priority -->
      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Priority
        </label>
        <div class="flex gap-2">
          <button
            v-for="p in priorities"
            :key="p.value"
            type="button"
            @click="form.priority = p.value"
            :class="[
              'flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors',
              form.priority === p.value
                ? p.activeClass
                : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
            ]"
          >
            {{ p.label }}
          </button>
        </div>
      </div>

      <!-- Tags/Emojis -->
      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Tags & Emojis
        </label>
        <div class="flex flex-wrap gap-2 mb-2">
          <span
            v-for="(tag, index) in form.tags"
            :key="index"
            class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-sm bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300"
          >
            {{ tag }}
            <button type="button" @click="removeTag(index)" class="hover:text-red-500">
              <XMarkIcon class="w-4 h-4" />
            </button>
          </span>
        </div>
        <div class="flex gap-2">
          <input
            v-model="newTag"
            type="text"
            placeholder="Add tag or emoji shortcode..."
            class="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            @keydown.enter.prevent="addTag"
          />
          <button
            type="button"
            @click="showEmojiPicker = !showEmojiPicker"
            class="px-3 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            <FaceSmileIcon class="w-5 h-5 text-gray-600 dark:text-gray-400" />
          </button>
        </div>

        <!-- Emoji Picker -->
        <div v-if="showEmojiPicker" class="mt-2 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600">
          <div class="flex flex-wrap gap-2 mb-3">
            <button
              v-for="cat in Object.keys(emojiCategories)"
              :key="cat"
              type="button"
              @click="selectedEmojiCategory = cat"
              :class="[
                'px-2 py-1 text-xs rounded',
                selectedEmojiCategory === cat
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300'
              ]"
            >
              {{ cat }}
            </button>
          </div>
          <div class="flex flex-wrap gap-1 max-h-32 overflow-y-auto">
            <button
              v-for="emoji in currentEmojis"
              :key="emoji.shortcode"
              type="button"
              @click="addEmojiTag(emoji.shortcode)"
              class="px-2 py-1 text-sm bg-white dark:bg-gray-800 rounded hover:bg-gray-100 dark:hover:bg-gray-600"
              :title="emoji.shortcode"
            >
              {{ emoji.emoji || emoji.shortcode }}
            </button>
          </div>
        </div>
      </div>

      <!-- Click URL -->
      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Click URL
        </label>
        <input
          v-model="form.click"
          type="url"
          placeholder="https://example.com - URL to open when notification is clicked"
          class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <!-- Action Buttons -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
            Action Buttons
          </label>
          <button
            type="button"
            @click="addAction"
            class="text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            + Add Action
          </button>
        </div>
        <div v-for="(action, index) in form.actions" :key="index" class="flex gap-2 mb-2">
          <select
            v-model="action.action"
            class="w-24 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-2 py-2 text-sm"
          >
            <option value="view">View</option>
            <option value="http">HTTP</option>
            <option value="broadcast">Broadcast</option>
          </select>
          <input
            v-model="action.label"
            type="text"
            placeholder="Button label"
            class="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm"
          />
          <input
            v-model="action.url"
            type="text"
            placeholder="URL"
            class="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm"
          />
          <button
            type="button"
            @click="removeAction(index)"
            class="px-2 text-red-500 hover:text-red-700"
          >
            <TrashIcon class="w-5 h-5" />
          </button>
        </div>
      </div>

      <!-- Advanced Options -->
      <div class="border-t border-gray-200 dark:border-gray-700 pt-4">
        <button
          type="button"
          @click="showAdvanced = !showAdvanced"
          class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
        >
          <ChevronDownIcon :class="['w-4 h-4 transition-transform', showAdvanced ? 'rotate-180' : '']" />
          Advanced Options
        </button>

        <div v-if="showAdvanced" class="mt-4 space-y-4">
          <!-- Attachment URL -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Attachment URL
            </label>
            <input
              v-model="form.attach"
              type="url"
              placeholder="https://example.com/file.pdf"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <!-- Icon URL -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Icon URL
            </label>
            <input
              v-model="form.icon"
              type="url"
              placeholder="https://example.com/icon.png"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <!-- Delay/Schedule -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Delay/Schedule
            </label>
            <input
              v-model="form.delay"
              type="text"
              placeholder="e.g., 30m, 2h, tomorrow 10am"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            />
            <p class="mt-1 text-xs text-gray-500">Supports: 30m, 2h, 1d, "tomorrow 10am", Unix timestamp</p>
          </div>

          <!-- Email Forward -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Email Forward
            </label>
            <input
              v-model="form.email"
              type="email"
              placeholder="user@example.com"
              class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      <!-- Submit Buttons -->
      <div class="flex gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
        <button
          type="submit"
          :disabled="sending || !form.topic || !form.message"
          class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          <PaperAirplaneIcon class="w-5 h-5" />
          {{ sending ? 'Sending...' : 'Send Message' }}
        </button>
        <button
          type="button"
          @click="saveMessage"
          :disabled="!form.topic || !form.message"
          class="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <BookmarkIcon class="w-5 h-5" />
          Save
        </button>
        <button
          type="button"
          @click="resetForm"
          class="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
        >
          Reset
        </button>
      </div>

      <!-- Result Message -->
      <div v-if="resultMessage" :class="[
        'p-3 rounded-lg text-sm',
        resultSuccess ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300' : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'
      ]">
        {{ resultMessage }}
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import {
  PaperAirplaneIcon,
  BookmarkIcon,
  XMarkIcon,
  TrashIcon,
  ChevronDownIcon,
  FaceSmileIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps({
  topics: { type: Array, default: () => [] },
  emojiCategories: { type: Object, default: () => ({}) },
  onSend: { type: Function, required: true },
  onSave: { type: Function, required: true },
})

// Form state
const form = ref({
  topic: '',
  title: '',
  message: '',
  priority: 3,
  tags: [],
  click: '',
  attach: '',
  icon: '',
  actions: [],
  delay: '',
  email: '',
  markdown: false,
})

const customTopic = ref('')
const newTag = ref('')
const showEmojiPicker = ref(false)
const selectedEmojiCategory = ref('')
const showAdvanced = ref(false)
const sending = ref(false)
const resultMessage = ref('')
const resultSuccess = ref(false)

// Priority options
const priorities = [
  { value: 1, label: 'Min', activeClass: 'bg-gray-500 text-white' },
  { value: 2, label: 'Low', activeClass: 'bg-blue-500 text-white' },
  { value: 3, label: 'Default', activeClass: 'bg-green-500 text-white' },
  { value: 4, label: 'High', activeClass: 'bg-orange-500 text-white' },
  { value: 5, label: 'Urgent', activeClass: 'bg-red-500 text-white' },
]

// Current emoji list
const currentEmojis = computed(() => {
  if (!selectedEmojiCategory.value || !props.emojiCategories[selectedEmojiCategory.value]) {
    return []
  }
  return props.emojiCategories[selectedEmojiCategory.value]
})

// Initialize selected category
if (Object.keys(props.emojiCategories).length > 0) {
  selectedEmojiCategory.value = Object.keys(props.emojiCategories)[0]
}

// Tag management
function addTag() {
  if (newTag.value.trim() && !form.value.tags.includes(newTag.value.trim())) {
    form.value.tags.push(newTag.value.trim())
    newTag.value = ''
  }
}

function removeTag(index) {
  form.value.tags.splice(index, 1)
}

function addEmojiTag(shortcode) {
  if (!form.value.tags.includes(shortcode)) {
    form.value.tags.push(shortcode)
  }
}

// Action management
function addAction() {
  form.value.actions.push({
    action: 'view',
    label: '',
    url: '',
  })
}

function removeAction(index) {
  form.value.actions.splice(index, 1)
}

// Send message
async function sendMessage() {
  sending.value = true
  resultMessage.value = ''

  try {
    const payload = {
      topic: form.value.topic,
      message: form.value.message,
      priority: form.value.priority,
      markdown: form.value.markdown,
    }

    if (form.value.title) payload.title = form.value.title
    if (form.value.tags.length) payload.tags = form.value.tags
    if (form.value.click) payload.click = form.value.click
    if (form.value.attach) payload.attach = form.value.attach
    if (form.value.icon) payload.icon = form.value.icon
    if (form.value.delay) payload.delay = form.value.delay
    if (form.value.email) payload.email = form.value.email
    if (form.value.actions.length) {
      payload.actions = form.value.actions.filter(a => a.label && a.url)
    }

    const result = await props.onSend(payload)

    if (result?.success) {
      resultSuccess.value = true
      resultMessage.value = 'Message sent successfully!'
      resetForm()
    } else {
      resultSuccess.value = false
      resultMessage.value = result?.error || 'Failed to send message'
    }
  } catch (error) {
    resultSuccess.value = false
    resultMessage.value = error.message || 'Failed to send message'
  } finally {
    sending.value = false
  }
}

// Save message
async function saveMessage() {
  const name = prompt('Enter a name for this saved message:')
  if (!name) return

  const payload = {
    name,
    topic: form.value.topic,
    message: form.value.message,
    priority: form.value.priority,
    use_markdown: form.value.markdown,
  }

  if (form.value.title) payload.title = form.value.title
  if (form.value.tags.length) payload.tags = form.value.tags
  if (form.value.click) payload.click_url = form.value.click
  if (form.value.attach) payload.attach_url = form.value.attach
  if (form.value.icon) payload.icon_url = form.value.icon
  if (form.value.delay) payload.delay = form.value.delay
  if (form.value.email) payload.email = form.value.email
  if (form.value.actions.length) {
    payload.actions = form.value.actions.filter(a => a.label && a.url)
  }

  const result = await props.onSave(payload)

  if (result?.success) {
    resultSuccess.value = true
    resultMessage.value = 'Message saved successfully!'
  } else {
    resultSuccess.value = false
    resultMessage.value = result?.error || 'Failed to save message'
  }
}

// Reset form
function resetForm() {
  form.value = {
    topic: '',
    title: '',
    message: '',
    priority: 3,
    tags: [],
    click: '',
    attach: '',
    icon: '',
    actions: [],
    delay: '',
    email: '',
    markdown: false,
  }
  customTopic.value = ''
  newTag.value = ''
  showAdvanced.value = false
}
</script>
