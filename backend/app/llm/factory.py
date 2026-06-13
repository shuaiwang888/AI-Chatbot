"""LLM 工厂: 根据 settings.llm_provider 选择 provider.

新增 provider 的步骤:
1. 在 base.py 实现一个新类 (或复用 OpenAICompatibleLLM)
2. 在本文件 _PROVIDERS 加一行
3. 在 .env.example 暴露新 env
"""
from __future__ import annotations

import logging
from functools import lru_cache

from app.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.base import AbstractLLM
from app.llm.minimax import OpenAICompatibleLLM

logger = logging.getLogger(__name__)


def _build_minimax() -> OpenAICompatibleLLM:
    key = settings.minimax_api_key.get_secret_value()
    if not key:
        raise LLMUnavailableError(
            "MINIMAX_API_KEY is empty. Set it in .env or HF Space secrets.",
            code="llm_api_key_missing",
        )
    return OpenAICompatibleLLM(
        api_key=key,
        base_url=settings.minimax_base_url,
        model=settings.minimax_model,
        provider_name="minimax",
    )


def _build_openai() -> OpenAICompatibleLLM:
    key = settings.openai_api_key.get_secret_value()
    if not key:
        raise LLMUnavailableError(
            "OPENAI_API_KEY is empty.",
            code="llm_api_key_missing",
        )
    return OpenAICompatibleLLM(
        api_key=key,
        base_url="https://api.openai.com/v1",
        # 允许用 env 覆盖 model (openai_model), 没设则用 gpt-4o-mini
        model=getattr(settings, "openai_model", "gpt-4o-mini"),
        provider_name="openai",
    )


def _build_qwen() -> OpenAICompatibleLLM:
    key = settings.qwen_api_key.get_secret_value()
    if not key:
        raise LLMUnavailableError(
            "QWEN_API_KEY is empty.",
            code="llm_api_key_missing",
        )
    return OpenAICompatibleLLM(
        api_key=key,
        # 阿里百炼 OpenAI 兼容端点
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model=getattr(settings, "qwen_model", "qwen-max"),
        provider_name="qwen",
    )


def _build_anthropic() -> AbstractLLM:
    """占位: Anthropic SDK 原生协议, 暂未实现, 留 hook."""
    raise NotImplementedError(
        "Anthropic provider not yet implemented. "
        "Use openai-compatible via OpenRouter or implement anthropic.AsyncAnthropic wrapper."
    )


_PROVIDERS = {
    "minimax": _build_minimax,
    "openai": _build_openai,
    "qwen": _build_qwen,
    "anthropic": _build_anthropic,
}


@lru_cache(maxsize=1)
def get_llm() -> AbstractLLM:
    """单例 LLM. 在 lifespan 中调用 + 缓存."""
    builder = _PROVIDERS.get(settings.llm_provider)
    if builder is None:
        raise LLMUnavailableError(
            f"Unknown llm_provider: {settings.llm_provider}",
            code="llm_provider_unknown",
        )
    logger.info("Initializing LLM provider: %s", settings.llm_provider)
    return builder()


async def close_llm() -> None:
    """关闭 LLM 客户端. lifespan shutdown 时调用."""
    try:
        llm = get_llm()
    except Exception:  # noqa: BLE001
        return
    await llm.aclose()
    get_llm.cache_clear()
