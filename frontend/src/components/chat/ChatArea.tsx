/**
 * ChatArea 容器. 包含 MessageList + ChatInput.
 */
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { useChatStore } from '@/stores/chatStore';
import { getOrCreateSessionId } from '@/lib/utils';

export function ChatArea() {
  const sessionId = useChatStore((s) => s.sessionId) || getOrCreateSessionId();

  return (
    <div className="flex h-full flex-col">
      <MessageList />
      <ChatInput sessionId={sessionId} />
    </div>
  );
}
