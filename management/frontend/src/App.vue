<script setup>
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import HorizontalLayout from '@/components/layouts/HorizontalLayout.vue'
import SidebarLayout from '@/components/layouts/SidebarLayout.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'

const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()

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
