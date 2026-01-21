<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/backup-ui/BackupContents.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import {
  EyeIcon,
  ExclamationTriangleIcon,
  DocumentTextIcon,
  KeyIcon,
  Cog6ToothIcon,
  HashtagIcon,
  ServerIcon,
  CubeIcon,
  DocumentIcon,
  ShieldCheckIcon
} from '@heroicons/vue/24/outline'
import BackupScanLoader from '../common/BackupScanLoader.vue'
import { formatBytes } from '../../utils/formatters'
import { getConfigFileIcon } from '../../utils/helpers'

const props = defineProps({
  backup: {
    type: Object,
    required: true
  },
  contents: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  },
  activeTab: {
    type: String,
    default: 'workflows'
  }
})

const emit = defineEmits(['update:activeTab'])

const iconMap = {
  ShieldCheckIcon,
  KeyIcon,
  ServerIcon,
  CubeIcon,
  DocumentIcon
}

function getIconComponent(file) {
  const iconName = getConfigFileIcon(file)
  return iconMap[iconName] || DocumentIcon
}

function formatFileSize(size) {
  return size ? formatBytes(size) : 'N/A'
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg border border-cyan-200 dark:border-cyan-700 overflow-hidden">
    <!-- Header with Summary -->
    <div class="p-4 bg-cyan-50 dark:bg-cyan-900/20 border-b border-cyan-200 dark:border-cyan-700">
      <h4 class="font-semibold text-primary flex items-center gap-2 mb-3">
        <EyeIcon class="h-5 w-5 text-cyan-600 dark:text-cyan-400" />
        Backup Contents
      </h4>
      <!-- Loading State -->
      <div v-if="loading" class="flex items-center justify-center py-8">
        <BackupScanLoader text="Scanning backup contents..." />
      </div>
      <!-- No Data State -->
      <div v-else-if="contents === null" class="text-center py-4 text-secondary">
        <ExclamationTriangleIcon class="h-8 w-8 mx-auto mb-2 text-amber-500" />
        <p>No metadata available for this backup.</p>
        <p class="text-xs mt-1">Older backups may not have contents metadata stored.</p>
      </div>
      <!-- Summary Stats -->
      <div v-else class="grid grid-cols-3 gap-4">
        <div class="text-center p-3 rounded-lg bg-white dark:bg-gray-800 border border-cyan-100 dark:border-cyan-800">
          <DocumentTextIcon class="h-6 w-6 mx-auto mb-1 text-indigo-500" />
          <p class="text-2xl font-bold text-primary">{{ contents.workflow_count || 0 }}</p>
          <p class="text-xs text-secondary">Workflows</p>
        </div>
        <div class="text-center p-3 rounded-lg bg-white dark:bg-gray-800 border border-cyan-100 dark:border-cyan-800">
          <KeyIcon class="h-6 w-6 mx-auto mb-1 text-amber-500" />
          <p class="text-2xl font-bold text-primary">{{ contents.credential_count || 0 }}</p>
          <p class="text-xs text-secondary">Credentials</p>
        </div>
        <div class="text-center p-3 rounded-lg bg-white dark:bg-gray-800 border border-cyan-100 dark:border-cyan-800">
          <Cog6ToothIcon class="h-6 w-6 mx-auto mb-1 text-emerald-500" />
          <p class="text-2xl font-bold text-primary">{{ contents.config_file_count || 0 }}</p>
          <p class="text-xs text-secondary">Config Files</p>
        </div>
      </div>
    </div>

    <!-- Tab Navigation -->
    <div v-if="contents" class="flex border-b border-gray-200 dark:border-gray-700">
      <button
        @click="emit('update:activeTab', 'workflows')"
        :class="[
          'flex-1 px-4 py-3 text-sm font-medium flex items-center justify-center gap-2 transition-colors',
          activeTab === 'workflows'
            ? 'text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20'
            : 'text-secondary hover:text-primary hover:bg-gray-50 dark:hover:bg-gray-800'
        ]"
      >
        <DocumentTextIcon class="h-4 w-4" />
        Workflows
      </button>
      <button
        @click="emit('update:activeTab', 'credentials')"
        :class="[
          'flex-1 px-4 py-3 text-sm font-medium flex items-center justify-center gap-2 transition-colors',
          activeTab === 'credentials'
            ? 'text-amber-600 dark:text-amber-400 border-b-2 border-amber-500 bg-amber-50 dark:bg-amber-900/20'
            : 'text-secondary hover:text-primary hover:bg-gray-50 dark:hover:bg-gray-800'
        ]"
      >
        <KeyIcon class="h-4 w-4" />
        Credentials
      </button>
      <button
        @click="emit('update:activeTab', 'config')"
        :class="[
          'flex-1 px-4 py-3 text-sm font-medium flex items-center justify-center gap-2 transition-colors',
          activeTab === 'config'
            ? 'text-emerald-600 dark:text-emerald-400 border-b-2 border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20'
            : 'text-secondary hover:text-primary hover:bg-gray-50 dark:hover:bg-gray-800'
        ]"
      >
        <Cog6ToothIcon class="h-4 w-4" />
        Configuration
      </button>
    </div>

    <!-- Tab Content -->
    <div v-if="contents" class="max-h-96 overflow-y-auto">
      <!-- Workflows Tab -->
      <div v-if="activeTab === 'workflows'">
        <div v-if="!contents.workflows_manifest || contents.workflows_manifest.length === 0" class="p-6 text-center text-secondary">
          <DocumentTextIcon class="h-8 w-8 mx-auto mb-2 text-gray-300 dark:text-gray-600" />
          <p>No workflows in this backup</p>
        </div>
        <table v-else class="w-full">
          <thead class="bg-gray-50 dark:bg-gray-800 sticky top-0">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-semibold text-secondary uppercase tracking-wide">Workflow Name</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-secondary uppercase tracking-wide">ID</th>
              <th class="px-4 py-3 text-center text-xs font-semibold text-secondary uppercase tracking-wide">Status</th>
              <th class="px-4 py-3 text-center text-xs font-semibold text-secondary uppercase tracking-wide">Nodes</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-secondary uppercase tracking-wide">Updated</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
            <tr v-for="workflow in contents.workflows_manifest" :key="workflow.id" class="hover:bg-gray-50 dark:hover:bg-gray-800/50">
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <DocumentTextIcon class="h-4 w-4 text-indigo-500 flex-shrink-0" />
                  <span class="font-medium text-primary truncate max-w-xs" :title="workflow.name">{{ workflow.name }}</span>
                </div>
              </td>
              <td class="px-4 py-3">
                <code class="text-xs bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded font-mono text-secondary">{{ workflow.id }}</code>
              </td>
              <td class="px-4 py-3 text-center">
                <span :class="[
                  'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
                  workflow.archived
                    ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400'
                    : workflow.active
                      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400'
                      : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                ]">
                  {{ workflow.archived ? 'Archived' : (workflow.active ? 'Active' : 'Inactive') }}
                </span>
              </td>
              <td class="px-4 py-3 text-center">
                <span class="inline-flex items-center gap-1 text-sm text-secondary">
                  <HashtagIcon class="h-3 w-3" />
                  {{ workflow.node_count || 0 }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm text-secondary">
                {{ workflow.updated_at ? new Date(workflow.updated_at).toLocaleDateString() : 'N/A' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Credentials Tab -->
      <div v-if="activeTab === 'credentials'">
        <div v-if="!contents.credentials_manifest || contents.credentials_manifest.length === 0" class="p-6 text-center text-secondary">
          <KeyIcon class="h-8 w-8 mx-auto mb-2 text-gray-300 dark:text-gray-600" />
          <p>No credentials metadata available</p>
          <p class="text-xs mt-1">Credential details are stored securely and not included in metadata</p>
        </div>
        <table v-else class="w-full">
          <thead class="bg-gray-50 dark:bg-gray-800 sticky top-0">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-semibold text-secondary uppercase tracking-wide">Credential Name</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-secondary uppercase tracking-wide">Type</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-secondary uppercase tracking-wide">ID</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
            <tr v-for="cred in contents.credentials_manifest" :key="cred.id" class="hover:bg-gray-50 dark:hover:bg-gray-800/50">
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <KeyIcon class="h-4 w-4 text-amber-500 flex-shrink-0" />
                  <span class="font-medium text-primary">{{ cred.name }}</span>
                </div>
              </td>
              <td class="px-4 py-3">
                <span class="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400">
                  {{ cred.type }}
                </span>
              </td>
              <td class="px-4 py-3">
                <code class="text-xs bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded font-mono text-secondary">{{ cred.id }}</code>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Configuration Tab -->
      <div v-if="activeTab === 'config'">
        <div v-if="!contents.config_files_manifest || contents.config_files_manifest.length === 0" class="p-6 text-center text-secondary">
          <Cog6ToothIcon class="h-8 w-8 mx-auto mb-2 text-gray-300 dark:text-gray-600" />
          <p>No configuration files metadata available</p>
        </div>
        <table v-else class="w-full">
          <thead class="bg-gray-50 dark:bg-gray-800 sticky top-0">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-semibold text-secondary uppercase tracking-wide">File Name</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-secondary uppercase tracking-wide">Path</th>
              <th class="px-4 py-3 text-right text-xs font-semibold text-secondary uppercase tracking-wide">Size</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-secondary uppercase tracking-wide">Checksum</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
            <tr v-for="(file, index) in contents.config_files_manifest" :key="index" class="hover:bg-gray-50 dark:hover:bg-gray-800/50">
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <component
                    :is="getIconComponent(file)"
                    class="h-4 w-4 text-emerald-500 flex-shrink-0"
                  />
                  <span class="font-medium text-primary">{{ file.name || file.filename || 'Unknown' }}</span>
                </div>
              </td>
              <td class="px-4 py-3">
                <code class="text-xs bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded font-mono text-secondary truncate max-w-xs block" :title="file.path">{{ file.path || 'N/A' }}</code>
              </td>
              <td class="px-4 py-3 text-right text-sm text-secondary">
                {{ formatFileSize(file.size) }}
              </td>
              <td class="px-4 py-3">
                <code v-if="file.checksum" class="text-xs bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded font-mono text-secondary truncate max-w-[120px] block" :title="file.checksum">{{ file.checksum?.substring(0, 12) }}...</code>
                <span v-else class="text-sm text-secondary">N/A</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
