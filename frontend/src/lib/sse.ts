/**
 * SSE 解析器 (fetch + ReadableStream).
 *
 * 为什么不用 EventSource: 它只支持 GET, 我们要 POST JSON.
 *
 * 输入: fetch Response 对象
 * 输出: async iterator of StreamEventPayload
 *
 * 后端 SSE 格式:
 *   event: <type>
 *   data: <json>
 *   \n\n
 */
import { apiBase } from '@/env';
import type { StreamEventPayload, StreamEventType } from '@/types';

export class SSEError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'SSEError';
  }
}

export interface StreamOptions {
  signal?: AbortSignal;
  onEvent?: (evt: StreamEventPayload) => void;
}

/**
 * 流式消费 chat API 的 SSE 事件.
 * 退出条件: 收到 `done` 或 `error` 事件, 或 connection 关闭.
 */
export async function* streamChat(
  body: { session_id: string; message: string; doc_ids?: string[] | null; locale?: 'zh' | 'en' },
  options: StreamOptions = {},
): AsyncGenerator<StreamEventPayload, void, void> {
  const res = await fetch(`${apiBase}/api/v1/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: options.signal,
  });

  if (!res.ok) {
    let detail = '';
    try {
      detail = (await res.text()).slice(0, 200);
    } catch {
      // ignore
    }
    throw new SSEError(res.status, `SSE connection failed: ${res.status} ${detail}`);
  }
  if (!res.body) {
    throw new SSEError(0, 'No response body');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      if (options.signal?.aborted) break;
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // 按 \n\n 切完整事件
      let sepIdx: number;
      while ((sepIdx = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, sepIdx);
        buffer = buffer.slice(sepIdx + 2);

        const evt = _parseSSERaw(rawEvent);
        if (evt) {
          options.onEvent?.(evt);
          yield evt;
          if (evt.type === 'done' || evt.type === 'error') return;
        }
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // ignore
    }
  }
}

function _parseSSERaw(raw: string): StreamEventPayload | null {
  let eventName: StreamEventType | null = null;
  const dataLines: string[] = [];

  for (const line of raw.split('\n')) {
    if (line.startsWith(':')) continue; // 注释/心跳
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim() as StreamEventType;
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (!eventName) return null;
  let data: any = {};
  const dataStr = dataLines.join('\n');
  if (dataStr && dataStr !== '[DONE]') {
    try {
      data = JSON.parse(dataStr);
    } catch {
      data = { raw: dataStr };
    }
  }
  return { type: eventName, data } as StreamEventPayload;
}
