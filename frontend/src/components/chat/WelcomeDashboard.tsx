import {
  ArrowUpRight, BookOpenCheck, FileSearch, GitCompareArrows,
  ListChecks, ShieldCheck, Sparkles, WandSparkles,
} from 'lucide-react';

import { useDocuments, summarizeDocs } from '@/hooks/useDocuments';
import { useChatStore } from '@/stores/chatStore';
import { useUIStore } from '@/stores/uiStore';
import { cn } from '@/lib/utils';
import { getAccessToken } from '@/lib/auth';

const STARTERS = [
  {
    icon: FileSearch,
    title: '查找关键结论',
    description: '从资料中定位事实，并附上来源。',
    prompt: '请从知识库中查找最重要的结论，并标注每条结论的引用来源。',
    accent: 'text-blue-300 bg-blue-400/10',
  },
  {
    icon: GitCompareArrows,
    title: '比较多份资料',
    description: '整理共同点、差异与潜在冲突。',
    prompt: '请对比知识库中的相关文档，用表格列出共同点、差异和可能的冲突。',
    accent: 'text-indigo-300 bg-indigo-400/10',
  },
  {
    icon: ListChecks,
    title: '提炼摘要与行动项',
    description: '把长内容转换为决策与下一步。',
    prompt: '请总结相关文档，分别列出核心结论、风险、待确认事项和可执行的下一步。',
    accent: 'text-emerald-300 bg-emerald-400/10',
  },
  {
    icon: ShieldCheck,
    title: '审阅风险与遗漏',
    description: '识别矛盾、假设和信息缺口。',
    prompt: '请审阅知识库中的相关内容，找出风险、矛盾、未经证实的假设和信息缺口。',
    accent: 'text-amber-300 bg-amber-400/10',
  },
] as const;

export function WelcomeDashboard() {
  const setDraft = useChatStore((s) => s.setDraft);
  const setSidebar = useUIStore((s) => s.setSidebar);
  const docsQ = useDocuments();
  const summary = summarizeDocs(docsQ.data?.documents);
  const hasAccessToken = Boolean(getAccessToken());
  const serviceState = !hasAccessToken
    ? { label: '连接后即可读取私人资料', dot: 'bg-amber-400', ping: false }
    : docsQ.isLoading
      ? { label: '正在检查知识服务', dot: 'bg-amber-400', ping: false }
      : docsQ.isError
        ? { label: '知识服务暂不可用', dot: 'bg-red-400', ping: false }
        : { label: 'Knowledge Agent 已就绪', dot: 'bg-emerald-400', ping: true };

  const choosePrompt = (prompt: string) => {
    setDraft(prompt);
    requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('[data-chat-input]')?.focus());
  };

  return (
    <div className="welcome-scroll h-full overflow-y-auto scrollbar-thin">
      <div className="welcome-content mx-auto flex min-h-full w-full max-w-5xl flex-col justify-center px-5 py-9 sm:px-8 md:py-12 lg:px-12">
        <section className="mx-auto w-full max-w-3xl text-center">
          <div className="welcome-mark mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-[1.15rem] bg-primary text-white shadow-[inset_0_1px_0_rgba(255,255,255,.28),0_16px_44px_rgba(10,132,255,.25)]">
            <WandSparkles className="h-6 w-6" />
          </div>
          <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-white/[0.055] px-3 py-1.5 text-[11px] font-medium text-muted-foreground">
            <span className="relative flex h-1.5 w-1.5">
              {serviceState.ping && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-55" />}
              <span className={cn('relative inline-flex h-1.5 w-1.5 rounded-full', serviceState.dot)} />
            </span>
            {serviceState.label}
          </div>
          <h2 className="welcome-title text-balance text-[2.15rem] font-semibold leading-[1.08] tracking-[-0.045em] text-white sm:text-[2.65rem] md:text-[3.1rem]">
            让你的资料，成为<br className="hidden sm:block" />可以对话的知识。
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-[13px] leading-6 text-muted-foreground sm:text-sm">
            提问、比较、总结或审阅。NEXUS 会检索相关资料，组织答案，并保留每一条可追溯的引用。
          </p>
        </section>

        <section className="welcome-actions mx-auto mt-9 w-full max-w-4xl">
          <div className="mb-2.5 flex items-center justify-between px-1">
            <h3 className="text-[11px] font-semibold tracking-[0.02em] text-foreground/80">快速开始</h3>
            <span className="text-[10px] text-muted-foreground">选择一个任务来填入输入框</span>
          </div>
          <div className="grid overflow-hidden rounded-[1.25rem] border border-white/[0.075] bg-black/15 sm:grid-cols-2">
            {STARTERS.map((item, index) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.title}
                  type="button"
                  onClick={() => choosePrompt(item.prompt)}
                  className={cn(
                    'apple-focus apple-pressable group relative flex items-center gap-3 p-4 text-left hover:bg-white/[0.045]',
                    index % 2 === 0 && 'sm:border-r sm:border-white/[0.065]',
                    index < 2 && 'border-b border-white/[0.065]',
                    index === 2 && 'border-b border-white/[0.065] sm:border-b-0',
                  )}
                >
                  <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-[.82rem]', item.accent)}>
                    <Icon className="h-[1.05rem] w-[1.05rem]" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-semibold tracking-[-0.015em] text-foreground">{item.title}</p>
                    <p className="mt-1 text-[11px] leading-4 text-muted-foreground">{item.description}</p>
                  </div>
                  <ArrowUpRight className="h-4 w-4 shrink-0 text-muted-foreground/45 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-primary" />
                </button>
              );
            })}
          </div>
        </section>

        <div className="mx-auto mt-4 flex w-full max-w-4xl flex-col gap-3 rounded-[1rem] bg-white/[0.035] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-[.72rem] bg-white/[0.055] text-primary">
              <BookOpenCheck className="h-4 w-4" />
            </div>
            <div>
              <p className="text-xs font-semibold tracking-[-0.01em] text-foreground">
                {!hasAccessToken
                  ? '连接私人知识库'
                  : docsQ.isLoading
                    ? '正在连接知识库…'
                    : docsQ.isError
                      ? '知识服务连接失败'
                      : summary.ready > 0 ? `${summary.ready} 份资料可用于回答` : '知识库还是空的'}
              </p>
              <p className="mt-0.5 text-[10px] text-muted-foreground">
                {summary.inProgress > 0 ? `${summary.inProgress} 份资料正在解析` : '支持 PDF、Office、Markdown 与图片'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSidebar(true)}
            className="apple-focus apple-pressable inline-flex items-center gap-1.5 self-start rounded-[.7rem] px-2.5 py-2 text-xs font-semibold text-primary hover:bg-primary/10 sm:self-auto"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {!hasAccessToken || docsQ.isError ? '查看连接状态' : summary.total > 0 ? '管理资料' : '上传第一份资料'}
          </button>
        </div>

        <div className="mx-auto mt-4 flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-[10px] text-muted-foreground/65">
          <span>混合检索</span><span className="h-1 w-1 rounded-full bg-white/15" />
          <span>实时进度</span><span className="h-1 w-1 rounded-full bg-white/15" />
          <span>引用可追溯</span><span className="h-1 w-1 rounded-full bg-white/15" />
          <span>流式回答</span>
        </div>
      </div>
    </div>
  );
}
