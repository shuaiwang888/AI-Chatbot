/**
 * 顶部栏: 标题 + 状态指示 + 侧栏切换按钮.
 */
import { Activity, Cpu, Database, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, Sparkles, Wifi, WifiOff } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { healthApi } from '@/lib/api';
import { useUIStore } from '@/stores/uiStore';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export function TopBar() {
  const { data: health, isError, isLoading } = useQuery({
    queryKey: ['health', 'readyz'],
    queryFn: () => healthApi.readiness(),
    refetchInterval: 10000,
    retry: 0,
  });

  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const rightOpen = useUIStore((s) => s.rightSidebarOpen);
  const toggleRight = useUIStore((s) => s.toggleRightSidebar);
  const showFluid = useUIStore((s) => s.showFluidBackground);
  const toggleFluid = useUIStore((s) => s.toggleFluidBackground);

  const online = !isError && health?.llm;
  const persistOn = health?.persist?.enabled && health?.persist?.mode !== 'disabled';

  return (
    <header className="flex h-14 min-w-0 shrink-0 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      {/* 左侧 logo + title. min-w-0 让标题区可压缩, 不会撑爆 TopBar */}
      <div className="flex min-w-0 shrink items-center gap-2">
        <div className="shrink-0 text-xl">🤖</div>
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold leading-none">AI Chatbot</h1>
          <p className="truncate text-[10px] text-muted-foreground">
            私人 Agent 智能客服 · v{health?.version || '...'}
          </p>
        </div>
      </div>

      {/* 右侧状态 + 切换. shrink-0 保证不被挤压, ml-auto 推到右边 */}
      <div className="ml-auto flex shrink-0 items-center gap-1.5 text-xs">
        {isLoading ? (
          <Badge variant="secondary">检查中…</Badge>
        ) : isError || !online ? (
          <Badge variant="destructive" className="hidden gap-1 sm:inline-flex">
            <WifiOff className="h-3 w-3" /> 后端离线
          </Badge>
        ) : (
          <Badge variant="success" className="hidden gap-1 sm:inline-flex">
            <Wifi className="h-3 w-3" /> 在线
          </Badge>
        )}
        <Badge
          variant={health?.chroma ? 'success' : 'secondary'}
          className="hidden gap-1 md:inline-flex"
          title="ChromaDB 向量库"
        >
          <Database className="h-3 w-3" />
          {health?.chroma ? 'Chroma' : 'Chroma?'}
        </Badge>
        <Badge
          variant={persistOn ? 'info' : 'secondary'}
          className="hidden gap-1 lg:inline-flex"
          title={`持久化模式: ${health?.persist?.mode || '?'}`}
        >
          <Activity className="h-3 w-3" />
          {persistOn ? 'HF Persist' : 'Local only'}
        </Badge>
        <Badge variant="outline" className="hidden gap-1 xl:inline-flex">
          <Cpu className="h-3 w-3" />
          {health?.llm ? 'LLM ✓' : 'LLM ✗'}
        </Badge>
        <div className="mx-1 hidden h-5 w-px bg-border sm:block" />
        <Button
          size="icon"
          variant={showFluid ? 'secondary' : 'ghost'}
          onClick={toggleFluid}
          title={showFluid ? '关闭流体背景' : '开启流体背景'}
          aria-label="切换流体背景"
          className="shrink-0"
        >
          <Sparkles className="h-4 w-4" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={toggleSidebar}
          title={sidebarOpen ? '折叠左侧' : '展开左侧'}
          aria-label="切换左侧栏"
          className="shrink-0"
        >
          {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={toggleRight}
          title={rightOpen ? '折叠历史对话' : '展开历史对话'}
          aria-label="切换历史对话栏"
          className="shrink-0"
        >
          {rightOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  );
}
