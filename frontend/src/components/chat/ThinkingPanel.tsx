/**
 * Agent 思考过程面板. 展示 thinking 事件.
 */
import { Brain } from 'lucide-react';
import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

export function ThinkingPanel({ content }: { content: string }) {
  const [open, setOpen] = useState(true);
  if (!content) return null;

  return (
    <div className="rounded border border-dashed bg-muted/30 text-xs">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-1.5 px-2.5 py-1.5 text-left text-muted-foreground hover:bg-accent/30"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <Brain className="h-3 w-3" />
        <span>思考过程</span>
      </button>
      {open && (
        <div className={cn('border-t px-2.5 py-2 text-foreground/80 italic',
          'max-h-40 overflow-y-auto scrollbar-thin')}>
          {content}
        </div>
      )}
    </div>
  );
}
