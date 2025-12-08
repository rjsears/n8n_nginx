# Frontend Agent Prompt - n8n Management System v3.0

## Role and Expertise
You are a Frontend Engineer specializing in Vue 3 Composition API, TailwindCSS, and modern SPA development. You have deep expertise in building responsive dashboards, data visualization, real-time updates, accessible user interfaces, and **multi-theme systems**.

## Project Context

### Technology Stack
- **Framework**: Vue 3 with Composition API and `<script setup>`
- **Build Tool**: Vite
- **Styling**: TailwindCSS 3.x with CSS custom properties for theming
- **State Management**: Pinia
- **HTTP Client**: Axios with interceptors
- **Icons**: Heroicons or Lucide Vue
- **Charts**: Chart.js with vue-chartjs (for system metrics)
- **Real-time**: Native WebSocket or EventSource for live updates

### Access Pattern
- Application served at `https://{domain}:{port}` (default port 3333)
- All API calls to `/api/*` endpoints
- Authentication via session token stored in httpOnly cookie
- SSO links to `/adminer/` and `/logs/` (Dozzle)

### Design Requirements
- **4 switchable themes** (user can change in Settings):
  - **Theme A**: Modern Light (horizontal nav, light colors)
  - **Theme B**: Modern Dark (horizontal nav, dark colors)
  - **Theme C**: Dashboard Light (sidebar nav, data-dense, light)
  - **Theme D**: Dashboard Dark + Neon (sidebar nav, data-dense, neon effects)
- Colored icons for visual hierarchy
- Responsive design (desktop-first, but mobile-friendly)
- Clear visual feedback for all actions
- Theme preference persisted to database

---

## Theme System Architecture

### Theme Dimensions
The theme system is composed of three independent settings:

```
┌─────────────────────────────────────────────────────────────┐
│                    THEME SYSTEM                             │
├─────────────────────────────────────────────────────────────┤
│  Layout Mode:     "horizontal"  or  "sidebar"               │
│  Color Mode:      "light"       or  "dark"                  │
│  Neon Effects:    true          or  false (dark only)       │
├─────────────────────────────────────────────────────────────┤
│  Theme Presets:                                             │
│  • A (Modern Light)     = horizontal + light + no-neon      │
│  • B (Modern Dark)      = horizontal + dark  + no-neon      │
│  • C (Dashboard Light)  = sidebar    + light + no-neon      │
│  • D (Dashboard Dark)   = sidebar    + dark  + neon         │
└─────────────────────────────────────────────────────────────┘
```

### Color Tokens (CSS Custom Properties)
```css
:root {
  /* Light mode colors (default) */
  --color-bg-primary: theme('colors.white');
  --color-bg-secondary: theme('colors.gray.50');
  --color-bg-tertiary: theme('colors.gray.100');
  --color-surface: theme('colors.white');
  --color-surface-hover: theme('colors.gray.50');
  --color-border: theme('colors.gray.200');
  --color-text-primary: theme('colors.gray.900');
  --color-text-secondary: theme('colors.gray.600');
  --color-text-muted: theme('colors.gray.400');
}

.dark {
  /* Dark mode colors */
  --color-bg-primary: theme('colors.slate.950');
  --color-bg-secondary: theme('colors.slate.900');
  --color-bg-tertiary: theme('colors.slate.800');
  --color-surface: theme('colors.slate.800');
  --color-surface-hover: theme('colors.slate.700');
  --color-border: theme('colors.slate.700');
  --color-text-primary: theme('colors.slate.100');
  --color-text-secondary: theme('colors.slate.400');
  --color-text-muted: theme('colors.slate.500');
}

.neon-enabled {
  /* Neon glow effects for Theme D */
  --glow-cyan: 0 0 20px theme('colors.cyan.400');
  --glow-fuchsia: 0 0 20px theme('colors.fuchsia.400');
  --glow-success: 0 0 15px theme('colors.emerald.400');
  --glow-warning: 0 0 15px theme('colors.amber.400');
  --glow-danger: 0 0 15px theme('colors.rose.400');
}
```

---

## Project Structure

Create the following structure under `/home/user/n8n_nginx/management/frontend/`:

