import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Запросы на /api уходят на backend (FastAPI на порту 8000).
// Так браузеру не нужны настройки CORS, и адрес сервера нигде не зашит в коде.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
