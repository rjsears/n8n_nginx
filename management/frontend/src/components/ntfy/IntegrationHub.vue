<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/ntfy/IntegrationHub.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<template>
  <div class="integration-hub">
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Integration Examples</h3>

    <p class="text-gray-600 dark:text-gray-400 mb-6">
      Use these examples to integrate NTFY notifications into your workflows, scripts, and applications.
    </p>

    <!-- Category Tabs -->
    <div class="flex flex-wrap gap-2 mb-6">
      <button
        v-for="cat in categories"
        :key="cat"
        @click="selectedCategory = cat"
        :class="[
          'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
          selectedCategory === cat
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
        ]"
      >
        {{ cat }}
      </button>
    </div>

    <!-- Webhook URL Generator -->
    <div class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 mb-6 border border-blue-200 dark:border-blue-800">
      <h4 class="font-medium text-blue-900 dark:text-blue-100 mb-3">Generate Webhook URL</h4>
      <div class="flex gap-2">
        <select
          v-model="selectedTopic"
          class="flex-1 rounded-lg border border-blue-300 dark:border-blue-700 bg-white dark:bg-gray-800 px-3 py-2"
        >
          <option value="">Select a topic...</option>
          <option v-for="topic in topics" :key="topic.id" :value="topic.name">
            {{ topic.name }}
          </option>
        </select>
        <button
          @click="generateWebhookUrl"
          :disabled="!selectedTopic"
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          Generate
        </button>
      </div>

      <div v-if="webhookUrl" class="mt-4 space-y-3">
        <div>
          <label class="text-sm font-medium text-blue-900 dark:text-blue-100">Webhook URL:</label>
          <div class="flex gap-2 mt-1">
            <input
              :value="webhookUrl"
              readonly
              class="flex-1 rounded-lg border border-blue-300 dark:border-blue-700 bg-white dark:bg-gray-800 px-3 py-2 font-mono text-sm"
            />
            <button
              @click="copyToClipboard(webhookUrl)"
              class="px-3 py-2 bg-blue-100 dark:bg-blue-800 text-blue-700 dark:text-blue-300 rounded-lg hover:bg-blue-200 dark:hover:bg-blue-700"
            >
              <ClipboardIcon class="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Examples Grid -->
    <div class="space-y-4">
      <div
        v-for="example in filteredExamples"
        :key="example.name"
        class="bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-400 dark:border-gray-600 overflow-hidden"
      >
        <div class="flex items-center justify-between p-4 border-b border-gray-400 dark:border-gray-600">
          <div>
            <h4 class="font-medium text-gray-900 dark:text-white">{{ example.name }}</h4>
            <p class="text-sm text-gray-600 dark:text-gray-400">{{ example.description }}</p>
          </div>
          <button
            @click="copyToClipboard(example.code)"
            class="px-3 py-1.5 text-sm bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-500 flex items-center gap-1"
          >
            <ClipboardIcon class="w-4 h-4" />
            Copy
          </button>
        </div>
        <pre class="p-4 overflow-x-auto text-sm bg-gray-900 text-gray-100"><code>{{ example.code }}</code></pre>
      </div>
    </div>

    <!-- Built-in Examples (if no API examples) -->
    <div v-if="!examples.length" class="space-y-4">
      <!-- cURL Example -->
      <div class="bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-400 dark:border-gray-600 overflow-hidden">
        <div class="flex items-center justify-between p-4 border-b border-gray-400 dark:border-gray-600">
          <div>
            <h4 class="font-medium text-gray-900 dark:text-white">cURL - Basic Message</h4>
            <p class="text-sm text-gray-600 dark:text-gray-400">Send a simple notification via command line</p>
          </div>
          <button
            @click="copyToClipboard(curlBasic)"
            class="px-3 py-1.5 text-sm bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-500 flex items-center gap-1"
          >
            <ClipboardIcon class="w-4 h-4" />
            Copy
          </button>
        </div>
        <pre class="p-4 overflow-x-auto text-sm bg-gray-900 text-gray-100"><code>{{ curlBasic }}</code></pre>
      </div>

      <!-- cURL with Actions -->
      <div class="bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-400 dark:border-gray-600 overflow-hidden">
        <div class="flex items-center justify-between p-4 border-b border-gray-400 dark:border-gray-600">
          <div>
            <h4 class="font-medium text-gray-900 dark:text-white">cURL - With Actions</h4>
            <p class="text-sm text-gray-600 dark:text-gray-400">Notification with clickable action buttons</p>
          </div>
          <button
            @click="copyToClipboard(curlActions)"
            class="px-3 py-1.5 text-sm bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-500 flex items-center gap-1"
          >
            <ClipboardIcon class="w-4 h-4" />
            Copy
          </button>
        </div>
        <pre class="p-4 overflow-x-auto text-sm bg-gray-900 text-gray-100"><code>{{ curlActions }}</code></pre>
      </div>

      <!-- Python Example -->
      <div class="bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-400 dark:border-gray-600 overflow-hidden">
        <div class="flex items-center justify-between p-4 border-b border-gray-400 dark:border-gray-600">
          <div>
            <h4 class="font-medium text-gray-900 dark:text-white">Python - Requests</h4>
            <p class="text-sm text-gray-600 dark:text-gray-400">Send notifications from Python scripts</p>
          </div>
          <button
            @click="copyToClipboard(pythonExample)"
            class="px-3 py-1.5 text-sm bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-500 flex items-center gap-1"
          >
            <ClipboardIcon class="w-4 h-4" />
            Copy
          </button>
        </div>
        <pre class="p-4 overflow-x-auto text-sm bg-gray-900 text-gray-100"><code>{{ pythonExample }}</code></pre>
      </div>

      <!-- n8n Webhook Example -->
      <div class="bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-400 dark:border-gray-600 overflow-hidden">
        <div class="flex items-center justify-between p-4 border-b border-gray-400 dark:border-gray-600">
          <div>
            <h4 class="font-medium text-gray-900 dark:text-white">n8n - HTTP Request Node</h4>
            <p class="text-sm text-gray-600 dark:text-gray-400">Send notifications from n8n workflows</p>
          </div>
          <button
            @click="copyToClipboard(n8nExample)"
            class="px-3 py-1.5 text-sm bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-500 flex items-center gap-1"
          >
            <ClipboardIcon class="w-4 h-4" />
            Copy
          </button>
        </div>
        <pre class="p-4 overflow-x-auto text-sm bg-gray-900 text-gray-100"><code>{{ n8nExample }}</code></pre>
      </div>

      <!-- Bash Script Example -->
      <div class="bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-400 dark:border-gray-600 overflow-hidden">
        <div class="flex items-center justify-between p-4 border-b border-gray-400 dark:border-gray-600">
          <div>
            <h4 class="font-medium text-gray-900 dark:text-white">Bash - Function</h4>
            <p class="text-sm text-gray-600 dark:text-gray-400">Reusable bash function for shell scripts</p>
          </div>
          <button
            @click="copyToClipboard(bashExample)"
            class="px-3 py-1.5 text-sm bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-500 flex items-center gap-1"
          >
            <ClipboardIcon class="w-4 h-4" />
            Copy
          </button>
        </div>
        <pre class="p-4 overflow-x-auto text-sm bg-gray-900 text-gray-100"><code>{{ bashExample }}</code></pre>
      </div>
    </div>

    <!-- Copy notification -->
    <div
      v-if="showCopied"
      class="fixed bottom-4 right-4 px-4 py-2 bg-green-600 text-white rounded-lg shadow-lg"
    >
      Copied to clipboard!
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ClipboardIcon } from '@heroicons/vue/24/outline'

