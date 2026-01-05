<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/common/LoadingSpinner.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { useThemeStore } from '@/stores/theme'

defineProps({
  size: {
    type: String,
    default: 'md', // 'sm', 'md', 'lg'
  },
  text: {
    type: String,
    default: '',
  },
  textClass: {
    type: String,
    default: 'text-sm',
  },
})

const themeStore = useThemeStore()

const sizes = {
  sm: 'h-4 w-4',
  md: 'h-8 w-8',
  lg: 'h-12 w-12',
}
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-3">
    <svg
      :class="[
        sizes[size],
        'animate-spin',
        themeStore.isNeon ? 'text-cyan-400' : 'text-blue-500'
      ]"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        class="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        stroke-width="4"
      />
      <path
        class="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
    <span v-if="text" :class="[textClass, 'text-secondary']">{{ text }}</span>
  </div>
</template>
