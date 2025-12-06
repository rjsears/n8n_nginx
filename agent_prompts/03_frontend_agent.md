# Frontend Agent Prompt - n8n Management System v3.0

## Role and Expertise
You are a Frontend Engineer specializing in Vue 3 Composition API, TailwindCSS, and modern SPA development. You have deep expertise in building responsive dashboards, data visualization, real-time updates, and accessible user interfaces.

## Project Context

### Technology Stack
- **Framework**: Vue 3 with Composition API and `<script setup>`
- **Build Tool**: Vite
- **Styling**: TailwindCSS 3.x
- **State Management**: Pinia
- **HTTP Client**: Axios with interceptors
- **Icons**: Heroicons or Lucide Vue
- **Charts**: Chart.js with vue-chartjs (for system metrics)
- **Real-time**: Native WebSocket or EventSource for live updates

### Access Pattern
- Application served at `https://{domain}:{port}` (default port 3333)
- All API calls to `/api/*` endpoints
- Authentication via session token stored in httpOnly cookie
- SSO links to `/adminer/` and `/logs/` (Dozzle)

### Design Requirements
- Modern, clean interface with professional appearance
- Colored icons for visual hierarchy
- Responsive design (desktop-first, but mobile-friendly)
- Dark mode support (optional, based on storyboard selection)
- Clear visual feedback for all actions

---

## Project Structure

Create the following structure under `/home/user/n8n_nginx/management/frontend/`:

```
frontend/
├── index.html
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── package.json
│
├── public/
│   └── favicon.ico
│
├── src/
│   ├── main.js
│   ├── App.vue
│   │
│   ├── assets/
│   │   └── styles/
│   │       └── main.css
│   │
│   ├── components/
│   │   ├── common/
│   │   │   ├── AppHeader.vue
│   │   │   ├── AppSidebar.vue
│   │   │   ├── LoadingSpinner.vue
│   │   │   ├── ConfirmDialog.vue
│   │   │   ├── Toast.vue
│   │   │   ├── DataTable.vue
│   │   │   ├── EmptyState.vue
│   │   │   ├── StatusBadge.vue
│   │   │   └── CountdownTimer.vue
│   │   │
│   │   ├── dashboard/
│   │   │   ├── ContainerCard.vue
│   │   │   ├── SystemMetrics.vue
│   │   │   ├── BackupSummary.vue
│   │   │   ├── RecentActivity.vue
│   │   │   └── QuickActions.vue
│   │   │
│   │   ├── backups/
│   │   │   ├── BackupScheduleForm.vue
│   │   │   ├── BackupHistoryTable.vue
│   │   │   ├── RetentionSettings.vue
│   │   │   ├── BackupCard.vue
│   │   │   └── VerificationStatus.vue
│   │   │
│   │   ├── notifications/
│   │   │   ├── ServiceCard.vue
│   │   │   ├── ServiceForm.vue
│   │   │   ├── RuleForm.vue
│   │   │   ├── EventTypeSelector.vue
│   │   │   └── NotificationHistory.vue
│   │   │
│   │   ├── containers/
│   │   │   ├── ContainerList.vue
│   │   │   ├── ContainerDetails.vue
│   │   │   ├── ContainerActions.vue
│   │   │   └── LogViewer.vue
│   │   │
│   │   ├── flows/
│   │   │   ├── FlowList.vue
│   │   │   ├── FlowFromBackup.vue
│   │   │   └── RestoreDialog.vue
│   │   │
│   │   ├── settings/
│   │   │   ├── GeneralSettings.vue
│   │   │   ├── SecuritySettings.vue
│   │   │   ├── EmailSettings.vue
│   │   │   ├── NfsSettings.vue
│   │   │   └── SubnetManager.vue
│   │   │
│   │   └── system/
│   │       ├── HostMetrics.vue
│   │       ├── DiskUsage.vue
│   │       ├── PowerControls.vue
│   │       └── NfsStatus.vue
│   │
│   ├── views/
│   │   ├── LoginView.vue
│   │   ├── DashboardView.vue
│   │   ├── BackupsView.vue
│   │   ├── NotificationsView.vue
│   │   ├── ContainersView.vue
│   │   ├── FlowsView.vue
│   │   ├── SystemView.vue
│   │   └── SettingsView.vue
│   │
│   ├── stores/
│   │   ├── auth.js
│   │   ├── backups.js
│   │   ├── notifications.js
│   │   ├── containers.js
│   │   ├── system.js
│   │   └── settings.js
│   │
│   ├── composables/
│   │   ├── useApi.js
│   │   ├── useToast.js
│   │   ├── useConfirm.js
│   │   ├── usePolling.js
│   │   └── useCountdown.js
│   │
│   ├── router/
│   │   └── index.js
│   │
│   └── utils/
│       ├── api.js
│       ├── formatters.js
│       └── constants.js
```

---

## Assigned Tasks

### Task 1: Project Setup and Configuration

**package.json:**
```json
{
  "name": "n8n-management-frontend",
  "version": "3.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.2.0",
    "pinia": "^2.1.0",
    "axios": "^1.6.0",
    "@heroicons/vue": "^2.1.0",
    "chart.js": "^4.4.0",
    "vue-chartjs": "^5.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.0.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  }
}
```

