<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useNotificationStore } from '@/stores/notifications'
import { LockClosedIcon, UserIcon, EyeIcon, EyeSlashIcon } from '@heroicons/vue/24/outline'

const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const notificationStore = useNotificationStore()

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const error = ref('')

const isValid = computed(() => username.value.length > 0 && password.value.length > 0)

async function handleLogin() {
  if (!isValid.value) return

  loading.value = true
  error.value = ''

  try {
    const success = await authStore.login({ username: username.value, password: password.value })
    if (success) {
      notificationStore.success('Welcome back!')
      router.push('/dashboard')
    } else {
      // Login failed - authStore sets error internally
      error.value = authStore.error || 'Invalid credentials'
      notificationStore.error(error.value)
    }
  } catch (err) {
    error.value = err.response?.data?.detail || 'Login failed'
    notificationStore.error(error.value)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-background p-4">
    <div class="w-full max-w-md">
      <!-- Logo/Title -->
      <div class="text-center mb-8">
        <div
          :class="[
            'inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4',
            themeStore.isNeon ? 'bg-cyan-500/20 neon-box-cyan' : 'bg-blue-500/10'
          ]"
        >
          <LockClosedIcon
            :class="[
              'h-8 w-8',
              themeStore.isNeon ? 'text-cyan-400' : 'text-blue-500'
            ]"
          />
        </div>
        <h1
          :class="[
            'text-2xl font-bold',
            themeStore.isNeon ? 'neon-text-cyan' : 'text-primary'
          ]"
        >
          n8n Management
        </h1>
        <p class="text-secondary mt-2">Sign in to your account</p>
      </div>

      <!-- Login Form -->
      <form
        @submit.prevent="handleLogin"
        :class="[
          'bg-surface rounded-xl border border-gray-400 dark:border-black p-6',
          themeStore.isNeon ? 'neon-card' : ''
        ]"
      >
        <!-- Error Alert -->
        <div
          v-if="error"
          class="mb-4 p-3 bg-red-100 dark:bg-red-500/20 border border-red-200 dark:border-red-500/30 rounded-lg"
        >
          <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
        </div>

        <!-- Username Field -->
        <div class="mb-4">
          <label for="username" class="block text-sm font-medium text-primary mb-1.5">
            Username
          </label>
          <div class="relative">
            <UserIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted" />
            <input
              id="username"
              v-model="username"
              type="text"
              autocomplete="username"
              placeholder="Enter your username"
              :class="[
                'input-field pl-10',
                themeStore.isNeon ? 'neon-input' : ''
              ]"
            />
          </div>
        </div>

        <!-- Password Field -->
        <div class="mb-6">
          <label for="password" class="block text-sm font-medium text-primary mb-1.5">
            Password
          </label>
          <div class="relative">
            <LockClosedIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted" />
            <input
              id="password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              placeholder="Enter your password"
              :class="[
                'input-field pl-10 pr-10',
                themeStore.isNeon ? 'neon-input' : ''
              ]"
            />
            <button
              type="button"
              @click="showPassword = !showPassword"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-secondary"
            >
              <EyeSlashIcon v-if="showPassword" class="h-5 w-5" />
              <EyeIcon v-else class="h-5 w-5" />
            </button>
          </div>
        </div>

        <!-- Submit Button -->
        <button
          type="submit"
          :disabled="!isValid || loading"
          :class="[
            'w-full py-2.5 rounded-lg font-medium transition-all',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            themeStore.isNeon
              ? 'bg-cyan-500 text-black hover:bg-cyan-400 neon-btn-cyan'
              : 'bg-blue-500 text-white hover:bg-blue-600'
          ]"
        >
          <span v-if="loading" class="flex items-center justify-center gap-2">
            <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Signing in...
          </span>
          <span v-else>Sign In</span>
        </button>
      </form>

      <!-- Footer -->
      <p class="text-center text-sm text-muted mt-6">
        n8n Management Console v3.0
      </p>
    </div>
  </div>
</template>
