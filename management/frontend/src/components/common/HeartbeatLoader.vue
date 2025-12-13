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
  <div class="flex flex-col items-center justify-center gap-6">
    <!-- EKG Monitor Display -->
    <div class="ekg-monitor">
      <!-- Monitor screen background -->
      <div class="ekg-screen">
        <svg
          class="ekg-svg"
          viewBox="0 0 300 80"
          preserveAspectRatio="xMidYMid meet"
        >
          <!-- Grid lines for monitor effect -->
          <defs>
            <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(16, 185, 129, 0.1)" stroke-width="0.5"/>
            </pattern>
            <!-- Glow filter for the trace -->
            <filter id="ekg-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
              <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
            <!-- Gradient for fade effect -->
            <linearGradient id="trace-fade" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="rgb(16, 185, 129)" stop-opacity="0"/>
              <stop offset="70%" stop-color="rgb(16, 185, 129)" stop-opacity="0.5"/>
              <stop offset="100%" stop-color="rgb(16, 185, 129)" stop-opacity="1"/>
            </linearGradient>
          </defs>

          <!-- Grid background -->
          <rect width="100%" height="100%" fill="url(#grid)"/>

          <!-- Base flatline (dimmed) -->
          <line x1="0" y1="40" x2="300" y2="40" stroke="rgba(16, 185, 129, 0.15)" stroke-width="1"/>

          <!-- EKG trace line - the main animated path -->
          <g class="ekg-trace-group">
            <!-- Shadow/glow layer -->
            <path
              class="ekg-trace ekg-trace-glow"
              fill="none"
              stroke="rgb(16, 185, 129)"
              stroke-width="3"
              stroke-linecap="round"
              stroke-linejoin="round"
              filter="url(#ekg-glow)"
              d="M0,40 L40,40 L50,40 L55,38 L60,42 L65,35 L70,20 L75,60 L80,10 L85,70 L90,40 L95,40 L100,38 L105,40 L150,40 L160,40 L165,38 L170,42 L175,35 L180,20 L185,60 L190,10 L195,70 L200,40 L205,40 L210,38 L215,40 L260,40 L270,40 L275,38 L280,42 L285,35 L290,20 L295,60 L300,40"
            />
            <!-- Main bright trace -->
            <path
              class="ekg-trace"
              fill="none"
              stroke="rgb(52, 211, 153)"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M0,40 L40,40 L50,40 L55,38 L60,42 L65,35 L70,20 L75,60 L80,10 L85,70 L90,40 L95,40 L100,38 L105,40 L150,40 L160,40 L165,38 L170,42 L175,35 L180,20 L185,60 L190,10 L195,70 L200,40 L205,40 L210,38 L215,40 L260,40 L270,40 L275,38 L280,42 L285,35 L290,20 L295,60 L300,40"
            />
          </g>

          <!-- Scanning line (vertical) -->
          <line class="scan-line" x1="0" y1="0" x2="0" y2="80" stroke="rgba(52, 211, 153, 0.8)" stroke-width="2"/>

          <!-- Bright dot at scan position -->
          <circle class="scan-dot" cx="0" cy="40" r="4" fill="rgb(52, 211, 153)" filter="url(#ekg-glow)"/>
        </svg>
      </div>
    </div>

    <!-- Text -->
    <span v-if="text" :class="[textClass, 'text-secondary text-center']">{{ text }}</span>
  </div>
</template>

<style scoped>
.ekg-monitor {
  width: 320px;
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
  padding: 8px;
  overflow: hidden;
}

.ekg-svg {
  width: 100%;
  height: 80px;
  display: block;
}

/* Main trace animation - draw effect */
.ekg-trace {
  stroke-dasharray: 800;
  stroke-dashoffset: 800;
  animation: trace-draw 2.5s linear infinite;
}

.ekg-trace-glow {
  opacity: 0.4;
  animation: trace-draw 2.5s linear infinite;
}

@keyframes trace-draw {
  0% {
    stroke-dashoffset: 800;
  }
  100% {
    stroke-dashoffset: 0;
  }
}

/* Scanning vertical line */
.scan-line {
  animation: scan-move 2.5s linear infinite;
}

/* Scanning dot */
.scan-dot {
  animation: dot-move 2.5s linear infinite;
}

@keyframes scan-move {
  0% {
    transform: translateX(0);
    opacity: 1;
  }
  100% {
    transform: translateX(300px);
    opacity: 1;
  }
}

@keyframes dot-move {
  0% {
    transform: translate(0, 0);
  }
  /* Flatline section */
  13% { transform: translate(40px, 0); }
  17% { transform: translate(50px, 0); }
  /* P wave */
  18% { transform: translate(55px, -2px); }
  20% { transform: translate(60px, 2px); }
  /* QRS complex */
  22% { transform: translate(65px, -5px); }
  23% { transform: translate(70px, -20px); }
  25% { transform: translate(75px, 20px); }
  27% { transform: translate(80px, -30px); }
  28% { transform: translate(85px, 30px); }
  30% { transform: translate(90px, 0); }
  /* T wave */
  32% { transform: translate(95px, 0); }
  33% { transform: translate(100px, -2px); }
  35% { transform: translate(105px, 0); }
  /* Continue to next beat... */
  100% { transform: translate(300px, 0); }
}
</style>
