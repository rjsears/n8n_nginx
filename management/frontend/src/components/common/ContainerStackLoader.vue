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
    <!-- Radar/Sonar Pulse Animation -->
    <div class="radar-container">
      <!-- Pulsing rings -->
      <div class="radar-ring ring-1"></div>
      <div class="radar-ring ring-2"></div>
      <div class="radar-ring ring-3"></div>
      <div class="radar-ring ring-4"></div>

      <!-- Center icon (container/box) -->
      <div class="radar-center">
        <svg class="w-8 h-8 text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <!-- Docker-style container icon -->
          <rect x="3" y="8" width="18" height="12" rx="1" />
          <path d="M7 8V6a2 2 0 012-2h6a2 2 0 012 2v2" />
          <line x1="8" y1="12" x2="8" y2="16" />
          <line x1="12" y1="12" x2="12" y2="16" />
          <line x1="16" y1="12" x2="16" y2="16" />
        </svg>
      </div>

      <!-- Scanning beam -->
      <div class="radar-beam"></div>

      <!-- Detected dots (blinking) -->
      <div class="detected-dot dot-1"></div>
      <div class="detected-dot dot-2"></div>
      <div class="detected-dot dot-3"></div>
    </div>

    <!-- Text -->
    <span v-if="text" :class="[textClass, 'text-secondary text-center']">{{ text }}</span>
  </div>
</template>

<style scoped>
.radar-container {
  width: 160px;
  height: 160px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.radar-ring {
  position: absolute;
  border-radius: 50%;
  border: 2px solid;
  animation: pulse-ring 3s ease-out infinite;
}

.ring-1 {
  width: 40px;
  height: 40px;
  border-color: rgba(59, 130, 246, 0.6);
  animation-delay: 0s;
}

.ring-2 {
  width: 70px;
  height: 70px;
  border-color: rgba(59, 130, 246, 0.4);
  animation-delay: 0.5s;
}

.ring-3 {
  width: 100px;
  height: 100px;
  border-color: rgba(59, 130, 246, 0.3);
  animation-delay: 1s;
}

.ring-4 {
  width: 130px;
  height: 130px;
  border-color: rgba(59, 130, 246, 0.2);
  animation-delay: 1.5s;
}

.radar-center {
  position: relative;
  z-index: 10;
  background: linear-gradient(135deg, #1e3a5f, #0f172a);
  border-radius: 50%;
  padding: 12px;
  box-shadow:
    0 0 20px rgba(59, 130, 246, 0.3),
    inset 0 0 10px rgba(59, 130, 246, 0.1);
  animation: pulse-center 2s ease-in-out infinite;
}

.radar-beam {
  position: absolute;
  width: 50%;
  height: 2px;
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.8), transparent);
  top: 50%;
  left: 50%;
  transform-origin: left center;
  animation: radar-sweep 3s linear infinite;
}

.detected-dot {
  position: absolute;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 10px rgba(16, 185, 129, 0.8);
  animation: blink-dot 1.5s ease-in-out infinite;
}

.dot-1 {
  top: 25%;
  right: 20%;
  animation-delay: 0s;
}

.dot-2 {
  bottom: 30%;
  left: 15%;
  animation-delay: 0.5s;
}

.dot-3 {
  top: 40%;
  left: 25%;
  animation-delay: 1s;
}

@keyframes pulse-ring {
  0% {
    transform: scale(0.8);
    opacity: 1;
  }
  100% {
    transform: scale(1.5);
    opacity: 0;
  }
}

@keyframes pulse-center {
  0%, 100% {
    transform: scale(1);
    box-shadow:
      0 0 20px rgba(59, 130, 246, 0.3),
      inset 0 0 10px rgba(59, 130, 246, 0.1);
  }
  50% {
    transform: scale(1.05);
    box-shadow:
      0 0 30px rgba(59, 130, 246, 0.5),
      inset 0 0 15px rgba(59, 130, 246, 0.2);
  }
}

@keyframes radar-sweep {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

@keyframes blink-dot {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.3;
    transform: scale(0.8);
  }
}
</style>
