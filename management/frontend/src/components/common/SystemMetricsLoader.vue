<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/common/SystemMetricsLoader.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useThemeStore } from '@/stores/theme'

defineProps({
  text: {
    type: String,
    default: 'Loading system metrics...',
  },
})

const themeStore = useThemeStore()

// Animated text that cycles through loading messages
const loadingMessages = [
  'Gathering CPU metrics...',
  'Analyzing memory usage...',
  'Checking disk space...',
  'Monitoring containers...',
  'Calculating network stats...',
  'Processing system data...',
]
const currentMessage = ref(0)
let messageInterval = null

onMounted(() => {
  messageInterval = setInterval(() => {
    currentMessage.value = (currentMessage.value + 1) % loadingMessages.length
  }, 2000)
})

onUnmounted(() => {
  if (messageInterval) clearInterval(messageInterval)
})
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12 px-4">
    <!-- Main animated graphic -->
    <div class="relative w-48 h-48 mb-6">
      <!-- Outer rotating ring -->
      <div class="absolute inset-0 rounded-full border-4 border-dashed animate-spin-slow"
           :class="themeStore.isNeon ? 'border-cyan-500/30' : 'border-blue-500/30'"></div>

      <!-- Middle pulsing ring -->
      <div class="absolute inset-4 rounded-full animate-pulse-ring"
           :class="themeStore.isNeon ? 'bg-cyan-500/10 border-2 border-cyan-400/50' : 'bg-blue-500/10 border-2 border-blue-400/50'"></div>

      <!-- Inner container with server icon -->
      <div class="absolute inset-8 rounded-full flex items-center justify-center"
           :class="themeStore.isNeon ? 'bg-gray-900/80' : 'bg-gray-100 dark:bg-gray-800'">

        <!-- Animated server/metrics visualization -->
        <div class="relative">
          <!-- Central server icon -->
          <svg class="w-16 h-16" :class="themeStore.isNeon ? 'text-cyan-400' : 'text-blue-500'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <!-- Server rack -->
            <rect x="4" y="2" width="16" height="6" rx="1" class="animate-pulse" />
            <rect x="4" y="9" width="16" height="6" rx="1" class="animate-pulse" style="animation-delay: 0.2s" />
            <rect x="4" y="16" width="16" height="6" rx="1" class="animate-pulse" style="animation-delay: 0.4s" />
            <!-- Status lights -->
            <circle cx="7" cy="5" r="1" fill="currentColor" class="animate-blink" />
            <circle cx="7" cy="12" r="1" fill="currentColor" class="animate-blink" style="animation-delay: 0.3s" />
            <circle cx="7" cy="19" r="1" fill="currentColor" class="animate-blink" style="animation-delay: 0.6s" />
            <!-- Slots -->
            <line x1="10" y1="5" x2="17" y2="5" stroke-linecap="round" />
            <line x1="10" y1="12" x2="17" y2="12" stroke-linecap="round" />
            <line x1="10" y1="19" x2="17" y2="19" stroke-linecap="round" />
          </svg>

          <!-- Orbiting data particles -->
          <div class="absolute -inset-6 animate-orbit">
            <div class="w-2 h-2 rounded-full absolute top-0 left-1/2 -translate-x-1/2"
                 :class="themeStore.isNeon ? 'bg-cyan-400 shadow-lg shadow-cyan-400/50' : 'bg-blue-500'"></div>
          </div>
          <div class="absolute -inset-6 animate-orbit-reverse">
            <div class="w-2 h-2 rounded-full absolute top-0 left-1/2 -translate-x-1/2"
                 :class="themeStore.isNeon ? 'bg-purple-400 shadow-lg shadow-purple-400/50' : 'bg-purple-500'"></div>
          </div>
          <div class="absolute -inset-6 animate-orbit-slow">
            <div class="w-1.5 h-1.5 rounded-full absolute bottom-0 left-1/2 -translate-x-1/2"
                 :class="themeStore.isNeon ? 'bg-emerald-400 shadow-lg shadow-emerald-400/50' : 'bg-emerald-500'"></div>
          </div>
        </div>
      </div>

      <!-- Data flow lines -->
      <svg class="absolute inset-0 w-full h-full" viewBox="0 0 200 200">
        <!-- Animated data streams -->
        <path d="M100 10 L100 40" stroke-dasharray="4 4" class="animate-dash"
              :class="themeStore.isNeon ? 'stroke-cyan-400/60' : 'stroke-blue-400/60'" stroke-width="2" fill="none" />
        <path d="M100 160 L100 190" stroke-dasharray="4 4" class="animate-dash"
              :class="themeStore.isNeon ? 'stroke-cyan-400/60' : 'stroke-blue-400/60'" stroke-width="2" fill="none" />
        <path d="M10 100 L40 100" stroke-dasharray="4 4" class="animate-dash"
              :class="themeStore.isNeon ? 'stroke-purple-400/60' : 'stroke-purple-400/60'" stroke-width="2" fill="none" />
        <path d="M160 100 L190 100" stroke-dasharray="4 4" class="animate-dash"
              :class="themeStore.isNeon ? 'stroke-purple-400/60' : 'stroke-purple-400/60'" stroke-width="2" fill="none" />
      </svg>
    </div>

    <!-- Animated bars representing metrics -->
    <div class="flex gap-1 mb-4 h-8 items-end">
      <div v-for="i in 12" :key="i"
           class="w-2 rounded-t animate-bar"
           :class="themeStore.isNeon ? 'bg-gradient-to-t from-cyan-600 to-cyan-400' : 'bg-gradient-to-t from-blue-600 to-blue-400'"
           :style="{ animationDelay: `${i * 0.1}s` }"></div>
    </div>

    <!-- Loading text with transition -->
    <transition name="fade" mode="out-in">
      <p :key="currentMessage" class="text-sm font-medium"
         :class="themeStore.isNeon ? 'text-cyan-400' : 'text-blue-500'">
        {{ loadingMessages[currentMessage] }}
      </p>
    </transition>

    <!-- Progress dots -->
    <div class="flex gap-2 mt-3">
      <span v-for="i in 3" :key="i"
            class="w-2 h-2 rounded-full animate-bounce"
            :class="themeStore.isNeon ? 'bg-cyan-400' : 'bg-blue-500'"
            :style="{ animationDelay: `${i * 0.15}s` }"></span>
    </div>
  </div>
</template>

<style scoped>
@keyframes spin-slow {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes pulse-ring {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.05); opacity: 0.8; }
}

@keyframes orbit {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes orbit-reverse {
  from { transform: rotate(360deg); }
  to { transform: rotate(0deg); }
}

@keyframes orbit-slow {
  from { transform: rotate(180deg); }
  to { transform: rotate(540deg); }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

@keyframes dash {
  to { stroke-dashoffset: -16; }
}

@keyframes bar {
  0%, 100% { height: 8px; }
  50% { height: 32px; }
}

.animate-spin-slow {
  animation: spin-slow 8s linear infinite;
}

.animate-pulse-ring {
  animation: pulse-ring 2s ease-in-out infinite;
}

.animate-orbit {
  animation: orbit 3s linear infinite;
}

.animate-orbit-reverse {
  animation: orbit-reverse 4s linear infinite;
}

.animate-orbit-slow {
  animation: orbit-slow 5s linear infinite;
}

.animate-blink {
  animation: blink 1s ease-in-out infinite;
}

.animate-dash {
  animation: dash 1s linear infinite;
}

.animate-bar {
  animation: bar 1s ease-in-out infinite;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
