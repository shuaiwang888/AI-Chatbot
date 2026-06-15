/**
 * 集中管理 import.meta.env. 校验 + 抛错, 避免运行时 undefined.
 *
 * ⚠️ 在线部署专属 (GH Pages). 必填:
 *   VITE_API_BASE 形如 https://xxx.hf.space/api/v1
 *                  (可带可不带尾部 /api/v1 后缀, 这里会规范化)
 */
const _rawApiBase = (import.meta.env.VITE_API_BASE || '').trim().replace(/\/$/, '');
// 规范化: 去掉尾部 /api/v1, 因为 API client (api.ts) 会在 path 里加 /api/v1/...
// 这样 VITE_API_BASE 可写成 "https://xxx.hf.space" 或 "https://xxx.hf.space/api/v1" 都行.
const _apiBase = _rawApiBase.replace(/\/api\/v1$/, '');
const _repoName = import.meta.env.VITE_REPO_NAME || 'ai-chatbot';

if (!_apiBase) {
  // 非阻塞, 仅警告. 生产构建时必须通过 GH Actions Secret 注入, 否则 SSE 请求会跨域失败.
  console.warn(
    '[env] VITE_API_BASE 未配置. GH Pages 构建需在 repo Settings → Secrets 设 VITE_API_BASE.'
  );
}

export const env = {
  isProd: import.meta.env.PROD,
  apiBase: _apiBase,           // 已规范化, 不带 /api/v1
  apiBaseRaw: _rawApiBase,     // 原始配置, 给调试用
  repoName: _repoName,
} as const;

/** 实际请求时用的 base. 永远用 apiBase (线上唯一部署, 没有 dev 模式). */
export const apiBase = env.apiBase;
