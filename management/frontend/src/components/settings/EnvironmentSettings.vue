<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/settings/EnvironmentSettings.vue

Environment Configuration Settings Component
Manages .env file variables with health checks and warnings

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref, onMounted, computed } from 'vue'
import { useNotificationStore } from '@/stores/notifications'
import api from '@/services/api'
import Card from '@/components/common/Card.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import {
  ExclamationCircleIcon,
  CircleStackIcon,
  ShieldCheckIcon,
  Cog6ToothIcon,
  ServerIcon,
  CloudIcon,
  GlobeAltIcon,
  CubeIcon,
  BellIcon,
  CodeBracketIcon,
  PlusCircleIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  EyeIcon,
  EyeSlashIcon,
  PencilSquareIcon,
  TrashIcon,
  ArrowPathIcon,
  ShieldExclamationIcon,
  InformationCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  PlusIcon,
  BeakerIcon,
} from '@heroicons/vue/24/outline'

const notificationStore = useNotificationStore()

// State
const loading = ref(true)
const saving = ref(false)
const envGroups = ref([])
const lastModified = ref(null)
const expandedGroups = ref(new Set())
const editingVariable = ref(null)
const editValue = ref('')
const showPassword = ref(new Set())
const pendingChanges = ref({})
const healthCheckResults = ref(null)
const healthCheckLoading = ref(false)

// Confirmation gate - user must acknowledge warning before seeing settings
const hasAcknowledgedRisk = ref(false)

// Add variable dialog
const showAddDialog = ref(false)
const newVarKey = ref('')
const newVarValue = ref('')

// Delete confirmation
const showDeleteConfirm = ref(false)
const variableToDelete = ref(null)

// Reload confirmation
const showReloadConfirm = ref(false)

// Icon mapping
const iconMap = {
  ExclamationCircleIcon,
  CircleStackIcon,
  ShieldCheckIcon,
  Cog6ToothIcon,
  ServerIcon,
  CloudIcon,
  GlobeAltIcon,
  CubeIcon,
  BellIcon,
  CodeBracketIcon,
  PlusCircleIcon,
}

// Color classes for groups
const colorClasses = {
  red: {
    bg: 'bg-red-50 dark:bg-red-500/10',
    border: 'border-red-200 dark:border-red-500/30',
    icon: 'text-red-500',
    text: 'text-red-700 dark:text-red-400',
    headerBg: 'bg-red-100 dark:bg-red-500/20',
  },
  blue: {
    bg: 'bg-blue-50 dark:bg-blue-500/10',
    border: 'border-blue-200 dark:border-blue-500/30',
    icon: 'text-blue-500',
    text: 'text-blue-700 dark:text-blue-400',
    headerBg: 'bg-blue-100 dark:bg-blue-500/20',
  },
  amber: {
    bg: 'bg-amber-50 dark:bg-amber-500/10',
    border: 'border-amber-200 dark:border-amber-500/30',
    icon: 'text-amber-500',
    text: 'text-amber-700 dark:text-amber-400',
    headerBg: 'bg-amber-100 dark:bg-amber-500/20',
  },
  purple: {
    bg: 'bg-purple-50 dark:bg-purple-500/10',
    border: 'border-purple-200 dark:border-purple-500/30',
    icon: 'text-purple-500',
    text: 'text-purple-700 dark:text-purple-400',
    headerBg: 'bg-purple-100 dark:bg-purple-500/20',
  },
  emerald: {
    bg: 'bg-emerald-50 dark:bg-emerald-500/10',
    border: 'border-emerald-200 dark:border-emerald-500/30',
    icon: 'text-emerald-500',
    text: 'text-emerald-700 dark:text-emerald-400',
    headerBg: 'bg-emerald-100 dark:bg-emerald-500/20',
  },
  orange: {
    bg: 'bg-orange-50 dark:bg-orange-500/10',
    border: 'border-orange-200 dark:border-orange-500/30',
    icon: 'text-orange-500',
    text: 'text-orange-700 dark:text-orange-400',
    headerBg: 'bg-orange-100 dark:bg-orange-500/20',
  },
  indigo: {
    bg: 'bg-indigo-50 dark:bg-indigo-500/10',
    border: 'border-indigo-200 dark:border-indigo-500/30',
    icon: 'text-indigo-500',
    text: 'text-indigo-700 dark:text-indigo-400',
    headerBg: 'bg-indigo-100 dark:bg-indigo-500/20',
  },
  gray: {
    bg: 'bg-gray-50 dark:bg-gray-500/10',
    border: 'border-gray-200 dark:border-gray-500/30',
    icon: 'text-gray-500',
    text: 'text-gray-700 dark:text-gray-400',
    headerBg: 'bg-gray-100 dark:bg-gray-500/20',
  },
  cyan: {
    bg: 'bg-cyan-50 dark:bg-cyan-500/10',
    border: 'border-cyan-200 dark:border-cyan-500/30',
    icon: 'text-cyan-500',
    text: 'text-cyan-700 dark:text-cyan-400',
    headerBg: 'bg-cyan-100 dark:bg-cyan-500/20',
  },
  pink: {
    bg: 'bg-pink-50 dark:bg-pink-500/10',
    border: 'border-pink-200 dark:border-pink-500/30',
    icon: 'text-pink-500',
    text: 'text-pink-700 dark:text-pink-400',
    headerBg: 'bg-pink-100 dark:bg-pink-500/20',
  },
  slate: {
    bg: 'bg-slate-50 dark:bg-slate-500/10',
    border: 'border-slate-200 dark:border-slate-500/30',
    icon: 'text-slate-500',
    text: 'text-slate-700 dark:text-slate-400',
    headerBg: 'bg-slate-100 dark:bg-slate-500/20',
  },
}

