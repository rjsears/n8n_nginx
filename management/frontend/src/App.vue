<script setup>
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useDebugStore } from '@/stores/debug'
import HorizontalLayout from '@/components/layouts/HorizontalLayout.vue'
import SidebarLayout from '@/components/layouts/SidebarLayout.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'

const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const debugStore = useDebugStore()

// Determine which layout to use
const LayoutComponent = computed(() => {
  // No layout for login page
  if (router.currentRoute.value.name === 'login') {
    return null
  }
  return themeStore.isSidebar ? SidebarLayout : HorizontalLayout
})

const showLayout = computed(() => {
  return router.currentRoute.value.name !== 'login' && authStore.isAuthenticated
})

onMounted(async () => {
  // Initialize theme
  themeStore.init()

  // Initialize auth (check if already logged in)
  await authStore.init()

  // Load debug mode state if authenticated
  if (authStore.isAuthenticated) {
    await debugStore.loadDebugMode()
  }
})
</script>

<template>
  <div :class="themeStore.themeClasses" class="min-h-screen">
    <!-- Login page - no layout -->
    <router-view v-if="!showLayout" />

    <!-- Main app with layout -->
    <component v-else :is="LayoutComponent">
      <router-view />
    </component>

    <!-- Global toast notifications -->
    <ToastContainer />
  </div>
</template>

<style>
/* Light mode - subtle gray boxes for stats */
.bg-surface-hover {
  background-color: #f3f4f6 !important;
}

/* Light mode - slightly lighter borders */
.border-\[var\(--color-border\)\] {
  border-color: #9ca3af !important;
}

/* Dark mode CSS variables - applied directly so dark mode works
   while light mode keeps its current appearance */
.dark {
  --color-bg-primary: #020617;
  --color-bg-secondary: #0f172a;
  --color-bg-tertiary: #1e293b;
  --color-surface: #1e293b;
  --color-surface-hover: #334155;
  --color-border: #64748b;
  --color-text-primary: #f1f5f9;
  --color-text-secondary: #94a3b8;
  --color-text-muted: #64748b;

  /* Accent colors - brighter for dark mode */
  --color-accent-primary: #60a5fa;
  --color-accent-success: #34d399;
  --color-accent-warning: #fbbf24;
  --color-accent-danger: #f87171;
  --color-accent-info: #22d3ee;

  /* Status colors - brighter for dark mode */
  --color-status-running: #34d399;
  --color-status-stopped: #9ca3af;
  --color-status-error: #f87171;
  --color-status-warning: #fbbf24;
}

/* Dark mode specific overrides for Tailwind classes */
.dark .bg-surface {
  background-color: var(--color-surface);
}

.dark .bg-surface-hover {
  background-color: #334155 !important;
}

.dark .bg-background-primary {
  background-color: var(--color-bg-primary);
}

.dark .bg-background-secondary {
  background-color: var(--color-bg-secondary);
}

.dark .text-primary {
  color: var(--color-text-primary);
}

.dark .text-secondary {
  color: var(--color-text-secondary);
}

.dark .text-muted {
  color: var(--color-text-muted);
}

.dark .border-\[var\(--color-border\)\] {
  border-color: #64748b !important;
}

/* Force dark mode borders on common elements */
.dark [class*="border-[var(--color-border)"] {
  border-color: #64748b !important;
}

.dark .border-b,
.dark .border-t,
.dark .border-r,
.dark .border-l,
.dark .border {
  border-color: #64748b;
}

/* Dark mode inputs and selects */
.dark input,
.dark textarea,
.dark select,
.dark .input,
.dark .select-field {
  background-color: #1e293b !important;
  color: #f1f5f9 !important;
  border-color: #64748b !important;
}

.dark input::placeholder,
.dark textarea::placeholder {
  color: #64748b !important;
}

.dark select option {
  background-color: #1e293b;
  color: #f1f5f9;
}
</style>
