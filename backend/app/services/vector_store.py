"""向量存储 + 混合检索.

ChromaDB v1.0 (Rust core) multi-vector 集合:
- 同一 collection 同时存 dense (1024d) + ColBERT (变长多向量)
- sparse 走旁路 BM25-style (用 BGE-M3 产出的 lexical weights 反序列化)

混合检索 (三路 RRF):
- dense 走 ChromaDB HNSW
- sparse 走反序列化 + dot product
- colbert 走 late interaction max-sim
- 三路结果 RRF 融合
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.config import settings
from app.core.paths import chroma_dir, sqlite_dir
from app.models import db

logger = logging.getLogger(__name__)


# ========== 检索结果 ==========
@dataclass
class RetrievalHit:
    chunk_id: str
    doc_id: str
    text: str
    score: float
    page_no: int | None
    heading: str | None
    context_prefix: str | None
    meta: dict[str, Any]
    # 用于 CRAG evaluate
    sparse_score: float = 0.0
    dense_score: float = 0.0
    colbert_score: float = 0.0
    # rerank 后填充
    rerank_score: float = 0.0
    original_rank: int = 0


# ========== Sparse 旁路索引 (SQLite) ==========
class SparseSidecar:
    """存 sparse lexical weights, 用 sqlite 反查 + 打分.

    表 schema: chunk_sparse(chunk_id, weights_json)
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self) -> None:
        with db.transaction() as _:
            db.get_conn().execute(
                """
                CREATE TABLE IF NOT EXISTS chunk_sparse (
                    chunk_id     TEXT PRIMARY KEY,
                    weights_json TEXT NOT NULL
                )
                """
            )

    def upsert_bulk(self, items: list[tuple[str, dict[int, float]]]) -> None:
        if not items:
            return
        with self._lock, db.transaction():
            db.get_conn().executemany(
                "INSERT OR REPLACE INTO chunk_sparse (chunk_id, weights_json) VALUES (?, ?)",
                [(cid, json.dumps({str(k): v for k, v in w.items()})) for cid, w in items],
            )

    def upsert_colbert(self, items: list[tuple[str, np.ndarray]]) -> None:
        """ColBERT 多向量太占地方, 暂存为 .npy 文件, 路径记到 chunk_sparse 旁表."""
        if not items:
            return
        from app.core.paths import data_dir

        colbert_dir = data_dir() / "colbert"
        colbert_dir.mkdir(parents=True, exist_ok=True)
        with self._lock, db.transaction():
            for cid, vec in items:
                path = colbert_dir / f"{cid}.npy"
                np.save(path, vec)
                db.get_conn().execute(
                    "INSERT OR REPLACE INTO chunk_sparse (chunk_id, weights_json) VALUES (?, ?)",
                    (cid, json.dumps({"colbert_path": str(path.relative_to(data_dir()))})),
                )

    def get_sparse(self, chunk_id: str) -> dict[int, float] | None:
        row = db.get_conn().execute(
            "SELECT weights_json FROM chunk_sparse WHERE chunk_id = ? AND weights_json NOT LIKE '%colbert_path%'",
            (chunk_id,),
        ).fetchone()
        if not row:
            return None
        try:
            d = json.loads(row["weights_json"])
            return {int(k): float(v) for k, v in d.items()}
        except (json.JSONDecodeError, ValueError):
            return None

    def get_colbert_path(self, chunk_id: str) -> str | None:
        row = db.get_conn().execute(
            "SELECT weights_json FROM chunk_sparse WHERE chunk_id = ? AND weights_json LIKE '%colbert_path%'",
            (chunk_id,),
        ).fetchone()
        if not row:
            return None
        try:
            d = json.loads(row["weights_json"])
            return d.get("colbert_path")
        except json.JSONDecodeError:
            return None

    def score_sparse(
        self, query_weights: dict[int, float], candidate_ids: list[str]
    ) -> dict[str, float]:
        """对 candidate 计算 sparse 分数 (q·d 内积). 0 表示完全无重叠."""
        out: dict[str, float] = {}
        if not query_weights:
            return out
        for cid in candidate_ids:
            doc_w = self.get_sparse(cid)
            if not doc_w:
                out[cid] = 0.0
                continue
            # 公共 token 上的内积
            s = 0.0
            for tid, qw in query_weights.items():
                dw = doc_w.get(tid)
                if dw is not None:
                    s += qw * dw
            out[cid] = s
        return out

    def delete_by_doc(self, doc_id: str) -> int:
        # 通过 doc chunks 关联删除
        rows = db.get_conn().execute(
            "SELECT id FROM chunks WHERE doc_id = ?", (doc_id,)
        ).fetchall()
        if not rows:
            return 0
        ids = [r["id"] for r in rows]
        cur = db.get_conn().execute(
            f"DELETE FROM chunk_sparse WHERE chunk_id IN ({','.join('?' * len(ids))})",
            ids,
        )
        return cur.rowcount


