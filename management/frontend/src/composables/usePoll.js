/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/composables/usePoll.js

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
*/

import { onMounted, onUnmounted, ref } from 'vue'

/**
 * Composable for handling polling logic
 * @param {Function} callback - Function to execute
 * @param {number} interval - Polling interval in ms
 * @param {boolean} immediate - Whether to execute immediately on mount
 */
export function usePoll(callback, interval = 30000, immediate = true) {
  const timer = ref(null)
  const isPolling = ref(false)

  const start = () => {
    if (timer.value) return
    isPolling.value = true
    timer.value = setInterval(() => {
      // Don't poll if document is hidden to save resources
      if (!document.hidden) {
        callback()
      }
    }, interval)
  }

  const stop = () => {
    if (timer.value) {
      clearInterval(timer.value)
      timer.value = null
      isPolling.value = false
    }
  }

  const restart = (newInterval) => {
    stop()
    if (newInterval) interval = newInterval
    start()
  }

  onMounted(() => {
    if (immediate) {
      callback()
    }
    start()
    
    // Listen for visibility changes
    document.addEventListener('visibilitychange', handleVisibilityChange)
  })

  onUnmounted(() => {
    stop()
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  })

  function handleVisibilityChange() {
    if (document.hidden) {
      // Optional: could stop polling immediately when hidden
      // relying on the check inside setInterval for now
    } else {
      // If we became visible, maybe trigger an immediate update?
      // callback()
    }
  }

  return {
    start,
    stop,
    restart,
    isPolling
  }
}
