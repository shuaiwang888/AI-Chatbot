/**
 * 会话管理 hook (TanStack Query). 镜像 useDocuments.ts 模式.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { sessionsApi } from '@/lib/api';
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

export function useSession(sessionId: string | null) {
  return useQuery<SessionDetail>({
    queryKey: ['sessions', sessionId],
    queryFn: () => sessionsApi.get(sessionId!),
    enabled: !!sessionId,
    staleTime: 60_000, // 历史会话不变, 长 stale
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
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
