/**
 * 与后端 schemas.py 对齐的类型定义.
 * 后端用 Pydantic, 前端用 zod 校验 (如需要), 但这里直接用 TS interface.
 */

// ========== Chat ==========
export interface ChatRequest {
  session_id: string;
  message: string;
  doc_ids?: string[] | null;
  locale?: 'zh' | 'en';
}

export interface Citation {
  doc_id: string;
  filename?: string;
  page?: number | null;
  heading?: string | null;
  snippet: string;
  score: number;
  rank: number;
}

export interface ChatResponse {
  session_id: string;
  message_id: string;
  content: string;
  citations: Citation[];
  agent_steps: AgentStepEvent[];
  usage: Record<string, number>;
  total_ms: number;
}

// ========== AG-UI SSE events ==========
export type StreamEventType =
  | 'thinking'
  | 'agent_step'
  | 'retrieval'
  | 'tool_call'
  | 'token'
  | 'citation'
  | 'progress'
  | 'done'
  | 'error';

export interface AgentStepEvent {
  node: string;
  status: 'running' | 'done' | 'error';
}

export interface RetrievalEvent {
  doc_ids: string[];
  count: number;
  scores: number[];
}

export interface CitationEvent extends Citation {}

export interface ProgressEvent {
  pct: number;       // 0-100
  label: string;
}

export interface TokenEvent {
  content: string;
}

export interface ThinkingEvent {
  content: string;
}

export interface ToolCallEvent {
  name: string;
  args: Record<string, unknown>;
  result_summary?: string;
}

export interface DoneEvent {
  usage: Record<string, number>;
  total_ms: number;
}

export interface ErrorEvent {
  code: string;
  message: string;
  retryable: boolean;
  detail?: Record<string, unknown>;
}

export type StreamEventPayload =
  | { type: 'token'; data: TokenEvent }
  | { type: 'thinking'; data: ThinkingEvent }
  | { type: 'agent_step'; data: AgentStepEvent }
  | { type: 'retrieval'; data: RetrievalEvent }
  | { type: 'tool_call'; data: ToolCallEvent }
  | { type: 'citation'; data: CitationEvent }
  | { type: 'progress'; data: ProgressEvent }
  | { type: 'done'; data: DoneEvent }
  | { type: 'error'; data: ErrorEvent };

// ========== Documents ==========
export type DocumentStatus = 'uploading' | 'parsing' | 'embedding' | 'ready' | 'failed';

export interface DocumentMeta {
  id: string;
  filename: string;
  mime: string;
  size: number;
  page_count?: number | null;
  chunk_count: number;
  status: DocumentStatus;
  progress?: number;          // 0-100
  progress_label?: string | null;
  error?: string | null;
  created_at: number;
  sha256?: string | null;
  parser?: string | null;
  chunk_size?: number | null;
  chunk_overlap?: number | null;
  semantic_chunking?: boolean;
  contextual_retrieval?: boolean;
  meta?: Record<string, unknown>;
}

export interface DocumentChunk {
  id: string;
  doc_id: string;
  parent_id?: string | null;
  chunk_index: number;
  text: string;
  token_count?: number | null;
  page_no?: number | null;
  heading?: string | null;
  context_prefix?: string | null;
  created_at: number;
}

export interface DocumentChunksResponse {
  doc_id: string;
  chunks: DocumentChunk[];
  total: number;
  returned: number;
}

export interface IngestResult {
  doc_id: string;
  chunk_count: number;
  status: 'ready' | 'duplicate';
}

// ========== Sessions ==========
export interface SessionMeta {
  id: string;
  title?: string | null;
  message_count: number;
  created_at: number;
  updated_at: number;
}

export interface SessionMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  citations?: Citation[];
  tool_calls?: unknown[];
  created_at: number;
}

export interface SessionDetail {
  session: SessionMeta;
  messages: SessionMessage[];
}

// ========== Health ==========
export interface HealthStatus {
  status: 'ok' | 'degraded';
  llm: boolean;
  persist: {
    enabled: boolean;
    mode: 'disabled' | 'cold_restore' | 'fresh_start';
    pending_push: boolean;
    repo: string | null;
  };
  chroma: boolean;
  version: string;
}
