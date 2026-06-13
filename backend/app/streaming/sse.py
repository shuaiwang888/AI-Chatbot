"""SSE generator 辅助. 提供 ping / retry / error 处理."""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from app.streaming.events import sse_format, sse_heartbeat

logger = logging.getLogger(__name__)


async def heartbeat_pinger(interval: float = 15.0) -> AsyncIterator[str]:
    """无限流式发送 SSE 注释保活. 配合 `asyncio.Queue` 一起使用."""
    try:
        while True:
            await asyncio.sleep(interval)
            yield sse_heartbeat()
    except asyncio.CancelledError:
        return


async def event_stream(
    queue: asyncio.Queue[tuple[str, dict] | None],
) -> AsyncIterator[str]:
    """从 asyncio.Queue 读取事件并序列化为 SSE. 收到 None 表示结束."""
    while True:
        item = await queue.get()
        if item is None:
            break
        event, data = item
        yield sse_format(event, data)


def safe_json(data: dict) -> str:
    """防御性 JSON 序列化."""
    return json.dumps(data, ensure_ascii=False, default=str)