# ========== ChromaDB 客户端 ==========
_chroma_client = None
_chroma_collection = None
_sparse_sidecar: SparseSidecar | None = None


def get_chroma():
    global _chroma_client, _chroma_collection, _sparse_sidecar
    if _chroma_client is None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        chroma_dir()
        _chroma_client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
        )
        # ChromaDB v1.0+ 支持 multi-vector; 不指定 embedding_function (我们自己 embed)
        _chroma_collection = _chroma_client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )
        # 旁路 sparse 索引
        _sparse_sidecar = SparseSidecar(settings.sqlite_db_path)
        logger.info(
            "ChromaDB ready: dir=%s collection=%s",
            settings.chroma_dir, settings.chroma_collection,
        )
    return _chroma_client, _chroma_collection, _sparse_sidecar


# ========== Upsert ==========
def upsert_chunks(
    *,
    ids: list[str],
    embeddings: np.ndarray,             # (N, 1024) dense
    documents: list[str],               # 文本
    metadatas: list[dict[str, Any]],
    sparse_weights: list[dict[int, float]] | None = None,
    colbert_vecs: list[np.ndarray] | None = None,
) -> None:
    """写入 ChromaDB + 旁路 sparse/colbert."""
    if not ids:
        return
    _, coll, sidecar = get_chroma()
    coll.upsert(
        ids=ids,
        embeddings=embeddings.tolist(),
        documents=documents,
        metadatas=metadatas,
    )
    if sparse_weights:
        sidecar.upsert_bulk(list(zip(ids, sparse_weights)))
    if colbert_vecs and settings.enable_colbert:
        sidecar.upsert_colbert(list(zip(ids, colbert_vecs)))


# ========== Query ==========
def query_dense(
    query_emb: np.ndarray, k: int = 20, where: dict | None = None
) -> list[tuple[str, float, dict]]:
    _, coll, _ = get_chroma()
    res = coll.query(
        query_embeddings=[query_emb.tolist()],
        n_results=k,
        where=where,
        include=["metadatas", "distances", "documents"],
    )
    if not res["ids"]:
        return []
    out: list[tuple[str, float, dict]] = []
    for i, cid in enumerate(res["ids"][0]):
        # cosine distance -> 转为 similarity
        dist = res["distances"][0][i] if res["distances"] else 0.0
        sim = 1.0 - dist
        out.append((cid, sim, {
            "text": res["documents"][0][i] if res["documents"] else "",
            "meta": res["metadatas"][0][i] if res["metadatas"] else {},
        }))
    return out


def rrf_fuse(
    *ranked_lists: list[tuple[str, float, dict]],
    k: int = 60,
) -> list[tuple[str, float, dict]]:
    """Reciprocal Rank Fusion.

    每个 list 是 [(id, score, payload), ...], 排名越靠前 (index 0) 权重越高.
    score = sum 1/(k + rank_i)
    """
    scores: dict[str, float] = {}
    payloads: dict[str, dict] = {}
    for ranked in ranked_lists:
        for rank, (cid, _score, payload) in enumerate(ranked):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            if cid not in payloads:
                payloads[cid] = payload
            elif payload and payload.get("text"):
                payloads[cid] = payload
    out = sorted(scores.items(), key=lambda x: -x[1])
    return [(cid, sc, payloads[cid]) for cid, sc in out]


