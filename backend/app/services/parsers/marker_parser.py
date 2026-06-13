"""Marker parser - 兜底 (Docling 失败时启用).

特性:
- PDF -> Markdown 转换, 速度快
- 内置 surya-ocr, 支持 90+ 语言
- 不擅长复杂表格 / 跨页表 (不如 Docling), 但胜在稳定
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from app.services.parsers.base_parser import BaseParser, ParsedDocument

logger = logging.getLogger(__name__)


class MarkerParser(BaseParser):
    name = "marker"

    def supported_extensions(self) -> set[str]:
        # Marker 强项是 PDF; 其它类型建议直接 Docling
        return {".pdf"}

    async def parse(self, file_path: Path) -> ParsedDocument:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._parse_sync, file_path)

    def _parse_sync(self, file_path: Path) -> ParsedDocument:
        # Marker 1.x 推荐用 marker's Python API 而非 CLI subprocess
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered

        started = time.time()
        logger.info("Marker parsing: %s", file_path.name)

        converter = PdfConverter(artifact_dict=create_model_dict())
        rendered = converter(str(file_path))
        markdown, _, _ = text_from_rendered(rendered)

        # Marker 不直接给 page-level 拆分, 走全文 markdown
        elapsed_ms = int((time.time() - started) * 1000)
        logger.info("Marker done: %dms", elapsed_ms)

        # 尝试从 rendered 拿 metadata
        meta = rendered.metadata if hasattr(rendered, "metadata") else {}
        page_count = meta.get("page_stats", {}).get("total_pages") if isinstance(meta, dict) else None

        return ParsedDocument(
            markdown=markdown,
            pages=[],  # Marker 不分页
            tables=[],
            images=[],
            meta={
                "parser": self.name,
                "page_count": page_count,
                "elapsed_ms": elapsed_ms,
            },
        )
