import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ['nquire.local'],
    proxy: {
      '/api': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      }
    }
  },
  preview: {
    allowedHosts: ['nquire.local'],
  }
})
