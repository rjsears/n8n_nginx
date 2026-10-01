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
import { useAuthStore, AUTH_EVENT_KEY } from '../stores/auth'

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

  // First navigation of this page load: ask the API whether the session
  // cookie is still valid (the token itself is not readable from JS).
  if (!authStore.checked) {
    await authStore.fetchCurrentUser({ redirect: false })
  }

  // Check if route requires auth
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'login', query: { redirect: to.fullPath } })
  }
  // Guest-only route (login) while we believe we are logged in: confirm with
  // the API before bouncing away, so a stale store can never keep an expired
  // session away from the login page. Unreachable API -> show the login page.
  else if (to.meta.guest && authStore.isAuthenticated) {
    const valid = await authStore.fetchCurrentUser({ redirect: false })
    if (valid === true) {
      next(safeRedirect(to.query.redirect) || { name: 'dashboard' })
    } else {
      next()
    }
  }
  else {
    next()
  }
})

// Only follow same-app relative redirects ("/backups?x=1"), never
// "//evil.example" or "https://..." style values from the query string.
export function safeRedirect(value) {
  if (typeof value !== 'string') return null
  if (!value.startsWith('/') || value.startsWith('//') || value.startsWith('/\\')) return null
  if (value.startsWith('/login')) return null
  return value
}

// Logout / login in another tab
window.addEventListener('storage', (event) => {
  if (event.key !== AUTH_EVENT_KEY || !event.newValue) return
  const authStore = useAuthStore()
  let type = null
  try {
    type = JSON.parse(event.newValue).type
  } catch {
    return
  }
  if (type === 'logout') {
    authStore.clearSession()
    if (router.currentRoute.value.name !== 'login') {
      router.replace({ name: 'login' }).catch(() => {})
    }
  } else if (type === 'login' && !authStore.isAuthenticated) {
    authStore.fetchCurrentUser({ redirect: false }).then((valid) => {
      if (valid === true && router.currentRoute.value.name === 'login') {
        router.replace(safeRedirect(router.currentRoute.value.query.redirect) || { name: 'dashboard' }).catch(() => {})
      }
    })
  }
})

export default router