```
frontend/
├── index.html
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── package.json
│
├── public/
│   └── favicon.ico
│
├── src/
│   ├── main.js
│   ├── App.vue
│   │
│   ├── assets/
│   │   └── styles/
│   │       ├── main.css
│   │       ├── themes.css          # Theme CSS custom properties
│   │       └── neon.css            # Neon glow effects for Theme D
│   │
│   ├── components/
│   │   ├── common/
│   │   │   ├── AppHeader.vue
│   │   │   ├── AppSidebar.vue
│   │   │   ├── LoadingSpinner.vue
│   │   │   ├── ConfirmDialog.vue
│   │   │   ├── Toast.vue
│   │   │   ├── DataTable.vue
│   │   │   ├── EmptyState.vue
│   │   │   ├── StatusBadge.vue
│   │   │   ├── CountdownTimer.vue
│   │   │   └── ThemeToggle.vue     # Quick theme switcher
│   │   │
│   │   ├── layouts/                 # NEW: Layout components
│   │   │   ├── HorizontalLayout.vue # For themes A & B
│   │   │   └── SidebarLayout.vue    # For themes C & D
│   │   │
│   │   ├── dashboard/
│   │   │   ├── ContainerCard.vue
│   │   │   ├── SystemMetrics.vue
│   │   │   ├── BackupSummary.vue
│   │   │   ├── RecentActivity.vue
│   │   │   └── QuickActions.vue
│   │   │
│   │   ├── backups/
│   │   │   ├── BackupScheduleForm.vue
│   │   │   ├── BackupHistoryTable.vue
│   │   │   ├── RetentionSettings.vue
│   │   │   ├── BackupCard.vue
│   │   │   └── VerificationStatus.vue
│   │   │
│   │   ├── notifications/
│   │   │   ├── ServiceCard.vue
│   │   │   ├── ServiceForm.vue
│   │   │   ├── RuleForm.vue
│   │   │   ├── EventTypeSelector.vue
│   │   │   └── NotificationHistory.vue
│   │   │
│   │   ├── containers/
│   │   │   ├── ContainerList.vue
│   │   │   ├── ContainerDetails.vue
│   │   │   ├── ContainerActions.vue
│   │   │   └── LogViewer.vue
│   │   │
│   │   ├── flows/
│   │   │   ├── FlowList.vue
│   │   │   ├── FlowFromBackup.vue
│   │   │   └── RestoreDialog.vue
│   │   │
│   │   ├── settings/
│   │   │   ├── GeneralSettings.vue
│   │   │   ├── SecuritySettings.vue
│   │   │   ├── EmailSettings.vue
│   │   │   ├── NfsSettings.vue
│   │   │   ├── SubnetManager.vue
│   │   │   └── AppearanceSettings.vue  # NEW: Theme selection
│   │   │
│   │   └── system/
│   │       ├── HostMetrics.vue
│   │       ├── DiskUsage.vue
│   │       ├── PowerControls.vue
│   │       └── NfsStatus.vue
│   │
│   ├── views/
│   │   ├── LoginView.vue
│   │   ├── DashboardView.vue
│   │   ├── BackupsView.vue
│   │   ├── NotificationsView.vue
│   │   ├── ContainersView.vue
│   │   ├── FlowsView.vue
│   │   ├── SystemView.vue
│   │   └── SettingsView.vue
│   │
│   ├── stores/
│   │   ├── auth.js
│   │   ├── theme.js               # NEW: Theme state management
│   │   ├── backups.js
│   │   ├── notifications.js
│   │   ├── containers.js
│   │   ├── system.js
│   │   └── settings.js
│   │
│   ├── composables/
│   │   ├── useApi.js
│   │   ├── useToast.js
│   │   ├── useConfirm.js
│   │   ├── usePolling.js
│   │   ├── useCountdown.js
│   │   └── useTheme.js            # NEW: Theme utilities
│   │
│   ├── router/
│   │   └── index.js
│   │
│   └── utils/
│       ├── api.js
│       ├── formatters.js
│       └── constants.js
```

---

## Assigned Tasks

### Task 1: Project Setup and Configuration

**package.json:**
```json
{
  "name": "n8n-management-frontend",
  "version": "3.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.2.0",
    "pinia": "^2.1.0",
    "pinia-plugin-persistedstate": "^3.2.0",
    "axios": "^1.6.0",
    "@heroicons/vue": "^2.1.0",
    "chart.js": "^4.4.0",
    "vue-chartjs": "^5.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.0.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  }
}
```

**tailwind.config.js:**
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class', // Enable class-based dark mode
  theme: {
    extend: {
      colors: {
        // Primary brand colors
        primary: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
          950: '#082f49',
        },
        // Status colors
        success: {
          DEFAULT: '#10b981',
          light: '#d1fae5',
          dark: '#059669',
        },
        warning: {
          DEFAULT: '#f59e0b',
          light: '#fef3c7',
          dark: '#d97706',
        },
        danger: {
          DEFAULT: '#ef4444',
          light: '#fee2e2',
          dark: '#dc2626',
        },
        info: {
          DEFAULT: '#3b82f6',
          light: '#dbeafe',
          dark: '#2563eb',
        },
        // Neon accent colors (for Theme D)
        neon: {
          cyan: '#22d3ee',
          fuchsia: '#e879f9',
          violet: '#a78bfa',
          emerald: '#34d399',
          amber: '#fbbf24',
          rose: '#fb7185',
        },
      },
      // Neon glow box shadows
      boxShadow: {
        'neon-cyan': '0 0 20px rgba(34, 211, 238, 0.5)',
        'neon-fuchsia': '0 0 20px rgba(232, 121, 249, 0.5)',
        'neon-success': '0 0 15px rgba(52, 211, 153, 0.5)',
        'neon-warning': '0 0 15px rgba(251, 191, 36, 0.5)',
        'neon-danger': '0 0 15px rgba(251, 113, 133, 0.5)',
      },
      // Animation for neon pulse
      animation: {
        'neon-pulse': 'neon-pulse 2s ease-in-out infinite',
      },
      keyframes: {
        'neon-pulse': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
      },
    },
  },
  plugins: [],
}
```

---

### Task 2: Theme Store

**src/stores/theme.js:**
```javascript
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import api from '@/utils/api'

// Theme presets mapping
const THEME_PRESETS = {
  modern_light: { layout: 'horizontal', colorMode: 'light', neonEffects: false },
  modern_dark: { layout: 'horizontal', colorMode: 'dark', neonEffects: false },
  dashboard_light: { layout: 'sidebar', colorMode: 'light', neonEffects: false },
  dashboard_dark_neon: { layout: 'sidebar', colorMode: 'dark', neonEffects: true },
}

