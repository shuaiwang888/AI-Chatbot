/**
 * 上传面板 (拖拽 + 按钮).
 */
import { useCallback, useRef, useState } from 'react';
import { Upload, FileUp, Loader2, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useUploadDocument } from '@/hooks/useDocuments';
import { cn, formatBytes } from '@/lib/utils';
import { getAccessToken } from '@/lib/auth';

export function UploadPanel() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [lastResult, setLastResult] = useState<{
    filename: string;
    status: 'ready' | 'duplicate' | 'failed';
    chunks?: number;
    error?: string;
  } | null>(null);
  const upload = useUploadDocument();
  const hasAccessToken = Boolean(getAccessToken());

  const handleFile = useCallback(
    async (file: File) => {
      // 客户端预检
      const ALLOWED = ['.pdf', '.docx', '.pptx', '.xlsx', '.png', '.jpg', '.jpeg', '.tiff', '.html', '.md', '.markdown'];
      const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();
      if (!ALLOWED.includes(ext)) {
        setLastResult({ filename: file.name, status: 'failed', error: `不支持的格式: ${ext}` });
        return;
      }
      if (file.size > 50 * 1024 * 1024) {
        setLastResult({ filename: file.name, status: 'failed', error: '超过 50MB 上限' });
        return;
      }

      try {
        const result = await upload.mutateAsync(file);
        setLastResult({
          filename: file.name,
          status: result.status,
          chunks: result.chunk_count,
        });
      } catch (e: any) {
        setLastResult({
          filename: file.name,
          status: 'failed',
          error: e?.message || '上传失败',
        });
      }
    },
    [upload],
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);
      if (!hasAccessToken) return;
      const files = Array.from(e.dataTransfer.files);
      files.forEach(handleFile);
    },
    [handleFile, hasAccessToken],
  );

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={cn(
          'spring-surface rounded-[1.1rem] border border-dashed p-4 text-center',
          dragOver ? 'scale-[1.015] border-primary/70 bg-primary/10 shadow-[0_12px_35px_rgba(10,132,255,.12)]' : 'border-white/10 bg-black/15 hover:border-white/20 hover:bg-black/20',
        )}
      >
        <div className={cn('mx-auto mb-2.5 flex h-10 w-10 items-center justify-center rounded-[.85rem] text-primary transition-colors', dragOver ? 'bg-primary text-white' : 'bg-primary/10')}>
          <Upload className="h-5 w-5" />
        </div>
        <p className="text-xs font-semibold tracking-[-0.01em] text-foreground">
          将资料拖到这里
        </p>
        <p className="mt-1 text-[10px] leading-4 text-muted-foreground">松开后自动解析并建立索引</p>
        <Button
          size="sm"
          variant="outline"
          className="mt-3 rounded-[.72rem]"
          onClick={() => inputRef.current?.click()}
          disabled={!hasAccessToken || upload.isPending}
        >
          {upload.isPending ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          ) : (
            <FileUp className="mr-1.5 h-3.5 w-3.5" />
          )}
          浏览文件
        </Button>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".pdf,.docx,.pptx,.xlsx,.png,.jpg,.jpeg,.tiff,.html,.md,.markdown"
          multiple
          disabled={!hasAccessToken}
          onChange={(e) => {
            const files = Array.from(e.target.files || []);
            files.forEach(handleFile);
            e.target.value = '';
          }}
        />
        <p className="mt-2 text-[10px] text-muted-foreground">
          {hasAccessToken ? 'PDF / Word / PPT / Excel / Markdown / 图片, ≤ 50MB' : '请先通过右上角钥匙按钮设置访问令牌'}
        </p>
      </div>

      {lastResult && (
        <div
          className={cn(
            'flex items-center gap-1.5 rounded-[.8rem] border px-2.5 py-2 text-[11px]',
            lastResult.status === 'failed'
              ? 'border-destructive/15 bg-destructive/10 text-destructive'
              : 'border-emerald-400/10 bg-emerald-400/[0.06] text-emerald-300',
          )}
        >
          {lastResult.status === 'failed' ? (
            <span>❌ {lastResult.filename}: {lastResult.error}</span>
          ) : lastResult.status === 'duplicate' ? (
            <>
              <CheckCircle2 className="h-3 w-3" />
              <span>{lastResult.filename} 已存在, 已复用 (chunks={lastResult.chunks})</span>
            </>
          ) : (
            <>
              <CheckCircle2 className="h-3 w-3" />
              <span>{lastResult.filename} 摄入完成 ({lastResult.chunks} chunks)</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
