<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useDebugStore } from '@/stores/debug'
import AboutDialog from '@/components/common/AboutDialog.vue'
import {
  HomeIcon,
  CloudIcon,
  BellIcon,
  ServerStackIcon,
  CubeTransparentIcon,
  CpuChipIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon,
  SunIcon,
  MoonIcon,
  Bars3Icon,
  XMarkIcon,
  InformationCircleIcon,
  BugAntIcon,
  MegaphoneIcon,
} from '@heroicons/vue/24/outline'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const debugStore = useDebugStore()

// About dialog state
const showAbout = ref(false)

const navItems = [
  { name: 'Dashboard', route: 'dashboard', icon: HomeIcon, color: 'text-blue-500' },
  { name: 'Backups', route: 'backups', icon: CloudIcon, color: 'text-emerald-500' },
  { name: 'Notifications', route: 'notifications', icon: BellIcon, color: 'text-amber-500' },
  { name: 'NTFY', route: 'ntfy', icon: MegaphoneIcon, color: 'text-orange-500' },
  { name: 'Containers', route: 'containers', icon: ServerStackIcon, color: 'text-purple-500' },
  { name: 'Flows', route: 'flows', icon: CubeTransparentIcon, color: 'text-cyan-500' },
  { name: 'System', route: 'system', icon: CpuChipIcon, color: 'text-rose-500' },
  { name: 'Settings', route: 'settings', icon: Cog6ToothIcon, color: 'text-gray-500' },
]

const isActive = (routeName) => route.name === routeName

const sidebarWidth = computed(() =>
  themeStore.sidebarCollapsed ? 'w-16' : 'w-64'
)

function goToDebugSettings() {
  router.push({ name: 'settings', query: { tab: 'api-debug' } })
}

async function handleLogout() {
  await authStore.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="min-h-screen bg-background-primary flex">
    <!-- Sidebar -->
    <aside
      :class="[
        sidebarWidth,
        'fixed inset-y-0 left-0 z-50 flex flex-col transition-all duration-300',
        'bg-background-secondary border-r border-gray-300 dark:border-black'
      ]"
    >
      <!-- Logo -->
      <div class="flex h-16 items-center justify-between px-4 border-b border-gray-300 dark:border-black">
        <div v-if="!themeStore.sidebarCollapsed" class="flex items-center">
          <span class="text-xl font-bold text-primary">n8n</span>
          <span class="text-xl font-light text-secondary ml-1">Mgmt</span>
        </div>
        <button
          @click="themeStore.toggleSidebar"
          class="p-1.5 rounded-lg text-secondary hover:text-primary hover:bg-surface-hover transition-colors"
        >
          <XMarkIcon v-if="!themeStore.sidebarCollapsed" class="h-5 w-5" />
          <Bars3Icon v-else class="h-5 w-5" />
        </button>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 py-4 space-y-1 px-2 overflow-y-auto">
        <router-link
          v-for="item in navItems"
          :key="item.route"
          :to="{ name: item.route }"
          :class="[
            'flex items-center rounded-lg transition-all duration-200',
            themeStore.sidebarCollapsed ? 'justify-center px-2 py-3' : 'px-3 py-2.5',
            isActive(item.route)
              ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-l-2 border-blue-500'
              : 'text-secondary hover:text-primary hover:bg-surface-hover'
          ]"
          :title="themeStore.sidebarCollapsed ? item.name : ''"
        >
          <component
            :is="item.icon"
            :class="[
              'h-5 w-5 flex-shrink-0',
              isActive(item.route) ? item.color : ''
            ]"
          />
          <span
            v-if="!themeStore.sidebarCollapsed"
            class="ml-3 text-sm font-medium"
          >
            {{ item.name }}
          </span>
        </router-link>
      </nav>

      <!-- Bottom section -->
      <div class="border-t border-gray-300 dark:border-black p-2 space-y-1">
        <!-- Controls -->
        <div :class="['flex items-center', themeStore.sidebarCollapsed ? 'flex-col space-y-2' : 'justify-between px-2']">
          <!-- Debug mode indicator (only shown when active) -->
          <button
            v-if="debugStore.isEnabled"
            @click="goToDebugSettings"
            class="p-2 text-emerald-500 hover:text-emerald-400 transition-colors"
            title="Debug Mode Active - Click to disable"
          >
            <BugAntIcon class="h-5 w-5" />
          </button>

          <button
            @click="showAbout = true"
            class="p-2 rounded-lg text-secondary hover:text-primary hover:bg-surface-hover transition-colors"
            title="About"
          >
            <InformationCircleIcon class="h-5 w-5" />
          </button>

          <button
            @click="themeStore.toggleColorMode"
            class="p-2 rounded-lg text-secondary hover:text-primary hover:bg-surface-hover transition-colors"
            title="Toggle dark mode"
          >
            <SunIcon v-if="themeStore.isDark" class="h-5 w-5" />
            <MoonIcon v-else class="h-5 w-5" />
          </button>
        </div>

        <!-- User & Logout -->
        <div :class="['flex items-center', themeStore.sidebarCollapsed ? 'justify-center' : 'px-2']">
          <span v-if="!themeStore.sidebarCollapsed" class="text-sm text-secondary truncate mr-2">
            {{ authStore.username }}
          </span>
          <button
            @click="handleLogout"
            class="p-2 rounded-lg text-secondary hover:text-red-500 hover:bg-red-500/10 transition-colors"
            title="Logout"
          >
            <ArrowRightOnRectangleIcon class="h-5 w-5" />
          </button>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main
      :class="[
        'flex-1 transition-all duration-300',
        themeStore.sidebarCollapsed ? 'ml-16' : 'ml-64'
      ]"
    >
      <div class="p-6 lg:p-8">
        <slot />
      </div>
    </main>

    <!-- About Dialog -->
    <AboutDialog :open="showAbout" @close="showAbout = false" />
  </div>
</template>