export const useThemeStore = defineStore('theme', () => {
  // Theme state
  const layout = ref('horizontal') // 'horizontal' | 'sidebar'
  const colorMode = ref('light')   // 'light' | 'dark'
  const neonEffects = ref(false)   // Only applies when colorMode is 'dark'
  const preset = ref('modern_light')
  const initialized = ref(false)

  // Computed
  const isHorizontalLayout = computed(() => layout.value === 'horizontal')
  const isSidebarLayout = computed(() => layout.value === 'sidebar')
  const isDark = computed(() => colorMode.value === 'dark')
  const isNeonEnabled = computed(() => neonEffects.value && isDark.value)

  // CSS classes for root element
  const themeClasses = computed(() => ({
    'dark': isDark.value,
    'neon-enabled': isNeonEnabled.value,
    'layout-horizontal': isHorizontalLayout.value,
    'layout-sidebar': isSidebarLayout.value,
  }))

  // Apply theme to document
  function applyTheme() {
    const html = document.documentElement

    // Color mode
    if (isDark.value) {
      html.classList.add('dark')
    } else {
      html.classList.remove('dark')
    }

    // Neon effects
    if (isNeonEnabled.value) {
      html.classList.add('neon-enabled')
    } else {
      html.classList.remove('neon-enabled')
    }
  }

  // Watch for changes and apply
  watch([colorMode, neonEffects], applyTheme, { immediate: true })

  // Set theme from preset
  function setPreset(presetName) {
    const config = THEME_PRESETS[presetName]
    if (config) {
      preset.value = presetName
      layout.value = config.layout
      colorMode.value = config.colorMode
      neonEffects.value = config.neonEffects
      saveToServer()
    }
  }

  // Set individual settings
  function setLayout(newLayout) {
    layout.value = newLayout
    updatePresetFromSettings()
    saveToServer()
  }

  function setColorMode(mode) {
    colorMode.value = mode
    updatePresetFromSettings()
    saveToServer()
  }

  function setNeonEffects(enabled) {
    neonEffects.value = enabled
    updatePresetFromSettings()
    saveToServer()
  }

  function toggleColorMode() {
    setColorMode(isDark.value ? 'light' : 'dark')
  }

  // Determine preset from current settings
  function updatePresetFromSettings() {
    for (const [name, config] of Object.entries(THEME_PRESETS)) {
      if (
        config.layout === layout.value &&
        config.colorMode === colorMode.value &&
        config.neonEffects === neonEffects.value
      ) {
        preset.value = name
        return
      }
    }
    preset.value = 'custom'
  }

  // Load from server
  async function loadFromServer() {
    try {
      const response = await api.get('/api/settings/theme')
      const data = response.data

      if (data.preset && THEME_PRESETS[data.preset]) {
        setPreset(data.preset)
      } else {
        layout.value = data.layout || 'horizontal'
        colorMode.value = data.color_mode || 'light'
        neonEffects.value = data.neon_effects || false
        updatePresetFromSettings()
      }
    } catch (error) {
      // Use defaults or localStorage fallback
      const saved = localStorage.getItem('theme')
      if (saved) {
        try {
          const parsed = JSON.parse(saved)
          layout.value = parsed.layout || 'horizontal'
          colorMode.value = parsed.colorMode || 'light'
          neonEffects.value = parsed.neonEffects || false
          updatePresetFromSettings()
        } catch (e) {
          // Use defaults
        }
      }
    } finally {
      initialized.value = true
      applyTheme()
    }
  }

  // Save to server (debounced)
  let saveTimeout = null
  async function saveToServer() {
    // Also save to localStorage for immediate persistence
    localStorage.setItem('theme', JSON.stringify({
      layout: layout.value,
      colorMode: colorMode.value,
      neonEffects: neonEffects.value,
    }))

    // Debounce server save
    if (saveTimeout) clearTimeout(saveTimeout)
    saveTimeout = setTimeout(async () => {
      try {
        await api.put('/api/settings/theme', {
          preset: preset.value,
          layout: layout.value,
          color_mode: colorMode.value,
          neon_effects: neonEffects.value,
        })
      } catch (error) {
        console.error('Failed to save theme settings:', error)
      }
    }, 500)
  }

  return {
    // State
    layout,
    colorMode,
    neonEffects,
    preset,
    initialized,

    // Computed
    isHorizontalLayout,
    isSidebarLayout,
    isDark,
    isNeonEnabled,
    themeClasses,

    // Actions
    setPreset,
    setLayout,
    setColorMode,
    setNeonEffects,
    toggleColorMode,
    loadFromServer,
    applyTheme,

    // Constants
    THEME_PRESETS,
  }
})
```

---

### Task 3: App.vue with Theme-Aware Layout Switching

**src/App.vue:**
```vue
<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import HorizontalLayout from '@/components/layouts/HorizontalLayout.vue'
import SidebarLayout from '@/components/layouts/SidebarLayout.vue'
import Toast from '@/components/common/Toast.vue'

const route = useRoute()
const authStore = useAuthStore()
const themeStore = useThemeStore()

const isLoginPage = computed(() => route.name === 'login')
const isAuthenticated = computed(() => authStore.isAuthenticated)

// Load theme on mount
onMounted(async () => {
  await themeStore.loadFromServer()
})
</script>

