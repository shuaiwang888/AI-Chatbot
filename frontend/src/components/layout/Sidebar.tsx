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
        'fixed inset-y-0 left-0 z-30 flex w-[min(22rem,88vw)] shrink-0 flex-col border-r border-white/[0.08] bg-[hsl(232_34%_10%/.98)] shadow-2xl backdrop-blur-xl transition duration-300 lg:relative lg:inset-auto lg:z-auto lg:rounded-2xl lg:border lg:bg-white/[0.025] lg:shadow-none',
        sidebarOpen ? 'translate-x-0 lg:w-[20rem]' : '-translate-x-full lg:w-14 lg:translate-x-0',
      )}
    >
      {/* 顶部栏 */}
      <div className="flex h-16 items-center gap-2 border-b border-white/[0.06] px-3">
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
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500/25 to-violet-500/20 text-blue-200">
              <Database className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">知识库</p>
              <p className="text-[9px] text-muted-foreground">Knowledge workspace</p>
            </div>
          </div>
        )}
      </div>

      {sidebarOpen && (
        <div className="flex-1 space-y-4 overflow-y-auto p-3 scrollbar-thin">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.035] px-2 py-2.5 text-center">
              <p className="text-base font-semibold text-foreground">{summary.total}</p>
              <p className="text-[9px] text-muted-foreground">全部资料</p>
            </div>
            <div className="rounded-xl border border-emerald-500/10 bg-emerald-500/[0.05] px-2 py-2.5 text-center">
              <p className="text-base font-semibold text-emerald-300">{summary.ready}</p>
              <p className="text-[9px] text-muted-foreground">已就绪</p>
            </div>
            <div className="rounded-xl border border-violet-500/10 bg-violet-500/[0.05] px-2 py-2.5 text-center">
              <p className="text-base font-semibold text-violet-300">{summary.inProgress}</p>
              <p className="text-[9px] text-muted-foreground">处理中</p>
            </div>
          </div>
          <UploadPanel />
          <div className="border-t border-white/[0.06] pt-3">
            <h3 className="mb-2 flex items-center justify-between px-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              <span className="inline-flex items-center gap-1.5"><BookOpenCheck className="h-3.5 w-3.5" /> 已上传资料</span>
              <span className="inline-flex items-center gap-1 font-normal normal-case tracking-normal text-primary"><Sparkles className="h-3 w-3" /> 自动索引</span>
            </h3>
            <DocumentList />
          </div>
        </div>
      )}
    </aside>
  );
}
