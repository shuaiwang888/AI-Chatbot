"""健康检查 + 探活."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.config import settings
from app.deps import get_llm, persist_status
from app.models.schemas import HealthStatus

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/healthz", response_model=HealthStatus)
async def healthz() -> HealthStatus:
    """Liveness 探针. 不检查外部依赖, 永远返回 ok (只要进程在)."""
    return HealthStatus(
        status="ok",
        llm=True,  # 进程在即代表 LLM 单例已建 (或尝试过)
        persist=persist_status(),
        chroma=False,  # 阶段 2 接入
        version=settings.app_version,
    )


@router.get("/readyz", response_model=HealthStatus)
async def readyz(request: Request) -> HealthStatus:
    """Readiness 探针. 检查 LLM 实际可达 + Chroma + 持久化模式."""
    llm_ok = False
    try:
        llm = get_llm()
        llm_ok = await llm.health_check()
    except Exception as e:  # noqa: BLE001
        logger.warning("readyz: LLM health check error: %s", e)

    chroma_ok = False
    try:
        from app.services.vector_store import get_chroma
        _, coll, _ = get_chroma()
        chroma_ok = coll.count() >= 0  # 任意 count 都不报错即说明连接通
    except Exception as e:  # noqa: BLE001
        logger.warning("readyz: Chroma check error: %s", e)

    persist = persist_status()
    overall = "ok" if (llm_ok and chroma_ok) else "degraded"

    return HealthStatus(
        status=overall,
        llm=llm_ok,
        persist=persist,
        chroma=chroma_ok,
        version=settings.app_version,
    )
