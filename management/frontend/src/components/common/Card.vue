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
})

const themeStore = useThemeStore()
</script>

<template>
  <div
    :class="[
      'rounded-lg border border-[var(--color-border)] bg-surface',
      neon && themeStore.isNeon ? 'neon-card' : '',
      padding ? '' : 'p-0'
    ]"
  >
    <!-- Header -->
    <div
      v-if="title || $slots.header"
      :class="[
        'border-b border-[var(--color-border)]',
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
    <div :class="padding ? 'p-6' : ''">
      <slot />
    </div>

    <!-- Footer -->
    <div
      v-if="$slots.footer"
      :class="[
        'border-t border-[var(--color-border)]',
        padding ? 'px-6 py-4' : 'px-4 py-3'
      ]"
    >
      <slot name="footer" />
    </div>
  </div>
</template>
