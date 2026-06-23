/**
 * 聊天输入框. Enter 发送, Shift+Enter 换行, Stop 按钮中断流.
 */
import { useCallback, useRef, useState, type KeyboardEvent } from 'react';
import { Send, Square, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useChatStream } from '@/hooks/useChatStream';
import { useChatStore } from '@/stores/chatStore';
import { cn } from '@/lib/utils';

export interface ChatInputProps {
  sessionId: string;
  docIds?: string[];
  placeholder?: string;
}

export function ChatInput({ sessionId, docIds, placeholder }: ChatInputProps) {
  const [text, setText] = useState('');
  const taRef = useRef<HTMLTextAreaElement>(null);
  const { send, stop, isStreaming } = useChatStream();
  const reset = useChatStore((s) => s.reset);
  const error = useChatStore((s) => s.error);

  const submit = useCallback(async () => {
    const msg = text.trim();
    if (!msg || isStreaming) return;
    // ⚠️ 自动新建对话的 50ms 窗口: SessionHistoryPanel 触发 handleNew →
    // POST /sessions → setSessionId(新id). 此期间 sessionId 为 '',
    // send() 会被 useChatStream 拒绝 (返回 error). 等几百毫秒后用户重发即可.
    // 这里额外判断, 直接拒绝避免误发到错误 session.
    if (!sessionId) {
      console.warn('[ChatInput] sessionId empty, please retry after auto-create completes');
      return;
    }
    setText('');
    if (taRef.current) taRef.current.style.height = 'auto';
    try {
      await send({ sessionId, message: msg, docIds });
    } catch (e) {
      console.error('send failed', e);
    }
  }, [text, isStreaming, send, sessionId, docIds]);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  };

  // 自动撑高
  const onChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    const ta = e.target;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 240) + 'px';
  };

  return (
    <div className="border-t bg-background px-4 py-3">
      <div className="mx-auto max-w-3xl">
        {error && (
          <div className="mb-2 text-xs text-destructive">⚠️ {error}</div>
        )}
        <div
          className={cn(
            'flex items-end gap-2 rounded-lg border bg-card p-2 shadow-sm',
            'focus-within:ring-2 focus-within:ring-ring',
          )}
        >
          <textarea
            ref={taRef}
            value={text}
            onChange={onChange}
            onKeyDown={onKeyDown}
            placeholder={placeholder ?? '输入问题, Enter 发送, Shift+Enter 换行...'}
            rows={1}
            className="min-h-[36px] max-h-[240px] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground"
            disabled={isStreaming}
          />
          {isStreaming ? (
            <Button
              size="icon"
              variant="destructive"
              onClick={stop}
              title="停止生成"
            >
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              size="icon"
              onClick={submit}
              disabled={!text.trim() || !sessionId}
              title={sessionId ? '发送 (Enter)' : '正在准备对话…'}
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
        <div className="mt-1.5 flex items-center justify-between text-[10px] text-muted-foreground">
          <span>Agent 模式 · 引用源 · 多轮对话</span>
          <button
            onClick={reset}
            className="hover:text-foreground"
            title="清空当前对话 (不会删除后端 session)"
          >
            清空对话
          </button>
        </div>
      </div>
    </div>
  );
}

// 没用上的导出, 避免 TS6133
export { Loader2 };
