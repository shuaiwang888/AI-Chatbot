/**
 * 聊天状态管理 (Zustand).
 *
 * 关注点:
 * - 消息列表 (user/assistant)
 * - 流式 token 累积 (per assistant message)
 * - 引用 (citations)
 * - Agent 步骤 (debug)
 * - 错误 + retry
 *
 * ⚡ A 改良版: appendToken 用 requestAnimationFrame 帧合并,
 * 同一帧内多个 SSE token 只触发 1 次 set, 减少 50-80% 渲染开销.
 * 长回答末段尤其明显 (避免"打字掉帧").
 */
import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import type {
  AgentStepEvent,
  Citation,
  ProgressEvent,
  RetrievalEvent,
  SessionMessage,
  StreamEventPayload,
  ThinkingEvent,
  ToolCallEvent,
} from '@/types';

export interface ChatMessage {
  id: string;                  // 客户端 UUID
  role: 'user' | 'assistant' | 'system';
  content: string;             // user: 原内容; assistant: 已累积 token
  thinking?: string;
  citations?: Citation[];
  toolCalls?: ToolCallEvent[];
  agentSteps?: AgentStepEvent[];
  retrieval?: RetrievalEvent;
  progress?: ProgressEvent;
  error?: string;
  streaming?: boolean;         // assistant 是否正在流式
  createdAt: number;
  // 内部: 跨 token 的 思考块解析状态 (不进 React render)
  _thinkState?: 'normal' | 'in_think';
  _thinkBuf?: string;
}

interface ChatState {
  sessionId: string;
  messages: ChatMessage[];
  isStreaming: boolean;
  currentAssistantId: string | null;  // 正在流式的 assistant 消息 id
  /** 正在 fetch 这个 session 的历史 (点击历史对话时设, onSuccess 清).
   *  MessageList 用它判断是否显示 "加载对话历史…". null = 不显示.
   *  关键: 新对话 handleNew 不设这个 flag → 永远显示欢迎页, 不会闪 loading.
   */
  loadingSessionId: string | null;
  error: string | null;
  // Show dev panels
  showAgentTrace: boolean;
  showCitations: boolean;

  // actions
  setSessionId: (id: string) => void;
  loadSessionMessages: (msgs: SessionMessage[]) => void;
  setLoadingSession: (id: string | null) => void;
  appendUser: (content: string) => string;       // 返回 message id
  startAssistant: () => string;                   // 返回 message id
  appendToken: (content: string) => void;
  setThinking: (content: string) => void;
  setRetrieval: (data: RetrievalEvent) => void;
  appendCitation: (c: Citation) => void;
  setAgentStep: (s: AgentStepEvent) => void;
  setProgress: (p: ProgressEvent) => void;
  appendToolCall: (tc: ToolCallEvent) => void;
  finishAssistant: () => void;
  failAssistant: (error: string) => void;
  reset: () => void;
  toggleAgentTrace: () => void;
  toggleCitations: () => void;
}

// ========== 模块级 rAF 工具 (SSR 兜底) ==========
// ⚡ 跨 token 累积: 多个 SSE token 推入 _tokenBuf, 同一帧内只触发 1 次 set.
// SSR / 测试环境没 requestAnimationFrame, 退化为 setTimeout 16ms.
const _rafImpl: (cb: () => void) => number =
  typeof requestAnimationFrame === 'function'
    ? requestAnimationFrame
    : ((cb: () => void) => setTimeout(cb, 16) as unknown as number);
const _cancelRaf: (id: number) => void =
  typeof cancelAnimationFrame === 'function'
    ? cancelAnimationFrame
    : ((id: number) => clearTimeout(id));

// THINK 块边界常量 (跟 chatStore 内同步)
const _THINK_OPEN = '<think' + '>';
const _THINK_CLOSE = '</think' + '>';


