"""Phase 2 smoke test — 文档摄入端到端验证.

用法:
    cd backend
    python tests/unit/smoke_phase2.py

前置:
    pip install -r requirements.txt
    pip install reportlab       # 用它生成测试 PDF
    复制 .env.example 为 .env, 填入 MINIMAX_API_KEY (无 key 时 contextual retrieval 自动跳过)

测试覆盖:
    1. 单元: chunk_document 对样本文本分块
    2. 单元: SHA256 幂等性
    3. 集成: 端到端 ingest_bytes(PDF) -> Chroma 检索
    4. 集成: duplicate sha256 不重复摄入
    5. 集成: delete 文档后从 Chroma 消失
    6. API: /documents/upload + /documents + /documents/{id} + DELETE
"""
from __future__ import annotations

import os
os.environ["TESTING"] = "true"

import asyncio
import io
import sys
import tempfile
import time
from pathlib import Path


def section(title: str) -> None:
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def check(label: str, ok: bool, detail: str = "") -> bool:
    icon = "✅" if ok else "❌"
    print(f"  {icon} {label}" + (f" — {detail}" if detail else ""))
    return ok


def make_sample_pdf() -> bytes:
    """生成一份多页 PDF 用作测试."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)

        # Page 1
        c.setFont("Helvetica-Bold", 18)
        c.drawString(72, 770, "AI Chatbot Test Document")
        c.setFont("Helvetica", 11)
        c.drawString(72, 740, "This is a multi-page test PDF for ingestion pipeline verification.")
        c.drawString(72, 720, "It contains English content for parsing and ingestion tests.")
        c.drawString(72, 690, "Paragraph 1: Testing document parser with PDF inputs.")
        c.drawString(72, 670, "Paragraph 2: Verifying Docling parser with BGE-M3 embeddings.")
        c.drawString(72, 650, "Key terms: Chatbot, RAG, Vector database, Citations.")
        c.showPage()

        # Page 2
        c.setFont("Helvetica-Bold", 14)
        c.drawString(72, 770, "Section: Chunking Strategy")
        c.setFont("Helvetica", 11)
        text_lines = [
            "We use hierarchical chunking: parent (2000t) and child (512t).",
            "Children are embedded for retrieval; parents for answer context.",
            "Anthropic-style contextual retrieval adds an LLM-generated prefix.",
            "BGE-M3 produces dense + sparse + colbert representations.",
            "RRF fusion combines all three retrieval channels.",
        ]
        y = 740
        for line in text_lines:
            c.drawString(72, y, line)
            y -= 20
        c.showPage()
        c.save()
        return buf.getvalue()
    except ImportError:
        # 没装 reportlab, 返回手搓最小 PDF (可能 Docling 解析失败, 但 SHA256 流程能测)
        return _minimal_pdf()


def _minimal_pdf() -> bytes:
    """手搓的最小 PDF. 仅用于 SHA256 / 解析降级测试."""
    return b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj
4 0 obj<</Length 44>>stream
BT /F1 12 Tf 72 720 Td (Test PDF) Tj ET
endstream endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000052 00000 n
0000000098 00000 n
0000000158 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref
240
%%EOF
"""


