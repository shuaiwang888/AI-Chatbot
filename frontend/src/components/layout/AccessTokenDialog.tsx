import { useEffect, useState, type FormEvent } from 'react';
import { Eye, EyeOff, KeyRound, LockKeyhole, ShieldCheck, Trash2 } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { clearAccessToken, getAccessToken, setAccessToken } from '@/lib/auth';

interface AccessTokenDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AccessTokenDialog({ open, onOpenChange }: AccessTokenDialogProps) {
  const [value, setValue] = useState('');
  const [visible, setVisible] = useState(false);
  const hasCurrentToken = Boolean(getAccessToken());

  useEffect(() => {
    if (!open) return;
    setValue(getAccessToken() || '');
    setVisible(false);
  }, [open]);

  const save = (event: FormEvent) => {
    event.preventDefault();
    const token = value.trim();
    if (!token) return;
    setAccessToken(token);
    onOpenChange(false);
    window.location.reload();
  };

  const clear = () => {
    clearAccessToken();
    onOpenChange(false);
    window.location.reload();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[calc(100%_-_2rem)] max-w-md overflow-hidden p-0">
        <div className="px-6 pb-5 pt-7 sm:px-7">
          <DialogHeader className="text-left">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-[1rem] bg-primary text-white shadow-[inset_0_1px_0_rgba(255,255,255,.25),0_12px_30px_rgba(10,132,255,.25)]">
              <LockKeyhole className="h-5 w-5" />
            </div>
            <DialogTitle className="text-xl font-semibold tracking-[-0.025em]">连接私人知识库</DialogTitle>
            <DialogDescription className="max-w-sm pt-1 text-[13px] leading-5">
              输入部署管理员提供的访问令牌。令牌仅保存在当前浏览器会话中，关闭浏览器后自动清除。
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={save} className="mt-6 space-y-4">
            <label className="block">
              <span className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">访问令牌</span>
              <div className="relative">
                <KeyRound className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  autoFocus
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                  type={visible ? 'text' : 'password'}
                  autoComplete="off"
                  spellCheck={false}
                  placeholder="输入访问令牌"
                  className="apple-focus h-12 w-full rounded-[.9rem] border border-white/10 bg-black/20 pl-10 pr-11 text-sm outline-none placeholder:text-muted-foreground/55"
                />
                <button
                  type="button"
                  onClick={() => setVisible((current) => !current)}
                  className="apple-focus absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground hover:bg-white/[0.07] hover:text-foreground"
                  aria-label={visible ? '隐藏令牌' : '显示令牌'}
                >
                  {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </label>

            <div className="flex items-start gap-2.5 rounded-[.9rem] border border-emerald-400/10 bg-emerald-400/[0.055] px-3.5 py-3 text-[11px] leading-5 text-muted-foreground">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
              <span>令牌不会写入仓库、日志或公开的前端构建文件。</span>
            </div>

            <DialogFooter className="flex-row items-center justify-between gap-2 pt-1">
              {hasCurrentToken ? (
                <Button type="button" variant="ghost" onClick={clear} className="mr-auto text-destructive hover:bg-destructive/10 hover:text-destructive">
                  <Trash2 className="h-4 w-4" /> 清除
                </Button>
              ) : <span />}
              <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>取消</Button>
              <Button type="submit" disabled={!value.trim()}>连接</Button>
            </DialogFooter>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  );
}
