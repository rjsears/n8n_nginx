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
  InformationCircleIcon,
  BugAntIcon,
} from '@heroicons/vue/24/outline'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const debugStore = useDebugStore()

// About dialog state
const showAbout = ref(false)

const navItems = [
  { name: 'Dashboard', route: 'dashboard', icon: HomeIcon },
  { name: 'Backups', route: 'backups', icon: CloudIcon },
  { name: 'Notifications', route: 'notifications', icon: BellIcon },
  { name: 'Containers', route: 'containers', icon: ServerStackIcon },
  { name: 'Flows', route: 'flows', icon: CubeTransparentIcon },
  { name: 'System', route: 'system', icon: CpuChipIcon },
  { name: 'Settings', route: 'settings', icon: Cog6ToothIcon },
]

const isActive = (routeName) => route.name === routeName

function goToDebugSettings() {
  router.push({ name: 'settings', query: { tab: 'api-debug' } })
}

async function handleLogout() {
  await authStore.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="min-h-screen bg-background-primary">
    <!-- Top Navigation Bar -->
    <header class="sticky top-0 z-[100] border-b border-gray-300 dark:border-slate-500 bg-surface backdrop-blur-sm bg-opacity-95 dark:bg-opacity-95">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div class="flex h-16 items-center justify-between">
          <!-- Logo -->
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <span class="text-xl font-bold text-primary">n8n</span>
              <span class="text-xl font-light text-secondary ml-1">Management</span>
            </div>
          </div>

          <!-- Navigation -->
          <nav class="hidden md:flex items-center space-x-1">
            <router-link
              v-for="item in navItems"
              :key="item.route"
              :to="{ name: item.route }"
              :class="[
                'flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors',
                isActive(item.route)
                  ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
                  : 'text-secondary hover:text-primary hover:bg-surface-hover'
              ]"
            >
              <component :is="item.icon" class="h-5 w-5 mr-1.5" />
              {{ item.name }}
            </router-link>
          </nav>

          <!-- Right side -->
          <div class="flex items-center space-x-3">
            <!-- Debug mode indicator (only shown when active) -->
            <button
              v-if="debugStore.isEnabled"
              @click="goToDebugSettings"
              class="p-2 text-emerald-500 hover:text-emerald-400 transition-colors"
              title="Debug Mode Active - Click to disable"
            >
              <BugAntIcon class="h-5 w-5" />
            </button>

            <!-- About button -->
            <button
              @click="showAbout = true"
              class="p-2 rounded-lg text-secondary hover:text-primary hover:bg-surface-hover transition-colors"
              title="About"
            >
              <InformationCircleIcon class="h-5 w-5" />
            </button>

            <!-- Theme toggle -->
            <button
              @click="themeStore.toggleColorMode"
              class="p-2 rounded-lg text-secondary hover:text-primary hover:bg-surface-hover transition-colors"
            >
              <SunIcon v-if="themeStore.isDark" class="h-5 w-5" />
              <MoonIcon v-else class="h-5 w-5" />
            </button>

            <!-- User menu -->
            <div class="flex items-center space-x-2">
              <span class="text-sm text-secondary hidden sm:block">
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
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <slot />
    </main>

    <!-- About Dialog -->
    <AboutDialog :open="showAbout" @close="showAbout = false" />
  </div>
</template>
