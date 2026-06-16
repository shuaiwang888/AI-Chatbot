/**
 * 引用源面板. 列出本次回答引用的 chunk 列表.
 * 点击可展开看 snippet (snippet 内部 markdown 渲染).
 */
import { useState } from 'react';
import {
  BookOpen, ChevronDown, ChevronRight, FileText, Hash, Library, MapPin,
  Quote, Sparkles,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { Citation } from '@/types';
import { cn } from '@/lib/utils';
import { CitationSnippet } from './CitationSnippet';

export function CitationPanel({ citations }: { citations: Citation[] }) {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  if (!citations.length) return null;

  const toggleExpand = (rank: number) => {
    setExpanded((s) => {
      const next = new Set(s);
      if (next.has(rank)) next.delete(rank);
      else next.add(rank);
      return next;
    });
  };

  // 把 doc_ids 去重, 用于显示"来源 N 个文档"
  const uniqueDocs = new Set(citations.map((c) => c.doc_id));

  return (
    <div className="rounded-lg border border-border bg-card text-xs shadow-sm">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left transition-colors hover:bg-accent/40"
      >
        <span className="flex items-center gap-1.5 font-medium">
          {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          <Library className="h-3.5 w-3.5 text-violet-500" />
          <span>引用源</span>
          <Badge variant="secondary" className="ml-1 font-mono">
            {citations.length}
          </Badge>
          <span className="text-muted-foreground">· 来自</span>
          <FileText className="h-3 w-3 text-sky-500" />
          <span className="text-muted-foreground">{uniqueDocs.size} 份文档</span>
        </span>
        <span className="text-[10px] text-muted-foreground">
          {open ? '收起' : '点击展开'}
        </span>
      </button>
      {open && (
        <div className="space-y-1.5 px-3 pb-3 pt-1">
          {citations.map((c) => {
            const isExpanded = expanded.has(c.rank);
            return (
              <div
                key={`${c.doc_id}-${c.rank}`}
                className={cn(
                  'overflow-hidden rounded-md border border-border/60 bg-background',
                  'transition-colors hover:border-primary/40',
                )}
              >
                <button
                  onClick={() => toggleExpand(c.rank)}
                  className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left transition-colors hover:bg-accent/30"
                >
                  {isExpanded ? (
                    <ChevronDown className="h-3 w-3 shrink-0" />
                  ) : (
                    <ChevronRight className="h-3 w-3 shrink-0" />
                  )}
                  <Badge variant="secondary" className="shrink-0 font-mono">
                    [{c.rank}]
                  </Badge>
                  <FileText className="h-3 w-3 shrink-0 text-sky-500" />
                  <span className="truncate font-medium" title={c.filename || c.doc_id}>
                    {c.filename || c.doc_id.slice(0, 8)}
                  </span>
                  {c.page != null && c.page > 0 && (
                    <span className="flex shrink-0 items-center gap-0.5 text-muted-foreground">
                      <MapPin className="h-3 w-3" /> {c.page} 页
                    </span>
                  )}
                  {c.heading && (
                    <span className="flex min-w-0 items-center gap-0.5 truncate text-muted-foreground">
                      <Hash className="h-3 w-3 shrink-0" />
                      <span className="truncate">{c.heading}</span>
                    </span>
                  )}
                  <Badge
                    variant={c.score >= 0.7 ? 'success' : c.score >= 0.5 ? 'info' : 'secondary'}
                    className="ml-auto shrink-0 font-mono"
                    title={`相关度 ${c.score.toFixed(4)}`}
                  >
                    {c.score >= 0.7 && <Sparkles className="mr-0.5 h-2.5 w-2.5" />}
                    {c.score.toFixed(2)}
                  </Badge>
                </button>
                {isExpanded && (
                  <div className="border-t border-border/60 bg-muted/30 px-2.5 py-2 max-h-64 overflow-y-auto scrollbar-thin">
                    <div className="mb-1 flex items-center gap-1 text-[10px] text-muted-foreground">
                      <Quote className="h-3 w-3" />
                      <span>原文片段</span>
                    </div>
                    <CitationSnippet text={c.snippet} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// 防止引用未使用
export { BookOpen };
