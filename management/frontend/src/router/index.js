/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/router/index.js

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
*/

import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { guest: true },
  },
  {
    path: '/',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/backups',
    name: 'backups',
    component: () => import('../views/BackupsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/backup-settings',
    name: 'backup-settings',
    component: () => import('../views/BackupSettingsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/notifications',
    name: 'notifications',
    component: () => import('../views/NotificationsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/containers',
    name: 'containers',
    component: () => import('../views/ContainersView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/flows',
    name: 'flows',
    component: () => import('../views/FlowsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/system',
    name: 'system',
    component: () => import('../views/SystemView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/file-browser',
    name: 'file-browser',
    component: () => import('../views/FileBrowserView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('../views/SettingsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    // Redirect /ntfy to notifications with ntfy tab
    path: '/ntfy',
    redirect: { name: 'notifications', query: { tab: 'ntfy' } },
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