<template>
  <div
    class="min-h-screen transition-colors duration-200"
    :class="[
      themeStore.isDark ? 'bg-slate-950 text-slate-100' : 'bg-gray-50 text-gray-900',
      { 'neon-enabled': themeStore.isNeonEnabled }
    ]"
  >
    <!-- Login page (no layout) -->
    <template v-if="isLoginPage">
      <router-view />
    </template>

    <!-- Authenticated layout -->
    <template v-else-if="isAuthenticated">
      <!-- Horizontal navigation layout (Themes A & B) -->
      <HorizontalLayout v-if="themeStore.isHorizontalLayout">
        <router-view />
      </HorizontalLayout>

      <!-- Sidebar navigation layout (Themes C & D) -->
      <SidebarLayout v-else>
        <router-view />
      </SidebarLayout>
    </template>

    <!-- Toast notifications -->
    <Toast />
  </div>
</template>
```

---

### Task 4: Layout Components

**src/components/layouts/HorizontalLayout.vue:**
```vue
<script setup>
import { useRoute } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import ThemeToggle from '@/components/common/ThemeToggle.vue'
import {
  HomeIcon,
  ArchiveBoxIcon,
  BellIcon,
  CubeIcon,
  ArrowPathIcon,
  ServerIcon,
  Cog6ToothIcon,
} from '@heroicons/vue/24/outline'

const route = useRoute()
const themeStore = useThemeStore()
const authStore = useAuthStore()

const navItems = [
  { name: 'Dashboard', path: '/', icon: HomeIcon },
  { name: 'Backups', path: '/backups', icon: ArchiveBoxIcon },
  { name: 'Notifications', path: '/notifications', icon: BellIcon },
  { name: 'Containers', path: '/containers', icon: CubeIcon },
  { name: 'Flows', path: '/flows', icon: ArrowPathIcon },
  { name: 'System', path: '/system', icon: ServerIcon },
  { name: 'Settings', path: '/settings', icon: Cog6ToothIcon },
]

function isActive(path) {
  return route.path === path
}
</script>

<template>
  <div class="flex flex-col h-screen">
    <!-- Top Navigation Bar -->
    <header
      class="h-16 border-b flex items-center px-6 justify-between"
      :class="themeStore.isDark
        ? 'bg-slate-900 border-slate-700'
        : 'bg-white border-gray-200'"
    >
      <!-- Logo -->
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
          <span class="text-white font-bold text-sm">n8n</span>
        </div>
        <span class="font-semibold text-lg">Management</span>
      </div>

      <!-- Navigation -->
      <nav class="hidden md:flex items-center gap-1">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="px-3 py-2 rounded-md text-sm font-medium transition-colors"
          :class="isActive(item.path)
            ? (themeStore.isDark
                ? 'bg-slate-800 text-white'
                : 'bg-primary-50 text-primary-700')
            : (themeStore.isDark
                ? 'text-slate-300 hover:bg-slate-800 hover:text-white'
                : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900')"
        >
          {{ item.name }}
        </router-link>
      </nav>

      <!-- Right side -->
      <div class="flex items-center gap-4">
        <ThemeToggle />

        <div class="relative">
          <button
            class="flex items-center gap-2 px-3 py-2 rounded-md text-sm"
            :class="themeStore.isDark
              ? 'hover:bg-slate-800'
              : 'hover:bg-gray-100'"
          >
            <span>{{ authStore.user?.username }}</span>
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      </div>
    </header>

    <!-- Main content -->
    <main
      class="flex-1 overflow-y-auto p-6"
      :class="themeStore.isDark ? 'bg-slate-950' : 'bg-gray-50'"
    >
      <slot />
    </main>
  </div>
</template>
```

**src/components/layouts/SidebarLayout.vue:**
```vue
<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import ThemeToggle from '@/components/common/ThemeToggle.vue'
import {
  HomeIcon,
  ArchiveBoxIcon,
  BellIcon,
  CubeIcon,
  ArrowPathIcon,
  ServerIcon,
  Cog6ToothIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@heroicons/vue/24/outline'

const route = useRoute()
const themeStore = useThemeStore()
const authStore = useAuthStore()

const collapsed = ref(false)

const navItems = [
  { name: 'Dashboard', path: '/', icon: HomeIcon, color: 'text-blue-500' },
  { name: 'Backups', path: '/backups', icon: ArchiveBoxIcon, color: 'text-purple-500' },
  { name: 'Notifications', path: '/notifications', icon: BellIcon, color: 'text-amber-500' },
  { name: 'Containers', path: '/containers', icon: CubeIcon, color: 'text-cyan-500' },
  { name: 'Flows', path: '/flows', icon: ArrowPathIcon, color: 'text-green-500' },
  { name: 'System', path: '/system', icon: ServerIcon, color: 'text-indigo-500' },
  { name: 'Settings', path: '/settings', icon: Cog6ToothIcon, color: 'text-slate-500' },
]

function isActive(path) {
  return route.path === path
}

const sidebarWidth = computed(() => collapsed.value ? 'w-16' : 'w-64')
</script>

<template>
  <div class="flex h-screen">
    <!-- Sidebar -->
    <aside
      class="flex flex-col border-r transition-all duration-200"
      :class="[
        sidebarWidth,
        themeStore.isDark
          ? 'bg-slate-900 border-slate-700'
          : 'bg-white border-gray-200'
      ]"
    >
      <!-- Logo -->
      <div class="h-16 flex items-center justify-between px-4 border-b"
           :class="themeStore.isDark ? 'border-slate-700' : 'border-gray-200'">
        <div v-if="!collapsed" class="flex items-center gap-3">
          <div
            class="w-8 h-8 rounded-lg flex items-center justify-center"
            :class="themeStore.isNeonEnabled
              ? 'bg-cyan-500/20 shadow-neon-cyan'
              : 'bg-primary-600'"
          >
            <span class="text-white font-bold text-sm">n8n</span>
          </div>
          <span class="font-semibold">Management</span>
        </div>

        <button
          @click="collapsed = !collapsed"
          class="p-1 rounded hover:bg-slate-700/50"
        >
          <ChevronLeftIcon v-if="!collapsed" class="w-5 h-5" />
          <ChevronRightIcon v-else class="w-5 h-5" />
        </button>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 p-2 space-y-1">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all"
          :class="[
            isActive(item.path)
              ? (themeStore.isDark
                  ? 'bg-slate-800 text-white'
                  : 'bg-primary-50 text-primary-700')
              : (themeStore.isDark
                  ? 'text-slate-400 hover:bg-slate-800 hover:text-white'
                  : 'text-gray-600 hover:bg-gray-100'),
            themeStore.isNeonEnabled && isActive(item.path) ? 'shadow-neon-cyan' : ''
          ]"
        >
          <component
            :is="item.icon"
            class="w-5 h-5 flex-shrink-0"
            :class="[
              item.color,
              themeStore.isNeonEnabled && isActive(item.path) ? 'drop-shadow-[0_0_8px_currentColor]' : ''
            ]"
          />
          <span v-if="!collapsed" class="text-sm font-medium">
            {{ item.name }}
          </span>
        </router-link>
      </nav>

      <!-- User section -->
      <div class="p-4 border-t" :class="themeStore.isDark ? 'border-slate-700' : 'border-gray-200'">
        <div v-if="!collapsed" class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
            <span class="text-sm font-medium text-primary-700">
              {{ authStore.user?.username?.charAt(0).toUpperCase() }}
            </span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium truncate">{{ authStore.user?.username }}</p>
            <p class="text-xs text-slate-500 truncate">Administrator</p>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main area -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Top bar -->
      <header
        class="h-14 border-b flex items-center justify-between px-6"
        :class="themeStore.isDark
          ? 'bg-slate-900 border-slate-700'
          : 'bg-white border-gray-200'"
      >
        <h1 class="text-lg font-semibold">
          {{ route.meta?.title || 'Dashboard' }}
        </h1>

        <div class="flex items-center gap-4">
          <ThemeToggle />
        </div>
      </header>

      <!-- Content -->
      <main
        class="flex-1 overflow-y-auto p-6"
        :class="themeStore.isDark ? 'bg-slate-950' : 'bg-gray-50'"
      >
        <slot />
      </main>
    </div>
  </div>
