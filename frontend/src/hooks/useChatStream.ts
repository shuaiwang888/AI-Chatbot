/**
 * SSE 消费者 hook. 把 streamChat + chatStore 绑在一起.
 *
 * 用法:
 *   const { send, stop, isStreaming } = useChatStream();
 *   await send({ sessionId, message });
 */
import { useCallback, useRef } from 'react';
import { dispatchStreamEvent, useChatStore } from '@/stores/chatStore';
import { streamChat, SSEError } from '@/lib/sse';

export function useChatStream() {
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(async (params: { sessionId: string; message: string; docIds?: string[] | null }) => {
    const store = useChatStore.getState();
    // 如果 sessionId 变化了, 先清空 (新会话不显示旧消息).
    // 同一 session 内继续发, 保留历史.
    if (store.sessionId !== params.sessionId) {
      store.reset();
    }
    store.setSessionId(params.sessionId);
    store.appendUser(params.message);
    store.startAssistant();

    // 中断上一轮
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      for await (const evt of streamChat(
        {
          session_id: params.sessionId,
          message: params.message,
          doc_ids: params.docIds ?? null,
        },
        { signal: ctrl.signal },
      )) {
        dispatchStreamEvent(evt);
        if (evt.type === 'done' || evt.type === 'error') break;
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') {
        useChatStore.getState().finishAssistant();
        return;
      }
      const err = e as SSEError | Error;
      useChatStore.getState().failAssistant(
        (err as Error).message || '未知错误',
      );
    } finally {
      if (abortRef.current === ctrl) {
        abortRef.current = null;
      }
    }
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    useChatStore.getState().finishAssistant();
  }, []);

  return {
    send,
    stop,
    isStreaming: useChatStore((s) => s.isStreaming),
  };
}
