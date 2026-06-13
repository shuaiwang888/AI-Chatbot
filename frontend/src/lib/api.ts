/**
 * 后端 API fetch 客户端.
 *
 * 设计:
 * - 统一 baseURL (apiBase from env)
 * - 错误统一抛 ApiError, 含 status + code + message
 * - 文件上传用 FormData, 走原生 fetch
 * - SSE 流式不走这里, 走 sse.ts
 */
import { apiBase } from '@/env';
import type {
  ChatRequest,
  ChatResponse,
  DocumentChunk,
  DocumentChunksResponse,
  DocumentMeta,
  HealthStatus,
  IngestResult,
  SessionDetail,
  SessionMeta,
} from '@/types';

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function _request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = `${apiBase}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      ...(init.body && !(init.body instanceof FormData)
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...init.headers,
    },
  });

  if (!res.ok) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      // 非 JSON
    }
    throw new ApiError(
      res.status,
      body?.code || 'http_error',
      body?.message || `HTTP ${res.status}`,
      body,
    );
  }

  if (res.status === 204) return null as T;
  return (await res.json()) as T;
}

// ========== Health ==========
export const healthApi = {
  liveness: () => _request<HealthStatus>('/api/v1/healthz'),
  readiness: () => _request<HealthStatus>('/api/v1/readyz'),
};

// ========== Chat ==========
export const chatApi = {
  send: (req: ChatRequest) =>
    _request<ChatResponse>('/api/v1/chat', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
  // SSE 流式见 sse.ts
};

// ========== Documents ==========
export const documentsApi = {
  list: (params: { limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return _request<{ documents: DocumentMeta[]; total: number }>(
      `/api/v1/documents${qs ? `?${qs}` : ''}`,
    );
  },
  get: (docId: string) => _request<DocumentMeta>(`/api/v1/documents/${docId}`),
  chunks: (docId: string, params: { limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return _request<DocumentChunksResponse>(
      `/api/v1/documents/${docId}/chunks${qs ? `?${qs}` : ''}`,
    );
  },
  upload: async (file: File): Promise<IngestResult> => {
    const fd = new FormData();
    fd.append('file', file);
    return _request<IngestResult>('/api/v1/documents/upload', {
      method: 'POST',
      body: fd,
    });
  },
  delete: (docId: string) =>
    _request<{ doc_id: string; deleted: boolean }>(`/api/v1/documents/${docId}`, {
      method: 'DELETE',
    }),
};

// ========== Sessions ==========
export const sessionsApi = {
  list: () => _request<{ sessions: SessionMeta[]; total: number }>('/api/v1/sessions'),
  get: (sessionId: string) => _request<SessionDetail>(`/api/v1/sessions/${sessionId}`),
  create: (title?: string) =>
    _request<{ session_id: string; title: string | null }>('/api/v1/sessions', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
  delete: (sessionId: string) =>
    _request<{ session_id: string; deleted: boolean }>(`/api/v1/sessions/${sessionId}`, {
      method: 'DELETE',
    }),
};
