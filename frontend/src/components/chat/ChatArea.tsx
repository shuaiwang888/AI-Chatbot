/**
 * ChatArea 容器. 包含 MessageList + ChatInput.
 */
import { useEffect, useState } from 'react';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { useChatStore } from '@/stores/chatStore';
import { getOrCreateSessionId } from '@/lib/utils';

export function ChatArea() {
  const storedId = useChatStore((s) => s.sessionId);
  const setSessionId = useChatStore((s) => s.setSessionId);
  // 兜底 id: 启动时从 localStorage 取 (固定 uuid), 首次 send 时写回 store.
  const [fallbackId] = useState(() => getOrCreateSessionId());
  // 兜底 id 生效时, 同步进 store (避免 send 内 store vs params 比较永远为 true)
  useEffect(() => {
    if (!storedId && fallbackId) {
      setSessionId(fallbackId);
    }
  }, [storedId, fallbackId, setSessionId]);
  const sessionId = storedId || fallbackId;

  return (
    <div className="flex h-full flex-col">
      <MessageList />
      <ChatInput sessionId={sessionId} />
    </div>
  );
}
