"""Parser 工厂: 智能路由 + 降级链.

智能路由逻辑:
1. 查 settings.parser_primary (默认 docling)
2. 主 parser 失败 -> 降级到 settings.parser_fallback
3. 全部失败 -> 抛 IngestionFailedError
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from app.core.errors import IngestionFailedError
from app.services.parsers.base_parser import BaseParser, ParsedDocument

logger = logging.getLogger(__name__)


# 延迟注册: 实际 import 在 _build_parser 内
_REGISTRY: dict[str, type[BaseParser]] = {}


def _register_default() -> None:
    """懒加载各 parser. 失败的 (未装) 仅记 warning, 不抛."""
    if _REGISTRY:
        return
    try:
        from app.services.parsers.docling_parser import DoclingParser
        _REGISTRY["docling"] = DoclingParser
    except ImportError as e:
        logger.warning("docling not installed: %s", e)
    try:
        from app.services.parsers.marker_parser import MarkerParser
        _REGISTRY["marker"] = MarkerParser
    except ImportError as e:
        logger.warning("marker-pdf not installed: %s", e)
    # mineru / vlm 留 hook (按需装)


def _build_parser(name: str) -> BaseParser:
    _register_default()
    cls = _REGISTRY.get(name)
    if cls is None:
        raise IngestionFailedError(
            f"Parser '{name}' is not installed. pip install docling / marker-pdf.",
            code="parser_unavailable",
        )
    return cls()


def get_parser(name: str | None = None) -> BaseParser:
    """获取单个 parser 实例 (按名字)."""
    return _build_parser(name or settings.parser_primary)


def get_parser_chain() -> list[BaseParser]:
    """按 settings 配置返回 [primary, fallback] 链."""
    chain: list[BaseParser] = []
    for name in (settings.parser_primary, settings.parser_fallback):
        if name and name not in {p.name for p in chain}:
            try:
                chain.append(_build_parser(name))
            except IngestionFailedError:
                # 跳过未装的, 继续
                continue
    return chain


async def parse_with_fallback(file_path: Path) -> ParsedDocument:
    """按链逐个尝试, 全部失败抛 IngestionFailedError."""
    chain = get_parser_chain()
    if not chain:
        raise IngestionFailedError(
            "No parser available. Install at least one of: docling, marker-pdf.",
            code="no_parser_available",
        )

    # 选能处理该扩展名的 parser
    candidates = [p for p in chain if p.can_handle(file_path)]
    if not candidates:
        raise IngestionFailedError(
            f"No parser in chain supports {file_path.suffix}",
            code="unsupported_format",
            detail={"suffix": file_path.suffix, "chain": [p.name for p in chain]},
        )

    last_err: Exception | None = None
    last_traceback: str | None = None
    for parser in candidates:
        try:
            return await parser.parse(file_path)
        except Exception as e:  # noqa: BLE001
            import traceback
            tb = traceback.format_exc()
            logger.warning("Parser %s failed for %s: %s\n%s", parser.name, file_path.name, e, tb)
            last_err = e
            last_traceback = tb

    # 把最后一个 parser 的具体异常信息暴露给前端, 方便诊断
    err_msg = f"All parsers failed for {file_path.name}"
    if last_err:
        err_msg += f" (last: {type(last_err).__name__}: {last_err})"
    raise IngestionFailedError(
        err_msg,
        code="all_parsers_failed",
        detail={
            "chain": [p.name for p in candidates],
            "last_error_type": type(last_err).__name__ if last_err else None,
            "last_error_msg": str(last_err)[:500] if last_err else None,
            "last_traceback": (last_traceback or "")[-1500:],  # 末 1.5KB, 防爆
        },
    ) from last_err


__all__ = [
    "BaseParser",
    "ParsedDocument",
    "PageContent",
    "get_parser",
    "get_parser_chain",
    "parse_with_fallback",
]
