<script setup>
import { computed } from 'vue'
import { XMarkIcon, CheckCircleIcon, ExclamationCircleIcon } from '@heroicons/vue/24/outline'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  type: {
    type: String,
    default: 'backup', // 'backup' or 'verify'
    validator: (v) => ['backup', 'verify'].includes(v)
  },
  progress: {
    type: Number,
    default: 0
  },
  progressMessage: {
    type: String,
    default: ''
  },
  status: {
    type: String,
    default: 'running' // 'running', 'success', 'failed'
  }
})

const emit = defineEmits(['close'])

// Define stages for each operation type
const backupStages = [
  { min: 0, max: 10, label: 'Initializing', description: 'Setting up backup process' },
  { min: 10, max: 40, label: 'Database Dump', description: 'Exporting PostgreSQL databases' },
  { min: 40, max: 55, label: 'Config Files', description: 'Copying configuration and SSL certificates' },
  { min: 55, max: 75, label: 'Manifests', description: 'Capturing workflow and credential manifests' },
  { min: 75, max: 85, label: 'Metadata', description: 'Writing metadata and restore script' },
  { min: 85, max: 95, label: 'Archive', description: 'Creating compressed archive' },
  { min: 95, max: 100, label: 'Finalizing', description: 'Calculating checksum and saving record' }
]

const verifyStages = [
  { min: 0, max: 10, label: 'Archive Check', description: 'Verifying archive integrity and checksum' },
  { min: 10, max: 25, label: 'Container', description: 'Starting temporary PostgreSQL container' },
  { min: 25, max: 40, label: 'Load Backup', description: 'Restoring backup into test container' },
  { min: 40, max: 55, label: 'Tables', description: 'Verifying all expected tables exist' },
  { min: 55, max: 70, label: 'Row Counts', description: 'Comparing row counts against manifest' },
  { min: 70, max: 85, label: 'Checksums', description: 'Verifying workflow data integrity' },
  { min: 85, max: 95, label: 'Config Files', description: 'Validating configuration file checksums' },
  { min: 95, max: 100, label: 'Complete', description: 'Finalizing verification results' }
]

const stages = computed(() => props.type === 'backup' ? backupStages : verifyStages)

const title = computed(() => {
  if (props.status === 'success') {
    return props.type === 'backup' ? 'Backup Complete' : 'Verification Complete'
  }
  if (props.status === 'failed') {
    return props.type === 'backup' ? 'Backup Failed' : 'Verification Failed'
  }
  return props.type === 'backup' ? 'Backup in Progress' : 'Verification in Progress'
})

const currentStageIndex = computed(() => {
  const stageList = stages.value
  for (let i = stageList.length - 1; i >= 0; i--) {
    if (props.progress >= stageList[i].min) {
      return i
    }
  }
  return 0
})

const currentStage = computed(() => stages.value[currentStageIndex.value])

// Calculate segment fill for each stage
function getSegmentStatus(stageIndex) {
  const stage = stages.value[stageIndex]

  // When failed, show the failed stage differently
  if (props.status === 'failed') {
    if (props.progress >= stage.max) {
      return 'complete' // Stages before failure
    } else if (props.progress >= stage.min) {
      return 'failed' // The stage where failure occurred
    }
    return 'pending' // Stages after failure
  }

  // Normal progress
  if (props.progress >= stage.max) {
    return 'complete' // Fully filled
  } else if (props.progress >= stage.min) {
    return 'active' // Currently in progress
  }
  return 'pending' // Not started
}

function getSegmentFillPercent(stageIndex) {
  const stage = stages.value[stageIndex]

  if (props.progress >= stage.max) {
    return 100
  } else if (props.progress >= stage.min) {
    const stageRange = stage.max - stage.min
    const progressInStage = props.progress - stage.min
    return Math.min(100, (progressInStage / stageRange) * 100)
  }
  return 0
}

// Get color class for segment based on status
function getSegmentColor(stageIndex) {
  const segmentStatus = getSegmentStatus(stageIndex)

  if (segmentStatus === 'complete') {
    return props.status === 'failed' ? 'bg-gray-400' : 'bg-emerald-500'
  } else if (segmentStatus === 'failed') {
    return 'bg-red-500'
  } else if (segmentStatus === 'active') {
    return props.type === 'backup' ? 'bg-blue-500' : 'bg-teal-500'
  }
  return 'bg-gray-300 dark:bg-gray-600'
}

