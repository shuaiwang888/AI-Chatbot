/**
 * 单条消息气泡. user 右对齐灰底, assistant 左对齐无背景.
 */
import { Bot, User } from 'lucide-react';
import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import type { ChatMessage } from '@/stores/chatStore';

/** 兜底: 如果 <think> 块因为任何原因没在流式阶段被剥掉 (e.g. 一次性大 token),
 *  渲染前再剥一次. 实时累加在 chatStore.appendToken 完成, 这里只做最后清理. */
function stripThink(s: string): string {
  return s.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  const visibleContent = useMemo(
    () => (isUser ? message.content : stripThink(message.content)),
    [message.content, isUser],
  );

  return (
    <div
      className={cn(
        'flex w-full gap-3',
        isUser ? 'flex-row-reverse' : 'flex-row',
      )}
    >
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-muted text-muted-foreground' : 'bg-primary text-primary-foreground',
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={cn(
          'max-w-[80%] whitespace-pre-wrap rounded-lg px-4 py-2.5 text-sm leading-relaxed',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted text-foreground',
          message.streaming && 'streaming-cursor',
        )}
      >
        {visibleContent || (message.streaming ? '' : '(空消息)')}
      </div>
    </div>
  );
}
