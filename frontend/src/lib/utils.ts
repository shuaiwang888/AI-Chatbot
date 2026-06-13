import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** shadcn 风格 className 合并 (clsx + tailwind-merge). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** 字节数 -> 人性化 (KB/MB/GB). */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

/** Unix 时间戳 -> 本地化相对时间 (e.g. "3 分钟前"). */
export function formatRelativeTime(ts: number): string {
  const now = Date.now() / 1000;
  const diff = now - ts;
  if (diff < 5) return '刚刚';
  if (diff < 60) return `${Math.floor(diff)} 秒前`;
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} 天前`;
  return new Date(ts * 1000).toLocaleDateString('zh-CN');
}

/** 文件名截断 (保留扩展名). */
export function truncateFilename(name: string, max = 40): string {
  if (name.length <= max) return name;
  const ext = name.includes('.') ? name.slice(name.lastIndexOf('.')) : '';
  const stem = name.slice(0, name.length - ext.length);
  const keep = Math.max(0, max - ext.length - 1);
  return `${stem.slice(0, keep)}…${ext}`;
}

/** 生成/取 session id (localStorage 持久化). */
export function getOrCreateSessionId(): string {
  const KEY = 'ai-chatbot:session-id';
  let id = localStorage.getItem(KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(KEY, id);
  }
  return id;
}

/** 重置 session id. */
export function resetSessionId(): string {
  const id = crypto.randomUUID();
  localStorage.setItem('ai-chatbot:session-id', id);
  return id;
}
