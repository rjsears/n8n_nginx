import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import api from '@/services/api'

// Theme presets mapping to individual settings
const THEME_PRESETS = {
  modern_light: { layout: 'horizontal', colorMode: 'light', neonEffects: false },
  modern_dark: { layout: 'horizontal', colorMode: 'dark', neonEffects: false },
  dashboard_light: { layout: 'sidebar', colorMode: 'light', neonEffects: false },
  dashboard_dark_neon: { layout: 'sidebar', colorMode: 'dark', neonEffects: true },
}

export const useThemeStore = defineStore('theme', () => {
  // State
  const currentPreset = ref(localStorage.getItem('theme_preset') || 'modern_light')
  const layoutMode = ref('horizontal') // 'horizontal' or 'sidebar'
  const colorMode = ref('light') // 'light' or 'dark'
  const neonEffects = ref(false)
  const sidebarCollapsed = ref(false)

  // Getters
  const isDark = computed(() => colorMode.value === 'dark')
  const isNeon = computed(() => neonEffects.value && isDark.value)
  const isSidebar = computed(() => layoutMode.value === 'sidebar')

  const themeClasses = computed(() => {
    const classes = []
    if (isDark.value) classes.push('dark')
    if (isNeon.value) classes.push('neon-enabled')
    if (isSidebar.value) classes.push('layout-sidebar')
    else classes.push('layout-horizontal')
    return classes.join(' ')
  })

  // Actions
  function setPreset(presetName) {
    if (!THEME_PRESETS[presetName]) return

    const preset = THEME_PRESETS[presetName]
    currentPreset.value = presetName
    layoutMode.value = preset.layout
    colorMode.value = preset.colorMode
    neonEffects.value = preset.neonEffects

    localStorage.setItem('theme_preset', presetName)
    applyTheme()
    saveToServer()
  }

  function setColorMode(mode) {
    colorMode.value = mode
    // Update preset to match if possible
    updatePresetFromSettings()
    applyTheme()
    saveToServer()
  }

  function setLayoutMode(mode) {
    layoutMode.value = mode
    updatePresetFromSettings()
    applyTheme()
    saveToServer()
  }

  function toggleNeonEffects() {
    neonEffects.value = !neonEffects.value
    updatePresetFromSettings()
    applyTheme()
    saveToServer()
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    localStorage.setItem('sidebar_collapsed', sidebarCollapsed.value)
  }

  function toggleColorMode() {
    setColorMode(colorMode.value === 'light' ? 'dark' : 'light')
  }

  function updatePresetFromSettings() {
    // Find matching preset
    for (const [name, preset] of Object.entries(THEME_PRESETS)) {
      if (
        preset.layout === layoutMode.value &&
        preset.colorMode === colorMode.value &&
        preset.neonEffects === neonEffects.value
      ) {
        currentPreset.value = name
        localStorage.setItem('theme_preset', name)
        return
      }
    }
    // No match - custom combination
    currentPreset.value = 'custom'
  }

  function applyTheme() {
    const html = document.documentElement
    const body = document.body

    // Reset classes
    html.classList.remove('dark', 'neon-enabled', 'layout-sidebar', 'layout-horizontal')
    body.classList.remove('dark', 'neon-enabled', 'layout-sidebar', 'layout-horizontal')

    // Apply new classes
    if (isDark.value) {
      html.classList.add('dark')
      body.classList.add('dark')
    }
    if (isNeon.value) {
      html.classList.add('neon-enabled')
      body.classList.add('neon-enabled')
    }
    if (isSidebar.value) {
      html.classList.add('layout-sidebar')
      body.classList.add('layout-sidebar')
    } else {
      html.classList.add('layout-horizontal')
      body.classList.add('layout-horizontal')
    }
  }

  async function saveToServer() {
    try {
      await api.put('/settings/appearance', {
        value: {
          preset: currentPreset.value,
          layout: layoutMode.value,
          colorMode: colorMode.value,
          neonEffects: neonEffects.value,
        }
      })
    } catch {
      // Ignore errors - local storage is fallback
    }
  }

  async function loadFromServer() {
    try {
      const response = await api.get('/settings/appearance')
      if (response.data?.value) {
        const settings = response.data.value
        if (settings.preset && THEME_PRESETS[settings.preset]) {
          setPreset(settings.preset)
        } else {
          layoutMode.value = settings.layout || 'horizontal'
          colorMode.value = settings.colorMode || 'light'
          neonEffects.value = settings.neonEffects || false
          applyTheme()
        }
      }
    } catch {
      // Use local storage fallback
      init()
    }
  }

  function init() {
    // Load from local storage
    const savedPreset = localStorage.getItem('theme_preset')
    const savedCollapsed = localStorage.getItem('sidebar_collapsed')

    if (savedPreset && THEME_PRESETS[savedPreset]) {
      setPreset(savedPreset)
    } else {
      // System preference
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        setPreset('modern_dark')
      }
    }

    if (savedCollapsed !== null) {
      sidebarCollapsed.value = savedCollapsed === 'true'
    }

    applyTheme()
  }

  return {
    // State
    currentPreset,
    layoutMode,
    colorMode,
    neonEffects,
    sidebarCollapsed,
    // Getters
    isDark,
    isNeon,
    isSidebar,
    themeClasses,
    // Computed properties for v-model binding
    get layout() { return layoutMode.value },
    set layout(val) { setLayoutMode(val) },
    // Actions
    setPreset,
    applyPreset: setPreset, // Alias for SettingsView compatibility
    setColorMode,
    setLayoutMode,
    toggleNeonEffects,
    toggleSidebar,
    toggleColorMode,
    applyTheme,
    loadFromServer,
    init,
  }
})
