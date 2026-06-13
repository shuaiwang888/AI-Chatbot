/**
 * 顶部栏: 标题 + 状态指示.
 */
import { Activity, Cpu, Database, Wifi, WifiOff } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { healthApi } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export function TopBar() {
  const { data: health, isError, isLoading } = useQuery({
    queryKey: ['health', 'readyz'],
    queryFn: () => healthApi.readiness(),
    refetchInterval: 10000,
    retry: 0,
  });

  const online = !isError && health?.llm;
  const persistOn = health?.persist?.enabled && health?.persist?.mode !== 'disabled';

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center gap-2">
        <div className="text-xl">🤖</div>
        <div>
          <h1 className="text-sm font-semibold leading-none">AI Chatbot</h1>
          <p className="text-[10px] text-muted-foreground">
            私人 Agent 智能客服 · v{health?.version || '...'}
          </p>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-2 text-xs">
        {isLoading ? (
          <Badge variant="secondary">检查中…</Badge>
        ) : isError || !online ? (
          <Badge variant="destructive" className="gap-1">
            <WifiOff className="h-3 w-3" /> 后端离线
          </Badge>
        ) : (
          <Badge variant="success" className="gap-1">
            <Wifi className="h-3 w-3" /> 在线
          </Badge>
        )}
        <Badge
          variant={health?.chroma ? 'success' : 'secondary'}
          className="gap-1"
          title="ChromaDB 向量库"
        >
          <Database className="h-3 w-3" />
          {health?.chroma ? 'Chroma' : 'Chroma?'}
        </Badge>
        <Badge
          variant={persistOn ? 'info' : 'secondary'}
          className="gap-1"
          title={`持久化模式: ${health?.persist?.mode || '?'}`}
        >
          <Activity className="h-3 w-3" />
          {persistOn ? 'HF Persist' : 'Local only'}
        </Badge>
        <Badge variant="outline" className={cn('gap-1')}>
          <Cpu className="h-3 w-3" />
          {health?.llm ? 'LLM ✓' : 'LLM ✗'}
        </Badge>
      </div>
    </header>
  );
}
