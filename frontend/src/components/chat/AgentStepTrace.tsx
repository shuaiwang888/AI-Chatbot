/**
 * 面向用户的实时处理进度：问题分析 → 知识检索 → 证据筛选 → 回答生成。
 */
import {
  Activity, Bot, CheckCircle2, Circle, Compass, Filter,
  Hammer, Loader2, Search, ShieldCheck,
} from 'lucide-react';
import type { AgentStepEvent, ProgressEvent, RetrievalEvent } from '@/types';
import { cn } from '@/lib/utils';

export interface AgentStepTraceProps {
  retrieval?: RetrievalEvent;
  steps?: AgentStepEvent[];
  progress?: ProgressEvent;
}

const NODE_META: Record<string, { label: string; icon: typeof Activity }> = {
  route:         { label: '理解问题', icon: Compass },
  query_rewrite: { label: '优化问题', icon: Activity },
  retrieve:      { label: '检索资料', icon: Search },
  rerank:        { label: '筛选证据', icon: Filter },
  evaluate:      { label: '校验证据', icon: ShieldCheck },
  tool_executor: { label: '调用工具', icon: Hammer },
  answer:        { label: '生成回答', icon: Bot },
};

export function AgentStepTrace({ retrieval, steps, progress }: AgentStepTraceProps) {
  if (!retrieval && !steps?.length && !progress) return null;

  const pct = Math.max(0, Math.min(100, progress?.pct ?? 0));
  const isDone = pct >= 100;

  return (
    <div
      className="overflow-hidden rounded-xl border border-primary/15 bg-gradient-to-br from-primary/[0.07] via-white/[0.025] to-violet-500/[0.05] text-xs shadow-[0_8px_30px_rgba(0,0,0,.08)]"
      aria-live="polite"
    >
      <div className="flex items-start gap-2.5 px-3 py-2.5">
        <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary">
          {isDone ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Loader2 className="h-3.5 w-3.5 animate-spin" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium text-foreground">{isDone ? '处理完成' : 'Agent 正在处理'}</span>
            <span className="ml-auto font-mono text-[10px] text-primary/80">{pct}%</span>
          </div>
          <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
            {progress?.label || '正在分析问题…'}
          </p>
        </div>
      </div>

      <div className="h-px bg-white/[0.05]">
        <div
          className="h-full bg-gradient-to-r from-sky-400 via-primary to-violet-400 transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>

      {steps && steps.length > 0 && (
        <div className="flex flex-wrap gap-1.5 px-3 py-2.5">
          {steps.map((step) => {
            const meta = NODE_META[step.node] || { label: step.node, icon: Circle };
            const Icon = meta.icon;
            const running = step.status === 'running';
            const done = step.status === 'done';
            return (
              <div
                key={step.node}
                className={cn(
                  'flex items-center gap-1.5 rounded-full border px-2 py-1 transition-colors',
                  running && 'border-primary/30 bg-primary/10 text-foreground',
                  done && 'border-emerald-400/15 bg-emerald-400/[0.06] text-foreground/65',
                  step.status === 'error' && 'border-destructive/30 bg-destructive/10 text-destructive',
                )}
              >
                {running ? (
                  <Loader2 className="h-3 w-3 animate-spin text-primary" />
                ) : done ? (
                  <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                ) : (
                  <Circle className="h-3 w-3" />
                )}
                <Icon className="h-3 w-3" />
                <span>{meta.label}</span>
              </div>
            );
          })}
        </div>
      )}

      {retrieval && (
        <div className="flex items-center gap-1.5 border-t border-white/[0.05] px-3 py-2 text-[11px] text-muted-foreground">
          <Search className="h-3 w-3 text-violet-400" />
          已命中 <strong className="font-semibold text-foreground">{retrieval.count}</strong> 个片段，来自{' '}
          <strong className="font-semibold text-foreground">{retrieval.doc_ids.length}</strong> 个文档
        </div>
      )}
    </div>
  );
}