// Computed
const hasPendingChanges = computed(() => Object.keys(pendingChanges.value).length > 0)

// Methods
async function loadEnvConfig() {
  loading.value = true
  try {
    const response = await api.get('/env-config')
    envGroups.value = response.data.groups
    lastModified.value = response.data.last_modified
  } catch (error) {
    console.error('Failed to load environment config:', error)
    notificationStore.error('Failed to load environment configuration')
  } finally {
    loading.value = false
  }
}

function toggleGroup(groupKey) {
  if (expandedGroups.value.has(groupKey)) {
    expandedGroups.value.delete(groupKey)
  } else {
    expandedGroups.value.add(groupKey)
  }
}

function getIcon(iconName) {
  return iconMap[iconName] || Cog6ToothIcon
}

function getColorClass(color, type) {
  return colorClasses[color]?.[type] || colorClasses.gray[type]
}

function startEditing(variable) {
  editingVariable.value = variable.key
  editValue.value = variable.sensitive ? '' : variable.value
}

function cancelEditing() {
  editingVariable.value = null
  editValue.value = ''
}

async function saveVariable(variable) {
  if (!editValue.value && variable.required) {
    notificationStore.error('This field is required')
    return
  }

  saving.value = true
  try {
    await api.put(`/env-config/${variable.key}`, {
      key: variable.key,
      value: editValue.value,
    })
    notificationStore.success(`${variable.label} updated successfully`)
    editingVariable.value = null
    editValue.value = ''
    await loadEnvConfig()
  } catch (error) {
    console.error('Failed to save variable:', error)
    notificationStore.error(error.response?.data?.detail || 'Failed to save variable')
  } finally {
    saving.value = false
  }
}

function togglePasswordVisibility(key) {
  if (showPassword.value.has(key)) {
    showPassword.value.delete(key)
  } else {
    showPassword.value.add(key)
  }
}

function getDisplayValue(variable) {
  if (variable.sensitive) {
    if (showPassword.value.has(variable.key)) {
      // We don't have the actual value, show placeholder
      return variable.value || '********'
    }
    return '********'
  }
  return variable.value || variable.default || ''
}

async function runHealthCheck() {
  healthCheckLoading.value = true
  healthCheckResults.value = null
  try {
    const response = await api.post('/env-config/health-check', pendingChanges.value)
    healthCheckResults.value = response.data
    if (response.data.overall_success) {
      notificationStore.success('All health checks passed')
    } else {
      notificationStore.warning('Some health checks failed')
    }
  } catch (error) {
    console.error('Health check failed:', error)
    notificationStore.error('Failed to run health checks')
  } finally {
    healthCheckLoading.value = false
  }
}

