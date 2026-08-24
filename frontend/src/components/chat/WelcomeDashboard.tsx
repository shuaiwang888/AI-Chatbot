import {
  ArrowUpRight,
  BookOpenCheck,
  FileSearch,
  GitCompareArrows,
  ListChecks,
  ShieldCheck,
  Sparkles,
  WandSparkles,
} from 'lucide-react';

import { useDocuments, summarizeDocs } from '@/hooks/useDocuments';
import { useChatStore } from '@/stores/chatStore';
import { useUIStore } from '@/stores/uiStore';
import { cn } from '@/lib/utils';
import { getAccessToken } from '@/lib/auth';

const STARTERS = [
  {
    icon: FileSearch,
    eyebrow: '快速定位',
    title: '从文档中找答案',
    description: '定位关键事实，并给出可回溯的引用位置。',
    prompt: '请从知识库中查找最重要的结论，并标注每条结论的引用来源。',
    tone: 'from-blue-500/20 to-cyan-400/5 text-blue-300',
  },
  {
    icon: GitCompareArrows,
    eyebrow: '交叉分析',
    title: '对比多份材料',
    description: '提炼共同点、差异与潜在冲突。',
    prompt: '请对比知识库中的相关文档，用表格列出共同点、差异和可能的冲突。',
    tone: 'from-violet-500/20 to-fuchsia-400/5 text-violet-300',
  },
  {
    icon: ListChecks,
    eyebrow: '结构化提炼',
    title: '生成摘要与行动项',
    description: '把长内容变成重点、决策和下一步。',
    prompt: '请总结相关文档，分别列出核心结论、风险、待确认事项和可执行的下一步。',
    tone: 'from-emerald-500/20 to-teal-400/5 text-emerald-300',
  },
  {
    icon: ShieldCheck,
    eyebrow: '审阅检查',
    title: '发现风险与遗漏',
    description: '从材料中识别矛盾、假设和缺口。',
    prompt: '请审阅知识库中的相关内容，找出风险、矛盾、未经证实的假设和信息缺口。',
    tone: 'from-amber-500/20 to-orange-400/5 text-amber-300',
  },
] as const;

export function WelcomeDashboard() {
  const setDraft = useChatStore((s) => s.setDraft);
  const setSidebar = useUIStore((s) => s.setSidebar);
  const docsQ = useDocuments();
  const summary = summarizeDocs(docsQ.data?.documents);
  const hasAccessToken = Boolean(getAccessToken());
  const serviceState = !hasAccessToken
    ? { label: '请先设置访问令牌', dot: 'bg-amber-400', ping: false }
    : docsQ.isLoading
      ? { label: '正在检查知识服务', dot: 'bg-amber-400', ping: false }
      : docsQ.isError
      ? {
          label: '知识服务暂不可用',
          dot: 'bg-amber-400',
          ping: false,
        }
      : { label: 'Knowledge Agent 已准备就绪', dot: 'bg-emerald-400', ping: true };

  const choosePrompt = (prompt: string) => {
    setDraft(prompt);
    requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('[data-chat-input]')?.focus());
  };

  return (
    <div className="welcome-scroll h-full overflow-y-auto scrollbar-thin">
      <div className="mx-auto flex min-h-full w-full max-w-5xl flex-col justify-center px-5 py-10 md:px-10 lg:py-12">
        <div className="mb-8 max-w-3xl">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1.5 text-xs font-medium text-blue-200 shadow-[0_0_30px_rgba(59,130,246,.12)]">
            <span className="relative flex h-2 w-2">
              {serviceState.ping && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />}
              <span className={cn('relative inline-flex h-2 w-2 rounded-full', serviceState.dot)} />
            </span>
            {serviceState.label}
          </div>

          <div className="flex items-start gap-4">
            <div className="hidden h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-gradient-to-br from-primary to-violet-500 text-white shadow-[0_12px_40px_rgba(59,130,246,.3)] sm:flex">
              <WandSparkles className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-balance text-3xl font-semibold tracking-tight text-white md:text-4xl">
                今天想从知识库中了解什么？
              </h2>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground md:text-base">
                我会先检索你的资料，再组织答案并附上引用。你可以直接提问，也可以从下面的任务开始。
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {STARTERS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.title}
                type="button"
                onClick={() => choosePrompt(item.prompt)}
                className="group relative overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.035] p-4 text-left transition duration-300 hover:-translate-y-1 hover:border-primary/30 hover:bg-white/[0.065] hover:shadow-[0_18px_45px_rgba(4,8,28,.35)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                <div className={cn('mb-5 flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br', item.tone)}>
                  <Icon className="h-5 w-5" />
                </div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{item.eyebrow}</p>
                <h3 className="mt-1.5 text-sm font-semibold text-foreground">{item.title}</h3>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">{item.description}</p>
                <ArrowUpRight className="absolute right-4 top-4 h-4 w-4 text-muted-foreground/40 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-primary" />
              </button>
            );
          })}
        </div>

        <div className="mt-5 flex flex-col gap-3 rounded-2xl border border-white/[0.07] bg-black/10 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <BookOpenCheck className="h-4 w-4" />
            </div>
            <div>
              <p className="text-xs font-medium text-foreground">
                {!hasAccessToken
                  ? '输入访问令牌后读取知识库'
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
            className="inline-flex items-center gap-1.5 self-start rounded-lg px-2 py-1.5 text-xs font-medium text-primary transition hover:bg-primary/10 sm:self-auto"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {!hasAccessToken || docsQ.isError ? '查看连接状态' : summary.total > 0 ? '管理知识库' : '上传第一份资料'}
          </button>
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-[10px] text-muted-foreground/70">
          <span>语义检索</span><span className="h-1 w-1 rounded-full bg-border" />
          <span>多轮推理</span><span className="h-1 w-1 rounded-full bg-border" />
          <span>引用可追溯</span><span className="h-1 w-1 rounded-full bg-border" />
          <span>流式回答</span>
        </div>
      </div>
    </div>
  );
}