const props = defineProps({
  examples: { type: Array, default: () => [] },
  topics: { type: Array, default: () => [] },
})

// State
const selectedCategory = ref('All')
const selectedTopic = ref('')
const webhookUrl = ref('')
const showCopied = ref(false)

// Categories
const categories = computed(() => {
  const cats = new Set(['All'])
  props.examples.forEach(e => cats.add(e.category))
  if (!props.examples.length) {
    cats.add('cURL')
    cats.add('Python')
    cats.add('n8n')
    cats.add('Bash')
  }
  return Array.from(cats)
})

// Filter examples
const filteredExamples = computed(() => {
  if (selectedCategory.value === 'All') return props.examples
  return props.examples.filter(e => e.category === selectedCategory.value)
})

// Generate webhook URL
function generateWebhookUrl() {
  if (!selectedTopic.value) return
  // Use the NTFY base URL from the environment or default
  const baseUrl = window.location.origin.replace(/:\d+$/, '') + ':8085'
  webhookUrl.value = `${baseUrl}/${selectedTopic.value}`
}

// Copy to clipboard
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text)
    showCopied.value = true
    setTimeout(() => {
      showCopied.value = false
    }, 2000)
  } catch {
    // Fallback for older browsers
    const textarea = document.createElement('textarea')
    textarea.value = text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    showCopied.value = true
    setTimeout(() => {
      showCopied.value = false
    }, 2000)
  }
}

