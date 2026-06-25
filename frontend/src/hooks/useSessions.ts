/**
 * 会话管理 hook (TanStack Query). 镜像 useDocuments.ts 模式.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { sessionsApi, ApiError } from '@/lib/api';
import type { SessionDetail, SessionMeta } from '@/types';

const KEY = ['sessions'] as const;

export function useSessions(limit = 50) {
  return useQuery({
    queryKey: [...KEY, { limit }],
    queryFn: () => sessionsApi.list({ limit }),
    refetchInterval: 30_000, // 30s 轮询, 看到新会话
    staleTime: 5_000,
  });
}

/** 详情查询 (被 SessionHistoryPanel 用, 用于"打开某条历史"后的额外 detail 缓存).
 *  注意: 真正的"点击 session 后立即把 messages 写进 chatStore" 在
 *  useSelectSession 里用 mutation + onSuccess 完成, 这里只是被动缓存.
 *  所以即便这里 staleTime 长也不会"点了没反应".
 */
export function useSession(sessionId: string | null) {
  return useQuery<SessionDetail>({
    queryKey: ['sessions', sessionId],
    queryFn: () => sessionsApi.get(sessionId!),
    enabled: !!sessionId,
    staleTime: 60_000,
  });
}

/** ⚡ 主动切换 session (点击历史对话用).
 *
 * 返回的 mutation.onSuccess(detail) 由调用方决定怎么 dispatch 进 chatStore.
 * 不在本 hook 内直接 import chatStore — 避免循环依赖 (chatStore 也 import 自 hooks).
 *
 * 用 mutation 而不是 useQuery 的原因:
 * - useQuery 是被动订阅, 数据 ready 时只更新 cache, 调用方需 useEffect 二次桥接
 *   → 容易出现 deps 不全导致 "点了没反应" 的竞态
 * - useMutation 是 imperative, onSuccess(detail) 同步拿到结果,
 *   → 调用方 1 行 .mutate(id) → 自动 fetch → onSuccess(detail) 写 store
 */
export function useSelectSession() {
  const qc = useQueryClient();
  return useMutation<SessionDetail, Error, string>({
    mutationFn: (sessionId: string) => sessionsApi.get(sessionId),
    onSuccess: (detail) => {
      // 塞进 query cache (复用, 后续 useSession 命中 cache 不重 fetch)
      qc.setQueryData(['sessions', detail.session.id], detail);
    },
  });
}

export function useCreateSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (title?: string) => sessionsApi.create(title),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => sessionsApi.delete(sessionId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: KEY });
      qc.removeQueries({ queryKey: ['sessions', vars] });
      toast.success('对话已删除');
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : String(err);
      toast.error(`删除失败: ${msg}`);
    },
  });
}

export function useRenameSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      sessionsApi.update(id, { title }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: KEY });
      qc.invalidateQueries({ queryKey: ['sessions', vars.id] });
    },
  });
}

/** 客户端聚合: 按 updated_at 倒序 (后端已排好, 这里再次保证). */
export function sortSessions(sessions: SessionMeta[] | undefined): SessionMeta[] {
  if (!sessions) return [];
  return [...sessions].sort((a, b) => b.updated_at - a.updated_at);
}

