/**
 * HashRouter 路由 (兼容 GitHub Pages).
 *
 * 路由:
 *   /#/                -> 重定向到 /chat
 *   /#/chat            -> 主聊天 (默认)
 *   /#/documents       -> 文档管理 (全屏)
 *   /#/sessions        -> 会话历史 (阶段 6)
 */
import { Navigate, Route, Routes } from 'react-router-dom';
import { ChatArea } from '@/components/chat/ChatArea';
import { DocumentList } from '@/components/documents/DocumentList';
import { ScrollArea } from '@/components/ui/scroll-area';

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/chat" replace />} />
      <Route path="/chat" element={<ChatArea />} />
      <Route
        path="/documents"
        element={
          <div className="mx-auto max-w-3xl p-6">
            <h2 className="mb-4 text-lg font-semibold">知识库管理</h2>
            <ScrollArea className="h-[calc(100vh-180px)]">
              <DocumentList />
            </ScrollArea>
          </div>
        }
      />
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}
