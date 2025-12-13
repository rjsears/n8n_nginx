import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'

// Theme presets mapping to individual settings
const THEME_PRESETS = {
  modern_light: { layout: 'horizontal', colorMode: 'light', neonEffects: false },
  modern_dark: { layout: 'horizontal', colorMode: 'dark', neonEffects: false },
  dashboard_light: { layout: 'sidebar', colorMode: 'light', neonEffects: false },
  dashboard_dark_neon: { layout: 'sidebar', colorMode: 'dark', neonEffects: true },
}

export const useThemeStore = defineStore('theme', () => {
  // Internal state
  const _currentPreset = ref(localStorage.getItem('theme_preset') || 'modern_light')
  const _layoutMode = ref('horizontal') // 'horizontal' or 'sidebar'
  const _colorMode = ref('light') // 'light' or 'dark'
  const _neonEffects = ref(false)
  const _sidebarCollapsed = ref(false)

  // Read-only getters
  const isDark = computed(() => _colorMode.value === 'dark')
  const isNeon = computed(() => _neonEffects.value && isDark.value)
  const isSidebar = computed(() => _layoutMode.value === 'sidebar')
  const currentPreset = computed(() => _currentPreset.value)
  const sidebarCollapsed = computed(() => _sidebarCollapsed.value)

  const themeClasses = computed(() => {
    const classes = []
    if (isDark.value) classes.push('dark')
    if (isNeon.value) classes.push('neon-enabled')
    if (isSidebar.value) classes.push('layout-sidebar')
    else classes.push('layout-horizontal')
    return classes.join(' ')
  })

  // Writable computed properties for v-model binding
  const layout = computed({
    get: () => _layoutMode.value,
    set: (val) => setLayoutMode(val)
  })

  const colorMode = computed({
    get: () => _colorMode.value,
    set: (val) => setColorMode(val)
  })

  const neonEffects = computed({
    get: () => _neonEffects.value,
    set: (val) => setNeonEffects(val)
  })

  // Apply theme to DOM
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

  // Update preset based on current settings
  function updatePresetFromSettings() {
    for (const [name, preset] of Object.entries(THEME_PRESETS)) {
      if (
        preset.layout === _layoutMode.value &&
        preset.colorMode === _colorMode.value &&
        preset.neonEffects === _neonEffects.value
      ) {
        _currentPreset.value = name
        localStorage.setItem('theme_preset', name)
        return
      }
    }
    // No match - custom combination
    _currentPreset.value = 'custom'
  }

  // Save to server
  async function saveToServer() {
    try {
      await api.put('/settings/appearance', {
        value: {
          preset: _currentPreset.value,
          layout: _layoutMode.value,
          colorMode: _colorMode.value,
          neonEffects: _neonEffects.value,
        }
      })
    } catch {
      // Ignore errors - local storage is fallback
    }
  }

  // Actions
  function setPreset(presetName) {
    if (!THEME_PRESETS[presetName]) return

    const preset = THEME_PRESETS[presetName]
    _currentPreset.value = presetName
    _layoutMode.value = preset.layout
    _colorMode.value = preset.colorMode
    _neonEffects.value = preset.neonEffects

    localStorage.setItem('theme_preset', presetName)
    applyTheme()
    saveToServer()
  }

  function setColorMode(mode) {
    _colorMode.value = mode
    updatePresetFromSettings()
    applyTheme()
    saveToServer()
  }

  function setLayoutMode(mode) {
    _layoutMode.value = mode
    updatePresetFromSettings()
    applyTheme()
    saveToServer()
  }

  function setNeonEffects(enabled) {
    _neonEffects.value = enabled
    updatePresetFromSettings()
    applyTheme()
    saveToServer()
  }

  function toggleNeonEffects() {
    setNeonEffects(!_neonEffects.value)
  }

  function toggleSidebar() {
    _sidebarCollapsed.value = !_sidebarCollapsed.value
    localStorage.setItem('sidebar_collapsed', _sidebarCollapsed.value)
  }

  function toggleColorMode() {
    setColorMode(_colorMode.value === 'light' ? 'dark' : 'light')
  }

  async function loadFromServer() {
    try {
      const response = await api.get('/settings/appearance')
      if (response.data?.value) {
        const settings = response.data.value
        if (settings.preset && THEME_PRESETS[settings.preset]) {
          setPreset(settings.preset)
        } else {
          _layoutMode.value = settings.layout || 'horizontal'
          _colorMode.value = settings.colorMode || 'light'
          _neonEffects.value = settings.neonEffects || false
          updatePresetFromSettings()
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
      } else {
        // Apply default
        applyTheme()
      }
    }

    if (savedCollapsed !== null) {
      _sidebarCollapsed.value = savedCollapsed === 'true'
    }
  }

  return {
    // Read-only state
    currentPreset,
    sidebarCollapsed,
    // Computed getters
    isDark,
    isNeon,
    isSidebar,
    themeClasses,
    // Writable computed for v-model binding
    layout,
    colorMode,
    neonEffects,
    // Also expose internal refs for direct reading (legacy compatibility)
    layoutMode: _layoutMode,
    // Actions
    setPreset,
    applyPreset: setPreset, // Alias for SettingsView compatibility
    setColorMode,
    setLayoutMode,
    setNeonEffects,
    toggleNeonEffects,
    toggleSidebar,
    toggleColorMode,
    applyTheme,
    loadFromServer,
    init,
  }
})
