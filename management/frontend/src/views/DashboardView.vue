<script setup>
import { ref, onMounted, computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useContainerStore } from '@/stores/containers'
import { useBackupStore } from '@/stores/backups'
import Card from '@/components/common/Card.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import {
  ServerIcon,
  CircleStackIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowTrendingUpIcon,
  CpuChipIcon,
} from '@heroicons/vue/24/outline'
import { Line, Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  Filler,
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  Filler
)

const themeStore = useThemeStore()
const containerStore = useContainerStore()
const backupStore = useBackupStore()

const loading = ref(true)
const systemStats = ref({
  cpu_percent: 0,
  memory_percent: 0,
  disk_percent: 0,
  uptime: '0 days',
})

// Stats cards configuration
const statsCards = computed(() => [
  {
    title: 'Containers',
    value: containerStore.containers.length,
    subtitle: `${containerStore.runningCount} running`,
    icon: ServerIcon,
    color: 'blue',
  },
  {
    title: 'Last Backup',
    value: backupStore.lastBackup?.created_at
      ? new Date(backupStore.lastBackup.created_at).toLocaleDateString()
      : 'Never',
    subtitle: backupStore.lastBackup?.status || 'No backups yet',
    icon: CircleStackIcon,
    color: 'emerald',
  },
  {
    title: 'System Uptime',
    value: systemStats.value.uptime,
    subtitle: 'Since last restart',
    icon: ClockIcon,
    color: 'purple',
  },
  {
    title: 'CPU Usage',
    value: `${systemStats.value.cpu_percent}%`,
    subtitle: 'Current load',
    icon: CpuChipIcon,
    color: systemStats.value.cpu_percent > 80 ? 'red' : 'amber',
  },
])

// Chart colors based on theme
const chartColors = computed(() => {
  if (themeStore.isNeon) {
    return {
      primary: 'rgb(34, 211, 238)', // cyan-400
      secondary: 'rgb(244, 114, 182)', // pink-400
      success: 'rgb(52, 211, 153)', // emerald-400
      warning: 'rgb(251, 191, 36)', // amber-400
      danger: 'rgb(248, 113, 113)', // red-400
      grid: 'rgba(34, 211, 238, 0.1)',
    }
  }
  return {
    primary: 'rgb(59, 130, 246)', // blue-500
    secondary: 'rgb(168, 85, 247)', // purple-500
    success: 'rgb(34, 197, 94)', // green-500
    warning: 'rgb(245, 158, 11)', // amber-500
    danger: 'rgb(239, 68, 68)', // red-500
    grid: 'rgba(107, 114, 128, 0.1)',
  }
})

// Resource usage chart data
const resourceChartData = computed(() => ({
  labels: ['12:00', '12:15', '12:30', '12:45', '13:00', '13:15', '13:30'],
  datasets: [
    {
      label: 'CPU %',
      data: [45, 52, 48, 61, 55, 49, systemStats.value.cpu_percent],
      borderColor: chartColors.value.primary,
      backgroundColor: `${chartColors.value.primary.replace('rgb', 'rgba').replace(')', ', 0.1)')}`,
      fill: true,
      tension: 0.4,
    },
    {
      label: 'Memory %',
      data: [62, 64, 63, 67, 65, 66, systemStats.value.memory_percent],
      borderColor: chartColors.value.secondary,
      backgroundColor: 'transparent',
      tension: 0.4,
    },
  ],
}))

const resourceChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'top',
      labels: {
        color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280',
      },
    },
  },
  scales: {
    x: {
      grid: { color: chartColors.value.grid },
      ticks: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280' },
    },
    y: {
      grid: { color: chartColors.value.grid },
      ticks: { color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280' },
      min: 0,
      max: 100,
    },
  },
}))

// Container status chart
const containerChartData = computed(() => ({
  labels: ['Running', 'Stopped', 'Unhealthy'],
  datasets: [
    {
      data: [
        containerStore.runningCount,
        containerStore.stoppedCount,
        containerStore.unhealthyCount,
      ],
      backgroundColor: [
        chartColors.value.success,
        chartColors.value.warning,
        chartColors.value.danger,
      ],
      borderWidth: 0,
    },
  ],
}))

const containerChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'right',
      labels: {
        color: themeStore.colorMode === 'dark' ? '#9ca3af' : '#6b7280',
        padding: 20,
      },
    },
  },
}))

