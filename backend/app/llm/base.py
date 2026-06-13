"""LLM provider 抽象基类 + 数据类型.

设计原则:
- 与 LangChain / Pydantic AI 解耦, 业务代码只依赖本模块
- 流式 + 非流式接口都提供
- 支持 tool calling (OpenAI 兼容格式)
- 内置指数退避重试
"""
from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMMessage:
    """与 OpenAI ChatMessage 兼容的轻量消息结构."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None  # assistant 消息的 tool_calls


@dataclass
class ToolSpec:
    """OpenAI 兼容的 function-calling 工具规格."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass
class LLMChunk:
    """流式响应的单个 chunk."""

    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, int] | None = None  # 仅最后一个 chunk 携带


@dataclass
class LLMResponse:
    """非流式响应的完整结果."""

    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None  # provider 原始响应 (调试用)


class AbstractLLM(abc.ABC):
    """LLM provider 抽象基类."""

    name: str = "abstract"

    @abc.abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """非流式聊天."""

    @abc.abstractmethod
    def stream_chat(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMChunk]:
        """流式聊天. 必须返回 AsyncIterator (async generator)."""
        # 抽象方法必须 yield 一次占位, 否则子类可能写错
        # 但子类实现是 async def + yield, 所以这里只是签名
        raise NotImplementedError
        yield  # type: ignore[unreachable]  # pragma: no cover

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """探活: 极简调用 (如 1 token completion)."""

    @abc.abstractmethod
    async def aclose(self) -> None:
        """关闭底层 client (httpx / AsyncOpenAI 等)."""
