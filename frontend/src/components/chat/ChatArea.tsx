/**
 * ChatArea 容器. 包含 MessageList + ChatInput.
 *
 * sessionId 解析:
 * - 优先用 store.sessionId (右侧栏/handleNew 写入)
 * - 首次 mount 时若 store 为空, 把 fallback (localStorage uuid) 写回 store
 *   (保证 ChatInput 始终有 id, 避免 useChatStream.send 内 store vs params 比较永远为 true)
 *
 * 关键: useEffect 只在 mount 时跑一次. deps 故意不跟 storedId,
 * 否则用户点 +新对话 setSessionId('') 时 effect 会重跑, 把 fallback 写回,
 * 导致 useSession(fallback) 加载旧 session 消息, +新对话就显示旧窗口.
 */
import { useEffect, useState } from 'react';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { useChatStore } from '@/stores/chatStore';
import { getOrCreateSessionId } from '@/lib/utils';

export function ChatArea() {
  const storedId = useChatStore((s) => s.sessionId);
  const setSessionId = useChatStore((s) => s.setSessionId);
  // 兜底 id: 启动时从 localStorage 取 (固定 uuid), 仅 mount 时写回 store.
  const [fallbackId] = useState(() => getOrCreateSessionId());
  useEffect(() => {
    if (!storedId && fallbackId) {
      setSessionId(fallbackId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // mount-only
  const sessionId = storedId || fallbackId;

  return (
    <div className="flex h-full flex-col">
      <MessageList />
      <ChatInput sessionId={sessionId} />
    </div>
  );
}
