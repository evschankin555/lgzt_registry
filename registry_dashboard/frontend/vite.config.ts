import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/registry/',
  server: {
    port: 3001,
    proxy: {
      '/api': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  }
})
