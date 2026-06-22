import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// GitHub Pages base path: /<repo-name>/
// ⚠️ GH Pages 路径**大小写敏感**, 必须与 GitHub 仓库名**精确匹配**
//   (e.g. "AI-Chatbot" ≠ "ai-chatbot") — 否则 404, 页面空白.
//
// 解析优先级:
//   1. VITE_REPO_NAME env (明确覆盖, 优先)
//   2. GITHUB_REPOSITORY env (GH Actions runner 自动注入, 形如 "owner/Repo")
//   3. 硬编码 "AI-Chatbot" (本仓库最终 fallback, 避免再次翻车)
function resolveRepoName(): string {
  const explicit = process.env.VITE_REPO_NAME;
  if (explicit) return explicit;
  const ghRepo = process.env.GITHUB_REPOSITORY;
  if (ghRepo) {
    const parts = ghRepo.split('/');
    if (parts.length === 2 && parts[1]) return parts[1];
  }
  return 'AI-Chatbot'; // ⚠️ 与 GH 仓库名一致 (大写)
}

const REPO_NAME = resolveRepoName();
// build 期校验: base path 首字符必须 /, 末 /
if (!REPO_NAME.match(/^[A-Za-z0-9._-]+$/)) {
  throw new Error(`Invalid VITE_REPO_NAME / GITHUB_REPOSITORY: "${REPO_NAME}"`);
}

// build 启动时打印, 方便 GH Actions log 一眼看出 base 是否正确
// eslint-disable-next-line no-console
console.log(`[vite.config] base=/${REPO_NAME}/ (VITE_API_BASE=${process.env.VITE_API_BASE ? 'set' : 'EMPTY'})`);

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
