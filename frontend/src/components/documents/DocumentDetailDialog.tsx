/**
 * 文档详情弹窗. 展示:
 * - 文档元信息 (大小 / 页数 / 状态 / 时间)
 * - 拆分规则 (parser / chunk_size / overlap / semantic / contextual)
 * - chunks 列表预览 (默认 50 个, 可滚动)
 * - 底部操作: 关闭 / 删除 (两步确认)
 */
import { useEffect, useMemo, useState } from 'react';
import {
  FileText, Loader2, Hash, Type, Cog, Layers, FileSearch,
  ChevronDown, ChevronRight, BookOpen, Sparkles, Trash2, X,
} from 'lucide-react';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useDeleteDocument, useDocument, useDocumentChunks } from '@/hooks/useDocuments';
import { formatBytes, formatRelativeTime, truncateFilename } from '@/lib/utils';
import { cn } from '@/lib/utils';
import type { DocumentChunk } from '@/types';

const STATUS_LABEL: Record<string, { label: string; variant: 'info' | 'success' | 'destructive' | 'warning' | 'secondary' }> = {
  uploading: { label: '上传中', variant: 'info' },
  parsing: { label: '解析中', variant: 'info' },
  embedding: { label: '向量化', variant: 'info' },
  ready: { label: '就绪', variant: 'success' },
  failed: { label: '失败', variant: 'destructive' },
};