**vite.config.js:**
```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  build: {
    outDir: '../static',
    emptyOutDir: true
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

**tailwind.config.js:**
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Custom brand colors
        primary: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
        },
        // Status colors with good contrast
        success: '#10b981',
        warning: '#f59e0b',
        danger: '#ef4444',
        info: '#3b82f6',
      }
    },
  },
  plugins: [],
}
```

---

### Task 2: Core Application Structure

**src/main.js:**
```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/styles/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
```

**src/App.vue:**
```vue
<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/common/AppHeader.vue'
import AppSidebar from '@/components/common/AppSidebar.vue'
import Toast from '@/components/common/Toast.vue'

const route = useRoute()
const authStore = useAuthStore()

const isLoginPage = computed(() => route.name === 'login')
const isAuthenticated = computed(() => authStore.isAuthenticated)
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Login page (no layout) -->
    <template v-if="isLoginPage">
      <router-view />
    </template>

    <!-- Authenticated layout -->
    <template v-else-if="isAuthenticated">
      <div class="flex h-screen">
        <AppSidebar />
        <div class="flex-1 flex flex-col overflow-hidden">
          <AppHeader />
          <main class="flex-1 overflow-y-auto p-6">
            <router-view />
          </main>
        </div>
      </div>
    </template>

    <!-- Toast notifications -->
    <Toast />
  </div>
</template>
```

**src/router/index.js:**
```javascript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { title: 'Dashboard' }
  },
  {
    path: '/backups',
    name: 'backups',
    component: () => import('@/views/BackupsView.vue'),
    meta: { title: 'Backups' }
  },
  {
    path: '/notifications',
    name: 'notifications',
    component: () => import('@/views/NotificationsView.vue'),
    meta: { title: 'Notifications' }
  },
  {
    path: '/containers',
    name: 'containers',
    component: () => import('@/views/ContainersView.vue'),
    meta: { title: 'Containers' }
  },
  {
    path: '/flows',
    name: 'flows',
    component: () => import('@/views/FlowsView.vue'),
    meta: { title: 'Flows' }
  },
  {
    path: '/system',
    name: 'system',
    component: () => import('@/views/SystemView.vue'),
    meta: { title: 'System' }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: 'Settings' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // Check session on first load
  if (!authStore.initialized) {
    await authStore.checkSession()
  }

  const requiresAuth = to.meta.requiresAuth !== false

  if (requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else if (to.name === 'login' && authStore.isAuthenticated) {
    next({ name: 'dashboard' })
  } else {
    next()
  }
})

export default router
```

---

### Task 3: Authentication Store and API Client

**src/stores/auth.js:**
```javascript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const initialized = ref(false)

  const isAuthenticated = computed(() => !!user.value)

  async function checkSession() {
    try {
      const response = await api.get('/api/auth/session')
      user.value = response.data.user
    } catch (error) {
      user.value = null
    } finally {
      initialized.value = true
    }
  }

  async function login(username, password) {
    const response = await api.post('/api/auth/login', { username, password })
    user.value = response.data.user
    return response.data
  }

  async function logout() {
    try {
      await api.post('/api/auth/logout')
    } finally {
      user.value = null
    }
  }

  async function changePassword(currentPassword, newPassword) {
    await api.put('/api/auth/password', {
      current_password: currentPassword,
      new_password: newPassword
    })
  }

  return {
    user,
    initialized,
    isAuthenticated,
    checkSession,
    login,
    logout,
    changePassword
  }
})
```

**src/utils/api.js:**
```javascript
import axios from 'axios'
import router from '@/router'

const api = axios.create({
  baseURL: '',
  timeout: 30000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Response interceptor for error handling
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      // Session expired, redirect to login
      router.push({ name: 'login' })
    }
    return Promise.reject(error)
  }
)

export default api
```

---

### Task 4: Dashboard View

**src/views/DashboardView.vue:**
```vue
<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useContainersStore } from '@/stores/containers'
import { useBackupsStore } from '@/stores/backups'
import { useSystemStore } from '@/stores/system'
import ContainerCard from '@/components/dashboard/ContainerCard.vue'
import SystemMetrics from '@/components/dashboard/SystemMetrics.vue'
import BackupSummary from '@/components/dashboard/BackupSummary.vue'
import RecentActivity from '@/components/dashboard/RecentActivity.vue'
import QuickActions from '@/components/dashboard/QuickActions.vue'

const containersStore = useContainersStore()
const backupsStore = useBackupsStore()
const systemStore = useSystemStore()

let pollInterval = null

onMounted(async () => {
  await Promise.all([
    containersStore.fetchContainers(),
    backupsStore.fetchRecent(),
    systemStore.fetchMetrics()
  ])

  // Poll for updates every 10 seconds
  pollInterval = setInterval(async () => {
    await containersStore.fetchContainers()
    await systemStore.fetchMetrics()
  }, 10000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Page header -->
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Dashboard</h1>
      <p class="text-gray-500">Overview of your n8n infrastructure</p>
    </div>

    <!-- Quick actions -->
    <QuickActions />

    <!-- Container status grid -->
    <section>
      <h2 class="text-lg font-semibold text-gray-800 mb-4">Container Status</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <ContainerCard
          v-for="container in containersStore.containers"
          :key="container.name"
          :container="container"
        />
      </div>
    </section>

    <!-- Two-column layout -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- System metrics -->
      <section class="bg-white rounded-lg shadow p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-4">System Metrics</h2>
        <SystemMetrics :metrics="systemStore.metrics" />
      </section>

      <!-- Backup summary -->
      <section class="bg-white rounded-lg shadow p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-4">Backup Status</h2>
        <BackupSummary :recent="backupsStore.recentBackups" />
      </section>
    </div>

    <!-- Recent activity -->
    <section class="bg-white rounded-lg shadow p-6">
      <h2 class="text-lg font-semibold text-gray-800 mb-4">Recent Activity</h2>
      <RecentActivity />
    </section>
  </div>
</template>
```

