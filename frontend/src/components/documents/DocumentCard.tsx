/**
 * 文档卡片 (单条). 点击打开详情, 进度条显示摄入进度.
 */
import { useState } from 'react';
import {
  FileText, Trash2, Loader2, AlertCircle, CheckCircle2, Clock, Eye,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { formatBytes, formatRelativeTime, truncateFilename } from '@/lib/utils';
import type { DocumentMeta } from '@/types';
import { useDeleteDocument } from '@/hooks/useDocuments';
import { cn } from '@/lib/utils';
import { DocumentDetailDialog } from './DocumentDetailDialog';

const STATUS_MAP: Record<
  DocumentMeta['status'],
  { label: string; variant: 'default' | 'info' | 'warning' | 'success' | 'destructive'; icon: any }
> = {
  uploading: { label: '上传中', variant: 'info', icon: Clock },
  parsing: { label: '解析中', variant: 'info', icon: Loader2 },
  embedding: { label: '向量化', variant: 'info', icon: Loader2 },
  ready: { label: '就绪', variant: 'success', icon: CheckCircle2 },
  failed: { label: '失败', variant: 'destructive', icon: AlertCircle },
};

export function DocumentCard({ doc }: { doc: DocumentMeta }) {
  const del = useDeleteDocument();
  const status = STATUS_MAP[doc.status];
  const Icon = status.icon;
  const isWorking = ['uploading', 'parsing', 'embedding'].includes(doc.status);

  const [detailOpen, setDetailOpen] = useState(false);

  const onCardClick = () => setDetailOpen(true);
  const onDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    // 一次点击直接弹原生确认框 (用户要求)
    if (window.confirm(`确认删除文档"${doc.filename}"?\n\n该操作不可撤销.`)) {
      del.mutate(doc.id);
    }
  };

  return (
    <>
      <Card
        className={cn(
          'group cursor-pointer border border-border transition-colors hover:border-primary/60',
          isWorking && 'border-sky-300/60 bg-sky-50/30 dark:bg-sky-950/10',
        )}
        onClick={onCardClick}
      >
        <CardContent className="space-y-1.5 p-3">
          <div className="flex items-start gap-2.5">
            <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <div className="flex items-start gap-1.5">
                <span className="line-clamp-2 min-w-0 flex-1 break-all text-sm font-medium" title={doc.filename}>
                  {truncateFilename(doc.filename, 60)}
                </span>
                <Badge variant={status.variant} className="shrink-0 gap-1">
                  <Icon className={cn('h-3 w-3', isWorking && 'animate-spin')} />
                  {status.label}
                </Badge>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-muted-foreground">
                <span>{formatBytes(doc.size)}</span>
                {doc.page_count ? <span>· {doc.page_count} 页</span> : null}
                {doc.chunk_count ? <span>· {doc.chunk_count} chunks</span> : null}
                <span>· {formatRelativeTime(doc.created_at)}</span>
              </div>
            </div>
          </div>

          {/* 进度条 (摄入中) */}
          {isWorking && (
            <div className="space-y-0.5">
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-sky-500 transition-all duration-500 ease-out"
                  style={{ width: `${Math.max(5, doc.progress ?? 5)}%` }}
                />
              </div>
              {doc.progress_label && (
                <p className="text-[10px] text-muted-foreground">{doc.progress_label}</p>
              )}
            </div>
          )}

          {/* 失败原因 */}
          {doc.status === 'failed' && doc.error && (
            <p className="text-[10px] text-destructive line-clamp-2">⚠️ {doc.error}</p>
          )}

          {/* 操作按钮 (icon-only, 默认 60% 透明, hover 全显 — 触屏/键盘也能看见) */}
          <div className="flex items-center gap-0.5 opacity-70 transition-opacity group-hover:opacity-100 focus-within:opacity-100 hover:opacity-100">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-muted-foreground hover:text-foreground"
              onClick={(e) => { e.stopPropagation(); setDetailOpen(true); }}
              title="查看详情 / chunks 预览"
            >
              <Eye className="h-3 w-3" />
            </Button>
            <div className="flex-1" />
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-muted-foreground hover:text-destructive"
              onClick={onDelete}
              disabled={del.isPending}
              title="删除文档"
            >
              {del.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
            </Button>
          </div>
        </CardContent>
      </Card>

      <DocumentDetailDialog
        docId={doc.id}
        open={detailOpen}
        onOpenChange={setDetailOpen}
      />
    </>
  );
}
