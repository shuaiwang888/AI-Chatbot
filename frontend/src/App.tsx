import { useEffect } from 'react';
import { HashRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { TopBar } from '@/components/layout/TopBar';
import { Sidebar } from '@/components/layout/Sidebar';
import { SessionHistoryPanel } from '@/components/sessions/SessionHistoryPanel';
import { AppRouter } from '@/router';
import { useUIStore } from '@/stores/uiStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 3000,
      gcTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
    },
  },
});

function Workspace() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const rightOpen = useUIStore((s) => s.rightSidebarOpen);
  const setSidebar = useUIStore((s) => s.setSidebar);
  const setRightSidebar = useUIStore((s) => s.setRightSidebar);

  useEffect(() => {
    const compact = window.matchMedia('(max-width: 1023px)');
    const closeDrawers = (matches: boolean) => {
      if (!matches) return;
      setSidebar(false);
      setRightSidebar(false);
    };
    closeDrawers(compact.matches);
    const onViewportChange = (event: MediaQueryListEvent) => closeDrawers(event.matches);
    compact.addEventListener('change', onViewportChange);
    return () => compact.removeEventListener('change', onViewportChange);
  }, [setSidebar, setRightSidebar]);

  return (
    <div className="relative flex h-full min-w-0 flex-col overflow-hidden bg-[radial-gradient(circle_at_15%_0%,rgba(65,87,255,.12),transparent_35%),radial-gradient(circle_at_85%_100%,rgba(139,92,246,.08),transparent_30%)]">
      <TopBar />
      <div className="relative flex min-h-0 flex-1 min-w-0 gap-0 overflow-hidden lg:gap-3 lg:p-3 lg:pt-2">
        {(sidebarOpen || rightOpen) && (
          <button
            type="button"
            aria-label="关闭侧栏"
            className="absolute inset-0 z-20 bg-black/55 backdrop-blur-sm lg:hidden"
            onClick={() => { setSidebar(false); setRightSidebar(false); }}
          />
        )}
        <Sidebar />
        <main className="min-w-0 flex-1 overflow-hidden">
          <AppRouter />
        </main>
        <SessionHistoryPanel />
      </div>
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <HashRouter>
        <Workspace />
        {/* 全局 toast: 删除/上传/错误反馈. theme 跟项目深色主题配 */}
        <Toaster theme="dark" position="bottom-right" richColors closeButton />
      </HashRouter>
    </QueryClientProvider>
  );
}