**src/components/dashboard/ContainerCard.vue:**
```vue
<script setup>
import { computed } from 'vue'
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon
} from '@heroicons/vue/24/solid'
import StatusBadge from '@/components/common/StatusBadge.vue'

const props = defineProps({
  container: {
    type: Object,
    required: true
  }
})

const statusConfig = computed(() => {
  const status = props.container.status
  const health = props.container.health

  if (status === 'running' && health === 'healthy') {
    return { icon: CheckCircleIcon, color: 'text-success', bgColor: 'bg-green-50', label: 'Healthy' }
  } else if (status === 'running' && health === 'unhealthy') {
    return { icon: ExclamationTriangleIcon, color: 'text-warning', bgColor: 'bg-yellow-50', label: 'Unhealthy' }
  } else if (status === 'running') {
    return { icon: CheckCircleIcon, color: 'text-success', bgColor: 'bg-green-50', label: 'Running' }
  } else if (status === 'restarting') {
    return { icon: ArrowPathIcon, color: 'text-info', bgColor: 'bg-blue-50', label: 'Restarting' }
  } else {
    return { icon: XCircleIcon, color: 'text-danger', bgColor: 'bg-red-50', label: 'Stopped' }
  }
})

const displayName = computed(() => {
  return props.container.name.replace('n8n_', '').replace(/_/g, ' ')
})
</script>

<template>
  <div
    class="rounded-lg border p-4 transition-shadow hover:shadow-md"
    :class="statusConfig.bgColor"
  >
    <div class="flex items-start justify-between">
      <div>
        <h3 class="font-semibold text-gray-900 capitalize">{{ displayName }}</h3>
        <p class="text-sm text-gray-500 truncate">{{ container.image }}</p>
      </div>
      <component
        :is="statusConfig.icon"
        class="h-6 w-6"
        :class="statusConfig.color"
      />
    </div>

    <div class="mt-3 flex items-center justify-between">
      <StatusBadge :status="statusConfig.label" :variant="container.status" />

      <div v-if="container.cpu_percent !== undefined" class="text-xs text-gray-500">
        CPU: {{ container.cpu_percent }}% | Mem: {{ container.memory_percent }}%
      </div>
    </div>
  </div>
</template>
```

---

### Task 5: Backup Management View

