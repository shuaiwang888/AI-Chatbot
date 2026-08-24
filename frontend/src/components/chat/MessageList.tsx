/**
 * 消息列表. 含 AgentStepTrace / CitationPanel 的内联展示.
 * 模型原始 reasoning 只用于从正文剥离，不直接暴露；过程反馈由结构化节点事件提供。
 * 用 react-virtuoso 虚拟化, 适合长对话.
 */
import { lazy, Suspense, useEffect, useRef } from 'react';
import { Loader2 } from 'lucide-react';
import { Virtuoso, type VirtuosoHandle } from 'react-virtuoso';
import { AgentStepTrace } from './AgentStepTrace';
import { CitationPanel } from './CitationPanel';
import { useChatStore } from '@/stores/chatStore';
import { WelcomeDashboard } from './WelcomeDashboard';

// Markdown + syntax highlighting are only needed once a message is rendered.
const MessageBubble = lazy(() => import('./MessageBubble').then((m) => ({ default: m.MessageBubble })));

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
    return <WelcomeDashboard />;
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
        <div className="mx-auto max-w-4xl space-y-3 px-4 py-4 md:px-8">
          {msg.role !== 'user' && (msg.agentSteps?.length || msg.retrieval || msg.progress) && (
            <div className="ml-11 space-y-2">
              {(msg.retrieval || msg.agentSteps?.length || msg.progress) && (
                <AgentStepTrace
                  retrieval={msg.retrieval}
                  steps={msg.agentSteps}
                  progress={msg.progress}
                />
              )}
            </div>
          )}
          <Suspense fallback={<div className="h-16 rounded-lg bg-muted/40" />}>
            <MessageBubble message={msg} />
          </Suspense>
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
