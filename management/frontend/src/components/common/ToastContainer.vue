<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/common/ToastContainer.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { useNotificationStore } from '@/stores/notifications'
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'

const notificationStore = useNotificationStore()

const icons = {
  success: CheckCircleIcon,
  error: ExclamationCircleIcon,
  warning: ExclamationTriangleIcon,
  info: InformationCircleIcon,
}

// Use solid backgrounds with colored left border accent
const colors = {
  success: 'border-l-4 border-l-emerald-500 border-y-gray-200 dark:border-y-gray-600 border-r-gray-200 dark:border-r-gray-600 text-emerald-700 dark:text-emerald-400',
  error: 'border-l-4 border-l-red-500 border-y-gray-200 dark:border-y-gray-600 border-r-gray-200 dark:border-r-gray-600 text-red-700 dark:text-red-400',
  warning: 'border-l-4 border-l-amber-500 border-y-gray-200 dark:border-y-gray-600 border-r-gray-200 dark:border-r-gray-600 text-amber-700 dark:text-amber-400',
  info: 'border-l-4 border-l-blue-500 border-y-gray-200 dark:border-y-gray-600 border-r-gray-200 dark:border-r-gray-600 text-blue-700 dark:text-blue-400',
}
</script>

<template>
  <div class="fixed bottom-4 right-4 z-[100] space-y-2 max-w-sm w-full">
    <TransitionGroup name="toast">
      <div
        v-for="toast in notificationStore.toasts"
        :key="toast.id"
        :class="[
          'flex items-start gap-3 p-4 rounded-lg shadow-lg',
          'bg-white dark:bg-gray-800',
          colors[toast.type]
        ]"
      >
        <component
          :is="icons[toast.type]"
          class="h-5 w-5 flex-shrink-0 mt-0.5"
        />
        <p class="flex-1 text-sm">{{ toast.message }}</p>
        <button
          @click="notificationStore.removeToast(toast.id)"
          class="flex-shrink-0 hover:opacity-70 transition-opacity"
        >
          <XMarkIcon class="h-4 w-4" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active {
  transition: all 0.3s ease-out;
}
.toast-leave-active {
  transition: all 0.2s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
.toast-move {
  transition: transform 0.3s ease;
}
</style>