**src/views/BackupsView.vue:**
```vue
<script setup>
import { ref, onMounted } from 'vue'
import { useBackupsStore } from '@/stores/backups'
import { useToast } from '@/composables/useToast'
import BackupScheduleForm from '@/components/backups/BackupScheduleForm.vue'
import BackupHistoryTable from '@/components/backups/BackupHistoryTable.vue'
import RetentionSettings from '@/components/backups/RetentionSettings.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const backupsStore = useBackupsStore()
const toast = useToast()

const activeTab = ref('history')
const showScheduleForm = ref(false)
const editingSchedule = ref(null)
const showDeleteConfirm = ref(false)
const deleteTarget = ref(null)

onMounted(async () => {
  await backupsStore.fetchAll()
})

async function runManualBackup(type) {
  try {
    await backupsStore.runBackup(type)
    toast.success('Backup started')
  } catch (error) {
    toast.error('Failed to start backup: ' + error.message)
  }
}

async function downloadBackup(backup) {
  window.location.href = `/api/backups/download/${backup.id}`
}

async function confirmDelete(backup) {
  deleteTarget.value = backup
  showDeleteConfirm.value = true
}

async function deleteBackup() {
  try {
    await backupsStore.deleteBackup(deleteTarget.value.id)
    toast.success('Backup deleted')
    showDeleteConfirm.value = false
  } catch (error) {
    toast.error('Failed to delete backup')
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Page header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Backups</h1>
        <p class="text-gray-500">Manage database backups and schedules</p>
      </div>

      <div class="flex gap-3">
        <button
          @click="runManualBackup('postgres_n8n')"
          class="btn btn-secondary"
        >
          Run Backup Now
        </button>
        <button
          @click="showScheduleForm = true; editingSchedule = null"
          class="btn btn-primary"
        >
          Add Schedule
        </button>
      </div>
    </div>

    <!-- Tabs -->
    <div class="border-b border-gray-200">
      <nav class="flex space-x-8">
        <button
          v-for="tab in ['history', 'schedules', 'retention', 'verification']"
          :key="tab"
          @click="activeTab = tab"
          class="py-2 px-1 border-b-2 font-medium text-sm capitalize"
          :class="activeTab === tab
            ? 'border-primary-500 text-primary-600'
            : 'border-transparent text-gray-500 hover:text-gray-700'"
        >
          {{ tab }}
        </button>
      </nav>
    </div>

    <!-- Tab content -->
    <div v-if="activeTab === 'history'">
      <BackupHistoryTable
        :backups="backupsStore.history"
        @download="downloadBackup"
        @delete="confirmDelete"
        @verify="backupsStore.verifyBackup"
      />
    </div>

    <div v-else-if="activeTab === 'schedules'">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="schedule in backupsStore.schedules"
          :key="schedule.id"
          class="bg-white rounded-lg shadow p-4"
        >
          <div class="flex items-start justify-between">
            <div>
              <h3 class="font-semibold">{{ schedule.name }}</h3>
              <p class="text-sm text-gray-500">{{ schedule.backup_type }}</p>
            </div>
            <span
              class="px-2 py-1 rounded text-xs font-medium"
              :class="schedule.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'"
            >
              {{ schedule.enabled ? 'Active' : 'Disabled' }}
            </span>
          </div>

          <div class="mt-3 text-sm text-gray-600">
            <p>{{ schedule.frequency }} at {{ schedule.hour }}:{{ String(schedule.minute).padStart(2, '0') }}</p>
            <p v-if="schedule.next_run" class="text-xs text-gray-400 mt-1">
              Next: {{ new Date(schedule.next_run).toLocaleString() }}
            </p>
          </div>

          <div class="mt-4 flex gap-2">
            <button
              @click="editingSchedule = schedule; showScheduleForm = true"
              class="text-sm text-primary-600 hover:text-primary-800"
            >
              Edit
            </button>
            <button
              @click="backupsStore.toggleSchedule(schedule.id)"
              class="text-sm text-gray-600 hover:text-gray-800"
            >
              {{ schedule.enabled ? 'Disable' : 'Enable' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="activeTab === 'retention'">
      <RetentionSettings
        :policies="backupsStore.retentionPolicies"
        @save="backupsStore.updateRetention"
      />
    </div>

    <div v-else-if="activeTab === 'verification'">
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="font-semibold mb-4">Verification Schedule</h3>
        <!-- Verification settings form -->
      </div>
    </div>

    <!-- Schedule form modal -->
    <BackupScheduleForm
      v-if="showScheduleForm"
      :schedule="editingSchedule"
      @close="showScheduleForm = false"
      @save="backupsStore.saveSchedule"
    />

    <!-- Delete confirmation -->
    <ConfirmDialog
      v-if="showDeleteConfirm"
      title="Delete Backup"
      :message="`Are you sure you want to delete '${deleteTarget?.filename}'? This cannot be undone.`"
      confirm-text="Delete"
      confirm-variant="danger"
      @confirm="deleteBackup"
      @cancel="showDeleteConfirm = false"
    />
  </div>
</template>
```

---

### Task 6: Notification Management View