def hybrid_query(
    *,
    query_emb: np.ndarray,
    query_sparse: dict[int, float] | None = None,
    query_colbert_emb: np.ndarray | None = None,
    k: int = 20,
    where: dict | None = None,
    over_retrieve: int = 50,
) -> list[RetrievalHit]:
    """三路混合检索 + RRF.

    Args:
        query_emb: dense 向量 (1024d)
        query_sparse: 稀疏权重
        query_colbert_emb: (T, 1024) 多向量
        k: 最终返回 top-k
        over_retrieve: 每路多取一些再融合
    """
    started = time.time()

    # 路 1: dense (ChromaDB HNSW)
    dense = query_dense(query_emb, k=over_retrieve, where=where)

    # 路 2: sparse (旁路 + 反查)
    sparse: list[tuple[str, float, dict]] = []
    if query_sparse:
        _, _, sidecar = get_chroma()
        cand_ids = [cid for cid, _, _ in dense]  # dense top-N 作为候选, 避免全表
        sparse_scores = sidecar.score_sparse(query_sparse, cand_ids)
        # 按 sparse score 排序
        sparse = sorted(
            [
                (cid, sparse_scores.get(cid, 0.0), {"text": "", "meta": {}})
                for cid in cand_ids
            ],
            key=lambda x: -x[1],
        )

    # 路 3: colbert (late interaction)
    colbert_ranked: list[tuple[str, float, dict]] = []
    if settings.enable_colbert and query_colbert_emb is not None and len(query_colbert_emb) > 0:
        from app.core.paths import data_dir
        # 只对 dense top-N 计算 colbert
        _, _, sidecar = get_chroma()
        cand_ids = [cid for cid, _, _ in dense[:30]]
        scored: list[tuple[str, float]] = []
        for cid in cand_ids:
            rel_path = sidecar.get_colbert_path(cid)
            if not rel_path:
                continue
            full = data_dir() / rel_path
            if not full.exists():
                continue
            try:
                doc_vec = np.load(full)
            except Exception:  # noqa: BLE001
                continue
            # max-sim
            sims = doc_vec @ query_colbert_emb.T  # (T_doc, T_q)
            if sims.size == 0:
                continue
            max_per_doc = sims.max(axis=0).mean()  # mean of per-query-token max
            scored.append((cid, float(max_per_doc)))
        colbert_ranked = sorted(scored, key=lambda x: -x[1])
        colbert_ranked = [(cid, s, {"text": "", "meta": {}}) for cid, s in colbert_ranked]

    # RRF 融合
    fused = rrf_fuse(dense, sparse, colbert_ranked, k=60)[:k]

    # 构造 RetrievalHit
    hits: list[RetrievalHit] = []
    for cid, rrf_score, payload in fused:
        meta = payload.get("meta", {})
        hits.append(RetrievalHit(
            chunk_id=cid,
            doc_id=meta.get("doc_id", ""),
            text=payload.get("text", ""),
            score=rrf_score,
            page_no=meta.get("page_no"),
            heading=meta.get("heading"),
            context_prefix=meta.get("context_prefix"),
            meta=meta,
        ))

    logger.debug("hybrid_query returned %d hits in %dms", len(hits), int((time.time() - started) * 1000))
    return hits


# ========== Delete ==========
def delete_by_doc(doc_id: str) -> int:
    """从 ChromaDB + sparse 旁路一并删除."""
    _, coll, sidecar = get_chroma()
    # 先列 id (ChromaDB v1.0 用 where 过滤删除)
    try:
        coll.delete(where={"doc_id": doc_id})
    except Exception as e:  # noqa: BLE001
        logger.warning("ChromaDB delete by where failed (%s), falling back to per-chunk", e)
        # fallback: 列出来删
        rows = db.get_conn().execute("SELECT id FROM chunks WHERE doc_id = ?", (doc_id,)).fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            coll.delete(ids=ids)
    n = sidecar.delete_by_doc(doc_id)
    return n