async def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    results: list[bool] = []

    # ========== 1. chunk_document 单元 ==========
    section("1. chunk_document 单元")
    try:
        from app.services.chunking import chunk_document
        from app.services.parsers.base_parser import ParsedDocument, PageContent

        # 构造一份带 3 个标题的样本文档
        sample_md = """# 简介

这是引言段, 描述文档目的。

# 第一章 背景

人工智能技术近年来发展迅速。大模型的能力在持续提升, 包括推理、生成、理解等多方面。
本节主要介绍背景知识。

更多段落填充, 让内容超过 chunk_size, 触发分块。
""" + ("这是填充段落。" * 200) + """

# 第二章 方法

## 2.1 嵌入

使用 BGE-M3 模型。

## 2.2 检索

混合检索三路。

# 第三章 结论

效果显著。
"""
        parsed = ParsedDocument(
            markdown=sample_md,
            pages=[PageContent(page_no=1, text=sample_md[:500])],
            tables=[],
            images=[],
            meta={"page_count": 1, "parser": "test"},
        )
        out = chunk_document(parsed, doc_id="test-doc")
        results.append(check("parents > 0", len(out.parents) > 0, f"={len(out.parents)}"))
        results.append(check("children > 0", len(out.children) > 0, f"={len(out.children)}"))
        results.append(check("每个 child 有 parent_id", all(c.parent_id for c in out.children)))
        results.append(check("chunk_index 单调递增", all(
            out.children[i].chunk_index < out.children[i + 1].chunk_index
            for i in range(len(out.children) - 1)
        )))
        results.append(check("token_count 合理", all(0 < c.token_count < 2000 for c in out.children)))
    except Exception as e:  # noqa: BLE001
        results.append(check("chunk_document", False, str(e)))

    # ========== 2. SHA256 幂等 ==========
    section("2. SHA256 幂等性")
    try:
        import hashlib
        content = b"hello world" * 100
        sha = hashlib.sha256(content).hexdigest()
        results.append(check("SHA256 一致", len(sha) == 64))
        results.append(check("同输入同哈希", hashlib.sha256(content).hexdigest() == sha))
    except Exception as e:  # noqa: BLE001
        results.append(check("SHA256", False, str(e)))

    # ========== 3. 端到端 ingest_bytes ==========
    section("3. 端到端 ingest_bytes (需要 docling + chromadb + bge-m3)")
    pdf_bytes = make_sample_pdf()
    print(f"  ℹ️  测试 PDF: {len(pdf_bytes)} bytes")

    try:
        from app.services.ingestion import ingest_bytes, list_documents, get_document, delete_document
        started = time.time()
        result = await ingest_bytes(content=pdf_bytes, filename="test.pdf")
        elapsed = int((time.time() - started) * 1000)
        results.append(check("ingest_bytes 返回", result is not None))
        results.append(check("  doc_id 存在", bool(result.doc_id)))
        results.append(check(f"  status in (ready/duplicate)", result.status in {"ready", "duplicate"}, f"={result.status}"))
        results.append(check(f"  chunk_count > 0", result.chunk_count > 0, f"={result.chunk_count}"))
        print(f"  ⏱  {elapsed}ms")

        # 4. list / get
        docs = list_documents()
        found = any(d["id"] == result.doc_id for d in docs)
        results.append(check("出现在 list", found, f"total={len(docs)}"))
        doc = get_document(result.doc_id)
        results.append(check("  get 返回完整元数据", doc is not None and "sha256" in doc))

        # 5. 重复上传 -> duplicate
        result2 = await ingest_bytes(content=pdf_bytes, filename="test.pdf")
        results.append(check("重复上传 -> duplicate", result2.status == "duplicate",
                              f"status={result2.status}"))
        results.append(check("  同 doc_id", result2.doc_id == result.doc_id))

        # 6. 检索验证 (用 doc 中的词)
        from app.services.embedding import get_embedder
        from app.services.vector_store import hybrid_query

        embedder = get_embedder()
        q_emb = await embedder.encode_query("chunking strategy")
        hits = hybrid_query(query_emb=q_emb["dense"][0] if q_emb["dense"].ndim == 2 else q_emb["dense"],
                           query_sparse=q_emb["sparse"][0] if q_emb["sparse"] else None,
                           k=3)
        results.append(check("hybrid_query 返回 hits", len(hits) > 0, f"={len(hits)}"))
        if hits:
            top = hits[0]
            results.append(check("  top hit 包含 doc_id", bool(top.doc_id), f"doc_id={top.doc_id[:8]}"))
            results.append(check("  text 长度合理", 50 < len(top.text) < 5000, f"len={len(top.text)}"))

        # 7. delete
        ok = await delete_document(result.doc_id)
        results.append(check("delete 成功", ok))
        results.append(check("  get 返 None", get_document(result.doc_id) is None))

        # 8. delete 后再检索应无 hit
        hits2 = hybrid_query(query_emb=q_emb["dense"][0] if q_emb["dense"].ndim == 2 else q_emb["dense"],
                            query_sparse=q_emb["sparse"][0] if q_emb["sparse"] else None,
                            k=3)
        results.append(check("delete 后无 hit", len(hits2) == 0, f"={len(hits2)}"))

    except Exception as e:  # noqa: BLE001
        import traceback
        results.append(check("端到端", False, f"{e}"))
        traceback.print_exc()

    # ========== 8. API 端点 ==========
    section("4. API 端点")
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        from app.core.paths import upload_dir

        with TestClient(app) as client:
            pdf_bytes2 = make_sample_pdf()
            r = client.post(
                "/api/v1/documents/upload",
                files={"file": ("api_test.pdf", io.BytesIO(pdf_bytes2), "application/pdf")},
            )
            results.append(check("POST /documents/upload", r.status_code == 200,
                                  f"status={r.status_code}"))
            doc_id_api = None
            if r.status_code == 200:
                doc_id_api = r.json().get("doc_id")

            r = client.get("/api/v1/documents")
            results.append(check("GET /documents", r.status_code == 200, f"status={r.status_code}"))
            if r.status_code == 200:
                body = r.json()
                results.append(check("  包含 documents 列表", "documents" in body))

            if doc_id_api:
                r = client.get(f"/api/v1/documents/{doc_id_api}")
                results.append(check("GET /documents/{id}", r.status_code == 200))

                r = client.delete(f"/api/v1/documents/{doc_id_api}")
                results.append(check("DELETE /documents/{id}", r.status_code == 200))

                r = client.get(f"/api/v1/documents/{doc_id_api}")
                results.append(check("  delete 后 404", r.status_code == 404))
    except Exception as e:  # noqa: BLE001
        import traceback
        results.append(check("API 测试", False, f"{e}"))
        traceback.print_exc()

    # ========== 总结 ==========
    section("总结")
    passed = sum(results)
    total = len(results)
    print(f"  通过: {passed}/{total}  ({passed / total * 100:.0f}%)")
    if passed < total:
        print("\n  提示: 失败可能因为未装 docling / FlagEmbedding / chromadb.")
        print("  请先: pip install -r requirements.txt")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
