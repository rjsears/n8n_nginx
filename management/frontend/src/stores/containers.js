/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/stores/containers.js

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

export const useContainerStore = defineStore('containers', () => {
  // State
  const containers = ref([])
  const stats = ref([])
  const loading = ref(false)
  const error = ref(null)
  const lastUpdated = ref(null)

  // Getters - with defensive array checks
  const containerList = computed(() =>
    Array.isArray(containers.value) ? containers.value : []
  )

  const runningCount = computed(() =>
    containerList.value.filter(c => c.status === 'running').length
  )

  const stoppedCount = computed(() =>
    containerList.value.filter(c => c.status !== 'running').length
  )

  const unhealthyCount = computed(() =>
    containerList.value.filter(c => c.health === 'unhealthy').length
  )

  const allHealthy = computed(() =>
    containerList.value.length > 0 && containerList.value.every(c =>
      c.status === 'running' && c.health !== 'unhealthy'
    )
  )

  // Actions
  async function fetchContainers() {
    loading.value = true
    error.value = null

    try {
      // Explicitly pass all=true to include stopped containers
      const response = await api.get('/containers/', { params: { all: true } })
      containers.value = Array.isArray(response.data) ? response.data : []
      lastUpdated.value = new Date()
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch containers'
      containers.value = []
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      const response = await api.get('/containers/stats')
      stats.value = response.data
    } catch (err) {
      console.error('Failed to fetch container stats:', err)
    }
  }

  async function startContainer(name) {
    try {
      await api.post(`/containers/${name}/start`)
      await fetchContainers()
      return true
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to start container'
      return false
    }
  }

  async function stopContainer(name) {
    try {
      await api.post(`/containers/${name}/stop`)
      await fetchContainers()
      return true
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to stop container'
      return false
    }
  }

  async function restartContainer(name) {
    try {
      await api.post(`/containers/${name}/restart`)
      await fetchContainers()
      return true
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to restart container'
      return false
    }
  }

  async function removeContainer(name) {
    try {
      await api.delete(`/containers/${name}`)
      // Small delay to ensure Docker has fully removed the container
      await new Promise(resolve => setTimeout(resolve, 500))
      await fetchContainers()
      return true
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to remove container'
      return false
    }
  }

  async function recreateContainer(name, pull = false) {
    try {
      const response = await api.post(`/containers/${name}/recreate`, null, {
        params: { pull }
      })
      await fetchContainers()
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to recreate container'
      throw err
    }
  }

  async function getLogs(name, options = {}) {
    try {
      const params = {}
      // Support both 'tail' and 'lines' parameter names
      if (options.lines !== undefined) {
        params.tail = options.lines
      } else if (options.tail !== undefined) {
        params.tail = options.tail
      } else {
        params.tail = 100
      }
      // Add since parameter if provided
      if (options.since) {
        params.since = options.since
      }
      const response = await api.get(`/containers/${name}/logs`, { params })
      return response.data.logs
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch logs'
      return null
    }
  }

  function getContainerByName(name) {
    return containers.value.find(c => c.name === name)
  }

  function getStatsByName(name) {
    return stats.value.find(s => s.name === name)
  }

  return {
    // State
    containers,
    stats,
    loading,
    error,
    lastUpdated,
    // Getters
    runningCount,
    stoppedCount,
    unhealthyCount,
    allHealthy,
    // Actions
    fetchContainers,
    fetchStats,
    startContainer,
    stopContainer,
    restartContainer,
    removeContainer,
    recreateContainer,
    getLogs,
    getContainerLogs: getLogs,  // Alias for ContainersView compatibility
    getContainerByName,
    getStatsByName,
  }
})