</template>
```

---

### Task 5: Theme Toggle Component

**src/components/common/ThemeToggle.vue:**
```vue
<script setup>
import { useThemeStore } from '@/stores/theme'
import { SunIcon, MoonIcon } from '@heroicons/vue/24/outline'

const themeStore = useThemeStore()
</script>

<template>
  <button
    @click="themeStore.toggleColorMode()"
    class="p-2 rounded-lg transition-colors"
    :class="themeStore.isDark
      ? 'hover:bg-slate-800 text-slate-400 hover:text-slate-200'
      : 'hover:bg-gray-100 text-gray-500 hover:text-gray-700'"
    :title="themeStore.isDark ? 'Switch to light mode' : 'Switch to dark mode'"
  >
    <SunIcon v-if="themeStore.isDark" class="w-5 h-5" />
    <MoonIcon v-else class="w-5 h-5" />
  </button>
</template>
```

---

### Task 6: Appearance Settings Component

**src/components/settings/AppearanceSettings.vue:**
```vue
<script setup>
import { computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useToast } from '@/composables/useToast'

const themeStore = useThemeStore()
const toast = useToast()

const presets = [
  {
    id: 'modern_light',
    name: 'Modern Light',
    description: 'Clean horizontal navigation with light colors',
    preview: 'bg-gray-100',
  },
  {
    id: 'modern_dark',
    name: 'Modern Dark',
    description: 'Clean horizontal navigation with dark colors',
    preview: 'bg-slate-800',
  },
  {
    id: 'dashboard_light',
    name: 'Dashboard Light',
    description: 'Data-dense sidebar layout with light colors',
    preview: 'bg-gray-100',
  },
  {
    id: 'dashboard_dark_neon',
    name: 'Dashboard Dark + Neon',
    description: 'Data-dense sidebar with neon glow effects',
    preview: 'bg-slate-900',
    hasNeon: true,
  },
]

function selectPreset(presetId) {
  themeStore.setPreset(presetId)
  toast.success('Theme updated')
}
</script>

