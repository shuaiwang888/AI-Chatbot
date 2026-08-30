/**
 * 聊天输入框. Enter 发送, Shift+Enter 换行, Stop 按钮中断流.
 */
import { useCallback, useEffect, useRef, type KeyboardEvent } from 'react';
import { ArrowUp, BookOpen, CornerDownLeft, RotateCcw, Sparkles, Square } from 'lucide-react';
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

  useEffect(() => {
    const focusComposer = (event: globalThis.KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        taRef.current?.focus();
      }
    };
    window.addEventListener('keydown', focusComposer);
    return () => window.removeEventListener('keydown', focusComposer);
  }, []);

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
    <div className="safe-bottom relative z-10 px-3 pt-2 md:px-6 md:pb-4">
      <div className="mx-auto max-w-4xl">
        {error && (
          <div className="mb-2 rounded-[.8rem] border border-destructive/15 bg-destructive/[0.07] px-3 py-2 text-xs text-destructive" role="alert">
            {error}
          </div>
        )}
        <div
          className={cn(
            'apple-material spring-surface overflow-hidden rounded-[1.35rem]',
            'focus-within:border-primary/45 focus-within:shadow-[inset_0_1px_0_rgba(255,255,255,.07),0_18px_55px_rgba(10,132,255,.15)]',
          )}
        >
          <div className="flex items-center gap-2 px-4 pb-0 pt-3 text-[10px] text-muted-foreground">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/[0.11] px-2 py-1 font-medium text-primary">
              <BookOpen className="h-3 w-3" /> 全知识库
            </span>
            <span className="inline-flex items-center gap-1.5"><Sparkles className="h-3 w-3" /> 自动规划与检索</span>
            <kbd className="ml-auto hidden rounded-md border border-white/[0.07] bg-black/15 px-1.5 py-0.5 font-sans text-[9px] text-muted-foreground/80 sm:inline">{navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'} K</kbd>
          </div>
          <div className="flex items-end gap-2 p-3">
            <textarea
              ref={taRef}
              data-chat-input
              value={text}
              onChange={onChange}
              onKeyDown={onKeyDown}
              placeholder={placeholder ?? '向你的知识库提问，或描述一个需要完成的任务…'}
              aria-label="聊天输入"
              rows={1}
              className="min-h-[50px] max-h-[180px] flex-1 resize-none bg-transparent px-1 py-2.5 text-[15px] leading-6 outline-none placeholder:text-muted-foreground/60"
              disabled={isStreaming}
            />
            {isStreaming ? (
              <Button size="icon" variant="destructive" onClick={stop} title="停止生成" className="mb-1 h-10 w-10 rounded-full">
                <Square className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                size="icon"
                onClick={submit}
                disabled={!text.trim() || !sessionId}
                title={sessionId ? '发送 (Enter)' : '正在准备对话…'}
                className="mb-1 h-10 w-10 rounded-full shadow-[inset_0_1px_0_rgba(255,255,255,.25),0_8px_22px_rgba(10,132,255,.24)]"
              >
                <ArrowUp className="h-4 w-4 stroke-[2.5]" />
              </Button>
            )}
          </div>
        </div>
        <div className="mt-2 flex items-center justify-between px-1 text-[10px] text-muted-foreground/65">
          <span className="hidden items-center gap-1 sm:inline-flex"><CornerDownLeft className="h-3 w-3" /> Enter 发送 · Shift + Enter 换行</span>
          <button
            onClick={reset}
            className="apple-focus inline-flex items-center gap-1 rounded-md px-1 py-0.5 hover:text-foreground"
            title="清空当前对话 (不会删除后端 session)"
          >
            <RotateCcw className="h-3 w-3" /> 清空当前视图
          </button>
        </div>
      </div>
    </div>
  );
}
