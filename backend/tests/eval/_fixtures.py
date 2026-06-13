"""RAGAS / DeepEval 共享 fixtures. 生成测试 PDF + 摄入."""
from __future__ import annotations

import asyncio
import io

from app.services.ingestion import ingest_bytes


def _make_test_pdf() -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 770, "Q3 2025 Financial Report")
        c.setFont("Helvetica", 11)
        for i, line in enumerate([
            "Revenue in Q3 2025 was $4.2 million, up 23% YoY.",
            "Operating margin improved to 18.5%.",
            "Key risks include supply chain and FX volatility.",
            "Q4 outlook: continued growth driven by AI products.",
            "R&D spending increased by 30%, mostly in the agent platform.",
        ]):
            c.drawString(72, 740 - i * 20, line)
        c.showPage()
        c.save()
        return buf.getvalue()
    except ImportError:
        return b"%PDF-1.4\n%minimal\n"


async def build_test_corpus() -> list[dict]:
    """建一个最小测试语料. 返回 [{doc_id, filename, content}]."""
    pdf = _make_test_pdf()
    result = await ingest_bytes(content=pdf, filename="ragas_test.pdf")
    return [{
        "doc_id": result.doc_id,
        "filename": "ragas_test.pdf",
        "chunk_count": result.chunk_count,
    }]


if __name__ == "__main__":
    docs = asyncio.run(build_test_corpus())
    print(f"Built {len(docs)} docs: {docs}")
