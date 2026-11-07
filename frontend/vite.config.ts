import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Сборка попадает в frontend/dist; в Docker её раздаёт nginx (frontend/Dockerfile).
// Целевые браузеры по ТЗ (4.2.3): Chrome/Edge 90+, Firefox 88+, Safari 14+, Яндекс.Браузер 21+.
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  build: {
    target: ['chrome90', 'edge90', 'firefox88', 'safari14'],
    cssTarget: ['chrome90', 'edge90', 'firefox88', 'safari14'],
    sourcemap: false,
  },
  server: {
    port: 5173,
    // В режиме разработки запросы к API идут на запущенный бэкенд.
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
  // `npm run preview` — просмотр готовой сборки без Docker, API на :8000.
  preview: {
    port: 4173,
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
})
