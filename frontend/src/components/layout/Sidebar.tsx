/**
 * 左侧栏: 上传 + 文档列表.
 */
import { useUIStore } from '@/stores/uiStore';
import { UploadPanel } from '@/components/documents/UploadPanel';
import { DocumentList } from '@/components/documents/DocumentList';
import { Button } from '@/components/ui/button';
import { BookOpenCheck, Database, PanelLeftClose, PanelLeftOpen, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { summarizeDocs, useDocuments } from '@/hooks/useDocuments';

export function Sidebar() {
  const { sidebarOpen, toggleSidebar } = useUIStore();
  const docsQ = useDocuments();
  const summary = summarizeDocs(docsQ.data?.documents);

  return (
    <aside
      className={cn(
        'apple-material-heavy spring-surface fixed bottom-0 left-0 top-[4.25rem] z-30 flex w-[min(22rem,90vw)] shrink-0 flex-col rounded-r-[1.55rem] border-y-0 border-l-0 lg:relative lg:inset-auto lg:z-auto lg:rounded-[1.55rem] lg:border',
        sidebarOpen ? 'translate-x-0 lg:w-[19rem]' : '-translate-x-full lg:w-14 lg:translate-x-0',
      )}
    >
      <div className="absolute left-1/2 top-2 h-1 w-9 -translate-x-1/2 rounded-full bg-white/15 lg:hidden" />
      {/* 顶部栏 */}
      <div className="flex h-14 items-center gap-2 px-2.5">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          title={sidebarOpen ? '收起侧栏' : '展开侧栏'}
        >
          {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
        </Button>
        {sidebarOpen && (
          <div className="flex min-w-0 items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-[.72rem] bg-primary/12 text-primary">
              <Database className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-[13px] font-semibold tracking-[-0.015em]">资料库</p>
              <p className="text-[9px] text-muted-foreground">{summary.ready} 份内容可检索</p>
            </div>
          </div>
        )}
      </div>

      {sidebarOpen && (
        <div className="scroll-edge-mask flex-1 space-y-4 overflow-y-auto px-3 py-4 scrollbar-thin">
          <div className="grid grid-cols-3 divide-x divide-white/[0.07] rounded-[1rem] bg-black/15 px-1 py-2.5">
            <div className="px-2 text-center">
              <p className="text-[15px] font-semibold tracking-[-0.03em] text-foreground">{summary.total}</p>
              <p className="mt-0.5 text-[9px] text-muted-foreground">全部</p>
            </div>
            <div className="px-2 text-center">
              <p className="text-[15px] font-semibold tracking-[-0.03em] text-emerald-300">{summary.ready}</p>
              <p className="mt-0.5 text-[9px] text-muted-foreground">已就绪</p>
            </div>
            <div className="px-2 text-center">
              <p className="text-[15px] font-semibold tracking-[-0.03em] text-amber-300">{summary.inProgress}</p>
              <p className="mt-0.5 text-[9px] text-muted-foreground">处理中</p>
            </div>
          </div>
          <UploadPanel />
          <div className="pt-1">
            <h3 className="mb-2.5 flex items-center justify-between px-1 text-[10px] font-semibold tracking-[0.04em] text-muted-foreground">
              <span className="inline-flex items-center gap-1.5"><BookOpenCheck className="h-3.5 w-3.5" /> 已上传资料</span>
              <span className="inline-flex items-center gap-1 font-normal tracking-normal text-primary"><Sparkles className="h-3 w-3" /> 自动索引</span>
            </h3>
            <DocumentList />
          </div>
        </div>
      )}
    </aside>
  );
}
