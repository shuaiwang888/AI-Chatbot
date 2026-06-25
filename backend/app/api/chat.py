"""阶段 3 chat 端点: 接 LangGraph agent, 完整 AG-UI 9 类事件.

事件流顺序 (典型):
  thinking        {content: "用户在询问财务数据..."}
  agent_step      {node: "route", status: "running"}
  agent_step      {node: "route", status: "done"}
  retrieval       {doc_ids: [...], scores: [...]}
  citation        {doc_id, page, snippet, score}
  token           {content: "..."}      (多次, 流式)
  agent_step      {node: "evaluate", status: "done"}
  done            {usage, total_ms}
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from app.agents.graph import get_compiled_graph
from app.agents.nodes import answer_node_stream
from app.agents.state import empty_state_for
from app.config import settings
from app.llm.base import LLMMessage
from app.llm.factory import get_llm
from app.models import db
from app.models.schemas import ChatRequest, ChatResponse
from app.services.persist import schedule_push
from app.streaming.events import (
    sse_done,
    sse_error,
    sse_format,
    EV_AGENT_STEP,
    EV_CITATION,
    EV_DONE,
    EV_ERROR,
    EV_PROGRESS,
    EV_RETRIEVAL,
    EV_THINKING,
    EV_TOKEN,
    EV_TOOL_CALL,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# 持引用防 GC: 后台算 title 的任务可能跑 1-2s, 中间被 GC 会丢更新
_deferred_tasks: set[asyncio.Task] = set()


# ========== 兜底: 阶段 1 简单直答 (route=direct / 无 agent) ==========
_FALLBACK_SYSTEM = (
    "你是一个有帮助的中文 AI 助手。"
    "回答应简洁、准确、礼貌。如不知道答案请直接说明。"
)


@router.post("", response_model=ChatResponse)
async def chat_simple(req: ChatRequest) -> ChatResponse:
    """非流式 chat: 跑完整 agent 但收集完整结果再返."""
    started = time.time()
    try:
        final_state, events_log = await _run_agent(req)
    except Exception as e:  # noqa: BLE001
        logger.exception("chat failed")
        raise HTTPException(status_code=502, detail=str(e)) from e

    answer = final_state.get("final_answer") or "(无回答)"
    return ChatResponse(
        session_id=req.session_id,
        message_id=uuid.uuid4().hex,
        content=answer,
        citations=final_state.get("citations", []),
        agent_steps=events_log,
        usage={},  # 阶段 3 暂不聚合
        total_ms=int((time.time() - started) * 1000),
    )


@router.post("/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """SSE 流式 chat: 完整 AG-UI 事件."""
    return StreamingResponse(
        _agent_event_stream(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # 关闭 nginx 缓冲
        },
    )


# ========== 核心: 跑 agent + 产生 SSE 事件 ==========
async def _agent_event_stream(req: ChatRequest) -> AsyncIterator[str]:
    """驱动 agent + 把过程映射为 AG-UI 事件."""
    queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue(maxsize=256)

    async def emit(event: str, data: dict) -> None:
        await queue.put((event, data))

    async def runner() -> None:
        try:
            await _run_agent(req, emit=emit)
        except Exception as e:  # noqa: BLE001
            logger.exception("agent runner failed")
            await emit(EV_ERROR, {"code": "agent_failed", "message": str(e), "retryable": True})
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())

    # 启动心跳
    started = time.time()
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                # 心跳
                yield ": keepalive\n\n"
                continue
            if item is None:
                break
            event, data = item
            yield sse_format(event, data)
    finally:
        if not task.done():
            task.cancel()

    # done
    yield sse_done(total_ms=int((time.time() - started) * 1000))


async def _run_agent(
    req: ChatRequest,
    emit=None,  # async callable | None
) -> tuple[dict, list[dict]]:
    """执行 agent. emit 可选, 用于 SSE 推送中间事件.

    Returns:
        (final_state_dict, events_log)
    """
    started = time.time()
    events_log: list[dict] = []

    async def _emit(event: str, data: dict) -> None:
        if emit is not None:
            await emit(event, data)
        events_log.append({"event": event, "data": data, "ts": time.time()})

    # 1. 加载历史消息
    history_rows = db.message_list_by_session(req.session_id, limit=20)
    from app.agents.state import messages_to_lc
    history_msgs = messages_to_lc([
        {"role": r["role"], "content": r["content"]}
        for r in history_rows
    ])

    # 2. 添加本轮 user message
    new_user_msg = HumanMessage(content=req.message)
    history_msgs.append(new_user_msg)

    # 3. 初始化 state
    state = empty_state_for(req.session_id, locale=req.locale)
    state["messages"] = history_msgs

    # 4. 记录 user message 到 SQLite
    #    - user message 同步写 (审计需要, 不能丢)
    #    - session 已有 title → 直接 upsert
    #    - session 还没有 title → 用 asyncio.create_task 后台算, 不阻塞首字
    #      (注: 实际 _auto_title 是字符串截断, 不是 LLM, 收益微小; 但作为
    #       防御性编程, 把所有非关键路径工作都移出 hot path)
    existing = db.session_get(req.session_id)
    if existing is not None and existing.get("title"):
        db.session_upsert(req.session_id, title=None)  # 仅 updated_at 刷新
    else:
        # 首次消息: 先空 title 写一行占位, 后台异步算 title 后再 upsert 更新
        db.session_upsert(req.session_id, title=None)

        async def _deferred_title() -> None:
            try:
                from app.api.sessions import _auto_title
                title = _auto_title(req.message)
                db.session_upsert(req.session_id, title=title)
            except Exception as e:  # noqa: BLE001
                logger.warning("Deferred auto_title failed: %s", e)

        # 持引用防 GC
        task = asyncio.create_task(_deferred_title())
        _deferred_tasks.add(task)
        task.add_done_callback(_deferred_tasks.discard)
    db.message_insert({
        "id": uuid.uuid4().hex,
        "session_id": req.session_id,
        "role": "user",
        "content": req.message,
    })

    # 5. 跑 LangGraph (retrieval loop)
    try:
        graph = await get_compiled_graph()
    except Exception as e:  # noqa: BLE001
        await _emit(EV_ERROR, {"code": "graph_init_failed", "message": str(e)})
        raise

    config = {"configurable": {"thread_id": req.session_id}}
    final_state: dict = dict(state)

    # 直接用 graph.ainvoke, 拿最终 state
    try:
        result = await graph.ainvoke(state, config=config)
        final_state.update(result)
    except Exception as e:  # noqa: BLE001
        logger.exception("graph.ainvoke failed")
        await _emit(EV_ERROR, {"code": "graph_failed", "message": str(e)})
        raise

    # 6. 推送检索事件
    if final_state.get("retrieved_doc_ids"):
        await _emit(EV_RETRIEVAL, {
            "doc_ids": final_state["retrieved_doc_ids"],
            "count": len(final_state.get("retrieved", [])),
            "scores": [round(h.score, 4) for h in final_state.get("retrieved", [])[:10]],
        })
    if final_state.get("citations"):
        await _emit(EV_PROGRESS, {"pct": 60, "label": "已生成引用, 正在回答..."})

    # 7. 跑 answer 流式 (直接调 LLM, 不走 graph)
    await _emit(EV_AGENT_STEP, {"node": "answer", "status": "running"})

    async def _on_token(content: str) -> None:
        await _emit(EV_TOKEN, {"content": content})

    async def _on_citation(c: dict) -> None:
        await _emit(EV_CITATION, c)

    async def _on_thinking(content: str) -> None:
        await _emit(EV_THINKING, {"content": content})

    answer_update = await answer_node_stream(
        final_state,
        on_token=_on_token,
        on_citation=_on_citation,
        on_thinking=_on_thinking,
    )
    final_state.update(answer_update)

    await _emit(EV_AGENT_STEP, {"node": "answer", "status": "done"})
    await _emit(EV_PROGRESS, {"pct": 100, "label": "完成"})

    # 8. 记录 assistant message 到 SQLite
    elapsed = int((time.time() - started) * 1000)
    db.message_insert({
        "id": uuid.uuid4().hex,
        "session_id": req.session_id,
        "role": "assistant",
        "content": final_state.get("final_answer", ""),
        "citations": final_state.get("citations", []),
    })

    # 9. ⚠️ 关键: 把 session/message 写完 → 调度 persist push (5s debounce).
    #    不调的话: 写本地 /data/sqlite/app.db → Space 重启 /data 临时卷清空 →
    #    历史对话全丢. 5s debounce 够合并同一 session 的 user+assistant 写入.
    try:
        await schedule_push()
    except Exception as e:  # noqa: BLE001
        logger.warning("schedule_push after chat failed: %s", e)

    return final_state, events_log
