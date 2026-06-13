/**
 * 上传面板 (拖拽 + 按钮).
 */
import { useCallback, useRef, useState } from 'react';
import { Upload, FileUp, Loader2, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useUploadDocument } from '@/hooks/useDocuments';
import { cn, formatBytes } from '@/lib/utils';

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

  const handleFile = useCallback(
    async (file: File) => {
      // 客户端预检
      const ALLOWED = ['.pdf', '.docx', '.pptx', '.xlsx', '.png', '.jpg', '.jpeg', '.tiff', '.html'];
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
      const files = Array.from(e.dataTransfer.files);
      files.forEach(handleFile);
    },
    [handleFile],
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
          'rounded-lg border-2 border-dashed p-4 text-center transition-colors',
          dragOver ? 'border-primary bg-primary/5' : 'border-muted',
        )}
      >
        <Upload className="mx-auto mb-1.5 h-6 w-6 text-muted-foreground" />
        <p className="text-xs text-muted-foreground">
          拖拽文件到这里, 或
        </p>
        <Button
          size="sm"
          variant="outline"
          className="mt-2"
          onClick={() => inputRef.current?.click()}
          disabled={upload.isPending}
        >
          {upload.isPending ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          ) : (
            <FileUp className="mr-1.5 h-3.5 w-3.5" />
          )}
          选择文件
        </Button>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".pdf,.docx,.pptx,.xlsx,.png,.jpg,.jpeg,.tiff,.html"
          multiple
          onChange={(e) => {
            const files = Array.from(e.target.files || []);
            files.forEach(handleFile);
            e.target.value = '';
          }}
        />
        <p className="mt-2 text-[10px] text-muted-foreground">
          PDF / Word / PPT / Excel / 图片, ≤ 50MB
        </p>
      </div>

      {lastResult && (
        <div
          className={cn(
            'flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs',
            lastResult.status === 'failed'
              ? 'bg-destructive/10 text-destructive'
              : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300',
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