function openAddDialog() {
  newVarKey.value = ''
  newVarValue.value = ''
  showAddDialog.value = true
}

async function addVariable() {
  if (!newVarKey.value) {
    notificationStore.error('Variable name is required')
    return
  }

  // Validate key format
  if (!/^[A-Z][A-Z0-9_]*$/.test(newVarKey.value)) {
    notificationStore.error('Variable name must be uppercase and start with a letter (e.g., MY_VARIABLE)')
    return
  }

  saving.value = true
  try {
    await api.post('/env-config', {
      key: newVarKey.value,
      value: newVarValue.value,
    })
    notificationStore.success(`Variable ${newVarKey.value} added successfully`)
    showAddDialog.value = false
    newVarKey.value = ''
    newVarValue.value = ''
    await loadEnvConfig()
  } catch (error) {
    console.error('Failed to add variable:', error)
    notificationStore.error(error.response?.data?.detail || 'Failed to add variable')
  } finally {
    saving.value = false
  }
}

function confirmDelete(variable) {
  variableToDelete.value = variable
  showDeleteConfirm.value = true
}

async function deleteVariable() {
  if (!variableToDelete.value) return

  saving.value = true
  try {
    await api.delete(`/env-config/${variableToDelete.value.key}`)
    notificationStore.success(`Variable ${variableToDelete.value.key} deleted`)
    showDeleteConfirm.value = false
    variableToDelete.value = null
    await loadEnvConfig()
  } catch (error) {
    console.error('Failed to delete variable:', error)
    notificationStore.error(error.response?.data?.detail || 'Failed to delete variable')
  } finally {
    saving.value = false
  }
}

async function reloadEnvVariables() {
  saving.value = true
  try {
    const response = await api.post('/env-config/reload')
    notificationStore.success(response.data.message)
    showReloadConfirm.value = false
    await loadEnvConfig()
  } catch (error) {
    console.error('Failed to reload variables:', error)
    notificationStore.error('Failed to reload environment variables')
  } finally {
    saving.value = false
  }
}

function formatDate(isoString) {
  if (!isoString) return 'Unknown'
  return new Date(isoString).toLocaleString()
}

function acknowledgeRisk() {
  hasAcknowledgedRisk.value = true
}

