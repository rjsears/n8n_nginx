<script setup>
import { ref, onMounted, computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useBackupStore } from '@/stores/backups'
import { useNotificationStore } from '@/stores/notifications'
import Card from '@/components/common/Card.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import {
  CircleStackIcon,
  PlayIcon,
  TrashIcon,
  ArrowDownTrayIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  CalendarIcon,
  Cog6ToothIcon,
} from '@heroicons/vue/24/outline'

const themeStore = useThemeStore()
const backupStore = useBackupStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const runningBackup = ref(false)
const deleteDialog = ref({ open: false, backup: null, loading: false })

// Backup schedule (would come from API)
const schedule = ref({
  enabled: true,
  time: '02:00',
  frequency: 'daily',
  retention_days: 30,
})

// Filter and sort
const filterStatus = ref('all')
const sortBy = ref('date')

const filteredBackups = computed(() => {
  let backups = [...backupStore.backups]

  // Filter by status
  if (filterStatus.value !== 'all') {
    backups = backups.filter((b) => b.status === filterStatus.value)
  }

  // Sort
  if (sortBy.value === 'date') {
    backups.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  } else if (sortBy.value === 'size') {
    backups.sort((a, b) => (b.size_bytes || 0) - (a.size_bytes || 0))
  }

  return backups
})

// Stats
const stats = computed(() => ({
  total: backupStore.backups.length,
  successful: backupStore.backups.filter((b) => b.status === 'success').length,
  failed: backupStore.backups.filter((b) => b.status === 'failed').length,
  totalSize: backupStore.backups.reduce((sum, b) => sum + (b.size_bytes || 0), 0),
}))

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

async function runBackupNow() {
  runningBackup.value = true
  try {
    await backupStore.triggerBackup()
    notificationStore.success('Backup started successfully')
  } catch (error) {
    notificationStore.error('Failed to start backup')
  } finally {
    runningBackup.value = false
  }
}

function openDeleteDialog(backup) {
  deleteDialog.value = { open: true, backup, loading: false }
}

async function confirmDelete() {
  if (!deleteDialog.value.backup) return

  deleteDialog.value.loading = true
  try {
    await backupStore.deleteBackup(deleteDialog.value.backup.id)
    notificationStore.success('Backup deleted')
    deleteDialog.value.open = false
  } catch (error) {
    notificationStore.error('Failed to delete backup')
  } finally {
    deleteDialog.value.loading = false
  }
}

async function loadData() {
  loading.value = true
  try {
    await backupStore.fetchBackups()
  } catch (error) {
    notificationStore.error('Failed to load backups')
  } finally {
    loading.value = false
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
          Backups
        </h1>
        <p class="text-secondary mt-1">Manage database and workflow backups</p>
      </div>
      <button
        @click="runBackupNow"
        :disabled="runningBackup"
        :class="[
          'btn-primary flex items-center gap-2',
          themeStore.isNeon ? 'neon-btn-cyan' : ''
        ]"
      >
        <PlayIcon class="h-4 w-4" />
        {{ runningBackup ? 'Running...' : 'Backup Now' }}
      </button>
    </div>

    <LoadingSpinner v-if="loading" size="lg" text="Loading backups..." class="py-12" />

    <template v-else>
      <!-- Stats Grid -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-500/20">
                <CircleStackIcon class="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Total Backups</p>
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
                <p class="text-sm text-secondary">Successful</p>
                <p class="text-xl font-bold text-primary">{{ stats.successful }}</p>
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

        <Card :neon="true" :padding="false">
          <div class="p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-500/20">
                <ArrowDownTrayIcon class="h-5 w-5 text-purple-500" />
              </div>
              <div>
                <p class="text-sm text-secondary">Total Size</p>
                <p class="text-xl font-bold text-primary">{{ formatBytes(stats.totalSize) }}</p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Schedule Card -->
      <Card title="Backup Schedule" :neon="true">
        <template #actions>
          <button class="btn-secondary text-sm flex items-center gap-1">
            <Cog6ToothIcon class="h-4 w-4" />
            Configure
          </button>
        </template>

        <div class="flex items-center gap-8">
          <div class="flex items-center gap-3">
            <CalendarIcon class="h-5 w-5 text-muted" />
            <div>
              <p class="text-sm text-secondary">Frequency</p>
              <p class="font-medium text-primary capitalize">{{ schedule.frequency }}</p>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <ClockIcon class="h-5 w-5 text-muted" />
            <div>
              <p class="text-sm text-secondary">Time</p>
              <p class="font-medium text-primary">{{ schedule.time }}</p>
            </div>
          </div>
          <div>
            <p class="text-sm text-secondary">Retention</p>
            <p class="font-medium text-primary">{{ schedule.retention_days }} days</p>
          </div>
          <div>
            <StatusBadge :status="schedule.enabled ? 'enabled' : 'disabled'" />
          </div>
        </div>
      </Card>

      <!-- Filters -->
      <Card :neon="true" :padding="false">
        <div class="p-4 flex items-center gap-4">
          <select v-model="filterStatus" class="select-field">
            <option value="all">All Statuses</option>
            <option value="success">Successful</option>
            <option value="failed">Failed</option>
            <option value="pending">Pending</option>
          </select>
          <select v-model="sortBy" class="select-field">
            <option value="date">Sort by Date</option>
            <option value="size">Sort by Size</option>
          </select>
        </div>
      </Card>

      <!-- Backups List -->
      <Card title="Backup History" :neon="true">
        <EmptyState
          v-if="filteredBackups.length === 0"
          :icon="CircleStackIcon"
          title="No backups found"
          description="No backups match your current filters."
        />

        <div v-else class="space-y-3">
          <div
            v-for="backup in filteredBackups"
            :key="backup.id"
            class="flex items-center justify-between p-4 rounded-lg bg-surface-hover border border-gray-300 dark:border-slate-500"
          >
            <div class="flex items-center gap-4">
              <div
                :class="[
                  'p-3 rounded-lg',
                  backup.status === 'success'
                    ? 'bg-emerald-100 dark:bg-emerald-500/20'
                    : backup.status === 'failed'
                    ? 'bg-red-100 dark:bg-red-500/20'
                    : 'bg-amber-100 dark:bg-amber-500/20'
                ]"
              >
                <CircleStackIcon
                  :class="[
                    'h-6 w-6',
                    backup.status === 'success'
                      ? 'text-emerald-500'
                      : backup.status === 'failed'
                      ? 'text-red-500'
                      : 'text-amber-500'
                  ]"
                />
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <p class="font-medium text-primary">{{ backup.type }} Backup</p>
                  <StatusBadge :status="backup.status" size="sm" />
                </div>
                <p class="text-sm text-secondary mt-1">
                  {{ new Date(backup.created_at).toLocaleString() }}
                </p>
                <p class="text-xs text-muted mt-0.5">
                  {{ backup.filename }} • {{ formatBytes(backup.size_bytes) }}
                </p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <button
                v-if="backup.status === 'success'"
                class="btn-secondary p-2"
                title="Download"
              >
                <ArrowDownTrayIcon class="h-4 w-4" />
              </button>
              <button
                @click="openDeleteDialog(backup)"
                class="btn-secondary p-2 text-red-500 hover:text-red-600"
                title="Delete"
              >
                <TrashIcon class="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </Card>
    </template>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="deleteDialog.open"
      title="Delete Backup"
      message="Are you sure you want to delete this backup? This action cannot be undone."
      confirm-text="Delete"
      :danger="true"
      :loading="deleteDialog.loading"
      @confirm="confirmDelete"
      @cancel="deleteDialog.open = false"
    />
  </div>
</template>
