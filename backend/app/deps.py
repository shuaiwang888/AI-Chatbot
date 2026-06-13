"""应用级单例 (LLM, embedder, vector store, etc.) 的获取与生命周期.

被 main.py lifespan 和各 router 复用. 保持依赖注入简单, 不引入 DI 框架.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.config import settings
from app.llm.base import AbstractLLM

if TYPE_CHECKING:
    from app.services.persist import persist_status

logger = logging.getLogger(__name__)


def get_llm() -> AbstractLLM:
    """从工厂取 LLM 单例. 失败时抛出 LLMUnavailableError."""
    from app.llm.factory import get_llm as _factory_get_llm
    return _factory_get_llm()


async def close_llm() -> None:
    from app.llm.factory import close_llm as _factory_close
    await _factory_close()


def persist_status() -> dict:
    from app.services.persist import persist_status as _ps
    return _ps()
