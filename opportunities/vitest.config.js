import { defineConfig } from 'vitest/config'

// Unit tests live alongside the code in src/ (*.spec.js). Playwright owns the
// tests/ directory, so scope vitest to src/ to keep the two runners separate.
export default defineConfig({
  test: {
    include: ['src/**/*.spec.js'],
    environment: 'node',
  },
})
