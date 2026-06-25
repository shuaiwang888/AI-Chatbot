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
from app.services.persist import push_to_hf

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
    """删除会话. SQLite + LangGraph checkpoint + HF Dataset 一并清.

    删除顺序 (重要):
    1) 先删 LangGraph checkpoint — 失败抛 500, session 行保留 (用户能重试)
    2) 再删 SQLite session 行 (FK CASCADE 自动删 messages)
    3) 最后 await push_to_hf() 同步推 HF Dataset, 配合 persist.py 的
       delete_patterns, 让远端 sqlite/langgraph.db 同步清理.
       用同步 push (非 schedule_push debounce) 因为:
       - 与 ingestion.delete_document 保持一致
       - 用户已点删除, 期望"彻底消失", 5s 窗口期崩了会留幽灵
       - session 体积小 (langgraph.db 单文件), push 比 doc 快很多

    历史坑:
    - 旧版先 db.session_delete 后 adelete_thread, checkpoint 失败时
      元数据已删, checkpoint 还在 → "删了但聊天记录还在"
    - 旧版没 schedule_push, 远端 sqlite 永远不更新 → 下次冷启动又冒出来
    - 旧版用 schedule_push debounce, 5s 内崩了 + 远端残留
    """
    # 1) LangGraph checkpoint 先删 (失败抛错, 不进下一步)
    try:
        graph = await get_compiled_graph()
        checkpointer = graph.checkpointer  # AsyncSqliteSaver
        if hasattr(checkpointer, "adelete_thread"):
            await checkpointer.adelete_thread(session_id)
        else:
            # 显式拒绝, 避免静默跳过
            raise RuntimeError(
                "Checkpointer does not support adelete_thread; "
                "langgraph version may be too old."
            )
    except Exception as e:  # noqa: BLE001
        logger.exception("LangGraph checkpoint delete failed for %s", session_id)
        raise HTTPException(
            status_code=500,
            detail=f"Checkpoint delete failed: {e}",
        ) from e

    # 2) SQLite session 行 (FK CASCADE 自动删 messages)
    db.session_delete(session_id)

    # 3) 同步推 HF Dataset (与 ingestion.delete_document 保持一致)
    push_ok = await push_to_hf()
    if not push_ok:
        logger.warning(
            "Delete ok locally but persist push failed for session %s. "
            "See /readyz persist.last_error. "
            "Local data is gone but HF Dataset remote may still have ghost files "
            "until next successful push or manual cleanup.",
            session_id,
        )

    return {"session_id": session_id, "deleted": True}


@router.post("")
async def create_session(body: SessionCreate) -> dict:
    """新建会话. 返回 session_id, 供后续 chat 使用.

    title 留空时, chat 端点会在首条 user 消息时自动生成.
    """
    session_id = uuid.uuid4().hex
    db.session_upsert(session_id, title=body.title)
    return {"session_id": session_id, "title": body.title}
