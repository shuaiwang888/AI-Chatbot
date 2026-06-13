"""BGE-M3 嵌入服务.

BGE-M3 单模型产出三路表示 (FlagEmbedding 库):
- dense_vecs: 1024 维稠密向量 (语义)
- lexical_weights: SPLADE 风格稀疏权重 (精确词命中)
- colbert_vecs: 多向量 (每 token 一个 1024 维) (late interaction)

设计:
- 全局单例 BGEM3FlagModel (首次调用懒加载)
- encode() 异步, 内部走线程池 (CPU 密集)
- encode_query() 给单 query 用, 自动加 instruction prefix
- 三路可独立开关 (ColBERT 占内存, 16GB RAM 下建议可降级)
"""
from __future__ import annotations

import asyncio
import logging
import threading
from functools import lru_cache
from typing import Any

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


# BGE-M3 query instruction (BAAI 官方推荐)
_QUERY_INSTRUCTION = (
    "Represent this sentence for searching relevant passages: "
)


@lru_cache(maxsize=1)
def get_bge_model():
    """懒加载 BGE-M3. CPU 上 fp16 自动降级为 fp32."""
    from FlagEmbedding import BGEM3FlagModel

    # CPU 上强制 fp32, 因为 FlagEmbedding 1.x 在 CPU + fp16 有数值问题
    use_fp16 = settings.use_fp16 and settings.embedding_device in ("cuda", "mps")
    logger.info(
        "Loading BGE-M3: model=%s device=%s fp16=%s",
        settings.embedding_model,
        settings.embedding_device,
        use_fp16,
    )
    model = BGEM3FlagModel(
        settings.embedding_model,
        use_fp16=use_fp16,
        device=settings.embedding_device,
        cache_dir=str(settings.hf_cache_dir),
    )
    # 立刻跑一次空 encode, 强制完成 meta→cpu 的 device 转移.
    # 否则 FlagEmbedding.encode 内部的 self.model.to(device) 会撞到 meta tensor 报
    # "Cannot copy out of meta tensor; no data!" (在 PyTorch 2.2 + transformers 4.57 组合下)
    try:
        with __import__("torch").no_grad():
            model.encode(
                ["warmup"],
                return_dense=True,
                return_sparse=settings.enable_colbert or True,
                return_colbert_vecs=settings.enable_colbert,
                batch_size=1,
                max_length=8,
            )
        logger.info("BGE-M3 meta→cpu device transfer done")
    except Exception as e:  # noqa: BLE001
        logger.warning("BGE-M3 warmup encode failed (will retry on first real call): %s", e)
    return model


def warm_up() -> None:
    """在 lifespan 启动时调用, 避免首次请求时的 30s 加载延迟."""
    try:
        get_bge_model()
        logger.info("BGE-M3 warmed up")
    except Exception as e:  # noqa: BLE001
        logger.warning("BGE-M3 warm-up failed: %s (will retry on first request)", e)


def _normalize_dense(vecs: np.ndarray) -> np.ndarray:
    """L2 归一化, 余弦相似度 = 点积."""
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return vecs / norms


class BGEM3Embedder:
    """BGE-M3 嵌入器, 同时产出 dense / sparse / colbert."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    async def encode(self, texts: list[str]) -> dict[str, Any]:
        """编码多个文本.

        Returns:
            {
              "dense": np.ndarray,    # (N, 1024) 已 L2 归一化
              "sparse": list[dict],   # [{"token_id": weight, ...}, ...]
              "colbert": list[np.ndarray],  # [N x (T_i, 1024)]
            }
        """
        if not texts:
            return {"dense": np.zeros((0, 1024), dtype=np.float32), "sparse": [], "colbert": []}
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._encode_sync, texts)

    def _encode_sync(self, texts: list[str]) -> dict[str, Any]:
        model = get_bge_model()
        with self._lock:
            out = model.encode(
                texts,
                return_dense=True,
                return_sparse=settings.enable_colbert or True,  # sparse 一直开
                return_colbert_vecs=settings.enable_colbert,
                batch_size=12,
                max_length=512,
            )

        dense = np.asarray(out["dense_vecs"], dtype=np.float32)
        dense = _normalize_dense(dense)

        # sparse: FlagEmbedding 返回 dict[token_str -> weight]; 标准化为 {token_id: weight}
        sparse_list: list[dict[int, float]] = []
        for sw in out.get("lexical_weights", []):
            # sw: {token_str: weight} or {token_id(int): weight}
            # FlagEmbedding 1.2+ 返回 token_id (int)
            sparse_list.append({int(tid): float(w) for tid, w in sw.items()})

        colbert_list: list[np.ndarray] = []
        if settings.enable_colbert and "colbert_vecs" in out:
            for v in out["colbert_vecs"]:
                colbert_list.append(np.asarray(v, dtype=np.float32))

        return {"dense": dense, "sparse": sparse_list, "colbert": colbert_list}

    async def encode_query(self, query: str) -> dict[str, Any]:
        """编码单条 query. 加 instruction prefix."""
        return await self.encode([_QUERY_INSTRUCTION + query])

    # ========== 便利方法 ==========
    async def encode_dense_only(self, texts: list[str]) -> np.ndarray:
        """只要 dense, 跳过 sparse/colbert (节省内存/时间)."""
        if not texts:
            return np.zeros((0, 1024), dtype=np.float32)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._encode_dense_only_sync, texts)

    def _encode_dense_only_sync(self, texts: list[str]) -> np.ndarray:
        model = get_bge_model()
        with self._lock:
            out = model.encode(
                [_QUERY_INSTRUCTION + t for t in texts],
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
                batch_size=12,
                max_length=512,
            )
        dense = np.asarray(out["dense_vecs"], dtype=np.float32)
        return _normalize_dense(dense)


# 全局单例
_embedder: BGEM3Embedder | None = None


def get_embedder() -> BGEM3Embedder:
    global _embedder
    if _embedder is None:
        _embedder = BGEM3Embedder()
    return _embedder