export const useChatStore = create<ChatState>()(
  subscribeWithSelector((set, get) => {
    // ⚡ 模块级 buffer 放在 create 闭包内, 这样 flush 函数能直接 set/get state.
    // 之前放模块顶层导致 _flushTokenBuffer 无法 set, 只能 .length=0 清掉 → 丢最后一批 token!
    const _tokenBuf: string[] = [];
    let _rafScheduled: number | null = null;

    /** 把 batched 字符串应用到 state, 走跟单 token 一样的 think 剥离逻辑. */
    function _applyTokenBatch(batched: string) {
      if (!batched) return;
      set((s) => ({
        messages: s.messages.map((m) => {
          if (m.id !== s.currentAssistantId) return m;
          const acc = m.content;
          const think = m.thinking || '';
          const buf = m._thinkBuf || '';
          const stream = buf + batched;
          let cursor = 0;
          let outContent = '';
          let outThink = '';
          let state: 'normal' | 'in_think' = (m._thinkState as any) || 'normal';
          while (cursor < stream.length) {
            if (state === 'normal') {
              const openIdx = stream.indexOf(_THINK_OPEN, cursor);
              if (openIdx === -1) {
                outContent += stream.slice(cursor);
                cursor = stream.length;
                break;
              }
              outContent += stream.slice(cursor, openIdx);
              cursor = openIdx + _THINK_OPEN.length;
              state = 'in_think';
            } else {
              const closeIdx = stream.indexOf(_THINK_CLOSE, cursor);
              if (closeIdx === -1) {
                outThink += stream.slice(cursor);
                cursor = stream.length;
                break;
              }
              outThink += stream.slice(cursor, closeIdx);
              cursor = closeIdx + _THINK_CLOSE.length;
              state = 'normal';
            }
          }
          return {
            ...m,
            content: acc + outContent,
            thinking: think + outThink,
            _thinkState: state,
            _thinkBuf: state === 'in_think' ? stream.slice(cursor) : '',
          };
        }),
      }));
    }

    /** 同步 flush: 取消 pending rAF, 立即把 buffer 应用到 state. */
    function _flushTokenBufferNow() {
      if (_rafScheduled !== null) {
        _cancelRaf(_rafScheduled);
        _rafScheduled = null;
      }
      if (_tokenBuf.length === 0) return;
      const batched = _tokenBuf.join('');
      _tokenBuf.length = 0;
      _applyTokenBatch(batched);
    }

    /** 简单清空 (不应用, 切 session / reset 时用, 因为要清的是错的 state). */
    function _clearTokenBuffer() {
      if (_rafScheduled !== null) {
        _cancelRaf(_rafScheduled);
        _rafScheduled = null;
      }
      _tokenBuf.length = 0;
    }

    return {
    sessionId: '',
    messages: [],
    isStreaming: false,
    currentAssistantId: null,
    loadingSessionId: null,
    error: null,
    showAgentTrace: false,
    showCitations: true,

    setSessionId: (id) => set({ sessionId: id }),
    // 不再 wipe messages; 由调用方显式调用 reset() / loadSessionMessages()

    setLoadingSession: (id) => set({ loadingSessionId: id }),

    /** 从后端 SessionDetail.messages 加载历史到当前 store. 替换现有 messages.
     *
     * 关键 guard: 如果正在 streaming, 跳过 (避免切到旧 session 时把刚 send 的 user +
     * 空 assistant 覆盖). 调用方应在切换 session 前先 stop() 当前流.
     *
     * 同时清掉 loadingSessionId — fetch 完成, 不再显示 loading.
     */
    loadSessionMessages: (msgs) => {
      if (get().isStreaming) {
        // 切到历史 session 时, 旧 session 的流还未结束 — 保留当前 messages,
        // 让用户先 stop 再切 (或忽略, 由 UI 处理).
        return;
      }
      _clearTokenBuffer();  // 切 session 时丢掉残留 token (不应用, 因为要换 messages)
      const messages: ChatMessage[] = (msgs ?? []).map((m) => ({
        id: m.id,
        role: m.role as ChatMessage['role'],
        content: m.content,
        createdAt: typeof m.created_at === 'number' ? m.created_at * 1000 : Date.now(),
      }));
      set({ messages, error: null, isStreaming: false, currentAssistantId: null, loadingSessionId: null });
    },

    appendUser: (content) => {
      const id = crypto.randomUUID();
      set((s) => ({
        messages: [
          ...s.messages,
          { id, role: 'user', content, createdAt: Date.now() },
        ],
      }));
      return id;
    },

    startAssistant: () => {
      const id = crypto.randomUUID();
      set((s) => ({
        messages: [
          ...s.messages,
          {
            id,
            role: 'assistant',
            content: '',
            citations: [],
            toolCalls: [],
            agentSteps: [],
            streaming: true,
            createdAt: Date.now(),
          },
        ],
        isStreaming: true,
        currentAssistantId: id,
        error: null,
      }));
      return id;
    },

    appendToken: (content) => {
      const { currentAssistantId } = get();
      if (!currentAssistantId) return;
      if (!content) return;
      // ⚡ 帧合并: 把 token 推到 buffer, requestAnimationFrame 调度一次 flush.
      // 同一帧内多个 SSE token 共享一次 set, 减少渲染开销 50-80%.
      _tokenBuf.push(content);
      if (_rafScheduled !== null) return;
      _rafScheduled = _rafImpl(() => {
        _rafScheduled = null;
        if (_tokenBuf.length === 0) return;
        const batched = _tokenBuf.join('');
        _tokenBuf.length = 0;  // 清空 buffer, 保留同一引用 (const)
        _applyTokenBatch(batched);
      });
    },

    setThinking: (content) => {
      const { currentAssistantId } = get();
      if (!currentAssistantId) return;
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === currentAssistantId
            ? { ...m, thinking: (m.thinking || '') + content }
            : m,
        ),
      }));
    },

    setRetrieval: (data) => {
      const { currentAssistantId } = get();
      if (!currentAssistantId) return;
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === currentAssistantId ? { ...m, retrieval: data } : m,
        ),
      }));
    },

    appendCitation: (c) => {
      const { currentAssistantId } = get();
      if (!currentAssistantId) return;
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === currentAssistantId
            ? {
                ...m,
                citations: [...(m.citations || []), c],
              }
            : m,
        ),
      }));
    },

    setAgentStep: (step) => {
      const { currentAssistantId } = get();
      if (!currentAssistantId) return;
      set((s) => ({
        messages: s.messages.map((m) => {
          if (m.id !== currentAssistantId) return m;
          // 关键: 按 node 去重, 同一个节点 (e.g. "answer") 多次事件 (running → done) 只保留一条,
          // 避免在 AgentStepTrace 中显示两个 "生成:" 标签 (其中一条一直 spinning).
          const steps = m.agentSteps || [];
          const idx = steps.findIndex((x) => x.node === step.node);
          if (idx >= 0) {
            const next = steps.slice();
            next[idx] = step;  // 覆盖, 状态从 running → done
            return { ...m, agentSteps: next };
          }
          return { ...m, agentSteps: [...steps, step] };
        }),
      }));
    },

    setProgress: (p) => {
      const { currentAssistantId } = get();
      if (!currentAssistantId) return;
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === currentAssistantId ? { ...m, progress: p } : m,
        ),
      }));
    },

    appendToolCall: (tc) => {
      const { currentAssistantId } = get();
      if (!currentAssistantId) return;
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === currentAssistantId
            ? { ...m, toolCalls: [...(m.toolCalls || []), tc] }
            : m,
        ),
      }));
    },

    finishAssistant: () => {
      _flushTokenBufferNow();  // ⚠️ 必须 flush **应用** 最后一帧, 不然末批 token 丢
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === s.currentAssistantId ? { ...m, streaming: false } : m,
        ),
        isStreaming: false,
        currentAssistantId: null,
      }));
    },

    failAssistant: (error) => {
      _flushTokenBufferNow();  // ⚠️ 必须 flush 应用
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === s.currentAssistantId
            ? { ...m, streaming: false, error }
            : m,
        ),
        isStreaming: false,
        currentAssistantId: null,
        error,
      }));
    },

    reset: () => {
      _clearTokenBuffer();
      set({ messages: [], error: null, currentAssistantId: null, isStreaming: false, loadingSessionId: null });
    },
    toggleAgentTrace: () => set((s) => ({ showAgentTrace: !s.showAgentTrace })),
    toggleCitations: () => set((s) => ({ showCitations: !s.showCitations })),
  };
  })
);

/**
 * 把 SSE 事件分发到 store.
 * 集中处理, 避免 useChatStream 里散落.
 */
export function dispatchStreamEvent(evt: StreamEventPayload): void {
  const store = useChatStore.getState();
  switch (evt.type) {
    case 'thinking':
      store.setThinking((evt.data as ThinkingEvent).content);
      break;
    case 'agent_step':
      store.setAgentStep(evt.data as AgentStepEvent);
      break;
    case 'retrieval':
      store.setRetrieval(evt.data as RetrievalEvent);
      break;
    case 'token':
      store.appendToken((evt.data as { content: string }).content);
      break;
    case 'citation':
      store.appendCitation(evt.data as Citation);
      break;
    case 'tool_call':
      store.appendToolCall(evt.data as ToolCallEvent);
      break;
    case 'progress':
      store.setProgress(evt.data as ProgressEvent);
      break;
    case 'done':
      store.finishAssistant();
      break;
    case 'error':
      store.failAssistant((evt.data as { message: string }).message);
      break;
  }
}
