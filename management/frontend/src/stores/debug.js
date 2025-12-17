import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/services/api'

export const useDebugStore = defineStore('debug', () => {
  const isEnabled = ref(false)
  const loading = ref(false)

  async function loadDebugMode() {
    try {
      const response = await api.settings.getDebugMode()
      isEnabled.value = response.data.enabled
    } catch (error) {
      console.error('Failed to load debug mode:', error)
    }
  }

  async function toggleDebugMode() {
    loading.value = true
    try {
      const newValue = !isEnabled.value
      await api.settings.setDebugMode(newValue)
      isEnabled.value = newValue
      return true
    } catch (error) {
      console.error('Failed to update debug mode:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    isEnabled,
    loading,
    loadDebugMode,
    toggleDebugMode,
  }
})
