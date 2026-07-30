import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// The console is a separate app from frontend/. It talks to the dedicated
// ugence_console_api service (default port 8090), proxied under /api in dev.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 3100,
    proxy: {
      '/api': {
        target: process.env.CONSOLE_API_URL || 'http://localhost:8090',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
});
