/**
 * 历史对话右栏. 镜像左侧 Sidebar 模式: 可折叠 (w-80/w-12), 默认展开.
 *
 * 关键交互修复 (vs 旧版本):
 * - 旧版用 useEffect 看 [sessionId], 闭包里用 currentDetail.data, 但 React 18
 *   不会因为 data 变化重跑 effect (deps 只看 sessionId), 导致"点了没反应".
 * - 新版用 useSelectSession (mutation): 点击 → mutate(id) → 后台 fetch →
 *   onSuccess(detail) 同步把 messages 写进 chatStore. 不依赖 useEffect 桥接.
 * - handleSelect 立即清 messages + 设 isStreaming 标志, MessageList 显示 spinner,
 *   给用户"我正在切"的视觉反馈 (之前的 1-3 秒空白期用户会以为没点中).
 */
import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Loader2, MessageSquareText, PanelRightClose, PanelRightOpen, Plus } from 'lucide-react';

import { useChatStore } from '@/stores/chatStore';
import { useUIStore } from '@/stores/uiStore';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  useCreateSession,
  useSelectSession,
  useSessions,
  sortSessions,
} from '@/hooks/useSessions';
import { SessionListItem } from './SessionListItem';
import { cn } from '@/lib/utils';

export function SessionHistoryPanel() {
  const open = useUIStore((s) => s.rightSidebarOpen);
  const toggle = useUIStore((s) => s.toggleRightSidebar);
  const sessionId = useChatStore((s) => s.sessionId);
  const setSessionId = useChatStore((s) => s.setSessionId);
  const reset = useChatStore((s) => s.reset);
  const loadSessionMessages = useChatStore((s) => s.loadSessionMessages);
  const setLoadingSession = useChatStore((s) => s.setLoadingSession);

  const sessionsQ = useSessions(50);
  const createMut = useCreateSession();
  const selectMut = useSelectSession();
  const queryClient = useQueryClient();

  const handleNew = useCallback(() => {
    // 路径:
    // 1. 删掉所有 useSelectSession cache — 防止旧 session 的 messages 仍被缓存
    // 2. reset() 清 messages + currentAssistantId + isStreaming
    // 3. 显式 loadSessionMessages([]) — 保险, 立即给用户空状态视觉反馈
    // 4. setSessionId('') — 中断当前 sessionId 引用
    // 5. createMut 创建新 session, onSuccess 拿到新 id, setSessionId(新id)
    //    (注意: 新 session 的 detail 不需要 fetch, messages 永远是空, 不调 selectMut)
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

  // ⚡ 自动进入对话 (首次打开 / 刷新页面):
  //
  // 行为:
  // 1. store.sessionId 已经有 → 啥都不做 (用户手动点过 history)
  // 2. 后端 sessions 列表已加载:
  //    a. 列表最新一条是空 session (message_count == 0) → 重用它
  //       (避免刷新页面就堆一堆 "Untitled chat")
  //    b. 列表最新一条有内容 (message_count > 0) → 新建一个空 session
  //    c. 列表为空 → 新建一个空 session
  // 3. 后端 sessions 还在 loading → 等加载完再决定 (effect 重跑)
  //
  // 用 ref 防 React 18 strict mode 双重 mount 导致的两次 create.
  const autoCreatedRef = useRef(false);
  useEffect(() => {
    if (autoCreatedRef.current) return;
    if (sessionId) return;            // 已有 session, 不动
    if (createMut.isPending) return;  // 已经在建, 等它完成

    // 还在加载 sessions 列表 → 等
    if (sessionsQ.isLoading) return;
    // 加载失败 (后端离线) → 也新建, 让用户至少能跟 LLM 聊 (虽然没 history)
    // 这里不 return, 直接走 handleNew

    const list = sortSessions(sessionsQ.data?.sessions);
    const newest = list[0];

    autoCreatedRef.current = true;

    if (newest && newest.message_count === 0) {
      // 重用最新的空 session (它本来就是上次刷新时"自动新建"留下的,
      // 用户大概率还没开始打字). 同样清 messages + 设 active.
      setSessionId(newest.id);
      loadSessionMessages([]);
      return;
    }

    // 列表里没有空 session (要么空列表, 要么最新一条已经有消息) → 新建
    handleNew();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionsQ.isLoading, sessionsQ.data, sessionId, createMut.isPending]);

  const handleSelect = useCallback(
    (id: string) => {
      if (id === sessionId) return;
      // ⚡ 立即视觉反馈:
      // - 切 sessionId 让左栏标题更新
      // - 清空 messages
      // - 设 loadingSessionId → MessageList 立刻显示 "加载对话历史…"
      //   (而不是等到 1-3 秒后 fetch 完成才换)
      setSessionId(id);
      loadSessionMessages([]);
      setLoadingSession(id);

      // ⚡ 主动 fetch + onSuccess 写 store (替代不可靠的 useEffect):
      // mutation 在 mutationKey 变化时不会重跑, 所以这里手动 cancel + reset,
      // 确保不会因为之前 in-flight 的 mutation 结果覆盖新 session 的 messages.
      selectMut.reset();
      selectMut.mutate(id, {
        onSuccess: (detail) => {
          // ⚠️ 防止"用户在新 session 还没来时又点了别的 session"的竞态:
          // 只在当前 sessionId 仍然是这个 id 时才写 store
          const currentId = useChatStore.getState().sessionId;
          if (currentId === id) {
            loadSessionMessages(detail.messages);
            // loadSessionMessages 内部会清 loadingSessionId
          }
        },
        onError: () => {
          // 失败也要清掉, 不然 spinner 永远转
          const currentId = useChatStore.getState().sessionId;
          if (currentId === id) setLoadingSession(null);
        },
      });
    },
    [sessionId, setSessionId, loadSessionMessages, setLoadingSession, selectMut],
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