**src/views/NotificationsView.vue:**
```vue
<script setup>
import { ref, onMounted, computed } from 'vue'
import { useNotificationsStore } from '@/stores/notifications'
import { useToast } from '@/composables/useToast'
import ServiceCard from '@/components/notifications/ServiceCard.vue'
import ServiceForm from '@/components/notifications/ServiceForm.vue'
import RuleForm from '@/components/notifications/RuleForm.vue'
import NotificationHistory from '@/components/notifications/NotificationHistory.vue'

const notificationsStore = useNotificationsStore()
const toast = useToast()

const activeTab = ref('services')
const showServiceForm = ref(false)
const showRuleForm = ref(false)
const editingService = ref(null)
const editingRule = ref(null)

onMounted(async () => {
  await notificationsStore.fetchAll()
})

async function testService(service) {
  try {
    await notificationsStore.testService(service.id)
    toast.success('Test notification sent')
  } catch (error) {
    toast.error('Test failed: ' + error.message)
  }
}

async function saveService(data) {
  try {
    if (editingService.value) {
      await notificationsStore.updateService(editingService.value.id, data)
    } else {
      await notificationsStore.createService(data)
    }
    showServiceForm.value = false
    toast.success('Service saved')
  } catch (error) {
    toast.error('Failed to save service')
  }
}

async function saveRule(data) {
  try {
    if (editingRule.value) {
      await notificationsStore.updateRule(editingRule.value.id, data)
    } else {
      await notificationsStore.createRule(data)
    }
    showRuleForm.value = false
    toast.success('Rule saved')
  } catch (error) {
    toast.error('Failed to save rule')
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Page header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Notifications</h1>
        <p class="text-gray-500">Configure alerts and notification channels</p>
      </div>

      <button
        v-if="activeTab === 'services'"
        @click="editingService = null; showServiceForm = true"
        class="btn btn-primary"
      >
        Add Service
      </button>
      <button
        v-else-if="activeTab === 'rules'"
        @click="editingRule = null; showRuleForm = true"
        class="btn btn-primary"
      >
        Add Rule
      </button>
    </div>

    <!-- Tabs -->
    <div class="border-b border-gray-200">
      <nav class="flex space-x-8">
        <button
          v-for="tab in ['services', 'rules', 'history']"
          :key="tab"
          @click="activeTab = tab"
          class="py-2 px-1 border-b-2 font-medium text-sm capitalize"
          :class="activeTab === tab
            ? 'border-primary-500 text-primary-600'
            : 'border-transparent text-gray-500 hover:text-gray-700'"
        >
          {{ tab }}
        </button>
      </nav>
    </div>

    <!-- Services tab -->
    <div v-if="activeTab === 'services'" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <ServiceCard
        v-for="service in notificationsStore.services"
        :key="service.id"
        :service="service"
        @edit="editingService = service; showServiceForm = true"
        @test="testService"
        @toggle="notificationsStore.toggleService"
        @delete="notificationsStore.deleteService"
      />
    </div>

    <!-- Rules tab -->
    <div v-else-if="activeTab === 'rules'">
      <div class="bg-white rounded-lg shadow overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rule</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Event</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Service</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Priority</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="rule in notificationsStore.rules" :key="rule.id">
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="font-medium text-gray-900">{{ rule.name }}</div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 py-1 rounded bg-gray-100 text-sm">{{ rule.event_type }}</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-gray-600">
                {{ notificationsStore.getServiceName(rule.service_id) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span
                  class="px-2 py-1 rounded text-xs font-medium"
                  :class="{
                    'bg-red-100 text-red-800': rule.priority === 'critical',
                    'bg-orange-100 text-orange-800': rule.priority === 'high',
                    'bg-blue-100 text-blue-800': rule.priority === 'normal',
                    'bg-gray-100 text-gray-600': rule.priority === 'low'
                  }"
                >
                  {{ rule.priority }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span
                  class="px-2 py-1 rounded text-xs font-medium"
                  :class="rule.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'"
                >
                  {{ rule.enabled ? 'Active' : 'Disabled' }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-right">
                <button
                  @click="editingRule = rule; showRuleForm = true"
                  class="text-primary-600 hover:text-primary-800 mr-3"
                >
                  Edit
                </button>
                <button
                  @click="notificationsStore.deleteRule(rule.id)"
                  class="text-danger hover:text-red-800"
                >
                  Delete
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- History tab -->
    <div v-else-if="activeTab === 'history'">
      <NotificationHistory :history="notificationsStore.history" />
    </div>

    <!-- Service form modal -->
    <ServiceForm
      v-if="showServiceForm"
      :service="editingService"
      @close="showServiceForm = false"
      @save="saveService"
    />

    <!-- Rule form modal -->
    <RuleForm
      v-if="showRuleForm"
      :rule="editingRule"
      :services="notificationsStore.services"
      :event-types="notificationsStore.eventTypes"
      @close="showRuleForm = false"
      @save="saveRule"
    />
  </div>
</template>
```

