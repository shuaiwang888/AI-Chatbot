/**
 * ChatArea 容器. 包含 MessageList + ChatInput + 背景 Ferrofluid 效果.
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
 * 背景效果: Ferrofluid 流体 (WebGL ogl). 默认开启, uiStore 关闭.
 *   - absolute 定位, pointer-events-none 不挡交互
 *   - mix-blend-mode: lighten 让亮色 rim 与浅背景融合
 *   - opacity 0.55 不挡文字阅读
 */
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import Ferrofluid from '@/components/effects/Ferrofluid';
import { useChatStore } from '@/stores/chatStore';
import { useUIStore } from '@/stores/uiStore';

export function ChatArea() {
  const sessionId = useChatStore((s) => s.sessionId);
  const showFluidBackground = useUIStore((s) => s.showFluidBackground);

  return (
    <div className="relative flex h-full flex-col">
      {/* 背景流体层 (WebGL, pointer-events-none 不挡交互) */}
      {showFluidBackground && (
        <div className="pointer-events-none absolute inset-0 -z-10">
          <Ferrofluid
            colors={['#6366F1', '#06B6D4', '#8B5CF6', '#EC4899']}
            speed={0.4}
            scale={1.2}
            turbulence={1.2}
            fluidity={0.15}
            rimWidth={0.25}
            sharpness={2.5}
            shimmer={0.8}
            glow={1.5}
            flowDirection="down"
            opacity={0.55}
            mouseInteraction={true}
            mouseStrength={0.6}
            mouseRadius={0.25}
            mixBlendMode="lighten"
          />
        </div>
      )}

      <MessageList />
      <ChatInput sessionId={sessionId} />
    </div>
  );
}
