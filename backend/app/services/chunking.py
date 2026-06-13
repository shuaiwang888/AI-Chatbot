"""层次化分块器.

策略:
1. 优先按 markdown 标题拆分 (H1/H2/H3)
2. 每个 section 内:
   - 段间按 token 预算合并 (parent: 1500-2000t)
   - 段内进一步切分 (child: 400-512t)
3. 可选: 语义分块 (按 sentence 相似度二次切)
4. 可选: Anthropic-style 上下文预置 (LLM 给每个 chunk 加 context prefix)

输出:
- parents: 大块, 给 LLM 喂上下文用
- children: 小块, 给向量检索用
- 每个 child 带 parent_id, page_no, heading 字段
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field

from app.config import settings
from app.llm.base import LLMMessage
from app.services.parsers.base_parser import ParsedDocument

logger = logging.getLogger(__name__)


# 标题正则 (markdown)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Chunk:
    """分块结果 (child or parent)."""

    id: str
    doc_id: str
    parent_id: str | None
    chunk_index: int
    text: str
    token_count: int
    page_no: int | None = None
    heading: str | None = None
    context_prefix: str | None = None
    created_at: float = field(default_factory=time.time)


def _approx_token_count(s: str) -> int:
    """粗估 token 数. 用 chars/2 当近似, 避免引 tiktoken."""
    if not s:
        return 0
    # 中英文混合: CJK 算 1.5 token/char, 其它算 0.5
    cjk = sum(1 for c in s if "一" <= c <= "鿿")
    other = len(s) - cjk
    return int(cjk * 1.5 + other * 0.5)


def _split_by_headings(markdown: str) -> list[tuple[str, str]]:
    """按 markdown 标题拆分. 返回 [(heading, body), ...].

    heading 为 None 表示标题前的引言段.
    """
    matches = list(_HEADING_RE.finditer(markdown))
    if not matches:
        return [(None, markdown)]

    chunks: list[tuple[str, str]] = []
    # 引言段
    pre = markdown[: matches[0].start()].strip()
    if pre:
        chunks.append((None, pre))

    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        body = markdown[start:end].strip()
        if body:
            chunks.append((heading, body))
    return chunks


def _sliding_window(text: str, target: int, overlap: int) -> list[str]:
    """按 token 估值的滑动窗口切分.

    简化版: 按段落切, 累积到 target token 就 flush, 与上一段重叠 overlap.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []

    pieces: list[str] = []
    buf: list[str] = []
    buf_tokens = 0
    for p in paragraphs:
        pt = _approx_token_count(p)
        # 单段超过 target, 硬切
        if pt > target:
            if buf:
                pieces.append("\n\n".join(buf))
                buf, buf_tokens = [], 0
            # 字符级切
            step = max(int(target * 2), 200)  # target * 2 chars ≈ target tokens
            for i in range(0, len(p), step):
                pieces.append(p[i : i + step])
            continue
        if buf_tokens + pt > target and buf:
            pieces.append("\n\n".join(buf))
            # overlap: 保留最后一段
            if overlap > 0 and buf:
                last = buf[-1]
                last_t = _approx_token_count(last)
                if last_t <= overlap:
                    buf = [last]
                    buf_tokens = last_t
                else:
                    buf, buf_tokens = [], 0
            else:
                buf, buf_tokens = [], 0
        buf.append(p)
        buf_tokens += pt
    if buf:
        pieces.append("\n\n".join(buf))
    return pieces


def _split_by_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


@dataclass
class ChunkingResult:
    parents: list[Chunk]
    children: list[Chunk]