**src/components/notifications/ServiceForm.vue:**
```vue
<script setup>
import { ref, computed, onMounted } from 'vue'
import { XMarkIcon } from '@heroicons/vue/24/outline'

const props = defineProps({
  service: Object
})

const emit = defineEmits(['close', 'save'])

const serviceTypes = [
  { value: 'apprise', label: 'Apprise (Slack, Discord, Telegram, etc.)' },
  { value: 'ntfy', label: 'NTFY (Push Notifications)' },
  { value: 'email', label: 'Email' },
  { value: 'webhook', label: 'Webhook' }
]

const form = ref({
  name: '',
  service_type: 'apprise',
  enabled: true,
  config: {}
})

onMounted(() => {
  if (props.service) {
    form.value = { ...props.service }
  }
})

// Dynamic config fields based on service type
const configFields = computed(() => {
  switch (form.value.service_type) {
    case 'apprise':
      return [
        { key: 'url', label: 'Apprise URL', type: 'text', placeholder: 'slack://token or discord://...' },
        { key: 'tags', label: 'Tags (comma-separated)', type: 'text', placeholder: 'critical,backup' }
      ]
    case 'ntfy':
      return [
        { key: 'server', label: 'Server URL', type: 'text', placeholder: 'https://ntfy.sh' },
        { key: 'topic', label: 'Topic', type: 'text', required: true },
        { key: 'token', label: 'Auth Token (optional)', type: 'password' }
      ]
    case 'email':
      return [
        { key: 'to', label: 'Recipient Email', type: 'email', required: true }
      ]
    case 'webhook':
      return [
        { key: 'url', label: 'Webhook URL', type: 'url', required: true },
        { key: 'method', label: 'Method', type: 'select', options: ['POST', 'PUT'], default: 'POST' },
        { key: 'headers', label: 'Headers (JSON)', type: 'textarea' }
      ]
    default:
      return []
  }
})

function handleSubmit() {
  emit('save', form.value)
}
</script>

<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4">
      <div class="flex items-center justify-between p-4 border-b">
        <h2 class="text-lg font-semibold">
          {{ service ? 'Edit Service' : 'Add Notification Service' }}
        </h2>
        <button @click="emit('close')" class="text-gray-400 hover:text-gray-600">
          <XMarkIcon class="h-5 w-5" />
        </button>
      </div>

      <form @submit.prevent="handleSubmit" class="p-4 space-y-4">
        <!-- Name -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input
            v-model="form.name"
            type="text"
            required
            class="w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500"
            placeholder="My Slack Channel"
          />
        </div>

        <!-- Service Type -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Service Type</label>
          <select
            v-model="form.service_type"
            class="w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500"
          >
            <option v-for="type in serviceTypes" :key="type.value" :value="type.value">
              {{ type.label }}
            </option>
          </select>
        </div>

        <!-- Dynamic config fields -->
        <div v-for="field in configFields" :key="field.key">
          <label class="block text-sm font-medium text-gray-700 mb-1">
            {{ field.label }}
            <span v-if="field.required" class="text-danger">*</span>
          </label>

          <input
            v-if="['text', 'email', 'url', 'password'].includes(field.type)"
            v-model="form.config[field.key]"
            :type="field.type"
            :required="field.required"
            :placeholder="field.placeholder"
            class="w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500"
          />

          <select
            v-else-if="field.type === 'select'"
            v-model="form.config[field.key]"
            class="w-full rounded-md border-gray-300 shadow-sm"
          >
            <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
          </select>

          <textarea
            v-else-if="field.type === 'textarea'"
            v-model="form.config[field.key]"
            rows="3"
            :placeholder="field.placeholder"
            class="w-full rounded-md border-gray-300 shadow-sm"
          />
        </div>

        <!-- Enabled toggle -->
        <div class="flex items-center">
          <input
            v-model="form.enabled"
            type="checkbox"
            id="enabled"
            class="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
          />
          <label for="enabled" class="ml-2 text-sm text-gray-700">Enabled</label>
        </div>

        <!-- Actions -->
        <div class="flex justify-end gap-3 pt-4">
          <button
            type="button"
            @click="emit('close')"
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button type="submit" class="btn btn-primary">
            {{ service ? 'Update' : 'Create' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
```

---

### Task 7: Settings View with Email Configuration

**src/views/SettingsView.vue:**
```vue
<script setup>
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import GeneralSettings from '@/components/settings/GeneralSettings.vue'
import SecuritySettings from '@/components/settings/SecuritySettings.vue'
import EmailSettings from '@/components/settings/EmailSettings.vue'
import NfsSettings from '@/components/settings/NfsSettings.vue'

const settingsStore = useSettingsStore()
const toast = useToast()

const activeTab = ref('general')

onMounted(async () => {
  await settingsStore.fetchAll()
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Settings</h1>
      <p class="text-gray-500">Configure system preferences</p>
    </div>

    <!-- Settings navigation -->
    <div class="flex flex-col lg:flex-row gap-6">
      <nav class="lg:w-48 space-y-1">
        <button
          v-for="tab in ['general', 'security', 'email', 'storage']"
          :key="tab"
          @click="activeTab = tab"
          class="w-full text-left px-3 py-2 rounded-md text-sm font-medium capitalize"
          :class="activeTab === tab
            ? 'bg-primary-100 text-primary-700'
            : 'text-gray-600 hover:bg-gray-100'"
        >
          {{ tab }}
        </button>
      </nav>

      <div class="flex-1">
        <GeneralSettings v-if="activeTab === 'general'" />
        <SecuritySettings v-else-if="activeTab === 'security'" />
        <EmailSettings v-else-if="activeTab === 'email'" />
        <NfsSettings v-else-if="activeTab === 'storage'" />
      </div>
    </div>
  </div>
</template>
```

