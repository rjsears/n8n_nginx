import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Views
import LoginView from '@/views/LoginView.vue'
import DashboardView from '@/views/DashboardView.vue'
import BackupsView from '@/views/BackupsView.vue'
import NotificationsView from '@/views/NotificationsView.vue'
import ContainersView from '@/views/ContainersView.vue'
import FlowsView from '@/views/FlowsView.vue'
import SystemView from '@/views/SystemView.vue'
import SettingsView from '@/views/SettingsView.vue'
import NtfyView from '@/views/NtfyView.vue'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { guest: true },
  },
  {
    path: '/',
    name: 'dashboard',
    component: DashboardView,
    meta: { requiresAuth: true },
  },
  {
    path: '/backups',
    name: 'backups',
    component: BackupsView,
    meta: { requiresAuth: true },
  },
  {
    path: '/notifications',
    name: 'notifications',
    component: NotificationsView,
    meta: { requiresAuth: true },
  },
  {
    path: '/containers',
    name: 'containers',
    component: ContainersView,
    meta: { requiresAuth: true },
  },
  {
    path: '/flows',
    name: 'flows',
    component: FlowsView,
    meta: { requiresAuth: true },
  },
  {
    path: '/system',
    name: 'system',
    component: SystemView,
    meta: { requiresAuth: true },
  },
  {
    path: '/settings',
    name: 'settings',
    component: SettingsView,
    meta: { requiresAuth: true },
  },
  {
    path: '/ntfy',
    name: 'ntfy',
    component: NtfyView,
    meta: { requiresAuth: true },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory('/management/'),
  routes,
})

// Navigation guard
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // Initialize auth if not done yet
  if (!authStore.user && authStore.token) {
    await authStore.fetchCurrentUser()
  }

  // Check if route requires auth
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'login', query: { redirect: to.fullPath } })
  }
  // Check if route is guest-only (like login)
  else if (to.meta.guest && authStore.isAuthenticated) {
    next({ name: 'dashboard' })
  }
  else {
    next()
  }
})

export default router
