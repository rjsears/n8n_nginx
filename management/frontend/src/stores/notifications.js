/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/stores/notifications.js

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
*/

import { defineStore } from 'pinia'
import { ref } from 'vue'

// Toast notification store
export const useNotificationStore = defineStore('notifications', () => {
  const toasts = ref([])
  let nextId = 0

  function addToast(message, type = 'info', duration = 5000) {
    const id = nextId++
    const toast = {
      id,
      message,
      type, // 'success', 'error', 'warning', 'info'
      duration,
    }

    toasts.value.push(toast)

    if (duration > 0) {
      setTimeout(() => {
        removeToast(id)
      }, duration)
    }

    return id
  }

  function removeToast(id) {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index > -1) {
      toasts.value.splice(index, 1)
    }
  }

  function success(message, duration = 5000) {
    return addToast(message, 'success', duration)
  }

  function error(message, duration = 8000) {
    return addToast(message, 'error', duration)
  }

  function warning(message, duration = 6000) {
    return addToast(message, 'warning', duration)
  }

  function info(message, duration = 5000) {
    return addToast(message, 'info', duration)
  }

  function clear() {
    toasts.value = []
  }

  return {
    toasts,
    addToast,
    removeToast,
    success,
    error,
    warning,
    info,
    clear,
  }
})
