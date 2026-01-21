<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/views/FileBrowserView.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref } from 'vue'
import { FolderIcon, ArrowPathIcon } from '@heroicons/vue/24/outline'
import Card from '../components/common/Card.vue'
import LoadingSpinner from '../components/common/LoadingSpinner.vue'

const loading = ref(true)
const iframeSrc = ref('/files/')
const iframeRef = ref(null)

function onIframeLoad() {
  loading.value = false
}

function refreshIframe() {
  loading.value = true
  // Force reload by resetting src
  const src = iframeSrc.value
  iframeSrc.value = ''
  setTimeout(() => {
    iframeSrc.value = src
  }, 50)
}
</script>

<template>
  <div class="space-y-6 h-full flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between flex-shrink-0">
      <div>
        <h1 class="text-2xl font-bold text-primary">
          File Manager
        </h1>
        <p class="text-secondary mt-1">Manage public website files</p>
      </div>
      <button
        @click="refreshIframe"
        class="btn-secondary flex items-center gap-2"
      >
        <ArrowPathIcon class="h-4 w-4" />
        Refresh
      </button>
    </div>

    <!-- Iframe Card -->
    <Card :padding="false" class="flex-1 flex flex-col overflow-hidden border border-gray-400 dark:border-black shadow-sm">
      <div class="relative w-full h-full bg-white dark:bg-gray-900">
        <LoadingSpinner 
          v-if="loading" 
          text="Loading File Browser..." 
          class="absolute inset-0 z-10 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm" 
        />
        
        <iframe
          ref="iframeRef"
          v-if="iframeSrc"
          :src="iframeSrc"
          class="w-full h-full border-0"
          @load="onIframeLoad"
        ></iframe>
      </div>
    </Card>
  </div>
</template>
