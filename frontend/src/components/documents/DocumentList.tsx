/**
 * 文档列表. 用 TanStack Query 轮询, 自动反映摄入状态.
 */
import { useMemo, useState } from 'react';
import { FileSearch, KeyRound, Loader2, Search, X } from 'lucide-react';
import { useDocuments, summarizeDocs } from '@/hooks/useDocuments';
import { DocumentCard } from './DocumentCard';
import { ScrollArea } from '@/components/ui/scroll-area';
import { getAccessToken } from '@/lib/auth';

export function DocumentList() {
  const [query, setQuery] = useState('');
  const { data, isLoading, isError } = useDocuments();
  const summary = summarizeDocs(data?.documents);
  const hasAccessToken = Boolean(getAccessToken());
  const filtered = useMemo(() => {
    const q = query.trim().toLocaleLowerCase();
    if (!q) return data?.documents ?? [];
    return (data?.documents ?? []).filter((doc) => doc.filename.toLocaleLowerCase().includes(q));
  }, [data?.documents, query]);

  if (!hasAccessToken) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-amber-500/20 bg-amber-500/[0.04] px-4 py-6 text-center text-amber-200">
        <KeyRound className="mb-2 h-5 w-5" />
        <p className="text-xs font-medium">需要访问令牌</p>
        <p className="mt-1 text-[10px] text-muted-foreground">点击页面右上角钥匙按钮设置</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground">
        <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
        <span className="text-xs">加载中…</span>
      </div>
    );
  }
  if (isError) {
    return (
      <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-xs text-destructive">
        ⚠️ 加载文档列表失败. 请检查后端连接.
      </div>
    );
  }

  if (!data?.documents?.length) {
    return (
      <div className="flex flex-col items-center justify-center gap-1 py-6 text-center text-muted-foreground">
        <FileSearch className="h-6 w-6" />
        <p className="text-xs">还没有文档</p>
        <p className="text-[10px]">上传一份 PDF / Word 试试</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索文件名…"
          className="h-9 w-full rounded-xl border border-white/[0.07] bg-black/10 pl-9 pr-8 text-xs outline-none transition placeholder:text-muted-foreground/60 focus:border-primary/40"
        />
        {query && (
          <button type="button" onClick={() => setQuery('')} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground" aria-label="清除搜索">
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <div className="flex items-center justify-between px-1 text-[10px] text-muted-foreground">
        <span>
          共 <strong>{summary.total}</strong> 份
          {summary.ready > 0 && <> · 就绪 {summary.ready}</>}
          {summary.inProgress > 0 && <> · 处理中 {summary.inProgress}</>}
          {summary.failed > 0 && <> · 失败 {summary.failed}</>}
        </span>
      </div>
      <ScrollArea className="h-[calc(100vh-430px)] min-h-40">
        <div className="space-y-2 pr-2">
          {filtered.map((doc) => (
            <DocumentCard key={doc.id} doc={doc} />
          ))}
          {filtered.length === 0 && (
            <div className="rounded-xl border border-dashed border-white/[0.07] px-3 py-6 text-center text-[10px] text-muted-foreground">没有匹配的资料</div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
