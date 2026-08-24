/**
 * 单条消息气泡. user 右对齐灰底, assistant 左对齐无背景.
 * assistant content 用 react-markdown 渲染 (GFM: 表格/任务列表/代码块等).
 *
 * ⚡ A 改良版: 用 React.memo 包裹, 配合 Virtuoso computeItemKey.
 * 流式时, 父组件 re-render 不再让所有历史 bubble 跟着重渲染,
 * 只重渲当前 streaming 那个 (props 引用变化的那个).
 */
import { Bot, Copy, Loader2, User } from 'lucide-react';
import { memo, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';

import { cn } from '@/lib/utils';
import type { ChatMessage } from '@/stores/chatStore';

/** 兜底: 如果 <think> 块因为任何原因没在流式阶段被剥掉, 渲染前再剥一次. */
function stripThink(s: string): string {
  return s.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
}

function MessageBubbleInner({ message }: { message: ChatMessage }) {
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
          'flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border',
          isUser ? 'border-white/10 bg-white/[0.06] text-muted-foreground' : 'border-primary/20 bg-gradient-to-br from-primary to-violet-500 text-white shadow-[0_8px_24px_rgba(59,130,246,.2)]',
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={cn(
          'group/bubble relative max-w-[84%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
          isUser
            ? 'rounded-tr-md border border-primary/20 bg-primary/15 text-foreground whitespace-pre-wrap'
            : 'rounded-tl-md border border-white/[0.07] bg-white/[0.045] text-foreground shadow-[0_10px_35px_rgba(0,0,0,.12)]',
          message.streaming && 'streaming-cursor',
        )}
      >
        {!isUser && visibleText && (
          <button type="button" onClick={() => navigator.clipboard?.writeText(visibleText)} className="absolute -right-1 -top-8 hidden items-center gap-1 rounded-lg border border-white/[0.07] bg-card px-2 py-1 text-[9px] text-muted-foreground shadow-lg transition hover:text-foreground group-hover/bubble:flex" title="复制回答">
            <Copy className="h-3 w-3" /> 复制
          </button>
        )}
        {isUser ? (
          // user 消息保留原样 (通常无 markdown 语法, 但也支持)
          visibleText || (message.streaming ? '' : '(空消息)')
        ) : (
          <div className="prose-chat">
            {message.streaming && !visibleText ? (
              <div className="flex min-h-6 items-center gap-2 text-muted-foreground" role="status">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                <span>{message.progress?.label || 'Agent 正在分析问题…'}</span>
              </div>
            ) : (
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
                {visibleText || '_(无回答)_'}
              </ReactMarkdown>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * ⚡ React.memo: 默认浅比较 props.
 * 流式时父组件 messages 数组每次都新建, 但非流消息的 props 引用未变,
 * → memo 阻止重渲. 仅当本条 message 引用变化时才重渲.
 */
export const MessageBubble = memo(MessageBubbleInner);
