"""AG-UI 兼容事件类型常量 + helper.

AG-UI 协议: https://docs.ag-ui.com (CopilotKit 提出, 2025 起逐步成为 agent UI 事件标准)

我们的 9 类事件:
- thinking: Agent 推理过程 / 决策说明
- agent_step: 节点生命周期 (running / done / error)
- retrieval: 命中文档 ID + 分数
- tool_call: 工具调用详情
- token: LLM delta
- citation: 引用片段
- progress: 整体进度 0-100
- done: 结束
- error: 错误
"""
from __future__ import annotations

import json
from typing import Any, Literal

# 事件类型常量 (防止拼写错)
EV_THINKING = "thinking"
EV_AGENT_STEP = "agent_step"
EV_RETRIEVAL = "retrieval"
EV_TOOL_CALL = "tool_call"
EV_TOKEN = "token"
EV_CITATION = "citation"
EV_PROGRESS = "progress"
EV_DONE = "done"
EV_ERROR = "error"

ALL_EVENTS: tuple[str, ...] = (
    EV_THINKING, EV_AGENT_STEP, EV_RETRIEVAL, EV_TOOL_CALL,
    EV_TOKEN, EV_CITATION, EV_PROGRESS, EV_DONE, EV_ERROR,
)


def sse_format(event: str, data: dict[str, Any]) -> str:
    """格式化为标准 SSE 双行: `event: <type>\\ndata: <json>\\n\\n`."""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def sse_heartbeat() -> str:
    """保活注释, 避免代理超时. 不属于事件, 不会触发前端 listener."""
    return ": keepalive\n\n"


def sse_done(usage: dict[str, int] | None = None, total_ms: int = 0) -> str:
    return sse_format(EV_DONE, {"usage": usage or {}, "total_ms": total_ms})


def sse_error(
    code: str,
    message: str,
    *,
    retryable: bool = False,
    detail: dict[str, Any] | None = None,
) -> str:
    return sse_format(
        EV_ERROR,
        {"code": code, "message": message, "retryable": retryable, "detail": detail or {}},
    )


# 节点名常量 (在 LangGraph 里用到, 统一在此声明)
NODE_ROUTE = "route"
NODE_QUERY_REWRITE = "query_rewrite"
NODE_RETRIEVE = "retrieve"
NODE_RERANK = "rerank"
NODE_TOOL = "tool_executor"
NODE_ANSWER = "answer"
NODE_EVALUATE = "evaluate"

ALL_NODES: tuple[str, ...] = (
    NODE_ROUTE, NODE_QUERY_REWRITE, NODE_RETRIEVE, NODE_RERANK,
    NODE_TOOL, NODE_ANSWER, NODE_EVALUATE,
)


NodeName = Literal[
    "route", "query_rewrite", "retrieve", "rerank",
    "tool_executor", "answer", "evaluate",
]