def chunk_document(parsed: ParsedDocument, doc_id: str) -> ChunkingResult:
    """对 ParsedDocument 做层次化分块.

    步骤:
    1. 按 markdown 标题分 section
    2. 每个 section 用滑动窗口切 parent (2000t, overlap 200)
    3. 每个 parent 内用滑动窗口切 child (512t, overlap 64)
    4. 按 page 编号 (按 parent 在 markdown 中的字符位置近似)
    """
    md = parsed.markdown
    sections = _split_by_headings(md)
    page_text = parsed.pages  # 可能为空 (Marker)

    parents: list[Chunk] = []
    children: list[Chunk] = []
    chunk_idx = 0

    for heading, body in sections:
        # 先切 parent
        for ptext in _sliding_window(body, target=2000, overlap=200):
            pid = uuid.uuid4().hex
            ptoks = _approx_token_count(ptext)
            # 估算 page_no
            page_no = _estimate_page_no(ptext, parsed) if page_text else None
            parent = Chunk(
                id=pid,
                doc_id=doc_id,
                parent_id=None,
                chunk_index=chunk_idx,
                text=ptext,
                token_count=ptoks,
                page_no=page_no,
                heading=heading,
            )
            parents.append(parent)
            chunk_idx += 1

            # 切 child
            for ctext in _sliding_window(ptext, target=settings.chunk_size, overlap=settings.chunk_overlap):
                cid = uuid.uuid4().hex
                ctoks = _approx_token_count(ctext)
                child = Chunk(
                    id=cid,
                    doc_id=doc_id,
                    parent_id=pid,
                    chunk_index=chunk_idx,
                    text=ctext,
                    token_count=ctoks,
                    page_no=page_no,
                    heading=heading,
                )
                children.append(child)
                chunk_idx += 1

    return ChunkingResult(parents=parents, children=children)


def _estimate_page_no(snippet: str, parsed: ParsedDocument) -> int | None:
    """在 parsed.pages 里找包含 snippet 片段的页. 简单字符串包含."""
    if not parsed.pages:
        return None
    # 取 snippet 前 50 字符作锚
    anchor = snippet[:50].strip()
    if not anchor:
        return None
    for p in parsed.pages:
        if anchor in p.text:
            return p.page_no
    return None


# ========== 上下文预置 (Anthropic-style) ==========
_CONTEXT_PROMPT_TEMPLATE = (
    "你是一名文档分块上下文标注助手。给定一段来自文档的 chunk (用 <chunk> 包裹) "
    "以及文档标题, 请用 1-2 句中文描述该 chunk 在整篇文档中的上下文, 帮助后续检索时理解其含义。\n\n"
    "要求:\n"
    "- 简洁, 不超过 80 字\n"
    "- 包含: 这是什么类型的内容 (定义 / 例子 / 数据 / 结论 / 步骤等), 在文档哪个章节\n"
    "- 不要重复 chunk 原内容\n"
    "- 仅输出描述本身, 不要加任何前缀\n\n"
    "文档标题: {doc_title}\n"
    "所属章节: {heading}\n"
    "<chunk>\n{chunk}\n</chunk>\n\n"
    "上下文描述:"
)


async def contextualize_chunks(
    chunks: list[Chunk],
    *,
    doc_title: str = "未知文档",
    max_concurrency: int = 4,
) -> list[Chunk]:
    """为每个 chunk 生成 context_prefix. Anthropic-style.

    优化:
    - 并发限流 (max_concurrency), 不爆 LLM 限流
    - 失败容错: 单条失败不中断, 留 prefix=None
    """
    if not settings.contextual_retrieval or not chunks:
        return chunks

    try:
        from app.llm.factory import get_llm
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM not available for contextual retrieval: %s", e)
        return chunks

    sem = asyncio.Semaphore(max_concurrency)

    async def _one(c: Chunk) -> None:
        if c.context_prefix:
            return
        async with sem:
            try:
                llm = get_llm()
                prompt = _CONTEXT_PROMPT_TEMPLATE.format(
                    doc_title=doc_title,
                    heading=c.heading or "无",
                    chunk=c.text[:1200],  # 限长, 防 LLM token 爆
                )
                resp = await llm.chat(
                    messages=[
                        LLMMessage(role="system", content="你是上下文标注助手。"),
                        LLMMessage(role="user", content=prompt),
                    ],
                    temperature=0.2,
                    max_tokens=160,
                )
                prefix = (resp.content or "").strip().strip('"').strip("'")
                if len(prefix) > 200:
                    prefix = prefix[:200]
                c.context_prefix = prefix or None
            except Exception as e:  # noqa: BLE001
                logger.warning("Contextual retrieval failed for chunk %s: %s", c.id[:8], e)

    await asyncio.gather(*[_one(c) for c in chunks])
    n_ok = sum(1 for c in chunks if c.context_prefix)
    logger.info("Contextualized %d/%d chunks", n_ok, len(chunks))
    return chunks


def chunk_to_embed_text(c: Chunk) -> str:
    """向量化用的文本: context_prefix + heading + body."""
    parts: list[str] = []
    if c.context_prefix:
        parts.append(f"[Context: {c.context_prefix}]")
    if c.heading:
        parts.append(f"[Section: {c.heading}]")
    parts.append(c.text)
    return "\n".join(parts)
