<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/common/HelpDialog.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { XMarkIcon, QuestionMarkCircleIcon, ArrowTopRightOnSquareIcon, BookOpenIcon, DocumentTextIcon, CodeBracketIcon, CpuChipIcon } from '@heroicons/vue/24/outline'

const props = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['close'])

// Help links configuration
const helpLinks = [
  {
    category: 'API Documentation',
    icon: CodeBracketIcon,
    links: [
      { name: 'Swagger UI', url: '/management/api/docs', description: 'Interactive API documentation with try-it-out', external: false },
      { name: 'ReDoc', url: '/management/api/redoc', description: 'Clean, readable API reference documentation', external: false },
      { name: 'OpenAPI Schema', url: '/management/api/openapi.json', description: 'Raw OpenAPI JSON specification', external: false },
    ]
  },
  {
    category: 'User Guides',
    icon: BookOpenIcon,
    links: [
      { name: 'Backup Guide', url: '/management/docs/BACKUP_GUIDE/', description: 'Complete backup and restore documentation', external: false },
      { name: 'API Reference', url: '/management/docs/API/', description: 'API endpoints and usage examples', external: false },
      { name: 'Notifications Setup', url: '/management/docs/NOTIFICATIONS/', description: 'Email and NTFY notification configuration', external: false },
      { name: 'Troubleshooting', url: '/management/docs/TROUBLESHOOTING/', description: 'Common issues and solutions', external: false },
      { name: 'User Manual', url: '/management/docs/manual/welcome/', description: 'Complete illustrated manual for every console page', external: false },
    ]
  },
  {
    category: 'Infrastructure Docs',
    icon: CpuChipIcon,
    links: [
      { name: 'Cloudflare Setup', url: '/management/docs/CLOUDFLARE/', description: 'Cloudflare tunnel and DNS configuration', external: false },
      { name: 'Tailscale Setup', url: '/management/docs/TAILSCALE/', description: 'Tailscale VPN integration', external: false },
      { name: 'Certbot SSL', url: '/management/docs/CERTBOT/', description: 'SSL certificate management', external: false },
      { name: 'Migration Guide', url: '/management/docs/MIGRATION/', description: 'Upgrading from previous versions', external: false },
    ]
  },
  {
    category: 'Project Resources',
    icon: DocumentTextIcon,
    links: [
      { name: 'GitHub Repository', url: 'https://github.com/rjsears/n8n_nginx', description: 'Source code and issue tracker', external: true },
      { name: 'README', url: 'https://rjsears.github.io/n8n_nginx/', description: 'Project overview and quick start', external: true },
    ]
  },
]

function close() {
  emit('close')
}

function openLink(link) {
  if (link.external) {
    window.open(link.url, '_blank', 'noopener,noreferrer')
  } else {
    window.open(link.url, '_blank')
  }
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
        <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col border border-gray-400 dark:border-gray-700">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-400 dark:border-gray-700 bg-white dark:bg-gray-800 rounded-t-lg">
            <div class="flex items-center gap-3">
              <div class="p-2 rounded-full bg-purple-100 dark:bg-purple-500/20">
                <QuestionMarkCircleIcon class="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 class="text-lg font-semibold text-primary">Help & Documentation</h3>
            </div>
            <button
              @click="close"
              class="p-1 rounded-lg text-secondary hover:text-primary hover:bg-surface-hover"
            >
              <XMarkIcon class="h-5 w-5" />
            </button>
          </div>

          <!-- Content -->
          <div class="px-6 py-4 bg-white dark:bg-gray-800 space-y-6 overflow-y-auto flex-1">
            <div
              v-for="section in helpLinks"
              :key="section.category"
              class="space-y-3"
            >
              <!-- Section Header -->
              <div class="flex items-center gap-2">
                <component :is="section.icon" class="h-5 w-5 text-gray-500 dark:text-gray-400" />
                <h4 class="font-medium text-primary">{{ section.category }}</h4>
              </div>

              <!-- Links Grid -->
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <button
                  v-for="link in section.links"
                  :key="link.name"
                  @click="openLink(link)"
                  class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-600 transition-colors text-left group"
                >
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-1">
                      <span class="font-medium text-sm text-primary group-hover:text-blue-600 dark:group-hover:text-blue-400 truncate">
                        {{ link.name }}
                      </span>
                      <ArrowTopRightOnSquareIcon v-if="link.external" class="h-3 w-3 text-gray-400 flex-shrink-0" />
                    </div>
                    <p class="text-xs text-muted mt-0.5 line-clamp-2">{{ link.description }}</p>
                  </div>
                </button>
              </div>
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
