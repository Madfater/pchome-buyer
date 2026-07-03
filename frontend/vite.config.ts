import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 開發時 API 由 `python main.py web` 提供（預設 8787），Vite 只代理 /api
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8787',
    },
  },
})
