/**
 * 历史对话右栏. 镜像左侧 Sidebar 模式: 可折叠 (w-80/w-12), 默认展开.
 *
 * - 顶部: + 新对话按钮 + 折叠按钮
 * - 中间: session 列表 (TanStack Query useSessions, 30s 轮询)
 * - 底部: 空状态 / loading / error
 *
 * 点击 session 触发 onSelect (切 sessionId + 加载消息).
 */
import { useCallback, useEffect, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Loader2, MessageSquareText, PanelRightClose, PanelRightOpen, Plus } from 'lucide-react';

import { useChatStore } from '@/stores/chatStore';
import { useUIStore } from '@/stores/uiStore';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useCreateSession, useSession, useSessions, sortSessions } from '@/hooks/useSessions';
import { SessionListItem } from './SessionListItem';
import { cn } from '@/lib/utils';

export function SessionHistoryPanel() {
  const open = useUIStore((s) => s.rightSidebarOpen);
  const toggle = useUIStore((s) => s.toggleRightSidebar);
  const sessionId = useChatStore((s) => s.sessionId);
  const setSessionId = useChatStore((s) => s.setSessionId);
  const reset = useChatStore((s) => s.reset);
  const loadSessionMessages = useChatStore((s) => s.loadSessionMessages);

  const sessionsQ = useSessions(50);
  const createMut = useCreateSession();
  const queryClient = useQueryClient();
  // 当前 session 的详情 (供点击时加载消息). 复用缓存.
  const currentDetail = useSession(sessionId || null);

  // sessionId 切换时, 加载该 session 的消息进 store
  // 关键: deps 只跟 sessionId. currentDetail.data 引用变化 (轮询) 不重载,
  // 否则会覆盖正在 streaming 的 user + 空 assistant.
  useEffect(() => {
    if (sessionId && currentDetail.data) {
      loadSessionMessages(currentDetail.data.messages);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const handleNew = useCallback(() => {
    // 关键路径 (按顺序):
    // 1. 删掉所有 useSession cache — 防止旧 session 的 messages 仍被缓存, 切时刷出来
    // 2. reset() 清 messages + currentAssistantId + isStreaming
    // 3. 显式 loadSessionMessages([]) — 保险, 不被 useEffect 异步覆盖
    // 4. setSessionId('') — 触发 useSession('') 不跑 (enabled:!!sessionId)
    // 5. createMut 创建新 session, onSuccess 拿到新 id, setSessionId(新id) 触发 useSession(新id)
    //    此时 useSession 是新 query key, 无 cache, fetch 后 currentDetail.data.messages=[],
    //    useEffect 触发 loadSessionMessages([]) 保持空
    queryClient.removeQueries({ queryKey: ['sessions'] });
    reset();
    loadSessionMessages([]);
    setSessionId('');
    createMut.mutate(undefined, {
      onSuccess: (res) => {
        setSessionId(res.session_id);
      },
    });
  }, [queryClient, reset, loadSessionMessages, setSessionId, createMut]);

  const handleSelect = useCallback(
    (id: string) => {
      if (id === sessionId) return;
      setSessionId(id);
      // 消息加载由上面的 useEffect 在 currentDetail.data 准备好后触发
    },
    [sessionId, setSessionId],
  );

  const sessions = useMemo(() => sortSessions(sessionsQ.data?.sessions), [sessionsQ.data]);

  if (!open) {
    // 折叠态: 只露一个竖排的展开按钮
    return (
      <aside className="flex w-12 shrink-0 flex-col items-center border-l bg-muted/20 py-2">
        <Button
          size="icon"
          variant="ghost"
          onClick={toggle}
          title="展开历史对话"
          aria-label="展开历史对话"
        >
          <PanelRightOpen className="h-4 w-4" />
        </Button>
        <div className="my-2 h-px w-6 bg-border" />
        <Button
          size="icon"
          variant="ghost"
          onClick={handleNew}
          title="新对话"
          aria-label="新对话"
          disabled={createMut.isPending}
        >
          {createMut.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Plus className="h-4 w-4" />
          )}
        </Button>
      </aside>
    );
  }

  return (
    <aside className="flex w-80 shrink-0 flex-col border-l bg-muted/20">
      {/* 顶部 */}
      <div className="flex h-12 shrink-0 items-center justify-between gap-1 border-b px-3">
        <div className="flex items-center gap-1.5 text-sm font-semibold">
          <MessageSquareText className="h-4 w-4" />
          <span>历史对话</span>
        </div>
        <div className="flex items-center gap-0.5">
          <Button
            size="icon"
            variant="ghost"
            onClick={handleNew}
            title="新对话"
            aria-label="新对话"
            disabled={createMut.isPending}
          >
            {createMut.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
          </Button>
          <Button
            size="icon"
            variant="ghost"
            onClick={toggle}
            title="折叠"
            aria-label="折叠"
          >
            <PanelRightClose className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* 列表 */}
      <ScrollArea className="flex-1">
        <div className="flex flex-col gap-0.5 p-2">
          {sessionsQ.isLoading && (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              加载中…
            </div>
          )}
          {sessionsQ.isError && (
            <div className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
              加载失败: {(sessionsQ.error as Error)?.message}
            </div>
          )}
          {!sessionsQ.isLoading && !sessionsQ.isError && sessions.length === 0 && (
            <div className="flex flex-col items-center justify-center px-4 py-12 text-center text-sm text-muted-foreground">
              <MessageSquareText className="mb-2 h-8 w-8 opacity-30" />
              <div className="mb-3">还没有对话</div>
              <Button size="sm" onClick={handleNew} disabled={createMut.isPending}>
                <Plus className="mr-1 h-3.5 w-3.5" />
                开始一个新对话
              </Button>
            </div>
          )}
          {sessions.map((s) => (
            <SessionListItem
              key={s.id}
              session={s}
              active={s.id === sessionId}
              onSelect={handleSelect}
            />
          ))}
        </div>
      </ScrollArea>
    </aside>
  );
}
