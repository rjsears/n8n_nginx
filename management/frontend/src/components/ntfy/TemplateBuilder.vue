<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/ntfy/TemplateBuilder.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<template>
  <div class="template-builder">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-white">Message Templates</h3>
      <button
        @click="openEditor(null)"
        class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
      >
        <PlusIcon class="w-5 h-5" />
        New Template
      </button>
    </div>

    <!-- Templates List -->
    <div v-if="templates.length === 0" class="text-center py-12 text-gray-500 dark:text-gray-400">
      <DocumentTextIcon class="w-12 h-12 mx-auto mb-3 opacity-50" />
      <p>No templates yet. Create your first template to get started.</p>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="template in templates"
        :key="template.id"
        class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-400 dark:border-gray-600"
      >
        <div class="flex justify-between items-start mb-2">
          <h4 class="font-medium text-gray-900 dark:text-white">{{ template.name }}</h4>
          <span :class="[
            'px-2 py-0.5 rounded text-xs',
            template.template_type === 'custom'
              ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300'
              : 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300'
          ]">
            {{ template.template_type }}
          </span>
        </div>
        <p v-if="template.description" class="text-sm text-gray-600 dark:text-gray-400 mb-3">
          {{ template.description }}
        </p>
        <div class="text-xs text-gray-500 dark:text-gray-400 mb-3">
          <span>Used {{ template.use_count }} times</span>
          <span v-if="template.last_used"> | Last: {{ formatDate(template.last_used) }}</span>
        </div>
        <div class="flex gap-2">
          <button
            @click="openEditor(template)"
            class="flex-1 px-3 py-1.5 text-sm bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-500"
          >
            Edit
          </button>
          <button
            @click="previewTemplate(template)"
            class="px-3 py-1.5 text-sm bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded hover:bg-blue-200 dark:hover:bg-blue-900/50"
          >
            Preview
          </button>
          <button
            @click="deleteTemplate(template)"
            class="px-3 py-1.5 text-sm text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 rounded"
          >
            <TrashIcon class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>

    <!-- Template Editor Modal -->
    <div v-if="showEditor" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden">
        <div class="flex justify-between items-center p-4 border-b border-gray-400 dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
            {{ editingTemplate ? 'Edit Template' : 'Create Template' }}
          </h3>
          <button @click="closeEditor" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <XMarkIcon class="w-6 h-6" />
          </button>
        </div>

        <div class="p-4 overflow-y-auto max-h-[calc(90vh-130px)]">
          <form @submit.prevent="saveTemplate" class="space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <!-- Name -->
              <div>
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Template Name <span class="text-red-500">*</span>
                </label>
                <input
                  v-model="editorForm.name"
                  type="text"
                  placeholder="my-template"
                  class="w-full rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
                  required
                />
              </div>

              <!-- Type -->
              <div>
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Template Type
                </label>
                <select
                  v-model="editorForm.template_type"
                  class="w-full rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
                >
                  <option value="custom">Custom</option>
                  <option value="github">GitHub</option>
                  <option value="grafana">Grafana</option>
                  <option value="alertmanager">AlertManager</option>
                </select>
              </div>
            </div>

            <!-- Description -->
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Description
              </label>
              <input
                v-model="editorForm.description"
                type="text"
                placeholder="What this template is for..."
                class="w-full rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
              />
            </div>

            <!-- Title Template -->
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Title Template
              </label>
              <input
                v-model="editorForm.title_template"
                type="text"
                placeholder="e.g., {{ .event }} on {{ .repository }}"
                class="w-full rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 font-mono text-sm"
              />
              <p class="mt-1 text-xs text-gray-500">Uses Go template syntax. Variables: <code v-pre>{{ .field }}</code></p>
            </div>

            <!-- Message Template -->
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Message Template
              </label>
              <textarea
                v-model="editorForm.message_template"
                rows="6"
                placeholder="e.g., {{ .description }}&#10;&#10;By: {{ .sender.login }}"
                class="w-full rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 font-mono text-sm"
              ></textarea>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <!-- Default Priority -->
              <div>
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Default Priority
                </label>
                <select
                  v-model="editorForm.default_priority"
                  class="w-full rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
                >
                  <option :value="1">Min</option>
                  <option :value="2">Low</option>
                  <option :value="3">Default</option>
                  <option :value="4">High</option>
                  <option :value="5">Urgent</option>
                </select>
              </div>

              <!-- Markdown -->
              <div class="flex items-center pt-6">
                <input
                  id="use_markdown"
                  v-model="editorForm.use_markdown"
                  type="checkbox"
                  class="rounded border-gray-400 text-blue-600 focus:ring-blue-500"
                />
                <label for="use_markdown" class="ml-2 text-sm text-gray-700 dark:text-gray-300">
                  Enable Markdown formatting
                </label>
              </div>
            </div>

            <!-- Default Tags -->
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Default Tags
              </label>
              <input
                v-model="tagsInput"
                type="text"
                placeholder="warning, server, alert (comma-separated)"
                class="w-full rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2"
              />
            </div>

            <!-- Sample JSON -->
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Sample JSON (for preview)
              </label>
              <textarea
                v-model="sampleJsonInput"
                rows="4"
                placeholder='{"event": "push", "repository": "my-repo"}'
                class="w-full rounded-lg border border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 font-mono text-sm"
              ></textarea>
            </div>

            <!-- Preview Section -->
            <div v-if="previewResult" class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
              <h4 class="font-medium text-gray-900 dark:text-white mb-2">Preview</h4>
              <div v-if="previewResult.success">
                <p v-if="previewResult.rendered_title" class="font-semibold text-gray-900 dark:text-white">
                  {{ previewResult.rendered_title }}
                </p>
                <p class="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                  {{ previewResult.rendered_message }}
                </p>
              </div>
              <p v-else class="text-red-600 dark:text-red-400">
                {{ previewResult.error }}
              </p>
            </div>
          </form>
        </div>

        <div class="flex justify-between p-4 border-t border-gray-400 dark:border-gray-700">
          <button
            @click="runPreview"
            type="button"
            class="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            Preview
          </button>
          <div class="flex gap-2">
            <button
              @click="closeEditor"
              type="button"
              class="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
            >
              Cancel
            </button>
            <button
              @click="saveTemplate"
              :disabled="saving"
              class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {{ saving ? 'Saving...' : (editingTemplate ? 'Update' : 'Create') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import {
  PlusIcon,
  DocumentTextIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps({
  templates: { type: Array, default: () => [] },
  onCreate: { type: Function, required: true },
  onUpdate: { type: Function, required: true },
  onDelete: { type: Function, required: true },
  onPreview: { type: Function, required: true },
})

// State
const showEditor = ref(false)
const editingTemplate = ref(null)
const saving = ref(false)
const previewResult = ref(null)

const editorForm = ref({
  name: '',
  description: '',
  template_type: 'custom',
  title_template: '',
  message_template: '',
  default_priority: 3,
  use_markdown: false,
})

const tagsInput = ref('')
const sampleJsonInput = ref('')

// Format date
function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString()
}

// Open editor
function openEditor(template) {
  editingTemplate.value = template
  previewResult.value = null

  if (template) {
    editorForm.value = {
      name: template.name,
      description: template.description || '',
      template_type: template.template_type,
      title_template: template.title_template || '',
      message_template: template.message_template || '',
      default_priority: template.default_priority,
      use_markdown: template.use_markdown,
    }
    tagsInput.value = (template.default_tags || []).join(', ')
    sampleJsonInput.value = template.sample_json ? JSON.stringify(template.sample_json, null, 2) : ''
  } else {
    editorForm.value = {
      name: '',
      description: '',
      template_type: 'custom',
      title_template: '',
      message_template: '',
      default_priority: 3,
      use_markdown: false,
    }
    tagsInput.value = ''
    sampleJsonInput.value = ''
  }

  showEditor.value = true
}

// Close editor
function closeEditor() {
  showEditor.value = false
  editingTemplate.value = null
  previewResult.value = null
}

// Save template
async function saveTemplate() {
  saving.value = true

  try {
    const data = {
      ...editorForm.value,
      default_tags: tagsInput.value.split(',').map(t => t.trim()).filter(t => t),
    }

    if (sampleJsonInput.value) {
      try {
        data.sample_json = JSON.parse(sampleJsonInput.value)
      } catch {
        alert('Invalid JSON in sample data')
        saving.value = false
        return
      }
    }

    let result
    if (editingTemplate.value) {
      result = await props.onUpdate(editingTemplate.value.id, data)
    } else {
      result = await props.onCreate(data)
    }

    if (result?.success) {
      closeEditor()
    } else {
      alert(result?.error || 'Failed to save template')
    }
  } finally {
    saving.value = false
  }
}

// Delete template
async function deleteTemplate(template) {
  if (!confirm(`Delete template "${template.name}"?`)) return

  const result = await props.onDelete(template.id)
  if (!result?.success) {
    alert(result?.error || 'Failed to delete template')
  }
}

// Preview template
async function previewTemplate(template) {
  openEditor(template)
  await runPreview()
}

// Run preview
async function runPreview() {
  let sampleJson = {}
  if (sampleJsonInput.value) {
    try {
      sampleJson = JSON.parse(sampleJsonInput.value)
    } catch {
      previewResult.value = { success: false, error: 'Invalid JSON' }
      return
    }
  }

  previewResult.value = await props.onPreview({
    title_template: editorForm.value.title_template,
    message_template: editorForm.value.message_template,
    sample_json: sampleJson,
  })
}
</script>
