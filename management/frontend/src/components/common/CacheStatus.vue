<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/common/CacheStatus.vue

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
  cacheStatus: {
    type: Object,
    default: () => ({ source: null, cached_at: null, age_seconds: null })
  },
  showDirectStatus: {
    type: Boolean,
    default: false
  }
})

const displayText = computed(() => {
  if (!props.cacheStatus) return null

  if (props.cacheStatus.source === 'cache') {
    const age = Math.round(props.cacheStatus.age_seconds || 0)
    if (age < 60) {
      return `Cached ${age}s ago`
    } else if (age < 3600) {
      return `Cached ${Math.round(age / 60)}m ago`
    } else {
      return `Cached ${Math.round(age / 3600)}h ago`
    }
  }

  if (props.showDirectStatus && props.cacheStatus.source === 'direct') {
    return 'Direct fetch'
  }

  return null
})

const statusClass = computed(() => {
  if (!props.cacheStatus) return ''

  if (props.cacheStatus.source === 'cache') {
    const age = props.cacheStatus.age_seconds || 0
    if (age < 10) {
      return 'text-emerald-500 dark:text-emerald-400'
    } else if (age < 30) {
      return 'text-blue-500 dark:text-blue-400'
    } else if (age < 60) {
      return 'text-yellow-500 dark:text-yellow-400'
    } else {
      return 'text-gray-500 dark:text-gray-400'
    }
  }

  return 'text-gray-500 dark:text-gray-400'
})
</script>

<template>
  <span v-if="displayText" :class="['text-xs', statusClass]">
    {{ displayText }}
  </span>
</template>
