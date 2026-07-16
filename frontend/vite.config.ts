import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Backend origin for the dev proxy. In production, set VITE_API_BASE to the
// deployed backend URL and calls go there directly instead of through this proxy.
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
  server: {
    proxy: {
      // Forward all API calls to the FastAPI backend during local dev so the
      // browser never talks to upstream providers and no keys are exposed.
      '/api': {
        target: BACKEND_URL,
        changeOrigin: true,
      },
    },
  },
});
