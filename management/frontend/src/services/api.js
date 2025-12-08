import axios from 'axios'
import router from '@/router'

// Create axios instance
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle 401 Unauthorized - redirect to login
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      // Only redirect if not already on login page
      if (router.currentRoute.value.name !== 'login') {
        router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
      }
    }

    // Handle 403 Forbidden
    if (error.response?.status === 403) {
      console.error('Access forbidden:', error.response?.data?.detail)
    }

    // Handle 429 Too Many Requests
    if (error.response?.status === 429) {
      console.error('Rate limited:', error.response?.data?.detail)
    }

    return Promise.reject(error)
  }
)

export default api

// Convenience methods for common endpoints
export const authApi = {
  login: (credentials) => api.post('/auth/login', credentials),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
  changePassword: (data) => api.put('/auth/password', data),
  getSessions: () => api.get('/auth/sessions'),
  getSubnets: () => api.get('/auth/subnets'),
  addSubnet: (data) => api.post('/auth/subnets', data),
  deleteSubnet: (id) => api.delete(`/auth/subnets/${id}`),
}

export const systemApi = {
  health: () => api.get('/system/health'),
  metrics: () => api.get('/system/metrics'),
  info: () => api.get('/system/info'),
  dockerInfo: () => api.get('/system/docker/info'),
  audit: (params) => api.get('/system/audit', { params }),
}

export const backupsApi = {
  getSchedules: () => api.get('/backups/schedules'),
  createSchedule: (data) => api.post('/backups/schedules', data),
  updateSchedule: (id, data) => api.put(`/backups/schedules/${id}`, data),
  deleteSchedule: (id) => api.delete(`/backups/schedules/${id}`),
  getHistory: (params) => api.get('/backups/history', { params }),
  runBackup: (data) => api.post('/backups/run', data),
  deleteBackup: (id) => api.delete(`/backups/${id}`),
  verifyBackup: (id) => api.post(`/backups/verification/run/${id}`),
  getStats: () => api.get('/backups/stats'),
  getRetention: () => api.get('/backups/retention'),
  updateRetention: (type, data) => api.put(`/backups/retention/${type}`, data),
}

export const containersApi = {
  list: (all = true) => api.get('/containers/', { params: { all } }),
  get: (name) => api.get(`/containers/${name}`),
  stats: () => api.get('/containers/stats'),
  health: () => api.get('/containers/health'),
  start: (name) => api.post(`/containers/${name}/start`),
  stop: (name) => api.post(`/containers/${name}/stop`),
  restart: (name) => api.post(`/containers/${name}/restart`),
  logs: (name, params) => api.get(`/containers/${name}/logs`, { params }),
}

export const notificationsApi = {
  getServices: () => api.get('/notifications/services'),
  createService: (data) => api.post('/notifications/services', data),
  updateService: (id, data) => api.put(`/notifications/services/${id}`, data),
  deleteService: (id) => api.delete(`/notifications/services/${id}`),
  testService: (id, data) => api.post(`/notifications/services/${id}/test`, data),
  getRules: () => api.get('/notifications/rules'),
  createRule: (data) => api.post('/notifications/rules', data),
  updateRule: (id, data) => api.put(`/notifications/rules/${id}`, data),
  deleteRule: (id) => api.delete(`/notifications/rules/${id}`),
  getEventTypes: () => api.get('/notifications/event-types'),
  getHistory: (params) => api.get('/notifications/history', { params }),
}

export const emailApi = {
  getConfig: () => api.get('/email/config'),
  updateConfig: (data) => api.put('/email/config', data),
  test: (data) => api.post('/email/test', data),
  getTemplates: () => api.get('/email/templates'),
  updateTemplate: (key, data) => api.put(`/email/templates/${key}`, data),
  previewTemplate: (data) => api.post('/email/templates/preview', data),
}

export const flowsApi = {
  list: (activeOnly = false) => api.get('/flows/list', { params: { active_only: activeOnly } }),
  export: (id) => api.get(`/flows/export/${id}`),
  exportBulk: (ids) => api.post('/flows/export/bulk', { flow_ids: ids }),
  stats: () => api.get('/flows/stats'),
}

export const settingsApi = {
  list: (category) => api.get('/settings/', { params: { category } }),
  get: (key) => api.get(`/settings/${key}`),
  update: (key, data) => api.put(`/settings/${key}`, data),
  getConfig: (type) => api.get(`/settings/config/${type}`),
  updateConfig: (type, data) => api.put(`/settings/config/${type}`, data),
  getNfsStatus: () => api.get('/settings/nfs/status'),
  updateNfsConfig: (data) => api.put('/settings/nfs/config', data),
}