async function loadData() {
  loading.value = true
  try {
    await Promise.all([
      containerStore.fetchContainers(),
      backupStore.fetchBackups(),
    ])
    // Simulated system stats (would come from API)
    systemStats.value = {
      cpu_percent: 45,
      memory_percent: 68,
      disk_percent: 52,
      uptime: '14 days',
    }
  } catch (error) {
    console.error('Failed to load dashboard data:', error)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div>
      <h1
        :class="[
          'text-2xl font-bold',
          themeStore.isNeon ? 'neon-text-cyan' : 'text-primary'
        ]"
      >
        Dashboard
      </h1>
      <p class="text-secondary mt-1">Overview of your n8n infrastructure</p>
    </div>

    <LoadingSpinner v-if="loading" size="lg" text="Loading dashboard..." class="py-12" />

    <template v-else>
      <!-- Stats Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card
          v-for="stat in statsCards"
          :key="stat.title"
          :neon="true"
          :padding="false"
        >
          <div class="p-4">
            <div class="flex items-start justify-between">
              <div>
                <p class="text-sm text-secondary">{{ stat.title }}</p>
                <p
                  :class="[
                    'text-2xl font-bold mt-1',
                    themeStore.isNeon ? 'neon-text-cyan' : 'text-primary'
                  ]"
                >
                  {{ stat.value }}
                </p>
                <p class="text-xs text-muted mt-1">{{ stat.subtitle }}</p>
              </div>
              <div
                :class="[
                  'p-2 rounded-lg',
                  `bg-${stat.color}-100 dark:bg-${stat.color}-500/20`
                ]"
              >
                <component
                  :is="stat.icon"
                  :class="[
                    'h-5 w-5',
                    `text-${stat.color}-500 dark:text-${stat.color}-400`
                  ]"
                />
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Charts Row -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Resource Usage Chart -->
        <Card title="Resource Usage" subtitle="Last 2 hours" :neon="true" class="lg:col-span-2">
          <div class="h-64">
            <Line :data="resourceChartData" :options="resourceChartOptions" />
          </div>
        </Card>

        <!-- Container Status Chart -->
        <Card title="Container Status" :neon="true">
          <div class="h-64">
            <Doughnut :data="containerChartData" :options="containerChartOptions" />
          </div>
        </Card>
      </div>

      <!-- Container List -->
      <Card title="Containers" subtitle="Docker container status" :neon="true">
        <template #actions>
          <button class="btn-secondary text-sm" @click="containerStore.fetchContainers">
            Refresh
          </button>
        </template>

        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-[var(--color-border)]">
                <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Name</th>
                <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Status</th>
                <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Image</th>
                <th class="text-left py-3 px-4 text-sm font-medium text-secondary">Uptime</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="container in containerStore.containers"
                :key="container.id"
                class="border-b border-[var(--color-border)] last:border-0"
              >
                <td class="py-3 px-4">
                  <span class="font-medium text-primary">{{ container.name }}</span>
                </td>
                <td class="py-3 px-4">
                  <StatusBadge :status="container.status" />
                </td>
                <td class="py-3 px-4 text-sm text-secondary">
                  {{ container.image }}
                </td>
                <td class="py-3 px-4 text-sm text-secondary">
                  {{ container.uptime || '-' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      <!-- Recent Backups -->
      <Card title="Recent Backups" subtitle="Last 5 backups" :neon="true">
        <template #actions>
          <router-link to="/backups" class="btn-secondary text-sm">
            View All
          </router-link>
        </template>

        <div class="space-y-3">
          <div
            v-for="backup in backupStore.backups.slice(0, 5)"
            :key="backup.id"
            class="flex items-center justify-between p-3 rounded-lg bg-surface-hover"
          >
            <div class="flex items-center gap-3">
              <div
                :class="[
                  'p-2 rounded-lg',
                  backup.status === 'success'
                    ? 'bg-emerald-100 dark:bg-emerald-500/20'
                    : 'bg-red-100 dark:bg-red-500/20'
                ]"
              >
                <CheckCircleIcon
                  v-if="backup.status === 'success'"
                  class="h-5 w-5 text-emerald-500"
                />
                <ExclamationTriangleIcon v-else class="h-5 w-5 text-red-500" />
              </div>
              <div>
                <p class="font-medium text-primary">{{ backup.type }} Backup</p>
                <p class="text-xs text-muted">
                  {{ new Date(backup.created_at).toLocaleString() }}
                </p>
              </div>
            </div>
            <StatusBadge :status="backup.status" size="sm" />
          </div>
        </div>
      </Card>
    </template>
  </div>
</template>