<template>
  <div class="space-y-6">
    <div
      class="rounded-lg shadow p-6"
      :class="themeStore.isDark ? 'bg-slate-800' : 'bg-white'"
    >
      <h2 class="text-lg font-semibold mb-4">Theme</h2>

      <!-- Preset Selection -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button
          v-for="preset in presets"
          :key="preset.id"
          @click="selectPreset(preset.id)"
          class="p-4 rounded-lg border-2 text-left transition-all"
          :class="[
            themeStore.preset === preset.id
              ? 'border-primary-500 ring-2 ring-primary-500/20'
              : (themeStore.isDark ? 'border-slate-700 hover:border-slate-600' : 'border-gray-200 hover:border-gray-300'),
          ]"
        >
          <!-- Preview bar -->
          <div
            class="h-16 rounded-md mb-3 flex items-center justify-center"
            :class="[
              preset.preview,
              preset.hasNeon ? 'shadow-neon-cyan' : ''
            ]"
          >
            <div class="flex gap-2">
              <div class="w-3 h-3 rounded-full bg-green-500"
                   :class="preset.hasNeon ? 'shadow-neon-success animate-neon-pulse' : ''"></div>
              <div class="w-3 h-3 rounded-full bg-yellow-500"
                   :class="preset.hasNeon ? 'shadow-neon-warning' : ''"></div>
              <div class="w-3 h-3 rounded-full bg-blue-500"
                   :class="preset.hasNeon ? 'shadow-neon-cyan' : ''"></div>
            </div>
          </div>

          <h3 class="font-medium">{{ preset.name }}</h3>
          <p class="text-sm mt-1"
             :class="themeStore.isDark ? 'text-slate-400' : 'text-gray-500'">
            {{ preset.description }}
          </p>

          <!-- Selected indicator -->
          <div v-if="themeStore.preset === preset.id"
               class="mt-2 text-xs font-medium text-primary-500">
            ✓ Active
          </div>
        </button>
      </div>
    </div>

    <!-- Advanced Options -->
    <div
      class="rounded-lg shadow p-6"
      :class="themeStore.isDark ? 'bg-slate-800' : 'bg-white'"
    >
      <h2 class="text-lg font-semibold mb-4">Advanced Options</h2>

      <div class="space-y-4">
        <!-- Layout Mode -->
        <div>
          <label class="block text-sm font-medium mb-2">Layout Style</label>
          <div class="flex gap-4">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="layout"
                value="horizontal"
                :checked="themeStore.layout === 'horizontal'"
                @change="themeStore.setLayout('horizontal')"
                class="text-primary-600"
              />
              <span>Horizontal Navigation</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="layout"
                value="sidebar"
                :checked="themeStore.layout === 'sidebar'"
                @change="themeStore.setLayout('sidebar')"
                class="text-primary-600"
              />
              <span>Sidebar Navigation</span>
            </label>
          </div>
        </div>

        <!-- Color Mode -->
        <div>
          <label class="block text-sm font-medium mb-2">Color Mode</label>
          <div class="flex gap-4">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="colorMode"
                value="light"
                :checked="themeStore.colorMode === 'light'"
                @change="themeStore.setColorMode('light')"
                class="text-primary-600"
              />
              <span>Light</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="colorMode"
                value="dark"
                :checked="themeStore.colorMode === 'dark'"
                @change="themeStore.setColorMode('dark')"
                class="text-primary-600"
              />
              <span>Dark</span>
            </label>
          </div>
        </div>

        <!-- Neon Effects (only show when dark mode) -->
        <div v-if="themeStore.isDark">
          <label class="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              :checked="themeStore.neonEffects"
              @change="themeStore.setNeonEffects($event.target.checked)"
              class="rounded text-primary-600"
            />
            <div>
              <span class="font-medium">Enable Neon Effects</span>
              <p class="text-sm" :class="themeStore.isDark ? 'text-slate-400' : 'text-gray-500'">
                Adds glowing accents to status indicators and buttons
              </p>
            </div>
          </label>
        </div>
      </div>
    </div>
  </div>
</template>
```

---

### Task 7: Update Settings View

**src/views/SettingsView.vue:**
```vue
<script setup>
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useThemeStore } from '@/stores/theme'
import GeneralSettings from '@/components/settings/GeneralSettings.vue'
import AppearanceSettings from '@/components/settings/AppearanceSettings.vue'
import SecuritySettings from '@/components/settings/SecuritySettings.vue'
import EmailSettings from '@/components/settings/EmailSettings.vue'
import NfsSettings from '@/components/settings/NfsSettings.vue'

const settingsStore = useSettingsStore()
const themeStore = useThemeStore()

const activeTab = ref('general')

const tabs = [
  { id: 'general', name: 'General' },
  { id: 'appearance', name: 'Appearance' },
  { id: 'security', name: 'Security' },
  { id: 'email', name: 'Email' },
  { id: 'storage', name: 'Storage' },
]