function getIndicatorColor(stageIndex) {
  const segmentStatus = getSegmentStatus(stageIndex)

  if (segmentStatus === 'complete') {
    return props.status === 'failed'
      ? 'bg-gray-400 text-white'
      : 'bg-emerald-500 text-white'
  } else if (segmentStatus === 'failed') {
    return 'bg-red-500 text-white'
  } else if (segmentStatus === 'active') {
    return props.type === 'backup'
      ? 'bg-blue-500 text-white'
      : 'bg-teal-500 text-white'
  }
  return 'bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
}

const statusColor = computed(() => {
  if (props.status === 'success') return 'emerald'
  if (props.status === 'failed') return 'red'
  return props.type === 'backup' ? 'blue' : 'teal'
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="show"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="status !== 'running' && emit('close')"></div>

        <!-- Modal -->
        <div class="relative bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
          <!-- Header -->
          <div
            :class="[
              'px-6 py-4 border-b border-gray-200 dark:border-gray-700',
              status === 'success' ? 'bg-emerald-50 dark:bg-emerald-900/20' :
              status === 'failed' ? 'bg-red-50 dark:bg-red-900/20' :
              type === 'backup' ? 'bg-blue-50 dark:bg-blue-900/20' : 'bg-teal-50 dark:bg-teal-900/20'
            ]"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div
                  :class="[
                    'p-2 rounded-full',
                    status === 'success' ? 'bg-emerald-100 dark:bg-emerald-800' :
                    status === 'failed' ? 'bg-red-100 dark:bg-red-800' :
                    type === 'backup' ? 'bg-blue-100 dark:bg-blue-800' : 'bg-teal-100 dark:bg-teal-800'
                  ]"
                >
                  <CheckCircleIcon v-if="status === 'success'" class="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
                  <ExclamationCircleIcon v-else-if="status === 'failed'" class="h-6 w-6 text-red-600 dark:text-red-400" />
                  <!-- Backup Animation: Files flowing to storage -->
                  <svg v-else-if="type === 'backup'" class="h-8 w-8" viewBox="0 0 48 48" fill="none">
                    <!-- Folder -->
                    <path d="M4 12C4 10.8954 4.89543 10 6 10H16L20 14H42C43.1046 14 44 14.8954 44 16V36C44 37.1046 43.1046 38 42 38H6C4.89543 38 4 37.1046 4 36V12Z" fill="#3B82F6" opacity="0.3"/>
                    <!-- Storage/Drive -->
                    <rect x="30" y="22" width="14" height="12" rx="2" fill="#3B82F6" opacity="0.6"/>
                    <circle cx="37" cy="28" r="1.5" fill="white"/>
                    <!-- Flying Documents -->
                    <g class="backup-doc-1">
                      <rect x="12" y="18" width="8" height="10" rx="1" fill="#60A5FA"/>
                      <line x1="14" y1="21" x2="18" y2="21" stroke="white" stroke-width="1"/>
                      <line x1="14" y1="24" x2="18" y2="24" stroke="white" stroke-width="1"/>
                    </g>
                    <g class="backup-doc-2">
                      <rect x="14" y="20" width="8" height="10" rx="1" fill="#93C5FD"/>
                      <line x1="16" y1="23" x2="20" y2="23" stroke="white" stroke-width="1"/>
                      <line x1="16" y1="26" x2="20" y2="26" stroke="white" stroke-width="1"/>
                    </g>
                    <g class="backup-doc-3">
                      <rect x="16" y="22" width="8" height="10" rx="1" fill="#BFDBFE"/>
                      <line x1="18" y1="25" x2="22" y2="25" stroke="white" stroke-width="1"/>
                      <line x1="18" y1="28" x2="22" y2="28" stroke="white" stroke-width="1"/>
                    </g>
                    <!-- Arrow indicator -->
                    <path class="backup-arrow" d="M24 28L28 28M28 28L26 26M28 28L26 30" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  <!-- Verification Animation: Magnifying glass scanning files -->
                  <svg v-else class="h-8 w-8" viewBox="0 0 48 48" fill="none">
                    <!-- Documents stack -->
                    <rect x="8" y="12" width="20" height="26" rx="2" fill="#14B8A6" opacity="0.2"/>
                    <rect x="10" y="14" width="16" height="3" rx="1" fill="#14B8A6" opacity="0.4"/>
                    <rect x="10" y="19" width="16" height="3" rx="1" fill="#14B8A6" opacity="0.4"/>
                    <rect x="10" y="24" width="16" height="3" rx="1" fill="#14B8A6" opacity="0.4"/>
                    <rect x="10" y="29" width="16" height="3" rx="1" fill="#14B8A6" opacity="0.4"/>
                    <!-- Checkmarks that appear -->
                    <path class="verify-check-1" d="M26 15.5L27.5 17L30 14" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path class="verify-check-2" d="M26 20.5L27.5 22L30 19" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path class="verify-check-3" d="M26 25.5L27.5 27L30 24" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path class="verify-check-4" d="M26 30.5L27.5 32L30 29" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <!-- Magnifying glass -->
                    <g class="verify-magnifier">
                      <circle cx="34" cy="22" r="8" stroke="#0D9488" stroke-width="3" fill="white" fill-opacity="0.3"/>
                      <line x1="40" y1="28" x2="44" y2="32" stroke="#0D9488" stroke-width="3" stroke-linecap="round"/>
                      <!-- Scan line inside magnifier -->
                      <line class="verify-scan-line" x1="28" y1="22" x2="40" y2="22" stroke="#14B8A6" stroke-width="1.5" opacity="0.6"/>
                    </g>
                  </svg>
                </div>
                <div>
                  <h3 class="text-lg font-semibold text-gray-900 dark:text-white">{{ title }}</h3>
                  <p class="text-sm text-gray-600 dark:text-gray-400">
                    {{ type === 'backup' ? 'Creating full backup archive' : 'Validating backup integrity' }}
                  </p>
                </div>
              </div>
              <button
                v-if="status !== 'running'"
                @click="emit('close')"
                class="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
                <XMarkIcon class="h-5 w-5 text-gray-500" />
              </button>
            </div>
          </div>

          <!-- Content -->
          <div class="p-6">
            <!-- Overall Progress -->
            <div class="mb-6">
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-medium text-gray-700 dark:text-gray-300">Overall Progress</span>
                <span
                  :class="[
                    'text-2xl font-bold',
                    status === 'success' ? 'text-emerald-600 dark:text-emerald-400' :
                    status === 'failed' ? 'text-red-600 dark:text-red-400' :
                    type === 'backup' ? 'text-blue-600 dark:text-blue-400' : 'text-teal-600 dark:text-teal-400'
                  ]"
                >{{ progress }}%</span>
              </div>

              <!-- Full Progress Bar -->
              <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  :class="[
                    'h-full transition-all duration-500 ease-out rounded-full',
                    status === 'success' ? 'bg-emerald-500' :
                    status === 'failed' ? 'bg-red-500' :
                    type === 'backup' ? 'bg-blue-500' : 'bg-teal-500'
                  ]"
                  :style="{ width: `${progress}%` }"
                ></div>
              </div>
            </div>

            <!-- Current Action -->
            <div
              :class="[
                'mb-6 p-4 rounded-xl border-2',
                status === 'success' ? 'bg-emerald-50 border-emerald-200 dark:bg-emerald-900/20 dark:border-emerald-700' :
                status === 'failed' ? 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-700' :
                type === 'backup' ? 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-700' : 'bg-teal-50 border-teal-200 dark:bg-teal-900/20 dark:border-teal-700'
              ]"
            >
              <div class="flex items-center gap-3">
                <div
                  v-if="status === 'running'"
                  :class="[
                    'flex-shrink-0 w-3 h-3 rounded-full animate-pulse',
                    type === 'backup' ? 'bg-blue-500' : 'bg-teal-500'
                  ]"
                ></div>
                <CheckCircleIcon v-else-if="status === 'success'" class="flex-shrink-0 h-5 w-5 text-emerald-500" />
                <ExclamationCircleIcon v-else class="flex-shrink-0 h-5 w-5 text-red-500" />
                <div>
                  <p class="font-medium text-gray-900 dark:text-white">
                    {{ progressMessage || currentStage.label }}
                  </p>
                  <p class="text-sm text-gray-600 dark:text-gray-400">
                    {{ currentStage.description }}
                  </p>
                </div>
              </div>
            </div>

            <!-- Segmented Stage Progress -->
            <div class="space-y-3">
              <p class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Stages</p>
              <div class="grid gap-2">
                <div
                  v-for="(stage, index) in stages"
                  :key="index"
                  class="flex items-center gap-3"
                >
                  <!-- Stage indicator -->
                  <div
                    :class="[
                      'flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300',
                      getIndicatorColor(index)
                    ]"
                  >
                    <CheckCircleIcon v-if="getSegmentStatus(index) === 'complete'" class="h-4 w-4" />
                    <ExclamationCircleIcon v-else-if="getSegmentStatus(index) === 'failed'" class="h-4 w-4" />
                    <span v-else>{{ index + 1 }}</span>
                  </div>

                  <!-- Stage bar -->
                  <div class="flex-grow">
                    <div class="flex items-center justify-between mb-1">
                      <span
                        :class="[
                          'text-sm font-medium',
                          getSegmentStatus(index) === 'pending'
                            ? 'text-gray-400 dark:text-gray-500'
                            : getSegmentStatus(index) === 'failed'
                              ? 'text-red-600 dark:text-red-400'
                              : 'text-gray-700 dark:text-gray-300'
                        ]"
                      >{{ stage.label }}</span>
                      <span
                        v-if="getSegmentStatus(index) === 'active' || getSegmentStatus(index) === 'failed'"
                        :class="getSegmentStatus(index) === 'failed' ? 'text-xs text-red-500' : 'text-xs text-gray-500'"
                      >{{ getSegmentStatus(index) === 'failed' ? 'FAILED' : Math.round(getSegmentFillPercent(index)) + '%' }}</span>
                    </div>
                    <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                      <div
                        :class="[
                          'h-full transition-all duration-300 rounded-full',
                          getSegmentColor(index)
                        ]"
                        :style="{ width: `${getSegmentFillPercent(index)}%` }"
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div
            v-if="status !== 'running'"
            class="px-6 py-4 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-200 dark:border-gray-700"
          >
            <button
              @click="emit('close')"
              :class="[
                'w-full py-3 px-4 rounded-xl font-medium transition-colors',
                status === 'success'
                  ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                  : 'bg-gray-600 hover:bg-gray-700 text-white'
              ]"
            >
              {{ status === 'success' ? 'Done' : 'Close' }}
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
  transition: all 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .relative,
