<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/common/EmptyState.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { InboxIcon } from '@heroicons/vue/24/outline'

defineProps({
  icon: {
    type: Object,
    default: () => InboxIcon,
  },
  title: {
    type: String,
    default: 'No data',
  },
  description: {
    type: String,
    default: '',
  },
  actionText: {
    type: String,
    default: '',
  },
})

defineEmits(['action'])
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12 text-center">
    <component
      :is="icon"
      class="h-12 w-12 text-muted mb-4"
    />
    <h3 class="text-lg font-medium text-primary mb-1">{{ title }}</h3>
    <p v-if="description" class="text-sm text-secondary mb-4 max-w-sm">
      {{ description }}
    </p>
    <button
      v-if="actionText"
      @click="$emit('action')"
      class="btn-primary"
    >
      {{ actionText }}
    </button>
    <slot />
  </div>
</template>
