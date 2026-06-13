/**
 * Agent 步骤追踪 + 检索 + 进度. 给开发者看 agent 流程用.
 */
import { Activity, CheckCircle2, Circle, Loader2, Search, Wrench } from 'lucide-react';
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

const NODE_LABELS: Record<string, string> = {
  route: '路由',
  query_rewrite: '查询改写',
  retrieve: '检索',
  rerank: '精排',
  tool_executor: '工具调用',
  answer: '生成',
  evaluate: '评估',
};

export function AgentStepTrace({ retrieval, steps, progress }: AgentStepTraceProps) {
  if (!retrieval && !steps?.length && !progress) return null;

  return (
    <div className="rounded border border-dashed bg-muted/20 px-2.5 py-1.5 text-xs">
      <div className="mb-1 flex items-center gap-1.5 text-muted-foreground">
        <Activity className="h-3 w-3" />
        <span>Agent 执行追踪</span>
        {progress && (
          <Badge variant="secondary" className="ml-auto font-mono">
            {progress.pct}% · {progress.label}
          </Badge>
        )}
      </div>

      {/* 检索结果 */}
      {retrieval && (
        <div className="mb-1 flex items-center gap-1.5 text-foreground/70">
          <Search className="h-3 w-3" />
          <span>
            命中 <strong>{retrieval.count}</strong> 个 chunk,
            来自 <strong>{retrieval.doc_ids.length}</strong> 个文档
          </span>
        </div>
      )}

      {/* 步骤 */}
      {steps && steps.length > 0 && (
        <div className="space-y-0.5">
          {steps.map((s, i) => (
            <div key={i} className="flex items-center gap-1.5">
              {s.status === 'running' ? (
                <Loader2 className="h-3 w-3 animate-spin text-sky-500" />
              ) : s.status === 'done' ? (
                <CheckCircle2 className="h-3 w-3 text-emerald-500" />
              ) : (
                <Circle className="h-3 w-3 text-rose-500" />
              )}
              <span className={cn(
                s.status === 'done' && 'text-foreground/60',
                s.status === 'error' && 'text-destructive',
              )}>
                {NODE_LABELS[s.node] || s.node}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// 防止引用未使用
export { Wrench };
