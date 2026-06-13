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
        # ⚠️ 不要设 artifacts_path: 设了但目录为空会被 Docling 拒绝 (报 "is not valid")
        # 不设时, Docling 通过 huggingface_hub 走 HF_HOME 自动下载 + 缓存
        # 我们的 Dockerfile 设了 HF_HOME=/data/.cache/huggingface (持久卷), 所以重启后还在
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


def _prewarm_docling_models() -> None:
    """预下载 Docling 需要的模型 (layout/heron, tableformer, paddleocr 等, 共 ~2GB).

    在 Space 启动 lifespan 阶段跑一次, 避免首次上传时下载超时或下载失败.
    模型会缓存到 settings.hf_cache_dir, 后续启动跳过.
    """
    import logging
    from pathlib import Path
    from app.config import settings

    logger_local = logging.getLogger(__name__)
    logger_local.info("Docling model prewarm: pulling layout/table/ocr models...")

    from huggingface_hub import snapshot_download

    # Docling 模型都在 ds4sd 命名空间下
    repos = [
        "ds4sd/docling-models",  # 主模型集 (layout, tableformer)
    ]

    cache_dir = Path(settings.hf_cache_dir) if hasattr(settings, "hf_cache_dir") else None
    if cache_dir is None:
        from app.core.paths import data_dir
        cache_dir = data_dir() / ".cache" / "huggingface"

    for repo in repos:
        try:
            p = snapshot_download(
                repo_id=repo,
                cache_dir=str(cache_dir),
                # 避免下载所有 variants, 只下必需的
                allow_patterns=[
                    "*.json",
                    "*.txt",
                    "*.safetensors",
                    "tokenizer*",
                ],
            )
            logger_local.info("Docling model %s cached at %s", repo, p)
        except Exception as e:  # noqa: BLE001
            logger_local.warning("Docling model prewarm %s failed: %s", repo, e)

    # PaddleOCR 模型 (Docling 内置 OCR 用). 单独下载.
    try:
        from paddleocr import PaddleOCR  # type: ignore
        # 实例化会触发模型下载到 ~/.paddleocr
        PaddleOCR(use_angle_cls=False, lang="ch", show_log=False)
        logger_local.info("PaddleOCR (ch) model cached")
    except Exception as e:  # noqa: BLE001
        # PaddleOCR 可能没装 (e.g. arm64 平台), 不阻塞
        logger_local.warning("PaddleOCR prewarm skipped: %s", e)

    logger_local.info("Docling model prewarm done")