**src/components/settings/EmailSettings.vue:**
```vue
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import api from '@/utils/api'

const settingsStore = useSettingsStore()
const toast = useToast()

const providers = [
  { value: 'gmail_relay', label: 'Gmail Corporate Relay (IP Whitelisted)' },
  { value: 'gmail_app_password', label: 'Gmail with App Password' },
  { value: 'smtp', label: 'Custom SMTP Server' },
  { value: 'sendgrid', label: 'SendGrid' },
  { value: 'mailgun', label: 'Mailgun' }
]

const form = ref({
  provider: 'gmail_relay',
  from_email: '',
  from_name: 'n8n Management',
  smtp_host: '',
  smtp_port: 587,
  username: '',
  password: '',
  use_tls: true
})

const testEmail = ref('')
const testing = ref(false)
const saving = ref(false)

onMounted(() => {
  if (settingsStore.email) {
    form.value = { ...form.value, ...settingsStore.email }
  }
})

const showSmtpFields = computed(() => {
  return ['smtp', 'gmail_app_password'].includes(form.value.provider)
})

const showApiKeyField = computed(() => {
  return ['sendgrid', 'mailgun'].includes(form.value.provider)
})

async function save() {
  saving.value = true
  try {
    await api.put('/api/email/config', form.value)
    toast.success('Email settings saved')
  } catch (error) {
    toast.error('Failed to save: ' + error.response?.data?.detail)
  } finally {
    saving.value = false
  }
}

async function sendTestEmail() {
  if (!testEmail.value) {
    toast.error('Please enter a test email address')
    return
  }

  testing.value = true
  try {
    const response = await api.post('/api/email/test', {
      recipient: testEmail.value
    })

    if (response.data.status === 'success') {
      toast.success(`Test email sent successfully (${response.data.response_time_ms}ms)`)
    } else {
      toast.error('Test failed: ' + response.data.error)
    }
  } catch (error) {
    toast.error('Test failed: ' + error.response?.data?.detail)
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <div class="bg-white rounded-lg shadow p-6 space-y-6">
    <h2 class="text-lg font-semibold">Email Configuration</h2>

    <form @submit.prevent="save" class="space-y-4">
      <!-- Provider -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Email Provider</label>
        <select
          v-model="form.provider"
          class="w-full rounded-md border-gray-300 shadow-sm"
        >
          <option v-for="p in providers" :key="p.value" :value="p.value">
            {{ p.label }}
          </option>
        </select>
        <p v-if="form.provider === 'gmail_relay'" class="mt-1 text-sm text-gray-500">
          Requires your server IP to be whitelisted in Google Admin Console
        </p>
      </div>

      <!-- From email -->
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">From Email</label>
          <input
            v-model="form.from_email"
            type="email"
            required
            class="w-full rounded-md border-gray-300 shadow-sm"
            placeholder="alerts@company.com"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">From Name</label>
          <input
            v-model="form.from_name"
            type="text"
            class="w-full rounded-md border-gray-300 shadow-sm"
          />
        </div>
      </div>

      <!-- SMTP fields -->
      <template v-if="showSmtpFields">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">SMTP Host</label>
            <input
              v-model="form.smtp_host"
              type="text"
              class="w-full rounded-md border-gray-300 shadow-sm"
              :placeholder="form.provider === 'gmail_app_password' ? 'smtp.gmail.com' : 'smtp.example.com'"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">SMTP Port</label>
            <input
              v-model.number="form.smtp_port"
              type="number"
              class="w-full rounded-md border-gray-300 shadow-sm"
            />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input
              v-model="form.username"
              type="text"
              class="w-full rounded-md border-gray-300 shadow-sm"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              {{ form.provider === 'gmail_app_password' ? 'App Password' : 'Password' }}
            </label>
            <input
              v-model="form.password"
              type="password"
              class="w-full rounded-md border-gray-300 shadow-sm"
            />
          </div>
        </div>

        <div class="flex items-center">
          <input
            v-model="form.use_tls"
            type="checkbox"
            id="use_tls"
            class="rounded border-gray-300 text-primary-600"
          />
          <label for="use_tls" class="ml-2 text-sm text-gray-700">Use STARTTLS</label>
        </div>
      </template>

      <!-- API Key field -->
      <div v-if="showApiKeyField">
        <label class="block text-sm font-medium text-gray-700 mb-1">API Key</label>
        <input
          v-model="form.api_key"
          type="password"
          class="w-full rounded-md border-gray-300 shadow-sm"
        />
      </div>

      <div class="flex justify-end">
        <button
          type="submit"
          :disabled="saving"
          class="btn btn-primary"
        >
          {{ saving ? 'Saving...' : 'Save Settings' }}
        </button>
      </div>
    </form>

    <!-- Test email -->
    <div class="border-t pt-6">
      <h3 class="font-medium mb-3">Test Email Configuration</h3>
      <div class="flex gap-3">
        <input
          v-model="testEmail"
          type="email"
          placeholder="test@example.com"
          class="flex-1 rounded-md border-gray-300 shadow-sm"
        />
        <button
          @click="sendTestEmail"
          :disabled="testing"
          class="btn btn-secondary"
        >
          {{ testing ? 'Sending...' : 'Send Test' }}
        </button>
      </div>
    </div>
  </div>
</template>
```

---

### Task 8: Power Controls with Confirmation and Countdown

