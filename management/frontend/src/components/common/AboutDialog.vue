<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/common/AboutDialog.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { XMarkIcon, InformationCircleIcon, ArrowTopRightOnSquareIcon } from '@heroicons/vue/24/outline'

const props = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['close'])

// Version info
const appInfo = {
  name: 'n8n Management Console',
  version: '3.0.0',
  versionDate: '2025-12-13',
  author: 'Richard J. Sears',
  email: 'richardjsears@gmail.com',
  githubUrl: 'https://github.com/rjsears/n8n_nginx',
}

function close() {
  emit('close')
}

function openGithub() {
  window.open(appInfo.githubUrl, '_blank', 'noopener,noreferrer')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open"
        class="fixed inset-0 z-[100] flex items-center justify-center p-4"
      >
        <!-- Backdrop -->
        <div
          class="absolute inset-0 bg-black/50"
          @click="close"
        />

        <!-- Dialog -->
        <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full border border-gray-400 dark:border-gray-700">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700 bg-white dark:bg-gray-800">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-full bg-blue-100 dark:bg-blue-500/20">
                <InformationCircleIcon class="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 class="text-lg font-semibold text-primary">About</h3>
            </div>
            <button
              @click="close"
              class="p-1 rounded-lg text-secondary hover:text-primary hover:bg-surface-hover"
            >
              <XMarkIcon class="h-5 w-5" />
            </button>
          </div>

          <!-- Content -->
          <div class="px-6 py-6 bg-white dark:bg-gray-800 space-y-6">
            <!-- App name and version -->
            <div class="text-center">
              <h2 class="text-2xl font-bold text-primary">{{ appInfo.name }}</h2>
              <div class="mt-2 flex items-center justify-center gap-2">
                <span class="px-2.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300 text-sm font-medium">
                  v{{ appInfo.version }}
                </span>
                <span class="text-sm text-muted">{{ appInfo.versionDate }}</span>
              </div>
            </div>

            <!-- Divider -->
            <div class="border-t border-gray-400 dark:border-gray-700"></div>

            <!-- Author info -->
            <div class="text-center space-y-1">
              <p class="text-sm text-muted">Developed by</p>
              <p class="font-medium text-primary">{{ appInfo.author }}</p>
              <a
                :href="`mailto:${appInfo.email}`"
                class="text-sm text-blue-600 dark:text-blue-400 hover:underline"
              >
                {{ appInfo.email }}
              </a>
            </div>

            <!-- Divider -->
            <div class="border-t border-gray-400 dark:border-gray-700"></div>

            <!-- GitHub link -->
            <div class="text-center">
              <button
                @click="openGithub"
                class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-primary transition-colors"
              >
                <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                  <path fill-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clip-rule="evenodd" />
                </svg>
                View on GitHub
                <ArrowTopRightOnSquareIcon class="h-4 w-4" />
              </button>
            </div>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-center px-6 py-4 border-t border-gray-400 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 rounded-b-lg">
            <button
              @click="close"
              class="btn-secondary"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
