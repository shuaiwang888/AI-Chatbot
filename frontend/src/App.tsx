import { HashRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { TopBar } from '@/components/layout/TopBar';
import { Sidebar } from '@/components/layout/Sidebar';
import { SessionHistoryPanel } from '@/components/sessions/SessionHistoryPanel';
import { AppRouter } from '@/router';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 3000,
      gcTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <HashRouter>
        <div className="flex h-full min-w-0 flex-col">
          <TopBar />
          <div className="flex flex-1 min-w-0 overflow-hidden">
            <Sidebar />
            <main className="flex-1 min-w-0 overflow-hidden">
              <AppRouter />
            </main>
            <SessionHistoryPanel />
          </div>
        </div>
        {/* 全局 toast: 删除/上传/错误反馈. theme 跟项目深色主题配 */}
        <Toaster theme="dark" position="bottom-right" richColors closeButton />
      </HashRouter>
    </QueryClientProvider>
  );
}