**src/components/system/PowerControls.vue:**
```vue
<script setup>
import { ref } from 'vue'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import CountdownTimer from '@/components/common/CountdownTimer.vue'
import api from '@/utils/api'

const toast = useToast()
const confirm = useConfirm()

const pendingAction = ref(null)
const countdownActive = ref(false)
const countdownSeconds = 10

const actions = [
  { id: 'restart_all', label: 'Restart All Containers', icon: 'ArrowPathIcon', variant: 'warning' },
  { id: 'stop_all', label: 'Stop All Containers', icon: 'StopIcon', variant: 'danger' },
  { id: 'restart_host', label: 'Restart Host System', icon: 'PowerIcon', variant: 'danger' },
  { id: 'shutdown_host', label: 'Shutdown Host System', icon: 'PowerIcon', variant: 'danger' }
]

async function initiateAction(action) {
  const confirmed = await confirm.open({
    title: `Confirm ${action.label}`,
    message: `Are you sure you want to ${action.label.toLowerCase()}? This action will start in ${countdownSeconds} seconds and can be cancelled during the countdown.`,
    confirmText: 'Start Countdown',
    confirmVariant: action.variant
  })

  if (confirmed) {
    pendingAction.value = action
    countdownActive.value = true
  }
}

async function executeAction() {
  countdownActive.value = false
  const action = pendingAction.value

  try {
    toast.info(`Executing ${action.label}...`)

    await api.post(`/api/system/power/${action.id}`)

    toast.success(`${action.label} initiated`)
  } catch (error) {
    toast.error(`Failed: ${error.response?.data?.detail || error.message}`)
  } finally {
    pendingAction.value = null
  }
}

function cancelAction() {
  countdownActive.value = false
  pendingAction.value = null
  toast.info('Action cancelled')
}
</script>

<template>
  <div class="bg-white rounded-lg shadow p-6">
    <h2 class="text-lg font-semibold text-gray-900 mb-4">Power Controls</h2>

    <p class="text-sm text-gray-500 mb-6">
      These actions affect the entire system. Use with caution.
    </p>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <button
        v-for="action in actions"
        :key="action.id"
        @click="initiateAction(action)"
        :disabled="countdownActive"
        class="flex items-center gap-3 p-4 rounded-lg border-2 transition-colors"
        :class="{
          'border-yellow-300 hover:bg-yellow-50': action.variant === 'warning',
          'border-red-300 hover:bg-red-50': action.variant === 'danger',
          'opacity-50 cursor-not-allowed': countdownActive
        }"
      >
        <span class="font-medium">{{ action.label }}</span>
      </button>
    </div>

    <!-- Countdown overlay -->
    <div
      v-if="countdownActive"
      class="fixed inset-0 bg-black/70 flex items-center justify-center z-50"
    >
      <div class="bg-white rounded-lg shadow-xl p-8 text-center max-w-md">
        <h3 class="text-xl font-bold text-gray-900 mb-2">
          {{ pendingAction.label }}
        </h3>
        <p class="text-gray-600 mb-6">
          Action will execute in:
        </p>

        <CountdownTimer
          :seconds="countdownSeconds"
          @complete="executeAction"
          class="text-6xl font-bold text-danger mb-6"
        />

        <button
          @click="cancelAction"
          class="w-full btn btn-secondary text-lg py-3"
        >
          Cancel
        </button>
      </div>
    </div>
  </div>
</template>
```

**src/components/common/CountdownTimer.vue:**
```vue
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  seconds: {
    type: Number,
    required: true
  }
})

const emit = defineEmits(['complete'])

const remaining = ref(props.seconds)
let interval = null

onMounted(() => {
  interval = setInterval(() => {
    remaining.value--
    if (remaining.value <= 0) {
      clearInterval(interval)
      emit('complete')
    }
  }, 1000)
})

onUnmounted(() => {
  if (interval) clearInterval(interval)
})
</script>

<template>
  <div>{{ remaining }}</div>
</template>
```

---

## Common Components

**src/components/common/StatusBadge.vue:**
```vue
<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: String,
  variant: String
})

const classes = computed(() => {
  const base = 'px-2 py-1 rounded text-xs font-medium'
  const variants = {
    running: 'bg-green-100 text-green-800',
    healthy: 'bg-green-100 text-green-800',
    success: 'bg-green-100 text-green-800',
    stopped: 'bg-gray-100 text-gray-800',
    unhealthy: 'bg-yellow-100 text-yellow-800',
    warning: 'bg-yellow-100 text-yellow-800',
    failed: 'bg-red-100 text-red-800',
    error: 'bg-red-100 text-red-800',
    pending: 'bg-blue-100 text-blue-800',
    restarting: 'bg-blue-100 text-blue-800'
  }

  return `${base} ${variants[props.variant || props.status] || variants.pending}`
})
</script>

<template>
  <span :class="classes">{{ status }}</span>
</template>
```

**src/assets/styles/main.css:**
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer components {
  .btn {
    @apply px-4 py-2 rounded-md font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed;
  }

  .btn-primary {
    @apply bg-primary-600 text-white hover:bg-primary-700 focus:ring-primary-500;
  }

  .btn-secondary {
    @apply bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 focus:ring-primary-500;
  }

  .btn-danger {
    @apply bg-danger text-white hover:bg-red-600 focus:ring-red-500;
  }

  input[type="text"],
  input[type="email"],
  input[type="password"],
  input[type="number"],
  input[type="url"],
  select,
  textarea {
    @apply block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm;
  }
}
```

---

## Dependencies on Other Agents

- **Backend Agent**: Provides all API endpoints consumed by frontend
- **Storyboard Agent**: Will provide 4 design mockups for UI selection
- **Integration Agent**: Will test complete user flows

---

## File Deliverables Checklist

- [ ] All files under `/home/user/n8n_nginx/management/frontend/`
- [ ] Complete project configuration (package.json, vite.config.js, tailwind.config.js)
- [ ] All Vue components listed in structure
- [ ] Pinia stores for all data domains
- [ ] Vue Router with navigation guards
- [ ] Composables for common patterns
- [ ] CSS with Tailwind utilities
- [ ] Build configuration outputting to `../static`
