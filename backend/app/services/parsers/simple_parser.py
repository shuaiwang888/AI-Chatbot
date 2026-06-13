"""SimpleParser - 零依赖的 PDF 文本提取 fallback.

适用场景:
- Docling 失败 / 模型下载卡住 / Docling 不可用
- 文本型 PDF (非扫描件) - 用 pypdf 直接抽文字

特性:
- 零 ML 依赖 (只有 pypdf)
- 快速, 内存友好
- 拿不到结构 (无表格识别), 只做 "能分页 + 拿文本"

这是 marker-pdf 的替代方案, 因为 marker-pdf 1.10+ 与 pydantic-ai 的 anthropic 版本冲突.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from app.services.parsers.base_parser import BaseParser, PageContent, ParsedDocument

logger = logging.getLogger(__name__)


class SimpleParser(BaseParser):
    """pypdf-based 轻量级 PDF 解析器. 兜底中的兜底."""

    name = "simple"

    def supported_extensions(self) -> set[str]:
        # 只支持 PDF; 其它格式 (docx/png) 还是走 Docling
        return {".pdf"}

    async def parse(self, file_path: Path) -> ParsedDocument:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._parse_sync, file_path)

    def _parse_sync(self, file_path: Path) -> ParsedDocument:
        started = time.time()
        logger.info("SimpleParser (pypdf) parsing: %s", file_path.name)

        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise RuntimeError(
                "pypdf not installed. Add 'pypdf>=4.0' to requirements.txt"
            ) from e

        reader = PdfReader(str(file_path))
        pages: list[PageContent] = []
        page_texts: list[str] = []

        for idx, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception as e:  # noqa: BLE001
                logger.warning("pypdf extract_text failed on page %d: %s", idx, e)
                text = ""
            pages.append(PageContent(
                page_no=idx + 1,
                text=text,
                tables=[],  # simple parser 不识别表格
                images=[],
            ))
            page_texts.append(text)

        # 全文 markdown (无结构, 直接拼)
        markdown = "\n\n".join(page_texts)

        elapsed_ms = int((time.time() - started) * 1000)
        logger.info(
            "SimpleParser done: %s pages, %dms (using pypdf)",
            len(pages), elapsed_ms,
        )

        return ParsedDocument(
            markdown=markdown,
            pages=pages,
            tables=[],
            images=[],
            meta={
                "parser": self.name,
                "page_count": len(pages),
                "elapsed_ms": elapsed_ms,
                "backend": "pypdf",
            },
        )
