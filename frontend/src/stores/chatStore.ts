/**
 * 聊天状态管理 (Zustand).
 *
 * 关注点:
 * - 消息列表 (user/assistant)
 * - 流式 token 累积 (per assistant message)
 * - 引用 (citations)
 * - Agent 步骤 (debug)
 * - 错误 + retry
 */
import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import type {
  AgentStepEvent,
  Citation,
  ProgressEvent,
  RetrievalEvent,
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
  // 内部: 跨 token 的 <think> 块解析状态 (不进 React render)
  _thinkState?: 'normal' | 'in_think';
  _thinkBuf?: string;
}

interface ChatState {
  sessionId: string;
  messages: ChatMessage[];
  isStreaming: boolean;
  currentAssistantId: string | null;  // 正在流式的 assistant 消息 id
  error: string | null;
  // Show dev panels
  showAgentTrace: boolean;
  showCitations: boolean;

  // actions
  setSessionId: (id: string) => void;
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

export const useChatStore = create<ChatState>()(
  subscribeWithSelector((set, get) => ({
    sessionId: '',
    messages: [],
    isStreaming: false,
    currentAssistantId: null,
    error: null,
    showAgentTrace: false,
    showCitations: true,

    setSessionId: (id) => set({ sessionId: id, messages: [], error: null }),

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
      set((s) => ({
        messages: s.messages.map((m) => {
          if (m.id !== currentAssistantId) return m;
          // 实时剥离 <think>...</think> 块: 块内 → thinking, 块外 → content
          let acc = m.content;
          let think = m.thinking || '';
          let buf = m._thinkBuf || '';
          // 先把上次残留的 buf 与新 token 拼起来
          const stream = buf + content;
          let cursor = 0;
          let outContent = '';
          let outThink = '';
          let state: 'normal' | 'in_think' = (m._thinkState as any) || 'normal';
          while (cursor < stream.length) {
            if (state === 'normal') {
              const openIdx = stream.indexOf('<think>', cursor);
              if (openIdx === -1) {
                outContent += stream.slice(cursor);
                break;
              }
              outContent += stream.slice(cursor, openIdx);
              cursor = openIdx + '<think>'.length;
              state = 'in_think';
            } else {
              const closeIdx = stream.indexOf('</think>', cursor);
              if (closeIdx === -1) {
                outThink += stream.slice(cursor);
                break;
              }
              outThink += stream.slice(cursor, closeIdx);
              cursor = closeIdx + '</think>'.length;
              state = 'normal';
            }
          }
          return {
            ...m,
            content: acc + outContent,
            thinking: think + outThink,
            _thinkState: state,
            _thinkBuf: '',  // 已消费完
          };
        }),
      }));
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
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === s.currentAssistantId ? { ...m, streaming: false } : m,
        ),
        isStreaming: false,
        currentAssistantId: null,
      }));
    },

    failAssistant: (error) => {
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

    reset: () => set({ messages: [], error: null, currentAssistantId: null, isStreaming: false }),
    toggleAgentTrace: () => set((s) => ({ showAgentTrace: !s.showAgentTrace })),
    toggleCitations: () => set((s) => ({ showCitations: !s.showCitations })),
  })),
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
