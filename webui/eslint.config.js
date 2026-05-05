import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
    },
  },
  {
    files: ['src/pages/arrCatalog/**/*.{ts,tsx}'],
    rules: {
      /** Catalog views mirror legacy page patterns (ref mirrors + fetch-on-mount effects). */
      'react-hooks/refs': 'off',
      'react-hooks/set-state-in-effect': 'off',
      /**
       * Definition files co-locate the per-Arr definition constant (used at module
       * load via `ARR_CATALOG_REGISTRY[kind] = …`) with the body components that
       * the definition references. Splitting them is unnecessary churn — fast
       * refresh works fine for the body components themselves at dev time.
       */
      'react-refresh/only-export-components': 'off',
    },
  },
])