onMounted(async () => {
  await settingsStore.fetchAll()
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold">Settings</h1>
      <p :class="themeStore.isDark ? 'text-slate-400' : 'text-gray-500'">
        Configure system preferences
      </p>
    </div>

    <!-- Settings navigation -->
    <div class="flex flex-col lg:flex-row gap-6">
      <nav class="lg:w-48 space-y-1">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="activeTab = tab.id"
          class="w-full text-left px-3 py-2 rounded-md text-sm font-medium transition-colors"
          :class="activeTab === tab.id
            ? (themeStore.isDark
                ? 'bg-slate-800 text-white'
                : 'bg-primary-100 text-primary-700')
            : (themeStore.isDark
                ? 'text-slate-400 hover:bg-slate-800 hover:text-white'
                : 'text-gray-600 hover:bg-gray-100')"
        >
          {{ tab.name }}
        </button>
      </nav>

      <div class="flex-1">
        <GeneralSettings v-if="activeTab === 'general'" />
        <AppearanceSettings v-else-if="activeTab === 'appearance'" />
        <SecuritySettings v-else-if="activeTab === 'security'" />
        <EmailSettings v-else-if="activeTab === 'email'" />
        <NfsSettings v-else-if="activeTab === 'storage'" />
      </div>
    </div>
  </div>
</template>
```

---

### Task 8: Theme-Aware CSS

**src/assets/styles/themes.css:**
```css
/* Theme CSS Custom Properties */
:root {
  /* Light mode (default) */
  --color-bg-primary: #ffffff;
  --color-bg-secondary: #f9fafb;
  --color-bg-tertiary: #f3f4f6;
  --color-surface: #ffffff;
  --color-surface-hover: #f9fafb;
  --color-border: #e5e7eb;
  --color-text-primary: #111827;
  --color-text-secondary: #4b5563;
  --color-text-muted: #9ca3af;
}

.dark {
  /* Dark mode */
  --color-bg-primary: #020617;
  --color-bg-secondary: #0f172a;
  --color-bg-tertiary: #1e293b;
  --color-surface: #1e293b;
  --color-surface-hover: #334155;
  --color-border: #334155;
  --color-text-primary: #f1f5f9;
  --color-text-secondary: #94a3b8;
  --color-text-muted: #64748b;
}
```

**src/assets/styles/neon.css:**
```css
/* Neon glow effects for Theme D */
.neon-enabled {
  /* Glow variables */
  --glow-cyan: 0 0 20px rgba(34, 211, 238, 0.5), 0 0 40px rgba(34, 211, 238, 0.3);
  --glow-fuchsia: 0 0 20px rgba(232, 121, 249, 0.5), 0 0 40px rgba(232, 121, 249, 0.3);
  --glow-success: 0 0 15px rgba(52, 211, 153, 0.5);
  --glow-warning: 0 0 15px rgba(251, 191, 36, 0.5);
  --glow-danger: 0 0 15px rgba(251, 113, 133, 0.5);
}

/* Neon status indicators */
.neon-enabled .status-success {
  box-shadow: var(--glow-success);
  animation: neon-pulse 2s ease-in-out infinite;
}

.neon-enabled .status-warning {
  box-shadow: var(--glow-warning);
}

.neon-enabled .status-danger {
  box-shadow: var(--glow-danger);
  animation: neon-pulse 1.5s ease-in-out infinite;
}

/* Neon buttons */
.neon-enabled .btn-primary {
  box-shadow: var(--glow-cyan);
  transition: box-shadow 0.3s ease;
}

.neon-enabled .btn-primary:hover {
  box-shadow: 0 0 30px rgba(34, 211, 238, 0.7), 0 0 60px rgba(34, 211, 238, 0.4);
}

/* Neon cards */
.neon-enabled .card-neon {
  border-color: rgba(34, 211, 238, 0.3);
  box-shadow: inset 0 0 20px rgba(34, 211, 238, 0.05);
}

.neon-enabled .card-neon:hover {
  border-color: rgba(34, 211, 238, 0.5);
  box-shadow: var(--glow-cyan), inset 0 0 30px rgba(34, 211, 238, 0.1);
}

/* Neon charts */
.neon-enabled .chart-line {
  filter: drop-shadow(0 0 6px currentColor);
}

/* Neon pulse animation */
@keyframes neon-pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

/* Grid background for neon theme */
.neon-enabled .neon-grid-bg {
  background-image:
    linear-gradient(rgba(34, 211, 238, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 211, 238, 0.03) 1px, transparent 1px);
  background-size: 50px 50px;
}
```

**src/assets/styles/main.css:**
```css
@import './themes.css';
@import './neon.css';

@tailwind base;
@tailwind components;
@tailwind utilities;

@layer components {
  .btn {
    @apply px-4 py-2 rounded-md font-medium transition-all duration-200
           focus:outline-none focus:ring-2 focus:ring-offset-2
           disabled:opacity-50 disabled:cursor-not-allowed;
  }

  .btn-primary {
    @apply bg-primary-600 text-white hover:bg-primary-700 focus:ring-primary-500;
  }

  .dark .btn-primary {
    @apply bg-primary-500 hover:bg-primary-400;
  }

  .btn-secondary {
    @apply bg-white text-gray-700 border border-gray-300 hover:bg-gray-50
           focus:ring-primary-500;
  }

  .dark .btn-secondary {
    @apply bg-slate-800 text-slate-200 border-slate-600 hover:bg-slate-700;
  }

  .btn-danger {
    @apply bg-danger text-white hover:bg-red-600 focus:ring-red-500;
  }

  /* Cards */
  .card {
    @apply rounded-lg shadow transition-shadow;
  }

  .card-light {
    @apply bg-white border border-gray-200;
  }

  .card-dark {
    @apply bg-slate-800 border border-slate-700;
  }

  /* Form inputs */
  .input {
    @apply block w-full rounded-md shadow-sm sm:text-sm transition-colors;
  }

  .input-light {
    @apply border-gray-300 focus:border-primary-500 focus:ring-primary-500;
  }

  .input-dark {
    @apply bg-slate-800 border-slate-600 text-slate-100
           focus:border-primary-400 focus:ring-primary-400;
  }
}
```

---

## Theme-Aware Component Example

**src/components/dashboard/ContainerCard.vue (Theme-Aware Version):**
```vue
<script setup>
import { computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon
} from '@heroicons/vue/24/solid'

const props = defineProps({
  container: { type: Object, required: true }
})

const themeStore = useThemeStore()

const statusConfig = computed(() => {
  const status = props.container.status
  const health = props.container.health

  if (status === 'running' && health === 'healthy') {
    return {
      icon: CheckCircleIcon,
      color: 'text-emerald-500',
      bgLight: 'bg-emerald-50',
      bgDark: 'bg-emerald-500/10',
      neonClass: 'status-success',
      label: 'Healthy'
    }
  } else if (status === 'running' && health === 'unhealthy') {
    return {
      icon: ExclamationTriangleIcon,
      color: 'text-amber-500',
      bgLight: 'bg-amber-50',
      bgDark: 'bg-amber-500/10',
      neonClass: 'status-warning',
      label: 'Unhealthy'
    }
  } else if (status === 'running') {
    return {
      icon: CheckCircleIcon,
      color: 'text-emerald-500',
      bgLight: 'bg-emerald-50',
      bgDark: 'bg-emerald-500/10',
      neonClass: 'status-success',
      label: 'Running'
    }
  } else if (status === 'restarting') {
    return {
      icon: ArrowPathIcon,
      color: 'text-blue-500',
      bgLight: 'bg-blue-50',
      bgDark: 'bg-blue-500/10',
      neonClass: '',
      label: 'Restarting'
    }
  } else {
    return {
      icon: XCircleIcon,
      color: 'text-rose-500',
      bgLight: 'bg-rose-50',
      bgDark: 'bg-rose-500/10',
      neonClass: 'status-danger',
      label: 'Stopped'
    }
  }
})

const displayName = computed(() => {
  return props.container.name.replace('n8n_', '').replace(/_/g, ' ')
})
</script>

<template>
  <div
    class="rounded-lg border p-4 transition-all duration-200"
    :class="[
      themeStore.isDark
        ? `${statusConfig.bgDark} border-slate-700 hover:border-slate-600`
        : `${statusConfig.bgLight} border-gray-200 hover:border-gray-300`,
      themeStore.isNeonEnabled ? 'card-neon' : ''
    ]"
  >
    <div class="flex items-start justify-between">
      <div>
        <h3 class="font-semibold capitalize"
            :class="themeStore.isDark ? 'text-slate-100' : 'text-gray-900'">
          {{ displayName }}
        </h3>
        <p class="text-sm truncate"
           :class="themeStore.isDark ? 'text-slate-400' : 'text-gray-500'">
          {{ container.image }}
        </p>
      </div>
      <component
        :is="statusConfig.icon"
        class="h-6 w-6"
        :class="[
          statusConfig.color,
          themeStore.isNeonEnabled ? statusConfig.neonClass : ''
        ]"
      />
    </div>

    <div class="mt-3 flex items-center justify-between">
      <span
        class="px-2 py-1 rounded text-xs font-medium"
        :class="[
          themeStore.isDark
            ? `${statusConfig.bgDark} ${statusConfig.color}`
            : `${statusConfig.bgLight} ${statusConfig.color}`
        ]"
      >
        {{ statusConfig.label }}
      </span>

      <div v-if="container.cpu_percent !== undefined"
           class="text-xs"
           :class="themeStore.isDark ? 'text-slate-500' : 'text-gray-500'">
        CPU: {{ container.cpu_percent }}% | Mem: {{ container.memory_percent }}%
      </div>
    </div>
  </div>
