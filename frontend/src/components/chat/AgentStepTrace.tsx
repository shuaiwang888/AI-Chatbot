/**
 * Agent 步骤追踪 + 检索 + 进度. 给开发者看 agent 流程用.
 */
import {
  Activity, Bot, CheckCircle2, Circle, Compass, Filter, GitBranch,
  Hammer, Loader2, Search, Wrench,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type {
  AgentStepEvent,
  ProgressEvent,
  RetrievalEvent,
} from '@/types';
import { cn } from '@/lib/utils';

export interface AgentStepTraceProps {
  retrieval?: RetrievalEvent;
  steps?: AgentStepEvent[];
  progress?: ProgressEvent;
}

const NODE_META: Record<string, { label: string; icon: any; color: string }> = {
  route:          { label: '路由',         icon: Compass,  color: 'text-amber-500' },
  query_rewrite:  { label: '查询改写',     icon: GitBranch, color: 'text-blue-500' },
  retrieve:       { label: '检索',         icon: Search,   color: 'text-violet-500' },
  rerank:         { label: '精排',         icon: Filter,   color: 'text-indigo-500' },
  tool_executor:  { label: '工具调用',     icon: Hammer,   color: 'text-orange-500' },
  answer:         { label: '生成',         icon: Bot,      color: 'text-emerald-500' },
  evaluate:       { label: '评估',         icon: Activity, color: 'text-pink-500' },
};

export function AgentStepTrace({ retrieval, steps, progress }: AgentStepTraceProps) {
  if (!retrieval && !steps?.length && !progress) return null;

  return (
    <div className="rounded-md border border-dashed border-border/80 bg-muted/20 px-2.5 py-1.5 text-xs">
      <div className="mb-1 flex items-center gap-1.5 text-muted-foreground">
        <Activity className="h-3 w-3" />
        <span>Agent 执行追踪</span>
        {progress && (
          <Badge variant="secondary" className="ml-auto gap-1 font-mono">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-500 animate-pulse" />
            {progress.pct}% · {progress.label}
          </Badge>
        )}
      </div>

      {/* 检索结果 */}
      {retrieval && (
        <div className="mb-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-foreground/75">
          <Search className="h-3 w-3 text-violet-500" />
          <span>
            命中 <strong className="text-violet-600 dark:text-violet-400">{retrieval.count}</strong> 个 chunk,
            来自 <strong className="text-sky-600 dark:text-sky-400">{retrieval.doc_ids.length}</strong> 个文档
          </span>
        </div>
      )}

      {/* 步骤 */}
      {steps && steps.length > 0 && (
        <div className="space-y-0.5">
          {steps.map((s, i) => {
            const meta = NODE_META[s.node] || { label: s.node, icon: Circle, color: 'text-muted-foreground' };
            const Icon = meta.icon;
            return (
              <div key={i} className="flex items-center gap-1.5">
                {s.status === 'running' ? (
                  <Loader2 className="h-3 w-3 animate-spin text-sky-500" />
                ) : s.status === 'done' ? (
                  <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                ) : (
                  <Circle className="h-3 w-3 text-rose-500" />
                )}
                <Icon className={cn('h-3 w-3', meta.color)} />
                <span className={cn(
                  s.status === 'done' && 'text-foreground/60',
                  s.status === 'error' && 'text-destructive',
                )}>
                  {meta.label}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// 防止引用未使用
export { Wrench };
