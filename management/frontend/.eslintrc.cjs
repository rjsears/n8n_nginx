/* eslint-env node */
module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true
  },
  extends: [
    'eslint:recommended',
    'plugin:vue/vue3-essential',  // Use essential instead of recommended (less strict)
    'prettier'
  ],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module'
  },
  plugins: ['vue'],
  rules: {
    // Vue specific rules - relaxed for existing codebase
    'vue/multi-word-component-names': 'off',
    'vue/no-v-html': 'warn',
    'vue/require-default-prop': 'off',
    'vue/require-prop-types': 'off',
    'vue/attributes-order': 'off',  // Existing code doesn't follow this
    'vue/first-attribute-linebreak': 'off',

    // General rules
    'no-console': 'off',  // Console is used throughout
    'no-debugger': process.env.NODE_ENV === 'production' ? 'error' : 'warn',
    'no-unused-vars': ['warn', {
      argsIgnorePattern: '^_',
      varsIgnorePattern: '^_'
    }],
    'no-undef': 'error',  // Keep this - it catches real bugs!
    'prefer-const': 'off',
    'no-var': 'error'
  },
  globals: {
    // Vue 3 Composition API globals (auto-imported by Vue)
    defineProps: 'readonly',
    defineEmits: 'readonly',
    defineExpose: 'readonly',
    withDefaults: 'readonly',
    // These need to be imported, but adding as globals to avoid false positives
    // in files that use unplugin-auto-import or similar
    ref: 'readonly',
    reactive: 'readonly',
    computed: 'readonly',
    watch: 'readonly',
    watchEffect: 'readonly',
    onMounted: 'readonly',
    onUnmounted: 'readonly',
    onBeforeMount: 'readonly',
    onBeforeUnmount: 'readonly',
    nextTick: 'readonly',
    toRef: 'readonly',
    toRefs: 'readonly',
    shallowRef: 'readonly',
    inject: 'readonly',
    provide: 'readonly'
  }
}
