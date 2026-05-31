import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const apiProxyTarget = process.env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000'

// Hosts the dev server will accept (Host header allow-list). Comma-separated.
// Use "*" or "all" to allow any host (e.g. when fronted by a reverse proxy).
const rawAllowedHosts = (process.env.VITE_ALLOWED_HOSTS || '').trim()
const allowedHosts =
  rawAllowedHosts === '*' || rawAllowedHosts.toLowerCase() === 'all'
    ? true
    : rawAllowedHosts
        .split(',')
        .map((h) => h.trim())
        .filter(Boolean)

export default defineConfig({
  plugins: [tailwindcss(), react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    allowedHosts,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: false,
      },
    },
  },
})
