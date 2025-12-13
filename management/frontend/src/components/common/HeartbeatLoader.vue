<script setup>
defineProps({
  text: {
    type: String,
    default: '',
  },
  textClass: {
    type: String,
    default: 'text-lg',
  },
  color: {
    type: String,
    default: 'emerald', // emerald, blue, red, etc.
  },
})
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-4">
    <!-- EKG/Heartbeat Line -->
    <div class="relative w-64 h-16 overflow-hidden">
      <svg
        class="heartbeat-svg"
        viewBox="0 0 200 50"
        preserveAspectRatio="none"
      >
        <!-- Background line -->
        <line
          x1="0" y1="25" x2="200" y2="25"
          :class="[`stroke-${color}-500/20`]"
          stroke-width="2"
        />
        <!-- Animated heartbeat path -->
        <path
          class="heartbeat-line"
          :class="[`stroke-${color}-500`]"
          fill="none"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M0,25 L30,25 L35,25 L40,10 L45,40 L50,5 L55,45 L60,25 L65,25 L200,25"
        />
        <!-- Glowing dot that follows the line -->
        <circle
          class="heartbeat-dot"
          :class="[`fill-${color}-400`]"
          r="4"
          filter="url(#glow)"
        >
          <animateMotion
            dur="1.5s"
            repeatCount="indefinite"
            path="M0,25 L30,25 L35,25 L40,10 L45,40 L50,5 L55,45 L60,25 L65,25 L200,25"
          />
        </circle>
        <!-- Glow filter -->
        <defs>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
      </svg>
    </div>

    <!-- Text -->
    <span v-if="text" :class="[textClass, 'text-secondary text-center']">{{ text }}</span>
  </div>
</template>

<style scoped>
.heartbeat-svg {
  width: 100%;
  height: 100%;
}

.heartbeat-line {
  stroke-dasharray: 300;
  stroke-dashoffset: 300;
  animation: heartbeat-draw 1.5s ease-in-out infinite;
}

@keyframes heartbeat-draw {
  0% {
    stroke-dashoffset: 300;
  }
  100% {
    stroke-dashoffset: 0;
  }
}

.heartbeat-dot {
  opacity: 0.9;
}
</style>
