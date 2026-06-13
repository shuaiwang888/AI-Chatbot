/**
 * 文档列表. 用 TanStack Query 轮询, 自动反映摄入状态.
 */
import { FileSearch, Loader2 } from 'lucide-react';
import { useDocuments, summarizeDocs } from '@/hooks/useDocuments';
import { DocumentCard } from './DocumentCard';
import { ScrollArea } from '@/components/ui/scroll-area';

export function DocumentList() {
  const { data, isLoading, isError } = useDocuments();
  const summary = summarizeDocs(data?.documents);

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
      <div className="flex items-center justify-between px-1 text-[10px] text-muted-foreground">
        <span>
          共 <strong>{summary.total}</strong> 份
          {summary.ready > 0 && <> · 就绪 {summary.ready}</>}
          {summary.inProgress > 0 && <> · 处理中 {summary.inProgress}</>}
          {summary.failed > 0 && <> · 失败 {summary.failed}</>}
        </span>
      </div>
      <ScrollArea className="h-[calc(100vh-300px)]">
        <div className="space-y-2 pr-2">
          {data.documents.map((doc) => (
            <DocumentCard key={doc.id} doc={doc} />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