export interface DocumentDetailDialogProps {
  docId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DocumentDetailDialog({ docId, open, onOpenChange }: DocumentDetailDialogProps) {
  const doc = useDocument(docId);
  const chunks = useDocumentChunks(docId, 200);
  const del = useDeleteDocument();

  const meta = doc.data;
  const status = meta?.status ? STATUS_LABEL[meta.status] : null;

  // 两步确认删除 (3 秒后自动取消确认)
  const [confirmDel, setConfirmDel] = useState(false);
  useEffect(() => {
    if (!confirmDel) return;
    const t = setTimeout(() => setConfirmDel(false), 3000);
    return () => clearTimeout(t);
  }, [confirmDel]);

  // 打开时清掉确认态
  useEffect(() => {
    if (open) setConfirmDel(false);
  }, [open, docId]);

  const onDelete = () => {
    if (!docId) return;
    if (!confirmDel) {
      setConfirmDel(true);
      return;
    }
    del.mutate(docId, {
      onSuccess: () => onOpenChange(false),
    });
  };

  // 按 parent 分组 (children 共享 parent_id, 这样用户能直观看到 parent/child 结构)
  const grouped = useMemo(() => {
    const list: DocumentChunk[] = chunks.data?.chunks ?? [];
    if (!list.length) return [];
    // 按 heading + chunk_index 排序
    const sorted = [...list].sort((a, b) => a.chunk_index - b.chunk_index);
    // 把相邻同 heading 的合为一组
    const groups: { heading: string | null; items: DocumentChunk[] }[] = [];
    for (const c of sorted) {
      const last = groups[groups.length - 1];
      if (last && last.heading === (c.heading ?? null)) {
        last.items.push(c);
      } else {
        groups.push({ heading: c.heading ?? null, items: [c] });
      }
    }
    return groups;
  }, [chunks.data]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl overflow-hidden">
        <DialogHeader>
          <div className="flex min-w-0 items-center gap-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <DialogTitle className="truncate" title={meta?.filename}>
              {meta ? truncateFilename(meta.filename, 60) : '加载中…'}
            </DialogTitle>
            {status && (
              <Badge variant={status.variant} className="ml-2">{status.label}</Badge>
            )}
          </div>
          {meta && (
            <DialogDescription>
              {formatBytes(meta.size)} ·{' '}
              {meta.page_count ? `${meta.page_count} 页 · ` : ''}
              {meta.chunk_count} chunks · 上传 {formatRelativeTime(meta.created_at)}
            </DialogDescription>
          )}
        </DialogHeader>

        {/* ========== 拆分规则 ========== */}
        {meta && (
          <div className="rounded-md border bg-muted/30 p-3 text-xs">
            <div className="mb-2 flex items-center gap-1.5 font-medium text-foreground">
              <Cog className="h-3.5 w-3.5" />
              拆分规则
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <RuleItem icon={FileSearch} label="解析器" value={meta.parser ?? '—'} />
              <RuleItem icon={Hash} label="chunk size" value={meta.chunk_size ? `${meta.chunk_size} tokens` : '—'} />
              <RuleItem icon={Hash} label="chunk overlap" value={meta.chunk_overlap != null ? `${meta.chunk_overlap} tokens` : '—'} />
              <RuleItem
                icon={Sparkles}
                label="上下文预置"
                value={meta.contextual_retrieval ? '开启 (Anthropic-style)' : '关闭'}
                highlight={meta.contextual_retrieval}
              />
              <RuleItem
                icon={Layers}
                label="语义分块"
                value={meta.semantic_chunking ? '开启' : '关闭'}
                highlight={meta.semantic_chunking}
              />
              <RuleItem icon={Type} label="层次化" value="Parent 2000t → Child" />
              <RuleItem icon={BookOpen} label="Embedding 模型" value="BGE-M3" />
              <RuleItem icon={Cog} label="Reranker" value="bge-reranker-v2-m3" />
            </div>
          </div>
        )}

        {/* ========== 错误信息 (failed 时) ========== */}
        {meta?.status === 'failed' && meta.error && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-xs text-destructive">
            ⚠️ 摄入失败: {meta.error}
          </div>
        )}

        {/* ========== Chunks 列表 ========== */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-medium text-foreground">
              <Layers className="h-3.5 w-3.5" />
              Chunks 预览
              <span className="text-muted-foreground">
                ({chunks.data?.returned ?? 0} / {chunks.data?.total ?? meta?.chunk_count ?? 0})
              </span>
            </div>
          </div>

          {chunks.isLoading && (
            <div className="flex items-center justify-center py-6 text-muted-foreground">
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              <span className="text-xs">加载 chunks…</span>
            </div>
          )}

          {chunks.isError && (
            <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-xs text-destructive">
              ⚠️ 加载失败
            </div>
          )}

          {chunks.data && grouped.length === 0 && (
            <div className="rounded border border-dashed p-6 text-center text-xs text-muted-foreground">
              还没有 chunks. 文档可能还在解析中, 或内容为空.
            </div>
          )}

          {chunks.data && grouped.length > 0 && (
            <ScrollArea className="h-[40vh] rounded-md border">
              <div className="divide-y">
                {grouped.map((g, gi) => (
                  <ChunkGroup key={gi} heading={g.heading} chunks={g.items} />
                ))}
              </div>
            </ScrollArea>
          )}
        </div>

        {/* ========== 底部操作 ========== */}
        <DialogFooter className="border-t pt-3">
          {meta?.status === 'failed' && meta.error && (
            <span className="mr-auto text-[10px] text-destructive">⚠️ 摄入失败</span>
          )}
          <Button
            variant={confirmDel ? 'destructive' : 'outline'}
            size="sm"
            onClick={onDelete}
            disabled={del.isPending || !docId}
            title={confirmDel ? '再次点击确认删除' : '删除此文档'}
          >
            {del.isPending ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            )}
            {confirmDel ? '确认删除' : '删除文档'}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
            <X className="mr-1.5 h-3.5 w-3.5" />
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function RuleItem({
  icon: Icon, label, value, highlight = false,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className={cn(
      'rounded border bg-background px-2 py-1.5',
      highlight && 'border-emerald-300 bg-emerald-50/50 dark:bg-emerald-950/20',
    )}>
      <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
        <Icon className="h-3 w-3" />
        {label}
      </div>
      <div className="mt-0.5 font-mono text-[11px] text-foreground">{value}</div>
    </div>
  );
}

function ChunkGroup({ heading, chunks }: { heading: string | null; chunks: DocumentChunk[] }) {
  const [open, setOpen] = useState(true);
  return (
    <div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-1.5 bg-muted/20 px-3 py-1.5 text-left text-xs font-medium hover:bg-muted/40"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <span className="truncate">{heading ?? '（无标题）'}</span>
        <span className="ml-auto text-[10px] text-muted-foreground">{chunks.length} 个 chunk</span>
      </button>
      {open && (
        <div className="space-y-1.5 p-2">
          {chunks.map((c) => (
            <ChunkCard key={c.id} chunk={c} />
          ))}
        </div>
      )}
    </div>
  );
}

function ChunkCard({ chunk }: { chunk: DocumentChunk }) {
  return (
    <div className="rounded border bg-card p-2 text-[11px]">
      <div className="mb-1 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
        <Badge variant="outline" className="font-mono">#{chunk.chunk_index}</Badge>
        {chunk.page_no != null && (
          <Badge variant="secondary" className="font-mono">p.{chunk.page_no}</Badge>
        )}
        {chunk.token_count != null && (
          <span className="font-mono">{chunk.token_count} tokens</span>
        )}
        {chunk.context_prefix && (
          <span className="ml-auto inline-flex items-center gap-1 rounded bg-emerald-50 px-1.5 py-0.5 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
            <Sparkles className="h-2.5 w-2.5" />
            {chunk.context_prefix.slice(0, 50)}{chunk.context_prefix.length > 50 ? '…' : ''}
          </span>
        )}
      </div>
      <p className="whitespace-pre-wrap break-words text-foreground/90 leading-relaxed">{chunk.text}</p>
    </div>
  );
}
