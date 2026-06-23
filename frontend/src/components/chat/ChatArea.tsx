/**
 * ChatArea 容器. 包含 MessageList + ChatInput.
 *
 * sessionId 来源:
 * - 只用 store.sessionId (右侧栏 / 自动创建 / 历史点击 写入)
 * - ⚠️ 不再用 localStorage fallback: 之前代码在 ChatArea mount 时
 *   从 localStorage 读上次的 sessionId 写回 store, 导致用户刷新页面
 *   自动进入"上次那个对话". 用户反馈: 期望"首次打开项目应该是新建对话".
 *
 *   现在首次打开 store 是空的, MessageList 显示欢迎页.
 *   SessionHistoryPanel 在 mount 时如果 store.sessionId=='' 自动调
 *   handleNew() 建新 session → setSessionId(新id) → 进入全新对话.
 *
 *   注意: ChatInput 拿到的 sessionId 可能是空字符串 (在自动新建的
 *   异步过程中, 几毫秒), 这种短暂窗口 send() 会被禁用 (见 useChatStream
 *   的 isPending / 校验). 不影响正常使用.
 */
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { useChatStore } from '@/stores/chatStore';

export function ChatArea() {
  const sessionId = useChatStore((s) => s.sessionId);

  return (
    <div className="flex h-full flex-col">
      <MessageList />
      <ChatInput sessionId={sessionId} />
    </div>
  );
}
