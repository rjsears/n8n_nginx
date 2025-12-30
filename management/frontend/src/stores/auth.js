/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/stores/auth.js

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
*/

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref(null)
  const token = ref(localStorage.getItem('auth_token'))
  const loading = ref(false)
  const error = ref(null)

  // Getters
  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const username = computed(() => user.value?.username || '')

  // Actions
  async function login(credentials) {
    loading.value = true
    error.value = null

    try {
      const response = await api.post('/auth/login', credentials)
      token.value = response.data.token
      user.value = response.data.user
      localStorage.setItem('auth_token', response.data.token)
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
      await api.post('/auth/logout')
    } catch {
      // Ignore errors during logout
    } finally {
      token.value = null
      user.value = null
      localStorage.removeItem('auth_token')
    }
  }

  async function fetchCurrentUser() {
    if (!token.value) return false

    try {
      const response = await api.get('/auth/me')
      user.value = response.data
      return true
    } catch {
      // Token invalid, clear it
      token.value = null
      user.value = null
      localStorage.removeItem('auth_token')
      return false
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

  // Initialize: try to fetch current user if token exists
  async function init() {
    if (token.value) {
      await fetchCurrentUser()
    }
  }

  return {
    // State
    user,
    token,
    loading,
    error,
    // Getters
    isAuthenticated,
    username,
    // Actions
    login,
    logout,
    fetchCurrentUser,
    changePassword,
    init,
  }
})
