/**
 * ChatArea 容器. 包含 MessageList + ChatInput + 背景 LightRays 效果.
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
 * 背景效果: LightRays 光束 (WebGL ogl). 默认开启, uiStore 关闭.
 *   - absolute 定位, pointer-events-none 不挡交互
 *   - mix-blend-mode: screen 让光束与浅背景融合
 *   - raysOrigin 从顶部中央向下发射 (默认)
 *   - followMouse 鼠标移动时光束方向微微偏转
 */
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { lazy, Suspense } from 'react';
import { BadgeCheck, BrainCircuit } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';
import { useUIStore } from '@/stores/uiStore';

// WebGL/OGL is decorative; keep it out of the initial interactive bundle.
const LightRays = lazy(() => import('@/components/effects/LightRays'));

export function ChatArea() {
  const sessionId = useChatStore((s) => s.sessionId);
  const showFluidBackground = useUIStore((s) => s.showFluidBackground);

  return (
    <div className="relative flex h-full flex-col overflow-hidden rounded-none bg-[radial-gradient(circle_at_50%_-20%,rgba(75,94,255,.12),transparent_44%)] lg:rounded-2xl lg:border lg:border-white/[0.07] lg:bg-black/10 lg:shadow-[0_24px_80px_rgba(0,0,0,.18)]">
      {/* 背景光束层 (WebGL, pointer-events-none 不挡交互) */}
      {showFluidBackground && (
        <div
          className="pointer-events-none absolute inset-0 z-0 mix-blend-screen opacity-50"
        >
          <Suspense fallback={null}>
            <LightRays
              raysOrigin="top-center"
              raysColor="#8b9eff"
              raysSpeed={0.6}
              lightSpread={0.55}
              rayLength={1.6}
              followMouse={true}
              mouseInfluence={0.15}
              noiseAmount={0.05}
              distortion={0.03}
            />
          </Suspense>
        </div>
      )}

      <div className="relative z-10 flex h-12 shrink-0 items-center justify-between border-b border-white/[0.06] px-4 md:px-6">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-primary/25 to-violet-500/15 text-blue-200">
            <BrainCircuit className="h-3.5 w-3.5" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-foreground">知识库对话</p>
            <p className="hidden text-[9px] text-muted-foreground sm:block">检索、推理、引用自动完成</p>
          </div>
        </div>
        <div className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.06] bg-white/[0.035] px-2.5 py-1.5 text-[10px] text-muted-foreground" title="使用混合检索、重排和引用生成">
          <BadgeCheck className="h-3 w-3 text-emerald-400" /> RAG 增强模式
        </div>
      </div>
      <div className="relative z-10 min-h-0 flex-1">
        <MessageList />
      </div>
      <ChatInput sessionId={sessionId} />
    </div>
  );
}
