<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/common/DnaHelixLoader.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
-->
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
  <div class="flex flex-col items-center justify-center gap-4">
    <!-- DNA Helix Animation -->
    <div class="dna-container">
      <div class="dna-helix">
        <div v-for="i in 10" :key="i" class="dna-strand" :style="{ animationDelay: `${(i - 1) * 0.1}s` }">
          <div class="dna-dot dna-dot-left"></div>
          <div class="dna-connector"></div>
          <div class="dna-dot dna-dot-right"></div>
        </div>
      </div>
    </div>

    <!-- Text -->
    <span v-if="text" :class="[textClass, 'text-secondary text-center']">{{ text }}</span>
  </div>
</template>

<style scoped>
.dna-container {
  width: 60px;
  height: 80px;
  perspective: 500px;
}

.dna-helix {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transform-style: preserve-3d;
}

.dna-strand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 6px;
  animation: dna-rotate 2s ease-in-out infinite;
  transform-style: preserve-3d;
}

.dna-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dna-dot-left {
  background: linear-gradient(135deg, #3b82f6, #60a5fa);
  box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
}

.dna-dot-right {
  background: linear-gradient(135deg, #8b5cf6, #a78bfa);
  box-shadow: 0 0 10px rgba(139, 92, 246, 0.5);
}

.dna-connector {
  flex: 1;
  height: 2px;
  margin: 0 2px;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6);
  opacity: 0.6;
  border-radius: 1px;
}

@keyframes dna-rotate {
  0% {
    transform: rotateY(0deg) scaleX(1);
  }
  25% {
    transform: rotateY(90deg) scaleX(0.1);
  }
  50% {
    transform: rotateY(180deg) scaleX(1);
  }
  75% {
    transform: rotateY(270deg) scaleX(0.1);
  }
  100% {
    transform: rotateY(360deg) scaleX(1);
  }
}

/* Stagger the animation for each strand */
.dna-strand:nth-child(1) { animation-delay: 0s; }
.dna-strand:nth-child(2) { animation-delay: 0.1s; }
.dna-strand:nth-child(3) { animation-delay: 0.2s; }
.dna-strand:nth-child(4) { animation-delay: 0.3s; }
.dna-strand:nth-child(5) { animation-delay: 0.4s; }
.dna-strand:nth-child(6) { animation-delay: 0.5s; }
.dna-strand:nth-child(7) { animation-delay: 0.6s; }
.dna-strand:nth-child(8) { animation-delay: 0.7s; }
.dna-strand:nth-child(9) { animation-delay: 0.8s; }
.dna-strand:nth-child(10) { animation-delay: 0.9s; }
</style>
