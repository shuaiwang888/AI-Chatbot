/**
 * 引用片段渲染. 文本可能含 markdown 公式/列表/代码块, 用 ReactMarkdown 渲染.
 * 但相对简洁 — 不需要 link target=_blank 等.
 */
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';

export function CitationSnippet({ text }: { text: string }) {
  if (!text) {
    return <div className="text-xs text-muted-foreground italic">(无片段)</div>;
  }
  return (
    <div className="prose-chat text-xs text-foreground/85">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
