/**
 * ChatArea 容器. 包含 MessageList + ChatInput + restrained ambient depth.
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
 *
 * 环境光使用静态 CSS 材质，避免全视口持续运动，并尊重用户的运动偏好.
 */
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { BadgeCheck, BrainCircuit } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';
import { useUIStore } from '@/stores/uiStore';

export function ChatArea() {
  const sessionId = useChatStore((s) => s.sessionId);
  const showAmbient = useUIStore((s) => s.showFluidBackground);

  return (
    <div className="apple-material-thin relative flex h-full flex-col overflow-hidden rounded-none border-x-0 border-b-0 lg:rounded-[1.55rem] lg:border">
      {showAmbient && (
        <div className="pointer-events-none absolute left-1/2 top-[-13rem] z-0 h-[28rem] w-[42rem] max-w-[95vw] -translate-x-1/2 rounded-full bg-primary/[0.09] blur-[90px]" />
      )}

      <div className="relative z-10 flex h-14 shrink-0 items-center justify-between px-4 after:absolute after:inset-x-0 after:bottom-0 after:h-5 after:translate-y-full after:bg-gradient-to-b after:from-[rgba(15,17,23,.5)] after:to-transparent after:content-[''] md:px-6">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-[.62rem] bg-white/[0.065] text-primary shadow-[inset_0_1px_0_rgba(255,255,255,.06)]">
            <BrainCircuit className="h-3.5 w-3.5" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-xs font-semibold tracking-[-0.01em] text-foreground">知识库对话</p>
            <p className="hidden text-[9px] text-muted-foreground sm:block">检索、组织与引用自动完成</p>
          </div>
        </div>
        <div className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.05] px-2.5 py-1.5 text-[10px] font-medium text-muted-foreground" title="使用混合检索、证据筛选和引用生成">
          <BadgeCheck className="h-3 w-3 text-emerald-400" /> 知识增强
        </div>
      </div>
      <div className="relative z-10 min-h-0 flex-1">
        <MessageList />
      </div>
      <ChatInput sessionId={sessionId} />
    </div>
  );
}
