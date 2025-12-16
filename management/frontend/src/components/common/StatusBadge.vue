<script setup>
import { computed } from 'vue'
import { useThemeStore } from '@/stores/theme'

const props = defineProps({
  status: {
    type: String,
    required: true,
  },
  size: {
    type: String,
    default: 'md', // 'sm', 'md', 'lg'
  },
})

const themeStore = useThemeStore()

const statusConfig = {
  // Container statuses
  running: { label: 'Running', color: 'emerald', neonClass: 'status-running' },
  stopped: { label: 'Stopped', color: 'gray', neonClass: 'status-stopped' },
  restarting: { label: 'Restarting', color: 'amber', neonClass: 'status-warning' },
  unhealthy: { label: 'Unhealthy', color: 'red', neonClass: 'status-error' },
  healthy: { label: 'Healthy', color: 'emerald', neonClass: 'status-running' },

  // Backup statuses
  success: { label: 'Success', color: 'emerald', neonClass: 'status-running' },
  failed: { label: 'Failed', color: 'red', neonClass: 'status-error' },
  pending: { label: 'Pending', color: 'amber', neonClass: 'status-warning' },
  partial: { label: 'Partial', color: 'amber', neonClass: 'status-warning' },

  // Verification statuses
  passed: { label: 'Passed', color: 'emerald', neonClass: 'status-running' },
  skipped: { label: 'Skipped', color: 'gray', neonClass: 'status-stopped' },

  // Notification statuses
  sent: { label: 'Sent', color: 'emerald', neonClass: 'status-running' },

  // Generic
  active: { label: 'Active', color: 'emerald', neonClass: 'status-running' },
  inactive: { label: 'Inactive', color: 'gray', neonClass: 'status-stopped' },
  enabled: { label: 'Enabled', color: 'emerald', neonClass: 'status-running' },
  disabled: { label: 'Disabled', color: 'gray', neonClass: 'status-stopped' },
  error: { label: 'Error', color: 'red', neonClass: 'status-error' },
  warning: { label: 'Warning', color: 'amber', neonClass: 'status-warning' },
  info: { label: 'Info', color: 'blue', neonClass: '' },
}

const config = computed(() => {
  const status = props.status.toLowerCase()
  return statusConfig[status] || { label: props.status, color: 'gray', neonClass: '' }
})

const colorClasses = computed(() => {
  const colors = {
    emerald: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-400',
    red: 'bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-400',
    amber: 'bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-400',
    blue: 'bg-blue-100 text-blue-800 dark:bg-blue-500/20 dark:text-blue-400',
    gray: 'bg-gray-100 text-gray-800 dark:bg-gray-500/20 dark:text-gray-400',
  }
  return colors[config.value.color] || colors.gray
})

const sizeClasses = computed(() => {
  const sizes = {
    sm: 'px-1.5 py-0.5 text-xs',
    md: 'px-2 py-1 text-xs',
    lg: 'px-2.5 py-1 text-sm',
  }
  return sizes[props.size] || sizes.md
})
</script>

<template>
  <span
    :class="[
      'inline-flex items-center font-medium rounded-full',
      colorClasses,
      sizeClasses,
      themeStore.isNeon ? config.neonClass : ''
    ]"
  >
    <span class="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-75" />
    {{ config.label }}
  </span>
</template>
