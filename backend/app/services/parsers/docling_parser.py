"""Docling parser - 主力.

特性:
- 结构感知 (reading order / headings)
- 跨页表合并 (TableFormer)
- 内置 OCR (PaddleOCR 支持中英)
- DOCX / PPTX / 图片 / HTML 全支持

Docling API 在 2.x 期间变动较多, 本实现基于 2.30+ 兼容.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from app.config import settings
from app.services.parsers.base_parser import BaseParser, PageContent, ParsedDocument

logger = logging.getLogger(__name__)


class DoclingParser(BaseParser):
    name = "docling"

    def supported_extensions(self) -> set[str]:
        return {".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg", ".tiff", ".html", ".xlsx"}

    async def parse(self, file_path: Path) -> ParsedDocument:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._parse_sync, file_path)

    def _parse_sync(self, file_path: Path) -> ParsedDocument:
        """实际解析. CPU 密集, 在线程池跑."""
        # Force CPU device for Docling to prevent MPS NotImplementedError on Intel Mac
        try:
            import docling.utils.accelerator_utils
            docling.utils.accelerator_utils.decide_device = lambda *args, **kwargs: "cpu"
        except ImportError:
            pass

        # 延迟 import, 避免启动期未装 docling 时崩溃
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        started = time.time()
        logger.info("Docling parsing: %s", file_path.name)

        from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
        opts = PdfPipelineOptions()
        opts.do_ocr = settings.parser_enable_ocr
        opts.do_table_structure = settings.parser_table_structure
        opts.images_scale = 2.0
        opts.artifacts_path = str(settings.data_dir / "docling_models")
        opts.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU)

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=opts),
            }
        )

        try:
            result = converter.convert(str(file_path))
        except Exception as e:  # noqa: BLE001
            logger.exception("Docling parse failed: %s", e)
            raise

        doc = result.document

        # 全文 markdown
        markdown = doc.export_to_markdown()

        # 页面级 (Docling 用 iterate_items / pages 属性, 视版本略有差异)
        pages: list[PageContent] = []
        try:
            page_count = len(doc.pages) if hasattr(doc, "pages") else 0
            for idx in range(page_count):
                page = doc.pages[idx]
                # 提取该页文本 (Docling 2.x 没有现成 API, 用 page-level export 近似)
                page_md = ""
                if hasattr(page, "export_to_markdown"):
                    try:
                        page_md = page.export_to_markdown()
                    except Exception:  # noqa: BLE001
                        page_md = ""
                pages.append(PageContent(
                    page_no=idx + 1,
                    text=page_md,
                    headings=[],  # Docling 不直接给页级 headings, 留空
                ))
        except Exception as e:  # noqa: BLE001
            logger.warning("Docling page extraction partial: %s", e)

        # 表格 (简化提取)
        tables: list[dict] = []
        try:
            for t in (doc.tables or []):
                tables.append({
                    "html": t.export_to_html() if hasattr(t, "export_to_html") else "",
                    "caption": getattr(t, "caption", None),
                })
        except Exception:  # noqa: BLE001
            pass

        elapsed_ms = int((time.time() - started) * 1000)
        logger.info("Docling done: %s pages, %s tables, %dms", len(pages), len(tables), elapsed_ms)

        return ParsedDocument(
            markdown=markdown,
            pages=pages,
            tables=tables,
            images=[],
            meta={
                "parser": self.name,
                "page_count": len(pages),
                "elapsed_ms": elapsed_ms,
            },
        )
