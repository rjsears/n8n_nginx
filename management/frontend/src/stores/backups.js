import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'

export const useBackupStore = defineStore('backups', () => {
  // State
  const schedules = ref([])
  const history = ref([])
  const stats = ref(null)
  const loading = ref(false)
  const error = ref(null)

  // Getters
  // Alias for dashboard compatibility
  const backups = computed(() => Array.isArray(history.value) ? history.value : [])

  const recentBackups = computed(() => backups.value.slice(0, 10))

  const lastBackup = computed(() => backups.value[0] || null)

  const successfulBackups = computed(() =>
    backups.value.filter(b => b.status === 'success')
  )

  const failedBackups = computed(() =>
    backups.value.filter(b => b.status === 'failed')
  )

  // Actions
  async function fetchSchedules() {
    loading.value = true
    error.value = null

    try {
      const response = await api.get('/backups/schedules')
      schedules.value = response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch schedules'
    } finally {
      loading.value = false
    }
  }

  async function fetchHistory(params = {}) {
    loading.value = true
    error.value = null

    try {
      const response = await api.get('/backups/history', { params })
      history.value = Array.isArray(response.data) ? response.data : []
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch history'
      history.value = []
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      const response = await api.get('/backups/stats')
      stats.value = response.data
    } catch (err) {
      console.error('Failed to fetch backup stats:', err)
    }
  }

  async function createSchedule(data) {
    try {
      const response = await api.post('/backups/schedules', data)
      schedules.value.push(response.data)
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to create schedule'
      throw err
    }
  }

  async function updateSchedule(id, data) {
    try {
      const response = await api.put(`/backups/schedules/${id}`, data)
      const index = schedules.value.findIndex(s => s.id === id)
      if (index > -1) {
        schedules.value[index] = response.data
      }
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to update schedule'
      throw err
    }
  }

  async function deleteSchedule(id) {
    try {
      await api.delete(`/backups/schedules/${id}`)
      schedules.value = schedules.value.filter(s => s.id !== id)
      return true
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to delete schedule'
      return false
    }
  }

  async function runBackup(backupType, compression = 'gzip') {
    try {
      const response = await api.post('/backups/run', {
        backup_type: backupType,
        compression,
      })
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to run backup'
      throw err
    }
  }

  async function deleteBackup(id) {
    try {
      await api.delete(`/backups/${id}`)
      history.value = history.value.filter(b => b.id !== id)
      return true
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to delete backup'
      return false
    }
  }

  async function verifyBackup(id) {
    try {
      const response = await api.post(`/backups/verification/run/${id}`)
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to verify backup'
      throw err
    }
  }

  function getDownloadUrl(id) {
    return `/api/backups/download/${id}`
  }

  // Phase 2: Backup Contents & Browsing

  async function fetchBackupContents(id) {
    try {
      const response = await api.get(`/backups/contents/${id}`)
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch backup contents'
      throw err
    }
  }

  async function fetchBackupWorkflows(id) {
    try {
      const response = await api.get(`/backups/contents/${id}/workflows`)
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch backup workflows'
      throw err
    }
  }

  async function fetchBackupConfigFiles(id) {
    try {
      const response = await api.get(`/backups/contents/${id}/config-files`)
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch config files'
      throw err
    }
  }

  async function runFullBackup(backupType, compression = 'gzip') {
    try {
      const response = await api.post('/backups/run-full', {
        backup_type: backupType,
        compression,
      })
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to run full backup'
      throw err
    }
  }

  // Phase 7: Backup Protection

  async function protectBackup(id, protected_, reason = null) {
    try {
      const response = await api.post(`/backups/${id}/protect`, {
        protected: protected_,
        reason,
      })
      // Update local state
      const index = history.value.findIndex(b => b.id === id)
      if (index > -1) {
        history.value[index] = { ...history.value[index], ...response.data }
      }
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to protect backup'
      throw err
    }
  }

  async function fetchProtectedBackups() {
    try {
      const response = await api.get('/backups/protected')
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch protected backups'
      throw err
    }
  }

  async function fetchPruningSettings() {
    try {
      const response = await api.get('/backups/pruning/settings')
      return response.data
    } catch (err) {
      if (err.response?.status !== 404) {
        error.value = err.response?.data?.detail || 'Failed to fetch pruning settings'
      }
      return null
    }
  }

  async function updatePruningSettings(data) {
    try {
      const response = await api.put('/backups/pruning/settings', data)
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to update pruning settings'
      throw err
    }
  }

  // Phase 4: Full System Restore

  async function fetchRestorePreview(backupId) {
    try {
      const response = await api.get(`/backups/${backupId}/restore/preview`)
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch restore preview'
      throw err
    }
  }

  async function fetchRestoreConfigFiles(backupId) {
    try {
      const response = await api.get(`/backups/${backupId}/restore/config-files`)
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch config files'
      throw err
    }
  }

  async function restoreConfigFile(backupId, configPath, targetPath = null, createBackup = true) {
    try {
      const response = await api.post(`/backups/${backupId}/restore/config`, {
        config_path: configPath,
        target_path: targetPath,
        create_backup: createBackup,
      })
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to restore config file'
      throw err
    }
  }

  async function restoreDatabase(backupId, databaseName, targetDatabase = null) {
    try {
      const response = await api.post(`/backups/${backupId}/restore/database`, {
        database_name: databaseName,
        target_database: targetDatabase,
      })
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to restore database'
      throw err
    }
  }

  async function fullSystemRestore(backupId, options = {}) {
    try {
      const response = await api.post(`/backups/${backupId}/restore/full`, {
        restore_databases: options.restoreDatabases ?? true,
        restore_configs: options.restoreConfigs ?? true,
        restore_ssl: options.restoreSsl ?? true,
        database_names: options.databaseNames ?? null,
        config_files: options.configFiles ?? null,
        create_backups: options.createBackups ?? true,
      })
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to perform full system restore'
      throw err
    }
  }

  async function restoreWorkflowToN8n(backupId, workflowId, renameFormat = '{name}_backup_{date}') {
    try {
      const response = await api.post(`/backups/${backupId}/restore/workflow`, {
        workflow_id: workflowId,
        rename_format: renameFormat,
      })
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to restore workflow'
      throw err
    }
  }

  async function fetchRestoreStatus() {
    try {
      const response = await api.get('/backups/restore/status')
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch restore status'
      throw err
    }
  }

  async function cleanupRestoreContainer() {
    try {
      const response = await api.post('/backups/restore/cleanup')
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to cleanup restore container'
      throw err
    }
  }

  // Phase 5: Backup Verification

  async function verifyBackup(backupId, options = {}) {
    try {
      const response = await api.post(`/backups/${backupId}/verify`, {
        verify_all_workflows: options.verifyAllWorkflows ?? false,
        workflow_sample_size: options.workflowSampleSize ?? 10,
      })
      // Update local state
      const index = history.value.findIndex(b => b.id === backupId)
      if (index > -1) {
        history.value[index] = {
          ...history.value[index],
          verification_status: response.data.overall_status,
          verification_date: new Date().toISOString(),
        }
      }
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to verify backup'
      throw err
    }
  }

  async function quickVerifyBackup(backupId) {
    try {
      const response = await api.post(`/backups/${backupId}/verify/quick`)
      // Update local state
      const index = history.value.findIndex(b => b.id === backupId)
      if (index > -1) {
        history.value[index] = {
          ...history.value[index],
          verification_status: response.data.overall_status,
          verification_date: new Date().toISOString(),
        }
      }
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to quick verify backup'
      throw err
    }
  }

  async function fetchVerificationStatus(backupId) {
    try {
      const response = await api.get(`/backups/${backupId}/verification/status`)
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch verification status'
      throw err
    }
  }

  async function cleanupVerifyContainer() {
    try {
      const response = await api.post('/backups/verification/cleanup')
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to cleanup verification container'
      throw err
    }
  }

  async function fetchVerifyContainerStatus() {
    try {
      const response = await api.get('/backups/verification/container/status')
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch verification container status'
      throw err
    }
  }

  return {
    // State
    schedules,
    history,
    stats,
    loading,
    error,
    // Getters
    backups,
    lastBackup,
    recentBackups,
    successfulBackups,
    failedBackups,
    // Actions
    fetchSchedules,
    fetchHistory,
    fetchBackups: fetchHistory,  // Alias for dashboard compatibility
    fetchStats,
    createSchedule,
    updateSchedule,
    deleteSchedule,
    runBackup,
    deleteBackup,
    verifyBackup,
    getDownloadUrl,
    // Phase 2: Backup Contents
    fetchBackupContents,
    fetchBackupWorkflows,
    fetchBackupConfigFiles,
    runFullBackup,
    // Phase 7: Protection & Pruning
    protectBackup,
    fetchProtectedBackups,
    fetchPruningSettings,
    updatePruningSettings,
    // Phase 4: Full System Restore
    fetchRestorePreview,
    fetchRestoreConfigFiles,
    restoreConfigFile,
    restoreDatabase,
    fullSystemRestore,
    restoreWorkflowToN8n,
    fetchRestoreStatus,
    cleanupRestoreContainer,
    // Phase 5: Backup Verification
    verifyBackup,
    quickVerifyBackup,
    fetchVerificationStatus,
    cleanupVerifyContainer,
    fetchVerifyContainerStatus,
  }
})
