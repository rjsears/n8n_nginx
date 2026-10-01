/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/stores/auth.js

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
*/

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'

// The session token lives only in the HttpOnly "session" cookie set by the
// API at login; page scripts never see it. This store only knows who is
// logged in. Older builds kept a copy in localStorage - remove it.
const LEGACY_TOKEN_KEY = 'auth_token'
// Cross-tab signal: writing this key fires a "storage" event in other tabs
const AUTH_EVENT_KEY = 'auth_event'

function removeLegacyToken() {
  try {
    localStorage.removeItem(LEGACY_TOKEN_KEY)
  } catch {
    // Storage unavailable (private mode etc.)
  }
}

function broadcast(type) {
  try {
    localStorage.setItem(AUTH_EVENT_KEY, JSON.stringify({ type, at: Date.now() }))
  } catch {
    // Storage unavailable: other tabs will notice on their next 401
  }
}

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref(null)
  const loading = ref(false)
  const error = ref(null)
  // True once /auth/me has answered (either way) during this page load
  const checked = ref(false)
  // True while the API cannot be reached (network error, 5xx). The session is
  // kept: a restarting API must not log everybody out.
  const apiUnreachable = ref(false)

  removeLegacyToken()

  // Getters
  const isAuthenticated = computed(() => !!user.value)
  const username = computed(() => user.value?.username || '')

  // Forget the logged-in user locally (the server-side session is already
  // gone or is being ended separately).
  function clearSession() {
    user.value = null
    checked.value = true
    removeLegacyToken()
  }

  // Actions
  async function login(credentials) {
    loading.value = true
    error.value = null

    try {
      const response = await api.post('/auth/login', credentials)
      user.value = response.data.user
      checked.value = true
      apiUnreachable.value = false
      broadcast('login')
      return true
    } catch (err) {
      error.value = err.response?.data?.detail || 'Login failed'
      return false
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try {
      await api.post('/auth/logout', null, { skipAuthRedirect: true })
    } catch {
      // Ignore errors during logout
    } finally {
      clearSession()
      broadcast('logout')
    }
  }

  /**
   * Ask the API who is logged in.
   * Returns true (valid session), false (no/expired session: store cleared)
   * or null (API unreachable: state left as it was).
   * Pass { redirect: false } when the caller handles navigation itself.
   */
  async function fetchCurrentUser({ redirect = true } = {}) {
    try {
      const response = await api.get('/auth/me', { skipAuthRedirect: !redirect })
      user.value = response.data
      checked.value = true
      apiUnreachable.value = false
      return true
    } catch (err) {
      if (err.response?.status === 401) {
        // The interceptor already cleared the session (and redirected,
        // unless told not to)
        clearSession()
        apiUnreachable.value = false
        return false
      }
      // Network error, 502/503 during a restart, timeout...: keep the session
      apiUnreachable.value = true
      return null
    }
  }

  async function changePassword(currentPassword, newPassword) {
    loading.value = true
    error.value = null

    try {
      await api.put('/auth/password', {
        current_password: currentPassword,
        new_password: newPassword,
      })
      return true
    } catch (err) {
      error.value = err.response?.data?.detail || 'Password change failed'
      return false
    } finally {
      loading.value = false
    }
  }

  // Initialize: find out whether the session cookie is still good
  async function init() {
    if (!checked.value) {
      await fetchCurrentUser({ redirect: false })
    }
  }

  return {
    // State
    user,
    loading,
    error,
    checked,
    apiUnreachable,
    // Getters
    isAuthenticated,
    username,
    // Actions
    login,
    logout,
    clearSession,
    fetchCurrentUser,
    changePassword,
    init,
  }
})

export { AUTH_EVENT_KEY }
