import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// GitHub Pages base path: /<repo-name>/  (e.g. /ai-chatbot/)
// 留空时用 '/' (root user/organization page)
const REPO_NAME = process.env.VITE_REPO_NAME || 'ai-chatbot';

export default defineConfig(({ mode }) => {
  // 让 Vite 在 build 时也能读到 import.meta.env
  const env = loadEnv(mode, process.cwd(), '');

  return {
    base: mode === 'production' ? `/${REPO_NAME}/` : '/',
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      proxy: {
        // 本地 dev 时, 前端 → 后端 走 vite proxy, 避免 CORS
        '/api': {
          target: env.VITE_DEV_API_BASE || 'http://localhost:7860',
          changeOrigin: true,
        },
      },
    },
    build: {
      target: 'esnext',
      sourcemap: false,
      chunkSizeWarningLimit: 800,
      rollupOptions: {
        output: {
          manualChunks: {
            react: ['react', 'react-dom', 'react-router-dom'],
            ui: ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu', '@radix-ui/react-slot'],
          },
        },
      },
    },
  };
});
