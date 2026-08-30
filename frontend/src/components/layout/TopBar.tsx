/** Floating workspace toolbar with compact, predictable status feedback. */
import { useState } from 'react';
import {
  Bot, Check, Database, KeyRound, Loader2, Menu, PanelRightClose,
  PanelRightOpen, Sparkles, WifiOff,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';

import { healthApi } from '@/lib/api';
import { getAccessToken } from '@/lib/auth';
import { useUIStore } from '@/stores/uiStore';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { AccessTokenDialog } from './AccessTokenDialog';

export function TopBar() {
  const [tokenOpen, setTokenOpen] = useState(false);
  const hasAccessToken = Boolean(getAccessToken());
  const { data: health, isError, isLoading } = useQuery({
    queryKey: ['health', 'readyz'],
    queryFn: () => healthApi.readiness(),
    refetchInterval: 10000,
    retry: 0,
    enabled: hasAccessToken,
  });

  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const rightOpen = useUIStore((s) => s.rightSidebarOpen);
  const showAmbient = useUIStore((s) => s.showFluidBackground);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const toggleRight = useUIStore((s) => s.toggleRightSidebar);
  const toggleAmbient = useUIStore((s) => s.toggleFluidBackground);
  const setSidebar = useUIStore((s) => s.setSidebar);
  const setRight = useUIStore((s) => s.setRightSidebar);

  const online = hasAccessToken && !isError && Boolean(health?.llm);
  const persistOn = Boolean(health?.persist?.enabled && health.persist.mode !== 'disabled');

  const connection = !hasAccessToken
    ? { label: '连接知识库', tone: 'text-amber-300', icon: KeyRound }
    : isLoading
      ? { label: '正在连接', tone: 'text-muted-foreground', icon: Loader2 }
      : online
        ? { label: '已连接', tone: 'text-emerald-300', icon: Check }
        : { label: '服务不可用', tone: 'text-red-300', icon: WifiOff };
  const ConnectionIcon = connection.icon;

  return (
    <>
      <header className="relative z-40 h-[4.25rem] shrink-0 px-2 pt-2 md:px-3">
        <div className="apple-material-thin mx-auto flex h-[3.25rem] min-w-0 items-center gap-1.5 rounded-[1.15rem] px-1.5 md:px-2.5">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => { setRight(false); setSidebar(!sidebarOpen); }}
            title="打开知识库"
            aria-label="打开知识库"
            className="shrink-0 lg:hidden"
          >
            <Menu className="h-[1.1rem] w-[1.1rem]" />
          </Button>

          <div className="flex min-w-0 items-center gap-2.5 px-1.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[.72rem] bg-primary text-white shadow-[inset_0_1px_0_rgba(255,255,255,.28),0_8px_22px_rgba(10,132,255,.25)]">
              <Bot className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-[13px] font-semibold leading-none tracking-[-0.02em]">NEXUS</h1>
              <p className="mt-1 truncate text-[9px] font-medium tracking-[0.035em] text-muted-foreground">Private Knowledge</p>
            </div>
          </div>

          <div className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-2 rounded-[.72rem] bg-black/15 px-3 py-1.5 text-[10px] text-muted-foreground md:flex">
            <span className="font-medium text-foreground/80">知识工作台</span>
            <span className="h-1 w-1 rounded-full bg-white/20" />
            <span>v{health?.version || '—'}</span>
          </div>

          <div className="ml-auto flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => setTokenOpen(true)}
              className={cn(
                'apple-focus apple-pressable hidden h-8 items-center gap-1.5 rounded-[.68rem] border border-white/[0.07] bg-white/[0.045] px-2.5 text-[10px] font-medium sm:inline-flex',
                connection.tone,
              )}
            >
              <ConnectionIcon className={cn('h-3 w-3', isLoading && hasAccessToken && 'animate-spin')} />
              {connection.label}
            </button>

            {online && (
              <div className="hidden h-8 items-center gap-2 rounded-[.68rem] bg-black/15 px-2.5 text-[9px] text-muted-foreground xl:flex" title={`持久化模式: ${health?.persist?.mode || 'unknown'}`}>
                <Database className="h-3 w-3 text-primary" />
                <span>{health?.chroma ? 'Vector Ready' : 'Vector —'}</span>
                <span className="h-3 w-px bg-white/10" />
                <span>{persistOn ? 'HF Sync' : 'Local'}</span>
              </div>
            )}

            <Button
              size="icon"
              variant="ghost"
              onClick={() => setTokenOpen(true)}
              title="访问令牌"
              aria-label="设置访问令牌"
              className="sm:hidden"
            >
              <KeyRound className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant={showAmbient ? 'secondary' : 'ghost'}
              onClick={toggleAmbient}
              title={showAmbient ? '关闭环境光' : '开启环境光'}
              aria-label="切换环境光"
            >
              <Sparkles className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant={sidebarOpen ? 'secondary' : 'ghost'}
              onClick={toggleSidebar}
              title={sidebarOpen ? '折叠知识库' : '展开知识库'}
              aria-label="切换知识库"
              className="hidden lg:inline-flex"
            >
              <Database className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant={rightOpen ? 'secondary' : 'ghost'}
              onClick={() => {
                if (window.matchMedia('(max-width: 1023px)').matches) setSidebar(false);
                toggleRight();
              }}
              title={rightOpen ? '折叠历史对话' : '展开历史对话'}
              aria-label="切换历史对话栏"
            >
              {rightOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </header>

      <AccessTokenDialog open={tokenOpen} onOpenChange={setTokenOpen} />
    </>
  );
}
