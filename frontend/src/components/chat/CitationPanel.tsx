/**
 * 引用源面板. 列出本次回答引用的 chunk 列表.
 * 点击可展开看 snippet.
 */
import { useState } from 'react';
import { ChevronDown, ChevronRight, FileText, MapPin, Hash } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { Citation } from '@/types';
import { cn } from '@/lib/utils';

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

  return (
    <div className="rounded-lg border bg-card text-xs">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-accent/50"
      >
        <span className="flex items-center gap-1.5 font-medium">
          {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          📚 引用源 ({citations.length})
        </span>
        <span className="text-[10px] text-muted-foreground">点击展开</span>
      </button>
      {open && (
        <div className="space-y-1.5 px-3 pb-3">
          {citations.map((c) => {
            const isExpanded = expanded.has(c.rank);
            return (
              <div
                key={`${c.doc_id}-${c.rank}`}
                className="rounded border bg-background"
              >
                <button
                  onClick={() => toggleExpand(c.rank)}
                  className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left hover:bg-accent/30"
                >
                  {isExpanded ? (
                    <ChevronDown className="h-3 w-3 shrink-0" />
                  ) : (
                    <ChevronRight className="h-3 w-3 shrink-0" />
                  )}
                  <Badge variant="secondary" className="font-mono">
                    [{c.rank}]
                  </Badge>
                  <FileText className="h-3 w-3 shrink-0 text-muted-foreground" />
                  <span className="truncate font-medium">{c.filename || c.doc_id.slice(0, 8)}</span>
                  {c.page != null && c.page > 0 && (
                    <span className="flex items-center gap-0.5 text-muted-foreground">
                      <MapPin className="h-3 w-3" /> {c.page}
                    </span>
                  )}
                  {c.heading && (
                    <span className="flex items-center gap-0.5 truncate text-muted-foreground">
                      <Hash className="h-3 w-3" /> {c.heading}
                    </span>
                  )}
                  <Badge variant="info" className="ml-auto font-mono">
                    {c.score.toFixed(2)}
                  </Badge>
                </button>
                {isExpanded && (
                  <div className={cn('border-t px-2.5 py-2 text-muted-foreground',
                    'max-h-48 overflow-y-auto scrollbar-thin')}>
                    {c.snippet}
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
