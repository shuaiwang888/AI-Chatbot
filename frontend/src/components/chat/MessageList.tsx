/**
 * 消息列表. 含 ThinkingPanel / AgentStepTrace / CitationPanel 的内联展示.
 * 用 react-virtuoso 虚拟化, 适合长对话.
 */
import { useEffect, useRef } from 'react';
import { Loader2 } from 'lucide-react';
import { Virtuoso, type VirtuosoHandle } from 'react-virtuoso';
import { MessageBubble } from './MessageBubble';
import { ThinkingPanel } from './ThinkingPanel';
import { AgentStepTrace } from './AgentStepTrace';
import { CitationPanel } from './CitationPanel';
import { useChatStore } from '@/stores/chatStore';

export function MessageList() {
  const messages = useChatStore((s) => s.messages);
  const loadingSessionId = useChatStore((s) => s.loadingSessionId);
  const virtuosoRef = useRef<VirtuosoHandle>(null);

  // 新消息自动滚到底
  useEffect(() => {
    virtuosoRef.current?.scrollToIndex({ index: messages.length - 1, behavior: 'smooth' });
  }, [messages.length]);

  if (messages.length === 0) {
    // 区分两种空状态 (用 loadingSessionId 而非 sessionId 判断,
    // 避免新对话 handleNew 把 sessionId 设成新 id 后误判为 "正在加载历史"):
    // - loadingSessionId 有值: 点了历史对话, fetch 进行中 → 显示 spinner
    // - loadingSessionId null: 全新对话 / 新建对话 → 显示欢迎页
    if (loadingSessionId) {
      return (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          加载对话历史…
        </div>
      );
    }
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <div className="max-w-md text-center">
          <div className="mb-3 flex justify-center gap-3 text-3xl">
            <span title="知识库">📚</span>
            <span title="Agent">🤖</span>
            <span title="引用源">💡</span>
          </div>
          <p className="text-sm font-medium text-foreground/80">开始提问吧</p>
          <p className="mt-1 text-xs text-muted-foreground">
            上传 PDF / Word / 图片到左侧 <strong>知识库</strong>,
            <br />Agent 会基于你的文档回答, 并标注 <strong>引用源</strong>.
          </p>
        </div>
      </div>
    );
  }

  return (
    <Virtuoso
      ref={virtuosoRef}
      data={messages}
      className="h-full"
      followOutput="smooth"
      // ⚡ A 改良版: computeItemKey 让 Virtuoso 用稳定 id 跟踪 row,
      // 避免默认按 index 重建所有已渲染 row 引用 → 配合 MessageBubble 的
      // React.memo, 流式时只有当前那条重渲, 历史 bubble 全部跳过.
      computeItemKey={(_, msg) => msg.id}
      itemContent={(_, msg) => (
        <div className="mx-auto max-w-3xl space-y-3 px-4 py-3">
          {msg.role !== 'user' && (msg.thinking || msg.agentSteps?.length || msg.retrieval) && (
            <div className="ml-11 space-y-2">
              {msg.thinking && <ThinkingPanel content={msg.thinking} />}
              {msg.retrieval && (
                <AgentStepTrace
                  retrieval={msg.retrieval}
                  steps={msg.agentSteps}
                  progress={msg.progress}
                />
              )}
            </div>
          )}
          <MessageBubble message={msg} />
          {msg.role === 'assistant' && msg.citations && msg.citations.length > 0 && (
            <div className="ml-11">
              <CitationPanel citations={msg.citations} />
            </div>
          )}
          {msg.error && (
            <div className="ml-11 rounded border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              ⚠️ {msg.error}
            </div>
          )}
        </div>
      )}
    />
  );
}
