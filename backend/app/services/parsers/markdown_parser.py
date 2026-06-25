"""Markdown 文档解析器.

设计:
- Markdown 文件本身就是 LLM 友好的纯文本 + 标记, 不需要 OCR / 表格识别 /
  版面分析等重型处理 — 直接读全文塞进 parsed.markdown 即可.
- 后续 chunking._split_by_headings 按 H1/H2/H3 拆 section, 完美适配.
- 支持扩展名: .md, .markdown
- 无任何外部依赖 (标准库即可).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from app.services.parsers.base_parser import BaseParser, ParsedDocument

logger = logging.getLogger(__name__)

# 单文件上限: Markdown 文档通常不会特别大, 5MB 足够 (≈ 150 万中文字).
# 上传入口的 50MB 限制已经先兜住, 这里再保险一道防 OOM.
_MAX_MD_BYTES = 5 * 1024 * 1024


class MarkdownParser(BaseParser):
    """零依赖 Markdown 解析器. 适用于 .md / .markdown 文件."""

    name = "markdown"

    def supported_extensions(self) -> set[str]:
        return {".md", ".markdown"}

    async def parse(self, file_path: Path) -> ParsedDocument:
        started = time.time()
        # 1. 大小保险
        size = file_path.stat().st_size
        if size > _MAX_MD_BYTES:
            raise ValueError(
                f"Markdown file too large: {size} bytes > {_MAX_MD_BYTES} limit"
            )

        # 2. 读全文. errors='replace' 防个别非法字节导致整个文件读失败.
        text = file_path.read_text(encoding="utf-8", errors="replace")
        # 去除首尾空白, 但保留正文的换行结构.
        text = text.strip()
        if not text:
            logger.warning("Markdown file is empty: %s", file_path.name)

        elapsed_ms = int((time.time() - started) * 1000)
        meta = {
            "parser": self.name,
            "elapsed_ms": elapsed_ms,
            "char_count": len(text),
            "line_count": text.count("\n") + 1 if text else 0,
            "page_count": 1,  # MD 是单 "页" 概念, 给个 1 兜底
        }
        logger.info(
            "MarkdownParser: %s -> %d chars, %d lines, %dms",
            file_path.name, meta["char_count"], meta["line_count"], elapsed_ms,
        )
        # 整篇视为单页, 让下游 page 引用逻辑不报错.
        from app.services.parsers.base_parser import PageContent
        pages = [PageContent(page_no=1, text=text, headings=[])] if text else []
        return ParsedDocument(markdown=text, pages=pages, meta=meta)
