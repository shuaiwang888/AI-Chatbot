"""DeepEval CI/CD 质量门禁.

特点:
- pytest 风格, 集成到 CI
- 阈值断言, 不达标直接 fail
- 用 DeepEval 的 G-Eval 评估答案质量

用法:
    pip install deepeval
    deepeval test run tests/eval/test_quality_gate.py

或在 CI:
    deepeval test run tests/eval/test_quality_gate.py --confident-api-key=...

阈值 (按项目需求调):
- answer_relevancy >= 0.7
- faithfulness >= 0.8
- hallucination <= 0.2
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path


# ========== 阈值 (项目级, 可改) ==========
MIN_ANSWER_RELEVANCY = 0.70
MIN_FAITHFULNESS = 0.80
MAX_HALLUCINATION = 0.20
MAX_RETRIEVAL_LATENCY_MS = 3000


GOLDEN_CASES = [
    {
        "input": "Q3 2025 营收是多少?",
        "expected_output": "$4.2 million",
        "retrieval_context": [
            "Revenue in Q3 2025 was $4.2 million, up 23% YoY.",
        ],
    },
    {
        "input": "文档中提到的关键风险因素有哪些?",
        "expected_output": "supply chain 和 FX volatility",
        "retrieval_context": [
            "Key risks include supply chain and FX volatility.",
        ],
    },
]


# ========== 单元测试用例 (pytest 风格) ==========
def test_module_imports():
    """冒烟: 模块 import 正常."""
    from app.agents.graph import _build_graph
    from app.agents.tools import _safe_eval, execute_tool
    assert _build_graph is not None
    assert _safe_eval is not None
    assert execute_tool is not None


def test_calculate_ast_sandbox():
    """AST 沙箱防注入."""
    from app.agents.tools import _safe_eval
    import ast
    # 正常运算
    assert _safe_eval(ast.parse("(10 + 5) * 2", mode="eval")) == 30
    # 注入防护
    for bad in [
        "__import__('os').system('echo HACKED')",
        "open('/etc/passwd')",
        "eval('1+1')",
    ]:
        try:
            _safe_eval(ast.parse(bad, mode="eval"))
            raise AssertionError(f"应该拒绝: {bad}")
        except (ValueError, TypeError, SyntaxError):
            pass  # expected


def test_safe_json_extraction():
    """LLM 输出抠 JSON 健壮性."""
    from app.agents.nodes import _safe_json
    assert _safe_json('{"a": 1}') == {"a": 1}
    assert _safe_json('思考: {"x": 2} 完毕') == {"x": 2}
    assert _safe_json('```json\n{"y": 3}\n```') == {"y": 3}
    assert _safe_json("not json") is None


def test_chunking_preserves_headings():
    """分块保留标题信息."""
    from app.services.chunking import chunk_document
    from app.services.parsers.base_parser import ParsedDocument, PageContent

    parsed = ParsedDocument(
        markdown="# 标题一\n段落1\n\n## 标题二\n段落2\n",
        pages=[PageContent(page_no=1, text="# 标题一\n段落1")],
    )
    result = chunk_document(parsed, doc_id="test")
    headings = {c.heading for c in result.children}
    assert "标题一" in headings
    assert "标题二" in headings


def test_access_control_fails_closed_without_deployment_secret():
    """A public Space must not silently become an unauthenticated data API."""
    from fastapi import HTTPException
    from app.core.auth import require_access_token

    try:
        asyncio.run(require_access_token(None))
    except HTTPException as exc:
        assert exc.status_code in (401, 503)
    else:
        # CI intentionally sets AUTH_REQUIRED=false; production defaults to on.
        from app.config import settings
        assert settings.auth_required is False


def test_document_scope_is_carried_by_agent_state():
    """The public doc_ids contract must reach retrieval instead of being ignored."""
    from app.agents.state import empty_state_for

    state = empty_state_for("scope-test", requested_doc_ids=["a", "a", "b"])
    assert state["requested_doc_ids"] == ["a", "a", "b"]


def test_colbert_storage_preserves_sparse_weights():
    """Optional ColBERT must augment, never replace, lexical retrieval data."""
    import uuid
    import numpy as np

    from app.config import settings
    from app.core.paths import data_dir
    from app.models import db
    from app.services.vector_store import SparseSidecar

    db.init_db()
    sidecar = SparseSidecar(settings.sqlite_db_path)
    chunk_id = f"sparse-colbert-{uuid.uuid4().hex}"
    sidecar.upsert_bulk([(chunk_id, {7: 0.75})])
    sidecar.upsert_colbert([(chunk_id, np.zeros((1, 4), dtype=np.float32))])

    assert sidecar.get_sparse(chunk_id) == {7: 0.75}
    colbert_path = sidecar.get_colbert_path(chunk_id)
    assert colbert_path

    conn = db.get_conn()
    conn.execute("DELETE FROM chunk_sparse WHERE chunk_id = ?", (chunk_id,))
    conn.execute("DELETE FROM chunk_colbert WHERE chunk_id = ?", (chunk_id,))
    (data_dir() / colbert_path).unlink(missing_ok=True)


def test_chat_stream_reports_graph_progress_before_answer(monkeypatch):
    """流式端点不能等检索图全部结束后才给用户第一帧反馈。"""
    from app.api import chat
    from app.models.schemas import ChatRequest

    class FakeHit:
        score = 0.91

    class FakeGraph:
        async def astream(self, state, config=None, stream_mode=None):
            assert stream_mode == "updates"
            yield {"route": {"route_decision": "retrieve", "query_rewritten": "测试问题"}}
            yield {"retrieve": {"retrieved": [FakeHit()], "retrieved_doc_ids": ["doc-1"]}}
            yield {"rerank": {"reranked": [FakeHit()], "citations": []}}
            yield {"evaluate": {"needs_more_retrieval": False}}

    async def fake_get_graph():
        return FakeGraph()

    async def fake_answer(state, on_token=None, **_kwargs):
        await on_token("## 核心结论\n\n流式答案")
        return {"final_answer": "## 核心结论\n\n流式答案", "citations": []}

    async def fake_schedule_push():
        return None

    monkeypatch.setattr(chat, "get_compiled_graph", fake_get_graph)
    monkeypatch.setattr(chat, "answer_node_stream", fake_answer)
    monkeypatch.setattr(chat, "schedule_push", fake_schedule_push)
    monkeypatch.setattr(chat.db, "message_list_by_session", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(chat.db, "session_get", lambda *_args, **_kwargs: {"title": "已有会话"})
    monkeypatch.setattr(chat.db, "session_upsert", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(chat.db, "message_insert", lambda *_args, **_kwargs: None)

    events = []

    async def emit(event, data):
        events.append((event, data))

    req = ChatRequest(session_id="stream-test", message="测试问题")
    state, _steps = asyncio.run(chat._run_agent(req, emit=emit))

    assert events[0][0] == chat.EV_PROGRESS
    assert events[0][1]["pct"] <= 2
    assert (chat.EV_AGENT_STEP, {"node": "route", "status": "running"}) in events
    retrieval_index = next(i for i, item in enumerate(events) if item[0] == chat.EV_RETRIEVAL)
    token_index = next(i for i, item in enumerate(events) if item[0] == chat.EV_TOKEN)
    assert retrieval_index < token_index
    assert state["final_answer"].startswith("## 核心结论")


def test_answer_prompt_requires_semantic_markdown_hierarchy():
    from app.agents.prompts import ANSWER_PROMPT

    assert "## 核心结论" in ANSWER_PROMPT
    assert "###" in ANSWER_PROMPT
    assert "## 参考来源" in ANSWER_PROMPT


def test_cpu_default_skips_cross_encoder_reranker(monkeypatch):
    """免费 CPU 默认不能把几十秒的 CrossEncoder 放在每次问答热路径。"""
    from app.agents import nodes
    from app.services.vector_store import RetrievalHit

    hit = RetrievalHit(
        chunk_id="chunk-1",
        doc_id="doc-1",
        text="与问题相关的内容",
        score=0.03,
        page_no=1,
        heading="测试",
        context_prefix=None,
        meta={},
        dense_score=0.72,
    )

    monkeypatch.setattr(nodes.settings, "enable_reranker", False)
    monkeypatch.setattr(nodes, "_doc_meta_brief", lambda _doc_id: {"filename": "test.md"})
    monkeypatch.setattr(
        nodes,
        "get_reranker_service",
        lambda: (_ for _ in ()).throw(AssertionError("CPU fallback must not load reranker")),
    )

    result = asyncio.run(nodes.rerank_node({
        "retrieved": [hit],
        "query_rewritten": "测试问题",
    }))

    assert result["reranked"] == [hit]
    assert result["relevance_verdict"] == "relevant"
    assert result["citations"][0]["score"] == 0.72


# ========== 端到端 (用 deepeval) ==========
def test_deepeval_e2e():
    """DeepEval 端到端: 摄入 → 检索 → 回答 → 4 个指标.

    需要: pip install deepeval
    跑法: deepeval test run tests/eval/test_quality_gate.py
    """
    try:
        import deepeval
        from deepeval import assert_test
        from deepeval.metrics import (
            AnswerRelevancyMetric,
            FaithfulnessMetric,
            HallucinationMetric,
        )
        from deepeval.test_case import LLMTestCase
    except ImportError:
        import pytest
        pytest.skip("deepeval 未装, 跳过")

    from tests.eval._fixtures import build_test_corpus

    async def _run():
        await build_test_corpus()

        from app.agents.graph import get_compiled_graph
        from app.agents.nodes import answer_node_stream
        from app.agents.state import empty_state_for
        from langchain_core.messages import HumanMessage

        graph = await get_compiled_graph()
        results = []
        for i, case in enumerate(GOLDEN_CASES):
            state = empty_state_for(f"deepeval-{i}")
            state["messages"] = [HumanMessage(content=case["input"])]
            res = await graph.ainvoke(state, config={"configurable": {"thread_id": f"deepeval-{i}"}})
            ans_update = await answer_node_stream(res)
            res.update(ans_update)
            test_case = LLMTestCase(
                input=case["input"],
                actual_output=res.get("final_answer", ""),
                expected_output=case["expected_output"],
                retrieval_context=case["retrieval_context"],
            )
            results.append(test_case)
        return results

    cases = asyncio.run(_run())
    for case in cases:
        assert_test(
            case,
            [
                AnswerRelevancyMetric(threshold=MIN_ANSWER_RELEVANCY),
                FaithfulnessMetric(threshold=MIN_FAITHFULNESS),
                HallucinationMetric(threshold=MAX_HALLUCINATION),
            ],
        )


# ========== Main 入口 (单独跑) ==========
def main() -> int:
    started = time.time()
    print("=" * 60)
    print("  DeepEval 质量门禁")
    print("=" * 60)
    print(f"  阈值: answer_relevancy ≥ {MIN_ANSWER_RELEVANCY}")
    print(f"        faithfulness    ≥ {MIN_FAITHFULNESS}")
    print(f"        hallucination   ≤ {MAX_HALLUCINATION}")
    print()

    test_module_imports()
    print("  ✅ module imports")
    test_calculate_ast_sandbox()
    print("  ✅ AST 沙箱防注入")
    test_safe_json_extraction()
    print("  ✅ safe_json 抠 JSON")
    test_chunking_preserves_headings()
    print("  ✅ 分块保留 heading")

    # DeepEval 端到端 (有依赖时跑)
    try:
        test_deepeval_e2e()
        print("  ✅ DeepEval 端到端")
    except Exception as e:  # noqa: BLE001
        if "deepeval" in str(e).lower() or "未装" in str(e):
            print(f"  ⏭  DeepEval 端到端 (需装 deepeval): {e}")
        else:
            raise

    print(f"\n  ⏱  {int((time.time() - started) * 1000)}ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
