import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// GitHub Pages base path: /<repo-name>/
// 优先级: VITE_REPO_NAME > GITHUB_REPOSITORY (GH Actions 自动注入, 形如 "owner/repo") > 默认
// ⚠️ GH Pages 路径**大小写敏感**, 必须与 GitHub 仓库名**精确匹配** (e.g. "AI-Chatbot" ≠ "ai-chatbot")
function resolveRepoName(): string {
  const explicit = process.env.VITE_REPO_NAME;
  if (explicit) return explicit;
  const ghRepo = process.env.GITHUB_REPOSITORY; // GH Actions 自动设, 形如 "shuaiwang888/AI-Chatbot"
  if (ghRepo) {
    const parts = ghRepo.split('/');
    if (parts.length === 2 && parts[1]) return parts[1];
  }
  return 'ai-chatbot';
}

const REPO_NAME = resolveRepoName();

export default defineConfig({
  base: `/${REPO_NAME}/`, // GH Pages 项目页 base
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
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
});