// Example code snippets
const curlBasic = `curl -X POST "http://your-ntfy-server/mytopic" \\
  -H "Content-Type: application/json" \\
  -d '{
    "message": "Hello from curl!",
    "title": "Test Notification",
    "priority": 4,
    "tags": ["warning", "server"]
  }'`

const curlActions = `curl -X POST "http://your-ntfy-server/mytopic" \\
  -H "Content-Type: application/json" \\
  -d '{
    "message": "Backup completed successfully",
    "title": "Backup Status",
    "priority": 3,
    "tags": ["white_check_mark", "backup"],
    "actions": [
      {"action": "view", "label": "View Logs", "url": "https://example.com/logs"},
      {"action": "http", "label": "Acknowledge", "url": "https://example.com/ack", "method": "POST"}
    ]
  }'`

const pythonExample = `import requests

def send_ntfy(topic, message, title=None, priority=3, tags=None):
    """Send a notification via NTFY."""
    url = f"http://your-ntfy-server/{topic}"

    payload = {
        "message": message,
        "priority": priority,
    }

    if title:
        payload["title"] = title
    if tags:
        payload["tags"] = tags

    response = requests.post(url, json=payload)
    return response.json()

# Example usage
send_ntfy(
    topic="alerts",
    message="Database backup completed",
    title="Backup Status",
    priority=4,
    tags=["white_check_mark", "database"]
)`

const n8nExample = `// n8n HTTP Request Node Configuration
// Method: POST
// URL: http://your-ntfy-server/{{ $json.topic }}

// Body (JSON):
{
  "message": "{{ $json.message }}",
  "title": "{{ $json.title }}",
  "priority": {{ $json.priority || 3 }},
  "tags": {{ $json.tags ? JSON.stringify($json.tags) : '[]' }}
}

// Headers:
// Content-Type: application/json`

// Using regular string to avoid Vue template parsing issues with bash ${} syntax
const bashExample = '#!/bin/bash\n\n# NTFY notification function\nsend_ntfy() {\n    local topic="$1"\n    local message="$2"\n    local title="${3:-}"\n    local priority="${4:-3}"\n    local tags="${5:-}"\n\n    local payload="{\\"message\\": \\"$message\\", \\"priority\\": $priority"\n\n    if [ -n "$title" ]; then\n        payload="$payload, \\"title\\": \\"$title\\""\n    fi\n\n    if [ -n "$tags" ]; then\n        payload="$payload, \\"tags\\": [$tags]"\n    fi\n\n    payload="$payload}"\n\n    curl -s -X POST "http://your-ntfy-server/$topic" \\\n        -H "Content-Type: application/json" \\\n        -d "$payload"\n}\n\n# Usage examples:\nsend_ntfy "alerts" "Backup completed" "Backup Status" 4 \'\\"white_check_mark\\"\'\nsend_ntfy "monitoring" "Server is healthy" "" 2'
</script>
