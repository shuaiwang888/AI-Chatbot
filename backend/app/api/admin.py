"""Admin / 运维端点. 用于手动修复持久化状态 / 触发快照.

⚠️ 当前 API 完全开放 (单用户系统, 无鉴权). 如果将来加多用户, 这里需要
   X-Admin-Token 之类的鉴权.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.services.persist import persist_status, push_to_hf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/push")
async def trigger_push() -> dict:
    """手动 trigger 一次 push. 用于:
    - 修复 push 卡死 (clear pending_push flag)
    - 手动快照当前 /data 到 Dataset
    - 验证持久化链路
    """
    status = persist_status()
    if not status["enabled"]:
        raise HTTPException(503, "Persistence not enabled (HF_PERSIST_REPO/HF_TOKEN missing)")

    # 强制清掉 stuck flag
    from app.services import persist as p
    p._state["pending_push"] = False  # type: ignore[index]

    await push_to_hf()

    new_status = persist_status()
    logger.info("admin/push invoked; status before=%s, after=%s", status, new_status)
    return {"status": "ok", "persist": new_status}


@router.get("/status")
async def admin_status() -> dict:
    """返回更详细的持久化状态 (供 debug)."""
    from app.services import persist as p

    return {
        "persist": persist_status(),
        "background_tasks_pending": len(p._background_tasks),  # type: ignore[arg-type]
    }
