"""RAGAS 离线评估脚本.

评估指标:
- Faithfulness: 答案是否仅基于检索上下文
- Answer Relevancy: 答案是否回答了用户问题
- Context Precision: 检索到的 chunk 排序是否合理
- Context Recall: 是否检索到了所有相关 chunk

用法:
    cd backend
    pip install ragas datasets
    python -m pytest tests/eval/test_ragas.py -v

或独立运行:
    python tests/eval/test_ragas.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# 测试数据集: 黄金 QA 对 (从真实文档抽取 5-10 个)
# 实际项目中应人工标注更大集合 (50-100 对)
GOLDEN_QA: list[dict[str, Any]] = [
    {
        "question": "Q3 2025 营收是多少?",
        "ground_truth": "$4.2 million",
        "context_keywords": ["Q3", "revenue", "$4.2"],
    },
    {
        "question": "文档中提到的关键风险因素有哪些?",
        "ground_truth": "supply chain 和 FX volatility",
        "context_keywords": ["risk", "supply chain", "FX"],
    },
    {
        "question": "R&D 投入增长了多少?",
        "ground_truth": "30%",
        "context_keywords": ["R&D", "30%"],
    },
]


async def _run_eval() -> dict[str, Any]:
    """跑一轮评估. 返回 metrics dict."""
    try:
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
        from datasets import Dataset
    except ImportError as e:
        print(f"❌ 缺依赖: {e}\n请先: pip install ragas datasets")
        return {"error": str(e)}

    # 收集数据: 跑 agent 拿到 answers + contexts
    print("=" * 60)
    print("  RAGAS 评估")
    print("=" * 60)
    print(f"  QA 数量: {len(GOLDEN_QA)}")
    print()

    # 阶段 1: 摄入测试文档 (复用 smoke_phase2 的 PDF 生成)
    from tests.eval._fixtures import build_test_corpus

    print("📄 摄入测试文档...")
    docs = await build_test_corpus()
    print(f"  ✅ {len(docs)} 个文档已就绪")

    # 阶段 2: 跑 agent 拿答案
    print("\n🤖 跑 agent 生成 answers...")
    from app.agents.graph import get_compiled_graph
    from app.agents.nodes import answer_node_stream
    from app.agents.state import empty_state_for
    from langchain_core.messages import HumanMessage

    graph = await get_compiled_graph()

    eval_data: list[dict[str, Any]] = []
    for i, qa in enumerate(GOLDEN_QA, 1):
        print(f"  [{i}/{len(GOLDEN_QA)}] {qa['question']}")
        state = empty_state_for(f"eval-{i}")
        state["messages"] = [HumanMessage(content=qa["question"])]
        try:
            result = await graph.ainvoke(
                state, config={"configurable": {"thread_id": f"eval-{i}"}}
            )
            # 跑 answer 流式
            ans_update = await answer_node_stream(result)
            result.update(ans_update)
            contexts = [c.text for c in result.get("reranked", [])]
            eval_data.append({
                "question": qa["question"],
                "answer": result.get("final_answer", ""),
                "contexts": contexts,
                "ground_truth": qa["ground_truth"],
            })
        except Exception as e:  # noqa: BLE001
            print(f"    ❌ {e}")
            eval_data.append({
                "question": qa["question"],
                "answer": f"ERROR: {e}",
                "contexts": [],
                "ground_truth": qa["ground_truth"],
            })

    # 阶段 3: 跑 RAGAS
    print("\n📊 跑 RAGAS 指标...")
    ds = Dataset.from_list(eval_data)
    try:
        scores = evaluate(
            ds,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        )
        return dict(scores)
    except Exception as e:  # noqa: BLE001
        # RAGAS 需要 LLM 来 judge, 用现有 LLM
        print(f"  ⚠️  RAGAS evaluate 失败: {e}")
        return {"error": str(e)}


def main() -> int:
    started = time.time()
    try:
        scores = asyncio.run(_run_eval())
    except KeyboardInterrupt:
        print("\n⏹  中断")
        return 130

    print("\n" + "=" * 60)
    print("  评估结果")
    print("=" * 60)
    if "error" in scores:
        print(f"  ❌ {scores['error']}")
        return 1

    for k, v in scores.items():
        if isinstance(v, (int, float)):
            bar = "█" * int(float(v) * 20)
            print(f"  {k:<25} {float(v):.3f}  {bar}")
    print(f"\n  ⏱  {int((time.time() - started) * 1000)}ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
