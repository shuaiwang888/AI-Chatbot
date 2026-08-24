/**
 * 文档管理 hook (TanStack Query).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { documentsApi, ApiError } from '@/lib/api';
import type { DocumentMeta } from '@/types';
import { getAccessToken } from '@/lib/auth';

const KEY = ['documents'] as const;

export function useDocuments() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => documentsApi.list({ limit: 100 }),
    refetchInterval: 5000, // 摄入中状态需要轮询
    staleTime: 2000,
    enabled: Boolean(getAccessToken()),
  });
}

export function useDocument(docId: string | null) {
  return useQuery({
    queryKey: ['documents', docId],
    queryFn: () => documentsApi.get(docId!),
    enabled: !!docId,
    staleTime: 2000,
  });
}

export function useDocumentChunks(docId: string | null, limit = 200) {
  return useQuery({
    queryKey: ['documents', docId, 'chunks', limit],
    queryFn: () => documentsApi.chunks(docId!, { limit }),
    enabled: !!docId,
    staleTime: 10_000, // chunks 不变, 长 stale
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => documentsApi.upload(file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (docId: string) => documentsApi.delete(docId),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: KEY });
      if (result.persisted) toast.success('文档已删除');
      else toast.warning(result.warning || '文档已在本地删除，远端备份正在重试');
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : String(err);
      toast.error(`删除失败: ${msg}`);
    },
  });
}

/** 客户端状态聚合: 按 status 分组. */
export function summarizeDocs(docs: DocumentMeta[] | undefined) {
  const list = docs ?? [];
  return {
    total: list.length,
    ready: list.filter((d) => d.status === 'ready').length,
    inProgress: list.filter((d) =>
      ['uploading', 'parsing', 'embedding'].includes(d.status),
    ).length,
    failed: list.filter((d) => d.status === 'failed').length,
  };
}
