/**
 * 消息列表. 含 ThinkingPanel / AgentStepTrace / CitationPanel 的内联展示.
 * 用 react-virtuoso 虚拟化, 适合长对话.
 */
import { useEffect, useRef } from 'react';
import { Virtuoso, type VirtuosoHandle } from 'react-virtuoso';
import { MessageBubble } from './MessageBubble';
import { ThinkingPanel } from './ThinkingPanel';
import { AgentStepTrace } from './AgentStepTrace';
import { CitationPanel } from './CitationPanel';
import { useChatStore } from '@/stores/chatStore';

export function MessageList() {
  const messages = useChatStore((s) => s.messages);
  const virtuosoRef = useRef<VirtuosoHandle>(null);

  // 新消息自动滚到底
  useEffect(() => {
    virtuosoRef.current?.scrollToIndex({ index: messages.length - 1, behavior: 'smooth' });
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <div className="text-center">
          <div className="text-4xl">💬</div>
          <p className="mt-3 text-sm">开始提问吧. 上传文档后, Agent 会基于你的知识库回答.</p>
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
