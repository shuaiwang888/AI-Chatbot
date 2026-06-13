"""BGE-reranker-v2-m3 精排服务.

输入: query + list[RetrievalHit]
输出: 同长度 list, 按相关性分数重排, 返回 top_n
"""
from __future__ import annotations

import asyncio
import logging
import threading
from functools import lru_cache

from app.config import settings
from app.services.vector_store import RetrievalHit

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_reranker():
    """懒加载 FlagReranker. CPU 上 fp16 强制 fp32."""
    from FlagEmbedding import FlagReranker

    use_fp16 = settings.use_fp16 and settings.embedding_device in ("cuda", "mps")
    logger.info(
        "Loading reranker: model=%s device=%s fp16=%s",
        settings.reranker_model, settings.embedding_device, use_fp16,
    )
    model = FlagReranker(
        settings.reranker_model,
        use_fp16=use_fp16,
        device=settings.embedding_device,
        cache_dir=str(settings.hf_cache_dir),
    )
    # 预热一次 compute_score, 强制 meta→cpu device 转移 (避免后续 "Cannot copy out of meta tensor")
    try:
        with __import__("torch").no_grad():
            model.compute_score([["warmup query", "warmup passage"]], normalize=True)
        logger.info("Reranker meta→cpu device transfer done")
    except Exception as e:  # noqa: BLE001
        logger.warning("Reranker warmup failed: %s", e)
    return model


def warm_up() -> None:
    try:
        get_reranker()
        logger.info("Reranker warmed up")
    except Exception as e:  # noqa: BLE001
        logger.warning("Reranker warm-up failed: %s", e)


class RerankerService:
    """封装 Reranker, 异步 + 限流 + 截断长文本."""

    _sem = None  # 全局信号量, 避免并发打爆 CPU

    def __init__(self, max_concurrency: int = 2) -> None:
        if RerankerService._sem is None:
            RerankerService._sem = asyncio.Semaphore(max_concurrency)

    async def rerank(
        self,
        query: str,
        hits: list[RetrievalHit],
        top_n: int | None = None,
        max_length: int = 512,
    ) -> list[RetrievalHit]:
        """对 hits 按 query 相关性重排, 返回 top_n. 原顺序保留在 original_rank."""
        if not hits:
            return []
        top_n = top_n or settings.rerank_top_n

        # 截断过长的 text (BGE-reranker max 512 token)
        pairs = [[query, (h.text or "")[: max_length * 2]] for h in hits]

        loop = asyncio.get_running_loop()
        scores = await loop.run_in_executor(None, self._rerank_sync, pairs)

        # 记 original_rank + 新分数
        for h, s in zip(hits, scores):
            h.original_rank = hits.index(h)
            h.rerank_score = float(s)

        # 按 rerank_score 降序
        reranked = sorted(hits, key=lambda h: h.rerank_score, reverse=True)
        return reranked[:top_n]

    def _rerank_sync(self, pairs: list[list[str]]) -> list[float]:
        model = get_reranker()
        # FlagReranker.compute_score 直接吃 list[list[str]]
        scores = model.compute_score(pairs, normalize=True)
        # 单条输入时返回 float, 统一为 list
        if isinstance(scores, (int, float)):
            scores = [float(scores)]
        return [float(s) for s in scores]


# 进程内单例
_reranker: RerankerService | None = None


def get_reranker_service() -> RerankerService:
    global _reranker
    if _reranker is None:
        _reranker = RerankerService()
    return _reranker
