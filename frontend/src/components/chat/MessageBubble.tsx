/**
 * 单条消息气泡. user 右对齐灰底, assistant 左对齐无背景.
 * assistant content 用 react-markdown 渲染 (GFM: 表格/任务列表/代码块等).
 */
import { Bot, User } from 'lucide-react';
import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';

import { cn } from '@/lib/utils';
import type { ChatMessage } from '@/stores/chatStore';

/** 兜底: 如果 <think> 块因为任何原因没在流式阶段被剥掉, 渲染前再剥一次. */
function stripThink(s: string): string {
  return s.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  // 实时剥离 <think> 块, 再交给 markdown 渲染
  const visibleText = useMemo(
    () => (isUser ? message.content : stripThink(message.content || '')),
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
          'max-w-[80%] rounded-lg px-4 py-2.5 text-sm leading-relaxed',
          isUser
            ? 'bg-primary text-primary-foreground whitespace-pre-wrap'
            : 'bg-muted text-foreground',
          message.streaming && 'streaming-cursor',
        )}
      >
        {isUser ? (
          // user 消息保留原样 (通常无 markdown 语法, 但也支持)
          visibleText || (message.streaming ? '' : '(空消息)')
        ) : (
          <div className="prose-chat">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
              components={{
                // 链接外开
                a: ({ node, ...props }) => (
                  <a {...props} target="_blank" rel="noopener noreferrer" />
                ),
              }}
            >
              {visibleText || (message.streaming ? '' : '_(无回答)_')}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
