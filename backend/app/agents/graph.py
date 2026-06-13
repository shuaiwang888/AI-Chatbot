"""LangGraph StateGraph 装配 + 编译.

设计: 图只负责"检索循环" (route → query_rewrite → retrieve → rerank → evaluate).
answer 流式生成由 chat 端点直接驱动 (answer_node_stream + asyncio.Queue),
这样 SSE token 流不依赖 astream_events 的复杂性.

流程图:

    START
      │
      ▼
   route ─── direct ───────────────────────────────► END
      │
      ▼
   query_rewrite ──► retrieve ──► rerank ──► evaluate
                                                   │
                       ┌──── (needs_more, iter<max) ───┐
                       │                              │
                       └──── (relevant/irrelevant/max) ┘
                              │
                              ▼
                             END
"""
from __future__ import annotations

import logging

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    evaluate_node,
    query_rewrite_node,
    rerank_node,
    retrieve_node,
    route_node,
)
from app.agents.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)


# ========== 边决策 ==========
def _after_route(state: AgentState) -> str:
    decision = state.get("route_decision", "retrieve")
    if decision == "direct":
        return END
    return "query_rewrite"


def _after_evaluate(state: AgentState) -> str:
    """evaluate 后: needs_more + iter<max -> 回 retrieve; 否则 END."""
    if state.get("needs_more_retrieval", False):
        return "query_rewrite"
    return END


# ========== 编译 ==========
def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("route", route_node)
    g.add_node("query_rewrite", query_rewrite_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("rerank", rerank_node)
    g.add_node("evaluate", evaluate_node)

    g.add_edge(START, "route")
    g.add_conditional_edges(
        "route", _after_route,
        {END: END, "query_rewrite": "query_rewrite"},
    )
    g.add_edge("query_rewrite", "retrieve")
    g.add_edge("retrieve", "rerank")
    g.add_edge("rerank", "evaluate")
    g.add_conditional_edges(
        "evaluate", _after_evaluate,
        {END: END, "query_rewrite": "query_rewrite"},
    )

    return g


# ========== 编译产物 (带 checkpointer) ==========
_compiled = None
_saver_cm = None
_compiled_loop = None


async def get_compiled_graph():
    """懒加载 + 单例 (按 event loop 隔离)."""
    global _compiled, _saver_cm, _compiled_loop
    import asyncio
    current_loop = asyncio.get_running_loop()

    if _compiled is not None and _compiled_loop is current_loop:
        return _compiled

    if _compiled is not None:
        await close_checkpointer()

    g = _build_graph()
    _saver_cm = AsyncSqliteSaver.from_conn_string(str(settings.langgraph_db_path))
    saver = await _saver_cm.__aenter__()
    _compiled = g.compile(checkpointer=saver)
    _compiled_loop = current_loop
    logger.info(
        "LangGraph compiled with AsyncSqliteSaver at %s",
        settings.langgraph_db_path,
    )
    return _compiled


async def close_checkpointer() -> None:
    global _compiled, _saver_cm, _compiled_loop
    _compiled = None
    _compiled_loop = None
    if _saver_cm is not None:
        try:
            await _saver_cm.__aexit__(None, None, None)
        except Exception as e:  # noqa: BLE001
            logger.warning("AsyncSqliteSaver close failed: %s", e)
        _saver_cm = None