</template>
```

---

## Dependencies on Other Agents

- **Backend Agent**: Provides all API endpoints including `/api/settings/theme`
- **Storyboard Agent**: Reference for detailed design specifications per theme
- **Integration Agent**: Will test complete theme switching flows

---

## File Deliverables Checklist

- [ ] All files under `/home/user/n8n_nginx/management/frontend/`
- [ ] Complete project configuration (package.json, vite.config.js, tailwind.config.js)
- [ ] Theme system:
  - [ ] `src/stores/theme.js` - Theme state management
  - [ ] `src/assets/styles/themes.css` - CSS custom properties
  - [ ] `src/assets/styles/neon.css` - Neon glow effects
- [ ] Layout components:
  - [ ] `src/components/layouts/HorizontalLayout.vue`
  - [ ] `src/components/layouts/SidebarLayout.vue`
- [ ] Theme UI:
  - [ ] `src/components/common/ThemeToggle.vue`
  - [ ] `src/components/settings/AppearanceSettings.vue`
- [ ] All Vue components with theme-aware styling
- [ ] Pinia stores for all data domains
- [ ] Vue Router with navigation guards
- [ ] Composables for common patterns
- [ ] Build configuration outputting to `../static`

---

## Important Implementation Notes

1. **All components must be theme-aware** - Use `themeStore.isDark` and `themeStore.isNeonEnabled` to conditionally apply classes
2. **Use Tailwind dark: prefix sparingly** - Prefer conditional classes based on theme store for more control
3. **CSS custom properties** - Use for colors that need to change with theme
4. **Neon effects are additive** - They enhance the dark theme, not replace it
5. **Layout switching is seamless** - Both layouts render the same `<router-view>` content
6. **Persist immediately to localStorage** - For instant theme application on refresh
7. **Debounce server saves** - Avoid API spam when user is experimenting with themes
