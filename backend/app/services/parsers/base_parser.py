"""文档解析抽象 + 数据结构.

支持的输入: PDF, DOCX, PNG/JPG (含扫描件).

设计:
- BaseParser 抽象 parse() -> ParsedDocument
- ParsedDocument 同时携带 markdown 全文 + 页面级结构 (含表格 / 图片)
- 各具体 parser (Docling / Marker / MinerU) 实现同一接口, 可热替换
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PageContent:
    """单页内容. 至少要有 text, 可选带 tables / images."""

    page_no: int
    text: str
    tables: list[dict] = field(default_factory=list)   # {html, bbox, rows}
    images: list[dict] = field(default_factory=list)   # {bbox, caption, b64_thumb}
    headings: list[str] = field(default_factory=list)  # 当前页的标题


@dataclass
class ParsedDocument:
    """解析后的统一文档结构.

    业务侧只用 markdown (全文) + pages (带页码引用) 两个核心字段.
    """

    markdown: str                                    # 全文 markdown (LLM 友好)
    pages: list[PageContent] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)  # 全部表格 (跨页表已合并)
    images: list[dict] = field(default_factory=list)
    meta: dict = field(default_factory=dict)          # page_count, parser, elapsed_ms, ...


class BaseParser(abc.ABC):
    """文档解析器抽象基类."""

    name: str = "abstract"

    @abc.abstractmethod
    def supported_extensions(self) -> set[str]:
        """形如 {'.pdf', '.docx'}."""

    @abc.abstractmethod
    async def parse(self, file_path: Path) -> ParsedDocument:
        """同步 IO + 异步 wrapper. 重 CPU 解析可放线程池."""

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.supported_extensions()
