<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/common/StatusBadge.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { computed } from 'vue'

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

const statusConfig = {
  // Container statuses
  running: { label: 'Running', color: 'emerald' },
  stopped: { label: 'Stopped', color: 'gray' },
  restarting: { label: 'Restarting', color: 'amber' },
  unhealthy: { label: 'Unhealthy', color: 'red' },
  healthy: { label: 'Healthy', color: 'emerald' },

  // Backup statuses
  success: { label: 'Success', color: 'emerald' },
  failed: { label: 'Failed', color: 'red' },
  pending: { label: 'Pending', color: 'amber' },
  partial: { label: 'Partial', color: 'amber' },

  // Verification statuses
  passed: { label: 'Passed', color: 'emerald' },
  skipped: { label: 'Skipped', color: 'gray' },

  // Notification statuses
  sent: { label: 'Sent', color: 'emerald' },

  // Generic
  active: { label: 'Active', color: 'emerald' },
  inactive: { label: 'Inactive', color: 'gray' },
  archived: { label: 'Archived', color: 'amber' },
  enabled: { label: 'Enabled', color: 'emerald' },
  disabled: { label: 'Disabled', color: 'gray' },
  error: { label: 'Error', color: 'red' },
  warning: { label: 'Warning', color: 'amber' },
  info: { label: 'Info', color: 'blue' },
}

const config = computed(() => {
  const status = props.status.toLowerCase()
  return statusConfig[status] || { label: props.status, color: 'gray' }
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
      sizeClasses
    ]"
  >
    <span class="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-75" />
    {{ config.label }}
  </span>
</template>
