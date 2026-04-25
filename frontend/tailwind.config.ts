import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        border: '#e2e8f0',
        background: '#ffffff',
        foreground: '#0f172a',
        primary: '#0f766e',
      },
    },
  },
  plugins: [],
} satisfies Config