.modal-leave-to .relative {
  transform: scale(0.95) translateY(10px);
}

/* Backup Animation - Documents flying to storage */
.backup-doc-1 {
  animation: flyToStorage 2s ease-in-out infinite;
  animation-delay: 0s;
}

.backup-doc-2 {
  animation: flyToStorage 2s ease-in-out infinite;
  animation-delay: 0.3s;
}

.backup-doc-3 {
  animation: flyToStorage 2s ease-in-out infinite;
  animation-delay: 0.6s;
}

@keyframes flyToStorage {
  0% {
    transform: translateX(0) translateY(0) scale(1);
    opacity: 1;
  }
  50% {
    transform: translateX(8px) translateY(-3px) scale(0.9);
    opacity: 0.8;
  }
  80% {
    transform: translateX(14px) translateY(0) scale(0.7);
    opacity: 0.4;
  }
  100% {
    transform: translateX(16px) translateY(0) scale(0.5);
    opacity: 0;
  }
}

.backup-arrow {
  animation: pulseArrow 1s ease-in-out infinite;
}

@keyframes pulseArrow {
  0%, 100% {
    opacity: 0.4;
    transform: translateX(0);
  }
  50% {
    opacity: 1;
    transform: translateX(2px);
  }
}

/* Verification Animation - Magnifying glass scanning */
.verify-magnifier {
  animation: scanMove 3s ease-in-out infinite;
}

@keyframes scanMove {
  0%, 100% {
    transform: translateY(0);
  }
  25% {
    transform: translateY(5px);
  }
  50% {
    transform: translateY(10px);
  }
  75% {
    transform: translateY(15px);
  }
}

.verify-scan-line {
  animation: scanPulse 0.5s ease-in-out infinite;
}

@keyframes scanPulse {
  0%, 100% {
    opacity: 0.3;
  }
  50% {
    opacity: 0.8;
  }
}

/* Checkmarks appearing sequentially */
.verify-check-1 {
  animation: checkAppear 3s ease-in-out infinite;
  animation-delay: 0s;
}

.verify-check-2 {
  animation: checkAppear 3s ease-in-out infinite;
  animation-delay: 0.75s;
}

.verify-check-3 {
  animation: checkAppear 3s ease-in-out infinite;
  animation-delay: 1.5s;
}

.verify-check-4 {
  animation: checkAppear 3s ease-in-out infinite;
  animation-delay: 2.25s;
}

@keyframes checkAppear {
  0%, 20% {
    opacity: 0;
    transform: scale(0);
  }
  25%, 100% {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
