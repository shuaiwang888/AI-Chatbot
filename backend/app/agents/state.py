"""AgentState - LangGraph 跨节点状态.

使用 TypedDict 而不是 Pydantic, 因为 LangGraph 内置 add_messages reducer
需要 Annotated[Sequence[BaseMessage], add_messages] 这样的类型签名.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Sequence, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from app.services.vector_store import RetrievalHit


RouteDecision = Literal["direct", "retrieve", "multi_step"]


class AgentState(TypedDict, total=False):
    """LangGraph 跨节点状态. total=False 让所有字段可选, 各 node 自行填充."""

    # ===== 基础 =====
    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str
    user_id: str
    locale: str  # "zh" | "en"

    # ===== 路由 =====
    route_decision: RouteDecision
    query_rewritten: str  # 改写后的查询
    plan: list[str]  # 多步拆解的子任务

    # ===== 检索 =====
    retrieved: list[RetrievalHit]
    reranked: list[RetrievalHit]
    retrieved_doc_ids: list[str]  # 命中 doc 列表 (用于 SSE retrieval 事件)

    # ===== 引用 =====
    citations: list[dict[str, Any]]  # [{doc_id, page, snippet, score, source}]

    # ===== 工具 =====
    tool_calls: list[dict[str, Any]]  # 工具调用历史
    tool_results: list[dict[str, Any]]  # 工具结果摘要

    # ===== CRAG 自校正 =====
    iteration: int
    max_iterations: int
    relevance_score: float  # top-1 rerank score, 0-1
    relevance_verdict: Literal["relevant", "ambiguous", "irrelevant"]
    needs_more_retrieval: bool
    crag_finished: bool

    # ===== 元数据 =====
    elapsed_ms: int
    final_answer: str
    error: str | None


# ========== State helpers ==========
def empty_state_for(session_id: str, user_id: str = "default", locale: str = "zh") -> AgentState:
    from app.config import settings

    return AgentState(
        messages=[],
        session_id=session_id,
        user_id=user_id,
        locale=locale,
        route_decision="retrieve",
        query_rewritten="",
        plan=[],
        retrieved=[],
        reranked=[],
        retrieved_doc_ids=[],
        citations=[],
        tool_calls=[],
        tool_results=[],
        iteration=0,
        max_iterations=settings.crag_max_iterations,
        relevance_score=0.0,
        relevance_verdict="ambiguous",
        needs_more_retrieval=False,
        crag_finished=False,
        elapsed_ms=0,
        final_answer="",
        error=None,
    )


def messages_to_lc(messages: list[dict[str, Any]] | list[BaseMessage]) -> list[BaseMessage]:
    """业务侧 dict 消息列表 (来自 SQLite) 转为 LangChain BaseMessage 列表."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    out: list[BaseMessage] = []
    for m in messages:
        if hasattr(m, "type"):
            out.append(m)  # 已经是 BaseMessage
            continue
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            extra = {}
            if m.get("tool_calls"):
                extra["tool_calls"] = m["tool_calls"]
            out.append(AIMessage(content=content, **extra))
        elif role == "tool":
            out.append(ToolMessage(
                content=content,
                tool_call_id=m.get("tool_call_id", ""),
            ))
    return out
