"""会话管理 API (阶段 3 接入 LangGraph checkpoint + SQLite)."""
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage, AIMessage

from app.agents.graph import get_compiled_graph
from app.agents.state import messages_to_lc
from app.models import db
from app.models.schemas import SessionCreate, SessionUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])


def _auto_title(content: str, max_chars: int = 30) -> str:
    """从首条 user 消息前 max_chars 字生成标题. 中文按字符算."""
    text = (content or "").strip().replace("\n", " ")
    if not text:
        return "新对话"
    if len(text) > max_chars:
        return text[:max_chars] + "…"
    return text


@router.get("")
async def list_sessions(limit: int = 50) -> dict:
    sessions = db.session_list(limit=limit)
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict:
    """返回会话 + 消息历史."""
    session = db.session_get(session_id)
    if session is None:
        # 可能还没消息, 但 LangGraph checkpoint 里有. 试一下
        pass
    messages = db.message_list_by_session(session_id)
    return {
        "session": session or {"id": session_id, "title": None, "message_count": 0},
        "messages": messages,
    }


@router.patch("/{session_id}")
async def update_session(session_id: str, body: SessionUpdate) -> dict:
    """更新会话元信息 (目前只支持 title). 字段为 None 时不更新."""
    existing = db.session_get(session_id)
    if existing is None:
        raise HTTPException(404, detail=f"Session {session_id} not found")

    new_title = body.title
    if new_title is not None:
        # 长度限制, 避免存储过大
        new_title = new_title.strip()[:200] or None

    db.session_upsert(session_id, title=new_title)
    updated = db.session_get(session_id) or {"id": session_id, "title": new_title, "message_count": 0}
    return {"session": updated}


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict:
    """删除会话. SQLite + LangGraph checkpoint 一并清."""
    db.session_delete(session_id)
    # LangGraph checkpoint 删: 用其内部 API
    try:
        graph = await get_compiled_graph()
        checkpointer = graph.checkpointer  # AsyncSqliteSaver
        if hasattr(checkpointer, "adelete_thread"):
            await checkpointer.adelete_thread(session_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("LangGraph checkpoint delete failed for %s: %s", session_id, e)
    return {"session_id": session_id, "deleted": True}


@router.post("")
async def create_session(body: SessionCreate) -> dict:
    """新建会话. 返回 session_id, 供后续 chat 使用.

    title 留空时, chat 端点会在首条 user 消息时自动生成.
    """
    session_id = uuid.uuid4().hex
    db.session_upsert(session_id, title=body.title)
    return {"session_id": session_id, "title": body.title}
