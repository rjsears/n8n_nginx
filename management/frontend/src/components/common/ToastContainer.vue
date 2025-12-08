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

const colors = {
  success: 'bg-emerald-500/10 border-emerald-500/50 text-emerald-600 dark:text-emerald-400',
  error: 'bg-red-500/10 border-red-500/50 text-red-600 dark:text-red-400',
  warning: 'bg-amber-500/10 border-amber-500/50 text-amber-600 dark:text-amber-400',
  info: 'bg-blue-500/10 border-blue-500/50 text-blue-600 dark:text-blue-400',
}
</script>

<template>
  <div class="fixed bottom-4 right-4 z-[100] space-y-2 max-w-sm w-full">
    <TransitionGroup name="toast">
      <div
        v-for="toast in notificationStore.toasts"
        :key="toast.id"
        :class="[
          'flex items-start gap-3 p-4 rounded-lg border shadow-lg',
          'bg-surface',
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
