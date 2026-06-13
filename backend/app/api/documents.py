"""文档管理 API. 阶段 2: 完整 upload / list / delete / get / chunks."""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.core.errors import DocumentNotFoundError
from app.models import db
from app.models.schemas import DocumentChunk, IngestResult
from app.services.ingestion import (
    delete_document,
    get_document,
    ingest_bytes,
    list_documents,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
async def list_docs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    docs = list_documents(limit=limit)
    return {
        "documents": docs[offset : offset + limit],
        "total": len(docs),
    }


@router.get("/{doc_id}")
async def get_doc(doc_id: str) -> dict:
    doc = get_document(doc_id)
    if doc is None:
        raise DocumentNotFoundError(f"Document {doc_id} not found", code="doc_not_found")
    return doc


@router.get("/{doc_id}/chunks")
async def list_chunks(
    doc_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """获取文档的 chunks 列表, 用于前端预览拆分结果.

    返回顺序: 按 chunk_index ASC. 包含 text / token_count / page_no / heading / context_prefix.
    """
    doc = get_document(doc_id)
    if doc is None:
        raise DocumentNotFoundError(f"Document {doc_id} not found", code="doc_not_found")
    rows = db.chunk_get_by_doc(doc_id, limit=limit + offset)
    # 截取 offset
    rows = rows[offset : offset + limit]
    return {
        "doc_id": doc_id,
        "chunks": [DocumentChunk(**r).model_dump() for r in rows],
        "total": doc.get("chunk_count", len(rows)),
        "returned": len(rows),
    }


@router.post("/upload", response_model=IngestResult)
async def upload(file: UploadFile = File(...)) -> IngestResult:
    """上传并摄入文档. 支持 PDF / DOCX / 图片.

    流程: 读字节 -> 摄入编排器 (内部 SHA256 查重 + 解析 + 分块 + 向量化 + 入库)
    """
    if file.filename is None:
        raise HTTPException(status_code=400, detail="filename missing")

    # 限制大小 (50MB; HF Space free 16GB RAM 下够用)
    MAX_BYTES = 50 * 1024 * 1024
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (> {MAX_BYTES // 1024 // 1024}MB). "
                   "Consider chunked upload via S3/R2 (TODO 阶段 5).",
        )

    try:
        result = await ingest_bytes(content=content, filename=file.filename)
    except Exception as e:  # noqa: BLE001
        # 已记录到 SQLite; 返回 502
        logger.exception("Upload failed")
        raise HTTPException(status_code=502, detail=f"Ingest failed: {e}") from e

    return result


@router.delete("/{doc_id}")
async def delete_doc(doc_id: str) -> dict:
    ok = await delete_document(doc_id)
    if not ok:
        raise DocumentNotFoundError(f"Document {doc_id} not found", code="doc_not_found")
    return {"doc_id": doc_id, "deleted": True}
