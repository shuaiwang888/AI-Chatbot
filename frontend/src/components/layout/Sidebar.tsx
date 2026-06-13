/**
 * 左侧栏: 上传 + 文档列表.
 */
import { useUIStore } from '@/stores/uiStore';
import { UploadPanel } from '@/components/documents/UploadPanel';
import { DocumentList } from '@/components/documents/DocumentList';
import { Button } from '@/components/ui/button';
import { PanelLeftClose, PanelLeftOpen, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';

export function Sidebar() {
  const { sidebarOpen, toggleSidebar } = useUIStore();

  return (
    <aside
      className={cn(
        'flex shrink-0 flex-col border-r bg-muted/20 transition-all',
        sidebarOpen ? 'w-80' : 'w-12',
      )}
    >
      {/* 顶部栏 */}
      <div className="flex h-14 items-center gap-2 border-b px-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          title={sidebarOpen ? '收起侧栏' : '展开侧栏'}
        >
          {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
        </Button>
        {sidebarOpen && (
          <div className="flex items-center gap-1.5 text-sm font-semibold">
            <FileText className="h-4 w-4" />
            知识库
          </div>
        )}
      </div>

      {sidebarOpen && (
        <div className="flex-1 space-y-4 overflow-y-auto p-3 scrollbar-thin">
          <UploadPanel />
          <div className="border-t pt-3">
            <h3 className="mb-2 px-1 text-xs font-semibold text-muted-foreground">
              已上传文档
            </h3>
            <DocumentList />
          </div>
        </div>
      )}
    </aside>
  );
}
