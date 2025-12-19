import axios from 'axios'
import router from '@/router'

// Determine API base URL based on current path
// If accessed via /management/, use /management/api, otherwise use /api
const getBaseUrl = () => {
  const path = window.location.pathname
  if (path.startsWith('/management')) {
    return '/management/api'
  }
  return '/api'
}

// Create axios instance
const api = axios.create({
  baseURL: getBaseUrl(),
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
  healthFull: () => api.get('/system/health/full'),
  metrics: () => api.get('/system/metrics'),
  info: () => api.get('/system/info'),
  dockerInfo: () => api.get('/system/docker/info'),
  audit: (params) => api.get('/system/audit', { params }),
  network: () => api.get('/system/network'),
  ssl: () => api.get('/system/ssl'),
  sslRenew: () => api.post('/system/ssl/renew'),
  cloudflare: () => api.get('/system/cloudflare'),
  tailscale: () => api.get('/system/tailscale'),
  terminalTargets: () => api.get('/system/terminal/targets'),
  externalServices: () => api.get('/system/external-services'),
  debug: () => api.get('/system/debug'),
  // Host metrics from database cache (collected via psutil + Docker API)
  hostMetricsCached: (historyMinutes = 60) => api.get('/system/host-metrics/cached', { params: { history_minutes: historyMinutes } }),
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
  // Channels (Services)
  getServices: () => api.get('/notifications/services'),
  createService: (data) => api.post('/notifications/services', data),
  updateService: (id, data) => api.put(`/notifications/services/${id}`, data),
  deleteService: (id) => api.delete(`/notifications/services/${id}`),
  testService: (id, data) => api.post(`/notifications/services/${id}/test`, data),
  // Groups
  getGroups: () => api.get('/notifications/groups'),
  getGroup: (id) => api.get(`/notifications/groups/${id}`),
  createGroup: (data) => api.post('/notifications/groups', data),
  updateGroup: (id, data) => api.put(`/notifications/groups/${id}`, data),
  deleteGroup: (id) => api.delete(`/notifications/groups/${id}`),
  // Rules
  getRules: () => api.get('/notifications/rules'),
  createRule: (data) => api.post('/notifications/rules', data),
  updateRule: (id, data) => api.put(`/notifications/rules/${id}`, data),
  deleteRule: (id) => api.delete(`/notifications/rules/${id}`),
  getEventTypes: () => api.get('/notifications/event-types'),
  getHistory: (params) => api.get('/notifications/history', { params }),
  // Webhook integration for n8n workflows
  getWebhookInfo: () => api.get('/notifications/webhook/info'),
  sendWebhook: (data) => api.post('/notifications/webhook', data),
  generateWebhookKey: () => api.post('/notifications/webhook/generate-key'),
  regenerateWebhookKey: () => api.post('/notifications/webhook/regenerate-key'),
  // n8n API integration
  getN8nStatus: () => api.get('/notifications/webhook/n8n-status'),
  createTestWorkflow: (workflowType = 'broadcast') => api.post(`/notifications/webhook/create-test-workflow?workflow_type=${workflowType}`),
  createAllTestWorkflows: () => api.post('/notifications/webhook/create-all-test-workflows'),
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
  // Environment variable management
  getEnvVariables: () => api.get('/settings/env'),
  getEnvVariable: (key) => api.get(`/settings/env/${key}`),
  updateEnvVariable: (key, value) => api.put(`/settings/env/${key}`, { key, value }),
  // Debug mode
  getDebugMode: () => api.get('/settings/debug'),
  setDebugMode: (enabled) => api.put('/settings/debug', { enabled }),
  // Container restart (uses containers API)
  restartContainer: (containerName, reason) => api.post(`/containers/${containerName}/restart`),
  // Access Control
  getAccessControl: () => api.get('/settings/access-control'),
  updateAccessControl: (data) => api.put('/settings/access-control', data),
  addIpRange: (data) => api.post('/settings/access-control/ip', data),
  updateIpRange: (cidr, description) => api.put(`/settings/access-control/ip/${encodeURIComponent(cidr)}`, { description }),
  deleteIpRange: (cidr) => api.delete(`/settings/access-control/ip/${encodeURIComponent(cidr)}`),
  reloadNginx: () => api.post('/settings/access-control/reload-nginx'),
  getDefaultIpRanges: () => api.get('/settings/access-control/defaults'),
  // External Routes
  getExternalRoutes: () => api.get('/settings/external-routes'),
  addExternalRoute: (data) => api.post('/settings/external-routes', data),
  deleteExternalRoute: (path) => api.delete(`/settings/external-routes/${path.replace(/^\//, '')}`),
  // Aliases for view compatibility
  getAll: () => api.get('/settings/'),
}

export const ntfyApi = {
  // Health & Status
  health: () => api.get('/ntfy/health'),
  status: () => api.get('/ntfy/status'),
  // Messages
  send: (data) => api.post('/ntfy/send', data),
  sendTemplate: (data) => api.post('/ntfy/send-template', data),
  // Templates
  getTemplates: (type) => api.get('/ntfy/templates', { params: { template_type: type } }),
  getTemplate: (id) => api.get(`/ntfy/templates/${id}`),
  createTemplate: (data) => api.post('/ntfy/templates', data),
  updateTemplate: (id, data) => api.put(`/ntfy/templates/${id}`, data),
  deleteTemplate: (id) => api.delete(`/ntfy/templates/${id}`),
  previewTemplate: (data) => api.post('/ntfy/templates/preview', data),
  // Topics
  getTopics: () => api.get('/ntfy/topics'),
  createTopic: (data) => api.post('/ntfy/topics', data),
  updateTopic: (id, data) => api.put(`/ntfy/topics/${id}`, data),
  deleteTopic: (id) => api.delete(`/ntfy/topics/${id}`),
  syncTopicsToChannels: () => api.post('/ntfy/topics/sync-channels'),
  // Saved Messages
  getSavedMessages: () => api.get('/ntfy/saved-messages'),
  createSavedMessage: (data) => api.post('/ntfy/saved-messages', data),
  sendSavedMessage: (id) => api.post(`/ntfy/saved-messages/${id}/send`),
  deleteSavedMessage: (id) => api.delete(`/ntfy/saved-messages/${id}`),
  // History
  getHistory: (params) => api.get('/ntfy/history', { params }),
  // Server Config
  getConfig: () => api.get('/ntfy/config'),
  updateConfig: (data) => api.put('/ntfy/config', data),
  // Emojis
  getEmojiCategories: () => api.get('/ntfy/emojis/categories'),
  searchEmojis: (query) => api.get('/ntfy/emojis/search', { params: { q: query } }),
  // Integrations
  getExamples: (category) => api.get('/ntfy/integrations/examples', { params: { category } }),
  getWebhookUrl: (topic) => api.get('/ntfy/integrations/webhook-url', { params: { topic } }),
}

// Attach APIs to the main instance for api.xxx.method() pattern compatibility
api.auth = authApi
api.system = {
  ...systemApi,
  // Aliases for SystemView compatibility
  getInfo: systemApi.info,
  getHealth: systemApi.health,
  getHealthFull: systemApi.healthFull,
  getNetwork: systemApi.network,
  getSsl: systemApi.ssl,
  getCloudflare: systemApi.cloudflare,
  getTailscale: systemApi.tailscale,
  getTerminalTargets: systemApi.terminalTargets,
  getExternalServices: systemApi.externalServices,
  getDebug: systemApi.debug,
}
api.backups = backupsApi
api.containers = containersApi
api.notifications = {
  ...notificationsApi,
  // Aliases for channel terminology compatibility (in case any code uses old names)
  getChannels: notificationsApi.getServices,
  testChannel: (id, data) => notificationsApi.testService(id, data),
  updateChannel: (id, data) => notificationsApi.updateService(id, data),
  deleteChannel: (id) => notificationsApi.deleteService(id),
  getHistory: (params) => api.get('/notifications/history', { params }),
}
api.email = emailApi
api.flows = {
  ...flowsApi,
  // Aliases for FlowsView compatibility
  getWorkflows: () => api.get('/flows/list'),
  getExecutions: (limit = 20) => api.get('/flows/executions', { params: { limit } }),
  toggleWorkflow: (id, active) => api.post(`/flows/${id}/toggle`, { active }),
  executeWorkflow: (id) => api.post(`/flows/${id}/execute`),
  getN8nUrl: () => api.get('/flows/n8n-url'),
}
api.settings = {
  ...settingsApi,
  getAll: () => api.get('/settings/'),
}
api.ntfy = ntfyApi
