<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/ntfy/ServerSettings.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<template>
  <div class="server-settings">
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Server Settings</h3>

    <div class="space-y-6">
      <div class="rounded-lg p-4 border border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20 text-sm text-blue-900 dark:text-blue-200">
        These are the settings the running NTFY container enforces. They are read-only here:
        change the <code>NTFY_*</code> keys in <code>.env</code> (Settings &gt; Environment) and
        recreate the ntfy container to apply them.
      </div>

      <div
        v-if="config.source === 'unavailable'"
        class="rounded-lg p-4 border border-yellow-300 dark:border-yellow-700 bg-yellow-50 dark:bg-yellow-900/20 text-sm text-yellow-900 dark:text-yellow-200"
      >
        The NTFY container could not be inspected, so its settings are unknown.
      </div>

      <div
        v-else-if="config.source && accessWarning"
        class="rounded-lg p-4 border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/20 text-sm text-red-900 dark:text-red-200"
      >
        {{ accessWarning }}
      </div>

      <div
        v-for="section in sections"
        :key="section.title"
        class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-400 dark:border-gray-600"
      >
        <h4 class="font-medium text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <component :is="section.icon" class="w-5 h-5" />
          {{ section.title }}
        </h4>
        <dl class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div v-for="item in section.items" :key="item.label">
            <dt class="text-gray-500 dark:text-gray-400">{{ item.label }}</dt>
            <dd class="mt-0.5 font-medium text-gray-900 dark:text-white break-all">
              {{ item.value === undefined || item.value === null || item.value === '' ? 'Not set' : item.value }}
            </dd>
            <dd class="mt-0.5 text-xs text-gray-500">{{ item.env }}</dd>
          </div>
        </dl>
      </div>

      <!-- Status Info -->
      <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-400 dark:border-gray-600">
        <h4 class="font-medium text-gray-900 dark:text-white mb-4">Server Status</h4>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span class="text-gray-500 dark:text-gray-400">Health Status:</span>
            <span :class="[
              'ml-2 font-medium',
              config.health_status === 'healthy'
                ? 'text-green-600 dark:text-green-400'
                : 'text-red-600 dark:text-red-400'
            ]">
              {{ config.health_status || 'Unknown' }}
            </span>
          </div>

          <div>
            <span class="text-gray-500 dark:text-gray-400">Last Check:</span>
            <span class="ml-2 text-gray-900 dark:text-white">
              {{ config.last_health_check ? formatDate(config.last_health_check) : 'Never' }}
            </span>
          </div>

          <div>
            <span class="text-gray-500 dark:text-gray-400">SMTP:</span>
            <span :class="[
              'ml-2 font-medium',
              config.smtp_configured ? 'text-green-600 dark:text-green-400' : 'text-gray-500'
            ]">
              {{ config.smtp_configured ? 'Configured' : 'Not configured' }}
            </span>
          </div>

          <div>
            <span class="text-gray-500 dark:text-gray-400">Publish Token:</span>
            <span :class="[
              'ml-2 font-medium',
              config.token_configured ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
            ]">
              {{ config.token_configured ? 'Configured' : 'Missing (NTFY_TOKEN)' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  GlobeAltIcon,
  ShieldCheckIcon,
  CircleStackIcon,
  ClockIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps({
  config: { type: Object, default: () => ({}) },
})

function yesNo(value) {
  return value ? 'Enabled' : 'Disabled'
}

const accessWarning = computed(() => {
  if (!props.config.auth_enabled) {
    return 'Authentication is not enabled (NTFY_AUTH_FILE is unset): anyone who can reach the server can read and publish.'
  }
  const access = props.config.default_access
  if (access && access !== 'deny-all') {
    return `Anonymous access is "${access}". Set NTFY_AUTH_DEFAULT_ACCESS=deny-all in .env unless the server is unreachable from the internet.`
  }
  return ''
})

const sections = computed(() => [
  {
    title: 'Connection',
    icon: GlobeAltIcon,
    items: [
      { label: 'Base URL', env: 'NTFY_BASE_URL', value: props.config.base_url },
      { label: 'Upstream Base URL', env: 'NTFY_UPSTREAM_BASE_URL', value: props.config.upstream_base_url },
    ],
  },
  {
    title: 'Access Control',
    icon: ShieldCheckIcon,
    items: [
      { label: 'Authentication', env: 'NTFY_AUTH_FILE', value: yesNo(props.config.auth_enabled) },
      { label: 'Anonymous Access', env: 'NTFY_AUTH_DEFAULT_ACCESS', value: props.config.default_access },
      { label: 'Web Login', env: 'NTFY_ENABLE_LOGIN', value: yesNo(props.config.enable_login) },
      { label: 'Sign-up', env: 'NTFY_ENABLE_SIGNUP', value: yesNo(props.config.enable_signup) },
    ],
  },
  {
    title: 'Cache & Attachments',
    icon: CircleStackIcon,
    items: [
      { label: 'Cache Duration', env: 'NTFY_CACHE_DURATION', value: props.config.cache_duration },
      { label: 'Attachment Expiry', env: 'NTFY_ATTACHMENT_EXPIRY_DURATION', value: props.config.attachment_expiry_duration },
      { label: 'Total Attachment Size Limit', env: 'NTFY_ATTACHMENT_TOTAL_SIZE_LIMIT', value: props.config.attachment_total_size_limit },
      { label: 'Per-File Size Limit', env: 'NTFY_ATTACHMENT_FILE_SIZE_LIMIT', value: props.config.attachment_file_size_limit },
    ],
  },
  {
    title: 'Rate Limiting',
    icon: ClockIcon,
    items: [
      {
        label: 'Daily Message Limit per Visitor',
        env: 'NTFY_VISITOR_MESSAGE_DAILY_LIMIT',
        value: props.config.visitor_message_daily_limit ? props.config.visitor_message_daily_limit : 'Unlimited',
      },
    ],
  },
])

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString()
}
</script>
