"""文档摄入编排器.

完整流水线:
1. 保存上传文件到 /data/uploads/{doc_id}/{filename}
2. 计算 SHA256, 查 SQLite 是否有同 sha 的 ready 文档
   - 有 -> 直接返回 {doc_id, status: "duplicate"}
3. 解析 (智能路由: primary -> fallback)
4. 分块 (层次化 + 可选语义 + 可选上下文预置)
5. 向量化 (BGE-M3 三路)
6. 入库:
   - ChromaDB: dense + (colbert)
   - 旁路: sparse (BM25-style)
   - SQLite: document 行 + chunk 行
7. 调度 persist.push 异步同步
8. 返回 {doc_id, chunk_count, status: "ready"}
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.config import settings
from app.core.errors import IngestionFailedError
from app.core.paths import upload_dir
from app.models import db
from app.models.schemas import IngestResult
from app.services.chunking import (
    Chunk,
    chunk_document,
    chunk_to_embed_text,
    contextualize_chunks,
)
from app.services.embedding import get_embedder
from app.services.parsers import parse_with_fallback
from app.services.parsers.base_parser import ParsedDocument
from app.services.persist import schedule_push
from app.services.vector_store import upsert_chunks

logger = logging.getLogger(__name__)


# 单并发摄入队列 (避免大 PDF 同时跑爆 RAM)
_ingest_lock = asyncio.Lock()


@dataclass
class _IngestContext:
    doc_id: str
    file_path: Path
    filename: str
    mime: str
    size: int
    sha256: str
    started: float


async def _save_upload(*, content: bytes, filename: str) -> tuple[Path, str, int, str]:
    """保存上传字节到 /data/uploads/{doc_id}/{filename}, 返回 (path, mime, size, sha256)."""
    doc_id = uuid.uuid4().hex
    dest_dir = upload_dir() / doc_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    # 防路径穿越
    safe_name = Path(filename).name or "upload"
    dest = dest_dir / safe_name
    dest.write_bytes(content)

    # MIME 简单嗅探
    mime = _sniff_mime(safe_name, content[:2048])
    sha = hashlib.sha256(content).hexdigest()
    return dest, mime, len(content), sha


def _sniff_mime(filename: str, head: bytes) -> str:
    ext = Path(filename).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".html": "text/html",
    }.get(ext, "application/octet-stream")


async def ingest_bytes(
    *,
    content: bytes,
    filename: str,
) -> IngestResult:
    """公开入口. 处理上传的原始字节."""
    async with _ingest_lock:
        return await _ingest_locked(content, filename)


async def _ingest_locked(content: bytes, filename: str) -> IngestResult:
    started = time.time()
    # 1. 保存
    file_path, mime, size, sha = await _save_upload(content=content, filename=filename)
    doc_id = file_path.parent.name  # 用 upload 子目录名当 doc_id (一致)

    logger.info("Ingest start: %s (%d bytes, sha=%s)", filename, size, sha[:12])

    # 2. SHA256 幂等检查
    existing = db.doc_find_by_sha256(sha)
    if existing is not None:
        logger.info("Duplicate by sha256: existing doc_id=%s", existing["id"])
        # 删除刚写入的副本, 复用旧 doc
        try:
            file_path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
        return IngestResult(doc_id=existing["id"], chunk_count=existing.get("chunk_count", 0), status="duplicate")

    # 3. 写入 SQLite (状态 uploading -> parsing)
    db.doc_insert({
        "id": doc_id,
        "filename": Path(filename).name,
        "mime": mime,
        "size": size,
        "sha256": sha,
        "status": "parsing",
        "progress": 0,
        "progress_label": "开始解析...",
        "parser": settings.parser_primary,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "semantic_chunking": settings.semantic_chunking,
        "contextual_retrieval": settings.contextual_retrieval,
        "created_at": started,
        "updated_at": started,
        "meta": {},
    })

    try:
        # 4. 解析
        db.doc_update_status(doc_id, "parsing", progress=10, progress_label="解析 PDF/Word 结构...")
        parsed = await parse_with_fallback(file_path)
        page_count = parsed.meta.get("page_count")
        db.doc_update_status(doc_id, "parsing", page_count=page_count, progress=30, progress_label="解析完成, 准备分块")

        # 5. 分块
        chunking = chunk_document(parsed, doc_id=doc_id)
        logger.info(
            "Chunked: %d parents, %d children for %s",
            len(chunking.parents), len(chunking.children), filename,
        )
        db.doc_update_status(
            doc_id, "parsing",
            progress=45,
            progress_label=f"分块 {len(chunking.children)} 个 chunk",
        )

        # 6. 上下文预置 (可选, 走 LLM, 慢但提升召回)
        if settings.contextual_retrieval and chunking.children:
            db.doc_update_status(
                doc_id, "embedding",
                progress=50,
                progress_label="上下文预标注 (走 LLM)...",
            )
            await contextualize_chunks(
                chunking.children, doc_title=Path(filename).name, max_concurrency=4
            )

        # 7. 向量化
        db.doc_update_status(doc_id, "embedding", progress=55, progress_label="向量化中...")
        embedder = get_embedder()
        embed_texts = [chunk_to_embed_text(c) for c in chunking.children]
        if not embed_texts:
            logger.warning("No chunks to embed for %s", filename)
            db.doc_update_status(doc_id, "ready", chunk_count=0, progress=100, progress_label="完成 (空文档)")
            return IngestResult(doc_id=doc_id, chunk_count=0, status="ready")

        # batch 编码
        BATCH = 32
        all_dense: list[np.ndarray] = []
        all_sparse: list[dict[int, float]] = []
        all_colbert: list[np.ndarray] = []
        n_total = len(embed_texts)
        for i in range(0, n_total, BATCH):
            batch = embed_texts[i : i + BATCH]
            out = await embedder.encode(batch)
            all_dense.append(out["dense"])
            all_sparse.extend(out.get("sparse", []))
            all_colbert.extend(out.get("colbert", []))
            done = min(i + BATCH, n_total)
            # 55% -> 95%
            pct = 55 + int((done / n_total) * 40)
            db.doc_update_status(
                doc_id, "embedding",
                progress=pct,
                progress_label=f"向量化 {done}/{n_total}",
            )
            logger.info(
                "Embedded %d/%d chunks", done, n_total
            )

        dense_arr = np.vstack(all_dense) if all_dense else np.zeros((0, 1024), dtype=np.float32)

        # 8. 入库 ChromaDB + sparse 旁路
        ids = [c.id for c in chunking.children]
        documents = [c.text for c in chunking.children]
        metadatas = [
            {
                "doc_id": c.doc_id,
                "parent_id": c.parent_id or "",
                "chunk_index": c.chunk_index,
                "page_no": c.page_no or 0,
                "heading": c.heading or "",
                "context_prefix": c.context_prefix or "",
            }
            for c in chunking.children
        ]
        upsert_chunks(
            ids=ids,
            embeddings=dense_arr,
            documents=documents,
            metadatas=metadatas,
            sparse_weights=all_sparse or None,
            colbert_vecs=all_colbert or None,
        )

        # 9. 写入 SQLite chunks
        db.chunk_insert_bulk([
            {
                "id": c.id,
                "doc_id": c.doc_id,
                "parent_id": c.parent_id,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "token_count": c.token_count,
                "page_no": c.page_no,
                "heading": c.heading,
                "context_prefix": c.context_prefix,
                "created_at": c.created_at,
            }
            for c in chunking.children
        ])

        # 10. 文档就绪
        elapsed_ms = int((time.time() - started) * 1000)
        db.doc_update_status(
            doc_id, "ready",
            chunk_count=len(chunking.children),
            page_count=page_count,
            progress=100,
            progress_label="就绪",
        )
        logger.info(
            "Ingest done: %s doc_id=%s chunks=%d %dms",
            filename, doc_id, len(chunking.children), elapsed_ms,
        )

        # 11. 调度持久化推送
        await schedule_push()

        return IngestResult(
            doc_id=doc_id,
            chunk_count=len(chunking.children),
            status="ready",
        )

    except Exception as e:  # noqa: BLE001
        logger.exception("Ingest failed for %s", filename)
        try:
            db.doc_update_status(doc_id, "failed", error=str(e)[:500])
        except Exception:  # noqa: BLE001
            pass
        raise IngestionFailedError(
            f"Ingest failed: {e}", code="ingest_failed", detail={"doc_id": doc_id}
        ) from e


async def delete_document(doc_id: str) -> bool:
    """完整删除: ChromaDB + 旁路 sparse + SQLite + uploads/."""
    # 先查, 拿文件路径
    doc = db.doc_get(doc_id)
    if doc is None:
        return False

    # 从 ChromaDB / sparse 旁路删
    try:
        from app.services.vector_store import delete_by_doc
        delete_by_doc(doc_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("ChromaDB delete failed for %s: %s", doc_id, e)

    # SQLite chunks + document
    db.chunk_delete_by_doc(doc_id)
    db.doc_delete(doc_id)

    # 删上传原文件
    if doc.get("sha256"):
        # doc_id 即子目录名
        up_dir = upload_dir() / doc_id
        if up_dir.exists():
            import shutil
            shutil.rmtree(up_dir, ignore_errors=True)

    await schedule_push()
    return True


def list_documents(limit: int = 100) -> list[dict[str, Any]]:
    return db.doc_list(limit=limit)


def get_document(doc_id: str) -> dict[str, Any] | None:
    return db.doc_get(doc_id)
