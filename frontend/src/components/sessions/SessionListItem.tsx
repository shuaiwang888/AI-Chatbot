/**
 * 单个 session 项. 显示标题/首条消息预览/时间/消息数, 支持点击切换、删除、重命名.
 */
import { useEffect, useRef, useState } from 'react';
import { Loader2, MessageSquare, MoreHorizontal, Pencil, Trash2, Check, X } from 'lucide-react';

import { useDeleteSession, useRenameSession } from '@/hooks/useSessions';
import { formatRelativeTime } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import type { SessionMeta } from '@/types';

export interface SessionListItemProps {
  session: SessionMeta;
  active: boolean;
  onSelect: (id: string) => void;
  collapsed?: boolean; // 折叠态 (侧栏收起来)
}

export function SessionListItem({ session, active, onSelect, collapsed }: SessionListItemProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(session.title ?? '');
  const inputRef = useRef<HTMLInputElement | null>(null);
  const del = useDeleteSession();
  const rename = useRenameSession();

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  const title = session.title?.trim() || 'Untitled chat';

  function commitRename() {
    const v = draft.trim();
    setEditing(false);
    if (!v || v === session.title) {
      setDraft(session.title ?? '');
      return;
    }
    rename.mutate({ id: session.id, title: v });
  }

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    // 一次点击直接弹原生确认框 (用户要求)
    if (window.confirm(`确认删除对话"${title}"?\n\n该操作不可撤销.`)) {
      del.mutate(session.id);
    }
  }

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => onSelect(session.id)}
        title={title}
        className={cn(
          'flex h-10 w-10 items-center justify-center rounded-md transition',
          active
            ? 'bg-primary/10 text-primary'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground',
        )}
      >
        <MessageSquare className="h-4 w-4" />
      </button>
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => !editing && onSelect(session.id)}
      onKeyDown={(e) => {
        if (editing) return;
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(session.id);
        }
      }}
      className={cn(
        'group flex w-full cursor-pointer items-start gap-2 rounded-md px-2 py-2 text-left transition',
        active
          ? 'bg-primary/10 text-foreground'
          : 'text-foreground/85 hover:bg-muted',
      )}
    >
      <MessageSquare
        className={cn(
          'mt-0.5 h-3.5 w-3.5 shrink-0',
          active ? 'text-primary' : 'text-muted-foreground',
        )}
      />
      <div className="min-w-0 flex-1">
        {editing ? (
          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitRename();
                if (e.key === 'Escape') {
                  setDraft(session.title ?? '');
                  setEditing(false);
                }
              }}
              onBlur={commitRename}
              className="min-w-0 flex-1 rounded border border-input bg-background px-1.5 py-0.5 text-sm outline-none focus:ring-1 focus:ring-ring"
              maxLength={200}
            />
            <Button
              size="icon"
              variant="ghost"
              className="h-6 w-6"
              onClick={commitRename}
              disabled={rename.isPending}
            >
              {rename.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-6 w-6"
              onClick={(e) => {
                e.stopPropagation();
                setDraft(session.title ?? '');
                setEditing(false);
              }}
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
        ) : (
          <>
            <div className="line-clamp-2 break-words text-sm font-medium" title={title}>
              {title}
            </div>
            <div className="mt-0.5 truncate text-[10px] text-muted-foreground">
              {session.message_count} 条 · {formatRelativeTime(session.updated_at)}
            </div>
          </>
        )}
      </div>
      {!editing && (
        <div
          className={cn(
            'flex shrink-0 items-center gap-0.5 opacity-60 transition-opacity',
            'group-hover:opacity-100 focus-within:opacity-100 hover:opacity-100',
          )}
          onClick={(e) => e.stopPropagation()}
        >
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6"
                aria-label="更多操作"
              >
                <MoreHorizontal className="h-3.5 w-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-32">
              <DropdownMenuItem onClick={() => setEditing(true)}>
                <Pencil className="mr-2 h-3.5 w-3.5" />
                重命名
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={handleDelete}
                className="text-destructive focus:text-destructive"
              >
                {del.isPending ? (
                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="mr-2 h-3.5 w-3.5" />
                )}
                删除
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}
    </div>
  );
}
