"""LangGraph 节点实现.

每个 node 接收 AgentState, 返回部分更新的 dict.
节点间通过 state 自动传递, 不直接耦合.

设计要点:
- 节点只做一件事, 容易测试
- LLM 调用统一走工厂, 走 LLM cache
- 异常不抛, 写入 state['error'], 让图走 fallback 边
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.prompts import (
    ANSWER_PROMPT,
    CRAG_EVAL_PROMPT,
    ROUTE_AND_REWRITE_PROMPT,
)
from app.agents.state import AgentState
from app.agents.tools import TOOL_SCHEMAS, execute_tool
from app.config import settings
from app.llm.base import LLMMessage
from app.llm.factory import get_llm
from app.services.embedding import get_embedder
from app.services.llm_cache import CachedAnswer, lookup as cache_lookup, store as cache_store
from app.services.reranker import get_reranker_service
from app.services.vector_store import RetrievalHit, hybrid_query

logger = logging.getLogger(__name__)


# ========== 工具: 取最近用户消息文本 ==========
def _last_user_query(state: AgentState) -> str:
    for m in reversed(list(state.get("messages") or [])):
        if hasattr(m, "type") and m.type == "human":
            return m.content if isinstance(m.content, str) else str(m.content)
        if isinstance(m, dict) and m.get("role") == "user":
            return m.get("content", "")
    return ""


def _safe_json(text: str) -> dict | None:
    """尽量从 LLM 输出中抠 JSON. 失败返回 None."""
    if not text:
        return None
    # 尝试直接 parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 抠 ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 抠第一个 { ... }
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ========== Node 1+2 合并: route + query_rewrite ==========
# ⚡ A 改良版: 旧版 route_node (LLM 1) → query_rewrite_node (LLM 2) 串行,
# 两次网络 RTT 0.5-1.5s. 合并为单次 LLM 调用, 输出 {route, query, steps}.
# 收益: 省 1 次 RTT (~0.3-0.8s) + 1 次 LLM TTFT (~0.2-0.5s).
async def route_node(state: AgentState) -> dict[str, Any]:
    """⚡ 单次 LLM 同时决定 route + 改写 query (multi_step 时拆子问题)."""
    started = time.time()
    query = _last_user_query(state)
    if not query:
        return {"route_decision": "retrieve", "query_rewritten": "", "plan": []}

    # 启发式快路 (短问候跳过 LLM, 省 0.5-1.5s)
    ql = query.strip().lower()
    if len(ql) <= 12 and any(g in ql for g in (
        "你好", "您好", "hi", "hello", "hey", "你是谁", "what's up", "how are you",
        "thanks", "thank you", "谢谢", "再见", "bye",
    )):
        return {"route_decision": "direct", "query_rewritten": query, "plan": []}

    try:
        llm = get_llm()
        resp = await llm.chat(
            messages=[
                LLMMessage(role="system", content=ROUTE_AND_REWRITE_PROMPT),
                LLMMessage(role="user", content=query),
            ],
            temperature=0.0,
            max_tokens=200,  # 比旧版 max 80 略多, 但单次调用比分两次便宜
        )
        data = _safe_json(resp.content or "")
        decision = (data or {}).get("route", "retrieve")
        rewritten = (data or {}).get("query", query) or query
        steps = (data or {}).get("steps", []) or []

        # 兜底: 决策不合法降级
        if decision not in ("direct", "retrieve", "multi_step"):
            decision = "retrieve"
        # 兜底: steps 不是 list 降级
        if not isinstance(steps, list):
            steps = []

        if decision == "multi_step":
            if not steps:
                steps = [rewritten]
            plan = steps
            # multi_step 时, query 字段是"第一个子问题", 直接覆盖
            final_query = steps[0]
        else:
            plan = []
            final_query = rewritten

        logger.debug(
            "route+rewrite: %s (%dms) q=%r plan=%d",
            decision, int((time.time() - started) * 1000), final_query[:30], len(plan),
        )
        return {
            "route_decision": decision,
            "query_rewritten": final_query,
            "plan": plan,
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("route_node failed: %s, default to retrieve", e)
        return {"route_decision": "retrieve", "query_rewritten": query, "plan": []}


# ⚠️ 旧 query_rewrite_node 已废弃 (合并到 route_node 上面)
# 保留作为旧 graph 配置兼容, 实际不再被任何 graph 调用.
# 如果有新代码误调, 走快速 fallback 避免崩溃.
async def query_rewrite_node(state: AgentState) -> dict[str, Any]:
    """[已废弃] 旧版 query_rewrite 节点. 实际功能已合并到 route_node."""
    logger.debug("query_rewrite_node called but deprecated; merging handled in route_node")
    query = state.get("query_rewritten") or _last_user_query(state)
    return {"query_rewritten": query, "plan": state.get("plan") or []}


# ========== Node 3: retrieve ==========
async def retrieve_node(state: AgentState) -> dict[str, Any]:
    """混合检索 top-K."""
    started = time.time()
    query = state.get("query_rewritten") or _last_user_query(state)
    if not query:
        return {"retrieved": [], "retrieved_doc_ids": []}

    embedder = get_embedder()
    out = await embedder.encode_query(query)
    dense = out["dense"]
    # dense shape: (1, 1024) or (1024,) depending on encode return
    if dense.ndim == 2:
        dense_vec = dense[0]
    else:
        dense_vec = dense
    sparse = out.get("sparse", [{}])[0] if out.get("sparse") else None
    colbert = out.get("colbert", [None])[0] if out.get("colbert") else None

    # multi_step: 每步独立检索再合并
    plan = state.get("plan") or []
    all_hits: list[RetrievalHit] = []
    seen: set[str] = set()
    queries_to_run = plan if plan else [query]
    for q in queries_to_run:
        if q == query and all_hits:
            continue  # 主 query 已跑过
        if q != query:
            sub_out = await embedder.encode_query(q)
            sub_dense = sub_out["dense"][0] if sub_out["dense"].ndim == 2 else sub_out["dense"]
            sub_sparse = sub_out.get("sparse", [{}])[0] if sub_out.get("sparse") else None
            sub_colbert = sub_out.get("colbert", [None])[0] if sub_out.get("colbert") else None
            hits = hybrid_query(
                query_emb=sub_dense,
                query_sparse=sub_sparse,
                query_colbert_emb=sub_colbert,
                k=settings.rerank_top_n * 4,
            )
        else:
            hits = hybrid_query(
                query_emb=dense_vec,
                query_sparse=sparse,
                query_colbert_emb=colbert,
                k=settings.rerank_top_n * 4,
            )
        for h in hits:
            if h.chunk_id not in seen:
                seen.add(h.chunk_id)
                all_hits.append(h)

    # 按 score 截前 N
    all_hits.sort(key=lambda h: h.score, reverse=True)
    all_hits = all_hits[: settings.rerank_top_n * 4]

    doc_ids = list({h.doc_id for h in all_hits if h.doc_id})
    logger.debug("retrieve: %d hits, %d docs, %dms",
                 len(all_hits), len(doc_ids), int((time.time() - started) * 1000))
    return {"retrieved": all_hits, "retrieved_doc_ids": doc_ids}


# ========== Node 4: rerank ==========
async def rerank_node(state: AgentState) -> dict[str, Any]:
    """BGE-reranker 精排 top-N + 产出引用."""
    started = time.time()
    hits = state.get("retrieved") or []
    query = state.get("query_rewritten") or _last_user_query(state)
    if not hits:
        return {"reranked": [], "citations": [], "relevance_score": 0.0, "relevance_verdict": "irrelevant"}

    reranker = get_reranker_service()
    reranked = await reranker.rerank(query, hits, top_n=settings.rerank_top_n)

    # 构造引用 (前 5 个, 按 rerank 分数)
    citations: list[dict[str, Any]] = []
    for i, h in enumerate(reranked):
        doc = _doc_meta_brief(h.doc_id)
        citations.append({
            "doc_id": h.doc_id,
            "filename": doc.get("filename", "未知"),
            "page": h.page_no,
            "heading": h.heading,
            "snippet": (h.text or "")[:240],
            "score": round(h.rerank_score, 4),
            "rank": i + 1,
        })

    top_score = reranked[0].rerank_score if reranked else 0.0
    if top_score >= settings.crag_relevance_threshold:
        verdict = "relevant"
    elif top_score < 0.3:
        verdict = "irrelevant"
    else:
        verdict = "ambiguous"

    logger.debug("rerank: top=%.3f verdict=%s %dms", top_score, verdict, int((time.time() - started) * 1000))
    return {
        "reranked": reranked,
        "citations": citations,
        "relevance_score": top_score,
        "relevance_verdict": verdict,
    }


def _doc_meta_brief(doc_id: str) -> dict[str, Any]:
    try:
        from app.models import db
        d = db.doc_get(doc_id)
        return d or {}
    except Exception:  # noqa: BLE001
        return {}


# ========== Node 5: answer (流式 LLM 调用) ==========
async def answer_node_stream(
    state: AgentState,
    on_token: Any = None,  # async callable(content: str) -> None
    on_citation: Any = None,
    on_thinking: Any = None,
) -> dict[str, Any]:
    """生成最终答案. 通过 on_token 回调逐 token 推送.

    流程:
    1. 拼装 context (从 reranked hits)
    2. 查 LLM 缓存
    3. 命中: 回放 tokens
    4. 未命中: 调 LLM 流式 + 缓存结果
    """
    query = state.get("query_rewritten") or _last_user_query(state)
    reranked = state.get("reranked") or []
    locale = state.get("locale", "zh")

    # 拼 context
    if reranked:
        ctx_lines: list[str] = []
        for i, h in enumerate(reranked, 1):
            tag = f"[{i}]"
            prefix_bits = []
            if h.heading:
                prefix_bits.append(f"章节: {h.heading}")
            if h.page_no:
                prefix_bits.append(f"页码: {h.page_no}")
            if h.context_prefix:
                prefix_bits.append(f"上下文: {h.context_prefix}")
            meta = " | ".join(prefix_bits)
            ctx_lines.append(f"{tag} {('('+meta+')') if meta else ''}\n{h.text}")
        context = "\n\n".join(ctx_lines)
    else:
        if on_thinking:
            await on_thinking("未在知识库中找到相关文档, 直接基于通用知识回答。")
        context = "(无相关文档)"

    prompt = ANSWER_PROMPT.format(context=context, query=query, LOCALE=locale)
    system_msg = "你是私人智能客服, 回答需基于 context 引用, 用对应 locale 回答。"

    # 缓存 key
    top_doc_ids = [c["doc_id"] for c in state.get("citations", [])]
    cached = cache_lookup(query, top_doc_ids, 0.7)

    started = time.time()
    if cached is not None:
        # 回放
        if on_thinking:
            await on_thinking("(cache hit, 跳过 LLM)")
        for tok in cached.tokens:
            if on_token:
                await on_token(tok)
        return {
            "final_answer": cached.content,
            "messages": [AIMessage(content=cached.content)],
            "elapsed_ms": int((time.time() - started) * 1000),
        }

    # 实际 LLM 流式
    llm = get_llm()
    collected: list[str] = []
    full_text = ""
    try:
        async for chunk in llm.stream_chat(
            messages=[
                LLMMessage(role="system", content=system_msg),
                LLMMessage(role="user", content=prompt),
            ],
            temperature=0.7,
            max_tokens=1200,
        ):
            if chunk.content:
                collected.append(chunk.content)
                full_text += chunk.content
                if on_token:
                    await on_token(chunk.content)
    except Exception as e:  # noqa: BLE001
        logger.exception("answer_node_stream failed")
        err_msg = f"抱歉, 生成答案时出错: {e}"
        if on_token:
            await on_token(err_msg)
        return {
            "final_answer": err_msg,
            "messages": [AIMessage(content=err_msg)],
            "error": str(e),
        }

    # 缓存结果
    cache_store(query, top_doc_ids, 0.7, CachedAnswer(
        content=full_text,
        citations=state.get("citations", []),
        tool_calls=[],
        tokens=collected,
    ))

    # 推引用 (在 answer 末尾)
    if on_citation and state.get("citations"):
        for c in state["citations"]:
            await on_citation(c)

    return {
        "final_answer": full_text,
        "messages": [AIMessage(content=full_text)],
        "elapsed_ms": int((time.time() - started) * 1000),
    }


# ========== Node 6: evaluate (CRAG) ==========
async def evaluate_node(state: AgentState) -> dict[str, Any]:
    """CRAG 自校正判定.

    阶段 1 (必走, 极快): 用 rerank top-1 score 做硬阈值判断
    阶段 2 (仅模糊区间): LLM judge 二次判定, 决定是否回 retrieve
    """
    iteration = state.get("iteration", 0) + 1
    score = state.get("relevance_score", 0.0)
    verdict = state.get("relevance_verdict", "ambiguous")
    max_iter = state.get("max_iterations", settings.crag_max_iterations)

    # 阶段 1: rerank 分数硬阈值
    if verdict == "relevant":
        return {
            "iteration": iteration,
            "needs_more_retrieval": False,
            "crag_finished": True,
        }
    if verdict == "irrelevant":
        # 直接告知用户, 不再循环
        return {
            "iteration": iteration,
            "needs_more_retrieval": False,
            "crag_finished": True,
        }

    # 阶段 2: 模糊区间, 调 LLM judge (用便宜的 judge model)
    if iteration >= max_iter:
        # 超过上限, 收口
        return {
            "iteration": iteration,
            "needs_more_retrieval": False,
            "crag_finished": True,
        }

    try:
        llm = get_llm()  # 用同 model (个人项目成本可接受)
        query = state.get("query_rewritten") or _last_user_query(state)
        reranked = state.get("reranked") or []
        docs_summary = "\n".join(
            f"[{i+1}] {h.heading or '无标题'}: {(h.text or '')[:120]}"
            for i, h in enumerate(reranked[:5])
        )
        resp = await llm.chat(
            messages=[
                LLMMessage(role="system", content=CRAG_EVAL_PROMPT.format(
                    query=query, n=len(reranked[:5]), docs_summary=docs_summary,
                )),
            ],
            temperature=0.0,
            max_tokens=120,
        )
        data = _safe_json(resp.content or "")
        v = (data or {}).get("verdict", "sufficient")
        needs = v == "insufficient" and iteration < max_iter
        return {
            "iteration": iteration,
            "needs_more_retrieval": needs,
            "crag_finished": not needs,
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("evaluate_node LLM judge failed: %s", e)
        return {
            "iteration": iteration,
            "needs_more_retrieval": False,
            "crag_finished": True,
        }


# ========== Node 7: tool_executor ==========
async def tool_executor_node(state: AgentState) -> dict[str, Any]:
    """执行 LLM 在 answer 阶段请求的工具调用."""
    msgs = list(state.get("messages") or [])
    last_ai = next((m for m in reversed(msgs)
                    if hasattr(m, "type") and m.type == "ai"), None)
    tool_calls = getattr(last_ai, "tool_calls", None) or []

    if not tool_calls:
        return {"tool_results": []}

    results: list[dict[str, Any]] = []
    for tc in tool_calls:
        name = tc.get("name", "")
        args = tc.get("args", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        try:
            out = await execute_tool(name, args)
        except Exception as e:  # noqa: BLE001
            out = f"工具执行异常: {e}"
        results.append({"name": name, "args": args, "output": out})

    return {
        "tool_results": results,
        "tool_calls": [{"name": r["name"], "args": r["args"]} for r in results],
    }