onMounted(() => {
  loadEnvConfig()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Warning Banner -->
    <div class="bg-gradient-to-r from-red-600 to-red-700 rounded-xl p-6 shadow-lg border border-red-500">
      <div class="flex items-start gap-4">
        <div class="flex-shrink-0">
          <div class="w-16 h-16 rounded-xl bg-white/10 flex items-center justify-center">
            <!-- Skull and Crossbones SVG -->
            <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C9.243 2 7 4.243 7 7c0 1.602.771 3.022 1.958 3.936C7.786 11.878 7 13.362 7 15v2h2v-2c0-1.654 1.346-3 3-3s3 1.346 3 3v2h2v-2c0-1.638-.786-3.122-2.042-4.064C16.229 10.022 17 8.602 17 7c0-2.757-2.243-5-5-5zm-2 6c-.552 0-1-.448-1-1s.448-1 1-1 1 .448 1 1-.448 1-1 1zm4 0c-.552 0-1-.448-1-1s.448-1 1-1 1 .448 1 1-.448 1-1 1z"/>
              <path d="M9 19h2v3H9zM13 19h2v3h-2z"/>
            </svg>
          </div>
        </div>
        <div class="flex-1">
          <h3 class="text-xl font-bold text-white mb-2">Advanced Configuration - Proceed with Caution</h3>
          <p class="text-red-100 text-sm leading-relaxed">
            Changing any of these environment variables could lead to <strong>system failure</strong>,
            <strong>loss of access</strong>, or <strong>data corruption</strong>. These settings control
            the core functionality of the n8n management system, supporting containers, and network access.
          </p>
          <div class="mt-3 flex items-center gap-2 text-red-200 text-sm">
            <ExclamationTriangleIcon class="h-5 w-5" />
            <span>This is an <strong>ADVANCED</strong> configuration area. Changes are not typically required during normal operation.</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Confirmation Gate - Show Continue Button if not acknowledged -->
    <div v-if="!hasAcknowledgedRisk" class="flex justify-center py-12">
      <button
        @click="acknowledgeRisk"
        class="flex items-center gap-3 px-8 py-4 bg-red-600 hover:bg-red-700 text-white rounded-xl font-semibold text-lg transition-colors shadow-lg hover:shadow-xl"
      >
        <ShieldExclamationIcon class="h-6 w-6" />
        I understand the risks, Continue...
      </button>
    </div>

    <!-- Main Content - Only show after acknowledgement -->
    <template v-if="hasAcknowledgedRisk">
      <!-- Action Bar -->
      <div class="flex items-center justify-between bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-400 dark:border-gray-700">
        <div class="flex items-center gap-4">
          <button
            @click="runHealthCheck"
            :disabled="healthCheckLoading"
            class="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            <BeakerIcon v-if="!healthCheckLoading" class="h-5 w-5" />
            <LoadingSpinner v-else size="sm" />
            Validate Configuration
          </button>
          <button
            @click="showReloadConfirm = true"
            class="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors"
          >
            <ArrowPathIcon class="h-5 w-5" />
            Reload Variables
          </button>
        </div>
        <div class="flex items-center gap-4">
          <button
            @click="openAddDialog"
            class="flex items-center gap-2 px-4 py-2 bg-purple-500 hover:bg-purple-600 text-white rounded-lg font-medium transition-colors"
          >
            <PlusIcon class="h-5 w-5" />
            Add Custom Variable
          </button>
          <div v-if="lastModified" class="text-sm text-secondary">
            Last modified: {{ formatDate(lastModified) }}
          </div>
        </div>
      </div>

      <!-- Health Check Results -->
      <Transition name="fade">
        <div v-if="healthCheckResults" class="bg-white dark:bg-gray-800 rounded-xl border border-gray-400 dark:border-gray-700 overflow-hidden">
          <div class="px-4 py-3 border-b border-gray-400 dark:border-gray-700 flex items-center justify-between">
            <div class="flex items-center gap-3">
              <component
                :is="healthCheckResults.overall_success ? CheckCircleIcon : XCircleIcon"
                :class="[
                  'h-6 w-6',
                  healthCheckResults.overall_success ? 'text-emerald-500' : 'text-red-500'
                ]"
              />
              <h3 class="font-semibold text-primary">
                Health Check Results - {{ healthCheckResults.overall_success ? 'All Passed' : 'Issues Found' }}
              </h3>
            </div>
            <button
              @click="healthCheckResults = null"
              class="text-secondary hover:text-primary"
            >
              <XCircleIcon class="h-5 w-5" />
            </button>
          </div>
          <div class="p-4 space-y-3">
            <div
              v-for="check in healthCheckResults.checks"
              :key="check.check_type"
              :class="[
                'flex items-center gap-3 p-3 rounded-lg',
                check.success ? 'bg-emerald-50 dark:bg-emerald-500/10' : 'bg-red-50 dark:bg-red-500/10'
              ]"
            >
              <component
                :is="check.success ? CheckCircleIcon : XCircleIcon"
                :class="['h-5 w-5', check.success ? 'text-emerald-500' : 'text-red-500']"
              />
              <div>
                <p :class="['font-medium', check.success ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400']">
                  {{ check.message }}
                </p>
                <p v-if="check.details" class="text-xs text-secondary mt-1">
                  {{ JSON.stringify(check.details) }}
                </p>
              </div>
            </div>
            <div v-if="healthCheckResults.warnings?.length > 0" class="mt-4">
              <h4 class="font-medium text-amber-700 dark:text-amber-400 mb-2">Warnings</h4>
              <ul class="space-y-2">
                <li
                  v-for="(warning, idx) in healthCheckResults.warnings"
                  :key="idx"
                  class="flex items-start gap-2 text-sm text-amber-600 dark:text-amber-400"
                >
                  <ExclamationTriangleIcon class="h-4 w-4 flex-shrink-0 mt-0.5" />
                  {{ warning }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Loading State -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <LoadingSpinner />
      </div>

      <!-- Variable Groups -->
      <div v-else class="space-y-4">
        <div
          v-for="group in envGroups"
          :key="group.key"
          class="bg-white dark:bg-gray-800 rounded-xl border border-gray-400 dark:border-gray-700 overflow-hidden"
        >
          <!-- Group Header - Icon on far left, click to expand -->
          <button
            @click="toggleGroup(group.key)"
            class="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
          >
            <!-- Icon container on far left -->
            <div :class="['p-2 rounded-lg', getColorClass(group.color, 'headerBg')]">
              <component
                :is="getIcon(group.icon)"
                :class="['h-5 w-5', getColorClass(group.color, 'icon')]"
              />
            </div>
            <div class="flex-1 text-left">
              <h3 :class="['font-semibold', getColorClass(group.color, 'text')]">
                {{ group.label }}
              </h3>
              <p class="text-xs text-secondary">{{ group.description }}</p>
            </div>
            <span class="text-sm text-secondary">
              {{ group.variables.length }} variable{{ group.variables.length !== 1 ? 's' : '' }}
            </span>
          </button>

          <!-- Group Variables -->
          <Transition name="collapse">
            <div v-if="expandedGroups.has(group.key)" class="divide-y divide-gray-200 dark:divide-gray-700 border-t border-gray-200 dark:border-gray-700">
              <div
                v-for="variable in group.variables"
                :key="variable.key"
                class="px-4 py-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
              >
                <div class="flex items-start justify-between gap-4">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1">
                      <span class="font-mono text-sm font-medium text-primary">{{ variable.key }}</span>
                      <span v-if="variable.required" class="text-xs px-1.5 py-0.5 bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 rounded">
                        Required
                      </span>
                      <span v-if="variable.sensitive" class="text-xs px-1.5 py-0.5 bg-amber-100 dark:bg-amber-500/20 text-amber-600 dark:text-amber-400 rounded">
                        Sensitive
                      </span>
                      <span v-if="variable.is_custom" class="text-xs px-1.5 py-0.5 bg-purple-100 dark:bg-purple-500/20 text-purple-600 dark:text-purple-400 rounded">
                        Custom
                      </span>
                      <span v-if="!variable.editable" class="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-500/20 text-gray-600 dark:text-gray-400 rounded">
                        Read-only
                      </span>
                    </div>
                    <p class="text-sm text-secondary mb-2">{{ variable.description }}</p>

                    <!-- Warning message -->
                    <div v-if="variable.warning" class="flex items-start gap-2 p-2 bg-red-50 dark:bg-red-500/10 rounded-lg mb-2">
                      <ExclamationTriangleIcon class="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
                      <span class="text-xs text-red-600 dark:text-red-400">{{ variable.warning }}</span>
                    </div>

                    <!-- Value Display / Edit -->
                    <div v-if="editingVariable === variable.key" class="flex items-center gap-2">
                      <input
                        v-model="editValue"
                        :type="variable.type === 'password' && !showPassword.has(variable.key) ? 'password' : 'text'"
                        :placeholder="variable.sensitive ? 'Enter new value' : variable.default || ''"
                        class="flex-1 px-3 py-2 border border-gray-400 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-primary font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                      <button
                        v-if="variable.type === 'password'"
                        @click="togglePasswordVisibility(variable.key)"
                        class="p-2 text-secondary hover:text-primary"
                      >
                        <EyeSlashIcon v-if="showPassword.has(variable.key)" class="h-5 w-5" />
                        <EyeIcon v-else class="h-5 w-5" />
                      </button>
                      <button
                        @click="saveVariable(variable)"
                        :disabled="saving"
                        class="px-3 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                      >
                        Save
                      </button>
                      <button
                        @click="cancelEditing"
                        class="px-3 py-2 bg-gray-200 dark:bg-gray-600 hover:bg-gray-300 dark:hover:bg-gray-500 text-primary rounded-lg text-sm font-medium transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                    <div v-else class="flex items-center gap-2">
                      <div class="flex-1 px-3 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg font-mono text-sm text-primary">
                        {{ getDisplayValue(variable) || '(not set)' }}
                      </div>
                      <button
                        v-if="variable.sensitive && variable.value"
                        @click="togglePasswordVisibility(variable.key)"
                        class="p-2 text-secondary hover:text-primary"
                      >
                        <EyeSlashIcon v-if="showPassword.has(variable.key)" class="h-5 w-5" />
                        <EyeIcon v-else class="h-5 w-5" />
                      </button>
                    </div>
                  </div>

                  <!-- Actions -->
                  <div class="flex items-center gap-2">
                    <button
                      v-if="variable.editable && editingVariable !== variable.key"
                      @click="startEditing(variable)"
                      class="p-2 text-blue-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-500/10 rounded-lg transition-colors"
                      title="Edit"
                    >
                      <PencilSquareIcon class="h-5 w-5" />
                    </button>
                    <button
                      v-if="variable.is_custom"
                      @click="confirmDelete(variable)"
                      class="p-2 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors"
                      title="Delete"
                    >
                      <TrashIcon class="h-5 w-5" />
                    </button>
                  </div>
                </div>
              </div>

              <!-- Empty state for custom group -->
              <div v-if="group.key === 'custom' && group.variables.length === 0" class="px-4 py-8 text-center">
                <PlusCircleIcon class="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
                <p class="text-secondary">No custom variables defined</p>
                <button
                  @click="openAddDialog"
                  class="mt-3 text-purple-500 hover:text-purple-600 text-sm font-medium"
                >
                  Add your first custom variable
                </button>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </template>

    <!-- Add Variable Dialog -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="showAddDialog"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4"
        >
          <!-- Backdrop -->
          <div
            class="absolute inset-0 bg-black/50"
            @click="showAddDialog = false"
          />

          <!-- Dialog -->
          <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full border border-gray-400 dark:border-gray-700">
            <!-- Header -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-full bg-purple-100 dark:bg-purple-500/20">
                  <PlusCircleIcon class="h-5 w-5 text-purple-600 dark:text-purple-400" />
                </div>
                <h3 class="text-lg font-semibold text-primary">Add Custom Variable</h3>
              </div>
              <button
                @click="showAddDialog = false"
                class="p-1 rounded-lg text-secondary hover:text-primary hover:bg-surface-hover"
              >
                <XCircleIcon class="h-5 w-5" />
              </button>
            </div>

            <!-- Content -->
            <div class="px-6 py-4 space-y-4">
              <div>
                <label class="block text-sm font-medium text-primary mb-1">Variable Name</label>
                <input
                  v-model="newVarKey"
                  type="text"
                  placeholder="MY_CUSTOM_VARIABLE"
                  class="w-full px-3 py-2 border border-gray-400 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-primary font-mono focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
                <p class="text-xs text-secondary mt-1">Must be uppercase, start with a letter, and contain only letters, numbers, and underscores</p>
              </div>
              <div>
                <label class="block text-sm font-medium text-primary mb-1">Value</label>
                <input
                  v-model="newVarValue"
                  type="text"
                  placeholder="Enter value"
                  class="w-full px-3 py-2 border border-gray-400 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-primary focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
            </div>

            <!-- Footer -->
            <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-400 dark:border-gray-700">
              <button
                @click="showAddDialog = false"
                class="btn-secondary"
              >
                Cancel
              </button>
              <button
                @click="addVariable"
                :disabled="saving"
                class="btn-primary"
              >
                <span v-if="saving" class="flex items-center gap-2">
                  <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Adding...
                </span>
                <span v-else>Add Variable</span>
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Delete Confirmation -->
    <ConfirmDialog
      :open="showDeleteConfirm"
      title="Delete Variable"
      :message="`Are you sure you want to delete '${variableToDelete?.key}'? This action cannot be undone.`"
      confirm-text="Delete"
      cancel-text="Cancel"
      :danger="true"
      @confirm="deleteVariable"
      @cancel="showDeleteConfirm = false; variableToDelete = null"
    />

    <!-- Reload Confirmation -->
    <ConfirmDialog
      :open="showReloadConfirm"
      title="Reload Environment Variables"
      message="This will reload environment variables into the current process. Note: Container restarts may be required for all changes to take full effect."
      confirm-text="Reload"
      cancel-text="Cancel"
      @confirm="reloadEnvVariables"
      @cancel="showReloadConfirm = false"
    />
  </div>
</template>

<style scoped>
.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.3s ease;
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
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
