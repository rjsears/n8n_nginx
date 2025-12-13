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
})
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-6">
    <!-- EKG Monitor Display -->
    <div class="ekg-monitor">
      <!-- Monitor screen background -->
      <div class="ekg-screen">
        <svg
          class="ekg-svg"
          viewBox="0 0 400 80"
          preserveAspectRatio="xMidYMid meet"
        >
          <!-- Grid lines for monitor effect -->
          <defs>
            <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(16, 185, 129, 0.08)" stroke-width="0.5"/>
            </pattern>
            <!-- Glow filter for the trace -->
            <filter id="ekg-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
              <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>

          <!-- Grid background -->
          <rect width="100%" height="100%" fill="url(#grid)"/>

          <!-- Base flatline (very dim) -->
          <line x1="0" y1="40" x2="400" y2="40" stroke="rgba(16, 185, 129, 0.1)" stroke-width="1"/>

          <!-- EKG trace - glow layer -->
          <path
            class="ekg-trace ekg-glow"
            fill="none"
            stroke="rgb(16, 185, 129)"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
            filter="url(#ekg-glow)"
            d="M0,40 L60,40 L70,40 L75,38 L80,42 L85,35 L92,15 L100,65 L108,8 L116,72 L124,40 L130,40 L138,36 L145,40
               L200,40 L210,40 L215,38 L220,42 L225,35 L232,15 L240,65 L248,8 L256,72 L264,40 L270,40 L278,36 L285,40
               L340,40 L350,40 L355,38 L360,42 L365,35 L372,15 L380,65 L388,8 L396,72 L400,40"
          />
          <!-- EKG trace - main bright line -->
          <path
            class="ekg-trace"
            fill="none"
            stroke="rgb(52, 211, 153)"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M0,40 L60,40 L70,40 L75,38 L80,42 L85,35 L92,15 L100,65 L108,8 L116,72 L124,40 L130,40 L138,36 L145,40
               L200,40 L210,40 L215,38 L220,42 L225,35 L232,15 L240,65 L248,8 L256,72 L264,40 L270,40 L278,36 L285,40
               L340,40 L350,40 L355,38 L360,42 L365,35 L372,15 L380,65 L388,8 L396,72 L400,40"
          />
        </svg>
      </div>
    </div>

    <!-- Text -->
    <span v-if="text" :class="[textClass, 'text-secondary text-center']">{{ text }}</span>
  </div>
</template>

<style scoped>
.ekg-monitor {
  width: 420px;
  padding: 8px;
  background: linear-gradient(145deg, #1a1a2e, #16213e);
  border-radius: 12px;
  box-shadow:
    0 4px 6px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.ekg-screen {
  background: linear-gradient(180deg, #0a1628, #0d1f3c);
  border-radius: 8px;
  padding: 12px;
  overflow: hidden;
}

.ekg-svg {
  width: 100%;
  height: 80px;
  display: block;
}

/* Main trace animation - draws the line */
.ekg-trace {
  stroke-dasharray: 1200;
  stroke-dashoffset: 1200;
  animation: trace-draw 4s linear infinite;
}

.ekg-glow {
  opacity: 0.3;
}

@keyframes trace-draw {
  0% {
    stroke-dashoffset: 1200;
  }
  100% {
    stroke-dashoffset: 0;
  }
}
</style>
