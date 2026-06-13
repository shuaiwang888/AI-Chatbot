/**
 * 集中管理 import.meta.env. 校验 + 抛错, 避免运行时 undefined.
 *
 * 生产 (GH Pages):  VITE_API_BASE 必填, 形如 https://xxx.hf.space/api/v1
 *                  (可带可不带尾部 /api/v1 后缀, 这里会规范化)
 * 本地 dev:        VITE_API_BASE 留空, vite proxy 把 /api 转到 VITE_DEV_API_BASE
 */
const _rawApiBase = (import.meta.env.VITE_API_BASE || '').trim().replace(/\/$/, '');
// 规范化: 去掉尾部 /api/v1, 因为 API client (api.ts) 会在 path 里加 /api/v1/...
// 这样 VITE_API_BASE 可写成 "https://xxx.hf.space" 或 "https://xxx.hf.space/api/v1" 都行.
const _apiBase = _rawApiBase.replace(/\/api\/v1$/, '');
const _devApiBase = (import.meta.env.VITE_DEV_API_BASE || 'http://localhost:7860').replace(/\/$/, '');
const _repoName = import.meta.env.VITE_REPO_NAME || 'ai-chatbot';

if (import.meta.env.PROD && !_apiBase) {
  // 非阻塞, 仅警告. dev 阶段允许空 (用 proxy)
  console.warn(
    '[env] VITE_API_BASE 未配置. 生产环境 (GH Pages) 必须设置, 否则 SSE 请求会跨域失败.'
  );
}

export const env = {
  isProd: import.meta.env.PROD,
  isDev: import.meta.env.DEV,
  apiBase: _apiBase,           // 生产用 (已规范化, 不带 /api/v1)
  apiBaseRaw: _rawApiBase,     // 原始配置, 给调试用
  devApiBase: _devApiBase,     // 本地 dev 时 vite proxy 目标
  repoName: _repoName,
} as const;

/** 实际请求时用的 base. dev 用空串 (走 proxy), prod 用 apiBase. */
export const apiBase = env.isDev ? '' : env.apiBase;
