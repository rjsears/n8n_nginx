<!--
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/components/common/BackupScanLoader.vue

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
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
  <div class="flex flex-col items-center justify-center gap-5">
    <!-- Backup Archive Scanner Animation -->
    <div class="scanner-container">
      <!-- Animated file blocks flying into archive -->
      <div class="file-stream">
        <div class="file-block file-1">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z"/>
            <path d="M14 2v6h6"/>
          </svg>
        </div>
        <div class="file-block file-2">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M4 4h16a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2V6a2 2 0 012-2z"/>
            <path d="M8 10h8M8 14h4"/>
          </svg>
        </div>
        <div class="file-block file-3">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 6v6l4 2"/>
          </svg>
        </div>
      </div>

      <!-- Central archive box -->
      <div class="archive-box">
        <div class="archive-lid"></div>
        <div class="archive-body">
          <!-- Archive stripes -->
          <div class="archive-stripe"></div>
          <div class="archive-stripe"></div>
          <div class="archive-stripe"></div>
        </div>
        <!-- Scanning line -->
        <div class="scan-line"></div>
      </div>

      <!-- Data particles emanating -->
      <div class="particles">
        <div class="particle p1"></div>
        <div class="particle p2"></div>
        <div class="particle p3"></div>
        <div class="particle p4"></div>
        <div class="particle p5"></div>
        <div class="particle p6"></div>
      </div>

      <!-- Orbit ring -->
      <div class="orbit-ring">
        <div class="orbit-dot"></div>
      </div>
    </div>

    <!-- Text -->
    <span v-if="text" :class="[textClass, 'text-secondary text-center']">{{ text }}</span>
  </div>
</template>

<style scoped>
.scanner-container {
  width: 140px;
  height: 140px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* File stream - files flying toward archive */
.file-stream {
  position: absolute;
  width: 100%;
  height: 100%;
}

.file-block {
  position: absolute;
  padding: 6px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  border-radius: 4px;
  color: white;
  box-shadow: 0 0 15px rgba(59, 130, 246, 0.5);
  animation: fly-to-archive 2.5s ease-in-out infinite;
}

.file-1 {
  top: 5%;
  left: 10%;
  animation-delay: 0s;
}

.file-2 {
  top: 15%;
  right: 5%;
  animation-delay: 0.8s;
}

.file-3 {
  bottom: 20%;
  left: 5%;
  animation-delay: 1.6s;
}

/* Central archive box */
.archive-box {
  position: relative;
  width: 50px;
  height: 45px;
  z-index: 10;
}

.archive-lid {
  position: absolute;
  top: 0;
  left: -3px;
  right: -3px;
  height: 12px;
  background: linear-gradient(180deg, #10b981, #059669);
  border-radius: 4px 4px 0 0;
  box-shadow: 0 -2px 10px rgba(16, 185, 129, 0.4);
  animation: lid-bounce 1.5s ease-in-out infinite;
  transform-origin: bottom center;
}

.archive-body {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 35px;
  background: linear-gradient(180deg, #064e3b, #022c22);
  border-radius: 0 0 6px 6px;
  border: 2px solid #10b981;
  overflow: hidden;
  box-shadow:
    0 4px 20px rgba(16, 185, 129, 0.3),
    inset 0 0 20px rgba(16, 185, 129, 0.1);
}

.archive-stripe {
  height: 6px;
  margin: 4px 6px;
  background: linear-gradient(90deg, transparent, rgba(16, 185, 129, 0.4), transparent);
  border-radius: 2px;
  animation: stripe-pulse 1s ease-in-out infinite;
}

.archive-stripe:nth-child(1) { animation-delay: 0s; }
.archive-stripe:nth-child(2) { animation-delay: 0.2s; }
.archive-stripe:nth-child(3) { animation-delay: 0.4s; }

/* Scanning line */
.scan-line {
  position: absolute;
  left: 5px;
  right: 5px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #34d399, transparent);
  box-shadow: 0 0 10px #34d399;
  animation: scan-move 1.5s ease-in-out infinite;
}

/* Data particles */
.particles {
  position: absolute;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.particle {
  position: absolute;
  width: 6px;
  height: 6px;
  background: #60a5fa;
  border-radius: 50%;
  box-shadow: 0 0 8px rgba(96, 165, 250, 0.8);
  animation: particle-float 3s ease-in-out infinite;
}

.p1 { top: 50%; left: 30%; animation-delay: 0s; }
.p2 { top: 40%; right: 25%; animation-delay: 0.5s; }
.p3 { bottom: 35%; left: 20%; animation-delay: 1s; }
.p4 { top: 30%; left: 50%; animation-delay: 1.5s; }
.p5 { bottom: 40%; right: 20%; animation-delay: 2s; }
.p6 { top: 55%; right: 30%; animation-delay: 2.5s; }

/* Orbit ring */
.orbit-ring {
  position: absolute;
  width: 110px;
  height: 110px;
  border: 2px dashed rgba(59, 130, 246, 0.3);
  border-radius: 50%;
  animation: orbit-spin 8s linear infinite;
}

.orbit-dot {
  position: absolute;
  top: -5px;
  left: 50%;
  transform: translateX(-50%);
  width: 10px;
  height: 10px;
  background: linear-gradient(135deg, #f59e0b, #d97706);
  border-radius: 50%;
  box-shadow: 0 0 12px rgba(245, 158, 11, 0.7);
}

/* Animations */
@keyframes fly-to-archive {
  0% {
    opacity: 0;
    transform: scale(0.5) translate(0, 0);
  }
  20% {
    opacity: 1;
    transform: scale(1) translate(0, 0);
  }
  80% {
    opacity: 1;
    transform: scale(0.6) translate(calc(50% - 20px), calc(50% - 15px));
  }
  100% {
    opacity: 0;
    transform: scale(0.3) translate(calc(50% - 20px), calc(50% - 15px));
  }
}

@keyframes lid-bounce {
  0%, 100% {
    transform: rotateX(0deg);
  }
  50% {
    transform: rotateX(-15deg);
  }
}

@keyframes stripe-pulse {
  0%, 100% {
    opacity: 0.4;
    transform: scaleX(0.8);
  }
  50% {
    opacity: 1;
    transform: scaleX(1);
  }
}

@keyframes scan-move {
  0% {
    top: 12px;
    opacity: 0;
  }
  10% {
    opacity: 1;
  }
  90% {
    opacity: 1;
  }
  100% {
    top: 40px;
    opacity: 0;
  }
}

@keyframes particle-float {
  0%, 100% {
    opacity: 0;
    transform: translateY(0) scale(0.5);
  }
  25% {
    opacity: 1;
    transform: translateY(-10px) scale(1);
  }
  75% {
    opacity: 1;
    transform: translateY(-25px) scale(0.8);
  }
}

@keyframes orbit-spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
</style>
