/**
 * 聊天输入框. Enter 发送, Shift+Enter 换行, Stop 按钮中断流.
 */
import { useCallback, useEffect, useRef, type KeyboardEvent } from 'react';
import { BookOpen, CornerDownLeft, Loader2, RotateCcw, Send, Sparkles, Square } from 'lucide-react';
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
  const taRef = useRef<HTMLTextAreaElement>(null);
  const { send, stop, isStreaming } = useChatStream();
  const reset = useChatStore((s) => s.reset);
  const error = useChatStore((s) => s.error);
  const text = useChatStore((s) => s.draft);
  const setText = useChatStore((s) => s.setDraft);

  useEffect(() => {
    if (!taRef.current) return;
    taRef.current.style.height = 'auto';
    taRef.current.style.height = Math.min(taRef.current.scrollHeight, 180) + 'px';
  }, [text]);

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
    <div className="relative z-10 px-3 pb-3 pt-2 md:px-6 md:pb-5">
      <div className="mx-auto max-w-4xl">
        {error && (
          <div className="mb-2 text-xs text-destructive">⚠️ {error}</div>
        )}
        <div
          className={cn(
            'overflow-hidden rounded-2xl border border-white/10 bg-[hsl(232_31%_13%/.92)] shadow-[0_18px_55px_rgba(1,4,20,.45)] backdrop-blur-xl transition',
            'focus-within:border-primary/40 focus-within:shadow-[0_18px_55px_rgba(20,55,140,.22)]',
          )}
        >
          <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-2.5 text-[10px] text-muted-foreground">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2 py-1 font-medium text-blue-200">
              <BookOpen className="h-3 w-3" /> 全知识库
            </span>
            <span className="inline-flex items-center gap-1.5"><Sparkles className="h-3 w-3 text-violet-300" /> Agent 自动规划</span>
          </div>
          <div className="flex items-end gap-2 p-3">
            <textarea
              ref={taRef}
              data-chat-input
              value={text}
              onChange={onChange}
              onKeyDown={onKeyDown}
              placeholder={placeholder ?? '向你的知识库提问，或描述一个需要完成的任务…'}
              rows={1}
              className="min-h-[48px] max-h-[180px] flex-1 resize-none bg-transparent px-1 py-2 text-sm leading-6 outline-none placeholder:text-muted-foreground/70"
              disabled={isStreaming}
            />
            {isStreaming ? (
              <Button size="icon" variant="destructive" onClick={stop} title="停止生成" className="h-10 w-10 rounded-xl">
                <Square className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                size="icon"
                onClick={submit}
                disabled={!text.trim() || !sessionId}
                title={sessionId ? '发送 (Enter)' : '正在准备对话…'}
                className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-500 to-violet-500 text-white shadow-[0_8px_24px_rgba(59,130,246,.28)] hover:from-blue-400 hover:to-violet-400"
              >
                <Send className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
        <div className="mt-2 flex items-center justify-between px-1 text-[10px] text-muted-foreground/70">
          <span className="hidden items-center gap-1 sm:inline-flex"><CornerDownLeft className="h-3 w-3" /> Enter 发送 · Shift + Enter 换行</span>
          <button
            onClick={reset}
            className="inline-flex items-center gap-1 transition hover:text-foreground"
            title="清空当前对话 (不会删除后端 session)"
          >
            <RotateCcw className="h-3 w-3" /> 清空当前视图
          </button>
        </div>
      </div>
    </div>
  );
}

// 没用上的导出, 避免 TS6133
export { Loader2 };
