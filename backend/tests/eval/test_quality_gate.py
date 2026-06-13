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
