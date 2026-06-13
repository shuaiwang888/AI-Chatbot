"""LLM 响应缓存 (内存 LRU).

为什么需要:
- 个人使用场景下, 同一问题反复问很常见
- 命中时直接跳过 LLM 调用 + 流式回放 token
- 节省 API 费用 + 缩短延迟

设计:
- key = sha256( (query + top_doc_ids + temperature) )  -- 只缓存"标准问答", 不缓存工具调用
- value = 完整回答内容 + 引用 + 工具调用结果
- LRU 容量可配 (默认 200)
- 进程内, 重启清空 (避免引入 Redis)
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from cachetools import LRUCache

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CachedAnswer:
    content: str
    citations: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    tokens: list[str]  # 预切好的 token 序列, 流式回放


_cache: LRUCache | None = None
_hits = 0
_misses = 0


def _make_key(query: str, top_doc_ids: list[str], temperature: float) -> str:
    """缓存 key. 包含 query + 命中文档 id + 温度, 避免不同上下文错命中."""
    payload = f"{query.strip()}|{','.join(sorted(top_doc_ids))}|{temperature:.2f}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_cache() -> LRUCache:
    global _cache
    if _cache is None:
        size = settings.llm_cache_size if settings.llm_cache_enabled else 0
        _cache = LRUCache(maxsize=size)
        logger.info("LLM cache initialized: enabled=%s size=%d", settings.llm_cache_enabled, size)
    return _cache


def lookup(query: str, top_doc_ids: list[str], temperature: float) -> CachedAnswer | None:
    if not settings.llm_cache_enabled:
        return None
    key = _make_key(query, top_doc_ids, temperature)
    hit = get_cache().get(key)
    global _hits, _misses
    if hit is not None:
        _hits += 1
        logger.debug("LLM cache HIT key=%s", key[:12])
    else:
        _misses += 1
    return hit


def store(query: str, top_doc_ids: list[str], temperature: float, answer: CachedAnswer) -> None:
    if not settings.llm_cache_enabled:
        return
    key = _make_key(query, top_doc_ids, temperature)
    get_cache()[key] = answer
    logger.debug("LLM cache STORE key=%s tokens=%d", key[:12], len(answer.tokens))


def stats() -> dict[str, Any]:
    return {
        "enabled": settings.llm_cache_enabled,
        "size": len(get_cache()),
        "max_size": get_cache().maxsize,
        "hits": _hits,
        "misses": _misses,
        "hit_rate": (_hits / max(_hits + _misses, 1)),
    }


def clear() -> None:
    global _cache, _hits, _misses
    _cache = None
    _hits = 0
    _misses = 0
    logger.info("LLM cache cleared")
