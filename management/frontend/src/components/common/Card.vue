<script setup>
import { useThemeStore } from '@/stores/theme'

defineProps({
  title: String,
  subtitle: String,
  neon: {
    type: Boolean,
    default: false,
  },
  padding: {
    type: Boolean,
    default: true,
  },
  flex: {
    type: Boolean,
    default: false,
  },
})

const themeStore = useThemeStore()
</script>

<template>
  <div
    :class="[
      'rounded-lg border border-gray-300 dark:border-slate-500 bg-surface',
      neon && themeStore.isNeon ? 'neon-card' : '',
      padding ? '' : 'p-0',
      flex ? 'flex flex-col' : ''
    ]"
  >
    <!-- Header -->
    <div
      v-if="title || $slots.header"
      :class="[
        'border-b border-gray-300 dark:border-slate-500 flex-shrink-0',
        padding ? 'px-6 py-4' : 'px-4 py-3'
      ]"
    >
      <slot name="header">
        <div class="flex items-center justify-between">
          <div>
            <h3
              :class="[
                'text-lg font-semibold',
                themeStore.isNeon && neon ? 'neon-text-cyan' : 'text-primary'
              ]"
            >
              {{ title }}
            </h3>
            <p v-if="subtitle" class="text-sm text-secondary mt-0.5">
              {{ subtitle }}
            </p>
          </div>
          <slot name="actions" />
        </div>
      </slot>
    </div>

    <!-- Content -->
    <div :class="[padding ? 'p-6' : '', flex ? 'flex-1 flex flex-col min-h-0' : '']">
      <slot />
    </div>

    <!-- Footer -->
    <div
      v-if="$slots.footer"
      :class="[
        'border-t border-gray-300 dark:border-slate-500 flex-shrink-0',
        padding ? 'px-6 py-4' : 'px-4 py-3'
      ]"
    >
      <slot name="footer" />
    </div>
  </div>
</template>
