"""MiniMax-M3 provider (OpenAI 兼容协议).

通过 AsyncOpenAI(base_url=...) 调用 MiniMax 端点.
所有 OpenAI 兼容的 provider (Qwen / DeepSeek / 自部署 vLLM 等) 都可以复用本类,
只需换 base_url 和 model.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.base import (
    AbstractLLM,
    LLMChunk,
    LLMMessage,
    LLMResponse,
    ToolSpec,
)

logger = logging.getLogger(__name__)


def _to_openai_messages(messages: list[LLMMessage]) -> list[dict[str, Any]]:
    """转换为本类消息 -> OpenAI ChatMessage dict."""
    out: list[dict[str, Any]] = []
    for m in messages:
        d: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.name:
            d["name"] = m.name
        if m.tool_call_id:
            d["tool_call_id"] = m.tool_call_id
        if m.tool_calls:
            d["tool_calls"] = m.tool_calls
        out.append(d)
    return out


def _to_openai_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    """ToolSpec -> OpenAI tools format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


class OpenAICompatibleLLM(AbstractLLM):
    """OpenAI 兼容协议的通用 LLM (MiniMax / Qwen / DeepSeek / 自部署 vLLM).

    之所以不叫 MiniMaxLLM: 因为实现是通用的, 通过 (base_url, model) 切换 provider.
    factory.py 用 settings 决定具体配置.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        provider_name: str = "openai-compat",
        timeout: float = 60.0,
    ) -> None:
        self.name = provider_name
        self.model = model
        # 关键: trust_env=False 强制不走系统代理 (urllib.getproxies() / macOS System Preferences)
        # 否则 httpx 会尝试走 127.0.0.1:7897, 若该端口代理服务不可用, TLS 握手会挂在
        # start_tls 阶段报 "Connection error"
        import httpx as _httpx
        _http_client = _httpx.AsyncClient(
            trust_env=False,
            timeout=timeout,
        )
        self.client = AsyncOpenAI(
            api_key=api_key or "EMPTY",
            base_url=base_url,
            timeout=timeout,
            max_retries=0,  # tenacity 自管
            http_client=_http_client,
        )
        logger.info(
            "LLM client init: provider=%s base_url=%s model=%s (trust_env=False, no proxy)",
            provider_name, base_url, model,
        )

    async def aclose(self) -> None:
        await self.client.close()

    @retry(
        retry=retry_if_exception_type((APITimeoutError, RateLimitError, APIError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        params: dict[str, Any] = {
            "model": self.model,
            "messages": _to_openai_messages(messages),
            "temperature": temperature,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if tools:
            params["tools"] = _to_openai_tools(tools)
        params.update(kwargs)

        try:
            resp = await self.client.chat.completions.create(**params)
        except (APITimeoutError, RateLimitError, APIError) as e:
            logger.warning("LLM chat retry: %s", e)
            raise
        except Exception as e:
            raise LLMUnavailableError(
                f"LLM call failed: {e}", retryable=False
            ) from e

        choice = resp.choices[0]
        msg = choice.message
        usage = (
            {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens,
            }
            if resp.usage
            else {}
        )
        return LLMResponse(
            content=msg.content or "",
            tool_calls=[tc.model_dump() for tc in (msg.tool_calls or [])],
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            raw=resp,
        )

    @retry(
        retry=retry_if_exception_type((APITimeoutError, RateLimitError, APIError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def stream_chat(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMChunk]:
        params: dict[str, Any] = {
            "model": self.model,
            "messages": _to_openai_messages(messages),
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if tools:
            params["tools"] = _to_openai_tools(tools)
        params.update(kwargs)

        try:
            stream = await self.client.chat.completions.create(**params)
            async for ev in stream:
                if not ev.choices:
                    # 最终 usage chunk (choices 为空, 只有 usage)
                    if getattr(ev, "usage", None):
                        yield LLMChunk(
                            content="",
                            finish_reason="stop",
                            usage={
                                "prompt_tokens": ev.usage.prompt_tokens,
                                "completion_tokens": ev.usage.completion_tokens,
                                "total_tokens": ev.usage.total_tokens,
                            },
                        )
                    continue
                choice = ev.choices[0]
                delta = choice.delta
                tc_dumps: list[dict[str, Any]] = []
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        tc_dumps.append(tc.model_dump(exclude_unset=True))
                yield LLMChunk(
                    content=delta.content or "",
                    tool_calls=tc_dumps,
                    finish_reason=choice.finish_reason,
                )
        except (APITimeoutError, RateLimitError, APIError) as e:
            logger.warning("LLM stream retry: %s", e)
            raise
        except Exception as e:
            raise LLMUnavailableError(
                f"LLM stream failed: {e}", retryable=False
            ) from e

    async def health_check(self) -> bool:
        """极简探活: 1 token 补全."""
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                temperature=0,
            )
            return bool(resp.choices)
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM health check failed: %s", e)
            return False


# 向后兼容别名: 早期代码可能用 MiniMaxLLM
MiniMaxLLM = OpenAICompatibleLLM
