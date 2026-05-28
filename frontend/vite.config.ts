import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // Load VITE_* from repo-root .env (shared with backend and docker compose)
  envDir: '..',
  plugins: [react()],
  server: {
    port: 5173,
  },
})
